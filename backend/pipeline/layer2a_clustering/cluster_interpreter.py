"""Layer 2-A - 클러스터 해석 및 라벨링.

docs/04: "각 클러스터 중심(μ_k)의 5차원 프로파일을 레이더 차트로 시각화. 사전 가설
(6개 도메인 유형)과 실제 클러스터 결과를 대조. 일치/불일치 모두 발표 소재로 기록."
"""
from __future__ import annotations

import pandas as pd
from sklearn.mixture import GaussianMixture

from .gmm_trainer import DOMAIN_INDEX_COLUMNS

# docs/04 사전 가설 6개 도메인 유형(참고용 - 실제 매핑은 사람이 최종 확정해야 함)
HYPOTHESIZED_CLUSTER_TYPES = [
    "주거비압박형",
    "부채과부하형",
    "소득공백형",
    "소비유동성위험형",
    "Thin Filer형",
    "자산형성가능형",
]

# 도메인지수 -> 그 지수가 가장 두드러질 때 대응되는 가설 유형(단순 argmax 매핑).
# "Thin Filer형"/"자산형성가능형"은 단일 지수의 argmax만으로 판단할 수 없어(전자는
# Thin Filer 플래그, 후자는 "모든 지수가 낮음" 같은 복합 조건이 필요) 이 매핑에서
# 의도적으로 제외했다 - 사람이 직접 검토해야 하는 부분이다.
_DOMAIN_TO_HYPOTHESIS = {
    "주거비압박지수": "주거비압박형",
    "부채상환위험지수": "부채과부하형",
    "소득변동성지수": "소득공백형",
    "소비압박지수": "소비유동성위험형",
    "신용취약지수": "신용취약형(가설 목록 밖 - 사람 확인 필요)",
}


def compute_cluster_profiles(
    model: GaussianMixture, columns: list[str] = DOMAIN_INDEX_COLUMNS
) -> pd.DataFrame:
    """각 클러스터 중심(μ_k)의 도메인지수 프로파일 - 레이더차트 원본 데이터."""
    return pd.DataFrame(
        model.means_, columns=columns, index=[f"cluster_{i}" for i in range(model.n_components)]
    )


def compute_cluster_sizes(membership_df: pd.DataFrame) -> pd.Series:
    """클러스터별 (소프트) 인원수 - responsibility 합계."""
    cluster_cols = [c for c in membership_df.columns if c.startswith("cluster_")]
    return membership_df[cluster_cols].sum()


def suggest_cluster_labels(cluster_profiles: pd.DataFrame) -> dict[str, str]:
    """클러스터 프로파일에서 가장 두드러진(z-score가 가장 큰) 도메인지수를 기준으로
    사전 가설 라벨 "초안"을 제안한다.

    주의: 이건 자동 확정이 아니라 발표 자료 작성을 돕는 초안일 뿐이다(docs/04:
    "일치/불일치 모두 발표 소재로 기록"). 특히 "Thin Filer형"/"자산형성가능형"은
    이 함수가 절대 자동으로 붙이지 않으므로 반드시 사람이 직접 확인해야 한다.
    """
    suggestions = {}
    for cluster_name, row in cluster_profiles.iterrows():
        top_index = row.idxmax()
        suggestions[cluster_name] = _DOMAIN_TO_HYPOTHESIS.get(top_index, "미분류(사람 확인 필요)")
    return suggestions
