import numpy as np
import pandas as pd
import pytest

from pipeline.layer2a_clustering import cluster_interpreter, gmm_trainer


def _make_df(n_per_cluster=50, seed=1):
    rng = np.random.default_rng(seed)
    centers = [(-3, -3, 0, 0, 0), (3, 3, 0, 0, 0)]
    rows = []
    for c in centers:
        for _ in range(n_per_cluster):
            rows.append([c[i] + rng.normal(0, 0.3) for i in range(5)])
    return pd.DataFrame(rows, columns=gmm_trainer.DOMAIN_INDEX_COLUMNS)


@pytest.fixture(scope="module")
def trained_model():
    df = _make_df()
    model, _ = gmm_trainer.train_gmm(df, k=2, covariance_type="diag")
    membership = gmm_trainer.predict_membership(model, df)
    return model, membership


class TestComputeClusterProfiles:
    def test_shape_matches_k_and_domain_indices(self, trained_model):
        model, _ = trained_model
        profiles = cluster_interpreter.compute_cluster_profiles(model)
        assert profiles.shape == (2, 5)
        assert list(profiles.columns) == gmm_trainer.DOMAIN_INDEX_COLUMNS


class TestComputeClusterSizes:
    def test_sizes_sum_to_total_rows(self, trained_model):
        _, membership = trained_model
        sizes = cluster_interpreter.compute_cluster_sizes(membership)
        assert sizes.sum() == pytest.approx(len(membership), abs=1e-6)


class TestSuggestClusterLabels:
    def test_labels_are_drafts_not_thin_filer_or_asset_types(self, trained_model):
        """Thin Filer형/자산형성가능형은 단순 argmax로 절대 자동 배정되면 안 된다
        (사람이 직접 확인해야 하는 유형이라 의도적으로 매핑에서 제외됨)."""
        model, _ = trained_model
        profiles = cluster_interpreter.compute_cluster_profiles(model)
        labels = cluster_interpreter.suggest_cluster_labels(profiles)
        assert "Thin Filer형" not in labels.values()
        assert "자산형성가능형" not in labels.values()

    def test_high_housing_burden_cluster_labeled_housing_type(self):
        profiles = pd.DataFrame(
            {
                "주거비압박지수": [5.0, -1.0],
                "부채상환위험지수": [0.0, 0.0],
                "소득변동성지수": [0.0, 0.0],
                "소비압박지수": [0.0, 0.0],
                "신용취약지수": [0.0, 0.0],
            },
            index=["cluster_0", "cluster_1"],
        )
        labels = cluster_interpreter.suggest_cluster_labels(profiles)
        assert labels["cluster_0"] == "주거비압박형"
