"""Task menu, filter catalogs, and prompt composition for the Sales Manager workspace."""

from __future__ import annotations

from dataclasses import dataclass, field

from agents.new_data_store import (
    accounts as load_accounts,
    data_ready,
    normalized_opportunities as load_opportunities,
    territories,
)

ACCOUNTS = load_accounts()
TERRITORIES = territories()

TASK_MENU: tuple[dict, ...] = (
    {
        "id": "forecasting",
        "label": "Forecasting",
        "items": (
            {
                "id": "deal_forecast_risks",
                "label": "Deal and forecast risks",
                "default_prompt": "Review my team's deals and forecast for east and spot the biggest risks to the number.",
                "scoped_prompt": "Review the deals and forecast for {account} and spot the biggest risks to the number.",
            },
            {
                "id": "stage_validation",
                "label": "Sales Stage Validator",
                "agent": "crm_intelligence_specialist",
                "default_prompt": "Run the Sales Stage Validator across east and list every deal whose stage is missing required evidence.",
                "scoped_prompt": "Run the Sales Stage Validator on {account} and list every deal whose stage is missing required evidence.",
            },
        ),
    },
    {
        "id": "forecast_inspection",
        "label": "Forecast inspection",
        "items": (
            {
                "id": "verbal_call",
                "label": "Weekly verbal call in Rev Intel",
                "default_prompt": "Pull the weekly verbal call in Rev Intel for my east team and flag any rep missing a week or ACV gap.",
                "scoped_prompt": "Pull the weekly verbal call in Rev Intel for {territory} and flag any rep missing a week or ACV gap.",
            },
            {
                "id": "call_vs_rollup",
                "label": "Verbal call vs deal roll-up",
                "default_prompt": "Compare my team's verbal call to the CRM deal roll-up for east and call out any mismatch.",
                "scoped_prompt": "Compare the verbal call to the CRM deal roll-up for {territory} and call out any mismatch.",
            },
            {
                "id": "pipeline_cover",
                "label": "Pipeline cover to call",
                "agent": "crm_intelligence_specialist",
                "default_prompt": "What is pipeline cover to the verbal call for east, and is my team's coverage healthy?",
                "scoped_prompt": "What is pipeline cover to the verbal call for {territory}, and is coverage healthy?",
            },
            {
                "id": "large_deal_backup",
                "label": "Large-deal backup",
                "agent": "crm_intelligence_specialist",
                "default_prompt": "For large deals in east, does my team have a backup opportunity, and which deals are uncovered?",
                "scoped_prompt": "For large deals in {territory}, is there a backup opportunity, and which deals are uncovered?",
            },
            {
                "id": "crm_score",
                "label": "CRM score this quarter",
                "agent": "crm_intelligence_specialist",
                "default_prompt": "What is the CRM score for my team's deals this quarter in east, and which deals look weak?",
                "scoped_prompt": "What is the CRM score for deals this quarter for {account}, and which deals look weak?",
            },
            {
                "id": "pacing",
                "label": "Pacing vs conversion",
                "agent": "forecast_modeling_specialist",
                "default_prompt": "Is my east team pacing to the verbal call based on conversion rates?",
                "scoped_prompt": "Is {territory} pacing to the verbal call based on conversion rates?",
            },
            {
                "id": "weekly_update",
                "label": "Weekly update and next steps",
                "default_prompt": "Do my reps have a weekly update (next step and manager note) for east, and which deals are stale?",
                "scoped_prompt": "Does {account} have a weekly update (next step and manager note), and which deals are stale?",
            },
        ),
    },
    {
        "id": "rep_participation",
        "label": "Rep participation",
        "items": (
            {
                "id": "reps_need_help",
                "label": "Reps who need help",
                "default_prompt": "Which reps need help in east, and what does the participation data show?",
                "scoped_prompt": "Which reps need help in {territory}, and what does the participation data show?",
            },
            {
                "id": "coaching_meetings",
                "label": "Coaching meetings to hold",
                "default_prompt": "Which coaching rep meetings should I hold in east this week, and on what topic?",
                "scoped_prompt": "Which coaching rep meetings should I hold in {territory} this week, and on what topic?",
            },
            {
                "id": "oversight_deals",
                "label": "Deals that need my oversight",
                "default_prompt": "Which deals need my oversight in east, and what action is expected from me?",
                "scoped_prompt": "Does {account} have deals that need my oversight, and what action is expected from me?",
            },
            {
                "id": "productivity_gaps",
                "label": "Productivity vs minimum expectations",
                "default_prompt": "Which reps missed minimum expectation productivity metrics in east?",
                "scoped_prompt": "Which reps missed minimum expectation productivity metrics in {territory}?",
            },
        ),
    },
    {
        "id": "future_pipeline",
        "label": "Future quarter pipeline overview",
        "items": (
            {
                "id": "stagnated_deals",
                "label": "Stagnated deals",
                "default_prompt": "Which deals have stagnated in east, and how long have they been stuck?",
                "scoped_prompt": "Which deals have stagnated for {account}, and how long have they been stuck?",
            },
            {
                "id": "modeled_forecast",
                "label": "Q+1 and Q+2 modeled forecast",
                "default_prompt": "What do the modeled Q+1 and Q+2 forecasts look like for east against target?",
                "scoped_prompt": "What do the modeled Q+1 and Q+2 forecasts look like for {territory} against target?",
            },
            {
                "id": "future_risks_gaps",
                "label": "Future-quarter risks and gaps",
                "default_prompt": "What are the risks and gaps in my east pipeline for Q+1 and Q+2?",
                "scoped_prompt": "What are the risks and gaps in the {territory} pipeline for Q+1 and Q+2?",
            },
        ),
    },
    {
        "id": "faq",
        "label": "Manager policy & knowledge",
        "items": (
            {
                "id": "knowledge_base",
                "label": "Ask policy & product FAQ",
                "agent": "knowledge_base_rag",
                "default_prompt": (
                    "What do the approved Sales Manager documents say about "
                    "rules of engagement, Deal Desk policy, compensation, "
                    "products, or competitive positioning?"
                ),
                "scopes": (),
            },
        ),
    },
)

