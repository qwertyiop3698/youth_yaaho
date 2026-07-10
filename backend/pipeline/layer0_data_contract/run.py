"""Layer 0 배치 실행 스크립트.

raw CSV(현재는 sample.csv, 해커톤 당일엔 실제 KCB 데이터)를 읽어
    - profiling_report.json / profiling_report.md
    - clean_dataset.parquet
    - cleaning_report.json
을 생성한다. docs/01_architecture.md의 Layer 0 산출물 계약을 그대로 구현.

CLAUDE.md 설계 원칙: "Layer0만 갈아끼우면 나머지는 그대로 작동해야 한다" - 실데이터
투입 시 --input 경로만 바꾸면 되고, column_groups.yaml의 컬럼명이 다르면 그 파일만
고치면 된다(이 스크립트/profiler.py/cleaner.py는 그대로 재사용).

사용법:
    python -m pipeline.layer0_data_contract.run
    python -m pipeline.layer0_data_contract.run --input ../data/real_kcb.csv --output-dir ../data/processed
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from . import cleaner, profiler

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_INPUT = _PROJECT_ROOT / "data" / "sample.csv"
DEFAULT_OUTPUT_DIR = _PROJECT_ROOT / "data" / "processed"


def run(input_path: Path, output_dir: Path, config_path: Path | None = None) -> dict:
    df = pd.read_csv(input_path)
    config = profiler.load_column_config(config_path) if config_path else profiler.load_column_config()

    output_dir.mkdir(parents=True, exist_ok=True)

    profiling_report = profiler.generate_profiling_report(
        df,
        config,
        json_path=output_dir / "profiling_report.json",
        md_path=output_dir / "profiling_report.md",
    )

    cleaned_df, cleaning_report = cleaner.clean_dataset(df, config)
    cleaned_df.to_parquet(output_dir / "clean_dataset.parquet", index=False)
    (output_dir / "cleaning_report.json").write_text(
        json.dumps(cleaning_report, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )

    print(f"[Layer0] 입력: {input_path} ({len(df)}행 {len(df.columns)}컬럼)")
    print(f"[Layer0] 출력 디렉토리: {output_dir}")
    print(f"[Layer0]   - clean_dataset.parquet ({len(cleaned_df)}행 {len(cleaned_df.columns)}컬럼)")
    print("[Layer0]   - profiling_report.json / .md")
    print("[Layer0]   - cleaning_report.json")
    if profiling_report["needs_human_review"]:
        print(f"[Layer0] 사람 확인 필요 컬럼: {profiling_report['needs_human_review']}")
    if profiling_report["missing_from_data"]:
        print(f"[Layer0] 설정엔 있으나 데이터엔 없는 컬럼: {profiling_report['missing_from_data']}")
    if profiling_report["unmapped_in_data"]:
        print(f"[Layer0] 데이터엔 있으나 설정엔 없는 컬럼(column_groups.yaml 갱신 필요): "
              f"{profiling_report['unmapped_in_data']}")
    print(f"[Layer0] 리스크모델 누수금지 컬럼(get_leakage_columns): {cleaner.get_leakage_columns(config)}")
    print(f"[Layer0] 준식별 지역조인키(get_quasi_identifier_columns, raw feature 제외 대상): "
          f"{cleaner.get_quasi_identifier_columns(config)}")

    return {"profiling_report": profiling_report, "cleaning_report": cleaning_report}


def main() -> None:
    parser = argparse.ArgumentParser(description="Layer 0 데이터 계약 검증 + 결측치 정제 배치 실행")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="원본 CSV 경로")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="산출물 저장 디렉토리")
    parser.add_argument("--config", type=Path, default=None, help="column_groups.yaml 경로(기본값 사용 시 생략)")
    args = parser.parse_args()
    run(args.input, args.output_dir, args.config)


if __name__ == "__main__":
    main()
