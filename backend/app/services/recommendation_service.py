"""공통 백엔드 - 정책 추천 서비스 (docs/07 GET /recommendations).

Layer3의 Δrisk_ip 공식(relevance_score × effectiveness_prior × risk_probability,
lp_allocator.compute_delta_risk)을 그대로 재사용해 "이 사람에게 어떤 정책이 가장
도움이 될지" 순위를 매긴다. 예산 제약(budget_cap)은 admin 쪽 배치 LP의 몫이라
개인별 추천에는 적용하지 않는다 - 배정 예산이 소진돼 있어도 "도움이 될 만한
정책"을 알려주는 것 자체는 항상 가능해야 하기 때문이다.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from pipeline.layer3_optimization import lp_allocator

from . import diagnose_service, youthcenter_service
from .pipeline_store import PipelineStore


def recommend_policies(
    input_payload: dict[str, Any], diagnosis_result: dict[str, Any], store: PipelineStore
) -> list[dict[str, Any]]:
    """세션의 입력값 + 진단결과로 정책별 기대효과(Δrisk_ip)를 계산해 순위를 매긴다."""
    domain_indices = diagnosis_result.get("domain_indices") or {}
    risk_probability = diagnosis_result.get("risk_probability")

    if risk_probability is None or not domain_indices:
        return []

    row: dict[str, Any] = dict(domain_indices)
    row["risk_probability"] = risk_probability

    age = diagnose_service.parse_age_group(input_payload.get("age_group", ""))
    if age is not None:
        row["연령대"] = age
    row["자가거주여부"] = diagnose_service.parse_home_ownership(input_payload.get("housing_type", ""))

    df = pd.DataFrame([row])
    policy_catalog = store.policy_catalog
    delta_risk, eligibility = lp_allocator.compute_delta_risk(df, policy_catalog, risk_col="risk_probability")

    idx = df.index[0]
    ranked = sorted(policy_catalog["policies"].keys(), key=lambda p: delta_risk[(idx, p)], reverse=True)

    return [
        {
            "policy": policy_name,
            "priority": rank + 1,
            "expected_effect": delta_risk[(idx, policy_name)],
            "eligible": eligibility[(idx, policy_name)]["eligible"],
            "eligibility_confidence": eligibility[(idx, policy_name)]["confidence"],
            "url": youthcenter_service.get_policy_url(
                policy_catalog["policies"][policy_name].get("youthcenter_plcy_no")
            ),
        }
        for rank, policy_name in enumerate(ranked)
    ]


def _age_matches(item: dict[str, Any], age: float | None) -> bool:
    """정책의 나이 제한 조건에 사용자가 걸리는지 확인한다.

    나이를 모르거나(age=None) 정책에 나이제한이 없으면(age_limited=False)
    항상 통과시킨다 - 모르는 조건으로 임의로 걸러내지 않는다는 원칙
    (policy_catalog.yaml의 assumed_unresolved_codebook 처리와 동일한 태도).
    """
    if age is None or not item.get("age_limited"):
        return True
    try:
        min_age = float(item["min_age"])
        max_age = float(item["max_age"])
    except (TypeError, ValueError):
        return True
    return min_age <= age <= max_age


def list_other_policies(input_payload: dict[str, Any], store: PipelineStore) -> list[dict[str, Any]]:
    """policy_catalog.yaml의 6개 정밀매칭 정책 외에, 온통청년 API로 사용자
    거주지역(시군구코드)에 적용되는 전국/부산시/구 단위 정책을 전부 검색해
    보여준다. Δrisk_ip를 계산할 수 없으므로(effectiveness_prior 없음) 순위는
    매기지 않고, 이미 6개 안에 있는 정책은 중복 표시하지 않는다.
    """
    zip_cd = input_payload.get("dong_code")
    age = diagnose_service.parse_age_group(input_payload.get("age_group", ""))

    policy_catalog = store.policy_catalog
    curated_plcy_nos = {
        cfg.get("youthcenter_plcy_no")
        for cfg in policy_catalog["policies"].values()
        if cfg.get("youthcenter_plcy_no")
    }

    candidates = youthcenter_service.search_policies_by_region(zip_cd)

    return [
        {
            "policy": item["policy"],
            "category": item.get("category"),
            "agency": item.get("agency"),
            "description": item.get("description"),
            "url": item.get("url"),
            "apply_period": item.get("apply_period"),
        }
        for item in candidates
        if item.get("plcyNo") not in curated_plcy_nos and _age_matches(item, age)
    ]
