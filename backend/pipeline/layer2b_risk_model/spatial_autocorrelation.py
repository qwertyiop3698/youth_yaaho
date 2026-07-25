"""Layer 2-B - 위험지도 공간적 자기상관 분석 (Global/Local Moran's I).

부산 16개 시군구의 인접관계를 손으로 하드코딩하지 않고, 이미 저장소에 있는
web-dashboard/public/busan_districts.geojson의 폴리곤 좌표에서 직접 유도한다 -
지도에 쓰는 것과 동일한 소스에서 계산하므로 인접관계가 지도와 어긋날 일이 없다.

무거운 지오 라이브러리(shapely/geopandas/pysal)는 추가하지 않는다. 좌표를
반올림해 두 폴리곤이 정점을 공유하면 인접(rook 근사)으로 판정하는 순수 파이썬
구현으로 간다(해커톤 당일 의존성 설치 리스크 최소화 원칙 - CLAUDE.md).

Global Moran's I는 "위험점수가 공간적으로 우연이 아니게 군집돼 있는가"를,
Local Moran's I(LISA)는 "어느 지역이 hotspot/coldspot인가"를 검정한다. 둘 다
정규성 가정 없이 순열검정(permutation test)으로 p-value를 계산한다.
"""
from __future__ import annotations

import itertools
import json
import logging
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# 정점 1개만 겹치면 꼭짓점 접촉(대각선 코너)일 뿐이라 변(edge) 공유를 요구한다.
MIN_SHARED_VERTICES = 2
COORD_PRECISION = 5
DEFAULT_N_PERMUTATIONS = 999
DEFAULT_LOCAL_N_PERMUTATIONS = 199

# 지도(RiskMap.tsx)가 쓰는 것과 동일한 geojson - 인접관계를 별도로 하드코딩하지
# 않고 이 파일에서 직접 유도한다(admin.py /risk-map이 기본값으로 사용).
DEFAULT_GEOJSON_PATH = (
    Path(__file__).resolve().parents[3] / "web-dashboard" / "public" / "busan_districts.geojson"
)


def _iter_coordinates(geometry: dict[str, Any]):
    """Polygon/MultiPolygon geometry의 모든 [x, y] 좌표를 순회한다."""
    coords = geometry["coordinates"]
    if geometry["type"] == "Polygon":
        polygons = [coords]
    elif geometry["type"] == "MultiPolygon":
        polygons = coords
    else:
        raise ValueError(f"지원하지 않는 geometry 타입입니다: {geometry['type']}")
    for polygon in polygons:
        for ring in polygon:
            for x, y in ring:
                yield x, y


@lru_cache(maxsize=4)
def _load_busan_adjacency_cached(geojson_path: str, precision: int) -> dict[str, frozenset[str]]:
    return {code: frozenset(neighbors) for code, neighbors in _load_busan_adjacency_uncached(geojson_path, precision).items()}


def load_busan_adjacency(geojson_path: str | Path, precision: int = COORD_PRECISION) -> dict[str, set[str]]:
    """geojson을 매 호출마다 다시 파싱하지 않도록 캐싱한 wrapper - 반환값은 매번
    새 set으로 복사해 호출자가 실수로 캐시된 내부 구조를 변경하지 못하게 한다."""
    cached = _load_busan_adjacency_cached(str(geojson_path), precision)
    return {code: set(neighbors) for code, neighbors in cached.items()}


def _load_busan_adjacency_uncached(geojson_path: str | Path, precision: int = COORD_PRECISION) -> dict[str, set[str]]:
    """geojson 폴리곤에서 시군구 인접행렬(rook 근사)을 유도한다.

    두 시군구가 반올림된 정점을 2개 이상 공유하면(=변을 공유하면) 인접으로
    판정한다. 섬 지역(영도구 등)처럼 육지 경계를 전혀 공유하지 않는 지역은 가장
    가까운 지역(중심점 거리 기준 - 다리/연락선으로 실질 연결된 지역의 근사)
    하나에 연결한다. 안 그러면 그 지역의 공간가중치 행 전체가 0이 되어 Moran's
    I 계산의 행 정규화가 깨진다(0으로 나눔).
    """
    with open(geojson_path, encoding="utf-8") as f:
        geojson = json.load(f)

    region_vertices: dict[str, set[tuple[float, float]]] = {}
    region_centroid: dict[str, tuple[float, float]] = {}
    vertex_to_regions: dict[tuple[float, float], set[str]] = defaultdict(set)

    for feature in geojson["features"]:
        region_code = str(feature["properties"]["region_code"])
        vertices = {(round(x, precision), round(y, precision)) for x, y in _iter_coordinates(feature["geometry"])}
        if not vertices:
            continue
        region_vertices[region_code] = vertices
        xs = [v[0] for v in vertices]
        ys = [v[1] for v in vertices]
        region_centroid[region_code] = (sum(xs) / len(xs), sum(ys) / len(ys))
        for v in vertices:
            vertex_to_regions[v].add(region_code)

    shared_counts: dict[tuple[str, str], int] = defaultdict(int)
    for regions in vertex_to_regions.values():
        if len(regions) < 2:
            continue
        for a, b in itertools.combinations(sorted(regions), 2):
            shared_counts[(a, b)] += 1

    adjacency: dict[str, set[str]] = {code: set() for code in region_vertices}
    for (a, b), count in shared_counts.items():
        if count >= MIN_SHARED_VERTICES:
            adjacency[a].add(b)
            adjacency[b].add(a)

    isolated = [code for code, neighbors in adjacency.items() if not neighbors]
    for code in isolated:
        cx, cy = region_centroid[code]
        candidates = [other for other in region_vertices if other != code]
        if not candidates:
            continue
        nearest = min(candidates, key=lambda other: (region_centroid[other][0] - cx) ** 2 + (region_centroid[other][1] - cy) ** 2)
        logger.info(
            "공간 인접성: '%s'는 경계를 공유하는 지역이 없어(섬 등) 최근접 지역 '%s'에 연결합니다.", code, nearest
        )
        adjacency[code].add(nearest)
        adjacency[nearest].add(code)

    return adjacency


