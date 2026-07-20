import { useQuery } from '@tanstack/react-query'
import { apiDownload, apiPost } from '../api/client'
import type { ReportExportResponse } from '../api/types'
import { useAuthStore } from '../store/authStore'

export function useReportExport() {
  const apiKey = useAuthStore((state) => state.apiKey)

  return useQuery({
    queryKey: ['admin', 'report-export'],
    queryFn: () => apiPost<ReportExportResponse>('/api/v1/admin/report/export?format=json'),
    enabled: Boolean(apiKey),
  })
}

export async function downloadReport(format: 'csv' | 'json') {
  const blob = await apiDownload(`/api/v1/admin/report/export?format=${format}`, 'POST')
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `assignment-summary.${format}`
  link.click()
  URL.revokeObjectURL(url)
}
