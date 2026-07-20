import { Link } from 'react-router-dom'

export function NotFound() {
  return (
    <div className="flex h-64 flex-col items-center justify-center gap-2 text-center">
      <p className="text-2xl font-semibold text-brand-ink">404</p>
      <p className="text-sm text-gray-500">요청하신 페이지를 찾을 수 없습니다.</p>
      <Link
        to="/"
        className="mt-2 rounded border border-gray-300 px-3 py-1.5 text-sm text-gray-700 transition-colors hover:bg-brand-surface-muted focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-blue"
      >
        종합 현황판으로 이동
      </Link>
    </div>
  )
}
