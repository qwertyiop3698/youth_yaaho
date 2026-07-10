import pathlib

import pandas as pd
import pytest

from pipeline.layer0_data_contract import cleaner, profiler
from pipeline.layer1_features import feature_engineer as fe
from pipeline.layer2b_risk_model import feature_gate


@pytest.fixture(scope="module")
def featured_sample():
    sample_path = pathlib.Path(__file__).parents[3] / "data" / "sample.csv"
    raw = pd.read_csv(sample_path)
    config = profiler.load_column_config()
    cleaned, _ = cleaner.clean_dataset(raw, config)
    featured, _ = fe.engineer_features(cleaned, config)
    return featured, config


class TestGetModelReadyFeatures:
    def test_excludes_leakage_quasi_identifier_and_diagnostic_columns(self, featured_sample):
        featured, config = featured_sample
        result = feature_gate.get_model_ready_features(featured, config)

        leakage = set(cleaner.get_leakage_columns(config))
        quasi = set(cleaner.get_quasi_identifier_columns(config))
        diagnostic = set(fe.get_diagnostic_only_features())

        assert not (leakage & set(result))
        assert not (quasi & set(result))
        assert not (diagnostic & set(result))

    def test_excludes_leaky_domain_indices_but_keeps_other_four(self, featured_sample):
        # 2026-07-10 발견: 신용취약지수는 연체심각도를 구성변수로 포함해 리스크모델에
        # 연체 정보를 우회 누수시킨다 - 리스크모델 피처에서는 제외하되, 나머지 4개
        # 도메인지수(GMM 공통 입력, docs/03)는 그대로 남아있어야 한다.
        featured, config = featured_sample
        result = feature_gate.get_model_ready_features(featured, config)

        assert "신용취약지수" not in result
        for clean_index in ["주거비압박지수", "부채상환위험지수", "소득변동성지수", "소비압박지수"]:
            assert clean_index in result

    def test_result_still_contains_legitimate_features(self, featured_sample):
        featured, config = featured_sample
        result = feature_gate.get_model_ready_features(featured, config)
        assert "추정DTI" in result
        assert "소득증감률" in result
        assert "성별" in result  # 준식별정보 아님(위치조인키 아닌 인구통계 공변량)

    def test_result_passes_all_four_asserts_directly(self, featured_sample):
        featured, config = featured_sample
        result = feature_gate.get_model_ready_features(featured, config)
        # get_model_ready_features 내부에서 이미 검증하지만, 결과를 재검증해도 통과해야 함
        cleaner.assert_no_leakage(result, config)
        cleaner.assert_no_quasi_identifier_leakage(result, config)
        fe.assert_no_diagnostic_leakage(result)
        fe.assert_no_domain_index_leakage(result)
