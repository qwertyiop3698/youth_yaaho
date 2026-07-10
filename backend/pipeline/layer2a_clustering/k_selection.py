"""Layer 2-A - GMM 클러스터 개수(K) 탐색.

docs/04: "K=3~10 범위에서 BIC와 실루엣 스코어를 동시 계산, elbow 지점에서 K 확정.
임의로 6개 정하지 않고 통계적으로 검증한다." / "공분산 구조: full vs diagonal 비교,
BIC로 최적 구조 선택."

"elbow 지점"은 BIC 최소값을 기준으로 근사한다(component 수가 늘수록 파라미터가
늘어 BIC가 복잡도 페널티를 자동으로 반영하므로, BIC 최소 지점이 실무적으로 흔히
쓰이는 elbow 근사 방법이다). 실루엣 스코어는 참고 지표로 함께 기록한다.

표본이 작으면(sample.csv=5행 등) GMM 자체가 통계적으로 무의미하므로(공분산 추정
불가) 탐색을 생략하고 경고를 남긴다.
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np
from sklearn.mixture import GaussianMixture
from sklearn.metrics import silhouette_score

logger = logging.getLogger(__name__)

K_RANGE = range(3, 11)  # doc04: K=3~10
COVARIANCE_TYPES = ("full", "diag")
MIN_SAMPLE_FOR_CLUSTERING = 30  # GMM 공분산 추정이 안정적이려면 필요한 경험적 최소 표본


def select_k(
    X: np.ndarray,
    k_range: range = K_RANGE,
    covariance_types: tuple[str, ...] = COVARIANCE_TYPES,
    min_sample: int = MIN_SAMPLE_FOR_CLUSTERING,
    random_state: int = 42,
) -> dict[str, Any]:
    """K/공분산구조 조합별 BIC·실루엣 스코어를 계산하고 BIC 최소 조합을 추천한다.

    표본이 min_sample 미만이면 GMM 공분산 추정 자체가 불안정하므로 탐색을 생략하고
    사유를 리포트에 남긴다(sample.csv=5행에서 K=3짜리 GMM을 학습하는 건 통계적으로
    무의미함 - 5차원 공분산행렬을 1~2개 관측치로 추정하는 셈).
    """
    n = len(X)
    if n < min_sample:
        logger.warning(
            "GMM K 탐색: 표본 부족(n=%d < %d)으로 BIC/실루엣 기반 탐색을 생략합니다. "
            "실데이터(표본 충분)에서는 정상 동작합니다.",
            n,
            min_sample,
        )
        return {
            "skipped": True,
            "reason": f"표본 부족(n={n} < {min_sample})",
            "candidates": [],
            "best_k": None,
            "best_covariance_type": None,
        }

    candidates: list[dict[str, Any]] = []
    for k in k_range:
        if k >= n:
            logger.warning("GMM K 탐색: K=%d는 표본 수(%d) 이상이라 건너뜁니다.", k, n)
            continue
        for cov_type in covariance_types:
            try:
                gmm = GaussianMixture(
                    n_components=k, covariance_type=cov_type, random_state=random_state, n_init=5
                )
                labels = gmm.fit_predict(X)
                bic = gmm.bic(X)
                sil = silhouette_score(X, labels) if len(set(labels)) > 1 else float("nan")
            except Exception as exc:  # noqa: BLE001 - 특정 K/공분산 조합 실패는 건너뛰고 계속 진행
                logger.warning("GMM K 탐색: K=%d, covariance=%s 학습 실패(%s) - 건너뜁니다.", k, cov_type, exc)
                continue
            candidates.append(
                {"k": k, "covariance_type": cov_type, "bic": float(bic), "silhouette": float(sil)}
            )

    if not candidates:
        logger.warning("GMM K 탐색: 유효한 K 후보가 없습니다(표본 수 대비 K 범위 부적절).")
        return {
            "skipped": True,
            "reason": "표본 수 대비 유효한 K 후보 없음",
            "candidates": [],
            "best_k": None,
            "best_covariance_type": None,
        }

    best = min(candidates, key=lambda c: c["bic"])
    return {
        "skipped": False,
        "candidates": candidates,
        "best_k": best["k"],
        "best_covariance_type": best["covariance_type"],
    }
