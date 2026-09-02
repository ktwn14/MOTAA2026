# -*- coding: utf-8 -*-
"""
Builds one complete chart (ephemeris + MOTAA analysis + Vimshottari dasha)
from a birth-data input dict. This is the single function app.py calls.
"""
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional

from . import ephemeris
from . import motaa
from . import dasha
from .constants import (GRAHA9, GRAHA_MM, GRAHA_SHORT, RASHI_MM,
                         OUTER_PLANETS, OUTER_PLANET_SHORT, LAGNA_SHORT)


@dataclass
class BirthInput:
    name: str
    year: int
    month: int
    day: int
    hour: int
    minute: int
    second: int = 0
    tz_offset_hours: float = 6.5     # Myanmar Standard Time default
    latitude: float = 16.8409        # Yangon default
    longitude: float = 96.1735
    ayanamsa: str = "lahiri"
    node_mode: str = "mean"          # "mean" or "true"
    house_system: str = "bhava_madhya"
    location_name: str = ""          # free-text birthplace name, display only


def build_chart(binput: BirthInput):
    local_dt = datetime(binput.year, binput.month, binput.day,
                         binput.hour, binput.minute, binput.second)

    eph = ephemeris.compute_chart_longitudes(
        local_dt, binput.tz_offset_hours, binput.latitude, binput.longitude,
        ayanamsa=binput.ayanamsa, node_mode=binput.node_mode, hsys=binput.house_system,
    )
    grahas = eph["grahas"]
    lagna_lon = eph["lagna"]
    cusps = eph["cusps"]
    outer_grahas, outer_retrograde = ephemeris.outer_planet_data(eph["jd_ut"])
    retrograde = {**eph["retrograde"], **outer_retrograde}

    positions, bhavas, rashi_matrix, house_matrix = motaa.compute_all(grahas, lagna_lon, cusps)

    seq = dasha.compute_vimshottari(grahas["Moon"], local_dt, span_years=120)
    md, ad = dasha.dasha_running_at(seq, datetime.now())

    lagna_rashi_idx = motaa.rashi_index(lagna_lon)

    # --- Navamsa (D9) positions, for the third chart display ---
    navamsa_lagna_idx = motaa.navamsa_rashi_index(lagna_lon)
    navamsa_grahas = {name: motaa.navamsa_rashi_index(lon) for name, lon in grahas.items()}

    return {
        "input": binput,
        "local_dt": local_dt,
        "jd_ut": eph["jd_ut"],
        "ayanamsa_value": eph["ayanamsa_value"],
        "lagna_lon": lagna_lon,
        "lagna_rashi_idx": lagna_rashi_idx,
        "lagna_rashi_mm": RASHI_MM[lagna_rashi_idx - 1],
        "cusps": cusps,
        "grahas": grahas,
        "outer_grahas": outer_grahas,
        "retrograde": retrograde,
        "positions": positions,
        "bhavas": bhavas,
        "dasha_sequence": seq,
        "dasha_now": {"maha": md, "antar": ad},
        "navamsa_lagna_idx": navamsa_lagna_idx,
        "navamsa_grahas": navamsa_grahas,
    }


def _empty_slots():
    return {h: {"rashi": "", "lagna": False, "planets": []} for h in range(1, 13)}


RETROGRADE_MARK = "®️"


def _format_entry(code: str, lon: float, retro: bool, with_degree: bool):
    """Returns (bold_part, regular_part): bold_part is just the graha/
    lagna code (e.g. "၄", "လဂ်"); regular_part is everything else —
    degree/minute (Rashi chart only — that's the only chart with room,
    and reason, to show exactly where in the sign a planet sits, not
    just which sign) plus the retrograde mark, shown everywhere a planet
    can actually be retrograde. Callers render the two parts at
    different font weights (see chart_svg.render_diamond_svg)."""
    regular = ""
    if with_degree:
        amsa, lipta = motaa.amsa_lipta(lon)
        regular = f" {amsa}°{lipta}'"
    if retro:
        regular += f" {RETROGRADE_MARK}"
    return code, regular


def _fill_sorted(content: dict, buckets: dict, retrograde: dict, with_degree: bool):
    """buckets: {grid_pos: [(lon, code, name), ...]}. Sorts each grid
    slot's entries by degree-within-sign ascending (so a 2+ planet house
    always reads low-to-high, not in whatever order they happened to be
    computed in) and appends the formatted (bold_part, regular_part)
    tuple to content[grid_pos]["planets"]."""
    for grid_pos, entries in buckets.items():
        for lon, code, name in sorted(entries, key=lambda e: e[0] % 30.0):
            content[grid_pos]["planets"].append(
                _format_entry(code, lon, retrograde.get(name, False), with_degree))


