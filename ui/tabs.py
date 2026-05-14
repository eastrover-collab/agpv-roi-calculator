"""각 탭별 렌더링 함수."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core.calculator import AnalysisResult, EconomicAnalysis
from core.scenarios import ScenarioBuilder


# ──────────────────────────────────────────────────────────────────
# 탭 1: 한눈에 보기 (Headline)
# ──────────────────────────────────────────────────────────────────

def _bc_color(bc: float) -> str:
    if bc >= 1.2:
        return "🟢"
    if bc >= 1.0:
        return "🟡"
    return "🔴"


def _bc_verdict(bc: float) -> tuple[str, str]:
    """B/C 값에 따른 평가 메시지."""
    if bc >= 1.5:
        return "수익성 매우 좋음", "green"
    if bc >= 1.2:
        return "수익성 있음", "green"
    if bc >= 1.0:
        return "수익성 경계", "yellow"
    return "손실 우려", "red"


def render_headline_tab(result: AnalysisResult, analysis: EconomicAnalysis):
    """가장 중요한 결과 — 농가가 가장 먼저 보는 화면."""
    bc = result.bc_ratio
    icon = _bc_color(bc)
    verdict, color = _bc_verdict(bc)

    st.markdown(f"### {icon} 종합 평가: <span class='stoplight-{color}'>{verdict}</span>",
                unsafe_allow_html=True)
    st.caption(
        "B/C 1.2 이상: 수익성 있음 · 1.0~1.2: 경계 · 1.0 미만: 손실 우려"
    )

    st.divider()

    # 큰 숫자 4개
    col1, col2, col3, col4 = st.columns(4)
    annual_net = result.npv_total_annualized
    col1.metric(
        "연간 순이익 (벼+태양광)",
        f"{annual_net:,.0f} 천원",
        delta=f"벼만 재배 대비 +{annual_net - result.annual_crop_revenue_base:,.0f} 천원",
    )
    col2.metric(
        "투자 회수 기간",
        f"{result.payback_year:.1f} 년" if result.payback_year else "—",
        delta=f"분석 기간 {result.project_years}년 중" if result.payback_year else None,
    )
    col3.metric(
        "내부수익률 (IRR)",
        f"{result.irr * 100:.1f}%" if result.irr else "—",
    )
    col4.metric(
        "B/C 비율",
        f"{bc:.2f}",
        delta="수익성 지표",
    )

    st.divider()

    # 연간 흐름 요약
    st.subheader("📥 연간 수입·지출 (운영기간 평균)")
    col_in, col_out = st.columns(2)

    with col_in:
        st.markdown("**수입**")
        df_in = pd.DataFrame({
            "항목": ["발전 수익", "벼 소득 (단수감소 반영)", "합계"],
            "금액 (천원/년)": [
                round(result.annual_power_revenue),
                round(result.annual_crop_revenue),
                round(result.annual_power_revenue + result.annual_crop_revenue),
            ],
        })
        st.dataframe(df_in, hide_index=True, use_container_width=True)

    with col_out:
        st.markdown("**지출 (운영비)**")
        df_out = pd.DataFrame({
            "항목": [
                "자기자본·이자·원금상환",
                "전기안전관리대행",
                "보험료",
                "인버터 교체(연간 분할)",
                "폐기물 처리",
                "전기료·수선비",
                "합계",
            ],
            "금액 (천원/년)": [
                round(result.annual_finance_cost),
                round(analysis.opex.electrical_mgmt),
                round(analysis.opex.insurance),
                round(analysis.opex.inverter_replace),
                round(analysis.opex.waste_disposal),
                round(analysis.opex.utility_repair),
                round(result.annual_opex),
            ],
        })
        st.dataframe(df_out, hide_index=True, use_container_width=True)

    # 종합 코멘트
    st.divider()
    st.subheader("💬 종합 코멘트")
    comments = []
    if bc >= 1.2:
        comments.append(f"✅ B/C가 **{bc:.2f}**로 양호합니다. 이 조건이라면 도입을 적극 검토할 수 있습니다.")
    elif bc >= 1.0:
        comments.append(f"⚠️ B/C가 **{bc:.2f}**로 경계 수준입니다. 발전가격이나 설치비가 조금만 불리해져도 손실 가능. 시나리오 비교 탭을 확인하세요.")
    else:
        comments.append(f"🚨 B/C가 **{bc:.2f}**로 손실 우려가 있습니다. 정책 융자·보조금 확보가 필수.")

    if result.payback_year and result.payback_year < 10:
        comments.append(f"💰 투자 회수 **{result.payback_year:.1f}년** — 빠른 편입니다.")
    elif result.payback_year and result.payback_year < 15:
        comments.append(f"💰 투자 회수 **{result.payback_year:.1f}년** — 중간 수준.")
    elif result.payback_year:
        comments.append(f"💰 투자 회수 **{result.payback_year:.1f}년** — 장기 시계가 필요.")
    else:
        comments.append("💰 분석 기간 내 투자 회수 어려움.")

    ratio = result.bc_vs_baseline
    if ratio > 2.5:
        comments.append(f"🌾 벼만 재배할 때 대비 **{ratio:.1f}배** 수익 — 큰 향상 기대.")
    elif ratio > 1.5:
        comments.append(f"🌾 벼만 재배할 때 대비 **{ratio:.1f}배** 수익 — 의미있는 향상.")
    else:
        comments.append(f"🌾 벼만 재배할 때 대비 **{ratio:.1f}배** — 향상폭이 크지 않음.")

    for c in comments:
        st.markdown(f"- {c}")


# ──────────────────────────────────────────────────────────────────
# 탭 2: 23년 시뮬레이션
# ──────────────────────────────────────────────────────────────────

def render_simulation_tab(result: AnalysisResult, analysis: EconomicAnalysis):
    """연도별 현금흐름 + 누적 차트."""
    st.subheader(f"📈 {result.project_years}년 누적 현금흐름")
    st.caption(
        "Year 0은 초기 자기자본 지출(음수)부터 시작. "
        "곡선이 0 위로 올라가는 시점이 투자 회수 시점."
    )

    cash_flows = result.cash_flows
    years = list(range(len(cash_flows)))
    cumulative = []
    running = 0
    for cf in cash_flows:
        running += cf
        cumulative.append(running)

    fig = go.Figure()
    # 누적 라인
    fig.add_trace(go.Scatter(
        x=years, y=cumulative,
        mode="lines+markers",
        name="누적 현금흐름",
        line=dict(color="#2563eb", width=3),
        fill="tozeroy",
        fillcolor="rgba(37, 99, 235, 0.1)",
    ))
    # 손익분기선
    fig.add_hline(y=0, line_dash="dash", line_color="#dc2626",
                  annotation_text="손익분기점", annotation_position="right")
    # 회수 시점 마커
    if result.payback_year:
        fig.add_vline(
            x=result.payback_year, line_dash="dot", line_color="#16a34a",
            annotation_text=f"회수 시점: {result.payback_year:.1f}년",
            annotation_position="top",
        )

    fig.update_layout(
        height=450,
        xaxis_title="연도 (Year 0 = 사업 시작)",
        yaxis_title="누적 현금흐름 (천원)",
        hovermode="x unified",
        margin=dict(l=40, r=40, t=20, b=40),
    )
    st.plotly_chart(fig, use_container_width=True)

    # 연도별 막대 그래프
    st.subheader("📊 연도별 수입·지출")
    col1, col2 = st.columns([3, 1])

    # 연도별 흐름 계산
    benefits = []
    costs = []
    for t in range(1, result.project_years + 1):
        b, c = analysis.yearly_cash_flow(t)
        benefits.append(b)
        costs.append(c)

    fig2 = go.Figure()
    fig2.add_trace(go.Bar(
        x=list(range(1, result.project_years + 1)),
        y=benefits, name="수입 (발전+벼)", marker_color="#16a34a",
    ))
    fig2.add_trace(go.Bar(
        x=list(range(1, result.project_years + 1)),
        y=[-c for c in costs], name="지출 (운영비)", marker_color="#dc2626",
    ))
    fig2.update_layout(
        height=350, barmode="relative",
        xaxis_title="연도",
        yaxis_title="현금흐름 (천원)",
        hovermode="x unified",
        margin=dict(l=40, r=40, t=20, b=40),
    )
    col1.plotly_chart(fig2, use_container_width=True)

    with col2:
        st.markdown("**연간 평균**")
        st.metric("수입", f"{sum(benefits)/len(benefits):,.0f} 천원")
        st.metric("지출", f"{sum(costs)/len(costs):,.0f} 천원")
        st.metric("순이익", f"{(sum(benefits)-sum(costs))/len(benefits):,.0f} 천원")


# ──────────────────────────────────────────────────────────────────
# 탭 3: 시나리오 비교 (낙관/현실/비관)
# ──────────────────────────────────────────────────────────────────

def render_scenarios_tab(builder: ScenarioBuilder):
    """단일요인 6개 시나리오 비교."""
    st.subheader("🔀 단일요인 변화 시나리오")
    st.caption(
        "발전가격·설치비·금리가 각각 변할 때 수익성이 어떻게 달라지는지 확인하세요. "
        "PDF 표 4-7 방식."
    )

    results = builder.single_factor_scenarios()

    # 막대 차트
    fig = go.Figure()
    colors = ["#2563eb" if r.name == "BL" else
              "#dc2626" if r.bc < 1.0 else
              "#ca8a04" if r.bc < 1.2 else
              "#16a34a" for r in results]

    fig.add_trace(go.Bar(
        x=[f"{r.name}<br>{r.description}" for r in results],
        y=[r.bc for r in results],
        marker_color=colors,
        text=[f"{r.bc:.2f}" for r in results],
        textposition="outside",
    ))
    fig.add_hline(y=1.0, line_dash="dash", line_color="#dc2626",
                  annotation_text="손익분기 (B/C=1.0)", annotation_position="right")
    fig.add_hline(y=1.2, line_dash="dot", line_color="#16a34a",
                  annotation_text="수익성 기준 (B/C=1.2)", annotation_position="right")
    fig.update_layout(
        height=450,
        yaxis_title="B/C 비율",
        margin=dict(l=40, r=40, t=20, b=40),
    )
    st.plotly_chart(fig, use_container_width=True)

    # 표
    st.markdown("**시나리오 상세**")
    df = pd.DataFrame([{
        "시나리오": r.name,
        "내용": r.description,
        "B/C": f"{r.bc:.2f}",
        "IRR": f"{r.irr*100:.1f}%" if r.irr else "—",
        "회수기간": f"{r.result.payback_year:.1f}년" if r.result.payback_year else "—",
        "벼 대비": f"{r.result.bc_vs_baseline:.1f}배",
        "판정": ("🟢 양호" if r.bc >= 1.2 else "🟡 경계" if r.bc >= 1.0 else "🔴 손실"),
    } for r in results])
    st.dataframe(df, hide_index=True, use_container_width=True)


# ──────────────────────────────────────────────────────────────────
# 탭 4: 리스크 점검
# ──────────────────────────────────────────────────────────────────

def render_risk_tab(builder: ScenarioBuilder, analysis: EconomicAnalysis):
    """토네이도 차트 + 손익분기 임계값."""
    st.subheader("⚠️ 어떤 변수가 수익성을 가장 흔드는가")
    st.caption(
        "베이스라인 대비 각 변수를 ±15% 흔들었을 때 B/C가 얼마나 변하는지. "
        "막대가 길수록 민감한 변수."
    )

    base = builder._run()
    base_bc = base.bc_ratio

    # 토네이도: ±15% 변동
    sensitivities = []
    # 발전가격
    high_price = analysis.price.unit_price * 1.15
    low_price = analysis.price.unit_price * 0.85
    bc_high = builder._run(price_override=high_price).bc_ratio
    bc_low = builder._run(price_override=low_price).bc_ratio
    sensitivities.append(("발전가격 ±15%", bc_low - base_bc, bc_high - base_bc))

    # 설치비
    bc_high = builder._run(cost_multiplier=0.85).bc_ratio
    bc_low = builder._run(cost_multiplier=1.15).bc_ratio
    sensitivities.append(("설치비 ±15%", bc_low - base_bc, bc_high - base_bc))

    # 금리 ±1%p
    bc_high = builder._run(loan_rate_override=max(analysis.finance.loan_rate - 0.01, 0.001)).bc_ratio
    bc_low = builder._run(loan_rate_override=analysis.finance.loan_rate + 0.01).bc_ratio
    sensitivities.append(("금리 ±1%p", bc_low - base_bc, bc_high - base_bc))

    # 정렬: 영향 큰 순
    sensitivities.sort(key=lambda x: abs(x[2] - x[1]), reverse=True)

    fig = go.Figure()
    for name, low, high in sensitivities:
        fig.add_trace(go.Bar(
            y=[name], x=[low], orientation="h",
            marker_color="#dc2626", name="불리한 방향",
            showlegend=name == sensitivities[0][0],
            text=f"{low:+.3f}", textposition="auto",
        ))
        fig.add_trace(go.Bar(
            y=[name], x=[high], orientation="h",
            marker_color="#16a34a", name="유리한 방향",
            showlegend=name == sensitivities[0][0],
            text=f"{high:+.3f}", textposition="auto",
        ))
    fig.update_layout(
        height=350, barmode="overlay",
        xaxis_title=f"B/C 변화 (베이스라인 {base_bc:.2f} 기준)",
        margin=dict(l=40, r=40, t=20, b=40),
    )
    st.plotly_chart(fig, use_container_width=True)

    # 손익분기 임계값
    st.divider()
    st.subheader("🎯 손익분기 임계값")
    st.caption("아래 값 이하/이상이 되면 B/C가 1.0 미만으로 떨어집니다.")

    # 발전가격 임계값 (bisection)
    base_price = analysis.price.unit_price
    lo, hi = base_price * 0.3, base_price
    for _ in range(40):
        mid = (lo + hi) / 2
        bc = builder._run(price_override=mid).bc_ratio
        if bc < 1.0:
            lo = mid
        else:
            hi = mid
    breakeven_price = (lo + hi) / 2

    # 설치비 임계값
    lo, hi = 1.0, 3.0
    for _ in range(40):
        mid = (lo + hi) / 2
        bc = builder._run(cost_multiplier=mid).bc_ratio
        if bc > 1.0:
            lo = mid
        else:
            hi = mid
    breakeven_cost_mult = (lo + hi) / 2

    col1, col2 = st.columns(2)
    col1.metric(
        "발전가격 손익분기",
        f"{breakeven_price:.1f} 원/kWh",
        delta=f"현재 {base_price:.1f}원 대비 {(breakeven_price/base_price-1)*100:+.1f}%",
        delta_color="off",
    )
    col2.metric(
        "설치비 손익분기",
        f"{breakeven_cost_mult*100:.0f}%",
        delta=f"현재 100% 대비 {(breakeven_cost_mult-1)*100:+.0f}%",
        delta_color="off",
    )


# ──────────────────────────────────────────────────────────────────
# 탭 5: 전문가 모드
# ──────────────────────────────────────────────────────────────────

def render_expert_tab(result: AnalysisResult, analysis: EconomicAnalysis, builder: ScenarioBuilder):
    """NPV/IRR 상세 + 18개 복합 시나리오 + 리스크 프리미엄."""
    st.subheader("🔬 상세 재무 지표")

    col1, col2, col3 = st.columns(3)
    col1.metric("NPV (발전 손익)", f"{result.npv_power:,.0f} 천원",
                f"연간 {result.npv_power_annualized:,.0f} 천원")
    col2.metric("NPV (벼 손익, 단수감소)", f"{result.npv_crop_with_reduction:,.0f} 천원",
                f"연간 {result.npv_crop_reduction_annualized:,.0f} 천원")
    col3.metric("NPV (벼+태양광)", f"{result.npv_total:,.0f} 천원",
                f"연간 {result.npv_total_annualized:,.0f} 천원")

    st.divider()

    # 복합 시나리오 18개 매트릭스
    st.subheader("📊 복합요인 18개 시나리오 (PDF 표 4-8)")
    st.caption("발전단가 × 금리 × 설치비 모든 조합")

    composite = builder.composite_scenarios()
    df = pd.DataFrame([{
        "시나리오": r.name,
        "발전단가": r.params["price"],
        "금리(%)": f"{r.params['rate']*100:.2f}",
        "설치비": f"{(r.params['cost_mult']-1)*100:+.0f}%",
        "B/C": r.bc,
    } for r in composite])

    # 히트맵
    pivot = df.pivot_table(
        index=["발전단가", "금리(%)"],
        columns="설치비",
        values="B/C",
        aggfunc="first",
    )

    fig_heatmap = go.Figure(data=go.Heatmap(
        z=pivot.values,
        x=[str(c) for c in pivot.columns],
        y=[f"{p}원 / {r}%" for p, r in pivot.index],
        colorscale=[(0, "#dc2626"), (0.5, "#fbbf24"), (1, "#16a34a")],
        zmin=0.9, zmax=1.5, zmid=1.2,
        text=pivot.values,
        texttemplate="%{text:.2f}",
        textfont={"size": 14},
        colorbar=dict(title="B/C"),
    ))
    fig_heatmap.update_layout(
        height=400,
        xaxis_title="설치비 변동",
        yaxis_title="발전단가 / 금리",
        margin=dict(l=40, r=40, t=20, b=40),
    )
    st.plotly_chart(fig_heatmap, use_container_width=True)

    # 표
    df_display = df.copy()
    df_display["B/C"] = df_display["B/C"].apply(lambda x: f"{x:.2f}")
    df_display["판정"] = df["B/C"].apply(
        lambda x: "🟢 양호" if x >= 1.2 else "🟡 경계" if x >= 1.0 else "🔴 손실"
    )
    st.dataframe(df_display, hide_index=True, use_container_width=True)

    st.divider()

    # 리스크 프리미엄
    st.subheader("⚠️ 리스크 프리미엄 (할인율 변화)")
    st.caption("시중금리 4.5% + 경영·금융 리스크 프리미엄 반영 시 B/C 변화")

    risk = builder.risk_premium_scenarios()
    df_risk = pd.DataFrame([{
        "시나리오": r.name,
        "설명": r.description,
        "할인율": f"{r.params['discount']*100:.1f}%",
        "B/C": f"{r.bc:.2f}",
        "판정": ("🟢" if r.bc >= 1.2 else "🟡" if r.bc >= 1.0 else "🔴"),
    } for r in risk])
    st.dataframe(df_risk, hide_index=True, use_container_width=True)

    st.divider()
    st.markdown("""
    **방법론 참고**
    - 모델: KREI(2023) 4장 + 프로젝트 파이낸스 표준
    - B/C = (자기자본 upfront + PV 운영비) 대비 PV(발전+벼 수익)
    - 분석 기간: 시설수명 23년 (농지법 개정, 2026.02 시행)
    - 할인율: 융자 금리 (기본 시나리오) / 시중금리 4.5% + 리스크 프리미엄 (리스크 분석)
    """)
