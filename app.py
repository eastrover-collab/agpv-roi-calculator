"""영농형 태양광 경제성 계산기 — Streamlit 앱."""
from __future__ import annotations

import urllib.parse

import streamlit as st

from core.calculator import (
    CostInput, CropInput, EconomicAnalysis, FacilityInput, FinanceInput,
    LandLawInput, OpexInput, PowerPriceInput, scale_opex_for_project,
)
from core.config import load_assumptions
from core.scenarios import ScenarioBuilder
from ui.tabs import render_cashflow_tab, render_sensitivity_tab, render_summary_tab


st.set_page_config(page_title="영농형 태양광 경제성 계산기", page_icon="🌾", layout="wide")
st.markdown("""
<style>
:root { --kifc-green:#17463f; --kifc-mint:#e9f1ee; --kifc-gold:#ca7a27; }
.main .block-container { max-width:1180px; padding-top:1.4rem; padding-bottom:3rem; }
h1,h2,h3 { color:var(--kifc-green); letter-spacing:-.025em; }
[data-testid="stMetric"] { background:#f7f9f8; border:1px solid #dce5e1; border-radius:12px; padding:14px; }
[data-testid="stMetricValue"] { color:#153f39; font-size:1.75rem; }
[data-testid="stTabs"] [role="tablist"] { gap:.6rem; border-bottom:none; flex-wrap:wrap; }
[data-testid="stTabs"] [role="tab"] {
  min-height:44px; padding:.5rem 1.5rem;
  border:1.5px solid #c3d2cc; border-radius:999px;
  background:#fff; color:var(--kifc-green);
  transition:background .15s, color .15s, border-color .15s;
}
[data-testid="stTabs"] [role="tab"] p { font-size:.95rem; font-weight:700; color:inherit; }
[data-testid="stTabs"] [role="tab"]:hover { background:var(--kifc-mint); }
[data-testid="stTabs"] [aria-selected="true"] {
  background:var(--kifc-green); border-color:var(--kifc-green); color:#fff;
}
[data-testid="stTabs"] [data-baseweb="tab-highlight"],
[data-testid="stTabs"] [data-baseweb="tab-border"] { display:none; }
.kifc-kicker { color:#59726b; font-size:.85rem; font-weight:700; letter-spacing:.08em; text-transform:uppercase; }
.kifc-note { background:var(--kifc-mint); border-left:4px solid var(--kifc-green); border-radius:8px; padding:12px 14px; margin:.5rem 0 1rem; }
@media(max-width:760px){.main .block-container{padding:1rem}.main h1{font-size:1.65rem}[data-testid="stHorizontalBlock"]{flex-wrap:wrap}[data-testid="stColumn"]{min-width:46%}}
</style>
""", unsafe_allow_html=True)


@st.cache_data
def assumptions():
    return load_assumptions()


A = assumptions()
QP = st.query_params
BASE_URL = "https://agpv-roi-calculator-2000m.streamlit.app/"


def qp_number(key: str, default: float, low: float, high: float) -> float:
    try:
        value = float(QP.get(key, default))
    except (TypeError, ValueError):
        value = default
    return min(max(value, low), high)


def qp_choice(key: str, default: str, choices: list[str]) -> str:
    value = str(QP.get(key, default))
    return value if value in choices else default


st.markdown('<div class="kifc-kicker">KIFC 의사결정 도구 · 외부 서비스</div>', unsafe_allow_html=True)
st.title("영농형 태양광 경제성 계산기")
st.write("농지와 자금 조건을 바꿔 사업 전체 수익성, 농가 자기자본 수익성, 원리금 상환 여력을 따로 확인합니다.")
st.markdown(
    '<div class="kifc-note"><strong>2026년 5월 기준 베타</strong> · 법률은 통과됐지만 세부 허가·지원 요건은 하위법령과 공고를 확인해야 합니다. 결과는 사업 타당성 검토의 출발점이며 견적이나 금융 승인을 대신하지 않습니다.</div>',
    unsafe_allow_html=True,
)


st.markdown("### ① 조건 입력")
st.caption("값을 바꾸면 아래 결과가 즉시 갱신됩니다. 필요한 경우 세부 가정을 펼쳐 조정하세요.")

