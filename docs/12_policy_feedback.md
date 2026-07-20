# 12. 청년정책 이용 피드백 및 정책개선 데이터 수집

## 목적과 범위

사용자가 실제로 신청 또는 이용 단계에 도달한 정책에 대해서만 단계별 피드백을
받고, 개인을 식별할 수 없는 정책 단위 집계로 부산시 정책 개선 지표를 만든다.
추천 후보는 기존 Layer 3 현재 카탈로그와 온통청년 연동 흐름을 그대로 사용한다.
종료 정책 목록을 별도로 추천하지 않으며, 과거 정책은 이미 생성된 `PolicyUsage`가
있는 경우에만 `내 정책 기록`에서 조회된다.

이번 1차 구현은 신뢰 가능한 상태·설문·보상·집계 기반과 재사용 가능한 Android
Presentation 컴포넌트를 제공한다. 동백전 실 API, 부산시 행정 시스템으로의 전송,
정책 신청 사실의 기관 검증은 아직 연동하지 않는다. AI/LLM은 사용하지 않는다.

## Layer별 책임

| Layer | 구현 위치 | 책임 |
|---|---|---|
| Presentation/API | `backend/app/feedback/router.py`, Android `ui/policyfeedback` | 회원 API, 관리자 API, 정책 상세/내 기록/단계별 설문 UI |
| Application | `backend/app/feedback/service.py` | 이용기록·상태변경·설문 제출·리워드 자격·집계 유스케이스 |
| Domain | `backend/app/feedback/domain.py` | 상태 전이, 설문 단계, 6문항/선택지, 기타 서술 검증 |
| Infrastructure | `models.py`, `repositories.py`, `policy_gateway.py`, `reward.py` | SQLite/PostgreSQL 호환 테이블, 집계 쿼리, 기존 정책 카탈로그 어댑터, Mock 리워드 |

피드백 패키지는 기존 `backend/pipeline/layer0_*`~`layer4_*` 배치 코드와 분리되어
있다. 기존 정책 추천은 읽기 전용 `CatalogPolicyRepository`를 통해서만 참조하므로
피드백 저장 실패가 진단·검색·추천 실행을 막지 않는다.

## 데이터 모델

| 테이블 | 주요 필드/제약 |
|---|---|
| `policy_usages` | `usage_id`, `user_id`, 정책 ID/이름/출처 snapshot, `current_status`; 사용자·정책 유일 |
| `policy_usage_status_history` | 상태와 `changed_at`; 모든 정상 전이를 append-only 기록 |
| `feedback_questions` | `form_version`, 문항 코드/문구/선택지/단계/순서; 6문항 멱등 seed |
| `policy_feedback` | 이용기록, 정책, 단계, `form_version`, 제출시각; `(usage_id, stage)` 유일 |
| `feedback_answers` | 문항 코드, 선택값, 제한된 기타 서술; 피드백·문항 유일 |
| `reward_grants` | 피드백/이용기록/단계/금액/상태/provider 참조; `(usage_id, stage)` 유일 |

`db.init_db()`가 새 테이블을 `create_all()`로 추가하고 `2026-01` 설문 문항을
멱등하게 초기화한다. 기존 테이블이나 데이터를 삭제하지 않는다. 운영 전환 및
비가산 스키마 변경부터는 Alembic 마이그레이션을 도입해야 한다.

## 정책 이용 상태 흐름

```text
recommended -> application_started -> applied -> selected -> using -> completed
                                           \-> rejected
recommended/application_started/applied/selected/using -> cancelled
```

동일 상태 재처리, 역행, 종료 상태(`rejected`, `completed`, `cancelled`) 이후 전이는
거부한다. Application 검증 뒤에도 DB 갱신 조건에 이전 상태를 포함해 동시 요청이
서로 덮어쓰지 못하게 한다.

설문 단계는 현재 이용 상태와 정확히 같아야 한다.

