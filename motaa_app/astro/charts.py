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
    outer_grahas = ephemeris.outer_planet_positions(eph["jd_ut"])

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
        "positions": positions,
        "bhavas": bhavas,
        "dasha_sequence": seq,
        "dasha_now": {"maha": md, "antar": ad},
        "navamsa_lagna_idx": navamsa_lagna_idx,
        "navamsa_grahas": navamsa_grahas,
    }


def _empty_slots():
    return {h: {"rashi": "", "lagna": False, "planets": []} for h in range(1, 13)}


def _amsa_lipta_tag(code: str, lon: float) -> str:
    """"<code> <degree>°<minute>'" — used only on the Rashi chart, where
    there's room (and reason) to show exactly where in the sign a planet
    sits, not just which sign."""
    amsa, lipta = motaa.amsa_lipta(lon)
    return f"{code} {amsa}°{lipta}'"


def build_diamond_chart_data(chart: dict):
    """Prepares house_content dicts for the 3 diamond-chart displays
    (Rashi / Bhava / Navamsa), each as {house_number: {"rashi": name,
    "lagna": bool, "planets": [name, ...]}} — see astro/chart_svg.py's
    render_diamond_svg for how this is drawn (rashi name small in the
    slot's corner, planets large and centered). Planets use their short
    numeral code (GRAHA_SHORT), not the full GRAHA_MM name, to leave room
    in these small cells; the outer planets (Uranus/Neptune/Pluto) are
    added as plain reference points (short code "U"/"N"/"P" only — no
    MOTAA strength/dasha math applies to them)."""
    positions = chart["positions"]
    bhavas = chart["bhavas"]
    cusps = chart["cusps"]
    outer_grahas = chart["outer_grahas"]
    lagna_rashi_idx = chart["lagna_rashi_idx"]
    lagna_lon = chart["lagna_lon"]

    # --- Rashi chart: FIXED rashi positions (Mesha/Aries always at the
    # top-middle grid slot, then Vrishabha/Taurus, Mithuna/Gemini, ... going
    # around) — this shows each planet in its own natural sign, independent
    # of the lagna, unlike the Bhava chart below (which is lagna/house-
    # system relative). The lagna itself is just a marker on whichever grid
    # slot its own rashi falls in.
    rashi_content = _empty_slots()
    for h in range(1, 13):
        rashi_content[h]["rashi"] = RASHI_MM[h - 1]
    for name in GRAHA9:
        gp = positions[name]
        rashi_content[gp.rashi_idx]["planets"].append(_amsa_lipta_tag(GRAHA_SHORT[name], gp.lon))
    for name in OUTER_PLANETS:
        lon = outer_grahas[name]
        rashi_content[motaa.rashi_index(lon)]["planets"].append(
            _amsa_lipta_tag(OUTER_PLANET_SHORT[name], lon))
    rashi_content[lagna_rashi_idx]["planets"].insert(0, _amsa_lipta_tag(LAGNA_SHORT, lagna_lon))
    rashi_content[lagna_rashi_idx]["lagna"] = True

    # --- Bhava chart: same fixed-rashi grid as the Rashi chart above (the
    # rashi wheel itself never moves — Mesha/Aries is always the top-middle
    # slot) but each planet is grouped by its *house* under the chosen
    # house system (bhavas[gp.house - 1].rashi_idx — the fixed slot that
    # house currently occupies, which shifts around the wheel with the
    # lagna).
    bhava_content = _empty_slots()
    for h in range(1, 13):
        bhava_content[h]["rashi"] = RASHI_MM[h - 1]
    for name in GRAHA9:
        gp = positions[name]
        grid_pos = bhavas[gp.house - 1].rashi_idx
        bhava_content[grid_pos]["planets"].append(GRAHA_SHORT[name])
    for name in OUTER_PLANETS:
        lon = outer_grahas[name]
        house = motaa.bhava_of(lon, cusps)
        grid_pos = bhavas[house - 1].rashi_idx
        bhava_content[grid_pos]["planets"].append(OUTER_PLANET_SHORT[name])
    bhava_content[lagna_rashi_idx]["planets"].insert(0, LAGNA_SHORT)
    bhava_content[lagna_rashi_idx]["lagna"] = True

    # --- Navamsa (D9) chart: same fixed-rashi convention as the Rashi
    # chart above (Mesha/Aries always at the top-middle grid slot) ---
    nav_lagna_idx = chart["navamsa_lagna_idx"]
    nav_content = _empty_slots()
    for h in range(1, 13):
        nav_content[h]["rashi"] = RASHI_MM[h - 1]
    for name in GRAHA9:
        nav_idx = chart["navamsa_grahas"][name]
        nav_content[nav_idx]["planets"].append(GRAHA_SHORT[name])
    for name in OUTER_PLANETS:
        nav_idx = motaa.navamsa_rashi_index(outer_grahas[name])
        nav_content[nav_idx]["planets"].append(OUTER_PLANET_SHORT[name])
    nav_content[nav_lagna_idx]["planets"].insert(0, LAGNA_SHORT)
    nav_content[nav_lagna_idx]["lagna"] = True

    return {"rashi": rashi_content, "bhava": bhava_content, "navamsa": nav_content}
