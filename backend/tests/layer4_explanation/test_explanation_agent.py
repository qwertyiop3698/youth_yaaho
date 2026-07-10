"""Layer4 설명 에이전트(pipeline/layer4_explanation/explanation_agent.py) 테스트.

실제 Claude API를 호출하지 않고 anthropic.Anthropic 클라이언트를 모킹한다.
"""
from __future__ import annotations

import pytest

from pipeline.layer4_explanation import explanation_agent


class _FakeTextBlock:
    def __init__(self, type_: str, text: str = "") -> None:
        self.type = type_
        self.text = text


class _FakeMessage:
    def __init__(self, blocks: list[_FakeTextBlock]) -> None:
        self.content = blocks


class _FakeMessagesResource:
    def __init__(self, response: _FakeMessage | None = None, exception: Exception | None = None) -> None:
        self._response = response
        self._exception = exception
        self.last_kwargs: dict | None = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        if self._exception is not None:
            raise self._exception
        return self._response


class _FakeAnthropicClient:
    def __init__(self, messages_resource: _FakeMessagesResource) -> None:
        self.messages = messages_resource


def _patch_anthropic(monkeypatch, messages_resource: _FakeMessagesResource) -> None:
    monkeypatch.setattr(
        explanation_agent.anthropic,
        "Anthropic",
        lambda *args, **kwargs: _FakeAnthropicClient(messages_resource),
    )


class TestGenerateExplanationSuccess:
    def test_returns_stripped_text_from_claude_response(self, monkeypatch):
        fake_messages = _FakeMessagesResource(
            response=_FakeMessage([_FakeTextBlock("text", "  이번 달 청년월세지원을 먼저 신청해보세요.  ")])
        )
        _patch_anthropic(monkeypatch, fake_messages)

        result = explanation_agent.generate_explanation(
            shap_top3=[{"feature": "주거가격부담률", "impact": 0.34}],
            cluster_membership={"주거비압박형": 0.6, "기타": 0.4},
            assigned_policies=["청년월세지원"],
            risk_probability=0.62,
        )

        assert result == "이번 달 청년월세지원을 먼저 신청해보세요."

    def test_uses_expected_model_and_system_prompt(self, monkeypatch):
        fake_messages = _FakeMessagesResource(response=_FakeMessage([_FakeTextBlock("text", "설명")]))
        _patch_anthropic(monkeypatch, fake_messages)

        explanation_agent.generate_explanation(
            shap_top3=[], cluster_membership={}, assigned_policies=[], risk_probability=None
        )

        assert fake_messages.last_kwargs["model"] == explanation_agent.MODEL
        system_prompt = fake_messages.last_kwargs["system"]
        # doc06 원칙: 낙인 문구 금지, 수치 미노출, 3~4문장 제한이 시스템 프롬프트에 명시돼야 함
        assert "고위험군" in system_prompt
        assert "3~4문장" in system_prompt

    def test_user_message_includes_shap_and_policies(self, monkeypatch):
        fake_messages = _FakeMessagesResource(response=_FakeMessage([_FakeTextBlock("text", "설명")]))
        _patch_anthropic(monkeypatch, fake_messages)

        explanation_agent.generate_explanation(
            shap_top3=[{"feature": "추정DTI", "impact": 0.21}],
            cluster_membership={"부채과부하형": 0.8},
            assigned_policies=["희망신용상담센터"],
            risk_probability=0.5,
        )

        user_content = fake_messages.last_kwargs["messages"][0]["content"]
        assert "추정DTI" in user_content
        assert "희망신용상담센터" in user_content
        assert "부채과부하형" in user_content

    def test_handles_missing_optional_fields(self, monkeypatch):
        fake_messages = _FakeMessagesResource(response=_FakeMessage([_FakeTextBlock("text", "설명")]))
        _patch_anthropic(monkeypatch, fake_messages)

        result = explanation_agent.generate_explanation(
            shap_top3=None, cluster_membership=None, assigned_policies=[], risk_probability=None
        )
        assert result == "설명"


class TestGenerateExplanationFailure:
    def test_propagates_api_exception(self, monkeypatch):
        fake_messages = _FakeMessagesResource(exception=RuntimeError("network down"))
        _patch_anthropic(monkeypatch, fake_messages)

        with pytest.raises(RuntimeError, match="network down"):
            explanation_agent.generate_explanation(
                shap_top3=[], cluster_membership={}, assigned_policies=[], risk_probability=None
            )

    def test_raises_when_response_has_no_text_block(self, monkeypatch):
        fake_messages = _FakeMessagesResource(response=_FakeMessage([_FakeTextBlock("thinking", "")]))
        _patch_anthropic(monkeypatch, fake_messages)

        with pytest.raises(RuntimeError):
            explanation_agent.generate_explanation(
                shap_top3=[], cluster_membership={}, assigned_policies=[], risk_probability=None
            )

    def test_raises_when_content_empty(self, monkeypatch):
        fake_messages = _FakeMessagesResource(response=_FakeMessage([]))
        _patch_anthropic(monkeypatch, fake_messages)

        with pytest.raises(RuntimeError):
            explanation_agent.generate_explanation(
                shap_top3=[], cluster_membership={}, assigned_policies=[], risk_probability=None
            )
