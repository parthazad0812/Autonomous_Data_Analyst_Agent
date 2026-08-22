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
from datetime import datetime, timezone
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
            self._saved_page_states.append(dict(self.__dict__))
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
    # Gradient-effect header table
    header_data = [[
        Paragraph(f"📊 {title}", s_title),
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
        f"<b>Generated:</b> {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}   "
        f"<b>Dataset:</b> {filename}   "
        f"<b>Findings:</b> {findings_count}"
    )
    story.append(Paragraph(meta_text, s_meta))
    story.append(HRFlowable(width=W, thickness=1, color=BORDER, spaceAfter=16))

    # ── Markdown parser ───────────────────────────────────────────────────────
    in_code   = False
    code_buf: list[str] = []

    def flush_code():
        nonlocal in_code, code_buf
        if code_buf:
            text = "\n".join(code_buf).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            story.append(Paragraph(text.replace("\n", "<br/>"), s_code))
            story.append(Spacer(1, 4))
        code_buf = []
        in_code = False

    def safe_inline(text: str) -> str:
        """Apply inline markdown formatting safely for ReportLab."""
        text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        # Bold
        text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
        text = re.sub(r"__(.+?)__",     r"<b>\1</b>", text)
        # Italic — use [^<>]+? so the match cannot span across <b>/<i> tags
        # that were just inserted above, preventing overlapping HTML like
        # <b>...<i>...</b>...</i> which crashes ReportLab's parser.
        text = re.sub(r"\*([^<>]+?)\*",     r"<i>\1</i>", text)
        text = re.sub(r"(?<!\w)_([^<>]+?)_(?!\w)", r"<i>\1</i>", text)
        # Inline code
        text = re.sub(
            r"`(.+?)`",
            r'<font name="Courier" size="8" color="#4f46e5">\1</font>',
            text,
        )
        return text

    def _safe_paragraph(text: str, style) -> Paragraph:
        """Create a Paragraph with proper fallback on parse errors."""
        try:
            return Paragraph(safe_inline(text), style)
        except Exception:
            # Fallback: strip all markdown formatting, keep only escaped text
            plain = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            try:
                return Paragraph(plain, style)
            except Exception:
                return Paragraph("[content could not be rendered]", style)

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
            if in_code:
                flush_code()
            else:
                in_code = True
            continue

        if in_code:
            code_buf.append(line)
            continue

        # ── Horizontal rule ───────────────────────────────────────────────────
        if re.match(r"^-{3,}$|^\*{3,}$|^_{3,}$", stripped):
            story.append(HRFlowable(width=W, thickness=1, color=BORDER, spaceBefore=10, spaceAfter=10))
            continue

        # ── Headings ──────────────────────────────────────────────────────────
        if stripped.startswith("#### "):
            story.append(_safe_paragraph(stripped[5:], s_h3))
            continue
        if stripped.startswith("### "):
            story.append(_safe_paragraph(stripped[4:], s_h3))
            continue
        if stripped.startswith("## "):
            story.append(_safe_paragraph(stripped[3:], s_h2))
            continue
        if stripped.startswith("# "):
            story.append(_safe_paragraph(stripped[2:], s_h1))
            continue

        # ── Bullet list ───────────────────────────────────────────────────────
        m = re.match(r"^[-*+]\s+(.*)", stripped)
        if m:
            story.append(_safe_paragraph(m.group(1), s_bullet))
            continue

        # ── Numbered list ─────────────────────────────────────────────────────
        m = re.match(r"^\d+\.\s+(.*)", stripped)
        if m:
            story.append(_safe_paragraph(m.group(1), s_bullet))
            continue

        # ── Blockquote ────────────────────────────────────────────────────────
        if stripped.startswith("> "):
            story.append(_safe_paragraph(stripped[2:], s_quote))
            continue

        # ── Image / chart reference ───────────────────────────────────────────
        m = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)", stripped)
        if m:
            alt, src = m.group(1), m.group(2)
            embedded = try_embed_chart(src)
            if embedded and alt:
                story.append(Paragraph(alt, s_caption))
            continue

        # ── Blank line ────────────────────────────────────────────────────────
        if not stripped:
            story.append(Spacer(1, 6))
            continue

        # ── Regular paragraph ─────────────────────────────────────────────────
        story.append(_safe_paragraph(stripped, s_body))

    # Flush any unclosed code block
    if in_code:
        flush_code()

    # ── Footer rule ───────────────────────────────────────────────────────────
    story.append(Spacer(1, 20))
    story.append(HRFlowable(width=W, thickness=1, color=BORDER, spaceAfter=6))
    story.append(Paragraph(
        "Generated by the <b>Autonomous Data Analyst Agent</b>",
        ps("RFooter", fontName="Helvetica", fontSize=8, textColor=MUTED, alignment=TA_CENTER),
    ))

    # ── Build PDF ─────────────────────────────────────────────────────────────
    NumberedCanvas = _make_page_number_canvas(Canvas)
    doc.build(story, canvasmaker=NumberedCanvas)
    return buffer.getvalue()
