"""Deterministic contracts around the final AE-facing response."""

from __future__ import annotations

import json

from agents.synthesis.payload import build_synthesis_request
from models.synthesis_output import (
    CopyReadyArtifact,
    RecommendedAction,
    SynthesisOutput,
    render_synthesis_markdown,
    validate_synthesis_output,
)


def _output() -> SynthesisOutput:
    return SynthesisOutput(
        summary="Meridian is in technical validation for a $3.1M expansion.",
        insights=["The RFP is due September 5."],
        actions=[
            RecommendedAction(
                action="Send the BAA-covered environment.",
                due="before Thursday",
                paste="Sending the BAA-covered environment before Thursday.",
            )
        ],
        artifacts=[
            CopyReadyArtifact(
                title="The ask",
                kind="ask",
                body="Can we secure the nursing informatics walkthrough?",
            )
        ],
    )


def test_render_has_exact_ordered_sections_and_no_preamble() -> None:
    rendered = render_synthesis_markdown(_output())
    headings = [
        "## Summary",
        "## Key Insights",
        "## Recommended Actions",
        "## Artifacts",
    ]
    assert rendered.startswith("## Summary\n")
    assert [rendered.index(heading) for heading in headings] == sorted(
        rendered.index(heading) for heading in headings
    )
    assert "```" in rendered


def test_validation_rejects_placeholders_hollow_copy_and_leaks() -> None:
    output = SynthesisOutput(
        summary="The orchestrator has not yet received [ACCOUNT] findings."
    )
    errors = validate_synthesis_output(
        output, forbidden_terms=("orchestrator",)
    )
    assert "contains bracket placeholders" in errors
    assert "claims specialist findings are unavailable" in errors
    assert any("leaks internal source names" in error for error in errors)

    hollow = SynthesisOutput(
        summary=(
            "We are currently missing specific performance data in the records "
            "to populate exact coverage figures."
        ),
        insights=["No specific numeric values were returned in the current records."],
        actions=[
            RecommendedAction(
                action="Request a fresh reporting pull for the West region.",
            )
        ],
    )
    assert "claims specialist findings are unavailable" in validate_synthesis_output(
        hollow
    )


def test_synthesis_request_contains_all_results_and_context() -> None:
    raw = build_synthesis_request(
        user_query="Brief Meridian",
        state={
            "ae_name": "Casey Nguyen",
            "last_account": "Meridian Health",
            "last_territory": "central",
            "last_opportunity": "",
        },
        results={
            "crm_intelligence_specialist": {"status": "ok", "account": "Meridian Health"},
            "rep_performance_specialist": {
                "status": "partial",
                "issues": ["manager oversight required"],
            },
        },
    )
    payload = json.loads(raw)
    assert payload["original_question"] == "Brief Meridian"
    assert payload["working_context"]["last_account"] == "Meridian Health"
    assert payload["verified_records"] == {}
    assert "plain english" in payload["writing_guidance"].lower()
    assert set(payload["specialist_results"]) == {
        "crm_intelligence_specialist",
        "rep_performance_specialist",
    }
