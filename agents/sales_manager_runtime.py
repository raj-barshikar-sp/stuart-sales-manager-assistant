"""Deterministic execution path for the five specialist architecture."""

from __future__ import annotations

from typing import Any

from agents.sales_manager_data import coerce_scope, scoped_accounts
from agents.sales_manager_query import (
    query_activity_engagement,
    query_crm_intelligence,
    query_forecast_modeling,
    query_knowledge_base,
    query_rep_performance,
)
from models.specialist_outputs import (
    ActivityEngagementOutput,
    CrmIntelligenceOutput,
    ForecastModelingOutput,
    KnowledgeBaseRagOutput,
    RepPerformanceOutput,
)

SALES_MANAGER_AGENT_IDS = (
    "crm_intelligence_specialist",
    "activity_engagement_specialist",
    "rep_performance_specialist",
    "forecast_modeling_specialist",
    "knowledge_base_rag",
)


def _user_query(request: str) -> str:
    for line in request.splitlines():
        if line.startswith("Original request:"):
            return line.split(":", 1)[1].strip()
    return request


def _scoped(request: str) -> tuple[str, list[str], dict[str, str], str]:
    query = _user_query(request)
    scope = coerce_scope(query=query)
    accounts, err = scoped_accounts(query=query, **scope)
    message = str(err.get("message") or "") if err else ""
    return query, accounts, scope, message


def execute_sales_manager(agent_id: str, request: str) -> dict[str, Any]:
    if agent_id not in SALES_MANAGER_AGENT_IDS:
        raise KeyError(agent_id)
    query = _user_query(request)
    if agent_id == "knowledge_base_rag":
        return KnowledgeBaseRagOutput(**query_knowledge_base(query)).model_dump()

    query, accounts, _scope, error = _scoped(request)
    status = "error" if error else "success"
    if agent_id == "crm_intelligence_specialist":
        return CrmIntelligenceOutput(
            **query_crm_intelligence(query, accounts), status=status, error=error
        ).model_dump()
    if agent_id == "activity_engagement_specialist":
        return ActivityEngagementOutput(
            **query_activity_engagement(query, accounts), status=status, error=error
        ).model_dump()
    if agent_id == "rep_performance_specialist":
        return RepPerformanceOutput(
            **query_rep_performance(query, accounts), status=status, error=error
        ).model_dump()
    return ForecastModelingOutput(
        **query_forecast_modeling(query, accounts), status=status, error=error
    ).model_dump()
