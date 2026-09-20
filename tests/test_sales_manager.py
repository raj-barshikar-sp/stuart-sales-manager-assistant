"""Grounded Sales Manager contracts over the consolidated snapshots."""

from __future__ import annotations

import importlib

import pytest

from agents.faq_knowledge import load_faq_sections
from agents.new_data_store import (
    activity,
    confluence,
    data_ready,
    gong,
    normalized_calendar_events,
    normalized_deal_intelligence,
    normalized_email_threads,
    normalized_opportunities,
    sales_users,
    workday,
)
from agents.sales_manager_data import (
    future_pipeline,
    rep_review,
    scoped_accounts,
    stage_validation,
)

SPECIALISTS = (
    "crm_intelligence_specialist",
    "activity_engagement_specialist",
    "rep_performance_specialist",
    "forecast_modeling_specialist",
    "knowledge_base_rag",
)


@pytest.mark.parametrize("agent_id", SPECIALISTS[:-1])
def test_specialist_is_single_turn_tool_grounded(agent_id: str) -> None:
    module = importlib.import_module(f"agents.{agent_id}.agent")
    agent = getattr(module, f"{agent_id}_agent")
    assert agent.name == agent_id
    assert agent.mode == "single_turn"
    assert agent.disallow_transfer_to_parent is True
    assert agent.tools
    assert agent.output_schema is not None


def test_knowledge_base_rag_is_one_rovo_agent() -> None:
    from agents.knowledge_base_rag.agent import knowledge_base_rag_agent

    assert knowledge_base_rag_agent.name == "knowledge_base_rag"
    assert "confluence" in knowledge_base_rag_agent.description.lower()


def test_new_snapshot_is_complete_and_linked() -> None:
    assert data_ready()
    user_ids = {row["Id"] for row in sales_users()}
    employee_ids = {row["sfdc_user_id"] for row in workday()["employees"]}
    opportunity_ids = {row["Id"] for row in normalized_opportunities()}
    assert user_ids <= employee_ids
    assert all(row["OwnerId"] in user_ids for row in normalized_opportunities())
    assert all(
        row["opportunity_id"] in opportunity_ids
        for row in (normalized_calendar_events() + normalized_email_threads())
    )
    assert all(
        row["opportunity_id"] in opportunity_ids
        for row in normalized_deal_intelligence()
    )


def test_stage_validator_derives_real_failures() -> None:
    rows = stage_validation([row["Account_Name"] for row in normalized_opportunities()])
    assert rows
    failures = [row for row in rows if row["status"] == "failed"]
    assert failures
    zenith = next(row for row in rows if row["account"] == "Zenith Health")
    assert zenith["stage_name"] == "SS40"
    assert "Lead_SE__c" in zenith["missing_fields"]


def test_rep_review_uses_salesforce_activity_and_workday() -> None:
    accounts = [row["Account_Name"] for row in normalized_opportunities()]
    review = rep_review(accounts)
    assert len(review["rep_metrics"]) == 4
    assert review["productivity_gaps"]
    assert review["coaching_queue"]
    marcus = next(
        row for row in review["coaching_queue"] if row["rep_name"] == "Marcus Brody"
    )
    assert "Ramping AE (0-6 months tenure)" in marcus["reason"]
    assert any(row["severity"] == "high" for row in review["oversight_deals"])


def test_future_pipeline_is_derived_without_inventing_q2_data() -> None:
    accounts = [row["Account_Name"] for row in normalized_opportunities()]
    rows = future_pipeline(accounts)["quarters"]
    assert {row["quarter"] for row in rows} == {"Q+1", "Q+2"}
    q1 = next(row for row in rows if row["quarter"] == "Q+1")
    q2 = next(row for row in rows if row["quarter"] == "Q+2")
    assert q1["pipeline"] == 2_050_000
    assert q1["weighted_forecast"] == 769_500
    assert q2["pipeline"] == 1_280_000
    assert q2["weighted_forecast"] == 240_000


def test_confluence_snapshot_is_the_local_faq_corpus() -> None:
    documents = confluence()["documents"]
    sections = load_faq_sections()
    assert len(documents) == 5
    assert {row["document_id"] for row in sections} == {
        "CONF-DOC-001",
        "CONF-DOC-002",
        "CONF-DOC-003",
        "CONF-DOC-004",
        "CONF-DOC-005",
    }
    assert all(row["content"] and row["source"].startswith("confluence://") for row in sections)


def test_query_packs_expose_new_source_records(local_faq_index) -> None:
    from agents.sales_manager_query import (
        query_activity_engagement,
        query_crm_intelligence,
        query_forecast_modeling,
        query_knowledge_base,
        query_rep_performance,
    )

    accounts = [row["Account_Name"] for row in normalized_opportunities()]
    crm = query_crm_intelligence("Run the stage validator.", accounts)
    assert crm["stage_failures"]
    assert crm["records"]["SalesforceOpportunity"]
    activity_pack = query_activity_engagement("Show engagement.", accounts)
    assert activity_pack["records"]["CalendarEvent"]
    assert activity_pack["records"]["GongDealIntelligence"]
    assert query_rep_performance("Show coaching.", accounts)["coaching_queue"]
    assert query_forecast_modeling("Model Q+1 and Q+2.", accounts)["quarters"]
    faq = query_knowledge_base("Who approves a 22% discount on ISC?")
    assert faq["sources"][0].startswith("CONF-DOC-002 §")
    assert "15.1% - 25%" in faq["records"]["PolicySection"][0]["content"]


def test_every_menu_prompt_has_one_legal_owner_and_route() -> None:
    from models.routing_decision import heuristic_route
    from ui.catalog import GROUP_AGENT, TASK_MENU

    labels = [group["label"] for group in TASK_MENU]
    assert labels == [
        "Forecasting",
        "Forecast inspection",
        "Rep participation",
        "Future quarter pipeline overview",
        "Manager policy & knowledge",
    ]
    for group in TASK_MENU:
        for item in group["items"]:
            owner = item.get("agent") or GROUP_AGENT[group["id"]]
            assert owner in SPECIALISTS
            actual = [
                route.agent_id
                for route in heuristic_route(item["default_prompt"]).agents
            ]
            assert owner in actual, (item["id"], actual, owner)


def test_every_menu_prompt_returns_grounded_records(local_faq_index) -> None:
    from agents.sales_manager_query import (
        query_activity_engagement,
        query_crm_intelligence,
        query_forecast_modeling,
        query_knowledge_base,
        query_rep_performance,
    )
    from ui.catalog import GROUP_AGENT, TASK_MENU

    queries = {
        "crm_intelligence_specialist": query_crm_intelligence,
        "activity_engagement_specialist": query_activity_engagement,
        "rep_performance_specialist": query_rep_performance,
        "forecast_modeling_specialist": query_forecast_modeling,
    }
    for group in TASK_MENU:
        for item in group["items"]:
            owner = item.get("agent") or GROUP_AGENT[group["id"]]
            prompt = item["default_prompt"]
            if owner == "knowledge_base_rag":
                payload = query_knowledge_base(prompt)
            else:
                accounts, error = scoped_accounts(query=prompt)
                assert error is None
                payload = queries[owner](prompt, accounts)
            assert payload["records"]
            assert any(payload["records"].values())
