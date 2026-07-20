"""정책 이용 피드백 Layered Architecture의 핵심 규칙/회귀 테스트."""
from __future__ import annotations

from datetime import date
import uuid

from sqlalchemy import func, select

from app.feedback import models
from app import db
from app.services import auth_service


POLICY_ID = "청년월세지원"


def _birthdate(age: int = 25) -> str:
    today = date.today()
    return date(today.year - age, today.month, today.day).isoformat()


def _auth_headers(client, suffix: str) -> dict[str, str]:
    email = f"feedback-{suffix}@test.com"
    user_id = str(uuid.uuid4())
    # 이 파일은 회원가입 기능이 아니라 피드백 API를 검증한다. 전체 suite에서
    # auth rate-limit 버킷을 소진하지 않도록 임시 DB에 정상 회원을 직접 준비한다.
    with client.engine.begin() as conn:
        conn.execute(
            db.users_table.insert().values(
                user_id=user_id,
                email=email,
                password_hash=auth_service.hash_password("password1234"),
                birthdate=_birthdate(),
                dong_code="26440",
                is_age_verified=False,
                auth_version=0,
                refresh_version=0,
            )
        )
    token = auth_service.create_access_token(user_id, version=0)
    return {"Authorization": f"Bearer {token}"}


def _create_usage(client, headers: dict[str, str]) -> str:
    response = client.post(
        "/api/v1/citizen/policy-usages", json={"policy_id": POLICY_ID}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()["usage_id"]


def _transition(client, headers: dict[str, str], usage_id: str, status: str) -> None:
    response = client.patch(
        f"/api/v1/citizen/policy-usages/{usage_id}/status",
        json={"status": status},
        headers=headers,
    )
    assert response.status_code == 200, response.text


def _reach(client, headers: dict[str, str], usage_id: str, target: str) -> None:
    path = ["application_started", "applied", "selected", "using", "completed"]
    for status in path[: path.index(target) + 1]:
        _transition(client, headers, usage_id, status)


def _applied_answers(choice: str = "제출서류") -> list[dict]:
    return [{"question_code": "application_barrier", "choice": choice}]


def _completed_answers(*, improvement: str = "지원금 확대", other_text: str | None = None) -> list[dict]:
    return [
        {"question_code": "most_helpful_area", "choice": "주거비"},
        {"question_code": "situation_change", "choice": "조금 좋아짐"},
        {"question_code": "support_adequacy", "choice": "금액 부족"},
        {"question_code": "followup_support", "choice": "월세·생활비"},
        {
            "question_code": "improvement_direction",
            "choice": improvement,
            "other_text": other_text,
        },
    ]


def test_feedback_requires_owned_policy_usage(client):
    headers = _auth_headers(client, "no-usage")
    response = client.post(
        "/api/v1/citizen/policy-usages/missing/feedback",
        json={"stage": "applied", "answers": _applied_answers()},
        headers=headers,
    )
    assert response.status_code == 404


def test_feedback_stage_must_match_current_usage_status(client):
    headers = _auth_headers(client, "stage-mismatch")
    usage_id = _create_usage(client, headers)
    _transition(client, headers, usage_id, "application_started")
    response = client.post(
        f"/api/v1/citizen/policy-usages/{usage_id}/feedback",
        json={"stage": "applied", "answers": _applied_answers()},
        headers=headers,
    )
    assert response.status_code == 422


def test_duplicate_stage_feedback_and_reward_are_blocked(client):
    headers = _auth_headers(client, "duplicate")
    usage_id = _create_usage(client, headers)
    _reach(client, headers, usage_id, "applied")
    payload = {"stage": "applied", "answers": _applied_answers()}

    first = client.post(
        f"/api/v1/citizen/policy-usages/{usage_id}/feedback", json=payload, headers=headers
    )
    second = client.post(
        f"/api/v1/citizen/policy-usages/{usage_id}/feedback", json=payload, headers=headers
    )

    assert first.status_code == 201
    assert first.json()["reward"]["status"] == "mock_paid"
    assert second.status_code == 409
    with client.engine.connect() as conn:
        reward_count = conn.scalar(
            select(func.count()).select_from(models.reward_grants).where(
                models.reward_grants.c.usage_id == usage_id
            )
        )
    assert reward_count == 1
    usage = client.get("/api/v1/citizen/me/policy-usages", headers=headers).json()[0]
    assert usage["available_feedback_stages"] == []
    assert usage["next_allowed_statuses"] == ["cancelled", "rejected", "selected"]
    assert usage["reward_summary"] == {"pending_amount": 0, "mock_paid_amount": 500}


def test_other_choice_requires_short_free_text(client):
    headers = _auth_headers(client, "other-required")
    usage_id = _create_usage(client, headers)
    _reach(client, headers, usage_id, "completed")
    response = client.post(
        f"/api/v1/citizen/policy-usages/{usage_id}/feedback",
        json={"stage": "completed", "answers": _completed_answers(improvement="기타")},
        headers=headers,
    )
    assert response.status_code == 422


def test_free_text_is_rejected_when_other_is_not_selected(client):
    headers = _auth_headers(client, "other-not-selected")
    usage_id = _create_usage(client, headers)
    _reach(client, headers, usage_id, "completed")
    response = client.post(
        f"/api/v1/citizen/policy-usages/{usage_id}/feedback",
        json={
            "stage": "completed",
            "answers": _completed_answers(improvement="지원금 확대", other_text="불필요한 원문"),
        },
        headers=headers,
    )
    assert response.status_code == 422


def test_details_are_suppressed_below_minimum_group_size(client):
    headers = _auth_headers(client, "suppressed")
    usage_id = _create_usage(client, headers)
    _reach(client, headers, usage_id, "applied")
    client.post(
        f"/api/v1/citizen/policy-usages/{usage_id}/feedback",
        json={"stage": "applied", "answers": _applied_answers()},
        headers=headers,
    )

    response = client.get(f"/api/v1/admin/policies/{POLICY_ID}/feedback-summary")
    assert response.status_code == 200
    assert response.json()["suppressed"] is True
    assert response.json()["metrics"] is None


def test_admin_aggregate_contains_no_personal_identifiers_or_free_text(client):
    for index in range(5):
        headers = _auth_headers(client, f"aggregate-{index}")
        usage_id = _create_usage(client, headers)
        _reach(client, headers, usage_id, "applied")
        response = client.post(
            f"/api/v1/citizen/policy-usages/{usage_id}/feedback",
            json={
                "stage": "applied",
                "answers": _applied_answers("자격조건" if index == 0 else "제출서류"),
            },
            headers=headers,
        )
        assert response.status_code == 201

    response = client.get(f"/api/v1/admin/policies/{POLICY_ID}/feedback-summary")
    body = response.json()
    serialized = response.text.lower()
    assert response.status_code == 200
    assert body["suppressed"] is False
    assert body["respondent_count"] == 5
    barrier_distribution = body["metrics"]["application_barrier_distribution"]
    assert barrier_distribution["자격조건"] == {"suppressed": True, "count": None}
    assert barrier_distribution["제출서류"] == {"suppressed": True, "count": None}
    for forbidden in ("user_id", "name", "email", "phone", "contact", "other_text", "financial"):
        assert forbidden not in serialized


def test_policy_usage_transition_is_forward_only_and_history_is_visible(client):
    headers = _auth_headers(client, "transition")
    usage_id = _create_usage(client, headers)
    _transition(client, headers, usage_id, "application_started")
    _transition(client, headers, usage_id, "applied")

    duplicate = client.patch(
        f"/api/v1/citizen/policy-usages/{usage_id}/status",
        json={"status": "applied"},
        headers=headers,
    )
    backward = client.patch(
        f"/api/v1/citizen/policy-usages/{usage_id}/status",
        json={"status": "application_started"},
        headers=headers,
    )
    records = client.get("/api/v1/citizen/me/policy-usages", headers=headers).json()

    assert duplicate.status_code == 422
    assert backward.status_code == 422
    assert [entry["status"] for entry in records[0]["status_history"]] == [
        "recommended", "application_started", "applied"
    ]
    assert records[0]["available_feedback_stages"] == ["applied"]
    assert records[0]["expected_reward_amount"] == 500
    assert records[0]["next_allowed_statuses"] == ["cancelled", "rejected", "selected"]


def test_feedback_form_contains_required_notice_and_stage_questions(client):
    headers = _auth_headers(client, "form")
    response = client.get(
        f"/api/v1/citizen/policies/{POLICY_ID}/feedback-form",
        params={"stage": "completed"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["notice"] == (
        "작성해 주신 의견은 익명으로 집계되어 부산시 청년정책 개선 자료로 전달됩니다. "
        "여러분의 경험이 다음 정책을 바꾸는 근거가 됩니다."
    )
    assert response.json()["expected_reward_amount"] == 1000
    assert {question["question_code"] for question in response.json()["questions"]} == {
        "most_helpful_area", "situation_change", "support_adequacy", "followup_support", "improvement_direction"
    }


def test_admin_policy_feedback_list_has_funnel_without_personal_data(client):
    response = client.get("/api/v1/admin/policy-feedback-summaries")
    assert response.status_code == 200
    body = response.json()
    assert {item["policy_name"] for item in body} >= {POLICY_ID}
    serialized = response.text.lower()
    for forbidden in ("user_id", "email", "phone", "other_text"):
        assert forbidden not in serialized
