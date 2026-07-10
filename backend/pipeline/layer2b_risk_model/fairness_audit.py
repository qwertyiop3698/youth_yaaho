"""Layer 2-B - 공정성 감사 (Fairness Audit).

docs/04: "성별/연령대별 서브그룹별 C-index, calibration 차이 비교. 특정 그룹의
시스템적 과대/과소 위험 판정 여부 확인 후 리포트화."

2026-07-08 사용자 결정으로 duration이 없어 C-index를 쓸 수 없으므로, 이진분류
평가지표(AUC-ROC, PR-AUC)로 서브그룹 비교를 수행한다(baseline_models.py와 동일한
지표 체계 유지).
"""
from __future__ import annotations

import logging
from typing import Any

import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

logger = logging.getLogger(__name__)

MIN_SUBGROUP_SAMPLE = 20


def audit_by_subgroup(
    model: Any,
    X: pd.DataFrame,
    y: pd.Series,
    subgroup: pd.Series,
    min_subgroup_sample: int = MIN_SUBGROUP_SAMPLE,
) -> dict[str, Any]:
    """subgroup(예: 성별, 연령대)별 AUC-ROC/PR-AUC를 비교해 특정 그룹의 과대/과소
    위험판정 여부를 확인한다. 표본이 부족한 그룹은 생략하고 경고를 남긴다(sample.csv
    처럼 그룹당 1~2명뿐이면 대부분 생략됨 - 실데이터는 정상 동작).
    """
    proba = pd.Series(model.predict_proba(X)[:, 1], index=X.index)
    results: dict[str, Any] = {}

    for group_value, idx in subgroup.groupby(subgroup).groups.items():
        idx = idx.intersection(X.index)
        n = int(len(idx))
        key = str(group_value)

        if n < min_subgroup_sample:
            logger.warning(
                "공정성 감사: 그룹 '%s' 표본 부족(n=%d < %d)으로 생략합니다.", key, n, min_subgroup_sample
            )
            results[key] = {"skipped": True, "n": n, "reason": "표본 부족"}
            continue

        y_sub = y.loc[idx]
        if y_sub.nunique() < 2:
            results[key] = {"skipped": True, "n": n, "reason": "단일 클래스"}
            continue

        proba_sub = proba.loc[idx]
        results[key] = {
            "skipped": False,
            "n": n,
            "auc_roc": float(roc_auc_score(y_sub, proba_sub)),
            "pr_auc": float(average_precision_score(y_sub, proba_sub)),
        }

    return results
