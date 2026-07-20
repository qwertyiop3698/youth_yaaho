"""citizen 라우터의 회원가입/로그인/refresh 엔드포인트 + 인증된 diagnose 연동 테스트.

기존 익명 진단 플로우가 안 망가졌는지(로그인 없이도 여전히 동작하는지)도 함께
확인한다.
"""
from __future__ import annotations

from datetime import date, timedelta

from app import db
from app.services import auth_service

DIAGNOSE_PAYLOAD = {
    "age_group": "25-29",
    "dong_code": "26440",
    "income_band": "2500-3000",
    "housing_type": "월세",
    "has_debt": True,
}


def _birthdate_for_age(age: int, as_of: date | None = None) -> str:
    as_of = as_of or date.today()
    return date(as_of.year - age, as_of.month, as_of.day).isoformat()


class TestSignup:
    def test_signup_succeeds_for_age_39(self, client):
        response = client.post(
            "/api/v1/citizen/auth/signup",
            json={
                "email": "young39@test.com",
                "password": "password1234",
                "birthdate": _birthdate_for_age(39),
                "dong_code": "26440",
            },
        )
        assert response.status_code == 201
        body = response.json()
        assert body["email"] == "young39@test.com"
        assert body["is_age_verified"] is False
        assert body["user_id"]

    def test_signup_rejected_for_age_40(self, client):
        response = client.post(
            "/api/v1/citizen/auth/signup",
            json={
                "email": "old40@test.com",
                "password": "password1234",
                "birthdate": _birthdate_for_age(40),
                "dong_code": "26440",
            },
        )
        assert response.status_code == 400

    def test_signup_duplicate_email_rejected(self, client):
        payload = {
            "email": "dup@test.com",
            "password": "password1234",
            "birthdate": _birthdate_for_age(25),
            "dong_code": None,
        }
        client.post("/api/v1/citizen/auth/signup", json=payload)
        response = client.post("/api/v1/citizen/auth/signup", json=payload)
        assert response.status_code == 409


