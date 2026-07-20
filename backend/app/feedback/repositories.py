"""정책 피드백 DB Repository 및 익명 집계 쿼리."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import uuid

from sqlalchemy import and_, distinct, func, select, update
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from . import models
from .domain import FORM_VERSION, QUESTIONS, FeedbackStage, UsageStatus


class DuplicateFeedbackError(Exception):
    pass


class ConcurrentUsageUpdateError(Exception):
    pass


def seed_feedback_questions(engine: Engine) -> None:
    """버전이 붙은 기본 6문항을 멱등하게 초기화한다."""
    with engine.begin() as conn:
        existing = set(
            conn.execute(
                select(models.feedback_questions.c.question_id).where(
                    models.feedback_questions.c.form_version == FORM_VERSION
                )
            ).scalars()
        )
        rows = [
            {
                "question_id": f"{FORM_VERSION}:{question.code}",
                "form_version": FORM_VERSION,
                "question_code": question.code,
                "prompt": question.prompt,
                "options": list(question.options),
                "stages": [stage.value for stage in sorted(question.stages, key=lambda value: value.value)],
                "position": question.position,
                "allows_other": question.other_option is not None,
                "active": True,
            }
            for question in QUESTIONS
            if f"{FORM_VERSION}:{question.code}" not in existing
        ]
        if rows:
            conn.execute(models.feedback_questions.insert(), rows)


class PolicyUsageRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def create(self, *, user_id: str, policy_id: str, policy_name: str, policy_source: str) -> dict:
        usage_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        with self.engine.begin() as conn:
            conn.execute(
                models.policy_usages.insert().values(
                    usage_id=usage_id,
                    user_id=user_id,
                    policy_id=policy_id,
                    policy_name=policy_name,
                    policy_source=policy_source,
                    current_status=UsageStatus.RECOMMENDED.value,
                    created_at=now,
                    updated_at=now,
                )
            )
            conn.execute(
                models.policy_usage_status_history.insert().values(
                    usage_id=usage_id, status=UsageStatus.RECOMMENDED.value, changed_at=now
                )
            )
        return self.get_owned(usage_id, user_id)  # type: ignore[return-value]

    def get_owned(self, usage_id: str, user_id: str) -> dict | None:
        with self.engine.connect() as conn:
            row = conn.execute(
                select(models.policy_usages).where(
                    and_(models.policy_usages.c.usage_id == usage_id, models.policy_usages.c.user_id == user_id)
                )
            ).mappings().first()
        return dict(row) if row else None

    def list_owned(self, user_id: str) -> list[dict]:
        with self.engine.connect() as conn:
            usage_rows = conn.execute(
                select(models.policy_usages)
                .where(models.policy_usages.c.user_id == user_id)
                .order_by(models.policy_usages.c.updated_at.desc())
            ).mappings().all()
            histories = conn.execute(
                select(models.policy_usage_status_history)
                .join(models.policy_usages, models.policy_usages.c.usage_id == models.policy_usage_status_history.c.usage_id)
                .where(models.policy_usages.c.user_id == user_id)
                .order_by(models.policy_usage_status_history.c.changed_at)
            ).mappings().all()
            feedback_rows = conn.execute(
                select(models.policy_feedback.c.usage_id, models.policy_feedback.c.stage).where(
                    models.policy_feedback.c.user_id == user_id
                )
            ).mappings().all()
        by_usage: dict[str, list[dict]] = {}
        for row in histories:
            by_usage.setdefault(row["usage_id"], []).append(
                {"status": row["status"], "changed_at": row["changed_at"]}
            )
        completed_by_usage: dict[str, list[str]] = {}
        for row in feedback_rows:
            completed_by_usage.setdefault(row["usage_id"], []).append(row["stage"])
        return [
            {
                **dict(row),
                "status_history": by_usage.get(row["usage_id"], []),
                "feedback_completed_stages": sorted(completed_by_usage.get(row["usage_id"], [])),
            }
            for row in usage_rows
        ]

    def update_status(self, *, usage: dict, target: UsageStatus) -> dict:
        now = datetime.now(timezone.utc)
        with self.engine.begin() as conn:
            result = conn.execute(
                update(models.policy_usages)
                .where(
                    and_(
                        models.policy_usages.c.usage_id == usage["usage_id"],
                        models.policy_usages.c.user_id == usage["user_id"],
                        models.policy_usages.c.current_status == usage["current_status"],
                    )
                )
                .values(current_status=target.value, updated_at=now)
            )
            if result.rowcount != 1:
                raise ConcurrentUsageUpdateError("이용 상태가 동시에 변경되었습니다. 다시 조회해 주세요.")
            conn.execute(
                models.policy_usage_status_history.insert().values(
                    usage_id=usage["usage_id"], status=target.value, changed_at=now
                )
            )
        return self.get_owned(usage["usage_id"], usage["user_id"])  # type: ignore[return-value]


class FeedbackRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def create_with_pending_reward(
        self,
        *,
        usage: dict,
        stage: FeedbackStage,
        answers: list[dict[str, str | None]],
        amount: int,
    ) -> tuple[dict, dict]:
        feedback_id = str(uuid.uuid4())
        reward_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        try:
            with self.engine.begin() as conn:
                conn.execute(
                    models.policy_feedback.insert().values(
                        feedback_id=feedback_id,
                        usage_id=usage["usage_id"],
                        user_id=usage["user_id"],
                        policy_id=usage["policy_id"],
                        stage=stage.value,
                        form_version=FORM_VERSION,
                        submitted_at=now,
                    )
                )
                conn.execute(
                    models.feedback_answers.insert(),
                    [{"feedback_id": feedback_id, **answer} for answer in answers],
                )
                conn.execute(
                    models.reward_grants.insert().values(
                        reward_id=reward_id,
                        feedback_id=feedback_id,
                        usage_id=usage["usage_id"],
                        user_id=usage["user_id"],
                        policy_id=usage["policy_id"],
                        stage=stage.value,
                        amount=amount,
                        status="pending",
                        created_at=now,
                        updated_at=now,
                    )
                )
        except IntegrityError as exc:
            raise DuplicateFeedbackError("동일 정책·동일 단계의 설문 또는 리워드가 이미 존재합니다.") from exc
        return (
            {"feedback_id": feedback_id, "stage": stage.value, "form_version": FORM_VERSION, "submitted_at": now},
            {"reward_id": reward_id, "amount": amount, "status": "pending"},
        )

    def complete_reward(self, reward_id: str, *, status: str, provider_reference: str | None) -> dict:
        with self.engine.begin() as conn:
            conn.execute(
                update(models.reward_grants)
                .where(models.reward_grants.c.reward_id == reward_id)
                .values(
                    status=status,
                    provider_reference=provider_reference,
                    updated_at=datetime.now(timezone.utc),
                )
            )
            row = conn.execute(
                select(models.reward_grants).where(models.reward_grants.c.reward_id == reward_id)
            ).mappings().one()
        return dict(row)

    def list_rewards(self, user_id: str) -> list[dict]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                select(
                    models.reward_grants.c.reward_id,
                    models.reward_grants.c.policy_id,
                    models.reward_grants.c.stage,
                    models.reward_grants.c.amount,
                    models.reward_grants.c.status,
                    models.reward_grants.c.created_at,
                    models.reward_grants.c.updated_at,
                )
                .where(models.reward_grants.c.user_id == user_id)
                .order_by(models.reward_grants.c.created_at.desc())
            ).mappings().all()
        return [dict(row) for row in rows]

    def reward_summary_for_usage(self, usage_id: str) -> dict[str, int]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                select(models.reward_grants.c.status, models.reward_grants.c.amount).where(
                    models.reward_grants.c.usage_id == usage_id
                )
            ).mappings().all()
        return {
            "pending_amount": sum(row["amount"] for row in rows if row["status"] == "pending"),
            "mock_paid_amount": sum(row["amount"] for row in rows if row["status"] == "mock_paid"),
        }


def _distribution(answers: list[dict], question_code: str) -> dict[str, int]:
    counts = Counter(row["choice"] for row in answers if row["question_code"] == question_code)
    return dict(sorted(counts.items()))


def _protected_distribution(
    answers: list[dict], question_code: str, minimum_group_size: int
) -> dict[str, dict[str, int | bool | None]]:
    """0은 그대로 두되 1~k-1인 셀의 정확한 수를 숨긴다."""
    return {
        choice: (
            {"suppressed": True, "count": None}
            if 0 < count < minimum_group_size
            else {"suppressed": False, "count": count}
        )
        for choice, count in _distribution(answers, question_code).items()
    }


class FeedbackAggregateRepository:
    """개인 원문을 반환하지 않고 정책 단위 집계만 계산한다."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def build(self, policy_id: str, minimum_group_size: int) -> dict:
        with self.engine.connect() as conn:
            feedback_rows = [
                dict(row) for row in conn.execute(
                    select(models.policy_feedback).where(models.policy_feedback.c.policy_id == policy_id)
                ).mappings().all()
            ]
            feedback_ids = [row["feedback_id"] for row in feedback_rows]
            answers = (
                [dict(row) for row in conn.execute(
                    select(
                        models.feedback_answers.c.feedback_id,
                        models.feedback_answers.c.question_code,
                        models.feedback_answers.c.choice,
                        # other_text는 집계 쿼리에서 의도적으로 선택하지 않는다.
                    ).where(models.feedback_answers.c.feedback_id.in_(feedback_ids))
                ).mappings().all()]
                if feedback_ids else []
            )
            free_text_count = 0
            if feedback_ids:
                free_text_count = int(conn.scalar(
                    select(func.count()).select_from(models.feedback_answers).where(
                        and_(
                            models.feedback_answers.c.feedback_id.in_(feedback_ids),
                            models.feedback_answers.c.other_text.is_not(None),
                        )
                    )
                ) or 0)
            usage_rows = [dict(row) for row in conn.execute(
                select(models.policy_usages.c.usage_id, models.policy_usages.c.current_status).where(
                    models.policy_usages.c.policy_id == policy_id
                )
            ).mappings().all()]
            reached_rows = [dict(row) for row in conn.execute(
                select(
                    models.policy_usage_status_history.c.usage_id,
                    models.policy_usage_status_history.c.status,
                )
                .join(models.policy_usages, models.policy_usages.c.usage_id == models.policy_usage_status_history.c.usage_id)
                .where(models.policy_usages.c.policy_id == policy_id)
            ).mappings().all()]

        respondent_count = len({row["user_id"] for row in feedback_rows})
        stage_opportunities = sum(
            len({row["usage_id"] for row in reached_rows if row["status"] == stage.value})
            for stage in FeedbackStage
        )
        base = {
            "policy_id": policy_id,
            "respondent_count": respondent_count,
            "minimum_group_size": minimum_group_size,
            "suppressed": respondent_count < minimum_group_size,
            "usage_count": len(usage_rows),
            "feedback_submission_count": len(feedback_rows),
            "overall_response_rate": len(feedback_rows) / stage_opportunities if stage_opportunities else None,
        }
        if respondent_count < minimum_group_size:
            return {**base, "suppression_reason": "minimum_group_size_not_met", "metrics": None}

        stage_counts = Counter(row["stage"] for row in feedback_rows)
        reached: dict[str, set[str]] = {}
        for row in reached_rows:
            reached.setdefault(row["status"], set()).add(row["usage_id"])
        stage_response_rates = {}
        for stage in FeedbackStage:
            responses = stage_counts.get(stage.value, 0)
            eligible = len(reached.get(stage.value, set()))
            small_nonzero_cell = (0 < responses < minimum_group_size) or (0 < eligible < minimum_group_size)
            stage_response_rates[stage.value] = (
                {"suppressed": True, "responses": None, "eligible_usages": None, "rate": None}
                if small_nonzero_cell
                else {
                    "suppressed": False,
                    "responses": responses,
                    "eligible_usages": eligible,
                    "rate": responses / eligible if eligible else None,
                }
            )
        adequacy = _distribution(answers, "support_adequacy")
        adequacy_total = sum(adequacy.values())

        feedback_by_id = {row["feedback_id"]: row for row in feedback_rows}
        outcome_barriers: dict[str, dict] = {}
        for outcome in (FeedbackStage.SELECTED.value, FeedbackStage.REJECTED.value):
            outcome_feedback_ids = {
                row["feedback_id"] for row in feedback_rows if row["stage"] == outcome
            }
            outcome_users = {
                feedback_by_id[feedback_id]["user_id"] for feedback_id in outcome_feedback_ids
            }
            if len(outcome_users) < minimum_group_size:
                outcome_barriers[outcome] = {"suppressed": True, "respondent_count": None}
            else:
                distribution = Counter(
                    row["choice"] for row in answers
                    if row["feedback_id"] in outcome_feedback_ids and row["question_code"] == "application_barrier"
                )
                total = sum(distribution.values())
                contains_small_cell = any(0 < value < minimum_group_size for value in distribution.values())
                outcome_barriers[outcome] = {
                    "suppressed": False,
                    "respondent_count": len(outcome_users),
                    "distribution": {
                        key: ({"suppressed": True, "count": None} if value < minimum_group_size else {"suppressed": False, "count": value})
                        for key, value in sorted(distribution.items())
                    },
                    # 작은 셀에서 역산하지 못하도록 비교용 비율 전체를 숨긴다.
                    "percentages": None if contains_small_cell else (
                        {key: value / total for key, value in sorted(distribution.items())} if total else {}
                    ),
                }

        difference = None
        if (
            not outcome_barriers["selected"]["suppressed"]
            and not outcome_barriers["rejected"]["suppressed"]
            and outcome_barriers["selected"]["percentages"] is not None
            and outcome_barriers["rejected"]["percentages"] is not None
        ):
            keys = set(outcome_barriers["selected"]["percentages"]) | set(outcome_barriers["rejected"]["percentages"])
            difference = {
                key: outcome_barriers["selected"]["percentages"].get(key, 0.0)
                - outcome_barriers["rejected"]["percentages"].get(key, 0.0)
                for key in sorted(keys)
            }

        completed_count = sum(row["current_status"] == UsageStatus.COMPLETED.value for row in usage_rows)
        metrics = {
            "usage_funnel": {
                status.value: (
                    {"suppressed": True, "count": None}
                    if 0 < len(reached.get(status.value, set())) < minimum_group_size
                    else {"suppressed": False, "count": len(reached.get(status.value, set()))}
                )
                for status in UsageStatus
            },
            "stage_response_rates": stage_response_rates,
            "perceived_effect_distribution": _protected_distribution(
                answers, "situation_change", minimum_group_size
            ),
            "most_helpful_area_distribution": _protected_distribution(
                answers, "most_helpful_area", minimum_group_size
            ),
            "application_barrier_distribution": _protected_distribution(
                answers, "application_barrier", minimum_group_size
            ),
            "support_adequacy_distribution": _protected_distribution(
                answers, "support_adequacy", minimum_group_size
            ),
            "insufficient_amount_ratio": (
                (adequacy.get("금액 부족", 0) + adequacy.get("모두 부족", 0)) / adequacy_total
                if adequacy_total >= minimum_group_size else None
            ),
            "insufficient_period_ratio": (
                (adequacy.get("기간 부족", 0) + adequacy.get("모두 부족", 0)) / adequacy_total
                if adequacy_total >= minimum_group_size else None
            ),
            "both_insufficient_ratio": (
                adequacy.get("모두 부족", 0) / adequacy_total
                if adequacy_total >= minimum_group_size else None
            ),
            "followup_support_distribution": _protected_distribution(
                answers, "followup_support", minimum_group_size
            ),
            "improvement_direction_distribution": _protected_distribution(
                answers, "improvement_direction", minimum_group_size
            ),
            "selected_rejected_barrier_comparison": {
                **outcome_barriers,
                "selected_minus_rejected_percentage_points": difference,
            },
            "policy_usage_completion_rate": completed_count / len(usage_rows) if usage_rows else None,
            "free_text_response_count": (
                None if 0 < free_text_count < minimum_group_size else free_text_count
            ),
            "free_text_response_suppressed": 0 < free_text_count < minimum_group_size,
        }
        return {**base, "suppression_reason": None, "metrics": metrics}
