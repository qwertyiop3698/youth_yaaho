import { useMemo, useState } from 'react'
import { Map as KakaoMap, Polygon, CustomOverlayMap, useKakaoLoader } from 'react-kakao-maps-sdk'
import { useRiskMap } from '../../hooks/useRiskMap'
import { useBusanGeoJson } from '../../hooks/useBusanGeoJson'
import { QueryState, NotReadyBanner } from '../../components/QueryState'
import type { RiskMapLevel, RiskRegion, SpatialStats } from '../../api/types'
import { featureOuterRings, featureLabelPoint, riskColor, NO_DATA_COLOR } from '../../utils/geo'
import type { BusanDistrictFeature } from '../../utils/geo'

const LEVELS: { value: RiskMapLevel; label: string }[] = [
  { value: 'sigungu', label: '시군구' },
  { value: 'dong', label: '행정동' },
]

export type MetricMode = 'absolute' | 'normalized'

const METRIC_MODES: { value: MetricMode; label: string }[] = [
  { value: 'absolute', label: '절대값' },
  { value: 'normalized', label: '인구 1천명당' },
]

const BUSAN_CENTER = { lat: 35.1796, lng: 129.0756 }
const KAKAO_APP_KEY = import.meta.env.VITE_KAKAO_MAP_APP_KEY

// 정규화 지표(high_risk_per_1000_population)를 riskColor()가 기대하는 0~1 범위로
// 맞추기 위한 지역간 min-max. 절대 위험도(avg_risk_probability)는 이미 0~1이라
// 별도 정규화가 필요 없지만, 인구 1천명당 위험군 수는 상한이 없는 비율이라
// 지도에 표시된 지역들 안에서 상대적으로 색을 매겨야 한다.
function computeNormalizedRange(regions: RiskRegion[]): { min: number; max: number } | null {
  const values = regions
    .map((r) => r.high_risk_per_1000_population)
    .filter((v): v is number => v !== null)
  if (values.length === 0) return null
  return { min: Math.min(...values), max: Math.max(...values) }
}

function metricColorValue(
  region: RiskRegion,
  mode: MetricMode,
  normalizedRange: { min: number; max: number } | null,
): number | null {
  if (mode === 'absolute') return region.avg_risk_probability
  if (region.high_risk_per_1000_population === null || !normalizedRange) return null
  const { min, max } = normalizedRange
  if (max === min) return 0.5
  return (region.high_risk_per_1000_population - min) / (max - min)
}

// 2026-07-25 DIVE 2026 이종결합 작업3: "역전세 위험" = 전세가 하락(jeonse_price_change_rate<0)
// + 위험군 밀집(그 지역의 high_risk_per_1000_population이 지도에 표시된 지역들의
// 중앙값보다 높음)의 교차. 절대적인 밀집 기준값이 따로 정의돼 있지 않아, 지금
// 화면에 보이는 지역들 사이의 상대적 중앙값을 기준으로 삼는다(정규화 지표와 같은
// 이유 - 절대 상한이 없는 비율이라 상대 비교가 더 의미 있음).
function computeHighRiskDensityMedian(regions: RiskRegion[]): number | null {
  const values = regions
    .map((r) => r.high_risk_per_1000_population)
    .filter((v): v is number => v !== null)
    .sort((a, b) => a - b)
  if (values.length === 0) return null
  const mid = Math.floor(values.length / 2)
  return values.length % 2 === 0 ? (values[mid - 1] + values[mid]) / 2 : values[mid]
}

function isReverseJeonseRisk(region: RiskRegion, densityMedian: number | null): boolean {
  if (region.jeonse_price_change_rate === null || region.jeonse_price_change_rate >= 0) return false
  if (densityMedian === null || region.high_risk_per_1000_population === null) return false
  return region.high_risk_per_1000_population > densityMedian
}

