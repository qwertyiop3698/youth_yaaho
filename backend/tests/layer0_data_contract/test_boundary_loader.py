from pathlib import Path

import pytest

from pipeline.layer0_data_contract import boundary_loader
from pipeline.layer2b_risk_model import spatial_autocorrelation

_REAL_GEOJSON_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "external" / "부산_행정동경계_ver20260401.geojson"
)


def _square_feature(sgg: str, x0: float, y0: float, x1: float, y1: float) -> dict:
    """지정한 사각형 좌표를 갖는 MultiPolygon 행정동 feature를 만든다."""
    ring = [[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]
    return {
        "type": "Feature",
        "properties": {"sgg": sgg},
        "geometry": {"type": "MultiPolygon", "coordinates": [[ring]]},
    }


def _write_geojson(tmp_path: Path, features: list[dict], filename: str = "boundary.geojson") -> Path:
    import json

    path = tmp_path / filename
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}), encoding="utf-8")
    return path


class TestComputeSigunguAdjacency:
    def test_two_dong_same_sigungu_do_not_create_self_edge(self, tmp_path):
        """같은 시군구 소속 행정동끼리 경계를 공유해도(내부 경계) 인접행렬에는
        영향이 없어야 한다 - dissolve 없이 정점을 시군구 단위로 모으는 접근의 핵심."""
        features = [
            _square_feature("A", 0, 0, 1, 1),  # A의 행정동 1
            _square_feature("A", 1, 0, 2, 1),  # A의 행정동 2 (행정동1과 변 공유, 둘 다 A)
        ]
        path = _write_geojson(tmp_path, features)

        adjacency, report = boundary_loader.compute_sigungu_adjacency(path)

        assert report["n_sigungu"] == 1
        assert report["n_dong_features"] == 2
        assert adjacency["A"] == set()  # 이웃 시군구가 아예 없음(자기 자신과의 엣지 없음)

    def test_adjacent_sigungu_detected_via_shared_edge(self, tmp_path):
        features = [
            _square_feature("A", 0, 0, 1, 1),
            _square_feature("B", 1, 0, 2, 1),  # A와 변(x=1) 공유
        ]
        path = _write_geojson(tmp_path, features)

        adjacency, report = boundary_loader.compute_sigungu_adjacency(path)

        assert adjacency["A"] == {"B"}
        assert adjacency["B"] == {"A"}  # 대칭
        assert report["isolated_sigungu_connections"] == []

    def test_isolated_sigungu_connected_via_nearest_centroid_fallback(self, tmp_path):
        """섬처럼 경계를 전혀 공유하지 않는 시군구는 최근접 시군구 1개에 연결돼야
        한다(spatial_autocorrelation의 고립 지역 처리 관례와 동일)."""
        features = [
            _square_feature("A", 0, 0, 1, 1),
            _square_feature("B", 1, 0, 2, 1),  # A와 인접
            _square_feature("C", 100, 100, 101, 101),  # 완전히 동떨어짐
        ]
        path = _write_geojson(tmp_path, features)

        adjacency, report = boundary_loader.compute_sigungu_adjacency(path)

        assert len(adjacency["C"]) == 1
        connected_to = next(iter(adjacency["C"]))
        assert connected_to in adjacency["C"]
        assert connected_to in adjacency and "C" in adjacency[connected_to]  # 대칭 연결
        assert len(report["isolated_sigungu_connections"]) == 1
        assert report["isolated_sigungu_connections"][0]["region_code"] == "C"

    def test_single_vertex_touch_below_threshold_is_not_adjacent(self, tmp_path):
        """정점을 1개만 공유하면(꼭짓점 대각선 접촉) 직접 인접으로 치지 않는다.

        A-D, B-E는 각각 변을 공유하는 '진짜' 이웃 쌍이라 A/B 둘 다 고립 지역
        fallback이 발동하지 않는다(이웃이 이미 있으므로). 그 상태에서 A는 D만,
        B는 E만 이웃이어야 - 대각선으로 (1,1) 꼭짓점만 접촉한 A-B가 fallback
        개입 없이도 직접 인접으로 판정되지 않았음을 순수하게 검증할 수 있다."""
        features = [
            _square_feature("A", 0, 0, 1, 1),
            _square_feature("D", -1, 0, 0, 1),  # A와 변(x=0, y:0~1) 공유 - A의 진짜 이웃
            _square_feature("B", 1, 1, 2, 2),  # A와 (1,1) 꼭짓점 1개만 접촉
            _square_feature("E", 2, 1, 3, 2),  # B와 변(x=2, y:1~2) 공유 - B의 진짜 이웃
        ]
        path = _write_geojson(tmp_path, features)

        adjacency, _ = boundary_loader.compute_sigungu_adjacency(path)

        assert adjacency["A"] == {"D"}
        assert adjacency["B"] == {"E"}

    def test_caching_returns_independent_mutable_copies(self, tmp_path):
        """캐시된 내부 구조를 호출자가 실수로 변경해도 다음 호출에 영향이 없어야 한다."""
        features = [_square_feature("A", 0, 0, 1, 1), _square_feature("B", 1, 0, 2, 1)]
        path = _write_geojson(tmp_path, features)

        adjacency1, report1 = boundary_loader.compute_sigungu_adjacency(path)
        adjacency1["A"].add("MUTATED")
        report1["isolated_sigungu_connections"].append({"fake": "entry"})

        adjacency2, report2 = boundary_loader.compute_sigungu_adjacency(path)
        assert "MUTATED" not in adjacency2["A"]
        assert report2["isolated_sigungu_connections"] == []


