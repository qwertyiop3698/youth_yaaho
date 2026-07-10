import { useQuery } from '@tanstack/react-query'
import { apiGet } from '../api/client'
import type { PolicyCatalogResponse } from '../api/types'
import { useAuthStore } from '../store/authStore'

export function usePolicyCatalog() {
  const apiKey = useAuthStore((state) => state.apiKey)

  return useQuery({
    queryKey: ['admin', 'policy-catalog'],
    queryFn: () => apiGet<PolicyCatalogResponse>('/api/v1/admin/policy-catalog'),
    enabled: Boolean(apiKey),
    staleTime: Infinity, // 카탈로그는 세션 중 거의 안 바뀜 - 슬라이더 재계산마다 다시 받을 필요 없음
  })
}
