"""Layer 2-B - 이진분류 주모델 (로지스틱회귀 + LightGBM).

2026-07-08 사용자 결정: KCB 데이터가 단일 시점 스냅샷이라 Cox 생존분석에 필요한
duration을 관측할 수 없다(target.py 문서 참고). 원래 "베이스라인"으로 기획됐던
로지스틱회귀/LightGBM 이진분류를 주모델로 승격한다. Cox는 실제 패널데이터 확보 시
활성화할 스텁으로 cox_trainer.py에 남겨둔다.

평가지표: AUC-ROC, PR-AUC, calibration curve. C-index는 duration이 없어 사용하지
않는다(doc04는 C-index를 언급하지만 duration 부재로 적용 불가 - 사용자 확인).

2026-07-08 추가 보강 (Layer2 승인 전 사용자 요청 3건)
------------------------------------------------------
1. **모델 선택 기준**: 이전 버전은 로지스틱/LightGBM을 "학습에 쓴 데이터로 그대로"
   평가해서(in-sample) risk_model.pkl로 LightGBM을 무조건 저장했다. 지금은
   train/test를 분리(가능하면)해 held-out PR-AUC가 더 높은 모델을 자동 선택하고
   사유를 report에 남긴다(`best_model_name`, `selection_reason`).
   **주의**: held-out 분리가 불가능할 만큼 표본이 적으면(`holdout_used=False`)
   in-sample PR-AUC로 비교하지 않는다 - LightGBM은 표현력이 커서 작은 표본에서
   거의 항상 in-sample 지표가 부풀려지고, 그 결과 "일반화가 잘 되는 모델"이 아니라
   "과대적합이 심한 모델"이 선택될 구조적 위험이 있기 때문이다(2026-07-08 사용자
   지적). 이 경우엔 비교 없이 분산이 낮은 로지스틱회귀를 기본값으로 선택한다.
2. **확률 보정(calibration)**: Layer3의 LP가 이 확률로 Δrisk_ip(정책 효과)를
   계산하므로, `CalibratedClassifierCV`로 두 모델 모두 보정한다. 표본이 너무 적어
   보정용 CV 폴드를 만들 수 없으면(클래스별 표본<2) 보정을 생략하고 그 사실을
   report에 남긴다(`calibration_applied`).
3. **클래스 불균형**: 두 모델 모두 `class_weight="balanced"`를 기본 적용한다.
   PR-AUC를 baseline(양성비율, 무작위 분류기의 기대 PR-AUC)과 비교해 로그로 남긴다.

SHAP(TreeExplainer)은 `CalibratedClassifierCV`로 감싸면 트리 구조에 직접 접근할 수
없어 작동하지 않는다. 그래서 "확률 산출용"(보정됨, risk_scores.parquet)과
"SHAP 설명용"(원본 LightGBM, doc04가 명시한 "LightGBM 베이스라인 기준")을 별도로
유지한다 - `train_and_compare_models()`의 반환값에 둘 다 들어있다.
"""
from __future__ import annotations

import logging
import re
from typing import Any

import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .feature_gate import get_model_ready_features

logger = logging.getLogger(__name__)

MIN_TRAIN_SAMPLE = 30  # 이진분류 학습 결과를 신뢰하기 위한 경험적 최소 표본
MIN_SAMPLE_FOR_HOLDOUT = 30  # 이 미만이면 train/test 분리를 생략(in-sample 평가로 명시적 표시)
MIN_CLASS_COUNT_FOR_HOLDOUT = 6  # 분리 후 양쪽 fold에 각 클래스가 남으려면 필요한 최소 클래스별 표본
DEFAULT_TEST_SIZE = 0.3
DEFAULT_CALIBRATION_METHOD = "sigmoid"  # 표본이 적을 때 isotonic보다 안정적(Platt scaling)
ISOTONIC_MIN_SAMPLE = 1000  # 이 이상이면 isotonic이 더 유연하고 데이터도 충분


