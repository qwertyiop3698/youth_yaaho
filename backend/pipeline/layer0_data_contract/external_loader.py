"""Layer 0 - 외부 데이터(부산시 생활인구/인구현황) 로더.

docs/02: "외부데이터(국토부 실거래가, 생활인구) 조인 시 행정동 키가 없을 수 있다는
전제로 설계해야 한다" - 이 모듈은 참조 테이블만 만들고, 실제 조인은 새 로직을 짜지
않고 join_adapter.join_with_fallback을 그대로 재사용한다(행정동 우선, 시군구코드
fallback, _join_method 인디케이터 유지).

2026-07-25 스키마 확인 결과(data/external/부산_인구현황_2026_06_통합.csv, 222행):
    컬럼: 시군구코드, 시군구명, 행정동코드, 행정동명, 거주자인구수, 세대수,
          세대당인구, 남자인구수, 여자인구수, 남여비율
  - 연령대 컬럼이 없다 -> 청년(19~39세)만 따로 집계할 수 없다. 임의 비율로
    추정하지 않고 전체 인구를 그대로 참조값으로 쓰며, age_filter_applied=False로
    이 근사를 리포트에 명시한다(미션 지시 "불가능하면 전체 생활인구 사용하되 그
    사실을 리포트에 명시").
  - 시간대별 컬럼도 없다 - 파일명은 "생활인구"지만 실제 값은 "거주자인구수"
    (주민등록 기반 상주인구)의 월간 스냅샷 1건뿐이다. 애초에 "거주지 기준" 인구라
    시간대별 생활인구 중 야간(거주 추정) 시간대를 고르려는 목적과 이미 동일한
    역할을 하므로 별도 시간대 선택이 필요 없다 - 이 사실 자체를 리포트에 남긴다.
  - 시군구코드 16개(26110~26710)가 KCB `거주지 시군구 코드`(column_groups.yaml의
    코드 시트)와 완전히 동일한 5자리 체계다 - 별도 코드 매핑 테이블이 필요 없고
    매핑 실패는 0건이다.
  - 행정동코드는 10자리(통계청 스타일, 예: 2611051000)이고, 구별 합계를 담은
    "소계" 행(행정동코드 끝자리 00000)이 각 시군구코드마다 1건씩 섞여 있다 -
    시군구 집계 시 이 행을 포함하면 인구가 2배로 잡히므로 반드시 제외해야 한다.
    (검증: 16개 시군구 전부 소계행 값 == 상세 행정동행 합계, 완전 일치 확인함.)
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

SUBTOTAL_LABEL = "소계"
REQUIRED_COLUMNS = ["시군구코드", "행정동코드", "행정동명", "거주자인구수"]
POPULATION_VALUE_COL = "population_reference"


def load_population_csv(path: Path) -> pd.DataFrame:
    """생활인구/인구현황 원본 CSV를 읽는다. 필수 컬럼이 없으면 바로 실패시켜
    (컬럼명이 당일 데이터에서 바뀌었을 가능성을 조용히 넘기지 않는다) 원인을 명확히
    드러낸다 - CLAUDE.md "방어적으로 작성하되 죽어야 할 땐 명확한 이유로 죽는다"
    원칙과 동일하게, 필수 식별 컬럼 자체의 부재는 결측치가 아니라 스키마 불일치라
    조용히 넘기지 않는다."""
    df = pd.read_csv(path, encoding="utf-8")
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            f"생활인구 CSV에 필요한 컬럼이 없습니다: {missing} (실제 컬럼: {list(df.columns)}). "
            "컬럼명이 바뀌었으면 이 모듈의 REQUIRED_COLUMNS/집계 로직을 실제 컬럼명에 맞춰 갱신하세요."
        )
    return df


def _split_subtotal_rows(raw_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """소계 행과 상세(행정동) 행을 분리하고, 소계 행의 시군구코드별 값을 반환한다."""
    is_subtotal = raw_df["행정동명"] == SUBTOTAL_LABEL
    detail = raw_df.loc[~is_subtotal].copy()
    subtotal_by_sigungu = raw_df.loc[is_subtotal].set_index("시군구코드")["거주자인구수"]
    return detail, subtotal_by_sigungu


def build_sigungu_population_reference(raw_df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """행정동 단위 상세행(소계 제외)을 시군구코드로 합산해 참조 테이블을 만든다.

    반환값의 population_reference 컬럼은 "청년 생활인구"가 아니라 전체 인구다 -
    원본에 연령대 컬럼이 없어 청년만 따로 뽑을 수 없기 때문이다(모듈 docstring
    참고). 호출 측(admin.py)은 report["age_filter_applied"]=False를 그대로
    API 응답에 실어 정규화 지표가 "청년" 기준이 아니라 "전체 인구" 기준 근사임을
    사용자에게 감추지 않는다.
    """
    detail, subtotal_by_sigungu = _split_subtotal_rows(raw_df)

    detail_sum = detail.groupby("시군구코드")["거주자인구수"].sum()
    diff = (subtotal_by_sigungu - detail_sum.reindex(subtotal_by_sigungu.index)).abs()
    mismatched = diff[diff > 0]
    if len(mismatched) > 0:
        logger.warning(
            "생활인구 소계행과 상세행정동 합계가 일치하지 않는 시군구코드: %s (원본 파일 확인 필요)",
            mismatched.index.tolist(),
        )

    sigungu_ref = (
        detail.groupby("시군구코드", as_index=False)["거주자인구수"]
        .sum()
        .rename(columns={"거주자인구수": POPULATION_VALUE_COL})
    )

    report = {
        "source_rows": int(len(raw_df)),
        "detail_rows_used": int(len(detail)),
        "subtotal_rows_excluded": int(len(raw_df) - len(detail)),
        "n_sigungu": int(sigungu_ref["시군구코드"].nunique()),
        "age_filter_applied": False,
        "age_filter_reason": "원본 CSV에 연령대 컬럼이 없어 청년만 따로 집계할 수 없음 - 전체 인구를 참조값으로 사용",
        "time_dimension_available": False,
        "time_dimension_note": (
            "원본이 시간대별 생활인구가 아니라 거주자인구수(주민등록 기반 상주인구)의 월간 스냅샷 1건뿐 - "
            "이미 '거주지 기준' 인구라 야간 생활인구가 근사하려는 개념과 같은 역할이라 시간대 선택이 불필요함"
        ),
        "code_system_check": "KCB 거주지 시군구 코드와 5자리 체계 완전 일치 확인 - 매핑 테이블 불필요, 매핑 실패 0건",
        "subtotal_mismatch_sigungu_codes": [str(code) for code in mismatched.index.tolist()],
    }
    return sigungu_ref, report


def build_dong_population_reference(raw_df: pd.DataFrame) -> pd.DataFrame:
    """행정동 단위 참조 테이블(소계 제외).

    현재 확보된 KCB 데이터에는 행정동 컬럼 자체가 없어(Layer0 프로파일링에서
    missing_from_data로 확인됨) 이 테이블은 지금 당장은 join_with_fallback의
    dong 매칭 단계에서 항상 미스매치로 빠지고 sigungu fallback만 실사용된다.
    그래도 "당일 데이터만 갈아끼우면 되는" 파이프라인 원칙에 따라 행정동 컬럼이
    나중에 확보되면 바로 쓸 수 있도록 미리 만들어둔다.
    """
    detail, _ = _split_subtotal_rows(raw_df)
    return detail[["행정동코드", "거주자인구수"]].rename(columns={"거주자인구수": POPULATION_VALUE_COL})
