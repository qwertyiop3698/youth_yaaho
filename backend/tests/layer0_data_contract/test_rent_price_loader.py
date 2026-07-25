import numpy as np
import pandas as pd
import pytest

from pipeline.layer0_data_contract import rent_price_loader as rpl

# 8개 분기(직전 4 + 최근 4) - (year, quarter_of_year) 튜플로 표현
PRIOR_QUARTERS = [(2024, 1), (2024, 2), (2024, 3), (2024, 4)]
RECENT_QUARTERS = [(2025, 1), (2025, 2), (2025, 3), (2025, 4)]
ALL_8_QUARTERS = PRIOR_QUARTERS + RECENT_QUARTERS


def _yyyymm(year: int, q: int) -> int:
    return year * 100 + (q - 1) * 3 + 1


def _jeonse_rows(
    sigungu: int,
    quarters: list[tuple[int, int]],
    value: float,
    n_per_quarter: int = 10,
    housing_type: str = "아파트",
) -> list[dict]:
    rows = []
    for year, q in quarters:
        for _ in range(n_per_quarter):
            rows.append({
                "시군구코드": sigungu,
                "전세여부": 1,
                "계약년월": _yyyymm(year, q),
                "㎡당보증금(만원)": value,
                "주택유형": housing_type,
                "계약구분": "신규",
                "보증금(만원)": 10000,
                "종전계약 보증금(만원)": np.nan,
            })
    return rows


def _renewal_rows(sigungu: int, n: int, deposit: float, prior_deposit: float) -> list[dict]:
    return [
        {
            "시군구코드": sigungu,
            "전세여부": 1,
            "계약년월": 202501,
            "㎡당보증금(만원)": 300.0,
            "주택유형": "아파트",
            "계약구분": "갱신",
            "보증금(만원)": deposit,
            "종전계약 보증금(만원)": prior_deposit,
        }
        for _ in range(n)
    ]


class TestLoadRentCsv:
    def test_missing_required_column_raises_clear_error(self, tmp_path):
        bad_csv = tmp_path / "bad.csv"
        pd.DataFrame({"시군구코드": [26110]}).to_csv(bad_csv, index=False, encoding="utf-8-sig")

        with pytest.raises(ValueError, match="필요한 컬럼이 없습니다"):
            rpl.load_rent_csv(bad_csv)


