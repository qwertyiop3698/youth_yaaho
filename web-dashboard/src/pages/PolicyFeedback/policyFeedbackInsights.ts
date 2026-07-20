import type { PolicyFeedbackSummary, ProtectedDistribution } from '../../api/types'

export function visibleDistribution(distribution: ProtectedDistribution | undefined) {
  if (!distribution) return []
  return Object.entries(distribution)
    .filter(([, cell]) => !cell.suppressed && cell.count !== null)
    .map(([label, cell]) => ({ label, count: cell.count as number }))
}

export function topVisibleLabel(distribution: ProtectedDistribution | undefined): string | null {
  const visible = visibleDistribution(distribution)
  if (visible.length === 0) return null
  return visible.reduce((best, item) => (item.count > best.count ? item : best)).label
}

export function generatePolicyFeedbackInsights(summary: PolicyFeedbackSummary): string[] {
  if (summary.suppressed || !summary.metrics) {
    return ['표본이 충분하지 않아 정책 효과를 판단하기 어렵습니다.']
  }
  const metrics = summary.metrics
  const insights: string[] = []
  const effect = topVisibleLabel(metrics.perceived_effect_distribution)
  const helpful = topVisibleLabel(metrics.most_helpful_area_distribution)
  const barrier = topVisibleLabel(metrics.application_barrier_distribution)
  const followup = topVisibleLabel(metrics.followup_support_distribution)
  const improvement = topVisibleLabel(metrics.improvement_direction_distribution)

  if (effect) insights.push(`정책 이용 전과 비교한 체감 변화는 '${effect}' 응답이 가장 많았습니다.`)
  if (helpful) insights.push(`이 정책은 '${helpful}' 영역에서 가장 도움이 된 것으로 집계되었습니다.`)
  if (barrier) insights.push(`응답자의 주요 신청 장벽은 '${barrier}'입니다.`)
  if (followup) insights.push(`정책 이후 '${followup}' 지원 수요가 가장 높습니다.`)
  if (improvement) insights.push(`가장 많이 요구된 개선 방향은 '${improvement}'입니다.`)

  const improvementCounts = new Map(
    visibleDistribution(metrics.improvement_direction_distribution).map((item) => [item.label, item.count]),
  )
  const amount = improvementCounts.get('지원금 확대')
  const duration = improvementCounts.get('지원기간 연장')
  if (amount !== undefined && duration !== undefined && duration > amount) {
    insights.push('지원금 확대보다 지원기간 연장 요구가 많습니다.')
  }
  return insights.length > 0 ? insights : ['공개 가능한 세부 셀이 없어 추가 판단을 보류해야 합니다.']
}
