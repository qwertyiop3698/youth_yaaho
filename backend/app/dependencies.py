"""공통 백엔드 - 공용 의존성(DB 엔진 싱글턴).

FastAPI 라우터에서 Depends(get_engine)으로 주입받는다. 테스트에서는
app.dependency_overrides[get_engine]로 임시 SQLite 파일을 가리키는 엔진으로
교체한다.
"""
from __future__ import annotations

from sqlalchemy.engine import Engine

from . import db

_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = db.create_db_engine()
        db.init_db(_engine)
    return _engine


def reset_engine() -> None:
    global _engine
    _engine = None
