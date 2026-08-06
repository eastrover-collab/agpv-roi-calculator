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


def _dscr(result: AnalysisResult) -> str:
    return "—" if result.minimum_dscr is None else f"{result.minimum_dscr:.2f}배"


def _dscr_year_note(result: AnalysisResult) -> str:
    """최저 DSCR 이 몇 년차인지. 인버터 교체 연도면 그 사실까지 함께 밝힌다."""
    year = result.minimum_dscr_year
    if year is None:
        return ""
    replacement = next(
        (d for d in result.annual_cash_flows if d.year == year and d.inverter_cost > 0), None
    )
    return f"{year}년차(인버터 교체)" if replacement else f"{year}년차"


def _decision_copy(result: AnalysisResult) -> tuple[str, str, str]:
    """Return a plain-language investment assessment for the summary panel."""
    if result.project_npv < 0:
        return (
            "재검토 필요",
            "현재 조건에서는 사업성이 부족합니다.",
            "설치비와 판매단가를 다시 확인하고 민감도 결과에서 손익이 바뀌는 조건을 살펴보세요.",
        )
    if result.minimum_dscr is not None and result.minimum_dscr < 1:
        return (
            "대출 상환 주의",
            "수익은 나지만 상환 부담이 큽니다.",
            "일부 연도에는 사업에서 번 현금만으로 원리금을 모두 갚기 어렵습니다. 자기자본 비율이나 대출 조건을 먼저 조정해 보세요.",
        )
    if result.minimum_dscr is not None and result.minimum_dscr < 1.2:
        return (
            "여유자금 확인",
            "사업성은 있지만 상환 여유가 작습니다.",
            "판매단가 하락이나 발전량 감소가 생기면 현금이 부족할 수 있습니다. 민감도 결과를 함께 확인하세요.",
        )
    return (
        "검토 가능",
        "현재 조건에서는 다음 검토로 넘어갈 수 있습니다.",
        "수익성과 원리금 상환 여력이 모두 기준을 충족합니다. 실제 견적과 계통연계 가능 여부를 추가로 확인하세요.",
    )


def render_decision_panel(result: AnalysisResult) -> None:
    """Render the farmer-facing decision summary next to the inputs."""
    badge, title, description = _decision_copy(result)
    tone = (
        "danger" if result.project_npv < 0
        else "warning" if result.minimum_dscr is not None and result.minimum_dscr < 1.2
        else "positive"
    )
    dscr_value = _dscr(result)
    dscr_note = _dscr_year_note(result)
    dscr_note = f"{dscr_note} 기준 · 1.0배 미만이면 부족" if dscr_note else "1.0배 미만이면 부족"

    st.markdown(
        f"""
        <div class="kifc-decision">
          <div class="kifc-decision__eyebrow">현재 조건의 핵심 판단</div>
          <div class="kifc-decision__status kifc-decision__status--{tone}">{badge}</div>
          <h2>{title}</h2>
          <p class="kifc-decision__lead">{description}</p>
          <div class="kifc-decision__metrics">
            <div>
              <span>필요 자기자본</span>
              <strong>{_money(-result.equity_cash_flows[0])}</strong>
            </div>
            <div>
              <span>원금상환 첫해</span>
              <strong>{_money(result.repayment_year_equity_cash or 0)}</strong>
            </div>
            <div>
              <span>상환 여력</span>
              <strong>{dscr_value}</strong>
              <small>{dscr_note}</small>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_summary_tab(result: AnalysisResult) -> None:
    st.subheader("사업성 지표")
    st.caption("사업 전체 수익성과 농가가 투입한 자기자본의 수익성은 서로 다른 현금흐름으로 계산합니다.")

    a, b, c, d = st.columns(4)
    a.metric("사업 순현재가치", _money(result.project_npv), help="총사업비를 Year 0에 반영한 사업 전체 NPV")
    b.metric("사업 내부수익률", _pct(result.project_irr), help="대출 조건과 무관한 사업 자체 IRR")
    c.metric("자기자본 내부수익률", _pct(result.equity_irr), help="초기 자기자본과 실제 원리금 상환을 반영한 IRR")
    dscr_note = _dscr_year_note(result)
    d.metric(
        f"최저 DSCR · {dscr_note}" if dscr_note else "최저 DSCR", _dscr(result),
        help="연간 영업현금흐름 ÷ 원리금 상환액의 최솟값. 인버터를 교체하는 해는 "
             "적립 없이 일시 지출로 반영하므로 그해만 낮게 나옵니다.",
    )

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
        "출력제어는 세부 가정의 '출력제어 비율'(기본 0%)로만 반영됩니다. "
        "세금·부가가치세, 임차료, 계통 보강비, 철거·원상복구비, 물가상승은 포함하지 않습니다."
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