_SAFE_FEATURE_NAME_CHARS = re.compile(r"[^0-9A-Za-z가-힣\s]")


def sanitize_feature_name(name: str) -> str:
    """LightGBM은 피처명에 JSON 특수문자(쉼표 등)가 있으면 학습 자체를 거부한다
    ("Do not support special JSON characters in feature name"). 실제 KCB 컬럼명
    "파산, 개인회생 신청 여부"에 쉼표가 포함돼 있어 그대로 두면 학습이 깨진다
    (실제로 재현/발견된 버그, 2026-07-09).

    2026-07-09 확인/보강: column_groups.yaml의 46개 원본 컬럼 + Layer1 파생변수/
    도메인지수 19개(총 65개 피처명 전부)를 LightGBM에 실제로 학습시켜본 결과, 지금
    시점에는 쉼표 하나만 문제였다(괄호/슬래시/하이픈은 현재 안전). 하지만 당일
    실제 KCB 데이터에는 지금 못 본 다른 특수문자가 등장할 수 있으므로, 발견된
    문자만 땜질하지 않고 **화이트리스트 방식**(한글 음절/영숫자/공백만 허용, 그 외
    전부 밑줄로 치환)으로 일반화한다 - 미래에 어떤 특수문자가 와도 안전하다.
    """
    return _SAFE_FEATURE_NAME_CHARS.sub("_", name)


def build_feature_matrix(
    df: pd.DataFrame, layer0_config: dict[str, Any] | None = None
) -> tuple[pd.DataFrame, list[str]]:
    """get_model_ready_features()로 안전한 컬럼만 골라 숫자형 행렬로 변환한다.

    범주형 컬럼 중 Layer0에서 "unknown"으로 대체된 값 등 숫자 변환이 안 되는 값은
    NaN이 되고, 그런 컬럼은 중앙값으로 채운다(모델 학습을 위한 최후 처리 - Layer0/1
    이 이미 대부분의 결측을 플래그+대체로 처리했으므로 여기서 남는 결측은 적을
    것으로 예상된다).

    반환되는 컬럼명은 sanitize_feature_name()을 거친 이름이다 - LightGBM 학습이
    깨지지 않도록 여기서 한 번만 정리하면 이 X를 그대로 쓰는 모든 곳(로지스틱,
    LightGBM, SHAP, feature_columns 저장값)이 자동으로 안전한 이름을 공유한다.
    """
    candidate_cols = get_model_ready_features(df, layer0_config)
    numeric_df = df[candidate_cols].apply(pd.to_numeric, errors="coerce")
    usable_cols = [c for c in candidate_cols if numeric_df[c].notna().any()]
    if len(usable_cols) < len(candidate_cols):
        dropped = sorted(set(candidate_cols) - set(usable_cols))
        logger.warning("build_feature_matrix: 전부 NaN이라 사용할 수 없는 컬럼 %s 제외.", dropped)

    X = numeric_df[usable_cols].fillna(numeric_df[usable_cols].median(numeric_only=True))
    X.columns = [sanitize_feature_name(c) for c in X.columns]
    return X, list(X.columns)


def train_logistic_regression(X: pd.DataFrame, y: pd.Series, **kwargs: Any) -> LogisticRegression:
    """원본(미보정) 로지스틱회귀. class_weight='balanced'가 기본 적용된다."""
    kwargs.setdefault("class_weight", "balanced")
    model = LogisticRegression(max_iter=1000, **kwargs)
    model.fit(X, y)
    return model


def train_lightgbm(X: pd.DataFrame, y: pd.Series, **kwargs: Any) -> LGBMClassifier:
    """원본(미보정) LightGBM. SHAP(TreeExplainer)은 이 원본 모델에만 적용 가능하므로
    보정된 확률용 모델과 별도로 유지한다. class_weight='balanced'가 기본 적용된다."""
    kwargs.setdefault("class_weight", "balanced")
    model = LGBMClassifier(**kwargs)
    model.fit(X, y)
    return model


