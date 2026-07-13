"""영농형 태양광 경제성 분석 엔진.

사업 전체(project), 자기자본(equity), 원리금 상환(debt service)을 서로 다른
현금흐름으로 계산한다. 금액 단위는 별도 표기가 없으면 천원이다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from core.finance import LoanSchedule, build_loan_schedule


@dataclass
class FacilityInput:
    area_m2: float = 2000
    capacity_kw: float = 99
    daily_gen_hours: float = 3.5
    efficiency_decline: float = 0.011
    lifetime_years: int = 20


@dataclass
class CostInput:
    construction: float = 180_000
    permits: float = 16_000

    @property
    def total(self) -> float:
        return self.construction + self.permits


@dataclass
class FinanceInput:
    equity_ratio: float = 0.235
    loan_rate: float = 0.028
    grace_years: int = 5
    repay_years: int = 10


@dataclass
class PowerPriceInput:
    track: str = "rps"
    smp_krw_per_kwh: float = 106.32
    rec_krw_per_kwh: float = 47.17
    weight: float = 1.2
    ppa_fixed_krw_per_kwh: float = 154.7
    override_krw_per_kwh: Optional[float] = None

    @property
    def unit_price(self) -> float:
        if self.override_krw_per_kwh is not None:
            return self.override_krw_per_kwh
        if self.track == "ppa":
            return self.ppa_fixed_krw_per_kwh
        return self.smp_krw_per_kwh + self.rec_krw_per_kwh * self.weight


@dataclass
class OpexInput:
    """99kW 기준 운영비.

    inverter_replace는 10년마다 지출할 교체비의 연간 적립액이다. 계산에서는
    10배를 10·20년차에 일시 지출한다.
    """

    inverter_replace: float = 1_000
    electrical_mgmt: float = 1_200
    insurance: float = 540
    waste_disposal: float = 250
    utility_repair: float = 420

    @property
    def steady(self) -> float:
        return self.electrical_mgmt + self.insurance + self.waste_disposal + self.utility_repair

    @property
    def total_excluding_finance(self) -> float:
        return self.inverter_replace + self.steady


def scale_opex_for_project(
    base_opex: OpexInput,
    *,
    base_capacity_kw: float,
    capacity_kw: float,
    base_total_cost: float,
    total_cost: float,
) -> OpexInput:
    capacity_ratio = capacity_kw / base_capacity_kw if base_capacity_kw > 0 else 1.0
    cost_ratio = total_cost / base_total_cost if base_total_cost > 0 else 1.0
    return OpexInput(
        inverter_replace=base_opex.inverter_replace * capacity_ratio,
        electrical_mgmt=base_opex.electrical_mgmt * (0.7 + 0.3 * capacity_ratio),
        insurance=base_opex.insurance * cost_ratio,
        waste_disposal=base_opex.waste_disposal * capacity_ratio,
        utility_repair=base_opex.utility_repair * capacity_ratio,
    )


@dataclass
class CropInput:
    name_kr: str = "논벼"
    base_income_thousand_krw_per_2000m2: float = 1_388
    yield_reduction: float = 0.20

    def income_with_reduction(self, area_m2: float) -> float:
        return self.base_income(area_m2) * (1 - self.yield_reduction)

    def base_income(self, area_m2: float) -> float:
        return self.base_income_thousand_krw_per_2000m2 * area_m2 / 2000.0


@dataclass
class LandLawInput:
    max_operation_years: int = 23
    requires_land_conversion: bool = False
    conversion_tax_per_year: float = 0.0


@dataclass
class AnnualCashFlow:
    year: int
    generation_kwh: float
    power_revenue: float
    crop_revenue: float
    steady_opex: float
    inverter_cost: float
    conversion_cost: float
    debt_interest: float
    debt_principal: float

    @property
    def operating_cash_flow(self) -> float:
        return (
            self.power_revenue + self.crop_revenue - self.steady_opex
            - self.inverter_cost - self.conversion_cost
        )

    @property
    def debt_service(self) -> float:
        return self.debt_interest + self.debt_principal

    @property
    def equity_cash_flow(self) -> float:
        return self.operating_cash_flow - self.debt_service


@dataclass
class AnalysisResult:
    annual_generation_kwh: float
    annual_power_revenue: float
    annual_crop_revenue: float
    annual_crop_revenue_base: float
    annual_opex: float
    annual_finance_cost: float

    project_npv: float
    project_bc_ratio: float
    project_irr: Optional[float]
    project_payback_year: Optional[float]
    equity_npv: float
    equity_irr: Optional[float]
    equity_payback_year: Optional[float]
    minimum_dscr: Optional[float]
    first_year_equity_cash: float
    repayment_year_equity_cash: Optional[float]

    npv_power: float
    npv_crop: float
    npv_crop_with_reduction: float
    npv_baseline_crop_only: float
    bc_vs_baseline: float
    project_years: int
    discount_rate: float
    loan_schedule: LoanSchedule = field(repr=False)
    annual_cash_flows: List[AnnualCashFlow] = field(default_factory=list, repr=False)
    project_cash_flows: List[float] = field(default_factory=list, repr=False)
    equity_cash_flows: List[float] = field(default_factory=list, repr=False)

    # 이전 UI/시나리오 코드의 읽기 전용 호환 필드. 의미는 명시적으로 고정한다.
    @property
    def bc_ratio(self) -> float:
        return self.project_bc_ratio

    @property
    def irr(self) -> Optional[float]:
        return self.equity_irr

    @property
    def payback_year(self) -> Optional[float]:
        return self.equity_payback_year

    @property
    def npv_total(self) -> float:
        return self.project_npv

    @property
    def cash_flows(self) -> List[float]:
        return self.equity_cash_flows

    @property
    def npv_total_annualized(self) -> float:
        af = EconomicAnalysis._annuity_factor(self.discount_rate, self.project_years)
        return self.project_npv / af if af else 0.0

    @property
    def npv_power_annualized(self) -> float:
        af = EconomicAnalysis._annuity_factor(self.discount_rate, self.project_years)
        return self.npv_power / af if af else 0.0

    @property
    def npv_crop_annualized(self) -> float:
        af = EconomicAnalysis._annuity_factor(self.discount_rate, self.project_years)
        return self.npv_crop / af if af else 0.0

    @property
    def npv_crop_reduction_annualized(self) -> float:
        af = EconomicAnalysis._annuity_factor(self.discount_rate, self.project_years)
        return self.npv_crop_with_reduction / af if af else 0.0


class EconomicAnalysis:
    def __init__(
        self,
        facility: FacilityInput,
        cost: CostInput,
        finance: FinanceInput,
        price: PowerPriceInput,
        opex: OpexInput,
        crop: CropInput,
        land_law: LandLawInput,
        discount_rate: float = 0.045,
    ):
        self.facility = facility
        self.cost = cost
        self.finance = finance
        self.price = price
        self.opex = opex
        self.crop = crop
        self.land_law = land_law
        self.discount_rate = discount_rate

    def average_annual_generation(self, years: int) -> float:
        if years <= 0:
            return 0.0
        return sum(self.yearly_generation(y) for y in range(1, years + 1)) / years

    def yearly_generation(self, year: int) -> float:
        base = self.facility.capacity_kw * self.facility.daily_gen_hours * 365
        return base * (1 - self.facility.efficiency_decline) ** (year - 1)

    def loan_schedule(self) -> LoanSchedule:
        return build_loan_schedule(
            principal=self.cost.total * (1 - self.finance.equity_ratio),
            rate=self.finance.loan_rate,
            grace_years=self.finance.grace_years,
            repay_years=self.finance.repay_years,
        )

    def upfront_equity(self) -> float:
        return self.cost.total * self.finance.equity_ratio

    def annual_loan_service(self) -> float:
        years = max(self.finance.grace_years + self.finance.repay_years, 1)
        return self.loan_schedule().total_payment / years

    def annual_finance_cost(self) -> float:
        return self.annual_loan_service()

    def total_annual_opex(self) -> float:
        return self.opex.total_excluding_finance + self.land_law.conversion_tax_per_year

    def annual_opex_for_cashflow(self) -> float:
        return self.total_annual_opex()

    def _inverter_cost(self, year: int) -> float:
        return self.opex.inverter_replace * 10 if year in (10, 20) else 0.0

    def annual_detail(self, year: int) -> AnnualCashFlow:
        operating = year <= min(self.land_law.max_operation_years, self.facility.lifetime_years)
        schedule = self.loan_schedule()
        generation = self.yearly_generation(year) if operating else 0.0
        crop = (
            self.crop.income_with_reduction(self.facility.area_m2)
            if operating else self.crop.base_income(self.facility.area_m2)
        )
        return AnnualCashFlow(
            year=year,
            generation_kwh=generation,
            power_revenue=generation * self.price.unit_price / 1000,
            crop_revenue=crop,
            steady_opex=self.opex.steady if operating else 0.0,
            inverter_cost=self._inverter_cost(year) if operating else 0.0,
            conversion_cost=self.land_law.conversion_tax_per_year if operating else 0.0,
            debt_interest=schedule.interest_in_year(year),
            debt_principal=schedule.principal_in_year(year),
        )

    def yearly_cash_flow(self, year: int) -> tuple[float, float]:
        """호환용 사업 현금흐름: (수입, 비금융 비용)."""
        d = self.annual_detail(year)
        return (
            d.power_revenue + d.crop_revenue,
            d.steady_opex + d.inverter_cost + d.conversion_cost,
        )

    @staticmethod
    def _pv(cash_flows: List[float], rate: float) -> float:
        return sum(cf / (1 + rate) ** t for t, cf in enumerate(cash_flows, start=1))

    @staticmethod
    def _npv(cash_flows: List[float], rate: float) -> float:
        return sum(cf / (1 + rate) ** t for t, cf in enumerate(cash_flows))

    @staticmethod
    def _annuity_factor(rate: float, n: int) -> float:
        if n <= 0:
            return 0.0
        return float(n) if rate == 0 else (1 - (1 + rate) ** -n) / rate

    def run(self) -> AnalysisResult:
        years = self.facility.lifetime_years
        details = [self.annual_detail(t) for t in range(1, years + 1)]
        project_flows = [-self.cost.total] + [d.operating_cash_flow for d in details]
        equity_flows = [-self.upfront_equity()] + [d.equity_cash_flow for d in details]

        pv_benefits = sum(
            (d.power_revenue + d.crop_revenue) / (1 + self.discount_rate) ** d.year
            for d in details
        )
        pv_operating_costs = sum(
            (d.steady_opex + d.inverter_cost + d.conversion_cost)
            / (1 + self.discount_rate) ** d.year
            for d in details
        )
        pv_costs = self.cost.total + pv_operating_costs
        project_npv = self._npv(project_flows, self.discount_rate)
        equity_npv = self._npv(equity_flows, self.discount_rate)

        debt_years = [d for d in details if d.debt_service > 0]
        dscrs = [d.operating_cash_flow / d.debt_service for d in debt_years]
        repayment_year = self.finance.grace_years + 1
        repayment_cash = next(
            (d.equity_cash_flow for d in details if d.year == repayment_year), None
        )

        op_years = min(self.land_law.max_operation_years, years)
        avg_gen = self.average_annual_generation(op_years)
        crop_reduced = self.crop.income_with_reduction(self.facility.area_m2)
        crop_base = self.crop.base_income(self.facility.area_m2)
        pv_power = sum(d.power_revenue / (1 + self.discount_rate) ** d.year for d in details)
        pv_crop = sum(d.crop_revenue / (1 + self.discount_rate) ** d.year for d in details)
        pv_crop_base = sum(crop_base / (1 + self.discount_rate) ** t for t in range(1, years + 1))

        return AnalysisResult(
            annual_generation_kwh=avg_gen,
            annual_power_revenue=avg_gen * self.price.unit_price / 1000,
            annual_crop_revenue=crop_reduced,
            annual_crop_revenue_base=crop_base,
            annual_opex=self.total_annual_opex(),
            annual_finance_cost=self.annual_finance_cost(),
            project_npv=project_npv,
            project_bc_ratio=pv_benefits / pv_costs if pv_costs else 0.0,
            project_irr=self._compute_irr(project_flows),
            project_payback_year=self._compute_payback(project_flows),
            equity_npv=equity_npv,
            equity_irr=self._compute_irr(equity_flows),
            equity_payback_year=self._compute_payback(equity_flows),
            minimum_dscr=min(dscrs) if dscrs else None,
            first_year_equity_cash=details[0].equity_cash_flow if details else 0.0,
            repayment_year_equity_cash=repayment_cash,
            npv_power=pv_power - pv_operating_costs,
            npv_crop=pv_crop_base,
            npv_crop_with_reduction=pv_crop,
            npv_baseline_crop_only=pv_crop_base,
            bc_vs_baseline=project_npv / pv_crop_base if pv_crop_base else 0.0,
            project_years=years,
            discount_rate=self.discount_rate,
            loan_schedule=self.loan_schedule(),
            annual_cash_flows=details,
            project_cash_flows=project_flows,
            equity_cash_flows=equity_flows,
        )

    @staticmethod
    def _compute_irr(cash_flows: List[float], guess: float = 0.1) -> Optional[float]:
        if not cash_flows or all(x >= 0 for x in cash_flows) or all(x <= 0 for x in cash_flows):
            return None

        def npv_at(rate: float) -> float:
            return sum(cf / (1 + rate) ** t for t, cf in enumerate(cash_flows))

        lo, hi = -0.99, 10.0
        f_lo, f_hi = npv_at(lo), npv_at(hi)
        if f_lo * f_hi > 0:
            return None
        for _ in range(240):
            mid = (lo + hi) / 2
            f_mid = npv_at(mid)
            if abs(f_mid) < 1e-7:
                return mid
            if f_lo * f_mid <= 0:
                hi = mid
            else:
                lo, f_lo = mid, f_mid
        return (lo + hi) / 2

    @staticmethod
    def _compute_payback(cash_flows: List[float]) -> Optional[float]:
        cumulative = cash_flows[0] if cash_flows else 0.0
        for year, flow in enumerate(cash_flows[1:], start=1):
            before = cumulative
            cumulative += flow
            if before < 0 <= cumulative:
                return year - 1 + (-before / flow if flow else 0)
        return None
