"""Layer 2-B 배치 실행 스크립트.

Layer 1 산출물(data/processed/featured_dataset.parquet)을 입력받아
    1. 프록시 event 라벨 계산 (target.py)
    2. 로지스틱회귀 + LightGBM 이진분류 학습/비교, held-out PR-AUC 기준 자동 선택,
       확률 보정(CalibratedClassifierCV), class_weight='balanced' 적용 (baseline_models.py)
    3. Spatial CV, SHAP top3, 공정성 감사 (spatial_cv/shap_explainer/fairness_audit)
을 수행하고 risk_model.pkl + risk_scores.parquet + risk_model_report.json을 생성한다.

Cox 생존분석은 duration을 관측할 수 없어 비활성 상태다(cox_trainer.py 스텁 참고,
2026-07-08 결정).

risk_model.pkl 구성 (2026-07-08 보강)
--------------------------------------
{"model": <선택된 보정모델>, "model_type": "logistic_regression"|"lightgbm",
 "shap_model": <원본 미보정 LightGBM, SHAP 전용>}
Layer3이 확률(Δrisk_ip 계산용)을 쓸 땐 bundle["model"].predict_proba(...)를,
Layer4가 SHAP 설명을 만들 땐 bundle["shap_model"]을 쓰면 된다(doc04: "SHAP은
LightGBM 베이스라인 기준"이라 선택된 모델이 로지스틱이어도 SHAP은 항상 LightGBM).

공정성 감사(fairness_audit)는 "선택된 보정모델"(deployed_model)로 실행한다 - 보정
자체가 서브그룹별로 다르게 틀어질 수 있어(calibration 차이), doc04가 요구하는 "그룹별
calibration 차이 비교"와 맞으려면 실제 배포되는 모델을 감사해야 하기 때문이다.

spatial CV는 원본(미보정) LightGBM 학습 함수를 그대로 쓴다 - 지역 일반화(AUC-ROC/
PR-AUC) 확인이 목적이라, 폴드마다 다시 보정 CV를 중첩시키는 건 과함(표본이 작을수록
더 불안정해짐).

사용법:
    python -m pipeline.layer2b_risk_model.run
    python -m pipeline.layer2b_risk_model.run --input ../data/processed/featured_dataset.parquet \
        --output-dir ../data/processed
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import joblib
import pandas as pd

from ..layer0_data_contract.profiler import load_column_config
from . import baseline_models, fairness_audit, fairness_correction, shap_explainer, spatial_cv, target

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_INPUT = _PROJECT_ROOT / "data" / "processed" / "featured_dataset.parquet"
DEFAULT_OUTPUT_DIR = _PROJECT_ROOT / "data" / "processed"

FAIRNESS_SUBGROUP_COLUMNS = ["성별", "연령대"]

# train_result 중 JSON으로 직렬화할 수 없는(모델 객체) 키는 report에서 제외한다.
_NON_SERIALIZABLE_TRAINING_KEYS = (
    "logistic_regression",
    "lightgbm",
    "deployed_model",
    "raw_lightgbm_for_shap",
)


def run(input_path: Path, output_dir: Path, config_path: Path | None = None) -> dict:
    if not input_path.exists():
        raise FileNotFoundError(
            f"{input_path} 가 없습니다. 먼저 Layer1(`python -m pipeline.layer1_features.run`)을 "
            "실행해서 featured_dataset.parquet을 생성하세요."
        )

    df = pd.read_parquet(input_path)
    config = load_column_config(config_path) if config_path else load_column_config()
    output_dir.mkdir(parents=True, exist_ok=True)

    event = target.compute_event_label(df)
    train_result = baseline_models.train_and_compare_models(df, event, config)

    report: dict = {
        "row_count": int(len(df)),
        "event_positive_rate": float(event.mean()) if len(event) else None,
        "training": {k: v for k, v in train_result.items() if k not in _NON_SERIALIZABLE_TRAINING_KEYS},
    }

    if train_result["skipped"]:
        print(f"[Layer2-B] 모델 학습 생략: {train_result['reason']} - risk_model.pkl을 생성하지 않습니다.")
        (output_dir / "risk_model_report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        return report

    report["logistic_regression_metrics"] = train_result["logistic_regression"]["metrics"]
    report["lightgbm_metrics"] = train_result["lightgbm"]["metrics"]
    report["best_model_name"] = train_result["best_model_name"]
    report["selection_reason"] = train_result["selection_reason"]
    report["calibration_applied"] = train_result["calibration_applied"]
    report["deployed_model_calibrated"] = train_result["deployed_model_calibrated"]

    X, feature_cols = baseline_models.build_feature_matrix(df, config)
    deployed_model = train_result["deployed_model"]
    shap_model = train_result["raw_lightgbm_for_shap"]

    spatial_result = spatial_cv.spatial_cross_validate(
        df,
        X,
        event,
        train_fn=baseline_models.train_lightgbm,
        eval_fn=baseline_models.evaluate_binary_classifier,
        layer0_config=config,
    )
    report["spatial_cv"] = spatial_result

    fairness_report: dict = {}
    for col in FAIRNESS_SUBGROUP_COLUMNS:
        if col not in df.columns:
            logging.getLogger(__name__).warning("공정성 감사: '%s' 컬럼이 없어 생략합니다.", col)
            continue
        fairness_report[col] = fairness_audit.audit_by_subgroup(deployed_model, X, event, df.loc[X.index, col])
    report["fairness_audit"] = fairness_report

    shap_top3 = shap_explainer.top_k_shap_features(shap_model, X, k=3)
    event_proba = pd.Series(deployed_model.predict_proba(X)[:, 1], index=X.index, name="event_probability")

    # 공정성 감사(fairness_audit)가 성별 AUC 격차를 "발견"했다면, 실제로 쓰이는
    # 임계값 지점(admin.py /policy-gaps의 risk_threshold, 기본 0.6)에 그룹별
    # equalized-odds 보정 임계값을 계산해둔다 - 감사에서 그치지 않고 교정까지 한다.
    fairness_correction_report: dict = {}
    if "성별" in df.columns:
        gender = df.loc[X.index, "성별"]
        correction = fairness_correction.compute_equalized_odds_thresholds(
            event.loc[X.index], event_proba, gender
        )
        if not correction.get("skipped"):
            correction["evaluation"] = fairness_correction.evaluate_correction(
                event.loc[X.index], event_proba, gender, correction["thresholds"], correction["baseline_threshold"]
            )
        fairness_correction_report = correction
    report["fairness_correction"] = fairness_correction_report

    risk_scores = pd.DataFrame({"event_probability": event_proba, "shap_top3": shap_top3.apply(json.dumps)})
    risk_scores.to_parquet(output_dir / "risk_scores.parquet", index=True)
    joblib.dump(
        {"model": deployed_model, "model_type": train_result["best_model_name"], "shap_model": shap_model},
        output_dir / "risk_model.pkl",
    )

    (output_dir / "risk_model_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )

    print(f"[Layer2-B] 입력: {input_path} ({len(df)}행)")
    print(f"[Layer2-B] event 양성비율: {report['event_positive_rate']}")
    print(f"[Layer2-B] 로지스틱 PR-AUC: {report['logistic_regression_metrics']['pr_auc']}, "
          f"LightGBM PR-AUC: {report['lightgbm_metrics']['pr_auc']}")
    print(f"[Layer2-B] 선택된 모델: {report['best_model_name']} ({report['selection_reason']})")
    print(f"[Layer2-B] 확률 보정 적용: {report['calibration_applied']}")
    print(f"[Layer2-B] spatial CV: skipped={spatial_result['skipped']}")
    if fairness_correction_report and not fairness_correction_report.get("skipped"):
        eval_ = fairness_correction_report.get("evaluation", {})
        print(
            f"[Layer2-B] 공정성 보정(성별): before_tpr_gap={eval_.get('before_tpr_gap')}, "
            f"after_tpr_gap={eval_.get('after_tpr_gap')}, improved={eval_.get('improved')}"
        )
    print(f"[Layer2-B] 출력: {output_dir}/risk_model.pkl, risk_scores.parquet")

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Layer 2-B 이진분류 위험모델 배치 실행")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="featured_dataset.parquet 경로")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="산출물 저장 디렉토리")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--log-level", default="WARNING")
    args = parser.parse_args()
    logging.basicConfig(level=args.log_level)
    run(args.input, args.output_dir, args.config)


if __name__ == "__main__":
    main()
