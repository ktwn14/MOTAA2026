# -*- coding: utf-8 -*-
"""
Generates a downloadable PDF report of a computed chart.

Uses reportlab (pure Python, no system dependencies beyond pip install —
easy on macOS). Myanmar Unicode text needs a font that actually contains
Myanmar glyphs; we try a few common system font paths and fall back to
Helvetica (which will render Myanmar text as boxes) with a clear warning
printed to the console so this is easy to notice and fix.
"""
import io
import os
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle, Paragraph,
                                 Spacer, PageBreak, Image as RLImage)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.graphics.shapes import Drawing, Polygon, Line, String
from reportlab.graphics import renderPM

from astro.constants import GRAHA_MM, RASHI_MM, GRAHA9
from astro.chart_svg import house_polygons, house_label_anchor, center_box

FONT_NAME = "Helvetica"
_CANDIDATE_FONTS = [
    # If you have "Masterpiece Uni Round" installed, point at its .ttf here
    # (Font Book usually installs to ~/Library/Fonts or /Library/Fonts):
    os.path.expanduser("~/Library/Fonts/MasterpieceUniRound.ttf"),
    os.path.expanduser("~/Library/Fonts/Masterpiece Uni Round.ttf"),
    "/Library/Fonts/MasterpieceUniRound.ttf",
    "/Library/Fonts/Masterpiece Uni Round.ttf",
    "/System/Library/Fonts/Supplemental/Myanmar MN.ttf",     # macOS fallback
    "/System/Library/Fonts/Myanmar.ttc",                      # older macOS
    "/usr/share/fonts/truetype/noto/NotoSansMyanmar-Regular.ttf",  # Linux (Noto)
    "/usr/share/fonts/truetype/padauk/Padauk.ttf",            # Linux (Padauk)
]


def _register_myanmar_font():
    global FONT_NAME
    for path in _CANDIDATE_FONTS:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont("MyanmarFont", path))
                FONT_NAME = "MyanmarFont"
                return
            except Exception:
                continue
    print("[pdf_report] WARNING: no Myanmar-capable font found on this system — "
          "Myanmar text in the PDF will not render correctly. Install 'Noto Sans "
          "Myanmar' or 'Padauk' and add its path to _CANDIDATE_FONTS in "
          "reports/pdf_report.py.")


_register_myanmar_font()


def _styles():
    ss = getSampleStyleSheet()
    base = ParagraphStyle("body", parent=ss["Normal"], fontName=FONT_NAME, fontSize=9, leading=13)
    h1 = ParagraphStyle("h1", parent=ss["Heading1"], fontName=FONT_NAME, fontSize=16)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], fontName=FONT_NAME, fontSize=12,
                         textColor=colors.HexColor("#4f33cc"))
    muted = ParagraphStyle("muted", parent=base, textColor=colors.HexColor("#6b7280"), fontSize=8)
    return base, h1, h2, muted


def _pct(v):
    return "-" if v is None else f"{v*100:.0f}%"


def _diamond_drawing(house_content, title, box=260):
    """Builds a reportlab Drawing of the Myanmar-style diamond chart, reusing
    the exact same geometry as the web SVG version (astro/chart_svg.py)."""
    scale = box / 260.0
    d = Drawing(box, box + 22)
    d.add(String(box / 2, box + 8, title, fontName=FONT_NAME, fontSize=10 * scale,
                  fillColor=colors.HexColor("#4f33cc"), textAnchor="middle"))

    def flip(y):  # reportlab y-axis grows upward; chart_svg's grows downward
        return box - y

    polys = house_polygons(box)
    for h, poly in polys.items():
        pts = []
        for (x, y) in poly:
            pts.extend([x, flip(y)])
        p = Polygon(pts, strokeColor=colors.HexColor("#2b2b2b"), strokeWidth=0.8,
                     fillColor=colors.HexColor("#fffdf7"))
        d.add(p)

    for h in range(1, 13):
        ax, ay = house_label_anchor(h, box)
        lines = house_content.get(h, [])
        n = len(lines)
        start_y = ay + (n - 1) * 5 * scale
        for i, line in enumerate(lines):
            y = start_y - i * 10 * scale
            size = (8 if i == 0 else 7) * scale
            color = colors.HexColor("#4f33cc") if i == 0 else colors.HexColor("#1f2430")
            d.add(String(ax, flip(y), line, fontName=FONT_NAME, fontSize=size,
                          fillColor=color, textAnchor="middle"))
    return d


