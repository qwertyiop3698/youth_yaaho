import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import { useOverview } from '../../hooks/useOverview'
import { StatCard } from '../../components/StatCard'
import { NotReadyBanner, QueryState } from '../../components/QueryState'
import { colorForIndex } from '../../colors'
import type { OverviewReady } from '../../api/types'

export function Overview() {
  const { data, isLoading, isError, error } = useOverview()

  return (
    <QueryState isLoading={isLoading} isError={isError} error={error}>
      {data && data.ready ? <OverviewContent data={data} /> : data ? <NotReadyBanner reason={data.reason} /> : null}
    </QueryState>
  )
}

function OverviewContent({ data }: { data: OverviewReady }) {
  const clusterEntries = Object.entries(data.cluster_sizes ?? {})
  const pieData = clusterEntries.map(([key, value]) => ({
    name: data.suggested_labels?.[key] ?? key,
    value,
  }))

  return (
    <div className="flex flex-col gap-6">
      <h2 className="text-xl font-semibold">종합 현황판</h2>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <StatCard label="부산 청년 1인가구 수" value={data.total_citizens.toLocaleString('ko-KR')} />
        <StatCard
          label="평균 프록시 위험점수"
          value={data.avg_risk_probability !== null ? `${(data.avg_risk_probability * 100).toFixed(1)}%` : '—'}
          hint="현재 프록시 라벨 기반 점수(0~1)의 전체 평균이며 미래 사건 확률이 아닙니다."
        />
      </div>

      <div className="rounded-lg border border-brand-border bg-white p-5 shadow-sm">
        <h3 className="mb-4 text-sm font-medium text-gray-500">유형(클러스터)별 분포</h3>
        {pieData.length === 0 ? (
          <p className="text-sm text-gray-400">클러스터 데이터가 없습니다.</p>
        ) : (
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={100} label>
                  {pieData.map((entry, index) => (
                    <Cell key={entry.name} fill={colorForIndex(index)} />
                  ))}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  )
}
