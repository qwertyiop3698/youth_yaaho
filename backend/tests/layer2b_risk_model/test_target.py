import pandas as pd
import pytest

from pipeline.layer2b_risk_model import target


class TestLowCreditScoreProxy:
    def test_bottom_quartile_flagged_true(self):
        df = pd.DataFrame({"신용평점": [100, 200, 300, 400, 900, 950, 970, 990]})
        result = target.compute_low_credit_score_proxy(df, percentile=0.25)
        # 하위 25% 근방(가장 낮은 점수들)은 True여야 함
        assert result.iloc[0] == True  # noqa: E712 - 100점(최저)
        assert result.iloc[-1] == False  # 990점(최고)은 False

    def test_missing_score_column_returns_all_false(self):
        df = pd.DataFrame({"기타컬럼": [1, 2, 3]})
        result = target.compute_low_credit_score_proxy(df)
        assert (result == False).all()  # noqa: E712


class TestComputeEventLabel:
    def test_delinquency_alone_triggers_event(self):
        df = pd.DataFrame({
            "대출연체건수": [1, 0],
            "카드연체건수": [0, 0],
            "추정DTI": [0.1, 0.1],
            "소득증감률": [0.1, 0.1],
            "신용평점": [900, 900],
        })
        event = target.compute_event_label(df)
        assert event.tolist() == [1, 0]

    def test_secondary_condition_requires_all_three_factors(self):
        """행 A: DTI상위+소득감소+저신용 3박자 모두 충족 -> event=1.
        행 B/C/D는 각각 한 요인씩만 빠뜨려 event=0이 되는지 확인한다."""
        df = pd.DataFrame(
            {
                "대출연체건수": [0, 0, 0, 0],
                "카드연체건수": [0, 0, 0, 0],
                "추정DTI": [0.9, 0.9, 0.9, 0.1],          # A,B,C=상위 / D=하위
                "소득증감률": [-0.3, -0.3, 0.2, -0.3],       # A,B,D=감소 / C=증가
                "신용평점": [100, 900, 100, 100],           # A,C,D=저신용 / B=고신용
            },
            index=["A_all_conditions", "B_high_score_blocks", "C_income_up_blocks", "D_low_dti_blocks"],
        )
        event = target.compute_event_label(df)
        assert event["A_all_conditions"] == 1
        assert event["B_high_score_blocks"] == 0
        assert event["C_income_up_blocks"] == 0
        assert event["D_low_dti_blocks"] == 0

    def test_no_event_when_all_conditions_absent(self):
        df = pd.DataFrame({
            "대출연체건수": [0, 0],
            "카드연체건수": [0, 0],
            "추정DTI": [0.1, 0.1],
            "소득증감률": [0.1, 0.2],
            "신용평점": [900, 950],
        })
        event = target.compute_event_label(df)
        assert event.tolist() == [0, 0]

    def test_missing_columns_do_not_crash(self):
        df = pd.DataFrame({"대출연체건수": [0, 1]})
        event = target.compute_event_label(df)
        assert event.tolist() == [0, 1]  # 연체 조건만으로도 계산 진행
