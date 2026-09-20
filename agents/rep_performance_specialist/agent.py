"""Rep performance specialist."""

from __future__ import annotations

from typing import Any

from agents.sales_manager_data import scoped_accounts
from agents.sales_manager_query import query_rep_performance
from agents.specialist_factory import make_specialist
from agents.tool_helpers import success
from agents.tooling import tool
from models.specialist_outputs import RepPerformanceOutput


@tool
async def inspect_rep_performance(
    geo: str = "",
    boat: str = "",
    account_name: str = "",
    opp_id: str = "",
    query: str = "",
) -> dict[str, Any]:
    """Compare rep actuals with the applicable Workday tenure-tier minima."""
    accounts, err = scoped_accounts(
        geo=geo, boat=boat, account_name=account_name, opp_id=opp_id, query=query
    )
    return err or success(query_rep_performance(query, accounts))


rep_performance_specialist_agent = make_specialist(
    name="rep_performance_specialist",
    description=(
        "Rep performance: Workday productivity minima and actuals, Gong "
        "coaching, manager oversight, and participation gaps."
    ),
    instruction=(
        "Always call inspect_rep_performance. Compare each rep only with their "
        "returned tenure tier and use the returned coaching evidence."
    ),
    tools=[inspect_rep_performance],
    output_schema=RepPerformanceOutput,
    output_key="rep_performance_specialist_result",
)
