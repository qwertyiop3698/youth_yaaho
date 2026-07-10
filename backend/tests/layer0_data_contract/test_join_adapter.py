import pandas as pd

from pipeline.layer0_data_contract import join_adapter


class TestJoinWithFallback:
    """docs/02: 조인은 행정동 우선 시도, 실패 시 시군구코드로 fallback."""

    def test_prefers_dong_match_over_sigungu(self):
        left = pd.DataFrame({
            "id": [1, 2, 3],
            "거주지행정동": ["11110", "99999", None],  # 2,3행은 행정동 매칭 실패 유도
            "거주지 시군구 코드": ["11000", "11000", "26000"],
        })
        right_by_dong = pd.DataFrame({"행정동코드": ["11110"], "avg_price": [50000]})
        right_by_sigungu = pd.DataFrame({"시군구코드": ["11000", "26000"], "avg_price": [30000, 20000]})

        result = join_adapter.join_with_fallback(
            left,
            dong_col="거주지행정동",
            sigungu_col="거주지 시군구 코드",
            value_cols=["avg_price"],
            right_by_dong=right_by_dong,
            right_by_sigungu=right_by_sigungu,
            dong_key="행정동코드",
            sigungu_key="시군구코드",
        )

        assert result.loc[0, "avg_price"] == 50000
        assert result.loc[0, "_join_method"] == "dong"
        assert result.loc[1, "avg_price"] == 30000  # 행정동 불일치 -> 시군구 fallback
        assert result.loc[1, "_join_method"] == "sigungu"
        assert result.loc[2, "avg_price"] == 20000  # 행정동 자체가 null -> 시군구 fallback
        assert result.loc[2, "_join_method"] == "sigungu"

    def test_missing_dong_column_falls_back_to_sigungu_entirely(self):
        """sample.csv처럼 행정동 컬럼 자체가 데이터에 없는 상황을 방어적으로 처리."""
        left = pd.DataFrame({"id": [1, 2], "거주지 시군구 코드": ["11000", "26000"]})
        right_by_sigungu = pd.DataFrame({"시군구코드": ["11000", "26000"], "avg_price": [30000, 20000]})

        result = join_adapter.join_with_fallback(
            left,
            dong_col=None,
            sigungu_col="거주지 시군구 코드",
            value_cols=["avg_price"],
            right_by_dong=None,
            right_by_sigungu=right_by_sigungu,
            sigungu_key="시군구코드",
        )

        assert result["_join_method"].tolist() == ["sigungu", "sigungu"]
        assert result["avg_price"].tolist() == [30000, 20000]

    def test_unmatched_when_neither_key_found(self):
        left = pd.DataFrame({"거주지 시군구 코드": ["99999"]})
        right_by_sigungu = pd.DataFrame({"시군구코드": ["11000"], "avg_price": [30000]})

        result = join_adapter.join_with_fallback(
            left,
            dong_col=None,
            sigungu_col="거주지 시군구 코드",
            value_cols=["avg_price"],
            right_by_sigungu=right_by_sigungu,
            sigungu_key="시군구코드",
        )

        assert result.loc[0, "_join_method"] == "unmatched"
        assert pd.isna(result.loc[0, "avg_price"])


class TestRegionalMedianWithFallback:
    """docs/02 구현원칙 3: 표본 미달 시 상위 카테고리(시군구)로 자동 백오프."""

    def test_dong_group_preferred_over_sigungu_when_both_sufficient(self):
        df = pd.DataFrame({
            "value": [10, 10, 10, 10, 10, 1000, 1000, 1000, 1000, 1000],
            "행정동": ["A"] * 5 + ["B"] * 5,
            "시군구": ["X"] * 10,  # 시군구 median은 두 그룹을 합친 505 - 행정동 median과 달라야 우선순위 검증 가능
        })
        result = join_adapter.regional_median_with_fallback(
            df, "value", dong_col="행정동", sigungu_col="시군구", min_sample_for_regional_group=5
        )
        assert (result.iloc[0:5] == 10).all()      # 행정동 A median
        assert (result.iloc[5:10] == 1000).all()   # 행정동 B median (시군구 505이 아님)

    def test_backs_off_to_sigungu_when_dong_sample_too_small(self):
        df = pd.DataFrame({
            "value": [100, 200, 150, 999999999],
            "행정동": ["A", "B", "C", "D"],  # 행정동 그룹별 표본 1개뿐 -> 부족
            "시군구": ["X", "X", "X", "X"],
        })
        valid_mask = pd.Series([True, True, True, False], index=df.index)
        result = join_adapter.regional_median_with_fallback(
            df,
            "value",
            dong_col="행정동",
            sigungu_col="시군구",
            min_sample_for_regional_group=2,
            valid_mask=valid_mask,
        )
        assert result.iloc[3] == 150  # 시군구 X 그룹(유효값 100,200,150) median

    def test_falls_back_to_global_median_when_no_dong_column(self):
        """sample.csv처럼 행정동 컬럼이 없는 경우에도 죽지 않고 전체 median으로 대체."""
        df = pd.DataFrame({"value": [10, 20, 30, -99999999]})
        valid_mask = pd.Series([True, True, True, False], index=df.index)
        result = join_adapter.regional_median_with_fallback(
            df, "value", dong_col=None, sigungu_col=None, valid_mask=valid_mask
        )
        assert (result == 20).all()
