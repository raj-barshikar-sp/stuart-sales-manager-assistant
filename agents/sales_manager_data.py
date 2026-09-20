"""Deterministic Sales Manager facts derived from the v2 snapshots."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from agents.crm_hygiene import validate_stage_evidence
from agents.new_data_store import (
    accounts as load_accounts,
    employee_by_sfdc_id,
    normalized_deal_intelligence,
    normalized_opportunities,
    productivity_tier_by_rep,
    quarterly_quotas,
    resolve_account,
    sales_users,
    snapshot_time,
    stage_rules,
    territories,
)
from agents.tool_helpers import error

ACCOUNTS = load_accounts()
TERRITORIES = territories()
OPPORTUNITIES = normalized_opportunities()
OPPORTUNITY_BY_ID = {row["Id"]: row for row in OPPORTUNITIES}
GONG_BY_OPPORTUNITY = {
    row["opportunity_id"]: row for row in normalized_deal_intelligence()
}
SNAPSHOT = datetime.fromisoformat(snapshot_time().replace("Z", "+00:00"))
_OPP_RE = re.compile(r"\b0068b00001Deal\d+\b", re.IGNORECASE)


def _stage_code(row: dict[str, Any]) -> str:
    return str(row["StageName"]).split(" ", 1)[0]


def _days_since(value: str) -> int:
    timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return max(0, (SNAPSHOT - timestamp).days)


def _account_in_text(text: str) -> str:
    lowered = text.lower()
    return next(
        (
            name
            for name in sorted(ACCOUNTS, key=len, reverse=True)
            if name.lower() in lowered
        ),
        "",
    )


def _owners() -> list[str]:
    return sorted(
        {str(row["owner"]) for row in ACCOUNTS.values()},
        key=len,
        reverse=True,
    )


def parse_scope_from_text(text: str) -> dict[str, str]:
    lowered = text.lower()
    owner = next((name for name in _owners() if name.lower() in lowered), "")
    match = _OPP_RE.search(text)
    return {
        "geo": "east" if re.search(r"\beast\b", lowered) else "",
        "boat": owner,
        "account_name": _account_in_text(text),
        "opp_id": match.group(0) if match else "",
    }


def coerce_scope(
    *,
    geo: str = "",
    boat: str = "",
    account_name: str = "",
    opp_id: str = "",
    query: str = "",
) -> dict[str, str]:
    inferred = parse_scope_from_text(" ".join((query, geo, boat, account_name, opp_id)))
    return {
        "geo": geo.strip().lower() or inferred["geo"],
        "boat": boat.strip() or inferred["boat"],
        "account_name": account_name.strip() or inferred["account_name"],
        "opp_id": opp_id.strip() or inferred["opp_id"],
    }


def territory_for(account: str) -> str:
    return "east" if account in ACCOUNTS else ""


def resolve_scope(
    *,
    geo: str = "",
    boat: str = "",
    account_name: str = "",
    opp_id: str = "",
    query: str = "",
) -> tuple[list[str], dict[str, Any] | None]:
    scope = coerce_scope(
        geo=geo,
        boat=boat,
        account_name=account_name,
        opp_id=opp_id,
        query=query,
    )
    selected = list(ACCOUNTS)
    if scope["opp_id"]:
        row = OPPORTUNITY_BY_ID.get(scope["opp_id"])
        if row is None:
            return [], error(f"Opportunity '{scope['opp_id']}' was not found.")
        selected = [row["Account_Name"]]
    elif scope["account_name"]:
        canonical = resolve_account(scope["account_name"])
        if canonical is None:
            return [], error(
                f"Account '{scope['account_name']}' was not found. "
                f"Known accounts: {', '.join(ACCOUNTS)}."
            )
        selected = [canonical]

    if scope["geo"] and scope["geo"] not in {"all", "east"}:
        return [], error("The snapshot contains only the Americas East team.")

    if scope["boat"]:
        needle = scope["boat"].lower()
        selected = [
            name
            for name in selected
            if needle
            in {
                str(ACCOUNTS[name]["owner"]).lower(),
                str(ACCOUNTS[name]["boat"]).lower(),
            }
        ]
        if not selected:
            return [], error(f"Rep or boat '{scope['boat']}' was not found.")
    return selected, None


def scoped_accounts(
    *, geo: str = "", boat: str = "", account_name: str = "", opp_id: str = "", query: str = ""
) -> tuple[list[str], dict[str, Any] | None]:
    return resolve_scope(
        geo=geo, boat=boat, account_name=account_name, opp_id=opp_id, query=query
    )


def _scoped_opportunities(accounts: list[str]) -> list[dict[str, Any]]:
    allowed = set(accounts)
    return [row for row in OPPORTUNITIES if row["Account_Name"] in allowed]


def _risk_reasons(row: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if int(row["CRM_Score__c"]) < 60:
        reasons.append(f"CRM score is {row['CRM_Score__c']}")
    if _days_since(row["LastModifiedDate"]) > 14:
        reasons.append(f"record is {_days_since(row['LastModifiedDate'])} days old")
    if not row.get("Lead_SE__c") and _stage_code(row) != "SS20":
        reasons.append("lead SE is missing")
    if "At Risk" in str(row.get("Early_Guidance_Tier__c")):
        reasons.append("early guidance is at risk")
    reasons.extend(
        GONG_BY_OPPORTUNITY.get(row["Id"], {}).get("risk_indicators", [])
    )
    return list(dict.fromkeys(reasons))


def forecast_rollup(accounts: list[str]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    commit = 0
    upside = 0
    missing: list[str] = []
    risks: list[str] = []
    for opportunity in _scoped_opportunities(accounts):
        category = opportunity["ForecastCategoryName"]
        amount = int(opportunity["ACV__c"])
        if category == "Commit":
            commit += amount
        elif category in {"Upside", "Best Case"}:
            upside += amount
        reasons = _risk_reasons(opportunity)
        rows.append(
            {
                "account": opportunity["Account_Name"],
                "opp_id": opportunity["Id"],
                "opportunity": opportunity["Name"],
                "owner": opportunity["Owner_Name"],
                "boat": opportunity.get("Boat__c", ""),
                "category": category,
                "commit": amount if category == "Commit" else 0,
                "upside": amount if category in {"Upside", "Best Case"} else 0,
                "close_date": opportunity["CloseDate"],
                "crm_score": opportunity["CRM_Score__c"],
                "missing": reasons,
                "next_step": opportunity["NextStep"],
            }
        )
        missing.extend(f"{opportunity['Account_Name']}: {reason}" for reason in reasons)
        if reasons:
            risks.append(f"{opportunity['Account_Name']}: " + "; ".join(reasons))
    return {
        "accounts": rows,
        "commit_total": commit,
        "upside_total": upside,
        "coverage": len(rows),
        "missing_data": missing,
        "risks": risks,
    }


def stage_validation(accounts: list[str]) -> list[dict[str, Any]]:
    scoped = _scoped_opportunities(accounts)
    details = {row["Id"]: row for row in scoped}
    return [
        {
            **result,
            "account": details[result["opp_id"]]["Account_Name"],
            "opportunity": details[result["opp_id"]]["Name"],
            "owner": details[result["opp_id"]]["Owner_Name"],
        }
        for result in validate_stage_evidence(scoped)
    ]


def deal_risk_review(accounts: list[str]) -> dict[str, Any]:
    validations = stage_validation(accounts)
    return {
        "rollup": forecast_rollup(accounts),
        "stage_validations": validations,
        "stage_failures": [
            row for row in validations if row["status"] in {"failed", "unverifiable"}
        ],
    }


def rep_review(accounts: list[str]) -> dict[str, Any]:
    scoped = _scoped_opportunities(accounts)
    owner_ids = {row["OwnerId"] for row in scoped}
    employees = employee_by_sfdc_id()
    tiers = productivity_tier_by_rep()
    metrics: list[dict[str, Any]] = []
    expectations: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    coaching: list[dict[str, Any]] = []
    from agents.new_data_store import gong

    scorecards = {row["rep_id"]: row for row in gong()["rep_scorecards"]}
    for user in [row for row in sales_users() if row["Id"] in owner_ids]:
        employee = employees[user["Id"]]
        actual = employee["quarterly_actuals_qtd"]
        tier = tiers[user["Id"]]
        weekly = tier["weekly_floors"]
        quarterly = tier["quarterly_floors"]
        row = {
            "rep_id": user["Id"],
            "rep_name": user["Name"],
            "boat": user.get("Boat__c", ""),
            "meetings": actual["meetings_completed_weekly_avg"],
            "outbound_touchpoints": actual["outbound_touchpoints_weekly_avg"],
            "new_opportunities": actual["new_opportunities_created"],
            "pipeline_created": actual["new_pipeline_created_acv"],
            "stage_advances": actual["stage_advances"],
            "forecast_submission_rate_pct": actual["forecast_submission_rate_pct"],
            "next_step_compliance_pct": actual["next_step_compliance_pct"],
            "quota": employee["quota_assignment_q3"],
            "ramp_status": employee["ramp_status"],
            "performance_band": employee["performance_band"],
            **scorecards.get(user["Id"], {}),
        }
        expectation = {
            "rep_id": user["Id"],
            "rep_name": user["Name"],
            "tier_name": tier["tier_name"],
            **weekly,
            **quarterly,
        }
        missed: list[str] = []
        comparisons = (
            ("meetings", "customer_meetings_min"),
            ("outbound_touchpoints", "outbound_prospecting_touchpoints_min"),
            ("new_opportunities", "new_opportunities_created_min"),
            ("pipeline_created", "new_pipeline_created_acv_min"),
            ("stage_advances", "stage_advances_min"),
            ("next_step_compliance_pct", "next_step_compliance_pct_min"),
        )
        for actual_key, minimum_key in comparisons:
            if row[actual_key] < expectation[minimum_key]:
                missed.append(actual_key)
        if weekly["forecast_submitted_weekly"] and row[
            "forecast_submission_rate_pct"
        ] < 100:
            missed.append("forecast_submission")
        metrics.append(row)
        expectations.append(expectation)
        if missed:
            gaps.append({**row, "missed_expectations": missed})
            coaching.append(
                {
                    "rep_id": user["Id"],
                    "rep_name": user["Name"],
                    "reason": f"Below {tier['tier_name']}: {', '.join(missed)}",
                    "topic": "Productivity, forecast discipline, and next steps",
                    "coaching_recommendation": scorecards.get(user["Id"], {}).get(
                        "coaching_recommendation", ""
                    ),
                }
            )

    oversight: list[dict[str, Any]] = []
    for opportunity in scoped:
        reasons = _risk_reasons(opportunity)
        if int(opportunity["ACV__c"]) >= 400_000 and not opportunity.get(
            "Backup_Deal_Id__c"
        ):
            reasons.append("large deal has no backup opportunity")
        if reasons:
            oversight.append(
                {
                    "opp_id": opportunity["Id"],
                    "opportunity": opportunity["Name"],
                    "account": opportunity["Account_Name"],
                    "rep_id": opportunity["OwnerId"],
                    "rep_name": opportunity["Owner_Name"],
                    "reason": "; ".join(reasons),
                    "manager_action": "Review the deal plan and assign a dated corrective next step.",
                    "severity": (
                        "high" if int(opportunity["CRM_Score__c"]) < 60 else "medium"
                    ),
                }
            )
    return {
        "expectations": expectations,
        "rep_metrics": metrics,
        "productivity_gaps": gaps,
        "coaching_queue": coaching,
        "oversight_deals": oversight,
    }


def future_pipeline(accounts: list[str], quarter: str = "") -> dict[str, Any]:
    scoped = _scoped_opportunities(accounts)
    quarter_key = quarter.strip().upper().replace(" ", "")
    period_map = {"Q+1": "Q4-FY26", "Q+2": "Q1-FY27"}
    quota_rows = quarterly_quotas()
    models: list[dict[str, Any]] = []
    for label, fiscal_quarter in period_map.items():
        if quarter_key and label != quarter_key:
            continue
        rows = [
            row for row in scoped if row["Fiscal_Quarter__c"] == fiscal_quarter
        ]
        pipeline = sum(int(row["ACV__c"]) for row in rows)
        weighted = round(
            sum(int(row["ACV__c"]) * float(row["Probability"]) / 100 for row in rows)
        )
        quota = int(quota_rows[fiscal_quarter]["total_team_quota"])
        models.append(
            {
                "quarter": label,
                "fiscal_quarter": fiscal_quarter,
                "geo": "east",
                "model": "Salesforce probability-weighted opportunity ACV",
                "assumptions": ["Uses each opportunity's recorded Probability"],
                "pipeline": pipeline,
                "weighted_forecast": weighted,
                "quota": quota,
                "coverage_ratio": round(pipeline / quota, 2) if quota else 0,
                "gap_to_quota": max(0, quota - weighted),
                "opportunity_ids": [row["Id"] for row in rows],
                "risks": [
                    f"{row['Account_Name']}: " + "; ".join(_risk_reasons(row))
                    for row in rows
                    if _risk_reasons(row)
                ],
                "gaps": [] if rows else [f"No opportunities close in {label}."],
            }
        )

    rules = stage_rules()
    stagnation: list[dict[str, Any]] = []
    for row in scoped:
        stage = _stage_code(row)
        days = int(row["Days_In_Current_Stage__c"])
        threshold = int(
            rules.get(stage, {}).get("max_stagnation_threshold_days", 0)
        )
        stagnation.append(
            {
                "opp_id": row["Id"],
                "opportunity": row["Name"],
                "account": row["Account_Name"],
                "stage_name": stage,
                "days_in_stage": days,
                "threshold_days": threshold,
                "stagnated": bool(threshold and days > threshold),
                "stage_entered_date": row["Stage_Entered_Date__c"],
            }
        )
    return {
        "quarters": models,
        "stagnated_deals": [row for row in stagnation if row["stagnated"]],
        "weighted_forecast_total": sum(row["weighted_forecast"] for row in models),
        "pipeline_total": sum(row["pipeline"] for row in models),
        "risks": [risk for row in models for risk in row["risks"]],
        "gaps": [gap for row in models for gap in row["gaps"]],
    }
