"""미충족 수요 노출·제출·중복 보상 Application Layer."""
from __future__ import annotations

from datetime import datetime, timedelta
import os

from sqlalchemy import select
from sqlalchemy.engine import Engine

from .. import db
from ..feedback.reward import MockRewardProvider, RewardProvider
from ..services import recommendation_service
from ..services.pipeline_store import PipelineStore
from .domain import (
    AMOUNTS, BARRIERS, DURATIONS, EMPLOYMENT_STATUSES, FORM_VERSION, NEED_AREAS, NOTICE,
    OTHER_TEXT_MAX_LENGTH, DemandRuleError, TriggerReason, validate_response,
)
from .repositories import PolicyDemandRepository


class DemandNotFoundError(LookupError):
    pass


class DemandConflictError(RuntimeError):
    def __init__(self, message: str, cooldown_until: datetime | None = None) -> None:
        super().__init__(message)
        self.cooldown_until = cooldown_until


AREA_POLICY_NAMES = {
    "취업교육": (), "일경험·인턴": (), "채용연계": (), "구직활동비": ("디딤돌",),
    "월세·주거비": ("월세", "머물자리", "이사비"), "생활비": ("디딤돌",),
    "금융·부채지원": ("신용", "통장", "머물자리"), "심리·사회활동": (), "기타": (),
}


class PolicyDemandService:
    def __init__(self, engine: Engine, store: PipelineStore, reward_provider: RewardProvider | None = None) -> None:
        self.engine = engine
        self.store = store
        self.repository = PolicyDemandRepository(engine)
        self.reward_provider = reward_provider or MockRewardProvider()
        self.reward_amount = max(int(os.environ.get("POLICY_DEMAND_REWARD_AMOUNT", "1000")), 0)
        self.cooldown_days = max(int(os.environ.get("POLICY_DEMAND_COOLDOWN_DAYS", "90")), 1)

    def _session(self, user_id: str, session_id: str) -> dict:
        with self.engine.connect() as conn:
            row = conn.execute(select(db.citizen_sessions).where(db.citizen_sessions.c.session_id == session_id)).mappings().first()
        if row is None:
            raise DemandNotFoundError("추천 세션을 찾을 수 없습니다.")
        session = dict(row)
        if session.get("user_id") != user_id:
            raise DemandNotFoundError("본인의 로그인 추천 세션만 사용할 수 있습니다.")
        return session

    def _trigger_allowed(self, session: dict, reason: TriggerReason, need_area: str | None) -> bool:
        recs = recommendation_service.recommend_policies(session["input_payload"], session["diagnosis_result"], self.store)
        eligible = [item for item in recs if item.get("eligible")]
        if reason is TriggerReason.USER_REPORTED_MISMATCH:
            return bool(recs)
        if reason is TriggerReason.NO_RECOMMENDATION:
            return not recs
        if reason is TriggerReason.NO_ELIGIBLE_POLICY:
            return bool(recs) and not eligible
        if reason in {TriggerReason.NO_MATCHING_POLICY, TriggerReason.FOLLOWUP_UNMATCHED}:
            if not need_area:
                return True  # 첫 노출 시 영역은 아직 선택 전이며 제출 때 재검증한다.
            keywords = AREA_POLICY_NAMES.get(need_area, ())
            return not keywords or not any(any(keyword in item["policy"] for keyword in keywords) for item in eligible)
        return False

    def eligibility(self, *, user_id: str, session_id: str, reason: TriggerReason, need_area: str | None = None) -> dict:
        session = self._session(user_id, session_id)
        allowed = self._trigger_allowed(session, reason, need_area)
        cooldown_until = None
        if need_area:
            cutoff = datetime.now() - timedelta(days=self.cooldown_days)
            recent = self.repository.latest_same_situation(user_id, need_area, reason.value, cutoff)
            if recent:
                cooldown_until = recent["submitted_at"] + timedelta(days=self.cooldown_days)
                allowed = False
        message = (
            "현재 조건에 맞는 지원을 찾지 못했습니다. 필요한 지원을 알려주시면 익명으로 정책 개선 자료에 반영됩니다."
            if reason is not TriggerReason.USER_REPORTED_MISMATCH
            else "추천된 정책이 필요한 지원과 다르다면 짧게 알려주세요. 익명 정책 개선 자료로만 집계됩니다."
        )
        return {"eligible": allowed, "trigger_reason": reason, "expected_reward_amount": self.reward_amount,
                "cooldown_until": cooldown_until, "explanation": message}

    def form(self) -> dict:
        return {
            "form_version": FORM_VERSION, "notice": NOTICE,
            "exposure_message": "현재 조건에 맞는 지원을 찾지 못했습니다. 필요한 지원을 알려주시면 익명으로 정책 개선 자료에 반영됩니다.",
            "expected_reward_amount": self.reward_amount, "cooldown_days": self.cooldown_days,
            "other_text_max_length": OTHER_TEXT_MAX_LENGTH,
            "questions": [
                {"code": "need_area", "prompt": "지금 가장 필요한 지원은 무엇인가요?", "options": list(NEED_AREAS), "required": True},
                {"code": "duration", "prompt": "지원이 필요한 예상 기간은 어느 정도인가요?", "options": list(DURATIONS), "required": True},
                {"code": "amount", "prompt": "한 달 기준 필요한 지원 규모는 어느 정도인가요?", "options": list(AMOUNTS), "required": True},
                {"code": "barrier", "prompt": "현재 정책을 이용하기 어려운 가장 큰 이유는 무엇인가요?", "options": list(BARRIERS), "required": True},
                {"code": "companion_support", "prompt": "함께 제공되면 좋은 지원은 무엇인가요?", "options": list(NEED_AREAS), "required": False, "conditional": True},
                {"code": "employment_status", "prompt": "현재 고용상태는 무엇인가요?", "options": list(EMPLOYMENT_STATUSES), "required": False, "conditional": True},
            ],
        }

    def submit(self, *, user_id: str, payload: dict) -> dict:
        validate_response(payload)
        session = self._session(user_id, payload["session_id"])
        reason = TriggerReason(payload["trigger_reason"])
        if not self._trigger_allowed(session, reason, payload["need_area"]):
            raise DemandRuleError("현재 추천 결과는 해당 수요 설문 노출 조건에 해당하지 않습니다.")
        cutoff = datetime.now() - timedelta(days=self.cooldown_days)
        recent = self.repository.latest_same_situation(user_id, payload["need_area"], reason.value, cutoff)
        if recent:
            until = recent["submitted_at"] + timedelta(days=self.cooldown_days)
            raise DemandConflictError("동일한 수요 상황은 재참여 제한 기간 이후 다시 응답할 수 있습니다.", until)
        input_payload = session.get("input_payload") or {}
        values = {
            "user_id": user_id, "session_id": payload["session_id"], "trigger_reason": reason.value,
            "need_area": payload["need_area"], "duration": payload["duration"], "amount": payload["amount"],
            "barrier": payload["barrier"], "companion_support": payload.get("companion_support"),
            "employment_status": payload.get("employment_status"), "district_code": input_payload.get("dong_code"),
            "other_text": (payload.get("other_text") or "").strip() or None, "form_version": FORM_VERSION,
        }
        response, reward = self.repository.create_with_reward(values=values, reward_amount=self.reward_amount, reward_provider=self.reward_provider)
        return {"response_id": response["response_id"], "submitted_at": response["submitted_at"], "reward": {
            "reward_id": reward["reward_id"], "amount": reward["amount"], "status": reward["status"],
        }}
