import logging
import pathlib

import numpy as np
import pandas as pd
import pytest

from pipeline.layer0_data_contract import cleaner, profiler
from pipeline.layer1_features import feature_engineer as fe


@pytest.fixture(scope="module")
def config():
    return profiler.load_column_config()


class TestSafeDivide:
    """docs/03: "모든 나눗셈 연산은 분모=0 케이스를 명시적으로 처리"."""

    def test_normal_division(self):
        result = fe.safe_divide(pd.Series([10.0, 20.0]), pd.Series([2.0, 4.0]))
        assert result.tolist() == [5.0, 5.0]

    def test_zero_denominator_returns_fill_value(self):
        result = fe.safe_divide(pd.Series([10.0, 20.0]), pd.Series([0.0, 4.0]))
        assert result.tolist() == [0.0, 5.0]

    def test_nan_denominator_returns_fill_value(self):
        result = fe.safe_divide(pd.Series([10.0]), pd.Series([np.nan]))
        assert result.tolist() == [0.0]

    def test_custom_fill_value(self):
        result = fe.safe_divide(pd.Series([10.0]), pd.Series([0.0]), fill_value=-1.0)
        assert result.tolist() == [-1.0]


class TestDerivedFeaturesWithZeroDenominator:
    def test_income_growth_rate_handles_zero_previous_income(self):
        df = pd.DataFrame({"추정 연소득": [1000, 2000], "2년전 추정 연소득 금액": [0, 1000]})
        result = fe.compute_income_growth_rate(df)
        assert result.iloc[0] == 0.0  # 분모=0 -> 0 처리
        assert result.iloc[1] == 1.0  # (2000-1000)/1000

    def test_installment_dependency_zero_when_no_card_spending(self):
        """doc03 명시: 분모=0(카드소비 없음)이면 0 처리."""
        df = pd.DataFrame({
            "최근 12개월 할부이용금액": [500, 300],
            "최근 12개월 신용카드소비금액": [0, 1000],
        })
        result = fe.compute_installment_dependency(df)
        assert result.iloc[0] == 0.0
        assert result.iloc[1] == 0.3


