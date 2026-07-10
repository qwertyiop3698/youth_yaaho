// docs/10_web_dashboard_spec.md 화면-API 매핑에 대응하는 응답 타입들.
// backend/app/routers/admin.py의 실제 응답 형태와 동일하게 유지할 것.

export interface NotReady {
  ready: false
  reason: string
}

export interface OverviewReady {
  ready: true
  total_citizens: number
  avg_risk_probability: number | null
  // 키는 "cluster_0", "cluster_1", ... (pipeline/layer2a_clustering/cluster_interpreter.py)
  cluster_sizes: Record<string, number> | null
  suggested_labels: Record<string, string> | null
}

export type OverviewResponse = OverviewReady | NotReady

export type RiskMapLevel = 'dong' | 'sigungu'

export interface RiskRegion {
  region_code: string
  avg_risk_probability: number
  n: number
}

export interface RiskMapReady {
  ready: true
  level: RiskMapLevel
  regions: RiskRegion[]
}

export type RiskMapResponse = RiskMapReady | NotReady

export interface PolicyGapsReady {
  ready: true
  risk_threshold: number
  n_high_risk: number
  n_high_risk_without_policy: number
  person_ids: string[] // 최대 100건까지만(백엔드에서 슬라이스)
}

export type PolicyGapsResponse = PolicyGapsReady | NotReady

export interface PolicyCatalogEntry {
  name: string
  unit_cost: number
  budget_cap: number
}

export interface PolicyCatalogResponse {
  ready: true
  policies: PolicyCatalogEntry[]
}

// simulate-budget은 다른 admin 엔드포인트와 달리 ready 필드가 아니라 skipped
// 필드로 "계산 불가" 상태를 표현한다(POST 바디 검증까지 거친 뒤의 결과라서).
export interface SimulateBudgetResult {
  coverage_rate: number | null
  coverage_rate_verified_only: number | null
  by_cluster: Record<string, unknown> | null
  marginal_gain_per_10pct_budget: number | null
  skipped: boolean
  reason: string | null
}

export interface ClustersReady {
  ready: true
  best_k: number
  // 키는 "cluster_0", "cluster_1", ... ; 값은 도메인지수 이름 -> z-score
  // (pipeline/layer2a_clustering/cluster_interpreter.compute_cluster_profiles)
  cluster_profiles: Record<string, Record<string, number>> | null
  cluster_sizes: Record<string, number> | null
  suggested_labels: Record<string, string> | null
}

export type ClustersResponse = ClustersReady | NotReady

export interface SegmentRegret {
  segment_index: number
  segment_label: string
  round_start: number
  round_end: number
  mean_instant_regret: number | null
}

export interface EffectivenessGap {
  policy: string
  effectiveness_prior: number
  true_effectiveness: number | null
  gap: number | null
  direction: string | null
}

export interface BanditStateEntry {
  alpha: number
  beta: number
}

export interface BanditStatusReady {
  ready: true
  is_simulation: boolean
  simulation_disclaimer: string
  n_rounds: number
  final_posterior_means: Record<string, number>
  bandit_state: Record<string, BanditStateEntry>
  true_effectiveness: Record<string, number>
  segment_regret: SegmentRegret[]
  effectiveness_prior_vs_true_gap: EffectivenessGap[]
}

export type BanditStatusResponse = BanditStatusReady | NotReady
