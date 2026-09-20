"""Map internal child authors to manager-facing status copy."""

from __future__ import annotations

STATUS_BY_AUTHOR = {
    "route_planner": "Figuring out what you need…",
    "crm_intelligence_specialist": "Validating CRM and stage evidence…",
    "activity_engagement_specialist": "Reviewing calls and engagement…",
    "rep_performance_specialist": "Checking rep performance…",
    "forecast_modeling_specialist": "Modelling forecast and pipeline…",
    "knowledge_base_rag": "Checking approved policy and product documents…",
    "policy_answer": "Writing the answer…",
    "synthesis": "Writing your briefing…",
}


def status_for_author(author: str) -> str | None:
    """Return a progress label, or None when the author is not shown to the manager."""
    return STATUS_BY_AUTHOR.get(author)