class TestIndividualDerivedFeatures:
    def test_job_change_risk_direction_and_magnitude(self):
        """소득이 줄면 양수(위험), 늘면 음수(안전) - 도메인지수 '높을수록 위험' 방향과
        일치해야 하고(직장변동위험도는 PROTECTIVE_FEATURES에 없어 z-score가 반전되지
        않으므로), 감소폭이 클수록(추정연소득 대비) 위험값도 커져야 한다(sign()만 쓰면
        감소폭 크기가 버려지는 문제 수정)."""
        df = pd.DataFrame({
            "2년내 직장명이력건수": [2, 3, 2, 0],
            "2년내 이직후 소득 증감액": [-100, 200, -500, 0],
            "추정 연소득": [1000, 1000, 1000, 1000],
        })
        result = fe.compute_job_change_risk(df)
        assert result.iloc[0] == pytest.approx(0.2)  # 소득 10% 감소 -> 위험 방향(양수)
        assert result.iloc[1] == pytest.approx(-0.6)  # 소득 20% 증가 -> 안전 방향(음수)
        assert result.iloc[2] == pytest.approx(1.0)  # 소득 50% 감소(더 큰 감소폭) -> 더 큰 위험값
        assert result.iloc[0] < result.iloc[2]  # 감소폭이 클수록 위험값도 커짐(크기 정보 보존)
        assert result.iloc[3] == 0.0  # 이직 없음 -> 0

    def test_job_change_risk_zero_income_falls_back_to_safe_divide(self):
        df = pd.DataFrame({
            "2년내 직장명이력건수": [1],
            "2년내 이직후 소득 증감액": [-50],
            "추정 연소득": [0],
        })
        result = fe.compute_job_change_risk(df)
        assert result.tolist() == [0.0]

    def test_housing_price_exposure_registered_but_excluded_from_domain_indices(self):
        """미션 지시: 도메인지수 5종 구성에는 넣지 않는다(GMM 재학습 리스크 회피)."""
        assert "전세가변동노출" in fe.FEATURE_COMPUTERS
        for constituent_columns in fe.DOMAIN_INDEX_DEFINITIONS.values():
            assert "전세가변동노출" not in constituent_columns

    def test_housing_price_exposure_missing_burden_column_returns_nan(self, config):
        df = pd.DataFrame({"거주지 시군구 코드": [26110]})
        result = fe.compute_housing_price_exposure(df, config)
        assert result.isna().all()

    def test_housing_price_exposure_no_reference_data_returns_nan(self, config, monkeypatch):
        monkeypatch.setattr(fe.rent_price_loader, "load_jeonse_trend_parquet", lambda *a, **k: None)
        df = pd.DataFrame({"주거가격부담률": [0.5], "거주지 시군구 코드": [26110]})
        result = fe.compute_housing_price_exposure(df, config)
        assert result.isna().all()

    def test_housing_price_exposure_sign_direction_falling_jeonse_increases_exposure(self, config, monkeypatch):
        """전세가 하락(변동률<0) 지역일수록 -전세가변동률이 양수가 되어, 이미 주거비
        부담이 큰 사람의 노출도가 커져야 한다(전세가변동노출 = 주거가격부담률 ×
        (-전세가변동률))."""
        jeonse_trend_df = pd.DataFrame({"시군구코드": [26110, 26140], "전세가변동률": [-0.10, 0.10]})
        monkeypatch.setattr(fe.rent_price_loader, "load_jeonse_trend_parquet", lambda *a, **k: jeonse_trend_df)

        df = pd.DataFrame({
            "주거가격부담률": [0.5, 0.5],
            "거주지 시군구 코드": [26110, 26140],  # 26110=하락지역, 26140=상승지역
        })
        result = fe.compute_housing_price_exposure(df, config)

        assert result.iloc[0] == pytest.approx(0.05)  # 0.5 * -(-0.10)
        assert result.iloc[1] == pytest.approx(-0.05)  # 0.5 * -(0.10)

    def test_housing_price_exposure_unmatched_sigungu_is_nan_not_zero(self, config, monkeypatch):
        jeonse_trend_df = pd.DataFrame({"시군구코드": [26110], "전세가변동률": [-0.10]})
        monkeypatch.setattr(fe.rent_price_loader, "load_jeonse_trend_parquet", lambda *a, **k: jeonse_trend_df)

        df = pd.DataFrame({"주거가격부담률": [0.5], "거주지 시군구 코드": [99999]})  # 매칭 안 되는 코드
        result = fe.compute_housing_price_exposure(df, config)

        assert result.isna().all()

    def test_asset_debt_gap_simple_subtraction(self):
        df = pd.DataFrame({
            "순자산평가금액(주택)": [1_000_000],
            "신용대출-총대출잔액": [200_000],
            "주택담보대출-총대출잔액": [300_000],
            "정책자금대출-총대출잔액": [0],
        })
        result = fe.compute_asset_debt_gap(df)
        assert result.iloc[0] == 500_000

    def test_delinquency_severity_flags_the_only_delinquent_row_higher(self):
        df = pd.DataFrame({
            "대출연체건수": [0, 0, 0, 10],
            "카드연체건수": [0, 0, 0, 0],
            "연체일수": [0, 0, 0, 5],
            "대출연체금액": [0, 0, 0, 1000],
            "카드연체금액": [0, 0, 0, 0],
        })
        result = fe.compute_delinquency_severity(df, min_sample=1)
        assert result.iloc[3] > result.iloc[0]
        assert result.iloc[0] == result.iloc[1] == result.iloc[2]


class TestResidenceWorkplaceMismatch:
    def test_uses_sigungu_when_dong_absent(self, config):
        df = pd.DataFrame({
            "거주지 시군구 코드": [26260, 26230, 26350],
            "근무지 시군구 코드": [26260, 26440, 26350],
        })
        result = fe.compute_residence_workplace_mismatch(df, config)
        assert result.tolist() == [False, True, False]

    def test_prefers_dong_over_sigungu_when_both_present(self, config):
        """행정동이 있으면 우선 사용 - 시군구코드만으로는 못 잡는 불일치도 잡아야 한다."""
        df = pd.DataFrame({
            "거주지행정동": ["11110", "11110"],
            "근무지행정동": ["11110", "99999"],
            "거주지 시군구 코드": [11000, 11000],
            "근무지 시군구 코드": [11000, 11000],  # 시군구만 보면 둘 다 일치로 보임
        })
        result = fe.compute_residence_workplace_mismatch(df, config)
        assert result.tolist() == [False, True]

    def test_returns_all_false_when_no_region_columns_available(self, config):
        df = pd.DataFrame({"성별": [1, 2]})
        result = fe.compute_residence_workplace_mismatch(df, config)
        assert result.tolist() == [False, False]


