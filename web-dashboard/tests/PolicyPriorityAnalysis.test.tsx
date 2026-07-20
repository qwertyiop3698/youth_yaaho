import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { PolicyFeedbackAnalysis } from '../src/api/types'
import { PolicyPriorityAnalysis } from '../src/pages/PolicyFeedback/PolicyPriorityAnalysis'

function analysis(overrides: Partial<PolicyFeedbackAnalysis> = {}): PolicyFeedbackAnalysis {
  return {
    policy_id: 'p1', policy_name: '청년월세지원', category: '주거', respondent_count: 30,
    publicly_available: true, confidence: 'high',
    scores: { effectiveness: 72.4, accessibility: 55.1, support_adequacy: 48.7, followup_need: 81.2, improvement_urgency: 66.8 },
    primary_bottleneck: '제출서류', top_followup_need: '일경험',
    primary_recommendation: 'extend_duration', secondary_recommendations: ['simplify', 'connect_followup'],
    summary: ['지원기간 연장 필요성을 우선 검토할 수 있습니다.'], suppressed_cell_count: 0,
    ranks: { improvement_urgency: 1 }, category_ranks: { improvement_urgency: 1 },
    ...overrides,
  }
}

describe('PolicyPriorityAnalysis', () => {
  it('renders the policy priority table and score columns', () => {
    render(<PolicyPriorityAnalysis analyses={[analysis()]} />)
    expect(screen.getByRole('heading', { name: '정책 개선 우선순위' })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: /개선 시급도/ })).toBeInTheDocument()
    expect(screen.getAllByText('66.8')).toHaveLength(2)
  })

  it('never exposes scores for insufficient data', () => {
    const item = analysis({
      policy_id: 'p0', primary_recommendation: 'insufficient_data', publicly_available: false,
      scores: { effectiveness: null, accessibility: null, support_adequacy: null, followup_need: null, improvement_urgency: null },
    })
    render(<PolicyPriorityAnalysis analyses={[item]} />)
    fireEvent.click(screen.getByLabelText('표본 부족 포함'))
    expect(screen.getAllByText('비공개').length).toBeGreaterThanOrEqual(4)
  })

  it('shows confidence and primary and secondary recommendations', () => {
    render(<PolicyPriorityAnalysis analyses={[analysis()]} />)
    expect(screen.getAllByText('높음').length).toBeGreaterThan(0)
    expect(screen.getAllByText('지원기간 연장 검토').length).toBeGreaterThan(0)
    expect(screen.getByText(/신청 절차 개선 검토 · 후속 정책 연계 검토/)).toBeInTheDocument()
  })

  it('filters by category', () => {
    render(<PolicyPriorityAnalysis analyses={[analysis(), analysis({ policy_id: 'p2', policy_name: '청년 일경험', category: '일자리' })]} />)
    fireEvent.change(screen.getByLabelText('정책 카테고리'), { target: { value: '일자리' } })
    expect(screen.getByRole('button', { name: '청년 일경험' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '청년월세지원' })).not.toBeInTheDocument()
  })

  it('sorts by improvement urgency in both directions', () => {
    const low = analysis({ policy_id: 'low', policy_name: '낮은 시급도', scores: { ...analysis().scores, improvement_urgency: 30 } })
    const high = analysis({ policy_id: 'high', policy_name: '높은 시급도', scores: { ...analysis().scores, improvement_urgency: 80 } })
    render(<PolicyPriorityAnalysis analyses={[low, high]} />)
    let rows = screen.getAllByRole('row').slice(1)
    expect(within(rows[0]).getByText('높은 시급도')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /개선 시급도/ }))
    rows = screen.getAllByRole('row').slice(1)
    expect(within(rows[0]).getByText('낮은 시급도')).toBeInTheDocument()
  })

  it('shows rule based summary and non-directive caveat', () => {
    render(<PolicyPriorityAnalysis analyses={[analysis()]} />)
    expect(screen.getByText(/지원기간 연장 필요성을 우선 검토할 수 있습니다/)).toBeInTheDocument()
    expect(screen.getByText(/자동 의사결정이 아니라/)).toBeInTheDocument()
  })

  it('switches the policy detail cards from a table row', () => {
    render(<PolicyPriorityAnalysis analyses={[analysis(), analysis({ policy_id: 'p2', policy_name: '머물자리론', primary_bottleneck: '자격조건' })]} />)
    fireEvent.click(screen.getByRole('button', { name: '머물자리론' }))
    expect(screen.getByLabelText('정책 상세 분석')).toHaveTextContent('머물자리론')
    expect(screen.getByLabelText('정책 상세 분석')).toHaveTextContent('자격조건')
  })

  it('invokes CSV and JSON downloads without persisting a report', () => {
    const onDownload = vi.fn()
    render(<PolicyPriorityAnalysis analyses={[analysis()]} onDownload={onDownload} />)
    fireEvent.click(screen.getByRole('button', { name: 'CSV 다운로드' }))
    fireEvent.click(screen.getByRole('button', { name: 'JSON 다운로드' }))
    expect(onDownload).toHaveBeenNthCalledWith(1, 'csv')
    expect(onDownload).toHaveBeenNthCalledWith(2, 'json')
  })
})
