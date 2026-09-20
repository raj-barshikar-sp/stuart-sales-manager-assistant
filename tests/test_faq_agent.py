"""Standalone FAQ retrieval, grounding, and deterministic execution."""

from __future__ import annotations

import base64
from pathlib import Path

import pytest

from agents.faq_knowledge import (
    faq_documents_ready,
    load_faq_sections,
    search_faq_documents,
)
from agents.knowledge_base_rag.agent import knowledge_base_rag_agent, rovo_headers
from agents.knowledge_base_rag.response import (
    build_answer_request,
    remove_visible_citations,
    render_policy_answer,
    unsupported_figures,
)
from agents.sales_manager_query import query_faq

pytestmark = pytest.mark.usefixtures("local_faq_index")


@pytest.mark.parametrize(
    ("question", "document_id", "required_text"),
    [
        (
            "Who approves a 22% discount on ISC?",
            "CONF-DOC-002",
            "15.1% - 25%",
        ),
        (
            "How is territory ownership assigned?",
            "CONF-DOC-001",
            "account ownership",
        ),
        (
            "How does the modernization SPIF work?",
            "CONF-DOC-003",
            "$5,000 flat bonus",
        ),
        (
            "How should I handle the Okta governance objection?",
            "CONF-DOC-004",
            "Competitive battlecard",
        ),
    ],
)
def test_retrieval_selects_the_approved_document(
    question: str, document_id: str, required_text: str
) -> None:
    records = search_faq_documents(question)
    assert records[0]["document_id"] == document_id
    assert required_text in f"{records[0]['section']}\n{records[0]['content']}"


def test_corpus_is_confluence_snapshot_with_metadata() -> None:
    assert faq_documents_ready()
    sections = load_faq_sections()
    assert sections
    assert len({row["document_id"] for row in sections}) == 5
    assert all(row["document_id"] and row["last_updated"] for row in sections)
    assert all(row["source"].startswith("confluence://") for row in sections)


def test_query_returns_section_citations_and_no_file_citations() -> None:
    result = query_faq("What are the rules for an inter-territory split?")
    assert result["status"] == "success"
    assert result["records"]["PolicySection"]
    assert result["sources"][0].startswith("CONF-DOC-001 §")
    assert all(".md" not in source for source in result["sources"])


def test_unsupported_question_returns_grounded_error() -> None:
    result = query_faq("What is the cafeteria lunch menu?")
    assert result["status"] == "error"
    assert result["records"]["PolicySection"] == []
    assert "No matching" in result["error"]


def test_old_stub_faq_json_is_gone() -> None:
    root = Path(__file__).resolve().parents[1] / "dummy_data"
    assert not list(root.glob("faq_*.json"))


def test_rovo_service_key_uses_bearer_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ROVO_MCP_API_KEY", "service-key")
    monkeypatch.delenv("ROVO_MCP_EMAIL", raising=False)
    assert rovo_headers() == {"Authorization": "Bearer service-key"}


def test_rovo_personal_token_uses_basic_auth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ROVO_MCP_API_KEY", "personal-token")
    monkeypatch.setenv("ROVO_MCP_EMAIL", "user@example.com")
    encoded = base64.b64encode(b"user@example.com:personal-token").decode()
    assert rovo_headers() == {"Authorization": f"Basic {encoded}"}


def test_faq_agent_uses_rovo_mcp_and_structured_output() -> None:
    assert knowledge_base_rag_agent.tools
    assert knowledge_base_rag_agent.output_schema is not None


def test_policy_response_preserves_threshold_without_visible_citation() -> None:
    payload = query_faq("Who approves a 22% discount on ISC?")
    answer = render_policy_answer(payload)
    assert "15.1% - 25%" in answer
    assert "Regional Vice President" in answer
    assert "CONF-DOC-002" not in answer
    assert "Source:" not in answer
    assert "20% to 29.9%" not in answer


def test_written_answer_may_quote_document_and_question_figures() -> None:
    question = "Who approves a 22% discount on ISC?"
    payload = query_faq(question)
    answer = (
        "A 22% discount lands in the 15.1% - 25% band, so the RVP approves it "
        "(CONF-DOC-002 § Approval Tiers)."
    )
    assert unsupported_figures(answer, payload, question) == []


def test_written_answer_that_invents_a_band_is_rejected() -> None:
    question = "Who approves a 22% discount on ISC?"
    payload = query_faq(question)
    answer = "A 22% discount sits in the 20% to 29.9% tier, so a VP signs off."
    assert "29.9" in unsupported_figures(answer, payload, question)


def test_answer_request_carries_only_retrieved_sections() -> None:
    question = "Who approves a 22% discount on ISC?"
    request = build_answer_request(question, query_faq(question))
    assert question in request
    assert "15.1% - 25%" in request
    assert "Approval Tiers" in request


def test_visible_citations_are_removed_from_written_answer() -> None:
    answer = (
        "Your RVP approves it (DOC-DEAL-002 § 2.1).\n"
        "Source: DOC-DEAL-002 § Discount Authorization"
    )
    assert remove_visible_citations(answer) == "Your RVP approves it."

