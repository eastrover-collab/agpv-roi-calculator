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
    scale_opex_for_project,
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

    /* 메인 탭 — 기본 Streamlit 탭보다 크게, 버튼처럼 보이게 */
    [data-testid="stTabs"] [role="tablist"] {
        gap: 8px;
        flex-wrap: wrap;
        border-bottom: 1px solid #e5e7eb;
        padding-bottom: 8px;
    }
    [data-testid="stTabs"] [role="tab"] {
        min-height: 44px;
        padding: 10px 14px;
        border: 1px solid #d1d5db;
        border-radius: 8px 8px 0 0;
        background-color: #f9fafb;
        font-size: 1rem;
        font-weight: 700;
        color: #374151;
    }
    [data-testid="stTabs"] [role="tab"][aria-selected="true"] {
        background-color: #e0f2fe;
        border-color: #0284c7;
        color: #075985;
    }
    [data-testid="stTabs"] [role="tab"] p {
        font-size: 1rem;
        font-weight: 700;
    }

    /* 입력 모드 선택 — 간편/전문가를 큰 토글처럼 표시 */
    section[data-testid="stSidebar"] [data-testid="stSegmentedControl"] {
        margin-top: 6px;
        margin-bottom: 14px;
    }
    section[data-testid="stSidebar"] [data-testid="stSegmentedControl"] [role="radiogroup"] {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 8px;
        width: 100%;
    }
    section[data-testid="stSidebar"] [data-testid="stSegmentedControl"] label {
        min-height: 44px;
        justify-content: center;
        border: 1px solid #d1d5db;
        border-radius: 8px;
        background-color: #f9fafb;
        font-size: 1rem;
        font-weight: 800;
    }
    section[data-testid="stSidebar"] [data-testid="stSegmentedControl"] label:has(input:checked) {
        background-color: #dcfce7;
        border-color: #16a34a;
        color: #14532d;
    }

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

    /* 모바일/태블릿 반응형 — 좁은 화면에서 메트릭·컬럼 2열로 자동 wrap */
    @media (max-width: 1100px) {
        [data-testid="stHorizontalBlock"] {
            flex-wrap: wrap !important;
            gap: 8px !important;
        }
        [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
            min-width: calc(50% - 8px) !important;
            flex: 0 0 calc(50% - 8px) !important;
        }
        /* 메트릭 폰트 크기 축소 */
        [data-testid="stMetricValue"] {
            font-size: 1.4rem !important;
        }
        [data-testid="stMetricLabel"] {
            font-size: 0.85rem !important;
        }
        [data-testid="stTabs"] [role="tab"] {
            min-height: 42px;
            padding: 8px 10px;
            font-size: 0.9rem;
        }
        [data-testid="stTabs"] [role="tab"] p {
            font-size: 0.9rem;
        }
    }
    @media (max-width: 600px) {
        /* 모바일: 메트릭 1열 stack */
        [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
            min-width: 100% !important;
            flex: 0 0 100% !important;
        }
        /* 제목 크기 축소 */
        h1 { font-size: 1.5rem !important; }
        h2 { font-size: 1.2rem !important; }
        h3 { font-size: 1.05rem !important; }
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
# URL Query Params (결과 공유용)
# ──────────────────────────────────────────────────────────────────
# 짧은 키: a=area, c=capacity, h=hours, b=budget, e=equity,
#         r=rate, t=track, s=smp, x=rec, w=weight, p=ppa
_qp = st.query_params


def _qp_int(key: str, default: int) -> int:
    try:
        return int(_qp.get(key, default))
    except (ValueError, TypeError):
        return default


def _qp_float(key: str, default: float) -> float:
    try:
        return float(_qp.get(key, default))
    except (ValueError, TypeError):
        return default


def _qp_str(key: str, default: str) -> str:
    return _qp.get(key, default)


def _qp_loan_choice(default_key: str) -> str:
    """융자 옵션 키. 잘못된 값이면 default."""
    val = _qp.get("l", default_key)
    return val if val in A["finance"]["loan_options"] else default_key


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
    advanced_qp_keys = {"c", "h", "b", "s", "x", "w", "p", "r"}
    default_mode = "전문가" if advanced_qp_keys.intersection(_qp.keys()) else "간편"
    mode_qp = _qp_str("m", "expert" if default_mode == "전문가" else "simple")
    input_mode = st.segmented_control(
        "입력 모드",
        options=["간편", "전문가"],
        default="전문가" if mode_qp == "expert" else "간편",
        help="간편 모드는 추천값을 자동 적용하고, 전문가 모드는 세부 가정을 직접 조정합니다.",
    )
    is_expert_mode = input_mode == "전문가"

    # 1. 농지 정보
    with st.expander("📍 1단계: 농지 정보", expanded=True):
        area_m2 = st.number_input(
            "농지 면적 (㎡)",
            min_value=500, max_value=10000,
            value=_qp_int("a", int(A["facility"]["area_m2"])),
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
        if is_expert_mode:
            capacity_kw = st.number_input(
                "시설 용량 (kW)",
                min_value=10, max_value=1000,
                value=_qp_int("c", recommended_kw),
                step=1,
                help=f"면적 기반 추천: {recommended_kw}kW. 직접 조정 가능.",
            )
            daily_hours = st.slider(
                "1일 평균 발전시간 (h)",
                min_value=2.5, max_value=5.0,
                value=_qp_float("h", float(A["facility"]["daily_gen_hours"])),
                step=0.1,
                help="전남 평균 3.5~3.8h. 일사량이 좋은 해남·영광은 3.8~4.0h.",
            )
        else:
            capacity_kw = recommended_kw
            daily_hours = float(A["facility"]["daily_gen_hours"])
            st.metric("추천 시설 용량", f"{capacity_kw:,} kW")
            st.caption(f"1일 평균 발전시간은 전남 기준 {daily_hours:.1f}h를 적용합니다.")

    # 3. 자금 조달
    with st.expander("💰 3단계: 자금 조달", expanded=True):
        # 용량 비례 사업비 (assumptions.yaml의 99kW 기준값을 base로 비례 산정)
        base_cost = int(A["cost"]["total"])      # 2026: 210,000 천원
        base_kw = int(A["facility"]["capacity_kw"])  # 99 kW
        recommended_cost = round(capacity_kw / base_kw * base_cost)
        if is_expert_mode:
            total_cost = st.number_input(
                "총 사업비 (천원)",
                min_value=10_000, max_value=1_000_000,
                value=_qp_int("b", recommended_cost),
                step=1_000,
                help=f"용량 기반 추천: {recommended_cost:,}천원 "
                     f"(2026 기준 kW당 약 {base_cost/base_kw/10:.0f}만원).",
            )
        else:
            total_cost = recommended_cost
            st.metric("추천 총 사업비", f"{total_cost:,} 천원")
        st.caption(f"≈ **{total_cost:,}** 천원 ({total_cost/100_000:.2f}억원)")
        st.caption("운영비는 시설 용량과 총 사업비에 맞춰 자동 보정됩니다.")
        equity_pct = st.slider(
            "자기자본 비율 (%)",
            min_value=10.0, max_value=100.0,
            value=_qp_float("e", float(A["finance"]["equity_ratio"] * 100)),
            step=0.5,
            help="융자 외에 본인이 부담하는 비율. PDF 기준 23.5%.",
        )

        loan_option_keys = list(A["finance"]["loan_options"].keys())
        default_loan = _qp_loan_choice("policy_2026")
        loan_choice = st.selectbox(
            "융자 조건",
            options=loan_option_keys,
            format_func=lambda k: f"{A['finance']['loan_options'][k]['name']} "
                                  f"({A['finance']['loan_options'][k]['rate']*100:.2f}%)",
            index=loan_option_keys.index(default_loan),
            help="2026 정책금리는 신재생에너지 금융지원 분기 변동.",
        )
        loan_rate = A["finance"]["loan_options"][loan_choice]["rate"]
        # URL로 사용자 정의 금리가 들어왔으면 자동 활성화
        url_custom_rate = "r" in _qp and abs(_qp_float("r", loan_rate) - loan_rate) > 1e-6
        custom_rate = st.checkbox("금리 직접 입력", value=url_custom_rate) if is_expert_mode else False
        if custom_rate:
            loan_rate = st.number_input(
                "융자 금리 (%)",
                min_value=0.5, max_value=10.0,
                value=_qp_float("r", loan_rate) * 100,
                step=0.1,
            ) / 100

    # 4. 발전가격
    with st.expander("⚡ 4단계: 발전 가격", expanded=True):
        default_track = _qp_str("t", "rps")
        if default_track not in ("rps", "ppa"):
            default_track = "rps"
        track = st.radio(
            "발전 가격 트랙",
            options=["rps", "ppa"],
            index=0 if default_track == "rps" else 1,
            format_func=lambda t: (
                {
                    "rps": "변동형 판매가격",
                    "ppa": "고정가격계약",
                }[t]
                if not is_expert_mode
                else {
                    "rps": "RPS 트랙 (SMP + REC × 1.2)",
                    "ppa": "PPA 트랙 (고정가격계약)",
                }[t]
            ),
            help=(
                "**RPS**: 2026년 이전 준공 사업. SMP + REC 합산.\n\n"
                "**PPA**: 2026년 RPS 일몰 후 신규 사업. 고정가격계약."
            ),
            horizontal=False,
        )
        if track == "rps" and is_expert_mode:
            col1, col2 = st.columns(2)
            with col1:
                smp = st.number_input(
                    "SMP (원/kWh)",
                    min_value=50.0, max_value=300.0,
                    value=_qp_float("s", float(A["power_price"]["rps_track"]["smp_krw_per_kwh"])),
                    step=1.0,
                    help="2026.1~4 평균 약 109.6원 (PDF 2023: 106.3원).",
                )
            with col2:
                rec = st.number_input(
                    "REC (원/kWh)",
                    min_value=10.0, max_value=200.0,
                    value=_qp_float("x", float(A["power_price"]["rps_track"]["rec_krw_per_kwh"])),
                    step=1.0,
                    help="2026.1~4 평균 약 71.3원 (PDF 2023: 47.17원).",
                )
            weight = st.number_input(
                "REC 가중치 (영농형 1.2 기본)",
                min_value=1.0, max_value=2.0,
                value=_qp_float("w", float(A["power_price"]["rps_track"]["weight"])),
                step=0.1,
            )
            unit_price = smp + rec * weight
            st.metric("최종 발전단가", f"{unit_price:.1f} 원/kWh")
            ppa_price = _qp_float("p", float(A["power_price"]["ppa_track"]["fixed_price_krw_per_kwh"]))
        elif track == "ppa" and is_expert_mode:
            ppa_price = st.number_input(
                "고정가격계약 단가 (원/kWh)",
                min_value=80.0, max_value=250.0,
                value=_qp_float("p", float(A["power_price"]["ppa_track"]["fixed_price_krw_per_kwh"])),
                step=1.0,
                help="2025 상반기 평균낙찰가 154.7원/kWh. 범위 140~170원.",
            )
            smp = _qp_float("s", float(A["power_price"]["rps_track"]["smp_krw_per_kwh"]))
            rec = _qp_float("x", float(A["power_price"]["rps_track"]["rec_krw_per_kwh"]))
            weight = _qp_float("w", float(A["power_price"]["rps_track"]["weight"]))
            st.metric("최종 발전단가", f"{ppa_price:.1f} 원/kWh")
        else:
            smp = float(A["power_price"]["rps_track"]["smp_krw_per_kwh"])
            rec = float(A["power_price"]["rps_track"]["rec_krw_per_kwh"])
            weight = float(A["power_price"]["rps_track"]["weight"])
            ppa_price = float(A["power_price"]["ppa_track"]["fixed_price_krw_per_kwh"])
            unit_price = smp + rec * weight if track == "rps" else ppa_price
            st.metric("추천 발전단가", f"{unit_price:.1f} 원/kWh")
            st.caption("세부 단가는 전문가 모드에서 조정할 수 있습니다.")

    # ─── URL에 현재 입력값 자동 동기화 ───
    _qp.update({
        "m": "expert" if is_expert_mode else "simple",
        "a": str(int(area_m2)),
        "c": str(int(capacity_kw)),
        "h": f"{daily_hours:.1f}",
        "b": str(int(total_cost)),
        "e": f"{equity_pct:.1f}",
        "l": loan_choice,
        "r": f"{loan_rate:.4f}",
        "t": track,
        "s": f"{smp:.2f}",
        "x": f"{rec:.2f}",
        "w": f"{weight:.2f}",
        "p": f"{ppa_price:.1f}",
    })

    st.divider()

    # ─── 공유 URL 섹션 ───
    st.markdown("### 🔗 결과 공유")
    import urllib.parse
    BASE_URL = "https://agpv-roi-calculator-2000m.streamlit.app/"
    share_query = urllib.parse.urlencode({k: v for k, v in _qp.to_dict().items()})
    share_url = f"{BASE_URL}?{share_query}"
    st.code(share_url, language=None)
    st.caption("이 링크를 카톡·SNS로 공유하면 똑같은 입력값으로 결과가 나옵니다.")

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
base_opex = OpexInput(
    inverter_replace=float(A["opex_thousand_krw"]["inverter_replace"]),
    electrical_mgmt=float(A["opex_thousand_krw"]["electrical_mgmt"]),
    insurance=float(A["opex_thousand_krw"]["insurance"]),
    waste_disposal=float(A["opex_thousand_krw"]["waste_disposal"]),
    utility_repair=float(A["opex_thousand_krw"]["utility_repair"]),
)
opex = scale_opex_for_project(
    base_opex,
    base_capacity_kw=float(A["facility"]["capacity_kw"]),
    capacity_kw=capacity_kw,
    base_total_cost=float(A["cost"]["total"]),
    total_cost=total_cost,
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
**농지법 일시사용 8년 → 23년 (2026.05.07 국회 통과)**"""
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
| 농지법 운영기간 | 8년 (또는 잡종지 20년) | **23년** (개정) | 재생에너지법 개정 2026.05.07 국회 통과 |
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
