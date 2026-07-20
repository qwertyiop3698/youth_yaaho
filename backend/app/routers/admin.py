"""docs/07 /api/v1/admin/* 라우터.

doc01 권한분리 원칙: admin 엔드포인트는 집계/통계만 다루고(개인 raw 데이터 노출
금지), 관리자 인증이 필요하다. 고정 API 키(환경변수 ADMIN_API_KEY, 요청 헤더
X-API-Key) 기반 최소 인증이 적용돼 있다 - app/auth.py 참고.

산출물(featured_dataset/risk_scores/cluster_model 등)이 아직 없으면(표본 부족으로
Layer1~3이 skip된 경우) 500 에러 대신 `{"ready": false, "reason": ...}`를 반환한다.
"""
from __future__ import annotations

import copy
from typing import Any

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from pipeline.layer0_data_contract import cleaner as layer0_cleaner
from pipeline.layer2b_risk_model import spatial_autocorrelation
from pipeline.layer3_optimization import lp_allocator, sensitivity_analysis

from ..auth import require_admin_api_key
from ..schemas import SimulateBudgetRequest, SimulateBudgetResponse
from ..services.pipeline_store import PipelineStore, get_pipeline_store

router = APIRouter(prefix="/api/v1/admin", tags=["admin"], dependencies=[Depends(require_admin_api_key)])


def _not_ready(reason: str) -> dict[str, Any]:
    return {"ready": False, "reason": reason}


@router.get("/overview")
def overview(store: PipelineStore = Depends(get_pipeline_store)) -> dict[str, Any]:
    featured_df = store.featured_dataset
    if featured_df is None:
        return _not_ready("featured_dataset이 없습니다(Layer1 미실행).")

    risk_scores = store.risk_scores
    cluster_report = store.cluster_report or {}

    return {
        "ready": True,
        "total_citizens": int(len(featured_df)),
        "avg_risk_probability": (float(risk_scores["event_probability"].mean()) if risk_scores is not None else None),
        "cluster_sizes": cluster_report.get("cluster_sizes"),
        "suggested_labels": cluster_report.get("suggested_labels"),
    }


@router.get("/risk-map")
def risk_map(
    level: str = Query(default="sigungu", pattern="^(dong|sigungu)$"),
    store: PipelineStore = Depends(get_pipeline_store),
) -> dict[str, Any]:
    featured_df = store.featured_dataset
    risk_scores = store.risk_scores
    if featured_df is None or risk_scores is None:
        return _not_ready("featured_dataset/risk_scores가 없습니다(Layer1~2-B 미실행 또는 표본부족).")

    join_cols = layer0_cleaner.resolve_join_columns(store.layer0_config)
    dong_col, sigungu_col = join_cols.get("residence", (None, None))
    group_col = dong_col if level == "dong" and dong_col in featured_df.columns else sigungu_col
    if not group_col or group_col not in featured_df.columns:
        return _not_ready(f"'{level}' 단위 지역 컬럼이 데이터에 없습니다.")

    merged = featured_df[[group_col]].join(risk_scores[["event_probability"]], how="inner")
    grouped = merged.groupby(group_col)["event_probability"].agg(["mean", "count"]).reset_index()
    grouped = grouped.rename(columns={group_col: "region_code", "mean": "avg_risk_probability", "count": "n"})
    # region_code가 원본 데이터에서 숫자(int64)로 들어오면 pydantic이 JSON number로
    # 직렬화해버려 프론트(GeoJSON의 문자열 코드)와 매칭이 깨진다. API 계약(RiskRegion.
    # region_code: string)을 항상 지키도록 명시적으로 문자열로 캐스팅한다.
    grouped["region_code"] = grouped["region_code"].astype(str)

    # 공간적 자기상관(Moran's I)은 폴리곤 경계 데이터가 있는 sigungu 단위에서만
    # 계산한다(dong 단위는 RiskMap.tsx 주석대로 아직 경계 geojson이 없다).
    spatial_stats: dict[str, Any] | None = None
    lisa_by_region: dict[str, dict[str, Any]] = {}
    if level == "sigungu" and spatial_autocorrelation.DEFAULT_GEOJSON_PATH.exists():
        risk_by_region = grouped.set_index("region_code")["avg_risk_probability"]
        adjacency = spatial_autocorrelation.load_busan_adjacency(spatial_autocorrelation.DEFAULT_GEOJSON_PATH)
        spatial_stats = spatial_autocorrelation.compute_morans_i(risk_by_region, adjacency)
        if not spatial_stats.get("skipped"):
            lisa_by_region = spatial_autocorrelation.compute_local_indicators(risk_by_region, adjacency)

    regions = grouped.to_dict(orient="records")
    for region in regions:
        lisa = lisa_by_region.get(region["region_code"])
        region["lisa_quadrant"] = lisa["quadrant"] if lisa else None

    return {"ready": True, "level": level, "regions": regions, "spatial_stats": spatial_stats}


