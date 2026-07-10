"""Layer 3 - Thompson Sampling 기반 지속학습 (docs/05 5-2).

정책 p의 효과를 베타분포로 모델링한다: θ_p ~ Beta(α_p, β_p).
라운드마다:
    1. 각 정책 p에 대해 θ_p 샘플링
    2. θ_p가 높은 정책을 우선 배정(탐색 vs 활용 균형)
    3. 배정 후 관측된 효과로 사후분포 갱신: 성공 시 α_p += 1, 실패 시 β_p += 1

실제 라벨이 없으므로 synthetic_reward.py의 합성 리워드로 시뮬레이션한다. 발표 시
반드시 "실제 운영 전 검증용 시뮬레이션"이라고 라벨링해야 한다(doc05 명시, 과장 금지).
"""
from __future__ import annotations

from typing import Iterable

import numpy as np


class ThompsonSamplingBandit:
    """정책별 Beta(α, β) 사후분포를 관리하는 밴딧."""

    def __init__(self, policy_names: Iterable[str], prior_alpha: float = 1.0, prior_beta: float = 1.0):
        self.policy_names = list(policy_names)
        self.alpha = {p: prior_alpha for p in self.policy_names}
        self.beta = {p: prior_beta for p in self.policy_names}

    def sample_theta(self, rng: np.random.Generator | None = None) -> dict[str, float]:
        rng = rng or np.random.default_rng()
        return {p: float(rng.beta(self.alpha[p], self.beta[p])) for p in self.policy_names}

    def select_policy(self, rng: np.random.Generator | None = None) -> str:
        """θ_p를 샘플링해 가장 높은 정책을 선택한다(탐색/활용 자동 균형)."""
        theta = self.sample_theta(rng)
        return max(theta, key=theta.get)

    def update(self, policy_name: str, success: bool) -> None:
        if success:
            self.alpha[policy_name] += 1
        else:
            self.beta[policy_name] += 1

    def posterior_mean(self, policy_name: str) -> float:
        return self.alpha[policy_name] / (self.alpha[policy_name] + self.beta[policy_name])

    def posterior_means(self) -> dict[str, float]:
        return {p: self.posterior_mean(p) for p in self.policy_names}

    def state(self) -> dict[str, dict[str, float]]:
        return {p: {"alpha": self.alpha[p], "beta": self.beta[p]} for p in self.policy_names}
