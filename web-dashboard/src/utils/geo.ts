// 부산 16개 구/군 GeoJSON 경계 데이터를 다루기 위한 최소 유틸.
// 지오메트리 자체의 투영/렌더링은 Kakao Map SDK(react-kakao-maps-sdk)가 담당하고,
// 여기서는 GeoJSON 좌표를 Kakao LatLng 배열로 바꾸고 라벨 앵커 포인트를 구하는
// 순수 데이터 변환만 다룬다.

export interface BusanDistrictFeature {
  type: 'Feature'
  properties: { region_code: string; name: string; name_eng: string }
  geometry: { type: 'Polygon' | 'MultiPolygon'; coordinates: unknown }
}

export interface BusanDistrictsGeoJson {
  type: 'FeatureCollection'
  features: BusanDistrictFeature[]
}

type LonLat = [number, number]
type Ring = LonLat[]
type Polygon = Ring[]

export interface LatLng {
  lat: number
  lng: number
}

function polygonsOf(geometry: BusanDistrictFeature['geometry']): Polygon[] {
  if (geometry.type === 'Polygon') return [geometry.coordinates as Polygon]
  return geometry.coordinates as Polygon[]
}

// 각 폴리곤(섬 포함)의 바깥 링만 사용한다 - 부산 구/군 경계에는 구멍(hole)이 없다.
// MultiPolygon인 경우(기장군 등 부속 도서 포함) 폴리곤마다 별도 Kakao Polygon으로 그린다.
export function featureOuterRings(feature: BusanDistrictFeature): LatLng[][] {
  return polygonsOf(feature.geometry).map((polygon) =>
    polygon[0].map(([lon, lat]) => ({ lat, lng: lon })),
  )
}

// 라벨/툴팁 앵커 - 정점이 가장 많은(=가장 큰) 폴리곤의 정점 산술평균.
// 정확한 centroid는 아니지만 구/군 라벨 배치용으로는 충분하고, 전체 폴리곤 평균과
// 달리 부속 도서 때문에 라벨이 바다 위로 튀는 문제를 피할 수 있다.
export function featureLabelPoint(feature: BusanDistrictFeature): LatLng {
  const rings = featureOuterRings(feature)
  const biggest = rings.reduce((a, b) => (b.length > a.length ? b : a))
  const sum = biggest.reduce((acc, p) => ({ lat: acc.lat + p.lat, lng: acc.lng + p.lng }), { lat: 0, lng: 0 })
  return { lat: sum.lat / biggest.length, lng: sum.lng / biggest.length }
}

// 위험도(0~1)를 초록(안전) -> 빨강(위험) 2색으로 보간. 데이터 없는 지역은 회색.
export function riskColor(risk: number): string {
  const clamped = Math.min(1, Math.max(0, risk))
  const r = Math.round(34 + (220 - 34) * clamped)
  const g = Math.round(150 + (38 - 150) * clamped)
  const b = Math.round(94 + (38 - 94) * clamped)
  return `rgb(${r}, ${g}, ${b})`
}

export const NO_DATA_COLOR = '#CBD1E0'