class TestDiagnosticOnlyFeatureSeparation:
    """doc03: "연체심각도는 반드시 리스크 예측모델의 피처 목록에서 제외되어야 함"."""

    def test_get_diagnostic_only_features(self):
        assert fe.get_diagnostic_only_features() == ["연체심각도"]

    def test_assert_raises_when_diagnostic_feature_used(self):
        with pytest.raises(AssertionError):
            fe.assert_no_diagnostic_leakage(["연체심각도", "소득증감률"])

    def test_assert_passes_for_clean_feature_list(self):
        fe.assert_no_diagnostic_leakage(["소득증감률", "상환부담률"])  # 예외 없이 통과


class TestLeakyDomainIndices:
    """2026-07-10 실스케일(n=1500) 리허설에서 발견: 신용취약지수가 연체심각도를
    구성변수로 포함해서 리스크모델에 연체 정보를 우회 누수시키고 있었다(held-out
    LightGBM PR-AUC 0.999로 발견). 리터럴 컬럼명 매칭만으로는 못 잡는 누수라
    별도 함수로 도메인지수 5종 전수조사를 강제한다."""

    def test_only_credit_vulnerability_index_is_leaky(self):
        # 신용취약지수만 연체심각도(진단전용)를 구성변수로 포함한다 - 나머지 4개
        # 도메인지수(주거비압박/부채상환위험/소득변동성/소비압박)는 누수 없음.
        assert fe.get_leaky_domain_indices() == ["신용취약지수"]

    def test_assert_raises_when_leaky_domain_index_used(self):
        with pytest.raises(AssertionError):
            fe.assert_no_domain_index_leakage(["신용취약지수", "소득증감률"])

    def test_assert_passes_for_other_domain_indices(self):
        # GMM 클러스터링 입력으로는 5개 다 허용되지만, 리스크모델 피처 게이트
        # 관점에서는 신용취약지수를 제외한 나머지 4개는 깨끗해야 한다.
        fe.assert_no_domain_index_leakage(
            ["주거비압박지수", "부채상환위험지수", "소득변동성지수", "소비압박지수"]
        )


class TestThinFilerAdjustedScore:
    def test_non_thin_filer_rows_keep_original_score(self):
        df = pd.DataFrame({
            "신용평점": [700, 650, 0],
            "Thin Filer 여부": [0, 0, 1],
            "추정 연소득": [3000, 3200, 2800],
        })
        result = fe.compute_thin_filer_adjusted_score(
            df, predictor_cols=["추정 연소득"], min_train_sample=30
        )
        assert result.iloc[0] == 700
        assert result.iloc[1] == 650

    def test_thin_filer_row_becomes_nan_when_train_sample_too_small(self):
        df = pd.DataFrame({
            "신용평점": [700, 650, 0],
            "Thin Filer 여부": [0, 0, 1],
            "추정 연소득": [3000, 3200, 2800],
        })
        result = fe.compute_thin_filer_adjusted_score(
            df, predictor_cols=["추정 연소득"], min_train_sample=30
        )
        assert pd.isna(result.iloc[2])

    def test_thin_filer_row_predicted_when_train_sample_sufficient(self):
        n_train = 40
        income = np.linspace(1000, 5000, n_train)
        score = 500 + 0.05 * income  # 결정론적 선형관계(노이즈 없음)
        df = pd.DataFrame({
            "추정 연소득": list(income) + [3000.0],
            "신용평점": list(score) + [0.0],
            "Thin Filer 여부": [0] * n_train + [1],
        })
        result = fe.compute_thin_filer_adjusted_score(
            df, predictor_cols=["추정 연소득"], min_train_sample=30
        )
        expected_last = 500 + 0.05 * 3000
        assert result.iloc[-1] == pytest.approx(expected_last, abs=1e-6)
        assert (result.iloc[:-1].to_numpy() == df["신용평점"].iloc[:-1].to_numpy()).all()

    def test_no_thin_filer_column_returns_original_scores(self):
        df = pd.DataFrame({"신용평점": [700, 0]})
        result = fe.compute_thin_filer_adjusted_score(df)
        assert result.tolist() == [700, 0]


