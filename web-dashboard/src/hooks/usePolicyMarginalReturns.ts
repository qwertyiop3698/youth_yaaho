import { useQuery } from '@tanstack/react-query'
import { apiGet } from '../api/client'
import type { PolicyMarginalReturnsResponse } from '../api/types'
import { useAuthStore } from '../store/authStore'

export function usePolicyMarginalReturns() {
  const apiKey = useAuthStore((state) => state.apiKey)

  return useQuery({
    queryKey: ['admin', 'policy-marginal-returns'],
    queryFn: () => apiGet<PolicyMarginalReturnsResponse>('/api/v1/admin/policy-marginal-returns'),
    enabled: Boolean(apiKey),
    staleTime: Infinity, // Layer3 배치 산출물 기반 - 슬라이더 조작으로 바뀌지 않음
  })
}
