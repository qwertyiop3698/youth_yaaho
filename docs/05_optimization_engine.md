# 05. 최적화 엔진 (Layer 3)

## 5-1. LP 기반 예산 배정 (1차, Must)

### 정식화

```
변수:   x_ip ∈ {0,1}   개인 i에게 정책 p 배정 여부
목적:   maximize Σ_i Σ_p (Δrisk_ip · x_ip)
제약1:  Σ_i (cost_p · x_ip) ≤ Budget_p   (정책별 예산 상한)
제약2:  Σ_p x_ip ≤ MaxPolicyPerPerson    (1인당 중복 배정 상한)
제약3:  x_ip ≤ eligibility_ip            (정책 자격조건 충족 여부)
```

- `expected_effect_ip`: 정책 p와 개인 i의 특성 적합도를 나타내는 실험용 휴리스틱 점수. 현재 데이터만으로 정책의 실제 위험 감소량이나 인과효과를 뜻하지 않으며, 그러한 표현으로 노출하지 않는다.
- 구현: `PuLP` (CBC solver).
- 출력: 배정표(person_id, policy_id) + 예산별 커버리지율 + 위험유형별 배정 분포.
- 시각화용 산출물: "예산을 10% 늘리면 커버율이 몇 %p 오르는가" 민감도 분석 데이터 — Y-SAFE 대시보드 예산 시뮬레이터 화면에서 사용.

### 구현 위치

`layer3_optimization/lp_allocator.py`, `layer3_optimization/sensitivity_analysis.py`

## 5-2. Thompson Sampling 기반 지속학습 레이어 (2차, Should — 최대 차별화)

정책 효과(`Δrisk_ip`)는 실제로는 불확실하다. 배정 후 피드백(3개월 후 신용점수 변화, 재연체 여부)으로 정책별 효과 추정치를 베이지안 방식으로 갱신한다.

```python
# 정책 p의 효과를 베타분포로 모델링: θ_p ~ Beta(α_p, β_p)
# 라운드마다:
#   1. 각 정책 p에 대해 θ_p 샘플링
#   2. θ_p가 높은 정책을 우선 배정 (탐색 vs 활용 균형)
#   3. 배정 후 관측된 효과로 사후분포 갱신: 성공 시 α_p += 1, 실패 시 β_p += 1
```

- 실제 라벨이 없으므로 **합성 리워드 함수**로 시뮬레이션: 정책별 사전 정의한 "실제 효과 확률"(예: 월세지원 성공률 0.6)을 숨겨두고, 밴딧이 라운드를 거치며 이 값을 추정해가는 학습곡선(regret curve)을 그려서 제시.
- 발표 시 반드시 "실제 운영 전 검증용 시뮬레이션"이라고 명확히 라벨링 — 과장 금지.
- DailyLog 프로젝트의 기존 Thompson Sampling 구현 재사용 가능.

### 구현 위치

`layer3_optimization/thompson_sampling.py`, `layer3_optimization/synthetic_reward.py`, `layer3_optimization/regret_curve.py`

출력: `bandit_state.json` (정책별 α, β), regret curve 데이터 (Y-SAFE 대시보드 "밴딧 학습 현황" 화면에서 사용)

## 정책 카탈로그 (참고)

| 정책명 | 대상 | 비고 |
|---|---|---|
| 청년월세지원 | 19~34세 무주택 청년 | 월 최대 20만원, 최대 24개월 |
| 머물자리론 | 19~39세 무주택 청년 세대주 | 임차보증금 대출, 이자 차등지원 |
| 청년 중개보수·이사비 지원 | 18~39세 근로 청년 1인가구 | 최대 40만원 |
| 희망신용상담센터 | 18~39세 청년 | 재무상담, 채무조정비용 지원 |
| 부산청년 기쁨두배통장 | 18~39세 근로 청년 | 저축 매칭 지원 |
| 청년디딤돌카드 플러스 | 미취업 청년 | 사회진입활동비 |

(정책 자격조건은 `layer3_optimization/policy_catalog.yaml`로 관리, 실제 자격조건은 부산시 정책 공고 기준으로 업데이트 필요)