def _row_standardized_weights(regions: list[str], adjacency: dict[str, set[str]]) -> np.ndarray:
    n = len(regions)
    index = {r: i for i, r in enumerate(regions)}
    w = np.zeros((n, n))
    for region in regions:
        neighbors = [nb for nb in adjacency.get(region, set()) if nb in index]
        if not neighbors:
            continue
        weight = 1.0 / len(neighbors)
        for nb in neighbors:
            w[index[region], index[nb]] = weight
    return w


def compute_morans_i(
    values: pd.Series,
    adjacency: dict[str, set[str]],
    n_permutations: int = DEFAULT_N_PERMUTATIONS,
    seed: int = 42,
) -> dict[str, Any]:
    """Global Moran's I - 지역 평균위험점수가 공간적으로 군집돼 있는지(양의 자기상관)
    통계적으로 검정한다. 정규성을 가정하지 않는 순열검정으로 p-value를 산출한다.
    """
    values = values.dropna()
    regions = [r for r in values.index if r in adjacency]
    if len(regions) < 3:
        return {"skipped": True, "reason": "지역 수가 3개 미만이라 계산할 수 없습니다.", "n_regions": len(regions)}

    x = values.loc[regions].to_numpy(dtype=float)
    w = _row_standardized_weights(regions, adjacency)
    n = len(regions)
    s0 = float(w.sum())

    def _moran(vec: np.ndarray) -> float:
        z = vec - vec.mean()
        denominator = float((z**2).sum())
        if denominator == 0 or s0 == 0:
            return 0.0
        numerator = float(z @ w @ z)
        return (n / s0) * (numerator / denominator)

    observed = _moran(x)

    rng = np.random.default_rng(seed)
    permuted = np.array([_moran(rng.permutation(x)) for _ in range(n_permutations)])
    p_value = float((np.sum(np.abs(permuted) >= abs(observed)) + 1) / (n_permutations + 1))

    return {
        "skipped": False,
        "morans_i": float(observed),
        "p_value": p_value,
        "n_regions": n,
        "n_permutations": n_permutations,
        "is_significant": bool(p_value < 0.05),
    }


def classify_hotspot(lisa: dict[str, Any] | None) -> str:
    """LISA 결과를 "hotspot"/"coldspot"/"not_significant" 3분류로 단순화한다
    (admin /risk-map, run_spatial_autocorrelation_report.py 공용). 세부 사분면
    (HL/LH, 이상치)이나 통계적으로 유의하지 않은 결과는 전부 not_significant로
    묶는다 - 세부 사분면 자체는 별도로 lisa_quadrant 필드에 그대로 남긴다."""
    if lisa and lisa.get("is_significant") and lisa.get("quadrant") == "HH":
        return "hotspot"
    if lisa and lisa.get("is_significant") and lisa.get("quadrant") == "LL":
        return "coldspot"
    return "not_significant"


def compute_local_indicators(
    values: pd.Series,
    adjacency: dict[str, set[str]],
    n_permutations: int = DEFAULT_LOCAL_N_PERMUTATIONS,
    seed: int = 42,
) -> dict[str, dict[str, Any]]:
    """LISA(Local Indicators of Spatial Association) - 지역별 hotspot(HH)/coldspot(LL)/
    이상치(HL, LH) 판정. 조건부 순열검정(그 지역 값은 고정하고 나머지를 섞음)으로
    p-value를 산출한다."""
    values = values.dropna()
    regions = [r for r in values.index if r in adjacency]
    if len(regions) < 3:
        return {}

    x = values.loc[regions].to_numpy(dtype=float)
    w = _row_standardized_weights(regions, adjacency)
    n = len(regions)
    z = x - x.mean()
    m2 = float((z**2).sum() / n)

    if m2 == 0:
        return {region: {"local_i": 0.0, "quadrant": "LL", "p_value": 1.0, "is_significant": False} for region in regions}

    lag = w @ z
    local_i = (z / m2) * lag

    rng = np.random.default_rng(seed)
    results: dict[str, dict[str, Any]] = {}
    for idx, region in enumerate(regions):
        if z[idx] >= 0 and lag[idx] >= 0:
            quadrant = "HH"
        elif z[idx] < 0 and lag[idx] < 0:
            quadrant = "LL"
        elif z[idx] >= 0 and lag[idx] < 0:
            quadrant = "HL"
        else:
            quadrant = "LH"

        others_idx = np.array([j for j in range(n) if j != idx])
        permuted_local = np.empty(n_permutations)
        for p in range(n_permutations):
            shuffled_z = z.copy()
            shuffled_z[others_idx] = z[rng.permutation(others_idx)]
            permuted_lag = float(w[idx] @ shuffled_z)
            permuted_local[p] = (z[idx] / m2) * permuted_lag
        p_value = float((np.sum(np.abs(permuted_local) >= abs(local_i[idx])) + 1) / (n_permutations + 1))

        results[region] = {
            "local_i": float(local_i[idx]),
            "quadrant": quadrant,
            "p_value": p_value,
            "is_significant": bool(p_value < 0.05),
        }
    return results
