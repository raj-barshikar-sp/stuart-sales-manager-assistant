"""Load Vertex/ADC env defaults before agents are constructed."""

from __future__ import annotations

import logging
import os
import warnings

from dotenv import load_dotenv

load_dotenv()

from agents.activity import configure_logging

configure_logging()

_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "").strip()
if _PROJECT and not os.environ.get("GOOGLE_CLOUD_QUOTA_PROJECT"):
    os.environ["GOOGLE_CLOUD_QUOTA_PROJECT"] = _PROJECT

# Experimental JSON Schema tool decls can trip Vertex with MALFORMED_FUNCTION_CALL.
os.environ.setdefault("ADK_DISABLE_JSON_SCHEMA_FOR_FUNC_DECL", "1")

warnings.filterwarnings(
    "ignore",
    message=r"Your application has authenticated using end user credentials.*",
)


class _DropAfcWarning(logging.Filter):
    """ADK calls generate_content with tools; google-genai logs a noisy AFC warning."""

    def filter(self, record: logging.LogRecord) -> bool:
        return "automatic function calling" not in record.getMessage().lower()


logging.getLogger("google.genai.models").addFilter(_DropAfcWarning())
