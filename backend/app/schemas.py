"""공통 백엔드 - Pydantic 스키마 (docs/07_api_spec.md).

2026-07-09 사용자 확정 설계: POST /diagnose는 5개 간단 필드만 받지만, 실제 GMM/
LightGBM 모델은 ~70개 피처가 필요하다. 이 간극은 diagnose_service.py가 "아는 값은
실제로 채우고 나머지는 population median/mode로 채운 뒤 같은 모델에 통과"시켜
메운다 - 그 결과가 근사치라는 걸 `diagnosis_mode`/`approximation_notice` 필드로
응답에 명시한다.
"""
from __future__ import annotations

from datetime import date
import math
import re
from typing import Any

from pydantic import BaseModel, Field, field_validator


class SignupRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=254, examples=["youth@example.com"])
    password: str = Field(..., min_length=8, max_length=128, examples=["password1234"])
    birthdate: date = Field(..., examples=["2000-01-01"])
    dong_code: str | None = Field(default=None, pattern=r"^\d{5,10}$", examples=["26440"])

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", normalized):
            raise ValueError("올바른 이메일 형식이 아닙니다.")
        return normalized

    @field_validator("password")
    @classmethod
    def validate_bcrypt_password_length(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("비밀번호는 UTF-8 기준 72바이트 이하여야 합니다.")
        return value


class SignupResponse(BaseModel):
    user_id: str
    email: str
    is_age_verified: bool  # 항상 False(자기기재) - 실제 본인인증 연동 전까지


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=254)
    password: str = Field(..., min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("password")
    @classmethod
    def validate_bcrypt_password_length(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("비밀번호는 UTF-8 기준 72바이트 이하여야 합니다.")
        return value


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1, max_length=4096)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class DiagnoseRequest(BaseModel):
    age_group: str = Field(..., pattern=r"^(19-24|25-29|30-34|35-39)$", examples=["25-29"])
    dong_code: str = Field(..., pattern=r"^26\d{3}$", examples=["26440"])
    income_band: str = Field(..., pattern=r"^\d{1,5}-\d{1,5}$", examples=["2500-3000"])
    housing_type: str = Field(..., pattern=r"^(자가|전세|월세|기타)$", examples=["월세"])
    has_debt: bool = False

    @field_validator("income_band")
    @classmethod
    def validate_income_band(cls, value: str) -> str:
        lower, upper = (int(part) for part in value.split("-", 1))
        if lower > upper:
            raise ValueError("소득 구간의 최솟값은 최댓값보다 클 수 없습니다.")
        return value


class DiagnoseResponse(BaseModel):
    session_id: str
    session_access_token: str | None = None
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
    url: str | None = None  # 온통청년 Open API 실시간 조회, 실패/미설정 시 None


class OtherPolicyItem(BaseModel):
    """policy_catalog.yaml의 6개 정밀매칭 정책 밖의 정책. 온통청년 API에서
    사용자 거주지역(전국/부산시/구 단위)으로 검색한 결과라 expected_effect
    같은 Δrisk 순위 정보는 없다(docs/05 effectiveness_prior 미보유)."""

    policy: str
    category: str | None = None
    agency: str | None = None
    description: str | None = None
    url: str | None = None
    apply_period: str | None = None


class RecommendationsResponse(BaseModel):
    recommendations: list[RecommendationItem]
    other_policies: list[OtherPolicyItem] = []


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

    @field_validator("policy_budgets")
    @classmethod
    def validate_policy_budgets(cls, value: dict[str, float]) -> dict[str, float]:
        for policy_name, budget in value.items():
            if not policy_name.strip():
                raise ValueError("정책명은 비어 있을 수 없습니다.")
            if not math.isfinite(budget) or budget < 0 or budget > 10_000_000_000_000:
                raise ValueError("정책 예산은 0 이상 10조 원 이하의 유한한 값이어야 합니다.")
        return value


class SimulateBudgetResponse(BaseModel):
    coverage_rate: float | None
    coverage_rate_verified_only: float | None
    by_cluster: dict[str, Any] | None = None
    marginal_gain_per_10pct_budget: float | None = None
    skipped: bool = False
    reason: str | None = None
