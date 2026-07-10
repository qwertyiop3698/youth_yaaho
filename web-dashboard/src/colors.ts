// 클러스터/카테고리 계열 데이터에 공통으로 쓰는 색상 팔레트.
export const CATEGORY_COLORS = ['#6366f1', '#f59e0b', '#10b981', '#ef4444', '#0ea5e9', '#a855f7', '#84cc16']

export function colorForIndex(index: number): string {
  return CATEGORY_COLORS[index % CATEGORY_COLORS.length]
}
