import { useQuery } from '@tanstack/react-query'
import { apiGet } from '../api/client'
import type { RiskMapLevel, RiskMapResponse } from '../api/types'
import { useAuthStore } from '../store/authStore'

export function useRiskMap(level: RiskMapLevel) {
  const apiKey = useAuthStore((state) => state.apiKey)

  return useQuery({
    queryKey: ['admin', 'risk-map', level],
    queryFn: () => apiGet<RiskMapResponse>(`/api/v1/admin/risk-map?level=${level}`),
    enabled: Boolean(apiKey),
  })
}
