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

export type LisaQuadrant = 'HH' | 'LL' | 'HL' | 'LH'

export interface RiskRegion {
  region_code: string
  avg_risk_probability: number
  n: number
  // sigungu 레벨에서만 채워짐(dong은 경계 geojson이 없어 공간분석 불가)
  lisa_quadrant: LisaQuadrant | null
  // 2026-07-25 DIVE 2026 이종결합 작업2: lisa_quadrant를 통계적 유의성까지 반영해
  // hotspot/coldspot/not_significant 3분류로 단순화한 것(HL/LH 이상치는 not_significant로 묶임).
  hotspot_classification: 'hotspot' | 'coldspot' | 'not_significant'
  // 2026-07-25 DIVE 2026 이종결합: 부산시 인구현황 외부데이터 결합. population_reference가
  // null이면 그 지역은 생활인구 매칭 실패(0명이 아니라 "모름" - 0으로 나누지 않음).
  n_high_risk: number
  population_reference: number | null
  population_join_method: 'dong' | 'sigungu' | 'unmatched' | null
  high_risk_per_1000_population: number | null
}

export interface SpatialStats {
  skipped: boolean
  reason?: string
  morans_i?: number
  p_value?: number
  n_regions?: number
  n_permutations?: number
  is_significant?: boolean
}

export interface RiskMapReady {
  ready: true
  level: RiskMapLevel
  regions: RiskRegion[]
  spatial_stats: SpatialStats | null
  population_reference_available: boolean
  population_data_note: string | null
}

export type RiskMapResponse = RiskMapReady | NotReady

export interface FairnessCorrectionGap {
  before_tpr_gap: number | null
  after_tpr_gap: number | null
}

export interface PolicyGapsReady {
  ready: true
  risk_threshold: number
  n_high_risk: number
  n_high_risk_without_policy: number
  regions: Array<{ region_code: string; n_high_risk_without_policy: number }>
  // 성별 equalized-odds 보정임계값이 적용됐는지(risk_threshold가 보정 기준선과
  // 다르면 자동으로 false - fairness_correction.py, admin.py 참고)
  fairness_correction_applied: boolean
  fairness_correction_before_after_gap: FairnessCorrectionGap | null
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

// LP는 이진변수(MIP)라 쉐도우 프라이스가 엄밀히 정의되지 않으므로, 정책 하나만
// 예산을 10% 올려 재풀이하는 finite-difference로 근사한 값이다(docs/05 5-3).
export interface PolicyMarginalReturn {
  policy: string
  baseline_coverage: number | null
  bumped_coverage: number | null
  marginal_gain_per_10pct: number | null
  objective_delta: number | null
  skipped: boolean
}

export interface PolicyMarginalReturnsReady {
  ready: true
  policies: PolicyMarginalReturn[]
}

export type PolicyMarginalReturnsResponse = PolicyMarginalReturnsReady | NotReady

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

// 실측 전이 데이터가 아니라 클러스터 중심 거리 + 위험도 방향으로 구성한
// 시뮬레이션이다(is_simulation은 항상 true - risk_trajectory_simulator.py 참고).
export interface TrajectoryStep {
  step: number
  expected_avg_risk: number
  [clusterKey: string]: number
}

export interface RiskTrajectoryOutlookReady {
  ready: true
  is_simulation: boolean
  simulation_disclaimer: string
  n_steps: number
  intervention_effectiveness_used: number
  no_intervention: TrajectoryStep[]
  intervention: TrajectoryStep[]
}

export type RiskTrajectoryOutlookResponse = RiskTrajectoryOutlookReady | NotReady

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

export interface ProtectedCount {
  suppressed: boolean
  count: number | null
}

export type ProtectedDistribution = Record<string, ProtectedCount>

export interface FeedbackStageRate {
  suppressed: boolean
  responses: number | null
  eligible_usages: number | null
  rate: number | null
}

export interface PolicyFeedbackMetrics {
  usage_funnel: Record<string, ProtectedCount>
  stage_response_rates: Record<string, FeedbackStageRate>
  perceived_effect_distribution: ProtectedDistribution
  most_helpful_area_distribution: ProtectedDistribution
  application_barrier_distribution: ProtectedDistribution
  support_adequacy_distribution: ProtectedDistribution
  insufficient_amount_ratio: number | null
  insufficient_period_ratio: number | null
  both_insufficient_ratio: number | null
  followup_support_distribution: ProtectedDistribution
  improvement_direction_distribution: ProtectedDistribution
  selected_rejected_barrier_comparison: Record<string, unknown>
  policy_usage_completion_rate: number | null
  free_text_response_count: number | null
  free_text_response_suppressed: boolean
}

export type PolicyRecommendation =
  | 'maintain' | 'expand' | 'simplify' | 'retarget' | 'extend_duration'
  | 'increase_amount' | 'connect_followup' | 'redesign' | 'insufficient_data'

export type AnalysisConfidence = 'low' | 'medium' | 'high'

export interface PolicyAnalysisScores {
  effectiveness: number | null
  accessibility: number | null
  support_adequacy: number | null
  followup_need: number | null
  improvement_urgency: number | null
}

export interface PolicyFeedbackAnalysis {
  policy_id: string
  policy_name: string
  category: string
  respondent_count: number
  publicly_available: boolean
  confidence: AnalysisConfidence
  scores: PolicyAnalysisScores
  primary_bottleneck: string | null
  top_followup_need: string | null
  primary_recommendation: PolicyRecommendation
  secondary_recommendations: PolicyRecommendation[]
  summary: string[]
  suppressed_cell_count: number
  ranks: Record<string, number | null>
  category_ranks: Record<string, number | null>
}

export interface PolicyFeedbackSummary {
  policy_id: string
  policy_name: string
  respondent_count: number
  minimum_group_size: number
  suppressed: boolean
  suppression_reason: string | null
  usage_count: number
  feedback_submission_count: number
  overall_response_rate: number | null
  metrics: PolicyFeedbackMetrics | null
}

export interface DemandTrend {
  suppressed: boolean
  current_count: number | null
  previous_count: number | null
  change_rate: number | null
}
export interface PolicyDemandMetrics {
  need_area_distribution: ProtectedDistribution
  duration_distribution: ProtectedDistribution
  amount_distribution: ProtectedDistribution
  barrier_distribution: ProtectedDistribution
  companion_support_distribution: ProtectedDistribution
  trigger_reason_distribution: ProtectedDistribution
  district_distribution: ProtectedDistribution
  employment_distribution: ProtectedDistribution
  category_gap_distribution: ProtectedDistribution
  trend_30_days: DemandTrend
  trend_90_days: DemandTrend
}
export interface PolicyDemandSummary {
  respondent_count: number
  minimum_group_size: number
  suppressed: boolean
  suppression_reason: string | null
  metrics: PolicyDemandMetrics | null
  comparison_summary: string[]
}
export interface ReportExportRow {
  policy: string
  eligibility_confidence: string
  n_assignments: number
  avg_experimental_fit: number | null
}

export interface ReportExportReady {
  ready: true
  format: 'json'
  rows: ReportExportRow[]
}

export type ReportExportResponse = ReportExportReady | NotReady

export interface PolicyDemandPriority {
  need_area: string
  respondent_count: number | null
  publicly_available: boolean
  score: number | null
  confidence: AnalysisConfidence
  components: Record<string, number | null> | null
  primary_recommendation: string
  secondary_recommendations: string[]
  top_district: string | null
  top_employment_status: string | null
  top_trigger_reason: string | null
  summary: string[]
}
