"""미충족 정책 수요 시민·관리자 API 스키마."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from .domain import TriggerReason


class DemandEligibilityResponse(BaseModel):
    eligible: bool
    trigger_reason: TriggerReason
    expected_reward_amount: int
    cooldown_until: datetime | None
    explanation: str


class DemandQuestionResponse(BaseModel):
    code: str
    prompt: str
    options: list[str]
    required: bool
    conditional: bool = False


class DemandFormResponse(BaseModel):
    form_version: str
    notice: str
    exposure_message: str
    expected_reward_amount: int
    cooldown_days: int
    other_text_max_length: int
    questions: list[DemandQuestionResponse]


class SubmitDemandRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=100)
    trigger_reason: TriggerReason
    need_area: str = Field(..., min_length=1, max_length=50)
    duration: str = Field(..., min_length=1, max_length=30)
    amount: str = Field(..., min_length=1, max_length=50)
    barrier: str = Field(..., min_length=1, max_length=50)
    companion_support: str | None = Field(default=None, max_length=50)
    employment_status: str | None = Field(default=None, max_length=30)
    other_text: str | None = Field(default=None, max_length=200)


class DemandSubmissionResponse(BaseModel):
    response_id: str
    submitted_at: datetime
    reward: dict[str, Any]


class MyDemandResponse(BaseModel):
    response_id: str
    session_id: str
    trigger_reason: str
    need_area: str
    duration: str
    amount: str
    barrier: str
    companion_support: str | None
    employment_status: str | None
    other_text: str | None
    form_version: str
    submitted_at: datetime
    reward_amount: int
    reward_status: str


class DemandSummaryResponse(BaseModel):
    respondent_count: int
    minimum_group_size: int
    suppressed: bool
    suppression_reason: str | None
    metrics: dict[str, Any] | None
    comparison_summary: list[str] = Field(default_factory=list)

