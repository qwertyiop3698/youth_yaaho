# 01. 전체 아키텍처

## 시스템 다이어그램

```
┌─────────────────────┐        ┌──────────────────────┐
│  청년야호 (앱)          │        │  Y-SAFE 대시보드(웹)     │
│  (Kotlin Compose)     │        │  (React + Kakao Map)   │
└──────────┬───────────┘        └───────────┬──────────┘
           │  REST/JSON                     │  REST/JSON
           └───────────────┬────────────────┘
                           ↓
        ┌───────────────────────────────────────┐
        │        API Gateway (FastAPI)            │
        │  /api/v1/citizen/*   /api/v1/admin/*    │
        └───────────────────┬─────────────────────┘
                            ↓
   ┌────────────────────────────────────────────────┐
   │   파이프라인 레이어                                  │
   │                                                  │
   │   Layer 0. Data Contract & 결측치 진단              │
   │       - 컬럼 그룹별 자동 프로파일링                    │
   │       - sentinel/0값 의미 분류                      │
   │       - 출력: clean_dataset + missing_flag 컬럼셋    │
   │                     ↓                            │
   │   Layer 1. Feature Engineering                   │
   │       - 파생변수 15종, 도메인 지수 5종                 │
   │                     ↓                            │
   │   Layer 2-A. GMM 소프트 클러스터링 (유형 발견)          │
   │   Layer 2-B. Cox 생존분석 + LGBM 베이스라인 + SHAP    │
   │                     ↓                            │
   │   Layer 3. 최적화 엔진                              │
   │       3-A. LP 기반 예산 배정 (PuLP)                  │
   │       3-B. Thompson Sampling 지속학습 시뮬레이터        │
   │                     ↓                            │
   │   Layer 4. 설명 에이전트 (Claude API)                │
   └───────────────────┬──────────────────────────────┘
                       ↓
        ┌───────────────────────────────┐
        │ PostgreSQL (원본데이터, 배정결과)   │
        │ Redis (세션, 캐시, 실시간 스코어)   │
        └───────────────────────────────┘
```

## 설계 원칙

1. **Layer 0만 갈아끼우면 나머지는 그대로 작동해야 한다.** 당일 실데이터 투입 시 Layer 0(데이터 계약 검증 + 결측치 프로파일러)만 재실행하고, 이후 레이어는 동일한 인터페이스(정제된 DataFrame/parquet)를 받는다.
2. **시민 데이터와 행정 집계 데이터를 API 레벨에서부터 분리한다.** `/api/v1/citizen/*`(개인정보 포함)과 `/api/v1/admin/*`(집계/통계만)를 코드 구조상으로도 분리해, 나중에 개인정보보호 심사를 받아도 구조적으로 안전하게 만든다.
3. **모델은 사전학습 후 서빙한다.** GMM/Cox 모델은 배치로 사전 학습해 pickle/joblib으로 저장하고, API는 저장된 모델을 로드해 실시간 추론만 수행한다 (해커톤 당일 재학습 시간 절약).
4. **LP/Thompson Sampling은 배치 작업이다.** 실시간 API 호출마다 최적화를 다시 풀지 않고, 주기적으로(또는 관리자 트리거로) 재계산 후 결과를 DB에 저장, API는 저장된 결과를 조회만 한다.

## 기술 스택

| 영역 | 스택 | 비고 |
|---|---|---|
| 백엔드 API | FastAPI | |
| 데이터 처리 | pandas / polars | |
| 모델링 | scikit-learn(GMM), lifelines(Cox), lightgbm, shap | |
| 최적화 | PuLP(LP), 자체 구현 Thompson Sampling(numpy/scipy) | |
| 저장 | PostgreSQL (+ pgvector 선택) | |
| 캐시 | Redis | |
| LLM | Claude API | 설명 에이전트 |
| 웹 프론트 | React + Vite + Tailwind + recharts + Kakao Map SDK | |
| 앱 | Kotlin Compose + Retrofit + Coroutines/Flow | |

## 레이어별 산출물 (인터페이스 계약)

| 레이어 | 입력 | 출력 |
|---|---|---|
| Layer 0 | raw CSV | `clean_dataset.parquet` (결측처리+플래그 컬럼 포함), `profiling_report.json` |
| Layer 1 | clean_dataset | `featured_dataset.parquet` (파생변수+도메인지수 5종 포함) |
| Layer 2-A | featured_dataset (도메인지수) | `cluster_model.pkl`, `cluster_membership.parquet` |
| Layer 2-B | featured_dataset | `risk_model.pkl`, `risk_scores.parquet` (hazard_months, shap_top3 포함) |
| Layer 3-A | risk_scores + cluster_membership + policy_catalog | `assignment_result.parquet` |
| Layer 3-B | assignment_result + 합성 리워드 | `bandit_state.json`, regret curve 데이터 |
| Layer 4 | shap_top3 + cluster_membership + assigned_policies | 자연어 설명 텍스트 (API 응답에 포함, 별도 저장 불필요) |
