"""Map internal child authors to manager-facing status copy."""

from __future__ import annotations

STATUS_BY_AUTHOR = {
    "route_planner": "Understanding your question…",
    "crm_intelligence_specialist": "Reading your CRM snapshot…",
    "activity_engagement_specialist": "Reading calls and engagement…",
    "rep_performance_specialist": "Reading team performance…",
    "forecast_modeling_specialist": "Reading forecast and pipeline…",
    "knowledge_base_rag": "Reading approved guidance…",
    "synthesis": "Putting that together…",
}


def status_for_author(author: str) -> str | None:
    """Return a progress label, or None when the author is not shown to the manager."""
    return STATUS_BY_AUTHOR.get(author)
