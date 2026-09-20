"""Shared mock-tool helpers for specialists."""

from __future__ import annotations

import logging
from typing import Any

from agents.activity import log_activity, preview
from agents.new_data_store import list_accounts, resolve_account


def error(message: str) -> dict[str, Any]:
    log_activity("tool.error", message=preview(message, 120))
    return {"status": "error", "message": message, "data": None}


def success(data: dict[str, Any]) -> dict[str, Any]:
    tables = sorted(data.get("records") or {}) if isinstance(data, dict) else []
    log_activity(
        "tool.success",
        topic=data.get("topic") if isinstance(data, dict) else "",
        tables=tables,
        level=logging.DEBUG,
    )
    return {"status": "success", "data": data}


def require_account(account_name: str) -> tuple[str | None, dict[str, Any] | None]:
    canonical = resolve_account(account_name)
    if canonical is None:
        return None, error(
            f"Account '{account_name}' was not found. "
            f"Known accounts: {', '.join(list_accounts())}."
        )
    return canonical, None