def generate_pdf(chart, diamonds=None) -> io.BytesIO:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                             leftMargin=18 * mm, rightMargin=18 * mm,
                             topMargin=16 * mm, bottomMargin=16 * mm)
    body, h1, h2, muted = _styles()
    story = []

    binput = chart["input"]
    story.append(Paragraph(f"MOTAA ဇာတာ အစီရင်ခံစာ — {binput.name}", h1))
    meta = (f"{chart['local_dt'].strftime('%Y-%m-%d %H:%M:%S')} "
            f"(UTC{'+' if binput.tz_offset_hours >= 0 else ''}{binput.tz_offset_hours}) &nbsp;·&nbsp; "
            f"Lat {binput.latitude:.4f}, Lon {binput.longitude:.4f} &nbsp;·&nbsp; "
            f"Ayanamsa: {binput.ayanamsa} ({chart['ayanamsa_value']:.4f}&deg;) &nbsp;·&nbsp; "
            f"House system: {binput.house_system}")
    story.append(Paragraph(meta, muted))
    story.append(Paragraph(f"လဂ် — <b>{chart['lagna_rashi_mm']}</b> {chart['lagna_lon'] % 30:.4f}&deg;", body))
    story.append(Spacer(1, 10))

    if diamonds:
        story.append(Paragraph("ဇာတာ ဇယား", h2))
        row = [
            [_diamond_drawing(diamonds["rashi"], "ရာသီ", box=145),
             _diamond_drawing(diamonds["bhava"], "ဘာဝ", box=145),
             _diamond_drawing(diamonds["navamsa"], "နဝင်း (D9)", box=145)]
        ]
        dt = Table(row, colWidths=[155, 155, 155])
        dt.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("ALIGN", (0, 0), (-1, -1), "CENTER")]))
        story.append(dt)
        story.append(Spacer(1, 10))

    # --- Planet strength table ---
    story.append(Paragraph("ဂြိုဟ် အင်အား (MOTAA Step 1-6)", h2))
    header = ["ဂြိုဟ်", "ရာသီ", "တန့်", "ကာရက", "S1", "S2", "S3", "S4", "S5", "S6", "နောက်ဆုံး"]
    rows = [header]
    for name in GRAHA9:
        gp = chart["positions"][name]
        rows.append([
            GRAHA_MM[name], RASHI_MM[gp.rashi_idx - 1], str(gp.house),
            "ပါပ" if gp.karaka == "Papa" else "သောမ",
            _pct(gp.step1), _pct(gp.step2), _pct(gp.step3), _pct(gp.step4), _pct(gp.step5), _pct(gp.step6),
            _pct(gp.final),
        ])
    t = Table(rows, repeatRows=1)
    t.setStyle(_table_style())
    story.append(t)
    story.append(Spacer(1, 14))

    # --- Bhava influence table ---
    story.append(Paragraph("ဘာဝ လွှမ်းမိုးမှု (BhavaInfluence)", h2))
    header2 = ["တန့်", "ရာသီ", "ပိုင်ရှင်", "သောမ/ပါပ", "ကိုယ်ပိုင် အင်အား", "ဂြိုဟ်ကောင်း", "ဂြိုဟ်ဆိုး", "စုစုပေါင်း"]
    rows2 = [header2]
    for row in chart["bhavas"]:
        rows2.append([
            str(row.house), row.rashi_name, GRAHA_MM[row.lord],
            "ပါပ" if row.karaka == "Papa" else "သောမ",
            _pct(row.own_strength), _pct(row.positive_influence), _pct(row.negative_influence),
            _pct(row.net_influence),
        ])
    t2 = Table(rows2, repeatRows=1)
    t2.setStyle(_table_style())
    story.append(t2)
    story.append(PageBreak())

    # --- Dasha ---
    story.append(Paragraph("ဝိသောတရီ ဒသာ (Vimshottari Dasha)", h2))
    header3 = ["မဟာဒသာ", "အစ", "အဆုံး", "နှစ်ပေါင်း"]
    rows3 = [header3]
    for md in chart["dasha_sequence"]:
        rows3.append([GRAHA_MM[md.lord], md.start.strftime("%Y-%m-%d"),
                      md.end.strftime("%Y-%m-%d"), f"{md.years:.2f}"])
    t3 = Table(rows3, repeatRows=1)
    t3.setStyle(_table_style())
    story.append(t3)
    story.append(Spacer(1, 12))

    for md in chart["dasha_sequence"][:3]:
        story.append(Paragraph(f"{GRAHA_MM[md.lord]} မဟာဒသာ ({md.start.strftime('%Y-%m-%d')} – {md.end.strftime('%Y-%m-%d')}) ၏ အန္တရများ", body))
        arows = [["အန္တရ", "အစ", "အဆုံး"]]
        for ad in md.antardashas:
            arows.append([GRAHA_MM[ad.lord], ad.start.strftime("%Y-%m-%d"), ad.end.strftime("%Y-%m-%d")])
        ta = Table(arows, repeatRows=1)
        ta.setStyle(_table_style(small=True))
        story.append(ta)
        story.append(Spacer(1, 8))

    doc.build(story)
    buf.seek(0)
    return buf


def _table_style(small=False):
    fs = 7 if small else 8
    return TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), FONT_NAME),
        ("FONTSIZE", (0, 0), (-1, -1), fs),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0eeff")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#4f33cc")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e3e5ea")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ])
