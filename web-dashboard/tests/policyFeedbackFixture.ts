import type { PolicyFeedbackSummary, ProtectedDistribution } from '../src/api/types'

export const distribution = (values: Record<string, number | null>): ProtectedDistribution =>
  Object.fromEntries(
    Object.entries(values).map(([label, count]) => [
      label,
      { suppressed: count === null, count },
    ]),
  )

export const summary = (suppressed = false): PolicyFeedbackSummary => ({
  policy_id: 'p1',
  policy_name: '청년월세지원',
  respondent_count: suppressed ? 3 : 10,
  minimum_group_size: 5,
  suppressed,
  suppression_reason: suppressed ? 'minimum_group_size_not_met' : null,
  usage_count: 12,
  feedback_submission_count: 10,
  overall_response_rate: 0.8,
  metrics: suppressed ? null : {
    usage_funnel: {},
    stage_response_rates: {},
    perceived_effect_distribution: distribution({ '조금 좋아짐': 7, '비슷함': null }),
    most_helpful_area_distribution: distribution({ '생활비': 6, '주거비': 5 }),
    application_barrier_distribution: distribution({ '제출서류': 8, '방문 필요': null }),
    support_adequacy_distribution: distribution({ '모두 충분': 5, '기간 부족': 5 }),
    insufficient_amount_ratio: 0.4,
    insufficient_period_ratio: 0.6,
    both_insufficient_ratio: 0.2,
    followup_support_distribution: distribution({ '일경험': 7 }),
    improvement_direction_distribution: distribution({ '지원금 확대': 5, '지원기간 연장': 7 }),
    selected_rejected_barrier_comparison: {},
    policy_usage_completion_rate: 0.5,
    free_text_response_count: 5,
    free_text_response_suppressed: false,
  },
})
