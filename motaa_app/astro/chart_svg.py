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

    # --- top-left corner (0,0): diagonal TL-BR ("\"), houses 2 & 3 ---
    tl, tr, br, bl = cell(0, 0)
    polys[2] = [tl, tr, br]               # touches TOP+RIGHT edge (shares w/ H1)
    polys[3] = [tl, bl, br]               # touches LEFT+BOTTOM edge (shares w/ H4)

    # --- bottom-left corner (0,2): diagonal TL-BR ("\"), houses 5 & 6 ---
    tl, tr, br, bl = cell(0, 2)
    polys[5] = [tl, tr, br]               # touches TOP+RIGHT (shares w/ H4 above)
    polys[6] = [tl, bl, br]               # outer tip (touches LEFT+BOTTOM)

    # --- bottom-right corner (2,2): diagonal BL-TR ("/"), houses 8 & 9 ---
    tl, tr, br, bl = cell(2, 2)
    polys[8] = [tl, tr, bl]               # touches TOP+LEFT (shares w/ H7)
    polys[9] = [tr, br, bl]               # outer tip (touches RIGHT+BOTTOM)

    # --- top-right corner (2,0): diagonal BL-TR ("/"), houses 11 & 12 ---
    tl, tr, br, bl = cell(2, 0)
    polys[11] = [tr, br, bl]              # touches RIGHT+BOTTOM (shares w/ H10 below)
    polys[12] = [tl, tr, bl]              # touches TOP+LEFT (shares w/ H1)

    return polys


def house_label_anchor(house: int, box: float = 300.0) -> Point:
    """A reasonable point to place text for a house. For the 4 plain
    (rectangular) Kendra houses this is the simple centroid. For the 8
    triangular corner houses, the centroid is pulled slightly toward the
    polygon's own "outer" vertex (the one furthest from the box center) so
    multi-line text clears the diagonal divider line."""
    poly = house_polygons(box)[house]
    cx = sum(p[0] for p in poly) / len(poly)
    cy = sum(p[1] for p in poly) / len(poly)
    if len(poly) == 3:
        bx, by = box / 2.0, box / 2.0
        outer = max(poly, key=lambda p: (p[0] - bx) ** 2 + (p[1] - by) ** 2)
        cx = cx * 0.68 + outer[0] * 0.32
        cy = cy * 0.68 + outer[1] * 0.32
    return cx, cy


def center_box(box: float = 300.0):
    u = box / 3.0
    return (u, u, u, u)  # x, y, width, height of the unused center cell


def polygon_to_svg_points(poly: List[Point]) -> str:
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in poly)


def render_diamond_svg(house_content: Dict[int, List[str]], center_title: str = "",
                        center_sub: str = "", box: float = 300.0,
                        font_family: str = "'Masterpiece Uni Round','Myanmar Text',sans-serif") -> str:
    """
    house_content: {house_number: [line1, line2, ...]} — short text lines
    (e.g. rashi name, then planet abbreviations) to place in each house.
    Returns a standalone <svg>...</svg> string.
    """
    polys = house_polygons(box)
    parts = [f'<svg viewBox="0 0 {box} {box}" xmlns="http://www.w3.org/2000/svg" '
              f'style="font-family:{font_family};max-width:100%;height:auto;">']
    parts.append(f'<rect x="0" y="0" width="{box}" height="{box}" '
                  f'fill="#fffdf7" stroke="#2b2b2b" stroke-width="2"/>')

    # grid + diagonal lines
    u = box / 3.0
    lines = [
        (u, 0, u, box), (2 * u, 0, 2 * u, box),          # verticals
        (0, u, box, u), (0, 2 * u, box, 2 * u),           # horizontals
        (0, 0, u, u),                                      # TL corner diagonal \
        (0, 2 * u, u, 3 * u),                              # BL corner diagonal \
        (2 * u, 2 * u, 3 * u, 3 * u),                       # BR corner diagonal / (part1)
        (3 * u, 2 * u, 2 * u, 3 * u),                       # BR corner diagonal / (part2, drawn as line too)
        (2 * u, u, 3 * u, 0),                               # TR corner diagonal /
    ]
    # simpler: draw exact diagonals matching house_polygons()
    diag_lines = [
        (0, 0, u, u),                 # TL: \
        (0, 2 * u, u, 3 * u),         # BL: \
        (2 * u, 3 * u, 3 * u, 2 * u),  # BR: /
        (2 * u, 0, 3 * u, u),          # TR: /
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

    # house numbers + content
    for h in range(1, 13):
        poly = polys[h]
        anchor_x, anchor_y = house_label_anchor(h, box)
        # house number, small, near the outer-most vertex of the polygon
        num_x, num_y = _outer_label_point(h, poly, box)
        parts.append(f'<text x="{num_x:.1f}" y="{num_y:.1f}" font-size="9" fill="#9ca3af">{h}</text>')

        lines = house_content.get(h, [])
        n = len(lines)
        start_y = anchor_y - (n - 1) * 6.5
        for i, line in enumerate(lines):
            y = start_y + i * 13
            weight = "700" if i == 0 else "500"
            size = 11 if i == 0 else 9.5
            color = "#4f33cc" if i == 0 else "#1f2430"
            parts.append(f'<text x="{anchor_x:.1f}" y="{y:.1f}" text-anchor="middle" '
                          f'font-size="{size}" font-weight="{weight}" fill="{color}">{_esc(line)}</text>')

    parts.append("</svg>")
    return "".join(parts)


def _outer_label_point(house: int, poly: List[Point], box: float) -> Point:
    """Small house-number placed near whichever polygon vertex is furthest
    from the box center (i.e. the outer corner/edge of the chart)."""
    cx = cy = box / 2.0
    best = max(poly, key=lambda p: (p[0] - cx) ** 2 + (p[1] - cy) ** 2)
    # nudge slightly inward so the digit isn't clipped by the border
    nx = best[0] + (cx - best[0]) * 0.12
    ny = best[1] + (cy - best[1]) * 0.12
    return nx, ny


def _esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
