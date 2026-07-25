"""Layer 0 - 전세가 변동 지표 배치 스크립트.

data/external/부산_전월세_실거래가_통합_2024-07_2026-07.csv를 읽어
busan_jeonse_trend.parquet(시군구코드/전세가변동률/갱신보증금변동률/표본수)와
집계 리포트 json을 만든다. feature_engineer.compute_housing_price_exposure()가
이 parquet을 참조테이블로 쓴다(2026-07-25 DIVE 2026 이종결합 작업3).

사용법:
    python -m pipeline.layer0_data_contract.run_rent_price_report
    python -m pipeline.layer0_data_contract.run_rent_price_report \
        --input ../data/external/부산_전월세_실거래가_통합_2024-07_2026-07.csv \
        --output-dir ../data/processed_real
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import rent_price_loader

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
# 미션 문서가 지정한 기본 산출 경로는 data/processed/busan_jeonse_trend.parquet이지만,
# data/processed/는 .gitignore 대상(로컬 스크래치)이라 이 세션에서 실제로 쓰고 있는
# data/processed_real/(실데이터 파이프라인 산출물 디렉토리, population/spatial 리포트와
# 동일 위치)을 기본값으로 둔다 - --output-dir로 언제든 미션 문서의 경로로 바꿀 수 있다.
DEFAULT_OUTPUT_DIR = _PROJECT_ROOT / "data" / "processed_real"


def run(input_path: Path, output_dir: Path) -> dict:
    rent_df = rent_price_loader.load_rent_csv(input_path)
    table, report = rent_price_loader.build_jeonse_trend_table(rent_df)

    output_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = output_dir / "busan_jeonse_trend.parquet"
    table.to_parquet(parquet_path, index=False)

    report_path = output_dir / "jeonse_trend_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    print(f"[RentPriceReport] 입력: {input_path} ({len(rent_df)}행)")
    print(f"[RentPriceReport] 전세 거래: {report['n_jeonse_rows']}건, 시군구: {report['n_sigungu']}개")
    if report["jeonse_trend_insufficient"]:
        print(f"[RentPriceReport] 전세가변동률 표본부족: {report['jeonse_trend_insufficient']}")
    if report["renewal_rate_insufficient"]:
        print(f"[RentPriceReport] 갱신보증금변동률 표본부족: {report['renewal_rate_insufficient']}")
    print(f"[RentPriceReport] 출력: {parquet_path}, {report_path}")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="전세가 변동 지표(시군구별) 배치 생성")
    parser.add_argument("--input", type=Path, default=rent_price_loader.DEFAULT_RENT_CSV_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    run(args.input, args.output_dir)


if __name__ == "__main__":
    main()
