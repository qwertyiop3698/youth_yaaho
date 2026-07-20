"""공통 백엔드 - 시민 회원(JWT) 선택적 인증 의존성.

`/citizen/diagnose`는 세션 기반 익명 플로우를 그대로 유지한다 - 로그인 없이도
여전히 익명으로 진단할 수 있어야 한다. 다만 Authorization 헤더로 access token이
오면 그 토큰을 검증해서 person(user_id)을 연동하고, 요청 시점 기준 나이가 청년
상한(만 39세)을 초과한 회원이면 신규 진단을 막는다(과거 히스토리는 그대로 유지).

app/auth.py(admin/internal 고정 API 키 인증)와는 별개의 인증 축이다.
"""
from __future__ import annotations

from datetime import date

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.engine import Engine

from .dependencies import get_engine
from .services import auth_service


def _resolve_current_user_id(authorization: str, engine: Engine, *, enforce_age_limit: bool) -> str:
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authorization 헤더는 'Bearer <token>' 형식이어야 합니다."
        )

    try:
        payload = auth_service.decode_token(token, "access")
    except auth_service.InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    user_id = payload["sub"]
    user = auth_service.get_user_by_id(engine, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="사용자를 찾을 수 없습니다.")
    if payload.get("ver") != user.get("auth_version"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="폐기된 로그인 토큰입니다.")

    age = auth_service.calculate_age(date.fromisoformat(user["birthdate"]))
    if enforce_age_limit and age > auth_service.MAX_AGE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"청년 상한(만 {auth_service.MAX_AGE}세)을 초과하여 신규 진단을 이용할 수 없습니다"
                f"(만 나이: {age}세). 과거 진단 기록은 삭제되지 않고 그대로 보관됩니다."
            ),
        )

    return user_id


def get_optional_current_user_id(
    authorization: str | None = Header(default=None, alias="Authorization"),
    engine: Engine = Depends(get_engine),
) -> str | None:
    """로그인 안 한 요청은 None, 유효한 Bearer 토큰이면 해당 user_id를 반환한다."""
    if authorization is None:
        return None
    return _resolve_current_user_id(authorization, engine, enforce_age_limit=True)


def get_current_user_id(
    authorization: str | None = Header(default=None, alias="Authorization"),
    engine: Engine = Depends(get_engine),
) -> str:
    """회원 전용 API에서 사용하는 필수 인증 의존성."""
    if authorization is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="로그인이 필요합니다.")
    return _resolve_current_user_id(authorization, engine, enforce_age_limit=False)
