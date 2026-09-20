"""Orchestrator routing decision models."""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from agents.constants import (
    ACK_REPLY,
    GREETING_REPLY,
    OFF_TOPIC_REPLY,
    THANKS_REPLY,
)
from agents.orchestrator.prompt import TASK_AGENT_IDS

_ROUTE_HINTS: dict[str, tuple[str, ...]] = {
    "crm_intelligence_specialist": (
        "review my deals",
        "review my team",
        "review deals",
        "review deal",
        "sales stage validator",
        "stage validator",
        "validate sales stage",
        "deal roll-up",
        "deal rollup",
        "roll-up",
        "rollup",
        "pipeline cover",
        "large deal",
        "backup",
        "crm score",
    ),
    "activity_engagement_specialist": (
        "forecast inspection",
        "verbal call",
        "match my deal",
        "weekly update",
        "email engagement",
        "customer activity",
        "gong",
    ),
    "rep_performance_specialist": (
        "reps need help",
        "rep needs help",
        "which reps",
        "coaching rep",
        "coaching meeting",
        "my oversight",
        "manager oversight",
        "productivity metrics",
        "minimum expectation",
        "rep participation",
        "rep performance",
    ),
    "forecast_modeling_specialist": (
        "spot risks",
        "spot the biggest risks",
        "forecast risks",
        "deal risks",
        "pacing",
        "conversion rate",
        "future quarter",
        "future-quarter",
        "stagnated",
        "stagnant",
        "q+1",
        "q + 1",
        "q1 forecast",
        "q+2",
        "q + 2",
        "q2 forecast",
        "pipeline modeling",
        "pipeline model",
        "future pipeline",
        "risks / gaps",
        "risks and gaps",
    ),
    "knowledge_base_rag": (
        "rules of engagement",
        "account ownership",
        "territory ownership",
        "engagement rules",
        "pricing & quoting",
        "pricing and quoting",
        "pricing policy",
        "quote policy",
        "discount",
        "discount approval",
        "contract terms",
        "payment terms",
        "modernization policy",
        "carve-out policy",
        "commission plan",
        "commission plans",
        "quota credit",
        "accelerator",
        "payout timing",
        "spif",
        "product overview",
        "product use case",
        "product bundle",
        "what does the product",
        "business plus",
        "identity security cloud",
        "identityiq",
        "battlecard",
        "saviynt",
        "okta",
        "microsoft entra",
        "cyberark",
        "delinea",
        "objection handling",
    ),
}

_GREETING_HINTS = (
    "hi",
    "hello",
    "hey",
    "good morning",
    "good afternoon",
    "hi there",
    "hey there",
    "hi stuart",
    "hey stuart",
    "hello stuart",
    "yo",
    "howdy",
)
_THANKS_HINTS = (
    "thanks",
    "thank you",
    "thanks stuart",
    "thank you stuart",
    "thx",
    "ty",
    "cheers",
    "appreciate it",
    "thanks a lot",
    "thanks so much",
    "thank you so much",
    "ok thanks",
    "okay thanks",
)
_ACK_HINTS = (
    "ok",
    "okay",
    "okay great",
    "ok great",
    "okay cool",
    "ok cool",
    "great",
    "cool",
    "nice",
    "perfect",
    "awesome",
    "sweet",
    "got it",
    "sounds good",
    "makes sense",
    "copy that",
    "noted",
    "will do",
    "all good",
    "all right",
    "alright",
    "yes",
    "yep",
    "yeah",
    "yup",
    "no",
    "nope",
    "nah",
    "k",
    "kk",
    "lol",
    "haha",
    "wow",
    "hmm",
    "nice one",
    "good to know",
    "that works",
    "that helps",
    "thats helpful",
    "that's helpful",
)
_CAPABILITY_HINTS = (
    "help",
    "what can you do",
    "what do you do",
    "who are you",
    "who are you stuart",
    "what are you",
    "how can you help",
)
_FOLLOW_UP_HINTS = (
    "that account",
    "same one",
    "same account",
    "my book",
    "that deal",
    "this deal",
    "the opp",
    "that opp",
    "this account",
    "what about",
    "and also",
    "same for",
    "go deeper",
    "more detail",
    "say more",
    "explain that",
    "walk me through",
)
_TASK_TOKENS = (
    "forecast",
    "pipeline",
    "deal",
    "revenue",
    "opportunity",
    "account",
    "quota",
    "risk",
    "bottleneck",
    "coverage",
    "verbal",
    "rollup",
    "stage",
    "rep",
    "coaching",
    "productivity",
    "stagnat",
    "q+1",
    "q+2",
    "commission",
    "pricing",
    "discount",
    "quoting",
    "policy",
    "spif",
    "battlecard",
    "competitor",
    "objection",
    "product",
    "engagement",
    "win rate",
    "commit",
    "upside",
    "pacing",
    "crm score",
    "rev intel",
)


class AgentRoute(BaseModel):
    """One task specialist the orchestrator should invoke."""

    agent_id: str = Field(
        description="Task specialist to run. Synthesis is not a routing target."
    )
    reason: str = Field(
        default="",
        description="Why this specialist is needed for the current query.",
    )
    focus: str = Field(
        default="",
        description="Account, territory, or topic the specialist should focus on.",
    )


