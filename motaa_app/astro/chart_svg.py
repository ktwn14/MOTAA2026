# -*- coding: utf-8 -*-
"""
Traditional Myanmar-style ("East Indian"/North-Indian-style) diamond chart
geometry: a square divided into a 3x3 grid, where the 4 corner cells are each
split by one diagonal into 2 triangular houses, the 4 edge-middle cells are
the 4 Kendra houses (1, 4, 7, 10), and the center cell is unused (used here
for a small title/label).

This layout was reverse-engineered and verified against a real Myanmar
astrology app screenshot the user provided (a 3x3 grid with diagonals inside
each corner cell — not the 4x4 "ring" approximation). House numbering runs
counter-clockwise starting at the top-middle cell (House 1), matching
standard North-Indian-chart convention.

Coordinate system: a BOX x BOX square (default 300x300), (0,0) at top-left.
Returns polygons as lists of (x, y) tuples; consumers (SVG string builder in
this module, or reportlab shapes in reports/pdf_report.py) can draw them
however they like.
"""
from dataclasses import dataclass
from typing import Dict, List, Tuple

Point = Tuple[float, float]


def house_polygons(box: float = 300.0) -> Dict[int, List[Point]]:
    u = box / 3.0  # one cell's width/height

    def cell(cx, cy):
        """corners of cell at column cx, row cy (0-indexed): TL,TR,BR,BL"""
        x0, y0 = cx * u, cy * u
        x1, y1 = x0 + u, y0 + u
        return (x0, y0), (x1, y0), (x1, y1), (x0, y1)

    polys: Dict[int, List[Point]] = {}

    # --- 4 Kendra (edge-middle) houses: plain rectangles ---
    tl, tr, br, bl = cell(1, 0)
    polys[1] = [tl, tr, br, bl]           # top-middle
    tl, tr, br, bl = cell(0, 1)
    polys[4] = [tl, tr, br, bl]           # left-middle
    tl, tr, br, bl = cell(1, 2)
    polys[7] = [tl, tr, br, bl]           # bottom-middle
    tl, tr, br, bl = cell(2, 1)
    polys[10] = [tl, tr, br, bl]          # right-middle

    # Every corner cell is split by a *chord of the outer square's own main
    # diagonal* — i.e. the line from that cell's own outer corner (a corner
    # of the whole box) to the inner grid corner nearest the box's center.
    # This makes all 4 corners consistent with each other (and with the
    # box's two real diagonals, (0,0)-(3u,3u) and (3u,0)-(0,3u)) — an
    # earlier version of this function used a different, unrelated chord
    # for 3 of the 4 corners, which drew a diagonal that didn't pass
    # through that corner's own outer tip at all.

    # --- top-left corner (0,0): diagonal (0,0)-(u,u) "\", houses 2 & 3 ---
    tl, tr, br, bl = cell(0, 0)
    polys[2] = [tl, tr, br]               # touches TOP+RIGHT edge (shares w/ H1)
    polys[3] = [tl, bl, br]               # touches LEFT+BOTTOM edge (shares w/ H4)

    # --- bottom-left corner (0,2): diagonal (0,3u)-(u,2u) "/", houses 5 & 6 ---
    tl, tr, br, bl = cell(0, 2)
    polys[5] = [tl, tr, bl]               # touches TOP edge (shares w/ H4 above)
    polys[6] = [tr, br, bl]               # touches RIGHT edge (shares w/ H7)

    # --- bottom-right corner (2,2): diagonal (2u,2u)-(3u,3u) "\", houses 8 & 9 ---
    tl, tr, br, bl = cell(2, 2)
    polys[8] = [tl, bl, br]               # touches LEFT edge (shares w/ H7)
    polys[9] = [tl, tr, br]               # touches TOP edge (shares w/ H10)

    # --- top-right corner (2,0): diagonal (3u,0)-(2u,u) "/", houses 11 & 12 ---
    tl, tr, br, bl = cell(2, 0)
    polys[11] = [tr, br, bl]              # touches BOTTOM edge (shares w/ H10 below)
    polys[12] = [tl, tr, bl]              # touches LEFT edge (shares w/ H1)

    return polys


# Each corner cell holds 2 triangular houses split by one diagonal; these
# are the two houses sharing each diagonal.
_CORNER_SIBLING = {2: 3, 3: 2, 5: 6, 6: 5, 8: 9, 9: 8, 11: 12, 12: 11}


def _outer_vertex(house: int, poly: List[Point], box: float) -> Point:
    """The vertex a house's text should lean toward. For a triangular
    corner house this is the vertex *not* shared with its sibling triangle
    (the other house occupying the same corner cell) — pulling toward
    "whichever vertex is furthest from the box center" (an earlier version
    of this) picks the *same* point — one of the shared diagonal's own
    endpoints — for both siblings, which pulls a crowded house's text
    toward its sibling instead of away from it. For a plain rectangular
    Kendra house there's no sibling to avoid, so the furthest-from-center
    vertex is simply that house's own natural "outer corner"."""
    if len(poly) == 3:
        sibling_poly = house_polygons(box)[_CORNER_SIBLING[house]]
        return next(p for p in poly if p not in sibling_poly)
    cx = cy = box / 2.0
    return max(poly, key=lambda p: (p[0] - cx) ** 2 + (p[1] - cy) ** 2)


