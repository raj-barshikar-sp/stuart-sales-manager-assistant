"""Session memory for the manager's live account, territory, and opportunity."""

from __future__ import annotations

import re
from typing import Any

from google.adk.agents.callback_context import CallbackContext
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext

from agents.new_data_store import (
    accounts,
    list_accounts,
    resolve_account,
    territories,
)
from agents.orchestrator.prompt import TASK_AGENT_IDS
from agents.tooling import tool

SESSION_KEYS = ("ae_name", "last_account", "last_territory", "last_opportunity")
ACCOUNTS = accounts()
TERRITORIES = territories()


def seed_session_state(callback_context: CallbackContext) -> None:
    """Guarantee placeholder keys exist so instruction injection does not fail."""
    for key in SESSION_KEYS:
        if not callback_context.state.get(key):
            callback_context.state[key] = ""


def seed_context_from_text(state: Any, text: str) -> dict[str, str]:
    """Capture account and territory before routing starts."""
    return apply_working_context(
        state,
        account=detect_account_in_text(text) or "",
        territory=detect_territory_in_text(text) or "",
    )


def detect_account_in_text(text: str) -> str | None:
    """Return a canonical account mentioned in free text, if any."""
    if not text.strip():
        return None
    # Prefer longer names so "7-Eleven" wins over a partial.
    ranked = sorted(list_accounts(), key=len, reverse=True)
    lowered = text.lower()
    for name in ranked:
        if name.lower() in lowered:
            return name
        record = ACCOUNTS[name]
        for alias in [record.get("legal_name", ""), *record.get("aliases", [])]:
            if alias and str(alias).lower() in lowered:
                return name
    for token in text.replace(",", " ").split():
        resolved = resolve_account(token)
        if resolved:
            return resolved
    return None


def detect_territory_in_text(text: str) -> str | None:
    lowered = text.lower()
    for territory in ("west", "central", "south", "east"):
        if re.search(rf"\b{territory}\b", lowered):
            return territory
    return None


def _territory_for_account(account: str) -> str:
    for territory, names in TERRITORIES.items():
        if territory != "all" and account in names:
            return territory
    return ""


def apply_working_context(
    state: Any,
    *,
    account: str = "",
    territory: str = "",
    ae_name: str = "",
    opportunity: str = "",
) -> dict[str, str]:
    """Write known context onto session state. Empty strings are ignored."""
    if account:
        canonical = resolve_account(account) or account
        state["last_account"] = canonical
        if canonical in ACCOUNTS:
            state["ae_name"] = ACCOUNTS[canonical]["owner"]
            inferred = _territory_for_account(canonical)
            if inferred:
                state["last_territory"] = inferred
    if territory:
        state["last_territory"] = territory.strip().lower()
    if ae_name:
        state["ae_name"] = ae_name
    if opportunity:
        state["last_opportunity"] = opportunity
    return {
        "ae_name": str(state.get("ae_name") or ""),
        "last_account": str(state.get("last_account") or ""),
        "last_territory": str(state.get("last_territory") or ""),
        "last_opportunity": str(state.get("last_opportunity") or ""),
    }


@tool
def remember_working_context(
    account_name: str = "",
    territory: str = "",
    ae_name: str = "",
    opportunity: str = "",
    tool_context: ToolContext | None = None,
) -> dict[str, str]:
    """Remember the user, live account, territory, and opportunity for follow-ups.

    Call this when the user names an account, a territory, an opportunity, or themselves.
    Follow-ups like "what about data quality?" reuse last_account.

    Args:
        account_name: Account to remember, for example "7-Eleven".
        territory: west, central, south, east, or all.
        ae_name: User name if they introduce themselves.
        opportunity: Opportunity name or id, for example "Project Phoenix" or OPP-712.
    """
    if tool_context is None:
        return {
            "ae_name": ae_name,
            "last_account": account_name,
            "last_territory": territory,
            "last_opportunity": opportunity,
        }
    return apply_working_context(
        tool_context.state,
        account=account_name,
        territory=territory,
        ae_name=ae_name,
        opportunity=opportunity,
    )


def remember_after_specialist(
    tool: BaseTool,
    args: dict[str, Any],
    tool_context: ToolContext,
    tool_response: dict[str, Any],
) -> None:
    """After a specialist runs, remember any account or territory in the request."""
    if tool.name not in TASK_AGENT_IDS:
        return None
    blob = str(
        args.get("request")
        or args.get("account_name")
        or args.get("query")
        or ""
    )
    if isinstance(tool_response, dict):
        blob = f"{blob} {tool_response.get('account') or ''}"
    account = detect_account_in_text(blob)
    territory = detect_territory_in_text(blob)
    opportunity = str(args.get("opp_id") or args.get("query") or "")
    apply_working_context(
        tool_context.state,
        account=account or "",
        territory=territory or "",
        opportunity=opportunity,
    )
    return None
