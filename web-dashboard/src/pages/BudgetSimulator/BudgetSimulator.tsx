import { useEffect, useState } from 'react'
import { usePolicyCatalog } from '../../hooks/usePolicyCatalog'
import { useSimulateBudget } from '../../hooks/useSimulateBudget'
import { useDebouncedValue } from '../../hooks/useDebouncedValue'
import { QueryState } from '../../components/QueryState'
import { StatCard } from '../../components/StatCard'
import { useAuthStore } from '../../store/authStore'
import { ApiError } from '../../api/client'
import type { SimulateBudgetResult } from '../../api/types'

const BUDGET_STEP = 10_000_000 // 1천만원 단위

function formatEok(krw: number): string {
  return `${(krw / 100_000_000).toFixed(1)}억원`
}

export function BudgetSimulator() {
  const apiKey = useAuthStore((state) => state.apiKey)
  const catalogQuery = usePolicyCatalog()
  const [budgets, setBudgets] = useState<Record<string, number> | null>(null)

  // 카탈로그가 처음 도착했을 때만 슬라이더 기본값을 채운다(그 뒤엔 사용자가 조작한
  // 값을 유지 - "초기화" 버튼을 눌러야만 기본값으로 되돌아간다).
  useEffect(() => {
    if (catalogQuery.data?.ready && budgets === null) {
      const initial: Record<string, number> = {}
      for (const policy of catalogQuery.data.policies) {
        initial[policy.name] = policy.budget_cap
      }
      setBudgets(initial)
    }
  }, [catalogQuery.data, budgets])

  const debouncedBudgets = useDebouncedValue(budgets, 400)
  const simulateQuery = useSimulateBudget(debouncedBudgets ?? {}, debouncedBudgets !== null)

  if (!apiKey) {
    return (
      <div className="rounded-lg border border-yellow-200 bg-yellow-50 p-4 text-sm text-yellow-800">
        먼저 오른쪽 위에서 admin API 키를 입력해야 데이터를 볼 수 있습니다.
      </div>
    )
  }

  const resetToDefaults = () => {
    if (!catalogQuery.data?.ready) return
    const initial: Record<string, number> = {}
    for (const policy of catalogQuery.data.policies) {
      initial[policy.name] = policy.budget_cap
    }
    setBudgets(initial)
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold">예산 시뮬레이터</h2>
          <p className="mt-1 text-sm text-gray-500">
            정책별 예산 슬라이더를 조정하면 LP가 재계산되어 커버율이 갱신됩니다.
          </p>
        </div>
        <button
          type="button"
          onClick={resetToDefaults}
          disabled={!catalogQuery.data?.ready}
          className="rounded border border-gray-300 px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 disabled:opacity-50"
        >
          기본값으로 초기화
        </button>
      </div>

      <QueryState isLoading={catalogQuery.isLoading} isError={catalogQuery.isError} error={catalogQuery.error}>
        {catalogQuery.data?.ready && budgets ? (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <div className="flex flex-col gap-4 rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
              <h3 className="text-sm font-medium text-gray-500">정책별 예산 배정 상한</h3>
              {catalogQuery.data.policies.map((policy) => (
                <div key={policy.name}>
                  <label className="flex items-center justify-between text-sm text-gray-700">
                    <span>{policy.name}</span>
                    <span className="font-medium text-gray-900">{formatEok(budgets[policy.name] ?? 0)}</span>
                  </label>
                  <input
                    type="range"
                    min={0}
                    max={policy.budget_cap * 2}
                    step={BUDGET_STEP}
                    value={budgets[policy.name] ?? 0}
                    onChange={(e) =>
                      setBudgets((prev) => ({ ...(prev ?? {}), [policy.name]: Number(e.target.value) }))
                    }
                    className="mt-1 w-full"
                  />
                </div>
              ))}
            </div>

            <SimulationResult
              isLoading={simulateQuery.isLoading}
              isError={simulateQuery.isError}
              error={simulateQuery.error}
              data={simulateQuery.data}
            />
          </div>
        ) : null}
      </QueryState>
    </div>
  )
}

interface SimulationResultProps {
  isLoading: boolean
  isError: boolean
  error: unknown
  data: SimulateBudgetResult | undefined
}

function SimulationResult({ isLoading, isError, error, data }: SimulationResultProps) {
  if (isLoading) {
    return <p className="text-sm text-gray-500">계산 중...</p>
  }
  if (isError) {
    const message = error instanceof ApiError ? error.message : '계산 중 오류가 발생했습니다.'
    return <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">{message}</div>
  }
  if (!data) {
    return null
  }
  if (data.skipped) {
    return (
      <div className="rounded-lg border border-gray-200 bg-white p-4 text-sm text-gray-600">
        계산할 수 없습니다: {data.reason}
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <StatCard
        label="전체 커버율"
        value={data.coverage_rate !== null ? `${(data.coverage_rate * 100).toFixed(1)}%` : '—'}
        hint="배정 대상자 중 실제로 정책이 배정된 비율"
      />
      <StatCard
        label="검증된 자격조건만 반영한 커버율"
        value={
          data.coverage_rate_verified_only !== null
            ? `${(data.coverage_rate_verified_only * 100).toFixed(1)}%`
            : '—'
        }
        hint="eligibility_confidence=verified인 규칙만 반영(코드북 미확정 잠정치는 제외한 보수적 추정)"
      />
    </div>
  )
}
