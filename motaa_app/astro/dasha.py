# -*- coding: utf-8 -*-
"""
Vimshottari Dasha (ဝိသောတရီ ဒသာ) calculation.

Pure math on top of the Moon's sidereal longitude at birth — no ephemeris
calls needed here, which makes this module fully unit-testable on its own.

Standard classical algorithm:
  1. Locate which of the 27 nakshatras the Moon occupies, and how far
     (as a fraction 0..1) the Moon has travelled through it.
  2. The nakshatra's ruling planet (cyclic 9-lord sequence, repeated 3x)
     is the Mahadasha lord running at birth.
  3. The *balance* of that first Mahadasha = (1 - fraction elapsed) * its
     full Vimshottari length.
  4. Subsequent Mahadashas follow the fixed 9-lord cycle, each running its
     full classical length, until we've covered the requested span
     (typically full 120-year cycle from birth).
  5. Each Mahadasha is further divided into 9 Antardashas (sub-periods),
     in the same 9-lord cyclic order *starting from the Mahadasha lord
     itself*, each proportional to (antar_lord_years * maha_lord_years)/120.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List

from .constants import DASHA_LORD_CYCLE, VIMSHOTTARI_YEARS, VIMSHOTTARI_TOTAL, NAKSHATRA_SPAN, \
    NAKSHATRA_EN, NAKSHATRA_MM, GRAHA_MM

YEAR_DAYS = 365.2425  # civil (Gregorian) year length used for Dasha date math


@dataclass
class AntarDasha:
    lord: str
    lord_mm: str
    start: datetime
    end: datetime
    years: float


@dataclass
class MahaDasha:
    lord: str
    lord_mm: str
    start: datetime
    end: datetime
    years: float
    antardashas: List[AntarDasha] = field(default_factory=list)


def nakshatra_of(moon_sidereal_lon: float):
    """Return (index 0..26, name_en, name_mm, lord, fraction_elapsed 0..1)."""
    lon = moon_sidereal_lon % 360.0
    idx = int(lon // NAKSHATRA_SPAN)
    idx = min(idx, 26)
    pos_in_nak = lon - idx * NAKSHATRA_SPAN
    fraction = pos_in_nak / NAKSHATRA_SPAN
    lord = DASHA_LORD_CYCLE[idx % 9]
    return idx, NAKSHATRA_EN[idx], NAKSHATRA_MM[idx], lord, fraction


def _add_years(dt: datetime, years: float) -> datetime:
    return dt + timedelta(days=years * YEAR_DAYS)


def compute_vimshottari(moon_sidereal_lon: float, birth_dt: datetime,
                         span_years: float = 120.0) -> List[MahaDasha]:
    """
    Build the full Mahadasha sequence (with Antardashas) starting at birth,
    covering `span_years` (default: one full 120-year cycle).
    """
    idx, nak_en, nak_mm, first_lord, frac_elapsed = nakshatra_of(moon_sidereal_lon)
    balance_fraction = 1.0 - frac_elapsed

    sequence: List[MahaDasha] = []
    cycle_start_pos = DASHA_LORD_CYCLE.index(first_lord)
    cursor = birth_dt
    total_covered = 0.0
    i = 0
    first = True
    while total_covered < span_years:
        lord = DASHA_LORD_CYCLE[(cycle_start_pos + i) % 9]
        full_years = VIMSHOTTARI_YEARS[lord]
        years = full_years * balance_fraction if first else full_years
        start = cursor
        end = _add_years(cursor, years)
        md = MahaDasha(lord=lord, lord_mm=GRAHA_MM[lord], start=start, end=end, years=years)
        md.antardashas = _antardashas(md, full_years_used_for_proportion=full_years,
                                       balance_fraction=balance_fraction if first else 1.0)
        sequence.append(md)
        cursor = end
        total_covered += years
        first = False
        i += 1
    return sequence


def _antardashas(md: MahaDasha, full_years_used_for_proportion: float,
                  balance_fraction: float) -> List[AntarDasha]:
    """
    Sub-divide one Mahadasha into its 9 Antardashas.

    For a *full* Mahadasha, each Antardasha's length = (maha_years * antar_years)/120,
    and the 9 antardashas exactly sum to the full Mahadasha length.

    For the *first* (partial/balance) Mahadasha at birth, we still slice the
    antardasha proportionally in the same ratios (i.e. we scale each full-length
    antardasha down by `balance_fraction`, and start the antardasha sequence
    from the Mahadasha lord itself but at the point already reached — the
    simplest, standard convention is to keep the same 9 proportional slices
    scaled by balance_fraction, in order starting from the Mahadasha lord).
    """
    start_pos = DASHA_LORD_CYCLE.index(md.lord)
    cursor = md.start
    out = []
    for j in range(9):
        alord = DASHA_LORD_CYCLE[(start_pos + j) % 9]
        # standard formula: (Mahadasha_full_years * Antardasha_lord_years) / 120
        full_antar_years = (full_years_used_for_proportion * VIMSHOTTARI_YEARS[alord]) / VIMSHOTTARI_TOTAL
        antar_years = full_antar_years * balance_fraction
        end = _add_years(cursor, antar_years)
        out.append(AntarDasha(lord=alord, lord_mm=GRAHA_MM[alord], start=cursor, end=end, years=antar_years))
        cursor = end
    return out


def dasha_running_at(sequence: List[MahaDasha], when: datetime):
    """Return (MahaDasha, AntarDasha) active at a given datetime, or (None, None)."""
    for md in sequence:
        if md.start <= when < md.end:
            for ad in md.antardashas:
                if ad.start <= when < ad.end:
                    return md, ad
            return md, md.antardashas[-1] if md.antardashas else None
    return None, None
