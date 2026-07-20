"""미충족 수요 응답·리워드 저장 및 익명 집계 Repository."""
from __future__ import annotations

from collections import Counter
from datetime import datetime
import uuid

from sqlalchemy import and_, select
from sqlalchemy.engine import Engine

from . import models


def _protected(counter: Counter, minimum: int) -> dict:
    return {
        key: ({"suppressed": True, "count": None} if 0 < count < minimum else {"suppressed": False, "count": count})
        for key, count in sorted(counter.items())
    }


class PolicyDemandRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def latest_same_situation(self, user_id: str, need_area: str, trigger_reason: str, since: datetime) -> dict | None:
        with self.engine.connect() as conn:
            row = conn.execute(
                select(models.policy_demand_responses)
                .where(and_(
                    models.policy_demand_responses.c.user_id == user_id,
                    models.policy_demand_responses.c.need_area == need_area,
                    models.policy_demand_responses.c.trigger_reason == trigger_reason,
                    models.policy_demand_responses.c.submitted_at >= since,
                ))
                .order_by(models.policy_demand_responses.c.submitted_at.desc())
                .limit(1)
            ).mappings().first()
        return dict(row) if row else None

    def create_with_reward(self, *, values: dict, reward_amount: int, reward_provider) -> tuple[dict, dict]:
        response_id, reward_id = str(uuid.uuid4()), str(uuid.uuid4())
        result = reward_provider.grant(reward_id=reward_id, user_id=values["user_id"], amount=reward_amount)
        now = datetime.now()
        response = {"response_id": response_id, **values, "submitted_at": now}
        reward = {
            "reward_id": reward_id, "response_id": response_id, "user_id": values["user_id"],
            "amount": reward_amount, "status": result.status,
            "provider_reference": result.provider_reference, "created_at": now, "updated_at": now,
        }
        with self.engine.begin() as conn:
            conn.execute(models.policy_demand_responses.insert().values(**response))
            conn.execute(models.demand_reward_grants.insert().values(**reward))
        return response, reward

    def list_for_user(self, user_id: str) -> list[dict]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                select(models.policy_demand_responses, models.demand_reward_grants.c.amount.label("reward_amount"), models.demand_reward_grants.c.status.label("reward_status"))
                .join(models.demand_reward_grants, models.demand_reward_grants.c.response_id == models.policy_demand_responses.c.response_id)
                .where(models.policy_demand_responses.c.user_id == user_id)
                .order_by(models.policy_demand_responses.c.submitted_at.desc())
            ).mappings().all()
        return [dict(row) for row in rows]

    def aggregate(self, minimum: int, now: datetime) -> dict:
        with self.engine.connect() as conn:
            rows = [dict(row) for row in conn.execute(select(
                models.policy_demand_responses.c.response_id,
                models.policy_demand_responses.c.user_id,
                models.policy_demand_responses.c.trigger_reason,
                models.policy_demand_responses.c.need_area,
                models.policy_demand_responses.c.duration,
                models.policy_demand_responses.c.amount,
                models.policy_demand_responses.c.barrier,
                models.policy_demand_responses.c.companion_support,
                models.policy_demand_responses.c.employment_status,
                models.policy_demand_responses.c.district_code,
                models.policy_demand_responses.c.submitted_at,
                # other_text는 의도적으로 선택하지 않는다.
            )).mappings().all()]
        respondents = len({row["user_id"] for row in rows})
        base = {"respondent_count": respondents, "minimum_group_size": minimum, "suppressed": respondents < minimum}
        if respondents < minimum:
            return {**base, "metrics": None, "suppression_reason": "minimum_group_size_not_met"}
        def dist(field: str, subset=rows):
            return _protected(Counter(row[field] for row in subset if row.get(field)), minimum)
        recent_30 = [row for row in rows if (now - row["submitted_at"]).days < 30]
        prior_30 = [row for row in rows if 30 <= (now - row["submitted_at"]).days < 60]
        recent_90 = [row for row in rows if (now - row["submitted_at"]).days < 90]
        prior_90 = [row for row in rows if 90 <= (now - row["submitted_at"]).days < 180]
        def trend(current: list, prior: list) -> dict:
            if (0 < len(current) < minimum) or (0 < len(prior) < minimum):
                return {"suppressed": True, "current_count": None, "previous_count": None, "change_rate": None}
            rate = None if not prior else (len(current) - len(prior)) / len(prior)
            return {"suppressed": False, "current_count": len(current), "previous_count": len(prior), "change_rate": rate}
        return {**base, "suppression_reason": None, "metrics": {
            "need_area_distribution": dist("need_area"), "duration_distribution": dist("duration"),
            "amount_distribution": dist("amount"), "barrier_distribution": dist("barrier"),
            "companion_support_distribution": dist("companion_support"),
            "trigger_reason_distribution": dist("trigger_reason"), "district_distribution": dist("district_code"),
            "employment_distribution": dist("employment_status"), "category_gap_distribution": dist("need_area"),
            "trend_30_days": trend(recent_30, prior_30), "trend_90_days": trend(recent_90, prior_90),
        }, "rows_for_analysis": rows}
