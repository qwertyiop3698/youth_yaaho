"""Layer 2-B - Spatial Cross Validation.

docs/04: "Spatial CV: 거주지 시군구코드(또는 확보되면 행정동) 기준으로 fold를 나눠
지역 일반화 성능 확인." Layer0의 join_role 메타데이터를 재사용해 행정동 우선, 없으면
시군구코드로 그룹을 나눈다(컬럼명 하드코딩 금지 원칙 유지, docs/02와 동일한 이중화
패턴).
"""
from __future__ import annotations

import logging
from typing import Any, Callable

import pandas as pd
from sklearn.model_selection import GroupKFold

from ..layer0_data_contract import cleaner as layer0_cleaner
from ..layer0_data_contract.profiler import load_column_config as load_layer0_config

logger = logging.getLogger(__name__)

MIN_GROUPS_FOR_SPATIAL_CV = 5
MIN_SAMPLE_FOR_SPATIAL_CV = 30


def resolve_spatial_group_column(
    df: pd.DataFrame, layer0_config: dict[str, Any] | None = None, scope: str = "residence"
) -> str | None:
    """행정동 우선, 없으면 시군구코드. 둘 다 없으면 None(호출부가 방어적으로 처리)."""
    layer0_config = layer0_config or load_layer0_config()
    join_cols = layer0_cleaner.resolve_join_columns(layer0_config)
    dong_col, sigungu_col = join_cols.get(scope, (None, None))
    if dong_col and dong_col in df.columns:
        return dong_col
    if sigungu_col and sigungu_col in df.columns:
        return sigungu_col
    return None


def spatial_cross_validate(
    df: pd.DataFrame,
    X: pd.DataFrame,
    y: pd.Series,
    train_fn: Callable[[pd.DataFrame, pd.Series], Any],
    eval_fn: Callable[[Any, pd.DataFrame, pd.Series], dict[str, Any]],
    n_splits: int = 5,
    layer0_config: dict[str, Any] | None = None,
    min_groups: int = MIN_GROUPS_FOR_SPATIAL_CV,
    min_sample: int = MIN_SAMPLE_FOR_SPATIAL_CV,
) -> dict[str, Any]:
    """지역 그룹 기준 GroupKFold CV. 표본/그룹 수가 부족하면 생략하고 경고를 남긴다
    (sample.csv=5행, 지역그룹도 몇 개뿐이라 대부분 생략될 것 - 실데이터는 정상 동작).
    """
    group_col = resolve_spatial_group_column(df, layer0_config)
    if group_col is None:
        logger.warning("spatial CV: 지역 그룹 컬럼(행정동/시군구코드)이 없어 생략합니다.")
        return {"skipped": True, "reason": "지역 그룹 컬럼 없음", "group_column": None, "folds": []}

    groups = df.loc[X.index, group_col]
    n_groups = int(groups.nunique())

    if len(X) < min_sample or n_groups < min_groups:
        logger.warning(
            "spatial CV: 표본(n=%d) 또는 지역 그룹 수(%d)가 부족해 생략합니다(각각 %d, %d 이상 필요). "
            "실데이터에서는 정상 동작합니다.",
            len(X),
            n_groups,
            min_sample,
            min_groups,
        )
        return {
            "skipped": True,
            "reason": f"표본/그룹 부족(n={len(X)}, groups={n_groups})",
            "group_column": group_col,
            "folds": [],
        }

    n_splits = min(n_splits, n_groups)
    gkf = GroupKFold(n_splits=n_splits)
    fold_results = []
    for fold_idx, (train_idx, test_idx) in enumerate(gkf.split(X, y, groups=groups)):
        y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
        if y_train.nunique() < 2 or y_test.nunique() < 2:
            logger.warning("spatial CV fold %d: 클래스가 1종류뿐이라 건너뜁니다.", fold_idx)
            continue
        model = train_fn(X.iloc[train_idx], y_train)
        metrics = eval_fn(model, X.iloc[test_idx], y_test)
        fold_results.append({"fold": fold_idx, "test_size": int(len(test_idx)), "metrics": metrics})

    return {"skipped": False, "group_column": group_col, "n_splits": n_splits, "folds": fold_results}
