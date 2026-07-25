"""Layer 2-B - 공간적 자기상관(Moran's I/LISA) 리포트 배치 스크립트.

2026-07-25 DIVE 2026 작업2: admin /risk-map은 요청마다 Moran's I/LISA를 계산해서
보여주기만 하고 결과를 남기지 않는다. 이 스크립트는 같은 계산 경로(공식 행정동
경계 기반 인접행렬, boundary_loader.load_adjacency_with_fallback)를 오프라인
배치로 한 번 실행해 리포트 파일로 남긴다(발표/검증용 - 인접행렬 요약, 고립 지역
처리 내역, Global Moran's I 통계량/p값, LISA hotspot/coldspot 목록).

사용법:
    python -m pipeline.layer2b_risk_model.run_spatial_autocorrelation_report
    python -m pipeline.layer2b_risk_model.run_spatial_autocorrelation_report \
        --data-dir ../data/processed_real --risk-threshold 0.6
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from pipeline.layer0_data_contract import boundary_loader
from pipeline.layer0_data_contract import cleaner as layer0_cleaner
from pipeline.layer0_data_contract.profiler import load_column_config

from . import spatial_autocorrelation

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATA_DIR = _PROJECT_ROOT / "data" / "processed_real"
DEFAULT_OUTPUT = DEFAULT_DATA_DIR / "spatial_autocorrelation_report.json"


def run(data_dir: Path, output_path: Path) -> dict[str, Any]:
    featured_df = pd.read_parquet(data_dir / "featured_dataset.parquet")
    risk_scores = pd.read_parquet(data_dir / "risk_scores.parquet")

    layer0_config = load_column_config()
    join_cols = layer0_cleaner.resolve_join_columns(layer0_config)
    _, sigungu_col = join_cols.get("residence", (None, None))
    if not sigungu_col or sigungu_col not in featured_df.columns:
        report = {"ready": False, "reason": f"시군구 조인 컬럼('{sigungu_col}')이 featured_dataset에 없습니다."}
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return report

    merged = featured_df[[sigungu_col]].join(risk_scores[["event_probability"]], how="inner")
    grouped = merged.groupby(sigungu_col)["event_probability"].mean()
    grouped.index = grouped.index.astype(str)

    adjacency, adjacency_report = boundary_loader.load_adjacency_with_fallback()
    if adjacency is None:
        report = {"ready": False, "reason": "인접행렬 소스(행정동 경계 geojson)가 없습니다."}
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return report

    morans_i = spatial_autocorrelation.compute_morans_i(grouped, adjacency)
    lisa_by_region: dict[str, dict[str, Any]] = {}
    if not morans_i.get("skipped"):
        lisa_by_region = spatial_autocorrelation.compute_local_indicators(grouped, adjacency)

    hotspot_regions = []
    coldspot_regions = []
    for region_code, lisa in lisa_by_region.items():
        classification = spatial_autocorrelation.classify_hotspot(lisa)
        entry = {
            "region_code": region_code,
            "avg_risk_probability": float(grouped.loc[region_code]),
            "local_i": lisa["local_i"],
            "quadrant": lisa["quadrant"],
            "p_value": lisa["p_value"],
        }
        if classification == "hotspot":
            hotspot_regions.append(entry)
        elif classification == "coldspot":
            coldspot_regions.append(entry)

    report = {
        "ready": True,
        "n_sigungu_with_data": int(len(grouped)),
        "adjacency_summary": adjacency_report,
        "global_morans_i": morans_i,
        "lisa_hotspot_regions": sorted(hotspot_regions, key=lambda r: r["region_code"]),
        "lisa_coldspot_regions": sorted(coldspot_regions, key=lambda r: r["region_code"]),
        "lisa_all_regions": {code: lisa for code, lisa in sorted(lisa_by_region.items())},
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"[SpatialAutocorrelationReport] 입력: {data_dir}")
    print(f"[SpatialAutocorrelationReport] Global Moran's I: {morans_i}")
    print(f"[SpatialAutocorrelationReport] hotspot {len(hotspot_regions)}개 / coldspot {len(coldspot_regions)}개")
    print(f"[SpatialAutocorrelationReport] 출력: {output_path}")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Moran's I/LISA 공간 자기상관 리포트 생성")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    run(args.data_dir, args.output)


if __name__ == "__main__":
    main()
