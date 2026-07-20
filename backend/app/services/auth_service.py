"""공통 백엔드 - 시민 앱 회원가입/로그인 서비스.

2026-07-09 사용자 확정 설계:
- 청년 상한(만 39세) 이하만 가입 허용. 이건 앱 전체 기준이고, 개별 정책 자격조건은
  지금처럼 policy_catalog.yaml 기준으로 별도 체크한다(건드리지 않음).
- 생년월일은 본인인증이 아니라 자기기재(self-declared) 값이라 is_age_verified=False로
  명시한다 - 나중에 실제 본인인증을 붙이면 이 필드만 true로 전환하면 된다.
- 로그인/refresh 요청마다 생년월일로 나이를 다시 계산해서 39세 초과면 거부한다
  (배치/크론 없이 요청 시점 계산으로 충분). 나이 초과로 로그인이 막힌 회원의
  과거 진단 히스토리(citizen_sessions)는 삭제하지 않고 그대로 둔다.
- 비밀번호는 bcrypt로 해시, 토큰은 PyJWT(HS256)로 발급한다(access 1시간 + refresh 2주).
- JWT_SECRET_KEY는 fail-closed다: 미설정 시 이 모듈을 import하는 시점에 바로
  RuntimeError로 죽는다(admin/internal API 키와 동일한 원칙). 예전엔 미설정 시
  프로세스 수명 동안만 유지되는 임시 시크릿을 자동생성했는데, 이러면 해커톤
  시연 중 서버가 한 번이라도 재시작될 때 그 순간까지 발급된 모든 로그인
  세션(토큰)이 통째로 무효화되는 사고가 날 수 있어서 없앴다 - 대신 앱을 아예
  못 띄우게 막아서 배포 전에 반드시 고정 시크릿을 설정하도록 강제한다.

이 모듈은 FastAPI에 의존하지 않는다 - 라우터가 아래 커스텀 예외를 잡아서
HTTPException으로 변환한다.
"""
from __future__ import annotations

import os
import uuid
from datetime import date, datetime, timedelta, timezone

import bcrypt
import jwt
from sqlalchemy import select, update
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from .. import config  # noqa: F401 - .env를 아래 os.environ 조회보다 먼저 로드하기 위한 import
from .. import db

MAX_AGE = 39  # 청년 상한 - "만 39세 이하"만 허용
MIN_AGE = 18  # 서비스 최소 연령 - 미성년자 자기기재 가입 방지

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE = timedelta(hours=1)
REFRESH_TOKEN_EXPIRE = timedelta(days=14)

_TOKEN_TYPE_ACCESS = "access"
_TOKEN_TYPE_REFRESH = "refresh"


def _require_jwt_secret() -> str:
    secret = os.environ.get("JWT_SECRET_KEY")
    if not secret:
        raise RuntimeError(
            "JWT_SECRET_KEY 환경변수가 설정되지 않았습니다. backend/.env.example을 참고해 "
            "`openssl rand -hex 32`로 생성한 값을 backend/.env에 JWT_SECRET_KEY=<값>으로 "
            "고정한 뒤 다시 실행하세요. (서버 재시작마다 시크릿이 바뀌면 그 순간까지 발급된 "
            "로그인 세션이 전부 무효화되므로, 임시 시크릿 자동생성 대신 앱 시작을 막습니다.)"
        )
    if len(secret.encode("utf-8")) < 32:
        raise RuntimeError("JWT_SECRET_KEY는 최소 32바이트의 무작위 값이어야 합니다.")
    return secret


# 모듈 import 시점에 즉시 확인한다 - 앱이 기동되자마자(첫 로그인 요청을 기다리지
# 않고) 실패하게 하기 위함이다. 이 값은 프로세스 수명 동안 고정된다.
_JWT_SECRET = _require_jwt_secret()


class EmailAlreadyExistsError(Exception):
    """이미 가입된 이메일로 가입을 시도한 경우."""


