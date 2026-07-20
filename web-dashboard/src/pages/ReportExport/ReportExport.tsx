import { useState } from 'react'
import { NotReadyBanner, QueryState } from '../../components/QueryState'
import { StatCard } from '../../components/StatCard'
import { useReportExport, downloadReport } from '../../hooks/useReportExport'
import type { ReportExportReady, ReportExportRow } from '../../api/types'

const CONFIDENCE_LABELS: Record<string, string> = {
  verified: '검증됨',
  assumed_unresolved_codebook: '코드북 미확정(잠정)',
}

export function ReportExport() {
  const { data, isLoading, isError, error } = useReportExport()

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="text-xl font-semibold">리포트 내보내기</h2>
        <p className="mt-1 text-sm text-gray-500">
          정책별·자격조건 검증상태별 배정 집계입니다. 개인 raw ID는 포함하지 않습니다.
        </p>
      </div>

      <QueryState isLoading={isLoading} isError={isError} error={error}>
        {data && data.ready ? (
          <ReportExportContent data={data} />
        ) : data ? (
          <NotReadyBanner reason={data.reason} />
        ) : null}
      </QueryState>
    </div>
  )
}

function ReportExportContent({ data }: { data: ReportExportReady }) {
  const [downloading, setDownloading] = useState<'csv' | 'json' | null>(null)

  const handleDownload = async (format: 'csv' | 'json') => {
    setDownloading(format)
    try {
      await downloadReport(format)
    } finally {
      setDownloading(null)
    }
  }

  const totalAssignments = data.rows.reduce((sum, row) => sum + row.n_assignments, 0)
  const policyCount = new Set(data.rows.map((row) => row.policy)).size

  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <StatCard label="총 배정 건수" value={totalAssignments.toLocaleString('ko-KR')} />
        <StatCard label="집계에 포함된 정책 수" value={String(policyCount)} />
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-brand-border bg-white p-5 shadow-sm">
        <div>
          <h3 className="text-sm font-medium text-gray-500">다운로드</h3>
          <p className="mt-1 text-xs text-gray-400">CSV는 스프레드시트로, JSON은 다른 시스템 연동용으로 적합합니다.</p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => void handleDownload('csv')}
            disabled={downloading !== null}
            className="rounded border border-gray-300 px-3 py-1.5 text-sm text-gray-700 transition-colors hover:bg-brand-surface-muted focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-blue disabled:opacity-50"
          >
            {downloading === 'csv' ? '다운로드 중...' : 'CSV 다운로드'}
          </button>
          <button
            type="button"
            onClick={() => void handleDownload('json')}
            disabled={downloading !== null}
            className="rounded border border-gray-300 px-3 py-1.5 text-sm text-gray-700 transition-colors hover:bg-brand-surface-muted focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-blue disabled:opacity-50"
          >
            {downloading === 'json' ? '다운로드 중...' : 'JSON 다운로드'}
          </button>
        </div>
      </div>

      <div className="rounded-lg border border-brand-border bg-white p-5 shadow-sm">
        <h3 className="mb-4 text-sm font-medium text-gray-500">정책 × 자격조건 검증상태별 집계</h3>
        {data.rows.length === 0 ? (
          <p className="text-sm text-gray-400">표시할 배정 데이터가 없습니다.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm" role="table" aria-label="정책별 배정 집계표">
              <thead className="text-gray-500">
                <tr>
                  <th className="border-b border-brand-border py-2 pr-4">정책</th>
                  <th className="border-b border-brand-border py-2 pr-4">자격조건 검증상태</th>
                  <th className="border-b border-brand-border py-2 pr-4 text-right">배정 건수</th>
                  <th className="border-b border-brand-border py-2 text-right">평균 실험적 적합도</th>
                </tr>
              </thead>
              <tbody>
                {data.rows.map((row: ReportExportRow) => (
                  <tr key={`${row.policy}-${row.eligibility_confidence}`}>
                    <td className="py-1.5 pr-4">{row.policy}</td>
                    <td className="py-1.5 pr-4 text-gray-600">
                      {CONFIDENCE_LABELS[row.eligibility_confidence] ?? row.eligibility_confidence}
                    </td>
                    <td className="py-1.5 pr-4 text-right font-medium">{row.n_assignments.toLocaleString('ko-KR')}</td>
                    <td className="py-1.5 text-right text-gray-600">
                      {row.avg_experimental_fit !== null ? row.avg_experimental_fit.toFixed(3) : '—'}
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
