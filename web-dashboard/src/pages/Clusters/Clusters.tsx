import {
  Legend,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
} from 'recharts'
import { useClusters } from '../../hooks/useClusters'
import { NotReadyBanner, QueryState } from '../../components/QueryState'
import { StatCard } from '../../components/StatCard'
import { colorForIndex } from '../../colors'
import type { ClustersReady } from '../../api/types'

export function Clusters() {
  const { data, isLoading, isError, error } = useClusters()

  return (
    <QueryState isLoading={isLoading} isError={isError} error={error}>
      {data && data.ready ? <ClustersContent data={data} /> : data ? <NotReadyBanner reason={data.reason} /> : null}
    </QueryState>
  )
}

function ClustersContent({ data }: { data: ClustersReady }) {
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

      <div className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
        <h3 className="mb-4 text-sm font-medium text-gray-500">클러스터별 도메인지수 프로파일(z-score)</h3>
        {radarData.length === 0 ? (
          <p className="text-sm text-gray-400">프로파일 데이터가 없습니다.</p>
        ) : (
          <div className="h-96">
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
    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <div className="flex items-center gap-2">
        <span className="h-3 w-3 rounded-full" style={{ backgroundColor: color }} />
        <p className="font-medium text-gray-900">{label ?? clusterKey}</p>
      </div>
      <p className="mt-1 text-xs text-gray-400">{clusterKey}</p>
      <p className="mt-3 text-sm text-gray-600">
        인원(소프트 합): <span className="font-medium text-gray-900">{size !== undefined ? size.toFixed(1) : '—'}</span>
      </p>
      {topDomain && (
        <p className="mt-1 text-sm text-gray-600">
          대표 특성: <span className="font-medium text-gray-900">{topDomain[0]}</span> (z={topDomain[1].toFixed(2)})
        </p>
      )}
    </div>
  )
}
