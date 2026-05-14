"""대출 상환 스케줄 — 거치 + 원금균등분할 방식.

KREI(2023) PDF: 5년 거치 10년 분할 상환, 금리 2.8%
- 거치 기간 (years 1~grace_years): 이자만 납부
- 분할 기간 (years grace+1 ~ grace+repay): 원금균등 + 이자
- 이자는 매년 초 잔액 기준 단리 계산
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class LoanYear:
    """한 해의 대출 상환 내역."""
    year: int
    opening_balance: float
    interest: float
    principal: float
    payment: float
    closing_balance: float


@dataclass
class LoanSchedule:
    """전체 대출 상환 스케줄."""
    principal: float
    rate: float
    grace_years: int
    repay_years: int
    years: List[LoanYear] = field(default_factory=list)

    @property
    def total_interest(self) -> float:
        return sum(y.interest for y in self.years)

    @property
    def total_payment(self) -> float:
        return sum(y.payment for y in self.years)

    def payment_in_year(self, year: int) -> float:
        """1-indexed year. 대출 기간 밖이면 0."""
        for y in self.years:
            if y.year == year:
                return y.payment
        return 0.0

    def interest_in_year(self, year: int) -> float:
        for y in self.years:
            if y.year == year:
                return y.interest
        return 0.0

    def principal_in_year(self, year: int) -> float:
        for y in self.years:
            if y.year == year:
                return y.principal
        return 0.0


def build_loan_schedule(
    principal: float,
    rate: float,
    grace_years: int,
    repay_years: int,
) -> LoanSchedule:
    """거치 + 원금균등분할 상환 스케줄 생성.

    Args:
        principal: 대출 원금 (천원)
        rate: 연 이자율 (0.028 = 2.8%)
        grace_years: 거치 기간 (이자만 납부)
        repay_years: 분할 기간 (원금균등 + 이자)

    Returns:
        LoanSchedule with year-by-year breakdown
    """
    schedule = LoanSchedule(
        principal=principal,
        rate=rate,
        grace_years=grace_years,
        repay_years=repay_years,
    )
    if principal <= 0:
        return schedule

    balance = principal
    principal_per_year = principal / repay_years if repay_years > 0 else 0

    # 거치 기간 (이자만)
    for year in range(1, grace_years + 1):
        interest = balance * rate
        schedule.years.append(LoanYear(
            year=year,
            opening_balance=balance,
            interest=interest,
            principal=0.0,
            payment=interest,
            closing_balance=balance,
        ))

    # 분할 상환 기간 (원금균등 + 이자)
    for i in range(1, repay_years + 1):
        year = grace_years + i
        interest = balance * rate
        payment = principal_per_year + interest
        closing = balance - principal_per_year
        schedule.years.append(LoanYear(
            year=year,
            opening_balance=balance,
            interest=interest,
            principal=principal_per_year,
            payment=payment,
            closing_balance=max(closing, 0),
        ))
        balance = closing

    return schedule


def annualized_finance_cost(
    equity: float,
    loan_schedule: LoanSchedule,
    amortize_over_years: int,
) -> float:
    """자기자본 + 대출 상환을 amortize_over_years로 평균한 연간 비용 (천원/년).

    KREI(2023) PDF의 '자기자본, 이자, 원금상환 11,900' 재현용.
    PDF 계산: (equity 46,000 + total_loan_payment 194,100) / 20 = 12,005 ≈ 11,900
    → amortize_over_years는 시설수명(20년)을 사용. 운영기간(operation_years)이 아님.
    """
    if amortize_over_years <= 0:
        return 0.0
    return (equity + loan_schedule.total_payment) / amortize_over_years