class TestLoadAdjacencyWithFallback:
    def test_prefers_boundary_loader_when_official_geojson_exists(self, monkeypatch, tmp_path):
        fake_geojson = tmp_path / "fake_boundary.geojson"
        fake_geojson.write_text("{}", encoding="utf-8")

        def _fake_compute(*args, **kwargs):
            return {"26110": {"26140"}, "26140": {"26110"}}, {"source": "boundary_loader(테스트)"}

        monkeypatch.setattr(boundary_loader, "compute_sigungu_adjacency", _fake_compute)

        adjacency, report = boundary_loader.load_adjacency_with_fallback(fake_geojson)
        assert adjacency == {"26110": {"26140"}, "26140": {"26110"}}
        assert report["source"] == "boundary_loader(테스트)"

    def test_falls_back_to_old_source_when_boundary_geojson_missing(self, tmp_path):
        missing_path = tmp_path / "does_not_exist.geojson"
        assert spatial_autocorrelation.DEFAULT_GEOJSON_PATH.exists()  # 기존 소스는 저장소에 실재해야 함

        adjacency, report = boundary_loader.load_adjacency_with_fallback(missing_path)
        assert adjacency is not None
        assert "폴백" in report["source"]

    def test_returns_none_when_neither_source_exists(self, monkeypatch, tmp_path):
        monkeypatch.setattr(spatial_autocorrelation, "DEFAULT_GEOJSON_PATH", tmp_path / "missing2.geojson")

        adjacency, report = boundary_loader.load_adjacency_with_fallback(tmp_path / "missing1.geojson")
        assert adjacency is None
        assert report is None


@pytest.mark.skipif(not _REAL_GEOJSON_PATH.exists(), reason="당일 제공된 행정동 경계 geojson이 없습니다.")
class TestComputeSigunguAdjacencyRealFile:
    def test_produces_16_sigungu_matching_kcb_code_system(self):
        adjacency, report = boundary_loader.compute_sigungu_adjacency(_REAL_GEOJSON_PATH)

        assert report["n_dong_features"] == 206
        assert report["n_sigungu"] == 16
        assert set(adjacency.keys()) == {
            "26110", "26140", "26170", "26200", "26230", "26260", "26290", "26320",
            "26350", "26380", "26410", "26440", "26470", "26500", "26530", "26710",
        }

    def test_every_sigungu_has_at_least_one_neighbor(self):
        adjacency, _ = boundary_loader.compute_sigungu_adjacency(_REAL_GEOJSON_PATH)
        for region_code, neighbors in adjacency.items():
            assert len(neighbors) >= 1, f"{region_code}에 이웃이 하나도 없습니다."

    def test_adjacency_is_symmetric(self):
        adjacency, _ = boundary_loader.compute_sigungu_adjacency(_REAL_GEOJSON_PATH)
        for region_code, neighbors in adjacency.items():
            for neighbor in neighbors:
                assert region_code in adjacency[neighbor], f"{region_code}->{neighbor}가 비대칭입니다."
