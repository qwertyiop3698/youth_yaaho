"""app/services/recommendation_service.list_other_policies() 테스트.

conftest.py의 _no_real_youthcenter_calls autouse fixture가
youthcenter_service.search_policies_by_region을 기본적으로 빈 리스트로
고정하므로, 각 테스트가 필요에 따라 monkeypatch로 결과를 채워 넣는다.
"""
from __future__ import annotations

from app.services import recommendation_service, youthcenter_service


class _FakeStore:
    def __init__(self, policies: dict) -> None:
        self.policy_catalog = {"policies": policies}


CURATED_POLICIES = {
    "청년월세지원": {"youthcenter_plcy_no": "P1"},
    "머물자리론": {"youthcenter_plcy_no": "P2"},
}


class TestListOtherPolicies:
    def test_excludes_policies_already_in_catalog(self, monkeypatch):
        monkeypatch.setattr(
            youthcenter_service,
            "search_policies_by_region",
            lambda zip_cd: [
                {"plcyNo": "P1", "policy": "청년월세지원", "category": "주거", "agency": "부산광역시", "url": None, "apply_period": None},
                {"plcyNo": "P99", "policy": "부산 청년두드림센터 운영", "category": "일자리", "agency": "부산광역시", "url": "https://x", "apply_period": None},
            ],
        )

        result = recommendation_service.list_other_policies(
            {"dong_code": "26440", "age_group": "25-29"}, _FakeStore(CURATED_POLICIES)
        )

        assert [p["policy"] for p in result] == ["부산 청년두드림센터 운영"]

    def test_filters_out_policies_outside_age_range(self, monkeypatch):
        monkeypatch.setattr(
            youthcenter_service,
            "search_policies_by_region",
            lambda zip_cd: [
                {
                    "plcyNo": "P10",
                    "policy": "40대 전용 정책",
                    "category": "복지문화",
                    "agency": "부산광역시",
                    "url": None,
                    "apply_period": None,
                    "min_age": "40",
                    "max_age": "49",
                    "age_limited": True,
                },
                {
                    "plcyNo": "P11",
                    "policy": "청년 전용 정책",
                    "category": "복지문화",
                    "agency": "부산광역시",
                    "url": None,
                    "apply_period": None,
                    "min_age": "19",
                    "max_age": "34",
                    "age_limited": True,
                },
            ],
        )

        result = recommendation_service.list_other_policies(
            {"dong_code": "26440", "age_group": "25-29"}, _FakeStore({})
        )

        assert [p["policy"] for p in result] == ["청년 전용 정책"]

    def test_keeps_policy_when_age_unknown(self, monkeypatch):
        monkeypatch.setattr(
            youthcenter_service,
            "search_policies_by_region",
            lambda zip_cd: [
                {
                    "plcyNo": "P12",
                    "policy": "나이제한 정책",
                    "category": "일자리",
                    "agency": "부산광역시",
                    "url": None,
                    "apply_period": None,
                    "min_age": "40",
                    "max_age": "49",
                    "age_limited": True,
                }
            ],
        )

        result = recommendation_service.list_other_policies({"dong_code": "26440", "age_group": ""}, _FakeStore({}))

        assert [p["policy"] for p in result] == ["나이제한 정책"]

    def test_keeps_policy_when_not_age_limited(self, monkeypatch):
        monkeypatch.setattr(
            youthcenter_service,
            "search_policies_by_region",
            lambda zip_cd: [
                {
                    "plcyNo": "P13",
                    "policy": "나이제한 없음",
                    "category": "일자리",
                    "agency": "부산광역시",
                    "url": None,
                    "apply_period": None,
                    "min_age": "0",
                    "max_age": "0",
                    "age_limited": False,
                }
            ],
        )

        result = recommendation_service.list_other_policies(
            {"dong_code": "26440", "age_group": "25-29"}, _FakeStore({})
        )

        assert [p["policy"] for p in result] == ["나이제한 없음"]

    def test_returns_empty_list_when_search_returns_nothing(self):
        # autouse fixture가 search_policies_by_region을 빈 리스트로 고정
        result = recommendation_service.list_other_policies(
            {"dong_code": "26440", "age_group": "25-29"}, _FakeStore(CURATED_POLICIES)
        )

        assert result == []

    def test_output_shape_matches_other_policy_item_fields(self, monkeypatch):
        monkeypatch.setattr(
            youthcenter_service,
            "search_policies_by_region",
            lambda zip_cd: [
                {
                    "plcyNo": "P14",
                    "policy": "정책명",
                    "category": "주거",
                    "agency": "부산광역시",
                    "url": "https://example.com",
                    "apply_period": "20260101 ~ 20261231",
                }
            ],
        )

        result = recommendation_service.list_other_policies({"dong_code": "26440", "age_group": ""}, _FakeStore({}))

        assert result == [
            {
                "policy": "정책명",
                "category": "주거",
                "agency": "부산광역시",
                "url": "https://example.com",
                "apply_period": "20260101 ~ 20261231",
            }
        ]