GROUP_AGENT = {
    "forecasting": "forecast_modeling_specialist",
    "forecast_inspection": "activity_engagement_specialist",
    "rep_participation": "rep_performance_specialist",
    "future_pipeline": "forecast_modeling_specialist",
    "faq": "knowledge_base_rag",
}

REPORT_TYPES: tuple[dict[str, str], ...] = (
    {"id": "this_quarter", "label": "This quarter"},
    {"id": "q_plus_1", "label": "Q+1"},
    {"id": "q_plus_2", "label": "Q+2"},
)

_TASKS_BY_ID = {
    item["id"]: item
    for group in TASK_MENU
    for item in group["items"]
}

TASK_AGENT = {
    item["id"]: str(item.get("agent") or GROUP_AGENT[group["id"]])
    for group in TASK_MENU
    if group["id"] in GROUP_AGENT
    for item in group["items"]
}


@dataclass
class FilterSelection:
    geos: list[str] = field(default_factory=list)
    boats: list[str] = field(default_factory=list)
    opps: list[str] = field(default_factory=list)
    report_types: list[str] = field(default_factory=list)


def agent_for_task(task_id: str) -> str:
    """Return the specialist that owns a menu task, or an empty string."""
    return TASK_AGENT.get(task_id, "")


def _territory_for_account(account: str) -> str:
    for territory, names in TERRITORIES.items():
        if territory != "all" and account in names:
            return territory
    return ""


