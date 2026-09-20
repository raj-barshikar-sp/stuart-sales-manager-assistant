"""Regression tests for the custom name-level eval gates."""

from __future__ import annotations

from google.adk.evaluation.eval_case import (
    IntermediateData,
    Invocation,
    InvocationEvent,
    InvocationEvents,
)
from google.genai import types

from evals.metrics import (
    intermediate_authors,
    routing_pass,
    synthesis_format_pass,
)


def test_routing_score_ignores_nested_tools_and_order_of_specialists() -> None:
    assert routing_pass(
        [
            "route_planner",
            "crm_intelligence_specialist",
            "activity_engagement_specialist",
            "synthesis",
        ],
        ["activity_engagement_specialist", "crm_intelligence_specialist", "synthesis"],
    )
    assert not routing_pass(
        ["route_planner", "synthesis"],
        ["crm_intelligence_specialist", "activity_engagement_specialist", "synthesis"],
    )
    assert routing_pass(
        ["route_planner", "crm_intelligence_specialist", "synthesis", "synthesis"],
        ["crm_intelligence_specialist", "synthesis"],
    )
    assert not routing_pass(
        ["route_planner", "crm_intelligence_specialist", "synthesis", "synthesis", "synthesis"],
        ["crm_intelligence_specialist", "synthesis"],
    )
    assert routing_pass(["knowledge_base_rag"], ["knowledge_base_rag"])


def test_intermediate_authors_reads_child_agent_events() -> None:
    invocation = Invocation(
        user_content=types.Content(
            role="user", parts=[types.Part.from_text(text="hello")]
        ),
        intermediate_data=IntermediateData(
            intermediate_responses=[
                ("route_planner", [types.Part.from_text(text="{}")]),
                ("crm_intelligence_specialist", [types.Part.from_text(text="{}")]),
            ]
        ),
    )
    assert intermediate_authors(invocation) == [
        "route_planner",
        "crm_intelligence_specialist",
    ]


def test_intermediate_authors_reads_invocation_events() -> None:
    invocation = Invocation(
        user_content=types.Content(
            role="user", parts=[types.Part.from_text(text="hello")]
        ),
        intermediate_data=InvocationEvents(
            invocation_events=[
                InvocationEvent(author="user", content=None),
                InvocationEvent(author="route_planner", content=None),
                InvocationEvent(author="crm_intelligence_specialist", content=None),
                InvocationEvent(author="synthesis", content=None),
            ]
        ),
    )
    assert intermediate_authors(invocation) == [
        "route_planner",
        "crm_intelligence_specialist",
        "synthesis",
    ]


def test_synthesis_format_gate_requires_no_preamble() -> None:
    valid = """## Summary
Ready.

## Key Insights
- One

## Recommended Actions
1. Act.

## Artifacts
None."""
    assert synthesis_format_pass(valid, expect_synthesis=True)
    assert not synthesis_format_pass(
        "Here you go.\n\n" + valid, expect_synthesis=True
    )
    assert not synthesis_format_pass(
        valid.replace("Ready.", "Awaiting specialist findings."),
        expect_synthesis=True,
    )
    assert synthesis_format_pass("Hello!", expect_synthesis=False)
