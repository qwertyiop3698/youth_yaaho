"""Layer 0 - 컬럼 그룹별 결측치/이상값 처리기.

docs/02_data_missing_value_framework.md "구현 원칙"을 그대로 따른다.
    1. 원본값 삭제 금지 - 모든 처리는 원본을 지우지 않고 `_was_missing`류 플래그
       컬럼을 추가한다. 행 삭제도 하지 않는다(표본 손실 최소화).
    2. 처리 전/후 분포 비교 - cleaning report에 컬럼별 before/after 통계를 남긴다.
    3. 최소 표본 미달 시 계층적 fallback - regional_median_impute 참고 (join_adapter.py).

절대 컬럼 전체에 "0=결측"/"0=정상" 같은 일괄 규칙을 적용하지 않는다. 모든 처리는
column_groups.yaml에 컬럼별로 명시된 missing_strategy를 따른다.
"""
from __future__ import annotations

from typing import Any, Callable, Iterable

import pandas as pd

from .join_adapter import regional_median_with_fallback


def get_leakage_columns(config: dict[str, Any]) -> list[str]:
    """docs/04 LEAKAGE_COLUMNS를 column_groups.yaml에서 도출.

    Layer 2(위험 예측모델) 학습 코드가 이 함수를 재사용해 피처 목록에 연체 관련
    컬럼이 섞이지 않았는지 강제해야 한다(CLAUDE.md: "코드에 assert로 강제할 것").
    """
    return [c for c, cfg in config.get("columns", {}).items() if cfg.get("is_leakage_column")]


def assert_no_leakage(feature_columns: Iterable[str], config: dict[str, Any]) -> None:
    """연체 관련 컬럼이 피처 목록에 포함되어 있지 않은지 강제 검증한다."""
    leakage = set(get_leakage_columns(config))
    offending = leakage & set(feature_columns)
    assert not offending, (
        "연체 관련 컬럼은 타겟(event) 정의에만 사용하고 피처에 포함하면 안 됩니다: "
        f"{sorted(offending)}"
    )


def get_quasi_identifier_columns(config: dict[str, Any]) -> list[str]:
    """준식별정보(재식별 위험) 컬럼 - 거주지/근무지 시군구코드·행정동처럼 위치를
    특정할 수 있는 조인키. column_spec.xlsx의 PII구분=준식별정보 표시 중, 명세의
    "열삭제"가 개인정보 보호(재식별 위험 완화) 목적이었을 가능성이 높다는 판단에 따라
    조인/spatial CV/행정 집계용으로는 유지하되 Cox/GMM 등 개인별 리스크모델의 raw
    feature 목록에서는 제외한다(assert_no_quasi_identifier_leakage 참고)."""
    return [c for c, cfg in config.get("columns", {}).items() if cfg.get("is_quasi_identifier")]


def assert_no_quasi_identifier_leakage(feature_columns: Iterable[str], config: dict[str, Any]) -> None:
    """개인별 리스크모델(Cox/GMM 등) 피처 목록에 준식별 지역 조인키 원본값이 raw
    categorical feature로 섞여 들어가지 않았는지 강제 검증한다. 조인/spatial CV/행정
    집계용으로 별도 사용하는 것은 이 검증의 대상이 아니다(그런 용도는 허용됨)."""
    quasi = set(get_quasi_identifier_columns(config))
    offending = quasi & set(feature_columns)
    assert not offending, (
        "시군구코드/행정동 등 준식별 지역 조인키는 재식별 위험 때문에 개인별 리스크모델의 "
        f"raw feature로 넣으면 안 됩니다. 그룹핑/조인 키로만 사용하세요: {sorted(offending)}"
    )


def _flag_col_name(col: str, col_cfg: dict[str, Any]) -> str:
    return col_cfg.get("flag_name", f"{col}_was_missing")


def _numeric_before_after(before: pd.Series, after: pd.Series, changed: pd.Series) -> dict[str, Any]:
    before_num = pd.to_numeric(before, errors="coerce")
    after_num = pd.to_numeric(after, errors="coerce")
    return {
        "changed_count": int(changed.sum()),
        "before": {"mean": _safe_float(before_num.mean()), "median": _safe_float(before_num.median())},
        "after": {"mean": _safe_float(after_num.mean()), "median": _safe_float(after_num.median())},
    }


