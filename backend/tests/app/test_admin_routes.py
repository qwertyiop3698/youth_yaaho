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

    def test_skipped_when_no_pipeline_output(self, empty_client):
        response = empty_client.post("/api/v1/admin/simulate-budget", json={"policy_budgets": {}})
        assert response.status_code == 200
        assert response.json()["skipped"] is True


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
        assert "person_id" in response.text

    def test_json_export(self, client):
        response = client.post("/api/v1/admin/report/export?format=json")
        assert response.status_code == 200
        body = response.json()
        assert body["ready"] is True
        assert len(body["rows"]) > 0
