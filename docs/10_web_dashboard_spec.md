# 10. 웹 대시보드 명세 — "Y-SAFE 대시보드" (React)

## 화면 구성

| 화면 | 기능 |
|---|---|
| 로그인 | 관리자 인증 |
| 종합 현황판 | 부산 전체 청년 1인가구 수, 평균 위험점수, 유형 분포 파이차트 |
| 지역 위험지도 | 행정동/시군구 단위 위험점수 choropleth 지도 (Kakao Map) |
| 유형별 상세 | 클러스터별 프로파일 레이더차트, 인구수, 대표 특성 |
| 정책 사각지대 탐지 | "프록시 위험점수 상위 + 정책 미배정" 지역별 집계(개인 ID 미노출) |
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
| 지역 위험지도 | `GET /api/v1/admin/risk-map?level=dong` (sigungu 레벨은 `spatial_stats`/`lisa_quadrant`에 Moran's I 포함) |
| 유형별 상세 | `GET /api/v1/admin/clusters`, `GET /api/v1/admin/risk-trajectory-outlook` (위험 궤적 시뮬레이션) |
| 정책 사각지대 | `GET /api/v1/admin/policy-gaps` (`fairness_corrected`로 성별 equalized-odds 보정임계값 적용) |
| 예산 시뮬레이터 | `POST /api/v1/admin/simulate-budget`, `GET /api/v1/admin/policy-marginal-returns` (정책별 예산 한계수익) |
| 밴딧 학습 현황 | `GET /api/v1/admin/bandit-status` |

### 차별화 기능 4종 (2026-07-20 추가)

기존 화면에 새 화면을 만들지 않고 패널로 얹었다 - 상세 설계는 docs/04, docs/05 참고.

| 기능 | 붙은 화면 | 근거 문서 |
|---|---|---|
| LP 쉐도우 프라이스(정책별 예산 한계수익) | 예산 시뮬레이터 | docs/05 5-3 |
| 위험지도 공간적 자기상관(Moran's I / LISA) | 지역 위험지도 | docs/04 |
| 공정성 감사 → equalized-odds 보정 | 정책 사각지대 | docs/04 |
| 위험 궤적 시뮬레이션(클러스터 간 Markov 전이) | 유형별 상세 | docs/04 |

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
