import { create } from 'zustand'

// 관리자 API 키는 브라우저 영구 저장소에 남기지 않고 현재 탭 메모리에만 보관한다.
// 새로고침 시 다시 입력해야 하지만 공유 PC/localStorage 탈취 시 키가 남는 위험을 줄인다.
// 회원 로그인(JWT)과는 별개 축 - 이건 "관리자 대시보드 접근용" 키다.
interface AuthState {
  apiKey: string | null
  setApiKey: (key: string) => void
  clearApiKey: () => void
}

export const useAuthStore = create<AuthState>()((set) => ({
  apiKey: null,
  setApiKey: (key: string) => set({ apiKey: key }),
  clearApiKey: () => set({ apiKey: null }),
}))
