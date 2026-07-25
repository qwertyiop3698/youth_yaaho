"""Layer 1 - 전세가변동노출과 기존 지표 간 상관관계 리포트.

2026-07-25 DIVE 2026 이종결합 작업3: "전세가변동노출"은 도메인지수 5종 구성에
넣지 않는다(GMM 재학습 리스크 회피, 미션 지시) - 대신 기존 도메인지수/위험점수와
실제로 얼마나 겹치거나 다른 신호인지 상관계수로 남겨 발표 소재로 쓴다("새 파생
변수가 기존 지표로는 못 보던 걸 보여주는가?"에 대한 근거).

Layer1(featured_dataset.parquet)과 Layer2-B(risk_scores.parquet) 산출물이 이미
있어야 한다(Layer1 재실행에 이 신규 파생변수가 이미 포함되어 있어야 함).

사용법:
    python -m pipeline.layer1_features.run_housing_exposure_correlation_report
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATA_DIR = _PROJECT_ROOT / "data" / "processed_real"
DEFAULT_OUTPUT = DEFAULT_DATA_DIR / "housing_exposure_correlation_report.json"

DOMAIN_INDEX_COLUMNS = ["주거비압박지수", "부채상환위험지수", "소득변동성지수", "소비압박지수", "신용취약지수"]
TARGET_COLUMN = "전세가변동노출"


def run(data_dir: Path, output_path: Path) -> dict[str, Any]:
    featured_df = pd.read_parquet(data_dir / "featured_dataset.parquet")
    risk_scores_path = data_dir / "risk_scores.parquet"
    risk_scores = pd.read_parquet(risk_scores_path) if risk_scores_path.exists() else None

    if TARGET_COLUMN not in featured_df.columns:
        report = {
            "ready": False,
            "reason": f"'{TARGET_COLUMN}'이 featured_dataset에 없습니다(Layer1을 최신 코드로 재실행했는지 확인).",
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return report

    exposure = pd.to_numeric(featured_df[TARGET_COLUMN], errors="coerce")

    correlations: dict[str, float | None] = {}
    for col in DOMAIN_INDEX_COLUMNS:
        if col not in featured_df.columns:
            correlations[col] = None
            continue
        other = pd.to_numeric(featured_df[col], errors="coerce")
        corr = exposure.corr(other)
        correlations[col] = None if pd.isna(corr) else float(corr)

    risk_correlation = None
    if risk_scores is not None and "event_probability" in risk_scores.columns:
        aligned = exposure.reindex(risk_scores.index)
        corr = aligned.corr(risk_scores["event_probability"])
        risk_correlation = None if pd.isna(corr) else float(corr)

    report = {
        "ready": True,
        "n_rows": int(len(featured_df)),
        "n_non_missing": int(exposure.notna().sum()),
        "n_missing": int(exposure.isna().sum()),
        "descriptive_stats": {
            "mean": float(exposure.mean()) if exposure.notna().any() else None,
            "median": float(exposure.median()) if exposure.notna().any() else None,
            "std": float(exposure.std()) if exposure.notna().any() else None,
            "min": float(exposure.min()) if exposure.notna().any() else None,
            "max": float(exposure.max()) if exposure.notna().any() else None,
        },
        "correlation_with_domain_indices": correlations,
        "correlation_with_risk_probability": risk_correlation,
        "note": (
            "전세가변동노출은 도메인지수 5종 구성에 포함되지 않음(GMM 재학습 리스크 회피, "
            "2026-07-25 미션 범위 밖) - 이 상관관계는 참고용/발표 소재로만 사용."
        ),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"[HousingExposureCorrelationReport] 도메인지수 상관계수: {correlations}")
    print(f"[HousingExposureCorrelationReport] 위험확률 상관계수: {risk_correlation}")
    print(f"[HousingExposureCorrelationReport] 출력: {output_path}")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="전세가변동노출 - 기존 지표 상관관계 리포트 생성")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    run(args.data_dir, args.output)


if __name__ == "__main__":
    main()
