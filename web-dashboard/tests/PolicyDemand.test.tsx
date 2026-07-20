import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { PolicyDemandPriority, PolicyDemandSummary, ProtectedDistribution } from '../src/api/types'
import { PolicyDemandDashboard } from '../src/pages/PolicyDemand/PolicyDemand'

const dist = (values: Record<string, number | null>): ProtectedDistribution => Object.fromEntries(Object.entries(values).map(([key, count]) => [key, { suppressed: count === null, count }]))
const summary = (suppressed = false): PolicyDemandSummary => ({
  respondent_count: suppressed ? 3 : 15, minimum_group_size: 5, suppressed,
  suppression_reason: suppressed ? 'minimum_group_size_not_met' : null,
  metrics: suppressed ? null : {
    need_area_distribution: dist({ 생활비: 10 }), duration_distribution: dist({ '7~12개월': 8 }),
    amount_distribution: dist({ '31~50만 원': 9 }), barrier_distribution: dist({ '재직·미취업 조건': 8 }),
    companion_support_distribution: dist({ 취업교육: 7 }), trigger_reason_distribution: dist({ no_matching_policy: 10 }),
    district_distribution: dist({ '26440': 10 }), employment_distribution: dist({ '구직 중': 10 }),
    category_gap_distribution: dist({ 생활비: 10 }),
    trend_30_days: { suppressed: false, current_count: 10, previous_count: 5, change_rate: 1 },
    trend_90_days: { suppressed: false, current_count: 15, previous_count: 5, change_rate: 2 },
  }, comparison_summary: ["실제 이용자는 지원기간 부족을 지적했고 미수혜자는 재직조건 장벽을 보였습니다."],
})
const priority = (overrides: Partial<PolicyDemandPriority> = {}): PolicyDemandPriority => ({
  need_area: '생활비', respondent_count: 10, publicly_available: true, score: 82.5, confidence: 'medium',
  components: { volume: 100 }, primary_recommendation: 'broaden_eligibility', secondary_recommendations: ['extend_duration'],
  top_district: '26440', top_employment_status: '구직 중', top_trigger_reason: 'no_matching_policy',
  summary: ["'생활비' 수요에 대해 기존 정책 자격 완화 검토를 우선 살펴볼 수 있습니다."], ...overrides,
})

describe('PolicyDemandDashboard', () => {
  it('renders demand priorities and recent change', () => {
    render(<PolicyDemandDashboard summary={summary()} priorities={[priority()]} />)
    expect(screen.getByText('정책 미충족 수요')).toBeInTheDocument()
    expect(screen.getByText('82.5')).toBeInTheDocument()
    expect(screen.getByText('+100.0%')).toBeInTheDocument()
  })
  it('hides scores for insufficient samples', () => {
    render(<PolicyDemandDashboard summary={summary()} priorities={[priority({ publicly_available: false, respondent_count: null, score: null, primary_recommendation: 'insufficient_data' })]} />)
    fireEvent.click(screen.getByLabelText('표본 부족 포함'))
    expect(screen.getAllByText('비공개').length).toBeGreaterThan(1)
  })
  it('filters by district and employment status', () => {
    const other = priority({ need_area: '주거비', top_district: '26350', top_employment_status: '재직' })
    render(<PolicyDemandDashboard summary={summary()} priorities={[priority(), other]} />)
    fireEvent.change(screen.getByLabelText('구·군'), { target: { value: '26350' } })
    fireEvent.change(screen.getByLabelText('고용상태'), { target: { value: '재직' } })
    const dataRows = screen.getAllByRole('row').slice(1)
    expect(dataRows).toHaveLength(1); expect(within(dataRows[0]).getByText('주거비')).toBeInTheDocument()
  })
  it('shows administrative recommendation as review language', () => {
    render(<PolicyDemandDashboard summary={summary()} priorities={[priority()]} />)
    expect(screen.getByText('기존 정책 자격 완화 검토')).toBeInTheDocument()
    expect(screen.getByText(/자동 결정이 아닌/)).toBeInTheDocument()
  })
  it('downloads CSV and JSON', () => {
    const onDownload = vi.fn(); render(<PolicyDemandDashboard summary={summary()} priorities={[priority()]} onDownload={onDownload} />)
    fireEvent.click(screen.getByRole('button', { name: 'CSV 다운로드' })); fireEvent.click(screen.getByRole('button', { name: 'JSON 다운로드' }))
    expect(onDownload).toHaveBeenNthCalledWith(1, 'csv'); expect(onDownload).toHaveBeenNthCalledWith(2, 'json')
  })
  it('renders comparison with existing policy feedback', () => {
    render(<PolicyDemandDashboard summary={summary()} priorities={[priority()]} />)
    expect(screen.getByText(/실제 이용자는 지원기간 부족/)).toBeInTheDocument()
  })
  it('suppresses all summary details below minimum group size', () => {
    render(<PolicyDemandDashboard summary={summary(true)} priorities={[]} />)
    expect(screen.getByText('응답 인원이 적어 세부 수요를 공개하지 않습니다.')).toBeInTheDocument()
    expect(screen.queryByText('+100.0%')).not.toBeInTheDocument()
  })
})
