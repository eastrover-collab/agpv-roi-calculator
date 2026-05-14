"""시나리오 빌더 — 단일/복합 변수 시나리오 + 리스크 프리미엄.

KREI(2023) PDF 표 4-7 (단일요인), 표 4-8 (복합 18개), 표 4-11 (리스크) 재현.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.calculator import (
    CostInput,
    CropInput,
    EconomicAnalysis,
    FacilityInput,
    FinanceInput,
    LandLawInput,
    OpexInput,
    PowerPriceInput,
    AnalysisResult,
)


@dataclass
class ScenarioResult:
    """시나리오 1개의 결과."""
    name: str
    description: str
    params: Dict[str, Any]  # 변경된 파라미터
    result: AnalysisResult

    @property
    def bc(self) -> float:
        return self.result.bc_ratio

    @property
    def irr(self) -> Optional[float]:
        return self.result.irr


@dataclass
class ScenarioBuilder:
    """시나리오 분석 묶음 실행기."""
    facility: FacilityInput
    cost: CostInput
    finance: FinanceInput
    price: PowerPriceInput
    opex: OpexInput
    crop: CropInput
    land_law: LandLawInput
    discount_rate: float = 0.028

    def _run(
        self,
        *,
        price_override: Optional[float] = None,
        loan_rate_override: Optional[float] = None,
        cost_multiplier: float = 1.0,
        discount_rate_override: Optional[float] = None,
        land_law_override: Optional[LandLawInput] = None,
        finance_override: Optional[FinanceInput] = None,
    ) -> AnalysisResult:
        """단일 실행 — 변수 override 가능."""
        price = copy.deepcopy(self.price)
        if price_override is not None:
            price.override_krw_per_kwh = price_override

        cost = copy.deepcopy(self.cost)
        cost.construction = self.cost.construction * cost_multiplier
        # permits 는 변경 없음 (PDF 표 4-7 기준)

        finance = finance_override if finance_override else copy.deepcopy(self.finance)
        if loan_rate_override is not None:
            finance.loan_rate = loan_rate_override

        land_law = land_law_override if land_law_override else self.land_law

        analysis = EconomicAnalysis(
            facility=self.facility,
            cost=cost,
            finance=finance,
            price=price,
            opex=self.opex,
            crop=self.crop,
            land_law=land_law,
            discount_rate=discount_rate_override or self.discount_rate,
        )
        return analysis.run()

    # ─── 단일요인 시나리오 (PDF 표 4-7) ──────────────────
    def single_factor_scenarios(self) -> List[ScenarioResult]:
        """베이스라인 + S1~S5."""
        results = []
        # BL
        results.append(ScenarioResult(
            name="BL",
            description="베이스라인 (현행)",
            params={"price": self.price.unit_price, "rate": self.finance.loan_rate, "cost_mult": 1.0},
            result=self._run(),
        ))
        # S1: 발전가격 하락 (152.4)
        results.append(ScenarioResult(
            name="S1",
            description="매전가격 하락 (152.4원/kWh)",
            params={"price": 152.4},
            result=self._run(price_override=152.4),
        ))
        # S2: 발전가격 크게 하락 (141.9)
        results.append(ScenarioResult(
            name="S2",
            description="매전가격 크게 하락 (141.9원/kWh)",
            params={"price": 141.9},
            result=self._run(price_override=141.9),
        ))
        # S3: 대출금리 1.75%
        results.append(ScenarioResult(
            name="S3",
            description="정책금리 인하 (1.75%)",
            params={"rate": 0.0175},
            result=self._run(loan_rate_override=0.0175),
        ))
        # S4: 설치비 15% 하락
        results.append(ScenarioResult(
            name="S4",
            description="설치비 15% 하락",
            params={"cost_mult": 0.85},
            result=self._run(cost_multiplier=0.85),
        ))
        # S5: 설치비 15% 상승
        results.append(ScenarioResult(
            name="S5",
            description="설치비 15% 상승",
            params={"cost_mult": 1.15},
            result=self._run(cost_multiplier=1.15),
        ))
        return results

    # ─── 현재 입력값 기준 단일요인 시나리오 ─────────────────
    def current_input_scenarios(self) -> List[ScenarioResult]:
        """사용자가 입력한 현재 조건을 기준으로 주요 변수를 흔든다.

        농가용 UI에서는 PDF 고정값보다 현재 입력값의 ±변화가 더 유용하다.
        PDF 표 재현용 시나리오는 single_factor_scenarios()에 보존한다.
        """
        base_price = self.price.unit_price
        base_rate = self.finance.loan_rate
        lower_rate = max(base_rate - 0.01, 0.001)

        return [
            ScenarioResult(
                name="BL",
                description="현재 입력값",
                params={"price": base_price, "rate": base_rate, "cost_mult": 1.0},
                result=self._run(),
            ),
            ScenarioResult(
                name="P-15",
                description=f"발전단가 15% 하락 ({base_price * 0.85:.1f}원/kWh)",
                params={"price": base_price * 0.85},
                result=self._run(price_override=base_price * 0.85),
            ),
            ScenarioResult(
                name="P+15",
                description=f"발전단가 15% 상승 ({base_price * 1.15:.1f}원/kWh)",
                params={"price": base_price * 1.15},
                result=self._run(price_override=base_price * 1.15),
            ),
            ScenarioResult(
                name="C-15",
                description="설치비 15% 절감",
                params={"cost_mult": 0.85},
                result=self._run(cost_multiplier=0.85),
            ),
            ScenarioResult(
                name="C+15",
                description="설치비 15% 증가",
                params={"cost_mult": 1.15},
                result=self._run(cost_multiplier=1.15),
            ),
            ScenarioResult(
                name="R-1",
                description=f"금리 1%p 인하 ({lower_rate * 100:.2f}%)",
                params={"rate": lower_rate},
                result=self._run(loan_rate_override=lower_rate),
            ),
            ScenarioResult(
                name="R+1",
                description=f"금리 1%p 인상 ({(base_rate + 0.01) * 100:.2f}%)",
                params={"rate": base_rate + 0.01},
                result=self._run(loan_rate_override=base_rate + 0.01),
            ),
        ]

    # ─── 복합요인 시나리오 (PDF 표 4-8) ──────────────────
    def composite_scenarios(self) -> List[ScenarioResult]:
        """18개 조합: 3 (발전단가) × 2 (금리) × 3 (설치비)."""
        prices = [
            (162.9, "현행"),
            (152.4, "하락"),
            (141.9, "크게 하락"),
        ]
        rates = [
            (0.028, "현행"),
            (0.0175, "인하"),
        ]
        cost_mults = [
            (1.0, "현행", "0%"),
            (1.15, "증가", "15%"),
            (0.85, "감소", "-15%"),
        ]

        results = []
        idx = 1
        for p, plabel in prices:
            for r, rlabel in rates:
                for c, clabel, csign in cost_mults:
                    desc = f"매전가격 {plabel} + 금리 {rlabel} + 설치비 {csign}"
                    results.append(ScenarioResult(
                        name=f"S{idx}",
                        description=desc,
                        params={"price": p, "rate": r, "cost_mult": c},
                        result=self._run(
                            price_override=p,
                            loan_rate_override=r,
                            cost_multiplier=c,
                        ),
                    ))
                    idx += 1
        return results

    # ─── 리스크 프리미엄 시나리오 (PDF 표 4-11) ───────────
    def risk_premium_scenarios(self) -> List[ScenarioResult]:
        """할인율 4.5 / 9.5 / 14.5 / 19.5% — 시중금리 4.5%, 20년 분할 가정."""
        market_finance = FinanceInput(
            equity_ratio=self.finance.equity_ratio,
            loan_rate=0.045,         # 시중금리
            grace_years=0,
            repay_years=20,
        )
        risk_levels = [
            ("BL",  0.045, "기준 할인율 4.5%"),
            ("S1",  0.095, "리스크 프리미엄 (낮음) → 9.5%"),
            ("S2",  0.145, "리스크 프리미엄 (중간) → 14.5%"),
            ("S3",  0.195, "리스크 프리미엄 (높음) → 19.5%"),
        ]
        results = []
        for name, dr, desc in risk_levels:
            results.append(ScenarioResult(
                name=name,
                description=desc,
                params={"discount": dr, "loan_rate": 0.045},
                result=self._run(
                    discount_rate_override=dr,
                    finance_override=market_finance,
                ),
            ))
        return results
