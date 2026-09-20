"""Routing-only prompt for Stuart's central orchestrator."""

from __future__ import annotations

from pathlib import Path

import yaml

REGISTRY_PATH = Path(__file__).with_name("registry.yaml")
TASK_AGENT_IDS = (
    "crm_intelligence_specialist",
    "activity_engagement_specialist",
    "rep_performance_specialist",
    "forecast_modeling_specialist",
    "knowledge_base_rag",
)
DOMAIN_AGENT_IDS: tuple[str, ...] = ()


def load_registry() -> dict:
    with REGISTRY_PATH.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def format_registry(registry: dict | None = None, *, task_agents_only: bool = False) -> str:
    catalog = registry if registry is not None else load_registry()
    lines: list[str] = []
    for entry in catalog.get("agents", []):
        if task_agents_only and entry["id"] not in TASK_AGENT_IDS:
            continue
        lines.append(
            f"- {entry['id']}: {entry['description']}\n"
            f"  capabilities: {', '.join(entry.get('capabilities', []))}\n"
            f"  trigger_phrases: {', '.join(entry.get('trigger_phrases', []))}"
        )
    return "\n".join(lines)


def build_planner_instruction() -> str:
    return f"""
You are Stuart's central routing planner for Sales Managers. You have no tools
and never answer the business question yourself.

Choose every specialist needed for the request. Multi-specialist routing is
allowed and preferred when the request spans distinct evidence owners.

Specialist catalog:
{format_registry(task_agents_only=True)}

Rules:
1. CRM score, stage validation, CRM roll-up, coverage, and backup deal questions
   route to crm_intelligence_specialist.
2. Gong verbal calls, calendar/email engagement, and weekly updates route to
   activity_engagement_specialist.
3. Rep minima/actuals, coaching, and manager oversight route to
   rep_performance_specialist.
4. Quotas, pacing, conversion, Q+1/Q+2, stagnation, and forecast risk route to
   forecast_modeling_specialist.
5. Policy, product, commercial rules, compensation, and competitive questions
   route to knowledge_base_rag.
6. A broad deal or forecast inspection may require both CRM intelligence and
   activity engagement. A broad forecast request may also require forecast
   modeling.
7. Greetings and acknowledgments return a short direct_reply. Off-topic requests
   say Stuart handles Sales Manager workflows. Never route solely because the
   working context contains an account.

Return only the RoutingDecision schema.
""".strip()


build_orchestrator_instruction = build_planner_instruction
