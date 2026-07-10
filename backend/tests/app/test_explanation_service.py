"""app/services/explanation_service.generate_explanation() 폴백 체인 테스트.

conftest.py의 _no_real_claude_calls autouse fixture가 기본적으로
explanation_agent.generate_explanation을 실패하도록 만들어두므로, 여기서는
개별 테스트가 필요에 따라 성공/실패 동작을 다시 monkeypatch로 오버라이드한다.
"""
from __future__ import annotations

from pipeline.layer4_explanation import explanation_agent

from app.services import explanation_service

DOMAIN_INDICES = {"주거비압박지수": 1.2, "부채상환위험지수": 0.3}
SHAP_TOP3 = [{"feature": "주거가격부담률", "impact": 0.34}]
RECOMMENDATIONS = [
    {"policy": "청년월세지원", "priority": 1, "expected_effect": 0.1, "eligible": True, "eligibility_confidence": "verified"},
    {"policy": "머물자리론", "priority": 2, "expected_effect": 0.05, "eligible": False, "eligibility_confidence": "verified"},
]


class TestGenerateExplanationFallbackChain:
    def test_falls_back_to_template_when_claude_fails(self):
        # autouse fixture가 이미 explanation_agent.generate_explanation을 실패시킴
        text, is_llm_generated = explanation_service.generate_explanation(
            DOMAIN_INDICES, SHAP_TOP3, RECOMMENDATIONS, cluster_membership={"주거비압박형": 0.7}, risk_probability=0.6
        )

        assert is_llm_generated is False
        assert len(text) > 0
        assert "고위험군" not in text

    def test_uses_claude_result_when_available(self, monkeypatch):
        monkeypatch.setattr(
            explanation_agent, "generate_explanation", lambda **kwargs: "Claude가 생성한 설명 문장입니다."
        )

        text, is_llm_generated = explanation_service.generate_explanation(
            DOMAIN_INDICES, SHAP_TOP3, RECOMMENDATIONS, cluster_membership={"주거비압박형": 0.7}, risk_probability=0.6
        )

        assert is_llm_generated is True
        assert text == "Claude가 생성한 설명 문장입니다."

    def test_passes_only_eligible_policies_as_assigned_policies(self, monkeypatch):
        captured = {}

        def _fake_generate(**kwargs):
            captured.update(kwargs)
            return "설명"

        monkeypatch.setattr(explanation_agent, "generate_explanation", _fake_generate)

        explanation_service.generate_explanation(
            DOMAIN_INDICES, SHAP_TOP3, RECOMMENDATIONS, cluster_membership=None, risk_probability=None
        )

        assert captured["assigned_policies"] == ["청년월세지원"]

    def test_falls_back_on_any_exception_type(self, monkeypatch):
        def _raise_value_error(**kwargs):
            raise ValueError("unexpected")

        monkeypatch.setattr(explanation_agent, "generate_explanation", _raise_value_error)

        text, is_llm_generated = explanation_service.generate_explanation(
            DOMAIN_INDICES, SHAP_TOP3, RECOMMENDATIONS
        )

        assert is_llm_generated is False
        assert len(text) > 0
