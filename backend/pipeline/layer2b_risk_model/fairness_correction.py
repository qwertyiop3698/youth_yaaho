"""Layer 2-B - 공정성 보정 (Equalized-Odds Threshold Correction).

docs/04: "성별/연령대별 서브그룹별 AUC/PR-AUC 차이 비교"까지는 fairness_audit.py가
한다. 이 모듈은 거기서 한 걸음 더 나아가 실제로 격차를 줄인다.

AUC는 threshold-independent라 그룹별 확률 재보정(recalibration)으로는 AUC 격차가
줄지 않는다 - 그룹별로 단조변환을 적용해도 그룹 내부의 순위(따라서 AUC)는 그대로
보존되기 때문이다. 대신 이 시스템이 실제로 쓰는 단일 임계값 지점 -
admin.py `/policy-gaps`의 `risk_threshold`(기본 0.6, "고위험" 판정 기준) - 에
그룹별(성별) 임계값을 적용하는 후처리로 범위를 좁힌다. Hardt et al.(2016)의
equalized-odds 후처리 아이디어를 "그룹 간 TPR을 맞춘다"는 형태로 근사 구현한다.

fairness_audit.py와 동일한 방어 원칙(MIN_SUBGROUP_SAMPLE 미만 그룹/단일 클래스
그룹은 건드리지 않고 기본임계값 유지)을 그대로 따른다.
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import roc_curve

from .fairness_audit import MIN_SUBGROUP_SAMPLE

logger = logging.getLogger(__name__)


def compute_equalized_odds_thresholds(
    y_true: pd.Series,
    y_proba: pd.Series,
    group: pd.Series,
    baseline_threshold: float = 0.6,
    min_subgroup_sample: int = MIN_SUBGROUP_SAMPLE,
) -> dict[str, Any]:
    """baseline_threshold에서의 전체 TPR을 목표로, 각 그룹이 그 TPR에 가장
    가까워지는 임계값을 그룹별 ROC 곡선에서 찾는다(그룹 간 TPR을 맞춰 equalized
    odds에 근사).
    """
    y_true = y_true.astype(int)
    if y_true.sum() == 0:
        return {"skipped": True, "reason": "양성 사례가 없어 TPR을 계산할 수 없습니다."}

    baseline_pred = (y_proba >= baseline_threshold).astype(int)
    global_tpr = float(((baseline_pred == 1) & (y_true == 1)).sum() / y_true.sum())

    thresholds: dict[str, float] = {}
    details: dict[str, Any] = {}

    for group_value, idx in group.groupby(group).groups.items():
        idx = idx.intersection(y_true.index)
        key = str(group_value)
        n = int(len(idx))

        if n < min_subgroup_sample:
            logger.warning(
                "공정성 보정: 그룹 '%s' 표본 부족(n=%d < %d)으로 기본임계값을 유지합니다.",
                key,
                n,
                min_subgroup_sample,
            )
            thresholds[key] = baseline_threshold
            details[key] = {"skipped": True, "n": n, "reason": "표본 부족", "threshold": baseline_threshold}
            continue

        y_sub = y_true.loc[idx]
        if y_sub.nunique() < 2:
            thresholds[key] = baseline_threshold
            details[key] = {"skipped": True, "n": n, "reason": "단일 클래스", "threshold": baseline_threshold}
            continue

        p_sub = y_proba.loc[idx]
        fpr, tpr, roc_thresholds = roc_curve(y_sub, p_sub)
        # global_tpr에 가장 가까운 지점의 임계값을 선택한다.
        closest_idx = int(np.argmin(np.abs(tpr - global_tpr)))
        # roc_curve의 첫 임계값은 관례적으로 max(score)+1인 sentinel이라 확률
        # 범위(0~1) 밖일 수 있다 - 그대로 못 쓰므로 클립한다.
        chosen_threshold = float(np.clip(roc_thresholds[closest_idx], 0.0, 1.0))

        thresholds[key] = chosen_threshold
        details[key] = {
            "skipped": False,
            "n": n,
            "threshold": chosen_threshold,
            "achieved_tpr": float(tpr[closest_idx]),
        }

    return {
        "skipped": False,
        "baseline_threshold": baseline_threshold,
        "global_tpr": global_tpr,
        "thresholds": thresholds,
        "details": details,
    }


def _tpr_by_group(y_true: pd.Series, y_proba: pd.Series, group: pd.Series, threshold_fn) -> dict[str, float]:
    tprs: dict[str, float] = {}
    for group_value, idx in group.groupby(group).groups.items():
        idx = idx.intersection(y_true.index)
        key = str(group_value)
        y_sub = y_true.loc[idx]
        if y_sub.sum() == 0:
            continue
        p_sub = y_proba.loc[idx]
        pred = (p_sub >= threshold_fn(key)).astype(int)
        tprs[key] = float(((pred == 1) & (y_sub == 1)).sum() / y_sub.sum())
    return tprs


def evaluate_correction(
    y_true: pd.Series,
    y_proba: pd.Series,
    group: pd.Series,
    thresholds: dict[str, float],
    baseline_threshold: float,
) -> dict[str, Any]:
    """보정 전(단일 baseline_threshold) vs 보정 후(그룹별 thresholds)의 그룹 간
    TPR 격차를 비교해 실제로 격차가 줄었는지를 숫자로 보여준다."""
    y_true = y_true.astype(int)
    before = _tpr_by_group(y_true, y_proba, group, lambda _key: baseline_threshold)
    after = _tpr_by_group(y_true, y_proba, group, lambda key: thresholds.get(key, baseline_threshold))

    before_gap = (max(before.values()) - min(before.values())) if len(before) >= 2 else None
    after_gap = (max(after.values()) - min(after.values())) if len(after) >= 2 else None

    return {
        "before_tpr_by_group": before,
        "after_tpr_by_group": after,
        "before_tpr_gap": before_gap,
        "after_tpr_gap": after_gap,
        "improved": bool(before_gap is not None and after_gap is not None and after_gap <= before_gap + 1e-9),
    }
