import { useQuery } from '@tanstack/react-query'
import { apiDownload, apiGet } from '../api/client'
import type { PolicyDemandPriority, PolicyDemandSummary } from '../api/types'
import { useAuthStore } from '../store/authStore'

export function usePolicyDemand() {
  const apiKey = useAuthStore((state) => state.apiKey)
  const summary = useQuery({ queryKey: ['admin', 'policy-demand-summary'], queryFn: () => apiGet<PolicyDemandSummary>('/api/v1/admin/policy-demand-summary'), enabled: Boolean(apiKey) })
  const priorities = useQuery({ queryKey: ['admin', 'policy-demand-priorities'], queryFn: () => apiGet<PolicyDemandPriority[]>('/api/v1/admin/policy-demand-priorities'), enabled: Boolean(apiKey) })
  return { summary, priorities }
}
export async function downloadPolicyDemand(format: 'csv' | 'json') {
  const blob = await apiDownload(`/api/v1/admin/policy-demand/export?format=${format}`)
  const url = URL.createObjectURL(blob); const link = document.createElement('a')
  link.href = url; link.download = `policy-demand.${format}`; link.click(); URL.revokeObjectURL(url)
}

