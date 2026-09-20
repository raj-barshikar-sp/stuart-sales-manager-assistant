"""Code-enforced workflow executes Sales Manager specialists then synthesis."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from google.adk.agents.invocation_context import InvocationContext
from google.adk.events.event import Event
from google.adk.sessions.session import Session
from google.genai import types

from agents.orchestrator.workflow import SellerCopilotWorkflow
from models.synthesis_output import SynthesisOutput


def _ctx(query: str) -> InvocationContext:
    return InvocationContext.model_construct(
        session_service=object(),
        invocation_id="inv",
        session=Session(id="s", app_name="agents", user_id="u", state={}),
        user_content=types.Content(
            role="user", parts=[types.Part.from_text(text=query)]
        ),
    )


def _workflow() -> SellerCopilotWorkflow:
    ids = (
        "crm_intelligence_specialist",
        "activity_engagement_specialist",
        "rep_performance_specialist",
        "forecast_modeling_specialist",
        "knowledge_base_rag",
    )
    return SellerCopilotWorkflow.model_construct(
        name="central_orchestrator",
        planner_agent=SimpleNamespace(name="route_planner"),
        specialist_agents={name: SimpleNamespace(name=name) for name in ids},
        final_synthesis_agent=SimpleNamespace(name="synthesis"),
        policy_answer_agent=SimpleNamespace(name="policy_answer"),
        sub_agents=[],
    )


_POLICY_PAYLOAD = {
    "status": "success",
    "records": {
        "PolicySection": [
            {
                "document_id": "DOC-DEAL-002",
                "section": "Discount Authorization > ISC",
                "content": "16% – 25% Discount: RVP Approval required.",
            }
        ]
    },
}


def _faq_workflow(written: str, calls: list[str]) -> SellerCopilotWorkflow:
    """Workflow whose retrieval is fixed and whose writer returns `written`."""
    workflow = _workflow()

    async def run_child(agent, ctx, request):  # noqa: ANN001
        calls.append(agent.name)
        assert agent.name != "synthesis"
        return [], _POLICY_PAYLOAD, ""

    async def stream_child(agent, ctx, request, outcome):  # noqa: ANN001
        calls.append(agent.name)
        outcome.update({"events": [], "payload": written, "error": ""})
        return
        yield  # pragma: no cover — keeps this an async generator

    workflow._run_child = run_child  # type: ignore[method-assign]
    workflow._stream_child = stream_child  # type: ignore[method-assign]
    return workflow


async def _collect(workflow: SellerCopilotWorkflow, query: str) -> str:
    text: list[str] = []
    async for event in workflow._run_async_impl(_ctx(query)):
        if event.content:
            text.extend(
                part.text
                for part in event.content.parts or []
                if getattr(part, "text", None)
            )
    return "\n".join(text)


def test_greeting_skips_all_children() -> None:
    workflow = _workflow()
    calls: list[str] = []

    async def fail(agent, ctx, request):  # noqa: ANN001
        calls.append(agent.name)
        raise AssertionError("children must not run")

    workflow._run_child = fail  # type: ignore[method-assign]
    assert asyncio.run(_collect(workflow, "hello"))
    assert calls == []


def test_specialist_payload_reaches_synthesis_once() -> None:
    workflow = _workflow()
    calls: list[str] = []
    synthesis_request = ""

    async def fake(agent, ctx, request):  # noqa: ANN001
        nonlocal synthesis_request
        calls.append(agent.name)
        if agent.name == "synthesis":
            synthesis_request = request
            return [], SynthesisOutput(
                summary="East forecast risks are ready.",
                insights=["0068b00001Deal002 failed its stage validation."],
            ).model_dump(), ""
        return [], {
            "status": "success",
            "records": {
                "StageValidationResult": [
                    {"opp_id": "0068b00001Deal002", "failed_rules": ["Lead_SE__c"]}
                ]
            },
        }, ""

    workflow._run_child = fake  # type: ignore[method-assign]
    rendered = asyncio.run(
        _collect(workflow, "Run the Sales Stage Validator for 0068b00001Deal002.")
    )
    assert calls == ["crm_intelligence_specialist", "synthesis"]
    assert "StageValidationResult" in synthesis_request
    assert "0068b00001Deal002" in synthesis_request
    assert rendered.startswith("## Summary\n")


def test_cross_domain_manager_ask_runs_each_specialist_then_synthesis() -> None:
    workflow = _workflow()
    calls: list[str] = []

    async def fake(agent, ctx, request):  # noqa: ANN001
        calls.append(agent.name)
        if agent.name == "synthesis":
            return [], SynthesisOutput(summary="Manager review is ready.").model_dump(), ""
        return [], {"status": "success", "records": {"Grounded": [{"id": 1}]}}, ""

    workflow._run_child = fake  # type: ignore[method-assign]
    asyncio.run(
        _collect(
            workflow,
            "Compare the verbal call to roll-up and model Q+1 and Q+2.",
        )
    )
    assert set(calls[:-1]) == {
        "crm_intelligence_specialist",
        "activity_engagement_specialist",
        "forecast_modeling_specialist",
    }
    assert calls[-1] == "synthesis"
    assert calls.count("synthesis") == 1


def test_faq_turn_answers_in_prose_without_synthesis() -> None:
    calls: list[str] = []
    written = (
        "A 22% discount on ISC needs your RVP to sign off, since it lands in "
        "the 16% – 25% band (DOC-DEAL-002 § Discount Authorization > ISC)."
    )
    workflow = _faq_workflow(written, calls)

    rendered = asyncio.run(
        _collect(workflow, "Who approves a 22% discount on ISC?")
    )
    assert calls == ["knowledge_base_rag", "policy_answer"]
    assert rendered.strip() == (
        "A 22% discount on ISC needs your RVP to sign off, since it lands in "
        "the 16% – 25% band."
    )
    assert "DOC-DEAL-002" not in rendered
    assert "Here is the approved guidance" not in rendered


def test_faq_turn_reads_answer_from_a_non_streaming_writer() -> None:
    """ADK emits no partial events when the model runs non-streaming."""
    calls: list[str] = []
    workflow = _workflow()
    written = (
        "A 22% discount on ISC needs your RVP to sign off, since it lands in "
        "the 16% – 25% band."
    )

    async def run_child(agent, ctx, request):  # noqa: ANN001
        calls.append(agent.name)
        return [], _POLICY_PAYLOAD, ""

    async def stream_child(agent, ctx, request, outcome):  # noqa: ANN001
        calls.append(agent.name)
        event = Event(
            invocation_id="inv",
            author=agent.name,
            content=types.Content(
                role="model", parts=[types.Part.from_text(text=written)]
            ),
        )
        outcome.update({"events": [event], "payload": None, "error": ""})
        yield event

    workflow._run_child = run_child  # type: ignore[method-assign]
    workflow._stream_child = stream_child  # type: ignore[method-assign]

    rendered = asyncio.run(_collect(workflow, "Who approves a 22% discount on ISC?"))
    assert calls == ["knowledge_base_rag", "policy_answer"]
    assert written in rendered
    assert "Here is the approved guidance" not in rendered


def test_faq_answer_with_invented_threshold_falls_back_to_excerpts() -> None:
    calls: list[str] = []
    workflow = _faq_workflow(
        "A 22% discount sits in the 20% to 29.9% tier, so it needs VP approval.",
        calls,
    )

    rendered = asyncio.run(
        _collect(workflow, "Who approves a 22% discount on ISC?")
    )
    assert calls.count("policy_answer") == 2  # one retry before falling back
    assert "29.9" not in rendered
    assert "16% – 25% Discount: RVP Approval required." in rendered


def test_specialist_request_preserves_scope_and_grounding_instruction() -> None:
    request = _workflow()._specialist_request(
        "Show productivity gaps for east.", {}, {}
    )
    assert '"geo": "east"' in request
    assert "record" in request.lower()
