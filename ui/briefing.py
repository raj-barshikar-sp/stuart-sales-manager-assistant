"""Parse workflow markdown into a manager-facing briefing payload."""

from __future__ import annotations

import re

_HEADINGS = (
    "## Summary",
    "## Key Insights",
    "## Recommended Actions",
    "## Artifacts",
)

_ACTION_RE = re.compile(
    r"^(?P<n>\d+)\.\s+(?P<body>.*?)(?:\s+\((?P<meta>[^)]*)\))?\s*$"
)
_FENCE_RE = re.compile(
    r"^###\s+(?P<title>.+?)\s*\n```\n(?P<body>.*?)\n```",
    re.MULTILINE | re.DOTALL,
)


def _section_map(text: str) -> dict[str, str] | None:
    positions = [text.find(heading) for heading in _HEADINGS]
    if positions[0] != 0 or any(position < 0 for position in positions):
        return None
    if positions != sorted(positions):
        return None
    sections: dict[str, str] = {}
    for index, heading in enumerate(_HEADINGS):
        start = positions[index] + len(heading)
        end = positions[index + 1] if index + 1 < len(positions) else len(text)
        sections[heading.lstrip("# ").strip()] = text[start:end].strip()
    return sections


def _parse_insights(block: str) -> list[str]:
    items: list[str] = []
    for line in block.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            items.append(stripped[2:].strip())
    return items


def _parse_actions(block: str) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        match = _ACTION_RE.match(stripped)
        if match:
            meta = match.group("meta") or ""
            owner = ""
            due = ""
            for part in (piece.strip() for piece in meta.split(",") if piece.strip()):
                if part.lower().startswith("owner:"):
                    owner = part.split(":", 1)[1].strip()
                elif part.lower().startswith("when:"):
                    due = part.split(":", 1)[1].strip()
            current = {
                "action": match.group("body").strip(),
                "owner": owner,
                "due": due,
                "paste": "",
            }
            actions.append(current)
            continue
        if current is not None and stripped.lower().startswith("paste:"):
            current["paste"] = stripped.split(":", 1)[1].strip()
    return actions


def _parse_artifacts(block: str) -> list[dict[str, str]]:
    if block.strip().rstrip(".") in {"", "None"}:
        return []
    return [
        {"title": match.group("title").strip(), "body": match.group("body").strip()}
        for match in _FENCE_RE.finditer(block)
    ]


def parse_reply(text: str) -> dict:
    """Turn orchestrator markdown into a structured UI payload."""
    stripped = text.strip()
    sections = _section_map(stripped)
    if not sections:
        return {"kind": "plain", "text": stripped}
    return {
        "kind": "briefing",
        "summary": sections["Summary"],
        "insights": _parse_insights(sections["Key Insights"]),
        "actions": _parse_actions(sections["Recommended Actions"]),
        "artifacts": _parse_artifacts(sections["Artifacts"]),
    }
