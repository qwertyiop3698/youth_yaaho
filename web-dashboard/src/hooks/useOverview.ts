import { useQuery } from '@tanstack/react-query'
import { apiGet } from '../api/client'
import type { OverviewResponse } from '../api/types'
import { useAuthStore } from '../store/authStore'

export function useOverview() {
  const apiKey = useAuthStore((state) => state.apiKey)

  return useQuery({
    queryKey: ['admin', 'overview'],
    queryFn: () => apiGet<OverviewResponse>('/api/v1/admin/overview'),
    enabled: Boolean(apiKey), // API 키가 없으면 아예 요청하지 않음(401만 반복해서 받지 않도록)
  })
}