class TestLoginAndDiagnoseIntegration:
    def _signup_and_login(self, client, email: str, age: int = 25) -> dict:
        client.post(
            "/api/v1/citizen/auth/signup",
            json={
                "email": email,
                "password": "password1234",
                "birthdate": _birthdate_for_age(age),
                "dong_code": None,
            },
        )
        response = client.post("/api/v1/citizen/auth/login", json={"email": email, "password": "password1234"})
        assert response.status_code == 200
        return response.json()

    def test_login_issues_access_and_refresh_tokens(self, client):
        tokens = self._signup_and_login(client, "login_route@test.com")
        assert tokens["token_type"] == "bearer"
        assert tokens["access_token"]
        assert tokens["refresh_token"]

    def test_login_wrong_password_returns_401(self, client):
        self._signup_and_login(client, "wrongpw_route@test.com")
        response = client.post(
            "/api/v1/citizen/auth/login", json={"email": "wrongpw_route@test.com", "password": "wrong"}
        )
        assert response.status_code == 401

    def test_diagnose_without_token_still_works_anonymously(self, client):
        # 기존 익명 플로우가 안 망가졌는지 확인 - 로그인 없이도 여전히 진단 가능해야 함
        response = client.post("/api/v1/citizen/diagnose", json=DIAGNOSE_PAYLOAD)
        assert response.status_code == 200

    def test_diagnose_with_valid_token_links_user_and_succeeds(self, client):
        tokens = self._signup_and_login(client, "diagnose_route@test.com")
        response = client.post(
            "/api/v1/citizen/diagnose",
            json=DIAGNOSE_PAYLOAD,
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        assert response.status_code == 200
        session_id = response.json()["session_id"]

        with client.engine.connect() as conn:
            row = (
                conn.execute(
                    db.citizen_sessions.select().where(db.citizen_sessions.c.session_id == session_id)
                )
                .mappings()
                .first()
            )
        assert row["user_id"] is not None

    def test_member_session_requires_owner_token(self, client):
        owner_tokens = self._signup_and_login(client, "session_owner@test.com")
        other_tokens = self._signup_and_login(client, "session_other@test.com")
        session_id = client.post(
            "/api/v1/citizen/diagnose",
            json=DIAGNOSE_PAYLOAD,
            headers={"Authorization": f"Bearer {owner_tokens['access_token']}"},
        ).json()["session_id"]

        assert client.get(f"/api/v1/citizen/{session_id}/history").status_code == 401
        assert client.get(
            f"/api/v1/citizen/{session_id}/history",
            headers={"Authorization": f"Bearer {other_tokens['access_token']}"},
        ).status_code == 403
        assert client.get(
            f"/api/v1/citizen/{session_id}/history",
            headers={"Authorization": f"Bearer {owner_tokens['access_token']}"},
        ).status_code == 200

    def test_delete_account_removes_user_and_linked_sessions(self, client):
        tokens = self._signup_and_login(client, "delete_me@test.com")
        session_id = client.post(
            "/api/v1/citizen/diagnose",
            json=DIAGNOSE_PAYLOAD,
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        ).json()["session_id"]

        response = client.delete(
            "/api/v1/citizen/auth/me",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        assert response.status_code == 204
        with client.engine.connect() as conn:
            assert conn.execute(
                db.users_table.select().where(db.users_table.c.email == "delete_me@test.com")
            ).first() is None
            assert conn.execute(
                db.citizen_sessions.select().where(db.citizen_sessions.c.session_id == session_id)
            ).first() is None

    def test_expired_access_token_rejected_on_diagnose(self, client):
        tokens = self._signup_and_login(client, "expired_route@test.com")
        payload = auth_service.decode_token(tokens["access_token"], "access")
        expired_token = auth_service.create_access_token(payload["sub"], expires_delta=timedelta(seconds=-1))

        response = client.post(
            "/api/v1/citizen/diagnose",
            json=DIAGNOSE_PAYLOAD,
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert response.status_code == 401

    def test_malformed_authorization_header_rejected(self, client):
        tokens = self._signup_and_login(client, "malformed_route@test.com")
        response = client.post(
            "/api/v1/citizen/diagnose",
            json=DIAGNOSE_PAYLOAD,
            headers={"Authorization": tokens["access_token"]},  # "Bearer " 접두어 누락
        )
        assert response.status_code == 401

    def test_diagnose_blocked_for_member_who_aged_out(self, client):
        """가입 당시엔 조건을 만족했지만 생일이 지나 40세가 된 회원은 신규 진단이 막힘."""
        email = "diagnose_aged_route@test.com"
        tokens = self._signup_and_login(client, email, age=39)

        aged_birthdate = _birthdate_for_age(40)
        with client.engine.begin() as conn:
            conn.execute(db.users_table.update().where(db.users_table.c.email == email).values(birthdate=aged_birthdate))

        response = client.post(
            "/api/v1/citizen/diagnose",
            json=DIAGNOSE_PAYLOAD,
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        assert response.status_code == 403

    def test_login_rejected_after_aging_out(self, client):
        """생일이 지나 40세가 된 기존 회원의 로그인 거부 - 과거 히스토리는 유지됨."""
        email = "aged_route@test.com"
        tokens = self._signup_and_login(client, email, age=39)

        # 나이 초과 전에 진단 히스토리를 하나 만들어둔다(삭제되면 안 됨을 확인하기 위해)
        client.post(
            "/api/v1/citizen/diagnose",
            json=DIAGNOSE_PAYLOAD,
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        with client.engine.connect() as conn:
            sessions_before = (
                conn.execute(db.citizen_sessions.select().where(db.citizen_sessions.c.user_id.isnot(None)))
                .mappings()
                .all()
            )
        assert len(sessions_before) >= 1

        aged_birthdate = _birthdate_for_age(40)
        with client.engine.begin() as conn:
            conn.execute(db.users_table.update().where(db.users_table.c.email == email).values(birthdate=aged_birthdate))

        response = client.post("/api/v1/citizen/auth/login", json={"email": email, "password": "password1234"})
        assert response.status_code == 401

        # 로그인은 막혔지만 기존 히스토리는 그대로 남아 있어야 함
        with client.engine.connect() as conn:
            sessions_after = (
                conn.execute(db.citizen_sessions.select().where(db.citizen_sessions.c.user_id.isnot(None)))
                .mappings()
                .all()
            )
        assert len(sessions_after) == len(sessions_before)


class TestRefresh:
    def _signup_and_login(self, client, email: str, age: int = 25) -> dict:
        client.post(
            "/api/v1/citizen/auth/signup",
            json={
                "email": email,
                "password": "password1234",
                "birthdate": _birthdate_for_age(age),
                "dong_code": None,
            },
        )
        response = client.post("/api/v1/citizen/auth/login", json={"email": email, "password": "password1234"})
        return response.json()

    def test_refresh_issues_new_access_token(self, client):
        tokens = self._signup_and_login(client, "refresh_route@test.com")
        response = client.post("/api/v1/citizen/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
        assert response.status_code == 200
        assert response.json()["access_token"]

        replay = client.post(
            "/api/v1/citizen/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        )
        assert replay.status_code == 401

    def test_refresh_rejects_expired_refresh_token(self, client):
        tokens = self._signup_and_login(client, "refresh_expired_route@test.com")
        payload = auth_service.decode_token(tokens["refresh_token"], "refresh")
        expired_refresh = auth_service.create_refresh_token(payload["sub"], expires_delta=timedelta(seconds=-1))

        response = client.post("/api/v1/citizen/auth/refresh", json={"refresh_token": expired_refresh})
        assert response.status_code == 401

    def test_refresh_rejected_after_aging_out(self, client):
        email = "refresh_aged_route@test.com"
        tokens = self._signup_and_login(client, email, age=39)

        aged_birthdate = _birthdate_for_age(40)
        with client.engine.begin() as conn:
            conn.execute(db.users_table.update().where(db.users_table.c.email == email).values(birthdate=aged_birthdate))

        response = client.post("/api/v1/citizen/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
        assert response.status_code == 401


class TestLogout:
    def test_logout_revokes_access_and_refresh_tokens(self, client):
        helper = TestLoginAndDiagnoseIntegration()
        tokens = helper._signup_and_login(client, "logout_route@test.com")

        response = client.post(
            "/api/v1/citizen/auth/logout",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        assert response.status_code == 204

        assert client.post(
            "/api/v1/citizen/diagnose",
            json=DIAGNOSE_PAYLOAD,
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        ).status_code == 401
        assert client.post(
            "/api/v1/citizen/auth/refresh",
            json={"refresh_token": tokens["refresh_token"]},
        ).status_code == 401
