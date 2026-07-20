from sqlalchemy import inspect

from app import db


def test_init_db_adds_security_columns_to_legacy_sqlite(tmp_path):
    engine = db.create_db_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE users (user_id VARCHAR PRIMARY KEY, email VARCHAR UNIQUE NOT NULL, "
            "password_hash VARCHAR NOT NULL, birthdate VARCHAR NOT NULL)"
        )
        conn.exec_driver_sql(
            "CREATE TABLE citizen_sessions (session_id VARCHAR PRIMARY KEY, input_payload JSON, "
            "diagnosis_result JSON)"
        )

    db.init_db(engine)

    inspector = inspect(engine)
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    session_columns = {column["name"] for column in inspector.get_columns("citizen_sessions")}
    assert {"auth_version", "refresh_version", "is_age_verified"} <= user_columns
    assert {"user_id", "access_token_hash", "explanation_text"} <= session_columns
