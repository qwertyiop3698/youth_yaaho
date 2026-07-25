"""Layer 0 - 행정동 경계 geojson -> 시군구 공간 인접행렬 로더.

data/external/부산_행정동경계_ver20260401.geojson(행정동 206개, WGS84, MultiPolygon)를
시군구(properties.sgg, KCB 시군구코드와 동일 5자리 체계) 단위로 묶어 인접행렬을
만든다. admin /risk-map의 Moran's I/LISA가 쓰는 공간 가중치를, 지금까지 쓰던
web-dashboard/public/busan_districts.geojson(단순화된 16개 폴리곤) 대신 이 공식
행정동 경계에서 유도한 값으로 교체하기 위한 모듈이다(2026-07-25 DIVE 2026
이종결합 작업 2).

## geopandas/shapely를 추가하지 않은 이유
pipeline.layer2b_risk_model.spatial_autocorrelation이 이미 같은 문제(폴리곤 인접
판정)를 "반올림한 정점을 2개 이상 공유하면 인접(rook 근사)"이라는 순수 파이썬
알고리즘으로 풀고 있다(그 모듈 docstring: "해커톤 당일 의존성 설치 리스크 최소화
원칙"). 이번에도 같은 근사·같은 원칙을 그대로 따른다.

시군구 폴리곤을 실제로 geometric dissolve(합집합)할 필요조차 없다: 행정동 A(시군구
X 소속)와 행정동 B(시군구 Y 소속, X≠Y)가 정점을 공유하면 그 자체가 "시군구 X와 Y가
인접하다"는 뜻이다. 그래서 "정점을 시군구 단위로 모아서" 기존과 동일한 vertex-sharing
알고리즘을 적용하면, 폴리곤 union 연산 없이 동일한 인접 판정 결과를 얻는다. 같은
시군구에 속한 행정동끼리 정점을 공유하는 건(내부 경계) 애초에 같은 그룹으로 묶여
무시되므로 이중 카운트 문제도 없다.

## 캐싱
spatial_autocorrelation._load_busan_adjacency_cached와 동일하게 lru_cache로
프로세스당 1회만 파싱한다 - 사전계산 JSON 파일을 별도로 관리(캐시 무효화, 당일
경계 파일 교체 시 재생성 여부 챙기기)하지 않아도 되는 쪽이 해커톤 당일 운영
부담이 더 적다고 판단했다(미션에서 허용한 두 방식 중 "런타임 캐싱"을 선택).
"""
from __future__ import annotations

import itertools
import json
import logging
from collections import defaultdict
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

from pipeline.layer2b_risk_model import spatial_autocorrelation
from pipeline.layer2b_risk_model.spatial_autocorrelation import _iter_coordinates

logger = logging.getLogger(__name__)

MIN_SHARED_VERTICES = 2
COORD_PRECISION = 5
DEFAULT_SGG_PROPERTY = "sgg"

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DONG_GEOJSON_PATH = _PROJECT_ROOT / "data" / "external" / "부산_행정동경계_ver20260401.geojson"


@lru_cache(maxsize=4)
def _compute_sigungu_adjacency_cached(
    geojson_path: str, sgg_property: str, precision: int
) -> tuple[dict[str, frozenset[str]], str]:
    adjacency, report = _compute_sigungu_adjacency_uncached(geojson_path, sgg_property, precision)
    frozen_adjacency = {code: frozenset(neighbors) for code, neighbors in adjacency.items()}
    # report는 dict/list/str/int만 담으므로 json 직렬화 가능 - 캐시된 값을 호출자가
    # 실수로 변형해도 다음 캐시 히트에 영향 없도록 문자열로 굳혀서 보관한다.
    return frozen_adjacency, json.dumps(report, ensure_ascii=False)


def compute_sigungu_adjacency(
    geojson_path: str | Path = DEFAULT_DONG_GEOJSON_PATH,
    sgg_property: str = DEFAULT_SGG_PROPERTY,
    precision: int = COORD_PRECISION,
) -> tuple[dict[str, set[str]], dict[str, Any]]:
    """행정동 경계 geojson에서 시군구 인접행렬을 유도한다.

    반환: (adjacency, report). adjacency는
    spatial_autocorrelation.compute_morans_i()/compute_local_indicators()가 받는
    dict[str, set[str]]과 완전히 같은 모양이라 시그니처 변경 없이 그대로 주입할 수
    있다. report에는 행정동/시군구 개수, 고립 시군구(섬 등) 처리 내역이 담긴다.
    """
    frozen_adjacency, report_json = _compute_sigungu_adjacency_cached(str(geojson_path), sgg_property, precision)
    adjacency = {code: set(neighbors) for code, neighbors in frozen_adjacency.items()}
    return adjacency, deepcopy(json.loads(report_json))


