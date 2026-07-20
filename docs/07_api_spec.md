# 07. API 명세

## 엔드포인트 전체 목록

```
POST   /api/v1/citizen/diagnose
POST   /api/v1/citizen/auth/signup
POST   /api/v1/citizen/auth/login
POST   /api/v1/citizen/auth/refresh
POST   /api/v1/citizen/auth/logout
DELETE /api/v1/citizen/auth/me
GET    /api/v1/citizen/{session_id}/recommendations
GET    /api/v1/citizen/{session_id}/explanation
GET    /api/v1/citizen/{session_id}/history
POST   /api/v1/citizen/policy-usages
PATCH  /api/v1/citizen/policy-usages/{usage_id}/status
GET    /api/v1/citizen/me/policy-usages
GET    /api/v1/citizen/policies/{policy_id}/feedback-form?stage={stage}
POST   /api/v1/citizen/policy-usages/{usage_id}/feedback
GET    /api/v1/citizen/me/rewards

GET    /api/v1/admin/overview
GET    /api/v1/admin/risk-map
GET    /api/v1/admin/clusters
GET    /api/v1/admin/policy-gaps
POST   /api/v1/admin/simulate-budget
GET    /api/v1/admin/bandit-status
POST   /api/v1/admin/report/export
GET    /api/v1/admin/policies/{policy_id}/feedback-summary
GET    /api/v1/admin/policy-feedback-summaries

POST   /api/v1/internal/pipeline/run-diagnostic   (Layer 0~2 배치 실행, 내부용)
POST   /api/v1/internal/pipeline/run-optimization (Layer 3 배치 실행, 내부용)
```

권한 분리 원칙: 익명 진단 세션은 UUID와 응답에서 한 번 발급된 `X-Session-Token`을
함께 요구하며 DB에는 토큰 해시만 저장한다. 로그인 회원의 세션은 해당 회원의 Bearer
JWT가 반드시 필요하다. `/admin/*`은 관리자 인증 필수이며 개인
ID 대신 집계만 반환한다. `/internal/*`은 외부 노출 금지(내부망 또는 API 키 인증).
인증·진단·설명 API에는 단일 프로세스 기준 요청 제한이 적용된다.

## 스키마 예시

### POST /api/v1/citizen/diagnose

```json
// request
{
  "age_group": "25-29",
  "dong_code": "26440",
  "income_band": "2500-3000",
  "housing_type": "월세",
  "has_debt": true
}

// response
{
  "session_id": "uuid",
  "session_access_token": "익명 세션에서만 발급되는 비밀 토큰",
  "domain_indices": {
    "주거비압박": 0.72,
    "부채상환위험": 0.55,
    "소득변동성": 0.30,
    "소비압박": 0.41,
    "신용취약": 0.28
  },
  "cluster_membership": {
    "주거비압박형": 0.62,
    "부채과부하형": 0.31,
    "기타": 0.07
  },
  "risk_probability": 0.42,
  "diagnosis_mode": "approximate",
  "approximation_notice": "간이 추정입니다..."
}
```

### GET /api/v1/citizen/{session_id}/recommendations

익명 세션은 진단 응답의 `session_access_token`을 `X-Session-Token` 헤더로 전달한다.
회원 세션은 Bearer access token을 사용한다.

```json
{
  "recommendations": [
    {"policy": "청년월세지원", "priority": 1, "expected_effect": 0.18, "eligible": true,
     "eligibility_confidence": "assumed_unresolved_codebook"},
    {"policy": "희망신용상담센터", "priority": 2, "expected_effect": 0.11, "eligible": true},
    {"policy": "부산청년 기쁨두배통장", "priority": 3, "expected_effect": 0.05, "eligible": false}
  ]
}
```

`expected_effect`는 실증된 위험 감소율이 아니라 프록시 위험점수·정책 대상 영역·
가정 prior를 조합한 실험적 적합도다. `eligibility_confidence`가 `verified`가 아니면
신청 가능으로 단정하지 않고 실제 공고를 확인해야 한다.

### POST /api/v1/admin/simulate-budget

```json
// request
{ "policy_budgets": {"청년월세지원": 500000000, "머물자리론": 300000000} }

// response
{
  "coverage_rate": 0.42,
  "by_cluster": {"주거비압박형": 0.55, "부채과부하형": 0.30},
  "marginal_gain_per_10pct_budget": 0.06
}
```

## 구현 위치

`backend/app/routers/citizen.py`, `backend/app/routers/admin.py`, `backend/app/routers/internal.py`

정책 피드백 익명 집계와 개선 우선순위 분석은 각각
`backend/app/feedback/router.py`, `backend/app/feedback_analysis/router.py`에 분리되어
있다. 분석 API는 기존 관리자 `X-API-Key` 인증을 그대로 사용한다. 상세 계약과
CSV/JSON export 스키마는 [12_policy_feedback.md](./12_policy_feedback.md)를 참고한다.

미충족 정책 수요 시민·관리자 API는 `backend/app/policy_demand/router.py`에 있으며,
집계·우선순위·보호 규칙은 [13_policy_demand.md](./13_policy_demand.md)를 참고한다.
