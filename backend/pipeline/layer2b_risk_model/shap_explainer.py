"""Layer 2-B - SHAP 기반 개인별 위험요인 설명.

docs/04: "SHAP(TreeExplainer, LightGBM 베이스라인 기준)... 개인별 top-3 위험 요인
추출 -> Layer4 입력." docs/06 explanation_agent의 입력 스키마(shap_top3: [{feature,
impact}, ...])와 동일한 형태로 반환한다.
"""
from __future__ import annotations

import logging

import pandas as pd
import shap

logger = logging.getLogger(__name__)


def compute_shap_values(model, X: pd.DataFrame):
    """LightGBM 모델 전용 TreeExplainer. Cox가 아직 스텁이라 지금은 LightGBM
    분류기(baseline_models.train_lightgbm 산출물)만 지원한다."""
    explainer = shap.TreeExplainer(model)
    return explainer.shap_values(X)


def top_k_shap_features(model, X: pd.DataFrame, k: int = 3) -> pd.Series:
    """행별 top-k SHAP 요인을 [{"feature":.., "impact":..}, ...] 형태로 반환한다
    (docs/06 shap_top3 입력 스키마와 동일)."""
    if len(X) == 0:
        return pd.Series([], dtype=object)

    shap_values = compute_shap_values(model, X)
    # 이진분류 LightGBM의 shap_values는 (n_samples, n_features) 배열 또는
    # [class0, class1] 리스트로 나올 수 있다 - positive class(1) 기준을 사용한다.
    if isinstance(shap_values, list):
        shap_values = shap_values[1]

    records = []
    for i in range(len(X)):
        contributions = list(zip(X.columns, shap_values[i]))
        contributions.sort(key=lambda kv: abs(kv[1]), reverse=True)
        top = [{"feature": f, "impact": float(v)} for f, v in contributions[:k]]
        records.append(top)

    return pd.Series(records, index=X.index, name="shap_top3")
