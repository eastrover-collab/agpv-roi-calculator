"""영농형 태양광 경제성 계산기 — Streamlit 앱."""
from __future__ import annotations

import streamlit as st

from core.calculator import (
    CostInput, CropInput, EconomicAnalysis, FacilityInput, FinanceInput,
    LandLawInput, OpexInput, PowerPriceInput, scale_opex_for_project,
)
from core.config import load_assumptions
from core.scenarios import ScenarioBuilder
from ui.tabs import (
    render_cashflow_tab,
    render_decision_panel,
    render_sensitivity_tab,
    render_summary_tab,
)


st.set_page_config(
    page_title="영농형 태양광 경제성 계산기",
    page_icon="assets/kifc-logo.png",
    layout="wide",
)
st.markdown("""
<style>
:root {
  --kifc-green:#17463f;
  --kifc-green-2:#245f55;
  --kifc-mint:#e9f1ee;
  --kifc-mint-2:#f4f7f5;
  --kifc-gold:#b86d24;
  --kifc-ink:#17231f;
  --kifc-muted:#60716b;
  --kifc-border:#d8e2de;
}
[data-testid="stAppViewContainer"] { background:var(--kifc-mint-2); }
.main .block-container,
[data-testid="stMainBlockContainer"] {
  max-width:1280px;
  padding-top:2rem;
  padding-bottom:3.5rem;
}
h1,h2,h3 { color:var(--kifc-green); letter-spacing:-.035em; }
p, label, [data-testid="stCaptionContainer"] { line-height:1.65; }
[data-testid="stMetric"] {
  min-height:126px;
  background:#fff;
  border:1px solid var(--kifc-border);
  border-radius:16px;
  padding:16px;
  box-shadow:0 8px 24px rgba(23,70,63,.055);
}
[data-testid="stMetricLabel"] p { color:#52645e; font-size:.9rem; font-weight:700; }
[data-testid="stMetricValue"] { color:#153f39; font-size:1.65rem; font-variant-numeric:tabular-nums; }
[data-testid="stNumberInput"] input,
[data-testid="stSelectbox"] > div > div,
[data-testid="stRadio"] label { min-height:46px; }
[data-testid="stNumberInput"] input { font-size:1rem; font-variant-numeric:tabular-nums; }
[data-testid="stWidgetLabel"] p { color:var(--kifc-ink); font-size:.96rem; font-weight:700; }
[data-testid="stExpander"] { border-color:var(--kifc-border); border-radius:14px; overflow:hidden; }
[data-testid="stVerticalBlockBorderWrapper"] {
  border-color:var(--kifc-border);
  border-radius:20px;
  box-shadow:0 14px 36px rgba(23,70,63,.07);
}
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
.kifc-hero {
  position:relative;
  overflow:hidden;
  color:#fff;
  background:
    radial-gradient(circle at 88% 15%, rgba(202,122,39,.32), transparent 26%),
    linear-gradient(135deg, #123d36 0%, #1f5b50 100%);
  border:1px solid rgba(255,255,255,.12);
  border-radius:26px;
  padding:clamp(1.5rem,3vw,2.7rem);
  box-shadow:0 22px 56px rgba(18,61,54,.18);
  margin-bottom:1.5rem;
}
.kifc-hero__kicker {
  color:#d8e9e3;
  font-size:.78rem;
  font-weight:800;
  letter-spacing:.09em;
  text-transform:uppercase;
}
.kifc-hero h1 {
  max-width:760px;
  color:#fff;
  font-size:clamp(2rem,4vw,3.45rem);
  line-height:1.08;
  margin:.7rem 0 .8rem;
}
.kifc-hero__lead {
  max-width:720px;
  color:#eef7f4;
  font-size:clamp(1rem,1.5vw,1.16rem);
  margin:0;
}
.kifc-hero__note {
  display:inline-block;
  color:#e9f2ef;
  background:rgba(255,255,255,.1);
  border:1px solid rgba(255,255,255,.18);
  border-radius:10px;
  padding:.65rem .8rem;
  margin:1.1rem 0 0;
  font-size:.86rem;
}
.kifc-section-kicker {
  color:#60716b;
  font-size:.78rem;
  font-weight:800;
  letter-spacing:.08em;
  text-transform:uppercase;
  margin-bottom:.15rem;
}
.kifc-decision { padding:.35rem .15rem .1rem; }
.kifc-decision__eyebrow {
  color:var(--kifc-muted);
  font-size:.78rem;
  font-weight:800;
  letter-spacing:.07em;
  text-transform:uppercase;
}
.kifc-decision__status {
  display:inline-flex;
  align-items:center;
  min-height:32px;
  border-radius:999px;
  padding:.35rem .72rem;
  margin:.8rem 0 .55rem;
  font-size:.82rem;
  font-weight:800;
}
.kifc-decision__status--danger { color:#8b2723; background:#fbe9e7; }
.kifc-decision__status--warning { color:#744511; background:#fff0d7; }
.kifc-decision__status--positive { color:#15553d; background:#e2f3ea; }
.kifc-decision h2 {
  color:var(--kifc-ink);
  font-size:clamp(1.55rem,2.5vw,2.15rem);
  line-height:1.25;
  margin:.2rem 0 .65rem;
}
.kifc-decision__lead { color:#4d5d57; font-size:.98rem; margin:0 0 1.15rem; }
.kifc-decision__metrics {
  display:grid;
  gap:.65rem;
  border-top:1px solid var(--kifc-border);
  padding-top:1rem;
}
.kifc-decision__metrics > div {
  display:grid;
  grid-template-columns:1fr auto;
  align-items:baseline;
  gap:.25rem .75rem;
}
.kifc-decision__metrics span { color:#5c6d67; font-size:.86rem; font-weight:700; }
.kifc-decision__metrics strong {
  color:var(--kifc-green);
  font-size:1.15rem;
  font-variant-numeric:tabular-nums;
}
.kifc-decision__metrics small {
  grid-column:1 / -1;
  color:#71817c;
  font-size:.75rem;
  text-align:right;
}
.st-key-input_panel [data-testid="stVerticalBlockBorderWrapper"],
.st-key-decision_panel [data-testid="stVerticalBlockBorderWrapper"] { background:#fff; }
.st-key-input_panel [data-testid="stVerticalBlockBorderWrapper"] { padding:1.1rem; }
.st-key-decision_panel [data-testid="stVerticalBlockBorderWrapper"] {
  border-top:4px solid var(--kifc-gold);
  padding:1.15rem;
}
@media(max-width:760px) {
  .main .block-container,
  [data-testid="stMainBlockContainer"] { padding:1rem .85rem 2.5rem; }
  .kifc-hero { border-radius:20px; padding:1.4rem 1.15rem; }
  .kifc-hero h1 { font-size:2.05rem; }
  .kifc-hero__note { font-size:.8rem; }
  [data-testid="stHorizontalBlock"] { flex-direction:column; gap:.7rem; }
  [data-testid="stColumn"] { width:100% !important; flex:1 1 100% !important; min-width:100% !important; }
  [data-testid="stMetric"] { min-height:108px; }
  [data-testid="stTabs"] [role="tab"] { flex:1 1 auto; padding:.5rem .85rem; }
}
@media(prefers-reduced-motion:reduce) {
  *, *::before, *::after { scroll-behavior:auto !important; transition-duration:.01ms !important; }
}
</style>
""", unsafe_allow_html=True)


