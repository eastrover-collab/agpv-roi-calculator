"""각 탭별 렌더링 함수."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core.calculator import AnalysisResult, EconomicAnalysis
from core.monthly import build_yearly_details, group_into_regimes, upfront_equity
from core.scenarios import ScenarioBuilder


# 천원 → "OO만원" 보기 좋게 (농가 친화)
def _to_manwon(thousand_krw: float) -> str:
    """천원 단위 → 만원 보기 좋게 (소수 1자리)."""
    return f"{thousand_krw / 10:,.1f}만원"


def _to_manwon_int(thousand_krw: float) -> str:
    return f"{round(thousand_krw / 10):,}만원"


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
# 탭 (신규): 월별 통장 흐름
# ──────────────────────────────────────────────────────────────────

def render_monthly_tab(analysis: EconomicAnalysis):
    """실제 매월 통장에 들어오는 돈 — 균등화 안 한 raw cash flow.

    Year 0 자기자본 → Year 1~5 거치(이자만) → Year 6~15 원금상환 → Year 16+ 융자완료
    """
    st.subheader("💰 매월 통장에 들어오는 돈 (실제 현금흐름)")
    st.caption(
        "B/C 계산용 균등화가 아닌, **실제 매월 통장 흐름**입니다. "
        "거치 기간(5년) 끝나는 6년차에 부담이 급증하는 점에 주의하세요."
    )

    # Year 0: 자기자본
    equity = upfront_equity(analysis)
    with st.container(border=True):
        col_emoji, col_main = st.columns([1, 6])
        col_emoji.markdown("# 🔴")
        col_main.markdown(f"### Year 0 — 사업 시작 직전")
        col_main.metric(
            "자기자본 일시 투입",
            f"-{_to_manwon_int(equity)}",
            delta="사업 시작 시점에 한꺼번에 들어가는 돈",
            delta_color="off",
        )
        col_main.caption("💡 융자 외에 농가가 직접 부담하는 초기 자본. 사업비의 "
                        f"{analysis.finance.equity_ratio*100:.0f}%")

    st.divider()

    # Year 1~ : 운영 기간 블록들
    details = build_yearly_details(analysis)
    blocks = group_into_regimes(details)

    st.markdown(f"### 📅 운영 기간 ({len(details)}년) — {len(blocks)}개 구간으로 압축")

    for idx, block in enumerate(blocks):
        # 신호등
        if block.monthly_net > 500:  # 월 +50만원 이상
            icon, color = "🟢", "green"
        elif block.monthly_net > -100:  # 거의 흑자
            icon, color = "🟡", "yellow"
        else:
            icon, color = "🔴", "red"

        span = (f"Year {block.year_start}" if block.year_start == block.year_end
                else f"Year {block.year_start}~{block.year_end} ({block.n_years}년간)")

        with st.container(border=True):
            col_icon, col_title = st.columns([1, 6])
            col_icon.markdown(f"# {icon}")
            col_title.markdown(f"### {span} — {block.label}")

            # 핵심 지표
            c1, c2, c3 = st.columns(3)
            c1.metric(
                "매월 통장 흐름 (벼 제외)",
                f"{'+' if block.monthly_net >= 0 else ''}{_to_manwon(block.monthly_net)}",
                delta=("흑자" if block.monthly_net > 0 else
                       "거의 균형" if block.monthly_net > -100 else "적자 위험"),
                delta_color="normal" if block.monthly_net > 0 else "inverse",
            )
            c2.metric(
                "가을 벼 수확 (일시)",
                f"+{_to_manwon(block.annual_crop)}",
                delta="매년 9~10월 수확",
                delta_color="off",
            )
            c3.metric(
                "연간 순이익 평균",
                f"{'+' if block.annual_net_avg >= 0 else ''}{_to_manwon_int(block.annual_net_avg)}",
                delta="벼+태양광 합산, 이벤트 포함",
                delta_color="normal" if block.annual_net_avg > 0 else "inverse",
            )

            # 월별 상세
            with st.expander("📋 월별 항목 상세 보기", expanded=(idx <= 1)):
                breakdown = pd.DataFrame({
                    "항목": [
                        "🌞 발전 수익",
                        "🏦 대출 상환 (이자+원금)",
                        "🔧 정기 운영비 (전기·보험·수선)",
                        "─── 매월 순흐름 ───",
                    ],
                    "월 금액": [
                        f"+{_to_manwon(block.monthly_power)}",
                        f"-{_to_manwon(block.monthly_loan)}" if block.monthly_loan > 0 else "0원 ✓",
                        f"-{_to_manwon(block.monthly_other_opex)}",
                        f"**{'+' if block.monthly_net >= 0 else ''}{_to_manwon(block.monthly_net)}**",
                    ],
                })
                st.dataframe(breakdown, hide_index=True, use_container_width=True)

            # 특별 이벤트
            if block.events:
                st.warning("⚠️ **특별 이벤트** (이 구간 내 일시 비용)")
                for year, name, amount in block.events:
                    st.markdown(f"- Year {year}: **{name}** {_to_manwon(amount)}")

            # 코멘트
            comments = _regime_comment(block, analysis)
            if comments:
                st.info("💡 " + comments)

    # 전체 흐름 차트 (확인용)
    st.divider()
    st.subheader("📊 23년 전체 월별 순흐름 (벼 수확 제외)")
    st.caption("거치 끝나는 6년차 급변, 융자 완료(16년차) 회복이 한눈에 보입니다.")

    years = [d.year for d in details]
    monthly_nets = [d.monthly_net_excluding_crop for d in details]
    colors = ["#16a34a" if m > 500 else "#ca8a04" if m > -100 else "#dc2626"
              for m in monthly_nets]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=years, y=monthly_nets,
        marker_color=colors,
        text=[f"{m/10:+.0f}만" for m in monthly_nets],
        textposition="outside",
        name="매월 순흐름",
    ))
    fig.add_hline(y=0, line_color="#000", line_width=1)
    fig.update_layout(
        height=380,
        xaxis_title="년차",
        yaxis_title="매월 순흐름 (천원/월)",
        showlegend=False,
        margin=dict(l=40, r=40, t=20, b=40),
    )
    st.plotly_chart(fig, use_container_width=True)


def _regime_comment(block, analysis: EconomicAnalysis) -> str:
    """블록 성격에 따른 농가 안내 코멘트."""
    if block.monthly_power == 0:
        return "사업 종료. 영농 단독 운영. 시설 폐기 비용 별도 발생 가능."
    if block.monthly_loan == 0:
        return "융자 다 갚았습니다! 이제부터 발전 수익은 거의 다 순수익."
    if block.monthly_loan < 500:
        return f"거치 기간({analysis.finance.grace_years}년) 동안은 이자만 납부. " \
               f"매월 부담 가벼움. 그러나 {analysis.finance.grace_years+1}년차부터 원금 상환 시작되면 부담 급증."
    if block.monthly_net < 0:
        return "원금 상환 부담으로 매월 흐름이 마이너스. " \
               "**가을 벼 수확으로 연간 합산은 흑자**일 수 있으나 평상시 현금 부족 주의. " \
               "비상금 준비 권장."
    return ""


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
