"""공통 백엔드 - DB 레이어 (docs/08_db_schema.md).

2026-07-09 사용자 결정: 해커톤 전 개발단계에서는 PostgreSQL 풀 세팅 없이 로컬
SQLite로 최소 구현한다. `DATABASE_URL` 환경변수만 postgres 커넥션 문자열로
바꾸면 이 파일의 테이블 정의/쿼리 코드는 그대로 재사용된다(SQLAlchemy 사용 이유).

doc08의 JSONB 컬럼은 SQLite에 없으므로 SQLAlchemy의 JSON 타입(TEXT에 직렬화)으로
대체한다 - Postgres로 전환하면 SQLAlchemy가 자동으로 JSONB를 사용하게 된다.
"""
from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import JSON, Boolean, Column, DateTime, Float, Integer, MetaData, String, Table, create_engine, func, inspect
from sqlalchemy.engine import Engine

from . import config  # noqa: F401 - .env를 아래 os.environ.get("DATABASE_URL")보다 먼저 로드

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SQLITE_PATH = _PROJECT_ROOT / "data" / "app.db"

metadata = MetaData()

users_table = Table(
    "users",
    metadata,
    Column("user_id", String, primary_key=True),
    Column("email", String, unique=True, nullable=False),
    Column("password_hash", String, nullable=False),
    Column("birthdate", String, nullable=False),  # YYYY-MM-DD, 자기기재
    Column("dong_code", String),
    # 자기기재(self-declared) 생년월일이지 본인인증이 아니다 - 실제 본인인증 연동 시
    # 이 필드를 true로 전환하면 된다. 지금은 항상 False로 저장한다.
    Column("is_age_verified", Boolean, default=False),
    Column("auth_version", Integer, nullable=False, default=0),
    Column("refresh_version", Integer, nullable=False, default=0),
    Column("created_at", DateTime, server_default=func.now()),
)

kcb_clean = Table(
    "kcb_clean",
    metadata,
    Column("person_id", String, primary_key=True),
    Column("dong_code", String),
    Column("sigungu_code", String),
    Column("domain_indices", JSON),
    Column("cluster_membership", JSON),
    Column("hazard_months", Float),
    Column("shap_top3", JSON),
    Column("created_at", DateTime, server_default=func.now()),
)

citizen_sessions = Table(
    "citizen_sessions",
    metadata,
    Column("session_id", String, primary_key=True),
    # 로그인한 회원이 진단한 경우에만 채워진다 - 익명 진단(비로그인)은 계속 NULL.
    Column("user_id", String),
    # 익명 세션 조회용 비밀 토큰은 원문 대신 SHA-256 해시만 저장한다.
    Column("access_token_hash", String),
    Column("input_payload", JSON),
    Column("diagnosis_result", JSON),
    Column("explanation_text", String),  # 캐싱된 설명문(docs/06: "재요청 시 재호출하지 않음")
    Column("explanation_is_llm_generated", Boolean),  # 캐싱된 설명문이 Claude API 생성인지 SHAP 템플릿 폴백인지
    Column("created_at", DateTime, server_default=func.now()),
)

policy_catalog_table = Table(
    "policy_catalog",
    metadata,
    Column("policy_id", Integer, primary_key=True, autoincrement=True),
    Column("name", String),
    Column("eligibility_rule", JSON),
    Column("unit_cost", Integer),
    Column("budget_cap", Integer),
)

assignment_results_table = Table(
    "assignment_results",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("person_id", String),
    Column("policy_id", Integer),
    Column("delta_risk", Float),
    Column("eligibility_confidence", String),
    Column("assigned_at", DateTime, server_default=func.now()),
)

bandit_state_table = Table(
    "bandit_state",
    metadata,
    Column("policy_id", Integer, primary_key=True),
    Column("alpha", Float, default=1.0),
    Column("beta", Float, default=1.0),
    Column("updated_at", DateTime, server_default=func.now()),
)

data_profiling_reports_table = Table(
    "data_profiling_reports",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("run_at", DateTime, server_default=func.now()),
    Column("report", JSON),
)


def get_database_url() -> str:
    return os.environ.get("DATABASE_URL", f"sqlite:///{DEFAULT_SQLITE_PATH}")


def create_db_engine(database_url: str | None = None) -> Engine:
    database_url = database_url or get_database_url()
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, connect_args=connect_args)


def init_db(engine: Engine) -> None:
    """주의: create_all()은 마이그레이션 도구가 아니다 - 없는 테이블은 만들지만,
    이미 존재하는 테이블에 새 컬럼이 추가돼도 기존 테이블은 알아서 ALTER하지
    않는다(조용히 무시함). 그래서 로컬 SQLite 파일(data/app.db)을 오래 재사용하면
    스키마가 코드보다 뒤처져서 "no column named ..." 같은 런타임 에러가 날 수 있다
    (2026-07-10 실제로 겪음: user_id 컬럼 추가 전에 만들어진 app.db가 계속
    재사용되다가 /diagnose에서 발생). pytest는 매번 tmp_path에 새 파일을 만들어서
    이 문제를 겪지 않는다. 현재 보안 관련 nullable/additive 컬럼은 아래의 제한된
    SQLite migration이 보강한다. 그 밖의 스키마 변경이 잦아지면 Alembic 같은 실제
    마이그레이션 도구를 도입해야 한다."""
    # 독립 피드백 Infrastructure 테이블을 공용 metadata에 등록한다. 로컬 import는
    # db.metadata를 참조하는 models 모듈과의 순환 import를 피하기 위함이다.
    from .feedback import models as _feedback_models  # noqa: F401
    from .feedback.repositories import seed_feedback_questions
    from .policy_demand import models as _policy_demand_models  # noqa: F401

    metadata.create_all(engine)
    _migrate_legacy_sqlite_schema(engine)
    seed_feedback_questions(engine)


def _migrate_legacy_sqlite_schema(engine: Engine) -> None:
    """기존 데모 SQLite DB에 안전한 nullable 컬럼을 보강한다.

    `create_all()`은 기존 테이블을 변경하지 않으므로, 앱 업데이트 뒤에도 예전
    `data/app.db`를 그대로 쓰면 진단/탈퇴가 즉시 실패할 수 있다. 해커톤 시연에서
    필요한 additive migration만 명시적으로 수행하고 데이터 삭제는 하지 않는다.
    """
    if engine.dialect.name != "sqlite":
        return

    additions = {
        "users": {
            "dong_code": "VARCHAR",
            "is_age_verified": "BOOLEAN DEFAULT 0",
            "created_at": "DATETIME",
            "auth_version": "INTEGER NOT NULL DEFAULT 0",
            "refresh_version": "INTEGER NOT NULL DEFAULT 0",
        },
        "citizen_sessions": {
            "user_id": "VARCHAR",
            "access_token_hash": "VARCHAR",
            "explanation_text": "TEXT",
            "explanation_is_llm_generated": "BOOLEAN",
            "created_at": "DATETIME",
        },
    }
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table_name, columns in additions.items():
            if table_name not in existing_tables:
                continue
            existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
            for column_name, sql_type in columns.items():
                if column_name not in existing_columns:
                    conn.exec_driver_sql(
                        f'ALTER TABLE "{table_name}" ADD COLUMN "{column_name}" {sql_type}'
                    )