export function RiskMap() {
  const [level, setLevel] = useState<RiskMapLevel>('sigungu')
  const [metricMode, setMetricMode] = useState<MetricMode>('absolute')
  const [showReverseJeonseLayer, setShowReverseJeonseLayer] = useState(false)
  const { data, isLoading, isError, error } = useRiskMap(level)

  const populationAvailable = data && data.ready ? data.population_reference_available : false
  const jeonseTrendAvailable = data && data.ready ? data.jeonse_trend_available : false

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-semibold">지역 위험지도</h2>
        <div className="flex flex-wrap gap-3">
          <div
            className="flex gap-1 rounded-lg border border-brand-border bg-white p-1"
            role="group"
            aria-label="위험지도 표시 지표"
          >
            {METRIC_MODES.map((m) => {
              const disabled = m.value === 'normalized' && !populationAvailable
              return (
                <button
                  key={m.value}
                  type="button"
                  onClick={() => setMetricMode(m.value)}
                  disabled={disabled}
                  title={disabled ? '생활인구 참조데이터가 없어 정규화 지표를 쓸 수 없습니다.' : undefined}
                  className={`rounded px-3 py-1 text-sm transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-blue disabled:cursor-not-allowed disabled:opacity-40 ${
                    metricMode === m.value
                      ? 'bg-brand-blue text-white'
                      : 'text-gray-600 hover:bg-brand-surface-muted'
                  }`}
                >
                  {m.label}
                </button>
              )
            })}
          </div>
          <div className="flex gap-1 rounded-lg border border-brand-border bg-white p-1">
            {LEVELS.map((l) => (
              <button
                key={l.value}
                type="button"
                onClick={() => setLevel(l.value)}
                className={`rounded px-3 py-1 text-sm transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-blue ${
                  level === l.value ? 'bg-brand-blue text-white' : 'text-gray-600 hover:bg-brand-surface-muted'
                }`}
              >
                {l.label}
              </button>
            ))}
          </div>
          <label
            className={`flex items-center gap-2 rounded-lg border border-brand-border bg-white px-3 py-1 text-sm ${
              jeonseTrendAvailable ? 'text-gray-600' : 'cursor-not-allowed text-gray-300'
            }`}
            title={
              jeonseTrendAvailable
                ? '전세가 하락 + 위험군 밀집이 겹치는 지역을 강조합니다.'
                : '전세가 변동 참조데이터가 없어 이 레이어를 쓸 수 없습니다.'
            }
          >
            <input
              type="checkbox"
              checked={showReverseJeonseLayer}
              disabled={!jeonseTrendAvailable}
              onChange={(e) => setShowReverseJeonseLayer(e.target.checked)}
            />
            역전세 위험 레이어
          </label>
        </div>
      </div>

      <QueryState isLoading={isLoading} isError={isError} error={error}>
        {data && data.ready ? (
          level === 'sigungu' ? (
            <div className="flex flex-col gap-3">
              <SpatialStatsBanner stats={data.spatial_stats} />
              {metricMode === 'normalized' && data.population_data_note && (
                <PopulationDataNoteBanner note={data.population_data_note} />
              )}
              <RiskChoroplethMap
                regions={data.regions}
                metricMode={metricMode}
                showReverseJeonseLayer={showReverseJeonseLayer}
              />
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              <div className="rounded-lg border border-blue-200 bg-blue-50 p-3 text-sm text-blue-800">
                행정동 단위는 아직 경계 데이터가 없어 카드 그리드로 표시합니다. 지도로 보려면 시군구
                단위를 선택해주세요.
              </div>
              {metricMode === 'normalized' && data.population_data_note && (
                <PopulationDataNoteBanner note={data.population_data_note} />
              )}
              <RiskMapGrid
                regions={data.regions}
                metricMode={metricMode}
                showReverseJeonseLayer={showReverseJeonseLayer}
              />
            </div>
          )
        ) : data ? (
          <NotReadyBanner reason={data.reason} />
        ) : null}
      </QueryState>
    </div>
  )
}

function PopulationDataNoteBanner({ note }: { note: string }) {
  return (
    <div className="rounded-lg border border-yellow-200 bg-yellow-50 p-3 text-sm text-yellow-800">
      인구 1천명당 지표 안내: {note}
    </div>
  )
}

