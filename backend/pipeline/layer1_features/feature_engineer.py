"""Layer 1 - 피처 엔지니어링.

docs/03_feature_engineering.md 의 파생변수 + 도메인지수 5종 구현.
입력은 Layer 0 산출물(clean_dataset.parquet, `_was_missing` 플래그 컬럼 포함)이다.

문서/사용자 확인 사항 (2026-07-08)
---------------------------------
- doc03 표에는 파생변수가 14개만 정의돼 있다(CLAUDE.md/doc01의 "15종" 표기와 불일치
  확인 후, 사용자 확인을 거쳐 doc03의 14개만 구현하기로 확정).
- `연체심각도`는 리스크 예측모델(Cox/LGBM) 입력 절대 금지 - `get_diagnostic_only_features()`
  로 분리 관리한다(docs/04 LEAKAGE_COLUMNS와 동일한 패턴, Layer0 cleaner.py 참고).
- 도메인지수 5종은 "높을수록 위험"으로 방향을 통일하기 위해 보호요인(순자산평가금액,
  신용평점, 소득증감률)의 z-score 부호를 반전한 뒤 평균한다(사용자 확인 완료).
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Iterable

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

from ..layer0_data_contract import cleaner as layer0_cleaner
from ..layer0_data_contract.profiler import load_column_config as load_layer0_config

logger = logging.getLogger(__name__)

DEFAULT_MIN_SAMPLE_FOR_ZSCORE = 20
DEFAULT_MIN_TRAIN_SAMPLE_FOR_THIN_FILER_MODEL = 30

LOAN_BALANCE_COLUMNS = ["신용대출-총대출잔액", "주택담보대출-총대출잔액", "정책자금대출-총대출잔액"]

DIAGNOSTIC_ONLY_FEATURES = ["연체심각도"]

# doc03 도메인지수 5종의 구성 변수. 값은 Layer0 원본 컬럼명 또는 이 모듈이 계산한
# 파생변수명(둘 다 동일한 df 안에 공존하므로 이름만 맞으면 됨).
DOMAIN_INDEX_DEFINITIONS: dict[str, list[str]] = {
    "주거비압박지수": ["주거가격부담률", "자가거주여부", "순자산평가금액(주택)"],
    "부채상환위험지수": ["추정DTI", "추정 LTV", "총대출건수", "상환부담률"],
    "소득변동성지수": ["소득증감률", "직장변동위험도", "소득증빙갭"],
    "소비압박지수": ["카드소비/소득비율", "할부의존도", "현금서비스의존도"],
    "신용취약지수": ["신용평점", "Thin Filer 여부", "연체심각도"],
}

# 2026-07-08 사용자 확인: 순자산평가금액/신용평점/소득증감률은 "높을수록 위험 낮음"인
# 보호요인이므로 z-score 부호를 반전해 지수 방향을 "높을수록 위험"으로 통일한다.
PROTECTIVE_FEATURES = {"순자산평가금액(주택)", "신용평점", "소득증감률"}

DEFAULT_THIN_FILER_PREDICTORS = ["추정 연소득", "추정DTI", "추정 LTV", "총대출건수", "2년내 직장명이력건수"]


def get_diagnostic_only_features() -> list[str]:
    """진단모델 전용 파생변수 목록. cleaner.get_leakage_columns()와 동일한 역할을
    파생변수 레벨에서 수행 - 리스크 예측모델(Cox/LGBM) 피처 목록에 절대 포함 금지."""
    return list(DIAGNOSTIC_ONLY_FEATURES)


def assert_no_diagnostic_leakage(feature_columns: Iterable[str]) -> None:
    """연체심각도 등 진단전용 파생변수가 예측모델 피처 목록에 섞이지 않았는지 강제 검증."""
    offending = set(get_diagnostic_only_features()) & set(feature_columns)
    assert not offending, (
        "진단모델 전용 파생변수는 리스크 예측모델의 피처로 쓰면 안 됩니다: "
        f"{sorted(offending)}"
    )


def get_leaky_domain_indices() -> list[str]:
    """get_diagnostic_only_features()의 파생변수를 구성변수로 포함하는 도메인지수 목록.

    2026-07-10 실스케일(n=1500) 리허설에서 발견: `신용취약지수`가 `연체심각도`를
    구성변수 중 하나로 평균에 포함하고 있어서, 리터럴 컬럼명만 비교하는
    get_diagnostic_only_features() 기반 검증으로는 안 잡히는 우회 누수가 있었다
    (held-out LightGBM PR-AUC가 0.999로 비정상적으로 높게 나와 발견). docs/03은
    도메인지수 5종을 "클러스터링/리스크모델 공통 입력"으로 명시하므로 GMM(Layer2-A,
    gmm_trainer.DOMAIN_INDEX_COLUMNS)에서는 5종 전부 그대로 쓰고, 이 함수는 그중
    리스크 예측모델(Cox/LGBM) 피처로는 쓰면 안 되는 것만 프로그램적으로 골라낸다
    (앞으로 DOMAIN_INDEX_DEFINITIONS나 DIAGNOSTIC_ONLY_FEATURES가 바뀌어도 자동으로
    맞게 갱신됨 - 하드코딩된 목록을 또 따로 안 만듦)."""
    diagnostic_only = set(get_diagnostic_only_features())
    return [
        name
        for name, constituents in DOMAIN_INDEX_DEFINITIONS.items()
        if diagnostic_only & set(constituents)
    ]


def assert_no_domain_index_leakage(feature_columns: Iterable[str]) -> None:
    """신용취약지수처럼 진단전용 파생변수를 구성변수로 포함하는 도메인지수가 리스크
    예측모델 피처 목록에 섞이지 않았는지 강제 검증(GMM 클러스터링 입력으로는 허용)."""
    offending = set(get_leaky_domain_indices()) & set(feature_columns)
    assert not offending, (
        "진단전용 파생변수를 구성변수로 포함하는 도메인지수는 리스크 예측모델의 피처로 "
        f"쓰면 안 됩니다(GMM 클러스터링 입력으로는 그대로 사용 가능): {sorted(offending)}"
    )


def _col_numeric(df: pd.DataFrame, name: str) -> pd.Series:
    if name not in df.columns:
        logger.warning("피처 계산에 필요한 컬럼 '%s'이 없어 NaN으로 대체합니다.", name)
        return pd.Series(np.nan, index=df.index)
    return pd.to_numeric(df[name], errors="coerce")


def _col_raw(df: pd.DataFrame, name: str) -> pd.Series:
    if name not in df.columns:
        logger.warning("피처 계산에 필요한 컬럼 '%s'이 없어 NaN으로 대체합니다.", name)
        return pd.Series(np.nan, index=df.index)
    return df[name]


def _sum_existing(df: pd.DataFrame, columns: list[str]) -> pd.Series:
    existing = [c for c in columns if c in df.columns]
    if not existing:
        logger.warning("합산 대상 컬럼 %s이 전부 없어 0으로 대체합니다.", columns)
        return pd.Series(0.0, index=df.index)
    return df[existing].apply(pd.to_numeric, errors="coerce").fillna(0).sum(axis=1)


def _total_loan_balance(df: pd.DataFrame) -> pd.Series:
    return _sum_existing(df, LOAN_BALANCE_COLUMNS)


def safe_divide(numerator: pd.Series, denominator: pd.Series, fill_value: float = 0.0) -> pd.Series:
    """분모=0(또는 NaN)이면 0으로 나누기를 피하고 fill_value를 반환한다.

    docs/03: "모든 나눗셈 연산은 분모=0 케이스를 명시적으로 처리 (0으로 나누기 방지,
    대체값 또는 0 반환 정의)" - 이 프로젝트는 fill_value 기본값 0.0을 사용한다
    (정보 없음/무의미한 비율을 0으로 표현).
    """
    num = pd.to_numeric(numerator, errors="coerce")
    den = pd.to_numeric(denominator, errors="coerce")
    is_invalid = den.isna() | (den == 0) | num.isna()
    safe_den = den.where(~is_invalid, other=1.0)  # 실제 0 나눗셈 자체를 회피
    result = num.where(~num.isna(), other=0.0) / safe_den
    return result.where(~is_invalid, other=fill_value)


def safe_zscore(
    series: pd.Series,
    min_sample: int = DEFAULT_MIN_SAMPLE_FOR_ZSCORE,
    *,
    population_mean: float | None = None,
    population_std: float | None = None,
) -> pd.Series:
    """z-score 표준화. 표본이 min_sample 미만이면(sample.csv=5행 등) 통계적으로
    불안정하다는 경고를 로깅한다(계산은 계속 진행 - 실데이터는 표본이 충분할 것이므로
    막을 필요는 없고, 지금 단계에서 결과를 과신하지 말라는 신호만 남긴다).
    표준편차가 0이면(전부 동일 값) 0으로 채운다.

    population_mean/population_std가 주어지면 series 자기 자신이 아니라 그 값으로
    표준화한다 - 진단 API처럼 1행짜리 series를 표준화할 때, 자기 자신 기준으로
    표준화하면 표준편차가 항상 0이라 결과가 항상 0이 되는 문제를 피하기 위함이다
    (population 기준값은 학습 데이터셋 전체에서 미리 계산해 재사용해야 한다)."""
    values = pd.to_numeric(series, errors="coerce")

    if population_mean is not None and population_std is not None:
        if not population_std or pd.isna(population_std):
            return pd.Series(0.0, index=series.index)
        return (values - population_mean) / population_std

    n = int(values.notna().sum())
    if 0 < n < min_sample:
        logger.warning(
            "z-score 표준화: 표본 부족(n=%d < %d)으로 결과가 통계적으로 불안정할 수 있습니다. "
            "실데이터(표본 충분)에서는 문제 없습니다.",
            n,
            min_sample,
        )
    std = values.std(ddof=0)
    if not std or pd.isna(std):
        return pd.Series(0.0, index=series.index)
    return (values - values.mean()) / std


# ---------------------------------------------------------------------------
# 파생변수 14종 (docs/03)
# ---------------------------------------------------------------------------


def compute_income_growth_rate(df: pd.DataFrame) -> pd.Series:
    """소득증감률 = (연소득 - 2년전연소득) / 2년전연소득"""
    income = _col_numeric(df, "추정 연소득")
    income_2y_ago = _col_numeric(df, "2년전 추정 연소득 금액")
    return safe_divide(income - income_2y_ago, income_2y_ago)


def compute_debt_to_income_ratio(df: pd.DataFrame) -> pd.Series:
    """총부채/소득비율 = Σ대출잔액 / 추정연소득"""
    return safe_divide(_total_loan_balance(df), _col_numeric(df, "추정 연소득"))


def compute_debt_service_ratio(df: pd.DataFrame) -> pd.Series:
    """상환부담률 = 최근12개월상환액 / 추정연소득"""
    repayment = _col_numeric(df, "총 대출 상환금액 (최근 12개월)")
    return safe_divide(repayment, _col_numeric(df, "추정 연소득"))


def compute_card_spending_to_income_ratio(df: pd.DataFrame) -> pd.Series:
    """카드소비/소득비율 = (신용+체크카드소비) / 추정연소득"""
    credit = _col_numeric(df, "최근 12개월 신용카드소비금액").fillna(0)
    check = _col_numeric(df, "최근 12개월 체크카드소비금액").fillna(0)
    return safe_divide(credit + check, _col_numeric(df, "추정 연소득"))


def compute_installment_dependency(df: pd.DataFrame) -> pd.Series:
    """할부의존도 = 할부이용액 / 신용카드소비액. 분모=0(카드소비 없음)이면 0 처리."""
    installment = _col_numeric(df, "최근 12개월 할부이용금액")
    card_spending = _col_numeric(df, "최근 12개월 신용카드소비금액")
    return safe_divide(installment, card_spending, fill_value=0.0)


def compute_cash_service_dependency(df: pd.DataFrame) -> pd.Series:
    """현금서비스의존도 = 현금서비스이용액 / 추정연소득"""
    cash_service = _col_numeric(df, "최근 12개월 현금서비스이용금액")
    return safe_divide(cash_service, _col_numeric(df, "추정 연소득"))


def compute_housing_price_burden_ratio(df: pd.DataFrame) -> pd.Series:
    """주거가격부담률 = 전세거래가(Layer0 결측처리 후) / 추정연소득"""
    jeonse = _col_numeric(df, "2년내 현거주지평균전세거래가")
    return safe_divide(jeonse, _col_numeric(df, "추정 연소득"))


def compute_job_change_risk(df: pd.DataFrame) -> pd.Series:
    """직장변동위험도 = 직장이력건수 × sign(이직후소득증감액)"""
    job_history_count = _col_numeric(df, "2년내 직장명이력건수").fillna(0)
    income_change_after_job = _col_numeric(df, "2년내 이직후 소득 증감액").fillna(0)
    return job_history_count * np.sign(income_change_after_job)


def compute_residence_workplace_mismatch(df: pd.DataFrame, config: dict[str, Any] | None = None) -> pd.Series:
    """거주-근무 불일치 (boolean). docs/02 조인키 이중화 원칙과 동일하게 행정동
    우선, 없으면 시군구코드로 판단한다. column_groups.yaml의 join_role 메타데이터를
    재사용해 컬럼명을 하드코딩하지 않는다."""
    config = config or load_layer0_config()
    join_cols = layer0_cleaner.resolve_join_columns(config)
    dong_res, sigungu_res = join_cols.get("residence", (None, None))
    dong_work, sigungu_work = join_cols.get("workplace", (None, None))

    if dong_res and dong_work and dong_res in df.columns and dong_work in df.columns:
        res, work = _col_raw(df, dong_res), _col_raw(df, dong_work)
    elif sigungu_res and sigungu_work and sigungu_res in df.columns and sigungu_work in df.columns:
        res, work = _col_raw(df, sigungu_res), _col_raw(df, sigungu_work)
    else:
        logger.warning("거주-근무 불일치: 지역 조인키 컬럼이 없어 전부 False로 채웁니다.")
        return pd.Series(False, index=df.index)

    both_known = res.notna() & work.notna()
    return (res != work) & both_known


def compute_income_proof_gap(df: pd.DataFrame) -> pd.Series:
    """소득증빙갭 = (추정연소득 - 증빙연소득) / 추정연소득. 증빙연소득=0은 정상값(Layer0 확인)."""
    income = _col_numeric(df, "추정 연소득")
    proof_income = _col_numeric(df, "증빙연소득")
    return safe_divide(income - proof_income, income)


def compute_credit_leverage(df: pd.DataFrame) -> pd.Series:
    """신용레버리지 = Σ대출잔액 / 총자산평가금액(주택)"""
    return safe_divide(_total_loan_balance(df), _col_numeric(df, "총자산평가금액(주택)"))


def compute_asset_debt_gap(df: pd.DataFrame) -> pd.Series:
    """자산-부채 갭 = 순자산평가금액(주택) - Σ대출잔액"""
    net_asset = _col_numeric(df, "순자산평가금액(주택)").fillna(0)
    return net_asset - _total_loan_balance(df)


def compute_delinquency_severity(
    df: pd.DataFrame, min_sample: int = DEFAULT_MIN_SAMPLE_FOR_ZSCORE
) -> pd.Series:
    """연체심각도 = z(연체건수) + z(연체일수) + z(연체금액).

    **진단모델 전용, 예측모델 입력 절대 금지** - get_diagnostic_only_features() 참고.
    연체건수/연체금액은 대출+카드를 합산한 값을 사용한다(연체일수는 이미 합산 컬럼).
    """
    total_count = _col_numeric(df, "대출연체건수").fillna(0) + _col_numeric(df, "카드연체건수").fillna(0)
    delinq_days = _col_numeric(df, "연체일수").fillna(0)
    total_amount = _col_numeric(df, "대출연체금액").fillna(0) + _col_numeric(df, "카드연체금액").fillna(0)

    return (
        safe_zscore(total_count, min_sample)
        + safe_zscore(delinq_days, min_sample)
        + safe_zscore(total_amount, min_sample)
    )


def compute_thin_filer_adjusted_score(
    df: pd.DataFrame,
    thin_filer_col: str = "Thin Filer 여부",
    score_col: str = "신용평점",
    predictor_cols: list[str] | None = None,
    min_train_sample: int = DEFAULT_MIN_TRAIN_SAMPLE_FOR_THIN_FILER_MODEL,
) -> pd.Series:
    """Thin Filer 보정 스코어.

    docs/03: "Thin Filer=1일 때 신용평점 대체모형 (별도 로지스틱 서브모델)". 신용평점이
    0~1000 연속값이라 분류기보다 회귀모형이 적절하다고 판단해 LinearRegression을
    사용한다(구현 판단, 필요 시 교체 가능).

    - Thin Filer=0 행: 원본 신용평점을 그대로 사용(산출 가능한 신뢰값이므로).
    - Thin Filer=1 행: Thin Filer=0 집단으로 학습한 회귀모형으로 대체 스코어를 예측.
    - 학습 표본이 min_train_sample 미만이면(현재 sample.csv=5행) 통계적으로 불안정하므로
      모델을 학습하지 않고 NaN으로 남기며 경고를 로깅한다(임의의 대체값을 만들지 않음 -
      Layer0의 "원본값 삭제/임의대체 금지" 원칙을 서브모델에도 동일하게 적용).
    """
    if score_col not in df.columns:
        logger.warning("'%s' 컬럼이 없어 Thin Filer 보정 스코어를 계산할 수 없습니다.", score_col)
        return pd.Series(np.nan, index=df.index)

    result = pd.to_numeric(df[score_col], errors="coerce").astype(float).copy()

    if thin_filer_col not in df.columns:
        logger.warning("'%s' 컬럼이 없어 신용평점을 그대로 사용합니다(보정 없음).", thin_filer_col)
        return result

    is_thin_filer = pd.to_numeric(df[thin_filer_col], errors="coerce").fillna(0) == 1
    if not is_thin_filer.any():
        return result

    predictor_cols = predictor_cols or [c for c in DEFAULT_THIN_FILER_PREDICTORS if c in df.columns]
    if not predictor_cols:
        logger.warning("Thin Filer 보정 스코어: 사용 가능한 예측변수가 없어 서브모델 생략(NaN 처리).")
        result.loc[is_thin_filer] = np.nan
        return result

    features = df[predictor_cols].apply(pd.to_numeric, errors="coerce")
    train_mask = (~is_thin_filer) & features.notna().all(axis=1) & result.notna()
    train_n = int(train_mask.sum())

    if train_n < min_train_sample:
        logger.warning(
            "Thin Filer 보정 스코어: 학습 표본 부족(n=%d < %d)으로 서브모델을 생략합니다. "
            "Thin Filer=1 행의 신용평점은 NaN으로 남깁니다(하드코딩 대체값 생성 안 함). "
            "실데이터로 표본이 충분해지면 자동으로 서브모델이 학습됩니다.",
            train_n,
            min_train_sample,
        )
        result.loc[is_thin_filer] = np.nan
        return result

    model = LinearRegression()
    model.fit(features.loc[train_mask], result.loc[train_mask])

    predict_mask = is_thin_filer & features.notna().all(axis=1)
    if predict_mask.any():
        result.loc[predict_mask] = model.predict(features.loc[predict_mask])

    skipped = is_thin_filer & ~predict_mask
    if skipped.any():
        logger.warning(
            "Thin Filer 보정 스코어: 예측변수 결측으로 %d건은 대체하지 못해 NaN으로 남깁니다.",
            int(skipped.sum()),
        )
        result.loc[skipped] = np.nan

    return result


FEATURE_COMPUTERS: dict[str, Callable[[pd.DataFrame], pd.Series]] = {
    "소득증감률": compute_income_growth_rate,
    "총부채/소득비율": compute_debt_to_income_ratio,
    "상환부담률": compute_debt_service_ratio,
    "카드소비/소득비율": compute_card_spending_to_income_ratio,
    "할부의존도": compute_installment_dependency,
    "현금서비스의존도": compute_cash_service_dependency,
    "주거가격부담률": compute_housing_price_burden_ratio,
    "직장변동위험도": compute_job_change_risk,
    "거주-근무 불일치": compute_residence_workplace_mismatch,
    "소득증빙갭": compute_income_proof_gap,
    "신용레버리지": compute_credit_leverage,
    "자산-부채 갭": compute_asset_debt_gap,
}


# ---------------------------------------------------------------------------
# 도메인 지수 5종
# ---------------------------------------------------------------------------


def compute_domain_index(
    df: pd.DataFrame,
    constituent_columns: list[str],
    protective: set[str] | None = None,
    min_sample: int = DEFAULT_MIN_SAMPLE_FOR_ZSCORE,
    population_stats: dict[str, tuple[float, float]] | None = None,
) -> pd.Series:
    """구성 변수를 z-score 표준화(보호요인은 부호 반전) 후 단순평균.

    population_stats가 주어지면(진단 API의 1행 입력 등) 각 구성 변수를 df 자신이
    아니라 population_stats[col]=(평균, 표준편차) 기준으로 표준화한다."""
    protective = protective or set()
    total = pd.Series(0.0, index=df.index)
    used = 0
    for col in constituent_columns:
        if col not in df.columns:
            logger.warning("도메인지수 계산: 구성변수 '%s'가 없어 건너뜁니다.", col)
            continue
        stats = (population_stats or {}).get(col)
        if stats is not None:
            z = safe_zscore(df[col], min_sample, population_mean=stats[0], population_std=stats[1])
        else:
            z = safe_zscore(df[col], min_sample)
        if col in protective:
            z = -z
        total = total + z
        used += 1
    if used == 0:
        return pd.Series(np.nan, index=df.index)
    return total / used


def compute_domain_index_population_stats(population_df: pd.DataFrame) -> dict[str, tuple[float, float]]:
    """도메인지수 구성 변수들의 population 평균/표준편차를 학습 데이터셋(featured_dataset)
    기준으로 미리 계산해둔다. 진단 API가 1행짜리 입력을 표준화할 때 이 값을 재사용해야
    "1행짜리 series는 표준편차가 항상 0이라 지수가 항상 0" 문제를 피할 수 있다."""
    constituent_columns = {col for cols in DOMAIN_INDEX_DEFINITIONS.values() for col in cols}
    stats: dict[str, tuple[float, float]] = {}
    for col in constituent_columns:
        if col not in population_df.columns:
            continue
        values = pd.to_numeric(population_df[col], errors="coerce")
        if values.notna().sum() == 0:
            continue
        stats[col] = (float(values.mean()), float(values.std(ddof=0)))
    return stats


def compute_all_domain_indices(
    df: pd.DataFrame,
    min_sample: int = DEFAULT_MIN_SAMPLE_FOR_ZSCORE,
    population_stats: dict[str, tuple[float, float]] | None = None,
) -> pd.DataFrame:
    """도메인 지수 5종(주거비압박/부채상환위험/소득변동성/소비압박/신용취약) 산출.
    df에는 파생변수 14종이 이미 계산되어 있어야 한다(engineer_features 참고)."""
    indices = {
        name: compute_domain_index(df, cols, PROTECTIVE_FEATURES, min_sample, population_stats)
        for name, cols in DOMAIN_INDEX_DEFINITIONS.items()
    }
    return pd.DataFrame(indices, index=df.index)


# ---------------------------------------------------------------------------
# 오케스트레이터
# ---------------------------------------------------------------------------


def engineer_features(
    df: pd.DataFrame,
    config: dict[str, Any] | None = None,
    min_sample_for_zscore: int = DEFAULT_MIN_SAMPLE_FOR_ZSCORE,
    thin_filer_min_train_sample: int = DEFAULT_MIN_TRAIN_SAMPLE_FOR_THIN_FILER_MODEL,
    domain_index_population_stats: dict[str, tuple[float, float]] | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Layer 0의 clean_dataset을 입력받아 파생변수 14종 + 도메인지수 5종을 추가한다.

    원본 컬럼은 전부 보존하고(삭제 없음), 새 컬럼만 추가한다.

    domain_index_population_stats가 주어지면(진단 API의 1행 입력 등) 도메인지수 5종을
    df 자신이 아니라 그 population 기준(평균/표준편차)으로 표준화한다
    (compute_domain_index_population_stats 참고).
    """
    df = df.copy()
    config = config or load_layer0_config()
    notes: list[str] = []

    for name, fn in FEATURE_COMPUTERS.items():
        df[name] = fn(df, config) if name == "거주-근무 불일치" else fn(df)
        notes.append(f"{name} 계산 완료")

    df["연체심각도"] = compute_delinquency_severity(df, min_sample=min_sample_for_zscore)
    notes.append("연체심각도 계산 완료 (진단모델 전용, get_diagnostic_only_features() 참고)")

    df["Thin Filer 보정 스코어"] = compute_thin_filer_adjusted_score(
        df, min_train_sample=thin_filer_min_train_sample
    )
    notes.append("Thin Filer 보정 스코어 계산 완료")

    domain_indices = compute_all_domain_indices(
        df, min_sample=min_sample_for_zscore, population_stats=domain_index_population_stats
    )
    for col in domain_indices.columns:
        df[col] = domain_indices[col]
    notes.append(f"도메인지수 5종 계산 완료: {list(domain_indices.columns)}")

    report = {
        "row_count": int(len(df)),
        "derived_features": list(FEATURE_COMPUTERS.keys()) + ["연체심각도", "Thin Filer 보정 스코어"],
        "domain_indices": list(DOMAIN_INDEX_DEFINITIONS.keys()),
        "diagnostic_only_features": get_diagnostic_only_features(),
        "notes": notes,
    }
    return df, report
