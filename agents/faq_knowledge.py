"""Section-level retrieval over the approved Sales Manager FAQ documents."""

from __future__ import annotations

import math
import re
from functools import lru_cache
from typing import Any

from agents.activity import log_activity
from agents.confluence_knowledge import (
    ConfluenceKnowledgeError,
    confluence_config_from_env,
    load_confluence_sections,
)
from agents.new_data_store import confluence

_HEADING = re.compile(r"^(#{1,4})\s+(.+?)\s*$")
_TOKEN = re.compile(r"[a-z0-9]+(?:\.[0-9]+)?")
_STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "can",
    "do",
    "does",
    "for",
    "how",
    "i",
    "in",
    "is",
    "it",
    "me",
    "of",
    "on",
    "our",
    "the",
    "to",
    "what",
    "when",
    "who",
    "with",
    "work",
}
_EXPANSIONS: dict[str, set[str]] = {
    "ownership": {"account", "named", "territory", "hq", "poaching", "assignment"},
    "engagement": {"ownership", "split", "holdover", "dispute", "routing"},
    "discount": {"authorization", "approval", "threshold", "list", "price", "pricing"},
    "quote": {"quoting", "cpq", "stage", "approval", "discount"},
    "pricing": {"discount", "quote", "list", "price", "approval"},
    "terms": {"payment", "billing", "net", "contract", "escalator"},
    "modernization": {"iiq", "isc", "saas", "carve", "bridge", "migration"},
    "commission": {"quota", "accelerator", "payout", "spif", "clawback"},
    "spif": {"spifs", "commission", "accelerator", "bonus"},
    "compensation": {"commission", "quota", "accelerator", "spif"},
    "product": {"isc", "suite", "business", "nerm", "das", "ciem", "licensing"},
    "battlecard": {"competitor", "saviynt", "okta", "entra", "cyberark", "objection"},
    "competitor": {"battlecard", "saviynt", "okta", "entra", "cyberark", "delinea"},
    "objection": {"battlecard", "response", "expensive", "governance", "iiq"},
}


def faq_documents_ready() -> bool:
    return bool(confluence().get("documents"))


def _render(value: Any) -> str:
    if isinstance(value, dict):
        return "\n".join(f"{key}: {_render(item)}" for key, item in value.items())
    if isinstance(value, list):
        return "\n".join(
            _render(item) if not isinstance(item, dict) else "; ".join(
                f"{key}: {_render(child)}" for key, child in item.items()
            )
            for item in value
        )
    return str(value)


@lru_cache(maxsize=1)
def load_faq_sections() -> tuple[dict[str, Any], ...]:
    """Normalize the bundled Confluence snapshot into searchable sections."""
    records: list[dict[str, Any]] = []
    for document in confluence()["documents"]:
        for section, content in document["content"].items():
            records.append(
                {
                    "document_id": document["id"],
                    "title": document["title"],
                    "section": section.replace("_", " ").title(),
                    "content": _render(content),
                    "last_updated": document["last_updated"],
                    "effective_fiscal_year": "FY26",
                    "source": f"confluence://{document['space']}/{document['id']}",
                }
            )
    return tuple(records)


def load_knowledge_sections() -> tuple[dict[str, Any], ...]:
    """Load allowlisted live Confluence pages through the legacy REST adapter."""
    try:
        config = confluence_config_from_env()
        if config is None:
            raise ConfluenceKnowledgeError("Confluence is not configured")
        sections = load_confluence_sections(config)
        if not sections:
            raise ConfluenceKnowledgeError(
                "No readable pages were found in the allowlisted Confluence spaces"
            )
        return sections
    except ConfluenceKnowledgeError as exc:
        log_activity("confluence.unavailable", error=str(exc))
        return ()


def _terms(text: str) -> set[str]:
    terms = {token for token in _TOKEN.findall(text.lower()) if token not in _STOP_WORDS}
    expanded = set(terms)
    for term in terms:
        expanded.update(_EXPANSIONS.get(term, ()))
    if "rules of engagement" in text.lower():
        expanded.update(_EXPANSIONS["engagement"])
    if "identityiq" in text.lower():
        expanded.update({"iiq", "modernization", "saas", "isc"})
    return expanded


_Index = tuple[tuple[tuple[set[str], set[str]], ...], dict[str, float]]
_INDEX_CACHE: tuple[tuple[dict[str, Any], ...], _Index] | None = None


def _index(sections: tuple[dict[str, Any], ...]) -> _Index:
    """Tokenise every section once and weight each term by how rare it is.

    Rebuilt only when the caller hands over a different sections tuple, which is
    what happens when the Confluence cache refreshes.
    """
    global _INDEX_CACHE
    if _INDEX_CACHE is not None and _INDEX_CACHE[0] is sections:
        return _INDEX_CACHE[1]
    tokens: list[tuple[set[str], set[str]]] = []
    frequency: dict[str, int] = {}
    for record in sections:
        heading_terms = _terms(f"{record['title']} {record['section']}")
        content_terms = _terms(record["content"])
        tokens.append((heading_terms, content_terms))
        for term in heading_terms | content_terms:
            frequency[term] = frequency.get(term, 0) + 1
    total = len(sections) or 1
    weights = {
        term: math.log(1 + total / count) for term, count in frequency.items()
    }
    index: _Index = (tuple(tokens), weights)
    _INDEX_CACHE = (sections, index)
    return index


def search_faq_documents(question: str, limit: int = 5) -> list[dict[str, Any]]:
    """Return the strongest complete policy sections for a manager question."""
    query_terms = _terms(question)
    heading_query_terms = {
        token
        for token in _TOKEN.findall(question.lower())
        if token not in _STOP_WORDS
    }
    if "spif" in heading_query_terms:
        heading_query_terms.add("spifs")
    sections = load_knowledge_sections()
    tokens, weights = _index(sections)
    scored: list[tuple[float, int, dict[str, Any]]] = []
    for position, record in enumerate(sections):
        heading_terms, content_terms = tokens[position]
        # A term shared by half the corpus says little about relevance, so rank on
        # the weight of what matched rather than the number of matches.
        score = 5 * sum(
            weights[term] for term in heading_query_terms & heading_terms
        )
        score += sum(weights[term] for term in query_terms & content_terms)
        if score:
            scored.append((score, -position, record))
    scored.sort(reverse=True, key=lambda item: (item[0], item[1]))
    return [dict(record) for _, _, record in scored[: max(1, limit)]]