def _default_calibration_method(n: int) -> str:
    return "isotonic" if n >= ISOTONIC_MIN_SAMPLE else DEFAULT_CALIBRATION_METHOD


def _resolve_cv_folds(y: pd.Series, max_folds: int = 5) -> int | None:
    """보정용 CV 폴드 수. 클래스별 표본이 2 미만이면 StratifiedKFold 자체가 불가능하므로
    None을 반환해(보정 생략 신호) 호출부가 방어적으로 처리하게 한다."""
    min_class_count = int(y.value_counts().min())
    if min_class_count < 2:
        return None
    return max(2, min(max_folds, min_class_count))


def train_calibrated_model(
    estimator_type: str, X: pd.DataFrame, y: pd.Series, method: str | None = None, **base_kwargs: Any
) -> tuple[Any, bool]:
    """base 모델(class_weight='balanced')을 CalibratedClassifierCV로 보정해 학습한다.

    Layer3의 LP가 이 확률로 Δrisk_ip(정책 효과)를 계산하므로, 보정 안 된 확률을 그대로
    쓰면 예산배정 자체가 왜곡될 수 있다(2026-07-08 사용자 지적). 클래스별 표본이 너무
    적어 보정용 CV를 만들 수 없으면(sample.csv 등) 보정을 생략하고 미보정 모델을 그대로
    반환한다 - predict_proba 인터페이스는 동일하므로 호출부는 신경 쓸 필요 없다.

    Returns:
        (모델, calibration_applied) 튜플.
    """
    if estimator_type == "logistic_regression":
        # 2026-07-10 실스케일(n=1500) 리허설에서 발견: 원본 피처 스케일이 제각각(소득
        # 수만대 vs 비율 0~2 vs LTV 0~150)이라 lbfgs가 ConvergenceWarning을 내며 제대로
        # 수렴하지 못했다. LightGBM은 트리 기반이라 스케일 영향을 안 받으므로 로지스틱
        # 쪽에만 StandardScaler를 추가한다(train_logistic_regression()의 단독 호출 경로는
        # 테스트가 반환값을 순수 LogisticRegression으로 가정하고 get_params()를 직접
        # 확인하므로 건드리지 않는다 - 실제 학습에 쓰이는 건 이 함수뿐).
        base = make_pipeline(
            StandardScaler(), LogisticRegression(max_iter=1000, class_weight="balanced", **base_kwargs)
        )
    elif estimator_type == "lightgbm":
        base = LGBMClassifier(class_weight="balanced", **base_kwargs)
    else:
        raise ValueError(f"알 수 없는 estimator_type: {estimator_type}")

    cv = _resolve_cv_folds(y)
    if cv is None:
        logger.warning(
            "%s: 클래스별 표본이 너무 적어(min=%d) 확률 보정(calibration)을 생략하고 "
            "미보정 확률을 사용합니다. 실데이터(표본 충분)에서는 정상 보정됩니다.",
            estimator_type,
            int(y.value_counts().min()),
        )
        base.fit(X, y)
        return base, False

    method = method or _default_calibration_method(len(y))
    calibrated = CalibratedClassifierCV(base, method=method, cv=cv)
    calibrated.fit(X, y)
    return calibrated, True


