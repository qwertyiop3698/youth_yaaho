import numpy as np
import pandas as pd
import pytest

from pipeline.layer2a_clustering import gmm_trainer


def _make_df(n_per_cluster=50, seed=1):
    rng = np.random.default_rng(seed)
    centers = [(-3, -3, 0, 0, 0), (3, 3, 0, 0, 0)]
    rows = []
    for c in centers:
        for _ in range(n_per_cluster):
            rows.append([c[i] + rng.normal(0, 0.3) for i in range(5)])
    return pd.DataFrame(rows, columns=gmm_trainer.DOMAIN_INDEX_COLUMNS)


class TestPrepareClusteringInput:
    def test_drops_rows_with_missing_domain_index(self):
        df = _make_df(n_per_cluster=5)
        df.loc[0, "주거비압박지수"] = np.nan
        X, valid_index = gmm_trainer.prepare_clustering_input(df)
        assert len(X) == len(df) - 1
        assert 0 not in valid_index

    def test_missing_columns_do_not_crash(self):
        df = pd.DataFrame({"주거비압박지수": [1, 2, 3]})
        X, valid_index = gmm_trainer.prepare_clustering_input(df)
        assert len(X) == 3  # 존재하는 컬럼만으로도 계산 진행


class TestTrainGmm:
    def test_rejects_k_greater_or_equal_to_sample_size(self):
        df = _make_df(n_per_cluster=2)  # n=4
        with pytest.raises(ValueError):
            gmm_trainer.train_gmm(df, k=10)

    def test_trains_successfully_with_valid_k(self):
        df = _make_df(n_per_cluster=50)
        model, valid_index = gmm_trainer.train_gmm(df, k=2, covariance_type="diag")
        assert model.n_components == 2
        assert len(valid_index) == len(df)


class TestPredictMembership:
    def test_membership_probabilities_sum_to_one(self):
        df = _make_df(n_per_cluster=50)
        model, _ = gmm_trainer.train_gmm(df, k=2, covariance_type="diag")
        membership = gmm_trainer.predict_membership(model, df)
        assert membership.shape[1] == 2
        sums = membership.sum(axis=1)
        assert np.allclose(sums, 1.0, atol=1e-6)

    def test_missing_domain_index_rows_get_nan_membership(self):
        df = _make_df(n_per_cluster=50)
        model, _ = gmm_trainer.train_gmm(df, k=2, covariance_type="diag")
        df_with_missing = df.copy()
        df_with_missing.loc[0, "주거비압박지수"] = np.nan
        membership = gmm_trainer.predict_membership(model, df_with_missing)
        assert membership.loc[0].isna().all()
