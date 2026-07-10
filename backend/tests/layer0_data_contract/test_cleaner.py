import pathlib

import pandas as pd
import pytest

from pipeline.layer0_data_contract import cleaner, profiler


@pytest.fixture(scope="module")
def config():
    return profiler.load_column_config()


class TestZeroIsNormalColumns:
    """docs/02: 대출/카드/연체 그룹은 0=정상, 결측 아님 -> 처리/플래그 없이 원본 그대로."""

    def test_loan_delinquency_columns_untouched(self, config):
        df = pd.DataFrame({"대출연체건수": [0, 0, 0], "카드연체건수": [0, 0, 0]})
        cleaned, _ = cleaner.clean_dataset(df, config)

        pd.testing.assert_series_equal(cleaned["대출연체건수"], df["대출연체건수"])
        assert "대출연체건수_was_missing" not in cleaned.columns
        assert "카드연체건수_was_missing" not in cleaned.columns

    def test_leakage_columns_exposed_and_assertable(self, config):
        """docs/04 데이터 누수 차단 규칙(assert)이 Layer0 config에서 그대로 도출되는지 확인."""
        leakage = cleaner.get_leakage_columns(config)
        assert set(leakage) == {"대출연체건수", "카드연체건수", "연체일수", "대출연체금액", "카드연체금액"}

        with pytest.raises(AssertionError):
            cleaner.assert_no_leakage(["대출연체건수", "추정DTI"], config)

        cleaner.assert_no_leakage(["추정DTI", "신용평점"], config)  # 예외 없이 통과해야 함


class TestQuasiIdentifierColumns:
    """지역 조인키(시군구코드/행정동)는 조인/spatial CV/행정 집계용으로는 유지하되,
    Cox/GMM 등 개인별 리스크모델의 raw feature 목록에서는 분리해야 한다(재식별 위험)."""

    def test_quasi_identifier_columns_are_the_four_location_join_keys(self, config):
        quasi = cleaner.get_quasi_identifier_columns(config)
        assert set(quasi) == {
            "거주지 시군구 코드", "근무지 시군구 코드", "거주지행정동", "근무지행정동",
        }

    def test_quasi_identifier_columns_still_kept_in_clean_dataset(self, config):
        """clean_dataset 결과물 자체에는 조인/집계용으로 남아있어야 한다(삭제 안 함)."""
        df = pd.DataFrame({
            "거주지 시군구 코드": [26260, 26230],
            "근무지 시군구 코드": [26260, 26230],
        })
        cleaned, _ = cleaner.clean_dataset(df, config)
        assert "거주지 시군구 코드" in cleaned.columns
        assert "근무지 시군구 코드" in cleaned.columns

    def test_assert_raises_when_quasi_identifier_used_as_raw_model_feature(self, config):
        with pytest.raises(AssertionError):
            cleaner.assert_no_quasi_identifier_leakage(
                ["거주지 시군구 코드", "추정DTI"], config
            )

    def test_assert_passes_for_legitimate_model_features(self, config):
        # 성별/연령대 등은 PII구분=준식별정보이긴 하지만 인구통계 공변량으로 정상 사용되므로
        # get_quasi_identifier_columns() 대상이 아니다(위치 조인키에만 한정).
        cleaner.assert_no_quasi_identifier_leakage(
            ["성별", "연령대", "추정DTI", "신용평점"], config
        )

    def test_leakage_and_quasi_identifier_sets_are_disjoint(self, config):
        assert set(cleaner.get_leakage_columns(config)).isdisjoint(
            cleaner.get_quasi_identifier_columns(config)
        )


class TestSentinelColumns:
    """docs/02: -99999999 sentinel은 결측 처리 대상 -> 지역 median 대체 + 플래그."""

    def test_sentinel_values_replaced_and_flagged(self, config):
        col = "2년내 현거주지평균전세거래가"
        df = pd.DataFrame({
            col: [-99999999, -99999999, -99999999, -99999999, 20000],
            "거주지 시군구 코드": [26260, 26230, 26260, 26350, 26350],
        })
        cleaned, _ = cleaner.clean_dataset(df, config)
        flag_col = f"{col}_was_missing"

        assert cleaned[flag_col].tolist() == [1, 1, 1, 1, 0]
        # 표본이 지역그룹 최소치에 못 미쳐 전체 median(유일 정상값 20000)으로 대체됨
        assert (cleaned[col] == 20000).all()

    def test_non_sentinel_rows_unaffected(self, config):
        col = "총자산평가금액(주택)"
        df = pd.DataFrame({
            col: [100000, 200000, 150000, 300000, 250000],
            "거주지 시군구 코드": [26260, 26230, 26260, 26350, 26350],
        })
        cleaned, _ = cleaner.clean_dataset(df, config)

        assert cleaned[col].tolist() == df[col].tolist()
        assert cleaned[f"{col}_was_missing"].sum() == 0


