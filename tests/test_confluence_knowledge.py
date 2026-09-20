"""Confluence knowledge loading without making live network calls."""

from __future__ import annotations

import base64
import urllib.parse

import pytest

from agents import confluence_knowledge
from agents.confluence_knowledge import (
    ConfluenceConfig,
    ConfluenceKnowledgeError,
    confluence_config_from_env,
    fetch_confluence_sections,
)


def _config(**changes) -> ConfluenceConfig:  # noqa: ANN003
    values = {
        "base_url": "https://example.atlassian.net/wiki",
        "api_token": "test-token",
        "email": "bot@example.com",
        "space_keys": ("GTM",),
        "page_limit": 1,
        "max_pages": 10,
    }
    values.update(changes)
    return ConfluenceConfig(**values)


def test_cloud_auth_uses_email_and_token() -> None:
    expected = base64.b64encode(b"bot@example.com:test-token").decode()
    assert _config().authorization == f"Basic {expected}"


def test_data_center_pat_uses_bearer_auth() -> None:
    assert _config(email="").authorization == "Bearer test-token"


def test_allowlisted_space_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONFLUENCE_BASE_URL", "https://example.atlassian.net/wiki")
    monkeypatch.setenv("CONFLUENCE_API_TOKEN", "token")
    monkeypatch.delenv("CONFLUENCE_SPACE_KEYS", raising=False)
    with pytest.raises(ConfluenceKnowledgeError, match="CONFLUENCE_SPACE_KEYS"):
        confluence_config_from_env()


def _page(page_id: str, title: str) -> dict:
    return {
        "id": page_id,
        "title": title,
        "space": {"key": "GTM"},
        "version": {"when": "2026-09-11T00:00:00Z"},
        "body": {
            "storage": {
                "value": (
                    "<h1>Approvals</h1><p>Up to 15% needs manager "
                    "approval.</p><h2>Exceptions</h2>"
                    "<ul><li>Public sector goes to Deal Desk.</li></ul>"
                )
            }
        },
        "_links": {
            "base": "https://example.atlassian.net/wiki",
            "webui": f"/spaces/GTM/pages/{page_id}",
        },
    }


def test_pages_are_paginated_by_cursor_and_split_by_heading(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cloud ignores `start` on this endpoint, so only the next link advances."""
    calls: list[str] = []
    batches = {
        "": {
            "results": [_page("123", "Discount policy")],
            "limit": 1,
            "_links": {
                "base": "https://example.atlassian.net/wiki",
                "next": "/rest/api/content/search?cursor=abc",
            },
        },
        "cursor=abc": {
            # A replayed row must not be indexed twice.
            "results": [_page("123", "Discount policy"), _page("456", "Quoting")],
            "limit": 1,
            "_links": {},
        },
    }

    def fake_request(config, url):  # noqa: ANN001
        calls.append(url)
        return batches["cursor=abc" if "cursor=abc" in url else ""]

    monkeypatch.setattr(confluence_knowledge, "_request_url", fake_request)
    sections = fetch_confluence_sections(_config())

    assert len(calls) == 2
    assert calls[1] == "https://example.atlassian.net/wiki/rest/api/content/search?cursor=abc"
    assert [(row["document_id"], row["section"]) for row in sections] == [
        ("123", "Approvals"),
        ("123", "Approvals > Exceptions"),
        ("456", "Approvals"),
        ("456", "Approvals > Exceptions"),
    ]
    assert "15%" in sections[0]["content"]
    assert sections[1]["source"].endswith("/spaces/GTM/pages/123")


def test_cql_never_searches_outside_allowlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = ""

    def fake_request(config, url):  # noqa: ANN001
        nonlocal seen
        seen = urllib.parse.unquote_plus(url)
        return {"results": [], "limit": 100}

    monkeypatch.setattr(confluence_knowledge, "_request_url", fake_request)
    fetch_confluence_sections(_config(space_keys=("GTM", "DEALDESK"), page_limit=100))
    assert 'space in ("GTM", "DEALDESK")' in seen
    assert "type=page" in seen


def test_faq_search_does_not_read_dummy_docs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "agents.faq_knowledge.confluence_config_from_env",
        lambda: None,
    )
    from agents.faq_knowledge import search_faq_documents

    records = search_faq_documents("Who approves a 22% discount on ISC?")
    assert records == []
    assert all("faq_docs/" not in str(row.get("source", "")) for row in records)
