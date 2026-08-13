"""
Report Service — converts a Markdown report + chart images into a PDF.

Uses ReportLab (pure-Python, zero system-level dependencies).
WeasyPrint was removed because it requires GTK/Cairo native libs
which are not available on Windows without a separate runtime install.

Strategy:
  1. Parse Markdown line-by-line into ReportLab Flowables
  2. Fetch chart images from MinIO as bytes → embed inline as Image objects
  3. Build a styled PDF with professional header, typography, and page numbers
"""

from __future__ import annotations

import base64
import io
import re
from datetime import datetime
from typing import Optional

from app.services.minio_service import get_minio_client
from app.config import settings


# ── Chart fetching ────────────────────────────────────────────────────────────

def _fetch_chart_bytes(minio_path: str) -> Optional[bytes]:
    """Download a chart PNG from MinIO and return raw bytes, or None on failure."""
    try:
        client = get_minio_client()
        response = client.get_object(settings.minio_bucket, minio_path)
        data = response.read()
        response.close()
        return data
    except Exception:
        return None


def _build_chart_map(chart_paths: list[str]) -> dict[str, bytes]:
    """Fetch all chart images and return {path: bytes} and {filename: bytes}."""
    chart_map: dict[str, bytes] = {}
    for path in chart_paths:
        if not path:
            continue
        data = _fetch_chart_bytes(path)
        if data:
            chart_map[path] = data
            fname = path.split("/")[-1]
            chart_map[fname] = data
    return chart_map


# ── Page numbering canvas ─────────────────────────────────────────────────────

def _make_page_number_canvas(canvas_class):
    """Return a canvas class that draws page numbers in the footer."""
    class NumberedCanvas(canvas_class):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._saved_page_states: list = []

        def showPage(self):
            state = dict(self.__dict__)
            state.pop('_saved_page_states', None)
            self._saved_page_states.append(state)
            self._startPage()

        def save(self):
            num_pages = len(self._saved_page_states)
            for state in self._saved_page_states:
                self.__dict__.update(state)
                self._draw_page_number(num_pages)
                super().showPage()
            super().save()

        def _draw_page_number(self, page_count: int):
            from reportlab.lib import colors
            self.setFont("Helvetica", 8)
            self.setFillColor(colors.HexColor("#9ca3af"))
            text = f"Page {self._pageNumber} of {page_count}"
            self.drawRightString(
                self._pagesize[0] - 2 * 28.35,
                1.5 * 28.35 / 2,
                text,
            )

    return NumberedCanvas


# ── Markdown Parser Utilities ─────────────────────────────────────────────────

def safe_inline(text: str) -> str:
    """
    Apply inline markdown formatting safely for ReportLab.
    Protects inline code spans first so underscores/asterisks inside code
    don't create corrupt nested XML tags.
    """
    # 1. Protect inline code spans with placeholder tokens
    code_spans: list[str] = []
    def save_code(match):
        code_spans.append(match.group(1))
        return f"___CODE_SPAN_{len(code_spans) - 1}___"

    text = re.sub(r"`([^`]+)`", save_code, text)

    # 2. Escape XML special characters
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # 3. Bold (**text** or __text__)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)

    # 4. Italic (*text* or _text_ at word boundaries)
    text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
    # Only match _italic_ if bounded by spaces/non-word chars to avoid snake_case column names
    text = re.sub(r"(?<=^|\s)_([^\s_].*?[^\s_])_(?=\s|$|[.,!?;:])", r"<i>\1</i>", text)

    # 5. Restore inline code spans with ReportLab <font> tag
    for i, code in enumerate(code_spans):
        escaped_code = code.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        font_tag = f'<font name="Courier" size="8" color="#4f46e5">{escaped_code}</font>'
        text = text.replace(f"___CODE_SPAN_{i}___", font_tag)

    return text


def make_paragraph(text: str, style):
    """
    Safely construct a ReportLab Paragraph.
    If XML parsing fails due to unexpected formatting, falls back to plain escaped text.
    """
    from reportlab.platypus import Paragraph
    try:
        formatted = safe_inline(text)
        return Paragraph(formatted, style)
    except Exception:
        clean = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return Paragraph(clean, style)


# ── Main PDF generator ────────────────────────────────────────────────────────

