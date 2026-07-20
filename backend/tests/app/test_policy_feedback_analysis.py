"""정책 개선 우선순위 분석 Layer의 점수·권고·보호 규칙 테스트."""
from __future__ import annotations

from app.feedback_analysis.domain import AnalysisScores, Recommendation
from app.feedback_analysis.scoring import (
    ScoringConfig,
    confidence_for,
    recommendations,
    score_policy,
    weighted_score,
)


def _dist(**counts: int) -> dict:
    return {label: {"suppressed": False, "count": count} for label, count in counts.items()}


def _aggregate() -> dict:
    return {
        "policy_id": "청년월세지원",
        "respondent_count": 20,
        "usage_count": 25,
        "suppressed": False,
        "feedback_submission_count": 20,
        "overall_response_rate": 0.8,
        "metrics": {
            "perceived_effect_distribution": _dist(**{"매우 좋아짐": 5, "조금 좋아짐": 5}),
            "most_helpful_area_distribution": _dist(**{"주거비": 8, "도움 없음": 2}),
            "application_barrier_distribution": _dist(**{"어려움 없음": 4, "제출서류": 6}),
            "support_adequacy_distribution": _dist(**{"모두 충분": 4, "금액 부족": 6}),
            "followup_support_distribution": _dist(**{"일경험": 7, "취업교육": 3}),
            "improvement_direction_distribution": _dist(**{"신청절차 간소화": 6, "지원금 확대": 4}),
            "usage_funnel": {"applied": {"suppressed": False, "count": 10}, "completed": {"suppressed": False, "count": 7}},
            "stage_response_rates": {"completed": {"suppressed": False, "responses": 10}},
            "policy_usage_completion_rate": 0.7,
            "insufficient_amount_ratio": 0.6,
            "insufficient_period_ratio": 0.1,
        },
    }


def _evidence(**overrides) -> dict:
    base = {
        "primary_bottleneck": None, "bottleneck_share": 0.0,
        "top_followup_share": 0.0, "completion_rate": 0.5, "response_rate": 0.5,
        "amount_shortage_ratio": 0.2, "period_shortage_ratio": 0.2,
    }
    return {**base, **overrides}


def test_effectiveness_score_uses_configured_weights():
    score = weighted_score(_dist(**{"매우 좋아짐": 5, "조금 좋아짐": 5}), ScoringConfig().effect_weights)
    assert score == 85.0


def test_policy_effectiveness_includes_no_help_penalty():
    scores, _ = score_policy(_aggregate(), ScoringConfig())
    assert scores.effectiveness == 84.0


def test_accessibility_score_inverts_barrier_severity():
    score = weighted_score(_dist(**{"어려움 없음": 5, "방문 필요": 5}), ScoringConfig().barrier_scores)
    assert score == 60.0


def test_support_adequacy_score_keeps_amount_and_period_evidence():
    scores, evidence = score_policy(_aggregate(), ScoringConfig())
    assert scores.support_adequacy == 73.0
    assert evidence["amount_shortage_ratio"] == 0.6
    assert evidence["period_shortage_ratio"] == 0.1


def test_improvement_urgency_is_bounded_and_calculated():
    scores, _ = score_policy(_aggregate(), ScoringConfig())
    assert scores.improvement_urgency is not None
    assert 0 <= scores.improvement_urgency <= 100


def test_suppressed_distribution_never_generates_a_score():
    distribution = {"매우 좋아짐": {"suppressed": True, "count": None}, "비슷함": {"suppressed": False, "count": 5}}
    assert weighted_score(distribution, ScoringConfig().effect_weights) is None


def test_insufficient_data_has_no_specific_recommendations():
    primary, secondary = recommendations(AnalysisScores(), {}, ScoringConfig())
    assert primary == Recommendation.INSUFFICIENT_DATA
    assert secondary == ()