- `applied`: 신청 장벽
- `selected`, `rejected`: 결과 단계별 신청 장벽
- `using`: 도움 영역, 상황 변화, 후속 지원
- `completed`: 도움 영역, 상황 변화, 금액·기간 적정성, 후속 지원, 개선 방향

개선 방향에서 `기타`를 선택한 경우에만 최대 200자 서술을 허용한다. 그 외 선택에
딸린 서술은 개인정보 최소수집 원칙상 저장하지 않고 요청 자체를 거부한다.

## API

모든 시민 피드백 API는 회원 Bearer JWT가 필요하다. 관리자 집계는 기존과 동일하게
32바이트 이상의 `ADMIN_API_KEY`를 `X-API-Key`로 요구하며 미설정 시 fail-closed다.

```text
POST  /api/v1/citizen/policy-usages
PATCH /api/v1/citizen/policy-usages/{usage_id}/status
GET   /api/v1/citizen/me/policy-usages
GET   /api/v1/citizen/policies/{policy_id}/feedback-form?stage=completed
POST  /api/v1/citizen/policy-usages/{usage_id}/feedback
GET   /api/v1/citizen/me/rewards
GET   /api/v1/admin/policies/{policy_id}/feedback-summary
GET   /api/v1/admin/policy-feedback-summaries
GET   /api/v1/admin/policy-feedback-analysis
GET   /api/v1/admin/policies/{policy_id}/feedback-analysis
GET   /api/v1/admin/policy-feedback-priorities
GET   /api/v1/admin/policy-feedback-analysis/export?format=csv|json
```

이용기록 생성 예시:

```json
{"policy_id": "청년월세지원"}
```

신청 완료 상태 변경 및 설문 제출 예시:

```json
{"status": "applied"}
```

```json
{
  "stage": "applied",
  "answers": [
    {"question_code": "application_barrier", "choice": "제출서류"}
  ]
}
```

설문 폼 응답의 `notice`에는 다음 문구가 항상 포함되고 Android 화면도 동일한 상수를
항상 표시한다.

> 작성해 주신 의견은 익명으로 집계되어 부산시 청년정책 개선 자료로 전달됩니다. 여러분의 경험이 다음 정책을 바꾸는 근거가 됩니다.

## 리워드 모의 처리

응답의 긍정/부정과 관계없이 유효한 설문 제출 완료만으로 자격을 판정한다. 이용기록,
현재 단계, 중복 여부가 모두 검증된 뒤 `pending` 리워드를 설문과 같은 트랜잭션에
저장한다. DB 커밋 뒤 `MockRewardProvider`가 `mock_paid`로 바꾼다. Provider가 실패하면
설문은 유지되고 리워드는 `pending`으로 남아 재처리할 수 있다.

기본 금액은 `.env`에서 바꾼다.

```dotenv
FEEDBACK_REWARD_APPLIED_AMOUNT=500
FEEDBACK_REWARD_SELECTED_AMOUNT=500
FEEDBACK_REWARD_REJECTED_AMOUNT=500
FEEDBACK_REWARD_USING_AMOUNT=700
FEEDBACK_REWARD_COMPLETED_AMOUNT=1000
```

코드 곳곳에 금액을 하드코딩하지 않고 `RewardPolicy`가 한 번 읽는다. 실제 동백전
연동 시 `RewardProvider` 구현만 교체한다. 확인되지 않은 동백전 URL이나 요청 형식은
만들지 않았다.

## 개인정보와 익명 집계

관리자 Repository는 선택형 응답과 집계에 필요한 상태만 조회한다. 사용자 ID,
이름, 이메일, 연락처, 원문 금융정보, 기타 자유서술 원문은 API 결과에 포함하지
않는다. 자유서술은 원문 대신 건수만 집계한다.

