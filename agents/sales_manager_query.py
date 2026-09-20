"""Grounded query packs for the five specialist architecture."""

from __future__ import annotations

from typing import Any

from agents.faq_knowledge import search_faq_documents
from agents.new_data_store import (
    normalized_calendar_events,
    normalized_deal_intelligence,
    normalized_email_threads,
    normalized_opportunities,
    quarterly_quotas,
    salesforce,
    verbal_forecast_calls,
)
from agents.sales_manager_data import (
    deal_risk_review,
    forecast_rollup,
    future_pipeline,
    rep_review,
)


def _scoped_opportunities(accounts: list[str]) -> list[dict[str, Any]]:
    allowed = set(accounts)
    return [
        row
        for row in normalized_opportunities()
        if row["Account_Name"] in allowed
    ]


def query_crm_intelligence(
    query: str, accounts: list[str], preflight: dict[str, Any] | None = None
) -> dict[str, Any]:
    data = deal_risk_review(accounts)
    return {
        "topic": "stage_validation" if "stage" in query.lower() else "crm_intelligence",
        "accounts": accounts,
        "commit_total": data["rollup"]["commit_total"],
        "upside_total": data["rollup"]["upside_total"],
        "risks": data["rollup"]["risks"],
        "stage_failures": data["stage_failures"],
        "records": {
            "SalesforceOpportunity": _scoped_opportunities(accounts),
            "ForecastRollup": data["rollup"]["accounts"],
            "StageValidation": data["stage_validations"],
            "CRMPreflight": [preflight] if preflight else [],
        },
        "findings": [],
        "next_action": "",
        "copy_ready": [],
    }


def query_activity_engagement(query: str, accounts: list[str]) -> dict[str, Any]:
    scoped = _scoped_opportunities(accounts)
    ids = {row["Id"] for row in scoped}
    owner_ids = {row["OwnerId"] for row in scoped}
    calendar = [
        row
        for row in normalized_calendar_events()
        if row["opportunity_id"] in ids
    ]
    email = [
        row
        for row in normalized_email_threads()
        if row["opportunity_id"] in ids
    ]
    intelligence = [
        row
        for row in normalized_deal_intelligence()
        if row["opportunity_id"] in ids
    ]
    verbal = [
        row for row in verbal_forecast_calls() if row["rep_id"] in owner_ids
    ]
    return {
        "topic": "activity_engagement",
        "accounts": accounts,
        "risks": [
            signal
            for row in intelligence
            for signal in row.get("risk_indicators", [])
        ],
        "records": {
            "CalendarEvent": calendar,
            "EmailThread": email,
            "GongDealIntelligence": intelligence,
            "WeeklyVerbalForecastCall": verbal,
        },
        "findings": [],
        "next_action": "",
        "copy_ready": [],
    }


def query_rep_performance(query: str, accounts: list[str]) -> dict[str, Any]:
    data = rep_review(accounts)
    return {
        "topic": "rep_performance",
        **data,
        "records": {
            "RepProductivity": data["rep_metrics"],
            "RepExpectations": data["expectations"],
            "CoachingQueue": data["coaching_queue"],
            "ManagerOversight": data["oversight_deals"],
        },
        "findings": [],
        "next_action": "",
        "copy_ready": [],
    }


def query_forecast_modeling(
    query: str, accounts: list[str], quarter: str = ""
) -> dict[str, Any]:
    normalized = query.upper().replace(" ", "")
    if not quarter:
        if "Q+1" in normalized and "Q+2" not in normalized:
            quarter = "Q+1"
        elif "Q+2" in normalized and "Q+1" not in normalized:
            quarter = "Q+2"
    future = future_pipeline(accounts, quarter)
    current = forecast_rollup(accounts)
    pacing = salesforce()["conversion_and_pacing_history"]
    owner_ids = {
        row["OwnerId"] for row in _scoped_opportunities(accounts)
    }
    verbal = [
        row for row in verbal_forecast_calls() if row["rep_id"] in owner_ids
    ]
    return {
        "topic": (
            "pipeline_stagnation"
            if "stagn" in query.lower()
            else "forecast_modeling"
        ),
        **future,
        "current_commit_total": current["commit_total"],
        "current_upside_total": current["upside_total"],
        "records": {
            "FutureQuarterForecast": future["quarters"],
            "PipelineStagnation": future["stagnated_deals"],
            "QuarterlyTeamQuota": list(quarterly_quotas().values()),
            "ConversionAndPacingHistory": [pacing],
            "WeeklyVerbalForecastCall": verbal,
            "ForecastRisk": current["accounts"],
        },
        "findings": [],
        "next_action": "",
        "copy_ready": [],
    }


def query_knowledge_base(question: str) -> dict[str, Any]:
    sections = search_faq_documents(question)
    return {
        "topic": "manager_policy_knowledge",
        "question": question,
        "answers": [row["content"] for row in sections],
        "sources": [
            f"{row['document_id']} § {row['section']}" for row in sections
        ],
        "records": {"PolicySection": sections},
        "findings": [],
        "next_action": "",
        "copy_ready": [],
        "status": "success" if sections else "error",
        "error": "" if sections else "No matching approved policy section was found.",
    }


# Transitional aliases for callers updated in the same migration.
query_forecasting = query_crm_intelligence
query_forecast_inspection = query_activity_engagement
query_rep_participation = query_rep_performance
query_future_pipeline = query_forecast_modeling
query_faq = query_knowledge_base
