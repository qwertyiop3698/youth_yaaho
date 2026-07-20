"""리워드 제공자 인터페이스와 네트워크를 사용하지 않는 모의 구현."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
import uuid


@dataclass(frozen=True)
class RewardResult:
    status: str
    provider_reference: str | None


class RewardProvider(Protocol):
    def grant(self, *, reward_id: str, user_id: str, amount: int) -> RewardResult: ...


class MockRewardProvider:
    """실제 동백전 호출 없이 지급 완료 상태만 모의한다."""

    def grant(self, *, reward_id: str, user_id: str, amount: int) -> RewardResult:
        del user_id, amount
        return RewardResult(status="mock_paid", provider_reference=f"mock:{reward_id}:{uuid.uuid4().hex[:8]}")
