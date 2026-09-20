"""Structured synthesis agent; the workflow renders its output as markdown."""

from __future__ import annotations

from google.adk.agents import Agent

from agents.constants import SYNTHESIS_GEN_CONFIG, SYNTHESIS_MODEL
from agents.synthesis.prompt import SYNTHESIS_INSTRUCTION
from models.synthesis_output import SynthesisOutput

synthesis_agent = Agent(
    name="synthesis",
    model=SYNTHESIS_MODEL,
    description=(
        "Merges specialist findings into one manager-facing answer with Summary, "
        "Key Insights, Recommended Actions, and Artifacts. Call this after "
        "every specialist run."
    ),
    instruction=SYNTHESIS_INSTRUCTION,
    tools=[],
    generate_content_config=SYNTHESIS_GEN_CONFIG,
    mode="single_turn",
    output_key="synthesis_result",
    output_schema=SynthesisOutput,
    disallow_transfer_to_parent=True,
    disallow_transfer_to_peers=True,
)
