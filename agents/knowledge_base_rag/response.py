"""Grounded manager-facing knowledge response helpers."""

from __future__ import annotations

import json
import re
from typing import Any

_MARKDOWN_LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_MARKUP = re.compile(r"[*_`]")
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
_STAGE_CODE = re.compile(r"\bss\s?\d{1,3}\b", re.IGNORECASE)
_PAREN_CITATION = re.compile(r"\s*\([^()]*(?:§|source:)[^()]*\)", re.IGNORECASE)
_SOURCE_LINE = re.compile(r"(?im)^\s*(?:source|citation):.*(?:\n|$)")

NO_MATCH_REPLY = (
    "I couldn't find that in the approved Sales Manager policy and product "
    "documents. Try naming the policy, product, competitor, or commercial rule."
)


def _plain(text: str) -> str:
    text = _MARKDOWN_LINK.sub(r"\1", text)
    text = _MARKUP.sub("", text)
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped in {"---", ""}:
            continue
        if stripped.startswith("| :---") or set(stripped) <= {"|", ":", "-", " "}:
            continue
        lines.append(stripped)
    return "\n".join(lines).strip()


def policy_sections(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return (payload.get("records") or {}).get("PolicySection") or []


def build_answer_request(
    question: str, payload: dict[str, Any], *, correction: str = ""
) -> str:
    sections = [
        {
            "document_title": row.get("title", ""),
            "section": row.get("section", ""),
            "content": row.get("content", ""),
            "internal_source": row.get("source", ""),
        }
        for row in policy_sections(payload)[:4]
    ]
    parts = [
        f"Manager question: {question}",
        "Approved sections (your only source of truth):",
        json.dumps(sections, ensure_ascii=False, indent=2),
    ]
    if correction:
        parts.append(
            "Your previous attempt was rejected: "
            f"{correction} Rewrite it using only figures that appear verbatim "
            "in the sections above."
        )
    return "\n\n".join(parts)


def _figures(text: str) -> set[str]:
    found = {
        match.group(0).replace(",", "").rstrip(".")
        for match in _NUMBER.finditer(text)
    }
    found.update(
        match.group(0).lower().replace(" ", "") for match in _STAGE_CODE.finditer(text)
    )
    return found


def unsupported_figures(
    answer: str, payload: dict[str, Any], question: str
) -> list[str]:
    allowed = _figures(question)
    for row in policy_sections(payload):
        allowed |= _figures(
            f"{row.get('document_id', '')} {row.get('title', '')} "
            f"{row.get('section', '')} {row.get('content', '')}"
        )
    return sorted(figure for figure in _figures(answer) if figure not in allowed)


def remove_visible_citations(answer: str) -> str:
    answer = _SOURCE_LINE.sub("", answer)
    answer = _PAREN_CITATION.sub("", answer)
    return re.sub(r"[ \t]+\n", "\n", answer).strip()


def render_policy_answer(payload: dict[str, Any]) -> str:
    sections = policy_sections(payload)
    if not sections:
        return NO_MATCH_REPLY
    blocks = ["Here is the approved guidance:"]
    for row in sections[:3]:
        content = _plain(str(row.get("content") or ""))
        if content:
            blocks.append(content)
    return "\n\n".join(blocks)
