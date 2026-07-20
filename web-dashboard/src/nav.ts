// docs/10_web_dashboard_spec.md 화면 목록. 사용자 확정 우선순위:
// 종합현황판 -> 지역위험지도 -> 정책사각지대 -> 예산시뮬레이터 -> 유형별상세
// -> 밴딧학습현황 -> (리포트 내보내기) -> 로그인.
// 로그인은 별도 화면이 아니라 헤더의 API 키 입력 위젯으로 최소 구현했다 -
// 우선순위상 "로그인" 항목까지 오면 필요 여부를 다시 판단한다.
export interface NavItem {
  path: string
  label: string
  implemented: boolean
}

export const NAV_ITEMS: NavItem[] = [
  { path: '/', label: '종합 현황판', implemented: true },
  { path: '/risk-map', label: '지역 위험지도', implemented: true },
  { path: '/policy-gaps', label: '정책 사각지대', implemented: true },
  { path: '/budget-simulator', label: '예산 시뮬레이터', implemented: true },
  { path: '/clusters', label: '유형별 상세', implemented: true },
  { path: '/bandit-status', label: '밴딧 학습 현황', implemented: true },
  { path: '/policy-feedback', label: '정책 피드백 분석', implemented: true },
  { path: '/policy-demand', label: '정책 미충족 수요', implemented: true },
  { path: '/report-export', label: '리포트 내보내기', implemented: false },
]
