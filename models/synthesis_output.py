"""Final Sales Manager-facing synthesis payload."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Literal

from pydantic import BaseModel, Field


class RecommendedAction(BaseModel):
    """One next step the manager can take, with optional paste-ready text."""

    action: str = Field(description="What to do, in one sentence.")
    owner: str = Field(default="you", description="Who does it.")
    due: str = Field(default="", description="Date or window if known.")
    paste: str = Field(
        default="",
        description="Short line the manager can copy into Slack or a meeting note.",
    )


class CopyReadyArtifact(BaseModel):
    """A block the manager can paste into email, CRM, or a doc."""

    title: str
    kind: Literal["email", "merge_instruction", "talking_points", "ask", "work_order", "other"] = (
        "other"
    )
    body: str = Field(description="Full paste-ready text. No placeholders like [NAME].")


class SynthesisOutput(BaseModel):
    """Merged, personalized answer produced by the synthesis agent."""

    summary: str = Field(description="Short briefing of the situation and ask.")
    insights: list[str] = Field(
        default_factory=list,
        description="The most important takeaways for the sales manager.",
    )
    actions: list[RecommendedAction] = Field(
        default_factory=list,
        description="Concrete next steps, each with optional paste text.",
    )
    artifacts: list[CopyReadyArtifact] = Field(
        default_factory=list,
        description="Emails, merge instructions, asks, and other paste-ready blocks.",
    )


_PLACEHOLDER_RE = re.compile(r"\[[A-Z][A-Z0-9_ /-]{1,40}\]")
_HOLLOW_RE = re.compile(
    r"awaiting (?:specialist|findings)|ha(?:ve|s) not (?:yet )?received|"
    r"underlying data .* not provided|ensure the orchestrator|"
    r"structured findings .* missing|"
    r"couldn't produce a reliable briefing|"
    r"findings need to be regenerated|"
    r"no specific numeric|"
    r"missing specific (?:performance )?data|"
    r"fresh (?:reporting )?pull|"
    r"not returned in the current records|"
    r"currently missing .* (?:coverage|kpi|metrics|performance)|"
    r"records to populate",
    re.IGNORECASE,
)


def validate_synthesis_output(
    output: SynthesisOutput,
    *,
    forbidden_terms: Iterable[str] = (),
) -> list[str]:
    """Return contract violations that should trigger one synthesis retry."""
    text = " ".join(
        [
            output.summary,
            *output.insights,
            *(action.action for action in output.actions),
            *(action.paste for action in output.actions),
            *(artifact.title for artifact in output.artifacts),
            *(artifact.body for artifact in output.artifacts),
        ]
    )
    errors: list[str] = []
    if not output.summary.strip():
        errors.append("summary is empty")
    if _PLACEHOLDER_RE.search(text):
        errors.append("contains bracket placeholders")
    if _HOLLOW_RE.search(text):
        errors.append("claims specialist findings are unavailable")
    lowered = text.lower()
    leaked = sorted(
        term for term in forbidden_terms if term.lower() in lowered
    )
    if leaked:
        errors.append(f"leaks internal source names: {', '.join(leaked)}")
    return errors


def _action_line(index: int, action: dict[str, object]) -> list[str]:
    body = str(action.get("action") or "").strip()
    if not body:
        return []
    owner = str(action.get("owner") or "you").strip()
    due = str(action.get("due") or "").strip()
    metadata = ", ".join(
        part
        for part in (
            f"owner: {owner}" if owner else "",
            f"when: {due}" if due else "",
        )
        if part
    )
    lines = [f"{index}. {body}{f' ({metadata})' if metadata else ''}"]
    paste = str(action.get("paste") or "").strip()
    if paste:
        lines.append(f"   Paste: {paste}")
    return lines


def render_partial_markdown(fields: dict[str, object]) -> str:
    """Render the sections of a still-streaming synthesis object.

    The result is always a prefix of the final `render_synthesis_markdown`
    output, so the UI can append text without ever rewriting what it showed.
    A section is emitted only once every earlier section has arrived.
    """
    summary = fields.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        return ""
    blocks = ["## Summary\n" + summary.strip()]

    raw_insights = fields.get("insights")
    insights = (
        [item.strip() for item in raw_insights if isinstance(item, str) and item.strip()]
        if isinstance(raw_insights, list)
        else []
    )
    if not insights:
        return "\n\n".join(blocks)
    blocks.append("## Key Insights\n" + "\n".join(f"- {item}" for item in insights))

    raw_actions = fields.get("actions")
    action_lines: list[str] = []
    if isinstance(raw_actions, list):
        for index, action in enumerate(raw_actions, start=1):
            if isinstance(action, dict):
                action_lines.extend(_action_line(index, action))
    if action_lines:
        blocks.append("## Recommended Actions\n" + "\n".join(action_lines))
    return "\n\n".join(blocks)


def render_synthesis_markdown(output: SynthesisOutput) -> str:
    """Render the validated schema into the manager-facing markdown shape."""
    insights = "\n".join(f"- {item.strip()}" for item in output.insights)
    if not insights:
        insights = "- No additional account-changing insight was identified."

    action_lines: list[str] = []
    for index, action in enumerate(output.actions, start=1):
        action_lines.extend(_action_line(index, action.model_dump()))
    actions = "\n".join(action_lines) or "1. Confirm the next step with the account."

    artifact_lines: list[str] = []
    for artifact in output.artifacts:
        artifact_lines.extend(
            [
                f"### {artifact.title.strip()}",
                "```",
                artifact.body.strip(),
                "```",
            ]
        )
    artifacts = "\n".join(artifact_lines) or "None."

    return "\n\n".join(
        [
            "## Summary\n" + output.summary.strip(),
            "## Key Insights\n" + insights,
            "## Recommended Actions\n" + actions,
            "## Artifacts\n" + artifacts,
        ]
    )
