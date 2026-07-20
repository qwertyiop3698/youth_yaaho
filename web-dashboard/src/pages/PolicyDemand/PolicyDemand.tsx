import { useMemo, useState } from 'react'
import type { PolicyDemandPriority, PolicyDemandSummary, ProtectedDistribution } from '../../api/types'
import { QueryState } from '../../components/QueryState'
import { StatCard } from '../../components/StatCard'
import { downloadPolicyDemand, usePolicyDemand } from '../../hooks/usePolicyDemand'

const REC: Record<string, string> = {
  create_new_policy: '신규 정책 검토', broaden_eligibility: '기존 정책 자격 완화 검토',
  increase_amount: '지원금 확대 검토', extend_duration: '지원기간 연장 검토',
  create_package: '복수 정책 패키지 검토', reopen_recruitment: '모집기간·횟수 확대 검토',
  simplify_application: '신청절차 개선 검토', insufficient_data: '판단 유보',
}
function top(distribution?: ProtectedDistribution) {
  const values = Object.entries(distribution ?? {}).filter(([, cell]) => !cell.suppressed && cell.count !== null)
  return values.sort((a, b) => (b[1].count ?? 0) - (a[1].count ?? 0))[0]?.[0] ?? '공개 불가'
}
function trend(summary: PolicyDemandSummary) {
  const value = summary.metrics?.trend_30_days
  if (!value || value.suppressed || value.change_rate === null) return '공개 불가'
  return `${value.change_rate >= 0 ? '+' : ''}${(value.change_rate * 100).toFixed(1)}%`
}

export function PolicyDemand() {
  const query = usePolicyDemand()
  return <QueryState isLoading={query.summary.isLoading || query.priorities.isLoading} isError={query.summary.isError || query.priorities.isError} error={query.summary.error ?? query.priorities.error}>
    <PolicyDemandDashboard summary={query.summary.data!} priorities={query.priorities.data ?? []} />
  </QueryState>
}

export function PolicyDemandDashboard({ summary, priorities, onDownload = downloadPolicyDemand }: {
  summary: PolicyDemandSummary; priorities: PolicyDemandPriority[]; onDownload?: (format: 'csv' | 'json') => void | Promise<void>
}) {
  const [district, setDistrict] = useState('all'); const [employment, setEmployment] = useState('all')
  const [area, setArea] = useState('all'); const [reason, setReason] = useState('all'); const [includeSmall, setIncludeSmall] = useState(false)
  const filtered = useMemo(() => priorities.filter((item) => includeSmall || item.publicly_available)
    .filter((item) => district === 'all' || item.top_district === district)
    .filter((item) => employment === 'all' || item.top_employment_status === employment)
    .filter((item) => area === 'all' || item.need_area === area)
    .filter((item) => reason === 'all' || item.top_trigger_reason === reason)
    .sort((a, b) => (b.score ?? -1) - (a.score ?? -1)), [area, district, employment, includeSmall, priorities, reason])
  const options = (field: keyof PolicyDemandPriority) => [...new Set(priorities.map((item) => item[field]).filter((value): value is string => typeof value === 'string'))]
  return <div className="flex flex-col gap-6">
    <div className="flex flex-wrap justify-between gap-3"><div><p className="text-sm font-medium text-brand-blue">익명 정책 공백 데이터</p><h2 className="text-2xl font-semibold">정책 미충족 수요</h2><p className="mt-2 text-sm text-gray-500">현재 정책으로 충족되지 않은 요구를 정책 이용 후기와 분리해 보여줍니다.</p></div><div className="flex gap-2"><button className="rounded border px-3 py-2" onClick={() => void onDownload('csv')}>CSV 다운로드</button><button className="rounded border px-3 py-2" onClick={() => void onDownload('json')}>JSON 다운로드</button></div></div>
    {summary.suppressed || !summary.metrics ? <div className="rounded-xl border border-amber-200 bg-amber-50 p-5">응답 인원이 적어 세부 수요를 공개하지 않습니다.</div> : <>
      <div className="grid gap-3 md:grid-cols-5"><StatCard label="가장 필요한 지원" value={top(summary.metrics.need_area_distribution)} /><StatCard label="가장 큰 정책 장벽" value={top(summary.metrics.barrier_distribution)} /><StatCard label="희망 지원금액" value={top(summary.metrics.amount_distribution)} /><StatCard label="희망 지원기간" value={top(summary.metrics.duration_distribution)} /><StatCard label="최근 30일 수요 변화" value={trend(summary)} /></div>
      <div className="rounded-xl border bg-blue-50 p-4"><h3 className="font-semibold">정책 후기와 비교 요약</h3><ul className="mt-2 text-sm">{summary.comparison_summary.map((item) => <li key={item}>• {item}</li>)}</ul></div>
    </>}
    <div className="grid gap-3 rounded-xl border p-4 md:grid-cols-5"><Select label="구·군" value={district} set={setDistrict} options={options('top_district')} /><Select label="고용상태" value={employment} set={setEmployment} options={options('top_employment_status')} /><Select label="수요 분야" value={area} set={setArea} options={options('need_area')} /><Select label="노출 사유" value={reason} set={setReason} options={options('top_trigger_reason')} /><label className="flex items-end gap-2 pb-2 text-sm"><input type="checkbox" checked={includeSmall} onChange={(event) => setIncludeSmall(event.target.checked)} />표본 부족 포함</label></div>
    <div className="overflow-x-auto rounded-xl border bg-white"><table className="min-w-full text-left text-sm"><thead className="bg-brand-surface-muted"><tr>{['순위', '수요 분야', '응답자', '우선순위', '신뢰도', '구·군', '고용상태', '검토 권고'].map((label) => <th className="px-3 py-3" key={label}>{label}</th>)}</tr></thead><tbody>{filtered.map((item, index) => <tr className="border-t" key={item.need_area}><td className="px-3 py-3">{item.score === null ? '-' : index + 1}</td><td className="px-3 py-3 font-medium">{item.need_area}</td><td className="px-3 py-3">{item.respondent_count ?? '비공개'}</td><td className="px-3 py-3">{item.score?.toFixed(1) ?? '비공개'}</td><td className="px-3 py-3">{{ low: '낮음', medium: '보통', high: '높음' }[item.confidence]}</td><td className="px-3 py-3">{item.top_district ?? '비공개'}</td><td className="px-3 py-3">{item.top_employment_status ?? '비공개'}</td><td className="px-3 py-3">{REC[item.primary_recommendation] ?? item.primary_recommendation}</td></tr>)}</tbody></table></div>
    {filtered[0] && <div className="rounded-xl border bg-white p-5"><h3 className="font-semibold">우선 검토 참고</h3><p className="mt-2 text-sm">{filtered[0].summary[0]}</p><p className="mt-2 text-xs text-gray-500">자동 결정이 아닌 행정 검토 참고자료이며, 종료 정책을 자동 재노출하지 않습니다.</p></div>}
  </div>
}
function Select({ label, value, set, options }: { label: string; value: string; set: (value: string) => void; options: string[] }) {
  return <label className="text-xs text-gray-600">{label}<select aria-label={label} value={value} onChange={(event) => set(event.target.value)} className="mt-1 w-full rounded border p-2 text-sm"><option value="all">전체</option>{options.map((option) => <option key={option}>{option}</option>)}</select></label>
}