class RoutingDecision(BaseModel):
    """Task specialists selected for a user query.

    Synthesis is not listed here. The orchestrator calls synthesis after
    every task specialist finishes.
    """

    agents: list[AgentRoute] = Field(
        default_factory=list,
        description=(
            "Task specialists to run in order. Empty means no specialist "
            "is needed (greeting or off-topic)."
        ),
    )
    direct_reply: str = Field(
        default="",
        description="Short reply when agents is empty. Ignored when agents is set.",
    )

    @classmethod
    def from_state(cls, raw: Any) -> RoutingDecision:
        """Parse a routing payload from session state, JSON, or model text."""
        if raw is None or raw == "":
            return cls()
        if isinstance(raw, cls):
            return raw
        if isinstance(raw, str):
            return cls.from_text(raw)
        if isinstance(raw, dict):
            return cls._from_mapping(raw)
        try:
            return cls.model_validate(raw)
        except ValidationError:
            return cls()

    @classmethod
    def from_text(cls, text: str) -> RoutingDecision:
        """Parse JSON or agent ids embedded in model text."""
        payload = _extract_json_object(text)
        if isinstance(payload, dict):
            parsed = cls._from_mapping(payload)
            if parsed.agents or parsed.direct_reply:
                return parsed
        found = [
            {"agent_id": agent_id}
            for agent_id in TASK_AGENT_IDS
            if re.search(rf"\b{agent_id}\b", text)
        ]
        if found:
            return cls._from_mapping({"agents": found})
        return cls()

    @classmethod
    def _from_mapping(cls, raw: dict[str, Any]) -> RoutingDecision:
        routes: list[dict[str, Any]] = []
        for item in raw.get("agents") or []:
            if isinstance(item, str) and item in TASK_AGENT_IDS:
                routes.append({"agent_id": item})
                continue
            if not isinstance(item, dict):
                continue
            agent_id = item.get("agent_id") or item.get("id") or item.get("name")
            if agent_id in TASK_AGENT_IDS:
                routes.append(
                    {
                        "agent_id": agent_id,
                        "reason": item.get("reason") or "",
                        "focus": item.get("focus") or "",
                    }
                )
        try:
            return cls.model_validate(
                {
                    "agents": routes,
                    "direct_reply": raw.get("direct_reply") or "",
                }
            )
        except ValidationError:
            return cls()


def _cleaned(query: str) -> str:
    return re.sub(r"[^\w\s]", "", query.lower()).strip()


def _is_greeting(query: str) -> bool:
    return _cleaned(query) in _GREETING_HINTS


def _is_thanks(query: str) -> bool:
    return _cleaned(query) in _THANKS_HINTS


def _is_ack(query: str) -> bool:
    cleaned = _cleaned(query)
    if cleaned in _ACK_HINTS:
        return True
    words = cleaned.split()
    if 1 <= len(words) <= 4 and all(
        word in _ACK_HINTS or word in {"stuart", "great", "cool", "nice"}
        for word in words
    ):
        return True
    return False


def _is_capability(query: str) -> bool:
    return _cleaned(query) in _CAPABILITY_HINTS


def _account_mentions(lowered: str) -> bool:
    from agents.new_data_store import accounts

    for name, row in accounts().items():
        if name.lower() in lowered:
            return True
        for alias in row.get("aliases") or []:
            if alias.lower() in lowered:
                return True
    return False


def looks_like_sales_manager_task(query: str) -> bool:
    """True when a manager is asking Bob to do team/book work."""
    lowered = query.lower()
    if any(
        hint in lowered for hints in _ROUTE_HINTS.values() for hint in hints
    ):
        return True
    if any(hint in lowered for hint in _FOLLOW_UP_HINTS):
        return True
    if any(token in lowered for token in _TASK_TOKENS):
        return True
    if re.search(r"\bopp-\d+\b", lowered):
        return True
    # Stage codes like SS20 or SS40 are manager shorthand on their own.
    if re.search(r"\bss\s?\d{2,3}\b", lowered):
        return True
    return _account_mentions(lowered)


def heuristic_route(query: str) -> RoutingDecision:
    """Deterministic routes for explicit intents; planner handles ambiguity."""
    text = query.strip()
    if not text:
        return RoutingDecision(direct_reply=GREETING_REPLY)

    lowered = text.lower()
    routes = [
        {"agent_id": agent_id, "reason": "explicit intent match"}
        for agent_id, hints in _ROUTE_HINTS.items()
        if any(hint in lowered for hint in hints)
    ]

    if routes:
        return RoutingDecision.from_state({"agents": routes})

    if _is_thanks(text):
        return RoutingDecision(direct_reply=THANKS_REPLY)
    if _is_greeting(text) or _is_capability(text):
        return RoutingDecision(direct_reply=GREETING_REPLY)
    if _is_ack(text):
        return RoutingDecision(direct_reply=ACK_REPLY)
    if not looks_like_sales_manager_task(text):
        return RoutingDecision(direct_reply=OFF_TOPIC_REPLY)

    return RoutingDecision()
def enforce_explicit_routes(
    query: str, planned: RoutingDecision
) -> RoutingDecision:
    """Prefer deterministic explicit intents, otherwise trust the planner."""
    explicit = heuristic_route(query)
    if explicit.agents or explicit.direct_reply:
        return explicit
    return RoutingDecision.from_state(planned)


def _extract_json_object(text: str) -> Any | None:
    stripped = text.strip()
    stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
    stripped = re.sub(r"\s*```$", "", stripped)
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        return json.loads(stripped[start : end + 1])
    except json.JSONDecodeError:
        return None
