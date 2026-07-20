"""공통 백엔드 - 온통청년 Open API 연동.

두 가지 용도로 쓴다:

1. get_policy_url(plcy_no): policy_catalog.yaml에 매핑해둔 6개 정밀매칭
   정책의 신청 URL을 정책번호로 조회(aplyUrlAddr, 비어있으면 refUrlAddr1 →
   refUrlAddr2 순으로 폴백).
2. search_policies_by_region(zip_cd): 시군구코드로 그 지역에 적용되는 정책을
   전부 검색한다(zipCd에 전국단위 정책은 모든 시군구코드가 다 들어있으므로,
   이 한 번의 호출로 전국+광역시+구 단위 정책이 함께 조회된다 - 2026-07-15
   실측 확인). 6개 정밀매칭 정책처럼 도메인지수 기반 Δrisk 순위를 매길 수는
   없지만("어떤 위험을 얼마나 줄여주는지"에 대한 effectiveness_prior가 없는
   비검증 정책들이라), "신청 가능한 정책이 6개뿐"이라는 문제를 완화하기 위해
   순위 없이 카테고리별 목록으로 보여준다.

API 키 누락/네트워크 오류/타임아웃/응답 이상 등 어떤 이유로든 실패해도
예외를 삼키고 빈 값(None 또는 [])을 반환한다 - explanation_service의 Claude
API 폴백 패턴과 동일하게, 이 연동이 죽어도 정책 추천 자체는 항상 동작해야
한다.

응답은 프로세스 메모리에 TTL 캐시해서 추천 요청마다 매번 외부 API를 호출하지
않도록 한다.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any
from urllib.parse import urlparse

import httpx

from .. import config  # noqa: F401 - .env를 아래 os.environ.get(...)보다 먼저 로드

logger = logging.getLogger(__name__)

API_URL = "https://www.youthcenter.go.kr/go/ythip/getPlcy"
REQUEST_TIMEOUT_SECONDS = 5.0
CACHE_TTL_SECONDS = 3600
REGION_SEARCH_PAGE_SIZE = 100
DESCRIPTION_MAX_LENGTH = 200

_cache: dict[str, tuple[float, str | None]] = {}
_region_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}


def _extract_url(item: dict[str, Any]) -> str | None:
    for field in ("aplyUrlAddr", "refUrlAddr1", "refUrlAddr2"):
        url = (item.get(field) or "").strip()
        parsed = urlparse(url)
        if parsed.scheme == "https" and parsed.hostname:
            return url
    return None


def _extract_description(item: dict[str, Any]) -> str | None:
    description = (item.get("plcyExplnCn") or "").strip()
    if not description:
        return None
    if len(description) > DESCRIPTION_MAX_LENGTH:
        description = description[:DESCRIPTION_MAX_LENGTH].rstrip() + "…"
    return description


def _fetch_policy_url_raw(plcy_no: str) -> str | None:
    api_key = os.environ.get("YOUTHCENTER_API_KEY")
    if not api_key:
        return None

    response = httpx.get(
        API_URL,
        params={
            "apiKeyNm": api_key,
            "plcyNo": plcy_no,
            "pageNum": 1,
            "pageSize": 1,
            "rtnType": "json",
        },
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    body: dict[str, Any] = response.json()

    items = (body.get("result") or {}).get("youthPolicyList") or []
    if isinstance(items, dict):  # 결과가 1건이면 API가 배열이 아닌 객체로 줄 때가 있음
        items = [items]
    if not items:
        return None
    return _extract_url(items[0])


def get_policy_url(plcy_no: str | None) -> str | None:
    """정책번호로 신청 URL을 조회한다. 실패 시 None(호출부는 폴백 처리 불필요)."""
    if not plcy_no:
        return None

    cached = _cache.get(plcy_no)
    if cached is not None and (time.monotonic() - cached[0]) < CACHE_TTL_SECONDS:
        return cached[1]

    try:
        url = _fetch_policy_url_raw(plcy_no)
    except Exception as exc:  # noqa: BLE001 - 온통청년 API 실패가 추천 응답 전체를 막으면 안 됨
        logger.warning("온통청년 API 조회 실패(plcyNo=%s), url=None으로 폴백합니다: %s", plcy_no, exc)
        url = None

    _cache[plcy_no] = (time.monotonic(), url)
    return url


def _fetch_policies_by_region_raw(zip_cd: str) -> list[dict[str, Any]]:
    api_key = os.environ.get("YOUTHCENTER_API_KEY")
    if not api_key:
        return []

    response = httpx.get(
        API_URL,
        params={
            "apiKeyNm": api_key,
            "zipCd": zip_cd,
            "pageNum": 1,
            "pageSize": REGION_SEARCH_PAGE_SIZE,
            "rtnType": "json",
        },
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    body: dict[str, Any] = response.json()

    items = (body.get("result") or {}).get("youthPolicyList") or []
    if isinstance(items, dict):
        items = [items]

    return [
        {
            "plcyNo": item.get("plcyNo"),
            "policy": item.get("plcyNm"),
            "category": item.get("lclsfNm"),
            "agency": item.get("sprvsnInstCdNm"),
            "description": _extract_description(item),
            "url": _extract_url(item),
            "apply_period": (item.get("aplyYmd") or "").strip() or None,
            "min_age": item.get("sprtTrgtMinAge"),
            "max_age": item.get("sprtTrgtMaxAge"),
            "age_limited": item.get("sprtTrgtAgeLmtYn") == "Y",
        }
        for item in items
        if item.get("plcyNo") and item.get("plcyNm")
    ]


def search_policies_by_region(zip_cd: str | None) -> list[dict[str, Any]]:
    """시군구코드로 적용 가능한 정책 전체를 검색한다. 실패 시 빈 리스트."""
    if not zip_cd:
        return []

    cached = _region_cache.get(zip_cd)
    if cached is not None and (time.monotonic() - cached[0]) < CACHE_TTL_SECONDS:
        return cached[1]

    try:
        policies = _fetch_policies_by_region_raw(zip_cd)
    except Exception as exc:  # noqa: BLE001 - 온통청년 API 실패가 추천 응답 전체를 막으면 안 됨
        logger.warning("온통청년 지역 정책 검색 실패(zipCd=%s), 빈 목록으로 폴백합니다: %s", zip_cd, exc)
        policies = []

    _region_cache[zip_cd] = (time.monotonic(), policies)
    return policies
