import { Component, type ErrorInfo, type ReactNode } from 'react'

interface ErrorBoundaryProps {
  children: ReactNode
}

interface ErrorBoundaryState {
  error: Error | null
}

// 렌더링 중 예상치 못한 에러가 나면 흰 화면 대신 최소한의 안내를 보여준다.
// React 에러 바운더리는 클래스 컴포넌트로만 구현 가능(훅 대체재 없음, React 공식 문서 기준).
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('렌더링 중 처리되지 않은 오류:', error, errorInfo)
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex h-screen flex-col items-center justify-center gap-3 bg-white p-6 text-center">
          <p className="text-lg font-semibold text-brand-ink">문제가 발생했습니다.</p>
          <p className="max-w-md text-sm text-gray-500">
            화면을 표시하는 중 오류가 발생했습니다. 새로고침해도 문제가 계속되면 관리자에게 알려주세요.
          </p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="mt-2 rounded bg-brand-blue px-3 py-1.5 text-sm text-white transition-colors hover:bg-brand-blue-dark"
          >
            새로고침
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
