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
from .constants import GRAHA9, GRAHA_MM, RASHI_MM


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
        "positions": positions,
        "bhavas": bhavas,
        "dasha_sequence": seq,
        "dasha_now": {"maha": md, "antar": ad},
        "navamsa_lagna_idx": navamsa_lagna_idx,
        "navamsa_grahas": navamsa_grahas,
    }


def build_diamond_chart_data(chart: dict):
    """Prepares house_content dicts for the 3 diamond-chart displays
    (Rashi / Bhava / Navamsa), each as {house_number: [line1, line2, ...]}
    with line1 = rashi (sign) name and following lines = planet abbreviations
    placed in that house."""
    from .constants import GRAHA_MM, RASHI_MM

    positions = chart["positions"]
    bhavas = chart["bhavas"]
    lagna_rashi_idx = chart["lagna_rashi_idx"]

    # --- Rashi chart: whole-sign house numbering ---
    rashi_content = {h: [bhavas[h - 1].rashi_name] for h in range(1, 13)}
    for name in GRAHA9:
        gp = positions[name]
        h = motaa.whole_sign_house(gp.rashi_idx, lagna_rashi_idx)
        rashi_content[h].append(GRAHA_MM[name])
    rashi_content[motaa.whole_sign_house(lagna_rashi_idx, lagna_rashi_idx)].insert(0, "(လဂ်)")

    # --- Bhava chart: Bhava-Madhya (or chosen house system) placement ---
    bhava_content = {h: [bhavas[h - 1].rashi_name] for h in range(1, 13)}
    for name in GRAHA9:
        gp = positions[name]
        bhava_content[gp.house].append(GRAHA_MM[name])
    bhava_content[1].insert(0, "(လဂ်)")

    # --- Navamsa (D9) chart: whole-sign from navamsa lagna ---
    nav_lagna_idx = chart["navamsa_lagna_idx"]
    nav_content = {
        h: [RASHI_MM[(nav_lagna_idx - 1 + (h - 1)) % 12]] for h in range(1, 13)
    }
    for name in GRAHA9:
        nav_idx = chart["navamsa_grahas"][name]
        h = motaa.whole_sign_house(nav_idx, nav_lagna_idx)
        nav_content[h].append(GRAHA_MM[name])
    nav_content[1].insert(0, "(လဂ်)")

    return {"rashi": rashi_content, "bhava": bhava_content, "navamsa": nav_content}
