"""Structured outputs for deterministic Sales Manager specialists."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class SalesManagerOutput(BaseModel):
    findings: list[str] = Field(default_factory=list)
    records: dict[str, Any] = Field(default_factory=dict)
    topic: str = ""
    next_action: str = ""
    copy_ready: list[str] = Field(default_factory=list)
    status: Literal["success", "partial", "error"] = "success"
    error: str = ""


class CrmIntelligenceOutput(SalesManagerOutput):
    accounts: list[str] = Field(default_factory=list)
    commit_total: int = 0
    upside_total: int = 0
    risks: list[str] = Field(default_factory=list)
    stage_failures: list[dict[str, Any]] = Field(default_factory=list)


class ActivityEngagementOutput(SalesManagerOutput):
    accounts: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


class RepPerformanceOutput(SalesManagerOutput):
    expectations: list[dict[str, Any]] = Field(default_factory=list)
    rep_metrics: list[dict[str, Any]] = Field(default_factory=list)
    productivity_gaps: list[dict[str, Any]] = Field(default_factory=list)
    coaching_queue: list[dict[str, Any]] = Field(default_factory=list)
    oversight_deals: list[dict[str, Any]] = Field(default_factory=list)


class ForecastModelingOutput(SalesManagerOutput):
    quarters: list[dict[str, Any]] = Field(default_factory=list)
    stagnated_deals: list[dict[str, Any]] = Field(default_factory=list)
    weighted_forecast_total: int = 0
    pipeline_total: int = 0
    risks: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    current_commit_total: int = 0
    current_upside_total: int = 0


class SmFaqOutput(SalesManagerOutput):
    question: str = ""
    answers: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)


class KnowledgeBaseRagOutput(SmFaqOutput):
    """Grounded sections selected from the approved policy-document corpus."""

    pass


# Compatibility aliases while tests and imports move to the new architecture.
SmForecastingOutput = CrmIntelligenceOutput
SmForecastInspectionOutput = ActivityEngagementOutput
SmRepParticipationOutput = RepPerformanceOutput
SmFuturePipelineOutput = ForecastModelingOutput
ManagerPolicyFaqOutput = KnowledgeBaseRagOutput