function RiskChoroplethMap({
  regions,
  metricMode,
  showReverseJeonseLayer,
}: {
  regions: RiskRegion[]
  metricMode: MetricMode
  showReverseJeonseLayer: boolean
}) {
  const [kakaoLoading, kakaoError] = useKakaoLoader({ appkey: KAKAO_APP_KEY ?? '' })
  const { data: geojson, isLoading: geoLoading, isError: geoError } = useBusanGeoJson()
  const [hoveredCode, setHoveredCode] = useState<string | null>(null)

  const regionByCode = useMemo(() => {
    const map = new globalThis.Map<string, RiskRegion>()
    for (const region of regions) map.set(region.region_code, region)
    return map
  }, [regions])

  const normalizedRange = useMemo(() => computeNormalizedRange(regions), [regions])
  const densityMedian = useMemo(() => computeHighRiskDensityMedian(regions), [regions])

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
          const colorValue = region ? metricColorValue(region, metricMode, normalizedRange) : null
          const color = colorValue !== null ? riskColor(colorValue) : NO_DATA_COLOR
          // LISA는 avg_risk_probability(절대값 지표)를 검정한 결과라 정규화 모드에서는
          // 테두리 강조를 보여주지 않는다(다른 지표를 보면서 이 통계 결과를 겹쳐 보이면
          // 오해 소지가 있음).
          const hotspotClassification = metricMode === 'absolute' ? region?.hotspot_classification : undefined
          const isHotspot = hotspotClassification === 'hotspot'
          const isColdspot = hotspotClassification === 'coldspot'
          return featureOuterRings(feature).map((path, i) => (
            <Polygon
              key={`${feature.properties.region_code}-${i}`}
              path={path}
              fillColor={color}
              fillOpacity={colorValue !== null ? 0.75 : 0.35}
              strokeColor={isHotspot ? '#dc2626' : isColdspot ? '#2563eb' : '#FFFFFF'}
              strokeWeight={isHotspot || isColdspot ? 4 : 2}
              strokeOpacity={0.9}
              onMouseover={() => setHoveredCode(feature.properties.region_code)}
              onMouseout={() =>
                setHoveredCode((prev) => (prev === feature.properties.region_code ? null : prev))
              }
            />
          ))
        })}
        {showReverseJeonseLayer &&
          geojson.features
            .filter((feature) => {
              const region = regionByCode.get(feature.properties.region_code)
              return region && isReverseJeonseRisk(region, densityMedian)
            })
            .map((feature) => (
              <CustomOverlayMap
                key={`reverse-jeonse-${feature.properties.region_code}`}
                position={featureLabelPoint(feature)}
                yAnchor={0.5}
              >
                <ReverseJeonseMarker />
              </CustomOverlayMap>
            ))}
        {hoveredFeature && (
          <CustomOverlayMap position={featureLabelPoint(hoveredFeature)} yAnchor={1.1}>
            <DistrictTooltip
              feature={hoveredFeature}
              region={hoveredRegion}
              metricMode={metricMode}
              densityMedian={showReverseJeonseLayer ? densityMedian : undefined}
            />
          </CustomOverlayMap>
        )}
      </KakaoMap>
      <RiskLegend metricMode={metricMode} showReverseJeonseLayer={showReverseJeonseLayer} />
    </div>
  )
}

const LISA_LABELS: Record<string, string> = {
  HH: 'hotspot (고위험 군집)',
  LL: 'coldspot (저위험 군집)',
  HL: '고위험 이상치(주변은 낮음)',
  LH: '저위험 이상치(주변은 높음)',
}

// hotspot_classification은 LISA quadrant + 통계적 유의성(p<0.05)까지 반영한 배지다
// (lisa_quadrant만 보면 유의하지 않은 HH도 "hotspot처럼" 보일 수 있어 배지로 구분).
function HotspotBadge({ classification }: { classification: RiskRegion['hotspot_classification'] }) {
  if (classification === 'hotspot') {
    return (
      <span className="mt-1 inline-flex items-center gap-1 rounded-full bg-red-100 px-2 py-0.5 text-[10px] font-semibold text-red-700">
        <span className="inline-block h-1.5 w-1.5 rounded-full bg-red-600" />
        hotspot (유의)
      </span>
    )
  }
  if (classification === 'coldspot') {
    return (
      <span className="mt-1 inline-flex items-center gap-1 rounded-full bg-blue-100 px-2 py-0.5 text-[10px] font-semibold text-blue-700">
        <span className="inline-block h-1.5 w-1.5 rounded-full bg-blue-600" />
        coldspot (유의)
      </span>
    )
  }
  return null
}

