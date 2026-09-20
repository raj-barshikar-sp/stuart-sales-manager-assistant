"""Forecast modeling specialist."""

from __future__ import annotations

from typing import Any

from agents.sales_manager_data import scoped_accounts
from agents.sales_manager_query import query_forecast_modeling
from agents.specialist_factory import make_specialist
from agents.tool_helpers import success
from agents.tooling import tool
from models.specialist_outputs import ForecastModelingOutput


@tool
async def inspect_forecast_model(
    geo: str = "",
    boat: str = "",
    account_name: str = "",
    opp_id: str = "",
    query: str = "",
) -> dict[str, Any]:
    """Model current pacing, Q+1/Q+2 forecast, stagnation, risks, and gaps."""
    accounts, err = scoped_accounts(
        geo=geo, boat=boat, account_name=account_name, opp_id=opp_id, query=query
    )
    return err or success(query_forecast_modeling(query, accounts))


forecast_modeling_specialist_agent = make_specialist(
    name="forecast_modeling_specialist",
    description=(
        "Forecast modeling: current deal risk, verbal-call pacing, conversion "
        "history, quotas, Q+1/Q+2 forecast, stagnation, risks, and gaps."
    ),
    instruction=(
        "Always call inspect_forecast_model. Use the returned Salesforce "
        "probabilities, quotas, conversion history, Gong calls, and official "
        "stagnation thresholds without substituting assumptions."
    ),
    tools=[inspect_forecast_model],
    output_schema=ForecastModelingOutput,
    output_key="forecast_modeling_specialist_result",
)
