# 04. 모델링 — 유형 발견(Layer 2-A) & 위험 예측(Layer 2-B)

## Layer 2-A: GMM 소프트 클러스터링

### 방법론

도메인 지수 5종 벡터에 Gaussian Mixture Model 적용.

```
p(x) = Σ_{k=1}^{K} π_k · N(x | μ_k, Σ_k)
```

- **K-means가 아니라 GMM을 쓰는 이유**: 소프트 할당(responsibility, γ_ik)으로 한 사람이 여러 위험유형에 걸쳐 있는 현실(예: 주거비압박 0.6 + 부채과부하 0.4)을 확률로 표현 가능. 이 확률이 Layer 3 LP의 정책 포트폴리오 가중치로 직결됨.
- **K(유형 개수) 결정**: K=3~10 범위에서 BIC와 실루엣 스코어를 동시 계산, elbow 지점에서 K 확정. 임의로 6개 정하지 않고 통계적으로 검증한다.
- **공분산 구조**: full vs diagonal 비교, BIC로 최적 구조 선택.

### 해석 및 라벨링

- 각 클러스터 중심(μ_k)의 5차원 프로파일을 레이더 차트로 시각화
- 사전 가설(6개 도메인 유형: 주거비압박형/부채과부하형/소득공백형/소비유동성위험형/Thin Filer형/자산형성가능형)과 실제 클러스터 결과를 대조. 일치/불일치 모두 발표 소재로 기록.

### 구현 위치

`layer2a_clustering/gmm_trainer.py`, `layer2a_clustering/k_selection.py` (BIC/실루엣 탐색), `layer2a_clustering/cluster_interpreter.py` (레이더차트 데이터 생성)

출력: `cluster_model.pkl`, `cluster_membership.parquet` (person_id별 K개 클러스터 소속확률)

### 위험 궤적 시뮬레이션 (2026-07-20 추가, 차별화 항목)

KCB 데이터가 단일 시점 스냅샷이라 실제 관측된 유형 전이(A유형→B유형)가 없다 -
Cox가 duration을 관측할 수 없어 폐기된 것과 동일한 이유. 그래서 실측 대신
**클러스터 중심 간 거리(가까울수록 전이 가능성 높음) + 평균위험 변화 방향**으로
전이확률행렬을 구성하고, Thompson Sampling과 동일하게 "실제 운영 전 검증용
시뮬레이션"임을 응답에 항상 명시한다(`is_simulation`/`simulation_disclaimer`).

- 무개입 시나리오: 위험이 더 높은 이웃 클러스터로 전이가 편향됨("위험 심화" 가정)
- 개입 시나리오: policy_catalog 평균 `effectiveness_prior`만큼 반대 방향(위험 감소)으로 편향
- 두 시나리오를 6-step(가상 개월) 궤적으로 비교해 정책 개입의 기대 효과를 시각화

**구현 위치**: `layer2a_clustering/risk_trajectory_simulator.py`. Layer2-A(클러스터
프로파일/소속확률)와 Layer2-B(위험확률)가 둘 다 필요해 실제 계산은 두 산출물이
합류하는 Layer3 배치(`layer3_optimization/run.py`)에서 수행하고, 결과는
`optimization_report.json`의 `trajectory_simulation` 키에 저장한다. API:
`GET /api/v1/admin/risk-trajectory-outlook`.

---

## Layer 2-B: 프록시 라벨 기반 이진 위험모델

### 타겟(라벨) 설계 — 가장 중요한 방법론적 정직성 포인트

KCB 데이터에는 "정책 신청/수혜/효과" 라벨이 없다. 프록시 타겟을 명시적으로 정의한다.

```python
event = 1 if (연체건수 > 0) or (
    추정DTI >= p75 and 소득증감률 < 0 and 신용평점_하락추정
) else 0

```

현재 KCB 샘플은 한 시점의 크로스섹션이며 사건까지 남은 기간(duration)을 관측할
수 없습니다. 따라서 이 값은 미래 사건 확률이나 인과적 정책효과가 아니라 현재
프록시 조건을 분류한 점수입니다. 실제 운영 시에는 3~6개월 후 사건 라벨과 반복
관측 데이터를 확보한 뒤 재학습해야 합니다.

### 모델

- **후보 모델**: 로지스틱 회귀와 LightGBM 이진분류.
- **선택 기준**: held-out PR-AUC가 높은 모델을 선택하고 확률 보정을 적용합니다.
- Cox 인터페이스는 패널데이터 확보 이후 확장용 스텁이며 현재 기능으로 발표하지 않습니다.

