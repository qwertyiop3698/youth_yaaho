"""Layer 2-B - 모델 투입 피처 게이트.

Cox/GMM 등 개인별 리스크모델에 피처를 넣기 전에 아래 4가지를 전부 걸러야 한다.
각각 이유가 다른 위험이라 하나라도 빠뜨리면 안 된다:

    1. cleaner.get_leakage_columns()                   - 연체 원본 컬럼(타겟 정의 전용, docs/04)
    2. cleaner.get_quasi_identifier_columns()          - 시군구코드/행정동(재식별 위험, docs/02)
    3. feature_engineer.get_diagnostic_only_features() - 연체심각도(진단모델 전용, docs/03)
    4. feature_engineer.get_leaky_domain_indices()     - 신용취약지수 등 연체심각도를 구성변수로
       포함하는 도메인지수(2026-07-10 실스케일 리허설에서 발견한 우회 누수, 리터럴 컬럼명
       매칭만으로는 안 잡힘 - held-out LightGBM PR-AUC 0.999로 발견)

2026-07-08 사용자 요청: 매번 여러 개를 따로 호출하다 하나 빠뜨리는 실수를 막기 위해
`get_model_ready_features()` 하나로 통합한다. 이 함수가 반환하는 목록은 내부적으로
4개 assert를 전부 통과했으므로, Layer2/3에서 그대로 피처 목록으로 써도 안전하다.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from ..layer0_data_contract import cleaner as layer0_cleaner
from ..layer0_data_contract.profiler import load_column_config as load_layer0_config
from ..layer1_features import feature_engineer as fe


def get_model_ready_features(df: pd.DataFrame, layer0_config: dict[str, Any] | None = None) -> list[str]:
    """df의 컬럼 중 개인별 리스크모델(Cox/GMM/LightGBM 등)에 안전하게 넣을 수 있는
    컬럼만 골라 반환한다. 반환 전 3개 assert(get_leakage/get_quasi_identifier/
    get_diagnostic_only)를 전부 통과시키므로, 결과를 그대로 신뢰해도 된다.
    """
    layer0_config = layer0_config or load_layer0_config()

    excluded = (
        set(layer0_cleaner.get_leakage_columns(layer0_config))
        | set(layer0_cleaner.get_quasi_identifier_columns(layer0_config))
        | set(fe.get_diagnostic_only_features())
        | set(fe.get_leaky_domain_indices())
    )
    candidate_columns = [c for c in df.columns if c not in excluded]

    layer0_cleaner.assert_no_leakage(candidate_columns, layer0_config)
    layer0_cleaner.assert_no_quasi_identifier_leakage(candidate_columns, layer0_config)
    fe.assert_no_diagnostic_leakage(candidate_columns)
    fe.assert_no_domain_index_leakage(candidate_columns)

    return candidate_columns
