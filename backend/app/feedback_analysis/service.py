"""익명 집계 입력을 정책 개선 참고지표로 변환하는 Application Layer."""
from __future__ import annotations

from dataclasses import replace

from sqlalchemy.engine import Engine

from ..feedback.repositories import FeedbackAggregateRepository
from .domain import PolicyFeedbackAnalysis, Recommendation
from .scoring import (
    ScoringConfig,
    confidence_for,
    count_suppressed_cells,
    recommendations,
    score_policy,
)

VALID_CATEGORIES = {"일자리", "주거", "금융·자산", "교육·역량", "복지·생활", "기타"}
SCORE_FIELDS = (
    "improvement_urgency", "effectiveness", "accessibility", "support_adequacy", "followup_need"
)


class AnalysisNotFoundError(LookupError):
    pass


def _summary(primary: Recommendation, evidence: dict) -> tuple[str, ...]:
    messages = {
        Recommendation.MAINTAIN: "현재 운영 방향을 유지하면서 추가 응답 추이를 살펴볼 수 있습니다.",
        Recommendation.EXPAND: "체감 효과와 이용 완료 지표를 바탕으로 확대 가능성을 검토할 수 있습니다.",
        Recommendation.SIMPLIFY: "신청 절차 간소화를 우선 검토할 수 있습니다.",
        Recommendation.RETARGET: "자격조건과 지원 대상의 적정성을 함께 검토할 수 있습니다.",
        Recommendation.EXTEND_DURATION: "지원기간 연장 필요성을 우선 검토할 수 있습니다.",
        Recommendation.INCREASE_AMOUNT: "지원금액 확대 필요성을 우선 검토할 수 있습니다.",
        Recommendation.CONNECT_FOLLOWUP: "후속 정책 연계 수요를 세부적으로 검토할 수 있습니다.",
        Recommendation.REDESIGN: "효과·접근성·지원 적정성을 함께 살피는 전반적 개편 검토가 필요합니다.",
        Recommendation.INSUFFICIENT_DATA: "공개 가능한 표본이 부족하여 구체적인 점수와 권고를 제시하지 않습니다.",
    }
    result = [messages[primary]]
    if primary is not Recommendation.INSUFFICIENT_DATA:
        if evidence.get("primary_bottleneck"):
            result.append(f"공개 가능한 응답에서 주요 신청 병목은 '{evidence['primary_bottleneck']}'으로 나타났습니다.")
        if evidence.get("top_followup_need"):
            result.append(f"공개 가능한 응답에서 후속 지원 수요는 '{evidence['top_followup_need']}'에 가장 많이 모였습니다.")
    return tuple(result[:3])


class PolicyFeedbackAnalysisService:
    def __init__(self, engine: Engine, policies: dict, config: ScoringConfig | None = None) -> None:
        self.aggregates = FeedbackAggregateRepository(engine)
        self.policies = policies
        self.config = config or ScoringConfig()

    def _policy_name(self, policy_id: str) -> str | None:
        if policy_id in self.policies:
            return policy_id
        for name, metadata in self.policies.items():
            if metadata.get("youthcenter_plcy_no") == policy_id:
                return name
        return None

    def analyze(self, policy_id: str, minimum_group_size: int) -> PolicyFeedbackAnalysis:
        policy_name = self._policy_name(policy_id)
        if policy_name is None:
            raise AnalysisNotFoundError("분석 대상 정책을 찾을 수 없습니다.")
        aggregate = self.aggregates.build(policy_id, minimum_group_size)
        # catalog 이름으로 생성된 이용 이력이 대부분이므로 외부 정책번호 조회가 비어 있으면 이름 기준도 확인한다.
        if policy_id != policy_name and aggregate.get("usage_count") == 0:
            aggregate = self.aggregates.build(policy_name, minimum_group_size)
            aggregate["policy_id"] = policy_id
        metrics = aggregate.get("metrics") or {}
        suppressed_cells = count_suppressed_cells(metrics)
        scores, evidence = score_policy(aggregate, self.config)
        primary, secondary = recommendations(scores, evidence, self.config)
        configured_category = self.policies.get(policy_name, {}).get("category")
        category = configured_category if configured_category in VALID_CATEGORIES else self.config.categories.get(policy_name, "기타")
        return PolicyFeedbackAnalysis(
            policy_id=policy_id,
            policy_name=policy_name,
            category=category,
            respondent_count=int(aggregate.get("respondent_count") or 0),
            publicly_available=not bool(aggregate.get("suppressed")),
            confidence=confidence_for(aggregate, suppressed_cells, self.config),
            scores=scores,
            primary_bottleneck=evidence.get("primary_bottleneck"),
            top_followup_need=evidence.get("top_followup_need"),
            primary_recommendation=primary,
            secondary_recommendations=secondary,
            summary=_summary(primary, evidence),
            suppressed_cell_count=suppressed_cells,
        )

    def analyze_all(self, minimum_group_size: int) -> list[PolicyFeedbackAnalysis]:
        analyses = [self.analyze(policy_id, minimum_group_size) for policy_id in self.policies]
        ranked = self._rank(analyses, category=False)
        return self._rank(ranked, category=True)

    @staticmethod
    def _rank(analyses: list[PolicyFeedbackAnalysis], *, category: bool) -> list[PolicyFeedbackAnalysis]:
        rank_maps: dict[str, dict[str, int]] = {}
        for field in SCORE_FIELDS:
            groups: dict[str, list[PolicyFeedbackAnalysis]] = {}
            for item in analyses:
                groups.setdefault(item.category if category else "all", []).append(item)
            for group, items in groups.items():
                visible = [item for item in items if getattr(item.scores, field) is not None]
                visible.sort(key=lambda item: (-getattr(item.scores, field), item.policy_name))
                last_value = None
                rank = 0
                for index, item in enumerate(visible, start=1):
                    value = getattr(item.scores, field)
                    if value != last_value:
                        rank = index
                        last_value = value
                    rank_maps.setdefault(f"{group}:{item.policy_id}", {})[field] = rank
        return [
            replace(
                item,
                **({"category_ranks": rank_maps.get(f"{item.category}:{item.policy_id}", {})}
                   if category else {"ranks": rank_maps.get(f"all:{item.policy_id}", {})}),
            )
            for item in analyses
        ]

    def priorities(self, minimum_group_size: int) -> list[PolicyFeedbackAnalysis]:
        return sorted(
            self.analyze_all(minimum_group_size),
            key=lambda item: (
                item.scores.improvement_urgency is None,
                -(item.scores.improvement_urgency or 0),
                item.policy_name,
            ),
        )