def _safe_float(v: Any) -> float | None:
    return None if pd.isna(v) else float(v)


def _eval_abnormal(numeric: pd.Series, abnormal_if: str) -> pd.Series:
    expr = abnormal_if.strip()
    if expr.startswith("<="):
        return numeric <= float(expr[2:])
    if expr.startswith(">="):
        return numeric >= float(expr[2:])
    if expr.startswith("=="):
        return numeric == float(expr[2:])
    if expr.startswith("<"):
        return numeric < float(expr[1:])
    if expr.startswith(">"):
        return numeric > float(expr[1:])
    raise ValueError(f"지원하지 않는 abnormal_if 표현식: {abnormal_if}")


def resolve_join_columns(config: dict[str, Any]) -> dict[str, tuple[str | None, str | None]]:
    """column_groups.yaml의 join_role/join_scope 메타데이터로부터
    {scope: (dong_col, sigungu_col)} 매핑을 만든다. 컬럼명을 코드에 하드코딩하지 않기 위함.

    Layer1(feature_engineer.py)의 거주-근무 불일치 계산에서도 그대로 재사용한다."""
    join_cols: dict[str, tuple[str | None, str | None]] = {}
    for col, cfg in config.get("columns", {}).items():
        role, scope = cfg.get("join_role"), cfg.get("join_scope")
        if role and scope:
            dong, sigungu = join_cols.get(scope, (None, None))
            if role == "dong":
                dong = col
            elif role == "sigungu":
                sigungu = col
            join_cols[scope] = (dong, sigungu)
    return join_cols


# ---------------------------------------------------------------------------
# 전략별 핸들러. 모두 (df, col, col_cfg, defaults, ctx) -> note dict 시그니처.
# df는 in-place로 수정한다.
# ---------------------------------------------------------------------------


def _handle_none(df: pd.DataFrame, col: str, col_cfg: dict, defaults: dict, ctx: dict) -> dict:
    """0 = 정상 비즈니스 값(거래/연체/이직 없음 등). 결측 아님. 아무 처리도 하지 않는다."""
    return {"column": col, "strategy": "none", "message": "0값=정상 비즈니스 값. 처리 없음."}


def _handle_drop_column(df: pd.DataFrame, col: str, col_cfg: dict, defaults: dict, ctx: dict) -> dict:
    df.drop(columns=[col], inplace=True)
    return {"column": col, "strategy": "drop_column", "message": "명세상 열삭제 대상 컬럼 제거."}


def _handle_unknown_category(df: pd.DataFrame, col: str, col_cfg: dict, defaults: dict, ctx: dict) -> dict:
    flag_col = _flag_col_name(col, col_cfg)
    codebook = col_cfg.get("codebook")
    series = df[col]
    is_null = series.isna()
    if codebook:
        known = set(codebook)
        is_unknown_code = (~series.isin(known)) & (~is_null)
    else:
        is_unknown_code = pd.Series(False, index=df.index)
    needs_replace = is_null | is_unknown_code

    df[flag_col] = needs_replace.astype(int)
    df[col] = series.astype(object).where(~needs_replace, other="unknown")
    return {
        "column": col,
        "strategy": "unknown_category",
        "message": (
            f"null {int(is_null.sum())}건 + 코드북 밖 값 {int(is_unknown_code.sum())}건을 "
            f"'unknown' 카테고리로 대체(최빈값 대체 아님, 편향 방지). 플래그: {flag_col}"
        ),
    }


def _handle_flag_only(df: pd.DataFrame, col: str, col_cfg: dict, defaults: dict, ctx: dict) -> dict:
    """0이 정상이지만 신호로서 의미가 있는 경우. 원본 값은 절대 바꾸지 않는다."""
    flag_col = _flag_col_name(col, col_cfg)
    numeric = pd.to_numeric(df[col], errors="coerce")
    df[flag_col] = (numeric == 0).astype(int)
    return {
        "column": col,
        "strategy": "flag_only",
        "message": f"0값 {int((numeric == 0).sum())}건은 정상(원본 유지) + 신호 컬럼 {flag_col} 추가.",
    }


