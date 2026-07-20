"""정책 이용·피드백·리워드·집계 Application 유스케이스."""
from __future__ import annotations

from dataclasses import dataclass
import os

from sqlalchemy.exc import IntegrityError
from sqlalchemy.engine import Engine

from .domain import (
    FORM_VERSION,
    ALLOWED_TRANSITIONS,
    OTHER_TEXT_MAX_LENGTH,
    SURVEY_NOTICE,
    DomainRuleError,
    FeedbackStage,
    UsageStatus,
    questions_for_stage,
    validate_answers,
    validate_stage,
    validate_transition,
)
from .policy_gateway import PolicyRepository
from .repositories import (
    ConcurrentUsageUpdateError,
    DuplicateFeedbackError,
    FeedbackAggregateRepository,
    FeedbackRepository,
    PolicyUsageRepository,
)
from .reward import MockRewardProvider, RewardProvider


class NotFoundError(Exception):
    pass


class ConflictError(Exception):
    pass


@dataclass(frozen=True)
class RewardPolicy:
    amounts: dict[FeedbackStage, int]

    @classmethod
    def from_environment(cls) -> "RewardPolicy":
        defaults = {
            FeedbackStage.APPLIED: 500,
            FeedbackStage.SELECTED: 500,
            FeedbackStage.REJECTED: 500,
            FeedbackStage.USING: 700,
            FeedbackStage.COMPLETED: 1000,
        }
        amounts: dict[FeedbackStage, int] = {}
        for stage, default in defaults.items():
            raw = os.environ.get(f"FEEDBACK_REWARD_{stage.value.upper()}_AMOUNT", str(default))
            try:
                amount = int(raw)
            except ValueError as exc:
                raise RuntimeError(f"리워드 금액 설정이 정수가 아닙니다: {stage.value}={raw}") from exc
            if amount < 0:
                raise RuntimeError(f"리워드 금액은 음수일 수 없습니다: {stage.value}={amount}")
            amounts[stage] = amount
        return cls(amounts=amounts)


