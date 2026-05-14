"""Summary PDF report generation for the Streamlit app."""
from __future__ import annotations

from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

from core.calculator import AnalysisResult, EconomicAnalysis


KIFC_LOGO_PATH = Path(__file__).resolve().parents[1] / "assets" / "kifc-logo.png"


def _money(thousand_krw: float) -> str:
    return f"{round(thousand_krw):,} 천원"


def _manwon(thousand_krw: float) -> str:
    return f"{round(thousand_krw / 10):,} 만원"


def _signed_manwon(thousand_krw: float) -> str:
    sign = "+" if thousand_krw >= 0 else "-"
    return f"{sign}{_manwon(abs(thousand_krw))}"


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _num(value: float, suffix: str = "") -> str:
    return f"{value:,.1f}{suffix}"


def _verdict(bc_ratio: float) -> str:
    if bc_ratio >= 1.5:
        return "수익성 매우 좋음"
    if bc_ratio >= 1.2:
        return "수익성 있음"
    if bc_ratio >= 1.0:
        return "수익성 경계"
    return "손실 우려"


def build_summary_pdf(
    *,
    result: AnalysisResult,
    analysis: EconomicAnalysis,
    assumptions: dict[str, Any],
    share_url: str | None = None,
) -> bytes:
    """Build a Korean summary PDF and return it as bytes.

    The report is intentionally compact and text/table based so generation stays
    fast enough for an interactive Streamlit download button.
    """
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.lib.utils import ImageReader
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        from reportlab.pdfbase.pdfmetrics import registerFont
        from reportlab.platypus import (
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except ImportError as exc:
        raise RuntimeError(
            "PDF 생성을 위해 reportlab 패키지가 필요합니다. "
            "`pip install reportlab` 후 다시 실행하세요."
        ) from exc

    registerFont(UnicodeCIDFont("HYGothic-Medium"))
    registerFont(UnicodeCIDFont("HYSMyeongJo-Medium"))

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=15 * mm,
        title="영농형 태양광 경제성 요약 보고서",
        author="AGPV ROI Calculator",
    )

    sample = getSampleStyleSheet()
    styles = {
        "title": ParagraphStyle(
            "KoreanTitle",
            parent=sample["Title"],
            fontName="HYGothic-Medium",
            fontSize=18,
            leading=24,
            alignment=TA_CENTER,
            spaceAfter=8,
        ),
        "subtitle": ParagraphStyle(
            "KoreanSubtitle",
            parent=sample["Normal"],
            fontName="HYGothic-Medium",
            fontSize=9,
            leading=13,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#4b5563"),
            spaceAfter=12,
        ),
        "heading": ParagraphStyle(
            "KoreanHeading",
            parent=sample["Heading2"],
            fontName="HYGothic-Medium",
            fontSize=12,
            leading=16,
            textColor=colors.HexColor("#075985"),
            spaceBefore=8,
            spaceAfter=6,
        ),
        "normal": ParagraphStyle(
            "KoreanNormal",
            parent=sample["Normal"],
            fontName="HYSMyeongJo-Medium",
            fontSize=9,
            leading=13,
            alignment=TA_LEFT,
            wordWrap="CJK",
        ),
        "small": ParagraphStyle(
            "KoreanSmall",
            parent=sample["Normal"],
            fontName="HYSMyeongJo-Medium",
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#4b5563"),
            wordWrap="CJK",
        ),
    }

    def para(text: str, style: str = "normal") -> Paragraph:
        escaped = (
            str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\n", "<br/>")
        )
        return Paragraph(escaped, styles[style])

    def table(rows: list[list[str]], widths: list[float] | None = None) -> Table:
        converted = [[para(cell) for cell in row] for row in rows]
        tbl = Table(converted, colWidths=widths, hAlign="LEFT", repeatRows=1)
        tbl.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), "HYSMyeongJo-Medium"),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e0f2fe")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0c4a6e")),
                    ("FONTNAME", (0, 0), (-1, 0), "HYGothic-Medium"),
                    ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        return tbl

    def draw_footer_logo(canvas, _doc):
        if not KIFC_LOGO_PATH.exists():
            return

        reader = ImageReader(str(KIFC_LOGO_PATH))
        image_width, image_height = reader.getSize()
        logo_width = 32 * mm
        logo_height = logo_width * image_height / image_width
        x = (doc.pagesize[0] - logo_width) / 2
        y = 5 * mm

        canvas.saveState()
        canvas.drawImage(
            reader,
            x,
            y,
            width=logo_width,
            height=logo_height,
            mask="auto",
            preserveAspectRatio=True,
        )
        canvas.restoreState()

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    meta = assumptions.get("meta", {})
    track_label = "PPA 고정가격계약" if analysis.price.track == "ppa" else "RPS 변동형(SMP+REC)"
    annual_income = result.annual_power_revenue + result.annual_crop_revenue
    annual_net = result.npv_total_annualized
    delta_vs_crop = annual_net - result.annual_crop_revenue_base

    story = [
        para("영농형 태양광 경제성 요약 보고서", "title"),
        para(
            f"생성일 {generated_at} · 데이터 기준 {meta.get('data_date', '확인 필요')} · "
            f"버전 {meta.get('version', '-')}",
            "subtitle",
        ),
        para("종합 평가", "heading"),
        table(
            [
                ["항목", "결과"],
                ["평가", _verdict(result.bc_ratio)],
                ["B/C 비율", f"{result.bc_ratio:.2f}"],
                ["내부수익률(IRR)", _pct(result.irr) if result.irr is not None else "-"],
                ["투자 회수 기간", f"{result.payback_year:.1f} 년" if result.payback_year is not None else "-"],
                ["연간 순이익(벼+태양광)", _manwon(annual_net)],
                ["벼만 재배 대비", _signed_manwon(delta_vs_crop)],
            ],
            [42 * mm, 118 * mm],
        ),
        Spacer(1, 6),
        para("입력 조건", "heading"),
        table(
            [
                ["항목", "값"],
                ["농지 면적", f"{analysis.facility.area_m2:,.0f} ㎡"],
                ["시설 용량", f"{analysis.facility.capacity_kw:,.0f} kW"],
                ["총 사업비", _money(analysis.cost.total)],
                ["자기자본 비율", _pct(analysis.finance.equity_ratio)],
                ["융자 금리", _pct(analysis.finance.loan_rate)],
                ["발전 가격 트랙", track_label],
                ["최종 발전단가", _num(analysis.price.unit_price, " 원/kWh")],
                ["운영 기간", f"{analysis.land_law.max_operation_years} 년"],
            ],
            [42 * mm, 118 * mm],
        ),
        Spacer(1, 6),
        para("연간 수입·지출", "heading"),
        table(
            [
                ["구분", "항목", "금액"],
                ["수입", "발전 수익", _money(result.annual_power_revenue)],
                ["수입", "벼 소득(단수감소 반영)", _money(result.annual_crop_revenue)],
                ["수입", "합계", _money(annual_income)],
                ["지출", "자기자본·이자·원금상환", _money(result.annual_finance_cost)],
                ["지출", "전기안전관리대행", _money(analysis.opex.electrical_mgmt)],
                ["지출", "보험료", _money(analysis.opex.insurance)],
                ["지출", "인버터 교체(연간 분할)", _money(analysis.opex.inverter_replace)],
                ["지출", "폐기물 처리", _money(analysis.opex.waste_disposal)],
                ["지출", "전기료·수선비", _money(analysis.opex.utility_repair)],
                ["지출", "합계", _money(result.annual_opex)],
            ],
            [24 * mm, 74 * mm, 62 * mm],
        ),
        Spacer(1, 6),
        para("현재가치 기준 지표", "heading"),
        table(
            [
                ["항목", "금액"],
                ["태양광 순현재가치", _money(result.npv_power)],
                ["벼 소득 현재가치(단수감소 반영)", _money(result.npv_crop_with_reduction)],
                ["총 순현재가치", _money(result.npv_total)],
                ["벼만 재배 시 현재가치", _money(result.npv_baseline_crop_only)],
                ["할인율", _pct(result.discount_rate)],
                ["분석 기간", f"{result.project_years} 년"],
            ],
            [72 * mm, 88 * mm],
        ),
        Spacer(1, 8),
        para(
            "본 보고서는 입력값과 공개 가정에 기반한 추정 결과입니다. 실제 도입 전에는 "
            "한국에너지공단, 지자체, 금융기관, 시공사와 사업 조건을 별도 확인하세요.",
            "small",
        ),
    ]

    if share_url:
        story.extend(
            [
                Spacer(1, 4),
                para(f"입력값 공유 링크: {share_url}", "small"),
            ]
        )

    doc.build(story, onFirstPage=draw_footer_logo, onLaterPages=draw_footer_logo)
    buffer.seek(0)
    return buffer.getvalue()
