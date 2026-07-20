import { useMemo, useState } from 'react'
import type {
  AnalysisConfidence,
  PolicyFeedbackAnalysis,
  PolicyRecommendation,
} from '../../api/types'
import { downloadPolicyAnalysis } from '../../hooks/usePolicyFeedbackAnalysis'

const RECOMMENDATION_LABELS: Record<PolicyRecommendation, string> = {
  maintain: '현행 유지 검토',
  expand: '확대 검토',
  simplify: '신청 절차 개선 검토',
  retarget: '대상 조건 조정 검토',
  extend_duration: '지원기간 연장 검토',
  increase_amount: '지원금 확대 검토',
  connect_followup: '후속 정책 연계 검토',
  redesign: '전반적 개편 검토',
  insufficient_data: '표본 부족',
}

const CONFIDENCE_LABELS: Record<AnalysisConfidence, string> = { low: '낮음', medium: '보통', high: '높음' }

const BUTTON_CLASS =
  'rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-700 transition-colors hover:bg-brand-surface-muted focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-blue'

function score(value: number | null, insufficient = false) {
  return insufficient || value === null ? '비공개' : value.toFixed(1)
}

function urgencyBand(value: number | null) {
  if (value === null) return 'insufficient'
  if (value >= 70) return 'high'
  if (value >= 40) return 'medium'
  return 'low'
}

interface Props {
  analyses: PolicyFeedbackAnalysis[]
  onDownload?: (format: 'csv' | 'json') => Promise<void> | void
}