@router.get("/clusters")
def clusters(store: PipelineStore = Depends(get_pipeline_store)) -> dict[str, Any]:
    report = store.cluster_report
    if not report or not report.get("model_trained"):
        return _not_ready("클러스터 모델이 아직 학습되지 않았습니다(표본 부족 등으로 Layer2-A 생략).")

    return {
        "ready": True,
        "best_k": report.get("best_k"),
        "cluster_profiles": report.get("cluster_profiles"),
        "cluster_sizes": report.get("cluster_sizes"),
        "suggested_labels": report.get("suggested_labels"),
    }


@router.get("/policy-gaps")
def policy_gaps(
    risk_threshold: float = Query(default=0.6, ge=0.0, le=1.0),
    fairness_corrected: bool = Query(
        default=True, description="risk_model_report.json의 성별 equalized-odds 보정임계값을 적용할지"
    ),
    store: PipelineStore = Depends(get_pipeline_store),
) -> dict[str, Any]:
    """정책 사각지대를 개인 ID 없이 지역별 집계로만 반환한다.

    fairness_corrected=True(기본)이고 risk_threshold가 risk_model_report.json에
    저장된 공정성 보정의 baseline_threshold와 같으면, 단일 임계값 대신 성별별
    equalized-odds 보정임계값(fairness_correction.py)으로 고위험 여부를 판정한다
    - 공정성 감사에서 발견한 성별 격차를 실제 판정 지점에서 교정한다(docs/04).
    risk_threshold를 다른 값으로 바꾸면 보정임계값(특정 baseline에 맞춰 계산됨)이
    더는 유효하지 않으므로 단일 임계값으로 자동 폴백한다.
    """
    risk_scores = store.risk_scores
    if risk_scores is None:
        return _not_ready("risk_scores가 없습니다(Layer2-B 미실행 또는 표본부족).")

    assignment_results = store.assignment_results

    fairness_correction_applied = False
    before_after_gap: dict[str, Any] | None = None
    high_risk_mask = risk_scores["event_probability"] >= risk_threshold

    if fairness_corrected:
        correction = (store.risk_model_report or {}).get("fairness_correction") or {}
        featured_df = store.featured_dataset
        if (
            not correction.get("skipped")
            and correction.get("baseline_threshold") is not None
            and abs(correction["baseline_threshold"] - risk_threshold) < 1e-9
            and featured_df is not None
            and "성별" in featured_df.columns
        ):
            gender = featured_df["성별"].reindex(risk_scores.index).astype(str)
            per_person_threshold = gender.map(correction["thresholds"]).fillna(risk_threshold)
            high_risk_mask = risk_scores["event_probability"] >= per_person_threshold
            fairness_correction_applied = True
            evaluation = correction.get("evaluation") or {}
            before_after_gap = {
                "before_tpr_gap": evaluation.get("before_tpr_gap"),
                "after_tpr_gap": evaluation.get("after_tpr_gap"),
            }

    high_risk_idx = risk_scores[high_risk_mask].index
    assigned_ids = set(assignment_results["person_id"].unique()) if assignment_results is not None else set()
    gap_ids = [i for i in high_risk_idx if i not in assigned_ids]

    regions: list[dict[str, Any]] = []
    featured_df = store.featured_dataset
    if featured_df is not None:
        join_cols = layer0_cleaner.resolve_join_columns(store.layer0_config)
        _, sigungu_col = join_cols.get("residence", (None, None))
        if sigungu_col and sigungu_col in featured_df.columns:
            gap_regions = featured_df.loc[featured_df.index.intersection(gap_ids), sigungu_col]
            counts = gap_regions.dropna().astype(str).value_counts()
            regions = [
                {"region_code": region_code, "n_high_risk_without_policy": int(count)}
                for region_code, count in counts.items()
            ]

    return {
        "ready": True,
        "risk_threshold": risk_threshold,
        "n_high_risk": int(len(high_risk_idx)),
        "n_high_risk_without_policy": len(gap_ids),
        "regions": regions,
        "fairness_correction_applied": fairness_correction_applied,
        "fairness_correction_before_after_gap": before_after_gap,
    }


