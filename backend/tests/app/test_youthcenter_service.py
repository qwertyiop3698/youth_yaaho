"""app/services/youthcenter_service.get_policy_url() 폴백 체인 테스트.

conftest.py의 _no_real_youthcenter_calls autouse fixture가 get_policy_url
자체를 monkeypatch하므로, 여기서는 그 아래 단계(_fetch_policy_url_raw, 캐시,
os.environ 키 체크)를 직접 호출해서 검증한다 - autouse fixture를 우회하기
위해 각 테스트에서 명시적으로 되돌린다.
"""
from __future__ import annotations

import httpx
import pytest

from app.services import youthcenter_service


@pytest.fixture(autouse=True)
def _real_get_policy_url(monkeypatch):
    """이 파일의 테스트들은 get_policy_url 자체의 동작을 검증하는 게 목적이므로,
    conftest의 autouse 폴백(monkeypatch로 None 고정)을 원래 구현으로 되돌린다."""
    monkeypatch.undo()
    yield


@pytest.fixture(autouse=True)
def _clear_cache():
    youthcenter_service._cache.clear()
    youthcenter_service._region_cache.clear()
    yield
    youthcenter_service._cache.clear()
    youthcenter_service._region_cache.clear()


def _fake_response(payload: dict, status_code: int = 200):
    request = httpx.Request("GET", youthcenter_service.API_URL)
    return httpx.Response(status_code, json=payload, request=request)


class TestGetPolicyUrl:
    def test_returns_none_when_api_key_unset(self, monkeypatch):
        monkeypatch.delenv("YOUTHCENTER_API_KEY", raising=False)

        assert youthcenter_service.get_policy_url("20260513005400213199") is None

    def test_returns_none_when_plcy_no_missing(self, monkeypatch):
        monkeypatch.setenv("YOUTHCENTER_API_KEY", "dummy-key")

        assert youthcenter_service.get_policy_url(None) is None

    def test_uses_aply_url_addr_when_present(self, monkeypatch):
        monkeypatch.setenv("YOUTHCENTER_API_KEY", "dummy-key")
        monkeypatch.setattr(
            httpx,
            "get",
            lambda *a, **k: _fake_response(
                {"result": {"youthPolicyList": [{"aplyUrlAddr": "https://young.busan.go.kr/apply", "refUrlAddr1": "https://ignored"}]}}
            ),
        )

        assert youthcenter_service.get_policy_url("plcy-1") == "https://young.busan.go.kr/apply"

    def test_falls_back_to_ref_url_addr1_when_aply_url_empty(self, monkeypatch):
        monkeypatch.setenv("YOUTHCENTER_API_KEY", "dummy-key")
        monkeypatch.setattr(
            httpx,
            "get",
            lambda *a, **k: _fake_response(
                {"result": {"youthPolicyList": [{"aplyUrlAddr": "", "refUrlAddr1": "https://young.busan.go.kr/ref"}]}}
            ),
        )

        assert youthcenter_service.get_policy_url("plcy-2") == "https://young.busan.go.kr/ref"

    def test_returns_none_when_no_results(self, monkeypatch):
        monkeypatch.setenv("YOUTHCENTER_API_KEY", "dummy-key")
        monkeypatch.setattr(httpx, "get", lambda *a, **k: _fake_response({"result": {"youthPolicyList": []}}))

        assert youthcenter_service.get_policy_url("plcy-3") is None

    def test_swallows_network_exception_and_returns_none(self, monkeypatch):
        monkeypatch.setenv("YOUTHCENTER_API_KEY", "dummy-key")

        def _raise(*args, **kwargs):
            raise httpx.ConnectTimeout("timed out")

        monkeypatch.setattr(httpx, "get", _raise)

        assert youthcenter_service.get_policy_url("plcy-4") is None

    def test_caches_result_and_does_not_call_twice(self, monkeypatch):
        monkeypatch.setenv("YOUTHCENTER_API_KEY", "dummy-key")
        call_count = {"n": 0}

        def _get(*args, **kwargs):
            call_count["n"] += 1
            return _fake_response({"result": {"youthPolicyList": [{"aplyUrlAddr": "https://example.com"}]}})

        monkeypatch.setattr(httpx, "get", _get)

        first = youthcenter_service.get_policy_url("plcy-5")
        second = youthcenter_service.get_policy_url("plcy-5")

        assert first == second == "https://example.com"
        assert call_count["n"] == 1


class TestSearchPoliciesByRegion:
    def test_returns_empty_list_when_api_key_unset(self, monkeypatch):
        monkeypatch.delenv("YOUTHCENTER_API_KEY", raising=False)

        assert youthcenter_service.search_policies_by_region("26440") == []

    def test_returns_empty_list_when_zip_cd_missing(self, monkeypatch):
        monkeypatch.setenv("YOUTHCENTER_API_KEY", "dummy-key")

        assert youthcenter_service.search_policies_by_region(None) == []

    def test_normalizes_fields_from_raw_items(self, monkeypatch):
        monkeypatch.setenv("YOUTHCENTER_API_KEY", "dummy-key")
        monkeypatch.setattr(
            httpx,
            "get",
            lambda *a, **k: _fake_response(
                {
                    "result": {
                        "youthPolicyList": [
                            {
                                "plcyNo": "P1",
                                "plcyNm": "부산 청년 정책",
                                "lclsfNm": "주거",
                                "sprvsnInstCdNm": "부산광역시",
                                "aplyUrlAddr": "https://example.com/apply",
                                "aplyYmd": "20260101 ~ 20261231",
                                "sprtTrgtMinAge": "19",
                                "sprtTrgtMaxAge": "34",
                                "sprtTrgtAgeLmtYn": "Y",
                            }
                        ]
                    }
                }
            ),
        )

        result = youthcenter_service.search_policies_by_region("26440")

        assert result == [
            {
                "plcyNo": "P1",
                "policy": "부산 청년 정책",
                "category": "주거",
                "agency": "부산광역시",
                "url": "https://example.com/apply",
                "apply_period": "20260101 ~ 20261231",
                "min_age": "19",
                "max_age": "34",
                "age_limited": True,
            }
        ]

    def test_skips_items_without_plcy_no_or_name(self, monkeypatch):
        monkeypatch.setenv("YOUTHCENTER_API_KEY", "dummy-key")
        monkeypatch.setattr(
            httpx,
            "get",
            lambda *a, **k: _fake_response(
                {"result": {"youthPolicyList": [{"plcyNo": "", "plcyNm": "이름만 있음"}, {"plcyNo": "P2"}]}}
            ),
        )

        assert youthcenter_service.search_policies_by_region("26440") == []

    def test_swallows_network_exception_and_returns_empty_list(self, monkeypatch):
        monkeypatch.setenv("YOUTHCENTER_API_KEY", "dummy-key")

        def _raise(*args, **kwargs):
            raise httpx.ConnectTimeout("timed out")

        monkeypatch.setattr(httpx, "get", _raise)

        assert youthcenter_service.search_policies_by_region("26440") == []

    def test_caches_result_and_does_not_call_twice(self, monkeypatch):
        monkeypatch.setenv("YOUTHCENTER_API_KEY", "dummy-key")
        call_count = {"n": 0}

        def _get(*args, **kwargs):
            call_count["n"] += 1
            return _fake_response({"result": {"youthPolicyList": [{"plcyNo": "P1", "plcyNm": "정책"}]}})

        monkeypatch.setattr(httpx, "get", _get)

        youthcenter_service.search_policies_by_region("26440")
        youthcenter_service.search_policies_by_region("26440")

        assert call_count["n"] == 1
