"""Layer 3 - LP 기반 예산 배정 (docs/05_optimization_engine.md 5-1).

정식화:
    변수:   x_ip ∈ {0,1}   개인 i에게 정책 p 배정 여부
    목적:   maximize Σ_i Σ_p (Δrisk_ip · x_ip)
    제약1:  Σ_i (cost_p · x_ip) ≤ Budget_p   (정책별 예산 상한)
    제약2:  Σ_p x_ip ≤ MaxPolicyPerPerson    (1인당 중복 배정 상한)
    제약3:  x_ip ≤ eligibility_ip            (정책 자격조건 충족 여부)

Δrisk_ip 공식 (2026-07-08/09 사용자 승인)
-----------------------------------------
    Δrisk_ip = risk_probability_i × relevance_score_ip × effectiveness_prior_p

- risk_probability_i: Layer2-B가 계산한 보정된 event_probability(0~1).
- relevance_score_ip: policy_catalog.yaml의 target_domains에 명시된 도메인지수들을
  sigmoid(z)로 0~1 압축한 뒤 가중평균한 값. 도메인지수는 z-score라 범위가 정해져
  있지 않아 그대로 곱하면 스케일이 깨지므로 sigmoid로 압축한다(평균적인 사람은 0.5).
- effectiveness_prior_p: 정책별 초기 효과 "가정치"(실제 근거 없음, policy_catalog.yaml
  참고). Thompson Sampling의 사후평균으로 나중에 교체 가능하도록
  build_and_solve_lp()의 effectiveness_override 인자를 지원한다.

eligibility_ip 구조 (2026-07-09 사용자 확정)
-----------------------------------------------
    {"eligible": bool, "confidence": "verified" | "assumed_unresolved_codebook"}

코드북이 불확실하거나 데이터에 아예 없는 조건은 "자격 있음으로 간주 + 경고 로그" 로
처리하고 confidence를 assumed_unresolved_codebook으로 낮춘다(임의로 특정 코드값이
자격을 충족/미충족한다고 단정하지 않는다). 이 confidence는 assignment_results
산출물에 컬럼으로 함께 저장되어, sensitivity_analysis.py가 "전체 커버리지율"과
"verified 조건만 기준으로 한 커버리지율"을 구분해서 보여줄 수 있게 한다.

person_id 관련: 현재 KCB 컬럼 명세(46개)에는 person_id/고유식별자 컬럼이 없다. 이
모듈은 방어적으로 DataFrame의 인덱스를 person_id로 사용한다 - 실제 데이터에 ID
컬럼이 확보되면 그 컬럼으로 교체해야 한다.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any

import numpy as np
import pandas as pd
import psutil
import pulp

logger = logging.getLogger(__name__)

# 2026-07-10 실스케일(n=1500) 리허설에서 발견: budget_cap이 빡빡하면 이진 MIP(1500명
# x6정책=9000개 변수)의 branch-and-bound가 몇 초가 아니라 수십 분 이상 걸릴 수 있다
# (knapsack형 MIP 특성상 예산이 빠듯할수록 조합폭발이 심해짐). 무한정 안 걸리게
# 상한을 둔다 - 값은 실측(각 budget_cap 축소 비율별 solve 시간 측정) 기준으로 정함.
DEFAULT_SOLVER_TIME_LIMIT_SECONDS = 30

# 2026-07-25 실측(100,816명 규모, 자격조건이 촘촘해진 뒤): 위 timeLimit을 PuLP의
# PULP_CBC_CMD(timeLimit=...)로 넘기면 CBC 실행파일에 "-sec 30"으로 전달되긴 하지만,
# CBC의 시간제한 체크는 branch-and-bound 노드 사이 체크포인트에서만 동작해서 문제가
# 크면(60만개 이진변수) 첫 노드(루트 LP relaxation/presolve) 자체가 30초를 넘겨도
# 전혀 발동하지 않을 수 있다 - 실제로 21분 넘게 하드행되는 것을 확인함. 게다가 PuLP의
# COIN_CMD.solve_CBC()는 subprocess.Popen을 파이썬 쪽 timeout 없는 cbc.wait()로
# 기다리기만 해서(PuLP 자체엔 강제 종료 기능이 없음), CBC가 스스로 안 멈추면 영원히
# 안 끝난다. 그래서 여기서 프로세스 트리를 직접 감시하는 워치독을 추가로 둔다.
SOLVER_KILL_GRACE_SECONDS = 15.0


def _kill_process_tree_by_name(pid: int, names: set[str]) -> list[int]:
    """pid의 자손 프로세스 중 이름이 names(소문자 비교)에 해당하는 프로세스만 강제
    종료한다(비슷한 이름의 다른 프로세스까지 건드리지 않도록 pid 기준으로 자손만
    조회 - 프로세스 이름만으로 시스템 전체를 뒤지지 않는다). 종료된 PID 목록을 반환."""
    killed: list[int] = []
    try:
        parent = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return killed
    for child in parent.children(recursive=True):
        try:
            if child.name().lower() in names:
                child.kill()
                killed.append(child.pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return killed


def _solve_with_hard_timeout(
    prob: "pulp.LpProblem",
    solver: "pulp.LpSolver",
    timeout_seconds: float,
    kill_grace_seconds: float = SOLVER_KILL_GRACE_SECONDS,
) -> bool:
    """prob.solve(solver)를 워치독과 함께 실행한다.

    PuLP의 timeLimit(-> CBC의 "-sec")이 항상 지켜진다는 보장이 없으므로(모듈
    docstring 참고), timeout_seconds + kill_grace_seconds를 넘기면 이 프로세스가
    띄운 cbc 자식 프로세스를 강제 종료한다. 반환값이 True면 워치독이 실제로
    개입했다는 뜻 - 이 경우 "그 시점까지 찾은 최선의 실행가능해"조차 신뢰할 수
    없으므로(강제 종료 시점의 변수값을 보장 못 함) 호출부는 배정 결과를 비운다.
    """
    done = threading.Event()
    errors: list[BaseException] = []

    def _target() -> None:
        try:
            prob.solve(solver)
        except BaseException as exc:  # noqa: BLE001 - 워치독 강제종료로 인한 예외도 여기로 들어옴
            errors.append(exc)
        finally:
            done.set()

    my_pid = os.getpid()
    worker = threading.Thread(target=_target, daemon=True)
    worker.start()

    hard_deadline = timeout_seconds + kill_grace_seconds
    finished_in_time = done.wait(timeout=hard_deadline)

    timed_out = False
    if not finished_in_time:
        killed_pids = _kill_process_tree_by_name(my_pid, {"cbc", "cbc.exe"})
        logger.warning(
            "LP 솔버가 시간제한(%s초 + 유예 %s초)을 넘겨 강제 종료했습니다(PID: %s). "
            "이번 배정은 해를 찾지 못한 것으로 처리합니다.",
            timeout_seconds,
            kill_grace_seconds,
            killed_pids,
        )
        timed_out = True
        done.wait(timeout=kill_grace_seconds)  # 강제종료 후 스레드가 정리될 시간을 준다

    if errors and not timed_out:
        # 워치독이 개입하지 않았는데 예외가 났다면 우리가 만든 상황이 아니므로 그대로 전파한다.
        raise errors[0]

    return timed_out

AGE_COLUMN = "연령대"


def _sigmoid(z: pd.Series) -> pd.Series:
    return 1.0 / (1.0 + np.exp(-z.astype(float)))


def compute_relevance_score(df: pd.DataFrame, target_domains: dict[str, float]) -> pd.Series:
    """정책이 겨냥하는 도메인지수들의 sigmoid 압축 후 가중평균 (relevance_score_ip)."""
    total_weight = sum(target_domains.values())
    if total_weight <= 0:
        return pd.Series(0.5, index=df.index)

    score = pd.Series(0.0, index=df.index)
    for domain, weight in target_domains.items():
        if domain not in df.columns:
            logger.warning("relevance_score 계산: 도메인지수 '%s'가 없어 중립값(0.5)으로 대체합니다.", domain)
            domain_sigmoid = pd.Series(0.5, index=df.index)
        else:
            domain_values = pd.to_numeric(df[domain], errors="coerce").fillna(0.0)
            domain_sigmoid = _sigmoid(domain_values)
        score = score + weight * domain_sigmoid
    return score / total_weight


def evaluate_policy_eligibility(df: pd.DataFrame, policy_name: str, policy_cfg: dict[str, Any]) -> pd.DataFrame:
    """정책 하나에 대한 모든 사람의 eligibility_ip를 계산한다.

    반환: index=df.index, columns=["eligible", "confidence"].
    규칙 중 confidence="assumed_unresolved_codebook"이거나 컬럼 자체가 데이터에 없으면
    그 규칙은 "자격 있음"으로 간주하고(자격을 깎지 않음) 경고를 로깅하며, 전체
    confidence를 assumed_unresolved_codebook으로 낮춘다. 이미 verified인 규칙이라도
    개별 행의 값이 결측이면 그 행만 확인 불가로 처리한다(동일한 기본 원칙 적용).
    """
    eligible = pd.Series(True, index=df.index)
    unresolved = pd.Series(False, index=df.index)

    rules = policy_cfg.get("eligibility", {}) or {}

    for rule_name, rule_cfg in rules.items():
        confidence = rule_cfg.get("confidence", "assumed_unresolved_codebook")
        column = rule_cfg.get("column") if rule_name != "age_range" else (rule_cfg.get("column") or AGE_COLUMN)

        if confidence != "verified" or column is None or column not in df.columns:
            logger.warning(
                "정책 '%s' 자격조건 '%s': 코드북/컬럼 미확정으로 자격 있음으로 간주합니다.",
                policy_name,
                rule_name,
            )
            unresolved = unresolved | True
            continue

        if rule_name == "age_range":
            values = pd.to_numeric(df[column], errors="coerce")
            satisfies = values.between(rule_cfg["min"], rule_cfg["max"])
        elif "expected_value" in rule_cfg:
            values = df[column]
            satisfies = values == rule_cfg["expected_value"]
        elif "excluded_value" in rule_cfg:
            # "특정 값이면 확실히 자격 미충족"만 아는 경우(예: 자가거주여부=1은 확실히
            # 자가). 나머지 코드값의 개별 의미는 몰라도 "그 특정 값이 아니면 통과"는
            # 데이터명세로 검증 가능하므로 verified로 취급할 수 있다.
            values = df[column]
            satisfies = values != rule_cfg["excluded_value"]
        else:
            logger.warning(
                "정책 '%s' 규칙 '%s'의 형식을 해석할 수 없어 자격 있음으로 간주합니다.", policy_name, rule_name
            )
            unresolved = unresolved | True
            continue

        row_missing = values.isna()
        eligible = eligible & (satisfies.fillna(False) | row_missing)
        unresolved = unresolved | row_missing

    confidence_series = unresolved.map({True: "assumed_unresolved_codebook", False: "verified"})
    return pd.DataFrame({"eligible": eligible, "confidence": confidence_series}, index=df.index)


def compute_delta_risk(
    df: pd.DataFrame,
    policy_catalog: dict[str, Any],
    risk_col: str = "risk_probability",
    effectiveness_override: dict[str, float] | None = None,
) -> tuple[dict[tuple[Any, str], float], dict[tuple[Any, str], dict[str, Any]]]:
    """모든 (person, policy) 쌍의 Δrisk_ip와 eligibility_ip를 계산한다.

    effectiveness_override: {policy_name: 값} 형태로 넘기면 policy_catalog의
    effectiveness_prior 대신 이 값을 사용한다 - Thompson Sampling의 사후평균으로
    Δrisk_ip를 갱신할 때 쓰는 훅이다(doc05: "추후 5-2 밴딧 결과로 갱신").
    """
    effectiveness_override = effectiveness_override or {}
    risk_probability = pd.to_numeric(df[risk_col], errors="coerce").fillna(0.0) if risk_col in df.columns else None
    if risk_probability is None:
        raise ValueError(f"'{risk_col}' 컬럼이 없어 Δrisk_ip를 계산할 수 없습니다.")

    delta_risk: dict[tuple[Any, str], float] = {}
    eligibility: dict[tuple[Any, str], dict[str, Any]] = {}

    for policy_name, policy_cfg in policy_catalog["policies"].items():
        relevance = compute_relevance_score(df, policy_cfg.get("target_domains", {}))
        effectiveness = effectiveness_override.get(policy_name, policy_cfg["effectiveness_prior"])
        elig_df = evaluate_policy_eligibility(df, policy_name, policy_cfg)

        values = risk_probability * relevance * effectiveness
        for idx in df.index:
            delta_risk[(idx, policy_name)] = float(values.loc[idx])
            eligibility[(idx, policy_name)] = {
                "eligible": bool(elig_df.loc[idx, "eligible"]),
                "confidence": elig_df.loc[idx, "confidence"],
            }

    return delta_risk, eligibility


def build_and_solve_lp(
    df: pd.DataFrame,
    policy_catalog: dict[str, Any],
    risk_col: str = "risk_probability",
    max_policy_per_person: int | None = None,
    effectiveness_override: dict[str, float] | None = None,
    solver: Any | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """LP를 세우고 풀어 배정표(assignment_results)를 만든다.

    표본이 비어있으면(risk_probability를 계산할 수 있는 사람이 0명) 빈 결과와
    skipped=True 리포트를 반환한다(가짜 배정을 만들지 않음).
    """
    if risk_col not in df.columns or df[risk_col].notna().sum() == 0:
        logger.warning("'%s' 컬럼이 없거나 전부 결측이라 LP를 풀 수 없습니다.", risk_col)
        return pd.DataFrame(
            columns=["person_id", "policy", "delta_risk", "eligibility_confidence"]
        ), {"skipped": True, "reason": f"'{risk_col}' 없음/전부 결측", "n_persons": 0}

    valid_df = df[df[risk_col].notna()]
    policies = policy_catalog["policies"]
    max_policy_per_person = max_policy_per_person or policy_catalog.get("defaults", {}).get(
        "max_policy_per_person", 1
    )

    delta_risk, eligibility = compute_delta_risk(valid_df, policy_catalog, risk_col, effectiveness_override)

    prob = pulp.LpProblem("policy_assignment", pulp.LpMaximize)
    x = {
        (i, p): pulp.LpVariable(f"x_{idx}_{p_idx}", cat="Binary")
        for idx, i in enumerate(valid_df.index)
        for p_idx, p in enumerate(policies)
    }

    prob += pulp.lpSum(delta_risk[(i, p)] * x[(i, p)] for i in valid_df.index for p in policies)

    for p, cfg in policies.items():
        prob += (
            pulp.lpSum(cfg["unit_cost"] * x[(i, p)] for i in valid_df.index) <= cfg["budget_cap"],
            f"budget_{p}",
        )

    for i in valid_df.index:
        prob += pulp.lpSum(x[(i, p)] for p in policies) <= max_policy_per_person, f"max_policy_{i}"

    for i in valid_df.index:
        for p in policies:
            if not eligibility[(i, p)]["eligible"]:
                prob += x[(i, p)] == 0

    # 2026-07-10 실스케일(n=1500) 리허설에서 발견: budget_cap을 빡빡하게 조이면
    # 1500명x6정책=9000개 이진변수 MIP의 branch-and-bound가 몇 초가 아니라 수십 분
    # 이상 걸릴 수 있다(knapsack형 MIP는 예산이 빠듯할수록 조합폭발이 심해짐).
    # 시간제한을 걸어 무한정 안 걸리게 하고, 시간제한에 걸려 "증명된 최적해"가
    # 아니라 "그 시점까지 찾은 최선의 실행가능해"로 끝났는지를 report에 남긴다
    # (안 남기면 나중에 이 배정표가 진짜 최적인지 그냥 시간 다 돼서 멈춘 건지
    # 구분이 안 되는 채로 쓰일 위험이 있음).
    solver = solver or pulp.PULP_CBC_CMD(msg=False, timeLimit=DEFAULT_SOLVER_TIME_LIMIT_SECONDS)
    # 워치독은 solver에 실제로 설정된 timeLimit을 따른다(호출부가 커스텀 solver로
    # 더 길게/짧게 줬으면 그 값을 존중 - 하드코딩된 상수로 워치독이 먼저 죽여버리면
    # solver의 timeLimit 파라미터가 무의미해짐). solver.timeLimit이 없으면(None)
    # 기본 상수로 폴백한다.
    watchdog_timeout = getattr(solver, "timeLimit", None) or DEFAULT_SOLVER_TIME_LIMIT_SECONDS
    timed_out = _solve_with_hard_timeout(prob, solver, watchdog_timeout)

    assignments = []
    if not timed_out:
        # 워치독이 강제종료한 경우 변수값을 신뢰할 수 없으므로(해를 못 읽었을 수
        # 있음) 배정을 아예 비운다 - "확인 안 된 부분해"를 실제 배정인 것처럼
        # 내보내지 않는다.
        for i in valid_df.index:
            for p in policies:
                var_value = x[(i, p)].value()
                if var_value is not None and var_value > 0.5:
                    assignments.append(
                        {
                            "person_id": i,
                            "policy": p,
                            "delta_risk": delta_risk[(i, p)],
                            "eligibility_confidence": eligibility[(i, p)]["confidence"],
                        }
                    )

    assignment_df = pd.DataFrame(assignments, columns=["person_id", "policy", "delta_risk", "eligibility_confidence"])

    report = {
        "skipped": False,
        "status": "Timeout_Killed" if timed_out else pulp.LpStatus[prob.status],
        "solver_status": "Killed_By_Watchdog" if timed_out else pulp.LpSolution[prob.sol_status],
        "is_optimal": (not timed_out) and prob.sol_status == pulp.LpSolutionOptimal,
        "objective_value": None if timed_out else pulp.value(prob.objective),
        "n_persons": int(len(valid_df)),
        "n_policies": len(policies),
        "n_assignments": int(len(assignment_df)),
        "max_policy_per_person": max_policy_per_person,
        "solver_watchdog_killed": timed_out,
    }
    return assignment_df, report
