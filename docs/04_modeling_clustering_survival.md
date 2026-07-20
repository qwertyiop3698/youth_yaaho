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

### 설명력

SHAP(TreeExplainer, LightGBM 기준)으로 개인별 top-3 위험 요인 추출 → Layer 4 입력.

### 구현 위치

`layer2b_risk_model/cox_trainer.py`, `layer2b_risk_model/baseline_models.py`, `layer2b_risk_model/spatial_cv.py`, `layer2b_risk_model/fairness_audit.py`, `layer2b_risk_model/shap_explainer.py`

출력: `risk_model.pkl`, `risk_scores.parquet` (event_probability, shap_top3 JSON)
