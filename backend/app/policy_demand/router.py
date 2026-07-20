"""미충족 정책 수요 시민·관리자 Presentation/API Layer."""
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
from ..user_auth import get_current_user_id
from ..policy_demand_analysis.service import PolicyDemandAnalysisService
from .domain import DemandRuleError, TriggerReason
from .schemas import (
    DemandEligibilityResponse, DemandFormResponse, DemandSubmissionResponse, DemandSummaryResponse,
    MyDemandResponse, SubmitDemandRequest,
)
from .service import DemandConflictError, DemandNotFoundError, PolicyDemandService

citizen_router = APIRouter(prefix="/api/v1/citizen/policy-demand", tags=["policy-demand"])
citizen_me_router = APIRouter(prefix="/api/v1/citizen", tags=["policy-demand"])
admin_router = APIRouter(prefix="/api/v1/admin", tags=["policy-demand-admin"], dependencies=[Depends(require_admin_api_key)])


def _service(engine: Engine, store: PipelineStore) -> PolicyDemandService:
    return PolicyDemandService(engine, store)


def _minimum() -> int:
    return max(int(os.environ.get("FEEDBACK_MIN_AGGREGATE_SIZE", "5")), 2)


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, DemandNotFoundError): return HTTPException(404, str(exc))
    if isinstance(exc, DemandConflictError): return HTTPException(409, {"message": str(exc), "cooldown_until": exc.cooldown_until.isoformat() if exc.cooldown_until else None})
    if isinstance(exc, DemandRuleError): return HTTPException(422, str(exc))
    return HTTPException(500, "정책 수요 처리 중 오류가 발생했습니다.")


@citizen_router.get("/eligibility", response_model=DemandEligibilityResponse)
def eligibility(session_id: str, trigger_reason: TriggerReason, need_area: str | None = None,
                user_id: str = Depends(get_current_user_id), engine: Engine = Depends(get_engine), store: PipelineStore = Depends(get_pipeline_store)):
    try: return _service(engine, store).eligibility(user_id=user_id, session_id=session_id, reason=trigger_reason, need_area=need_area)
    except (DemandNotFoundError, DemandRuleError) as exc: raise _error(exc) from exc


@citizen_router.get("/form", response_model=DemandFormResponse)
def form(_: str = Depends(get_current_user_id), engine: Engine = Depends(get_engine), store: PipelineStore = Depends(get_pipeline_store)):
    return _service(engine, store).form()


@citizen_router.post("/responses", response_model=DemandSubmissionResponse, status_code=201)
def submit(payload: SubmitDemandRequest, user_id: str = Depends(get_current_user_id), engine: Engine = Depends(get_engine), store: PipelineStore = Depends(get_pipeline_store)):
    try: return _service(engine, store).submit(user_id=user_id, payload=payload.model_dump())
    except (DemandNotFoundError, DemandConflictError, DemandRuleError) as exc: raise _error(exc) from exc


@citizen_router.get("/responses", response_model=list[MyDemandResponse])
def my_responses(user_id: str = Depends(get_current_user_id), engine: Engine = Depends(get_engine), store: PipelineStore = Depends(get_pipeline_store)):
    return _service(engine, store).repository.list_for_user(user_id)


@citizen_me_router.get("/me/policy-demand-responses", response_model=list[MyDemandResponse])
def my_responses_alias(user_id: str = Depends(get_current_user_id), engine: Engine = Depends(get_engine), store: PipelineStore = Depends(get_pipeline_store)):
    return _service(engine, store).repository.list_for_user(user_id)


@admin_router.get("/policy-demand-summary", response_model=DemandSummaryResponse)
def summary(engine: Engine = Depends(get_engine), store: PipelineStore = Depends(get_pipeline_store)):
    return PolicyDemandAnalysisService(engine, store.policy_catalog.get("policies", {})).summary(_minimum())


@admin_router.get("/policy-demand-priorities")
def priorities(engine: Engine = Depends(get_engine), store: PipelineStore = Depends(get_pipeline_store)):
    return PolicyDemandAnalysisService(engine, store.policy_catalog.get("policies", {})).priorities(_minimum())


@admin_router.get("/policy-demand/export")
def export(format: str = Query("csv", pattern="^(csv|json)$"), engine: Engine = Depends(get_engine), store: PipelineStore = Depends(get_pipeline_store)):
    rows = PolicyDemandAnalysisService(engine, store.policy_catalog.get("policies", {})).priorities(_minimum())
    safe_rows = [{k: v for k, v in row.items() if k not in {"components"}} | {"components": row.get("components")} for row in rows]
    if format == "json":
        return Response(json.dumps(safe_rows, ensure_ascii=False, default=str, indent=2), media_type="application/json; charset=utf-8", headers={"Content-Disposition": 'attachment; filename="policy-demand.json"'})
    output = io.StringIO(newline="")
    fields = ["need_area", "respondent_count", "publicly_available", "score", "confidence", "top_district", "top_employment_status", "top_trigger_reason", "primary_recommendation", "secondary_recommendations"]
    writer = csv.DictWriter(output, fieldnames=fields); writer.writeheader()
    for row in safe_rows:
        writer.writerow({key: "|".join(map(str, row[key])) if key == "secondary_recommendations" else row.get(key) for key in fields})
    return Response("\ufeff" + output.getvalue(), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": 'attachment; filename="policy-demand.csv"'})
