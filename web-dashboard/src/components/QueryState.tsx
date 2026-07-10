import type { ReactNode } from 'react'
import { ApiError } from '../api/client'
import { useAuthStore } from '../store/authStore'

interface QueryStateProps {
  isLoading: boolean
  isError: boolean
  error: unknown
  children: ReactNode
}

// 여러 화면에서 반복되는 "API 키 없음 / 로딩 중 / 에러" 3단 분기를 공통화.
// ready:false(표본 부족 등 비즈니스 로직상 미준비)는 각 페이지가 NotReadyBanner로 별도 처리.
export function QueryState({ isLoading, isError, error, children }: QueryStateProps) {
  const apiKey = useAuthStore((state) => state.apiKey)

  if (!apiKey) {
    return (
      <div className="rounded-lg border border-yellow-200 bg-yellow-50 p-4 text-sm text-yellow-800">
        먼저 오른쪽 위에서 admin API 키를 입력해야 데이터를 볼 수 있습니다.
      </div>
    )
  }

  if (isLoading) {
    return <p className="text-sm text-gray-500">불러오는 중...</p>
  }

  if (isError) {
    const message = error instanceof ApiError ? error.message : '알 수 없는 오류가 발생했습니다.'
    return <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">{message}</div>
  }

  return <>{children}</>
}

export function NotReadyBanner({ reason }: { reason: string }) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 text-sm text-gray-600">
      아직 데이터가 준비되지 않았습니다: {reason}
    </div>
  )
}