def assumptions():
    """Load the small config file on each rerun so deployments never show stale assumptions."""
    return load_assumptions()


A = assumptions()
QP = st.query_params


def qp_number(key: str, default: float, low: float, high: float) -> float:
    try:
        value = float(QP.get(key, default))
    except (TypeError, ValueError):
        value = default
    return min(max(value, low), high)


def qp_choice(key: str, default: str, choices: list[str]) -> str:
    value = str(QP.get(key, default))
    return value if value in choices else default


st.markdown(
    """
    <section class="kifc-hero">
      <div class="kifc-hero__kicker">KIFC 의사결정 도구 · 외부 서비스</div>
      <h1>내 농지의 태양광 사업성,<br>숫자로 먼저 확인하세요.</h1>
      <p class="kifc-hero__lead">농지와 자금 조건을 바꾸면 사업 수익성, 농가 자기자본 수익성, 원리금 상환 여력을 한 번에 비교할 수 있습니다.</p>
      <p class="kifc-hero__note"><strong>2026년 5월 기준 베타</strong> · 실제 허가·지원 요건은 하위법령과 공고를 확인해야 하며, 결과는 견적이나 금융 승인을 대신하지 않습니다.</p>
    </section>
    """,
    unsafe_allow_html=True,
)


input_column, decision_column = st.columns([1.55, .85], gap="large", vertical_alignment="top")

