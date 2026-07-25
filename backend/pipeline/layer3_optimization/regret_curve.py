"""Layer 3 - Thompson Sampling 학습곡선(regret curve) 산출 (docs/05 5-2).

밴딧이 라운드를 거치며 정책별 효과를 얼마나 잘 추정해가는지 보여주는 regret curve
데이터를 만든다. Y-SAFE 대시보드 "밴딧 학습 현황" 화면(docs/10)에서 사용.

**반드시 "실제 운영 전 검증용 시뮬레이션"이라고 라벨링할 것** - true_effectiveness는
숨겨둔 합성 정답이지 실제 정책 효과가 아니다(doc05 명시, 과장 금지).

2026-07-09 사용자 지적 및 보강
--------------------------------
누적 regret(cumulative_regret)의 "단조 비감소"는 instant_regret >= 0이 항상 성립하는
한 자동으로 참이라, 밴딧이 실제로 학습하고 있는지는 증명하지 못한다(그냥 계속
더해지기만 해도 단조 비감소니까). 실질적인 학습 검증은 "구간별 평균 순간 regret이
후반으로 갈수록 줄어드는가"(sublinear growth)이므로, 이를 별도로 계산해
segment_regret으로 결과에 포함시킨다 - Y-SAFE 대시보드에서 "학습이 진행될수록
후회가 줄어든다"를 막대그래프 등으로 시각화할 수 있게 하기 위함이다.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from tqdm import tqdm

from . import synthetic_reward
from .thompson_sampling import ThompsonSamplingBandit

DEFAULT_SEGMENT_LABELS = ["초반", "중반", "후반"]


def compute_segment_average_regret(
    history: pd.DataFrame, n_segments: int = 3, segment_labels: list[str] | None = None
) -> pd.DataFrame:
    """라운드를 n_segments개 구간(기본: 초반/중반/후반)으로 나눠 구간별 평균 순간
    regret(instant_regret)을 계산한다.

    후반 구간으로 갈수록 평균이 줄어들면 밴딧이 실제로 좋은 정책 쪽으로 수렴하고
    있다는 증거다(sublinear regret growth). 누적 regret의 단조성과 달리, 이 지표는
    "학습이 안 되고 있다"는 반례가 실제로 존재할 수 있는 검증이다(예: 랜덤 선택이면
    구간별 평균이 거의 일정해야 함).
    """
    n_rounds = len(history)
    segment_labels = segment_labels or DEFAULT_SEGMENT_LABELS
    n_segments = min(n_segments, n_rounds) if n_rounds else n_segments
    if n_segments <= 0:
        return pd.DataFrame(
            columns=["segment_index", "segment_label", "round_start", "round_end", "mean_instant_regret"]
        )

    segment_size = n_rounds // n_segments
    rows = []
    for i in range(n_segments):
        start = i * segment_size
        end = (i + 1) * segment_size if i < n_segments - 1 else n_rounds
        segment_df = history.iloc[start:end]
        label = segment_labels[i] if i < len(segment_labels) else f"segment_{i}"
        rows.append(
            {
                "segment_index": i,
                "segment_label": label,
                "round_start": int(start),
                "round_end": int(end - 1),
                "mean_instant_regret": float(segment_df["instant_regret"].mean()) if len(segment_df) else None,
            }
        )
    return pd.DataFrame(rows)


def run_bandit_simulation(
    policy_names: list[str],
    n_rounds: int,
    true_effectiveness: dict[str, float] | None = None,
    seed: int = 42,
    n_segments: int = 3,
) -> dict[str, Any]:
    """n_rounds 동안 Thompson Sampling 밴딧을 시뮬레이션하고 regret curve 데이터를 만든다."""
    rng = np.random.default_rng(seed)
    true_effectiveness = true_effectiveness or synthetic_reward.DEFAULT_TRUE_EFFECTIVENESS
    bandit = ThompsonSamplingBandit(policy_names)

    best_true_rate = max(true_effectiveness.get(p, 0.5) for p in policy_names)

    cumulative_regret = 0.0
    history = []
    for round_idx in tqdm(range(n_rounds), desc="[Layer3] Thompson Sampling 시뮬레이션", unit="라운드"):
        chosen = bandit.select_policy(rng)
        success = synthetic_reward.simulate_reward(chosen, true_effectiveness, rng)
        bandit.update(chosen, success)

        instant_regret = best_true_rate - true_effectiveness.get(chosen, 0.5)
        cumulative_regret += instant_regret
        history.append(
            {
                "round": round_idx,
                "chosen_policy": chosen,
                "success": success,
                "instant_regret": instant_regret,
                "cumulative_regret": cumulative_regret,
            }
        )

    history_df = pd.DataFrame(history)

    return {
        "is_simulation": True,  # doc05: 실제 운영 전 검증용 시뮬레이션임을 데이터에도 명시
        "history": history_df,
        "segment_regret": compute_segment_average_regret(history_df, n_segments=n_segments),
        "final_posterior_means": bandit.posterior_means(),
        "bandit_state": bandit.state(),
        "true_effectiveness": dict(true_effectiveness),
    }
