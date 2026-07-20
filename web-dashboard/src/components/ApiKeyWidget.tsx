import { useState } from 'react'
import { useAuthStore } from '../store/authStore'

// 최소 구현 로그인: admin API 키를 현재 탭 메모리에만 보관하고,
// 이후 모든 admin API 요청에 X-API-Key 헤더로 실어보낸다(app/auth.py 참고).
// 별도 /login 라우트가 아니라 헤더에 항상 떠 있는 위젯으로 둔 이유는 어떤 화면도
// 로그인으로 막혀있지 않기 때문 - 화면 우선순위상 "로그인" 차례가 오면 이 위젯을
// 그대로 쓸지 전용 페이지로 승격할지 다시 판단한다.
export function ApiKeyWidget() {
  const apiKey = useAuthStore((state) => state.apiKey)
  const setApiKey = useAuthStore((state) => state.setApiKey)
  const clearApiKey = useAuthStore((state) => state.clearApiKey)
  const [draft, setDraft] = useState('')

  if (apiKey) {
    const masked = apiKey.length > 4 ? `••••${apiKey.slice(-4)}` : '••••'
    return (
      <div className="flex items-center gap-2 text-sm">
        <span className="text-green-700">API 키 설정됨 ({masked})</span>
        <button
          type="button"
          onClick={clearApiKey}
          className="rounded border border-gray-300 px-2 py-1 text-gray-600 transition-colors hover:bg-gray-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-blue"
        >
          해제
        </button>
      </div>
    )
  }

  return (
    <form
      className="flex items-center gap-2"
      onSubmit={(e) => {
        e.preventDefault()
        if (draft.trim()) {
          setApiKey(draft.trim())
          setDraft('')
        }
      }}
    >
      <input
        type="password"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        placeholder="Admin API 키(X-API-Key)"
        aria-label="Admin API 키"
        className="rounded border border-gray-300 px-2 py-1 text-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-blue"
      />
      <button
        type="submit"
        className="rounded bg-brand-blue px-3 py-1 text-sm text-white transition-colors hover:bg-brand-blue-dark focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-blue-dark"
      >
        저장
      </button>
    </form>
  )
}
