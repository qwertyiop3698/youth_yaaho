"""정책 피드백 Presentation/API Layer."""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.engine import Engine

from ..auth import require_admin_api_key
from ..dependencies import get_engine
from ..services.pipeline_store import PipelineStore, get_pipeline_store
from ..user_auth import get_current_user_id
from .domain import DomainRuleError, FeedbackStage
from .policy_gateway import CatalogPolicyRepository
from .schemas import (
    CreatePolicyUsageRequest,
    FeedbackAggregateResponse,
    PolicyFeedbackListItemResponse,
    FeedbackFormResponse,
    FeedbackSubmissionResponse,
    PolicyUsageResponse,
    RewardResponse,
    SubmitFeedbackRequest,
    UpdatePolicyUsageStatusRequest,
)
from .service import ConflictError, FeedbackApplicationService, NotFoundError


citizen_router = APIRouter(prefix="/api/v1/citizen", tags=["policy-feedback"])
admin_router = APIRouter(
    prefix="/api/v1/admin",
    tags=["policy-feedback-admin"],
    dependencies=[Depends(require_admin_api_key)],
)


def _service(engine: Engine, store: PipelineStore) -> FeedbackApplicationService:
    return FeedbackApplicationService(engine, CatalogPolicyRepository(store))


def _translate_error(exc: Exception) -> HTTPException:
    if isinstance(exc, NotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, ConflictError):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, DomainRuleError):
        return HTTPException(status_code=422, detail=str(exc))
    return HTTPException(status_code=500, detail="정책 피드백 처리 중 오류가 발생했습니다.")


@citizen_router.post("/policy-usages", response_model=PolicyUsageResponse, status_code=status.HTTP_201_CREATED)
def create_policy_usage(
    payload: CreatePolicyUsageRequest,
    user_id: str = Depends(get_current_user_id),
    engine: Engine = Depends(get_engine),
    store: PipelineStore = Depends(get_pipeline_store),
) -> dict:
    try:
        return _service(engine, store).create_usage(user_id=user_id, policy_id=payload.policy_id)
    except (NotFoundError, ConflictError, DomainRuleError) as exc:
        raise _translate_error(exc) from exc


@citizen_router.patch("/policy-usages/{usage_id}/status", response_model=PolicyUsageResponse)
def update_policy_usage_status(
    usage_id: str,
    payload: UpdatePolicyUsageStatusRequest,
    user_id: str = Depends(get_current_user_id),
    engine: Engine = Depends(get_engine),
    store: PipelineStore = Depends(get_pipeline_store),
) -> dict:
    try:
        return _service(engine, store).update_usage_status(
            user_id=user_id, usage_id=usage_id, target=payload.status
        )
    except (NotFoundError, ConflictError, DomainRuleError) as exc:
        raise _translate_error(exc) from exc


@citizen_router.get("/me/policy-usages", response_model=list[PolicyUsageResponse])
def my_policy_usages(
    user_id: str = Depends(get_current_user_id),
    engine: Engine = Depends(get_engine),
    store: PipelineStore = Depends(get_pipeline_store),
) -> list[dict]:
    return _service(engine, store).list_usages(user_id)


@citizen_router.get("/policies/{policy_id}/feedback-form", response_model=FeedbackFormResponse)
def feedback_form(
    policy_id: str,
    stage: FeedbackStage = Query(...),
    _: str = Depends(get_current_user_id),
    engine: Engine = Depends(get_engine),
    store: PipelineStore = Depends(get_pipeline_store),
) -> dict:
    try:
        return _service(engine, store).get_form(policy_id=policy_id, stage=stage)
    except NotFoundError as exc:
        raise _translate_error(exc) from exc


@citizen_router.post(
    "/policy-usages/{usage_id}/feedback",
    response_model=FeedbackSubmissionResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_feedback(
    usage_id: str,
    payload: SubmitFeedbackRequest,
    user_id: str = Depends(get_current_user_id),
    engine: Engine = Depends(get_engine),
    store: PipelineStore = Depends(get_pipeline_store),
) -> dict:
    try:
        return _service(engine, store).submit_feedback(
            user_id=user_id,
            usage_id=usage_id,
            stage=payload.stage,
            answers=[answer.model_dump() for answer in payload.answers],
        )
    except (NotFoundError, ConflictError, DomainRuleError) as exc:
        raise _translate_error(exc) from exc


@citizen_router.get("/me/rewards", response_model=list[RewardResponse])
def my_rewards(
    user_id: str = Depends(get_current_user_id),
    engine: Engine = Depends(get_engine),
    store: PipelineStore = Depends(get_pipeline_store),
) -> list[dict]:
    return _service(engine, store).list_rewards(user_id)


def _minimum_group_size() -> int:
    raw = os.environ.get("FEEDBACK_MIN_AGGREGATE_SIZE", "5")
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError("FEEDBACK_MIN_AGGREGATE_SIZE는 정수여야 합니다.") from exc
    return max(value, 2)


@admin_router.get(
    "/policies/{policy_id}/feedback-summary",
    response_model=FeedbackAggregateResponse,
)
def feedback_summary(
    policy_id: str,
    engine: Engine = Depends(get_engine),
    store: PipelineStore = Depends(get_pipeline_store),
) -> dict:
    return _service(engine, store).aggregate(policy_id, _minimum_group_size())


@admin_router.get(
    "/policy-feedback-summaries",
    response_model=list[PolicyFeedbackListItemResponse],
)
def feedback_summaries(
    engine: Engine = Depends(get_engine),
    store: PipelineStore = Depends(get_pipeline_store),
) -> list[dict]:
    policies = store.policy_catalog.get("policies", {})
    return _service(engine, store).aggregate_list(policies, _minimum_group_size())