// 지도 위 마커(호버 없이 항상 보임) - 전세가 하락 + 위험군 밀집 교차 지역을 표시.
function ReverseJeonseMarker() {
  return (
    <div
      className="flex h-5 w-5 items-center justify-center rounded-full border-2 border-white bg-purple-600 shadow-md"
      title="역전세 위험 교차 지역(전세가 하락 + 위험군 밀집)"
    >
      <span className="h-1.5 w-1.5 rounded-full bg-white" />
    </div>
  )
}

function ReverseJeonseBadge() {
  return (
    <span className="mt-1 inline-flex items-center gap-1 rounded-full bg-purple-100 px-2 py-0.5 text-[10px] font-semibold text-purple-700">
      <span className="inline-block h-1.5 w-1.5 rounded-full bg-purple-600" />
      역전세 위험 교차
    </span>
  )
}

function DistrictTooltip({
  feature,
  region,
  metricMode,
  densityMedian,
}: {
  feature: BusanDistrictFeature
  region: RiskRegion | undefined
  metricMode: MetricMode
  densityMedian?: number | null
}) {
  return (
    <div className="rounded-lg border border-brand-border bg-white px-3 py-2 text-xs shadow-md">
      <p className="font-semibold text-brand-ink">{feature.properties.name}</p>
      {region ? (
        <>
          {metricMode === 'absolute' ? (
            <>
              <p className="mt-0.5 text-gray-600">평균 프록시 점수 {(region.avg_risk_probability * 100).toFixed(0)}점</p>
              <p className="text-gray-400">표본 {region.n}명</p>
              {region.lisa_quadrant && (
                <p className="mt-0.5 text-gray-600">{LISA_LABELS[region.lisa_quadrant] ?? region.lisa_quadrant}</p>
              )}
              <HotspotBadge classification={region.hotspot_classification} />
            </>
          ) : region.high_risk_per_1000_population !== null ? (
            <>
              <p className="mt-0.5 text-gray-600">
                인구 1천명당 위험군 {region.high_risk_per_1000_population.toFixed(2)}명
              </p>
              <p className="text-gray-400">위험군 {region.n_high_risk}명 / 참조인구 {region.population_reference?.toLocaleString('ko-KR')}명</p>
            </>
          ) : (
            <p className="mt-0.5 text-gray-400">생활인구 매칭 실패 - 정규화 불가</p>
          )}
          {region.jeonse_price_change_rate !== null && (
            <p className="mt-0.5 text-gray-400">
              전세가변동률 {(region.jeonse_price_change_rate * 100).toFixed(1)}%
              {region.renewal_deposit_change_rate !== null &&
                ` · 갱신보증금변동률 ${(region.renewal_deposit_change_rate * 100).toFixed(1)}%`}
            </p>
          )}
          {densityMedian !== undefined && isReverseJeonseRisk(region, densityMedian) && <ReverseJeonseBadge />}
        </>
      ) : (
        <p className="mt-0.5 text-gray-400">표본 데이터 없음</p>
      )}
    </div>
  )
}

function SpatialStatsBanner({ stats }: { stats: SpatialStats | null }) {
  if (!stats || stats.skipped || stats.morans_i === undefined || stats.p_value === undefined) {
    return null
  }

  const significant = stats.is_significant
  const bg = significant ? 'border-red-200 bg-red-50 text-red-800' : 'border-gray-200 bg-gray-50 text-gray-600'

  return (
    <div className={`rounded-lg border p-3 text-sm ${bg}`}>
      <span className="font-medium">Moran&apos;s I = {stats.morans_i.toFixed(3)}</span>{' '}
      (p = {stats.p_value.toFixed(3)}, {stats.n_permutations?.toLocaleString('ko-KR')}회 순열검정) —{' '}
      {significant
        ? '통계적으로 유의미한 공간적 군집이 있습니다. 빨간 테두리는 hotspot(고위험 군집), 파란 테두리는 coldspot(저위험 군집) 지역입니다.'
        : '통계적으로 유의미한 공간적 군집이 발견되지 않았습니다(우연한 분포와 구분되지 않음).'}
    </div>
  )
}

