"""Sales Manager routing, registry, and workflow wiring."""

from __future__ import annotations

import json
from pathlib import Path

from agents.constants import GREETING_REPLY
from agents.orchestrator.agent import planner_agent, root_agent
from agents.orchestrator.prompt import (
    TASK_AGENT_IDS,
    build_orchestrator_instruction,
    build_planner_instruction,
    format_registry,
    load_registry,
)
from agents.orchestrator.workflow import SellerCopilotWorkflow
from models.routing_decision import (
    AgentRoute,
    RoutingDecision,
    enforce_explicit_routes,
    heuristic_route,
)

SPECIALISTS = (
    "crm_intelligence_specialist",
    "activity_engagement_specialist",
    "rep_performance_specialist",
    "forecast_modeling_specialist",
    "knowledge_base_rag",
)


def test_exact_sales_manager_specialist_allowlist() -> None:
    assert tuple(TASK_AGENT_IDS) == SPECIALISTS
    assert set(root_agent.specialist_agents) == set(SPECIALISTS)


def test_registry_lists_only_sales_manager_specialists() -> None:
    catalog = load_registry()
    ids = [entry["id"] for entry in catalog["agents"]]
    assert ids == [*SPECIALISTS]
    assert all(
        entry["description"] and entry["capabilities"] and entry["trigger_phrases"]
        for entry in catalog["agents"]
    )
    task_only = format_registry(task_agents_only=True)
    assert all(agent_id in task_only for agent_id in SPECIALISTS)


def test_root_agent_keeps_enforced_workflow_contract() -> None:
    assert isinstance(root_agent, SellerCopilotWorkflow)
    assert root_agent.name == "central_orchestrator"
    assert [agent.name for agent in root_agent.sub_agents] == [
        "route_planner",
        *SPECIALISTS,
        "synthesis",
        "policy_answer",
    ]
    assert planner_agent.output_schema.__name__ == "RoutingDecision"
    assert root_agent.final_synthesis_agent.name == "synthesis"


def test_prompts_are_manager_facing_and_tool_grounded() -> None:
    orchestrator = build_orchestrator_instruction()
    planner = build_planner_instruction()
    assert "Choose every specialist" in orchestrator
    assert all(agent_id in orchestrator for agent_id in SPECIALISTS)
    assert "manager" in (orchestrator + planner).lower()
    assert "Multi-specialist routing" in planner


def test_direct_replies_do_not_open_specialists() -> None:
    assert heuristic_route("hello").direct_reply == GREETING_REPLY
    assert heuristic_route("thanks").agents == []
    assert heuristic_route("okay great").agents == []
    assert heuristic_route("what is the weather?").agents == []


def test_plain_deal_questions_reach_the_planner() -> None:
    """No hint matches, but these are manager work — the planner must decide."""
    for prompt in (
        "Give me the information about our top revenue deals, "
        "and what are the bottlenecks we are facing?",
        "Which deals are at risk this quarter?",
    ):
        assert heuristic_route(prompt).direct_reply == "", prompt


def test_explicit_sales_manager_routes() -> None:
    cases = {
        "Review deal and forecast risks for east.": [
            "crm_intelligence_specialist",
            "forecast_modeling_specialist",
        ],
        "Run the Sales Stage Validator for 0068b00001Deal002.": [
            "crm_intelligence_specialist"
        ],
        "Compare the weekly verbal call to the CRM roll-up for west.": [
            "crm_intelligence_specialist",
            "activity_engagement_specialist",
        ],
        "Which reps need coaching and manager oversight?": ["rep_performance_specialist"],
        "Show stagnated deals and model Q+1 and Q+2.": ["forecast_modeling_specialist"],
        "What are the rules of engagement?": ["knowledge_base_rag"],
        "How do pricing and quoting approvals work?": ["knowledge_base_rag"],
        "Who approves a 22% discount on ISC?": ["knowledge_base_rag"],
        "Explain the commission plan.": ["knowledge_base_rag"],
        "Give me the product overview.": ["knowledge_base_rag"],
        "How do we handle the Okta objection?": ["knowledge_base_rag"],
    }
    for prompt, expected in cases.items():
        assert [r.agent_id for r in heuristic_route(prompt).agents] == expected, prompt


def test_explicit_route_overrides_wrong_plan() -> None:
    wrong = RoutingDecision(agents=[AgentRoute(agent_id="knowledge_base_rag")])
    actual = enforce_explicit_routes("Run the Sales Stage Validator.", wrong)
    assert [route.agent_id for route in actual.agents] == ["crm_intelligence_specialist"]


def test_eval_prompts_match_deterministic_routes() -> None:
    path = Path(__file__).resolve().parents[1] / "evals" / "routing.evalset.json"
    for case in json.loads(path.read_text(encoding="utf-8"))["eval_cases"]:
        turn = case["conversation"][0]
        prompt = turn["user_content"]["parts"][0]["text"]
        expected = [
            call["name"]
            for call in turn["intermediate_data"]["tool_uses"]
            if call["name"] != "synthesis"
        ]
        assert [route.agent_id for route in heuristic_route(prompt).agents] == expected


def test_routing_model_rejects_old_and_unknown_ids() -> None:
    decision = RoutingDecision.from_state(
        {
            "agents": [
                {"agent_id": "forecast_modeling_specialist"},
                {"agent_id": "synthesis"},
                {"agent_id": "unknown"},
            ]
        }
    )
    assert [route.agent_id for route in decision.agents] == ["forecast_modeling_specialist"]
