"""미충족 정책 수요 수집·보상·익명 분석 테스트."""
from __future__ import annotations

from datetime import date, datetime
import uuid

from app import db
from app.policy_demand.domain import TriggerReason
from app.policy_demand.service import PolicyDemandService
from app.policy_demand_analysis.scoring import DemandScoringConfig, score_need_area
from app.services import auth_service
from app.services.pipeline_store import get_pipeline_store


def _user_session(client, suffix: str) -> tuple[dict[str, str], str, str]:
    user_id = str(uuid.uuid4())
    email = f"demand-{suffix}@test.com"
    today = date.today()
    with client.engine.begin() as conn:
        conn.execute(db.users_table.insert().values(
            user_id=user_id, email=email, password_hash=auth_service.hash_password("password1234"),
            birthdate=date(today.year - 25, today.month, today.day).isoformat(), dong_code="26440",
            is_age_verified=False, auth_version=0, refresh_version=0,
        ))
        session_id = str(uuid.uuid4())
        conn.execute(db.citizen_sessions.insert().values(
            session_id=session_id, user_id=user_id,
            input_payload={"age_group": "25-29", "dong_code": "26440", "income_band": "2000-2500", "housing_type": "월세", "has_debt": True},
            diagnosis_result={"domain_indices": {"주거비압박지수": 0.8, "소득변동성지수": 0.5, "신용취약지수": 0.4, "부채상환위험지수": 0.4, "소비압박지수": 0.4}, "risk_probability": 0.6},
        ))
    token = auth_service.create_access_token(user_id, version=0)
    return {"Authorization": f"Bearer {token}"}, session_id, user_id


def _payload(session_id: str, **overrides) -> dict:
    base = {
        "session_id": session_id, "trigger_reason": "user_reported_mismatch",
        "need_area": "구직활동비", "duration": "7~12개월", "amount": "31~50만 원",
        "barrier": "지원내용 불일치", "companion_support": "취업교육", "employment_status": "구직 중",
    }
    return {**base, **overrides}


def _rows(count=5, **overrides):
    base = {"trigger_reason": "no_matching_policy", "need_area": "생활비", "duration": "7~12개월",
            "amount": "31~50만 원", "barrier": "해당 정책 자체가 없음", "companion_support": "취업교육",
            "submitted_at": datetime.utcnow(), "district_code": "26440", "employment_status": "구직 중"}
    return [{**base, **overrides, "user_id": str(index)} for index in range(count)]


def test_demand_is_blocked_without_exposure_condition(client):
    headers, session_id, _ = _user_session(client, "blocked")
    response = client.post("/api/v1/citizen/policy-demand/responses", headers=headers,
                           json=_payload(session_id, trigger_reason="no_eligible_policy"))
    assert response.status_code == 422


def test_no_recommendation_allows_participation(monkeypatch, client):
    headers, session_id, user_id = _user_session(client, "none")
    service = PolicyDemandService(client.engine, client.app.dependency_overrides[get_pipeline_store]())
    monkeypatch.setattr("app.policy_demand.service.recommendation_service.recommend_policies", lambda *args: [])
    result = service.eligibility(user_id=user_id, session_id=session_id, reason=TriggerReason.NO_RECOMMENDATION)
    assert result["eligible"] is True


def test_user_reported_policy_mismatch_allows_participation(client):
    headers, session_id, _ = _user_session(client, "mismatch")
    response = client.post("/api/v1/citizen/policy-demand/responses", headers=headers, json=_payload(session_id))
    assert response.status_code == 201
    assert response.json()["reward"]["status"] == "mock_paid"
    assert response.json()["reward"]["amount"] == 1000


def test_same_demand_situation_is_blocked_for_90_days(client):
    headers, session_id, _ = _user_session(client, "duplicate")
    assert client.post("/api/v1/citizen/policy-demand/responses", headers=headers, json=_payload(session_id)).status_code == 201
    second = client.post("/api/v1/citizen/policy-demand/responses", headers=headers, json=_payload(session_id))
    assert second.status_code == 409
    assert "cooldown_until" in second.text


def test_different_need_area_can_participate_separately(client):
    headers, session_id, _ = _user_session(client, "other-area")
    assert client.post("/api/v1/citizen/policy-demand/responses", headers=headers, json=_payload(session_id)).status_code == 201
    assert client.post("/api/v1/citizen/policy-demand/responses", headers=headers,
                       json=_payload(session_id, need_area="생활비")).status_code == 201


