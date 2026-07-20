import { useQuery } from '@tanstack/react-query'
import { apiGet } from '../api/client'
import type { PolicyFeedbackSummary } from '../api/types'
import { useAuthStore } from '../store/authStore'

export function usePolicyFeedback() {
  const apiKey = useAuthStore((state) => state.apiKey)
  return useQuery({
    queryKey: ['admin', 'policy-feedback-summaries'],
    queryFn: () => apiGet<PolicyFeedbackSummary[]>('/api/v1/admin/policy-feedback-summaries'),
    enabled: Boolean(apiKey),
  })
}
