"""Deterministic CRM-hygiene contracts over the v2 snapshots."""

from agents.crm_hygiene import run_preflight, validate_stage_evidence
from agents.new_data_store import normalized_opportunities


def test_preflight_checks_all_v2_joins_and_scope() -> None:
    result = run_preflight("Review east deals.", {})
    assert result["status"] == "success"
    assert len(result["accounts"]) == 19
    assert len(result["stage_evidence"]) == 19
    assert result["join_errors"] == []
    assert result["missing_files"] == []


def test_absent_stage_evidence_is_unverifiable_not_failed() -> None:
    opportunity = normalized_opportunities()[0]
    result = validate_stage_evidence([opportunity])[0]
    assert result["status"] == "unverifiable"
    assert result["passed"] is None
    assert "Manager_Notes__c" in result["unverifiable_fields"]


def test_known_missing_stage_evidence_is_a_failure() -> None:
    opportunity = next(
        row
        for row in normalized_opportunities()
        if row["Id"] == "0068b00001Deal002"
    )
    result = validate_stage_evidence([opportunity])[0]
    assert result["status"] == "failed"
    assert result["passed"] is False
    assert result["missing_fields"] == ["Lead_SE__c"]
