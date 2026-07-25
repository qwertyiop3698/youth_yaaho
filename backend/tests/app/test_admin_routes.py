from pathlib import Path

import numpy as np
import pandas as pd
import pytest


def _write_population_csv(dir_path: Path, sigungu_to_population: dict[int, int], filename: str = "pop.csv") -> None:
    """실제 부산_인구현황 CSV와 동일한 스키마(소계 행 포함)로 테스트용 인구 파일을 만든다."""
    rows = []
    for code, population in sigungu_to_population.items():
        common = {"시군구명": "구", "세대수": 1, "세대당인구": 1.0, "남자인구수": 1, "여자인구수": 1, "남여비율": 1.0}
        rows.append({"시군구코드": code, "행정동코드": code * 10000, "행정동명": "소계", "거주자인구수": population, **common})
        rows.append({"시군구코드": code, "행정동코드": code * 10000 + 1, "행정동명": "동1", "거주자인구수": population, **common})
    dir_path.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(dir_path / filename, index=False, encoding="utf-8")


class TestOverview:
    def test_returns_summary_stats(self, client):
        response = client.get("/api/v1/admin/overview")
        assert response.status_code == 200
        body = response.json()
        assert body["ready"] is True
        assert body["total_citizens"] == 150
        assert body["avg_risk_probability"] is not None

    def test_not_ready_when_no_pipeline_output(self, empty_client):
        response = empty_client.get("/api/v1/admin/overview")
        assert response.status_code == 200
        assert response.json()["ready"] is False


class TestRiskMap:
    def test_returns_regions_grouped_by_sigungu(self, client):
        response = client.get("/api/v1/admin/risk-map?level=sigungu")
        assert response.status_code == 200
        body = response.json()
        assert body["ready"] is True
        assert len(body["regions"]) > 0
        for region in body["regions"]:
            assert 0.0 <= region["avg_risk_probability"] <= 1.0

    def test_sigungu_level_includes_spatial_stats_and_lisa_quadrant(self, client):
        response = client.get("/api/v1/admin/risk-map?level=sigungu")
        assert response.status_code == 200
        body = response.json()
        assert body["spatial_stats"] is not None
        assert body["spatial_stats"]["skipped"] is False
        assert -1.0 <= body["spatial_stats"]["morans_i"] <= 1.0
        assert 0.0 <= body["spatial_stats"]["p_value"] <= 1.0
        for region in body["regions"]:
            assert region["lisa_quadrant"] in {"HH", "LL", "HL", "LH"}

    def test_uses_official_boundary_adjacency_when_available(self, client):
        """2026-07-25 작업2: data/external/의 공식 행정동 경계가 있으면 그걸 인접행렬
        소스로 써야 한다(기존 web-dashboard 단순화 폴리곤 대신)."""
        response = client.get("/api/v1/admin/risk-map?level=sigungu")
        body = response.json()
        adjacency_source = body["spatial_stats"]["adjacency_source"]
        assert adjacency_source["n_sigungu"] == 16
        assert adjacency_source["n_dong_features"] == 206
        assert "행정동" in adjacency_source["source"]

    def test_regions_include_hotspot_classification(self, client):
        response = client.get("/api/v1/admin/risk-map?level=sigungu")
        body = response.json()
        for region in body["regions"]:
            assert region["hotspot_classification"] in {"hotspot", "coldspot", "not_significant"}
            if region["hotspot_classification"] == "hotspot":
                assert region["lisa_quadrant"] == "HH"
            if region["hotspot_classification"] == "coldspot":
                assert region["lisa_quadrant"] == "LL"


class TestRiskMapJeonseTrend:
    """2026-07-25 DIVE 2026 이종결합 작업3: 전세가변동률/갱신보증금변동률 필드.
    conftest의 합성 원본 KCB는 거주지 시군구 코드로 [26260, 26230, 26350, 26320, 26440]를 쓴다."""

    def test_no_jeonse_trend_file_disables_fields(self, client_with_data_dir, pipeline_output_dir, tmp_path):
        import shutil
        data_dir = tmp_path / "no_jeonse"
        shutil.copytree(pipeline_output_dir, data_dir)
        test_client = client_with_data_dir(data_dir)

        body = test_client.get("/api/v1/admin/risk-map?level=sigungu").json()

        assert body["jeonse_trend_available"] is False
        for region in body["regions"]:
            assert region["jeonse_price_change_rate"] is None
            assert region["renewal_deposit_change_rate"] is None

    def test_jeonse_trend_fields_populated_when_file_present(self, client_with_data_dir, pipeline_output_dir, tmp_path):
        import shutil
        data_dir = tmp_path / "with_jeonse"
        shutil.copytree(pipeline_output_dir, data_dir)
        pd.DataFrame({
            "시군구코드": [26260, 26230, 26350, 26320, 26440],
            "전세가변동률": [-0.05, 0.03, np.nan, -0.12, 0.0],
            "갱신보증금변동률": [0.01, np.nan, 0.02, -0.01, 0.0],
            "표본수": [500, 600, 40, 700, 300],
        }).to_parquet(data_dir / "busan_jeonse_trend.parquet", index=False)
        test_client = client_with_data_dir(data_dir)

        body = test_client.get("/api/v1/admin/risk-map?level=sigungu").json()

        assert body["jeonse_trend_available"] is True
        regions_by_code = {r["region_code"]: r for r in body["regions"]}
        assert regions_by_code["26260"]["jeonse_price_change_rate"] == pytest.approx(-0.05)
        assert regions_by_code["26440"]["jeonse_price_change_rate"] == pytest.approx(0.0)
        # 전세가변동률이 NaN인 26350은 null이어야 함(0으로 채우면 안 됨)
        assert regions_by_code["26350"]["jeonse_price_change_rate"] is None
        assert regions_by_code["26230"]["renewal_deposit_change_rate"] is None


