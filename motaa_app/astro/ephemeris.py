# -*- coding: utf-8 -*-
"""
Swiss Ephemeris wrapper — the only module in this project that talks to
`pyswisseph` directly. Everything else (motaa.py, dasha.py) works on plain
longitudes in degrees, so this is the single place to look if planetary
positions ever need debugging or a different ephemeris backend swapped in.

Reference: Swiss Ephemeris Programmer's Manual (swephprg.pdf, bundled with
this project) and https://github.com/aloistr/swisseph

Ayanamsa: Lahiri (SIDM_LAHIRI) by default — the de-facto standard for
Myanmar / Vedic sidereal (Nirayana) astrology, matching MOTAA usage.

Calculation flag: FLG_MOSEPH (Moshier semi-analytic ephemeris) is used by
default because it ships inside pyswisseph itself — no separate ephemeris
data files need to be downloaded for the app to work out of the box.
Accuracy is a few arc-seconds for planets, entirely sufficient for
sign/house/degree-level astrology. If you want full JPL-grade precision,
download the .se1 files from https://www.astro.com/ftp/swisseph/ephe/ and
switch to swe.FLG_SWIEPH (see `set_ephe_path` below).
"""
import swisseph as swe
from datetime import datetime, timedelta, timezone as dt_timezone

AYANAMSA_MODES = {
    "lahiri": swe.SIDM_LAHIRI,
    "raman": swe.SIDM_RAMAN,
    "krishnamurti": swe.SIDM_KRISHNAMURTI,
}

PLANET_IDS = {
    "Sun": swe.SUN, "Moon": swe.MOON, "Mars": swe.MARS, "Mercury": swe.MERCURY,
    "Jupiter": swe.JUPITER, "Venus": swe.VENUS, "Saturn": swe.SATURN,
}

# Display-only outer planets (see constants.OUTER_PLANETS) — not part of
# the classical 9-graha set above.
OUTER_PLANET_IDS = {"Uranus": swe.URANUS, "Neptune": swe.NEPTUNE, "Pluto": swe.PLUTO}

# House systems offered in the UI, each mapped to a real Swiss Ephemeris
# house-system code (swe.houses_ex). MOTAA's own "Bhava-Madhya" definition
# (Ascendant at the middle of house 1) used to be offered here as its own
# entry, computed directly rather than via swe.houses_ex — but it's
# numerically identical to swisseph's own 'V' (Vehlow Equal), which uses
# the exact same definition (verified: cusps match to floating-point
# noise), so it was dropped as a redundant duplicate of "vequal" below.
HOUSE_SYSTEMS = {
    "vequal": b"V",
    "equal": b"E",
    "placidus": b"P",
    "koch": b"K",
    "porphyrius": b"O",
    "regiomontanus": b"R",
    "campanus": b"C",
    # "vplacidus" intentionally omitted — not a standard Swiss Ephemeris
    # house system and its exact definition could not be verified; see README.
}

# Full (non-abbreviated) display name for each HOUSE_SYSTEMS key — shown in
# the UI dropdown, the result page, and the PDF, so "vequal" always reads
# as "VEqual (Vehlow Equal)" rather than the bare internal key.
HOUSE_SYSTEM_LABELS = [
    ("vequal", "VEqual (Vehlow Equal)"),
    ("equal", "Equal"),
    ("placidus", "Placidus"),
    ("koch", "Koch"),
    ("porphyrius", "Porphyrius"),
    ("regiomontanus", "Regiomontanus"),
    ("campanus", "Campanus"),
]
HOUSE_SYSTEM_LABEL_MAP = dict(HOUSE_SYSTEM_LABELS)

_CALC_FLAG = swe.FLG_MOSEPH | swe.FLG_SIDEREAL | swe.FLG_SPEED


def set_ephe_path(path: str):
    """Call once at app start if you have real Swiss Ephemeris .se1 data
    files and want to use swe.FLG_SWIEPH instead of the built-in Moshier
    approximation for maximum precision."""
    swe.set_ephe_path(path)


def configure(ayanamsa: str = "lahiri"):
    mode = AYANAMSA_MODES.get(ayanamsa.lower(), swe.SIDM_LAHIRI)
    swe.set_sid_mode(mode, 0, 0)


def to_julian_ut(local_dt: datetime, tz_offset_hours: float) -> float:
    """Convert a local civil datetime + timezone offset (hours, e.g. Myanmar
    = +6.5) into a Julian Day (Universal Time) usable by swe.calc_ut/houses_ex."""
    ut_dt = local_dt - timedelta(hours=tz_offset_hours)
    hour = ut_dt.hour + ut_dt.minute / 60.0 + ut_dt.second / 3600.0
    return swe.julday(ut_dt.year, ut_dt.month, ut_dt.day, hour)


def get_ayanamsa(jd_ut: float) -> float:
    return swe.get_ayanamsa_ut(jd_ut)


def _calc(jd_ut: float, pid: int, flags: int):
    """Defensive wrapper: different pyswisseph releases have returned either
    a flat 6-tuple, or a (6-tuple, return_flag) pair, from swe.calc_ut().
    Handle both so this app isn't tied to one exact package version."""
    result = swe.calc_ut(jd_ut, pid, flags)
    if len(result) == 2 and isinstance(result[0], (tuple, list)):
        xx, _retflag = result
    else:
        xx = result
    return xx


