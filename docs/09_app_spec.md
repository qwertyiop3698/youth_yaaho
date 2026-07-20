# 09. 앱 명세 — "청년야호" (Kotlin Compose)

## 브랜딩

- 앱 이름: **청년야호**
- 서브타이틀: "위기가 오기 전에, 먼저 압니다"
- 톤: 친근하고 캐주얼. 낙인 문구("당신은 고위험군") 절대 금지.

## 화면 구성

| 화면 | 기능 |
|---|---|
| 온보딩 | "청년야호 — 위기가 오기 전에, 먼저 압니다" 슬로건 노출, 서비스 소개, 개인정보 동의, 게스트/로그인 선택 |
| 정보 입력 | 나이, 거주 행정동, 소득구간, 주거형태, 부채여부 등 간단 입력 (슬라이더/버튼 위주 UX, 민감정보 최소화) |
| 진단 결과 | 5개 도메인 지수 레이더차트 + 위험유형 멤버십(%) 시각화 |
| 정책 추천 | 우선순위 top3 정책 카드 (실험적 적합도/자격 확인 상태/신청링크 포함) |
| 왜 추천했는지 | LLM 생성 설명문 (SHAP 요인 기반 자연어) |
| 히스토리 | 현재 세션의 저장된 진단 1건 확인(MVP) |
| 설정 | 로컬 알림 선호, 회원 계정·연결 진단 기록 즉시 삭제 |

## UX 원칙

- 입력 항목 최소화 (3~4개 목표). 실제 운영 시 본인인증 연동으로 입력 없이 자동진단 가능하다는 점을 발표에서 언급할 수 있도록 아키텍처상 확장 가능하게 설계.
- 행동 지향적 문구 사용: "이번 달 먼저 신청하면 좋은 정책" 등.

## 기술 스택

| 영역 | 선택 | 비고 |
|---|---|---|
| UI | Jetpack Compose | |
| 아키텍처 | MVVM + Repository 패턴 | |
| 네트워킹 | Retrofit + OkHttp | |
| 비동기 | Kotlin Coroutines + Flow | |
| 로컬 상태 | DataStore + Android Keystore AES-GCM | 로그인 토큰 암호화 |
| 차트 | Vico 또는 MPAndroidChart | 레이더차트 지원 확인 필요 |
| 인증 | 회원 JWT 또는 익명 세션ID + 비밀 토큰 | UUID 단독 조회 금지 |

## 화면-API 매핑

| 화면 | 호출 API |
|---|---|
| 정보 입력 → 진단 결과 | `POST /api/v1/citizen/diagnose` |
| 정책 추천 | `GET /api/v1/citizen/{session_id}/recommendations` + 익명 `X-Session-Token` |
| 설명 문구 | `GET /api/v1/citizen/{session_id}/explanation` + 익명 `X-Session-Token` |
| 히스토리 | `GET /api/v1/citizen/{session_id}/history` + 익명 `X-Session-Token` |

## 프로젝트 구조 제안

```
mobile-app/
├── app/src/main/java/.../
│   ├── ui/
│   │   ├── onboarding/
│   │   ├── diagnose/
│   │   ├── result/
│   │   ├── recommendation/
│   │   ├── history/
│   │   └── settings/
│   ├── data/
│   │   ├── api/          # Retrofit 서비스 인터페이스
│   │   └── repository/
│   ├── domain/           # 모델, usecase
│   └── viewmodel/
```
