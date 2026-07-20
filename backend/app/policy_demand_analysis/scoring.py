"""미충족 수요의 설명 가능한 점수·권고 규칙."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Mapping


class DemandRecommendation(StrEnum):
    CREATE_NEW_POLICY = "create_new_policy"
    BROADEN_ELIGIBILITY = "broaden_eligibility"
    INCREASE_AMOUNT = "increase_amount"
    EXTEND_DURATION = "extend_duration"
    CREATE_PACKAGE = "create_package"
    REOPEN_RECRUITMENT = "reopen_recruitment"
    SIMPLIFY_APPLICATION = "simplify_application"
    INSUFFICIENT_DATA = "insufficient_data"


@dataclass(frozen=True)
class DemandScoringConfig:
    weights: Mapping[str, float] = field(default_factory=lambda: {
        "volume": .20, "concentration": .15, "policy_gap": .20, "eligibility_gap": .15,
        "long_duration": .10, "package_need": .10, "recent_growth": .10,
    })
    gap_threshold: float = .45
    eligibility_threshold: float = .45
    long_duration_threshold: float = .40
    package_threshold: float = .40
    high_amount_threshold: float = .40
    recruitment_threshold: float = .40
    application_threshold: float = .40
    high_confidence_count: int = 30
    medium_confidence_count: int = 10


def _protected_ratio(rows: list[dict], predicate, minimum: int) -> float | None:
    matched = sum(1 for row in rows if predicate(row))
    unmatched = len(rows) - matched
    if (0 < matched < minimum) or (0 < unmatched < minimum):
        return None
    return matched / len(rows) if rows else 0.0


def score_need_area(rows: list[dict], *, total: int, max_count: int, minimum: int, now, config: DemandScoringConfig, has_suppressed_area: bool = False) -> dict:
    if len(rows) < minimum:
        return {"score": None, "confidence": "low", "components": None,
                "primary_recommendation": DemandRecommendation.INSUFFICIENT_DATA, "secondary_recommendations": []}
    recent = [row for row in rows if (now - row["submitted_at"]).days < 30]
    prior = [row for row in rows if 30 <= (now - row["submitted_at"]).days < 60]
    growth = None
    if len(recent) == 0 and len(prior) == 0:
        growth = 0.0
    elif len(recent) >= minimum and (len(prior) == 0 or len(prior) >= minimum):
        growth = 1.0 if not prior else max(-1.0, min(1.0, (len(recent) - len(prior)) / len(prior)))
    policy_gap = _protected_ratio(rows, lambda r: r["trigger_reason"] in {"no_recommendation", "no_matching_policy", "followup_unmatched"} or r["barrier"] == "해당 정책 자체가 없음", minimum)
    eligibility = _protected_ratio(rows, lambda r: r["barrier"] in {"연령조건", "소득조건", "재직·미취업 조건", "부모·가구 기준", "거주지 조건"}, minimum)
    long_duration = _protected_ratio(rows, lambda r: r["duration"] in {"7~12개월", "1년 이상"}, minimum)
    package_need = _protected_ratio(rows, lambda r: bool(r.get("companion_support")), minimum)
    components = {
        "volume": len(rows) / max_count * 100 if max_count else 0,
        "concentration": None if has_suppressed_area else (len(rows) / total * 100 if total else 0),
        "policy_gap": None if policy_gap is None else policy_gap * 100,
        "eligibility_gap": None if eligibility is None else eligibility * 100,
        "long_duration": None if long_duration is None else long_duration * 100,
        "package_need": None if package_need is None else package_need * 100,
        "recent_growth": None if growth is None else max(0.0, growth) * 100,
    }
    available = [(key, value) for key, value in components.items() if value is not None]
    denominator = sum(config.weights[key] for key, _ in available)
    score = round(sum(value * config.weights[key] for key, value in available) / denominator, 1)
    confidence = "high" if len(rows) >= config.high_confidence_count and growth is not None else (
        "medium" if len(rows) >= config.medium_confidence_count else "low"
    )
    evidence = {
        "policy_gap": policy_gap, "eligibility_gap": eligibility, "long_duration": long_duration,
        "package_need": package_need,
        "high_amount": _protected_ratio(rows, lambda r: r["amount"] in {"31~50만 원", "51~100만 원"}, minimum),
        "recruitment": _protected_ratio(rows, lambda r: r["barrier"] == "모집기간 종료", minimum),
        "application": _protected_ratio(rows, lambda r: r["barrier"] == "신청절차 부담", minimum),
    }
    recs: list[DemandRecommendation] = []
    if evidence["policy_gap"] is not None and evidence["policy_gap"] >= config.gap_threshold: recs.append(DemandRecommendation.CREATE_NEW_POLICY)
    if evidence["eligibility_gap"] is not None and evidence["eligibility_gap"] >= config.eligibility_threshold: recs.append(DemandRecommendation.BROADEN_ELIGIBILITY)
    if evidence["high_amount"] is not None and evidence["high_amount"] >= config.high_amount_threshold: recs.append(DemandRecommendation.INCREASE_AMOUNT)
    if evidence["long_duration"] is not None and evidence["long_duration"] >= config.long_duration_threshold: recs.append(DemandRecommendation.EXTEND_DURATION)
    if evidence["package_need"] is not None and evidence["package_need"] >= config.package_threshold: recs.append(DemandRecommendation.CREATE_PACKAGE)
    if evidence["recruitment"] is not None and evidence["recruitment"] >= config.recruitment_threshold: recs.append(DemandRecommendation.REOPEN_RECRUITMENT)
    if evidence["application"] is not None and evidence["application"] >= config.application_threshold: recs.append(DemandRecommendation.SIMPLIFY_APPLICATION)
    if not recs: recs.append(DemandRecommendation.CREATE_NEW_POLICY)
    return {"score": score, "confidence": confidence, "components": {key: None if value is None else round(value, 1) for key, value in components.items()},
            "primary_recommendation": recs[0], "secondary_recommendations": recs[1:]}