def sidereal_positions_and_retrograde(jd_ut: float, node_mode: str = "mean"):
    """Return ({"Sun": lon, ..., "Rahu": lon, "Ketu": lon}, {"Sun": bool, ...})
    — sidereal longitude in degrees and whether that body's apparent daily
    motion is retrograde (negative ecliptic-longitude speed, xx[3] from
    calc_ut — _CALC_FLAG always includes FLG_SPEED). One calc_ut call per
    body serves both dicts. Ketu mirrors Rahu (opposite point, same axis,
    so the same direction of motion)."""
    lons, retro = {}, {}
    for name, pid in PLANET_IDS.items():
        xx = _calc(jd_ut, pid, _CALC_FLAG)
        lons[name] = xx[0] % 360.0
        retro[name] = xx[3] < 0

    node_id = swe.TRUE_NODE if node_mode == "true" else swe.MEAN_NODE
    xx = _calc(jd_ut, node_id, _CALC_FLAG)
    lons["Rahu"] = xx[0] % 360.0
    lons["Ketu"] = (xx[0] + 180.0) % 360.0
    retro["Rahu"] = retro["Ketu"] = xx[3] < 0
    return lons, retro


def sidereal_positions(jd_ut: float, node_mode: str = "mean") -> dict:
    """Return {"Sun": lon, ..., "Rahu": lon, "Ketu": lon} in sidereal degrees."""
    lons, _retro = sidereal_positions_and_retrograde(jd_ut, node_mode)
    return lons


def outer_planet_data(jd_ut: float):
    """Return ({"Uranus": lon, "Neptune": lon, "Pluto": lon}, {"Uranus":
    bool, ...}) — sidereal longitude and retrograde flag for each
    display-only reference planet, see constants.OUTER_PLANETS."""
    lons, retro = {}, {}
    for name, pid in OUTER_PLANET_IDS.items():
        xx = _calc(jd_ut, pid, _CALC_FLAG)
        lons[name] = xx[0] % 360.0
        retro[name] = xx[3] < 0
    return lons, retro


def sidereal_ascendant_and_cusps(jd_ut: float, lat: float, lon: float, hsys_code: bytes):
    """Ascendant + 12 house cusps (both sidereal degrees) for a real Swiss
    Ephemeris house system (Placidus, Koch, Equal, etc.).

    Implementation note (fixed after a real bug report): this deliberately
    does NOT rely on swe.houses_ex()'s sidereal flag. Different pyswisseph
    builds have been seen with different positional-argument orders for
    houses_ex()'s iflag parameter, and passing it wrong silently produces a
    *tropical* ascendant while planets (via calc_ut, whose argument order is
    unambiguous) stay sidereal — a systematic ~1-sign offset between the
    lagna and every planet, which is exactly the symptom that was reported.

    Instead we use the plain swe.houses() call — documented unambiguously as
    (tjdut, lat, lon, hsys), no flags at all, always tropical — and then
    subtract the ayanamsa ourselves. This is the exact pattern shown in
    pyswisseph's own official docs for sidereal house cusps:
        cusps[i] = swe.degnorm(cusps[i] - aya)
        ascmc[i] = swe.degnorm(ascmc[i] - aya)
    (see docs/programmers_manual/house_cusp_calculation.rst)

    Also note: swe.houses()/houses_ex() return `cusps` as a plain 12-tuple
    indexed 0..11 for houses 1..12 (NOT a 13-element, index-0-unused tuple
    like the underlying C array) — indexing this wrong (e.g. cusps[1:13])
    silently produces a too-short list and an IndexError downstream, which
    was the other bug reported ("list index out of range").
    """
    cusps, ascmc = swe.houses(jd_ut, lat, lon, hsys_code)
    aya = swe.get_ayanamsa_ut(jd_ut)
    asc = (ascmc[0] - aya) % 360.0
    # Defensive: house() is documented to return a plain 12-tuple (houses
    # 1..12 at indices 0..11), but guard against a 13-element variant
    # (index 0 unused, matching the underlying C array) just in case.
    raw = list(cusps[1:13]) if len(cusps) >= 13 else list(cusps[:12])
    assert len(raw) == 12, f"expected 12 house cusps from swe.houses(), got {len(raw)}"
    cusp_list = [(c - aya) % 360.0 for c in raw]
    return asc, cusp_list


def house_cusps(jd_ut: float, lat: float, lon: float, hsys: str = "vequal"):
    """Returns (ascendant_deg, [12 cusp-start longitudes]) for the requested
    house system key (see HOUSE_SYSTEMS)."""
    code = HOUSE_SYSTEMS.get(hsys, b"P")
    return sidereal_ascendant_and_cusps(jd_ut, lat, lon, code)


def compute_chart_longitudes(local_dt: datetime, tz_offset_hours: float,
                              lat: float, lon: float, ayanamsa: str = "lahiri",
                              node_mode: str = "mean", hsys: str = "vequal"):
    """One-stop convenience call used by astro/charts.py."""
    configure(ayanamsa)
    jd_ut = to_julian_ut(local_dt, tz_offset_hours)
    grahas, retrograde = sidereal_positions_and_retrograde(jd_ut, node_mode=node_mode)
    asc, cusps = house_cusps(jd_ut, lat, lon, hsys=hsys)
    ayan = get_ayanamsa(jd_ut)
    return {
        "jd_ut": jd_ut,
        "ayanamsa_value": ayan,
        "grahas": grahas,
        "retrograde": retrograde,
        "lagna": asc,
        "cusps": cusps,
    }
