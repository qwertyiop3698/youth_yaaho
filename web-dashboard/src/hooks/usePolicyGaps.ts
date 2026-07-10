import { useQuery } from '@tanstack/react-query'
import { apiGet } from '../api/client'
import type { PolicyGapsResponse } from '../api/types'
import { useAuthStore } from '../store/authStore'

export function usePolicyGaps(riskThreshold: number) {
  const apiKey = useAuthStore((state) => state.apiKey)

  return useQuery({
    queryKey: ['admin', 'policy-gaps', riskThreshold],
    queryFn: () => apiGet<PolicyGapsResponse>(`/api/v1/admin/policy-gaps?risk_threshold=${riskThreshold}`),
    enabled: Boolean(apiKey),
  })
}
