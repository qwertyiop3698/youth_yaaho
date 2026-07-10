# 10. 웹 대시보드 명세 — "Y-SAFE 대시보드" (React)

## 화면 구성

| 화면 | 기능 |
|---|---|
| 로그인 | 관리자 인증 |
| 종합 현황판 | 부산 전체 청년 1인가구 수, 평균 위험점수, 유형 분포 파이차트 |
| 지역 위험지도 | 행정동/시군구 단위 위험점수 choropleth 지도 (Kakao Map) |
| 유형별 상세 | 클러스터별 프로파일 레이더차트, 인구수, 대표 특성 |
| 정책 사각지대 탐지 | "위험점수 상위 + 자격정책 부족" 그룹 하이라이트 테이블 |
| 예산 시뮬레이터 | 정책별 예산 슬라이더 → LP 재계산 → 커버율 변화 실시간 반영 |
| 밴딧 학습 현황 | Thompson Sampling regret curve, 정책별 효과 추정치 변화 그래프 |
| 리포트 내보내기 | PDF/CSV 다운로드 |

## 기술 스택

| 영역 | 선택 | 비고 |
|---|---|---|
| 프레임워크 | React + Vite | |
| 상태관리 | React Query(서버상태) + Zustand(클라이언트상태) | |
| 지도 | Kakao Map SDK | |
| 차트 | recharts | 레이더/파이/라인차트 |
| 스타일 | Tailwind | |

## 화면-API 매핑

| 화면 | 호출 API |
|---|---|
| 종합 현황판 | `GET /api/v1/admin/overview` |
| 지역 위험지도 | `GET /api/v1/admin/risk-map?level=dong` |
| 유형별 상세 | `GET /api/v1/admin/clusters` |
| 정책 사각지대 | `GET /api/v1/admin/policy-gaps` |
| 예산 시뮬레이터 | `POST /api/v1/admin/simulate-budget` |
| 밴딧 학습 현황 | `GET /api/v1/admin/bandit-status` |

## 프로젝트 구조 제안

```
web-dashboard/
├── src/
│   ├── pages/
│   │   ├── Overview/
│   │   ├── RiskMap/
│   │   ├── Clusters/
│   │   ├── PolicyGaps/
│   │   ├── BudgetSimulator/
│   │   └── BanditStatus/
│   ├── components/
│   ├── hooks/           # React Query 훅
│   └── api/              # API 클라이언트
```
