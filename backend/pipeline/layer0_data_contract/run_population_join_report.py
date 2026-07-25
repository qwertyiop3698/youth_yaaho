"""Layer 0 - 생활인구(인구현황) 외부데이터 조인 리포트 배치 스크립트.

admin /risk-map이 요청마다 계산하는 것과 동일한 join_with_fallback 경로를 오프라인
배치로 한 번 실행해, 조인 성공/실패 건수와 시군구별 정규화 값 요약을 파일로 남긴다
(발표/검증용 - "장식용 레이어가 아니라 분석적 결합"임을 산출물로 보여주기 위함).

사용법:
    python -m pipeline.layer0_data_contract.run_population_join_report
    python -m pipeline.layer0_data_contract.run_population_join_report \
        --data-dir ../data/processed_real --external-dir ../data/external \
        --output ../data/processed_real/population_join_report.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from . import cleaner as layer0_cleaner
from . import external_loader
from . import join_adapter
from .profiler import load_column_config

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATA_DIR = _PROJECT_ROOT / "data" / "processed_real"
DEFAULT_EXTERNAL_DIR = _PROJECT_ROOT / "data" / "external"
DEFAULT_OUTPUT = DEFAULT_DATA_DIR / "population_join_report.json"
DEFAULT_RISK_THRESHOLD = 0.6


def run(
    data_dir: Path,
    external_dir: Path,
    output_path: Path,
    risk_threshold: float = DEFAULT_RISK_THRESHOLD,
) -> dict[str, Any]:
    featured_df = pd.read_parquet(data_dir / "featured_dataset.parquet")
    risk_scores_path = data_dir / "risk_scores.parquet"
    risk_scores = pd.read_parquet(risk_scores_path) if risk_scores_path.exists() else None

    csv_files = sorted(external_dir.glob("*.csv")) if external_dir.exists() else []
    if len(csv_files) != 1:
        report = {
            "ready": False,
            "reason": f"data/external/에 CSV가 정확히 1개여야 합니다(발견: {len(csv_files)}개).",
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return report

    raw = external_loader.load_population_csv(csv_files[0])
    sigungu_ref, population_report = external_loader.build_sigungu_population_reference(raw)
    dong_ref = external_loader.build_dong_population_reference(raw)

    layer0_config = load_column_config()
    join_cols = layer0_cleaner.resolve_join_columns(layer0_config)
    dong_col, sigungu_col = join_cols.get("residence", (None, None))
    cols_present = [c for c in (dong_col, sigungu_col) if c and c in featured_df.columns]

    joined = join_adapter.join_with_fallback(
        featured_df[cols_present],
        dong_col=dong_col if dong_col in featured_df.columns else None,
        sigungu_col=sigungu_col if sigungu_col in featured_df.columns else None,
        value_cols=[external_loader.POPULATION_VALUE_COL],
        right_by_dong=dong_ref,
        right_by_sigungu=sigungu_ref,
        dong_key="행정동코드",
        sigungu_key="시군구코드",
    )

    join_method_counts = joined["_join_method"].value_counts().to_dict()
    group_col = sigungu_col if sigungu_col in featured_df.columns else dong_col

    region_summary: list[dict[str, Any]] = []
    if group_col:
        high_risk_mask = None
        if risk_scores is not None and "event_probability" in risk_scores.columns:
            high_risk_mask = risk_scores["event_probability"] >= risk_threshold

        grouped = joined.groupby(group_col)
        for region_code, region_df in grouped:
            pop_ref = region_df[external_loader.POPULATION_VALUE_COL].dropna()
            population_reference = float(pop_ref.iloc[0]) if len(pop_ref) else None
            join_method = region_df["_join_method"].iloc[0]

            n_high_risk = None
            high_risk_per_1000 = None
            if high_risk_mask is not None:
                region_idx = region_df.index.intersection(high_risk_mask.index)
                n_high_risk = int(high_risk_mask.loc[region_idx].sum())
                if population_reference:
                    high_risk_per_1000 = round(n_high_risk / population_reference * 1000, 4)

            region_summary.append({
                "region_code": str(region_code),
                "n_persons": int(len(region_df)),
                "population_join_method": join_method,
                "population_reference": population_reference,
                "n_high_risk": n_high_risk,
                "high_risk_per_1000_population": high_risk_per_1000,
            })

    report = {
        "ready": True,
        "source_population_csv": csv_files[0].name,
        "risk_threshold": risk_threshold,
        "n_persons_total": int(len(featured_df)),
        "join_method_counts": {str(k): int(v) for k, v in join_method_counts.items()},
        "n_join_failed": int(join_method_counts.get("unmatched", 0)),
        "population_data_notes": {
            "age_filter_applied": population_report["age_filter_applied"],
            "age_filter_reason": population_report["age_filter_reason"],
            "time_dimension_available": population_report["time_dimension_available"],
            "time_dimension_note": population_report["time_dimension_note"],
            "code_system_check": population_report["code_system_check"],
            "subtotal_mismatch_sigungu_codes": population_report["subtotal_mismatch_sigungu_codes"],
        },
        "region_summary": sorted(region_summary, key=lambda r: r["region_code"]),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"[PopulationJoinReport] 입력: {data_dir} / 생활인구: {csv_files[0].name}")
    print(f"[PopulationJoinReport] 조인 방식 분포: {join_method_counts}")
    print(f"[PopulationJoinReport] 출력: {output_path}")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="생활인구 외부데이터 조인 리포트 생성")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--external-dir", type=Path, default=DEFAULT_EXTERNAL_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--risk-threshold", type=float, default=DEFAULT_RISK_THRESHOLD)
    args = parser.parse_args()
    run(args.data_dir, args.external_dir, args.output, args.risk_threshold)


if __name__ == "__main__":
    main()
