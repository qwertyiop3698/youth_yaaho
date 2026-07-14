# Layer 0 결측치 프로파일링 리포트

- 생성 시각: 2026-07-11T05:23:28.716383+00:00
- 행 수: 1500, 컬럼 수: 46

## 컬럼별 요약

| 컬럼 | 그룹 | null% | 0% | unique | 검토필요 | 사유 |
|---|---|---|---|---|---|---|
| 성별 | personal_info | 0.0% | 0.0% | 2 |  |  |
| 연령대 | personal_info | 0.0% | 0.0% | 13 |  |  |
| 직업군 | personal_info | 0.0% | 0.0% | 4 |  |  |
| 직업군상세 | personal_info | 0.0% | 0.0% | 5 |  |  |
| 거주지 시군구 코드 | personal_info | 0.0% | 0.0% | 6 |  |  |
| 근무지 시군구 코드 | personal_info | 0.0% | 0.0% | 6 |  |  |
| 거주지행정동 | personal_info | 0.0% | 0.0% | 15 |  |  |
| 근무지행정동 | personal_info | 0.0% | 0.0% | 15 |  |  |
| 추정가구원수 | personal_info | 0.0% | 0.0% | 4 |  |  |
| 추정월소득 | income | 0.0% | 0.0% | 1115 |  |  |
| 증빙연소득 | income | 0.0% | 59.8% | 602 |  |  |
| 추정 연소득 | income | 0.0% | 2.1% | 1435 |  |  |
| 2년전 추정 연소득 금액 | income | 0.0% | 0.0% | 1419 |  |  |
| 2년내 이직후 소득 증감액 | income | 0.0% | 64.1% | 516 |  |  |
| 총자산평가금액(주택) | asset_housing | 0.0% | 0.0% | 1462 | ⚠️ | known sentinel 값 발견; 통계적 이상치(IQR) 후보 발견 |
| 순자산평가금액(주택) | asset_housing | 0.0% | 0.0% | 1471 | ⚠️ | known sentinel 값 발견; 통계적 이상치(IQR) 후보 발견 |
| 자가거주여부 | asset_housing | 0.0% | 68.8% | 2 |  |  |
| 현 거주지의 아파트여부 | asset_housing | 0.0% | 45.8% | 2 |  |  |
| 현 거주지의 매매가(국토부 실거래가) 또는 공시가격 | asset_housing | 0.0% | 0.0% | 1431 | ⚠️ | known sentinel 값 발견 |
| 차량보유(국산/수입) | asset_housing | 0.0% | 55.5% | 3 |  |  |
| 추정 LTV | estimated_model | 0.0% | 82.7% | 80 |  |  |
| 추정DTI | estimated_model | 0.0% | 43.1% | 483 |  |  |
| 신용평점 | estimated_model | 0.0% | 16.5% | 481 |  |  |
| 총대출건수 | loan_card_delinquency | 0.0% | 24.5% | 7 |  |  |
| 신용대출-총대출약정액 | loan_card_delinquency | 0.0% | 58.5% | 608 |  |  |
| 신용대출-총대출잔액 | loan_card_delinquency | 0.0% | 58.5% | 596 |  |  |
| 주택담보대출-총대출약정액 | loan_card_delinquency | 0.0% | 82.7% | 260 |  |  |
| 주택담보대출-총대출잔액 | loan_card_delinquency | 0.0% | 82.7% | 259 |  |  |
| 정책자금대출-총대출약정액 | loan_card_delinquency | 0.0% | 89.5% | 158 |  |  |
| 정책자금대출-총대출잔액 | loan_card_delinquency | 0.0% | 89.5% | 156 |  |  |
| 총 대출 상환금액 (최근 12개월) | loan_card_delinquency | 0.0% | 43.1% | 692 |  |  |
| 최근 12개월 신용카드소비금액 | loan_card_delinquency | 0.0% | 2.1% | 1398 |  |  |
| 최근 12개월 체크카드소비금액 | loan_card_delinquency | 0.0% | 2.1% | 1268 |  |  |
| 최근 12개월 일시불이용금액 | loan_card_delinquency | 0.0% | 2.1% | 1322 |  |  |
| 최근 12개월 할부이용금액 | loan_card_delinquency | 0.0% | 2.1% | 1180 |  |  |
| 최근 12개월 현금서비스이용금액 | loan_card_delinquency | 0.0% | 2.1% | 1160 |  |  |
| 대출연체건수 | loan_card_delinquency | 0.0% | 85.8% | 6 |  |  |
| 카드연체건수 | loan_card_delinquency | 0.0% | 92.1% | 6 |  |  |
| 연체일수 | loan_card_delinquency | 0.0% | 85.8% | 31 |  |  |
| 대출연체금액 | loan_card_delinquency | 0.0% | 85.8% | 210 |  |  |
| 카드연체금액 | loan_card_delinquency | 0.0% | 85.8% | 198 |  |  |
| Thin Filer 여부 | other | 0.0% | 83.5% | 2 |  |  |
| 파산, 개인회생 신청 여부 | other | 0.0% | 96.7% | 2 |  |  |
| 2년내 현거주지평균실거래가 | asset_housing | 0.0% | 0.0% | 1396 | ⚠️ | known sentinel 값 발견 |
| 2년내 현거주지평균전세거래가 | asset_housing | 0.0% | 0.0% | 1400 | ⚠️ | known sentinel 값 발견; 통계적 이상치(IQR) 후보 발견 |
| 2년내 직장명이력건수 | life_pattern | 0.0% | 63.9% | 5 |  |  |

## 사람 확인이 필요한 컬럼

- 총자산평가금액(주택)
- 순자산평가금액(주택)
- 현 거주지의 매매가(국토부 실거래가) 또는 공시가격
- 2년내 현거주지평균실거래가
- 2년내 현거주지평균전세거래가
