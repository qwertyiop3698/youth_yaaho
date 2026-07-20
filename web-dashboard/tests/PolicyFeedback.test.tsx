import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { PolicyFeedbackDashboard } from '../src/pages/PolicyFeedback/PolicyFeedback'
import { summary } from './policyFeedbackFixture'

describe('PolicyFeedbackDashboard', () => {
  it('renders policy list and detailed aggregate sections', () => {
    render(<PolicyFeedbackDashboard summaries={[summary()]} />)
    expect(screen.getAllByText('청년월세지원').length).toBeGreaterThan(0)
    expect(screen.getByText('정책 효과')).toBeInTheDocument()
    expect(screen.getByText('신청 장벽')).toBeInTheDocument()
    expect(screen.getByText('후속 정책 수요')).toBeInTheDocument()
    expect(screen.getByText('개선 요구')).toBeInTheDocument()
    expect(screen.getByText(/응답자의 주요 신청 장벽은 '제출서류'입니다/)).toBeInTheDocument()
  })

  it('shows suppression notice and does not render detail charts', () => {
    render(<PolicyFeedbackDashboard summaries={[summary(true)]} />)
    expect(screen.getByText('응답 인원이 적어 세부 결과를 공개하지 않습니다.')).toBeInTheDocument()
    expect(screen.queryByRole('img', { name: '정책 효과 분포 차트' })).not.toBeInTheDocument()
  })

  it('switches detail when another policy is selected', () => {
    const second = { ...summary(), policy_id: 'p2', policy_name: '청년 일경험 지원' }
    render(<PolicyFeedbackDashboard summaries={[summary(), second]} />)
    fireEvent.click(screen.getByRole('button', { name: '청년 일경험 지원' }))
    expect(screen.getByRole('heading', { name: '청년 일경험 지원' })).toBeInTheDocument()
  })
})
