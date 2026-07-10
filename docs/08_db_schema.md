# 08. DB 스키마

```sql
-- 원본 결측처리 완료 데이터 (Layer 0~2 산출물)
CREATE TABLE kcb_clean (
    person_id UUID PRIMARY KEY,
    dong_code VARCHAR(10),
    sigungu_code VARCHAR(10),
    domain_indices JSONB,
    cluster_membership JSONB,
    hazard_months FLOAT,
    shap_top3 JSONB,
    created_at TIMESTAMP DEFAULT now()
);

-- 시민 진단 세션 (앱)
CREATE TABLE citizen_sessions (
    session_id UUID PRIMARY KEY,
    input_payload JSONB,
    diagnosis_result JSONB,
    created_at TIMESTAMP DEFAULT now()
);

-- 정책 카탈로그
CREATE TABLE policy_catalog (
    policy_id SERIAL PRIMARY KEY,
    name VARCHAR(100),
    eligibility_rule JSONB,
    unit_cost INT,
    budget_cap BIGINT
);

-- LP 배정 결과 (배치 실행 결과 저장)
CREATE TABLE assignment_results (
    id SERIAL PRIMARY KEY,
    person_id UUID REFERENCES kcb_clean(person_id),
    policy_id INT REFERENCES policy_catalog(policy_id),
    assigned_at TIMESTAMP DEFAULT now()
);

-- Thompson Sampling 상태 (정책별 베타분포 파라미터)
CREATE TABLE bandit_state (
    policy_id INT REFERENCES policy_catalog(policy_id),
    alpha FLOAT DEFAULT 1.0,
    beta FLOAT DEFAULT 1.0,
    updated_at TIMESTAMP DEFAULT now()
);

-- 결측치 프로파일링 리포트 (감사용)
CREATE TABLE data_profiling_reports (
    id SERIAL PRIMARY KEY,
    run_at TIMESTAMP DEFAULT now(),
    report JSONB  -- Layer 0 profiler.py 출력 그대로 저장
);
```

## 인덱스 권장

```sql
CREATE INDEX idx_kcb_clean_dong ON kcb_clean(dong_code);
CREATE INDEX idx_kcb_clean_sigungu ON kcb_clean(sigungu_code);
CREATE INDEX idx_assignment_person ON assignment_results(person_id);
```

## 마이그레이션 도구

Alembic 사용 권장 (`backend/alembic/`). 컬럼 추가/변경 시 반드시 마이그레이션 스크립트 작성.
