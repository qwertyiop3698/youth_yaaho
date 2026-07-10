"""Layer 1 배치 실행 스크립트.

Layer 0 산출물(data/processed/clean_dataset.parquet)을 입력받아 파생변수 14종 +
도메인지수 5종을 계산하고 featured_dataset.parquet + feature_engineering_report.json을
생성한다. docs/01_architecture.md의 Layer 1 산출물 계약을 그대로 구현.

사용법:
    python -m pipeline.layer1_features.run
    python -m pipeline.layer1_features.run --input ../data/processed/clean_dataset.parquet \
        --output-dir ../data/processed
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import pandas as pd

from ..layer0_data_contract.profiler import load_column_config
from . import feature_engineer as fe

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_INPUT = _PROJECT_ROOT / "data" / "processed" / "clean_dataset.parquet"
DEFAULT_OUTPUT_DIR = _PROJECT_ROOT / "data" / "processed"


def run(input_path: Path, output_dir: Path, config_path: Path | None = None) -> dict:
    if not input_path.exists():
        raise FileNotFoundError(
            f"{input_path} 가 없습니다. 먼저 Layer0(`python -m pipeline.layer0_data_contract.run`)를 "
            "실행해서 clean_dataset.parquet을 생성하세요."
        )

    df = pd.read_parquet(input_path)
    config = load_column_config(config_path) if config_path else load_column_config()

    featured_df, feature_report = fe.engineer_features(df, config)

    output_dir.mkdir(parents=True, exist_ok=True)
    featured_df.to_parquet(output_dir / "featured_dataset.parquet", index=False)
    (output_dir / "feature_engineering_report.json").write_text(
        json.dumps(feature_report, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )

    print(f"[Layer1] 입력: {input_path} ({len(df)}행 {len(df.columns)}컬럼)")
    print(f"[Layer1] 출력: {output_dir}/featured_dataset.parquet "
          f"({len(featured_df)}행 {len(featured_df.columns)}컬럼)")
    print(f"[Layer1] 파생변수({len(feature_report['derived_features'])}개): "
          f"{feature_report['derived_features']}")
    print(f"[Layer1] 도메인지수 5종: {feature_report['domain_indices']}")
    print(f"[Layer1] 진단모델 전용(예측피처 제외 대상, get_diagnostic_only_features): "
          f"{feature_report['diagnostic_only_features']}")

    return feature_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Layer 1 피처 엔지니어링 배치 실행")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="clean_dataset.parquet 경로")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="산출물 저장 디렉토리")
    parser.add_argument("--config", type=Path, default=None, help="column_groups.yaml 경로(기본값 사용 시 생략)")
    parser.add_argument(
        "--log-level", default="WARNING", help="로그 레벨(소표본 경고 등을 보려면 WARNING 이상 권장)"
    )
    args = parser.parse_args()
    logging.basicConfig(level=args.log_level)
    run(args.input, args.output_dir, args.config)


if __name__ == "__main__":
    main()
