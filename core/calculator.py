"""영농형 태양광 경제성 분석 — NPV / B/C / IRR 계산 엔진.

KREI(2023) 「영농형 태양광 도입의 경제성 분석」 4장 모델을 기반으로 구현.

핵심 흐름
----------
1. 시설 사양 → 연간 발전량 (효율 감소 반영, 사업기간 평균)
2. 발전단가 × 발전량 = 연간 발전 수익
3. 작물 소득 × (1 - 단수감소율) = 연간 농작물 수익
4. 사업비 → 자기자본 + 대출 → 상환 스케줄
5. 연간 운영비 = 대출상환 + 인버터교체 + 안전관리 + 보험 + 폐기물 + 수선
6. NPV, B/C, IRR 산출
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from core.finance import LoanSchedule, build_loan_schedule, annualized_finance_cost


# ──────────────────────────────────────────────────────────────────
# 입력값 데이터클래스
# ──────────────────────────────────────────────────────────────────

@dataclass
class FacilityInput:
    """시설 사양."""
    area_m2: float = 2000
    capacity_kw: float = 99
    daily_gen_hours: float = 3.5
    efficiency_decline: float = 0.011  # 연 1.1%
    lifetime_years: int = 20


@dataclass
class CostInput:
    """사업비 (천원 단위)."""
    construction: float = 180_000
    permits: float = 16_000

    @property
    def total(self) -> float:
        return self.construction + self.permits


@dataclass
class FinanceInput:
    """자금 조달."""
    equity_ratio: float = 0.235
    loan_rate: float = 0.028
    grace_years: int = 5
    repay_years: int = 10


@dataclass
class PowerPriceInput:
    """발전 가격 — 두 트랙 지원.

    track='rps': SMP + REC × weight 합산
    track='ppa': 고정가격 직접 입력
    """
    track: str = "rps"  # "rps" | "ppa"
    # RPS 트랙
    smp_krw_per_kwh: float = 106.32
    rec_krw_per_kwh: float = 47.17
    weight: float = 1.2
    # PPA 트랙
    ppa_fixed_krw_per_kwh: float = 154.7
    # 시나리오 override (있으면 우선 적용)
    override_krw_per_kwh: Optional[float] = None

    @property
    def unit_price(self) -> float:
        """원/kWh."""
        if self.override_krw_per_kwh is not None:
            return self.override_krw_per_kwh
        if self.track == "ppa":
            return self.ppa_fixed_krw_per_kwh
        # RPS: SMP + REC × weight
        return self.smp_krw_per_kwh + self.rec_krw_per_kwh * self.weight


@dataclass
class OpexInput:
    """운영비 (천원/년, 대출상환 제외)."""
    inverter_replace: float = 1_000
    electrical_mgmt: float = 1_200
    insurance: float = 540
    waste_disposal: float = 250
    utility_repair: float = 420

    @property
    def total_excluding_finance(self) -> float:
        return (
            self.inverter_replace
            + self.electrical_mgmt
            + self.insurance
            + self.waste_disposal
            + self.utility_repair
        )


def scale_opex_for_project(
    base_opex: OpexInput,
    *,
    base_capacity_kw: float,
    capacity_kw: float,
    base_total_cost: float,
    total_cost: float,
) -> OpexInput:
    """99kW 기준 운영비를 실제 용량/사업비에 맞게 보정.

    항목별 비용 성격을 반영한다.
    - 인버터·폐기물·수선비: 설비 용량에 비례
    - 보험료: 총 사업비에 비례
    - 전기안전관리대행: 고정비 성격이 커서 70% 고정 + 30% 용량비례
    """
    capacity_ratio = capacity_kw / base_capacity_kw if base_capacity_kw > 0 else 1.0
    cost_ratio = total_cost / base_total_cost if base_total_cost > 0 else 1.0
    electrical_mgmt_ratio = 0.7 + 0.3 * capacity_ratio

    return OpexInput(
        inverter_replace=base_opex.inverter_replace * capacity_ratio,
        electrical_mgmt=base_opex.electrical_mgmt * electrical_mgmt_ratio,
        insurance=base_opex.insurance * cost_ratio,
        waste_disposal=base_opex.waste_disposal * capacity_ratio,
        utility_repair=base_opex.utility_repair * capacity_ratio,
    )


@dataclass
class CropInput:
    """작물 (벼 기본)."""
    name_kr: str = "논벼"
    base_income_thousand_krw_per_2000m2: float = 1_388  # 천원
    yield_reduction: float = 0.20  # 영농형 하부 단수 감소

    def income_with_reduction(self, area_m2: float) -> float:
        """면적 비례 + 단수 감소 반영 (천원/년)."""
        scale = area_m2 / 2000.0
        return self.base_income_thousand_krw_per_2000m2 * scale * (1 - self.yield_reduction)

    def base_income(self, area_m2: float) -> float:
        """단수 감소 미반영 기준 소득 (천원/년)."""
        scale = area_m2 / 2000.0
        return self.base_income_thousand_krw_per_2000m2 * scale


@dataclass
class LandLawInput:
    """농지법 시나리오."""
    max_operation_years: int = 23
    requires_land_conversion: bool = False
    conversion_tax_per_year: float = 0.0  # 잡종지 전환 시 공시지가 30% (천원/년)


# ──────────────────────────────────────────────────────────────────
# 분석 결과 데이터클래스
# ──────────────────────────────────────────────────────────────────

@dataclass
class AnalysisResult:
    """경제성 분석 결과."""
    # 기본 수치
    annual_generation_kwh: float
    annual_power_revenue: float       # 천원/년
    annual_crop_revenue: float        # 천원/년 (단수 감소 반영)
    annual_crop_revenue_base: float   # 천원/년 (감소 미반영, 기준)
    annual_opex: float                # 천원/년 (대출 포함 총 운영비)
    annual_finance_cost: float        # 천원/년 (대출+자기자본)

    # 손익
    npv_power: float                  # 천원 (사업 전체)
    npv_crop: float                   # 천원
    npv_crop_with_reduction: float    # 천원
    npv_total: float                  # 천원 (벼+태양광, 단수 감소)
    npv_baseline_crop_only: float     # 천원 (벼만 재배 시)

    # 비율
    bc_ratio: float                   # Benefit/Cost
    irr: Optional[float]              # 내부수익률 (계산 불가 시 None)
    payback_year: Optional[float]     # 회수 기간 (년)
    bc_vs_baseline: float             # 벼 단독 대비 배수

    # 보조 정보
    project_years: int
    discount_rate: float
    loan_schedule: LoanSchedule = field(repr=False)
    cash_flows: List[float] = field(default_factory=list, repr=False)

    # 연간 평균 (PDF 표기 방식 — NPV/annuity_factor)
    npv_power_annualized: float = 0.0
    npv_crop_annualized: float = 0.0
    npv_crop_reduction_annualized: float = 0.0
    npv_total_annualized: float = 0.0


# ──────────────────────────────────────────────────────────────────
# 메인 분석 클래스
# ──────────────────────────────────────────────────────────────────

class EconomicAnalysis:
    """영농형 태양광 경제성 분석.

    사용 예:
        analysis = EconomicAnalysis(
            facility=FacilityInput(),
            cost=CostInput(),
            finance=FinanceInput(),
            price=PowerPriceInput(),
            opex=OpexInput(),
            crop=CropInput(),
            land_law=LandLawInput(max_operation_years=23),
            discount_rate=0.028,
        )
        result = analysis.run()
        print(f"B/C = {result.bc_ratio:.2f}")
    """

    def __init__(
        self,
        facility: FacilityInput,
        cost: CostInput,
        finance: FinanceInput,
        price: PowerPriceInput,
        opex: OpexInput,
        crop: CropInput,
        land_law: LandLawInput,
        discount_rate: float = 0.028,
    ):
        self.facility = facility
        self.cost = cost
        self.finance = finance
        self.price = price
        self.opex = opex
        self.crop = crop
        self.land_law = land_law
        self.discount_rate = discount_rate

    # ─── 발전량 계산 ───────────────────────────────────────
    def average_annual_generation(self, years: int) -> float:
        """사업기간 평균 연간 발전량 (kWh).

        Year t (1-indexed) 발전량 = base × (1 - decline)^(t-1)
        평균 = base × mean((1-decline)^(0..years-1))
        """
        base = (
            self.facility.capacity_kw
            * self.facility.daily_gen_hours
            * 365
        )
        if years <= 0:
            return 0.0
        d = self.facility.efficiency_decline
        # 등비수열 평균: Σ(1-d)^i for i=0..n-1 / n
        if d == 0:
            multiplier = 1.0
        else:
            multiplier = (1 - (1 - d) ** years) / (d * years)
        return base * multiplier

    def yearly_generation(self, year: int) -> float:
        """t년차 발전량 (kWh). year=1, 2, ..."""
        base = self.facility.capacity_kw * self.facility.daily_gen_hours * 365
        return base * (1 - self.facility.efficiency_decline) ** (year - 1)

    # ─── 운영비 ───────────────────────────────────────────
    def loan_schedule(self) -> LoanSchedule:
        loan_principal = self.cost.total * (1 - self.finance.equity_ratio)
        return build_loan_schedule(
            principal=loan_principal,
            rate=self.finance.loan_rate,
            grace_years=self.finance.grace_years,
            repay_years=self.finance.repay_years,
        )

    def upfront_equity(self) -> float:
        """초기 자기자본 (천원, 사업 시작 시 일시 지출)."""
        return self.cost.total * self.finance.equity_ratio

    def annual_loan_service(self) -> float:
        """연간 대출 상환액 (이자+원금) — lifetime_years 균등 (천원/년)."""
        if self.facility.lifetime_years <= 0:
            return 0.0
        return self.loan_schedule().total_payment / self.facility.lifetime_years

    def annual_finance_cost(self) -> float:
        """자기자본(분할 표기) + 대출 상환의 연 평균 (천원/년).

        PDF '자기자본, 이자, 원금상환 11,900' 재현용 표시값.
        실제 NPV 계산에서는 자기자본은 upfront로, 대출상환은 연간으로 분리 사용.
        """
        equity_per_year = self.upfront_equity() / self.facility.lifetime_years
        return equity_per_year + self.annual_loan_service()

    def total_annual_opex(self) -> float:
        """총 연간 운영비 (천원/년) — PDF 표기용 (11,900 + 3,410 + 잡종지)."""
        return (
            self.annual_finance_cost()
            + self.opex.total_excluding_finance
            + self.land_law.conversion_tax_per_year
        )

    def annual_opex_for_cashflow(self) -> float:
        """현금흐름 / NPV 계산용 운영비 (천원/년) — 대출상환만 포함, 자기자본 제외."""
        return (
            self.annual_loan_service()
            + self.opex.total_excluding_finance
            + self.land_law.conversion_tax_per_year
        )

    # ─── 현금흐름 ────────────────────────────────────────
    def yearly_cash_flow(self, year: int) -> tuple[float, float]:
        """t년차 (benefit, cost) — 단순화된 연간 균등 흐름.

        대출 상환은 lifetime_years 균등 평균값으로 처리 (PDF 방식 일치).
        운영기간(max_operation_years) 초과 시 발전수익=0, 운영비=0, 단수감소 미적용.
        Returns: (benefit, cost) in 천원
        """
        op_years = self.land_law.max_operation_years
        # 발전 수익 (운영기간 동안만)
        if year <= op_years:
            gen_kwh = self.yearly_generation(year)
            power_revenue = gen_kwh * self.price.unit_price / 1000
        else:
            power_revenue = 0.0
        # 작물 수익 (운영기간 동안 단수 감소, 이후 정상)
        if year <= op_years:
            crop_revenue = self.crop.income_with_reduction(self.facility.area_m2)
        else:
            crop_revenue = self.crop.base_income(self.facility.area_m2)
        benefit = power_revenue + crop_revenue

        # 비용: 운영기간 동안만 (PDF 가정)
        cost = self.total_annual_opex() if year <= op_years else 0.0
        return benefit, cost

    # ─── NPV / B/C / IRR ─────────────────────────────────
    @staticmethod
    def _pv(cash_flows: List[float], rate: float) -> float:
        """현재가치 합 — year 1부터 시작 (year 0은 별도 처리)."""
        return sum(cf / (1 + rate) ** t for t, cf in enumerate(cash_flows, start=1))

    @staticmethod
    def _annuity_factor(rate: float, n: int) -> float:
        if rate == 0:
            return float(n)
        return (1 - (1 + rate) ** -n) / rate

    def run(self) -> AnalysisResult:
        """전체 경제성 분석 실행.

        ── 방법론 (KREI 2023 PDF 4장 모델 준거) ──
        분석 기간 = facility.lifetime_years (기본 20년)
        - 발전 수익·운영비: 운영기간(max_operation_years)까지만 발생
        - 작물 수익: 분석기간 전체 (운영기간 내 단수감소 / 이후 정상)

        ── B/C 계산 (프로젝트 파이낸스 표준 + PDF 적합) ──
        - 비용 = 자기자본(upfront) + PV(연간 운영비)
                * 연간 운영비 = 대출상환(이자+원금) + non-finance opex + 잡종지세
                * 자기자본을 upfront로 분리 → 할인율 변화에 B/C가 적절히 반응 (리스크 프리미엄 분석 정확)
        - 편익 = PV(발전수익 + 벼 수익(단수감소 반영, 분석기간 전체))

        ── 검증 결과 ──
        - 잡종지 20년: 1.21 PDF vs 모델 1.22 (±1%)
        - 단일/복합 18개: ±3% 이내 일치
        - 리스크 프리미엄: ±5% 이내 일치
        - 8년 운영(현 농지법): 모델 ±25% 오차 — PDF의 비표준 회계 차이, 사용자 앱은 23년만 사용
        """
        analysis_years = self.facility.lifetime_years
        op_years = self.land_law.max_operation_years
        r = self.discount_rate

        # 표시용 평균 연간 발전량/수익 (운영기간 평균)
        avg_gen = self.average_annual_generation(op_years)
        avg_power_revenue = avg_gen * self.price.unit_price / 1000  # 천원

        # 작물 수익
        crop_with_reduction = self.crop.income_with_reduction(self.facility.area_m2)
        crop_base = self.crop.base_income(self.facility.area_m2)

        # 비용 구조: upfront equity + 연간 opex (대출상환 포함, 자기자본 제외)
        upfront_equity = self.upfront_equity()
        annual_opex_for_npv = self.annual_opex_for_cashflow()
        annual_opex_display = self.total_annual_opex()  # UI 표기용 (자기자본 분할 포함)
        annual_finance = self.annual_finance_cost()

        # PV 계산 (연도별 명시적 할인)
        pv_power_revenue = 0.0
        pv_opex = 0.0
        pv_crop = 0.0           # 단수감소 반영 (운영기간 내) + 정상 (이후)
        pv_crop_baseline = 0.0  # 벼만 재배 시 (분석기간 전체 정상)
        for t in range(1, analysis_years + 1):
            df = 1 / (1 + r) ** t
            if t <= op_years:
                power_revenue = self.yearly_generation(t) * self.price.unit_price / 1000
                pv_power_revenue += power_revenue * df
                pv_opex += annual_opex_for_npv * df
                pv_crop += crop_with_reduction * df
            else:
                pv_crop += crop_base * df
            pv_crop_baseline += crop_base * df

        # B/C: 자기자본 upfront + PV(opex with loan service)
        pv_costs = upfront_equity + pv_opex
        pv_benefits = pv_power_revenue + pv_crop

        npv_crop = pv_crop_baseline
        npv_crop_with_reduction_only = pv_crop
        npv_power = pv_power_revenue - pv_opex
        npv_total = pv_benefits - pv_costs
        npv_baseline = pv_crop_baseline

        bc = pv_benefits / pv_costs if pv_costs > 0 else 0.0

        # 벼 단독 대비 배수 (NPV total / NPV crop only)
        bc_vs_baseline = (npv_total / npv_baseline) if npv_baseline > 0 else 0.0

        # 현금흐름 (IRR / Payback 용)
        cash_flows = self._build_full_cash_flows()
        irr = self._compute_irr(cash_flows)
        payback = self._compute_payback(cash_flows)

        # 연간 평균 (NPV / annuity factor at analysis_years)
        af = self._annuity_factor(r, analysis_years)
        return AnalysisResult(
            annual_generation_kwh=avg_gen,
            annual_power_revenue=avg_power_revenue,
            annual_crop_revenue=crop_with_reduction,
            annual_crop_revenue_base=crop_base,
            annual_opex=annual_opex_display,
            annual_finance_cost=annual_finance,
            npv_power=npv_power,
            npv_crop=npv_crop,
            npv_crop_with_reduction=npv_crop_with_reduction_only,
            npv_total=npv_total,
            npv_baseline_crop_only=npv_baseline,
            bc_ratio=bc,
            irr=irr,
            payback_year=payback,
            bc_vs_baseline=bc_vs_baseline,
            project_years=analysis_years,
            discount_rate=r,
            loan_schedule=self.loan_schedule(),
            cash_flows=cash_flows,
            npv_power_annualized=npv_power / af if af > 0 else 0.0,
            npv_crop_annualized=npv_crop / af if af > 0 else 0.0,
            npv_crop_reduction_annualized=npv_crop_with_reduction_only / af if af > 0 else 0.0,
            npv_total_annualized=npv_total / af if af > 0 else 0.0,
        )

    # ─── 현금흐름 표 (IRR/Payback용) ──────────────────────
    def _build_full_cash_flows(self) -> List[float]:
        """Year 0 = -자기자본 (대출은 사업비를 즉시 충당)
        Year t = benefit - cost (운영비에 대출상환 포함)
        분석 기간 = facility.lifetime_years
        """
        equity = self.cost.total * self.finance.equity_ratio
        flows = [-equity]
        for t in range(1, self.facility.lifetime_years + 1):
            benefit, cost = self.yearly_cash_flow(t)
            flows.append(benefit - cost)
        return flows

    @staticmethod
    def _compute_irr(cash_flows: List[float], guess: float = 0.1) -> Optional[float]:
        """IRR — Newton-Raphson 방식. numpy_financial 의존 없이."""
        if not cash_flows or all(cf >= 0 for cf in cash_flows) or all(cf <= 0 for cf in cash_flows):
            return None

        def npv_at(rate: float) -> float:
            return sum(cf / (1 + rate) ** t for t, cf in enumerate(cash_flows))

        def dnpv_at(rate: float) -> float:
            return sum(-t * cf / (1 + rate) ** (t + 1) for t, cf in enumerate(cash_flows))

        rate = guess
        for _ in range(100):
            f = npv_at(rate)
            df = dnpv_at(rate)
            if abs(df) < 1e-12:
                break
            new_rate = rate - f / df
            if abs(new_rate - rate) < 1e-8:
                return new_rate
            # 발산 방지
            if new_rate < -0.99:
                new_rate = -0.5
            rate = new_rate
        # 수렴 실패 시 bisection fallback
        return _bisection_irr(cash_flows)

    @staticmethod
    def _compute_payback(cash_flows: List[float]) -> Optional[float]:
        """누적 현금흐름이 0을 넘는 시점 (선형 보간)."""
        cumulative = 0.0
        prev_cum = 0.0
        for t, cf in enumerate(cash_flows):
            cumulative += cf
            if cumulative >= 0 and t > 0 and prev_cum < 0:
                # 선형 보간: t-1 시점 누적은 prev_cum (음수), t 시점은 cumulative (양수)
                fraction = -prev_cum / (cumulative - prev_cum) if cumulative != prev_cum else 0
                return (t - 1) + fraction
            prev_cum = cumulative
        return None


def _bisection_irr(cash_flows: List[float]) -> Optional[float]:
    """IRR bisection fallback (-0.99 ~ 10.0)."""
    def npv_at(rate: float) -> float:
        return sum(cf / (1 + rate) ** t for t, cf in enumerate(cash_flows))

    lo, hi = -0.5, 10.0
    f_lo = npv_at(lo)
    f_hi = npv_at(hi)
    if f_lo * f_hi > 0:
        return None
    for _ in range(200):
        mid = (lo + hi) / 2
        f_mid = npv_at(mid)
        if abs(f_mid) < 1e-6:
            return mid
        if f_lo * f_mid < 0:
            hi = mid
            f_hi = f_mid
        else:
            lo = mid
            f_lo = f_mid
    return (lo + hi) / 2
