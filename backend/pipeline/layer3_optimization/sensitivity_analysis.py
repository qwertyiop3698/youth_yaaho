"""Layer 3 - 예산 민감도 분석 (docs/05 5-1).

"예산을 10% 늘리면 커버율이 몇 %p 오르는가"를 확인하기 위해 예산 배율을
0.5~1.5(±50%) 범위로 바꿔가며 LP를 재실행하고 커버리지율 변화를 계산한다.

2026-07-09 사용자 요청: 커버리지율을 "전체"와 "verified 조건만 기준"으로 나눠서
같이 리포트한다 - eligibility_ip 중 상당수가 confidence=assumed_unresolved_codebook
(코드북 미확정으로 자격 있음 간주)이기 때문에, 전체 커버리지율은 낙관적으로 잡힐 수
있다. verified-only 커버리지율은 "코드북이 확정되기 전까지 확실하게 보장할 수 있는
하한선"을 숫자로 보여주기 위한 것이다(발표에서 "코드북 확정 전 잠정치"임을 명시할 때
사용).
"""
from __future__ import annotations

import copy
from typing import Any

import pandas as pd

from . import lp_allocator

DEFAULT_BUDGET_MULTIPLIERS = (0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5)


def compute_coverage_rate(assignment_df: pd.DataFrame, total_persons: int) -> dict[str, float | None]:
    """전체 커버리지율과 verified 조건만 기준으로 한 커버리지율을 함께 계산한다."""
    if total_persons == 0:
        return {"overall": None, "verified_only": None}

    overall_covered = assignment_df["person_id"].nunique() if len(assignment_df) else 0
    overall_rate = overall_covered / total_persons

    if len(assignment_df):
        verified_assignments = assignment_df[assignment_df["eligibility_confidence"] == "verified"]
        verified_covered = verified_assignments["person_id"].nunique()
    else:
        verified_covered = 0
    verified_rate = verified_covered / total_persons

    return {"overall": overall_rate, "verified_only": verified_rate}


def _scale_budget(policy_catalog: dict[str, Any], multiplier: float) -> dict[str, Any]:
    scaled = copy.deepcopy(policy_catalog)
    for policy_cfg in scaled["policies"].values():
        policy_cfg["budget_cap"] = policy_cfg["budget_cap"] * multiplier
    return scaled


def run_budget_sensitivity(
    df: pd.DataFrame,
    policy_catalog: dict[str, Any],
    multipliers: tuple[float, ...] = DEFAULT_BUDGET_MULTIPLIERS,
    risk_col: str = "risk_probability",
    max_policy_per_person: int | None = None,
) -> pd.DataFrame:
    """예산 배율별 LP를 재실행해 커버리지율(전체/verified-only) 변화를 계산한다."""
    total_persons = int(df[risk_col].notna().sum()) if risk_col in df.columns else 0

    rows = []
    for multiplier in multipliers:
        scaled_catalog = _scale_budget(policy_catalog, multiplier)
        assignment_df, solve_report = lp_allocator.build_and_solve_lp(
            df, scaled_catalog, risk_col=risk_col, max_policy_per_person=max_policy_per_person
        )
        coverage = compute_coverage_rate(assignment_df, total_persons)
        rows.append(
            {
                "budget_multiplier": multiplier,
                "coverage_overall": coverage["overall"],
                "coverage_verified_only": coverage["verified_only"],
                "objective_value": solve_report.get("objective_value"),
                "n_assignments": solve_report.get("n_assignments"),
                "skipped": solve_report.get("skipped", False),
            }
        )

    return pd.DataFrame(rows)


def marginal_gain_per_10pct_budget(sensitivity_df: pd.DataFrame, coverage_col: str = "coverage_overall") -> float | None:
    """docs/07 API 예시의 'marginal_gain_per_10pct_budget'과 동일한 개념 - 예산을
    10%p 늘릴 때 커버리지율이 평균적으로 몇 %p 오르는지."""
    valid = sensitivity_df.dropna(subset=[coverage_col]).sort_values("budget_multiplier")
    if len(valid) < 2:
        return None
    delta_budget = valid["budget_multiplier"].diff()
    delta_coverage = valid[coverage_col].diff()
    per_10pct = (delta_coverage / delta_budget * 0.1).dropna()
    if per_10pct.empty:
        return None
    return float(per_10pct.mean())
