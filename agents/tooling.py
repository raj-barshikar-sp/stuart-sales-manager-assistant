"""Tool decorator compatible with Google ADK.

ADK 2.x auto-wraps callables passed to ``Agent(tools=[...])`` as FunctionTools.
A ``@tool`` export does not exist on ``google.adk.tools`` in current releases,
so this module provides the same decorator API the project spec calls for.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

F = TypeVar("F", bound=Callable[..., object])

try:
    from google.adk.tools import tool as tool
except ImportError:

    def tool(func: F) -> F:
        """Mark ``func`` as an ADK tool. Identity decorator; ADK wraps it later."""
        return func
