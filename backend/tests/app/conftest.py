"""backend/app 테스트 공용 픽스처.

실제 파이프라인 run.py 스크립트(Layer0~3)를 합성 원본 KCB 유사 CSV(n=150)에
그대로 돌려서 실제 학습된 cluster_model.pkl/risk_model.pkl을 만든다. sample.csv
(5행)로는 Layer2~3이 표본부족으로 전부 skip되므로, API가 "모델이 실제로 있을 때"
어떻게 동작하는지 검증하려면 이렇게 합성 데이터로 진짜 파이프라인을 돌려야 한다.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app import db
from app.auth import require_admin_api_key, require_internal_api_key
from app.dependencies import get_engine
from app.main import app
from app.services.pipeline_store import PipelineStore, get_pipeline_store
from pipeline.layer0_data_contract import run as layer0_run
from pipeline.layer1_features import run as layer1_run
from pipeline.layer2a_clustering import run as layer2a_run
from pipeline.layer2b_risk_model import run as layer2b_run
from pipeline.layer3_optimization import run as layer3_run


def _generate_synthetic_raw_kcb(n: int = 150, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    sigungu_codes = [26260, 26230, 26350, 26320, 26440]
    return pd.DataFrame(
        {
            "성별": rng.choice([1, 2], n),
            "연령대": rng.choice([20, 25, 30, 35, 40], n),
            "직업군": rng.choice([420, 910], n),
            "거주지 시군구 코드": rng.choice(sigungu_codes, n),
            "근무지 시군구 코드": rng.choice(sigungu_codes, n),
            "추정월소득": rng.uniform(1500, 5000, n).round(0),
            "증빙연소득": rng.choice([0, 1], n) * rng.uniform(1000, 4000, n),
            "추정 연소득": rng.uniform(15000, 60000, n),
            "2년전 추정 연소득 금액": rng.uniform(15000, 60000, n),
            "총자산평가금액(주택)": rng.uniform(30000, 300000, n),
            "순자산평가금액(주택)": rng.uniform(20000, 280000, n),
            "자가거주여부": rng.choice([0, 1], n),
            "현 거주지의 아파트여부": rng.choice([0, 1], n),
            "현 거주지의 매매가(국토부 실거래가) 또는 공시가격": rng.uniform(30000, 400000, n),
            "차량보유(국산/수입)": rng.choice([0, 1, 2], n),
            "추정 LTV": rng.uniform(0, 80, n),
            "추정DTI": rng.uniform(0, 60, n),
            "신용평점": rng.uniform(400, 950, n),
            "총대출건수": rng.integers(0, 6, n),
            "신용대출-총대출약정액": rng.uniform(0, 30000, n),
            "신용대출-총대출잔액": rng.uniform(0, 30000, n),
            "주택담보대출-총대출약정액": rng.uniform(0, 200000, n),
            "주택담보대출-총대출잔액": rng.uniform(0, 200000, n),
            "정책자금대출-총대출약정액": rng.uniform(0, 5000, n),
            "정책자금대출-총대출잔액": rng.uniform(0, 5000, n),
            "총 대출 상환금액 (최근 12개월)": rng.uniform(0, 5000, n),
            "최근 12개월 신용카드소비금액": rng.uniform(0, 20000, n),
            "최근 12개월 체크카드소비금액": rng.uniform(0, 10000, n),
            "최근 12개월 일시불이용금액": rng.uniform(0, 15000, n),
            "최근 12개월 할부이용금액": rng.uniform(0, 5000, n),
            "최근 12개월 현금서비스이용금액": rng.uniform(0, 2000, n),
            "대출연체건수": rng.integers(0, 2, n),
            "카드연체건수": rng.integers(0, 2, n),
            "연체일수": rng.integers(0, 30, n),
            "대출연체금액": rng.uniform(0, 500, n),
            "카드연체금액": rng.uniform(0, 500, n),
            "Thin Filer 여부": rng.choice([0, 1], n, p=[0.9, 0.1]),
            "파산, 개인회생 신청 여부": rng.choice([0, 1], n, p=[0.98, 0.02]),
            "2년내 현거주지평균실거래가": rng.uniform(30000, 400000, n),
            "2년내 현거주지평균전세거래가": rng.uniform(10000, 200000, n),
            "2년내 직장명이력건수": rng.integers(0, 3, n),
            "2년내 이직후 소득 증감액": rng.normal(0, 500, n),
        }
    )


@pytest.fixture(scope="session")
def pipeline_output_dir(tmp_path_factory) -> "Path":  # noqa: F821
    """합성 KCB 데이터로 Layer0~3을 실제로 돌려 산출물 디렉토리를 만든다(세션 스코프 -
    여러 테스트가 재사용해 매번 몇 초씩 걸리는 파이프라인 재실행을 피한다)."""
    tmp_path = tmp_path_factory.mktemp("pipeline_output")
    raw_csv_path = tmp_path / "raw.csv"
    _generate_synthetic_raw_kcb().to_csv(raw_csv_path, index=False, encoding="utf-8-sig")

    output_dir = tmp_path / "processed"
    layer0_run.run(raw_csv_path, output_dir)
    layer1_run.run(output_dir / "clean_dataset.parquet", output_dir)
    layer2a_run.run(output_dir / "featured_dataset.parquet", output_dir)
    layer2b_run.run(output_dir / "featured_dataset.parquet", output_dir)
    layer3_run.run(
        output_dir / "featured_dataset.parquet",
        output_dir / "risk_scores.parquet",
        layer3_run.DEFAULT_POLICY_CATALOG,
        output_dir,
    )
    return output_dir


@pytest.fixture(autouse=True)
def _no_real_claude_calls(monkeypatch):
    """테스트에서 실제 Claude API로 나가지 않도록 기본적으로 폴백(SHAP 템플릿)을
    강제한다. LLM 성공 경로를 검증하는 테스트는 이 fixture를 monkeypatch로
    오버라이드해서 explanation_agent.generate_explanation을 직접 모킹한다."""
    from pipeline.layer4_explanation import explanation_agent

    def _raise(*args, **kwargs):
        raise RuntimeError("테스트 환경에서는 실제 Claude API를 호출하지 않습니다.")

    monkeypatch.setattr(explanation_agent, "generate_explanation", _raise)


@pytest.fixture(autouse=True)
def _no_real_youthcenter_calls(monkeypatch):
    """테스트에서 실제 온통청년 API로 나가지 않도록 기본적으로 url=None 폴백을
    강제한다(네트워크 의존/느림/키 유출 방지). 개별 조회 동작을 검증하는
    테스트는 이 fixture를 monkeypatch로 오버라이드해서 직접 검증한다."""
    from app.services import youthcenter_service

    monkeypatch.setattr(youthcenter_service, "get_policy_url", lambda plcy_no: None)
    monkeypatch.setattr(youthcenter_service, "search_policies_by_region", lambda zip_cd: [])


@pytest.fixture()
def client(pipeline_output_dir, tmp_path):
    """산출물이 준비된 PipelineStore + 임시 SQLite로 앱을 띄운 TestClient."""
    store = PipelineStore(data_dir=pipeline_output_dir, policy_catalog_path=layer3_run.DEFAULT_POLICY_CATALOG)
    engine = db.create_db_engine(f"sqlite:///{tmp_path / 'test_app.db'}")
    db.init_db(engine)

    app.dependency_overrides[get_pipeline_store] = lambda: store
    app.dependency_overrides[get_engine] = lambda: engine
    # admin/internal 인증은 별도 테스트(test_admin_internal_auth.py)에서 검증하므로
    # 나머지 라우터 테스트에서는 우회한다.
    app.dependency_overrides[require_admin_api_key] = lambda: None
    app.dependency_overrides[require_internal_api_key] = lambda: None

    with TestClient(app) as test_client:
        test_client.engine = engine  # 회원 관련 테스트에서 DB를 직접 조작/조회할 때 사용
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture()
def client_with_external_dir(pipeline_output_dir, tmp_path):
    """client 픽스처와 동일하지만 external_data_dir(생활인구 등)을 호출부가 직접
    지정할 수 있는 팩토리. 실제 저장소의 data/external/에 있는 파일에 암묵적으로
    의존하지 않고, 조인 성공/실패/모호(파일 0개 또는 2개 이상) 각 경우를 결정적으로
    테스트하기 위함."""
    created: list[TestClient] = []

    def _make(external_data_dir: Path) -> TestClient:
        store = PipelineStore(
            data_dir=pipeline_output_dir,
            policy_catalog_path=layer3_run.DEFAULT_POLICY_CATALOG,
            external_data_dir=external_data_dir,
        )
        engine = db.create_db_engine(f"sqlite:///{tmp_path / f'test_app_{len(created)}.db'}")
        db.init_db(engine)

        app.dependency_overrides[get_pipeline_store] = lambda: store
        app.dependency_overrides[get_engine] = lambda: engine
        app.dependency_overrides[require_admin_api_key] = lambda: None
        app.dependency_overrides[require_internal_api_key] = lambda: None

        test_client = TestClient(app)
        test_client.__enter__()
        created.append(test_client)
        return test_client

    yield _make

    for test_client in created:
        test_client.__exit__(None, None, None)
    app.dependency_overrides.clear()


@pytest.fixture()
def empty_client(tmp_path):
    """산출물이 하나도 없는(Layer1~3 미실행) 상태의 앱 - 방어적 응답 확인용."""
    store = PipelineStore(data_dir=tmp_path / "empty", policy_catalog_path=layer3_run.DEFAULT_POLICY_CATALOG)
    engine = db.create_db_engine(f"sqlite:///{tmp_path / 'empty_app.db'}")
    db.init_db(engine)

    app.dependency_overrides[get_pipeline_store] = lambda: store
    app.dependency_overrides[get_engine] = lambda: engine
    app.dependency_overrides[require_admin_api_key] = lambda: None
    app.dependency_overrides[require_internal_api_key] = lambda: None

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
