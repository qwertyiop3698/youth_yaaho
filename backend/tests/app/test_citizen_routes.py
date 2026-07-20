from app import db
from pipeline.layer4_explanation import explanation_agent

DIAGNOSE_PAYLOAD = {
    "age_group": "25-29",
    "dong_code": "26440",
    "income_band": "2500-3000",
    "housing_type": "월세",
    "has_debt": True,
}


def _anonymous_session(client) -> tuple[str, dict[str, str]]:
    body = client.post("/api/v1/citizen/diagnose", json=DIAGNOSE_PAYLOAD).json()
    return body["session_id"], {"X-Session-Token": body["session_access_token"]}


class TestDiagnoseEndpoint:
    def test_returns_domain_indices_and_cluster_membership(self, client):
        response = client.post("/api/v1/citizen/diagnose", json=DIAGNOSE_PAYLOAD)
        assert response.status_code == 200
        body = response.json()

        assert body["diagnosis_mode"] == "approximate"
        assert "approximation_notice" in body
        assert set(body["domain_indices"].keys()) == {
            "주거비압박지수", "부채상환위험지수", "소득변동성지수", "소비압박지수", "신용취약지수",
        }
        assert len(body["cluster_membership"]) > 0
        assert 0.0 <= body["risk_probability"] <= 1.0

    def test_same_input_produces_different_session_ids(self, client):
        r1 = client.post("/api/v1/citizen/diagnose", json=DIAGNOSE_PAYLOAD)
        r2 = client.post("/api/v1/citizen/diagnose", json=DIAGNOSE_PAYLOAD)
        assert r1.json()["session_id"] != r2.json()["session_id"]

    def test_missing_pipeline_output_returns_empty_but_does_not_crash(self, empty_client):
        response = empty_client.post("/api/v1/citizen/diagnose", json=DIAGNOSE_PAYLOAD)
        assert response.status_code == 200
        body = response.json()
        assert body["domain_indices"] == {}
        assert body["cluster_membership"] == {}
        assert body["risk_probability"] is None


class TestRecommendationsEndpoint:
    def test_returns_ranked_policies_with_eligibility(self, client):
        session_id, headers = _anonymous_session(client)
        response = client.get(f"/api/v1/citizen/{session_id}/recommendations", headers=headers)
        assert response.status_code == 200
        recs = response.json()["recommendations"]

        assert len(recs) == 6
        priorities = [r["priority"] for r in recs]
        assert priorities == sorted(priorities)
        effects = [r["expected_effect"] for r in recs]
        assert effects == sorted(effects, reverse=True)
        for r in recs:
            assert r["eligibility_confidence"] in ("verified", "assumed_unresolved_codebook")

    def test_unknown_session_returns_404(self, client):
        response = client.get("/api/v1/citizen/no-such-session/recommendations")
        assert response.status_code == 404


class TestExplanationEndpoint:
    def test_generates_and_caches_explanation(self, client):
        session_id, headers = _anonymous_session(client)

        r1 = client.get(f"/api/v1/citizen/{session_id}/explanation", headers=headers)
        assert r1.status_code == 200
        body1 = r1.json()
        assert body1["is_llm_generated"] is False
        assert len(body1["explanation"]) > 0
        # doc06: 낙인 문구 금지
        assert "고위험군" not in body1["explanation"]

        r2 = client.get(f"/api/v1/citizen/{session_id}/explanation", headers=headers)
        assert r2.json()["explanation"] == body1["explanation"]  # 캐싱 확인

    def test_unknown_session_returns_404(self, client):
        response = client.get("/api/v1/citizen/no-such-session/explanation")
        assert response.status_code == 404

    def test_llm_success_is_cached_with_correct_flag(self, client, monkeypatch):
        monkeypatch.setattr(
            explanation_agent, "generate_explanation", lambda **kwargs: "Claude가 생성한 설명입니다."
        )
        session_id, headers = _anonymous_session(client)

        r1 = client.get(f"/api/v1/citizen/{session_id}/explanation", headers=headers)
        assert r1.status_code == 200
        body1 = r1.json()
        assert body1["is_llm_generated"] is True
        assert body1["explanation"] == "Claude가 생성한 설명입니다."

        # 캐싱 확인: 재요청 시 explanation_agent를 다시 부르지 않고 캐싱된 값+플래그를 반환
        monkeypatch.setattr(
            explanation_agent,
            "generate_explanation",
            lambda **kwargs: (_ for _ in ()).throw(AssertionError("캐시 히트 시 재호출되면 안 됨")),
        )
        r2 = client.get(f"/api/v1/citizen/{session_id}/explanation", headers=headers)
        assert r2.json() == body1


class TestHistoryEndpoint:
    def test_returns_stored_diagnosis(self, client):
        session_id, headers = _anonymous_session(client)
        response = client.get(f"/api/v1/citizen/{session_id}/history", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert len(body["history"]) == 1
        assert "note" in body  # session 단위 한계 명시 확인

    def test_unknown_session_returns_404(self, client):
        response = client.get("/api/v1/citizen/no-such-session/history")
        assert response.status_code == 404

    def test_anonymous_session_requires_separate_secret_and_stores_only_hash(self, client):
        body = client.post("/api/v1/citizen/diagnose", json=DIAGNOSE_PAYLOAD).json()
        session_id = body["session_id"]
        token = body["session_access_token"]

        assert token
        assert client.get(f"/api/v1/citizen/{session_id}/history").status_code == 401
        assert client.get(
            f"/api/v1/citizen/{session_id}/history",
            headers={"X-Session-Token": "wrong-token"},
        ).status_code == 401
        assert client.get(
            f"/api/v1/citizen/{session_id}/history",
            headers={"X-Session-Token": token},
        ).status_code == 200

        with client.engine.connect() as conn:
            row = conn.execute(
                db.citizen_sessions.select().where(db.citizen_sessions.c.session_id == session_id)
            ).mappings().first()
        assert row["access_token_hash"]
        assert row["access_token_hash"] != token