class TestComputeJeonsePriceTrend:
    def test_price_increase_is_captured_correctly(self):
        rows = _jeonse_rows(26110, PRIOR_QUARTERS, value=300.0) + _jeonse_rows(26110, RECENT_QUARTERS, value=330.0)
        df = rpl._add_quarter_columns(pd.DataFrame(rows))
        quarterly = rpl._compute_quarterly_representative(df)

        trend = rpl.compute_jeonse_price_trend(quarterly)

        row = trend[trend["시군구코드"] == 26110].iloc[0]
        assert row["전세가변동률"] == pytest.approx(0.10, abs=1e-6)  # (330-300)/300
        assert row["insufficient_reason"] is None

    def test_price_decrease_yields_negative_rate(self):
        rows = _jeonse_rows(26110, PRIOR_QUARTERS, value=300.0) + _jeonse_rows(26110, RECENT_QUARTERS, value=270.0)
        df = rpl._add_quarter_columns(pd.DataFrame(rows))
        quarterly = rpl._compute_quarterly_representative(df)

        trend = rpl.compute_jeonse_price_trend(quarterly)

        row = trend[trend["시군구코드"] == 26110].iloc[0]
        assert row["전세가변동률"] == pytest.approx(-0.10, abs=1e-6)

    def test_fewer_than_8_quarters_yields_nan_with_reason(self):
        """분기 하나짜리 비교는 노이즈가 커서 금지 - 8분기(최근4+직전4) 미만이면 NaN."""
        rows = _jeonse_rows(26110, PRIOR_QUARTERS[:3], value=300.0)  # 3분기뿐
        df = rpl._add_quarter_columns(pd.DataFrame(rows))
        quarterly = rpl._compute_quarterly_representative(df)

        trend = rpl.compute_jeonse_price_trend(quarterly)

        row = trend[trend["시군구코드"] == 26110].iloc[0]
        assert pd.isna(row["전세가변동률"])
        assert "8" in row["insufficient_reason"] or "4" in row["insufficient_reason"]

    def test_insufficient_transaction_count_in_window_yields_nan(self):
        """8분기를 다 채워도 거래건수가 너무 적으면(윈도우당 30건 미만) NaN."""
        rows = _jeonse_rows(26110, ALL_8_QUARTERS, value=300.0, n_per_quarter=2)  # 4분기 합=8건 < 30
        df = rpl._add_quarter_columns(pd.DataFrame(rows))
        quarterly = rpl._compute_quarterly_representative(df)

        trend = rpl.compute_jeonse_price_trend(quarterly)

        row = trend[trend["시군구코드"] == 26110].iloc[0]
        assert pd.isna(row["전세가변동률"])
        assert "거래건수 부족" in row["insufficient_reason"]

    def test_uses_most_recent_quarters_even_with_extra_older_data(self):
        """9번째(더 오래된) 분기가 섞여 있어도 "가장 최근 8개"만 써야 한다 - 당월
        일부만 포함된 불완전 최신 분기가 있어도 "최신부터 거꾸로 8개" 규칙이라
        별도 보정 없이 처리된다는 설계를 검증."""
        extra_old = _jeonse_rows(26110, [(2023, 4)], value=999.0)  # 아주 오래된 이상치
        rows = extra_old + _jeonse_rows(26110, PRIOR_QUARTERS, value=300.0) + _jeonse_rows(26110, RECENT_QUARTERS, value=330.0)
        df = rpl._add_quarter_columns(pd.DataFrame(rows))
        quarterly = rpl._compute_quarterly_representative(df)

        trend = rpl.compute_jeonse_price_trend(quarterly)

        row = trend[trend["시군구코드"] == 26110].iloc[0]
        assert row["전세가변동률"] == pytest.approx(0.10, abs=1e-6)  # 2023Q4(999) 영향 없어야 함
        assert row["n_quarters_available"] == 9


class TestComputeQuarterlyRepresentativeFixedWeight:
    def test_missing_housing_type_in_quarter_renormalizes_among_present_types(self):
        """그 분기에 특정 주택유형 거래가 아예 없으면, 존재하는 유형들의 비중으로
        재정규화해야 한다(없는 유형을 0으로 취급해 대표값을 부당하게 낮추지 않음)."""
        rows = (
            _jeonse_rows(26110, [(2025, 1)], value=300.0, housing_type="아파트", n_per_quarter=8)
            + _jeonse_rows(26110, [(2025, 1)], value=200.0, housing_type="오피스텔", n_per_quarter=2)
            # 연립다세대는 이 분기에 거래 없음
        )
        df = rpl._add_quarter_columns(pd.DataFrame(rows))
        quarterly = rpl._compute_quarterly_representative(df)

        row = quarterly.iloc[0]
        # 두 유형 중앙값(300, 200)의 재정규화된 가중합이라 200~300 사이여야 한다
        assert 200.0 < row["representative_value"] < 300.0


