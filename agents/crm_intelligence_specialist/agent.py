"""CRM intelligence specialist."""

from __future__ import annotations

from typing import Any

from agents.sales_manager_data import scoped_accounts
from agents.sales_manager_query import query_crm_intelligence
from agents.specialist_factory import make_specialist
from agents.tool_helpers import success
from agents.tooling import tool
from models.specialist_outputs import CrmIntelligenceOutput


@tool
async def inspect_crm_intelligence(
    geo: str = "",
    boat: str = "",
    account_name: str = "",
    opp_id: str = "",
    query: str = "",
) -> dict[str, Any]:
    """Inspect CRM score, roll-up, backup, and official stage evidence."""
    accounts, err = scoped_accounts(
        geo=geo, boat=boat, account_name=account_name, opp_id=opp_id, query=query
    )
    return err or success(query_crm_intelligence(query, accounts))


crm_intelligence_specialist_agent = make_specialist(
    name="crm_intelligence_specialist",
    description=(
        "CRM intelligence: stage evidence, CRM score, deal roll-up, pipeline "
        "coverage, and large-deal backup."
    ),
    instruction=(
        "Always call inspect_crm_intelligence. Use only returned Salesforce "
        "records and deterministic hygiene results. Treat unverifiable evidence "
        "as unknown, never as passed or failed."
    ),
    tools=[inspect_crm_intelligence],
    output_schema=CrmIntelligenceOutput,
    output_key="crm_intelligence_specialist_result",
)
