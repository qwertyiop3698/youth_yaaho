"""Layer 2-A - GMM 소프트 클러스터링 학습.

docs/04: "도메인 지수 5종 벡터에 Gaussian Mixture Model 적용." 소프트 할당
(responsibility, γ_ik)으로 한 사람이 여러 위험유형에 걸쳐 있는 현실을 확률로 표현한다.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from sklearn.mixture import GaussianMixture

logger = logging.getLogger(__name__)

DOMAIN_INDEX_COLUMNS = [
    "주거비압박지수",
    "부채상환위험지수",
    "소득변동성지수",
    "소비압박지수",
    "신용취약지수",
]


def prepare_clustering_input(
    df: pd.DataFrame, columns: list[str] = DOMAIN_INDEX_COLUMNS
) -> tuple[np.ndarray, pd.Index]:
    """도메인지수 5종을 GMM 입력 행렬로 변환한다. 결측이 하나라도 있는 행은 제외하고,
    제외 후 남은 행의 원본 인덱스를 함께 반환해 나중에 person 단위로 다시 매핑할 수
    있게 한다."""
    missing_cols = [c for c in columns if c not in df.columns]
    if missing_cols:
        logger.warning("GMM 입력 준비: 도메인지수 컬럼 %s이 없습니다.", missing_cols)
    available = [c for c in columns if c in df.columns]
    if not available:
        return np.empty((0, 0)), df.index[:0]

    subset = df[available].apply(pd.to_numeric, errors="coerce")
    valid_mask = subset.notna().all(axis=1)
    return subset.loc[valid_mask].to_numpy(), df.index[valid_mask]


def train_gmm(
    df: pd.DataFrame,
    k: int,
    covariance_type: str = "full",
    columns: list[str] = DOMAIN_INDEX_COLUMNS,
    random_state: int = 42,
) -> tuple[GaussianMixture, pd.Index]:
    """지정된 K/공분산구조로 GMM을 학습한다. k_selection.select_k()의 best_k를
    그대로 넘겨 쓰는 것을 전제로 한다."""
    X, valid_index = prepare_clustering_input(df, columns)
    if len(X) == 0:
        raise ValueError("GMM 학습 입력이 비어 있습니다(도메인지수 컬럼이 없거나 전부 결측).")
    if k >= len(X):
        raise ValueError(f"K({k})가 유효 표본 수({len(X)}) 이상이라 GMM을 학습할 수 없습니다.")

    model = GaussianMixture(
        n_components=k, covariance_type=covariance_type, random_state=random_state, n_init=5
    )
    model.fit(X)
    return model, valid_index


def predict_membership(
    model: GaussianMixture, df: pd.DataFrame, columns: list[str] = DOMAIN_INDEX_COLUMNS
) -> pd.DataFrame:
    """person별 K개 클러스터 소속 확률(responsibility, γ_ik)을 반환한다(docs/04).

    도메인지수가 결측인 행은 확률을 계산할 수 없으므로 NaN으로 남긴다(임의로 0 등을
    채우지 않음 - Layer0/1의 "원본값 삭제/임의대체 금지" 원칙과 동일하게 적용).
    """
    X, valid_index = prepare_clustering_input(df, columns)
    cluster_columns = [f"cluster_{i}" for i in range(model.n_components)]
    result = pd.DataFrame(np.nan, index=df.index, columns=cluster_columns)
    if len(X) == 0:
        return result
    proba = model.predict_proba(X)
    result.loc[valid_index, cluster_columns] = proba
    return result