@router.get("/policy-catalog")
def policy_catalog(store: PipelineStore = Depends(get_pipeline_store)) -> dict[str, Any]:
    """정책 카탈로그(이름/단가/기본 예산) - 예산 시뮬레이터 슬라이더 초기값용.

    Layer3 실행 여부와 무관하게 항상 존재하는 정적 설정 파일(policy_catalog.yaml)
    기반이라 ready:false 분기가 필요 없다.
    """
    policies = store.policy_catalog.get("policies", {})
    return {
        "ready": True,
        "policies": [
            {"name": name, "unit_cost": info.get("unit_cost"), "budget_cap": info.get("budget_cap")}
            for name, info in policies.items()
        ],
    }


@router.post("/simulate-budget", response_model=SimulateBudgetResponse)
def simulate_budget(
    payload: SimulateBudgetRequest, store: PipelineStore = Depends(get_pipeline_store)
) -> SimulateBudgetResponse:
    featured_df = store.featured_dataset
    risk_scores = store.risk_scores
    if featured_df is None or risk_scores is None:
        return SimulateBudgetResponse(
            coverage_rate=None,
            coverage_rate_verified_only=None,
            skipped=True,
            reason="featured_dataset/risk_scores가 없습니다(Layer1~2-B 미실행 또는 표본부족).",
        )

    df = featured_df.join(risk_scores[["event_probability"]], how="left")

    custom_catalog = copy.deepcopy(store.policy_catalog)
    unknown_policies = sorted(set(payload.policy_budgets) - set(custom_catalog["policies"]))
    if unknown_policies:
        raise HTTPException(status_code=422, detail=f"알 수 없는 정책명입니다: {unknown_policies}")
    for policy_name, new_budget in payload.policy_budgets.items():
        if policy_name in custom_catalog["policies"]:
            custom_catalog["policies"][policy_name]["budget_cap"] = new_budget

    assignment_df, lp_report = lp_allocator.build_and_solve_lp(df, custom_catalog, risk_col="event_probability")
    total_persons = int(df["event_probability"].notna().sum())
    coverage = sensitivity_analysis.compute_coverage_rate(assignment_df, total_persons)

    # 전체 예산을 10% 더 늘리면 커버율이 얼마나 오르는지 - 11개 배율을 전부 스윕하는
    # sensitivity_analysis.run_budget_sensitivity()는 이 대화형 엔드포인트(슬라이더
    # 조작마다 호출)에서 쓰기엔 LP를 너무 많이(11회) 다시 풀어야 해서 느리다. 대신
    # 방금 계산한 현재(1.0배율) 커버율에 1.1배율 한 번만 추가로 풀어서 2점으로 근사한다.
    marginal_gain = None
    if not lp_report.get("skipped", False) and coverage["overall"] is not None:
        bumped_catalog = copy.deepcopy(custom_catalog)
        for policy_cfg in bumped_catalog["policies"].values():
            policy_cfg["budget_cap"] = policy_cfg["budget_cap"] * 1.1
        bumped_assignment, bumped_report = lp_allocator.build_and_solve_lp(
            df, bumped_catalog, risk_col="event_probability"
        )
        if not bumped_report.get("skipped", False):
            bumped_coverage = sensitivity_analysis.compute_coverage_rate(bumped_assignment, total_persons)
            two_point_df = pd.DataFrame(
                {"budget_multiplier": [1.0, 1.1], "coverage_overall": [coverage["overall"], bumped_coverage["overall"]]}
            )
            marginal_gain = sensitivity_analysis.marginal_gain_per_10pct_budget(two_point_df)

    return SimulateBudgetResponse(
        coverage_rate=coverage["overall"],
        coverage_rate_verified_only=coverage["verified_only"],
        marginal_gain_per_10pct_budget=marginal_gain,
        skipped=lp_report.get("skipped", False),
        reason=lp_report.get("reason"),
    )


