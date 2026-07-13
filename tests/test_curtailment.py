"""출력제어(curtailment) 파라미터 검증.

- 기본값 0%는 기존 결과와 완전히 동일해야 한다 (기존 공유 URL 보존).
- 출력제어율 k는 발전량·발전수익을 정확히 (1-k)배로 줄여야 한다.
- 작물 수익은 출력제어와 무관해야 한다.
"""
from __future__ import annotations

import pytest

from core.calculator import (
    CostInput,
    CropInput,
    EconomicAnalysis,
    FacilityInput,
    FinanceInput,
    LandLawInput,
    OpexInput,
    PowerPriceInput,
)


def _analysis(curtailment_rate: float) -> EconomicAnalysis:
    return EconomicAnalysis(
        facility=FacilityInput(
            daily_gen_hours=3.7,
            lifetime_years=23,
            curtailment_rate=curtailment_rate,
        ),
        cost=CostInput(construction=194_000, permits=16_000),
        finance=FinanceInput(loan_rate=0.018),
        price=PowerPriceInput(track="ppa", ppa_fixed_krw_per_kwh=154.7),
        opex=OpexInput(),
        crop=CropInput(),
        land_law=LandLawInput(max_operation_years=23),
        discount_rate=0.045,
    )


def test_default_curtailment_is_zero():
    assert FacilityInput().curtailment_rate == 0.0


def test_zero_curtailment_matches_legacy_generation():
    a = _analysis(0.0)
    assert a.yearly_generation(1) == pytest.approx(99 * 3.7 * 365)


def test_generation_scales_by_one_minus_k():
    base = _analysis(0.0)
    cut = _analysis(0.05)
    for year in (1, 10, 23):
        assert cut.yearly_generation(year) == pytest.approx(
            base.yearly_generation(year) * 0.95
        )
    assert cut.average_annual_generation(23) == pytest.approx(
        base.average_annual_generation(23) * 0.95
    )


def test_power_revenue_scales_but_crop_unaffected():
    base = _analysis(0.0).run()
    cut = _analysis(0.05).run()
    assert cut.annual_power_revenue == pytest.approx(base.annual_power_revenue * 0.95)
    assert cut.annual_crop_revenue == pytest.approx(base.annual_crop_revenue)


def test_curtailment_lowers_project_npv_and_dscr():
    base = _analysis(0.0).run()
    cut = _analysis(0.10).run()
    assert cut.project_npv < base.project_npv
    assert cut.project_bc_ratio < base.project_bc_ratio
    if base.minimum_dscr is not None and cut.minimum_dscr is not None:
        assert cut.minimum_dscr < base.minimum_dscr
