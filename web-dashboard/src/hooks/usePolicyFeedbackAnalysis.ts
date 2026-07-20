import { useQuery } from '@tanstack/react-query'
import { apiDownload, apiGet } from '../api/client'
import type { PolicyFeedbackAnalysis } from '../api/types'
import { useAuthStore } from '../store/authStore'

export function usePolicyFeedbackAnalysis() {
  const apiKey = useAuthStore((state) => state.apiKey)
  return useQuery({
    queryKey: ['admin', 'policy-feedback-priorities'],
    queryFn: () => apiGet<PolicyFeedbackAnalysis[]>('/api/v1/admin/policy-feedback-priorities'),
    enabled: Boolean(apiKey),
  })
}

export async function downloadPolicyAnalysis(format: 'csv' | 'json') {
  const blob = await apiDownload(`/api/v1/admin/policy-feedback-analysis/export?format=${format}`)
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `policy-feedback-analysis.${format}`
  link.click()
  URL.revokeObjectURL(url)
}