def load_adjacency_with_fallback(
    dong_geojson_path: str | Path = DEFAULT_DONG_GEOJSON_PATH,
) -> tuple[dict[str, set[str]] | None, dict[str, Any] | None]:
    """admin /risk-map, run_spatial_autocorrelation_report.py가 공용으로 쓰는
    공간 가중치(인접행렬) 소스 선택 로직.

    2026-07-25 DIVE 2026 작업2: 공식 행정동 경계(이 모듈)를 우선 쓴다 - 실제
    행정구역 폴리곤을 dissolve해 유도한 인접관계라 기존 소스보다 정밀하다. 당일
    파일이 없으면 기존 소스(web-dashboard/public/busan_districts.geojson, 단순화된
    16개 폴리곤)로 폴백해 호출부가 죽지 않게 한다. 둘 다 없으면 (None, None) -
    호출부가 공간 통계 계산 자체를 건너뛰어야 한다는 신호."""
    dong_geojson_path = Path(dong_geojson_path)
    if dong_geojson_path.exists():
        return compute_sigungu_adjacency(dong_geojson_path)
    if spatial_autocorrelation.DEFAULT_GEOJSON_PATH.exists():
        adjacency = spatial_autocorrelation.load_busan_adjacency(spatial_autocorrelation.DEFAULT_GEOJSON_PATH)
        return adjacency, {"source": "spatial_autocorrelation(단순화된 16개 폴리곤, 공식 경계 없어 폴백)"}
    return None, None


def _compute_sigungu_adjacency_uncached(
    geojson_path: str, sgg_property: str, precision: int
) -> tuple[dict[str, set[str]], dict[str, Any]]:
    with open(geojson_path, encoding="utf-8") as f:
        geojson = json.load(f)

    sigungu_vertices: dict[str, set[tuple[float, float]]] = defaultdict(set)
    dong_count_by_sigungu: dict[str, int] = defaultdict(int)
    vertex_to_sigungu: dict[tuple[float, float], set[str]] = defaultdict(set)

    n_dong = 0
    for feature in geojson["features"]:
        sgg = str(feature["properties"][sgg_property])
        vertices = {(round(x, precision), round(y, precision)) for x, y in _iter_coordinates(feature["geometry"])}
        if not vertices:
            continue
        n_dong += 1
        dong_count_by_sigungu[sgg] += 1
        sigungu_vertices[sgg] |= vertices
        for v in vertices:
            vertex_to_sigungu[v].add(sgg)

    shared_counts: dict[tuple[str, str], int] = defaultdict(int)
    for sggs in vertex_to_sigungu.values():
        if len(sggs) < 2:
            continue
        for a, b in itertools.combinations(sorted(sggs), 2):
            shared_counts[(a, b)] += 1

    adjacency: dict[str, set[str]] = {code: set() for code in sigungu_vertices}
    for (a, b), count in shared_counts.items():
        if count >= MIN_SHARED_VERTICES:
            adjacency[a].add(b)
            adjacency[b].add(a)

    centroid: dict[str, tuple[float, float]] = {
        code: (sum(v[0] for v in verts) / len(verts), sum(v[1] for v in verts) / len(verts))
        for code, verts in sigungu_vertices.items()
    }

    # 강서구(26440)·영도구(26200) 등 섬/해협 지형은 육지 경계를 공유하지 않아
    # 인접이 0개로 나올 수 있다 - spatial_autocorrelation._load_busan_adjacency_uncached와
    # 동일한 관례(최근접 지역 중심점 거리 기준 1개 연결)를 그대로 따른다. 안 그러면 그
    # 지역의 공간가중치 행이 전부 0이 되어 Moran's I 행 정규화가 깨진다.
    isolated = sorted(code for code, neighbors in adjacency.items() if not neighbors)
    isolated_connections: list[dict[str, str]] = []
    for code in isolated:
        cx, cy = centroid[code]
        candidates = [other for other in sigungu_vertices if other != code]
        if not candidates:
            continue
        nearest = min(candidates, key=lambda other: (centroid[other][0] - cx) ** 2 + (centroid[other][1] - cy) ** 2)
        logger.info(
            "시군구 공간 인접성: '%s'는 경계를 공유하는 시군구가 없어(섬/해협 등) 최근접 시군구 '%s'에 연결합니다.",
            code,
            nearest,
        )
        adjacency[code].add(nearest)
        adjacency[nearest].add(code)
        isolated_connections.append(
            {"region_code": code, "connected_to": nearest, "reason": "폴리곤 경계 미공유(섬/해협 등 지형)"}
        )

    report = {
        "source": "boundary_loader(행정동 경계 dissolve)",
        "n_dong_features": n_dong,
        "n_sigungu": len(sigungu_vertices),
        "dong_count_by_sigungu": dict(sorted(dong_count_by_sigungu.items())),
        "min_shared_vertices": MIN_SHARED_VERTICES,
        "coord_precision": precision,
        "isolated_sigungu_connections": isolated_connections,
        "adjacency_edge_count": sum(len(v) for v in adjacency.values()) // 2,
    }
    return adjacency, report
