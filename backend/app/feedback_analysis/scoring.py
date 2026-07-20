"""설명 가능하고 테스트 가능한 정책 피드백 점수·권고 규칙."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from .domain import AnalysisScores, Confidence, Recommendation

ProtectedDistribution = Mapping[str, Mapping[str, object]]


@dataclass(frozen=True)
class ScoringConfig:
    effect_weights: Mapping[str, float] = field(default_factory=lambda: {
        "매우 좋아짐": 100.0, "조금 좋아짐": 70.0, "비슷함": 40.0, "더 나빠짐": 0.0,
    })
    helpfulness_weights: Mapping[str, float] = field(default_factory=lambda: {
        "취업 준비": 100.0, "생활비": 100.0, "주거비": 100.0, "금융 부담": 100.0,
        "심리·사회활동": 100.0, "도움 없음": 0.0,
    })
    situation_effect_weight: float = 0.80
    helpfulness_effect_weight: float = 0.20
    barrier_scores: Mapping[str, float] = field(default_factory=lambda: {
        "어려움 없음": 100.0, "결과 대기": 45.0, "신청방법": 35.0,
        "제출서류": 30.0, "자격조건": 25.0, "방문 필요": 20.0,
    })
    adequacy_scores: Mapping[str, float] = field(default_factory=lambda: {
        "모두 충분": 100.0, "금액 부족": 55.0, "기간 부족": 55.0, "모두 부족": 0.0,
    })
    urgency_weights: Mapping[str, float] = field(default_factory=lambda: {
        "effectiveness_gap": 0.25, "accessibility_gap": 0.20,
        "support_gap": 0.20, "dropout": 0.15,
        "improvement_concentration": 0.10, "completion_gap": 0.10,
    })
    redesign_score_max: float = 45.0
    maintain_effect_min: float = 65.0
    maintain_other_min: float = 60.0
    expand_effect_min: float = 75.0
    expand_completion_min: float = 0.65
    expand_response_rate_min: float = 0.50
    barrier_recommendation_share_min: float = 0.35
    support_shortage_ratio_min: float = 0.40
    support_shortage_margin: float = 0.10
    followup_concentration_min: float = 0.45
    high_confidence_respondents: int = 30
    high_confidence_response_rate: float = 0.60
    high_confidence_completed_share: float = 0.40
    medium_confidence_respondents: int = 10
    medium_confidence_response_rate: float = 0.30
    categories: Mapping[str, str] = field(default_factory=lambda: {
        "청년월세지원": "주거", "머물자리론": "주거", "청년 중개보수·이사비 지원": "주거",
        "희망신용상담센터": "금융·자산", "부산청년 기쁨두배통장": "금융·자산",
        "청년디딤돌카드 플러스": "복지·생활",
    })


def _visible_counts(distribution: ProtectedDistribution | None) -> dict[str, int] | None:
    """억제 셀이 하나라도 있으면 해당 분포를 계산에 사용하지 않는다."""
    if not distribution or any(bool(cell.get("suppressed")) for cell in distribution.values()):
        return None
    counts = {
        label: int(cell.get("count") or 0)
        for label, cell in distribution.items()
        if cell.get("count") is not None
    }
    return counts if sum(counts.values()) > 0 else None


def weighted_score(distribution: ProtectedDistribution | None, weights: Mapping[str, float]) -> float | None:
    counts = _visible_counts(distribution)
    if counts is None:
        return None
    total = sum(counts.values())
    return round(sum(count * weights.get(label, 0.0) for label, count in counts.items()) / total, 1)


def concentration(distribution: ProtectedDistribution | None) -> tuple[float | None, str | None, float | None]:
    counts = _visible_counts(distribution)
    if counts is None:
        return None, None, None
    label, count = max(counts.items(), key=lambda item: (item[1], item[0]))
    share = count / sum(counts.values())
    return round(share * 100, 1), label, share


def count_suppressed_cells(value: object) -> int:
    if isinstance(value, dict):
        own = 1 if value.get("suppressed") is True else 0
        return own + sum(count_suppressed_cells(child) for key, child in value.items() if key != "suppressed")
    if isinstance(value, list):
        return sum(count_suppressed_cells(child) for child in value)
    return 0


def completed_share(metrics: dict, submissions: int) -> float | None:
    if submissions <= 0:
        return None
    cell = metrics.get("stage_response_rates", {}).get("completed", {})
    if cell.get("suppressed") or cell.get("responses") is None:
        return None
    return min(float(cell["responses"]) / submissions, 1.0)


def score_policy(aggregate: dict, config: ScoringConfig) -> tuple[AnalysisScores, dict]:
    metrics = aggregate.get("metrics")
    if aggregate.get("suppressed") or not metrics:
        return AnalysisScores(), {}
    situation_effect = weighted_score(metrics.get("perceived_effect_distribution"), config.effect_weights)
    helpfulness_effect = weighted_score(metrics.get("most_helpful_area_distribution"), config.helpfulness_weights)
    effectiveness = None
    if situation_effect is not None and helpfulness_effect is not None:
        effectiveness = round(
            situation_effect * config.situation_effect_weight
            + helpfulness_effect * config.helpfulness_effect_weight,
            1,
        )
    accessibility = weighted_score(metrics.get("application_barrier_distribution"), config.barrier_scores)
    support = weighted_score(metrics.get("support_adequacy_distribution"), config.adequacy_scores)
    followup, top_followup, top_followup_share = concentration(metrics.get("followup_support_distribution"))
    _, bottleneck, bottleneck_share = concentration(metrics.get("application_barrier_distribution"))
    improvement, _, _ = concentration(metrics.get("improvement_direction_distribution"))
    completion_rate = metrics.get("policy_usage_completion_rate")
    funnel = metrics.get("usage_funnel", {})
    applied = funnel.get("applied", {})
    completed = funnel.get("completed", {})
    dropout = None
    if not applied.get("suppressed") and not completed.get("suppressed"):
        applied_count, completed_count = applied.get("count"), completed.get("count")
        if applied_count:
            dropout = max(0.0, 1.0 - (float(completed_count or 0) / float(applied_count)))
    components = {
        "effectiveness_gap": None if effectiveness is None else 100.0 - effectiveness,
        "accessibility_gap": None if accessibility is None else 100.0 - accessibility,
        "support_gap": None if support is None else 100.0 - support,
        "dropout": None if dropout is None else dropout * 100.0,
        "improvement_concentration": improvement,
        "completion_gap": None if completion_rate is None else (1.0 - float(completion_rate)) * 100.0,
    }
    available = [(name, value) for name, value in components.items() if value is not None]
    urgency = None
    if effectiveness is not None and accessibility is not None and support is not None and available:
        denominator = sum(config.urgency_weights[name] for name, _ in available)
        urgency = round(sum(value * config.urgency_weights[name] for name, value in available) / denominator, 1)
    scores = AnalysisScores(effectiveness, accessibility, support, followup, urgency)
    evidence = {
        "primary_bottleneck": None if bottleneck == "어려움 없음" else bottleneck,
        "bottleneck_share": bottleneck_share,
        "top_followup_need": top_followup,
        "top_followup_share": top_followup_share,
        "completion_rate": completion_rate,
        "response_rate": aggregate.get("overall_response_rate"),
        "amount_shortage_ratio": metrics.get("insufficient_amount_ratio"),
        "period_shortage_ratio": metrics.get("insufficient_period_ratio"),
    }
    return scores, evidence


def confidence_for(aggregate: dict, suppressed_cells: int, config: ScoringConfig) -> Confidence:
    metrics = aggregate.get("metrics") or {}
    respondents = int(aggregate.get("respondent_count") or 0)
    usage_count = int(aggregate.get("usage_count") or 0)
    response_rate = min(respondents / usage_count, 1.0) if usage_count else None
    completed = completed_share(metrics, int(aggregate.get("feedback_submission_count") or 0))
    if (suppressed_cells == 0 and respondents >= config.high_confidence_respondents
            and response_rate is not None and response_rate >= config.high_confidence_response_rate
            and completed is not None and completed >= config.high_confidence_completed_share):
        return Confidence.HIGH
    if (respondents >= config.medium_confidence_respondents
            and response_rate is not None and response_rate >= config.medium_confidence_response_rate
            and completed is not None and completed > 0):
        return Confidence.MEDIUM
    return Confidence.LOW


def recommendations(scores: AnalysisScores, evidence: dict, config: ScoringConfig) -> tuple[Recommendation, tuple[Recommendation, ...]]:
    core = (scores.effectiveness, scores.accessibility, scores.support_adequacy, scores.improvement_urgency)
    if any(value is None for value in core):
        return Recommendation.INSUFFICIENT_DATA, ()
    found: list[Recommendation] = []
    if all(value <= config.redesign_score_max for value in core[:3]):
        found.append(Recommendation.REDESIGN)
    bottleneck = evidence.get("primary_bottleneck")
    share = evidence.get("bottleneck_share") or 0.0
    if share >= config.barrier_recommendation_share_min:
        if bottleneck == "자격조건":
            found.append(Recommendation.RETARGET)
        elif bottleneck in {"제출서류", "신청방법", "방문 필요", "결과 대기"}:
            found.append(Recommendation.SIMPLIFY)
    amount = evidence.get("amount_shortage_ratio")
    period = evidence.get("period_shortage_ratio")
    if amount is not None and period is not None:
        if period >= config.support_shortage_ratio_min and period - amount >= config.support_shortage_margin:
            found.append(Recommendation.EXTEND_DURATION)
        if amount >= config.support_shortage_ratio_min and amount - period >= config.support_shortage_margin:
            found.append(Recommendation.INCREASE_AMOUNT)
    if (evidence.get("top_followup_share") or 0.0) >= config.followup_concentration_min:
        found.append(Recommendation.CONNECT_FOLLOWUP)
    completion = evidence.get("completion_rate")
    response_rate = evidence.get("response_rate")
    if (scores.effectiveness >= config.expand_effect_min and completion is not None
            and completion >= config.expand_completion_min and response_rate is not None
            and response_rate >= config.expand_response_rate_min):
        found.append(Recommendation.EXPAND)
    if (scores.effectiveness >= config.maintain_effect_min
            and scores.accessibility >= config.maintain_other_min
            and scores.support_adequacy >= config.maintain_other_min):
        found.append(Recommendation.MAINTAIN)
    if not found:
        found.append(Recommendation.MAINTAIN)
    priority = [
        Recommendation.REDESIGN, Recommendation.EXTEND_DURATION, Recommendation.INCREASE_AMOUNT,
        Recommendation.SIMPLIFY, Recommendation.RETARGET, Recommendation.CONNECT_FOLLOWUP,
        Recommendation.EXPAND, Recommendation.MAINTAIN,
    ]
    unique = list(dict.fromkeys(found))
    primary = next(item for item in priority if item in unique)
    return primary, tuple(item for item in unique if item != primary)
