"""Code-enforced planner → specialists → synthesis workflow."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncGenerator
from typing import Any

from google.adk.agents import Agent, BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import types as genai_types

from agents.activity import log_activity, preview
from agents.constants import CHILD_TIMEOUT_SECONDS, GREETING_REPLY, OFF_TOPIC_REPLY
from agents.crm_hygiene import run_preflight
from agents.knowledge_base_rag.response import (
    build_answer_request,
    policy_sections,
    remove_visible_citations,
    render_policy_answer,
    unsupported_figures,
)
from agents.knowledge_base_rag.writer import (
    policy_answer_agent as default_policy_answer_agent,
)
from agents.orchestrator.prompt import DOMAIN_AGENT_IDS, TASK_AGENT_IDS
from agents.session_memory import (
    SESSION_KEYS,
    apply_working_context,
    detect_account_in_text,
    detect_territory_in_text,
    seed_context_from_text,
)
from agents.synthesis.payload import build_synthesis_request
from models.routing_decision import RoutingDecision, heuristic_route, looks_like_sales_manager_task
from models.partial_json import completed_fields
from models.synthesis_output import (
    CopyReadyArtifact,
    RecommendedAction,
    SynthesisOutput,
    render_partial_markdown,
    render_synthesis_markdown,
    validate_synthesis_output,
)

_INTERNAL_TERMS = (
    *TASK_AGENT_IDS,
    *DOMAIN_AGENT_IDS,
    "central_orchestrator",
    "synthesis",
    "policy_answer",
    "single_turn",
    "remember_working_context",
    "route_planner",
)


def _content(text: str) -> genai_types.Content:
    return genai_types.Content(
        role="user", parts=[genai_types.Part.from_text(text=text)]
    )


def _event_text(event: Event) -> str:
    if not event.content or not event.content.parts:
        return ""
    return "\n".join(
        part.text for part in event.content.parts if getattr(part, "text", None)
    )


def _user_text(ctx: InvocationContext) -> str:
    if not ctx.user_content or not ctx.user_content.parts:
        return ""
    return "\n".join(
        part.text
        for part in ctx.user_content.parts
        if getattr(part, "text", None)
    )


def _parse_payload(events: list[Event]) -> Any:
    for event in reversed(events):
        if event.output is not None:
            return event.output
        text = _event_text(event).strip()
        if not text:
            continue
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            continue
    return None


def _last_text(events: list[Event]) -> str:
    """Read a child's complete answer from its final event.

    ADK only emits partial events when the model is invoked in streaming mode. A
    non-streaming call delivers the whole answer in one final event, so relying on
    partials alone loses the answer entirely.
    """
    for event in reversed(events):
        if event.partial:
            continue
        text = _event_text(event).strip()
        if text:
            return text
    return ""


def _text_payload(payload: Any) -> str:
    """Read a plain-text child answer that ADK returned as a payload."""
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        for key in ("policy_answer", "answer", "text"):
            if isinstance(payload.get(key), str):
                return payload[key]
    return ""


def _final_event(author: str, ctx: InvocationContext, text: str) -> Event:
    return Event(
        invocation_id=ctx.invocation_id,
        author=author,
        branch=ctx.branch,
        content=genai_types.Content(
            role="model", parts=[genai_types.Part.from_text(text=text)]
        ),
    )


def _preview_event(author: str, ctx: InvocationContext, text: str) -> Event:
    """A growing draft of the briefing. Marked partial so ADK skips persisting it."""
    event = _final_event(author, ctx, text)
    event.partial = True
    return event


def _grounded_fallback(results: dict[str, Any]) -> SynthesisOutput | None:
    """Build a briefing from specialist rows when synthesis stays hollow."""
    for payload in results.values():
        if not isinstance(payload, dict):
            continue
        records = payload.get("records") or {}
        periods = records.get("KpiPeriod") or []
        kpis = records.get("KpiSummary") or {}
        slides = [
            str(item).strip()
            for item in (payload.get("slides") or [])
            if str(item).strip()
        ]
        copy_ready = [
            str(item).strip()
            for item in (payload.get("copy_ready") or [])
            if str(item).strip()
        ]
        findings = [
            str(item).strip()
            for item in (payload.get("findings") or [])
            if str(item).strip()
        ]
        record_rows = [
            row
            for value in records.values()
            for row in (value if isinstance(value, list) else [value])
            if isinstance(row, dict)
        ]
        if not periods and not slides and not kpis and not findings and not record_rows:
            continue
        insights: list[str] = []
        for row in periods:
            insights.append(
                f"{str(row.get('period', '')).title()}: coverage "
                f"{row.get('pipeline_coverage_ratio')}x, verbal call "
                f"${int(row.get('verbal_call_acv') or 0):,}, landing "
                f"${int(row.get('landing_projected') or 0):,}, cycle "
                f"{row.get('avg_sales_cycle_days')} days."
            )
        if not insights:
            insights = slides[1:] or slides[:3]
        if not insights and kpis:
            insights = [
                (
                    f"Coverage {kpis.get('pipeline_coverage_ratio')}x, "
                    f"verbal call ${int(kpis.get('verbal_call_acv') or 0):,}, "
                    f"quarterly landing "
                    f"${int(kpis.get('quarterly_landing_projected') or 0):,}, "
                    f"cycle {kpis.get('avg_sales_cycle_days')} days."
                )
            ]
        if not insights:
            insights = findings[:8]
        if not insights and record_rows:
            insights = [
                ", ".join(
                    f"{key.replace('_', ' ')}: {value}"
                    for key, value in list(row.items())[:5]
                    if value not in (None, "", [])
                )
                for row in record_rows[:8]
            ]
        headline = (
            slides[0]
            if slides
            else "Here is the grounded Sales Manager view from the current book."
        )
        if copy_ready:
            summary = f"{headline} {copy_ready[0]}"
        elif kpis:
            summary = (
                f"{headline} Coverage is {kpis.get('pipeline_coverage_ratio')}x, "
                f"verbal call ${int(kpis.get('verbal_call_acv') or 0):,}, "
                f"quarterly landing "
                f"${int(kpis.get('quarterly_landing_projected') or 0):,}, "
                f"cycle {kpis.get('avg_sales_cycle_days')} days."
            )
        else:
            summary = headline
        artifacts: list[CopyReadyArtifact] = []
        body = "\n".join(slides or copy_ready)
        if body:
            artifacts.append(
                CopyReadyArtifact(
                    title="Snapshot",
                    kind="talking_points",
                    body=body,
                )
            )
        return SynthesisOutput(
            summary=summary.strip(),
            insights=insights[:8],
            actions=[
                RecommendedAction(
                    action="Use these findings in the next team or forecast review.",
                    owner="Sales Manager",
                    due="Today",
                    paste=copy_ready[0] if copy_ready else "",
                )
            ],
            artifacts=artifacts,
        )
    return None


class SellerCopilotWorkflow(BaseAgent):
    """Run a validated route instead of asking an LLM to choreograph tools."""

    planner_agent: Agent
    specialist_agents: dict[str, BaseAgent] = {}
    final_synthesis_agent: Agent
    policy_answer_agent: Agent = default_policy_answer_agent

    def model_post_init(self, __context: Any) -> None:
        specialists = dict(self.specialist_agents)
        for child in self.sub_agents:
            if child.name in TASK_AGENT_IDS:
                specialists[child.name] = child
        object.__setattr__(self, "specialist_agents", specialists)

    def _child_ctx(
        self, agent: BaseAgent, ctx: InvocationContext, request: str
    ) -> InvocationContext:
        return ctx.model_copy(
            update={
                "user_content": _content(request),
                "branch": (
                    f"{ctx.branch}.{self.name}.{agent.name}"
                    if ctx.branch
                    else f"{self.name}.{agent.name}"
                ),
            }
        )

    async def _stream_child(
        self,
        agent: BaseAgent,
        ctx: InvocationContext,
        request: str,
        outcome: dict[str, Any],
    ) -> AsyncGenerator[Event, None]:
        """Yield child events as they arrive; report payload and error in `outcome`."""
        child_ctx = self._child_ctx(agent, ctx, request)
        events: list[Event] = []
        error = ""
        started = time.perf_counter()
        log_activity("child.start", agent=agent.name, streaming=True)
        try:
            async with asyncio.timeout(CHILD_TIMEOUT_SECONDS):
                async for event in agent.run_async(child_ctx):
                    events.append(event)
                    yield event
        except TimeoutError:
            error = f"Timeout after {CHILD_TIMEOUT_SECONDS}s"
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        log_activity(
            "child.failed" if error else "child.done",
            agent=agent.name,
            error=error,
            elapsed_ms=elapsed_ms,
            events=len(events),
            level=logging.INFO if error else logging.DEBUG,
        )
        outcome["events"] = events
        outcome["payload"] = _parse_payload(events)
        outcome["error"] = error

    async def _run_child(
        self,
        agent: BaseAgent,
        ctx: InvocationContext,
        request: str,
    ) -> tuple[list[Event], Any, str]:
        child_ctx = self._child_ctx(agent, ctx, request)
        events: list[Event] = []
        error = ""
        started = time.perf_counter()
        log_activity("child.start", agent=agent.name)
        try:
            async with asyncio.timeout(CHILD_TIMEOUT_SECONDS):
                async for event in agent.run_async(child_ctx):
                    events.append(event)
        except TimeoutError:
            error = f"Timeout after {CHILD_TIMEOUT_SECONDS}s"
        except Exception as exc:  # keep one failed specialist from killing the turn
            error = f"{type(exc).__name__}: {exc}"
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        if error:
            log_activity(
                "child.failed",
                agent=agent.name,
                error=error,
                elapsed_ms=elapsed_ms,
            )
        else:
            log_activity(
                "child.done",
                agent=agent.name,
                elapsed_ms=elapsed_ms,
                events=len(events),
                level=logging.DEBUG,
            )
        return events, _parse_payload(events), error

    def _planner_request(self, query: str, state: Any) -> str:
        context = {key: str(state.get(key) or "") for key in SESSION_KEYS}
        return json.dumps(
            {"query": query, "working_context": context},
            ensure_ascii=False,
            sort_keys=True,
        )

    def _specialist_request(
        self, query: str, state: Any, preflight: dict[str, Any]
    ) -> str:
        from agents.sales_manager_data import parse_scope_from_text

        context = {key: str(state.get(key) or "") for key in SESSION_KEYS}
        scope = parse_scope_from_text(query)
        if not any(scope.values()):
            if context.get("last_account"):
                scope["account_name"] = context["last_account"]
            elif context.get("last_territory"):
                scope["geo"] = context["last_territory"]
        return (
            f"Original request: {query}\n"
            f"Working context: {json.dumps(context, ensure_ascii=False)}\n"
            "Tool scope — pass these arguments exactly:\n"
            f"{json.dumps(scope, ensure_ascii=False)}\n"
            "Deterministic CRM hygiene preflight (reuse it; do not re-run or "
            "reinterpret unknown evidence):\n"
            f"{json.dumps(preflight, ensure_ascii=False, default=str)}\n"
            "Use the named account, territory, or opportunity from the request "
            "or working context. Query grounded records first and return the "
            "required structured result without inventing facts."
        )

    async def _answer_policy_question(
        self, ctx: InvocationContext, query: str, payload: Any
    ) -> AsyncGenerator[Event, None]:
        """Write the policy answer in prose, but never let it drift off-document."""
        if not isinstance(payload, dict) or not policy_sections(payload):
            answer = render_policy_answer(payload if isinstance(payload, dict) else {})
            log_activity("faq.no_match", chars=len(answer))
            yield _final_event(self.name, ctx, answer)
            return

        answer = ""
        correction = ""
        for attempt in (1, 2):
            outcome: dict[str, Any] = {}
            streamed = ""
            request = build_answer_request(query, payload, correction=correction)
            async for event in self._stream_child(
                self.policy_answer_agent, ctx, request, outcome
            ):
                yield event
                if not event.partial:
                    continue
                streamed += _event_text(event)
            events = outcome.get("events") or []
            candidate = remove_visible_citations(
                streamed
                or _last_text(events)
                or _text_payload(outcome.get("payload"))
            )
            if outcome.get("error") or not candidate:
                log_activity("faq.write_failed", error=outcome.get("error") or "empty")
                break
            invented = unsupported_figures(candidate, payload, query)
            if not invented:
                answer = candidate
                break
            log_activity("faq.ungrounded", attempt=attempt, figures=invented)
            correction = (
                "it used figures that are not in the approved sections: "
                f"{', '.join(invented)}."
            )

        if not answer:
            # The UI restarts the pane when the final text isn't a draft prefix.
            answer = render_policy_answer(payload)
            log_activity("faq.fallback_to_excerpts", chars=len(answer))

        log_activity(
            "turn.done",
            specialists=["knowledge_base_rag"],
            synthesis_skipped=True,
            chars=len(answer),
        )
        yield _final_event(self.name, ctx, answer)

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        query = _user_text(ctx).strip()
        state = ctx.session.state
        for key in SESSION_KEYS:
            state.setdefault(key, "")
        seed_context_from_text(state, query)
        log_activity(
            "turn.start",
            invocation=ctx.invocation_id,
            query=preview(query),
        )

        explicit = heuristic_route(query)
        if explicit.direct_reply and not explicit.agents:
            log_activity("route.direct", reply=preview(explicit.direct_reply, 80))
            yield _final_event(self.name, ctx, explicit.direct_reply)
            return

        matched_ids = [route.agent_id for route in explicit.agents]
        if matched_ids:
            log_activity("route.heuristic", specialists=matched_ids)
        planner_error = ""
        planned = RoutingDecision()
        if not matched_ids:
            planner_events, raw_plan, planner_error = await self._run_child(
                self.planner_agent,
                ctx,
                self._planner_request(query, state),
            )
            for event in planner_events:
                yield event
            planned = RoutingDecision.from_state(raw_plan)
            matched_ids = [route.agent_id for route in planned.agents]
            log_activity(
                "route.planner",
                specialists=matched_ids,
                error=planner_error or "",
            )

        if matched_ids and not looks_like_sales_manager_task(query):
            matched_ids = []
            if not planned.direct_reply:
                planned = RoutingDecision(direct_reply=OFF_TOPIC_REPLY)
            log_activity("route.rejected", reason="not_a_sales_manager_task")

        if not matched_ids:
            reply = planned.direct_reply or GREETING_REPLY
            if planner_error:
                reply = (
                    "I couldn't confidently route that request. Please name the "
                    "account and the outcome you want."
                )
            log_activity("route.none", reply=preview(reply, 80))
            yield _final_event(self.name, ctx, reply)
            return

        selected = [name for name in matched_ids if name in self.specialist_agents]
        selected = list(dict.fromkeys(selected))
        if not selected:
            yield _final_event(
                self.name,
                ctx,
                "Which Sales Manager outcome do you need — CRM intelligence, "
                "activity engagement, rep performance, forecast modeling, or "
                "knowledge-base guidance?",
            )
            return
        preflight = run_preflight(
            query,
            state,
            require_scope=selected != ["knowledge_base_rag"],
        )
        request = self._specialist_request(query, state, preflight)
        log_activity(
            "turn.specialists",
            specialists=selected,
            hygiene_status=preflight["status"],
        )
        results: dict[str, Any] = {}

        async def _run_named(name: str) -> tuple[str, list[Event], Any, str]:
            events, payload, error = await self._run_child(
                self.specialist_agents[name], ctx, request
            )
            return name, events, payload, error

        pending = [asyncio.create_task(_run_named(name)) for name in selected]
        for finished in asyncio.as_completed(pending):
            name, events, payload, error = await finished
            for event in events:
                yield event
            if error:
                results[name] = {"status": "error", "error": error}
                log_activity("specialist.failed", specialist=name, error=error)
            elif payload is None:
                results[name] = {
                    "status": "error",
                    "error": "Specialist returned no structured payload.",
                }
                log_activity("specialist.empty", specialist=name)
            else:
                results[name] = payload
                records = payload.get("records") if isinstance(payload, dict) else {}
                log_activity(
                    "specialist.done",
                    specialist=name,
                    status=payload.get("status") if isinstance(payload, dict) else "",
                    tables=sorted(records) if isinstance(records, dict) else [],
                )
            blob = f"{query} {json.dumps(results[name], default=str)}"
            apply_working_context(
                state,
                account=detect_account_in_text(blob) or "",
                territory=detect_territory_in_text(blob) or "",
                opportunity="",
            )

        if selected == ["knowledge_base_rag"]:
            async for event in self._answer_policy_question(
                ctx, query, results["knowledge_base_rag"]
            ):
                yield event
            return

        synthesis_request = build_synthesis_request(
            user_query=query,
            state=state,
            results=results,
        )
        yield Event(
            invocation_id=ctx.invocation_id,
            author="synthesis",
            branch=ctx.branch,
        )
        outcome: dict[str, Any] = {}
        streamed = ""
        shown = ""
        async for event in self._stream_child(
            self.final_synthesis_agent, ctx, synthesis_request, outcome
        ):
            yield event
            if not event.partial:
                continue
            streamed += _event_text(event)
            draft = render_partial_markdown(completed_fields(streamed))
            # Only ever extend what the manager has already seen.
            if len(draft) > len(shown) and draft.startswith(shown):
                shown = draft
                yield _preview_event(self.name, ctx, shown)
        raw_synthesis = outcome.get("payload")
        synthesis_error = outcome.get("error") or ""
        if shown:
            log_activity("synthesis.streamed", chars=len(shown))

        output: SynthesisOutput | None = None
        validation_errors: list[str] = []
        if synthesis_error:
            validation_errors.append(synthesis_error)
        else:
            try:
                output = SynthesisOutput.model_validate(raw_synthesis)
                validation_errors = validate_synthesis_output(
                    output, forbidden_terms=_INTERNAL_TERMS
                )
            except Exception as exc:
                validation_errors.append(f"invalid synthesis payload: {exc}")

        if validation_errors:
            log_activity("synthesis.retry", errors=validation_errors)
            retry_request = build_synthesis_request(
                user_query=query,
                state=state,
                results=results,
                validation_errors=validation_errors,
            )
            retry_events, raw_retry, retry_error = await self._run_child(
                self.final_synthesis_agent, ctx, retry_request
            )
            for event in retry_events:
                yield event
            if not retry_error:
                try:
                    candidate = SynthesisOutput.model_validate(raw_retry)
                    if not validate_synthesis_output(
                        candidate, forbidden_terms=_INTERNAL_TERMS
                    ):
                        output = candidate
                except Exception:
                    pass

        if output is None or validate_synthesis_output(
            output, forbidden_terms=_INTERNAL_TERMS
        ):
            fallback = _grounded_fallback(results)
            log_activity(
                "synthesis.fallback",
                used_records=fallback is not None,
            )
            output = fallback or SynthesisOutput(
                summary=(
                    "I couldn't produce a reliable briefing from the available "
                    "account data without risking unsupported details."
                ),
                insights=[
                    "The account findings need to be regenerated before you act on them."
                ],
                actions=[
                    RecommendedAction(
                        action="Retry the request with the account and desired outcome.",
                        paste="Please regenerate this briefing using only verified account findings.",
                    )
                ],
            )

        log_activity(
            "turn.done",
            specialists=selected,
            insights=len(output.insights),
            actions=len(output.actions),
        )
        yield _final_event(
            self.name,
            ctx,
            render_synthesis_markdown(output),
        )
