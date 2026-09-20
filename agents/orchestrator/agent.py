"""Root code-enforced orchestrator for Seller Co-Pilot."""

from __future__ import annotations

import agents.runtime_env  # noqa: F401 — load Vertex quota + ADK flags first

from google.adk.agents import Agent

from agents.activity_engagement_specialist.agent import (
    activity_engagement_specialist_agent,
)
from agents.constants import GEMINI_MODEL, SAFE_GEN_CONFIG
from agents.crm_intelligence_specialist.agent import crm_intelligence_specialist_agent
from agents.forecast_modeling_specialist.agent import forecast_modeling_specialist_agent
from agents.knowledge_base_rag.agent import knowledge_base_rag_agent
from agents.orchestrator.prompt import build_planner_instruction
from agents.knowledge_base_rag.writer import policy_answer_agent
from agents.orchestrator.workflow import SellerCopilotWorkflow
from agents.rep_performance_specialist.agent import rep_performance_specialist_agent
from agents.synthesis.agent import synthesis_agent
from models.routing_decision import RoutingDecision

planner_agent = Agent(
    name="route_planner",
    model=GEMINI_MODEL,
    description=(
        "Thin Sales Manager front door. Picks one team from child descriptions "
        "or asks one clarifying question. Never answers with numbers."
    ),
    instruction=build_planner_instruction(),
    generate_content_config=SAFE_GEN_CONFIG,
    tools=[],
    output_schema=RoutingDecision,
    output_key="routing_decision",
)

root_agent = SellerCopilotWorkflow(
    name="central_orchestrator",
    description=(
        "Stuart's central orchestrator with one deterministic CRM hygiene "
        "preflight and direct routing to five Sales Manager specialists."
    ),
    planner_agent=planner_agent,
    final_synthesis_agent=synthesis_agent,
    policy_answer_agent=policy_answer_agent,
    sub_agents=[
        planner_agent,
        crm_intelligence_specialist_agent,
        activity_engagement_specialist_agent,
        rep_performance_specialist_agent,
        forecast_modeling_specialist_agent,
        knowledge_base_rag_agent,
        synthesis_agent,
        policy_answer_agent,
    ],
)
