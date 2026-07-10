"""공통 백엔드 - FastAPI 앱 조립 (docs/07_api_spec.md).

실행: `uvicorn app.main:app --reload` (backend/ 디렉토리에서).
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import config  # noqa: F401 - .env를 다른 모든 import보다 먼저 로드(JWT_SECRET_KEY 등)
from .dependencies import get_engine
from .routers import admin, citizen, internal


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_engine()  # DB 테이블 생성 보장
    yield


app = FastAPI(title="Y-SAFE / 청년야호 공통 백엔드", version="0.1.0", lifespan=lifespan)

# 웹 대시보드(React, 별도 origin)에서 브라우저로 직접 호출하기 위해 필요.
# 해커톤 데모 단계라 전체 허용 - 운영 전환 시 프론트엔드 도메인으로 제한할 것.
# X-API-Key/Authorization 헤더 기반 인증만 쓰고 쿠키는 안 쓰므로 allow_credentials=False.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(citizen.router)
app.include_router(admin.router)
app.include_router(internal.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
