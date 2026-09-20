"""Deterministic CRM completeness, freshness, and join validation."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from agents.new_data_store import (
    FILES,
    DATA_DIR,
    employee_by_sfdc_id,
    normalized_calendar_events,
    normalized_deal_intelligence,
    normalized_email_threads,
    normalized_opportunities,
    sales_users,
    snapshot_time,
    stage_rules,
)

_FIELD = re.compile(r"^[A-Za-z0-9_]+")
_EXPECTED = re.compile(r"==\s*'([^']+)'")


def _field_name(rule: str) -> str:
    match = _FIELD.match(rule)
    return match.group(0) if match else rule


def _evidence_status(
    opportunity: dict[str, Any], requirement: str
) -> tuple[str, str]:
    field = _field_name(requirement)
    if field not in opportunity:
        return "unverifiable", field
    value = opportunity.get(field)
    if value in (None, "", False, []):
        return "missing", field
    expected = _EXPECTED.search(requirement)
    if expected and str(value) != expected.group(1):
        return "invalid", field
    return "present", field


def validate_stage_evidence(
    opportunities: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rules = stage_rules()
    rows: list[dict[str, Any]] = []
    for opportunity in opportunities:
        stage = str(opportunity["StageName"]).split(" ", 1)[0]
        rule = rules.get(stage)
        if not rule:
            rows.append(
                {
                    "opp_id": opportunity["Id"],
                    "stage_name": stage,
                    "status": "unverifiable",
                    "missing_fields": [],
                    "invalid_fields": [],
                    "unverifiable_fields": ["stage_rule"],
                }
            )
            continue
        checks = [
            (*_evidence_status(opportunity, requirement), requirement)
            for requirement in rule["required_evidence_fields"]
        ]
        missing = [field for status, field, _ in checks if status == "missing"]
        invalid = [field for status, field, _ in checks if status == "invalid"]
        unverifiable = [
            field for status, field, _ in checks if status == "unverifiable"
        ]
        status = (
            "failed"
            if missing or invalid
            else "unverifiable"
            if unverifiable
            else "passed"
        )
        rows.append(
            {
                "opp_id": opportunity["Id"],
                "stage_name": stage,
                "status": status,
                "passed": (
                    True if status == "passed" else False if status == "failed" else None
                ),
                "required_fields": list(rule["required_evidence_fields"]),
                "missing_fields": missing,
                "invalid_fields": invalid,
                "unverifiable_fields": unverifiable,
                "exit_criteria": rule["exit_criteria"],
            }
        )
    return rows


def _join_errors() -> list[str]:
    opportunities = normalized_opportunities()
    opportunity_ids = {row["Id"] for row in opportunities}
    rep_ids = {row["Id"] for row in sales_users()}
    employee_ids = set(employee_by_sfdc_id())
    errors: list[str] = []
    for row in opportunities:
        if row["OwnerId"] not in rep_ids:
            errors.append(f"{row['Id']}: OwnerId does not resolve")
    for source, rows in (
        ("calendar", normalized_calendar_events()),
        ("email", normalized_email_threads()),
        ("gong", normalized_deal_intelligence()),
    ):
        for row in rows:
            if row["opportunity_id"] not in opportunity_ids:
                errors.append(f"{source}: {row['opportunity_id']} does not resolve")
    for rep_id in rep_ids:
        if rep_id not in employee_ids:
            errors.append(f"{rep_id}: Workday employee does not resolve")
    return errors


def run_preflight(
    query: str,
    state: Any,
    *,
    require_scope: bool = True,
) -> dict[str, Any]:
    """Return one reusable preflight payload for specialist dispatch."""
    from agents.sales_manager_data import parse_scope_from_text, scoped_accounts

    missing_files = [name for name in FILES if not (DATA_DIR / name).is_file()]
    scope = parse_scope_from_text(query)
    if not any(scope.values()):
        if state.get("last_account"):
            scope["account_name"] = str(state["last_account"])
        elif state.get("last_territory"):
            scope["geo"] = str(state["last_territory"])

    accounts: list[str] = []
    scope_error = ""
    if require_scope:
        accounts, error = scoped_accounts(query=query, **scope)
        scope_error = str((error or {}).get("message") or "")

    scoped = [
        row
        for row in normalized_opportunities()
        if not require_scope or row["Account_Name"] in set(accounts)
    ]
    synced_at = datetime.fromisoformat(snapshot_time().replace("Z", "+00:00"))
    return {
        "status": (
            "error"
            if missing_files or scope_error
            else "partial"
            if _join_errors()
            else "success"
        ),
        "scope": scope,
        "accounts": accounts,
        "scope_error": scope_error,
        "missing_files": missing_files,
        "join_errors": _join_errors(),
        "snapshot_synced_at": synced_at.isoformat(),
        "stage_evidence": validate_stage_evidence(scoped),
    }
