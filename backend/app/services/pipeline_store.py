"""공통 백엔드 - Layer0~3 파이프라인 산출물 로더.

data/processed/의 parquet/json/pkl 파일들을 읽어 API가 재사용할 수 있게 캐싱해서
제공한다. 표본 부족 등으로 특정 산출물이 아직 없으면(Layer2-A/2-B/3이 skip된 경우)
None으로 두고 status()에서 명확히 표시한다 - 없는 파일을 억지로 채우거나 죽지
않는다(Layer0~3 전체에 걸친 방어적 설계 원칙과 동일하게 유지).
"""
from __future__ import annotations

import json
import os
from functools import cached_property
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
import yaml

from pipeline.layer0_data_contract.profiler import load_column_config
from pipeline.layer1_features import feature_engineer as fe

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_PRIMARY_DATA_DIR = _PROJECT_ROOT / "data" / "processed"
_DEMO_DATA_DIR = _PROJECT_ROOT / "data" / "processed_large"


def _resolve_default_data_dir() -> Path:
    configured = os.environ.get("PIPELINE_DATA_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    # 새 clone에는 ignored인 processed/가 없으므로 추적된 합성 데모 산출물로 폴백한다.
    return _PRIMARY_DATA_DIR if _PRIMARY_DATA_DIR.exists() else _DEMO_DATA_DIR


DEFAULT_DATA_DIR = _resolve_default_data_dir()
DEFAULT_POLICY_CATALOG_PATH = (
    Path(__file__).resolve().parents[2] / "pipeline" / "layer3_optimization" / "policy_catalog.yaml"
)


def _read_parquet_if_exists(path: Path) -> pd.DataFrame | None:
    return pd.read_parquet(path) if path.exists() else None


def _read_json_if_exists(path: Path) -> dict[str, Any] | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def _load_pickle_if_exists(path: Path) -> Any | None:
    return joblib.load(path) if path.exists() else None


class PipelineStore:
    """data_dir의 Layer0~3 산출물을 lazy하게 로드/캐싱하는 저장소.

    FastAPI 요청마다 새로 만들지 말고 get_pipeline_store()로 얻은 싱글턴을
    재사용해야 한다(안 그러면 매 요청마다 parquet/pkl을 다시 읽는다).
    """

    def __init__(
        self, data_dir: Path = DEFAULT_DATA_DIR, policy_catalog_path: Path = DEFAULT_POLICY_CATALOG_PATH
    ) -> None:
        self.data_dir = Path(data_dir)
        self.policy_catalog_path = Path(policy_catalog_path)

    @cached_property
    def layer0_config(self) -> dict[str, Any]:
        return load_column_config()

    @cached_property
    def policy_catalog(self) -> dict[str, Any]:
        with open(self.policy_catalog_path, encoding="utf-8") as f:
            return yaml.safe_load(f)

    @cached_property
    def featured_dataset(self) -> pd.DataFrame | None:
        return _read_parquet_if_exists(self.data_dir / "featured_dataset.parquet")

    @cached_property
    def domain_index_population_stats(self) -> dict[str, tuple[float, float]] | None:
        """도메인지수 구성변수들의 population 평균/표준편차(학습 데이터셋 기준).

        진단 API가 시민의 1행짜리 입력을 z-score로 표준화할 때, 그 1행 자기 자신을
        기준으로 표준화하면 표준편차가 항상 0이 되어 도메인지수가 항상 0으로 나오는
        문제가 있었다 - 대신 이 population 기준값으로 표준화해야 한다
        (backend/app/services/diagnose_service.py 참고)."""
        if self.featured_dataset is None:
            return None
        return fe.compute_domain_index_population_stats(self.featured_dataset)

    @cached_property
    def risk_scores(self) -> pd.DataFrame | None:
        return _read_parquet_if_exists(self.data_dir / "risk_scores.parquet")

    @cached_property
    def cluster_membership_table(self) -> pd.DataFrame | None:
        return _read_parquet_if_exists(self.data_dir / "cluster_membership.parquet")

    @cached_property
    def assignment_results(self) -> pd.DataFrame | None:
        return _read_parquet_if_exists(self.data_dir / "assignment_results.parquet")

    @cached_property
    def budget_sensitivity(self) -> pd.DataFrame | None:
        return _read_parquet_if_exists(self.data_dir / "budget_sensitivity.parquet")

    @cached_property
    def policy_marginal_return(self) -> pd.DataFrame | None:
        return _read_parquet_if_exists(self.data_dir / "policy_marginal_return.parquet")

    @cached_property
    def regret_curve(self) -> pd.DataFrame | None:
        return _read_parquet_if_exists(self.data_dir / "regret_curve.parquet")

    @cached_property
    def regret_segment_summary(self) -> pd.DataFrame | None:
        return _read_parquet_if_exists(self.data_dir / "regret_segment_summary.parquet")

    @cached_property
    def cluster_report(self) -> dict[str, Any] | None:
        return _read_json_if_exists(self.data_dir / "cluster_report.json")

    @cached_property
    def risk_model_report(self) -> dict[str, Any] | None:
        return _read_json_if_exists(self.data_dir / "risk_model_report.json")

    @cached_property
    def optimization_report(self) -> dict[str, Any] | None:
        return _read_json_if_exists(self.data_dir / "optimization_report.json")

    @cached_property
    def profiling_report(self) -> dict[str, Any] | None:
        return _read_json_if_exists(self.data_dir / "profiling_report.json")

    @cached_property
    def cluster_model(self) -> Any | None:
        return _load_pickle_if_exists(self.data_dir / "cluster_model.pkl")

    @cached_property
    def risk_model_bundle(self) -> dict[str, Any] | None:
        return _load_pickle_if_exists(self.data_dir / "risk_model.pkl")

    @property
    def risk_model_feature_columns(self) -> list[str] | None:
        report = self.risk_model_report
        if not report or report.get("training", {}).get("skipped"):
            return None
        return report["training"].get("feature_columns")

    @property
    def cluster_label_map(self) -> dict[str, str]:
        report = self.cluster_report
        if not report or not report.get("model_trained"):
            return {}
        return report.get("suggested_labels", {})

    def status(self) -> dict[str, bool]:
        """어떤 산출물이 준비됐는지 요약 - admin 화면/헬스체크에서 사용."""
        return {
            "featured_dataset": self.featured_dataset is not None,
            "risk_scores": self.risk_scores is not None,
            "cluster_model": self.cluster_model is not None,
            "risk_model_bundle": self.risk_model_bundle is not None,
            "assignment_results": self.assignment_results is not None,
            "optimization_report": self.optimization_report is not None,
        }


_default_store: PipelineStore | None = None


def get_pipeline_store() -> PipelineStore:
    """FastAPI 의존성으로 쓰는 싱글턴 getter."""
    global _default_store
    if _default_store is None:
        _default_store = PipelineStore()
    return _default_store


def reset_pipeline_store() -> None:
    """/internal/pipeline/* 로 배치를 재실행한 뒤 캐시를 비울 때 사용."""
    global _default_store
    _default_store = None
