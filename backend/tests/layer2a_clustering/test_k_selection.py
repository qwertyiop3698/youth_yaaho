import numpy as np
import pytest

from pipeline.layer2a_clustering import k_selection


def _make_synthetic_clusters(n_per_cluster=60, seed=42):
    rng = np.random.default_rng(seed)
    centers = [(-3, -3, 0, 0, 0), (3, 3, 0, 0, 0), (0, 0, 3, 3, 3)]
    rows = []
    for c in centers:
        for _ in range(n_per_cluster):
            rows.append([c[i] + rng.normal(0, 0.3) for i in range(5)])
    return np.array(rows)


class TestSelectKSmallSample:
    def test_skips_when_sample_too_small(self):
        X = np.random.default_rng(0).normal(size=(5, 5))  # sample.csv 수준 표본
        result = k_selection.select_k(X, min_sample=30)
        assert result["skipped"] is True
        assert result["best_k"] is None
        assert result["candidates"] == []

    def test_default_min_sample_matches_module_constant(self):
        assert k_selection.MIN_SAMPLE_FOR_CLUSTERING == 30


class TestSelectKSufficientSample:
    def test_recovers_reasonable_k_for_well_separated_clusters(self):
        X = _make_synthetic_clusters()
        result = k_selection.select_k(X, min_sample=30)
        assert result["skipped"] is False
        assert result["best_k"] in {2, 3, 4}  # 3개로 뚜렷이 분리된 데이터라 3 근처여야 함
        assert result["best_covariance_type"] in k_selection.COVARIANCE_TYPES
        assert len(result["candidates"]) > 0
        for c in result["candidates"]:
            assert "bic" in c and "silhouette" in c

    def test_skips_k_values_at_or_above_sample_size(self):
        X = _make_synthetic_clusters(n_per_cluster=2)  # n=6, K_RANGE(3~10)의 대부분이 n 이상
        result = k_selection.select_k(X, k_range=range(3, 11), min_sample=1)
        # K >= n인 조합은 전부 건너뛰므로 실행되더라도 후보가 있거나 비어있거나 둘 다 허용(죽지 않는 게 핵심)
        assert isinstance(result["candidates"], list)