class FeedbackApplicationService:
    def __init__(
        self,
        engine: Engine,
        policy_repository: PolicyRepository,
        reward_provider: RewardProvider | None = None,
        reward_policy: RewardPolicy | None = None,
    ) -> None:
        self.usage_repository = PolicyUsageRepository(engine)
        self.feedback_repository = FeedbackRepository(engine)
        self.aggregate_repository = FeedbackAggregateRepository(engine)
        self.policy_repository = policy_repository
        self.reward_provider = reward_provider or MockRewardProvider()
        self.reward_policy = reward_policy or RewardPolicy.from_environment()

    def _enrich_usage(self, usage: dict) -> dict:
        current = UsageStatus(usage["current_status"])
        completed = set(usage.get("feedback_completed_stages", []))
        available: list[FeedbackStage] = []
        try:
            stage = FeedbackStage(current.value)
        except ValueError:
            stage = None
        if stage is not None and stage.value not in completed:
            available.append(stage)
        return {
            **usage,
            "available_feedback_stages": [item.value for item in available],
            "next_allowed_statuses": [
                status.value for status in sorted(ALLOWED_TRANSITIONS[current], key=lambda item: item.value)
            ],
            "expected_reward_amount": self.reward_policy.amounts[available[0]] if available else None,
            "reward_summary": self.feedback_repository.reward_summary_for_usage(usage["usage_id"]),
        }

    def create_usage(self, *, user_id: str, policy_id: str) -> dict:
        policy = self.policy_repository.get_available_policy(policy_id)
        if policy is None:
            raise NotFoundError(
                "현재 추천 카탈로그에서 확인되지 않은 정책입니다. 종료 정책 목록을 신규 이용기록으로 노출하지 않습니다."
            )
        try:
            created = self.usage_repository.create(user_id=user_id, **policy)
            detailed = next(
                item for item in self.usage_repository.list_owned(user_id)
                if item["usage_id"] == created["usage_id"]
            )
            return self._enrich_usage(detailed)
        except IntegrityError as exc:
            raise ConflictError("동일 사용자의 동일 정책 이용기록이 이미 존재합니다.") from exc

    def update_usage_status(self, *, user_id: str, usage_id: str, target: UsageStatus) -> dict:
        usage = self.usage_repository.get_owned(usage_id, user_id)
        if usage is None:
            raise NotFoundError("정책 이용기록을 찾을 수 없습니다.")
        validate_transition(UsageStatus(usage["current_status"]), target)
        try:
            updated = self.usage_repository.update_status(usage=usage, target=target)
            detailed = next(
                item for item in self.usage_repository.list_owned(user_id)
                if item["usage_id"] == updated["usage_id"]
            )
            return self._enrich_usage(detailed)
        except ConcurrentUsageUpdateError as exc:
            raise ConflictError(str(exc)) from exc

    def list_usages(self, user_id: str) -> list[dict]:
        return [self._enrich_usage(usage) for usage in self.usage_repository.list_owned(user_id)]

    def get_form(self, *, policy_id: str, stage: FeedbackStage) -> dict:
        policy = self.policy_repository.get_available_policy(policy_id)
        if policy is None:
            raise NotFoundError("현재 추천 카탈로그에서 확인되지 않은 정책입니다.")
        return {
            "policy_id": policy_id,
            "stage": stage.value,
            "form_version": FORM_VERSION,
            "notice": SURVEY_NOTICE,
            "other_text_max_length": OTHER_TEXT_MAX_LENGTH,
            "expected_reward_amount": self.reward_policy.amounts[stage],
            "questions": [
                {
                    "question_code": question.code,
                    "prompt": question.prompt,
                    "options": list(question.options),
                    "required": True,
                    "allows_other_text": question.other_option is not None,
                }
                for question in questions_for_stage(stage)
            ],
        }

    def submit_feedback(
        self,
        *,
        user_id: str,
        usage_id: str,
        stage: FeedbackStage,
        answers: list[dict[str, str | None]],
    ) -> dict:
        usage = self.usage_repository.get_owned(usage_id, user_id)
        if usage is None:
            raise NotFoundError("해당 사용자의 정책 이용기록을 찾을 수 없습니다.")
        validate_stage(UsageStatus(usage["current_status"]), stage)
        normalized_answers = validate_answers(stage, answers)
        amount = self.reward_policy.amounts[stage]
        try:
            feedback, reward = self.feedback_repository.create_with_pending_reward(
                usage=usage, stage=stage, answers=normalized_answers, amount=amount
            )
        except DuplicateFeedbackError as exc:
            raise ConflictError(str(exc)) from exc

        # 외부 지급 실패가 설문 저장을 롤백하지 않도록 DB 커밋 뒤 호출한다. 실제
        # Provider를 붙였을 때 실패하면 pending을 유지해 재처리할 수 있다.
        try:
            result = self.reward_provider.grant(
                reward_id=reward["reward_id"], user_id=user_id, amount=amount
            )
        except Exception:  # noqa: BLE001 - pending 상태가 복구 가능한 계약이다.
            completed_reward = reward
        else:
            completed_reward = self.feedback_repository.complete_reward(
                reward["reward_id"],
                status=result.status,
                provider_reference=result.provider_reference,
            )
        return {"feedback": feedback, "reward": completed_reward}

    def list_rewards(self, user_id: str) -> list[dict]:
        return self.feedback_repository.list_rewards(user_id)

    def aggregate(self, policy_id: str, minimum_group_size: int) -> dict:
        return self.aggregate_repository.build(policy_id, minimum_group_size)

    def aggregate_list(self, policies: dict, minimum_group_size: int) -> list[dict]:
        return [
            {
                **self.aggregate_repository.build(policy_id, minimum_group_size),
                "policy_name": policy_id,
            }
            for policy_id in policies
        ]
