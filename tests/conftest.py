"""Shared test fixtures."""

from __future__ import annotations

import asyncio

import pytest


@pytest.fixture(autouse=True)
def fast_tool_latency(monkeypatch: pytest.MonkeyPatch) -> None:
    """Skip the 0.5s mock latency so the suite stays fast."""

    async def _instant(_seconds: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", _instant)


@pytest.fixture
def local_faq_index(monkeypatch: pytest.MonkeyPatch) -> None:
    """Score FAQ tests against the bundled Confluence snapshot."""
    from agents.faq_knowledge import load_faq_sections

    monkeypatch.setattr(
        "agents.faq_knowledge.load_knowledge_sections",
        load_faq_sections,
    )
