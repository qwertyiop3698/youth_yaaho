import { describe, expect, it } from 'vitest'
import {
  generatePolicyFeedbackInsights,
  topVisibleLabel,
  visibleDistribution,
} from '../src/pages/PolicyFeedback/policyFeedbackInsights'
import { distribution, summary } from './policyFeedbackFixture'

describe('policy feedback insights', () => {
  it('completely removes suppressed cells', () => {
    expect(visibleDistribution(distribution({ 공개: 5, 비공개: null }))).toEqual([{ label: '공개', count: 5 }])
    expect(topVisibleLabel(distribution({ 공개: 5, 비공개: null }))).toBe('공개')
  })

  it('creates rule based insights from visible aggregates', () => {
    const insights = generatePolicyFeedbackInsights(summary())
    expect(insights).toContain("응답자의 주요 신청 장벽은 '제출서류'입니다.")
    expect(insights).toContain("정책 이후 '일경험' 지원 수요가 가장 높습니다.")
    expect(insights).toContain('지원금 확대보다 지원기간 연장 요구가 많습니다.')
  })

  it('returns only sample warning when aggregate is suppressed', () => {
    expect(generatePolicyFeedbackInsights(summary(true))).toEqual([
      '표본이 충분하지 않아 정책 효과를 판단하기 어렵습니다.',
    ])
  })
})
