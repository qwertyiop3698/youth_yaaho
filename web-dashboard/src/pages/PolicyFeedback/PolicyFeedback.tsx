import { useMemo, useState } from 'react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { PolicyFeedbackAnalysis, PolicyFeedbackSummary, ProtectedDistribution } from '../../api/types'
import { QueryState } from '../../components/QueryState'
import { StatCard } from '../../components/StatCard'
import { usePolicyFeedback } from '../../hooks/usePolicyFeedback'
import { usePolicyFeedbackAnalysis } from '../../hooks/usePolicyFeedbackAnalysis'
import { PolicyPriorityAnalysis } from './PolicyPriorityAnalysis'
import {
  generatePolicyFeedbackInsights,
  topVisibleLabel,
  visibleDistribution,
} from './policyFeedbackInsights'

const SUPPRESSED_MESSAGE = '응답 인원이 적어 세부 결과를 공개하지 않습니다.'

function percent(value: number | null) {
  return value === null ? '공개 불가' : `${(value * 100).toFixed(1)}%`
}

export function PolicyFeedback() {
  const query = usePolicyFeedback()
  const analysisQuery = usePolicyFeedbackAnalysis()

  return (
    <QueryState isLoading={query.isLoading || analysisQuery.isLoading} isError={query.isError || analysisQuery.isError} error={query.error ?? analysisQuery.error}>
      <PolicyFeedbackDashboard summaries={query.data ?? []} analyses={analysisQuery.data ?? []} />
    </QueryState>
  )
}

