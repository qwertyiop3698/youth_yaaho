"""Layer 0 - 부산 전월세 실거래가 -> 전세가 변동 지표 로더.

data/external/부산_전월세_실거래가_통합_2024-07_2026-07.csv(213,872건, 2026-07-25
확인)에서 전세(전세여부==1) 거래만 추려, 시군구코드 × 분기 단위 ㎡당보증금(만원)
대표값을 만들고 "전세가변동률"/"갱신계약 보증금 변동률" 두 지표를 산출한다
(2026-07-25 DIVE 2026 이종결합 작업3).

## 대표값 집계 방식 선택: 전체 중앙값 vs 주택유형별 중앙값 고정비중 가중합
분기 간 주택유형 거래 구성비가 흔들리면(예: 이번 분기에 유독 오피스텔 거래가
많았다) 전체 중앙값만으로는 "가격이 올랐다"와 "비싼/싼 유형 거래가 늘었다"를
구분할 수 없다(Simpson's paradox류 왜곡). 실제 데이터로 두 방식을 비교했다
(부산 전체 집계 기준, 분기별 변화율의 표준편차로 비교):
  - 전체 중앙값(주택유형 구분 없이): 0.02649
  - 주택유형별(아파트/오피스텔/연립다세대) 중앙값을 전체기간 고정비중
    (각각 79.2%/13.5%/7.3%)으로 가중합: 0.02577
고정비중 가중합 쪽이 더(또는 최소한 같이) 안정적이라 이 방식을 택한다 - 이번
데이터는 아파트 비중이 워낙 커서 차이가 크진 않지만, 주택유형 구성이 더 흔들리는
분기/지역에서는 차이가 커질 수 있고 손해볼 게 없는 선택이다. "고정비중"은 전체
기간 거래건수 비중으로 계산하며, 분기마다 새로 계산하지 않는다(그러면 다시 구성비
변화가 섞여 들어가 의미가 없어짐).

## 전세가변동률: 왜 4분기 vs 4분기인가
분기 하나짜리 비교는 계절성/소수 거래 노이즈가 커서 금지한다(미션 지시). 시군구별로
"데이터에 있는 가장 최근 분기부터 거꾸로 4개(최근 4분기) vs 그 앞 4개(직전
4분기)"의 대표값 중앙값을 비교한다 - 마지막 분기가 당월 일부만 포함해 불완전해도
"최신 분기부터 거꾸로 센다"는 규칙이라 특별한 보정 없이 자연스럽게 처리된다.
시군구의 전체 분기 수가 8개 미만이거나, 두 4분기 구간 중 하나라도 원거래건수 합이
MIN_SAMPLE_PER_WINDOW 미만이면 노이즈가 너무 커 NaN 처리하고 사유를 리포트에
남긴다(원본값 삭제/임의대체 금지 원칙 - 결측은 결측대로 표기).

## 갱신계약 보증금 변동률
계약구분==갱신이고 종전계약 보증금이 있는 행에서
(보증금-종전계약보증금)/종전계약보증금의 시군구별 중앙값. 같은 매물의 계약 전후
비교라 주택유형 구성 왜곡이 원천적으로 없는 강한 신호다. 표본 30건 미만 시군구는
NaN 처리하고 건수를 리포트에 남긴다(미션이 명시한 기준).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

N_QUARTERS_PER_WINDOW = 4
MIN_SAMPLE_PER_QUARTER_WINDOW = 30  # 전세가변동률 계산에 쓰는 4분기 구간 하나당 최소 원거래건수
MIN_SAMPLE_FOR_RENEWAL_RATE = 30  # 갱신계약 보증금 변동률 - 미션이 명시한 기준

REQUIRED_COLUMNS = [
    "시군구코드", "전세여부", "계약년월", "㎡당보증금(만원)", "주택유형",
    "계약구분", "보증금(만원)", "종전계약 보증금(만원)",
]

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RENT_CSV_PATH = (
    _PROJECT_ROOT / "data" / "external" / "부산_전월세_실거래가_통합_2024-07_2026-07.csv"
)
# 미션 문서는 data/processed/busan_jeonse_trend.parquet을 지정하지만, 이 세션은
# 실데이터 파이프라인 산출물을 전부 data/processed_real/에 쌓아왔다(population/
# spatial 리포트와 동일 위치) - 기본값을 그 관례에 맞춘다. feature_engineer.
# compute_housing_price_exposure()는 load_jeonse_trend_parquet(path=...)를 통해
# 다른 데이터 디렉토리를 쓰는 파이프라인 실행에서도 경로를 바꿔 넘길 수 있다.
DEFAULT_JEONSE_TREND_OUTPUT_PATH = _PROJECT_ROOT / "data" / "processed_real" / "busan_jeonse_trend.parquet"


def load_jeonse_trend_parquet(path: Path = DEFAULT_JEONSE_TREND_OUTPUT_PATH) -> pd.DataFrame | None:
    """feature_engineer.compute_housing_price_exposure()가 쓰는 참조테이블 로더.

    파일이 없으면 None을 반환한다 - 호출부가 "컬럼/참조데이터 부재 시 NaN + 경고
    로깅"이라는 기존 관례대로 처리하게 둔다(여기서 예외를 던지지 않음)."""
    path = Path(path)
    if not path.exists():
        return None
    return pd.read_parquet(path)


