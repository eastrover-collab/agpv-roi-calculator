"""PDF summary report smoke tests."""
from __future__ import annotations

from core.calculator import (
    CostInput,
    CropInput,
    EconomicAnalysis,
    FacilityInput,
    FinanceInput,
    LandLawInput,
    OpexInput,
    PowerPriceInput,
    scale_opex_for_project,
)
from core.config import load_assumptions
from core.report_pdf import build_summary_pdf


def _default_analysis() -> EconomicAnalysis:
    assumptions = load_assumptions()

    facility = FacilityInput(
        area_m2=float(assumptions["facility"]["area_m2"]),
        capacity_kw=float(assumptions["facility"]["capacity_kw"]),
        daily_gen_hours=float(assumptions["facility"]["daily_gen_hours"]),
        efficiency_decline=float(assumptions["facility"]["efficiency_decline"]),
        lifetime_years=int(assumptions["facility"]["lifetime_years"]),
    )
    cost = CostInput(
        construction=float(assumptions["cost"]["total"] - assumptions["cost"]["permits"]),
        permits=float(assumptions["cost"]["permits"]),
    )
    finance = FinanceInput(
        equity_ratio=float(assumptions["finance"]["equity_ratio"]),
        loan_rate=float(assumptions["finance"]["loan_options"]["policy_2026"]["rate"]),
        grace_years=int(assumptions["finance"]["grace_years"]),
        repay_years=int(assumptions["finance"]["repay_years"]),
    )
    price = PowerPriceInput(
        track="rps",
        smp_krw_per_kwh=float(assumptions["power_price"]["rps_track"]["smp_krw_per_kwh"]),
        rec_krw_per_kwh=float(assumptions["power_price"]["rps_track"]["rec_krw_per_kwh"]),
        weight=float(assumptions["power_price"]["rps_track"]["weight"]),
        ppa_fixed_krw_per_kwh=float(assumptions["power_price"]["ppa_track"]["fixed_price_krw_per_kwh"]),
    )
    base_opex = OpexInput(
        inverter_replace=float(assumptions["opex_thousand_krw"]["inverter_replace"]),
        electrical_mgmt=float(assumptions["opex_thousand_krw"]["electrical_mgmt"]),
        insurance=float(assumptions["opex_thousand_krw"]["insurance"]),
        waste_disposal=float(assumptions["opex_thousand_krw"]["waste_disposal"]),
        utility_repair=float(assumptions["opex_thousand_krw"]["utility_repair"]),
    )
    opex = scale_opex_for_project(
        base_opex,
        base_capacity_kw=float(assumptions["facility"]["capacity_kw"]),
        capacity_kw=facility.capacity_kw,
        base_total_cost=float(assumptions["cost"]["total"]),
        total_cost=cost.total,
    )
    crop = CropInput(
        name_kr=assumptions["crops"]["rice"]["name_kr"],
        base_income_thousand_krw_per_2000m2=float(
            assumptions["crops"]["rice"]["base_income_thousand_krw_per_2000m2"]
        ),
        yield_reduction=float(assumptions["crops"]["rice"]["yield_reduction"]),
    )

    return EconomicAnalysis(
        facility=facility,
        cost=cost,
        finance=finance,
        price=price,
        opex=opex,
        crop=crop,
        land_law=LandLawInput(
            max_operation_years=int(assumptions["land_law"]["current"]["max_operation_years"])
        ),
        discount_rate=finance.loan_rate,
    )


def test_build_summary_pdf_returns_pdf_bytes():
    assumptions = load_assumptions()
    analysis = _default_analysis()

    pdf_bytes = build_summary_pdf(
        result=analysis.run(),
        analysis=analysis,
        assumptions=assumptions,
        share_url="https://agpv-roi-calculator-2000m.streamlit.app/?m=simple&a=2000",
    )

    assert pdf_bytes.startswith(b"%PDF-")
    assert len(pdf_bytes) > 5_000
