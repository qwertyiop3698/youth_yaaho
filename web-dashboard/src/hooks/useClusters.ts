import { useQuery } from '@tanstack/react-query'
import { apiGet } from '../api/client'
import type { ClustersResponse } from '../api/types'
import { useAuthStore } from '../store/authStore'

export function useClusters() {
  const apiKey = useAuthStore((state) => state.apiKey)

  return useQuery({
    queryKey: ['admin', 'clusters'],
    queryFn: () => apiGet<ClustersResponse>('/api/v1/admin/clusters'),
    enabled: Boolean(apiKey),
  })
}