def load_rent_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="utf-8-sig")
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            f"전월세 실거래가 CSV에 필요한 컬럼이 없습니다: {missing} (실제 컬럼: {list(df.columns)}). "
            "컬럼명이 바뀌었으면 이 모듈의 REQUIRED_COLUMNS/집계 로직을 실제 컬럼명에 맞춰 갱신하세요."
        )
    return df


def _add_quarter_columns(df: pd.DataFrame) -> pd.DataFrame:
    """계약년월(YYYYMM)에서 정렬 가능한 분기 정수키와 표시용 라벨을 만든다."""
    df = df.copy()
    year = df["계약년월"] // 100
    month = df["계약년월"] % 100
    quarter_of_year = ((month - 1) // 3) + 1
    df["_quarter_key"] = year * 4 + quarter_of_year  # 예: 2025Q2 -> 2025*4+2, 분기간 비교/정렬이 쉬움
    df["_quarter_label"] = year.astype(str) + "Q" + quarter_of_year.astype(str)
    return df


def _compute_quarterly_representative(jeonse_df: pd.DataFrame) -> pd.DataFrame:
    """시군구코드 × 분기 단위 대표값(주택유형별 중앙값의 전체기간 고정비중 가중합).

    반환 columns: 시군구코드, _quarter_key, _quarter_label, representative_value, n_transactions
    """
    type_share = jeonse_df["주택유형"].value_counts(normalize=True)  # 전체 기간 고정 비중

    type_medians = (
        jeonse_df.groupby(["시군구코드", "_quarter_key", "_quarter_label", "주택유형"])["㎡당보증금(만원)"]
        .median()
        .reset_index()
    )
    type_medians["weight"] = type_medians["주택유형"].map(type_share)
    type_medians["weighted_value"] = type_medians["㎡당보증금(만원)"] * type_medians["weight"]

    grouped = type_medians.groupby(["시군구코드", "_quarter_key", "_quarter_label"])
    # 그 분기에 특정 주택유형 거래가 아예 없으면(weight 합이 1보다 작아짐) 존재하는
    # 유형들의 비중으로 재정규화한다(없는 유형을 0으로 취급해 대표값을 낮추지 않음).
    representative = (grouped["weighted_value"].sum() / grouped["weight"].sum()).rename("representative_value")

    n_transactions = jeonse_df.groupby(["시군구코드", "_quarter_key"]).size().rename("n_transactions")

    result = representative.reset_index()
    result = result.merge(
        n_transactions.reset_index(), on=["시군구코드", "_quarter_key"], how="left"
    )
    return result


def compute_jeonse_price_trend(quarterly: pd.DataFrame) -> pd.DataFrame:
    """시군구별 "최근 4분기 vs 직전 4분기" 대표값 중앙값을 비교해 전세가변동률을 만든다.

    quarterly: _compute_quarterly_representative()의 출력.
    반환 columns: 시군구코드, 전세가변동률, n_quarters_available, recent_window_n,
    prior_window_n, insufficient_reason(NaN이면 None)
    """
    columns = [
        "시군구코드", "전세가변동률", "n_quarters_available",
        "recent_window_n", "prior_window_n", "insufficient_reason",
    ]
    if quarterly.empty:
        # 전세 거래가 아예 없는 입력(예: 월세만 있는 데이터)이면 groupby가 아무것도
        # 순회하지 않아 rows가 비고, pd.DataFrame([])는 컬럼이 하나도 없는 빈
        # 프레임이 된다 - build_jeonse_trend_table()의 merge(on="시군구코드")가
        # 그 상태로는 KeyError로 죽으므로, 빈 경우에도 스키마를 명시해서 반환한다.
        return pd.DataFrame(columns=columns)

    rows: list[dict[str, Any]] = []
    for sigungu, group in quarterly.groupby("시군구코드"):
        group = group.sort_values("_quarter_key")
        n_quarters = len(group)

        if n_quarters < 2 * N_QUARTERS_PER_WINDOW:
            rows.append({
                "시군구코드": sigungu,
                "전세가변동률": np.nan,
                "n_quarters_available": n_quarters,
                "recent_window_n": None,
                "prior_window_n": None,
                "insufficient_reason": (
                    f"분기 데이터 {n_quarters}개 < 최근4+직전4={2 * N_QUARTERS_PER_WINDOW}개 필요"
                ),
            })
            continue

        recent = group.tail(N_QUARTERS_PER_WINDOW)
        prior = group.iloc[-(2 * N_QUARTERS_PER_WINDOW):-N_QUARTERS_PER_WINDOW]
        recent_n = int(recent["n_transactions"].sum())
        prior_n = int(prior["n_transactions"].sum())

        if recent_n < MIN_SAMPLE_PER_QUARTER_WINDOW or prior_n < MIN_SAMPLE_PER_QUARTER_WINDOW:
            rows.append({
                "시군구코드": sigungu,
                "전세가변동률": np.nan,
                "n_quarters_available": n_quarters,
                "recent_window_n": recent_n,
                "prior_window_n": prior_n,
                "insufficient_reason": (
                    f"4분기 구간 거래건수 부족(최근={recent_n}, 직전={prior_n}, "
                    f"기준={MIN_SAMPLE_PER_QUARTER_WINDOW})"
                ),
            })
            continue

        recent_value = float(recent["representative_value"].median())
        prior_value = float(prior["representative_value"].median())
        # safe_divide와 동일한 원칙(분모=0 명시 처리) - 여기서는 분모가 0이 되는
        # 경우 자체가 비정상(㎡당보증금이 0인 분기 중앙값)이라 발생 시 결측 처리한다.
        change_rate = (recent_value - prior_value) / prior_value if prior_value else np.nan

        rows.append({
            "시군구코드": sigungu,
            "전세가변동률": change_rate,
            "n_quarters_available": n_quarters,
            "recent_window_n": recent_n,
            "prior_window_n": prior_n,
            "insufficient_reason": None,
        })

    return pd.DataFrame(rows)


def compute_renewal_deposit_change_rate(rent_df: pd.DataFrame) -> pd.DataFrame:
    """갱신계약 보증금 변동률 - (보증금-종전계약보증금)/종전계약보증금의 시군구별 중앙값.

    전세/월세 구분 없이 "갱신" 계약 전체를 본다(전세 갱신뿐 아니라 월세 보증금
    갱신도 같은 신호 - 같은 매물의 전후 비교라는 성질은 동일). 표본 30건 미만
    시군구는 NaN 처리하고 건수를 리포트에 남긴다(미션이 명시한 기준).
    """
    columns = ["시군구코드", "갱신보증금변동률", "n_renewal_contracts", "insufficient_reason"]
    renewal = rent_df[
        (rent_df["계약구분"] == "갱신") & rent_df["종전계약 보증금(만원)"].notna() & (rent_df["종전계약 보증금(만원)"] != 0)
    ].copy()
    if renewal.empty:
        # compute_jeonse_price_trend()의 빈 입력 처리와 동일한 이유(merge용 스키마 보존).
        return pd.DataFrame(columns=columns)

    renewal["_change_rate"] = (
        renewal["보증금(만원)"] - renewal["종전계약 보증금(만원)"]
    ) / renewal["종전계약 보증금(만원)"]

    rows: list[dict[str, Any]] = []
    for sigungu, group in renewal.groupby("시군구코드"):
        n = len(group)
        if n < MIN_SAMPLE_FOR_RENEWAL_RATE:
            rows.append({
                "시군구코드": sigungu,
                "갱신보증금변동률": np.nan,
                "n_renewal_contracts": n,
                "insufficient_reason": f"갱신계약 표본 {n}건 < 최소 {MIN_SAMPLE_FOR_RENEWAL_RATE}건",
            })
            continue
        rows.append({
            "시군구코드": sigungu,
            "갱신보증금변동률": float(group["_change_rate"].median()),
            "n_renewal_contracts": n,
            "insufficient_reason": None,
        })

    return pd.DataFrame(rows)


def build_jeonse_trend_table(rent_df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """시군구코드, 전세가변동률, 갱신보증금변동률, 표본수를 담은 최종 테이블 + 리포트.

    산출물 스키마(미션 3-1): 시군구코드, 전세가변동률, 갱신보증금변동률, 표본수.
    """
    jeonse = rent_df[rent_df["전세여부"] == 1].copy()
    jeonse = _add_quarter_columns(jeonse)

    quarterly = _compute_quarterly_representative(jeonse)
    trend = compute_jeonse_price_trend(quarterly)
    renewal = compute_renewal_deposit_change_rate(rent_df)

    merged = trend.merge(renewal, on="시군구코드", how="outer")
    merged["표본수"] = merged["recent_window_n"].fillna(0) + merged["prior_window_n"].fillna(0)

    table = merged[["시군구코드", "전세가변동률", "갱신보증금변동률", "표본수"]].copy()

    report = {
        "n_source_rows": int(len(rent_df)),
        "n_jeonse_rows": int(len(jeonse)),
        "n_sigungu": int(merged["시군구코드"].nunique()),
        "representative_aggregation_method": (
            "주택유형별(아파트/오피스텔/연립다세대) 분기 중앙값을 전체기간 고정비중으로 가중합"
            "(전체 중앙값 대비 분기별 변화율 표준편차가 더 낮아 채택, 2026-07-25 검증)"
        ),
        "n_quarters_per_window": N_QUARTERS_PER_WINDOW,
        "min_sample_per_quarter_window": MIN_SAMPLE_PER_QUARTER_WINDOW,
        "min_sample_for_renewal_rate": MIN_SAMPLE_FOR_RENEWAL_RATE,
        "jeonse_trend_insufficient": [
            {"시군구코드": str(r["시군구코드"]), "reason": r["insufficient_reason"]}
            for r in trend.to_dict(orient="records")
            if r["insufficient_reason"]
        ],
        "renewal_rate_insufficient": [
            {"시군구코드": str(r["시군구코드"]), "reason": r["insufficient_reason"]}
            for r in renewal.to_dict(orient="records")
            if r["insufficient_reason"]
        ],
    }
    return table, report
