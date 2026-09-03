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
two fonts (both SIL Open Font License — see the matching -LICENSE.txt
next to each .ttf in static/fonts/) and uses them TOGETHER, not as
either/or alternatives:

  - Padauk (FONT_NAME/FONT_NAME_BOLD) is the full-coverage font — every
    digit, Latin letter and punctuation mark this app uses, plus Myanmar
    script. It's what actually renders anything Masterpiece Uni Round
    can't.
  - Masterpiece Uni Round (FONT_NAME_DISPLAY) is the preferred display
    face for Myanmar TEXT specifically (the rounder, more familiar style
    asked for over Padauk alone) — but the font itself has ONLY Myanmar-
    script glyphs, nothing else (not even '°', straight quotes, '®', or
    '·', all used constantly here), so on its own it would draw half of
    every table cell as tofu.

Unlike a browser's CSS font-family list, reportlab has no automatic
per-glyph font fallback of its own — a plain string drawn in one font
just shows .notdef boxes for whatever that font lacks. _font_runs() /
_mixed_markup() do that fallback manually: split text into runs by
whether FONT_NAME_DISPLAY's own cmap (_DISPLAY_FONT_RANGES) covers each
character, and mark each run with its own font. This is applied to every
Paragraph and table cell (see _mixed_markup, _cell_para); the diamond
charts' own text (drawn via reportlab's lower-level Drawing/String
shapes, not Paragraph) deliberately stays Padauk-only instead — see
_add_column_row's docstring for why.
"""
import io
import os
from xml.sax.saxutils import escape as _xml_escape
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
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
FONT_NAME_DISPLAY = None  # set below if the bundled Masterpiece Uni Round registers
_CANDIDATE_FONTS = [
    # Bundled with this project — works out of the box on any machine,
    # regardless of what (if anything) is installed system-wide, so this
    # is the effective default. This is the FULL-COVERAGE font (Myanmar
    # script plus every digit, Latin letter and symbol this app uses) —
    # see FONT_NAME_DISPLAY below for the separate, nicer-looking but
    # Myanmar-only display font layered on top of it.
    os.path.join(_APP_DIR, "static", "fonts", "Padauk-Regular.ttf"),
    "/System/Library/Fonts/Supplemental/Myanmar MN.ttf",     # macOS fallback
    "/System/Library/Fonts/Myanmar.ttc",                      # older macOS
    "/usr/share/fonts/truetype/noto/NotoSansMyanmar-Regular.ttf",  # Linux (Noto)
    "/usr/share/fonts/truetype/padauk/Padauk.ttf",            # Linux (Padauk)
]
_CANDIDATE_FONTS_BOLD = [
    os.path.join(_APP_DIR, "static", "fonts", "Padauk-Bold.ttf"),
    "/usr/share/fonts/truetype/noto/NotoSansMyanmar-Bold.ttf",
    "/usr/share/fonts/truetype/padauk/Padauk-Bold.ttf",
]
_DISPLAY_FONT_PATH = os.path.join(_APP_DIR, "static", "fonts", "MasterpieceUniRound.ttf")

# Which codepoints the bundled Masterpiece Uni Round display font actually
# has glyphs for (from its own cmap — see static/fonts/
# MasterpieceUniRound-LICENSE.txt for provenance): Myanmar script only —
# no Latin letters, digits, or most punctuation at all, not even '°',
# straight quotes, '®', or '·', all used constantly throughout this app.
# Anything outside these ranges must fall back to FONT_NAME/FONT_NAME_BOLD
# (Padauk) instead — see _font_runs()/_mixed_markup(). U+1039 (virama —
# what stacks a conjunct consonant under the one before it, e.g. in
# "အင်္ဂါ"/Mars or "ဗုဒ္ဓဟူး"/Mercury) is deliberately carved out of its
# own (0x1036-0x104F) range even though MUR does have a glyph for it:
# without real shaping, that glyph draws in ISOLATION rather than
# properly stacking — and MUR's isolated form is a large, prominent
# dotted circle, while Padauk's (used here instead) is a small, mostly
# unobtrusive mark, matching what every earlier round of this session
# already verified as an acceptable (if imperfect) rendering for this
# exact "kinzi" limitation.
_DISPLAY_FONT_RANGES = [
    (0x0020, 0x0020), (0x1000, 0x1021), (0x1023, 0x1027), (0x1029, 0x1032),
    (0x1036, 0x1038), (0x103B, 0x104F), (0x200B, 0x200D), (0x2013, 0x2013), (0x23CC, 0x23CC),
    (0x25CC, 0x25CC),
]


def _display_font_covers(ch: str) -> bool:
    cp = ord(ch)
    return any(lo <= cp <= hi for lo, hi in _DISPLAY_FONT_RANGES)


def _register_myanmar_font():
    global FONT_NAME, FONT_NAME_BOLD, FONT_NAME_DISPLAY
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
                break
            except Exception:
                continue
    else:
        # No true bold face found for whichever font matched above — reuse
        # the regular one rather than silently falling back to
        # Helvetica-Bold (which would render Myanmar text as boxes again).
        FONT_NAME_BOLD = FONT_NAME

    if os.path.exists(_DISPLAY_FONT_PATH):
        try:
            pdfmetrics.registerFont(TTFont("MasterpieceUniRound", _DISPLAY_FONT_PATH))
            FONT_NAME_DISPLAY = "MasterpieceUniRound"
        except Exception:
            pass


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


_MM_MEDIALS = "ျြွှ"   # ျြွှ — medial ya/ra/wa/ha
_MM_E_VOWEL = "ေ"                      # ေ
_MM_LO, _MM_HI = 0x1000, 0x109F             # Myanmar Unicode block


def _reorder_myanmar(text: str) -> str:
    """Move each Myanmar pre-base vowel sign 'ေ' (U+1031) to just before
    the base consonant it modifies (skipping back over any medial
    consonant signs — ျြွှ — sitting between that consonant and the
    vowel). Myanmar text is stored in logical order (consonant, then any
    medials, then this vowel), but the vowel is drawn to the LEFT of
    that whole cluster — a font-shaping rule applied by a real text
    shaping engine (HarfBuzz, used by browsers) but never by reportlab,
    which only ever draws a Unicode string's characters one at a time,
    left to right, in raw storage order. Without this, "မေထုန်" (Gemini)
    would draw with 'ေ' stuck after the whole word instead of before its
    first letter — exactly the "Myanmar rendering still isn't right" bug
    reported after every other PDF fix.

    This is a deliberately narrow, dependency-free fix for the single
    most visually-breaking Myanmar shaping rule, verified against real
    HarfBuzz shaping output for every Myanmar string this app actually
    uses (see session notes) — not a general Myanmar text shaper. It
    does NOT reproduce two rarer effects real shaping also applies: the
    "kinzi" mark (a killed-nga+virama cluster rendered as a small
    superscript on the FOLLOWING consonant, e.g. in "တနင်္ဂနွေ"/Sunday)
    and conjunct ligatures (e.g. "ဇေဋ္ဌ"/Jyeshtha's stacked ဋ္ဌ) — both
    need real glyph substitution/positioning reportlab has no access to.
    Both remain readable in plain sequential form; only this vowel's
    position was actually breaking legibility.

    Safe to call on ANY string, not just pure Myanmar ones: strings with
    no 'ေ' are returned unchanged (the common case, cheaply short-
    circuited), and even a string mixing Myanmar with HTML-ish markup
    (reportlab's Paragraph markup, e.g. "<b>...") or Latin text is left
    alone at any point where the character immediately before 'ေ' isn't
    itself Myanmar — it only ever reaches back past medials plus exactly
    one base-consonant character, never past a tag or a space."""
    if _MM_E_VOWEL not in text:
        return text
    out = []
    for ch in text:
        if ch == _MM_E_VOWEL:
            j = len(out)
            while j > 0 and out[j - 1] in _MM_MEDIALS:
                j -= 1
            if j > 0 and _MM_LO <= ord(out[j - 1]) <= _MM_HI:
                j -= 1
            out.insert(j, ch)
        else:
            out.append(ch)
    return "".join(out)


def _font_runs(text: str, default_font: str):
    """Split `text` into (font_name, substring) runs: FONT_NAME_DISPLAY
    (Masterpiece Uni Round) for characters it actually covers, else
    `default_font`. When the caller asked for bold (default_font is
    FONT_NAME_BOLD), the display font is skipped entirely and every
    character goes through `default_font` instead — Masterpiece Uni
    Round has no bold face of its own, and silently keeping it at
    regular weight would defeat the point of asking for bold (the lagna
    rashi name, a dasha lord's name, …), so those short bold values fall
    back to Padauk-Bold instead of losing their emphasis."""
    if not FONT_NAME_DISPLAY or not text or default_font == FONT_NAME_BOLD:
        return [(default_font, text)] if text else []
    runs = []
    cur_font, cur_chars = None, []
    for ch in text:
        want = FONT_NAME_DISPLAY if _display_font_covers(ch) else default_font
        if want != cur_font:
            if cur_chars:
                runs.append((cur_font, "".join(cur_chars)))
            cur_font, cur_chars = want, [ch]
        else:
            cur_chars.append(ch)
    if cur_chars:
        runs.append((cur_font, "".join(cur_chars)))
    return runs


def _mixed_markup(text: str, default_font: str) -> str:
    """Reportlab Paragraph markup for one plain-text VALUE (never a
    string that already has markup of its own baked in — see below):
    _reorder_myanmar()'d for correct vowel position, XML-escaped (this
    wraps free-typed values too, e.g. binput.name/location_name, not
    just this app's own fixed Myanmar vocabulary), with each run (see
    _font_runs) wrapped in its own <font face="..."> tag so a Paragraph
    using `default_font` as its base style renders Myanmar script in the
    nicer Masterpiece Uni Round face wherever that font actually has the
    glyph, and everything else (digits, Latin, punctuation, and any
    Myanmar character it doesn't have) in `default_font` (Padauk),
    unaffected.

    Callers that build their OWN markup around an interpolated value
    (<b>, &nbsp;, …) must apply this to each VALUE individually, before
    composing the final string with that literal markup — never to an
    already-markup-bearing string as a whole, which would both
    double-escape the existing tags and risk mis-wrapping a tag
    delimiter that happens to sit next to a Myanmar run."""
    text = _reorder_myanmar(text)
    return "".join(f'<font face="{font}">{_xml_escape(chunk)}</font>'
                    for font, chunk in _font_runs(text, default_font))


def _P(text: str, style) -> Paragraph:
    """Paragraph() for a plain string with no markup of its own —
    _mixed_markup applied against the style's own base font."""
    return Paragraph(_mixed_markup(text, style.fontName), style)


def _cell_para(text, font_size: float, color=None) -> Paragraph:
    """One Table cell's content as a Paragraph (needed so _mixed_markup's
    <font> tags are actually interpreted rather than shown as literal
    text — a plain-string cell doesn't parse markup at all) — centered
    via its own ParagraphStyle, since Table's ALIGN style command has no
    effect on a Paragraph cell's internal text alignment; likewise
    `color` (used for the header row) since TableStyle's TEXTCOLOR
    command doesn't reach inside a Paragraph either."""
    style = ParagraphStyle("cell", fontName=FONT_NAME, fontSize=font_size,
                            leading=font_size * 1.25, alignment=TA_CENTER,
                            textColor=color or colors.black)
    return Paragraph(_mixed_markup(str(text), FONT_NAME), style)


def _mixed_rows(rows, font_size: float):
    """Convert a Table's 2D row list (plain strings) into _cell_para
    Paragraph cells, row 0 (the header) styled in the same purple
    TableStyle's own TEXTCOLOR command would have used on a plain-string
    cell — see _cell_para for why that command alone isn't enough once
    cells are Paragraphs."""
    header_color = colors.HexColor("#4f33cc")
    return [[_cell_para(cell, font_size, color=(header_color if r == 0 else None))
             for cell in row] for r, row in enumerate(rows)]


def _add_column_row(d, x0, y, code, rest, code_col_w, code_size, size, color):
    """Draws `code` (FONT_NAME_BOLD, at `code_size` — a bit larger than the
    rest of the line, see _CODE_SIZE_FACTOR) at x0, and `rest` (FONT_NAME,
    at `size`) at a second, fixed column x0+code_col_w — like a tiny
    2-column table, so a multi-line house's degree/minute text lines up
    in a clean column instead of each line being independently
    re-centered (see the matching comment in
    chart_svg.render_diamond_svg). reportlab's graphics String has no
    rich-text/run concept, so this just places two separate String
    shapes. Deliberately Padauk-only (FONT_NAME/FONT_NAME_BOLD), not
    Masterpiece-Uni-Round-aware like _mixed_markup: this text's exact
    on-page position is measured via pdfmetrics.stringWidth against
    whichever font actually draws it (see _diamond_drawing) as part of
    keeping a crowded house's text off the diagonal/grid line it sits
    against — swapping fonts mid-computation for just some characters
    would reopen exactly that risk for no real benefit at this font
    size (6-9pt, where the two fonts' style difference barely reads)."""
    d.add(String(x0, y, code, fontName=FONT_NAME_BOLD, fontSize=code_size,
                  fillColor=color, textAnchor="start"))
    if rest:
        d.add(String(x0 + code_col_w, y, rest, fontName=FONT_NAME, fontSize=size,
                      fillColor=color, textAnchor="start"))


def _diamond_drawing(house_content, title, box=260):
    """Builds a reportlab Drawing of the Myanmar-style diamond chart, reusing
    the exact same geometry as the web SVG version (astro/chart_svg.py)."""
    d = Drawing(box, box)

    def flip(y):  # reportlab y-axis grows upward; chart_svg's grows downward
        return box - y

    # chart-type label ("ရာသီ"/"ဘာဝ"/"နဝင်း (D9)") in the unused center
    # cell — same spot chart_svg.render_diamond_svg puts it in on the web,
    # not above the whole diamond (an earlier version of this drawing put
    # it there instead).
    cx, cy, cw, ch = center_box(box)
    d.add(String(cx + cw / 2, flip(cy + ch / 2 + 4), _reorder_myanmar(title),
                  fontName=FONT_NAME_BOLD, fontSize=13 * box / 300.0,
                  fillColor=colors.HexColor("#4f33cc"), textAnchor="middle"))

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
    story.append(_P(f"MOTAA စနစ် ဇာတာ — {binput.name}", h1))
    location_bit = (f"{_mixed_markup(binput.location_name, FONT_NAME)} &nbsp;·&nbsp; "
                     if binput.location_name else "")
    meta = (f"{chart['local_dt'].strftime('%Y-%m-%d')} ({chart['local_dt'].strftime('%a')}) "
            f"{chart['local_dt'].strftime('%H:%M:%S')} "
            f"(UTC{'+' if binput.tz_offset_hours >= 0 else ''}{binput.tz_offset_hours}) &nbsp;·&nbsp; "
            f"{location_bit}"
            f"Lat {_dms(binput.latitude, 'N', 'S')}, Lon {_dms(binput.longitude, 'E', 'W')} &nbsp;·&nbsp; "
            f"Ayanamsa: {binput.ayanamsa} ({_dms_sym(chart['ayanamsa_value'])})")
    story.append(Paragraph(meta, muted))
    lagna_prefix = _mixed_markup("လဂ် — ", FONT_NAME)
    lagna_bold = _mixed_markup(chart['lagna_rashi_mm'], FONT_NAME_BOLD)
    house_sys_label = _mixed_markup(
        HOUSE_SYSTEM_LABEL_MAP.get(binput.house_system, binput.house_system), FONT_NAME)
    story.append(Paragraph(f"{lagna_prefix}{lagna_bold} ({_dms_sym(chart['lagna_lon'] % 30)}) &nbsp;·&nbsp; "
                            f"House system: {house_sys_label}", muted))
    story.append(Spacer(1, 10))

    if diamonds:
        row = [
            [_diamond_drawing(diamonds["rashi"], "ရာသီ", box=145),
             _diamond_drawing(diamonds["bhava"], "ဘာဝ", box=145),
             _diamond_drawing(diamonds["navamsa"], "နဝင်း (D9)", box=145)]
        ]
        dt = Table(row, colWidths=[155, 155, 155])
        dt.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("ALIGN", (0, 0), (-1, -1), "CENTER")]))
        story.append(dt)
        story.append(Spacer(1, 10))

    # --- Nakshatra-wise table ---
    story.append(_P("နက္ခတ်စီး ဇယား", h2))
    nak_header = ["ပြိုလ်", "ဒီဂရီ", "ရာသီ", "ဓာတ်", "နက္ခတ်", "နက္ခတ်သခင်",
                  "မိတ်/ရန်", "ဘာဝသခင်", "နဝင်းသခင်", "နဝင်းမိတ်/ရန်"]
    nak_rows = [nak_header]
    for row in chart["nakshatra_table"]:
        label = "လဂ်" if row.name == "Lagna" else GRAHA_MM[row.name]
        nak_rows.append([
            label, f"{row.amsa}°{row.lipta}'", RASHI_MM[row.rashi_idx - 1],
            f"{row.motion}/{row.element}", f"{row.nakshatra_mm} {row.nakshatra_pada}",
            GRAHA_MM[row.nakshatra_lord], row.friend_enemy, GRAHA_MM[row.bhava_lord],
            GRAHA_MM[row.navamsa_lord], row.navamsa_friend_enemy,
        ])
    tn = Table(_mixed_rows(nak_rows, 7), repeatRows=1)
    tn.setStyle(_table_style(small=True))
    story.append(tn)
    story.append(Spacer(1, 14))

    # --- Planet strength table ---
    story.append(_P("ဂြိုဟ် အင်အား (MOTAA Step 1-6)", h2))
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
    t = Table(_mixed_rows(rows, 8), repeatRows=1)
    t.setStyle(_table_style())
    story.append(t)
    story.append(Spacer(1, 14))

    # --- Bhava influence table ---
    story.append(_P("ဘာဝ လွှမ်းမိုးမှု (BhavaInfluence)", h2))
    header2 = ["တန့်", "ရာသီ", "ပိုင်ရှင်", "သောမ/ပါပ", "ကိုယ်ပိုင် အင်အား", "ဂြိုဟ်ကောင်း", "ဂြိုဟ်ဆိုး", "စုစုပေါင်း"]
    rows2 = [header2]
    for row in chart["bhavas"]:
        rows2.append([
            str(row.house), row.rashi_name, GRAHA_MM[row.lord],
            "ပါပ" if row.karaka == "Papa" else "သောမ",
            _pct(row.own_strength), _pct(row.positive_influence), _pct(row.negative_influence),
            _pct(row.net_influence),
        ])
    t2 = Table(_mixed_rows(rows2, 8), repeatRows=1)
    t2.setStyle(_table_style())
    story.append(t2)
    story.append(PageBreak())

    # --- Dasha ---
    story.append(_P("ဝိသောတ္တရီ ဒသာ (Vimshottari Dasha)", h2))
    db = chart["dasha_balance"]
    balance_prefix = _mixed_markup("စောင့်ရင်းဒသာ — ", FONT_NAME)
    balance_bold = _mixed_markup(f"{GRAHA_MM[db['lord']]} ဒသာ", FONT_NAME_BOLD)
    balance_suffix = _mixed_markup(f" ({db['years']} နှစ် {db['months']} လ {db['days']} ရက်)", FONT_NAME)
    story.append(Paragraph(f"{balance_prefix}{balance_bold}{balance_suffix}", body))
    story.append(Spacer(1, 8))
    header3 = ["မဟာဒသာ", "အစ", "အဆုံး", "နှစ်ပေါင်း"]
    rows3 = [header3]
    for md in chart["dasha_sequence"]:
        rows3.append([GRAHA_MM[md.lord], md.start.strftime("%Y-%m-%d"),
                      md.end.strftime("%Y-%m-%d"), f"{md.years:.2f}"])
    t3 = Table(_mixed_rows(rows3, 8), repeatRows=1)
    t3.setStyle(_table_style())
    story.append(t3)
    story.append(Spacer(1, 12))

    for md in chart["dasha_sequence"][:3]:
        story.append(_P(f"{GRAHA_MM[md.lord]} မဟာဒသာ ({md.start.strftime('%Y-%m-%d')} – {md.end.strftime('%Y-%m-%d')}) ၏ အန္တရများ", body))
        arows = [["အန္တရ", "အစ", "အဆုံး"]]
        for ad in md.antardashas:
            arows.append([GRAHA_MM[ad.lord], ad.start.strftime("%Y-%m-%d"), ad.end.strftime("%Y-%m-%d")])
        ta = Table(_mixed_rows(arows, 7), repeatRows=1)
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
