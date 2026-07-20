"""공통 백엔드 - FastAPI 앱 조립 (docs/07_api_spec.md).

실행: `uvicorn app.main:app --reload` (backend/ 디렉토리에서).
"""
from __future__ import annotations

from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import config  # noqa: F401 - .env를 다른 모든 import보다 먼저 로드(JWT_SECRET_KEY 등)
from .dependencies import get_engine
from .rate_limit import CitizenRateLimitMiddleware
from .routers import admin, citizen, internal
from .feedback.router import admin_router as feedback_admin_router
from .feedback.router import citizen_router as feedback_citizen_router
from .feedback_analysis.router import router as feedback_analysis_router
from .policy_demand.router import admin_router as policy_demand_admin_router
from .policy_demand.router import citizen_router as policy_demand_citizen_router
from .policy_demand.router import citizen_me_router as policy_demand_citizen_me_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_engine()  # DB 테이블 생성 보장
    yield


app = FastAPI(title="Y-SAFE / 청년야호 공통 백엔드", version="0.1.0", lifespan=lifespan)
app.add_middleware(CitizenRateLimitMiddleware)

# 웹 대시보드(React, 별도 origin)에서 브라우저로 직접 호출하기 위해 필요.
# 기본값은 로컬 개발 origin만 허용하며 배포 도메인은 CORS_ALLOW_ORIGINS로 명시한다.
# X-API-Key/Authorization 헤더 기반 인증만 쓰고 쿠키는 안 쓰므로 allow_credentials=False.
_cors_origins = [
    origin.strip()
    for origin in os.environ.get(
        "CORS_ALLOW_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key", "X-Session-Token"],
)

app.include_router(citizen.router)
app.include_router(admin.router)
app.include_router(internal.router)
app.include_router(feedback_citizen_router)
app.include_router(feedback_admin_router)
app.include_router(feedback_analysis_router)
app.include_router(policy_demand_citizen_router)
app.include_router(policy_demand_citizen_me_router)
app.include_router(policy_demand_admin_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
