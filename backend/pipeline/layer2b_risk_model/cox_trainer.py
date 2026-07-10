"""Layer 2-B - Cox 생존분석 (현재 비활성 스텁).

2026-07-08 사용자 결정: KCB 데이터가 단일 시점 크로스섹션 스냅샷이라 duration(사건
까지 남은 시간)을 관측할 방법이 없다(target.py 상단 문서 참고). 검토했던 대안:

    A. 연체일수를 "경과기간"으로 근사 -> 기각.
       backward recurrence time(이미 지난 시간)을 Cox가 요구하는 prospective
       time-to-event(앞으로 남을 시간)로 쓰면 방향이 정반대라 hazard ratio 해석
       자체가 무의미해짐.
    B. 위험도 기반 합성(시뮬레이션) duration -> 기각.
       위험도로 duration을 만들고 그 위험도를 다시 피처로 쓰면 순환논증이 됨.
    C. duration 없이 event(이진 라벨)만 예측 -> 채택.
       로지스틱회귀 + LightGBM 이진분류가 지금의 주모델이다(baseline_models.py).

이 파일은 실제 패널/시계열 데이터(예: 월별 신용평점·연체상태 이력)가 확보되면 바로
채워 넣을 수 있도록 lifelines.CoxPHFitter 기반 인터페이스만 스텁으로 남겨둔다.
지금 호출하면 NotImplementedError를 던진다 - 임의의 duration을 만들어 조용히
실행되는 것을 막기 위해 의도적으로 막아둔 것이다. lifelines는 아직 requirements.txt
에 추가하지 않았다(사용하지 않는 의존성을 미리 설치하지 않기 위함 - 활성화 시 추가).
"""
from __future__ import annotations

from typing import Any

import pandas as pd


def train_cox_model(
    df: pd.DataFrame,
    duration_col: str,
    event_col: str,
    **kwargs: Any,
):
    """CoxPHFitter 학습(lifelines). 실제 패널데이터로 duration_col을 관측할 수
    있게 되면 아래와 같은 형태로 구현하면 된다:

        from lifelines import CoxPHFitter
        cph = CoxPHFitter(**kwargs)
        cph.fit(df[[duration_col, event_col, *feature_columns]],
                duration_col=duration_col, event_col=event_col)
        return cph

    지금은 duration을 관측/근사할 방법이 없어 의도적으로 비활성화되어 있다.
    """
    raise NotImplementedError(
        "Cox 생존분석은 현재 비활성 상태입니다. duration(사건까지 남은 시간)을 관측할 "
        "수 있는 실제 패널/시계열 데이터가 확보되면 이 함수를 구현하세요. "
        "지금 단계의 주모델은 baseline_models.train_and_compare_models()입니다."
    )


def check_proportional_hazards_assumption(cox_model: Any, df: pd.DataFrame, **kwargs: Any):
    """Schoenfeld residual test (docs/04). Cox 모델이 활성화된 이후에만 의미가 있다."""
    raise NotImplementedError(
        "Cox 모델이 아직 비활성 상태입니다(cox_trainer.train_cox_model 참고)."
    )