def _corner_point(house: int, poly: List[Point], box: float, pull: float) -> Point:
    """Blend of the polygon's centroid and its `_outer_vertex` — 0 = dead
    centroid, 1 = right on that outer vertex."""
    cx = sum(p[0] for p in poly) / len(poly)
    cy = sum(p[1] for p in poly) / len(poly)
    ox, oy = _outer_vertex(house, poly, box)
    return cx * (1 - pull) + ox * pull, cy * (1 - pull) + oy * pull


def house_label_anchor(house: int, box: float = 300.0, pull: float = 0.32) -> Point:
    """A reasonable point to place a house's *planet* text. For the 4 plain
    (rectangular) Kendra houses this is the simple centroid (pull ignored —
    they aren't split by a diagonal, so there's no crowding to lean away
    from). For the 8 triangular corner houses, the centroid is pulled
    toward `_outer_vertex` — `pull` controls how far (0 = centroid, 1 = that
    vertex); callers with a crowded (many-planet) house should pass a
    larger pull so that house's text leans further away from the diagonal
    it shares with its sibling."""
    poly = house_polygons(box)[house]
    if len(poly) != 3:
        return sum(p[0] for p in poly) / len(poly), sum(p[1] for p in poly) / len(poly)
    return _corner_point(house, poly, box, pull)


_UNIFORM_SIZE = 6.5  # at box=300 — see text_layout_for_lines() docstring


def text_layout_for_lines(n: int, box: float = 300.0) -> Tuple[float, float, float]:
    """Line-height, font-size, and anchor `pull` for a house whose text
    block has `n` lines, scaled to `box`. Font *size* is fixed — the same
    for every house regardless of its own planet count — sized so that
    even the crowded (5-planet-or-more) case stays legible; a 1-planet
    house's text isn't drawn bigger than a crowded neighbor's, so the
    chart doesn't read as visually inconsistent from house to house. What
    still varies with `n` is line-height (tighter stacking for more
    lines, so they fit the triangle vertically) and anchor `pull` (a
    crowded house leans harder toward its triangle's outer vertex, so the
    block both shrinks its line spacing and leans away from the shared
    diagonal instead of overrunning it or bleeding into the neighboring
    house's own text)."""
    scale = box / 300.0
    if n <= 2:
        line_h, pull = 9.5, 0.30
    elif n == 3:
        line_h, pull = 8.0, 0.28
    elif n == 4:
        line_h, pull = 7.0, 0.26
    elif n == 5:
        line_h, pull = 6.2, 0.22
    else:
        line_h, pull = 5.4, 0.18
    return line_h * scale, _UNIFORM_SIZE * scale, pull


def _approx_text_width_em(s: str) -> float:
    """Rough visual width of `s`, in units of its own font-size ("em"),
    used only to lay out the two-column (code, degree/minute) planet-text
    blocks below — real glyph metrics aren't available on the Python side
    for an SVG that's rendered by the browser's own font (see
    reports/pdf_report.py for the PDF path, which *can* measure exact
    widths via reportlab). Myanmar glyphs run wider than Latin/digits;
    the invisible emoji variation selector (used after the retrograde
    "®️" mark) has zero visual width and must not be counted."""
    total = 0.0
    for ch in s:
        if ch == "️":
            continue
        elif "က" <= ch <= "႟":
            total += 0.95
        elif ch == " ":
            total += 0.3
        elif ch in "°'\"":
            total += 0.5
        else:
            total += 0.62
    return total


def center_box(box: float = 300.0):
    u = box / 3.0
    return (u, u, u, u)  # x, y, width, height of the unused center cell


def polygon_to_svg_points(poly: List[Point]) -> str:
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in poly)


