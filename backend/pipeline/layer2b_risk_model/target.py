"""Layer 2-B - 프록시 타겟(event) 정의.

docs/04_modeling_clustering_survival.md의 프록시 라벨 설계를 구현한다.

2026-07-08 사용자 결정 (중요 - 반드시 읽을 것)
------------------------------------------
KCB 데이터는 날짜/관측기간/person_id 컬럼이 전혀 없는 **단일 시점 크로스섹션
스냅샷**이다(sample.csv 43개 컬럼 전수 확인 완료). "2년내"/"2년전" 컬럼들도 하나의
기준시점에서 과거를 돌아본 집계값일 뿐, 여러 시점을 반복 관측한 패널 데이터가
아니다. 즉 duration(생존분석에서 "사건까지 남은 시간")을 관측할 방법이 원천적으로
없다.

검토했던 대안:
    A. 연체일수를 "경과기간"으로 근사 -> 기각. 이건 backward recurrence time(이미
       지난 시간)인데 Cox가 요구하는 prospective time-to-event(앞으로 남은 시간)와
       방향이 정반대라 hazard ratio 해석 자체가 무의미해짐.
    B. 위험도 기반 합성(시뮬레이션) duration -> 기각. 위험도로 duration을 만들고
       그 위험도를 다시 피처로 쓰면 순환논증이 됨.
    C. duration 없이 event(이진 라벨)만 예측 -> 채택. 로지스틱회귀/LightGBM
       이진분류가 주모델로 승격됨(baseline_models.py). Cox는 실제 패널데이터가
       확보되면 활성화할 스텁으로 남김(cox_trainer.py).

이 파일은 doc04 공식 그대로 event만 계산한다:
    event = 1 if (연체건수 > 0) or (
        추정DTI >= p75 and 소득증감률 < 0 and 신용평점_저위험군_근사
    ) else 0

"신용평점_저위험군_근사"에 대해
--------------------------------
doc04 원문은 "신용평점_하락추정"이라고 썼지만, 과거 신용평점 이력 컬럼이 전혀 없어
실제 "하락"은 계산할 방법이 없다. 사용자 확인(2026-07-08)에 따라 "현재 낮은 수준"을
근사한다는 걸 정직하게 드러내는 이름으로 바꿨다: 전체 분포 기준 하위 25%(p25)
이하를 "낮은 신용평점 상태"로 근사한다.

Thin Filer 여부로 대체하는 방안은 명시적으로 기각됐다 - Thin Filer는 "신용이력이
없어 점수를 못 매기는 상태"지 "위험한 상태"가 아니다. 이걸 위험 신호로 쓰면 대출/
카드 이력 자체가 없는 사회초년생(안전한 그룹일 수 있음)을 위험군으로 잘못 분류할
수 있고, Layer1에서 이미 Thin Filer를 별도 서브모델(compute_thin_filer_adjusted_score)
로 다루고 있어 같은 신호를 이중으로 다르게 해석하는 셈이 된다.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# docs/04: 연체 관련 컬럼은 타겟(event) 정의에만 사용 허용(피처 사용은 절대 금지,
# feature_gate.get_model_ready_features()가 강제한다).
DELINQUENCY_COUNT_COLUMNS = ["대출연체건수", "카드연체건수"]

LOW_CREDIT_SCORE_PERCENTILE = 0.25
DTI_HIGH_PERCENTILE = 0.75


def compute_low_credit_score_proxy(
    df: pd.DataFrame,
    score_col: str = "신용평점",
    percentile: float = LOW_CREDIT_SCORE_PERCENTILE,
) -> pd.Series:
    """신용평점_저위험군_근사: 신용평점이 전체 분포 하위 percentile 이하인지 여부.

    "하락"이 아니라 "현재 낮은 수준"의 근사임을 유의할 것 - 시계열 이력이 없어
    실제 하락폭은 계산 불가능하다는 한계를 그대로 안고 간다.
    """
    if score_col not in df.columns:
        logger.warning("'%s' 컬럼이 없어 신용평점_저위험군_근사를 계산할 수 없습니다.", score_col)
        return pd.Series(False, index=df.index)

    scores = pd.to_numeric(df[score_col], errors="coerce")
    if scores.notna().sum() == 0:
        logger.warning("'%s' 컬럼에 유효값이 없어 신용평점_저위험군_근사를 계산할 수 없습니다.", score_col)
        return pd.Series(False, index=df.index)

    threshold = scores.quantile(percentile)
    return scores <= threshold


def _total_delinquency_count(df: pd.DataFrame) -> pd.Series:
    present = [c for c in DELINQUENCY_COUNT_COLUMNS if c in df.columns]
    missing = [c for c in DELINQUENCY_COUNT_COLUMNS if c not in df.columns]
    if missing:
        logger.warning("event 계산: 연체건수 컬럼 %s이 없어 0으로 간주합니다.", missing)
    if not present:
        return pd.Series(0.0, index=df.index)
    return sum(pd.to_numeric(df[c], errors="coerce").fillna(0) for c in present)


def compute_event_label(
    df: pd.DataFrame,
    dti_col: str = "추정DTI",
    income_growth_col: str = "소득증감률",
    score_col: str = "신용평점",
    dti_percentile: float = DTI_HIGH_PERCENTILE,
    low_score_percentile: float = LOW_CREDIT_SCORE_PERCENTILE,
) -> pd.Series:
    """docs/04 프록시 event 정의. featured_dataset(소득증감률 등 Layer1 파생변수
    포함)을 입력으로 받는 것을 전제로 한다.

    연체건수는 대출연체건수+카드연체건수 합산(2026-07-08 사용자 승인 - Layer1의
    연체심각도와 동일한 해석 유지, docs/04 LEAKAGE_COLUMNS 5개 중 건수 2개를 묶음).
    """
    has_delinquency = _total_delinquency_count(df) > 0

    if dti_col not in df.columns:
        logger.warning("event 계산: '%s' 컬럼이 없어 2차 조건을 계산할 수 없습니다.", dti_col)
        dti = pd.Series(np.nan, index=df.index)
    else:
        dti = pd.to_numeric(df[dti_col], errors="coerce")

    if income_growth_col not in df.columns:
        logger.warning("event 계산: '%s' 컬럼이 없어 2차 조건을 계산할 수 없습니다.", income_growth_col)
        income_growth = pd.Series(np.nan, index=df.index)
    else:
        income_growth = pd.to_numeric(df[income_growth_col], errors="coerce")

    low_score = compute_low_credit_score_proxy(df, score_col, low_score_percentile)

    dti_threshold = dti.quantile(dti_percentile) if dti.notna().any() else np.nan
    high_dti = dti >= dti_threshold if pd.notna(dti_threshold) else pd.Series(False, index=df.index)
    income_declining = income_growth < 0

    secondary_condition = high_dti & income_declining & low_score
    event = (has_delinquency | secondary_condition).fillna(False).astype(int)
    return event
