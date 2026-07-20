import { useEffect, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { usePolicyCatalog } from '../../hooks/usePolicyCatalog'
import { useSimulateBudget } from '../../hooks/useSimulateBudget'
import { usePolicyMarginalReturns } from '../../hooks/usePolicyMarginalReturns'
import { useDebouncedValue } from '../../hooks/useDebouncedValue'
import { QueryState, NotReadyBanner } from '../../components/QueryState'
import { StatCard } from '../../components/StatCard'
import { useAuthStore } from '../../store/authStore'
import { ApiError } from '../../api/client'
import type { SimulateBudgetResult, PolicyMarginalReturnsResponse } from '../../api/types'

const BUDGET_STEP = 10_000_000 // 1천만원 단위

function formatEok(krw: number): string {
  return `${(krw / 100_000_000).toFixed(1)}억원`
}

export function BudgetSimulator() {
  const apiKey = useAuthStore((state) => state.apiKey)
  const catalogQuery = usePolicyCatalog()
  const marginalReturnsQuery = usePolicyMarginalReturns()
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

  const resetToDefaults = () => {
    if (!catalogQuery.data?.ready) return
    const initial: Record<string, number> = {}
    for (const policy of catalogQuery.data.policies) {
      initial[policy.name] = policy.budget_cap
    }
    setBudgets(initial)
  }

  return (
    <QueryState isLoading={false} isError={false} error={null}>
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
            className="rounded border border-gray-300 px-3 py-1.5 text-sm text-gray-600 transition-colors hover:bg-brand-surface-muted focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-blue disabled:opacity-50"
          >
            기본값으로 초기화
          </button>
        </div>

        <QueryState isLoading={catalogQuery.isLoading} isError={catalogQuery.isError} error={catalogQuery.error}>
          {catalogQuery.data?.ready && budgets ? (
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              <div className="flex flex-col gap-4 rounded-lg border border-brand-border bg-white p-5 shadow-sm">
                <h3 className="text-sm font-medium text-gray-500">정책별 예산 배정 상한</h3>
                {catalogQuery.data.policies.map((policy) => (
                  <div key={policy.name}>
                    <label className="flex items-center justify-between text-sm text-gray-700">
                      <span>{policy.name}</span>
                      <span className="font-medium text-brand-ink">{formatEok(budgets[policy.name] ?? 0)}</span>
                    </label>
                    <input
                      type="range"
                      min={0}
                      max={policy.budget_cap * 2}
                      step={BUDGET_STEP}
                      value={budgets[policy.name] ?? 0}
                      aria-valuetext={formatEok(budgets[policy.name] ?? 0)}
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

        <PolicyMarginalReturnsPanel
          isLoading={marginalReturnsQuery.isLoading}
          isError={marginalReturnsQuery.isError}
          error={marginalReturnsQuery.error}
          data={marginalReturnsQuery.data}
          hasApiKey={Boolean(apiKey)}
        />
      </div>
    </QueryState>
  )
}

interface PolicyMarginalReturnsPanelProps {
  isLoading: boolean
  isError: boolean
  error: unknown
  data: PolicyMarginalReturnsResponse | undefined
  hasApiKey: boolean
}

function PolicyMarginalReturnsPanel({ isLoading, isError, error, data, hasApiKey }: PolicyMarginalReturnsPanelProps) {
  if (!hasApiKey) return null

  return (
    <div className="rounded-lg border border-brand-border bg-white p-5 shadow-sm">
      <h3 className="mb-1 text-sm font-medium text-gray-500">정책별 예산 10% 증액 시 한계 커버리지 증가(쉐도우 프라이스)</h3>
      <p className="mb-4 text-xs text-gray-400">
        정책 하나만 예산을 10% 늘리고 나머지는 고정한 채 LP를 재풀이한 결과입니다. 지금 예산배분에서 추가 1원당
        효과가 가장 큰 정책이 어디인지 보여줍니다.
      </p>
      <QueryState isLoading={isLoading} isError={isError} error={error}>
        {data && data.ready ? (
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={data.policies.map((p) => ({
                  policy: p.policy,
                  marginal_gain_per_10pct: p.marginal_gain_per_10pct,
                }))}
                layout="vertical"
                margin={{ left: 24 }}
              >
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis type="number" tickFormatter={(v: number) => `${(v * 100).toFixed(1)}%p`} />
                <YAxis type="category" dataKey="policy" width={140} tick={{ fontSize: 12 }} />
                <Tooltip formatter={(v: number) => (v !== null ? `${(v * 100).toFixed(2)}%p` : '—')} />
                <Bar dataKey="marginal_gain_per_10pct" name="한계 커버리지 증가">
                  {data.policies.map((p) => (
                    <Cell key={p.policy} fill={(p.marginal_gain_per_10pct ?? 0) > 0 ? '#0ea5e9' : '#94a3b8'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : data ? (
          <NotReadyBanner reason={data.reason} />
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
      <div className="rounded-lg border border-brand-border bg-white p-4 text-sm text-gray-600">
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
