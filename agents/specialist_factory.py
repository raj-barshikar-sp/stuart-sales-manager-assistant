"""Build single-turn specialists with the same ADK contract."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from google.adk.agents import Agent
from pydantic import BaseModel

from agents.constants import GEMINI_MODEL, SAFE_GEN_CONFIG
from agents.reply_contract import REPLY_CONTRACT


def make_specialist(
    *,
    name: str,
    description: str,
    instruction: str,
    tools: Sequence[Callable[..., Any]],
    output_schema: type[BaseModel],
    output_key: str,
) -> Agent:
    """Flash specialist: tools first, structured JSON, no chat transfer."""
    return Agent(
        name=name,
        model=GEMINI_MODEL,
        description=description,
        instruction=f"{instruction}\n\n{REPLY_CONTRACT}",
        tools=list(tools),
        generate_content_config=SAFE_GEN_CONFIG,
        mode="single_turn",
        output_key=output_key,
        output_schema=output_schema,
        disallow_transfer_to_parent=True,
        disallow_transfer_to_peers=True,
    )
