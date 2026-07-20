"""Layer 2-A - 클러스터 간 위험 궤적 시뮬레이션 (Markov 전이).

KCB 데이터는 단일 시점 스냅샷이라 실제 관측된 유형 전이(A유형 -> B유형, 시간에
따른 변화)가 없다 - Cox 생존모형이 duration을 관측할 수 없어 폐기된 것과 동일한
이유다(docs/04). 따라서 이 모듈이 만드는 전이확률은 실측이 아니라 원칙 기반
근사이며, Thompson Sampling(thompson_sampling.py)과 동일하게 "실제 운영 전
검증용 시뮬레이션"임을 명시적으로 라벨링한다(docs/05 관례를 그대로 따름).

전이확률 구성 방법
------------------
- 두 클러스터 중심(도메인지수 5차원 z-score 공간) 간 유클리드 거리가 가까울수록
  전이 가능성이 높다고 가정한다: affinity(k, k') = exp(-dist(k, k') / temperature)
- risk_bias로 방향성을 준다: 양수면 평균위험이 더 높은 이웃 쪽으로(무개입 - "위험
  심화" 시나리오), 음수면 더 낮은 이웃 쪽으로(정책 개입 - 절대값이 클수록 개입
  효과가 강하다고 가정) 가중치가 쏠린다.
- 자기전이(그대로 머무름)에 최소 하한(min_self_transition)을 둬서 매 스텝마다
  유형이 확 바뀌는 비현실적인 결과를 막는다.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

DEFAULT_TEMPERATURE = 1.0
DEFAULT_MIN_SELF_TRANSITION = 0.5
DEFAULT_N_STEPS = 6
DEFAULT_RISK_BIAS_NO_INTERVENTION = 1.0

SIMULATION_DISCLAIMER = (
    "실제 관측된 전이 데이터가 아니라, 클러스터 중심 간 거리와 위험도 변화 방향으로 "
    "구성한 시뮬레이션입니다. 실제 종단(패널) 데이터가 확보되면 실측 전이확률로 "
    "교체해야 합니다."
)


def compute_cluster_avg_risk(membership_df: pd.DataFrame, risk_scores: pd.Series) -> pd.Series:
    """클러스터별 responsibility(소프트 소속확률)로 가중평균한 위험확률.

    avg_risk[k] = Σ_i(membership[i,k] · risk_i) / Σ_i(membership[i,k])
    """
    cluster_cols = [c for c in membership_df.columns if c.startswith("cluster_")]
    aligned_risk = risk_scores.reindex(membership_df.index)
    weights = membership_df[cluster_cols].fillna(0.0)
    weighted_sum = weights.mul(aligned_risk, axis=0).sum()
    weight_total = weights.sum()
    return (weighted_sum / weight_total.replace(0, np.nan)).rename("avg_risk")


def compute_population_initial_distribution(membership_df: pd.DataFrame) -> pd.Series:
    """인구 전체 기준 초기 클러스터 분포(각 클러스터의 responsibility 합을 정규화)."""
    cluster_cols = [c for c in membership_df.columns if c.startswith("cluster_")]
    totals = membership_df[cluster_cols].fillna(0.0).sum()
    grand_total = totals.sum()
    if grand_total <= 0:
        return pd.Series(0.0, index=cluster_cols)
    return totals / grand_total


def build_transition_matrix(
    cluster_profiles: pd.DataFrame,
    cluster_avg_risk: pd.Series,
    temperature: float = DEFAULT_TEMPERATURE,
    risk_bias: float = 0.0,
    min_self_transition: float = DEFAULT_MIN_SELF_TRANSITION,
) -> pd.DataFrame:
    """K x K 전이확률 행렬을 만든다.

    cluster_profiles: index=클러스터명, columns=도메인지수(compute_cluster_profiles 출력).
    cluster_avg_risk: 클러스터별 평균위험(compute_cluster_avg_risk 출력과 동일 index 기대,
    없는 클러스터는 전체 평균으로 대체).
    """
    clusters = list(cluster_profiles.index)
    k = len(clusters)
    if k == 0:
        return pd.DataFrame()
    if k == 1:
        return pd.DataFrame([[1.0]], index=clusters, columns=clusters)

    centers = cluster_profiles.loc[clusters].to_numpy(dtype=float)
    diff = centers[:, None, :] - centers[None, :, :]
    dist = np.linalg.norm(diff, axis=2)
    affinity = np.exp(-dist / max(temperature, 1e-6))

    risk_series = cluster_avg_risk.reindex(clusters)
    fallback = risk_series.mean() if risk_series.notna().any() else 0.0
    risk = risk_series.fillna(fallback).to_numpy(dtype=float)
    risk_delta = risk[None, :] - risk[:, None]  # risk_delta[i, j] = risk[j] - risk[i]
    bias = np.exp(risk_bias * risk_delta)

    weighted = affinity * bias
    np.fill_diagonal(weighted, 0.0)

    row_sum = weighted.sum(axis=1, keepdims=True)
    off_diag_target = 1.0 - min_self_transition
    normalized = np.divide(
        weighted * off_diag_target, row_sum, out=np.zeros_like(weighted), where=row_sum > 0
    )

    matrix = normalized
    np.fill_diagonal(matrix, min_self_transition)

    # 모든 이웃과의 affinity가 0인 극단적 케이스(row_sum<=0) - 방어적으로 자기전이 100%
    zero_rows = row_sum.flatten() <= 0
    for i in np.where(zero_rows)[0]:
        matrix[i, :] = 0.0
        matrix[i, i] = 1.0

    return pd.DataFrame(matrix, index=clusters, columns=clusters)


def simulate_trajectory(
    initial_distribution: pd.Series,
    transition_matrix: pd.DataFrame,
    cluster_avg_risk: pd.Series,
    n_steps: int = DEFAULT_N_STEPS,
) -> pd.DataFrame:
    """초기 분포에서 시작해 전이행렬을 n_steps번 반복 적용한다. 각 step의 클러스터
    분포와 그 시점의 가중평균 위험(expected_avg_risk)을 반환한다."""
    clusters = list(transition_matrix.index)
    dist = initial_distribution.reindex(clusters).fillna(0.0).to_numpy(dtype=float)
    total = dist.sum()
    if total > 0:
        dist = dist / total

    risk_series = cluster_avg_risk.reindex(clusters)
    fallback = risk_series.mean() if risk_series.notna().any() else 0.0
    risk = risk_series.fillna(fallback).to_numpy(dtype=float)
    transition = transition_matrix.to_numpy(dtype=float)

    rows = []
    current = dist
    for step in range(n_steps + 1):
        row = {"step": step, "expected_avg_risk": float(current @ risk)}
        row.update({cluster: float(current[i]) for i, cluster in enumerate(clusters)})
        rows.append(row)
        if step < n_steps:
            current = current @ transition
    return pd.DataFrame(rows)


def simulate_no_intervention_vs_intervention(
    cluster_profiles: pd.DataFrame,
    cluster_avg_risk: pd.Series,
    initial_distribution: pd.Series,
    intervention_effectiveness: float,
    n_steps: int = DEFAULT_N_STEPS,
    temperature: float = DEFAULT_TEMPERATURE,
    risk_bias_no_intervention: float = DEFAULT_RISK_BIAS_NO_INTERVENTION,
    min_self_transition: float = DEFAULT_MIN_SELF_TRANSITION,
) -> dict[str, Any]:
    """무개입(위험 심화 방향으로 편향) vs 개입(policy_catalog 평균 effectiveness_prior
    만큼 위험 감소 방향으로 편향) 두 시나리오를 나란히 시뮬레이션한다."""
    no_intervention_matrix = build_transition_matrix(
        cluster_profiles,
        cluster_avg_risk,
        temperature=temperature,
        risk_bias=risk_bias_no_intervention,
        min_self_transition=min_self_transition,
    )
    intervention_matrix = build_transition_matrix(
        cluster_profiles,
        cluster_avg_risk,
        temperature=temperature,
        risk_bias=-intervention_effectiveness * risk_bias_no_intervention,
        min_self_transition=min_self_transition,
    )

    no_intervention_traj = simulate_trajectory(initial_distribution, no_intervention_matrix, cluster_avg_risk, n_steps)
    intervention_traj = simulate_trajectory(initial_distribution, intervention_matrix, cluster_avg_risk, n_steps)

    return {
        "is_simulation": True,
        "simulation_disclaimer": SIMULATION_DISCLAIMER,
        "n_steps": n_steps,
        "intervention_effectiveness_used": intervention_effectiveness,
        "no_intervention": no_intervention_traj.to_dict(orient="records"),
        "intervention": intervention_traj.to_dict(orient="records"),
    }
