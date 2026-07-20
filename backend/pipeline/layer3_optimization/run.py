"""Layer 3 배치 실행 스크립트.

Layer1 산출물(featured_dataset.parquet, 도메인지수+인구통계)과 Layer2-B 산출물
(risk_scores.parquet, event_probability)을 합쳐
    1. LP 기반 예산 배정 (lp_allocator.py) -> assignment_results.parquet
    2. 예산 민감도 분석 (sensitivity_analysis.py) -> budget_sensitivity.parquet
    3. Thompson Sampling regret curve 시뮬레이션 (regret_curve.py) -> regret_curve.parquet
을 생성한다. docs/01_architecture.md Layer3 산출물 계약을 구현.

Thompson Sampling은 실제 배정 피드백 데이터가 없으므로 synthetic_reward.py의 합성
리워드로 시뮬레이션한다 - **"실제 운영 전 검증용 시뮬레이션"**이며 실제 정책 효과가
아니다(doc05 명시, 과장 금지). optimization_report.json에도 이 사실을 명시해둔다.

사용법:
    python -m pipeline.layer3_optimization.run
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import pandas as pd
import yaml

from ..layer2a_clustering import risk_trajectory_simulator
from . import lp_allocator, regret_curve, sensitivity_analysis, synthetic_reward

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_FEATURED_INPUT = _PROJECT_ROOT / "data" / "processed" / "featured_dataset.parquet"
DEFAULT_RISK_SCORES_INPUT = _PROJECT_ROOT / "data" / "processed" / "risk_scores.parquet"
DEFAULT_POLICY_CATALOG = Path(__file__).parent / "policy_catalog.yaml"
DEFAULT_OUTPUT_DIR = _PROJECT_ROOT / "data" / "processed"

RISK_COL = "event_probability"
N_BANDIT_ROUNDS = 2000


def load_policy_catalog(path: Path = DEFAULT_POLICY_CATALOG) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def run(
    featured_path: Path = DEFAULT_FEATURED_INPUT,
    risk_scores_path: Path = DEFAULT_RISK_SCORES_INPUT,
    policy_catalog_path: Path = DEFAULT_POLICY_CATALOG,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict:
    if not featured_path.exists():
        raise FileNotFoundError(
            f"{featured_path} 가 없습니다. 먼저 Layer1(`python -m pipeline.layer1_features.run`)을 "
            "실행해서 featured_dataset.parquet을 생성하세요."
        )
    if not risk_scores_path.exists():
        raise FileNotFoundError(
            f"{risk_scores_path} 가 없습니다. 먼저 Layer2-B(`python -m pipeline.layer2b_risk_model.run`)를 "
            "실행해서 risk_scores.parquet을 생성하세요(표본이 너무 작아 Layer2-B 학습이 "
            "생략됐다면 이 파일 자체가 없을 수 있습니다 - 그 경우 Layer3도 실행할 수 없습니다)."
        )

    featured_df = pd.read_parquet(featured_path)
    risk_scores = pd.read_parquet(risk_scores_path)
    df = featured_df.join(risk_scores[[RISK_COL]], how="left")

    policy_catalog = load_policy_catalog(policy_catalog_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    assignment_df, lp_report = lp_allocator.build_and_solve_lp(df, policy_catalog, risk_col=RISK_COL)
    assignment_df.to_parquet(output_dir / "assignment_results.parquet", index=False)

    sensitivity_df = sensitivity_analysis.run_budget_sensitivity(df, policy_catalog, risk_col=RISK_COL)
    sensitivity_df.to_parquet(output_dir / "budget_sensitivity.parquet", index=False)
    marginal_gain = sensitivity_analysis.marginal_gain_per_10pct_budget(sensitivity_df)

    policy_marginal_df = sensitivity_analysis.run_per_policy_marginal_analysis(df, policy_catalog, risk_col=RISK_COL)
    policy_marginal_df.to_parquet(output_dir / "policy_marginal_return.parquet", index=False)

    policy_names = list(policy_catalog["policies"].keys())
    bandit_result = regret_curve.run_bandit_simulation(policy_names, n_rounds=N_BANDIT_ROUNDS)
    bandit_result["history"].to_parquet(output_dir / "regret_curve.parquet", index=False)
    bandit_result["segment_regret"].to_parquet(output_dir / "regret_segment_summary.parquet", index=False)

    gap_df = synthetic_reward.compute_prior_vs_true_gap(policy_catalog, bandit_result["true_effectiveness"])

    report = {
        "lp": lp_report,
        "sensitivity_marginal_gain_per_10pct_budget": marginal_gain,
        "policy_marginal_return": policy_marginal_df.to_dict(orient="records"),
        "bandit": {
            "is_simulation": bandit_result["is_simulation"],
            "simulation_disclaimer": (
                "실제 운영 전 검증용 시뮬레이션입니다. true_effectiveness는 밴딧 수렴 검증을 위해 "
                "임의로 숨겨둔 값이며 실제 정책 효과가 아닙니다(발표 시 명시 필요)."
            ),
            "n_rounds": N_BANDIT_ROUNDS,
            "final_posterior_means": bandit_result["final_posterior_means"],
            "bandit_state": bandit_result["bandit_state"],
            "true_effectiveness": bandit_result["true_effectiveness"],
            # 구간별(초반/중반/후반) 평균 순간 regret - Y-SAFE 대시보드 "학습이 진행될수록
            # 후회가 줄어든다" 시각화용. 누적 regret의 단조 비감소만으로는 실제 학습 여부를
            # 증명하지 못하므로(2026-07-09 지적) 이 구간별 비교가 실질적인 검증/시각화 지표다.
            "segment_regret": bandit_result["segment_regret"].to_dict(orient="records"),
            # prior(LP 초기 가정치) 대비 true_effectiveness(시뮬레이션 숨겨진 정답) 격차.
            # 격차가 방향/크기 모두 다양해야 "밴딧이 틀린 가정을 교정한다"는 데모가 설득력 있다.
            "effectiveness_prior_vs_true_gap": gap_df.to_dict(orient="records"),
        },
    }

    # 위험 궤적 시뮬레이션(docs/04) - Layer2-A(클러스터 프로파일/소속확률)와
    # Layer2-B(위험확률)가 둘 다 필요해 두 레이어 산출물이 합류하는 Layer3에서
    # 계산한다. 둘 중 하나라도 없으면(표본부족으로 Layer2-A 생략 등) 조용히
    # skipped로 남긴다 - 가짜 궤적을 만들지 않는다.
    trajectory_report: dict = {
        "skipped": True,
        "reason": "cluster_report.json/cluster_membership.parquet가 없습니다(Layer2-A 미실행 또는 표본부족).",
    }
    cluster_report_path = output_dir / "cluster_report.json"
    cluster_membership_path = output_dir / "cluster_membership.parquet"
    if cluster_report_path.exists() and cluster_membership_path.exists():
        cluster_report = json.loads(cluster_report_path.read_text(encoding="utf-8"))
        if cluster_report.get("model_trained"):
            cluster_profiles = pd.DataFrame.from_dict(cluster_report["cluster_profiles"], orient="index")
            membership = pd.read_parquet(cluster_membership_path)
            cluster_avg_risk = risk_trajectory_simulator.compute_cluster_avg_risk(membership, risk_scores[RISK_COL])
            initial_distribution = risk_trajectory_simulator.compute_population_initial_distribution(membership)
            effectiveness_values = [cfg["effectiveness_prior"] for cfg in policy_catalog["policies"].values()]
            avg_effectiveness = sum(effectiveness_values) / len(effectiveness_values) if effectiveness_values else 0.0
            trajectory_report = risk_trajectory_simulator.simulate_no_intervention_vs_intervention(
                cluster_profiles,
                cluster_avg_risk,
                initial_distribution,
                intervention_effectiveness=avg_effectiveness,
            )
            trajectory_report["skipped"] = False
        else:
            trajectory_report["reason"] = "클러스터 모델이 학습되지 않았습니다(표본 부족 등으로 Layer2-A 생략)."
    report["trajectory_simulation"] = trajectory_report

    (output_dir / "optimization_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )

    print(f"[Layer3] LP: {lp_report}")
    print(f"[Layer3] 예산 10%당 커버리지율 평균 증가분: {marginal_gain}")
    print(f"[Layer3] 정책별 예산 10%당 한계 커버리지: {policy_marginal_df.to_dict(orient='records')}")
    print(f"[Layer3] 밴딧(시뮬레이션) 사후평균: {bandit_result['final_posterior_means']}")
    print(f"[Layer3] 구간별 평균 regret(초반->후반): "
          f"{bandit_result['segment_regret']['mean_instant_regret'].tolist()}")
    if not trajectory_report.get("skipped"):
        print(
            f"[Layer3] 위험 궤적 시뮬레이션: 무개입 최종 평균위험={trajectory_report['no_intervention'][-1]['expected_avg_risk']:.3f}, "
            f"개입 최종 평균위험={trajectory_report['intervention'][-1]['expected_avg_risk']:.3f}"
        )
    else:
        print(f"[Layer3] 위험 궤적 시뮬레이션 생략: {trajectory_report['reason']}")
    print(
        f"[Layer3] 출력: {output_dir}/assignment_results.parquet, budget_sensitivity.parquet, "
        "policy_marginal_return.parquet, regret_curve.parquet, regret_segment_summary.parquet, "
        "optimization_report.json"
    )

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Layer 3 LP 최적화 + Thompson Sampling 배치 실행")
    parser.add_argument("--featured", type=Path, default=DEFAULT_FEATURED_INPUT)
    parser.add_argument("--risk-scores", type=Path, default=DEFAULT_RISK_SCORES_INPUT)
    parser.add_argument("--policy-catalog", type=Path, default=DEFAULT_POLICY_CATALOG)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--log-level", default="WARNING")
    args = parser.parse_args()
    logging.basicConfig(level=args.log_level)
    run(args.featured, args.risk_scores, args.policy_catalog, args.output_dir)


if __name__ == "__main__":
    main()
