"""정책 피드백 Presentation/API 스키마."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from .domain import FeedbackStage, UsageStatus


class CreatePolicyUsageRequest(BaseModel):
    policy_id: str = Field(..., min_length=1, max_length=200)


class UpdatePolicyUsageStatusRequest(BaseModel):
    status: UsageStatus


class UsageStatusHistoryResponse(BaseModel):
    status: UsageStatus
    changed_at: datetime


class UsageRewardSummaryResponse(BaseModel):
    pending_amount: int = 0
    mock_paid_amount: int = 0


class PolicyUsageResponse(BaseModel):
    usage_id: str
    policy_id: str
    policy_name: str
    policy_source: str
    current_status: UsageStatus
    created_at: datetime
    updated_at: datetime
    status_history: list[UsageStatusHistoryResponse] = Field(default_factory=list)
    feedback_completed_stages: list[FeedbackStage] = Field(default_factory=list)
    available_feedback_stages: list[FeedbackStage] = Field(default_factory=list)
    next_allowed_statuses: list[UsageStatus] = Field(default_factory=list)
    expected_reward_amount: int | None = None
    reward_summary: UsageRewardSummaryResponse = Field(default_factory=UsageRewardSummaryResponse)


class FeedbackQuestionResponse(BaseModel):
    question_code: str
    prompt: str
    options: list[str]
    required: bool
    allows_other_text: bool


class FeedbackFormResponse(BaseModel):
    policy_id: str
    stage: FeedbackStage
    form_version: str
    notice: str
    other_text_max_length: int
    expected_reward_amount: int
    questions: list[FeedbackQuestionResponse]


class FeedbackAnswerRequest(BaseModel):
    question_code: str = Field(..., min_length=1, max_length=100)
    choice: str = Field(..., min_length=1, max_length=100)
    other_text: str | None = Field(default=None, max_length=200)


class SubmitFeedbackRequest(BaseModel):
    stage: FeedbackStage
    answers: list[FeedbackAnswerRequest] = Field(..., min_length=1, max_length=6)


class FeedbackSubmissionResponse(BaseModel):
    feedback: dict[str, Any]
    reward: dict[str, Any]


class RewardResponse(BaseModel):
    reward_id: str
    policy_id: str
    stage: FeedbackStage
    amount: int
    status: str
    created_at: datetime
    updated_at: datetime


class FeedbackAggregateResponse(BaseModel):
    policy_id: str
    respondent_count: int
    minimum_group_size: int
    suppressed: bool
    suppression_reason: str | None
    metrics: dict[str, Any] | None
    usage_count: int = 0
    feedback_submission_count: int = 0
    overall_response_rate: float | None = None


class PolicyFeedbackListItemResponse(FeedbackAggregateResponse):
    policy_name: str