with st.container(border=True):
    c1, c2, c3 = st.columns(3)
    with c1:
        area = int(st.number_input(
            "농지 면적(㎡)", 500, 10_000,
            int(qp_number("a", A["facility"]["area_m2"], 500, 10_000)), step=100,
        ))
        equity_pct = st.slider(
            "자기자본 비율(%)", 10.0, 100.0,
            qp_number("e", A["finance"]["equity_ratio"] * 100, 10, 100), step=.5,
        )
    recommended_kw = max(10, round(area * A["facility"]["capacity_kw"] / A["facility"]["area_m2"]))
    recommended_cost = round(recommended_kw / A["facility"]["capacity_kw"] * A["cost"]["total"])
    with c2:
        total_cost = int(st.number_input(
            "총사업비(천원)", int(A["cost"]["permits"]), 1_000_000,
            int(qp_number("b", recommended_cost, A["cost"]["permits"], 1_000_000)), step=1_000,
            help="공사비, 설계·감리, 인허가와 계통연계 관련 비용을 합한 금액을 입력하세요.",
        ))
        loan_keys = list(A["finance"]["loan_options"])
        loan_key = st.selectbox(
            "대출 가정", loan_keys,
            index=loan_keys.index(qp_choice("l", "policy_2026", loan_keys)),
            format_func=lambda k: f"{A['finance']['loan_options'][k]['name']} ({A['finance']['loan_options'][k]['rate']*100:.2f}%)",
        )
        loan_rate = float(A["finance"]["loan_options"][loan_key]["rate"])
    with c3:
        track = st.radio(
            "전력 판매 가정", ["ppa", "rps"],
            index=["ppa", "rps"].index(qp_choice("t", "ppa", ["ppa", "rps"])),
            format_func=lambda x: "고정가격계약(PPA)" if x == "ppa" else "SMP+REC(기존 사업 비교)",
            help="실제 적용 가능 여부와 계약 단가는 사업별 공고·계약서를 확인해야 합니다.",
            horizontal=True,
        )
        default_price = (
            A["power_price"]["ppa_track"]["fixed_price_krw_per_kwh"] if track == "ppa"
            else A["power_price"]["rps_track"]["smp_krw_per_kwh"] + A["power_price"]["rps_track"]["rec_krw_per_kwh"] * A["power_price"]["rps_track"]["weight"]
        )
        sale_price = st.number_input(
            "전력 판매단가(원/kWh)", 50.0, 300.0,
            qp_number("p", default_price, 50, 300), step=1.0,
        )

    with st.expander("세부 가정 — 용량 · 발전시간 · 할인율 · 단수감소 · 출력제어"):
        e1, e2, e3 = st.columns(3)
        with e1:
            capacity = int(st.number_input(
                "시설용량(kW)", 10, 1_000,
                int(qp_number("c", recommended_kw, 10, 1_000)), step=1,
            ))
            daily_hours = st.slider(
                "1일 평균 발전시간", 2.5, 5.0,
                qp_number("h", A["facility"]["daily_gen_hours"], 2.5, 5.0), step=.1,
            )
        with e2:
            discount_rate = st.number_input(
                "요구수익률·할인율(%)", 0.0, 20.0,
                qp_number("d", A["discount"]["base_rate"] * 100, 0, 20), step=.5,
                help="대출금리와 별개입니다. 투자자가 요구하는 수익률을 입력하세요.",
            ) / 100
            yield_reduction = st.slider(
                "벼 단수 감소율(%)", 0, 50,
                int(qp_number("y", A["crops"]["rice"]["yield_reduction"] * 100, 0, 50)), step=1,
            ) / 100
        with e3:
            curtailment_rate = st.slider(
                "출력제어 비율(%)", 0.0, 15.0,
                qp_number("k", A["facility"].get("curtailment_rate", 0.0) * 100, 0, 15), step=.5,
                help="계통 사정으로 발전이 차단되는 연간 비율. 전남 등 계통 포화 지역은 "
                     "봄철 경부하기 출력제어 위험이 있습니다. 기본 0%는 KREI(2023)와 동일 가정이며 "
                     "실적·전망은 한국전력거래소(KPX)·한전 공고를 확인하세요.",
            ) / 100

QP.update({
    "a": str(area), "b": str(total_cost), "e": f"{equity_pct:.1f}", "t": track,
    "p": f"{sale_price:.1f}", "l": loan_key, "c": str(capacity),
    "h": f"{daily_hours:.1f}", "d": f"{discount_rate*100:.1f}", "y": f"{yield_reduction*100:.0f}",
    "k": f"{curtailment_rate*100:.1f}",
})
share_url = BASE_URL + "?" + urllib.parse.urlencode(QP.to_dict())
st.caption("현재 조건은 주소창 URL에 저장됩니다 — 복사하면 같은 조건을 공유할 수 있습니다.")


facility = FacilityInput(
    area_m2=area, capacity_kw=capacity, daily_gen_hours=daily_hours,
    efficiency_decline=float(A["facility"]["efficiency_decline"]),
    lifetime_years=int(A["facility"]["lifetime_years"]),
    curtailment_rate=curtailment_rate,
)
cost = CostInput(construction=total_cost - A["cost"]["permits"], permits=A["cost"]["permits"])
finance = FinanceInput(
    equity_ratio=equity_pct / 100, loan_rate=loan_rate,
    grace_years=int(A["finance"]["grace_years"]), repay_years=int(A["finance"]["repay_years"]),
)
price = PowerPriceInput(track="ppa", ppa_fixed_krw_per_kwh=sale_price)
base_opex = OpexInput(**A["opex_thousand_krw"])
opex = scale_opex_for_project(
    base_opex, base_capacity_kw=float(A["facility"]["capacity_kw"]), capacity_kw=capacity,
    base_total_cost=float(A["cost"]["total"]), total_cost=total_cost,
)
crop = CropInput(
    name_kr=A["crops"]["rice"]["name_kr"],
    base_income_thousand_krw_per_2000m2=float(A["crops"]["rice"]["base_income_thousand_krw_per_2000m2"]),
    yield_reduction=yield_reduction,
)
law = LandLawInput(max_operation_years=int(A["land_law"]["current"]["max_operation_years"]))
analysis = EconomicAnalysis(facility, cost, finance, price, opex, crop, law, discount_rate)
result = analysis.run()
builder = ScenarioBuilder(facility, cost, finance, price, opex, crop, law, discount_rate)

st.divider()
st.markdown("### ② 결과")
summary, cashflow, sensitivity = st.tabs(["요약", "현금흐름", "민감도"])
with summary:
    render_summary_tab(result)
with cashflow:
    render_cashflow_tab(result)
with sensitivity:
    render_sensitivity_tab(builder)

st.divider()
st.caption(
    f"기준 데이터 {A['meta']['data_date']} · 계산기 {A['meta']['version']} · "
    "사단법인 식량과기후(KIFC). 외부 Streamlit 서비스에서 제공됩니다."
)
