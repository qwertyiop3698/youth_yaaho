"""app/services/auth_service.py 단위 테스트 (FastAPI 없이 서비스 로직만 검증)."""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from app import db
from app.services import auth_service


def _birthdate_for_age(age: int, as_of: date | None = None) -> date:
    """as_of 시점 기준 정확히 age세가 되는 생년월일(생일이 지난 날짜)을 만든다."""
    as_of = as_of or date.today()
    return date(as_of.year - age, as_of.month, as_of.day)


@pytest.fixture()
def engine(tmp_path):
    eng = db.create_db_engine(f"sqlite:///{tmp_path / 'auth_service_test.db'}")
    db.init_db(eng)
    return eng


class TestCalculateAge:
    def test_exact_birthday_today(self):
        today = date(2026, 7, 9)
        assert auth_service.calculate_age(date(2000, 7, 9), as_of=today) == 26

    def test_birthday_not_yet_this_year(self):
        today = date(2026, 7, 9)
        assert auth_service.calculate_age(date(2000, 12, 31), as_of=today) == 25

    def test_birthday_already_passed_this_year(self):
        today = date(2026, 7, 9)
        assert auth_service.calculate_age(date(2000, 1, 1), as_of=today) == 26


class TestPasswordHashing:
    def test_verify_correct_password(self):
        hashed = auth_service.hash_password("password1234")
        assert auth_service.verify_password("password1234", hashed) is True

    def test_verify_wrong_password(self):
        hashed = auth_service.hash_password("password1234")
        assert auth_service.verify_password("wrong-password", hashed) is False


class TestSignup:
    def test_signup_succeeds_for_age_39(self, engine):
        birthdate = _birthdate_for_age(39)
        result = auth_service.signup(engine, "young@test.com", "password1234", birthdate, "26440")
        assert result["email"] == "young@test.com"
        assert result["is_age_verified"] is False
        assert result["user_id"]

    def test_signup_rejected_for_age_40(self, engine):
        birthdate = _birthdate_for_age(40)
        with pytest.raises(auth_service.AgeLimitExceededError):
            auth_service.signup(engine, "old@test.com", "password1234", birthdate, "26440")

    def test_signup_rejected_for_minor(self, engine):
        birthdate = _birthdate_for_age(0)
        with pytest.raises(auth_service.AgeLimitExceededError):
            auth_service.signup(engine, "baby@test.com", "password1234", birthdate, None)

    def test_duplicate_email_rejected(self, engine):
        birthdate = _birthdate_for_age(25)
        auth_service.signup(engine, "dup@test.com", "password1234", birthdate, None)
        with pytest.raises(auth_service.EmailAlreadyExistsError):
            auth_service.signup(engine, "dup@test.com", "password1234", birthdate, None)


class TestLogin:
    def test_login_succeeds_and_issues_tokens(self, engine):
        birthdate = _birthdate_for_age(30)
        auth_service.signup(engine, "login@test.com", "password1234", birthdate, None)

        tokens = auth_service.login(engine, "login@test.com", "password1234")
        assert tokens["token_type"] == "bearer"
        assert tokens["access_token"]
        assert tokens["refresh_token"]

    def test_login_wrong_password_rejected(self, engine):
        birthdate = _birthdate_for_age(30)
        auth_service.signup(engine, "wrongpw@test.com", "password1234", birthdate, None)

        with pytest.raises(auth_service.InvalidCredentialsError):
            auth_service.login(engine, "wrongpw@test.com", "incorrect")

    def test_login_unknown_email_rejected(self, engine):
        with pytest.raises(auth_service.InvalidCredentialsError):
            auth_service.login(engine, "nobody@test.com", "password1234")

    def test_login_rejected_after_aging_out(self, engine):
        """가입 당시엔 39세였지만 생일이 지나 40세가 된 기존 회원의 로그인 거부."""
        birthdate = _birthdate_for_age(39)
        auth_service.signup(engine, "aged@test.com", "password1234", birthdate, None)

        # DB에 저장된 생년월일을 직접 40세가 되도록 되돌려서 "시간이 흘러 생일이 지남"을 시뮬레이션
        aged_birthdate = _birthdate_for_age(40)
        with engine.begin() as conn:
            conn.execute(
                db.users_table.update()
                .where(db.users_table.c.email == "aged@test.com")
                .values(birthdate=aged_birthdate.isoformat())
            )

        with pytest.raises(auth_service.AgeLimitExceededError):
            auth_service.login(engine, "aged@test.com", "password1234")


class TestRefreshTokens:
    def test_refresh_succeeds_with_valid_refresh_token(self, engine):
        birthdate = _birthdate_for_age(25)
        signup_result = auth_service.signup(engine, "refresh@test.com", "password1234", birthdate, None)
        tokens = auth_service.login(engine, "refresh@test.com", "password1234")

        new_tokens = auth_service.refresh_tokens(engine, tokens["refresh_token"])
        assert new_tokens["access_token"]
        payload = auth_service.decode_token(new_tokens["access_token"], "access")
        assert payload["sub"] == signup_result["user_id"]

    def test_refresh_rejects_access_token_used_as_refresh(self, engine):
        birthdate = _birthdate_for_age(25)
        auth_service.signup(engine, "wrongtype@test.com", "password1234", birthdate, None)
        tokens = auth_service.login(engine, "wrongtype@test.com", "password1234")

        with pytest.raises(auth_service.InvalidTokenError):
            auth_service.refresh_tokens(engine, tokens["access_token"])

    def test_refresh_rejects_expired_token(self, engine):
        birthdate = _birthdate_for_age(25)
        signup_result = auth_service.signup(engine, "expired@test.com", "password1234", birthdate, None)
        expired_refresh = auth_service.create_refresh_token(
            signup_result["user_id"], expires_delta=timedelta(seconds=-1)
        )

        with pytest.raises(auth_service.InvalidTokenError):
            auth_service.refresh_tokens(engine, expired_refresh)

    def test_refresh_rejected_after_aging_out(self, engine):
        birthdate = _birthdate_for_age(39)
        auth_service.signup(engine, "refresh_aged@test.com", "password1234", birthdate, None)
        tokens = auth_service.login(engine, "refresh_aged@test.com", "password1234")

        aged_birthdate = _birthdate_for_age(40)
        with engine.begin() as conn:
            conn.execute(
                db.users_table.update()
                .where(db.users_table.c.email == "refresh_aged@test.com")
                .values(birthdate=aged_birthdate.isoformat())
            )

        with pytest.raises(auth_service.AgeLimitExceededError):
            auth_service.refresh_tokens(engine, tokens["refresh_token"])
