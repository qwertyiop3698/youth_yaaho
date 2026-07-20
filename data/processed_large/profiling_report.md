# Layer 0 결측치 프로파일링 리포트

- 생성 시각: 2026-07-20T12:52:42.267128+00:00
- 행 수: 1500, 컬럼 수: 46

## 컬럼별 요약

| 컬럼 | 그룹 | null% | 0% | unique | 검토필요 | 사유 |
|---|---|---|---|---|---|---|
| 성별 | personal_info | 0.0% | 0.0% | 2 |  |  |
| 연령대 | personal_info | 0.0% | 0.0% | 13 |  |  |
| 직업군 | personal_info | 0.0% | 0.0% | 4 |  |  |
| 직업군상세 | personal_info | 0.0% | 0.0% | 5 |  |  |
| 거주지 시군구 코드 | personal_info | 0.0% | 0.0% | 16 |  |  |
| 근무지 시군구 코드 | personal_info | 0.0% | 0.0% | 16 |  |  |
| 거주지행정동 | personal_info | 0.0% | 0.0% | 42 |  |  |
| 근무지행정동 | personal_info | 0.0% | 0.0% | 42 |  |  |
| 추정가구원수 | personal_info | 0.0% | 0.0% | 4 |  |  |
| 추정월소득 | income | 0.0% | 0.0% | 1131 |  |  |
| 증빙연소득 | income | 0.0% | 59.2% | 606 |  |  |
| 추정 연소득 | income | 0.0% | 2.2% | 1430 |  |  |
| 2년전 추정 연소득 금액 | income | 0.0% | 0.0% | 1449 |  |  |
| 2년내 이직후 소득 증감액 | income | 0.0% | 64.4% | 521 |  |  |
| 총자산평가금액(주택) | asset_housing | 0.0% | 0.0% | 1474 | ⚠️ | known sentinel 값 발견; 통계적 이상치(IQR) 후보 발견 |
| 순자산평가금액(주택) | asset_housing | 0.0% | 0.0% | 1455 | ⚠️ | known sentinel 값 발견; 통계적 이상치(IQR) 후보 발견 |
| 자가거주여부 | asset_housing | 0.0% | 69.3% | 2 |  |  |
| 현 거주지의 아파트여부 | asset_housing | 0.0% | 44.6% | 2 |  |  |
| 현 거주지의 매매가(국토부 실거래가) 또는 공시가격 | asset_housing | 0.0% | 0.0% | 1459 | ⚠️ | known sentinel 값 발견; 통계적 이상치(IQR) 후보 발견 |
| 차량보유(국산/수입) | asset_housing | 0.0% | 54.4% | 3 |  |  |
| 추정 LTV | estimated_model | 0.0% | 84.0% | 76 |  |  |
| 추정DTI | estimated_model | 0.0% | 45.0% | 462 |  |  |
| 신용평점 | estimated_model | 0.0% | 19.6% | 479 |  |  |
| 총대출건수 | loan_card_delinquency | 0.0% | 27.3% | 6 |  |  |
| 신용대출-총대출약정액 | loan_card_delinquency | 0.0% | 61.5% | 564 |  |  |
| 신용대출-총대출잔액 | loan_card_delinquency | 0.0% | 61.5% | 552 |  |  |
| 주택담보대출-총대출약정액 | loan_card_delinquency | 0.0% | 84.0% | 241 |  |  |
| 주택담보대출-총대출잔액 | loan_card_delinquency | 0.0% | 84.0% | 238 |  |  |
| 정책자금대출-총대출약정액 | loan_card_delinquency | 0.0% | 88.2% | 172 |  |  |
| 정책자금대출-총대출잔액 | loan_card_delinquency | 0.0% | 88.2% | 175 |  |  |
| 총 대출 상환금액 (최근 12개월) | loan_card_delinquency | 0.0% | 45.0% | 668 |  |  |
| 최근 12개월 신용카드소비금액 | loan_card_delinquency | 0.0% | 2.2% | 1383 |  |  |
| 최근 12개월 체크카드소비금액 | loan_card_delinquency | 0.0% | 2.2% | 1270 |  |  |
| 최근 12개월 일시불이용금액 | loan_card_delinquency | 0.0% | 2.2% | 1334 |  |  |
| 최근 12개월 할부이용금액 | loan_card_delinquency | 0.0% | 2.2% | 1198 |  |  |
| 최근 12개월 현금서비스이용금액 | loan_card_delinquency | 0.0% | 2.2% | 1142 |  |  |
| 대출연체건수 | loan_card_delinquency | 0.0% | 82.7% | 6 |  |  |
| 카드연체건수 | loan_card_delinquency | 0.0% | 90.9% | 5 |  |  |
| 연체일수 | loan_card_delinquency | 0.0% | 82.7% | 32 |  |  |
| 대출연체금액 | loan_card_delinquency | 0.0% | 82.7% | 249 |  |  |
| 카드연체금액 | loan_card_delinquency | 0.0% | 82.7% | 233 |  |  |
| Thin Filer 여부 | other | 0.0% | 80.4% | 2 |  |  |
| 파산, 개인회생 신청 여부 | other | 0.0% | 97.1% | 2 |  |  |
| 2년내 현거주지평균실거래가 | asset_housing | 0.0% | 0.0% | 1431 | ⚠️ | known sentinel 값 발견; 통계적 이상치(IQR) 후보 발견 |
| 2년내 현거주지평균전세거래가 | asset_housing | 0.0% | 0.0% | 1417 | ⚠️ | known sentinel 값 발견; 통계적 이상치(IQR) 후보 발견 |
| 2년내 직장명이력건수 | life_pattern | 0.0% | 64.1% | 5 |  |  |

## 사람 확인이 필요한 컬럼

- 총자산평가금액(주택)
- 순자산평가금액(주택)
- 현 거주지의 매매가(국토부 실거래가) 또는 공시가격
- 2년내 현거주지평균실거래가
- 2년내 현거주지평균전세거래가