def evaluate_binary_classifier(model: Any, X: pd.DataFrame, y: pd.Series) -> dict[str, Any]:
    """AUC-ROC, PR-AUC, calibration curve 계산. 클래스가 1종류뿐이면(표본 부족 등)
    계산 불가하므로 None으로 채우고 경고만 남긴다(죽지 않음).

    PR-AUC는 클래스 불균형에 민감한 지표라, baseline(양성비율 = 무작위 분류기의 기대
    PR-AUC)과 비교한 lift를 함께 로그로 남긴다(2026-07-08 사용자 요청).
    """
    result: dict[str, Any] = {"n": int(len(y)), "positive_rate": float(y.mean()) if len(y) else None}

    if y.nunique() < 2:
        logger.warning("evaluate_binary_classifier: y가 단일 클래스뿐이라 AUC/PR-AUC를 계산할 수 없습니다.")
        result.update({"auc_roc": None, "pr_auc": None, "baseline_pr_auc": None, "calibration": None})
        return result

    proba = model.predict_proba(X)[:, 1]
    result["auc_roc"] = float(roc_auc_score(y, proba))
    result["pr_auc"] = float(average_precision_score(y, proba))

    baseline_pr_auc = float(y.mean())  # 무작위 분류기의 기대 PR-AUC ≈ 양성비율
    result["baseline_pr_auc"] = baseline_pr_auc
    lift = (result["pr_auc"] / baseline_pr_auc) if baseline_pr_auc > 0 else float("nan")
    logger.info(
        "클래스 불균형 대비 성능: 양성비율(baseline PR-AUC)=%.4f, 실제 PR-AUC=%.4f, lift=%.2fx",
        baseline_pr_auc,
        result["pr_auc"],
        lift,
    )

    n_bins = min(10, max(2, len(y) // 5))
    frac_pos, mean_pred = calibration_curve(y, proba, n_bins=n_bins, strategy="quantile")
    result["calibration"] = {"mean_predicted": mean_pred.tolist(), "fraction_positive": frac_pos.tolist()}
    return result


def train_and_compare_models(
    df: pd.DataFrame,
    event: pd.Series,
    layer0_config: dict[str, Any] | None = None,
    min_train_sample: int = MIN_TRAIN_SAMPLE,
    min_holdout_sample: int = MIN_SAMPLE_FOR_HOLDOUT,
) -> dict[str, Any]:
    """로지스틱회귀/LightGBM을 학습하고 held-out(가능하면) PR-AUC로 비교해 주모델을
    자동 선택한다. 표본이 min_train_sample 미만이면(sample.csv=5행 등) 통계적으로
    불안정하다는 경고를 남기지만, 계산 자체는 죽지 않고 진행한다.

    반환값의 `deployed_model`이 risk_model.pkl로 저장할 최종(보정된) 모델이고,
    `raw_lightgbm_for_shap`이 SHAP 설명 전용 원본 LightGBM이다(둘은 별도 목적).
    """
    X, feature_cols = build_feature_matrix(df, layer0_config)
    n = len(X)

    if n < min_train_sample:
        logger.warning(
            "이진분류 학습: 표본 부족(n=%d < %d)으로 결과가 통계적으로 불안정할 수 있습니다. "
            "실데이터(표본 충분)에서는 문제 없습니다.",
            n,
            min_train_sample,
        )

    if event.nunique() < 2:
        logger.warning("train_and_compare_models: event 라벨이 단일 클래스뿐이라 모델을 학습할 수 없습니다.")
        return {"skipped": True, "reason": "event 라벨 단일 클래스", "feature_columns": feature_cols}

    positive_rate = float(event.mean())
    logger.info(
        "클래스 불균형 확인: 양성비율=%.4f (n=%d). class_weight='balanced'를 두 모델 모두에 적용합니다.",
        positive_rate,
        n,
    )

    min_class_count = int(event.value_counts().min())
    can_holdout = n >= min_holdout_sample and min_class_count >= MIN_CLASS_COUNT_FOR_HOLDOUT

    if can_holdout:
        X_train, X_test, y_train, y_test = train_test_split(
            X, event, test_size=DEFAULT_TEST_SIZE, stratify=event, random_state=42
        )
        holdout_used = True
    else:
        logger.warning(
            "held-out validation 분리 불가(n=%d, 최소 클래스 표본=%d, 필요 조건: n>=%d & 클래스별>=%d)"
            "로 in-sample로 평가합니다 - 결과가 과대추정될 수 있습니다. 실데이터에서는 정상 분리됩니다.",
            n,
            min_class_count,
            min_holdout_sample,
            MIN_CLASS_COUNT_FOR_HOLDOUT,
        )
        X_train, X_test, y_train, y_test = X, X, event, event
        holdout_used = False

    lgbm_kwargs = dict(
        min_child_samples=max(1, len(X_train) // 10), num_leaves=min(31, max(2, len(X_train) // 2)), verbosity=-1
    )

    candidates: dict[str, Any] = {}
    calibration_applied: dict[str, bool] = {}
    for name, kwargs in (("logistic_regression", {}), ("lightgbm", lgbm_kwargs)):
        model, applied = train_calibrated_model(name, X_train, y_train, **kwargs)
        candidates[name] = model
        calibration_applied[name] = applied

    metrics = {name: evaluate_binary_classifier(model, X_test, y_test) for name, model in candidates.items()}

    # 2026-07-08 사용자 지적: in-sample(hold-out 없음) PR-AUC로 LightGBM과 로지스틱을
    # 비교하면 구조적으로 편향된다 - LightGBM은 표현력이 커서 작은 표본에서 거의 항상
    # in-sample 지표가 부풀려지고, 그 결과 "일반화가 잘 되는 모델"이 아니라 "과대적합이
    # 심한 모델"이 선택될 위험이 있다. 그래서 holdout_used=False(held-out 비교 불가)인
    # 경우엔 애초에 PR-AUC 비교 자체를 하지 않고, 분산이 낮고 과대적합 위험이 적은
    # 로지스틱회귀를 기본값으로 선택한다. held-out이 있을 때만(holdout_used=True)
    # 실제로 일반화 성능을 반영하는 PR-AUC 비교를 수행한다.
    comparable = (
        {name: m["pr_auc"] for name, m in metrics.items() if m["pr_auc"] is not None} if holdout_used else {}
    )

    if comparable:
        best_name = max(comparable, key=comparable.get)
        selection_reason = (
            f"held-out PR-AUC 기준 선택: {best_name}(PR-AUC={comparable[best_name]:.4f}) vs "
            f"{ {k: round(v, 4) for k, v in comparable.items()} }"
        )
    elif not holdout_used:
        best_name = "logistic_regression"
        selection_reason = (
            "표본 부족으로 held-out 비교 불가, 과대적합 위험이 낮은 로지스틱을 기본 선택 "
            "(LightGBM은 표현력이 커서 in-sample 지표로 비교하면 과대적합된 모델이 선택될 위험이 있음)"
        )
    else:
        best_name = "logistic_regression"
        selection_reason = "PR-AUC 계산 불가(단일 클래스 등)로 기본값(로지스틱, 과대적합 위험 최소화) 선택"

    # 최종 배포 모델(risk_model.pkl)은 held-out으로 버렸던 표본까지 포함해 전체 데이터로 재학습
    deployed_model, deployed_calibration_applied = train_calibrated_model(
        best_name, X, event, **(lgbm_kwargs if best_name == "lightgbm" else {})
    )
    raw_lightgbm_for_shap = train_lightgbm(X, event, **lgbm_kwargs)  # doc04: SHAP은 항상 LightGBM 기준

    return {
        "skipped": False,
        "n": n,
        "holdout_used": holdout_used,
        "positive_rate": positive_rate,
        "feature_columns": feature_cols,
        "calibration_applied": calibration_applied,
        "logistic_regression": {"model": candidates["logistic_regression"], "metrics": metrics["logistic_regression"]},
        "lightgbm": {"model": candidates["lightgbm"], "metrics": metrics["lightgbm"]},
        "best_model_name": best_name,
        "selection_reason": selection_reason,
        "deployed_model": deployed_model,
        "deployed_model_calibrated": deployed_calibration_applied,
        "raw_lightgbm_for_shap": raw_lightgbm_for_shap,
    }
