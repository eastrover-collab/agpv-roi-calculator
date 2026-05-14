"""영농형 태양광 경제성 계산기 — Streamlit 메인.

농가가 자기 농지 조건을 입력하면 영농형 태양광 도입 시 수익성을
즉시 확인할 수 있는 의사결정 도구.
"""
from __future__ import annotations

import streamlit as st

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
from core.config import load_assumptions
from core.scenarios import ScenarioBuilder
from ui.tabs import (
    render_expert_tab,
    render_headline_tab,
    render_monthly_tab,
    render_risk_tab,
    render_scenarios_tab,
    render_simulation_tab,
)


# ──────────────────────────────────────────────────────────────────
# 페이지 설정
# ──────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="영농형 태양광 경제성 계산기",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 전역 스타일
st.markdown("""
<style>
    .main .block-container { padding-top: 2rem; padding-bottom: 2rem; }
    [data-testid="stMetricValue"] { font-size: 2rem; }
    [data-testid="stMetricLabel"] { font-size: 1rem; }
    .stoplight-green { color: #16a34a; font-weight: 700; }
    .stoplight-yellow { color: #ca8a04; font-weight: 700; }
    .stoplight-red { color: #dc2626; font-weight: 700; }

    /* 사이드바 입력 4단계 헤더 — 단계별 색상 구분 */
    section[data-testid="stSidebar"] [data-testid="stExpander"] {
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        overflow: hidden;
        margin-bottom: 8px;
    }
    section[data-testid="stSidebar"] [data-testid="stExpander"] summary,
    section[data-testid="stSidebar"] [data-testid="stExpander"] details > div:first-child {
        padding: 8px 12px !important;
        font-weight: 600;
    }
    /* 1단계: 농지 정보 — 하늘색 (Sky) */
    section[data-testid="stSidebar"] [data-testid="stExpander"]:nth-of-type(1) summary,
    section[data-testid="stSidebar"] [data-testid="stExpander"]:nth-of-type(1) details > div:first-child {
        background-color: #dbeafe !important;
        border-left: 4px solid #2563eb;
    }
    /* 2단계: 시설 정보 — 호박색 (Amber) */
    section[data-testid="stSidebar"] [data-testid="stExpander"]:nth-of-type(2) summary,
    section[data-testid="stSidebar"] [data-testid="stExpander"]:nth-of-type(2) details > div:first-child {
        background-color: #fef3c7 !important;
        border-left: 4px solid #d97706;
    }
    /* 3단계: 자금 조달 — 분홍색 (Rose) */
    section[data-testid="stSidebar"] [data-testid="stExpander"]:nth-of-type(3) summary,
    section[data-testid="stSidebar"] [data-testid="stExpander"]:nth-of-type(3) details > div:first-child {
        background-color: #fce7f3 !important;
        border-left: 4px solid #db2777;
    }
    /* 4단계: 발전 가격 — 녹색 (Emerald) */
    section[data-testid="stSidebar"] [data-testid="stExpander"]:nth-of-type(4) summary,
    section[data-testid="stSidebar"] [data-testid="stExpander"]:nth-of-type(4) details > div:first-child {
        background-color: #d1fae5 !important;
        border-left: 4px solid #059669;
    }
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────────
# 데이터 로드
# ──────────────────────────────────────────────────────────────────
@st.cache_data
def get_assumptions():
    return load_assumptions()


A = get_assumptions()


# ──────────────────────────────────────────────────────────────────
# 헤더
# ──────────────────────────────────────────────────────────────────
st.title("🌾 영농형 태양광 경제성 계산기")
st.caption(
    f"전라남도 / 논벼 / 23년 운영 기준 · KREI(2023) 모델 + 2026.05 데이터 · "
    f"v{A['meta']['version']}"
)


# ──────────────────────────────────────────────────────────────────
# 사이드바: 입력
# ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("🧮 우리 농지 조건 입력")
    st.caption("입력값을 바꾸면 결과가 실시간으로 업데이트됩니다.")

    # 1. 농지 정보
    with st.expander("📍 1단계: 농지 정보", expanded=True):
        area_m2 = st.number_input(
            "농지 면적 (㎡)",
            min_value=500, max_value=10000,
            value=int(A["facility"]["area_m2"]),
            step=100,
            help="영농형 태양광을 설치할 면적. PDF 기준값 2,000㎡.",
        )
        st.caption(f"≈ **{area_m2:,}** ㎡ ({area_m2/3.3058:,.0f}평)")
        region_label = st.selectbox(
            "지역",
            options=["전라남도"],
            help="현재 전남 데이터만 지원. 추후 확장 예정.",
        )

    # 2. 시설 정보
    with st.expander("⚡ 2단계: 시설 정보", expanded=True):
        # 면적 기반 자동 추천 (PDF: 2000㎡ → 99kW, 약 0.05 kW/㎡)
        recommended_kw = round(area_m2 * 99 / 2000)
        capacity_kw = st.number_input(
            "시설 용량 (kW)",
            min_value=10, max_value=1000,
            value=recommended_kw,
            step=1,
            help=f"면적 기반 추천: {recommended_kw}kW. 직접 조정 가능.",
        )
        daily_hours = st.slider(
            "1일 평균 발전시간 (h)",
            min_value=2.5, max_value=5.0,
            value=float(A["facility"]["daily_gen_hours"]),
            step=0.1,
            help="전남 평균 3.5~3.8h. 일사량이 좋은 해남·영광은 3.8~4.0h.",
        )

    # 3. 자금 조달
    with st.expander("💰 3단계: 자금 조달", expanded=True):
        # 용량 비례 사업비 (assumptions.yaml의 99kW 기준값을 base로 비례 산정)
        base_cost = int(A["cost"]["total"])      # 2026: 210,000 천원
        base_kw = int(A["facility"]["capacity_kw"])  # 99 kW
        recommended_cost = round(capacity_kw / base_kw * base_cost)
        total_cost = st.number_input(
            "총 사업비 (천원)",
            min_value=10_000, max_value=1_000_000,
            value=recommended_cost,
            step=1_000,
            help=f"용량 기반 추천: {recommended_cost:,}천원 "
                 f"(2026 기준 kW당 약 {base_cost/base_kw/10:.0f}만원).",
        )
        st.caption(f"≈ **{total_cost:,}** 천원 ({total_cost/100_000:.2f}억원)")
        equity_pct = st.slider(
            "자기자본 비율 (%)",
            min_value=10, max_value=100,
            value=int(A["finance"]["equity_ratio"] * 100),
            step=5,
            help="융자 외에 본인이 부담하는 비율.",
        )

        loan_option_keys = list(A["finance"]["loan_options"].keys())
        loan_choice = st.selectbox(
            "융자 조건",
            options=loan_option_keys,
            format_func=lambda k: f"{A['finance']['loan_options'][k]['name']} "
                                  f"({A['finance']['loan_options'][k]['rate']*100:.2f}%)",
            index=1,  # 기본: 2026 정책금리
            help="2026 정책금리는 신재생에너지 금융지원 분기 변동.",
        )
        loan_rate = A["finance"]["loan_options"][loan_choice]["rate"]
        custom_rate = st.checkbox("금리 직접 입력", value=False)
        if custom_rate:
            loan_rate = st.number_input(
                "융자 금리 (%)",
                min_value=0.5, max_value=10.0,
                value=loan_rate * 100,
                step=0.1,
            ) / 100

    # 4. 발전가격
    with st.expander("⚡ 4단계: 발전 가격", expanded=True):
        track = st.radio(
            "발전 가격 트랙",
            options=["rps", "ppa"],
            format_func=lambda t: {
                "rps": "RPS 트랙 (SMP + REC × 1.2)",
                "ppa": "PPA 트랙 (고정가격계약)",
            }[t],
            help=(
                "**RPS**: 2026년 이전 준공 사업. SMP + REC 합산.\n\n"
                "**PPA**: 2026년 RPS 일몰 후 신규 사업. 고정가격계약."
            ),
            horizontal=False,
        )
        if track == "rps":
            col1, col2 = st.columns(2)
            with col1:
                smp = st.number_input(
                    "SMP (원/kWh)",
                    min_value=50.0, max_value=300.0,
                    value=float(A["power_price"]["rps_track"]["smp_krw_per_kwh"]),
                    step=1.0,
                    help="2026.1~4 평균 약 109.6원 (PDF 2023: 106.3원).",
                )
            with col2:
                rec = st.number_input(
                    "REC (원/kWh)",
                    min_value=10.0, max_value=200.0,
                    value=float(A["power_price"]["rps_track"]["rec_krw_per_kwh"]),
                    step=1.0,
                    help="2026.1~4 평균 약 71.3원 (PDF 2023: 47.17원).",
                )
            weight = st.number_input(
                "REC 가중치 (영농형 1.2 기본)",
                min_value=1.0, max_value=2.0,
                value=float(A["power_price"]["rps_track"]["weight"]),
                step=0.1,
            )
            unit_price = smp + rec * weight
            st.metric("최종 발전단가", f"{unit_price:.1f} 원/kWh")
            ppa_price = float(A["power_price"]["ppa_track"]["fixed_price_krw_per_kwh"])
        else:
            ppa_price = st.number_input(
                "고정가격계약 단가 (원/kWh)",
                min_value=80.0, max_value=250.0,
                value=float(A["power_price"]["ppa_track"]["fixed_price_krw_per_kwh"]),
                step=1.0,
                help="2025 상반기 평균낙찰가 154.7원/kWh. 범위 140~170원.",
            )
            smp = float(A["power_price"]["rps_track"]["smp_krw_per_kwh"])
            rec = float(A["power_price"]["rps_track"]["rec_krw_per_kwh"])
            weight = float(A["power_price"]["rps_track"]["weight"])
            st.metric("최종 발전단가", f"{ppa_price:.1f} 원/kWh")

    st.divider()
    st.caption("💡 결과는 추정치입니다. 실제 도입 전 전문가 상담 권장.")


# ──────────────────────────────────────────────────────────────────
# 분석 객체 구성
# ──────────────────────────────────────────────────────────────────
facility = FacilityInput(
    area_m2=area_m2,
    capacity_kw=capacity_kw,
    daily_gen_hours=daily_hours,
    efficiency_decline=float(A["facility"]["efficiency_decline"]),
    lifetime_years=int(A["facility"]["lifetime_years"]),
)
cost = CostInput(
    construction=total_cost - A["cost"]["permits"],
    permits=A["cost"]["permits"],
)
finance = FinanceInput(
    equity_ratio=equity_pct / 100,
    loan_rate=loan_rate,
    grace_years=int(A["finance"]["grace_years"]),
    repay_years=int(A["finance"]["repay_years"]),
)
price = PowerPriceInput(
    track=track,
    smp_krw_per_kwh=smp,
    rec_krw_per_kwh=rec,
    weight=weight,
    ppa_fixed_krw_per_kwh=ppa_price,
)
opex = OpexInput(
    inverter_replace=float(A["opex_thousand_krw"]["inverter_replace"]),
    electrical_mgmt=float(A["opex_thousand_krw"]["electrical_mgmt"]),
    insurance=float(A["opex_thousand_krw"]["insurance"]),
    waste_disposal=float(A["opex_thousand_krw"]["waste_disposal"]),
    utility_repair=float(A["opex_thousand_krw"]["utility_repair"]),
)
crop = CropInput(
    name_kr=A["crops"]["rice"]["name_kr"],
    base_income_thousand_krw_per_2000m2=float(
        A["crops"]["rice"]["base_income_thousand_krw_per_2000m2"]
    ),
    yield_reduction=float(A["crops"]["rice"]["yield_reduction"]),
)
land_law = LandLawInput(
    max_operation_years=int(A["land_law"]["current"]["max_operation_years"]),
    requires_land_conversion=False,
)

analysis = EconomicAnalysis(
    facility=facility,
    cost=cost,
    finance=finance,
    price=price,
    opex=opex,
    crop=crop,
    land_law=land_law,
    discount_rate=loan_rate,  # 할인율 = 융자 금리 (PDF 방식)
)
result = analysis.run()

builder = ScenarioBuilder(
    facility=facility,
    cost=cost,
    finance=finance,
    price=price,
    opex=opex,
    crop=crop,
    land_law=land_law,
    discount_rate=loan_rate,
)


# ──────────────────────────────────────────────────────────────────
# 메인 영역: 탭
# ──────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📊 한눈에 보기",
    "💰 월별 통장 흐름",
    "📈 23년 시뮬레이션",
    "🔀 시나리오 비교",
    "⚠️ 리스크 점검",
    "🔬 전문가 모드",
])

with tab1:
    render_headline_tab(result, analysis)

with tab2:
    render_monthly_tab(analysis)

with tab3:
    render_simulation_tab(result, analysis)

with tab4:
    render_scenarios_tab(builder)

with tab5:
    render_risk_tab(builder, analysis)

with tab6:
    render_expert_tab(result, analysis, builder)


# ──────────────────────────────────────────────────────────────────
# 푸터
# ──────────────────────────────────────────────────────────────────
st.divider()

# 데이터 갱신 안내 (눈에 띄게)
st.success(
    f"""📊 **본 계산기는 KREI(2023) 「영농형 태양광 도입의 경제성 분석」 4장 모델을 기반으로 하되,
2026.05 기준 최신 데이터로 갱신했습니다.** (버전 `{A['meta']['version']}`, 기준일 {A['meta']['data_date']})

**주요 갱신 (KREI 2023 → 2026 v1.1):**
발전가격 162.9 → 195.2 원/kWh (+20%) · 정책금리 2.8% → 1.8% · 사업비 1.96억 → 2.10억 (+7%) ·
**농지법 일시사용 8년 → 23년 (2026.02.12 국회 통과)**"""
)

# 상세 비교표 (접힘)
with st.expander("🔍 KREI(2023) vs 2026 v1.1 상세 비교 및 출처", expanded=False):
    st.markdown("""
| 항목 | KREI(2023) 값 | **본 계산기 (2026 v1.1)** | 출처 |
|---|---|---|---|
| SMP 전력 도매가 | 106.32 원/kWh | **109.6 원/kWh** | 한국전력거래소 EPSIS 2026.1~4 평균 |
| REC 가격 | 47.17 원/kWh | **71.3 원/kWh** | 한국전력거래소 EPSIS 2026.1~4 평균 |
| REC 영농형 가중치 | 1.2 | **1.2** (변동 없음) | 산업부 고시 별표2 |
| 발전 단가 합계 | 162.9 원/kWh | **195.2 원/kWh** (+20%) | SMP + REC × 1.2 |
| 정책 융자 금리 | 2.8% | **1.8%** (분기 변동) | 한국에너지공단 신재생에너지 금융지원 2026 |
| 99kW 사업비 | 1.96억원 | **2.10억원** (+7%) | 업계 견적 평균 2026 |
| 발전시간 (전남 평균) | 3.5 h/일 | **3.7 h/일** | 한국에너지공단·기상청 |
| 농지법 운영기간 | 8년 (또는 잡종지 20년) | **23년** (개정) | 재생에너지법 개정 2026.02.12 국회 통과 |
| 공시지가 (전남 진흥지역 밖) | 15,415 원/㎡ | **16,200 원/㎡** | 부동산공시가격알리미 2025 |
| 벼 단수감소 (영농형 하부) | 20% | **20%** (영암 실증 21%) | 전남도농업기술원·정부 실증 |
| 논벼 기준 소득 | 138.8만원/2,000㎡ | 138.8만원 (KOSIS 2020~2024 확인 필요) | 통계청 농가경제조사 |

**계산 엔진 검증**: 본 계산기 코드는 KREI(2023) PDF 표 4-4, 4-7, 4-8, 4-11 결과를
**±5% 이내 재현** (단위 테스트 10/11 통과, 1개 skip은 8년 특수 회계 차이로 제외).

**참고 자료**:
- KREI(2023) 「영농형 태양광 도입의 경제성 분석」 4장 (한국농촌경제연구원)
- 한국전력거래소 EPSIS [https://epsis.kpx.or.kr](https://epsis.kpx.or.kr)
- 한국에너지공단 신재생에너지센터 [https://www.knrec.or.kr](https://www.knrec.or.kr)
- 통계청 KOSIS 농가경제조사 · 영암군 영농형 태양광 실증 결과

> 📌 본 계산기는 추정치입니다. 실제 도입 결정 전 한국에너지공단(1855-3020) 또는 농협 상담 권장.
""")