function RiskLegend({
  metricMode,
  showReverseJeonseLayer,
}: {
  metricMode: MetricMode
  showReverseJeonseLayer: boolean
}) {
  return (
    <div className="flex flex-wrap items-center gap-4 rounded-lg border border-brand-border bg-white p-3 text-xs text-gray-600">
      <span>{metricMode === 'absolute' ? '프록시 점수' : '인구 1천명당 위험군'}</span>
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
        <span>{metricMode === 'absolute' ? '표본 없음' : '생활인구 매칭 실패'}</span>
      </div>
      {metricMode === 'absolute' && (
        <>
          <div className="flex items-center gap-1">
            <span className="inline-block h-3 w-3 rounded border-2 border-red-600" />
            <span>hotspot 테두리</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="inline-block h-3 w-3 rounded border-2 border-blue-600" />
            <span>coldspot 테두리</span>
          </div>
        </>
      )}
      {showReverseJeonseLayer && (
        <div className="flex items-center gap-1">
          <span className="inline-block h-3 w-3 rounded-full bg-purple-600" />
          <span>역전세 위험 교차(전세가 하락 + 위험군 밀집)</span>
        </div>
      )}
    </div>
  )
}

function RiskMapGrid({
  regions,
  metricMode,
  showReverseJeonseLayer,
}: {
  regions: RiskRegion[]
  metricMode: MetricMode
  showReverseJeonseLayer: boolean
}) {
  if (regions.length === 0) {
    return <p className="text-sm text-gray-400">표시할 지역 데이터가 없습니다.</p>
  }

  const normalizedRange = computeNormalizedRange(regions)
  const densityMedian = computeHighRiskDensityMedian(regions)
  const sorted = [...regions].sort((a, b) => {
    const metricA = metricMode === 'absolute' ? a.avg_risk_probability : (a.high_risk_per_1000_population ?? -1)
    const metricB = metricMode === 'absolute' ? b.avg_risk_probability : (b.high_risk_per_1000_population ?? -1)
    return metricB - metricA
  })

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
      {sorted.map((region) => {
        const colorValue = metricColorValue(region, metricMode, normalizedRange)
        const backgroundColor = colorValue !== null ? riskColor(colorValue) : NO_DATA_COLOR
        return (
          <div
            key={region.region_code}
            className="relative rounded-lg p-4 text-white shadow-sm"
            style={{ backgroundColor, textShadow: '0 1px 2px rgba(0,0,0,0.55)' }}
          >
            {showReverseJeonseLayer && isReverseJeonseRisk(region, densityMedian) && (
              <span
                className="absolute right-2 top-2 h-3 w-3 rounded-full border-2 border-white bg-purple-600"
                title="역전세 위험 교차 지역"
              />
            )}
            <p className="text-xs opacity-90">{region.region_code}</p>
            {metricMode === 'absolute' ? (
              <>
                <p className="mt-1 text-2xl font-semibold">{(region.avg_risk_probability * 100).toFixed(0)}점</p>
                <p className="mt-1 text-xs opacity-90">표본 {region.n}명</p>
                <HotspotBadge classification={region.hotspot_classification} />
              </>
            ) : region.high_risk_per_1000_population !== null ? (
              <>
                <p className="mt-1 text-2xl font-semibold">{region.high_risk_per_1000_population.toFixed(2)}명</p>
                <p className="mt-1 text-xs opacity-90">위험군 {region.n_high_risk}명 / 참조인구 {region.population_reference?.toLocaleString('ko-KR')}명</p>
              </>
            ) : (
              <p className="mt-1 text-sm font-medium opacity-90">생활인구 매칭 실패</p>
            )}
          </div>
        )
      })}
    </div>
  )
}
