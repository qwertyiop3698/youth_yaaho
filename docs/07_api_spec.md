# 07. API 명세

## 엔드포인트 전체 목록

```
POST   /api/v1/citizen/diagnose
GET    /api/v1/citizen/{session_id}/recommendations
GET    /api/v1/citizen/{session_id}/explanation
GET    /api/v1/citizen/{session_id}/history

GET    /api/v1/admin/overview
GET    /api/v1/admin/risk-map
GET    /api/v1/admin/clusters
GET    /api/v1/admin/policy-gaps
POST   /api/v1/admin/simulate-budget
GET    /api/v1/admin/bandit-status
POST   /api/v1/admin/report/export

POST   /api/v1/internal/pipeline/run-diagnostic   (Layer 0~2 배치 실행, 내부용)
POST   /api/v1/internal/pipeline/run-optimization (Layer 3 배치 실행, 내부용)
```

권한 분리 원칙: `/citizen/*`은 세션 기반 익명 접근 허용, `/admin/*`은 관리자 인증 필수, `/internal/*`은 외부 노출 금지(내부망 또는 API 키 인증).

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
  "hazard_estimate_months": 4.2
}
```

### GET /api/v1/citizen/{session_id}/recommendations

```json
{
  "recommendations": [
    {"policy": "청년월세지원", "priority": 1, "expected_effect": 0.18, "eligible": true},
    {"policy": "희망신용상담센터", "priority": 2, "expected_effect": 0.11, "eligible": true},
    {"policy": "부산청년 기쁨두배통장", "priority": 3, "expected_effect": 0.05, "eligible": false}
  ]
}
```

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
