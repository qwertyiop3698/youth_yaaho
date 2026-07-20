"""정책 피드백 도메인 규칙.

FastAPI나 SQLAlchemy에 의존하지 않는 상태 전이, 설문 정의, 응답 검증 규칙만
둔다. 외부 정책/리워드 연동은 Infrastructure 계층의 인터페이스 뒤에 숨긴다.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


SURVEY_NOTICE = (
    "작성해 주신 의견은 익명으로 집계되어 부산시 청년정책 개선 자료로 전달됩니다. "
    "여러분의 경험이 다음 정책을 바꾸는 근거가 됩니다."
)
FORM_VERSION = "2026-01"
OTHER_TEXT_MAX_LENGTH = 200


class UsageStatus(StrEnum):
    RECOMMENDED = "recommended"
    APPLICATION_STARTED = "application_started"
    APPLIED = "applied"
    SELECTED = "selected"
    REJECTED = "rejected"
    USING = "using"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class FeedbackStage(StrEnum):
    APPLIED = "applied"
    SELECTED = "selected"
    REJECTED = "rejected"
    USING = "using"
    COMPLETED = "completed"


ALLOWED_TRANSITIONS: dict[UsageStatus, frozenset[UsageStatus]] = {
    UsageStatus.RECOMMENDED: frozenset({UsageStatus.APPLICATION_STARTED, UsageStatus.CANCELLED}),
    UsageStatus.APPLICATION_STARTED: frozenset({UsageStatus.APPLIED, UsageStatus.CANCELLED}),
    UsageStatus.APPLIED: frozenset({UsageStatus.SELECTED, UsageStatus.REJECTED, UsageStatus.CANCELLED}),
    UsageStatus.SELECTED: frozenset({UsageStatus.USING, UsageStatus.CANCELLED}),
    UsageStatus.REJECTED: frozenset(),
    UsageStatus.USING: frozenset({UsageStatus.COMPLETED, UsageStatus.CANCELLED}),
    UsageStatus.COMPLETED: frozenset(),
    UsageStatus.CANCELLED: frozenset(),
}


class DomainRuleError(ValueError):
    """도메인 불변식 위반."""


def validate_transition(current: UsageStatus, target: UsageStatus) -> None:
    if target == current:
        raise DomainRuleError(f"이미 {current.value} 상태입니다.")
    if target not in ALLOWED_TRANSITIONS[current]:
        raise DomainRuleError(f"허용되지 않는 상태 전이입니다: {current.value} -> {target.value}")


def validate_stage(current: UsageStatus, stage: FeedbackStage) -> None:
    if current.value != stage.value:
        raise DomainRuleError(
            f"현재 이용 상태({current.value})에서는 {stage.value} 단계 설문을 제출할 수 없습니다."
        )


@dataclass(frozen=True)
class QuestionDefinition:
    code: str
    prompt: str
    options: tuple[str, ...]
    stages: frozenset[FeedbackStage]
    position: int
    other_option: str | None = None


QUESTIONS: tuple[QuestionDefinition, ...] = (
    QuestionDefinition(
        "most_helpful_area", "이 정책이 실제로 가장 도움이 된 부분",
        ("취업 준비", "생활비", "주거비", "금융 부담", "심리·사회활동", "도움 없음"),
        frozenset({FeedbackStage.USING, FeedbackStage.COMPLETED}), 1,
    ),
    QuestionDefinition(
        "situation_change", "정책 이용 전과 비교한 상황 변화",
        ("매우 좋아짐", "조금 좋아짐", "비슷함", "더 나빠짐"),
        frozenset({FeedbackStage.USING, FeedbackStage.COMPLETED}), 2,
    ),
    QuestionDefinition(
        "application_barrier", "신청 과정에서 가장 어려웠던 부분",
        ("자격조건", "제출서류", "신청방법", "결과 대기", "방문 필요", "어려움 없음"),
        frozenset({FeedbackStage.APPLIED, FeedbackStage.SELECTED, FeedbackStage.REJECTED}), 3,
    ),
    QuestionDefinition(
        "support_adequacy", "지원금액과 지원기간의 적정성",
        ("모두 충분", "금액 부족", "기간 부족", "모두 부족"),
        frozenset({FeedbackStage.COMPLETED}), 4,
    ),
    QuestionDefinition(
        "followup_support", "이 정책 이후 가장 필요한 후속 지원",
        ("취업교육", "일경험", "채용연계", "월세·생활비", "금융지원", "심리·사회활동 지원"),
        frozenset({FeedbackStage.USING, FeedbackStage.COMPLETED}), 5,
    ),
    QuestionDefinition(
        "improvement_direction", "정책의 가장 필요한 개선 방향",
        ("자격조건 완화", "지원금 확대", "지원기간 연장", "신청절차 간소화", "지원대상 확대", "기타"),
        frozenset({FeedbackStage.COMPLETED}), 6, other_option="기타",
    ),
)

QUESTION_BY_CODE = {question.code: question for question in QUESTIONS}


def questions_for_stage(stage: FeedbackStage) -> tuple[QuestionDefinition, ...]:
    return tuple(question for question in QUESTIONS if stage in question.stages)


def validate_answers(stage: FeedbackStage, answers: list[dict[str, str | None]]) -> list[dict[str, str | None]]:
    expected = {question.code: question for question in questions_for_stage(stage)}
    received: dict[str, dict[str, str | None]] = {}
    for answer in answers:
        code = str(answer.get("question_code") or "")
        if code in received:
            raise DomainRuleError(f"문항 응답이 중복되었습니다: {code}")
        received[code] = answer

    if set(received) != set(expected):
        missing = sorted(set(expected) - set(received))
        extra = sorted(set(received) - set(expected))
        raise DomainRuleError(f"설문 문항 구성이 올바르지 않습니다(missing={missing}, extra={extra}).")

    normalized: list[dict[str, str | None]] = []
    for code, question in expected.items():
        answer = received[code]
        choice = str(answer.get("choice") or "")
        if choice not in question.options:
            raise DomainRuleError(f"{code} 문항의 선택값이 올바르지 않습니다.")
        other_text = str(answer.get("other_text") or "").strip() or None
        if question.other_option and choice == question.other_option:
            if other_text is None:
                raise DomainRuleError("기타 선택 시 짧은 자유서술을 입력해야 합니다.")
            if len(other_text) > OTHER_TEXT_MAX_LENGTH:
                raise DomainRuleError(f"자유서술은 {OTHER_TEXT_MAX_LENGTH}자 이하여야 합니다.")
        elif other_text is not None:
            raise DomainRuleError("기타를 선택하지 않은 문항에는 자유서술을 입력할 수 없습니다.")
        normalized.append({"question_code": code, "choice": choice, "other_text": other_text})
    return normalized
