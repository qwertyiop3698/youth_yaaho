"""공통 백엔드 - Pydantic 스키마 (docs/07_api_spec.md).

2026-07-09 사용자 확정 설계: POST /diagnose는 5개 간단 필드만 받지만, 실제 GMM/
LightGBM 모델은 ~70개 피처가 필요하다. 이 간극은 diagnose_service.py가 "아는 값은
실제로 채우고 나머지는 population median/mode로 채운 뒤 같은 모델에 통과"시켜
메운다 - 그 결과가 근사치라는 걸 `diagnosis_mode`/`approximation_notice` 필드로
응답에 명시한다.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field


class SignupRequest(BaseModel):
    email: str = Field(..., examples=["youth@example.com"])
    password: str = Field(..., min_length=8, examples=["password1234"])
    birthdate: date = Field(..., examples=["2000-01-01"])
    dong_code: str | None = Field(default=None, examples=["26440"])


class SignupResponse(BaseModel):
    user_id: str
    email: str
    is_age_verified: bool  # 항상 False(자기기재) - 실제 본인인증 연동 전까지


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class DiagnoseRequest(BaseModel):
    age_group: str = Field(..., examples=["25-29"])
    dong_code: str = Field(..., examples=["26440"])
    income_band: str = Field(..., examples=["2500-3000"])
    housing_type: str = Field(..., examples=["월세"])
    has_debt: bool = False


class DiagnoseResponse(BaseModel):
    session_id: str
    domain_indices: dict[str, float]
    cluster_membership: dict[str, float]
    risk_probability: float | None = None
    diagnosis_mode: str  # "approximate" | "full" (실제 46컬럼 KCB 데이터 확보 시)
    approximation_notice: str


class RecommendationItem(BaseModel):
    policy: str
    priority: int
    expected_effect: float
    eligible: bool
    eligibility_confidence: str


class RecommendationsResponse(BaseModel):
    recommendations: list[RecommendationItem]


class ExplanationResponse(BaseModel):
    session_id: str
    explanation: str
    is_llm_generated: bool  # False: 지금은 SHAP 기반 템플릿(Layer4 붙기 전)


class HistoryEntry(BaseModel):
    created_at: str
    diagnosis_result: dict[str, Any]


class HistoryResponse(BaseModel):
    session_id: str
    history: list[HistoryEntry]
    note: str  # session_id 기준 단일 진단만 지원한다는 한계 명시(아래 참고)


class SimulateBudgetRequest(BaseModel):
    policy_budgets: dict[str, float]


class SimulateBudgetResponse(BaseModel):
    coverage_rate: float | None
    coverage_rate_verified_only: float | None
    by_cluster: dict[str, Any] | None = None
    marginal_gain_per_10pct_budget: float | None = None
    skipped: bool = False
    reason: str | None = None