export function PolicyPriorityAnalysis({ analyses, onDownload = downloadPolicyAnalysis }: Props) {
  const [category, setCategory] = useState('all')
  const [confidence, setConfidence] = useState('all')
  const [recommendation, setRecommendation] = useState('all')
  const [band, setBand] = useState('all')
  const [includeInsufficient, setIncludeInsufficient] = useState(false)
  const [descending, setDescending] = useState(true)
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const categories = useMemo(() => [...new Set(analyses.map((item) => item.category))].sort(), [analyses])
  const filtered = useMemo(
    () =>
      analyses
        .filter((item) => includeInsufficient || item.primary_recommendation !== 'insufficient_data')
        .filter((item) => category === 'all' || item.category === category)
        .filter((item) => confidence === 'all' || item.confidence === confidence)
        .filter((item) => recommendation === 'all' || item.primary_recommendation === recommendation)
        .filter((item) => band === 'all' || urgencyBand(item.scores.improvement_urgency) === band)
        .sort((a, b) => {
          const left = a.scores.improvement_urgency ?? -1
          const right = b.scores.improvement_urgency ?? -1
          return descending ? right - left : left - right
        }),
    [analyses, band, category, confidence, descending, includeInsufficient, recommendation],
  )
  const selected = analyses.find((item) => item.policy_id === selectedId) ?? filtered[0]

  return (
    <section className="flex flex-col gap-5" aria-labelledby="priority-analysis-title">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h3 id="priority-analysis-title" className="text-lg font-semibold">
            정책 개선 우선순위
          </h3>
          <p className="mt-1 text-sm text-gray-500">익명 집계에 규칙 기반 점수를 적용한 행정 검토용 참고자료입니다.</p>
        </div>
        <div className="flex gap-2">
          <button type="button" className={BUTTON_CLASS} onClick={() => void onDownload('csv')}>
            CSV 다운로드
          </button>
          <button type="button" className={BUTTON_CLASS} onClick={() => void onDownload('json')}>
            JSON 다운로드
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 rounded-lg border border-brand-border bg-white p-4 md:grid-cols-5">
        <Filter label="정책 카테고리" value={category} onChange={setCategory} options={categories} />
        <Filter
          label="분석 신뢰도"
          value={confidence}
          onChange={setConfidence}
          options={['high', 'medium', 'low']}
          labels={CONFIDENCE_LABELS}
        />
        <Filter
          label="주요 권고"
          value={recommendation}
          onChange={setRecommendation}
          options={Object.keys(RECOMMENDATION_LABELS)}
          labels={RECOMMENDATION_LABELS}
        />
        <Filter
          label="개선 시급도 구간"
          value={band}
          onChange={setBand}
          options={['high', 'medium', 'low']}
          labels={{ high: '70 이상', medium: '40~69.9', low: '40 미만' }}
        />
        <label className="flex items-end gap-2 pb-2 text-sm">
          <input
            type="checkbox"
            checked={includeInsufficient}
            onChange={(event) => setIncludeInsufficient(event.target.checked)}
          />
          표본 부족 포함
        </label>
      </div>

      <div className="overflow-x-auto rounded-lg border border-brand-border bg-white shadow-sm">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-brand-surface-muted text-gray-600">
            <tr>
              {['순위', '정책명', '카테고리', '효과', '접근성', '지원 적정성'].map((label) => (
                <th key={label} className="px-3 py-3">
                  {label}
                </th>
              ))}
              <th className="px-3 py-3">
                <button
                  type="button"
                  className="font-medium underline transition-colors hover:text-brand-blue focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-blue"
                  onClick={() => setDescending((value) => !value)}
                >
                  개선 시급도 {descending ? '↓' : '↑'}
                </button>
              </th>
              <th className="px-3 py-3">신뢰도</th>
              <th className="px-3 py-3">주요 권고</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((item, index) => {
              const insufficient = item.primary_recommendation === 'insufficient_data'
              return (
                <tr key={item.policy_id} className="border-t border-brand-border">
                  <td className="px-3 py-3">{item.ranks.improvement_urgency ?? index + 1}</td>
                  <td className="px-3 py-3">
                    <button
                      type="button"
                      className="font-medium text-brand-blue transition-colors hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-blue"
                      onClick={() => setSelectedId(item.policy_id)}
                    >
                      {item.policy_name}
                    </button>
                  </td>
                  <td className="px-3 py-3">{item.category}</td>
                  <td className="px-3 py-3">{score(item.scores.effectiveness, insufficient)}</td>
                  <td className="px-3 py-3">{score(item.scores.accessibility, insufficient)}</td>
                  <td className="px-3 py-3">{score(item.scores.support_adequacy, insufficient)}</td>
                  <td className="px-3 py-3">{score(item.scores.improvement_urgency, insufficient)}</td>
                  <td className="px-3 py-3">
                    <span className="rounded-full bg-blue-50 px-2 py-1">{CONFIDENCE_LABELS[item.confidence]}</span>
                  </td>
                  <td className="px-3 py-3">{RECOMMENDATION_LABELS[item.primary_recommendation]}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
        {filtered.length === 0 && <p className="p-5 text-sm text-gray-500">조건에 맞는 공개 가능 분석이 없습니다.</p>}
      </div>
      {selected && <PolicyAnalysisDetail analysis={selected} />}
    </section>
  )
}

function Filter({
  label,
  value,
  onChange,
  options,
  labels = {},
}: {
  label: string
  value: string
  onChange: (value: string) => void
  options: string[]
  labels?: Record<string, string>
}) {
  return (
    <label className="text-xs text-gray-600">
      {label}
      <select
        aria-label={label}
        className="mt-1 w-full rounded-lg border border-gray-300 p-2 text-sm"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="all">전체</option>
        {options.map((option) => (
          <option key={option} value={option}>
            {labels[option] ?? option}
          </option>
        ))}
      </select>
    </label>
  )
}

export function PolicyAnalysisDetail({ analysis }: { analysis: PolicyFeedbackAnalysis }) {
  const insufficient = analysis.primary_recommendation === 'insufficient_data'
  return (
    <div className="rounded-lg border border-brand-border bg-white p-5" aria-label="정책 상세 분석">
      <div className="flex flex-wrap justify-between gap-2">
        <div>
          <p className="text-xs text-gray-500">정책 상세 분석</p>
          <h4 className="text-lg font-semibold">{analysis.policy_name}</h4>
        </div>
        <span className="text-sm">분석 신뢰도: {CONFIDENCE_LABELS[analysis.confidence]}</span>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-5">
        {(
          [
            ['종합 정책 효과', analysis.scores.effectiveness],
            ['신청 접근성', analysis.scores.accessibility],
            ['지원 적정성', analysis.scores.support_adequacy],
            ['후속 연계 필요도', analysis.scores.followup_need],
            ['개선 시급도', analysis.scores.improvement_urgency],
          ] as const
        ).map(([label, value]) => (
          <div key={label} className="rounded-lg bg-gray-50 p-3">
            <p className="text-xs text-gray-500">{label}</p>
            <p className="mt-1 text-xl font-semibold">{score(value, insufficient)}</p>
          </div>
        ))}
      </div>
      <dl className="mt-4 grid gap-3 text-sm md:grid-cols-3">
        <div>
          <dt className="text-gray-500">주요 신청 병목</dt>
          <dd>{insufficient ? '공개 불가' : (analysis.primary_bottleneck ?? '뚜렷한 병목 없음')}</dd>
        </div>
        <div>
          <dt className="text-gray-500">가장 필요한 후속 정책</dt>
          <dd>{insufficient ? '공개 불가' : (analysis.top_followup_need ?? '공개 가능한 수요 없음')}</dd>
        </div>
        <div>
          <dt className="text-gray-500">대안 검토 권고</dt>
          <dd>
            {RECOMMENDATION_LABELS[analysis.primary_recommendation]}
            {analysis.secondary_recommendations.map((item) => ` · ${RECOMMENDATION_LABELS[item]}`)}
          </dd>
        </div>
      </dl>
      <ul className="mt-4 space-y-1 rounded-lg bg-blue-50 p-4 text-sm">
        {analysis.summary.map((item) => (
          <li key={item}>• {item}</li>
        ))}
      </ul>
      <p className="mt-3 text-xs text-gray-500">이 결과는 자동 의사결정이 아니라 정책 담당자의 추가 검토를 돕는 참고자료입니다.</p>
    </div>
  )
}
