import { useMemo, useState } from 'react'
import { Map as KakaoMap, Polygon, CustomOverlayMap, useKakaoLoader } from 'react-kakao-maps-sdk'
import { useRiskMap } from '../../hooks/useRiskMap'
import { useBusanGeoJson } from '../../hooks/useBusanGeoJson'
import { QueryState, NotReadyBanner } from '../../components/QueryState'
import type { RiskMapLevel, RiskRegion } from '../../api/types'
import { featureOuterRings, featureLabelPoint, riskColor, NO_DATA_COLOR } from '../../utils/geo'
import type { BusanDistrictFeature } from '../../utils/geo'

const LEVELS: { value: RiskMapLevel; label: string }[] = [
  { value: 'sigungu', label: '시군구' },
  { value: 'dong', label: '행정동' },
]

const BUSAN_CENTER = { lat: 35.1796, lng: 129.0756 }
const KAKAO_APP_KEY = import.meta.env.VITE_KAKAO_MAP_APP_KEY

export function RiskMap() {
  const [level, setLevel] = useState<RiskMapLevel>('sigungu')
  const { data, isLoading, isError, error } = useRiskMap(level)

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">지역 위험지도</h2>
        <div className="flex gap-1 rounded-lg border border-brand-border bg-white p-1">
          {LEVELS.map((l) => (
            <button
              key={l.value}
              type="button"
              onClick={() => setLevel(l.value)}
              className={`rounded px-3 py-1 text-sm ${
                level === l.value ? 'bg-brand-blue text-white' : 'text-gray-600 hover:bg-brand-surface-muted'
              }`}
            >
              {l.label}
            </button>
          ))}
        </div>
      </div>

      <QueryState isLoading={isLoading} isError={isError} error={error}>
        {data && data.ready ? (
          level === 'sigungu' ? (
            <RiskChoroplethMap regions={data.regions} />
          ) : (
            <div className="flex flex-col gap-3">
              <div className="rounded-lg border border-blue-200 bg-blue-50 p-3 text-sm text-blue-800">
                행정동 단위는 아직 경계 데이터가 없어 카드 그리드로 표시합니다. 지도로 보려면 시군구
                단위를 선택해주세요.
              </div>
              <RiskMapGrid regions={data.regions} />
            </div>
          )
        ) : data ? (
          <NotReadyBanner reason={data.reason} />
        ) : null}
      </QueryState>
    </div>
  )
}

function RiskChoroplethMap({ regions }: { regions: RiskRegion[] }) {
  const [kakaoLoading, kakaoError] = useKakaoLoader({ appkey: KAKAO_APP_KEY ?? '' })
  const { data: geojson, isLoading: geoLoading, isError: geoError } = useBusanGeoJson()
  const [hoveredCode, setHoveredCode] = useState<string | null>(null)

  const regionByCode = useMemo(() => {
    const map = new globalThis.Map<string, RiskRegion>()
    for (const region of regions) map.set(region.region_code, region)
    return map
  }, [regions])

  if (!KAKAO_APP_KEY) {
    return (
      <div className="rounded-lg border border-yellow-200 bg-yellow-50 p-4 text-sm text-yellow-800">
        Kakao Map 키가 설정되지 않았습니다. web-dashboard/.env의 VITE_KAKAO_MAP_APP_KEY에 Kakao
        Developers에서 발급받은 JavaScript 키를 넣어주세요.
      </div>
    )
  }

  if (kakaoError) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
        Kakao Map을 불러오지 못했습니다. 키가 올바른지, Kakao Developers에서 현재 도메인이 Web
        플랫폼으로 등록되어 있는지 확인해주세요.
      </div>
    )
  }

  if (geoError) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
        부산 행정구역 경계 데이터를 불러오지 못했습니다.
      </div>
    )
  }

  if (kakaoLoading || geoLoading || !geojson) {
    return <p className="text-sm text-gray-500">지도를 불러오는 중...</p>
  }

  const hoveredFeature = geojson.features.find((f) => f.properties.region_code === hoveredCode)
  const hoveredRegion = hoveredCode ? regionByCode.get(hoveredCode) : undefined

  return (
    <div className="flex flex-col gap-3">
      <KakaoMap center={BUSAN_CENTER} level={10} style={{ width: '100%', height: '560px', borderRadius: '0.5rem' }}>
        {geojson.features.map((feature) => {
          const region = regionByCode.get(feature.properties.region_code)
          const color = region ? riskColor(region.avg_risk_probability) : NO_DATA_COLOR
          return featureOuterRings(feature).map((path, i) => (
            <Polygon
              key={`${feature.properties.region_code}-${i}`}
              path={path}
              fillColor={color}
              fillOpacity={region ? 0.75 : 0.35}
              strokeColor="#FFFFFF"
              strokeWeight={2}
              strokeOpacity={0.9}
              onMouseover={() => setHoveredCode(feature.properties.region_code)}
              onMouseout={() =>
                setHoveredCode((prev) => (prev === feature.properties.region_code ? null : prev))
              }
            />
          ))
        })}
        {hoveredFeature && (
          <CustomOverlayMap position={featureLabelPoint(hoveredFeature)} yAnchor={1.1}>
            <DistrictTooltip feature={hoveredFeature} region={hoveredRegion} />
          </CustomOverlayMap>
        )}
      </KakaoMap>
      <RiskLegend />
    </div>
  )
}

function DistrictTooltip({ feature, region }: { feature: BusanDistrictFeature; region: RiskRegion | undefined }) {
  return (
    <div className="rounded-lg border border-brand-border bg-white px-3 py-2 text-xs shadow-md">
      <p className="font-semibold text-brand-ink">{feature.properties.name}</p>
      {region ? (
        <>
          <p className="mt-0.5 text-gray-600">평균 위험도 {(region.avg_risk_probability * 100).toFixed(0)}%</p>
          <p className="text-gray-400">표본 {region.n}명</p>
        </>
      ) : (
        <p className="mt-0.5 text-gray-400">표본 데이터 없음</p>
      )}
    </div>
  )
}

function RiskLegend() {
  return (
    <div className="flex items-center gap-4 rounded-lg border border-brand-border bg-white p-3 text-xs text-gray-600">
      <span>위험도</span>
      <div className="flex items-center gap-1">
        <span>낮음</span>
        <div
          className="h-3 w-32 rounded"
          style={{ background: `linear-gradient(to right, ${riskColor(0)}, ${riskColor(1)})` }}
        />
        <span>높음</span>
      </div>
      <div className="flex items-center gap-1">
        <span className="inline-block h-3 w-3 rounded" style={{ backgroundColor: NO_DATA_COLOR }} />
        <span>표본 없음</span>
      </div>
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
