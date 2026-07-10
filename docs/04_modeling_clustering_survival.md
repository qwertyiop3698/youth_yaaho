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

---

## Layer 2-B: Cox 생존분석 기반 위험 예측

### 타겟(라벨) 설계 — 가장 중요한 방법론적 정직성 포인트

KCB 데이터에는 "정책 신청/수혜/효과" 라벨이 없다. 프록시 타겟을 명시적으로 정의한다.

```python
event = 1 if (연체건수 > 0) or (
    추정DTI >= p75 and 소득증감률 < 0 and 신용평점_하락추정
) else 0

duration = 관측시작 ~ event 발생(또는 관측종료)까지 기간(월)
```

발표 문구: "실제 정책효과 라벨이 없어, MVP 근사치로 이 프록시를 사용했고, 실제 운영 시엔 3~6개월 후 실연체 발생 여부로 교체 가능하도록 설계했다."

### 모델

- **주모델**: Cox 비례위험모형 (`lifelines.CoxPHFitter`) — "위험 진입까지 남은 기간"을 추정해 조기경보 컨셉과 모델 산출물을 정합시킴. Hazard ratio로 "이 요인이 위험 진입 속도를 몇 배 높이는가"를 직접 해석 가능.
- **베이스라인**: 로지스틱 회귀, LightGBM 이진분류. Cox 모델과 AUC/C-index 비교로 방법론 선택의 정당성 확보.

### 데이터 누수 차단 (필수, 코드 레벨 강제)

```python
LEAKAGE_COLUMNS = ['대출연체건수', '카드연체건수', '연체일수', '대출연체금액', '카드연체금액']
assert not any(col in feature_columns for col in LEAKAGE_COLUMNS), \
    "연체 관련 컬럼은 타겟 정의에만 사용, 피처에 포함 금지"
```

### 검증 전략

- **Spatial CV**: 거주지 시군구코드(또는 확보되면 행정동) 기준으로 fold를 나눠 지역 일반화 성능 확인.
- **C-index (Concordance Index)**: 생존모델 표준 평가지표.
- **Calibration plot**: 예측 위험도와 실제 관측 사건 발생률 정렬 확인.
- **Schoenfeld residual test**: Cox 모델의 비례위험 가정 검정. 위반 시 시간의존 Cox 또는 계층화 Cox로 대체.

### 공정성 감사 (Fairness Audit)

- 성별/연령대 서브그룹별 C-index, calibration 차이 비교. 특정 그룹의 시스템적 과대/과소 위험 판정 여부 확인 후 리포트화.

### 설명력

SHAP(TreeExplainer, LightGBM 베이스라인 기준) 또는 Cox hazard ratio로 개인별 top-3 위험 요인 추출 → Layer 4 입력.

### 구현 위치

`layer2b_risk_model/cox_trainer.py`, `layer2b_risk_model/baseline_models.py`, `layer2b_risk_model/spatial_cv.py`, `layer2b_risk_model/fairness_audit.py`, `layer2b_risk_model/shap_explainer.py`

출력: `risk_model.pkl`, `risk_scores.parquet` (person_id, hazard_months, shap_top3 JSON)
