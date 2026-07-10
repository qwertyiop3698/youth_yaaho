import { useAuthStore } from '../store/authStore'

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const apiKey = useAuthStore.getState().apiKey

  const headers = new Headers(options.headers)
  headers.set('Content-Type', 'application/json')
  if (apiKey) {
    headers.set('X-API-Key', apiKey)
  }

  let response: Response
  try {
    response = await fetch(`${BASE_URL}${path}`, { ...options, headers })
  } catch {
    throw new ApiError(0, `백엔드(${BASE_URL})에 연결할 수 없습니다. 서버가 켜져 있는지 확인하세요.`)
  }

  if (!response.ok) {
    let detail = `요청이 실패했습니다 (HTTP ${response.status}).`
    try {
      const body = (await response.json()) as { detail?: string }
      if (typeof body?.detail === 'string') {
        detail = body.detail
      }
    } catch {
      // 에러 응답 본문이 JSON이 아닌 경우 - 기본 메시지 사용
    }
    throw new ApiError(response.status, detail)
  }

  return (await response.json()) as T
}

export const apiGet = <T>(path: string): Promise<T> => request<T>(path)

export const apiPost = <T>(path: string, body?: unknown): Promise<T> =>
  request<T>(path, {
    method: 'POST',
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
