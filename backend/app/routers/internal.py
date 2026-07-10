"""docs/07 /api/v1/internal/* 라우터.

doc01 명시: "internal은 외부 노출 금지(내부망 또는 API 키 인증)". 고정 API 키
(환경변수 INTERNAL_API_KEY, 요청 헤더 X-API-Key) 기반 최소 인증이 적용돼 있다 -
app/auth.py 참고. Layer0~3 배치를 API로 트리거하는 용도로 쓴다.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from pipeline.layer0_data_contract import run as layer0_run
from pipeline.layer1_features import run as layer1_run
from pipeline.layer2a_clustering import run as layer2a_run
from pipeline.layer2b_risk_model import run as layer2b_run
from pipeline.layer3_optimization import run as layer3_run

from ..auth import require_internal_api_key
from ..services.pipeline_store import reset_pipeline_store

router = APIRouter(prefix="/api/v1/internal", tags=["internal"], dependencies=[Depends(require_internal_api_key)])


@router.post("/pipeline/run-diagnostic")
def run_diagnostic() -> dict[str, Any]:
    """Layer 0~2 배치 실행 (docs/07)."""
    layer0_report = layer0_run.run(layer0_run.DEFAULT_INPUT, layer0_run.DEFAULT_OUTPUT_DIR)
    layer1_report = layer1_run.run(layer1_run.DEFAULT_INPUT, layer1_run.DEFAULT_OUTPUT_DIR)
    layer2a_report = layer2a_run.run(layer2a_run.DEFAULT_INPUT, layer2a_run.DEFAULT_OUTPUT_DIR)
    layer2b_report = layer2b_run.run(layer2b_run.DEFAULT_INPUT, layer2b_run.DEFAULT_OUTPUT_DIR)

    reset_pipeline_store()
    return {
        "layer0_row_count": layer0_report.get("row_count"),
        "layer1_row_count": layer1_report.get("row_count"),
        "layer2a_model_trained": layer2a_report.get("model_trained"),
        "layer2b_training": layer2b_report.get("training", layer2b_report),
    }


@router.post("/pipeline/run-optimization")
def run_optimization() -> dict[str, Any]:
    """Layer 3 배치 실행 (docs/07)."""
    try:
        report = layer3_run.run()
    except FileNotFoundError as exc:
        return {"skipped": True, "reason": str(exc)}

    reset_pipeline_store()
    return report
