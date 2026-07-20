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
    user_id UUID NULL,
    access_token_hash VARCHAR(64) NULL,
    input_payload JSONB,
    diagnosis_result JSONB,
    explanation_text TEXT NULL,
    explanation_is_llm_generated BOOLEAN NULL,
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

회원 테이블은 bcrypt 비밀번호 해시와 `auth_version`, `refresh_version`을 저장한다.
로그인·로그아웃은 두 버전을 회전해 기존 토큰을 폐기하고, refresh token은 한 번
사용할 때마다 `refresh_version`이 증가해 재사용을 거부한다.

## 마이그레이션

현재 SQLite MVP는 `db.init_db()`가 위 보안 관련 additive 컬럼을 자동 보강한다.
운영 DB로 전환하거나 비가산 변경을 할 때는 Alembic 마이그레이션을 도입해야 한다.

정책 이용 피드백은 기존 분석 테이블과 분리된 `policy_usages`,
`policy_usage_status_history`, `feedback_questions`, `policy_feedback`,
`feedback_answers`, `reward_grants` 테이블을 사용한다. 필드·유일 제약·익명 집계
원칙은 `docs/12_policy_feedback.md`에 정리되어 있다.
