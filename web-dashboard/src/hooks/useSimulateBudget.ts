import { useQuery } from '@tanstack/react-query'
import { apiPost } from '../api/client'
import type { SimulateBudgetResult } from '../api/types'
import { useAuthStore } from '../store/authStore'

export function useSimulateBudget(policyBudgets: Record<string, number>, enabled: boolean) {
  const apiKey = useAuthStore((state) => state.apiKey)

  return useQuery({
    // 예산 조합 자체를 키에 포함시켜서, 슬라이더로 이전에 봤던 조합으로 돌아오면
    // 재계산 없이 캐시된 결과를 바로 보여준다.
    queryKey: ['admin', 'simulate-budget', policyBudgets],
    queryFn: () => apiPost<SimulateBudgetResult>('/api/v1/admin/simulate-budget', { policy_budgets: policyBudgets }),
    enabled: Boolean(apiKey) && enabled,
  })
}
