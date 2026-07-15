import { useQuery } from '@tanstack/react-query'
import type { BusanDistrictsGeoJson } from '../utils/geo'

// public/busan_districts.geojson: southkorea/southkorea-maps(KOSTAT 2018, MIT)
// 시군구 경계 중 부산 16개 구/군만 추출하고 region_code를 실제 5자리 SGG 코드로
// 매핑해둔 정적 파일. 서버 없이 정적 자산이라 React Query로 한 번만 불러와 캐싱한다.
export function useBusanGeoJson() {
  return useQuery({
    queryKey: ['static', 'busan-districts-geojson'],
    queryFn: async () => {
      const res = await fetch('/busan_districts.geojson')
      if (!res.ok) throw new Error('부산 행정구역 경계 데이터를 불러오지 못했습니다.')
      return (await res.json()) as BusanDistrictsGeoJson
    },
    staleTime: Infinity,
  })
}
