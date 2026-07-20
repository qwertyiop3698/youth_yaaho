import { useState } from 'react'
import { usePolicyGaps } from '../../hooks/usePolicyGaps'
import { useDebouncedValue } from '../../hooks/useDebouncedValue'
import { NotReadyBanner, QueryState } from '../../components/QueryState'
import { StatCard } from '../../components/StatCard'
import type { PolicyGapsReady } from '../../api/types'

const DEFAULT_THRESHOLD = 0.6

export function PolicyGaps() {
  const [threshold, setThreshold] = useState(DEFAULT_THRESHOLD)
  const debouncedThreshold = useDebouncedValue(threshold, 300)
  const { data, isLoading, isError, error } = usePolicyGaps(debouncedThreshold)

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="text-xl font-semibold">정책 사각지대 탐지</h2>
        <p className="mt-1 text-sm text-gray-500">프록시 위험점수 상위 그룹 중 정책 미배정 인원을 지역별로 집계합니다.</p>
      </div>

      <div className="rounded-lg border border-brand-border bg-white p-4 shadow-sm">
        <label className="flex items-center justify-between text-sm text-gray-600">
          <span>위험점수 기준선(risk_threshold)</span>
          <span className="font-medium text-brand-ink">{threshold.toFixed(2)}</span>
        </label>
        <input
          type="range"
          min={0.1}
          max={0.95}
          step={0.01}
          value={threshold}
          onChange={(e) => setThreshold(Number(e.target.value))}
          className="mt-2 w-full"
        />
      </div>

      <QueryState isLoading={isLoading} isError={isError} error={error}>
        {data && data.ready ? (
          <PolicyGapsContent data={data} />
        ) : data ? (
          <NotReadyBanner reason={data.reason} />
        ) : null}
      </QueryState>
    </div>
  )
}

function PolicyGapsContent({ data }: { data: PolicyGapsReady }) {
  const gapRatio = data.n_high_risk > 0 ? (data.n_high_risk_without_policy / data.n_high_risk) * 100 : null

  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard label="위험점수 상위 인원" value={data.n_high_risk.toLocaleString('ko-KR')} />
        <StatCard
          label="그중 정책 미배정 인원"
          value={data.n_high_risk_without_policy.toLocaleString('ko-KR')}
        />
        <StatCard
          label="사각지대 비율"
          value={gapRatio !== null ? `${gapRatio.toFixed(1)}%` : '—'}
          hint="위험 상위 인원 중 정책이 하나도 배정되지 않은 비율"
        />
      </div>

      <div className="rounded-lg border border-brand-border bg-white p-5 shadow-sm">
        <h3 className="mb-4 text-sm font-medium text-gray-500">지역별 정책 미배정 집계</h3>
        {data.regions.length === 0 ? (
          <p className="text-sm text-gray-400">현재 기준선에서 표시할 지역 집계가 없습니다.</p>
        ) : (
          <div className="max-h-96 overflow-y-auto">
            <table className="w-full text-left text-sm">
              <thead className="sticky top-0 bg-white text-gray-500">
                <tr>
                  <th className="border-b border-brand-border py-2 pr-4">지역 코드</th>
                  <th className="border-b border-brand-border py-2 text-right">정책 미배정 인원</th>
                </tr>
              </thead>
              <tbody>
                {data.regions.map((region) => (
                  <tr key={region.region_code} className="odd:bg-red-50">
                    <td className="py-1.5 pr-4 font-mono text-gray-800">{region.region_code}</td>
                    <td className="py-1.5 text-right font-medium text-gray-800">
                      {region.n_high_risk_without_policy.toLocaleString('ko-KR')}명
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
