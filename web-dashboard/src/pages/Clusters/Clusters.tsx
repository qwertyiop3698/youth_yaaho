import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { useClusters } from '../../hooks/useClusters'
import { useRiskTrajectoryOutlook } from '../../hooks/useRiskTrajectoryOutlook'
import { NotReadyBanner, QueryState } from '../../components/QueryState'
import { StatCard } from '../../components/StatCard'
import { colorForIndex } from '../../colors'
import type { ClustersReady, RiskTrajectoryOutlookResponse } from '../../api/types'

export function Clusters() {
  const { data, isLoading, isError, error } = useClusters()
  const trajectoryQuery = useRiskTrajectoryOutlook()

  return (
    <QueryState isLoading={isLoading} isError={isError} error={error}>
      {data && data.ready ? (
        <ClustersContent data={data} trajectory={trajectoryQuery.data} />
      ) : data ? (
        <NotReadyBanner reason={data.reason} />
      ) : null}
    </QueryState>
  )
}

function ClustersContent({ data, trajectory }: { data: ClustersReady; trajectory: RiskTrajectoryOutlookResponse | undefined }) {
  const profiles = data.cluster_profiles ?? {}
  const clusterKeys = Object.keys(profiles)
  const totalPopulation = Object.values(data.cluster_sizes ?? {}).reduce((sum, n) => sum + n, 0)

  // 도메인지수 이름은 하드코딩하지 않고 실제 응답에서 뽑는다(첫 클러스터 프로파일의 키).
  const domainNames = clusterKeys.length > 0 ? Object.keys(profiles[clusterKeys[0]]) : []
  const radarData = domainNames.map((domain) => {
    const row: Record<string, string | number> = { domain }
    for (const key of clusterKeys) {
      row[key] = profiles[key][domain]
    }
    return row
  })

  return (
    <div className="flex flex-col gap-6">
      <h2 className="text-xl font-semibold">유형별 상세</h2>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <StatCard label="탐지된 유형(클러스터) 수" value={String(data.best_k)} />
        <StatCard label="전체 인원(소프트 합)" value={totalPopulation.toFixed(0)} />
      </div>

      <div className="rounded-lg border border-brand-border bg-white p-5 shadow-sm">
        <h3 className="mb-4 text-sm font-medium text-gray-500">클러스터별 도메인지수 프로파일(z-score)</h3>
        {radarData.length === 0 ? (
          <p className="text-sm text-gray-400">프로파일 데이터가 없습니다.</p>
        ) : (
          <div className="h-96" role="img" aria-label="클러스터별 도메인지수 z-score 레이더 차트">
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart data={radarData}>
                <PolarGrid />
                <PolarAngleAxis dataKey="domain" tick={{ fontSize: 12 }} />
                <PolarRadiusAxis />
                {clusterKeys.map((key, index) => (
                  <Radar
                    key={key}
                    name={data.suggested_labels?.[key] ?? key}
                    dataKey={key}
                    stroke={colorForIndex(index)}
                    fill={colorForIndex(index)}
                    fillOpacity={0.15}
                  />
                ))}
                <Tooltip />
                <Legend />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {clusterKeys.map((key, index) => (
          <ClusterCard
            key={key}
            clusterKey={key}
            label={data.suggested_labels?.[key]}
            size={data.cluster_sizes?.[key]}
            profile={profiles[key]}
            color={colorForIndex(index)}
          />
        ))}
      </div>

      <RiskTrajectoryPanel trajectory={trajectory} />
    </div>
  )
}

function RiskTrajectoryPanel({ trajectory }: { trajectory: RiskTrajectoryOutlookResponse | undefined }) {
  if (!trajectory) return null

  if (!trajectory.ready) {
    return (
      <div className="rounded-lg border border-brand-border bg-white p-5 shadow-sm">
        <h3 className="mb-4 text-sm font-medium text-gray-500">위험 궤적 시뮬레이션: 정책 미개입 vs 정책 반영</h3>
        <NotReadyBanner reason={trajectory.reason} />
      </div>
    )
  }

  const chartData = trajectory.no_intervention.map((step, i) => ({
    step: step.step,
    no_intervention_risk: step.expected_avg_risk,
    intervention_risk: trajectory.intervention[i]?.expected_avg_risk,
  }))

  return (
    <div className="rounded-lg border border-brand-border bg-white p-5 shadow-sm">
      <h3 className="mb-1 text-sm font-medium text-gray-500">위험 궤적 시뮬레이션: 정책 미개입 vs 정책 반영</h3>
      <div className="mb-4 rounded-lg border border-orange-200 bg-orange-50 p-3 text-sm text-orange-800">
        {trajectory.simulation_disclaimer}
      </div>
      <div className="h-72" role="img" aria-label="정책 미개입 대비 정책 반영 시나리오의 위험 궤적 라인 차트">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="step" label={{ value: '스텝(가상 개월)', position: 'insideBottom', offset: -5 }} />
            <YAxis domain={[0, 1]} tickFormatter={(v: number) => v.toFixed(2)} />
            <Tooltip formatter={(v: number) => v.toFixed(3)} />
            <Legend />
            <Line
              type="monotone"
              dataKey="no_intervention_risk"
              name="정책 미개입(위험 심화 가정)"
              stroke="#ef4444"
              strokeWidth={2}
              dot={false}
            />
            <Line
              type="monotone"
              dataKey="intervention_risk"
              name="정책 반영(개입 효과 가정)"
              stroke="#0ea5e9"
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

interface ClusterCardProps {
  clusterKey: string
  label: string | undefined
  size: number | undefined
  profile: Record<string, number>
  color: string
}

function ClusterCard({ clusterKey, label, size, profile, color }: ClusterCardProps) {
  const entries = Object.entries(profile)
  const topDomain = entries.length > 0 ? entries.reduce((a, b) => (b[1] > a[1] ? b : a)) : null

  return (
    <div className="rounded-lg border border-brand-border bg-white p-4 shadow-sm">
      <div className="flex items-center gap-2">
        <span className="h-3 w-3 rounded-full" style={{ backgroundColor: color }} />
        <p className="font-medium text-brand-ink">{label ?? clusterKey}</p>
      </div>
      <p className="mt-1 text-xs text-gray-400">{clusterKey}</p>
      <p className="mt-3 text-sm text-gray-600">
        인원(소프트 합): <span className="font-medium text-brand-ink">{size !== undefined ? size.toFixed(1) : '—'}</span>
      </p>
      {topDomain && (
        <p className="mt-1 text-sm text-gray-600">
          대표 특성: <span className="font-medium text-brand-ink">{topDomain[0]}</span> (z={topDomain[1].toFixed(2)})
        </p>
      )}
    </div>
  )
}