@router.get("/policy-marginal-returns")
def policy_marginal_returns(store: PipelineStore = Depends(get_pipeline_store)) -> dict[str, Any]:
    """정책별 '예산 10% 증액 시 한계 커버리지 증가분' 순위 (docs/05 5-3).

    Layer3 배치(run.py)가 sensitivity_analysis.run_per_policy_marginal_analysis()로
    미리 계산해둔 값을 그대로 반환한다 - 정책 6개 x 재풀이라 매 요청마다 계산하기엔
    무거워서 simulate-budget과 달리 배치 산출물을 쓴다.
    """
    df = store.policy_marginal_return
    if df is None:
        return _not_ready("policy_marginal_return가 없습니다(Layer3 미실행).")
    return {"ready": True, "policies": df.to_dict(orient="records")}


@router.get("/risk-trajectory-outlook")
def risk_trajectory_outlook(store: PipelineStore = Depends(get_pipeline_store)) -> dict[str, Any]:
    """클러스터 간 위험 궤적 시뮬레이션(무개입 vs 정책 개입, docs/04) - Layer3 배치가
    미리 계산해둔 optimization_report.json의 trajectory_simulation을 그대로 반환한다.

    실측 전이 데이터가 아니라 클러스터 중심 거리 + 위험도 방향으로 구성한
    시뮬레이션이라는 점(is_simulation/simulation_disclaimer)이 항상 함께 온다.
    """
    report = store.optimization_report
    if not report:
        return _not_ready("optimization_report.json이 없습니다(Layer3 미실행).")
    trajectory = report.get("trajectory_simulation")
    if not trajectory or trajectory.get("skipped"):
        return _not_ready((trajectory or {}).get("reason", "위험 궤적 시뮬레이션 산출물이 없습니다."))
    return {"ready": True, **trajectory}


@router.get("/bandit-status")
def bandit_status(store: PipelineStore = Depends(get_pipeline_store)) -> dict[str, Any]:
    report = store.optimization_report
    if not report:
        return _not_ready("optimization_report.json이 없습니다(Layer3 미실행).")
    return {"ready": True, **report.get("bandit", {})}


@router.post("/report/export")
def export_report(format: str = "csv", store: PipelineStore = Depends(get_pipeline_store)):
    assignment_df = store.assignment_results
    if assignment_df is None:
        return _not_ready("assignment_results가 없습니다(Layer3 미실행).")

    # 관리자 다운로드도 개인 raw ID를 내보내지 않고 정책/검증상태별 집계만 제공한다.
    report_df = (
        assignment_df.groupby(["policy", "eligibility_confidence"], dropna=False)
        .agg(
            n_assignments=("person_id", "count"),
            avg_experimental_fit=("delta_risk", "mean"),
        )
        .reset_index()
    )

    if format == "csv":
        csv_bytes = report_df.to_csv(index=False).encode("utf-8-sig")
        return Response(
            content=csv_bytes,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=assignment_summary.csv"},
        )

    return {"ready": True, "format": "json", "rows": report_df.to_dict(orient="records")}