class TestRiskMapPopulationNormalization:
    """2026-07-25 DIVE 2026 이종결합: 부산시 인구현황 외부데이터로 '인구 1천명당
    위험군 수'를 정규화. conftest의 합성 원본 KCB는 거주지 시군구 코드로
    [26260, 26230, 26350, 26320, 26440] 5개를 쓴다(n=150, seed=0 기준 5개 전부 등장)."""

    SIGUNGU_CODES = [26260, 26230, 26350, 26320, 26440]

    def test_no_external_csv_disables_population_fields(self, client_with_external_dir, tmp_path):
        empty_external_dir = tmp_path / "external_empty"
        empty_external_dir.mkdir()
        test_client = client_with_external_dir(empty_external_dir)

        body = test_client.get("/api/v1/admin/risk-map?level=sigungu").json()

        assert body["population_reference_available"] is False
        for region in body["regions"]:
            assert region["population_reference"] is None
            assert region["high_risk_per_1000_population"] is None

    def test_ambiguous_multiple_csv_files_disables_population_fields(self, client_with_external_dir, tmp_path):
        external_dir = tmp_path / "external_ambiguous"
        _write_population_csv(external_dir, {code: 10000 for code in self.SIGUNGU_CODES}, filename="a.csv")
        _write_population_csv(external_dir, {code: 20000 for code in self.SIGUNGU_CODES}, filename="b.csv")
        test_client = client_with_external_dir(external_dir)

        body = test_client.get("/api/v1/admin/risk-map?level=sigungu").json()

        assert body["population_reference_available"] is False

    def test_matched_population_computes_normalized_rate(self, client_with_external_dir, tmp_path):
        external_dir = tmp_path / "external_matched"
        population_by_code = {code: 50000 for code in self.SIGUNGU_CODES}
        _write_population_csv(external_dir, population_by_code)
        test_client = client_with_external_dir(external_dir)

        body = test_client.get("/api/v1/admin/risk-map?level=sigungu&risk_threshold=0.0").json()

        assert body["population_reference_available"] is True
        assert body["population_data_note"] is not None
        assert len(body["regions"]) > 0
        for region in body["regions"]:
            assert region["population_reference"] == 50000.0
            # risk_threshold=0.0 -> 전원이 위험군이므로 n_high_risk == n(해당 지역 표본수)
            assert region["n_high_risk"] == region["n"]
            expected = round(region["n_high_risk"] / 50000.0 * 1000, 4)
            assert region["high_risk_per_1000_population"] == expected
            assert region["population_join_method"] == "sigungu"

    def test_unmatched_region_population_is_null_not_zero(self, client_with_external_dir, tmp_path):
        """생활인구 매칭에 실패한 지역은 0이 아니라 null이어야 한다(미션 원칙)."""
        external_dir = tmp_path / "external_partial"
        codes_with_population = self.SIGUNGU_CODES[:-1]  # 마지막 코드(26440) 하나는 일부러 뺌
        _write_population_csv(external_dir, {code: 30000 for code in codes_with_population})
        test_client = client_with_external_dir(external_dir)

        body = test_client.get("/api/v1/admin/risk-map?level=sigungu").json()

        regions_by_code = {r["region_code"]: r for r in body["regions"]}
        assert regions_by_code["26440"]["population_reference"] is None
        assert regions_by_code["26440"]["high_risk_per_1000_population"] is None
        for code in codes_with_population:
            matched_region = regions_by_code[str(code)]
            assert matched_region["population_reference"] == 30000.0
            assert matched_region["high_risk_per_1000_population"] is not None


class TestClusters:
    def test_returns_cluster_profiles_and_labels(self, client):
        response = client.get("/api/v1/admin/clusters")
        assert response.status_code == 200
        body = response.json()
        assert body["ready"] is True
        assert body["best_k"] is not None
        assert len(body["cluster_profiles"]) == body["best_k"]

    def test_not_ready_when_no_cluster_model(self, empty_client):
        response = empty_client.get("/api/v1/admin/clusters")
        assert response.json()["ready"] is False


