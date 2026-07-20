"""정책 개선 우선순위 관리자 API."""
from __future__ import annotations

import csv
import io
import json
import os

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.engine import Engine

from ..auth import require_admin_api_key
from ..dependencies import get_engine
from ..services.pipeline_store import PipelineStore, get_pipeline_store
from .schemas import PolicyFeedbackAnalysisResponse
from .service import AnalysisNotFoundError, PolicyFeedbackAnalysisService

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["policy-feedback-analysis"],
    dependencies=[Depends(require_admin_api_key)],
)


def _minimum_group_size() -> int:
    try:
        return max(int(os.environ.get("FEEDBACK_MIN_AGGREGATE_SIZE", "5")), 2)
    except ValueError as exc:
        raise RuntimeError("FEEDBACK_MIN_AGGREGATE_SIZE는 정수여야 합니다.") from exc


def _service(engine: Engine, store: PipelineStore) -> PolicyFeedbackAnalysisService:
    return PolicyFeedbackAnalysisService(engine, store.policy_catalog.get("policies", {}))


def _as_dict(item) -> dict:
    return item.to_dict()


@router.get("/policy-feedback-analysis", response_model=list[PolicyFeedbackAnalysisResponse])
def policy_feedback_analysis(
    engine: Engine = Depends(get_engine), store: PipelineStore = Depends(get_pipeline_store)
) -> list[dict]:
    return [_as_dict(item) for item in _service(engine, store).analyze_all(_minimum_group_size())]


@router.get("/policies/{policy_id}/feedback-analysis", response_model=PolicyFeedbackAnalysisResponse)
def policy_feedback_analysis_detail(
    policy_id: str,
    engine: Engine = Depends(get_engine),
    store: PipelineStore = Depends(get_pipeline_store),
) -> dict:
    try:
        return _as_dict(_service(engine, store).analyze(policy_id, _minimum_group_size()))
    except AnalysisNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/policy-feedback-priorities", response_model=list[PolicyFeedbackAnalysisResponse])
def policy_feedback_priorities(
    engine: Engine = Depends(get_engine), store: PipelineStore = Depends(get_pipeline_store)
) -> list[dict]:
    return [_as_dict(item) for item in _service(engine, store).priorities(_minimum_group_size())]


@router.get("/policy-feedback-analysis/export")
def export_policy_feedback_analysis(
    format: str = Query("csv", pattern="^(csv|json)$"),
    engine: Engine = Depends(get_engine),
    store: PipelineStore = Depends(get_pipeline_store),
) -> Response:
    rows = [_as_dict(item) for item in _service(engine, store).priorities(_minimum_group_size())]
    if format == "json":
        payload = json.dumps(rows, ensure_ascii=False, default=str, indent=2)
        return Response(
            content=payload,
            media_type="application/json; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="policy-feedback-analysis.json"'},
        )
    output = io.StringIO(newline="")
    fieldnames = [
        "policy_id", "policy_name", "category", "respondent_count", "publicly_available",
        "effectiveness", "accessibility", "support_adequacy", "followup_need",
        "improvement_urgency", "confidence", "primary_bottleneck", "top_followup_need",
        "primary_recommendation", "secondary_recommendations",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow({
            "policy_id": row["policy_id"], "policy_name": row["policy_name"],
            "category": row["category"], "respondent_count": row["respondent_count"],
            "publicly_available": row["publicly_available"], **row["scores"],
            "confidence": row["confidence"], "primary_bottleneck": row["primary_bottleneck"],
            "top_followup_need": row["top_followup_need"],
            "primary_recommendation": row["primary_recommendation"],
            "secondary_recommendations": "|".join(str(value) for value in row["secondary_recommendations"]),
        })
    return Response(
        content="\ufeff" + output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="policy-feedback-analysis.csv"'},
    )

