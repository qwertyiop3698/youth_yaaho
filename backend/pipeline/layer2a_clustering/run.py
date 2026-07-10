"""Layer 2-A 배치 실행 스크립트.

Layer 1 산출물(data/processed/featured_dataset.parquet)을 입력받아 도메인지수 5종으로
GMM K 탐색 -> 학습 -> 클러스터 소속확률/프로파일을 계산한다. docs/01_architecture.md의
Layer 2-A 산출물 계약(cluster_model.pkl, cluster_membership.parquet)을 구현한다.

표본이 부족하면(sample.csv=5행 등) K 탐색/학습이 통계적으로 무의미하므로 모델을
억지로 만들어내지 않는다 - 이 경우 report.json에 사유만 남기고 cluster_model.pkl/
cluster_membership.parquet은 생성하지 않는다(가짜 산출물을 남기지 않기 위함).

사용법:
    python -m pipeline.layer2a_clustering.run
    python -m pipeline.layer2a_clustering.run --input ../data/processed/featured_dataset.parquet \
        --output-dir ../data/processed
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import joblib
import pandas as pd

from . import cluster_interpreter, gmm_trainer, k_selection

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_INPUT = _PROJECT_ROOT / "data" / "processed" / "featured_dataset.parquet"
DEFAULT_OUTPUT_DIR = _PROJECT_ROOT / "data" / "processed"


def run(input_path: Path, output_dir: Path) -> dict:
    if not input_path.exists():
        raise FileNotFoundError(
            f"{input_path} 가 없습니다. 먼저 Layer1(`python -m pipeline.layer1_features.run`)을 "
            "실행해서 featured_dataset.parquet을 생성하세요."
        )

    df = pd.read_parquet(input_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    X, _ = gmm_trainer.prepare_clustering_input(df)
    k_result = k_selection.select_k(X)

    report: dict = {"row_count": int(len(df)), "valid_row_count": int(len(X)), "k_selection": k_result}

    if k_result["skipped"]:
        print(f"[Layer2-A] K 탐색 생략: {k_result['reason']} - GMM 모델을 생성하지 않습니다.")
        report["model_trained"] = False
        (output_dir / "cluster_report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        return report

    model, valid_index = gmm_trainer.train_gmm(
        df, k=k_result["best_k"], covariance_type=k_result["best_covariance_type"]
    )
    membership = gmm_trainer.predict_membership(model, df)
    profiles = cluster_interpreter.compute_cluster_profiles(model)
    sizes = cluster_interpreter.compute_cluster_sizes(membership)
    labels = cluster_interpreter.suggest_cluster_labels(profiles)

    joblib.dump(model, output_dir / "cluster_model.pkl")
    membership.to_parquet(output_dir / "cluster_membership.parquet", index=True)

    report.update(
        {
            "model_trained": True,
            "best_k": k_result["best_k"],
            "best_covariance_type": k_result["best_covariance_type"],
            "cluster_profiles": profiles.to_dict(orient="index"),
            "cluster_sizes": sizes.to_dict(),
            "suggested_labels": labels,
        }
    )
    (output_dir / "cluster_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )

    print(f"[Layer2-A] 입력: {input_path} ({len(df)}행)")
    print(f"[Layer2-A] 학습 표본: {len(X)}행, K={k_result['best_k']}, "
          f"covariance={k_result['best_covariance_type']}")
    print(f"[Layer2-A] 출력: {output_dir}/cluster_model.pkl, cluster_membership.parquet")
    print(f"[Layer2-A] 클러스터 라벨 초안(사람 확인 필요): {labels}")

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Layer 2-A GMM 클러스터링 배치 실행")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="featured_dataset.parquet 경로")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="산출물 저장 디렉토리")
    parser.add_argument("--log-level", default="WARNING")
    args = parser.parse_args()
    logging.basicConfig(level=args.log_level)
    run(args.input, args.output_dir)


if __name__ == "__main__":
    main()