def test_extend_duration_when_period_shortage_is_clearly_higher():
    scores = AnalysisScores(70, 70, 50, 50, 50)
    primary, _ = recommendations(scores, _evidence(period_shortage_ratio=0.7, amount_shortage_ratio=0.2), ScoringConfig())
    assert primary == Recommendation.EXTEND_DURATION


def test_increase_amount_when_amount_shortage_is_clearly_higher():
    scores = AnalysisScores(70, 70, 50, 50, 50)
    primary, _ = recommendations(scores, _evidence(amount_shortage_ratio=0.7, period_shortage_ratio=0.2), ScoringConfig())
    assert primary == Recommendation.INCREASE_AMOUNT


def test_simplify_for_document_bottleneck():
    scores = AnalysisScores(70, 50, 60, 50, 50)
    primary, _ = recommendations(scores, _evidence(primary_bottleneck="제출서류", bottleneck_share=0.6), ScoringConfig())
    assert primary == Recommendation.SIMPLIFY


def test_retarget_for_eligibility_bottleneck():
    scores = AnalysisScores(70, 50, 60, 50, 50)
    primary, _ = recommendations(scores, _evidence(primary_bottleneck="자격조건", bottleneck_share=0.6), ScoringConfig())
    assert primary == Recommendation.RETARGET


def test_connect_followup_can_be_secondary_recommendation():
    scores = AnalysisScores(70, 50, 60, 80, 50)
    primary, secondary = recommendations(
        scores, _evidence(primary_bottleneck="제출서류", bottleneck_share=0.6, top_followup_share=0.7), ScoringConfig()
    )
    assert primary == Recommendation.SIMPLIFY
    assert Recommendation.CONNECT_FOLLOWUP in secondary


def test_low_core_scores_generate_redesign():
    primary, _ = recommendations(AnalysisScores(30, 40, 35, 50, 80), _evidence(), ScoringConfig())
    assert primary == Recommendation.REDESIGN


def test_confidence_accounts_for_sample_response_completion_and_suppression():
    aggregate = _aggregate()
    aggregate["respondent_count"] = 35
    assert confidence_for(aggregate, 0, ScoringConfig()).value == "high"
    assert confidence_for(aggregate, 1, ScoringConfig()).value == "medium"


def test_admin_analysis_api_contains_no_personal_or_free_text_fields(client):
    response = client.get("/api/v1/admin/policy-feedback-analysis")
    assert response.status_code == 200
    serialized = response.text.lower()
    for forbidden in ("user_id", "email", "phone", "contact", "other_text", "financial"):
        assert forbidden not in serialized
    first = response.json()[0]
    assert first["primary_recommendation"] == "insufficient_data"
    assert all(value is None for value in first["scores"].values())


def test_priority_api_is_sorted_and_has_global_and_category_ranks(client):
    response = client.get("/api/v1/admin/policy-feedback-priorities")
    assert response.status_code == 200
    assert len(response.json()) == 6
    assert all("ranks" in item and "category_ranks" in item for item in response.json())


def test_single_policy_analysis_uses_admin_contract(client):
    response = client.get("/api/v1/admin/policies/청년월세지원/feedback-analysis")
    assert response.status_code == 200
    assert response.json()["category"] == "주거"
    assert response.json()["publicly_available"] is False


def test_unknown_policy_analysis_returns_not_found(client):
    assert client.get("/api/v1/admin/policies/not-found/feedback-analysis").status_code == 404


def test_csv_export_contains_no_free_text_or_personal_identifiers(client):
    response = client.get("/api/v1/admin/policy-feedback-analysis/export?format=csv")
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    serialized = response.text.lower()
    assert "policy_id" in serialized
    for forbidden in ("user_id", "email", "phone", "other_text", "자유서술"):
        assert forbidden not in serialized


def test_json_export_is_generated_without_persistence(client):
    response = client.get("/api/v1/admin/policy-feedback-analysis/export?format=json")
    assert response.status_code == 200
    assert response.headers["content-disposition"].endswith('policy-feedback-analysis.json"')
    assert isinstance(response.json(), list)
