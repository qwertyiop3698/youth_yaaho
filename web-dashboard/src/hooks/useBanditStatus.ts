import { useQuery } from '@tanstack/react-query'
import { apiGet } from '../api/client'
import type { BanditStatusResponse } from '../api/types'
import { useAuthStore } from '../store/authStore'

export function useBanditStatus() {
  const apiKey = useAuthStore((state) => state.apiKey)

  return useQuery({
    queryKey: ['admin', 'bandit-status'],
    queryFn: () => apiGet<BanditStatusResponse>('/api/v1/admin/bandit-status'),
    enabled: Boolean(apiKey),
  })
}