기본 최소 집계 인원은 고유 응답자 5명이다. 전체 고유 응답자가 기준 미만이면
`suppressed=true`, `metrics=null`을 반환한다. 전체 기준을 넘더라도 선정자/탈락자
하위 그룹은 각각 5명 미만이면 해당 비교 분포를 별도로 억제한다.

제공 지표는 단계별 응답률, 체감 효과, 도움 영역, 신청 장벽, 금액/기간 부족 비율,
후속 지원, 개선 방향, 선정자·탈락자 장벽 차이, 이용 완료율, 자유서술 건수다.

```dotenv
FEEDBACK_MIN_AGGREGATE_SIZE=5
```

## 시민 Android 사용자 흐름

```text
정책 추천 → 정책 상세 → 내 정책에 추가/신청 시작/신청 완료
→ 내 정책 기록 → 서버가 허용한 다음 상태 선택 → 단계별 설문
→ 제출 완료 및 동백전 지급 예정(Mock) 확인 → 내 모의 리워드
```

- 추천 카드의 `정책 상세 및 이용 기록`에서 상세 화면으로 이동한다.
- 상세 화면은 기존 기록을 먼저 조회하며, 이미 존재하면 `POST /policy-usages`를
  반복 호출하지 않는다. 경쟁 요청으로 409가 발생해도 목록을 다시 읽어 기존 기록을
  사용한다.
- 외부 `신청하러 가기`를 누를 때도 신청 시작 기록을 함께 시도한다. HTTPS 신청
  주소만 외부 앱으로 전달한다.
- 설정 화면과 정책 상세에서 `내 정책 기록`으로 진입할 수 있다.
- 기록은 신청 준비, 신청 완료, 선정, 탈락, 이용 중, 이용 완료, 취소로 묶어 표시한다.
- 상태 버튼은 API의 `next_allowed_statuses`만 사용한다. Android가 상태 전이표를
  복제해 임의 역행 버튼을 만들지 않는다.
- `available_feedback_stages`가 있을 때만 다음 작성 가능한 의견 버튼을 표시한다.

### 상태별 화면과 버튼

| 현재 상태 | 대표 다음 버튼 | 자동 노출 설문 |
|---|---|---|
| `recommended` | 신청 시작 기록, 기록 취소 | 없음 |
| `application_started` | 신청 완료했어요, 기록 취소 | 없음 |
| `applied` | 선정되었어요, 선정되지 않았어요, 취소 | 신청 과정 피드백 |
| `selected` | 이용을 시작했어요, 취소 | 선정 결과 피드백 |
| `rejected` | 없음 | 탈락 결과 피드백 |
| `using` | 이용을 완료했어요, 취소 | 이용 중간 피드백 |
| `completed` | 없음 | 최종 효과 피드백 |

설문은 진행률, 문항별 단일선택, 기타 선택 시에만 표시되는 200자 입력과 글자 수,
미응답 제출 차단, 예상 리워드 금액을 제공한다. 다음 안내를 항상 표시한다.

> 솔직한 의견을 남겨주세요. 좋은 평가와 아쉬운 평가 모두 동일한 리워드가 지급됩니다.

완료 화면은 제출 금액과 `pending` 또는 `mock_paid` 상태를 표시한다. 리워드 화면은
지급 대기 금액, Mock 지급 완료 금액, 정책·설문 단계·생성일별 내역을 보여준다.

## React 행정 대시보드

사이드 메뉴의 `정책 피드백 분석`은 정책 목록과 선택 정책 상세를 한 화면에서
제공한다.

- 정책 목록: 이용기록 수, 응답자 수, 전체 응답률, 대표 체감 효과, 주요 신청 장벽,
  대표 개선 방향, 집계 가능 여부
- 정책 효과: 상황 변화 선택지 분포
- 도움 영역: 취업·생활비·주거비·금융·심리·사회활동 분포
- 신청 장벽: 자격조건, 서류, 신청방법, 결과 대기, 방문 필요
- 예산 적정성: 금액 부족, 기간 부족, 모두 부족 비율
- 후속 정책 수요 및 개선 요구 분포

