"""Layer4 설명 에이전트 (docs/06_explanation_agent.md).

Claude API를 호출해 SHAP top3 + 클러스터 소속 + 배정 정책 + 위험확률을 개인화된
3~4문장 한국어 설명으로 생성한다. doc06의 프롬프트 설계 원칙(낙인 문구 금지,
수치 미노출, 행동 지향적 문구, 3~4문장 제한)을 시스템 프롬프트에 인코딩한다.

이 모듈은 실패 시 예외를 그대로 전파한다 - Claude API 호출 실패 시 SHAP 템플릿으로
폴백하는 로직은 호출부(app/services/explanation_service.py)의 책임이다.
"""
from __future__ import annotations

import anthropic

MODEL = "claude-opus-4-8"
MAX_TOKENS = 512

SYSTEM_PROMPT = """당신은 부산 청년 경제위험 진단 결과를 이용자에게 설명해주는 assistant입니다.

다음 원칙을 반드시 지키세요 (docs/06_explanation_agent.md 기준):
1. 낙인 문구 금지: "당신은 고위험군입니다", "위험군으로 분류되었습니다" 같은 표현을
   쓰지 마세요. 대신 "이번 달 먼저 신청하면 좋은 정책은..." 처럼 행동 지향적으로
   표현하세요.
2. 수치를 그대로 노출하지 마세요. "impact 0.34", "위험확률 0.62" 같은 원본
   숫자나 영문 필드명을 문장에 쓰지 말고, "주거비 부담이 다른 요인보다 크게
   작용했어요"처럼 자연어로 풀어서 설명하세요.
3. 응답은 3~4문장 이내로 작성하세요 (앱 UI 카드 한 장 분량).
4. 친근하고 담백한 존댓말을 사용하세요.

출력은 이용자에게 보여줄 설명 문장만 반환하세요. 따옴표, 머리말, 목록 기호 등
다른 텍스트를 덧붙이지 마세요."""


def _build_user_message(
    shap_top3: list[dict],
    cluster_membership: dict[str, float],
    assigned_policies: list[str],
    risk_probability: float | None,
) -> str:
    lines = ["다음은 한 청년 이용자의 진단 결과입니다."]

    if shap_top3:
        feature_lines = ", ".join(
            f"{item.get('feature')}(영향도 {item.get('impact', 0):.2f})" for item in shap_top3
        )
        lines.append(f"- 위험도에 영향을 준 주요 요인(영향도가 클수록 더 크게 작용): {feature_lines}")

    if cluster_membership:
        top_cluster = max(cluster_membership, key=cluster_membership.get)
        lines.append(f"- 가장 가까운 유형: {top_cluster}")

    if risk_probability is not None:
        lines.append(f"- 경제위험 확률(0~1 범위, 높을수록 위험): {risk_probability:.2f}")

    if assigned_policies:
        lines.append(f"- 지금 신청 가능한 정책: {', '.join(assigned_policies)}")
    else:
        lines.append("- 지금 조건에 맞는 정책은 없습니다.")

    lines.append("\n위 시스템 프롬프트의 원칙을 지켜서 이 사람에게 보여줄 설명을 작성하세요.")
    return "\n".join(lines)


def generate_explanation(
    shap_top3: list[dict] | None,
    cluster_membership: dict[str, float] | None,
    assigned_policies: list[str],
    risk_probability: float | None,
) -> str:
    """Claude API를 호출해 설명 문장을 생성한다.

    API 키 누락, 네트워크 오류, API 오류 등은 그대로 예외로 전파한다 - 폴백
    처리는 app/services/explanation_service.generate_explanation()이 담당한다.
    """
    client = anthropic.Anthropic()
    message = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": _build_user_message(
                    shap_top3 or [], cluster_membership or {}, assigned_policies, risk_probability
                ),
            }
        ],
    )

    text = "".join(block.text for block in message.content if block.type == "text").strip()
    if not text:
        raise RuntimeError("Claude API 응답에 텍스트 블록이 없습니다.")
    return text
