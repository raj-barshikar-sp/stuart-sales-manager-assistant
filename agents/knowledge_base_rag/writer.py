"""Hidden writer for manager-facing answers from retrieved sections."""

from __future__ import annotations

from google.adk.agents import Agent
from google.adk.agents.readonly_context import ReadonlyContext

from agents.constants import SYNTHESIS_GEN_CONFIG, SYNTHESIS_MODEL
from agents.knowledge_base_rag.prompt import POLICY_ANSWER_INSTRUCTION


def _instruction(ctx: ReadonlyContext) -> str:
    content = ctx.user_content
    request = (
        "\n".join(
            part.text
            for part in (content.parts or [])
            if getattr(part, "text", None)
        )
        if content
        else ""
    )
    if not request.strip():
        return POLICY_ANSWER_INSTRUCTION
    return f"{POLICY_ANSWER_INSTRUCTION}\n\n{request}"


policy_answer_agent = Agent(
    name="policy_answer",
    model=SYNTHESIS_MODEL,
    description="Writes a grounded conversational answer from approved sections.",
    instruction=_instruction,
    tools=[],
    generate_content_config=SYNTHESIS_GEN_CONFIG,
    mode="single_turn",
    output_key="policy_answer",
    disallow_transfer_to_parent=True,
    disallow_transfer_to_peers=True,
)
