import pandas as pd
import pytest

from pipeline.layer2b_risk_model import cox_trainer


def test_train_cox_model_raises_not_implemented():
    """duration을 관측할 방법이 없어 Cox는 의도적으로 비활성 상태다(2026-07-08 결정).
    조용히 가짜 값으로 학습되는 일이 없도록 반드시 예외를 던져야 한다."""
    df = pd.DataFrame({"duration": [1, 2], "event": [0, 1]})
    with pytest.raises(NotImplementedError):
        cox_trainer.train_cox_model(df, duration_col="duration", event_col="event")


def test_check_proportional_hazards_raises_not_implemented():
    with pytest.raises(NotImplementedError):
        cox_trainer.check_proportional_hazards_assumption(None, pd.DataFrame())
