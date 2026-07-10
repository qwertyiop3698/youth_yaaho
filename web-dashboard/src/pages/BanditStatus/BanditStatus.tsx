import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useBanditStatus } from '../../hooks/useBanditStatus'
import { NotReadyBanner, QueryState } from '../../components/QueryState'
import { StatCard } from '../../components/StatCard'
import type { BanditStatusReady } from '../../api/types'

export function BanditStatus() {
  const { data, isLoading, isError, error } = useBanditStatus()

  return (
    <QueryState isLoading={isLoading} isError={isError} error={error}>
      {data && data.ready ? <BanditStatusContent data={data} /> : data ? <NotReadyBanner reason={data.reason} /> : null}
    </QueryState>
  )
}

function BanditStatusContent({ data }: { data: BanditStatusReady }) {
  const segmentData = data.segment_regret.map((s) => ({
    label: s.segment_label,
    mean_instant_regret: s.mean_instant_regret,
  }))

  const first = data.segment_regret[0]?.mean_instant_regret ?? null
  const last = data.segment_regret[data.segment_regret.length - 1]?.mean_instant_regret ?? null
  const improvementPct = first !== null && last !== null && first !== 0 ? ((first - last) / first) * 100 : null

  const policyNames = Object.keys(data.true_effectiveness)
  const comparisonData = policyNames.map((policy) => ({
    policy,
    prior: data.effectiveness_prior_vs_true_gap.find((g) => g.policy === policy)?.effectiveness_prior ?? null,
    true_effectiveness: data.true_effectiveness[policy],
    learned: data.final_posterior_means[policy],
  }))

  return (
    <div className="flex flex-col gap-6">
      <h2 className="text-xl font-semibold">밴딧 학습 현황</h2>

      {data.is_simulation && (
        <div className="rounded-lg border border-orange-200 bg-orange-50 p-3 text-sm text-orange-800">
          {data.simulation_disclaimer}
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <StatCard label="시뮬레이션 라운드 수" value={data.n_rounds.toLocaleString('ko-KR')} />
        <StatCard
          label="구간별 평균 regret 개선율(초반 대비 후반)"
          value={improvementPct !== null ? `${improvementPct.toFixed(1)}%` : '—'}
          hint="누적 regret은 성질상 항상 단조 증가라 학습 증거가 못 됨 - 구간별 평균 감소가 실제 지표"
        />
      </div>

      <div className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
        <h3 className="mb-4 text-sm font-medium text-gray-500">구간별(초반/중반/후반) 평균 순간 regret</h3>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={segmentData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="label" />
              <YAxis />
              <Tooltip />
              <Bar dataKey="mean_instant_regret" name="평균 순간 regret" fill="#ef4444" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
        <h3 className="mb-4 text-sm font-medium text-gray-500">
          정책별 효과 추정치: 초기 가정치(prior) vs 숨겨진 정답(true, 시뮬레이션 전용) vs 밴딧 학습값(learned)
        </h3>
        <div className="h-80">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={comparisonData} layout="vertical" margin={{ left: 24 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" domain={[0, 1]} />
              <YAxis type="category" dataKey="policy" width={140} tick={{ fontSize: 12 }} />
              <Tooltip />
              <Legend />
              <Bar dataKey="prior" name="초기 가정치(prior)" fill="#94a3b8" />
              <Bar dataKey="true_effectiveness" name="숨겨진 정답(true)" fill="#0ea5e9" />
              <Bar dataKey="learned" name="밴딧 학습값(learned)" fill="#10b981" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
        <h3 className="mb-4 text-sm font-medium text-gray-500">정책별 격차 요약</h3>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[560px] text-left text-sm">
            <thead className="text-gray-500">
              <tr>
                <th className="border-b border-gray-200 py-2 pr-4">정책</th>
                <th className="border-b border-gray-200 py-2 pr-4">초기 가정치</th>
                <th className="border-b border-gray-200 py-2 pr-4">숨겨진 정답</th>
                <th className="border-b border-gray-200 py-2 pr-4">밴딧 학습값</th>
                <th className="border-b border-gray-200 py-2">방향</th>
              </tr>
            </thead>
            <tbody>
              {data.effectiveness_prior_vs_true_gap.map((row) => (
                <tr key={row.policy}>
                  <td className="py-1.5 pr-4">{row.policy}</td>
                  <td className="py-1.5 pr-4">{row.effectiveness_prior.toFixed(2)}</td>
                  <td className="py-1.5 pr-4">{row.true_effectiveness?.toFixed(2) ?? '—'}</td>
                  <td className="py-1.5 pr-4">{data.final_posterior_means[row.policy]?.toFixed(2) ?? '—'}</td>
                  <td className="py-1.5 text-gray-600">{row.direction ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
