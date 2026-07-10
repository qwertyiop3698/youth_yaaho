"""Layer 3 - 합성 리워드 함수 (docs/05 5-2).

실제 정책 신청/수혜/효과 라벨이 없으므로, 정책별 "실제 효과 확률"을 미리 정의해
숨겨두고(DEFAULT_TRUE_EFFECTIVENESS) 밴딧이 라운드를 거치며 이 값을 추정해가는
과정을 시뮬레이션한다.

**중요**: 이 값들은 시뮬레이션 전용 "숨겨진 정답"이며 실제 정책 효과가 아니다.
policy_catalog.yaml의 effectiveness_prior(LP가 사용하는 초기 가정치)와는 다른
값이다 - 밴딧이 라운드를 거치며 이 숨겨진 값에 얼마나 잘 수렴하는지 보여주기 위한
장치일 뿐이다. 발표 시 "실제 운영 전 검증용 시뮬레이션"이라고 명확히 라벨링할 것
(doc05 명시, 과장 금지).

2026-07-09 사용자 지적 및 조정
--------------------------------
최초 버전은 모든 정책에서 true_effectiveness가 effectiveness_prior보다 0.05~0.1
정도 "항상 더 높기만" 했다(청년디딤돌카드 플러스는 격차가 0이었음). 이러면 "밴딧이
학습해서 수렴했다"는 게 사실 처음부터 prior가 거의 정답에 가까웠다는 뜻이라 데모
설득력이 없다. 그래서 정책별로 prior 대비 과대평가/과소평가가 섞이고 격차도 커지도록
(±0.2~0.25) 의도적으로 재조정했다 - 이 값도 시뮬레이션 전용이라 root cause는 없고,
순전히 "밴딧이 틀린 가정을 실제값으로 교정해간다"는 걸 보여주기 위한 데모 설계다.

policy_catalog.yaml effectiveness_prior 대비 조정 후 격차:
    청년월세지원              prior=0.5  true=0.75  gap=+0.25  (과소평가 -> 상향 조정)
    머물자리론                prior=0.5  true=0.25  gap=-0.25  (과대평가 -> 하향 조정)
    청년 중개보수·이사비 지원   prior=0.3  true=0.55  gap=+0.25  (과소평가 -> 상향 조정)
    희망신용상담센터           prior=0.4  true=0.15  gap=-0.25  (과대평가 -> 하향 조정)
    부산청년 기쁨두배통장       prior=0.4  true=0.65  gap=+0.25  (과소평가 -> 상향 조정)
    청년디딤돌카드 플러스       prior=0.3  true=0.10  gap=-0.20  (과대평가 -> 하향 조정)
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

# 정책별 숨겨진 "실제 효과 확률"(시뮬레이션 전용, 실제 근거 없음).
# 2026-07-09: prior 대비 과대/과소평가가 섞이고 격차가 커지도록 의도적으로 재조정(위 표 참고).
DEFAULT_TRUE_EFFECTIVENESS: dict[str, float] = {
    "청년월세지원": 0.75,
    "머물자리론": 0.25,
    "청년 중개보수·이사비 지원": 0.55,
    "희망신용상담센터": 0.15,
    "부산청년 기쁨두배통장": 0.65,
    "청년디딤돌카드 플러스": 0.10,
}


def simulate_reward(
    policy_name: str,
    true_effectiveness: dict[str, float] | None = None,
    rng: np.random.Generator | None = None,
) -> bool:
    """정책 배정 후 "성공/실패" 결과를 합성 리워드 함수로 시뮬레이션한다."""
    true_effectiveness = true_effectiveness or DEFAULT_TRUE_EFFECTIVENESS
    rng = rng or np.random.default_rng()
    p = true_effectiveness.get(policy_name, 0.5)
    return bool(rng.random() < p)


def compute_prior_vs_true_gap(
    policy_catalog: dict[str, Any], true_effectiveness: dict[str, float] | None = None
) -> pd.DataFrame:
    """policy_catalog.yaml의 effectiveness_prior(LP 초기 가정치)와 이 모듈의
    true_effectiveness(밴딧 시뮬레이션용 숨겨진 정답) 사이 격차를 계산한다.

    2026-07-09 사용자 요청: 격차가 거의 없으면 "밴딧이 학습했다"는 게 처음부터 정답에
    가까웠던 것 뿐이라 데모 설득력이 없으므로, 이 함수로 격차를 항상 확인할 수 있게
    한다(run.py의 optimization_report.json에도 포함됨).
    """
    true_effectiveness = true_effectiveness or DEFAULT_TRUE_EFFECTIVENESS
    rows = []
    for policy_name, policy_cfg in policy_catalog["policies"].items():
        prior = policy_cfg["effectiveness_prior"]
        true_value = true_effectiveness.get(policy_name)
        gap = None if true_value is None else round(true_value - prior, 4)
        if gap is None:
            direction = None
        elif gap > 0:
            direction = "과소평가(상향 조정 필요)"
        elif gap < 0:
            direction = "과대평가(하향 조정 필요)"
        else:
            direction = "일치"
        rows.append(
            {
                "policy": policy_name,
                "effectiveness_prior": prior,
                "true_effectiveness": true_value,
                "gap": gap,
                "direction": direction,
            }
        )
    return pd.DataFrame(rows)