`policyFeedbackInsights.ts`는 공개 가능한 선택형 집계만 받아 다음 규칙으로 문장을
만든다. LLM은 호출하지 않는다.

1. 각 분포에서 공개된 최빈 선택지를 찾는다.
2. 체감 변화, 도움 영역, 신청 장벽, 후속 지원, 개선 방향을 문장으로 바꾼다.
3. `지원기간 연장` 공개 건수가 `지원금 확대`보다 크면 기간 연장 요구 인사이트를 추가한다.
4. 전체가 억제됐거나 공개 셀이 없으면 판단 보류 문구만 표시한다.

### 표본 보호 UI 원칙

- `suppressed=true`이면 응답자 수, 응답률, 상세 차트와 수치를 모두 `숨김` 처리한다.
- 세부 셀의 `suppressed=true` 또는 `count=null`은 차트 데이터에서 완전히 제거한다.
- `1~4명` 같은 범위나 비율 역산값을 만들지 않는다.
- 공개 가능한 셀이 하나도 없으면 `응답 인원이 적어 세부 결과를 공개하지 않습니다.`를 표시한다.

## 정책 개선 우선순위 분석 Layer

`backend/app/feedback_analysis`는 피드백 저장 도메인과 분리된 읽기 전용 Layer다.
`FeedbackAggregateRepository`가 반환한 익명·보호 집계만 입력으로 사용하며
`policy_feedback`, `feedback_answers` 원시 테이블이나 자유서술 원문을 직접 읽지 않는다.

| 파일 | 책임 |
|---|---|
| `domain.py` | 점수, 신뢰도, 주·보조 권고 값 객체 |
| `scoring.py` | `ScoringConfig`, 점수·신뢰도·권고 순수 함수 |
| `service.py` | 정책 메타데이터 결합, 분석 생성, 전체·카테고리 순위 |
| `schemas.py`, `router.py` | 관리자 조회와 요청 시점 CSV/JSON export |

### 점수 정의와 기본 가중치

모든 점수는 0~100이며 소수 첫째 자리로 반올림한다. 분포 안에 억제 셀이 하나라도
있으면 숨은 값을 0으로 간주하거나 역산하지 않고 해당 점수를 `null`로 둔다.

- 효과: 상황 변화(`매우 좋아짐=100`, `조금 좋아짐=70`, `비슷함=40`,
  `더 나빠짐=0`) 80%와 도움 영역(`도움 없음=0`, 그 외=100) 20%의 결합 점수
- 접근성: `어려움 없음=100`, `결과 대기=45`, `신청방법=35`, `제출서류=30`,
  `자격조건=25`, `방문 필요=20`의 가중평균. 공개 최빈 장벽도 별도 반환
- 지원 적정성: `모두 충분=100`, `금액 부족=55`, `기간 부족=55`, `모두 부족=0`.
  금액·기간·모두 부족 비율은 원 집계 값을 그대로 병행 제공
- 후속 연계 필요도: 공개 가능한 후속 지원 분포의 최빈 선택 비중
- 개선 시급도: 효과 부족 25%, 접근성 부족 20%, 지원 부족 20%, 신청 후 이탈 15%,
  개선 요구 집중도 10%, 낮은 완료율 10%. 공개 가능한 항목만 재정규화하지만 효과·
  접근성·지원 적정성 핵심 3점수가 모두 있어야 계산

가중치와 임계값은 모두 `ScoringConfig` 한 곳에서 변경한다. 운영에서 변경할 때는
설정 버전과 변경 사유를 함께 관리하고 회귀 테스트 기대값을 갱신해야 한다.

### 권고와 신뢰도 규칙

