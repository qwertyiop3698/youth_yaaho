"""data/synthetic_large.csv 생성 - 실스케일 파이프라인 리허설용 합성 데이터.

지금까지 Layer0~3 파이프라인 검증은 sample.csv(5행) 또는 소규모 합성데이터
(n=150~300, 유닛테스트용)로만 이뤄졌다. 실제 KCB 데이터는 수백~수천 행 규모일
것이므로, sanitize_feature_name() 쉼표버그처럼 "진짜 스케일에서만 터지는" 문제를
해커톤 당일 전에 미리 잡기 위해 n=1000~2000 규모의 현실적 분포를 가진 합성 데이터를
만든다(2026-07-10 사용자 요청).

컬럼명은 column_groups.yaml에서 그대로 읽어온다(CLAUDE.md "컬럼명 하드코딩 최소화"
원칙과 동일한 이유 - 여기서 46개 한글 컬럼명을 다시 타이핑하면 오타로 실제
파이프라인이 기대하는 이름과 미묘하게 어긋날 위험이 있다). 그래서 값 배열은
column_groups.yaml에서 읽은 순서(인덱스)로만 조립하고, 마지막에 생성된 컬럼 집합이
yaml의 46개와 정확히 같은지 assert로 검증한다.

의도적으로 만든 "현실 결함"들 (지금까지 5행/소표본 데이터로는 못 봤던 코드 경로를
이번에 실제로 태워보기 위함):
    - 자산/가격 계열 컬럼에 -99999999 sentinel을 ~2%씩 독립 주입
      (regional_median_impute + sentinel_check 경로를 대규모로 검증)
    - 추정 연소득류 컬럼에 <=0 abnormal 값을 ~2% 주입(median_impute 경로 검증)
    - 거주지행정동/근무지행정동/직업군상세/추정가구원수처럼 sample.csv엔 없고
      명세에만 있던 컬럼을 실제로 채워 넣음(행정동 우선 조인/drop_column 경로가
      "컬럼이 아예 없어서 건너뜀"이 아니라 "있어서 실제로 처리됨" 경로를 타게 함)
    - 대출연체건수/카드연체건수를 ~15% 확률로 발생시켜 event 라벨 양성비율이
      0%/100%로 퇴화하지 않게 함(로지스틱/LightGBM 학습이 실제로 의미있게 되도록)

사용법:
    python -m scripts.generate_synthetic_large_dataset --n 1500 --seed 42
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
COLUMN_CONFIG_PATH = (
    _PROJECT_ROOT / "backend" / "pipeline" / "layer0_data_contract" / "column_groups.yaml"
)
DEFAULT_OUTPUT = _PROJECT_ROOT / "data" / "synthetic_large.csv"

# sample.csv에서 실제로 관측된 5개 부산 시군구 코드(모바일 앱 dong_code quick-select와
# 동일) + 여유분 1개 - spatial CV 최소 그룹 수(MIN_GROUPS_FOR_SPATIAL_CV=5)를 넉넉히
# 넘기기 위함.
SIGUNGU_CODES = ["26440", "26260", "26230", "26350", "26320", "26410"]


def load_columns() -> list[str]:
    with open(COLUMN_CONFIG_PATH, encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return list(config["columns"].keys())


def build_dong_lookup(rng: np.random.Generator) -> dict[str, list[str]]:
    """시군구코드별 하위 행정동코드 2~3개. 실데이터엔 있고 sample.csv엔 없던
    거주지행정동/근무지행정동 컬럼을 채워 "행정동 우선" 조인/spatial CV 경로를
    이번에 처음 실제로 태워본다."""
    lookup: dict[str, list[str]] = {}
    for sigungu in SIGUNGU_CODES:
        n_dong = rng.integers(2, 4)
        lookup[sigungu] = [f"{sigungu}{i:02d}" for i in range(1, n_dong + 1)]
    return lookup


def generate(n: int, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    columns = load_columns()
    assert len(columns) == 46, f"column_groups.yaml 컬럼 수가 46개가 아닙니다: {len(columns)}"

    dong_lookup = build_dong_lookup(rng)
    residence_sigungu = rng.choice(SIGUNGU_CODES, size=n)
    workplace_sigungu = rng.choice(SIGUNGU_CODES, size=n)
    residence_dong = np.array([rng.choice(dong_lookup[s]) for s in residence_sigungu])
    workplace_dong = np.array([rng.choice(dong_lookup[s]) for s in workplace_sigungu])

    gender = rng.choice([1, 2], size=n)

    age_bands = np.array([18, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75])
    age_p = np.array([0.03, 0.10, 0.22, 0.20, 0.15, 0.10, 0.07, 0.05, 0.04, 0.03, 0.02, 0.01, 0.01])
    age_band = rng.choice(age_bands, size=n, p=age_p / age_p.sum())

    # 직업군/직업군상세: 코드북 미확정(column_groups.yaml notes) - sample.csv에서
    # 관측된 420/910 위주로 생성한 placeholder. 실데이터 코드북 확정 전까지는 임의값.
    job_group = rng.choice([420, 910, 110, 220], size=n, p=[0.35, 0.30, 0.20, 0.15])
    job_group_detail = rng.integers(1, 6, size=n)

    household_size = rng.integers(1, 5, size=n)  # drop_column 대상이라 파이프라인엔 영향 없음

    monthly_income = rng.normal(2800, 650, size=n).clip(300, 8000).round()

    has_proof_income = rng.random(n) < 0.4
    proof_income = np.where(
        has_proof_income, (monthly_income * 12 * rng.uniform(0.6, 1.0, size=n)).round(), 0.0
    )

    annual_income = (monthly_income * rng.uniform(10.5, 12.5, size=n)).round()
    annual_income = np.where(rng.random(n) < 0.02, 0, annual_income)  # abnormal_if<=0 경로 검증용

    income_growth = rng.normal(0.03, 0.15, size=n)
    income_2y_ago = np.where(
        annual_income > 0,
        (annual_income / (1 + income_growth)).round(),
        (monthly_income * 11).round(),  # annual_income이 abnormal(0)이어도 분모는 정상값 유지
    )
    income_2y_ago = np.where(rng.random(n) < 0.02, -1, income_2y_ago)  # abnormal_if<=0 경로 검증용

    job_history_count = rng.poisson(0.4, size=n)
    job_change_delta = np.where(
        job_history_count > 0, rng.normal(0, annual_income * 0.1 + 1), 0.0
    ).round()

    gross_asset = rng.lognormal(mean=11.5, sigma=0.6, size=n).round()
    net_asset = (gross_asset * rng.uniform(0.4, 0.95, size=n)).round()
    gross_asset = np.where(rng.random(n) < 0.02, -99999999, gross_asset)
    net_asset = np.where(rng.random(n) < 0.02, -99999999, net_asset)

    home_ownership = (rng.random(n) < 0.32).astype(int)  # 청년층답게 무주택 다수
    is_apartment = (rng.random(n) < 0.55).astype(int)

    region_price_multiplier = {code: rng.uniform(0.7, 1.6) for code in SIGUNGU_CODES}
    base_home_price = np.clip(gross_asset, 1, None) * rng.uniform(0.9, 1.3, size=n)
    home_price = np.array(
        [base_home_price[i] * region_price_multiplier[residence_sigungu[i]] for i in range(n)]
    ).round()
    home_price = np.where(rng.random(n) < 0.02, -99999999, home_price)

    vehicle_ownership = rng.choice([0, 1, 2], size=n, p=[0.55, 0.35, 0.10])

    thin_filer = (rng.random(n) < 0.18).astype(int)  # 청년층 신용이력 부족 반영
    credit_score = rng.normal(650, 130, size=n).clip(0, 1000).round()
    credit_score = np.where(thin_filer == 1, 0, credit_score)  # Thin Filer=1은 산출 자체가 안 됨

    loan_count = rng.poisson(1.3, size=n)

    has_credit_loan = rng.random(n) < 0.4
    credit_loan_principal = np.where(has_credit_loan, rng.lognormal(8.5, 0.7, size=n).round(), 0.0)
    credit_loan_balance = (credit_loan_principal * rng.uniform(0.3, 0.9, size=n)).round()

    has_mortgage = (home_ownership == 1) & (rng.random(n) < 0.55)
    mortgage_principal = np.where(has_mortgage, rng.lognormal(10.5, 0.5, size=n).round(), 0.0)
    mortgage_balance = (mortgage_principal * rng.uniform(0.5, 0.95, size=n)).round()

    has_policy_loan = rng.random(n) < 0.12
    policy_loan_principal = np.where(has_policy_loan, rng.lognormal(8.0, 0.6, size=n).round(), 0.0)
    policy_loan_balance = (policy_loan_principal * rng.uniform(0.4, 0.9, size=n)).round()

    total_loan_balance = credit_loan_balance + mortgage_balance + policy_loan_balance
    loan_repayment_12m = (total_loan_balance * rng.uniform(0.08, 0.2, size=n)).round()

    credit_card_spending = (np.clip(annual_income, 1, None) * rng.uniform(0.1, 0.45, size=n)).round()
    check_card_spending = (np.clip(annual_income, 1, None) * rng.uniform(0.02, 0.15, size=n)).round()
    lump_sum_spending = (credit_card_spending * rng.uniform(0.3, 0.7, size=n)).round()
    installment_spending = (credit_card_spending * rng.uniform(0.05, 0.35, size=n)).round()
    cash_service_spending = (np.clip(annual_income, 1, None) * rng.uniform(0.0, 0.08, size=n)).round()

    ltv = np.where(
        has_mortgage, np.clip(mortgage_balance / np.clip(home_price, 1, None) * 100, 0, 150), 0.0
    ).round()
    dti = (total_loan_balance / np.clip(annual_income, 1, None) * 100).round(1)

    # event 라벨(target.py) 1차 조건 - ~15% 확률로 연체 발생시켜 양성비율이
    # 0%/100%로 퇴화하지 않게 함(로지스틱/LightGBM이 실제로 학습되도록).
    has_delinquency = rng.random(n) < 0.15
    loan_delinquency_count = np.where(has_delinquency, rng.poisson(1.2, size=n) + 1, 0)
    card_delinquency_count = np.where(has_delinquency, rng.poisson(0.8, size=n), 0)
    delinquency_days = np.where(has_delinquency, rng.poisson(35, size=n) + 1, 0)
    loan_delinquency_amount = np.where(has_delinquency, rng.lognormal(7.5, 0.8, size=n).round(), 0.0)
    card_delinquency_amount = np.where(has_delinquency, rng.lognormal(6.5, 0.8, size=n).round(), 0.0)

    bankruptcy_flag = (rng.random(n) < 0.03).astype(int)

    avg_sale_price = (np.clip(home_price, 1, None) * rng.uniform(0.85, 1.15, size=n)).round()
    avg_jeonse_price = (avg_sale_price * rng.uniform(0.5, 0.75, size=n)).round()
    avg_sale_price = np.where(rng.random(n) < 0.02, -99999999, avg_sale_price)
    avg_jeonse_price = np.where(rng.random(n) < 0.02, -99999999, avg_jeonse_price)

    # column_groups.yaml 순서(load_columns())와 정확히 같은 순서로 조립한다.
    values = [
        gender, age_band, job_group, job_group_detail,
        residence_sigungu, workplace_sigungu, residence_dong, workplace_dong,
        household_size, monthly_income, proof_income, annual_income, income_2y_ago,
        job_change_delta, gross_asset, net_asset, home_ownership, is_apartment, home_price,
        vehicle_ownership, ltv, dti, credit_score, loan_count,
        credit_loan_principal, credit_loan_balance, mortgage_principal, mortgage_balance,
        policy_loan_principal, policy_loan_balance, loan_repayment_12m,
        credit_card_spending, check_card_spending, lump_sum_spending, installment_spending,
        cash_service_spending, loan_delinquency_count, card_delinquency_count, delinquency_days,
        loan_delinquency_amount, card_delinquency_amount, thin_filer, bankruptcy_flag,
        avg_sale_price, avg_jeonse_price, job_history_count,
    ]
    assert len(values) == len(columns), f"조립한 값 배열 수({len(values)}) != 컬럼 수({len(columns)})"

    df = pd.DataFrame({col: val for col, val in zip(columns, values)})
    assert set(df.columns) == set(columns), "생성된 컬럼명이 column_groups.yaml과 일치하지 않습니다."

    return df


def main() -> None:
    parser = argparse.ArgumentParser(description="실스케일 리허설용 합성 KCB 데이터 생성")
    parser.add_argument("--n", type=int, default=1500, help="생성할 행 수 (기본 1500, 권장 1000~2000)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    df = generate(args.n, args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output, index=False, encoding="utf-8-sig")

    has_delinquency_rate = float(((df["대출연체건수"] > 0) | (df["카드연체건수"] > 0)).mean())
    print(f"[synthetic] 생성 완료: {args.output} ({len(df)}행 {len(df.columns)}컬럼)")
    print(f"[synthetic] 연체 발생 비율(event 1차 조건): {has_delinquency_rate:.3f}")
    print(f"[synthetic] 거주지 시군구 코드 종류 수: {df['거주지 시군구 코드'].nunique()}")
    print(f"[synthetic] 거주지행정동 종류 수: {df['거주지행정동'].nunique()}")
    print(
        f"[synthetic] sentinel(-99999999) 주입 건수 - 총자산평가금액(주택): "
        f"{int((df['총자산평가금액(주택)'] == -99999999).sum())}건"
    )


if __name__ == "__main__":
    main()