class TestComputeRenewalDepositChangeRate:
    def test_median_change_rate_computed_when_sample_sufficient(self):
        rows = _renewal_rows(26110, 30, deposit=11000.0, prior_deposit=10000.0)  # +10%
        df = pd.DataFrame(rows)

        result = rpl.compute_renewal_deposit_change_rate(df)

        row = result[result["시군구코드"] == 26110].iloc[0]
        assert row["갱신보증금변동률"] == pytest.approx(0.10, abs=1e-6)
        assert row["n_renewal_contracts"] == 30

    def test_below_30_samples_yields_nan_with_count_in_reason(self):
        rows = _renewal_rows(26110, 29, deposit=11000.0, prior_deposit=10000.0)
        df = pd.DataFrame(rows)

        result = rpl.compute_renewal_deposit_change_rate(df)

        row = result[result["시군구코드"] == 26110].iloc[0]
        assert pd.isna(row["갱신보증금변동률"])
        assert "29" in row["insufficient_reason"]

    def test_non_renewal_rows_are_excluded(self):
        rows = _renewal_rows(26110, 30, deposit=11000.0, prior_deposit=10000.0)
        rows += _jeonse_rows(26110, [(2025, 1)], value=300.0, n_per_quarter=5)  # 계약구분=신규
        df = pd.DataFrame(rows)

        result = rpl.compute_renewal_deposit_change_rate(df)

        row = result[result["시군구코드"] == 26110].iloc[0]
        assert row["n_renewal_contracts"] == 30  # 신규 5건은 안 섞임

    def test_zero_previous_deposit_excluded_to_avoid_division_by_zero(self):
        rows = _renewal_rows(26110, 30, deposit=11000.0, prior_deposit=10000.0)
        rows += _renewal_rows(26110, 5, deposit=5000.0, prior_deposit=0.0)  # 0으로 나누기 방지 대상
        df = pd.DataFrame(rows)

        result = rpl.compute_renewal_deposit_change_rate(df)

        row = result[result["시군구코드"] == 26110].iloc[0]
        assert row["n_renewal_contracts"] == 30  # 종전계약 보증금=0인 5건은 제외됨
        assert not np.isinf(row["갱신보증금변동률"])


class TestLoadJeonseTrendParquet:
    def test_missing_file_returns_none(self, tmp_path):
        assert rpl.load_jeonse_trend_parquet(tmp_path / "missing.parquet") is None

    def test_existing_file_loaded(self, tmp_path):
        path = tmp_path / "trend.parquet"
        pd.DataFrame({"시군구코드": [26110], "전세가변동률": [-0.05]}).to_parquet(path, index=False)

        result = rpl.load_jeonse_trend_parquet(path)

        assert result is not None
        assert result.iloc[0]["전세가변동률"] == pytest.approx(-0.05)


class TestBuildJeonseTrendTable:
    def test_end_to_end_schema_and_report(self):
        rows = (
            _jeonse_rows(26110, PRIOR_QUARTERS, value=300.0)
            + _jeonse_rows(26110, RECENT_QUARTERS, value=330.0)
            + _renewal_rows(26110, 30, deposit=11000.0, prior_deposit=10000.0)
        )
        df = pd.DataFrame(rows)

        table, report = rpl.build_jeonse_trend_table(df)

        assert set(table.columns) == {"시군구코드", "전세가변동률", "갱신보증금변동률", "표본수"}
        row = table[table["시군구코드"] == 26110].iloc[0]
        assert row["전세가변동률"] == pytest.approx(0.10, abs=1e-6)
        assert row["갱신보증금변동률"] == pytest.approx(0.10, abs=1e-6)
        assert report["n_sigungu"] == 1
        assert report["jeonse_trend_insufficient"] == []
        assert report["renewal_rate_insufficient"] == []

    def test_wolse_rows_excluded_from_jeonse_trend(self):
        """전세여부==0(월세)인 행은 전세가변동률 계산에서 제외돼야 한다."""
        wolse_rows = [
            {
                "시군구코드": 26110, "전세여부": 0, "계약년월": 202501,
                "㎡당보증금(만원)": 9999.0, "주택유형": "아파트",
                "계약구분": "신규", "보증금(만원)": 10000, "종전계약 보증금(만원)": np.nan,
            }
            for _ in range(50)
        ]
        df = pd.DataFrame(wolse_rows)

        table, report = rpl.build_jeonse_trend_table(df)

        assert report["n_jeonse_rows"] == 0
