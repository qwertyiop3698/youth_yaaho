import { useQuery } from '@tanstack/react-query'
import { apiGet } from '../api/client'
import type { RiskTrajectoryOutlookResponse } from '../api/types'
import { useAuthStore } from '../store/authStore'

export function useRiskTrajectoryOutlook() {
  const apiKey = useAuthStore((state) => state.apiKey)

  return useQuery({
    queryKey: ['admin', 'risk-trajectory-outlook'],
    queryFn: () => apiGet<RiskTrajectoryOutlookResponse>('/api/v1/admin/risk-trajectory-outlook'),
    enabled: Boolean(apiKey),
    staleTime: Infinity, // Layer3 배치 산출물 기반
  })
}
