# CLAUDE.md — 청년야호 / Y-SAFE 프로젝트

이 문서는 Claude Code가 이 저장소에서 작업할 때 항상 먼저 참고해야 하는 프로젝트 컨텍스트다.

## 프로젝트 한 줄 정의

DIVE 2026 해커톤(부산광역시 × KCB) 출품작. KCB 금융 데이터를 기반으로 부산 청년 1인가구의 경제위험을 조기진단하고, 예산 제약 하에서 정책을 최적배정하는 시스템.

- **시민용 앱**: "청년야호" (Kotlin Compose, Android 네이티브)
- **정부용 웹 대시보드**: "Y-SAFE 대시보드" (React)
- **공통 백엔드**: FastAPI + PostgreSQL + Redis

## 지금 상황 (중요)

- 실제 KCB 데이터는 해커톤 당일에만 제공됨. 지금은 5행짜리 샘플 CSV(`data/sample.csv`)와 컬럼 명세 엑셀(`data/column_spec.xlsx`)만 있음.
- **개발 목표는 "당일 데이터만 갈아끼우면 되는" 파이프라인을 지금 다 만들어두는 것.** 모든 데이터 처리 로직은 컬럼명이 바뀌거나 일부 컬럼이 없어도 죽지 않도록 방어적으로 작성한다.
- 결측치 처리는 컬럼 그룹별로 의미가 다르므로 절대 일괄 규칙(전부 삭제, 전부 0 대체 등)을 쓰지 않는다. 반드시 `docs/02_data_missing_value_framework.md`를 먼저 읽고 그 로직대로 구현한다.

## 문서 읽는 순서 (작업 시작 전 필수)

새 기능을 만들기 전에 관련 문서를 먼저 읽어라. 문서를 안 읽고 임의로 설계하면 안 된다.

| 순서 | 문서 | 언제 참고 |
|---|---|---|
| 1 | `docs/00_service_overview.md` | 전체 맥락 파악, 첫 실행 시 항상 |
| 2 | `docs/01_architecture.md` | 새 모듈/레이어 작업 전 |
| 3 | `docs/02_data_missing_value_framework.md` | 데이터 전처리 코드 작성 전 (필수) |
| 4 | `docs/03_feature_engineering.md` | 파생변수 코드 작성 전 |
| 5 | `docs/04_modeling_clustering_survival.md` | GMM/Cox/SHAP 모델링 작업 전 |
| 6 | `docs/05_optimization_engine.md` | LP/Thompson Sampling 작업 전 |
| 7 | `docs/06_explanation_agent.md` | LLM 설명 에이전트 작업 전 |
| 8 | `docs/07_api_spec.md` | 백엔드 엔드포인트 작업 전 |
| 9 | `docs/08_db_schema.md` | DB 마이그레이션/쿼리 작업 전 |
| 10 | `docs/09_app_spec.md` | 앱(Kotlin Compose) 화면 작업 전 |
| 11 | `docs/10_web_dashboard_spec.md` | 웹 대시보드 화면 작업 전 |
| 12 | `docs/11_roadmap_and_priorities.md` | 무엇부터 할지 헷갈릴 때 |

## 코딩 컨벤션 및 원칙

- **데이터 누수 절대 금지**: 연체 관련 컬럼(연체건수/금액/일수)은 위험 예측모델의 입력 피처에 절대 넣지 않는다. 타겟(event) 정의에만 사용. 코드에 `assert` 로 강제할 것.
- **모든 결측 처리는 원본 삭제가 아니라 대체값 + `_was_missing` 플래그 컬럼 추가** 방식을 기본으로 한다 (표본 손실 최소화, 결측 자체가 신호일 수 있음).
- **컬럼명 하드코딩 최소화**: 실제 데이터가 오면 컬럼명/구성이 달라질 수 있으므로, 컬럼 매핑을 설정 파일(`config/column_mapping.yaml` 등)로 분리해 코드 수정 없이 대응 가능하게 만든다.
- **조인키 이중화**: 지역 데이터 조인은 행정동 우선, 실패 시 시군구코드로 fallback.
- 언어/스택: 백엔드·모델링은 Python(FastAPI, scikit-learn, lifelines, lightgbm, shap, pulp), 웹은 React, 앱은 Kotlin Compose.
- 커밋 전 항상 관련 유닛테스트 실행. 결측치 처리 모듈, 리스크모델 누수 방지 로직에는 반드시 테스트 작성.

## 디렉토리 구조 (제안)

```
youthyaho-project/
├── CLAUDE.md
├── docs/                     # 기획 문서 (이 폴더)
├── data/                     # 샘플 데이터, 실제 데이터(당일 교체)
├── backend/
│   ├── app/                  # FastAPI 앱
│   ├── pipeline/             # Layer 0~4 파이프라인
│   │   ├── layer0_data_contract/
│   │   ├── layer1_features/
│   │   ├── layer2a_clustering/
│   │   ├── layer2b_risk_model/
│   │   ├── layer3_optimization/
│   │   └── layer4_explanation/
│   └── tests/
├── web-dashboard/             # React 프로젝트
└── mobile-app/                 # Kotlin Compose 프로젝트
```

## 작업 시작 시 첫 행동

1. `docs/11_roadmap_and_priorities.md`에서 현재 우선순위 확인
2. 해당 작업과 관련된 문서 읽기
3. `data/sample.csv`, `data/column_spec.xlsx` 구조 확인 후 코드 작성
4. 구현 후 테스트 작성 및 실행
