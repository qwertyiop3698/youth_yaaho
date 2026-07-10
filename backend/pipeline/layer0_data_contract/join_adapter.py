"""Layer 0 - 조인키 이중화 어댑터.

docs/02_data_missing_value_framework.md:
    "외부데이터(국토부 실거래가, 생활인구) 조인 시 행정동 키가 없을 수 있다는 전제로
    설계해야 한다. -> 조인은 행정동 우선 시도, 실패 시 시군구코드로 fallback하는
    이중 조인 로직 구현."

지금 sample.csv에는 거주지행정동/근무지행정동 컬럼 자체가 없고 시군구코드만 있다
(column_spec.xlsx엔 존재). 즉 fallback 경로가 "예외 상황"이 아니라 현재 확보된
데이터로는 사실상 기본 경로다 - 이 모듈은 그 상황에서도 죽지 않게 방어적으로 짠다.
"""
from __future__ import annotations

from typing import Iterable

import pandas as pd


def join_with_fallback(
    left: pd.DataFrame,
    dong_col: str | None,
    sigungu_col: str | None,
    value_cols: Iterable[str],
    right_by_dong: pd.DataFrame | None = None,
    right_by_sigungu: pd.DataFrame | None = None,
    dong_key: str | None = None,
    sigungu_key: str | None = None,
    indicator_col: str = "_join_method",
) -> pd.DataFrame:
    """행정동 기준 매칭을 우선 시도하고, 매칭되지 않은 행(또는 행정동 컬럼/참조테이블
    자체가 없는 경우)에 한해 시군구코드 기준으로 fallback 매칭한다.

    Args:
        left: 조인 대상(원본) 데이터프레임.
        dong_col: left의 행정동 컬럼명. 없으면 None(행정동 조인 자체를 건너뜀).
        sigungu_col: left의 시군구코드 컬럼명. 없으면 None(fallback도 건너뜀).
        value_cols: 조인으로 채워 넣을 값 컬럼명들.
        right_by_dong: 행정동 단위로 집계된 참조 테이블(예: 행정동별 평균 실거래가).
        right_by_sigungu: 시군구 단위로 집계된 참조 테이블.
        dong_key / sigungu_key: 참조 테이블 쪽의 키 컬럼명(생략 시 left와 동일 이름으로 간주).
        indicator_col: 매칭 방식을 남길 컬럼명("dong" | "sigungu" | "unmatched").

    Returns:
        value_cols와 indicator_col이 채워진 left의 복사본.
    """
    dong_key = dong_key or dong_col
    sigungu_key = sigungu_key or sigungu_col
    value_cols = list(value_cols)

    result = left.copy()
    for col in value_cols:
        if col not in result.columns:
            result[col] = pd.NA
    result[indicator_col] = "unmatched"

    matched = pd.Series(False, index=result.index)

    if (
        right_by_dong is not None
        and dong_col is not None
        and dong_col in result.columns
        and dong_key in right_by_dong.columns
    ):
        lookup = right_by_dong.drop_duplicates(subset=[dong_key]).set_index(dong_key)
        found = result[dong_col].isin(lookup.index)
        for col in value_cols:
            if col in lookup.columns:
                result.loc[found, col] = result.loc[found, dong_col].map(lookup[col])
        result.loc[found, indicator_col] = "dong"
        matched = matched | found

    need_fallback = ~matched
    if (
        right_by_sigungu is not None
        and sigungu_col is not None
        and sigungu_col in result.columns
        and sigungu_key in right_by_sigungu.columns
        and need_fallback.any()
    ):
        lookup = right_by_sigungu.drop_duplicates(subset=[sigungu_key]).set_index(sigungu_key)
        found = need_fallback & result[sigungu_col].isin(lookup.index)
        for col in value_cols:
            if col in lookup.columns:
                result.loc[found, col] = result.loc[found, sigungu_col].map(lookup[col])
        result.loc[found, indicator_col] = "sigungu"

    return result


def regional_median_with_fallback(
    df: pd.DataFrame,
    value_col: str,
    dong_col: str | None,
    sigungu_col: str | None,
    min_sample_for_regional_group: int = 5,
    valid_mask: pd.Series | None = None,
) -> pd.Series:
    """행별 대체값(지역 median)을 계층적으로 계산한다.

    docs/02 구현원칙 3: "최소 표본 미달 시 계층적 fallback: 특정 그룹(예: 특정
    행정동)의 표본이 너무 적으면 상위 카테고리(시군구)로 자동 백오프."

    우선순위: 행정동 그룹 median(표본충분) > 시군구 그룹 median(표본충분) > 전체 median.
    dong_col이 None이거나 데이터에 없으면(현재 sample.csv 상황) 자동으로 시군구 단계부터
    시작하고, 그마저 표본이 부족하면 전체 median으로 떨어진다 - 별도 예외처리 불필요.

    Args:
        valid_mask: True인 행만 "정상값"으로 취급해 median 계산에 사용한다.
            (sentinel/이상값을 median 계산에 섞으면 대체값 자체가 오염되므로 제외)
    """
    values = pd.to_numeric(df[value_col], errors="coerce")
    values_for_stats = values.where(valid_mask) if valid_mask is not None else values

    global_median = values_for_stats.median()
    result = pd.Series(global_median, index=df.index, dtype="float64")

    if sigungu_col and sigungu_col in df.columns:
        group = df[sigungu_col]
        counts = values_for_stats.groupby(group).transform("count")
        medians = values_for_stats.groupby(group).transform("median")
        use_sigungu = counts >= min_sample_for_regional_group
        result = result.where(~use_sigungu, medians)

    if dong_col and dong_col in df.columns:
        group = df[dong_col]
        counts = values_for_stats.groupby(group).transform("count")
        medians = values_for_stats.groupby(group).transform("median")
        use_dong = counts >= min_sample_for_regional_group
        result = result.where(~use_dong, medians)

    return result.fillna(global_median)
