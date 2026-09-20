"""Synthesis agent is LLM-only and formats a merged AE answer."""

from __future__ import annotations

from agents.synthesis.agent import synthesis_agent
from agents.synthesis.prompt import SYNTHESIS_INSTRUCTION
from models.synthesis_output import CopyReadyArtifact, RecommendedAction, SynthesisOutput


def test_agent_has_no_tools() -> None:
    assert synthesis_agent.name == "synthesis"
    assert synthesis_agent.mode == "single_turn"
    assert synthesis_agent.tools == []
    assert synthesis_agent.output_key == "synthesis_result"
    assert synthesis_agent.model == "gemini-3.6-flash"
    assert synthesis_agent.output_schema is SynthesisOutput


def test_prompt_merge_personalize_strip_format() -> None:
    prompt = SYNTHESIS_INSTRUCTION.lower()
    assert "merge" in prompt
    assert "personalize" in prompt
    assert "strip sources" in prompt
    assert "required synthesisoutput schema" in prompt
    assert "never use bracket placeholders" in prompt
    assert "never name" in prompt
    assert "agent" in prompt
    assert "verified_records" in prompt
    assert "plain english" in prompt or "readable sentences" in prompt
    assert "zero is a real" in prompt
    assert "fresh pull" in prompt
    assert "sales manager" in prompt
    assert "grounded" in prompt or "verified" in prompt


def test_synthesis_output_model() -> None:
    output = SynthesisOutput(
        summary="Meridian is in technical validation on a $3.1M expansion.",
        insights=["RFP is due September 5.", "CMIO is the champion."],
        actions=[
            RecommendedAction(
                action="Send the BAA-covered demo environment before the walkthrough.",
                paste="Sending the BAA-covered demo env before Thursday's walkthrough.",
            )
        ],
        artifacts=[
            CopyReadyArtifact(
                title="Nursing informatics workflow script",
                kind="talking_points",
                body="Walk the CMIO through the nursing informatics workflow, then ask for the RFP slot.",
            )
        ],
    )
    assert output.summary.startswith("Meridian")
    assert len(output.insights) == 2
    assert output.actions[0].owner == "you"
    assert output.artifacts[0].kind == "talking_points"
    dumped = output.model_dump()
    assert set(dumped) == {"summary", "insights", "actions", "artifacts"}