def _handle_ambiguous_flag(df: pd.DataFrame, col: str, col_cfg: dict, defaults: dict, ctx: dict) -> dict:
    flag_col = _flag_col_name(col, col_cfg)
    numeric = pd.to_numeric(df[col], errors="coerce")
    is_ambiguous = numeric.isna() | (numeric == 0)

    valid = numeric[~is_ambiguous]
    median = valid.median() if len(valid) else numeric.median()

    before = numeric.copy()
    df[flag_col] = is_ambiguous.astype(int)
    df[col] = numeric.where(~is_ambiguous, other=median)

    note = {
        "column": col,
        "strategy": "ambiguous_flag",
        "message": (
            f"0/null {int(is_ambiguous.sum())}건을 median({_safe_float(median)})으로 잠정 대체 + "
            f"플래그 {flag_col} 추가. 결측/정상 여부가 불확실하므로 사람 확인 필요(needs_human_review)."
        ),
    }
    note.update(_numeric_before_after(before, df[col], is_ambiguous))
    return note


def _handle_median_impute(df: pd.DataFrame, col: str, col_cfg: dict, defaults: dict, ctx: dict) -> dict:
    flag_col = _flag_col_name(col, col_cfg)
    numeric = pd.to_numeric(df[col], errors="coerce")
    abnormal_if = col_cfg.get("abnormal_if", "<= 0")
    is_abnormal = _eval_abnormal(numeric, abnormal_if) | numeric.isna()

    valid = numeric[~is_abnormal]
    median = valid.median() if len(valid) else numeric.median()

    before = numeric.copy()
    df[flag_col] = is_abnormal.astype(int)
    df[col] = numeric.where(~is_abnormal, other=median)

    note = {
        "column": col,
        "strategy": "median_impute",
        "message": (
            f"이상값/결측 {int(is_abnormal.sum())}건({abnormal_if})을 median({_safe_float(median)})으로 "
            f"대체 + 플래그 {flag_col} 추가."
        ),
    }
    note.update(_numeric_before_after(before, df[col], is_abnormal))
    return note


def _handle_regional_median_impute(df: pd.DataFrame, col: str, col_cfg: dict, defaults: dict, ctx: dict) -> dict:
    flag_col = _flag_col_name(col, col_cfg)
    numeric = pd.to_numeric(df[col], errors="coerce")

    known_sentinels = col_cfg.get("known_sentinel_values") or []
    is_sentinel = numeric.isin(known_sentinels) if known_sentinels else pd.Series(False, index=df.index)
    is_abnormal_zero = (numeric == 0) if col_cfg.get("zero_meaning") == "abnormal" else pd.Series(
        False, index=df.index
    )
    is_missing = numeric.isna() | is_sentinel | is_abnormal_zero
    valid_mask = ~is_missing

    join_scope = col_cfg.get("join_scope", "residence")
    dong_col, sigungu_col = ctx["join_cols"].get(join_scope, (None, None))

    fallback_values = regional_median_with_fallback(
        df,
        col,
        dong_col,
        sigungu_col,
        min_sample_for_regional_group=defaults.get("min_sample_for_regional_group", 5),
        valid_mask=valid_mask,
    )

    before = numeric.copy()
    df[flag_col] = is_missing.astype(int)
    df[col] = numeric.where(~is_missing, other=fallback_values)

    note = {
        "column": col,
        "strategy": "regional_median_impute",
        "message": (
            f"sentinel {int(is_sentinel.sum())}건 + 이상 0값 {int(is_abnormal_zero.sum())}건 + "
            f"null {int(numeric.isna().sum())}건을 지역(행정동->시군구->전체) median으로 대체 "
            f"(join_scope={join_scope}, dong_col={dong_col}, sigungu_col={sigungu_col}) + "
            f"플래그 {flag_col} 추가."
        ),
    }
    note.update(_numeric_before_after(before, df[col], is_missing))
    return note


