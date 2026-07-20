"""정책 개선 분석 API 스키마."""
from __future__ import annotations

from pydantic import BaseModel, Field

from .domain import Confidence, Recommendation


class AnalysisScoresResponse(BaseModel):
    effectiveness: float | None = None
    accessibility: float | None = None
    support_adequacy: float | None = None
    followup_need: float | None = None
    improvement_urgency: float | None = None


class PolicyFeedbackAnalysisResponse(BaseModel):
    policy_id: str
    policy_name: str
    category: str
    respondent_count: int
    publicly_available: bool
    confidence: Confidence
    scores: AnalysisScoresResponse
    primary_bottleneck: str | None = None
    top_followup_need: str | None = None
    primary_recommendation: Recommendation
    secondary_recommendations: list[Recommendation] = Field(default_factory=list)
    summary: list[str] = Field(default_factory=list)
    suppressed_cell_count: int = 0
    ranks: dict[str, int | None] = Field(default_factory=dict)
    category_ranks: dict[str, int | None] = Field(default_factory=dict)

