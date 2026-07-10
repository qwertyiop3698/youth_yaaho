import { create } from 'zustand'
import { persist } from 'zustand/middleware'

// 최소 구현: admin API 키를 브라우저(localStorage)에 저장해두고 요청마다
// X-API-Key 헤더로 실어보낸다(백엔드 app/auth.py의 require_admin_api_key와 매칭).
// 회원 로그인(JWT)과는 별개 축 - 이건 "관리자 대시보드 접근용" 키다.
interface AuthState {
  apiKey: string | null
  setApiKey: (key: string) => void
  clearApiKey: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      apiKey: null,
      setApiKey: (key: string) => set({ apiKey: key }),
      clearApiKey: () => set({ apiKey: null }),
    }),
    { name: 'ysafe-admin-auth' },
  ),
)
