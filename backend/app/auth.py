"""공통 백엔드 - Admin/Internal API 키 인증 (docs/07_api_spec.md 권한분리 원칙).

doc07: "`/admin/*`은 관리자 인증 필수, `/internal/*`은 외부 노출 금지(내부망 또는
API 키 인증)". 해커톤 MVP 최소 구현으로 고정 API 키(환경변수) 기반 인증만
붙인다 - 키 발급/폐기, 회전, 사용자별 권한 등은 실 서비스 전환 시 별도 설계 필요.

env var가 아예 설정되지 않은 경우 요청을 통과시키지 않고 503으로 막는다
(fail-closed) - "설정을 깜빡해서 무방비로 노출"되는 사고를 방지하기 위함이다.
"""
from __future__ import annotations

import os
import secrets

from fastapi import Header, HTTPException, status

from . import config  # noqa: F401 - .env를 아래 os.environ.get(...)보다 먼저 로드


def _check_api_key(provided: str | None, env_var_name: str, role: str) -> None:
    expected = os.environ.get(env_var_name)
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"{env_var_name} 환경변수가 설정되지 않아 {role} API를 사용할 수 없습니다.",
        )
    if len(expected.encode("utf-8")) < 32:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"{env_var_name}은 최소 32바이트의 무작위 값이어야 합니다.",
        )
    other_name = "INTERNAL_API_KEY" if env_var_name == "ADMIN_API_KEY" else "ADMIN_API_KEY"
    other = os.environ.get(other_name)
    if other and secrets.compare_digest(expected, other):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ADMIN_API_KEY와 INTERNAL_API_KEY는 서로 다른 값이어야 합니다.",
        )
    if not provided or not secrets.compare_digest(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"{role} API 키(X-API-Key 헤더)가 없거나 올바르지 않습니다.",
        )


def require_admin_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    _check_api_key(x_api_key, "ADMIN_API_KEY", "admin")


def require_internal_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    _check_api_key(x_api_key, "INTERNAL_API_KEY", "internal")