def _handle_conditional_thin_filer(df: pd.DataFrame, col: str, col_cfg: dict, defaults: dict, ctx: dict) -> dict:
    """신용평점 전용. docs/02: "Thin Filer=1이면 신용평점 산출 자체가 안됨".

    - Thin Filer=1 인 행: 산출 불가가 정상이므로 원본값을 그대로 두고
      구조적 결측 플래그만 추가한다(임의 대체값 생성 안 함 - 대체모형은 docs/03의
      Layer1 서브모델 몫이라 Layer0 범위 밖).
    - Thin Filer=0 인데 값이 비정상(0 이하)인 행: 진짜 이상값이므로 median 대체.
    """
    flag_col = _flag_col_name(col, col_cfg)
    depends_on = col_cfg.get("depends_on")
    numeric = pd.to_numeric(df[col], errors="coerce")

    if depends_on not in df.columns:
        # Thin Filer 컬럼 자체가 없는 경우(실데이터 컬럼 누락 등) - 안전하게 median_impute로 대체
        fallback_cfg = {**col_cfg, "abnormal_if": "<= 0"}
        note = _handle_median_impute(df, col, fallback_cfg, defaults, ctx)
        note["message"] += f" ({depends_on} 컬럼 없어 conditional 로직 대신 median_impute로 대체)"
        return note

    thin_filer = pd.to_numeric(df[depends_on], errors="coerce").fillna(0)
    is_thin_filer = thin_filer == 1
    is_low_or_missing = numeric.isna() | (numeric <= 0)

    structural_missing = is_thin_filer & is_low_or_missing
    abnormal_non_thin_filer = (~is_thin_filer) & is_low_or_missing

    before = numeric.copy()
    flags = pd.Series(0, index=df.index)
    flags[structural_missing] = 1
    flags[abnormal_non_thin_filer] = 1
    df[flag_col] = flags

    valid = numeric[~structural_missing & ~abnormal_non_thin_filer]
    median = valid.median() if len(valid) else numeric.median()
    df[col] = numeric.where(~abnormal_non_thin_filer, other=median)
    # structural_missing(Thin Filer=1)은 의도적으로 원본값 유지 - 대체하지 않음.

    note = {
        "column": col,
        "strategy": "conditional_thin_filer",
        "message": (
            f"Thin Filer=1 구조적 결측 {int(structural_missing.sum())}건(원본 유지, 플래그만 추가) / "
            f"Thin Filer=0 이상값 {int(abnormal_non_thin_filer.sum())}건(median 대체) 분리 처리."
        ),
    }
    note.update(_numeric_before_after(before, df[col], structural_missing | abnormal_non_thin_filer))
    return note


STRATEGY_HANDLERS: dict[str, Callable[..., dict]] = {
    "none": _handle_none,
    "drop_column": _handle_drop_column,
    "unknown_category": _handle_unknown_category,
    "flag_only": _handle_flag_only,
    "ambiguous_flag": _handle_ambiguous_flag,
    "median_impute": _handle_median_impute,
    "regional_median_impute": _handle_regional_median_impute,
    "conditional_thin_filer": _handle_conditional_thin_filer,
}


def clean_dataset(df: pd.DataFrame, config: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, Any]]:
    """column_groups.yaml에 정의된 그룹별 전략을 적용해 clean_dataset을 만든다.

    - 데이터에 없는 설정 컬럼은 조용히 건너뛴다(실데이터 컬럼 구성이 달라도 안 죽는다).
    - drop_column을 제외하면 어떤 원본 컬럼도 삭제하지 않고, 어떤 행도 삭제하지 않는다.
    """
    df = df.copy()
    notes: list[dict[str, Any]] = []
    ctx = {"join_cols": resolve_join_columns(config)}

    for col, col_cfg in config.get("columns", {}).items():
        if col not in df.columns:
            continue
        strategy = col_cfg.get("missing_strategy", "none")
        handler = STRATEGY_HANDLERS.get(strategy)
        if handler is None:
            raise ValueError(f"알 수 없는 missing_strategy '{strategy}' (컬럼: {col})")
        notes.append(handler(df, col, col_cfg, config.get("defaults", {}), ctx))

    report = {"notes": notes, "leakage_columns": get_leakage_columns(config)}
    return df, report
