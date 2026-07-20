"""미충족 정책 수요 도메인 규칙과 설문 정의."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


NOTICE = "작성해 주신 의견은 익명으로 집계되어 부산시 청년정책 개선 자료로 전달됩니다. 여러분의 경험이 다음 정책을 바꾸는 근거가 됩니다."
FORM_VERSION = "2026-01"
OTHER_TEXT_MAX_LENGTH = 200


class DemandRuleError(ValueError):
    pass


class TriggerReason(StrEnum):
    NO_RECOMMENDATION = "no_recommendation"
    NO_MATCHING_POLICY = "no_matching_policy"
    NO_ELIGIBLE_POLICY = "no_eligible_policy"
    USER_REPORTED_MISMATCH = "user_reported_mismatch"
    FOLLOWUP_UNMATCHED = "followup_unmatched"


NEED_AREAS = (
    "취업교육", "일경험·인턴", "채용연계", "구직활동비", "월세·주거비",
    "생활비", "금융·부채지원", "심리·사회활동", "기타",
)
DURATIONS = ("1개월 이하", "2~3개월", "4~6개월", "7~12개월", "1년 이상")
AMOUNTS = ("10만 원 이하", "11~30만 원", "31~50만 원", "51~100만 원", "금전지원보다 서비스가 필요함")
BARRIERS = (
    "연령조건", "소득조건", "재직·미취업 조건", "부모·가구 기준", "거주지 조건",
    "모집기간 종료", "지원내용 불일치", "신청절차 부담", "해당 정책 자체가 없음", "기타",
)
EMPLOYMENT_STATUSES = ("재직", "미취업", "구직 중", "불안정·단기근로", "학생", "기타")


@dataclass(frozen=True)
class DemandForm:
    version: str = FORM_VERSION
    notice: str = NOTICE
    other_text_max_length: int = OTHER_TEXT_MAX_LENGTH


def validate_response(payload: dict) -> None:
    required = {
        "need_area": NEED_AREAS,
        "duration": DURATIONS,
        "amount": AMOUNTS,
        "barrier": BARRIERS,
    }
    for field, choices in required.items():
        value = payload.get(field)
        if value not in choices:
            raise DemandRuleError(f"{field} 응답값이 올바르지 않습니다.")
    employment = payload.get("employment_status")
    if employment is not None and employment not in EMPLOYMENT_STATUSES:
        raise DemandRuleError("employment_status 응답값이 올바르지 않습니다.")
    companion = payload.get("companion_support")
    if companion is not None and companion not in NEED_AREAS:
        raise DemandRuleError("companion_support 응답값이 올바르지 않습니다.")
    other_selected = "기타" in {
        payload.get("need_area"), payload.get("barrier"), employment, companion,
    }
    other_text = (payload.get("other_text") or "").strip()
    if other_selected and not other_text:
        raise DemandRuleError("기타 선택 시 기타 의견을 입력해야 합니다.")
    if not other_selected and other_text:
        raise DemandRuleError("기타를 선택한 경우에만 기타 의견을 입력할 수 있습니다.")
    if len(other_text) > OTHER_TEXT_MAX_LENGTH:
        raise DemandRuleError(f"기타 의견은 {OTHER_TEXT_MAX_LENGTH}자 이하여야 합니다.")

