"""정책 피드백 분석 도메인 값 객체."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum


class Recommendation(StrEnum):
    MAINTAIN = "maintain"
    EXPAND = "expand"
    SIMPLIFY = "simplify"
    RETARGET = "retarget"
    EXTEND_DURATION = "extend_duration"
    INCREASE_AMOUNT = "increase_amount"
    CONNECT_FOLLOWUP = "connect_followup"
    REDESIGN = "redesign"
    INSUFFICIENT_DATA = "insufficient_data"


class Confidence(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True)
class AnalysisScores:
    effectiveness: float | None = None
    accessibility: float | None = None
    support_adequacy: float | None = None
    followup_need: float | None = None
    improvement_urgency: float | None = None


@dataclass(frozen=True)
class PolicyFeedbackAnalysis:
    policy_id: str
    policy_name: str
    category: str
    respondent_count: int
    publicly_available: bool
    confidence: Confidence
    scores: AnalysisScores
    primary_bottleneck: str | None
    top_followup_need: str | None
    primary_recommendation: Recommendation
    secondary_recommendations: tuple[Recommendation, ...] = field(default_factory=tuple)
    summary: tuple[str, ...] = field(default_factory=tuple)
    suppressed_cell_count: int = 0
    ranks: dict[str, int | None] = field(default_factory=dict)
    category_ranks: dict[str, int | None] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

