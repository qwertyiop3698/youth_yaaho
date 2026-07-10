"""admin/internal 라우터 API 키 인증 테스트 (docs/07 권한분리 원칙).

conftest.py의 client/empty_client fixture는 인증 의존성을 override해서
우회하므로, 여기서는 override 없는 순수 TestClient로 실제 401/503/200 분기를
검증한다.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import db
from app.dependencies import get_engine
from app.main import app
from app.routers import internal
from app.services.pipeline_store import PipelineStore, get_pipeline_store
from pipeline.layer3_optimization import run as layer3_run


@pytest.fixture()
def raw_client(tmp_path, monkeypatch):
    """인증 의존성을 override하지 않은 TestClient. ADMIN/INTERNAL_API_KEY를 설정해둔다."""
    monkeypatch.setenv("ADMIN_API_KEY", "admin-secret")
    monkeypatch.setenv("INTERNAL_API_KEY", "internal-secret")

    store = PipelineStore(data_dir=tmp_path / "empty", policy_catalog_path=layer3_run.DEFAULT_POLICY_CATALOG)
    engine = db.create_db_engine(f"sqlite:///{tmp_path / 'auth_test.db'}")
    db.init_db(engine)

    app.dependency_overrides[get_pipeline_store] = lambda: store
    app.dependency_overrides[get_engine] = lambda: engine

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


class TestAdminAuth:
    def test_missing_key_returns_401(self, raw_client):
        response = raw_client.get("/api/v1/admin/overview")
        assert response.status_code == 401

    def test_wrong_key_returns_401(self, raw_client):
        response = raw_client.get("/api/v1/admin/overview", headers={"X-API-Key": "wrong"})
        assert response.status_code == 401

    def test_correct_key_returns_200(self, raw_client):
        response = raw_client.get("/api/v1/admin/overview", headers={"X-API-Key": "admin-secret"})
        assert response.status_code == 200

    def test_internal_key_does_not_work_on_admin(self, raw_client):
        response = raw_client.get("/api/v1/admin/overview", headers={"X-API-Key": "internal-secret"})
        assert response.status_code == 401


class TestInternalAuth:
    def test_missing_key_returns_401(self, raw_client):
        response = raw_client.post("/api/v1/internal/pipeline/run-optimization")
        assert response.status_code == 401

    def test_admin_key_does_not_work_on_internal(self, raw_client):
        response = raw_client.post(
            "/api/v1/internal/pipeline/run-optimization", headers={"X-API-Key": "admin-secret"}
        )
        assert response.status_code == 401

    def test_correct_key_allows_access(self, raw_client, monkeypatch):
        # 실제 파이프라인(Layer3) 실행/실 데이터 접근을 피하려고 run()을 스텁으로 교체한다.
        monkeypatch.setattr(internal.layer3_run, "run", lambda: {"skipped": True, "reason": "test stub"})

        response = raw_client.post(
            "/api/v1/internal/pipeline/run-optimization", headers={"X-API-Key": "internal-secret"}
        )
        assert response.status_code == 200
        assert response.json()["skipped"] is True


class TestKeyNotConfigured:
    def test_admin_endpoint_fails_closed_when_env_var_unset(self, tmp_path, monkeypatch):
        monkeypatch.delenv("ADMIN_API_KEY", raising=False)
        store = PipelineStore(data_dir=tmp_path / "empty", policy_catalog_path=layer3_run.DEFAULT_POLICY_CATALOG)
        engine = db.create_db_engine(f"sqlite:///{tmp_path / 'unset.db'}")
        db.init_db(engine)
        app.dependency_overrides[get_pipeline_store] = lambda: store
        app.dependency_overrides[get_engine] = lambda: engine

        with TestClient(app) as test_client:
            response = test_client.get("/api/v1/admin/overview", headers={"X-API-Key": "anything"})

        app.dependency_overrides.clear()
        assert response.status_code == 503