def render_diamond_svg(house_content: Dict[int, dict], center_label: str = "",
                        box: float = 300.0,
                        font_family: str = "'Masterpiece Uni Round','Myanmar Text',sans-serif") -> str:
    """
    house_content: {grid_position: {"rashi": str, "lagna": bool,
    "planets": [name, ...]}} for each of the 12 fixed grid slots (1 =
    top-middle, going counter-clockwise). Only "planets" is drawn — the
    lagna itself is just an entry in that same list (its own code, e.g.
    "လဂ်"), so no separate marker or styling is needed for it. "rashi" and
    "lagna" are kept in the data (some callers still use them, e.g. to
    pick which grid slot a value belongs on) but not rendered — an
    earlier version drew the rashi name and a grid/house number as a
    small tag in each slot's corner, which read as clutter more than as
    useful reference.
    center_label: short text (e.g. "ရာသီ"/"ဘာဝ"/"နဝင်း (D9)") shown in the
    unused center cell — just the chart type, not the person's name.
    Returns a standalone <svg>...</svg> string.
    """
    parts = [f'<svg viewBox="0 0 {box} {box}" xmlns="http://www.w3.org/2000/svg" '
              f'style="font-family:{font_family};max-width:100%;height:auto;">']
    parts.append(f'<rect x="0" y="0" width="{box}" height="{box}" '
                  f'fill="#fffdf7" stroke="#2b2b2b" stroke-width="2"/>')

    # grid + diagonal lines — each corner's diagonal is the chord of the
    # box's own main diagonal that falls inside that cell (matching
    # house_polygons(); see the comment there for why this is what makes
    # all 4 corners consistent with each other).
    u = box / 3.0
    diag_lines = [
        (0, 0, u, u),                  # TL: (0,0) -> (u,u)
        (0, 3 * u, u, 2 * u),          # BL: (0,3u) -> (u,2u)
        (3 * u, 3 * u, 2 * u, 2 * u),  # BR: (3u,3u) -> (2u,2u)
        (3 * u, 0, 2 * u, u),          # TR: (3u,0) -> (2u,u)
    ]
    for x1, y1, x2, y2 in [(u, 0, u, box), (2 * u, 0, 2 * u, box),
                            (0, u, box, u), (0, 2 * u, box, 2 * u)] + diag_lines:
        parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                      f'stroke="#2b2b2b" stroke-width="1.5"/>')

    # center label — just the chart type (e.g. "ရာသီ"), nothing else
    cx, cy, cw, ch = center_box(box)
    if center_label:
        parts.append(f'<text x="{cx + cw/2:.1f}" y="{cy + ch/2 + 4:.1f}" text-anchor="middle" '
                      f'font-size="13" font-weight="700" fill="#4f33cc">{_esc(center_label)}</text>')

    # planets (and the lagna marker among them) — all styled identically
    # (same size/color) regardless of position in the list, so a
    # multi-planet house doesn't have one line standing out from the rest.
    # Each line is (bold_code, regular_rest): the code drawn bold in its
    # own left-aligned column, the degree/minute/retrograde-mark that
    # follows it drawn at normal weight starting from a second, fixed
    # column — like a tiny 2-column table — instead of each line being
    # independently centered as one string (which, once codes differ in
    # width, e.g. "လဂ်" vs "၁", left the degree text "clumped" at
    # different x per line rather than reading as a clean list). The
    # block's column widths are sized per-house from its own longest code
    # (see _approx_text_width_em); its horizontal position leans the same
    # way house_label_anchor's `pull` already does — toward the triangle's
    # open side, away from the shared diagonal (house_lean) — or, for the
    # 4 plain Kendra houses (no diagonal to avoid), is simply centered. No
    # rashi name or house/grid number is drawn in the house any more —
    # see house_content's own "rashi" field if that's ever needed again.
    for h in range(1, 13):
        entry = house_content.get(h) or {}
        planets = entry.get("planets", [])
        n = len(planets)
        pad = box * 0.03

        line_h, size, pull = text_layout_for_lines(n, box)
        anchor_x, anchor_y = house_label_anchor(h, box, pull=pull)
        start_y = anchor_y - (n - 1) * line_h / 2.0
        start_y = max(pad, min(start_y, box - pad - max(n - 1, 0) * line_h))

        # Two left-aligned columns (code, then degree/minute) within a
        # block that's still *centered* on the pull-biased anchor — same
        # horizontal footprint as the single centered string this
        # replaces, just laid out as a mini 2-column table internally.
        # (An earlier version of this instead grew the whole block in one
        # direction from the anchor — start-aligned toward the triangle's
        # open vertex — but that roughly doubles the anchor's old
        # single-line reach, and for a crowded house the anchor already
        # sits close to that vertex, which for a corner triangle is
        # always exactly on an internal grid line: the block then
        # overshot past it into the neighboring cell.)
        gap_em = 0.4
        code_col_em = max((_approx_text_width_em(code) for code, _ in planets), default=0.0) + gap_em
        code_col_w = size * code_col_em
        rest_w = max((size * _approx_text_width_em(rest) for _, rest in planets), default=0.0)
        block_w = code_col_w + rest_w
        x0 = anchor_x - block_w / 2.0
        x0 = max(pad, min(x0, box - pad - block_w))

        for i, (code, rest) in enumerate(planets):
            y = start_y + i * line_h
            rest_tspan = (f'<tspan x="{x0 + code_col_w:.1f}" font-weight="400">{_esc(rest)}</tspan>'
                          if rest else "")
            parts.append(f'<text y="{y:.1f}" font-size="{size:.1f}" fill="#1f2430">'
                          f'<tspan x="{x0:.1f}" font-weight="700">{_esc(code)}</tspan>'
                          f'{rest_tspan}</text>')

    parts.append("</svg>")
    return "".join(parts)


def _esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