### 데이터 누수 차단 (필수, 코드 레벨 강제)

```python
LEAKAGE_COLUMNS = ['대출연체건수', '카드연체건수', '연체일수', '대출연체금액', '카드연체금액']
assert not any(col in feature_columns for col in LEAKAGE_COLUMNS), \
    "연체 관련 컬럼은 타겟 정의에만 사용, 피처에 포함 금지"
```

### 검증 전략

- **Spatial CV**: 거주지 시군구코드(또는 확보되면 행정동) 기준으로 fold를 나눠 지역 일반화 성능 확인.
- **PR-AUC/AUC-ROC**: 클래스 불균형을 고려해 양성비율 baseline과 함께 제시.
- **Calibration plot**: 예측 위험도와 실제 관측 사건 발생률 정렬 확인.

### 공정성 감사 (Fairness Audit)

- 성별/연령대 서브그룹별 AUC/PR-AUC 차이 비교. 특정 그룹의 시스템적 과대/과소 위험 판정 여부 확인 후 리포트화.

### 공정성 보정 (2026-07-20 추가, 차별화 항목)

AUC는 threshold-independent라 그룹별 확률 재보정(recalibration)으로는 AUC 격차가
줄지 않는다(그룹별 단조변환은 그룹 내부 순위/AUC를 그대로 보존하기 때문). 대신
실제로 쓰이는 단일 임계값 지점 - `/policy-gaps`의 `risk_threshold`(기본 0.6,
"고위험" 판정 기준) - 에 **성별별 equalized-odds 보정임계값**을 적용해 감사에서
그치지 않고 실제로 격차를 줄인다(Hardt et al. 2016 후처리 공정성 기법의 근사
구현). 기본임계값에서의 전체 TPR을 목표로, 각 그룹이 그 TPR에 가장 가까워지는
임계값을 그룹별 ROC 곡선에서 찾는다. 표본 부족 그룹은 기본임계값을 그대로
유지한다(fairness_audit.py와 동일한 방어 원칙).

`risk_model_report.json`의 `fairness_correction`에 그룹별 보정임계값과 보정
전/후 TPR 격차(`evaluation.before_tpr_gap`/`after_tpr_gap`)가 함께 저장된다.
`/policy-gaps`가 `risk_threshold`를 보정 기준선(기본 0.6)과 동일하게 요청하면
자동 적용되고, 다르면 보정값이 그 임계값에 맞춰 계산된 게 아니므로 단일
임계값으로 자동 폴백한다.

**구현 위치**: `layer2b_risk_model/fairness_correction.py`

### 설명력

SHAP(TreeExplainer, LightGBM 기준)으로 개인별 top-3 위험 요인 추출 → Layer 4 입력.

### 위험지도 공간적 자기상관 (2026-07-20 추가, 차별화 항목)

지역 위험지도가 "그냥 색칠"이 아니라 통계적으로 유의미한 공간적 군집(hotspot)인지
검정한다. Global Moran's I로 "위험점수가 공간적으로 우연이 아니게 몰려 있는가"를,
Local Moran's I(LISA)로 "어느 지역이 hotspot(HH)/coldspot(LL)/이상치(HL, LH)인가"를
판정한다. 둘 다 정규성을 가정하지 않는 순열검정으로 p-value를 산출한다.

부산 16개 시군구의 인접관계는 손으로 하드코딩하지 않고 `web-dashboard/public/
busan_districts.geojson`(지도가 쓰는 것과 동일한 소스) 폴리곤에서 정점 공유 여부로
직접 유도한다. 영도구처럼 육지 경계가 없는 섬 지역은 최근접 지역에 연결해 공간가중치
행렬에 고립된(이웃 0개) 행이 생기지 않게 한다.

**구현 위치**: `layer2b_risk_model/spatial_autocorrelation.py`. API:
`GET /api/v1/admin/risk-map?level=sigungu` 응답의 `spatial_stats`/`regions[].lisa_quadrant`.

### 구현 위치

`layer2b_risk_model/cox_trainer.py`, `layer2b_risk_model/baseline_models.py`, `layer2b_risk_model/spatial_cv.py`, `layer2b_risk_model/fairness_audit.py`, `layer2b_risk_model/fairness_correction.py`, `layer2b_risk_model/spatial_autocorrelation.py`, `layer2b_risk_model/shap_explainer.py`

출력: `risk_model.pkl`, `risk_scores.parquet` (event_probability, shap_top3 JSON)
