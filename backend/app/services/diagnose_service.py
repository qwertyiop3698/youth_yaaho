"""공통 백엔드 - 근사 진단 서비스 (docs/07 POST /diagnose).

2026-07-09 사용자 확정 설계 (중요 - 반드시 읽을 것)
------------------------------------------------------
앱에서 시민이 입력하는 건 5개 간단 필드(age_group, dong_code, income_band,
housing_type, has_debt)뿐이지만, 실제 학습된 GMM(cluster_model.pkl)과 LightGBM/
로지스틱(risk_model.pkl)은 KCB 46개 컬럼에서 파생된 ~70개 피처가 있어야 돌아간다.

이 간극은 다음과 같이 메운다(근거 없는 별도 근사공식을 새로 만들지 않는다):
    1. 5개 필드로 실제로 알 수 있는 피처(연령대/지역조인키/추정월소득/자가거주여부/
       총대출건수)는 진짜 값으로 채운다.
    2. 나머지 모든 피처는 featured_dataset 기준 population median(수치형)/
       mode(범주형)로 채워 완전한 피처벡터를 만든다.
    3. 이 벡터를 Layer1 feature_engineer.engineer_features()에 그대로 통과시켜
       파생변수+도메인지수를 "실제 코드로" 재계산한다.
    4. 도메인지수는 실제 GMM(cluster_model.pkl)에, 모델피처는 실제 위험모델
       (risk_model.pkl)에 그대로 통과시킨다 - cluster_membership과
       risk_probability 둘 다 같은 모델에서 나온다(계산 경로를 둘로 쪼개지 않음).

근사가 들어가는 지점은 "일부 입력값을 population 평균/최빈값으로 채운다"는 것
뿐이고, 모델 자체는 항상 하나로 일관된다. 응답에는 diagnosis_mode="approximate"
와 안내 문구를 포함해 이게 약식 진단임을 명시한다. 실제 46컬럼 KCB 데이터가
개인별로 연동되면(doc09: "실제 운영 시 본인인증 연동") 이 서비스는 그 실제 행을
그대로 넣기만 하면 되므로 diagnosis_mode="full"로 자연스럽게 전환 가능하다.
"""
from __future__ import annotations

import logging
import re
from typing import Any

import pandas as pd

from pipeline.layer0_data_contract import cleaner as layer0_cleaner
from pipeline.layer1_features import feature_engineer as fe
from pipeline.layer2a_clustering import gmm_trainer
from pipeline.layer2b_risk_model import baseline_models, shap_explainer

from ..schemas import DiagnoseRequest
from .pipeline_store import PipelineStore

logger = logging.getLogger(__name__)

APPROXIMATION_NOTICE = (
    "간이 추정입니다 - 몇 가지 정보로 빠르게 확인한 결과이며, 실제 KCB 데이터 연동 시 "
    "더 정확해집니다."
)

DOMAIN_INDEX_COLUMNS = gmm_trainer.DOMAIN_INDEX_COLUMNS

AGE_COLUMN = "연령대"
INCOME_COLUMN = "추정월소득"
OWNERSHIP_COLUMN = "자가거주여부"
DEBT_COUNT_COLUMN = "총대출건수"


def parse_age_group(age_group: str) -> float | None:
    """"25-29" -> 25.0 (연령대 컬럼은 5세단위 구간의 하한값을 쓴다, docs/03)."""
    match = re.search(r"\d+", age_group)
    return float(match.group()) if match else None


def parse_income_band(income_band: str) -> float | None:
    """"2500-3000" -> 2750.0(구간 중앙값). 숫자가 하나뿐이면 그 값을 그대로 사용."""
    numbers = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", income_band)]
    if not numbers:
        return None
    return sum(numbers) / len(numbers)


def parse_home_ownership(housing_type: str) -> int:
    """"자가"가 포함되면 자가거주(1), 그 외(월세/전세 등)는 무주택(0)으로 근사."""
    return 1 if "자가" in housing_type else 0


def build_population_reference(featured_df: pd.DataFrame, layer0_config: dict[str, Any]) -> dict[str, Any]:
    """각 컬럼의 population 대표값(수치형=median, 범주형=mode)을 계산한다."""
    columns_cfg = layer0_config.get("columns", {})
    reference: dict[str, Any] = {}

    for col in featured_df.columns:
        dtype = columns_cfg.get(col, {}).get("dtype")
        series = featured_df[col]

        if dtype == "categorical":
            mode = series.mode(dropna=True)
            reference[col] = mode.iloc[0] if len(mode) else None
            continue

        numeric = pd.to_numeric(series, errors="coerce")
        if numeric.notna().any():
            reference[col] = float(numeric.median())
        else:
            mode = series.mode(dropna=True)
            reference[col] = mode.iloc[0] if len(mode) else None

    return reference


