"""Activity and engagement specialist."""

from __future__ import annotations

from typing import Any

from agents.sales_manager_data import scoped_accounts
from agents.sales_manager_query import query_activity_engagement
from agents.specialist_factory import make_specialist
from agents.tool_helpers import success
from agents.tooling import tool
from models.specialist_outputs import ActivityEngagementOutput


@tool
async def inspect_activity_engagement(
    geo: str = "",
    boat: str = "",
    account_name: str = "",
    opp_id: str = "",
    query: str = "",
) -> dict[str, Any]:
    """Inspect Gong verbal calls plus calendar and email engagement."""
    accounts, err = scoped_accounts(
        geo=geo, boat=boat, account_name=account_name, opp_id=opp_id, query=query
    )
    return err or success(query_activity_engagement(query, accounts))


activity_engagement_specialist_agent = make_specialist(
    name="activity_engagement_specialist",
    description=(
        "Activity and engagement: weekly verbal submissions, Gong deal health, "
        "calendar/email engagement, sentiment, and stale next steps."
    ),
    instruction=(
        "Always call inspect_activity_engagement. Use only returned Gong, "
        "calendar, email, and Salesforce activity records."
    ),
    tools=[inspect_activity_engagement],
    output_schema=ActivityEngagementOutput,
    output_key="activity_engagement_specialist_result",
)
