"""수요 집계·우선순위·정책 피드백 비교 Application Layer."""
from __future__ import annotations

from collections import Counter
from datetime import datetime

from sqlalchemy.engine import Engine

from ..feedback.repositories import FeedbackAggregateRepository
from ..policy_demand.repositories import PolicyDemandRepository
from .scoring import DemandScoringConfig, score_need_area


def _top_visible(distribution: dict | None) -> str | None:
    visible = [(key, cell["count"]) for key, cell in (distribution or {}).items() if not cell.get("suppressed") and cell.get("count") is not None]
    return max(visible, key=lambda item: (item[1], item[0]))[0] if visible else None


class PolicyDemandAnalysisService:
    def __init__(self, engine: Engine, policies: dict, config: DemandScoringConfig | None = None) -> None:
        self.demand = PolicyDemandRepository(engine)
        self.feedback = FeedbackAggregateRepository(engine)
        self.policies = policies
        self.config = config or DemandScoringConfig()

    def summary(self, minimum: int, now: datetime | None = None) -> dict:
        now = now or datetime.now()
        aggregate = self.demand.aggregate(minimum, now)
        rows = aggregate.pop("rows_for_analysis", [])
        comparison: list[str] = []
        if aggregate.get("metrics"):
            barrier = _top_visible(aggregate["metrics"].get("barrier_distribution"))
            if barrier:
                comparison.append(f"미충족 수요에서는 '{barrier}'이 주요 접근 장벽으로 나타나 추가 검토할 수 있습니다.")
            feedback_ratios = []
            for policy_id in self.policies:
                item = self.feedback.build(policy_id, minimum)
                metrics = item.get("metrics") or {}
                if metrics.get("insufficient_period_ratio") is not None:
                    feedback_ratios.append((metrics["insufficient_period_ratio"], policy_id))
            if feedback_ratios:
                _, policy = max(feedback_ratios)
                comparison.append(f"실제 이용 피드백에서는 '{policy}'의 지원기간 부족 응답도 함께 확인되어 기간과 접근조건을 함께 검토할 수 있습니다.")
        return {**aggregate, "comparison_summary": comparison}

    def priorities(self, minimum: int, now: datetime | None = None) -> list[dict]:
        now = now or datetime.now()
        aggregate = self.demand.aggregate(minimum, now)
        rows = aggregate.get("rows_for_analysis", [])
        counts = Counter(row["need_area"] for row in rows)
        max_public = max((count for count in counts.values() if count >= minimum), default=0)
        has_suppressed_area = any(0 < count < minimum for count in counts.values())
        results = []
        for area in sorted(counts):
            area_rows = [row for row in rows if row["need_area"] == area]
            scored = score_need_area(area_rows, total=len(rows), max_count=max_public, minimum=minimum, now=now, config=self.config, has_suppressed_area=has_suppressed_area)
            district = Counter(row["district_code"] for row in area_rows if row.get("district_code"))
            employment = Counter(row["employment_status"] for row in area_rows if row.get("employment_status"))
            trigger = Counter(row["trigger_reason"] for row in area_rows)
            results.append({
                "need_area": area, "respondent_count": len(area_rows) if len(area_rows) >= minimum else None,
                "publicly_available": len(area_rows) >= minimum, **scored,
                "top_district": district.most_common(1)[0][0] if district and district.most_common(1)[0][1] >= minimum else None,
                "top_employment_status": employment.most_common(1)[0][0] if employment and employment.most_common(1)[0][1] >= minimum else None,
                "top_trigger_reason": trigger.most_common(1)[0][0] if trigger and trigger.most_common(1)[0][1] >= minimum else None,
                "summary": self._summary(area, scored),
            })
        return sorted(results, key=lambda item: (item["score"] is None, -(item["score"] or 0), item["need_area"]))

    @staticmethod
    def _summary(area: str, scored: dict) -> list[str]:
        if scored["score"] is None:
            return ["공개 가능한 표본이 부족하여 구체적인 수요 판단을 유보합니다."]
        labels = {
            "create_new_policy": "신규 정책 검토", "broaden_eligibility": "기존 정책 자격 완화 검토",
            "increase_amount": "지원금 확대 검토", "extend_duration": "지원기간 연장 검토",
            "create_package": "복수 정책 패키지 검토", "reopen_recruitment": "모집기간·횟수 확대 검토",
            "simplify_application": "신청절차 개선 검토",
        }
        return [f"'{area}' 수요에 대해 {labels.get(str(scored['primary_recommendation']), '추가 정책 검토')}를 우선 살펴볼 수 있습니다."]