def build_approximate_input_row(
    payload: DiagnoseRequest, featured_df: pd.DataFrame, layer0_config: dict[str, Any]
) -> pd.DataFrame:
    """5개 간단 필드 + population 근사값으로 완전한 1행 피처벡터를 만든다."""
    reference = build_population_reference(featured_df, layer0_config)
    row = dict(reference)

    if AGE_COLUMN in row:
        parsed_age = parse_age_group(payload.age_group)
        if parsed_age is not None:
            row[AGE_COLUMN] = parsed_age

    join_cols = layer0_cleaner.resolve_join_columns(layer0_config)
    dong_col, sigungu_col = join_cols.get("residence", (None, None))
    region_col = dong_col if dong_col in featured_df.columns else sigungu_col
    if region_col:
        row[region_col] = payload.dong_code

    if INCOME_COLUMN in row:
        parsed_income = parse_income_band(payload.income_band)
        if parsed_income is not None:
            row[INCOME_COLUMN] = parsed_income

    if OWNERSHIP_COLUMN in row:
        row[OWNERSHIP_COLUMN] = parse_home_ownership(payload.housing_type)

    if DEBT_COUNT_COLUMN in featured_df.columns:
        if not payload.has_debt:
            row[DEBT_COUNT_COLUMN] = 0
        else:
            debt_values = pd.to_numeric(featured_df[DEBT_COUNT_COLUMN], errors="coerce")
            positive = debt_values[debt_values > 0]
            row[DEBT_COUNT_COLUMN] = float(positive.median()) if len(positive) else 1.0

    return pd.DataFrame([row])


def _build_risk_model_input(
    engineered_row: pd.DataFrame, feature_columns: list[str], reference: dict[str, Any]
) -> pd.DataFrame:
    """학습 시점 feature_columns 순서/집합에 맞춰 입력 행렬을 재정렬한다.

    feature_columns는 baseline_models.build_feature_matrix()가 만든 것이라
    sanitize_feature_name()을 거친 이름이다(LightGBM이 쉼표 등 JSON 특수문자를
    피처명으로 거부하는 문제 회피, 2026-07-09 발견). engineered_row/reference는
    아직 원본 이름이므로 여기서도 동일하게 sanitize해서 맞춰준다.

    학습 때 있던 컬럼이 이 행에 없으면 population reference 값으로, 그마저 숫자가
    아니면 0으로 채운다(0을 임의로 먼저 쓰지 않고 population 값을 우선한다)."""
    sanitized_row = engineered_row.copy()
    sanitized_row.columns = [baseline_models.sanitize_feature_name(c) for c in sanitized_row.columns]
    sanitized_reference = {baseline_models.sanitize_feature_name(k): v for k, v in reference.items()}

    row = sanitized_row.reindex(columns=feature_columns)
    for col in feature_columns:
        if pd.isna(row.iloc[0][col]):
            fallback = sanitized_reference.get(col)
            row.loc[row.index[0], col] = fallback if isinstance(fallback, (int, float)) else 0.0
    return row.apply(pd.to_numeric, errors="coerce").fillna(0.0)


def diagnose(payload: DiagnoseRequest, store: PipelineStore) -> dict[str, Any]:
    """POST /diagnose 핵심 로직.

    featured_dataset/cluster_model/risk_model 중 아직 없는 것(Layer1~2가 표본
    부족으로 skip된 경우)이 있으면 계산 가능한 부분만 채우고 나머지는 빈 값으로
    반환한다(죽지 않음).
    """
    featured_df = store.featured_dataset
    layer0_config = store.layer0_config

    if featured_df is None or len(featured_df) == 0:
        logger.warning("diagnose: featured_dataset이 없어 도메인지수를 계산할 수 없습니다.")
        return {"domain_indices": {}, "cluster_membership": {}, "risk_probability": None}

    reference = build_population_reference(featured_df, layer0_config)
    input_row = build_approximate_input_row(payload, featured_df, layer0_config)
    engineered_row, _ = fe.engineer_features(
        input_row, layer0_config, domain_index_population_stats=store.domain_index_population_stats
    )

    domain_indices = {
        col: float(engineered_row.iloc[0][col])
        for col in DOMAIN_INDEX_COLUMNS
        if col in engineered_row.columns and pd.notna(engineered_row.iloc[0][col])
    }

    cluster_membership: dict[str, float] = {}
    if store.cluster_model is not None:
        membership_df = gmm_trainer.predict_membership(store.cluster_model, engineered_row)
        row0 = membership_df.iloc[0].dropna()
        label_map = store.cluster_label_map
        cluster_membership = {label_map.get(idx, idx): float(v) for idx, v in row0.items()}

    risk_probability = None
    shap_top3: list[dict[str, Any]] = []
    feature_columns = store.risk_model_feature_columns
    if store.risk_model_bundle is not None and feature_columns:
        X = _build_risk_model_input(engineered_row, feature_columns, reference)
        model = store.risk_model_bundle["model"]
        risk_probability = float(model.predict_proba(X)[:, 1][0])

        shap_model = store.risk_model_bundle.get("shap_model")
        if shap_model is not None:
            try:
                shap_series = shap_explainer.top_k_shap_features(shap_model, X, k=3)
                shap_top3 = list(shap_series.iloc[0])
            except Exception as exc:  # noqa: BLE001 - SHAP 실패해도 진단 자체는 계속 제공
                logger.warning("diagnose: SHAP 계산 실패(%s) - shap_top3 없이 진행합니다.", exc)

    return {
        "domain_indices": domain_indices,
        "cluster_membership": cluster_membership,
        "risk_probability": risk_probability,
        "shap_top3": shap_top3,
    }
