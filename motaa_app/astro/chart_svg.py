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


def text_layout_for_lines(n: int, box: float = 300.0) -> Tuple[float, float, float, float]:
    """Line-height, head font-size, body font-size, and anchor `pull` for a
    house whose text block has `n` lines, scaled to `box`. Houses with more
    planets stacked in them get smaller/tighter text *and* a stronger pull
    toward their triangle's outer vertex, so the block both shrinks and
    leans away from the shared diagonal instead of overrunning it (the
    fixed-size, symmetric-growth layout this replaces let 3+ planet houses
    overlap their neighbor's text, or spill past the chart's own border)."""
    scale = box / 300.0
    if n <= 2:
        line_h, size_head, size_body, pull = 13.0, 11.0, 9.5, 0.32
    elif n == 3:
        line_h, size_head, size_body, pull = 10.5, 10.0, 8.5, 0.44
    elif n == 4:
        line_h, size_head, size_body, pull = 9.0, 9.5, 7.5, 0.54
    else:
        line_h, size_head, size_body, pull = 7.5, 9.0, 6.5, 0.60
    return line_h * scale, size_head * scale, size_body * scale, pull


def center_box(box: float = 300.0):
    u = box / 3.0
    return (u, u, u, u)  # x, y, width, height of the unused center cell


def polygon_to_svg_points(poly: List[Point]) -> str:
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in poly)


def render_diamond_svg(house_content: Dict[int, dict], center_title: str = "",
                        center_sub: str = "", box: float = 300.0,
                        font_family: str = "'Masterpiece Uni Round','Myanmar Text',sans-serif",
                        position_labels: Dict[int, str] = None) -> str:
    """
    house_content: {grid_position: {"rashi": str, "lagna": bool,
    "planets": [name, ...]}} for each of the 12 fixed grid slots (1 =
    top-middle, going counter-clockwise). The rashi name is drawn small,
    tucked into the slot's own outer corner (alongside its number/house
    label) so it reads as a reference tag rather than competing with the
    planet names, which get the slot's full center and are what the eye
    should land on first.
    position_labels: optional {grid_position: label} for the small number
    in that same corner. Defaults to the grid position itself (1-12) —
    pass this to show something else instead, e.g. each slot's *house*
    number in a Bhava chart, which (unlike the slot's rashi) moves around
    the fixed grid depending on where the lagna falls.
    Returns a standalone <svg>...</svg> string.
    """
    position_labels = position_labels or {}
    polys = house_polygons(box)
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

    # center label
    cx, cy, cw, ch = center_box(box)
    parts.append(f'<text x="{cx + cw/2:.1f}" y="{cy + ch/2 - 4:.1f}" text-anchor="middle" '
                  f'font-size="13" font-weight="700" fill="#4f33cc">{_esc(center_title)}</text>')
    if center_sub:
        parts.append(f'<text x="{cx + cw/2:.1f}" y="{cy + ch/2 + 14:.1f}" text-anchor="middle" '
                      f'font-size="10" fill="#6b7280">{_esc(center_sub)}</text>')

    # house numbers + rashi tag (small, corner) + planets (large, centered)
    for h in range(1, 13):
        poly = polys[h]
        entry = house_content.get(h) or {}
        planets = entry.get("planets", [])
        rashi = entry.get("rashi", "")
        is_lagna = bool(entry.get("lagna"))
        n = len(planets)
        pad = box * 0.03

        # --- planets: the main, centered content ---
        line_h, size_head, size_body, pull = text_layout_for_lines(n, box)
        anchor_x, anchor_y = house_label_anchor(h, box, pull=pull)
        start_y = anchor_y - (n - 1) * line_h / 2.0
        start_y = max(pad, min(start_y, box - pad - max(n - 1, 0) * line_h))
        for i, name in enumerate(planets):
            y = start_y + i * line_h
            weight = "700" if i == 0 else "500"
            size = size_head if i == 0 else size_body
            color = "#4f33cc" if i == 0 else "#1f2430"
            parts.append(f'<text x="{anchor_x:.1f}" y="{y:.1f}" text-anchor="middle" '
                          f'font-size="{size:.1f}" font-weight="{weight}" fill="{color}">{_esc(name)}</text>')

        # --- small corner tag: number/house label, then the rashi name
        # below it — pull=0.78 keeps it well past the planets' own pull
        # (capped at 0.60 above) so the two never collide even in a
        # crowded house, while staying inside the polygon (unlike the
        # unclamped very-tip point an earlier version used, which let a
        # sibling pair's tags land on literally the same pixel) ---
        tag_x, tag_y = _corner_point(h, poly, box, pull=0.78)
        tag_lines = [str(position_labels.get(h, h)), rashi]
        tag_start_y = max(pad, min(tag_y, box - pad - 9.0))
        for i, t in enumerate(tag_lines):
            y = tag_start_y + i * 9.0
            color = "#7c6fd1" if (i == 1 and is_lagna) else "#9ca3af"
            weight = "700" if (i == 1 and is_lagna) else "400"
            parts.append(f'<text x="{tag_x:.1f}" y="{y:.1f}" text-anchor="middle" '
                          f'font-size="7.5" font-weight="{weight}" fill="{color}">{_esc(t)}</text>')

    parts.append("</svg>")
    return "".join(parts)


def _esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
