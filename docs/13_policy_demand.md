# 13. 미충족 정책 수요 수집 및 신규 정책 제안 분석

## 정의와 경계

미충족 정책 수요는 현재 신청 가능한 정책으로 충족되지 않은 사용자의 요구다.
실제 신청·이용 경험을 다루는 `feedback`과 분리해 `policy_demand`에 저장하며,
행정 화면에서 두 집계의 규칙 기반 비교 문장만 함께 보여준다. AI/LLM은 사용하지
않고 종료 정책을 검색하거나 자동 재노출하지 않는다.

## Layer 구조

| Layer | 위치 | 책임 |
|---|---|---|
| Domain/Application | `backend/app/policy_demand` | 노출 검증, 설문 검증, 90일 중복 방지, Mock 보상 |
| Infrastructure | `models.py`, `repositories.py` | 응답·리워드 저장, 익명 보호 집계 |
| Analysis | `backend/app/policy_demand_analysis` | 0~100 우선순위, 신뢰도, 행정 권고 |
| Presentation | `policy_demand/router.py`, Android `ui/policydemand`, React `PolicyDemand` | 시민 여정과 관리자 화면 |

## 설문 노출 조건

서버는 로그인 회원이 소유한 추천 세션을 다시 읽고 현재 추천 결과를 재계산한다.

- `no_recommendation`: 추천 정책 0개
- `no_eligible_policy`: 추천은 있으나 신청 가능 정책 없음
- `no_matching_policy`: 선택한 필요영역과 일치하는 신청 가능 정책 없음
- `user_reported_mismatch`: 추천 카드에서 사용자가 “필요한 지원과 다름”을 선택
- `followup_unmatched`: 후속 지원과 연결 가능한 현재 정책 없음

조건이 없거나 다른 회원·익명 세션이면 제출을 거부한다. Android는 서버의
`eligible=true`일 때만 “지금 필요한 지원을 알려주세요” 또는 “찾으시는 지원과
다른가요?” 카드를 표시한다. 게스트 세션에는 회원 전용 수요·리워드 카드를 노출하지
않는다.

## 설문과 저장 데이터

필수 4문항은 필요 지원, 기간, 월 지원규모, 이용 장벽이다. 선택 문항은 함께 필요한
지원과 고용상태다. 어느 선택형 문항에서든 `기타`를 고르면 최대 200자의 기타 의견이
필수이며, 기타 미선택 원문은 거부한다.

`policy_demand_responses`는 내부 `user_id`, 추천 `session_id`, 노출사유, 수요영역,
기간·금액·장벽, 동반 지원, 고용상태, 진단 시점 구·군 코드, 제한 서술,
`form_version`, 제출시각을 저장한다. `demand_reward_grants`는 응답별 보상 금액,
상태, provider 참조를 저장한다. 분석 쿼리는 `other_text`를 선택하지 않는다.

## 중복 보상과 Mock 처리

동일 `user_id + need_area + trigger_reason` 응답은 기본 90일 동안 다시 보상하지 않는다.
기간은 `POLICY_DEMAND_COOLDOWN_DAYS`, 정액 보상은
`POLICY_DEMAND_REWARD_AMOUNT`로 변경한다. 응답의 긍정·부정 여부는 금액에 영향을
주지 않는다. 기존 `RewardProvider`와 `MockRewardProvider`를 재사용하며 실제 동백전
네트워크 API는 구현하지 않는다.

## 익명 집계와 우선순위

기본 최소 공개 인원은 `FEEDBACK_MIN_AGGREGATE_SIZE=5`다. 지원 분야·기간·금액·
장벽·동반지원·노출사유·구군·고용상태·정책 공백 카테고리와 30일/90일 변화를
집계한다. 1~4명 셀은 `count=null, suppressed=true`이며 0으로 바꾸거나 역산하지
않는다.

우선순위는 `DemandScoringConfig`의 다음 기본 가중치를 쓴다.

```text
수요 규모 20% + 전체 집중도 15% + 현재 정책 공백 20%
+ 자격조건 사각지대 15% + 장기 필요 10% + 복수지원 필요 10%
+ 최근 30일 증가 10%
```

공개 수요영역 표본이 5명 미만이면 점수와 구체 권고 없이 `insufficient_data`다.
신뢰도는 공개 응답자 30명 이상이며 최근 추세도 공개 가능하면 high, 10명 이상은
medium, 나머지는 low다. 이 점수는 자동 정책 결정이나 정책 효과 추정치가 아니라
추가 행정 검토 순서를 돕는 참고값이다.

## 행정 권고 규칙

- 정책 부재 집중: `create_new_policy`
- 연령·소득·재직·가구·거주 조건 집중: `broaden_eligibility`
- 31만원 이상 수요 집중: `increase_amount`
- 7개월 이상 수요 집중: `extend_duration`
- 동반지원 수요 집중: `create_package`
- 모집 종료 집중: `reopen_recruitment`
- 신청절차 부담 집중: `simplify_application`

각 기본 임계값은 40~45%이며 `DemandScoringConfig`에서 변경한다. 문구는 “검토할 수
있습니다” 형태로 표시한다.

## API와 export

시민 API는 Bearer JWT, 관리자 API는 기존 `X-API-Key`를 사용한다.

```text
GET  /api/v1/citizen/policy-demand/eligibility
GET  /api/v1/citizen/policy-demand/form
POST /api/v1/citizen/policy-demand/responses
GET  /api/v1/citizen/me/policy-demand-responses
GET  /api/v1/admin/policy-demand-summary
GET  /api/v1/admin/policy-demand-priorities
GET  /api/v1/admin/policy-demand/export?format=csv|json
```

CSV/JSON은 요청 시 메모리에서 생성하며 사용자 ID, 연락처, 금융 원문, 기타 의견
원문을 포함하지 않는다.

## 실제 부산시 전달 전 TODO

- 정책 카테고리·신청 가능 기간·자격조건의 부산시 원장 계약
- 구·군 코드 및 고용상태 통계의 행정 표준 코드 매핑
- 동백전 운영 Provider의 멱등키·webhook·재처리·감사로그
- 수요 목적·보유기간·파기·접근권한에 대한 개인정보 처리 협약
- 우선순위 가중치와 임계값의 담당부서 검토·버전 관리
- 부산시 시스템 자동 전송을 위한 별도 인증 및 승인 절차

