"""Progressive rendering of a synthesis payload that is still streaming."""

from __future__ import annotations

import json

from models.partial_json import completed_fields
from models.synthesis_output import (
    CopyReadyArtifact,
    RecommendedAction,
    SynthesisOutput,
    render_partial_markdown,
    render_synthesis_markdown,
)

OUTPUT = SynthesisOutput(
    summary="7-Eleven is a $2.4M commit deal flagged for stage risk.",
    insights=[
        "The deal closes 2026-09-30 and sits in the commit category.",
        "OPP-711 fails stage validation: no economic buyer confirmed.",
    ],
    actions=[
        RecommendedAction(
            action="Ask Avery Cole to confirm the economic buyer.",
            owner="Sales Manager",
            due="This week",
            paste="Can you confirm the economic buyer on 7-Eleven?",
        ),
        RecommendedAction(action="Re-score the commit after the buyer is named."),
    ],
    artifacts=[
        CopyReadyArtifact(
            title="Nudge for Avery",
            kind="email",
            body="Hi Avery,\n\nQuick check on 7-Eleven.\n\nThanks",
        )
    ],
)


def test_completed_fields_ignores_a_half_written_string() -> None:
    fields = completed_fields('{"summary": "done", "insights": ["first", "seco')
    assert fields["summary"] == "done"
    assert fields["insights"] == ["first"]


def test_completed_fields_ignores_an_unclosed_object() -> None:
    text = '{"summary": "s", "actions": [{"action": "a", "owner": "me"}, {"action": "b"'
    fields = completed_fields(text)
    assert fields["actions"] == [{"action": "a", "owner": "me"}]


def test_completed_fields_handles_escapes_and_empty_input() -> None:
    assert completed_fields('{"summary": "line\\nbreak"}')["summary"] == "line\nbreak"
    assert completed_fields("") == {}
    assert completed_fields("not json") == {}
    assert completed_fields('{"summary": "trailing backslash \\\\') == {}


def test_every_draft_is_a_prefix_of_the_final_briefing() -> None:
    """The UI only appends text, so a draft must never contradict the final."""
    final = render_synthesis_markdown(OUTPUT)
    stream = json.dumps(OUTPUT.model_dump())
    drafts = set()
    for size in range(len(stream) + 1):
        draft = render_partial_markdown(completed_fields(stream[:size]))
        assert final.startswith(draft), f"draft diverged at {size} chars"
        drafts.add(draft)
    assert len(drafts) > 3, "expected the draft to grow in several steps"


def test_draft_grows_monotonically() -> None:
    stream = json.dumps(OUTPUT.model_dump())
    lengths = [
        len(render_partial_markdown(completed_fields(stream[:size])))
        for size in range(len(stream) + 1)
    ]
    assert lengths == sorted(lengths)
    assert lengths[-1] > 0


def test_actions_wait_for_insights() -> None:
    """Skipping a section would break the prefix guarantee."""
    fields = {"summary": "s", "actions": [{"action": "a"}]}
    assert render_partial_markdown(fields) == "## Summary\ns"