class AgeLimitExceededError(Exception):
    """청년 상한(만 39세)을 초과한 경우. 사유 메시지는 detail에 담는다."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class InvalidCredentialsError(Exception):
    """이메일/비밀번호가 일치하지 않는 경우."""


class InvalidTokenError(Exception):
    """토큰이 만료/변조되었거나 타입이 맞지 않는 경우."""


class UserNotFoundError(Exception):
    """토큰에 담긴 사용자를 DB에서 찾을 수 없는 경우(탈퇴 등)."""


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


# 존재하지 않는 이메일도 bcrypt 검증을 한 번 수행해 응답 시간 차이로 가입 여부를
# 추측하기 어렵게 한다. 프로세스 시작 시 한 번만 생성한다.
_DUMMY_PASSWORD_HASH = hash_password("not-a-real-user-password")


def calculate_age(birthdate: date, as_of: date | None = None) -> int:
    """만 나이 계산(생일이 아직 지나지 않았으면 1살 덜 센다)."""
    as_of = as_of or date.today()
    had_birthday = (as_of.month, as_of.day) >= (birthdate.month, birthdate.day)
    return as_of.year - birthdate.year - (0 if had_birthday else 1)


def _create_token(user_id: str, token_type: str, version: int, expires_delta: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "type": token_type,
        "ver": version,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, _JWT_SECRET, algorithm=ALGORITHM)


def create_access_token(
    user_id: str, expires_delta: timedelta | None = None, *, version: int = 0
) -> str:
    return _create_token(user_id, _TOKEN_TYPE_ACCESS, version, expires_delta or ACCESS_TOKEN_EXPIRE)


def create_refresh_token(
    user_id: str, expires_delta: timedelta | None = None, *, version: int = 0
) -> str:
    return _create_token(user_id, _TOKEN_TYPE_REFRESH, version, expires_delta or REFRESH_TOKEN_EXPIRE)


def decode_token(token: str, expected_type: str) -> dict:
    """토큰을 검증하고 payload를 반환한다. 만료/변조/타입불일치 시 InvalidTokenError."""
    try:
        payload = jwt.decode(token, _JWT_SECRET, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise InvalidTokenError("토큰이 만료되었습니다.") from exc
    except jwt.InvalidTokenError as exc:
        raise InvalidTokenError("유효하지 않은 토큰입니다.") from exc

    if payload.get("type") != expected_type:
        raise InvalidTokenError(f"토큰 타입이 올바르지 않습니다(expected={expected_type}).")
    return payload


def get_user_by_id(engine: Engine, user_id: str) -> dict | None:
    with engine.connect() as conn:
        row = conn.execute(select(db.users_table).where(db.users_table.c.user_id == user_id)).mappings().first()
    return dict(row) if row is not None else None


def _get_user_by_email(engine: Engine, email: str) -> dict | None:
    with engine.connect() as conn:
        row = conn.execute(select(db.users_table).where(db.users_table.c.email == email)).mappings().first()
    return dict(row) if row is not None else None


def _issue_tokens(user_id: str, auth_version: int, refresh_version: int) -> dict:
    return {
        "access_token": create_access_token(user_id, version=auth_version),
        "refresh_token": create_refresh_token(user_id, version=refresh_version),
        "token_type": "bearer",
    }


def signup(engine: Engine, email: str, password: str, birthdate: date, dong_code: str | None) -> dict:
    if _get_user_by_email(engine, email) is not None:
        raise EmailAlreadyExistsError(f"이미 가입된 이메일입니다: {email}")

    age = calculate_age(birthdate)
    if age < MIN_AGE:
        raise AgeLimitExceededError(
            f"서비스 최소 연령(만 {MIN_AGE}세)에 미달하여 가입할 수 없습니다(만 나이: {age}세)."
        )
    if age > MAX_AGE:
        raise AgeLimitExceededError(
            f"청년 상한(만 {MAX_AGE}세)을 초과하여 가입할 수 없습니다(만 나이: {age}세)."
        )

    user_id = str(uuid.uuid4())
    try:
        with engine.begin() as conn:
            conn.execute(
                db.users_table.insert().values(
                    user_id=user_id,
                    email=email,
                    password_hash=hash_password(password),
                    birthdate=birthdate.isoformat(),
                    dong_code=dong_code,
                    is_age_verified=False,  # 자기기재 값 - 본인인증 아님
                    auth_version=0,
                    refresh_version=0,
                )
            )
    except IntegrityError as exc:
        # 사전 조회와 INSERT 사이에 같은 이메일 가입이 들어오는 경쟁 조건도 500이
        # 아니라 동일한 409 계약으로 처리한다.
        raise EmailAlreadyExistsError(f"이미 가입된 이메일입니다: {email}") from exc

    return {"user_id": user_id, "email": email, "is_age_verified": False}


def login(engine: Engine, email: str, password: str) -> dict:
    user = _get_user_by_email(engine, email)
    password_hash = user["password_hash"] if user is not None else _DUMMY_PASSWORD_HASH
    password_matches = verify_password(password, password_hash)
    if user is None or not password_matches:
        raise InvalidCredentialsError("이메일 또는 비밀번호가 올바르지 않습니다.")

    age = calculate_age(date.fromisoformat(user["birthdate"]))
    if age < MIN_AGE:
        raise AgeLimitExceededError(
            f"서비스 최소 연령(만 {MIN_AGE}세)에 미달하여 로그인할 수 없습니다(만 나이: {age}세)."
        )
    if age > MAX_AGE:
        raise AgeLimitExceededError(
            f"청년 상한(만 {MAX_AGE}세)을 초과하여 더 이상 로그인할 수 없습니다(만 나이: {age}세). "
            "과거 진단 기록은 삭제되지 않고 그대로 보관됩니다."
        )

    with engine.begin() as conn:
        conn.execute(
            update(db.users_table)
            .where(db.users_table.c.user_id == user["user_id"])
            .values(
                auth_version=db.users_table.c.auth_version + 1,
                refresh_version=db.users_table.c.refresh_version + 1,
            )
        )
        versions = conn.execute(
            select(db.users_table.c.auth_version, db.users_table.c.refresh_version).where(
                db.users_table.c.user_id == user["user_id"]
            )
        ).mappings().one()
    return _issue_tokens(user["user_id"], versions["auth_version"], versions["refresh_version"])


def refresh_tokens(engine: Engine, refresh_token: str) -> dict:
    try:
        payload = decode_token(refresh_token, _TOKEN_TYPE_REFRESH)
    except InvalidTokenError:
        raise

    with engine.begin() as conn:
        user_row = conn.execute(
            select(db.users_table).where(db.users_table.c.user_id == payload["sub"])
        ).mappings().first()
        if user_row is None:
            raise UserNotFoundError("토큰에 해당하는 사용자를 찾을 수 없습니다.")
        user = dict(user_row)

        age = calculate_age(date.fromisoformat(user["birthdate"]))
        if age < MIN_AGE:
            raise AgeLimitExceededError(
                f"서비스 최소 연령(만 {MIN_AGE}세)에 미달하여 세션을 갱신할 수 없습니다(만 나이: {age}세)."
            )
        if age > MAX_AGE:
            raise AgeLimitExceededError(
                f"청년 상한(만 {MAX_AGE}세)을 초과하여 세션을 갱신할 수 없습니다(만 나이: {age}세). "
                "과거 진단 기록은 삭제되지 않고 그대로 보관됩니다."
            )

        token_version = payload.get("ver")
        if not isinstance(token_version, int):
            raise InvalidTokenError("refresh token 버전 정보가 없습니다.")
        rotated = conn.execute(
            update(db.users_table)
            .where(
                db.users_table.c.user_id == user["user_id"],
                db.users_table.c.refresh_version == token_version,
            )
            .values(refresh_version=token_version + 1)
        )
        if rotated.rowcount != 1:
            raise InvalidTokenError("이미 사용되었거나 폐기된 refresh token입니다.")

    return _issue_tokens(user["user_id"], user["auth_version"], token_version + 1)


def revoke_user_tokens(engine: Engine, user_id: str) -> None:
    """로그아웃 시 기존 access/refresh 토큰을 모두 즉시 폐기한다."""
    with engine.begin() as conn:
        result = conn.execute(
            update(db.users_table)
            .where(db.users_table.c.user_id == user_id)
            .values(
                auth_version=db.users_table.c.auth_version + 1,
                refresh_version=db.users_table.c.refresh_version + 1,
            )
        )
    if result.rowcount != 1:
        raise UserNotFoundError("사용자를 찾을 수 없습니다.")
