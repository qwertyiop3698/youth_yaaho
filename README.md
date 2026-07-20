# 청년야호 / Y-SAFE

부산 청년의 경제상태를 **프록시 위험점수**로 진단하고, 정책 대상 영역과 예산
제약을 함께 고려하는 DIVE 2026 해커톤 프로토타입입니다.

> 현재 저장소의 `synthetic_large.csv`와 `processed_large/`는 파이프라인·UI 검증용
> 합성 데이터입니다. 실제 성능·정책 효과를 의미하지 않습니다. 대회 당일 제공되는
> KCB 데이터로 Layer 0~3을 다시 실행한 결과만 최종 발표 지표로 사용해야 합니다.

## 구성

- `backend/`: FastAPI, 데이터 정제·피처·GMM·이진 위험모델·LP·설명 폴백
- `web-dashboard/`: 행정 담당자용 React 대시보드(집계 데이터만 표시)
- `mobile-app/`: 시민용 Android Compose 앱
- `docs/`: 설계와 데이터 처리 근거

정책을 실제 신청·이용한 회원의 단계별 경험을 수집하고 최소 5명 기준으로 익명
집계하는 피드백 기반 코드가 추가되어 있습니다. 상태 전이, 6개 핵심 문항, Mock
리워드, 관리자 집계, Android UI 기반과 설정 방법은
[`docs/12_policy_feedback.md`](docs/12_policy_feedback.md)를 참고하세요.

현재 MVP는 SQLite와 프로세스 메모리 캐시를 사용합니다. PostgreSQL/Redis와 Cox
생존분석은 운영·패널데이터 확보 이후 확장 항목이며 현재 구현 기능이 아닙니다.

## 빠른 실행

### 백엔드

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\pip.exe install -r requirements.txt
Copy-Item .env.example .env
# .env의 JWT_SECRET_KEY, ADMIN_API_KEY, INTERNAL_API_KEY를 안전한 값으로 설정
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

`data/processed/`가 있으면 실제/로컬 재실행 산출물을 사용하고, 없으면 저장소에
포함된 `data/processed_large/` 합성 데모 산출물을 자동 사용합니다.

### 웹

```powershell
cd web-dashboard
npm ci
Copy-Item .env.example .env
npm run dev
```

관리자 API 키는 브라우저 저장소에 영구 저장되지 않으므로 새로고침 후 다시 입력합니다.

### Android

```powershell
cd mobile-app
.\gradlew.bat test
.\gradlew.bat assembleDebug
```

debug 빌드만 로컬 HTTP 백엔드를 허용합니다. release 빌드는 HTTPS가 필요합니다.
release APK를 만들기 전 `mobile-app/local.properties`에
`RELEASE_API_BASE_URL=https://배포주소/`를 설정해야 하며, 없으면 빌드가 실패합니다.
로그인 토큰은 Android Keystore AES-GCM으로 암호화해 저장하며, 익명 진단 결과는
세션 UUID 외에 별도 비밀 토큰이 있어야 다시 조회할 수 있습니다.

## 검증

```powershell
cd backend
$env:PYTHONUTF8='1'
.\.venv\Scripts\python.exe -m pytest -q

cd ..\web-dashboard
npm run build
npm run lint
```

## 발표 시 지켜야 할 표현

- `risk_probability`는 미래 위기를 실증한 확률이 아니라 현재 프록시 라벨 기반 점수입니다.
- `expected_effect`는 인과적 정책 효과가 아니라 위험·정책 영역·가정 prior를 조합한 실험적 적합도입니다.
- Thompson Sampling 결과는 실제 정책 성과가 아닌 수렴 동작 검증용 시뮬레이션입니다.
- 미확인 자격조건은 신청 가능으로 단정하지 않고 실제 공고 확인이 필요합니다.
