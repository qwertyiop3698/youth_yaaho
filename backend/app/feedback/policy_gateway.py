"""기존 Layer 3 정책 카탈로그와 피드백 도메인을 잇는 읽기 전용 어댑터."""
from __future__ import annotations

from typing import Protocol

from ..services.pipeline_store import PipelineStore


class PolicyRepository(Protocol):
    def get_available_policy(self, policy_id: str) -> dict | None: ...


class CatalogPolicyRepository:
    """현재 추천에 쓰이는 검증된 정적 카탈로그만 신규 이용기록 대상으로 허용한다.

    종료 정책 전체를 별도 조회하거나 추천하지 않는다. 과거 정책은 이미 저장된
    PolicyUsage가 있을 때만 내 기록에서 보이게 된다.
    """

    def __init__(self, store: PipelineStore) -> None:
        self.store = store

    def get_available_policy(self, policy_id: str) -> dict | None:
        policies = self.store.policy_catalog.get("policies", {})
        if policy_id in policies:
            return {"policy_id": policy_id, "policy_name": policy_id, "policy_source": "layer3_catalog"}
        for name, config in policies.items():
            if config.get("youthcenter_plcy_no") == policy_id:
                return {"policy_id": policy_id, "policy_name": name, "policy_source": "youthcenter"}
        return None