def build_diamond_chart_data(chart: dict):
    """Prepares house_content dicts for the 3 diamond-chart displays
    (Rashi / Bhava / Navamsa), each as {house_number: {"rashi": name,
    "lagna": bool, "planets": [(bold_code, regular_rest), ...]}} — see
    astro/chart_svg.py's render_diamond_svg for how this is drawn (each
    tuple as one line, code in bold, the rest — degree/minute and/or a
    retrograde mark — in a lighter weight). Planets use their short
    numeral code (GRAHA_SHORT), not the full GRAHA_MM name, to leave room
    in these small cells; the outer planets (Uranus/Neptune/Pluto) are
    added as plain reference points (short code "U"/"N"/"P" only — no
    MOTAA strength/dasha math applies to them)."""
    positions = chart["positions"]
    bhavas = chart["bhavas"]
    cusps = chart["cusps"]
    outer_grahas = chart["outer_grahas"]
    retrograde = chart["retrograde"]
    lagna_rashi_idx = chart["lagna_rashi_idx"]
    lagna_lon = chart["lagna_lon"]

    # --- Rashi chart: FIXED rashi positions (Mesha/Aries always at the
    # top-middle grid slot, then Vrishabha/Taurus, Mithuna/Gemini, ... going
    # around) — this shows each planet in its own natural sign, independent
    # of the lagna, unlike the Bhava chart below (which is lagna/house-
    # system relative). The lagna itself is just a marker on whichever grid
    # slot its own rashi falls in.
    rashi_content = _empty_slots()
    rashi_buckets = {h: [] for h in range(1, 13)}
    for h in range(1, 13):
        rashi_content[h]["rashi"] = RASHI_MM[h - 1]
    for name in GRAHA9:
        gp = positions[name]
        rashi_buckets[gp.rashi_idx].append((gp.lon, GRAHA_SHORT[name], name))
    for name in OUTER_PLANETS:
        lon = outer_grahas[name]
        rashi_buckets[motaa.rashi_index(lon)].append((lon, OUTER_PLANET_SHORT[name], name))
    _fill_sorted(rashi_content, rashi_buckets, retrograde, with_degree=True)
    rashi_content[lagna_rashi_idx]["planets"].insert(
        0, _format_entry(LAGNA_SHORT, lagna_lon, False, with_degree=True))
    rashi_content[lagna_rashi_idx]["lagna"] = True

    # --- Bhava chart: same fixed-rashi grid as the Rashi chart above (the
    # rashi wheel itself never moves — Mesha/Aries is always the top-middle
    # slot) but each planet is grouped by its *house* under the chosen
    # house system (bhavas[gp.house - 1].rashi_idx — the fixed slot that
    # house currently occupies, which shifts around the wheel with the
    # lagna).
    bhava_content = _empty_slots()
    bhava_buckets = {h: [] for h in range(1, 13)}
    for h in range(1, 13):
        bhava_content[h]["rashi"] = RASHI_MM[h - 1]
    for name in GRAHA9:
        gp = positions[name]
        grid_pos = bhavas[gp.house - 1].rashi_idx
        bhava_buckets[grid_pos].append((gp.lon, GRAHA_SHORT[name], name))
    for name in OUTER_PLANETS:
        lon = outer_grahas[name]
        house = motaa.bhava_of(lon, cusps)
        grid_pos = bhavas[house - 1].rashi_idx
        bhava_buckets[grid_pos].append((lon, OUTER_PLANET_SHORT[name], name))
    _fill_sorted(bhava_content, bhava_buckets, retrograde, with_degree=False)
    bhava_content[lagna_rashi_idx]["planets"].insert(0, (LAGNA_SHORT, ""))
    bhava_content[lagna_rashi_idx]["lagna"] = True

    # --- Navamsa (D9) chart: same fixed-rashi convention as the Rashi
    # chart above (Mesha/Aries always at the top-middle grid slot) ---
    nav_lagna_idx = chart["navamsa_lagna_idx"]
    nav_content = _empty_slots()
    nav_buckets = {h: [] for h in range(1, 13)}
    for h in range(1, 13):
        nav_content[h]["rashi"] = RASHI_MM[h - 1]
    for name in GRAHA9:
        lon = chart["grahas"][name]
        nav_idx = chart["navamsa_grahas"][name]
        nav_buckets[nav_idx].append((lon, GRAHA_SHORT[name], name))
    for name in OUTER_PLANETS:
        lon = outer_grahas[name]
        nav_idx = motaa.navamsa_rashi_index(lon)
        nav_buckets[nav_idx].append((lon, OUTER_PLANET_SHORT[name], name))
    _fill_sorted(nav_content, nav_buckets, retrograde, with_degree=False)
    nav_content[nav_lagna_idx]["planets"].insert(0, (LAGNA_SHORT, ""))
    nav_content[nav_lagna_idx]["lagna"] = True

    return {"rashi": rashi_content, "bhava": bhava_content, "navamsa": nav_content}