def generate_pdf(
    markdown_text: str,
    title: str = "Analytical Report",
    filename: str = "dataset",
    findings_count: int = 0,
    chart_paths: list[str] | None = None,
) -> bytes:
    """
    Convert a Markdown report into a styled PDF using ReportLab.
    Returns raw PDF bytes.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, HRFlowable,
        Image, Table, TableStyle, KeepTogether,
    )
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
    from reportlab.pdfgen.canvas import Canvas

    chart_paths = chart_paths or []
    chart_map = _build_chart_map(chart_paths)

    # ── Colour palette ────────────────────────────────────────────────────────
    INDIGO    = colors.HexColor("#4f46e5")
    VIOLET    = colors.HexColor("#7c3aed")
    DARK      = colors.HexColor("#111827")
    BODY      = colors.HexColor("#374151")
    MUTED     = colors.HexColor("#6b7280")
    BORDER    = colors.HexColor("#e5e7eb")
    BG_CODE   = colors.HexColor("#f3f4f6")
    BG_TABLE  = colors.HexColor("#f9fafb")
    WHITE     = colors.white

    # ── Styles ────────────────────────────────────────────────────────────────
    styles = getSampleStyleSheet()

    def ps(name, **kw) -> ParagraphStyle:
        return ParagraphStyle(name, **kw)

    s_title = ps("RTitle",
        fontName="Helvetica-Bold", fontSize=22, textColor=DARK,
        spaceAfter=4, leading=28,
    )
    s_meta = ps("RMeta",
        fontName="Helvetica", fontSize=9, textColor=MUTED,
        spaceAfter=20,
    )
    s_h1 = ps("RH1",
        fontName="Helvetica-Bold", fontSize=18, textColor=DARK,
        spaceBefore=24, spaceAfter=8, leading=24,
    )
    s_h2 = ps("RH2",
        fontName="Helvetica-Bold", fontSize=14, textColor=INDIGO,
        spaceBefore=18, spaceAfter=6, leading=20,
    )
    s_h3 = ps("RH3",
        fontName="Helvetica-Bold", fontSize=11, textColor=VIOLET,
        spaceBefore=12, spaceAfter=4, leading=16,
    )
    s_body = ps("RBody",
        fontName="Helvetica", fontSize=10, textColor=BODY,
        spaceAfter=8, leading=16,
    )
    s_bullet = ps("RBullet",
        fontName="Helvetica", fontSize=10, textColor=BODY,
        spaceAfter=4, leading=15, leftIndent=16,
        bulletText="•", bulletIndent=4,
    )
    s_code = ps("RCode",
        fontName="Courier", fontSize=8, textColor=DARK,
        spaceAfter=8, leading=13, leftIndent=12, rightIndent=12,
        backColor=BG_CODE, borderPadding=8,
    )
    s_caption = ps("RCaption",
        fontName="Helvetica-Oblique", fontSize=8, textColor=MUTED,
        spaceAfter=12, leading=12, alignment=TA_CENTER,
    )
    s_quote = ps("RQuote",
        fontName="Helvetica-Oblique", fontSize=10, textColor=MUTED,
        spaceAfter=8, leading=15, leftIndent=20,
    )
    s_th = ps("RTH",
        fontName="Helvetica-Bold", fontSize=9, textColor=WHITE,
        leading=12, alignment=TA_LEFT,
    )
    s_td = ps("RTD",
        fontName="Helvetica", fontSize=9, textColor=BODY,
        leading=13, alignment=TA_LEFT,
    )

    # ── Buffer + doc ──────────────────────────────────────────────────────────
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2.2 * cm,
        leftMargin=2.2 * cm,
        topMargin=2.0 * cm,
        bottomMargin=2.0 * cm,
        title=title,
        author="Autonomous Data Analyst Agent",
    )

    W = A4[0] - 4.4 * cm  # usable width

    story: list = []

    # ── Cover header ──────────────────────────────────────────────────────────
    header_data = [[
        make_paragraph(f"📊 {title}", s_title),
    ]]
    header_table = Table(header_data, colWidths=[W])
    header_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#f5f3ff")),
        ("LINEBELOW",     (0, 0), (-1, -1), 2, INDIGO),
        ("TOPPADDING",    (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("LEFTPADDING",   (0, 0), (-1, -1), 16),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 16),
        ("ROUNDEDCORNERS", [6]),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 6))

    meta_text = (
        f"<b>Generated:</b> {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}   "
        f"<b>Dataset:</b> {filename}   "
        f"<b>Findings:</b> {findings_count}"
    )
    story.append(make_paragraph(meta_text, s_meta))
    story.append(HRFlowable(width=W, thickness=1, color=BORDER, spaceAfter=16))

    # ── Markdown parser ───────────────────────────────────────────────────────
    in_code   = False
    code_buf: list[str] = []
    table_buf: list[str] = []

    def flush_code():
        nonlocal in_code, code_buf
        if code_buf:
            text = "\n".join(code_buf).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            story.append(make_paragraph(text.replace("\n", "<br/>"), s_code))
            story.append(Spacer(1, 4))
        code_buf = []
        in_code = False

    def flush_table():
        nonlocal table_buf
        if not table_buf:
            return
        
        parsed_rows: list[list[str]] = []
        for row_str in table_buf:
            cells = [c.strip() for c in row_str.strip("|").split("|")]
            # Ignore divider rows like |---|---|
            if all(re.match(r"^:?-+:?$", c) for c in cells if c):
                continue
            parsed_rows.append(cells)
        
        table_buf = []
        if not parsed_rows:
            return

        # Determine column widths
        num_cols = max(len(r) for r in parsed_rows)
        col_width = W / max(num_cols, 1)

        table_data = []
        for r_idx, row in enumerate(parsed_rows):
            row_cells = []
            is_header = (r_idx == 0)
            style = s_th if is_header else s_td
            for cell in row:
                row_cells.append(make_paragraph(cell, style))
            # Pad row if fewer cells than num_cols
            while len(row_cells) < num_cols:
                row_cells.append(make_paragraph("", style))
            table_data.append(row_cells)

        t = Table(table_data, colWidths=[col_width] * num_cols)
        t_style = [
            ("BACKGROUND", (0, 0), (-1, 0), INDIGO),
            ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
        ]
        # Alternating row background
        for i in range(1, len(table_data)):
            if i % 2 == 0:
                t_style.append(("BACKGROUND", (0, i), (-1, i), BG_TABLE))

        t.setStyle(TableStyle(t_style))
        story.append(Spacer(1, 4))
        story.append(KeepTogether([t]))
        story.append(Spacer(1, 8))

    def try_embed_chart(src: str) -> bool:
        """Try to embed a chart from the chart map into the story. Returns True if successful."""
        for key, data in chart_map.items():
            if key in src or src in key:
                try:
                    img_buf = io.BytesIO(data)
                    img = Image(img_buf, width=W * 0.85, height=W * 0.52)
                    img.hAlign = "CENTER"
                    story.append(Spacer(1, 8))
                    story.append(KeepTogether([img]))
                    story.append(Spacer(1, 4))
                    return True
                except Exception:
                    pass
        return False

    for line in markdown_text.splitlines():
        stripped = line.strip()

        # ── Code fence ────────────────────────────────────────────────────────
        if stripped.startswith("```"):
            flush_table()
            if in_code:
                flush_code()
            else:
                in_code = True
            continue

        if in_code:
            code_buf.append(line)
            continue

        # ── Table row ─────────────────────────────────────────────────────────
        if stripped.startswith("|") and stripped.endswith("|"):
            table_buf.append(stripped)
            continue
        else:
            flush_table()

        # ── Horizontal rule ───────────────────────────────────────────────────
        if re.match(r"^-{3,}$|^\*{3,}$|^_{3,}$", stripped):
            story.append(HRFlowable(width=W, thickness=1, color=BORDER, spaceBefore=10, spaceAfter=10))
            continue

        # ── Headings ──────────────────────────────────────────────────────────
        if stripped.startswith("#### "):
            story.append(make_paragraph(stripped[5:], s_h3))
            continue
        if stripped.startswith("### "):
            story.append(make_paragraph(stripped[4:], s_h3))
            continue
        if stripped.startswith("## "):
            story.append(make_paragraph(stripped[3:], s_h2))
            continue
        if stripped.startswith("# "):
            story.append(make_paragraph(stripped[2:], s_h1))
            continue

        # ── Bullet list ───────────────────────────────────────────────────────
        m = re.match(r"^[-*+]\s+(.*)", stripped)
        if m:
            story.append(make_paragraph(m.group(1), s_bullet))
            continue

        # ── Numbered list ─────────────────────────────────────────────────────
        m = re.match(r"^\d+\.\s+(.*)", stripped)
        if m:
            story.append(make_paragraph(m.group(1), s_bullet))
            continue

        # ── Blockquote ────────────────────────────────────────────────────────
        if stripped.startswith("> "):
            story.append(make_paragraph(stripped[2:], s_quote))
            continue

        # ── Image / chart reference ───────────────────────────────────────────
        m = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)", stripped)
        if m:
            alt, src = m.group(1), m.group(2)
            embedded = try_embed_chart(src)
            if embedded and alt:
                story.append(make_paragraph(alt, s_caption))
            continue

        # ── Blank line ────────────────────────────────────────────────────────
        if not stripped:
            story.append(Spacer(1, 6))
            continue

        # ── Regular paragraph ─────────────────────────────────────────────────
        story.append(make_paragraph(stripped, s_body))

    # Flush unclosed blocks
    if in_code:
        flush_code()
    flush_table()

    # ── Footer rule ───────────────────────────────────────────────────────────
    story.append(Spacer(1, 20))
    story.append(HRFlowable(width=W, thickness=1, color=BORDER, spaceAfter=6))
    story.append(make_paragraph(
        "Generated by the <b>Autonomous Data Analyst Agent</b>",
        ps("RFooter", fontName="Helvetica", fontSize=8, textColor=MUTED, alignment=TA_CENTER),
    ))

    # ── Build PDF ─────────────────────────────────────────────────────────────
    NumberedCanvas = _make_page_number_canvas(Canvas)
    doc.build(story, canvasmaker=NumberedCanvas)
    return buffer.getvalue()