class TestPolicyGaps:
    def test_returns_high_risk_without_policy_count(self, client):
        response = client.get("/api/v1/admin/policy-gaps?risk_threshold=0.5")
        assert response.status_code == 200
        body = response.json()
        assert body["ready"] is True
        assert body["n_high_risk"] >= body["n_high_risk_without_policy"]
        assert "person_ids" not in body
        assert isinstance(body["regions"], list)

    def test_fairness_correction_applied_at_matching_baseline_threshold(self, client):
        # risk_model_report.json의 fairness_correction.baseline_threshold는 0.6이므로
        # risk_threshold를 명시하지 않으면(기본 0.6) 매칭되어 보정이 적용돼야 한다.
        response = client.get("/api/v1/admin/policy-gaps")
        assert response.status_code == 200
        body = response.json()
        assert body["ready"] is True
        assert body["fairness_correction_applied"] is True
        assert "before_tpr_gap" in body["fairness_correction_before_after_gap"]

    def test_fairness_correction_falls_back_at_different_threshold(self, client):
        response = client.get("/api/v1/admin/policy-gaps?risk_threshold=0.5")
        assert response.status_code == 200
        body = response.json()
        assert body["fairness_correction_applied"] is False
        assert body["fairness_correction_before_after_gap"] is None

    def test_fairness_correction_can_be_disabled(self, client):
        response = client.get("/api/v1/admin/policy-gaps?fairness_corrected=false")
        assert response.status_code == 200
        body = response.json()
        assert body["fairness_correction_applied"] is False


class TestPolicyCatalog:
    def test_returns_all_policies_with_defaults(self, client):
        response = client.get("/api/v1/admin/policy-catalog")
        assert response.status_code == 200
        body = response.json()
        assert body["ready"] is True
        assert len(body["policies"]) == 6
        names = {p["name"] for p in body["policies"]}
        assert "청년월세지원" in names
        for policy in body["policies"]:
            assert policy["unit_cost"] > 0
            assert policy["budget_cap"] > 0

    def test_available_even_without_pipeline_output(self, empty_client):
        # 정적 설정 파일 기반이라 Layer3 미실행이어도 항상 응답해야 함
        response = empty_client.get("/api/v1/admin/policy-catalog")
        assert response.status_code == 200
        assert response.json()["ready"] is True


class TestSimulateBudget:
    def test_returns_coverage_rates(self, client):
        response = client.post("/api/v1/admin/simulate-budget", json={"policy_budgets": {"청년월세지원": 100_000_000}})
        assert response.status_code == 200
        body = response.json()
        assert body["skipped"] is False
        assert 0.0 <= body["coverage_rate"] <= 1.0
        assert body["coverage_rate_verified_only"] <= body["coverage_rate"] + 1e-9

    def test_returns_marginal_gain_when_not_skipped(self, client):
        response = client.post("/api/v1/admin/simulate-budget", json={"policy_budgets": {}})
        assert response.status_code == 200
        body = response.json()
        assert body["skipped"] is False
        assert body["marginal_gain_per_10pct_budget"] is not None

    def test_skipped_when_no_pipeline_output(self, empty_client):
        response = empty_client.post("/api/v1/admin/simulate-budget", json={"policy_budgets": {}})
        assert response.status_code == 200
        assert response.json()["skipped"] is True


class TestPolicyMarginalReturns:
    def test_returns_ranked_policies(self, client):
        response = client.get("/api/v1/admin/policy-marginal-returns")
        assert response.status_code == 200
        body = response.json()
        assert body["ready"] is True
        assert len(body["policies"]) == 6
        names = {p["policy"] for p in body["policies"]}
        assert "청년월세지원" in names

    def test_not_ready_when_no_pipeline_output(self, empty_client):
        response = empty_client.get("/api/v1/admin/policy-marginal-returns")
        assert response.status_code == 200
        assert response.json()["ready"] is False


class TestRiskTrajectoryOutlook:
    def test_returns_no_intervention_and_intervention_trajectories(self, client):
        response = client.get("/api/v1/admin/risk-trajectory-outlook")
        assert response.status_code == 200
        body = response.json()
        assert body["ready"] is True
        assert body["is_simulation"] is True
        assert "simulation_disclaimer" in body
        assert len(body["no_intervention"]) == body["n_steps"] + 1
        assert len(body["intervention"]) == body["n_steps"] + 1

    def test_not_ready_when_no_pipeline_output(self, empty_client):
        response = empty_client.get("/api/v1/admin/risk-trajectory-outlook")
        assert response.status_code == 200
        assert response.json()["ready"] is False


class TestBanditStatus:
    def test_returns_simulation_disclaimer_and_segment_regret(self, client):
        response = client.get("/api/v1/admin/bandit-status")
        assert response.status_code == 200
        body = response.json()
        assert body["ready"] is True
        assert body["is_simulation"] is True
        assert "simulation_disclaimer" in body
        assert len(body["segment_regret"]) == 3


class TestReportExport:
    def test_csv_export_returns_csv_content_type(self, client):
        response = client.post("/api/v1/admin/report/export?format=csv")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/csv")
        assert "person_id" not in response.text
        assert "n_assignments" in response.text

    def test_json_export(self, client):
        response = client.post("/api/v1/admin/report/export?format=json")
        assert response.status_code == 200
        body = response.json()
        assert body["ready"] is True
        assert len(body["rows"]) > 0