def workspace_catalog() -> dict:
    """Return tasks and filters that have a working agent and dummy JSON rows."""
    assistant = {
        "name": "Stuart",
        "title": "Stuart — Sales Manager Assistant",
        "tagline": "Inspect the forecast, coach your reps, and see next quarter early.",
    }
    if not data_ready():
        return {
            "assistant": assistant,
            "tasks": [],
            "filters": {"geos": [], "boats": [], "opps": [], "report_types": []},
        }
    accounts = [
        {"account": name, "owner": row["owner"], "geo": "east"}
        for name, row in load_accounts().items()
    ]
    geos = [
        {"id": geo, "label": geo.title()}
        for geo in ("west", "central", "south", "east")
        if any(row["geo"] == geo for row in accounts)
    ]
    boats = [
        {
            "id": name,
            "label": name,
            "geos": sorted(
                {row["geo"] for row in accounts if row.get("owner") == name}
            ),
        }
        for name in sorted({row["owner"] for row in accounts if row.get("owner")})
    ]
    owner_of = {row["account"]: row["owner"] for row in accounts}
    geo_of = {row["account"]: row["geo"] for row in accounts}
    opps = [
        {
            "id": row["opp_id"],
            "account": row["account"],
            "territory": geo_of.get(row["account"], ""),
            "owner": owner_of.get(row["account"], ""),
            "label": f"{row['opp_id']} · {row['account']} · {row['stage_name']}",
        }
        for source in load_opportunities()
        for row in [
            {
                "opp_id": source["Id"],
                "account": source["Account_Name"],
                "stage_name": source["StageName"],
            }
        ]
    ]
    return {
        "assistant": assistant,
        "tasks": [
            {
                "id": group["id"],
                "label": group["label"],
                "agent": GROUP_AGENT[group["id"]],
                "items": [
                    {**item, "agent": TASK_AGENT[item["id"]]}
                    for item in group["items"]
                ],
            }
            for group in TASK_MENU
            if group["id"] in GROUP_AGENT
        ],
        "filters": {
            "geos": geos,
            "boats": boats,
            "opps": opps,
            "report_types": [dict(item) for item in REPORT_TYPES],
        },
    }


def _opp_index() -> dict[str, dict[str, str]]:
    catalog = workspace_catalog()
    return {item["id"]: item for item in catalog["filters"]["opps"]}


def _first_account(selection: FilterSelection) -> str:
    opps = _opp_index()
    for opp_id in selection.opps:
        if opp_id in opps:
            return opps[opp_id]["account"]
    for geo in selection.geos:
        names = TERRITORIES.get(geo, [])
        if names:
            return names[0]
    for boat in selection.boats:
        for account, record in ACCOUNTS.items():
            if record.get("owner") == boat:
                return account
    return ""


def _first_territory(selection: FilterSelection, account: str) -> str:
    if selection.geos:
        return selection.geos[0]
    return _territory_for_account(account) or "east"


def compose_task_message(
    task_id: str, selection: FilterSelection | None = None
) -> str:
    """Turn a left-nav task plus right-rail filters into one manager prompt."""
    task = _TASKS_BY_ID.get(task_id)
    if task is None:
        raise KeyError(task_id)
    selection = selection or FilterSelection()
    account = _first_account(selection)
    territory = _first_territory(selection, account)
    if account and task.get("scoped_prompt"):
        text = str(task["scoped_prompt"]).format(
            account=account, territory=territory
        )
    else:
        text = str(task["default_prompt"])
    return apply_filter_notes(text, selection)


def filter_notes(selection: FilterSelection) -> list[str]:
    notes: list[str] = []
    if selection.geos:
        notes.append("Territory: " + ", ".join(selection.geos))
    if selection.boats:
        notes.append("Reps: " + ", ".join(selection.boats))
    if selection.opps:
        labels = [
            _opp_index()[opp_id]["label"]
            for opp_id in selection.opps
            if opp_id in _opp_index()
        ]
        if labels:
            notes.append("Deals: " + "; ".join(labels))
    if selection.report_types:
        labels = [
            item["label"]
            for item in REPORT_TYPES
            if item["id"] in selection.report_types
        ]
        if labels:
            notes.append("Horizon: " + ", ".join(labels))
    return notes


def apply_filter_notes(text: str, selection: FilterSelection | None) -> str:
    notes = filter_notes(selection or FilterSelection())
    if not notes:
        return text
    return text + "\n\nWorking filters:\n" + "\n".join(f"- {note}" for note in notes)


def default_starters() -> list[str]:
    return [str(item["default_prompt"]) for group in TASK_MENU for item in group["items"]]
