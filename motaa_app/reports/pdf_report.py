# -*- coding: utf-8 -*-
"""
Generates a downloadable PDF report of a computed chart.

Uses reportlab (pure Python, no system dependencies beyond pip install —
easy on macOS). Myanmar Unicode text needs a font that actually contains
Myanmar glyphs; reportlab's built-in fonts (Helvetica etc.) don't, and
relying on the *host* having one installed meant the PDF silently fell
back to rendering Myanmar text as black boxes on any machine that
didn't (e.g. a fresh Linux container/Codespace with no Myanmar font
package) — this bit real users, not just a hypothetical. So this bundles
Padauk (SIL Open Font License — see static/fonts/Padauk-LICENSE.txt),
one directory over from this file, and tries that first; a handful of
common system paths are kept below only as a fallback for anyone who's
replaced it with a different font locally.
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
from astro.chart_svg import (house_polygons, house_label_anchor, house_bbox, center_box,
                              text_layout_for_lines, diagonal_x0_bounds, _CODE_SIZE_FACTOR)
from astro.ephemeris import HOUSE_SYSTEM_LABEL_MAP

_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FONT_NAME = "Helvetica"
FONT_NAME_BOLD = "Helvetica-Bold"
_CANDIDATE_FONTS = [
    # If you have "Masterpiece Uni Round" installed, point at its .ttf here
    # (Font Book usually installs to ~/Library/Fonts or /Library/Fonts) to
    # make the PDF match the web UI's own font:
    os.path.expanduser("~/Library/Fonts/MasterpieceUniRound.ttf"),
    os.path.expanduser("~/Library/Fonts/Masterpiece Uni Round.ttf"),
    "/Library/Fonts/MasterpieceUniRound.ttf",
    "/Library/Fonts/Masterpiece Uni Round.ttf",
    # Bundled with this project — works out of the box on any machine,
    # regardless of what (if anything) is installed system-wide, so this
    # is the effective default whenever the font above isn't present.
    os.path.join(_APP_DIR, "static", "fonts", "Padauk-Regular.ttf"),
    "/System/Library/Fonts/Supplemental/Myanmar MN.ttf",     # macOS fallback
    "/System/Library/Fonts/Myanmar.ttc",                      # older macOS
    "/usr/share/fonts/truetype/noto/NotoSansMyanmar-Regular.ttf",  # Linux (Noto)
    "/usr/share/fonts/truetype/padauk/Padauk.ttf",            # Linux (Padauk)
]
_CANDIDATE_FONTS_BOLD = [
    os.path.expanduser("~/Library/Fonts/MasterpieceUniRound-Bold.ttf"),
    "/Library/Fonts/MasterpieceUniRound-Bold.ttf",
    os.path.join(_APP_DIR, "static", "fonts", "Padauk-Bold.ttf"),
    "/usr/share/fonts/truetype/noto/NotoSansMyanmar-Bold.ttf",
    "/usr/share/fonts/truetype/padauk/Padauk-Bold.ttf",
]


def _register_myanmar_font():
    global FONT_NAME, FONT_NAME_BOLD
    for path in _CANDIDATE_FONTS:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont("MyanmarFont", path))
                FONT_NAME = "MyanmarFont"
                break
            except Exception:
                continue
    else:
        print("[pdf_report] WARNING: no Myanmar-capable font found on this system — "
              "Myanmar text in the PDF will not render correctly. Install 'Noto Sans "
              "Myanmar' or 'Padauk' and add its path to _CANDIDATE_FONTS in "
              "reports/pdf_report.py.")

    for path in _CANDIDATE_FONTS_BOLD:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont("MyanmarFont-Bold", path))
                FONT_NAME_BOLD = "MyanmarFont-Bold"
                return
            except Exception:
                continue
    # No true bold face found for whichever font matched above — reuse the
    # regular one rather than silently falling back to Helvetica-Bold
    # (which would render Myanmar text as boxes again).
    FONT_NAME_BOLD = FONT_NAME


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


def _dms(value: float, pos_dir: str, neg_dir: str) -> str:
    """Format a signed decimal-degree float as "dd:mm:ss D" (matches the
    web UI's own dd:mm:ss input/display convention)."""
    direction = pos_dir if value >= 0 else neg_dir
    value = abs(value)
    deg = int(value)
    minute_full = (value - deg) * 60.0
    minute = int(minute_full)
    sec = round((minute_full - minute) * 60.0)
    if sec == 60:
        sec, minute = 0, minute + 1
    if minute == 60:
        minute, deg = 0, deg + 1
    return f"{deg}:{minute:02d}:{sec:02d} {direction}"


def _dms_sym(value: float) -> str:
    """Format an unsigned decimal-degree float (e.g. an ayanamsa value) as
    "dd°mm'ss\"" — no direction letter, since it isn't a coordinate."""
    deg = int(value)
    minute_full = (value - deg) * 60.0
    minute = int(minute_full)
    sec = round((minute_full - minute) * 60.0)
    if sec == 60:
        sec, minute = 0, minute + 1
    if minute == 60:
        minute, deg = 0, deg + 1
    return f"{deg}°{minute:02d}'{sec:02d}\""


def _add_column_row(d, x0, y, code, rest, code_col_w, code_size, size, color):
    """Draws `code` (FONT_NAME_BOLD, at `code_size` — a bit larger than the
    rest of the line, see _CODE_SIZE_FACTOR) at x0, and `rest` (FONT_NAME,
    at `size`) at a second, fixed column x0+code_col_w — like a tiny
    2-column table, so a multi-line house's degree/minute text lines up
    in a clean column instead of each line being independently
    re-centered (see the matching comment in
    chart_svg.render_diamond_svg). reportlab's graphics String has no
    rich-text/run concept, so this just places two separate String
    shapes."""
    d.add(String(x0, y, code, fontName=FONT_NAME_BOLD, fontSize=code_size,
                  fillColor=color, textAnchor="start"))
    if rest:
        d.add(String(x0 + code_col_w, y, rest, fontName=FONT_NAME, fontSize=size,
                      fillColor=color, textAnchor="start"))


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

    # planets (and the lagna marker among them) — all styled identically
    # (same size/color/weight pair) regardless of position in the list, so
    # a multi-planet house doesn't have one line standing out from the
    # rest. Each line is (bold_code, regular_rest) laid out as a tiny
    # 2-column table (see _add_column_row) — code left-aligned in its own
    # column at code_size (a bit larger, _CODE_SIZE_FACTOR), degree/minute/
    # retrograde-mark starting from a second, fixed column at the regular
    # `size` — rather than each line independently centered as one string,
    # which left the degree text at a different x per line once codes
    # differed in width (e.g. "လဂ်" vs "၁"). Column widths are measured
    # exactly via pdfmetrics (unlike the web SVG counterpart, which has to
    # estimate).
    # The whole 2-column block is centered on the same pull-biased anchor
    # house_label_anchor already computes — same horizontal footprint as
    # the single centered string this replaces (an earlier version instead
    # grew the block in one direction from the anchor, toward the
    # triangle's open vertex, but that roughly doubles the anchor's old
    # single-line reach; since a crowded house's anchor already sits close
    # to that vertex — always exactly on an internal grid line for a
    # corner triangle — the block overshot into the neighboring cell). No
    # rashi name or house number is drawn any more.
    for h in range(1, 13):
        entry = house_content.get(h) or {}
        planets = entry.get("planets", [])
        n = len(planets)
        pad = box * 0.03

        minx, maxx, miny, maxy = house_bbox(h, box)
        line_h, size, pull = text_layout_for_lines(n, box)
        ax, ay = house_label_anchor(h, box, pull=pull)
        start_y = ay + (n - 1) * line_h / 2.0
        start_y = min(start_y, maxy - pad)
        start_y = max(start_y, miny + pad + max(n - 1, 0) * line_h)

        code_size = size * _CODE_SIZE_FACTOR
        gap = size * 0.08
        code_col_w = max((pdfmetrics.stringWidth(code, FONT_NAME_BOLD, code_size) for code, _ in planets),
                          default=0.0) + gap
        rest_w = max((pdfmetrics.stringWidth(rest, FONT_NAME, size) for _, rest in planets),
                     default=0.0)
        block_w = code_col_w + rest_w
        x0 = ax - block_w / 2.0
        min_y_line = start_y - max(n - 1, 0) * line_h
        diag_lo, diag_hi = diagonal_x0_bounds(h, box, min_y_line, start_y, block_w)
        lo, hi = max(minx + pad, diag_lo), min(maxx - pad - block_w, diag_hi)
        # See the matching comment in chart_svg.render_diamond_svg: a
        # genuinely crowded house can be too wide to fit both this cell's
        # bbox and clear its diagonal — split the difference rather than
        # fully committing to one boundary.
        x0 = max(lo, min(x0, hi)) if lo <= hi else (lo + hi) / 2.0

        for i, (code, rest) in enumerate(planets):
            y = start_y - i * line_h
            _add_column_row(d, x0, flip(y), code, rest, code_col_w, code_size, size, colors.HexColor("#1f2430"))
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
    location_bit = f"{binput.location_name} &nbsp;·&nbsp; " if binput.location_name else ""
    meta = (f"{chart['local_dt'].strftime('%Y-%m-%d')} ({chart['local_dt'].strftime('%a')}) "
            f"{chart['local_dt'].strftime('%H:%M:%S')} "
            f"(UTC{'+' if binput.tz_offset_hours >= 0 else ''}{binput.tz_offset_hours}) &nbsp;·&nbsp; "
            f"{location_bit}"
            f"Lat {_dms(binput.latitude, 'N', 'S')}, Lon {_dms(binput.longitude, 'E', 'W')} &nbsp;·&nbsp; "
            f"Ayanamsa: {binput.ayanamsa} ({_dms_sym(chart['ayanamsa_value'])})")
    story.append(Paragraph(meta, muted))
    story.append(Paragraph(f"လဂ် — <b>{chart['lagna_rashi_mm']}</b> ({_dms_sym(chart['lagna_lon'] % 30)}) &nbsp;·&nbsp; "
                            f"House system: {HOUSE_SYSTEM_LABEL_MAP.get(binput.house_system, binput.house_system)}", muted))
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
    header = ["ဂြိုဟ်", "ရာသီ", "အံသာ", "လိတ္တာ", "တန့်", "ကာရက", "S1", "S2", "S3", "S4", "S5", "S6", "နောက်ဆုံး"]
    rows = [header]
    for name in GRAHA9:
        gp = chart["positions"][name]
        rows.append([
            GRAHA_MM[name], RASHI_MM[gp.rashi_idx - 1], f"{gp.amsa}°", f"{gp.lipta}'", str(gp.house),
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
    story.append(Paragraph("ဝိသောတ္တရီ ဒသာ (Vimshottari Dasha)", h2))
    db = chart["dasha_balance"]
    story.append(Paragraph(f"စောင့်ရင်းဒသာ — <b>{GRAHA_MM[db['lord']]} ဒသာ</b> "
                            f"({db['years']} နှစ် {db['months']} လ {db['days']} ရက်)", body))
    story.append(Spacer(1, 8))
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