with input_column:
    st.markdown('<div class="kifc-section-kicker">01 · 사업 조건</div>', unsafe_allow_html=True)
    st.markdown("### 내 조건 입력")
    st.caption("기본 항목만 입력해도 결과가 바로 바뀝니다. 전문 가정은 아래에서 펼쳐 조정할 수 있습니다.")
    with st.container(border=True, key="input_panel"):
        c1, c2 = st.columns(2, gap="medium")
        with c1:
            area = int(st.number_input(
                "농지 면적(㎡)", 500, 10_000,
                int(qp_number("a", A["facility"]["area_m2"], 500, 10_000)), step=100,
                help="태양광 설비와 농작업 공간을 함께 사용할 전체 농지 면적입니다.",
            ))
        recommended_kw = max(10, round(area * A["facility"]["capacity_kw"] / A["facility"]["area_m2"]))
        recommended_cost = round(recommended_kw / A["facility"]["capacity_kw"] * A["cost"]["total"])
        with c2:
            total_cost = int(st.number_input(
                "총사업비(천원)", int(A["cost"]["permits"]), 1_000_000,
                int(qp_number("b", recommended_cost, A["cost"]["permits"], 1_000_000)), step=1_000,
                help="공사비, 설계·감리, 인허가와 계통연계 관련 비용을 합한 금액입니다.",
            ))

        f1, f2 = st.columns(2, gap="medium")
        with f1:
            equity_pct = st.slider(
                "내 돈으로 부담할 비율(%)", 10.0, 100.0,
                qp_number("e", A["finance"]["equity_ratio"] * 100, 10, 100), step=.5,
                help="총사업비 가운데 대출을 제외하고 농가가 직접 부담할 비율입니다.",
            )
        with f2:
            loan_keys = list(A["finance"]["loan_options"])
            loan_key = st.selectbox(
                "대출 조건", loan_keys,
                index=loan_keys.index(qp_choice("l", "policy_2026", loan_keys)),
                format_func=lambda k: f"{A['finance']['loan_options'][k]['name']} ({A['finance']['loan_options'][k]['rate']*100:.2f}%)",
            )
            loan_rate = float(A["finance"]["loan_options"][loan_key]["rate"])

        track = st.radio(
            "전력 판매 방식", ["ppa", "rps"],
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
            help="전기를 1kWh 판매할 때 받는 금액입니다. 계약서나 사업 공고의 단가를 입력하세요.",
        )

        with st.expander("세부 가정 조정 · 시설용량, 발전시간, 수익률, 단수, 출력제어"):
            e1, e2 = st.columns(2, gap="medium")
            with e1:
                capacity = int(st.number_input(
                    "시설용량(kW)", 10, 1_000,
                    int(qp_number("c", recommended_kw, 10, 1_000)), step=1,
                ))
                daily_hours = st.slider(
                    "1일 평균 발전시간", 2.5, 5.0,
                    qp_number("h", A["facility"]["daily_gen_hours"], 2.5, 5.0), step=.1,
                )
                discount_rate = st.number_input(
                    "요구수익률·할인율(%)", 0.0, 20.0,
                    qp_number("d", A["discount"]["base_rate"] * 100, 0, 20), step=.5,
                    help="대출금리와 별개입니다. 투자자가 요구하는 수익률을 입력하세요.",
                ) / 100
            with e2:
                yield_reduction = st.slider(
                    "벼 단수 감소율(%)", 0, 50,
                    int(qp_number("y", A["crops"]["rice"]["yield_reduction"] * 100, 0, 50)), step=1,
                ) / 100
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

with decision_column:
    st.markdown('<div class="kifc-section-kicker">02 · 현재 판단</div>', unsafe_allow_html=True)
    st.markdown("### 결과 요약")
    st.caption("입력값을 바꾸면 이 판단과 금액이 즉시 갱신됩니다.")
    with st.container(border=True, key="decision_panel"):
        render_decision_panel(result)
    st.caption("현재 조건은 주소창 URL에 자동 저장됩니다. 주소를 복사하면 같은 조건을 공유할 수 있습니다.")

st.divider()
st.markdown('<div id="result-detail" class="kifc-section-kicker">03 · 상세 분석</div>', unsafe_allow_html=True)
st.markdown("### 결과 상세 보기")
st.caption("핵심 지표의 뜻과 연도별 현금흐름, 조건 변화에 따른 민감도를 확인하세요.")
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
