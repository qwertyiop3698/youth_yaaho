from pathlib import Path

import pandas as pd
import pytest

from pipeline.layer2b_risk_model import spatial_autocorrelation as sa

_GEOJSON_PATH = Path(__file__).resolve().parents[3] / "web-dashboard" / "public" / "busan_districts.geojson"


def _cycle_adjacency(n: int) -> dict[str, set[str]]:
    """0..n-1을 원형으로 연결한 인접행렬(각 노드는 좌우 이웃 2개)."""
    codes = [str(i) for i in range(n)]
    return {codes[i]: {codes[(i - 1) % n], codes[(i + 1) % n]} for i in range(n)}


class TestLoadBusanAdjacency:
    def test_every_district_has_at_least_one_neighbor(self):
        adjacency = sa.load_busan_adjacency(_GEOJSON_PATH)
        assert len(adjacency) == 16
        for region_code, neighbors in adjacency.items():
            assert len(neighbors) >= 1, f"{region_code}에 이웃이 하나도 없습니다."

    def test_adjacency_is_symmetric(self):
        adjacency = sa.load_busan_adjacency(_GEOJSON_PATH)
        for region_code, neighbors in adjacency.items():
            for neighbor in neighbors:
                assert region_code in adjacency[neighbor], f"{region_code}->{neighbor}가 비대칭입니다."

    def test_island_district_connected_via_nearest_neighbor_fallback(self):
        # 26200 = 영도구(섬) - 육지 경계 공유가 없어 최근접 지역 폴백으로 연결돼야 한다.
        adjacency = sa.load_busan_adjacency(_GEOJSON_PATH)
        assert len(adjacency["26200"]) >= 1


class TestComputeMoransI:
    def test_clustered_pattern_yields_positive_i(self):
        adjacency = _cycle_adjacency(6)
        values = pd.Series([10.0, 10.0, 10.0, 1.0, 1.0, 1.0], index=[str(i) for i in range(6)])
        result = sa.compute_morans_i(values, adjacency, n_permutations=499)
        assert result["skipped"] is False
        assert result["morans_i"] > 0

    def test_checkerboard_pattern_yields_negative_i(self):
        adjacency = _cycle_adjacency(6)
        values = pd.Series([10.0, 1.0, 10.0, 1.0, 10.0, 1.0], index=[str(i) for i in range(6)])
        result = sa.compute_morans_i(values, adjacency, n_permutations=499)
        assert result["skipped"] is False
        assert result["morans_i"] < 0

    def test_p_value_within_valid_range(self):
        adjacency = _cycle_adjacency(6)
        values = pd.Series([10.0, 10.0, 10.0, 1.0, 1.0, 1.0], index=[str(i) for i in range(6)])
        result = sa.compute_morans_i(values, adjacency, n_permutations=499)
        assert 0.0 <= result["p_value"] <= 1.0

    def test_skipped_when_fewer_than_three_regions(self):
        adjacency = _cycle_adjacency(2)
        values = pd.Series([10.0, 1.0], index=["0", "1"])
        result = sa.compute_morans_i(values, adjacency)
        assert result["skipped"] is True

    def test_real_busan_risk_scores_produce_valid_result(self):
        adjacency = sa.load_busan_adjacency(_GEOJSON_PATH)
        codes = list(adjacency.keys())
        values = pd.Series(range(len(codes)), index=codes, dtype=float)
        result = sa.compute_morans_i(values, adjacency, n_permutations=199)
        assert result["skipped"] is False
        assert result["n_regions"] == 16


class TestComputeLocalIndicators:
    def test_returns_entry_per_region(self):
        adjacency = _cycle_adjacency(6)
        values = pd.Series([10.0, 10.0, 10.0, 1.0, 1.0, 1.0], index=[str(i) for i in range(6)])
        result = sa.compute_local_indicators(values, adjacency, n_permutations=99)
        assert set(result.keys()) == {str(i) for i in range(6)}
        for entry in result.values():
            assert entry["quadrant"] in {"HH", "LL", "HL", "LH"}
            assert 0.0 <= entry["p_value"] <= 1.0

    def test_high_value_surrounded_by_high_values_is_hh(self):
        adjacency = _cycle_adjacency(6)
        values = pd.Series([10.0, 10.0, 10.0, 1.0, 1.0, 1.0], index=[str(i) for i in range(6)])
        result = sa.compute_local_indicators(values, adjacency, n_permutations=99)
        assert result["1"]["quadrant"] == "HH"  # 양옆(0,2)도 모두 높은 값
        assert result["4"]["quadrant"] == "LL"  # 양옆(3,5)도 모두 낮은 값

    def test_empty_when_fewer_than_three_regions(self):
        adjacency = _cycle_adjacency(2)
        values = pd.Series([10.0, 1.0], index=["0", "1"])
        assert sa.compute_local_indicators(values, adjacency) == {}
