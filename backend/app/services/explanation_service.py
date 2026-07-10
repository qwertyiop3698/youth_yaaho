"""공통 백엔드 - 설명문 생성 서비스 (docs/07 GET /explanation).

Layer4(Claude API 기반 설명 에이전트, docs/06)를 1순위로 호출하고, API 키 누락/
네트워크 오류/API 오류 등 어떤 이유로든 실패하면 기존 SHAP 템플릿
(generate_explanation_text)으로 폴백한다. 폴백 체인이지 완전 교체가 아니므로
템플릿 함수는 그대로 남겨둔다 - Claude API가 막히는 환경(오프라인 데모 등)에서도
설명이 항상 생성되도록 하기 위함이다.
"""
from __future__ import annotations

import logging

from pipeline.layer2b_risk_model.baseline_models import sanitize_feature_name
from pipeline.layer4_explanation import explanation_agent

logger = logging.getLogger(__name__)

FEATURE_KOREAN_PHRASES: dict[str, str] = {
    "추정DTI": "부채 상환 부담",
    "상환부담률": "매달 갚아야 하는 금액 부담",
    "소득증감률": "최근 소득 변화",
    "주거가격부담률": "주거비 부담",
    "카드소비/소득비율": "카드 소비 비중",
    "할부의존도": "할부 사용 비중",
    "현금서비스의존도": "현금서비스 이용",
    "신용레버리지": "대출 대비 자산 여력",
    "소득증빙갭": "소득 증빙 자료 차이",
    "직장변동위험도": "최근 직장 변동",
    "신용평점": "신용 점수",
    "총부채/소득비율": "소득 대비 부채 비중",
}

DOMAIN_INDEX_KOREAN_PHRASES: dict[str, str] = {
    "주거비압박지수": "주거비 부담",
    "부채상환위험지수": "부채 상환 부담",
    "소득변동성지수": "소득 변화",
    "소비압박지수": "소비 지출 부담",
    "신용취약지수": "신용 관리",
}

# shap_top3의 "feature" 값은 baseline_models.sanitize_feature_name()을 거친 이름이다
# (LightGBM이 쉼표 등 특수문자를 피처명으로 거부하는 문제 회피, 2026-07-09). 원본
# 한글 문구 사전과 매칭하려면 이 사전의 키도 동일하게 sanitize해서 비교해야 한다.
_SANITIZED_FEATURE_PHRASES: dict[str, str] = {
    sanitize_feature_name(k): v for k, v in FEATURE_KOREAN_PHRASES.items()
}


def _top_domain_index(domain_indices: dict[str, float]) -> str | None:
    if not domain_indices:
        return None
    return max(domain_indices, key=domain_indices.get)


def generate_explanation_text(
    domain_indices: dict[str, float],
    shap_top3: list[dict] | None,
    recommendations: list[dict],
) -> str:
    """doc06 원칙: 낙인 문구("당신은 고위험군") 금지, 행동 지향적 문구, 3~4문장 이내."""
    sentences: list[str] = []

    top_feature_name = shap_top3[0].get("feature") if shap_top3 else None
    phrase = _SANITIZED_FEATURE_PHRASES.get(top_feature_name) if top_feature_name else None

    if phrase is None:
        top_domain = _top_domain_index(domain_indices)
        phrase = DOMAIN_INDEX_KOREAN_PHRASES.get(top_domain) if top_domain else None

    if phrase:
        sentences.append(f"최근 {phrase}이(가) 다른 요인보다 크게 작용했어요.")
    else:
        sentences.append("여러 요인을 종합해서 이번 진단 결과를 계산했어요.")

    eligible_recs = [r for r in recommendations if r.get("eligible")]
    if eligible_recs:
        top_policy = eligible_recs[0]["policy"]
        sentences.append(f"이번 달 먼저 신청하면 좋은 정책은 {top_policy}이에요.")
    else:
        sentences.append("지금 조건에 딱 맞는 정책은 없지만, 상황이 바뀌면 다시 확인해볼 수 있어요.")

    sentences.append("지금 미리 준비해두면 상황이 더 어려워지기 전에 도움을 받을 수 있어요.")

    return " ".join(sentences)


def generate_explanation(
    domain_indices: dict[str, float],
    shap_top3: list[dict] | None,
    recommendations: list[dict],
    cluster_membership: dict[str, float] | None = None,
    risk_probability: float | None = None,
) -> tuple[str, bool]:
    """폴백 체인: Claude API(Layer4) 우선 시도, 실패 시 SHAP 템플릿으로 대체.

    반환값은 (설명 문장, is_llm_generated) 튜플이다.
    """
    assigned_policies = [r["policy"] for r in recommendations if r.get("eligible")]
    try:
        text = explanation_agent.generate_explanation(
            shap_top3=shap_top3,
            cluster_membership=cluster_membership,
            assigned_policies=assigned_policies,
            risk_probability=risk_probability,
        )
        return text, True
    except Exception as exc:  # noqa: BLE001 - Claude API 실패 시 템플릿 폴백으로 이어져야 함
        logger.warning("Claude API 설명 생성 실패, SHAP 템플릿으로 폴백합니다: %s", exc)
        return generate_explanation_text(domain_indices, shap_top3, recommendations), False