def test_other_choice_requires_free_text(client):
    headers, session_id, _ = _user_session(client, "other")
    response = client.post("/api/v1/citizen/policy-demand/responses", headers=headers,
                           json=_payload(session_id, need_area="기타"))
    assert response.status_code == 422
    ok = client.post("/api/v1/citizen/policy-demand/responses", headers=headers,
                     json=_payload(session_id, need_area="기타", other_text="교통 지원"))
    assert ok.status_code == 201


def test_demand_form_has_four_required_questions_and_notice(client):
    headers, _, _ = _user_session(client, "form")
    body = client.get("/api/v1/citizen/policy-demand/form", headers=headers).json()
    assert sum(question["required"] for question in body["questions"]) == 4
    assert len(body["questions"]) == 6
    assert "익명으로 집계" in body["notice"]


def test_aggregate_is_suppressed_below_minimum(client):
    headers, session_id, _ = _user_session(client, "small")
    client.post("/api/v1/citizen/policy-demand/responses", headers=headers, json=_payload(session_id))
    body = client.get("/api/v1/admin/policy-demand-summary").json()
    assert body["suppressed"] is True
    assert body["metrics"] is None


def test_suppressed_need_area_generates_no_score():
    result = score_need_area(_rows(4), total=4, max_count=0, minimum=5, now=datetime.utcnow(), config=DemandScoringConfig())
    assert result["score"] is None
    assert result["primary_recommendation"] == "insufficient_data"


def test_small_subgroup_is_excluded_instead_of_counted_as_zero():
    rows = _rows()
    rows[0]["barrier"] = "재직·미취업 조건"
    result = score_need_area(rows, total=5, max_count=5, minimum=5, now=datetime.utcnow(), config=DemandScoringConfig())
    assert result["components"]["eligibility_gap"] is None


def test_demand_priority_score_is_calculated():
    result = score_need_area(_rows(), total=5, max_count=5, minimum=5, now=datetime.utcnow(), config=DemandScoringConfig())
    assert 0 <= result["score"] <= 100


def test_policy_gap_generates_create_new_policy():
    result = score_need_area(_rows(), total=5, max_count=5, minimum=5, now=datetime.utcnow(), config=DemandScoringConfig())
    assert result["primary_recommendation"] == "create_new_policy"


def test_eligibility_barrier_generates_broaden_eligibility():
    result = score_need_area(_rows(barrier="재직·미취업 조건", trigger_reason="no_eligible_policy"), total=5, max_count=5, minimum=5, now=datetime.utcnow(), config=DemandScoringConfig())
    assert result["primary_recommendation"] == "broaden_eligibility"


def test_long_duration_generates_extend_duration():
    rows = _rows(trigger_reason="user_reported_mismatch", barrier="지원내용 불일치", amount="10만 원 이하", companion_support=None)
    result = score_need_area(rows, total=5, max_count=5, minimum=5, now=datetime.utcnow(), config=DemandScoringConfig())
    assert result["primary_recommendation"] == "extend_duration"


def test_admin_and_export_never_expose_personal_or_free_text(client):
    for index in range(5):
        headers, session_id, _ = _user_session(client, f"privacy-{index}")
        assert client.post("/api/v1/citizen/policy-demand/responses", headers=headers,
                           json=_payload(session_id)).status_code == 201
    for path in ("/api/v1/admin/policy-demand-summary", "/api/v1/admin/policy-demand-priorities",
                 "/api/v1/admin/policy-demand/export?format=csv", "/api/v1/admin/policy-demand/export?format=json"):
        response = client.get(path)
        assert response.status_code == 200
        text = response.text.lower()
        for forbidden in ("user_id", "email", "phone", "other_text", "교통 지원"):
            assert forbidden not in text


def test_my_demand_response_alias_returns_only_current_users_records(client):
    headers, session_id, _ = _user_session(client, "mine")
    client.post("/api/v1/citizen/policy-demand/responses", headers=headers, json=_payload(session_id))
    response = client.get("/api/v1/citizen/me/policy-demand-responses", headers=headers)
    assert response.status_code == 200
    assert response.json()[0]["need_area"] == "구직활동비"
