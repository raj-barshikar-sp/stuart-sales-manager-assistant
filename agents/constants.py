"""Shared constants for Seller Co-Pilot agents."""

import os

from google.genai import types

GEMINI_MODEL = os.getenv("SELLER_COPILOT_MODEL", "gemini-3.6-flash")
SYNTHESIS_MODEL = os.getenv(
    "SELLER_COPILOT_SYNTHESIS_MODEL", "gemini-3.6-flash"
)
TOOL_LATENCY_SECONDS = float(
    os.getenv("SELLER_COPILOT_MOCK_LATENCY_SECONDS", "0")
)
CHILD_TIMEOUT_SECONDS = float(
    os.getenv("SELLER_COPILOT_CHILD_TIMEOUT_SECONDS", "90")
)

GREETING_REPLY = (
    "Hey — I'm Stuart from Project Gru. I can review forecast risk, inspect the "
    "call, coach the team, model future pipeline, or answer sales FAQs. "
    "What do you need?"
)
THANKS_REPLY = "Anytime. What should Stuart work on next?"
ACK_REPLY = "Glad that helped. What should Stuart work on next?"
OFF_TOPIC_REPLY = (
    "I focus on Sales Manager work — forecast inspection, deal and stage risk, "
    "rep coaching, future pipeline, and sales FAQs. What do you need?"
)

# Flash + tools: keep thinking cheap so function calls stay well-formed.
SAFE_GEN_CONFIG = types.GenerateContentConfig(
    temperature=0.2,
    thinking_config=types.ThinkingConfig(thinking_level="MINIMAL"),
)

SYNTHESIS_GEN_CONFIG = types.GenerateContentConfig(
    temperature=0.4,
    thinking_config=types.ThinkingConfig(thinking_level="LOW"),
)