export function PolicyFeedbackDashboard({ summaries, analyses = [] }: { summaries: PolicyFeedbackSummary[]; analyses?: PolicyFeedbackAnalysis[] }) {
  const [selectedPolicyId, setSelectedPolicyId] = useState<string | null>(null)
  const selected = useMemo(
    () => summaries.find((item) => item.policy_id === selectedPolicyId) ?? summaries[0],
    [selectedPolicyId, summaries],
  )

  return (
      <div className="flex flex-col gap-6">
        <div>
          <p className="text-sm font-medium text-brand-blue">정책 이용 경험 데이터</p>
          <h2 className="mt-1 text-xl font-semibold">정책 피드백 분석</h2>
          <p className="mt-2 text-sm text-gray-500">
            신청 장벽, 체감 효과, 후속 지원과 개선 요구를 익명 집계로 확인합니다.
          </p>
        </div>

        <section aria-labelledby="policy-feedback-list-title">
          <h3 id="policy-feedback-list-title" className="mb-3 text-lg font-semibold">정책별 응답 현황</h3>
          <div className="overflow-x-auto rounded-lg border border-brand-border bg-white shadow-sm">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-brand-surface-muted text-gray-600">
                <tr>
                  {['정책명', '이용기록', '응답자', '응답률', '체감 효과', '주요 장벽', '개선 방향', '상태'].map((label) => (
                    <th key={label} className="px-4 py-3 font-medium">{label}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {summaries.map((summary) => (
                  <tr key={summary.policy_id} className="border-t border-brand-border">
                    <td className="px-4 py-3">
                      <button
                        className="font-medium text-brand-blue hover:underline"
                        onClick={() => setSelectedPolicyId(summary.policy_id)}
                      >
                        {summary.policy_name}
                      </button>
                    </td>
                    <td className="px-4 py-3">{summary.usage_count}</td>
                    <td className="px-4 py-3">{summary.suppressed ? '숨김' : summary.respondent_count}</td>
                    <td className="px-4 py-3">{summary.suppressed ? '숨김' : percent(summary.overall_response_rate)}</td>
                    <td className="px-4 py-3">{summary.suppressed ? '숨김' : topVisibleLabel(summary.metrics?.perceived_effect_distribution) ?? '—'}</td>
                    <td className="px-4 py-3">{summary.suppressed ? '숨김' : topVisibleLabel(summary.metrics?.application_barrier_distribution) ?? '—'}</td>
                    <td className="px-4 py-3">{summary.suppressed ? '숨김' : topVisibleLabel(summary.metrics?.improvement_direction_distribution) ?? '—'}</td>
                    <td className="px-4 py-3">
                      <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${summary.suppressed ? 'bg-gray-100 text-gray-600' : 'bg-emerald-50 text-emerald-700'}`}>
                        {summary.suppressed ? '표본 부족' : '집계 가능'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {summaries.length === 0 && <p className="p-6 text-sm text-gray-500">정책 목록이 없습니다.</p>}
          </div>
        </section>

        <PolicyPriorityAnalysis analyses={analyses} />

        {selected && <PolicyFeedbackDetail summary={selected} />}
      </div>
  )
}

export function PolicyFeedbackDetail({ summary }: { summary: PolicyFeedbackSummary }) {
  if (summary.suppressed || !summary.metrics) {
    return (
      <section className="rounded-lg border border-amber-200 bg-amber-50 p-6" aria-live="polite">
        <h3 className="text-lg font-semibold">{summary.policy_name}</h3>
        <p className="mt-3 text-sm text-amber-900">{SUPPRESSED_MESSAGE}</p>
        <InsightCards insights={generatePolicyFeedbackInsights(summary)} />
      </section>
    )
  }
  const metrics = summary.metrics
  return (
    <section className="flex flex-col gap-6" aria-labelledby="policy-feedback-detail-title">
      <div>
        <p className="text-sm text-gray-500">선택 정책</p>
        <h3 id="policy-feedback-detail-title" className="text-xl font-semibold">{summary.policy_name}</h3>
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="피드백 응답자" value={`${summary.respondent_count}명`} />
        <StatCard label="전체 응답률" value={percent(summary.overall_response_rate)} />
        <StatCard label="금액 부족 응답" value={percent(metrics.insufficient_amount_ratio)} />
        <StatCard label="기간 부족 응답" value={percent(metrics.insufficient_period_ratio)} />
      </div>
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        <DistributionCard title="정책 효과" distribution={metrics.perceived_effect_distribution} />
        <DistributionCard title="가장 도움 된 영역" distribution={metrics.most_helpful_area_distribution} />
        <DistributionCard title="신청 장벽" distribution={metrics.application_barrier_distribution} />
        <DistributionCard title="후속 정책 수요" distribution={metrics.followup_support_distribution} />
        <DistributionCard title="개선 요구" distribution={metrics.improvement_direction_distribution} />
        <div className="rounded-lg border border-brand-border bg-white p-5 shadow-sm">
          <h4 className="font-semibold">예산 적정성</h4>
          <dl className="mt-4 grid grid-cols-1 gap-3 text-sm sm:grid-cols-3">
            <div><dt className="text-gray-500">금액 부족</dt><dd className="mt-1 text-xl font-semibold">{percent(metrics.insufficient_amount_ratio)}</dd></div>
            <div><dt className="text-gray-500">기간 부족</dt><dd className="mt-1 text-xl font-semibold">{percent(metrics.insufficient_period_ratio)}</dd></div>
            <div><dt className="text-gray-500">모두 부족</dt><dd className="mt-1 text-xl font-semibold">{percent(metrics.both_insufficient_ratio)}</dd></div>
          </dl>
        </div>
      </div>
      <InsightCards insights={generatePolicyFeedbackInsights(summary)} />
    </section>
  )
}

function DistributionCard({ title, distribution }: { title: string; distribution: ProtectedDistribution }) {
  const data = visibleDistribution(distribution)
  const hasSuppressedCell = Object.values(distribution).some((cell) => cell.suppressed)
  return (
    <div className="rounded-lg border border-brand-border bg-white p-5 shadow-sm">
      <h4 className="font-semibold">{title}</h4>
      {hasSuppressedCell && <p className="mt-2 text-xs text-gray-500">일부 소수 응답 셀은 완전히 숨겼습니다.</p>}
      {data.length === 0 ? (
        <p className="mt-5 text-sm text-gray-500">{SUPPRESSED_MESSAGE}</p>
      ) : (
        <div className="mt-4 h-64" role="img" aria-label={`${title} 분포 차트`}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} layout="vertical" margin={{ left: 20 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" allowDecimals={false} />
              <YAxis type="category" dataKey="label" width={100} tick={{ fontSize: 12 }} />
              <Tooltip />
              <Bar dataKey="count" name="응답 수" fill="#2f6fed" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}

function InsightCards({ insights }: { insights: string[] }) {
  return (
    <div className="rounded-lg border border-brand-blue/20 bg-blue-50 p-5">
      <h4 className="font-semibold text-brand-ink">규칙 기반 행정 인사이트</h4>
      <ul className="mt-3 grid gap-2 text-sm text-gray-700">
        {insights.map((insight) => <li key={insight}>• {insight}</li>)}
      </ul>
      <p className="mt-3 text-xs text-gray-500">선택형 익명 집계만 사용하며 AI/LLM을 사용하지 않습니다.</p>
    </div>
  )
}
