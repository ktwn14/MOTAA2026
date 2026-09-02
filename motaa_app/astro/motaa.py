# -*- coding: utf-8 -*-
"""
MOTAA Astrology Course Level-1 (Lesson 6 & 7) calculations.

This is a direct Python port of the logic built earlier as an Excel workbook,
now working on real ephemeris-derived longitudes instead of manual input.
See README.md for the full list of documented assumptions/simplifications.
"""
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .constants import (RASHI_MM, RASHI_EN, RASHI_LORD, GRAHA7, GRAHA9, GRAHA_MM,
                         FRIENDSHIP, EXALT_DEBIL, COMBUST_ORB, KENDRA_TRIKONA, DUSTHANA)


# ---------------------------------------------------------------------------
# small geometry helpers
# ---------------------------------------------------------------------------
def rashi_index(lon: float) -> int:
    """1..12"""
    return int((lon % 360.0) // 30) + 1


def amsa_lipta(lon: float):
    """Degree (အံသာ, 0-29) and arc-minute (လိတ္တာ, 0-59) within the planet's
    own rashi — e.g. 187.62 deg (7 deg into Vrishabha) -> (7, 37)."""
    deg_in_sign = lon % 30.0
    amsa = int(deg_in_sign)
    lipta = round((deg_in_sign - amsa) * 60.0)
    if lipta == 60:
        lipta = 0
        amsa += 1
        if amsa == 30:
            amsa = 0
    return amsa, lipta


def angular_distance(a: float, b: float) -> float:
    """Minimal angular distance 0..180 between two longitudes."""
    d = abs((a - b) % 360.0)
    return 360.0 - d if d > 180.0 else d


def influence_pct(lon: float, target_deg: float, max_orb: float) -> float:
    """
    Exact orb->influence formula from MOTAA course PDF (Lesson 6, p38 / Lesson 7):
        IF(orb < max_orb, ((1/(sin(radians((90/max_orb)*orb))^2+1))-0.5)*2, 0)
    Returns a value in [0, 1].
    """
    orb = angular_distance(lon, target_deg)
    if orb >= max_orb:
        return 0.0
    angle = math.radians((90.0 / max_orb) * orb)
    return ((1.0 / (math.sin(angle) ** 2 + 1.0)) - 0.5) * 2.0


def bhava_of(lon: float, cusps: List[float]) -> int:
    """Generalized house lookup: given 12 cusp-START longitudes (in zodiacal
    order, cusps[i] = start of house i+1), find which house `lon` falls in.
    Works for equal *and* unequal (Placidus/Koch/...) house systems."""
    n = len(cusps)
    for i in range(n):
        start = cusps[i]
        end = cusps[(i + 1) % n]
        width = (end - start) % 360.0
        if width == 0:
            width = 360.0
        offset = (lon - start) % 360.0
        if offset < width:
            return i + 1
    return 12  # fallback, should not normally be reached


def house_madhya_and_width(house: int, cusps: List[float]):
    """Midpoint longitude and angular width (deg) of a house, from its cusp list."""
    n = len(cusps)
    start = cusps[house - 1]
    end = cusps[house % n]
    width = (end - start) % 360.0
    if width == 0:
        width = 360.0
    madhya = (start + width / 2.0) % 360.0
    return madhya, width


def whole_sign_house(rashi_idx: int, lagna_rashi_idx: int) -> int:
    """Which house (1-12) a given rashi falls in, counted whole-sign from Lagna's sign."""
    return (rashi_idx - lagna_rashi_idx) % 12 + 1


def navamsa_rashi_index(lon: float) -> int:
    """D9 (Navamsa) sign index (1-12) for a given sidereal longitude.
    Uses the standard continuous formula (108 navamsa slices of 3d20' each,
    cycling through the 12 signs 9 times) — mathematically identical to the
    classical 'count from a fixed starting sign depending on movable/
    fixed/dual nature' rule."""
    navamsa_width = 30.0 / 9.0
    global_idx = int((lon % 360.0) // navamsa_width)  # 0..107
    return (global_idx % 12) + 1


# ---------------------------------------------------------------------------
# data classes
# ---------------------------------------------------------------------------
@dataclass
class GrahaPos:
    name: str                 # English key, e.g. "Sun"
    lon: float                # sidereal longitude, degrees 0-360
    rashi_idx: int = 0
    amsa: int = 0              # degree within the rashi, 0-29 (အံသာ)
    lipta: int = 0             # arc-minute within that degree, 0-59 (လိတ္တာ)
    house: int = 0            # bhava-madhya based placement
    own_sign: Optional[bool] = None
    karaka: str = ""          # "Soma" or "Papa"
    step1: Optional[float] = None
    step2: Optional[float] = None
    step3: Optional[float] = None
    step4: Optional[float] = None
    step5: Optional[float] = None
    step6: Optional[float] = None
    final: float = 0.0
    label: str = ""


@dataclass
class BhavaRow:
    house: int
    rashi_idx: int
    rashi_name: str
    lord: str
    karaka: str                  # "Soma" or "Papa"  (of the house, via its lord)
    madhya: float
    own_strength: float = 0.0    # = lord's final strength
    positive_influence: float = 0.0
    negative_influence: float = 0.0
    net_influence: float = 0.0


def compute_bhavas(lagna_lon: float, cusps: List[float]) -> List[BhavaRow]:
    lagna_rashi = rashi_index(lagna_lon)
    rows = []
    for h in range(1, 13):
        r_idx = (lagna_rashi - 1 + (h - 1)) % 12 + 1
        lord = RASHI_LORD[r_idx - 1]
        karaka = "Papa" if h in DUSTHANA else "Soma"
        madhya, _width = house_madhya_and_width(h, cusps)
        rows.append(BhavaRow(
            house=h, rashi_idx=r_idx, rashi_name=RASHI_MM[r_idx - 1],
            lord=lord, karaka=karaka, madhya=madhya,
        ))
    return rows


def graha_karaka_status(name: str, bhavas: List[BhavaRow]) -> str:
    """'Soma' or 'Papa'. Rahu/Ketu are always Papa (course Lesson 6 p14).
    A planet owning two signs is classed Papa if EITHER owned house is a
    dusthana (6/8/12) — see README for this documented judgment call."""
    if name in ("Rahu", "Ketu"):
        return "Papa"
    for row in bhavas:
        if row.lord == name and row.karaka == "Papa":
            return "Papa"
    return "Soma"


def absolute_positional_strength(name: str, lon: float, rashi_idx: int) -> Optional[float]:
    """Step 1. Own-sign = +1.0 (100%). Otherwise a continuous linear score
    between the graha's exaltation point (+1) and debilitation point (-1),
    both fixed at the sign MIDPOINT (15 deg) per MOTAA's convention.
    Returns None for Rahu/Ketu (not scored — see README)."""
    if name not in EXALT_DEBIL:
        return None
    if RASHI_LORD[rashi_idx - 1] == name:
        return 1.0
    exalt_idx, _debil_idx = EXALT_DEBIL[name]
    exalt_point = (exalt_idx - 1) * 30 + 15
    d = angular_distance(lon, exalt_point)      # 0..180, 0=at exaltation, 180=at debilitation
    return (90.0 - d) / 90.0                     # +1 .. -1 linear


def relative_positional_strength(house: int, name: str, bhavas: List[BhavaRow]) -> float:
    """Step 2. Kendra/Trikona = +1.0. Dusthana = -1.0, unless the graha is
    itself that dusthana house's own (whole-sign) lord, in which case +1.0.
    All other houses = 0.0."""
    if house in KENDRA_TRIKONA:
        return 1.0
    if house in DUSTHANA:
        owns_it = any(r.house == house and r.lord == name for r in bhavas)
        return 1.0 if owns_it else -1.0
    return 0.0


def combustion_score(name: str, lon: float, sun_lon: float) -> Optional[float]:
    """Step 3. Negative malus, 0 (no combustion) to -1 (exact conjunction).
    None for Sun itself, Rahu, Ketu."""
    if name not in COMBUST_ORB:
        return None
    orb = COMBUST_ORB[name]
    return -influence_pct(lon, sun_lon, orb)


def compute_all(grahas: Dict[str, float], lagna_lon: float, cusps: List[float]):
    """
    grahas: {"Sun": lon, "Moon": lon, ..., "Rahu": lon, "Ketu": lon}  (sidereal, degrees)
    lagna_lon: sidereal ascendant longitude, degrees
    cusps: 12 house-start longitudes (from ephemeris.house_cusps / bhava_madhya_cusps)

    Returns (graha_positions: dict[str,GrahaPos], bhavas: list[BhavaRow],
             rashi_to_grahamidpoint_matrix, house_matrix)
    """
    bhavas = compute_bhavas(lagna_lon, cusps)
    sun_lon = grahas["Sun"]

    positions: Dict[str, GrahaPos] = {}
    for name in GRAHA9:
        lon = grahas[name]
        r_idx = rashi_index(lon)
        amsa, lipta = amsa_lipta(lon)
        house = bhava_of(lon, cusps)
        own_sign = (RASHI_LORD[r_idx - 1] == name) if name in GRAHA7 else None
        karaka = graha_karaka_status(name, bhavas)
        gp = GrahaPos(name=name, lon=lon, rashi_idx=r_idx, amsa=amsa, lipta=lipta,
                      house=house, own_sign=own_sign, karaka=karaka)
        gp.step1 = absolute_positional_strength(name, lon, r_idx)
        gp.step2 = relative_positional_strength(house, name, bhavas)
        gp.step3 = combustion_score(name, lon, sun_lon) if name != "Sun" else None
        positions[name] = gp

    # Step 4 / Step 5 need a 9x12 raw-influence matrix onto each RASHI midpoint
    rashi_matrix: Dict[str, List[float]] = {}   # name -> [influence on rashi k=1..12]
    for name in GRAHA9:
        lon = grahas[name]
        rashi_matrix[name] = [influence_pct(lon, (k - 1) * 30 + 15, 15) for k in range(1, 13)]

    def weighted_sum_on_rashi(target_rashi: int, exclude: str) -> float:
        total = 0.0
        for other in GRAHA9:
            if other == exclude:
                continue
            val = rashi_matrix[other][target_rashi - 1]
            if val >= 0.6:
                wt = -1 if positions[other].karaka == "Papa" else 1
                total += wt * val
        return total

    for name in GRAHA9:
        gp = positions[name]
        owned = [i + 1 for i in range(12) if RASHI_LORD[i] == name]
        if owned:
            gp.step4 = sum(weighted_sum_on_rashi(o, name) for o in owned) / len(owned)
        else:
            gp.step4 = None
        gp.step5 = weighted_sum_on_rashi(gp.rashi_idx, name)

    # Step 6: dispositor's full pre-step-6 aggregate (Steps 1+2+3+4+5 of the
    # sign LORD), per the course's own worked table ("အင်းအား (0+2+3+4+5)"
    # column feeding directly into the next graha's Step-6 lookup). Since this
    # only ever reads OTHER planets' steps 1-5 (never anyone's step 6), it is
    # never circular — even in mutual sign-exchange (Parivartana) cases.
    for name in GRAHA9:
        gp = positions[name]
        lord = RASHI_LORD[gp.rashi_idx - 1]
        lp = positions[lord]
        parts = [v for v in (lp.step1, lp.step2, lp.step3, lp.step4, lp.step5) if v is not None]
        gp.step6 = sum(parts) / len(parts) if parts else 0.0

    # Final average across whichever of the 6 steps are numeric
    for name in GRAHA9:
        gp = positions[name]
        vals = [v for v in (gp.step1, gp.step2, gp.step3, gp.step4, gp.step5, gp.step6)
                if v is not None]
        gp.final = sum(vals) / len(vals) if vals else 0.0
        gp.label = _label(gp.final)

    # House-level raw influence matrix (9 grahas x 12 houses, onto bhava
    # madhya). max_orb is HALF that house's own angular width, so unequal
    # house systems (Placidus/Koch/...) get a sensibly-scaled orb per house
    # instead of an assumed fixed 15 deg.
    house_matrix: Dict[str, List[float]] = {}
    house_widths = [house_madhya_and_width(h, cusps)[1] for h in range(1, 13)]
    for name in GRAHA9:
        lon = grahas[name]
        house_matrix[name] = [
            influence_pct(lon, bhavas[h - 1].madhya, house_widths[h - 1] / 2.0)
            for h in range(1, 13)
        ]

    for row in bhavas:
        lord_final = positions[row.lord].final
        row.own_strength = lord_final
        pos_total = 0.0
        neg_total = 0.0
        for name in GRAHA9:
            val = house_matrix[name][row.house - 1]
            if val >= 0.6:
                if positions[name].karaka == "Papa":
                    neg_total -= val
                else:
                    pos_total += val
        row.positive_influence = pos_total
        row.negative_influence = neg_total
        row.net_influence = pos_total + neg_total

    return positions, bhavas, rashi_matrix, house_matrix


def _label(final: float) -> str:
    if final >= 0.5:
        return "အင်အား အလွန်ကောင်း"
    if final >= 0.15:
        return "အင်အား ကောင်း"
    if final >= -0.15:
        return "အလယ်အလတ်"
    if final >= -0.5:
        return "အင်အား နည်း"
    return "အင်အား အလွန်နည်း"