class TestThinFilerCreditScore:
    """docs/02: 신용평점 0/저평점은 Thin Filer 여부와 교차 확인해서 분리 처리."""

    def test_thin_filer_row_keeps_raw_value_with_structural_flag(self, config):
        df = pd.DataFrame({
            "신용평점": [0, 700, 0, 650],
            "Thin Filer 여부": [1, 0, 0, 0],
        })
        cleaned, _ = cleaner.clean_dataset(df, config)

        # Thin Filer=1(구조적으로 산출 불가) -> 원본값 그대로 유지, 플래그만 추가
        assert cleaned.loc[0, "신용평점"] == 0
        assert cleaned.loc[0, "신용평점_was_missing"] == 1

        # Thin Filer=0인데 0점 -> 진짜 이상값으로 median 대체
        assert cleaned.loc[2, "신용평점"] != 0
        assert cleaned.loc[2, "신용평점_was_missing"] == 1

        # 정상 값은 변경 없음
        assert cleaned.loc[1, "신용평점"] == 700
        assert cleaned.loc[1, "신용평점_was_missing"] == 0
        assert cleaned.loc[3, "신용평점"] == 650
        assert cleaned.loc[3, "신용평점_was_missing"] == 0


class TestNoOriginalDataLoss:
    """docs/02 구현원칙 1: 원본값/행 삭제 금지(drop_column으로 명시된 컬럼 제외)."""

    def test_no_rows_dropped(self, config):
        df = pd.DataFrame({"성별": [1, 2, None]})
        cleaned, _ = cleaner.clean_dataset(df, config)
        assert len(cleaned) == len(df)

    def test_planned_drop_column_removed(self, config):
        df = pd.DataFrame({"추정가구원수": [1, 2, 3]})
        cleaned, _ = cleaner.clean_dataset(df, config)
        assert "추정가구원수" not in cleaned.columns

    def test_join_key_sigungu_columns_preserved_despite_spec_drop(self, config):
        """명세는 시군구코드 컬럼을 '열 삭제' 대상으로 표시하지만, docs/02 조인키
        이중화 원칙 때문에 Layer0은 이를 override해서 유지해야 한다."""
        df = pd.DataFrame({
            "거주지 시군구 코드": [26260, 26230],
            "근무지 시군구 코드": [26260, 26230],
        })
        cleaned, _ = cleaner.clean_dataset(df, config)
        assert "거주지 시군구 코드" in cleaned.columns
        assert "근무지 시군구 코드" in cleaned.columns


class TestAmbiguousIncome:
    def test_income_zero_flagged_and_imputed(self, config):
        df = pd.DataFrame({"추정월소득": [0, 300, 250, 0, 180]})
        cleaned, _ = cleaner.clean_dataset(df, config)
        assert cleaned["추정월소득_was_missing"].tolist() == [1, 0, 0, 1, 0]
        assert cleaned.loc[0, "추정월소득"] != 0


class TestProofIncomeFlagOnly:
    def test_proof_income_zero_kept_with_custom_flag(self, config):
        df = pd.DataFrame({"증빙연소득": [0, 0, 500]})
        cleaned, _ = cleaner.clean_dataset(df, config)
        assert cleaned["증빙연소득"].tolist() == [0, 0, 500]  # 원본 유지(대체 안 함)
        assert cleaned["증빙연소득_증빙없음"].tolist() == [1, 1, 0]


def test_real_sample_csv_cleans_without_error():
    sample_path = pathlib.Path(__file__).parents[3] / "data" / "sample.csv"
    df = pd.read_csv(sample_path)
    cfg = profiler.load_column_config()

    cleaned, report = cleaner.clean_dataset(df, cfg)

    assert len(cleaned) == len(df)  # 행 손실 없음(5행 그대로)
    assert len(cleaned.columns) > len(df.columns)  # was_missing류 플래그 컬럼 추가됨
    assert set(cleaner.get_leakage_columns(cfg)).issubset(df.columns)
