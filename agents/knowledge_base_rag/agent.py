"""Knowledge-base RAG specialist backed by Atlassian Rovo MCP v2."""

from __future__ import annotations

import base64
import os

from google.adk.agents import Agent
from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams

from agents.constants import GEMINI_MODEL, SAFE_GEN_CONFIG
from models.specialist_outputs import KnowledgeBaseRagOutput


def rovo_headers() -> dict[str, str]:
    key = os.getenv("ROVO_MCP_API_KEY", "").strip()
    email = os.getenv("ROVO_MCP_EMAIL", "").strip()
    if not key:
        return {}
    if email:
        token = base64.b64encode(f"{email}:{key}".encode()).decode()
        return {"Authorization": f"Basic {token}"}
    return {"Authorization": f"Bearer {key}"}


rovo_tools = McpToolset(
    connection_params=StreamableHTTPConnectionParams(
        url=os.getenv("ROVO_MCP_URL", "https://mcp.atlassian.com/v2/mcp"),
        headers=rovo_headers(),
        timeout=15,
        sse_read_timeout=120,
    ),
    tool_filter=["searchConfluence", "getConfluenceContent"],
    tool_list_cache_ttl_seconds=300,
)

knowledge_base_rag_agent = Agent(
    name="knowledge_base_rag",
    model=GEMINI_MODEL,
    description=(
        "Approved policy, compensation, product, packaging, competitive, "
        "Deal Desk, and CRM stage-gate knowledge from Confluence."
    ),
    instruction=(
        "Answer Sales Manager knowledge questions from approved Confluence "
        "content through Atlassian Rovo only. Use searchConfluence, then "
        "getConfluenceContent. Never use Jira, general knowledge, or write "
        "tools. Preserve exact thresholds and return KnowledgeBaseRagOutput "
        "with complete PolicySection records. Return status error when no "
        "approved content supports the question."
    ),
    tools=[rovo_tools],
    generate_content_config=SAFE_GEN_CONFIG,
    mode="single_turn",
    output_schema=KnowledgeBaseRagOutput,
    output_key="knowledge_base_rag_result",
    disallow_transfer_to_parent=True,
    disallow_transfer_to_peers=True,
)
