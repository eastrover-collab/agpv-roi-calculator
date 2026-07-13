"""Streamlit 결과 화면: 요약, 현금흐름, 민감도."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core.calculator import AnalysisResult, EconomicAnalysis
from core.scenarios import ScenarioBuilder


def _money(value: float) -> str:
    sign = "-" if value < 0 else ""
    value = abs(value)
    if value >= 100_000:
        return f"{sign}{value / 100_000:.2f}억원"
    return f"{sign}{value / 10:,.0f}만원"


def _pct(value: float | None) -> str:
    return "계산 불가" if value is None else f"{value * 100:.1f}%"


def render_summary_tab(result: AnalysisResult) -> None:
    st.subheader("한눈에 보는 결과")
    st.caption("사업 전체와 농가 자기자본의 수익률은 서로 다른 현금흐름으로 계산합니다.")

    a, b, c, d = st.columns(4)
    a.metric("사업 순현재가치", _money(result.project_npv), help="총사업비를 Year 0에 반영한 사업 전체 NPV")
    b.metric("사업 내부수익률", _pct(result.project_irr), help="대출 조건과 무관한 사업 자체 IRR")
    c.metric("자기자본 내부수익률", _pct(result.equity_irr), help="초기 자기자본과 실제 원리금 상환을 반영한 IRR")
    d.metric("최저 DSCR", "—" if result.minimum_dscr is None else f"{result.minimum_dscr:.2f}배", help="연간 영업현금흐름 ÷ 원리금 상환액의 최솟값")

    if result.project_npv < 0:
        st.warning("현재 가정에서는 요구수익률을 적용한 사업 순현재가치가 음수입니다.")
    if result.minimum_dscr is not None and result.minimum_dscr < 1:
        st.error("일부 연도에 영업현금만으로 원리금을 갚지 못하는 것으로 계산됩니다.")
    elif result.minimum_dscr is not None and result.minimum_dscr < 1.2:
        st.warning("원리금 상환 여유가 크지 않습니다. 가격 하락·발전량 감소 조건을 함께 확인하세요.")

    st.markdown("#### 농가 통장 기준")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("필요 자기자본", _money(-result.equity_cash_flows[0]))
    c2.metric("1년차 순현금", _money(result.first_year_equity_cash))
    c3.metric("원금상환 첫해 순현금", _money(result.repayment_year_equity_cash or 0))
    c4.metric("자기자본 회수", "—" if result.equity_payback_year is None else f"{result.equity_payback_year:.1f}년")

    st.markdown("#### 계산 범위")
    st.info(
        "발전수익, 벼 소득, 정기 운영비, 인버터 교체, 실제 원리금 상환을 포함합니다. "
        "세금·부가가치세, 임차료, 계통 보강비와 출력제어, 철거·원상복구비, 물가상승은 포함하지 않습니다."
    )


def render_cashflow_tab(result: AnalysisResult) -> None:
    st.subheader("연도별 현금흐름")
    rows = []
    project_cum = 0.0
    equity_cum = 0.0
    for year in range(result.project_years + 1):
        project = result.project_cash_flows[year]
        equity = result.equity_cash_flows[year]
        project_cum += project
        equity_cum += equity
        rows.append({
            "연도": year,
            "사업 현금흐름": project,
            "자기자본 현금흐름": equity,
            "사업 누계": project_cum,
            "자기자본 누계": equity_cum,
        })
    df = pd.DataFrame(rows)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["연도"], y=df["사업 누계"], name="사업 누계", line=dict(color="#17463f", width=3)))
    fig.add_trace(go.Scatter(x=df["연도"], y=df["자기자본 누계"], name="자기자본 누계", line=dict(color="#ca7a27", width=3)))
    fig.add_hline(y=0, line_color="#7a817d", line_dash="dot")
    fig.update_layout(height=410, margin=dict(l=12, r=12, t=24, b=12), yaxis_title="천원", hovermode="x unified")
    st.plotly_chart(fig, width="stretch")

    details = pd.DataFrame([
        {
            "연도": d.year,
            "발전수익": round(d.power_revenue),
            "농업소득": round(d.crop_revenue),
            "운영·교체비": round(d.steady_opex + d.inverter_cost + d.conversion_cost),
            "이자": round(d.debt_interest),
            "원금": round(d.debt_principal),
            "농가 순현금": round(d.equity_cash_flow),
        }
        for d in result.annual_cash_flows
    ])
    st.dataframe(details, hide_index=True, width="stretch")
    st.caption("단위: 천원. 인버터 교체비는 10년차와 20년차에 일시 반영합니다.")


def render_sensitivity_tab(builder: ScenarioBuilder) -> None:
    st.subheader("가격·설치비·금리 민감도")
    st.caption("한 번에 한 조건만 바꿔 현재 입력값과 비교합니다. 예측이 아니라 스트레스 테스트입니다.")
    scenarios = builder.current_input_scenarios()
    rows = []
    for scenario in scenarios:
        r = scenario.result
        rows.append({
            "조건": scenario.description,
            "사업 NPV(천원)": round(r.project_npv),
            "사업 IRR": None if r.project_irr is None else r.project_irr * 100,
            "자기자본 IRR": None if r.equity_irr is None else r.equity_irr * 100,
            "최저 DSCR": r.minimum_dscr,
        })
    df = pd.DataFrame(rows)
    colors = ["#17463f" if i == 0 else "#79a49a" for i in range(len(df))]
    fig = go.Figure(go.Bar(x=df["조건"], y=df["사업 NPV(천원)"], marker_color=colors))
    fig.add_hline(y=0, line_color="#9a3c32", line_dash="dot")
    fig.update_layout(height=390, margin=dict(l=12, r=12, t=24, b=110), yaxis_title="사업 NPV(천원)")
    st.plotly_chart(fig, width="stretch")
    st.dataframe(
        df.style.format({"사업 NPV(천원)": "{:,.0f}", "사업 IRR": "{:.1f}%", "자기자본 IRR": "{:.1f}%", "최저 DSCR": "{:.2f}"}, na_rep="—"),
        hide_index=True,
        width="stretch",
    )
