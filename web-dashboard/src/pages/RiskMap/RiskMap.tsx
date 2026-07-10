import { useState } from 'react'
import { useRiskMap } from '../../hooks/useRiskMap'
import { NotReadyBanner, QueryState } from '../../components/QueryState'
import type { RiskMapLevel, RiskRegion } from '../../api/types'

const LEVELS: { value: RiskMapLevel; label: string }[] = [
  { value: 'sigungu', label: '시군구' },
  { value: 'dong', label: '행정동' },
]

// 위험도(0~1)를 초록(안전) -> 빨강(위험) 2색 보간으로 표현. 실제 Kakao Map
// choropleth 연동 전까지 이 카드 그리드가 지도 역할을 대신한다.
function riskColor(risk: number): string {
  const clamped = Math.min(1, Math.max(0, risk))
  const r = Math.round(34 + (220 - 34) * clamped)
  const g = Math.round(150 + (38 - 150) * clamped)
  const b = Math.round(94 + (38 - 94) * clamped)
  return `rgb(${r}, ${g}, ${b})`
}

export function RiskMap() {
  const [level, setLevel] = useState<RiskMapLevel>('sigungu')
  const { data, isLoading, isError, error } = useRiskMap(level)

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">지역 위험지도</h2>
        <div className="flex gap-1 rounded-lg border border-gray-200 bg-white p-1">
          {LEVELS.map((l) => (
            <button
              key={l.value}
              type="button"
              onClick={() => setLevel(l.value)}
              className={`rounded px-3 py-1 text-sm ${
                level === l.value ? 'bg-gray-900 text-white' : 'text-gray-600 hover:bg-gray-100'
              }`}
            >
              {l.label}
            </button>
          ))}
        </div>
      </div>

      <div className="rounded-lg border border-blue-200 bg-blue-50 p-3 text-sm text-blue-800">
        Kakao Map API 키 발급 전까지는 실제 지도 대신 지역별 위험도 카드 그리드로 표시합니다. 키
        발급 후 이 영역을 Kakao Map choropleth로 교체할 예정입니다.
      </div>

      <QueryState isLoading={isLoading} isError={isError} error={error}>
        {data && data.ready ? (
          <RiskMapGrid regions={data.regions} />
        ) : data ? (
          <NotReadyBanner reason={data.reason} />
        ) : null}
      </QueryState>
    </div>
  )
}

function RiskMapGrid({ regions }: { regions: RiskRegion[] }) {
  if (regions.length === 0) {
    return <p className="text-sm text-gray-400">표시할 지역 데이터가 없습니다.</p>
  }

  const sorted = [...regions].sort((a, b) => b.avg_risk_probability - a.avg_risk_probability)

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
      {sorted.map((region) => (
        <div
          key={region.region_code}
          className="rounded-lg p-4 text-white shadow-sm"
          style={{ backgroundColor: riskColor(region.avg_risk_probability) }}
        >
          <p className="text-xs opacity-90">{region.region_code}</p>
          <p className="mt-1 text-2xl font-semibold">{(region.avg_risk_probability * 100).toFixed(0)}%</p>
          <p className="mt-1 text-xs opacity-90">표본 {region.n}명</p>
        </div>
      ))}
    </div>
  )
}
