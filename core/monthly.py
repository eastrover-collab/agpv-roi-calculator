"""실제 월별 현금흐름 분석 — 균등화 안 된 raw 통장 흐름.

기존 calculator.py는 B/C 계산을 위해 자기자본·대출상환을 lifetime으로 균등화함.
이 모듈은 실제로 농가 통장에 매월 들어오고 나가는 돈을 그대로 보여줌.

주요 변화 시점:
  Year 0:    자기자본 일시 투입
  Year 1~5:  거치 기간 (이자만 납부 — 매월 부담 가벼움)
  Year 6:    원금 상환 시작 (매월 부담 급증)
  Year 10:   인버터 1차 교체 (일시)
  Year 15:   융자 완료 (대출 부담 0)
  Year 20:   인버터 2차 교체 (일시)
  Year 23:   사업 종료
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple

from core.calculator import EconomicAnalysis


# ──────────────────────────────────────────────────────────────────
# 데이터 구조
# ──────────────────────────────────────────────────────────────────

@dataclass
class YearlyDetail:
    """t년차 실제 현금흐름 (천원 단위)."""
    year: int
    power_revenue: float          # 발전 수익 (변동: 효율 감소)
    loan_interest: float          # 대출 이자 (잔액에 따라 변동)
    loan_principal: float         # 대출 원금 상환
    other_opex_steady: float      # 정기 운영비 (전기안전·보험·폐기물·수선)
    inverter_cost: float          # 인버터 교체 (10년/20년차 일시)
    crop_income: float            # 벼 수확 (가을 일시)

    @property
    def monthly_power(self) -> float:
        """월평균 발전 수익 (천원/월)."""
        return self.power_revenue / 12

    @property
    def monthly_loan(self) -> float:
        """월평균 대출 상환 (천원/월)."""
        return (self.loan_interest + self.loan_principal) / 12

    @property
    def monthly_other_opex(self) -> float:
        """월평균 운영비 (천원/월)."""
        return self.other_opex_steady / 12

    @property
    def monthly_net_excluding_crop(self) -> float:
        """월평균 순흐름 (벼 수확 제외) — 평상시 통장 흐름."""
        return self.monthly_power - self.monthly_loan - self.monthly_other_opex

    @property
    def annual_net(self) -> float:
        """연간 순이익 (모든 항목 합산)."""
        return (
            self.power_revenue + self.crop_income
            - self.loan_interest - self.loan_principal
            - self.other_opex_steady - self.inverter_cost
        )


@dataclass
class RegimeBlock:
    """동일 패턴이 지속되는 연도 구간 — '이하 동일' 압축용."""
    year_start: int
    year_end: int
    monthly_power: float
    monthly_loan: float
    monthly_other_opex: float
    monthly_net: float            # 발전 - 대출 - 운영비 (벼 제외)
    annual_crop: float            # 가을 수확 일시 (벼 단수감소 반영)
    annual_net_avg: float         # 연간 평균 순이익
    events: List[Tuple[int, str, float]] = field(default_factory=list)
    label: str = ""               # 사람이 읽을 라벨 ("거치 기간" 등)

    @property
    def n_years(self) -> int:
        return self.year_end - self.year_start + 1


# ──────────────────────────────────────────────────────────────────
# 메인 함수
# ──────────────────────────────────────────────────────────────────

def build_yearly_details(analysis: EconomicAnalysis) -> List[YearlyDetail]:
    """사업 1년차부터 시설수명까지 실제 현금흐름 (균등화 안 함)."""
    details = []
    schedule = analysis.loan_schedule()
    op_years = analysis.land_law.max_operation_years

    # 인버터 교체 주기: 10년 (총 비용은 PDF의 annualized 1,000 천원 × 10 = 10,000 천원으로 추정)
    inverter_one_time_cost = analysis.opex.inverter_replace * 10
    inverter_years = {10, 20}  # lifetime 23년 내에서 2회 교체

    # 운영비 (인버터 제외)
    steady_opex = (
        analysis.opex.electrical_mgmt
        + analysis.opex.insurance
        + analysis.opex.waste_disposal
        + analysis.opex.utility_repair
    )

    for t in range(1, analysis.facility.lifetime_years + 1):
        # 발전 수익 (운영기간 동안만, 효율 감소 반영)
        if t <= op_years:
            gen = analysis.yearly_generation(t)
            power_revenue = gen * analysis.price.unit_price / 1000
        else:
            power_revenue = 0.0

        # 대출 상환 (스케줄에서 가져옴, 균등화 안 함)
        interest = schedule.interest_in_year(t)
        principal = schedule.principal_in_year(t)

        # 정기 운영비 (운영기간 동안만)
        other = steady_opex if t <= op_years else 0.0

        # 인버터 교체 (특정 연도만 일시)
        inverter = inverter_one_time_cost if (t in inverter_years and t <= op_years) else 0.0

        # 벼 수확 (가을 일시) — 운영기간 단수감소 / 이후 정상
        if t <= op_years:
            crop = analysis.crop.income_with_reduction(analysis.facility.area_m2)
        else:
            crop = analysis.crop.base_income(analysis.facility.area_m2)

        details.append(YearlyDetail(
            year=t,
            power_revenue=power_revenue,
            loan_interest=interest,
            loan_principal=principal,
            other_opex_steady=other,
            inverter_cost=inverter,
            crop_income=crop,
        ))
    return details


def group_into_regimes(details: List[YearlyDetail], threshold_thousand_krw: float = 100) -> List[RegimeBlock]:
    """연속된 동일 패턴 연도를 압축. threshold(천원/월) 이내 차이는 같은 블록."""
    if not details:
        return []

    blocks: List[RegimeBlock] = []

    def _start_block(d: YearlyDetail) -> RegimeBlock:
        block = RegimeBlock(
            year_start=d.year,
            year_end=d.year,
            monthly_power=d.monthly_power,
            monthly_loan=d.monthly_loan,
            monthly_other_opex=d.monthly_other_opex,
            monthly_net=d.monthly_net_excluding_crop,
            annual_crop=d.crop_income,
            annual_net_avg=d.annual_net,
        )
        if d.inverter_cost > 0:
            block.events.append((d.year, "인버터 교체", -d.inverter_cost))
        return block

    current = _start_block(details[0])
    running_nets = [details[0].annual_net]

    for d in details[1:]:
        same_pattern = (
            abs(d.monthly_net_excluding_crop - current.monthly_net) < threshold_thousand_krw
            and d.inverter_cost == 0
            and (d.power_revenue > 0) == (current.monthly_power > 0)  # 운영/비운영 전환 분리
        )
        if same_pattern:
            current.year_end = d.year
            running_nets.append(d.annual_net)
        else:
            # 이전 블록 마무리
            current.annual_net_avg = sum(running_nets) / len(running_nets)
            blocks.append(current)
            # 새 블록 시작
            current = _start_block(d)
            running_nets = [d.annual_net]

    current.annual_net_avg = sum(running_nets) / len(running_nets)
    blocks.append(current)

    # 라벨링
    for block in blocks:
        block.label = _label_for_regime(block)
    return blocks


def _label_for_regime(block: RegimeBlock) -> str:
    """블록 성격을 한 줄 라벨로 표현. 대출 상태가 우선, 인버터 등 이벤트는 별도 박스."""
    if block.monthly_power == 0:
        return "사업 종료 (벼 수확만 남음)"
    if block.monthly_loan == 0:
        return "융자 완료 — 순수익 시기 🎉"
    # 거치 vs 분할 판단: monthly_loan < 50만원이면 이자만 (대출 150,000천원 × 2.8% / 12 = 350천원/월)
    if block.monthly_loan < 500:
        return "거치 기간 — 이자만 납부"
    return "원금+이자 상환 중"


def upfront_equity(analysis: EconomicAnalysis) -> float:
    """Year 0 자기자본 일시 투입 (천원)."""
    return analysis.upfront_equity()
