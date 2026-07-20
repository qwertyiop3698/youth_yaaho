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