class TestDomainIndexDirection:
    """2026-07-08 사용자 확인: 보호요인은 부호 반전 -> 지수는 항상 "높을수록 위험"."""

    def test_lower_credit_score_yields_higher_credit_vulnerability_index(self):
        df = pd.DataFrame({
            "신용평점": [300, 500, 900],  # 낮음 -> 중간 -> 높음
            "Thin Filer 여부": [0, 0, 0],
            "연체심각도": [0, 0, 0],
        })
        result = fe.compute_domain_index(
            df, fe.DOMAIN_INDEX_DEFINITIONS["신용취약지수"], fe.PROTECTIVE_FEATURES, min_sample=1
        )
        # 신용평점이 낮을수록(위험할수록) 지수가 높아야 한다
        assert result.iloc[0] > result.iloc[1] > result.iloc[2]

    def test_missing_constituent_column_is_skipped_not_fatal(self):
        df = pd.DataFrame({"추정DTI": [0.1, 0.5], "추정 LTV": [0.3, 0.6]})
        result = fe.compute_domain_index(
            df, fe.DOMAIN_INDEX_DEFINITIONS["부채상환위험지수"], fe.PROTECTIVE_FEATURES, min_sample=1
        )
        assert not result.isna().all()


class TestSmallSampleWarning:
    """doc 요청: 표본 수가 적을 때 경고 로그를 남기는 방어 로직."""

    def test_zscore_logs_warning_when_sample_small(self, caplog):
        with caplog.at_level(logging.WARNING, logger="pipeline.layer1_features.feature_engineer"):
            fe.safe_zscore(pd.Series([1, 2, 3, 4, 5]), min_sample=20)
        assert any("표본 부족" in r.message for r in caplog.records)

    def test_zscore_no_warning_when_sample_sufficient(self, caplog):
        with caplog.at_level(logging.WARNING, logger="pipeline.layer1_features.feature_engineer"):
            fe.safe_zscore(pd.Series(range(25)), min_sample=20)
        assert not any("표본 부족" in r.message for r in caplog.records)


class TestEngineerFeaturesEndToEnd:
    def test_real_sample_csv_produces_all_features_without_error(self):
        sample_path = pathlib.Path(__file__).parents[3] / "data" / "sample.csv"
        raw = pd.read_csv(sample_path)
        config = profiler.load_column_config()
        cleaned, _ = cleaner.clean_dataset(raw, config)

        featured, report = fe.engineer_features(cleaned, config)

        assert len(featured) == len(cleaned)  # 행 손실 없음
        assert set(cleaned.columns).issubset(set(featured.columns))  # 원본 컬럼 보존
        for col in report["derived_features"]:
            assert col in featured.columns
        for col in report["domain_indices"]:
            assert col in featured.columns
        assert report["diagnostic_only_features"] == ["연체심각도"]

    def test_diagnostic_feature_not_silently_included_in_derived_list_misuse(self):
        """연체심각도가 derived_features에는 있지만, 그 목록을 그대로 예측모델
        피처로 쓰면 assert가 걸려야 한다(사용자가 요청한 안전장치)."""
        sample_path = pathlib.Path(__file__).parents[3] / "data" / "sample.csv"
        raw = pd.read_csv(sample_path)
        config = profiler.load_column_config()
        cleaned, _ = cleaner.clean_dataset(raw, config)
        _, report = fe.engineer_features(cleaned, config)

        with pytest.raises(AssertionError):
            fe.assert_no_diagnostic_leakage(report["derived_features"])

        safe_features = [c for c in report["derived_features"] if c not in fe.get_diagnostic_only_features()]
        fe.assert_no_diagnostic_leakage(safe_features)  # 예외 없이 통과
