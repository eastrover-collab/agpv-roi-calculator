"""v2 재무모형의 회계 항등식과 핵심 동작 검증."""
from __future__ import annotations

import pytest

from core.calculator import (
    CostInput, CropInput, EconomicAnalysis, FacilityInput, FinanceInput,
    LandLawInput, OpexInput, PowerPriceInput,
)


def build(finance: FinanceInput | None = None, discount: float = 0.045) -> EconomicAnalysis:
    return EconomicAnalysis(
        facility=FacilityInput(area_m2=2000, capacity_kw=99, daily_gen_hours=3.7, lifetime_years=23),
        cost=CostInput(construction=194_000, permits=16_000),
        finance=finance or FinanceInput(equity_ratio=.235, loan_rate=.018, grace_years=5, repay_years=10),
        price=PowerPriceInput(track="ppa", ppa_fixed_krw_per_kwh=154.7),
        opex=OpexInput(),
        crop=CropInput(),
        land_law=LandLawInput(max_operation_years=23),
        discount_rate=discount,
    )


def test_project_cashflow_starts_with_full_cost():
    analysis = build()
    result = analysis.run()
    assert result.project_cash_flows[0] == -analysis.cost.total
    assert result.equity_cash_flows[0] == -analysis.upfront_equity()


def test_equity_flow_reconciles_actual_debt_schedule():
    result = build().run()
    for detail, flow in zip(result.annual_cash_flows, result.equity_cash_flows[1:]):
        assert flow == pytest.approx(detail.operating_cash_flow - detail.debt_service)


def test_project_metrics_do_not_change_with_financing():
    low_debt = build(FinanceInput(equity_ratio=.8, loan_rate=.01, grace_years=2, repay_years=5)).run()
    high_debt = build(FinanceInput(equity_ratio=.1, loan_rate=.06, grace_years=5, repay_years=15)).run()
    assert low_debt.project_npv == pytest.approx(high_debt.project_npv)
    assert low_debt.project_bc_ratio == pytest.approx(high_debt.project_bc_ratio)
    assert low_debt.project_irr == pytest.approx(high_debt.project_irr)
    assert low_debt.equity_npv != pytest.approx(high_debt.equity_npv)


def test_npv_equals_discounted_project_cashflows():
    analysis = build(discount=.07)
    result = analysis.run()
    expected = sum(cf / 1.07**year for year, cf in enumerate(result.project_cash_flows))
    assert result.project_npv == pytest.approx(expected)


def test_inverter_cost_is_one_time_in_years_10_and_20():
    result = build().run()
    costs = {d.year: d.inverter_cost for d in result.annual_cash_flows}
    assert costs[9] == 0
    assert costs[10] == 10_000
    assert costs[20] == 10_000
    assert costs[21] == 0


def test_dscr_is_minimum_of_debt_years():
    result = build().run()
    expected = min(
        d.operating_cash_flow / d.debt_service
        for d in result.annual_cash_flows if d.debt_service > 0
    )
    assert result.minimum_dscr == pytest.approx(expected)