권고는 `maintain`, `expand`, `simplify`, `retarget`, `extend_duration`,
`increase_amount`, `connect_followup`, `redesign`, `insufficient_data`를 지원한다.
지원기간/금액 부족률 40% 이상이면서 상대 항목보다 10%p 이상 높을 때 기간 연장 또는
금액 확대를 검토하고, 장벽·후속 수요의 공개 최빈 비중이 각각 35%, 45% 이상일 때
절차/대상 또는 후속 연계를 검토한다. 효과·접근성·적정성이 모두 45점 이하이면
전반 개편 검토가 우선한다. 하나의 주 권고와 함께 조건을 만족한 보조 권고를 반환한다.

신뢰도는 응답자 수, 이용기록 대비 응답률, completed 단계 응답 비중, 억제 셀 유무를
함께 사용한다. 기본 high는 응답자 30명 이상·응답률 60% 이상·완료 응답 비중 40%
이상·억제 셀 없음, medium은 응답자 10명 이상·응답률 30% 이상이며 나머지는 low다.
최소 집계 인원 미달 또는 핵심 점수 산출 불가이면 `insufficient_data`이고 모든 점수와
구체 권고를 숨긴다.

정책 카테고리는 카탈로그의 유효한 `category`를 우선 사용하고, 현재 6개 정책은
`ScoringConfig.categories` 매핑을 사용한다. 분류가 없으면 `기타`다. 전체 순위와
동일 카테고리 안의 순위를 함께 제공하되, 규모가 다른 정책의 단순 순위는 효과성
판정이 아니라 추가 검토 순서를 돕는 참고값이다.

### React 화면과 export

행정 대시보드는 효과·접근성·지원 적정성·후속 연계·개선 시급도, 신뢰도, 주요 병목,
후속 수요와 주·보조 권고를 표시한다. 카테고리·신뢰도·주 권고·시급도 구간·표본 부족
포함 여부 필터와 시급도 정렬을 제공한다. 문구는 명령형 대신 `검토할 수 있습니다`로
표현하며 자동 의사결정이 아닌 참고자료임을 항상 표시한다.

CSV/JSON은 요청 시 메모리에서 생성하고 서버 파일로 저장하지 않는다. CSV 열은
`policy_id`, `policy_name`, `category`, `respondent_count`, `publicly_available`,
5개 점수, `confidence`, `primary_bottleneck`, `top_followup_need`,
`primary_recommendation`, `secondary_recommendations`다. 사용자 ID·연락처·금융 원문·
자유서술 원문은 조회와 export 모두에 포함하지 않는다.

## 실행과 테스트

```powershell
cd backend
$env:PYTHONUTF8='1'
.\.venv\Scripts\python.exe -m pytest -q tests\app\test_policy_feedback.py
.\.venv\Scripts\python.exe -m pytest -q

cd ..\mobile-app
$env:JAVA_HOME='C:\Program Files\Android\Android Studio\jbr'
.\gradlew.bat test assembleDebug --no-daemon

cd ..\web-dashboard
npm test
npm run build
npm run lint
```

## 외부 연동 교체 지점과 TODO

- 동백전: `RewardProvider`의 운영 구현, 멱등키 전달, webhook/재처리 작업자 필요
- 정책 데이터: `PolicyRepository`의 부산시/온통청년 운영 어댑터와 신청기간 상태
  검증 필요. 현재 신규 기록은 기존 Layer 3 추천 카탈로그만 허용한다.
- 신청 사실: 기관 원장 또는 본인확인 연동 전까지 상태 변경은 로그인 회원의
  자기기록이다. 운영 보상 전에 증빙/행정 상태 동기화가 필요하다.
- Android Navigation, 상태 관리, 정책 상세·내 기록·설문·완료·리워드 화면은 연결했다.
  실제 정책기관 신청 상태 자동동기화와 푸시 알림은 아직 연동하지 않는다.
- 행정 전달: 익명 분석 CSV/JSON 다운로드까지 제공한다. 부산시 시스템으로 자동
  전송하는 운영 연동은 별도 인증·감사로그·스키마 합의 후 구현해야 한다.
