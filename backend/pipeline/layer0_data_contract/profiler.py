"""Layer 0 - 컬럼 자동 프로파일러.

docs/02_data_missing_value_framework.md 의 "자동 컬럼 프로파일러" 절 구현.
당일 실데이터가 들어오면 42개+ 컬럼을 사람이 눈으로 훑을 시간이 없다는 전제로,
결측 후보(sentinel/코드북 밖 값)와 0-값 비율을 자동으로 스캔해 리포트를 만든다.

이 모듈은 원본 데이터를 변형하지 않는다(순수 진단/리포트 전용). 실제 처리는 cleaner.py.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

DEFAULT_CONFIG_PATH = Path(__file__).parent / "column_groups.yaml"


def load_column_config(config_path: str | Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    """column_groups.yaml 로드. 실제 데이터 투입 시 이 파일만 바꾸면 코드 변경 없이 대응 가능."""
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def detect_known_sentinels(series: pd.Series, known_values: list | None) -> dict[str, Any]:
    """설정에 명시된 sentinel 값(예: -99999999)과 정확히 일치하는 값 탐지.

    표본 크기와 무관하게 항상 수행한다 - 통계적 방법(IQR)은 소표본에서 불안정하지만
    "알려진 sentinel 값과 정확히 같다"는 판단은 표본 크기에 영향받지 않기 때문.
    """
    if not known_values:
        return {"checked": False, "hits": {}}
    hits: dict[Any, int] = {}
    for v in known_values:
        count = int((series == v).sum())
        if count:
            hits[v] = count
    return {"checked": True, "hits": hits}


def detect_statistical_outliers(
    series: pd.Series, iqr_multiplier: float, min_sample: int
) -> dict[str, Any]:
    """IQR 기반 통계적 이상치(sentinel 후보) 탐지.

    docs/02: "절댓값이 해당 컬럼 정상범위(IQR 기반)의 1000배 이상인 극단값".
    표본이 min_sample 미만이면 사분위수 자체가 불안정하므로 생략하고 사유를 남긴다
    (5행짜리 샘플 목업에 통계적 방법을 과신하지 말라는 docs/02의 경고를 코드로 반영).
    """
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    if len(numeric) < min_sample:
        return {
            "checked": False,
            "reason": f"표본 부족(n={len(numeric)} < {min_sample})으로 통계적 이상치 탐지 생략",
            "candidates": [],
        }
    q1, q3 = numeric.quantile(0.25), numeric.quantile(0.75)
    iqr = q3 - q1
    scale = iqr if iqr > 0 else (numeric.abs().median() or 1.0)
    threshold = scale * iqr_multiplier
    candidates = numeric[numeric.abs() > threshold]
    return {
        "checked": True,
        "threshold": float(threshold),
        "candidate_count": int(len(candidates)),
        "candidates": sorted(candidates.unique().tolist()),
    }


def detect_unknown_categories(series: pd.Series, codebook: list | None) -> dict[str, Any]:
    """코드북 범위를 벗어난 범주형 값 탐지. 코드북이 아직 없으면(당일 확인 필요) 생략."""
    if not codebook:
        return {"checked": False, "reason": "코드북 미확정", "unknown_values": []}
    known = set(codebook)
    non_null = series.dropna()
    unknown = non_null[~non_null.isin(known)]
    return {
        "checked": True,
        "unknown_count": int(len(unknown)),
        "unknown_values": sorted({str(v) for v in unknown.unique().tolist()}),
    }


def profile_column(
    series: pd.Series, col_cfg: dict[str, Any], defaults: dict[str, Any]
) -> dict[str, Any]:
    """컬럼 하나에 대한 프로파일링 결과(결측 후보/0비율/유니크값 수 등)."""
    n = len(series)
    null_count = int(series.isna().sum())
    zero_count = int((pd.to_numeric(series, errors="coerce") == 0).sum())
    unique_count = int(series.nunique(dropna=True))

    profile: dict[str, Any] = {
        "group": col_cfg.get("group"),
        "dtype": col_cfg.get("dtype"),
        "zero_meaning": col_cfg.get("zero_meaning"),
        "missing_strategy": col_cfg.get("missing_strategy"),
        "row_count": n,
        "null_count": null_count,
        "null_pct": round(null_count / n, 4) if n else None,
        "zero_count": zero_count,
        "zero_pct": round(zero_count / n, 4) if n else None,
        "unique_count": unique_count,
    }

    if col_cfg.get("sentinel_check"):
        profile["known_sentinel"] = detect_known_sentinels(
            series, col_cfg.get("known_sentinel_values")
        )
        profile["statistical_outlier"] = detect_statistical_outliers(
            series,
            defaults.get("sentinel_iqr_multiplier", 1000),
            defaults.get("min_sample_for_iqr", 20),
        )

    if col_cfg.get("dtype") == "categorical":
        profile["unknown_category"] = detect_unknown_categories(series, col_cfg.get("codebook"))

    needs_review = False
    review_reasons = []
    if col_cfg.get("zero_meaning") == "ambiguous" and zero_count > 0:
        needs_review = True
        review_reasons.append(f"0값 {zero_count}건 - 결측/정상 여부 불확실(설계상 사람 확인 필요)")
    if profile.get("known_sentinel", {}).get("hits"):
        needs_review = True
        review_reasons.append("known sentinel 값 발견")
    if profile.get("statistical_outlier", {}).get("candidate_count"):
        needs_review = True
        review_reasons.append("통계적 이상치(IQR) 후보 발견")
    if profile.get("unknown_category", {}).get("unknown_count"):
        needs_review = True
        review_reasons.append("코드북 밖 값 발견")

    profile["needs_human_review"] = needs_review
    profile["review_reasons"] = review_reasons
    return profile


def profile_dataset(df: pd.DataFrame, config: dict[str, Any]) -> dict[str, Any]:
    """데이터셋 전체 프로파일링. 컬럼명이 config와 어긋나도 죽지 않고 리포트에 남긴다."""
    columns_cfg = config.get("columns", {})
    defaults = config.get("defaults", {})

    profiled: dict[str, Any] = {}
    for col, col_cfg in columns_cfg.items():
        if col not in df.columns:
            continue
        profiled[col] = profile_column(df[col], col_cfg, defaults)

    missing_from_data = sorted(set(columns_cfg) - set(df.columns))
    unmapped_in_data = sorted(set(df.columns) - set(columns_cfg))
    needs_review_cols = [c for c, p in profiled.items() if p["needs_human_review"]]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "row_count": int(len(df)),
        "column_count": int(len(df.columns)),
        "columns": profiled,
        "missing_from_data": missing_from_data,
        "unmapped_in_data": unmapped_in_data,
        "needs_human_review": needs_review_cols,
    }


def _report_to_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Layer 0 결측치 프로파일링 리포트",
        "",
        f"- 생성 시각: {report['generated_at']}",
        f"- 행 수: {report['row_count']}, 컬럼 수: {report['column_count']}",
        "",
        "## 컬럼별 요약",
        "",
        "| 컬럼 | 그룹 | null% | 0% | unique | 검토필요 | 사유 |",
        "|---|---|---|---|---|---|---|",
    ]
    for col, p in report["columns"].items():
        null_pct = f"{p['null_pct']:.1%}" if p["null_pct"] is not None else "-"
        zero_pct = f"{p['zero_pct']:.1%}" if p["zero_pct"] is not None else "-"
        review = "⚠️" if p["needs_human_review"] else ""
        reasons = "; ".join(p["review_reasons"])
        lines.append(
            f"| {col} | {p['group']} | {null_pct} | {zero_pct} | {p['unique_count']} | {review} | {reasons} |"
        )

    if report["missing_from_data"]:
        lines += ["", "## 설정엔 있으나 데이터엔 없는 컬럼", ""]
        lines += [f"- {c}" for c in report["missing_from_data"]]

    if report["unmapped_in_data"]:
        lines += ["", "## 데이터엔 있으나 설정에 없는 컬럼 (column_groups.yaml 갱신 필요)", ""]
        lines += [f"- {c}" for c in report["unmapped_in_data"]]

    if report["needs_human_review"]:
        lines += ["", "## 사람 확인이 필요한 컬럼", ""]
        lines += [f"- {c}" for c in report["needs_human_review"]]

    return "\n".join(lines) + "\n"


def generate_profiling_report(
    df: pd.DataFrame,
    config: dict[str, Any],
    json_path: str | Path,
    md_path: str | Path | None = None,
) -> dict[str, Any]:
    """profiling_report.json (+ 선택적으로 .md) 생성."""
    report = profile_dataset(df, config)

    json_path = Path(json_path)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    if md_path is not None:
        md_path = Path(md_path)
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(_report_to_markdown(report), encoding="utf-8")

    return report
