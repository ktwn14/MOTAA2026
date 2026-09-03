# -*- coding: utf-8 -*-
"""
Shared reference data for the MOTAA Level-1 chart calculator.
All classical/astronomical tables used by ephemeris.py, motaa.py and dasha.py
live here so they can be audited and edited in one place.
"""

# ---------------------------------------------------------------------------
# Rashi (zodiac signs), 1-indexed, starting at Mesha (Aries)
# ---------------------------------------------------------------------------
RASHI_MM = ["မိဿ", "ပြိဿ", "မေထုန်", "ကရကဋ်", "သိဟ်", "ကန်",
            "တူ", "ဗြိစ္ဆာ", "ဓနု", "မကာရ", "ကုံ", "မိန်"]
RASHI_EN = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
            "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]

# Rashi lord (standard whole-sign rulership; used as "moolatrikona lord" per
# MOTAA's simplified Level-1 convention — see README / course Lesson 6 p6, p12)
RASHI_LORD = ["Mars", "Venus", "Mercury", "Moon", "Sun", "Mercury",
              "Venus", "Mars", "Jupiter", "Saturn", "Saturn", "Jupiter"]

# Motion (chara/movable, sthira/fixed, dwiswabhava/dual) and element
# (tejo/fire, prithvi/earth, vayo/air, apas/water), both a fixed classical
# property of the SIGN itself (independent of which planet occupies it) —
# each cycles every 3 signs starting from Mesha/Aries.
RASHI_MOTION = ["စရ", "ထိရ", "ဒွေးဒဟ", "စရ", "ထိရ", "ဒွေးဒဟ",
                "စရ", "ထိရ", "ဒွေးဒဟ", "စရ", "ထိရ", "ဒွေးဒဟ"]
RASHI_ELEMENT = ["တေဇော", "ပထဝီ", "ဝါယော", "အာပေါ", "တေဇော", "ပထဝီ",
                  "ဝါယော", "အာပေါ", "တေဇော", "ပထဝီ", "ဝါယော", "အာပေါ"]

# ---------------------------------------------------------------------------
# Grahas
# ---------------------------------------------------------------------------
GRAHA7 = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]
GRAHA9 = GRAHA7 + ["Rahu", "Ketu"]

GRAHA_MM = {
    "Sun": "တနင်္ဂနွေ", "Moon": "တနင်္လာ", "Mars": "အင်္ဂါ", "Mercury": "ဗုဒ္ဓဟူး",
    "Jupiter": "ကြာသပတေး", "Venus": "သောကြာ", "Saturn": "စနေ",
    "Rahu": "ရာဟု", "Ketu": "ကိတ်",
}

# Compact numeral code for each graha, used in the diamond charts where
# GRAHA_MM's full names don't fit — the lagna's own short label is just
# "လဂ်" (no numeral). Sun..Venus follow the classical 1..6 order; Saturn is
# "0" rather than "7" per MOTAA's own convention, Rahu/Ketu are 8/9.
GRAHA_SHORT = {
    "Sun": "၁", "Moon": "၂", "Mars": "၃", "Mercury": "၄", "Jupiter": "၅",
    "Venus": "၆", "Saturn": "၀", "Rahu": "၈", "Ketu": "၉",
}
LAGNA_SHORT = "လဂ်"

# ---------------------------------------------------------------------------
# Outer planets (Uranus/Neptune/Pluto) — not part of the classical 9-graha
# Vedic system MOTAA's Steps 1-6 / karaka / dasha logic is built on, so
# they're display-only reference points on the diamond charts (short code
# only, no rashi_idx/house math beyond simple placement, no strength or
# dasha calculation).
# ---------------------------------------------------------------------------
OUTER_PLANETS = ["Uranus", "Neptune", "Pluto"]
OUTER_PLANET_SHORT = {"Uranus": "U", "Neptune": "N", "Pluto": "P"}

# Natural benefic / malefic (reference only; MOTAA's *functional* karaka
# classification, not this natural one, drives the actual calculations)
NATURAL_BENEFIC = {"Jupiter", "Venus"}
NATURAL_MALEFIC = {"Sun", "Mars", "Saturn"}
NATURAL_VARIABLE = {"Moon", "Mercury"}

# Naisargika Maitri (classical Parashara natural friendship table)
FRIENDSHIP = {
    "Sun":     {"friend": {"Moon", "Mars", "Jupiter"},   "enemy": {"Venus", "Saturn"}},
    "Moon":    {"friend": {"Sun", "Mercury"},             "enemy": set()},
    "Mars":    {"friend": {"Sun", "Moon", "Jupiter"},     "enemy": {"Mercury"}},
    "Mercury": {"friend": {"Sun", "Venus"},                "enemy": {"Moon"}},
    "Jupiter": {"friend": {"Sun", "Moon", "Mars"},        "enemy": {"Mercury", "Venus"}},
    "Venus":   {"friend": {"Mercury", "Saturn"},           "enemy": {"Sun", "Moon"}},
    "Saturn":  {"friend": {"Mercury", "Venus"},            "enemy": {"Sun", "Moon", "Mars"}},
}

# Exaltation / debilitation sign (1-indexed rashi). MOTAA uses the SIGN
# MIDPOINT (15 deg) as the reference "peak" point rather than the classical
# exact degree (course Lesson 6, p32-33) — see motaa.py absolute_positional_strength()
EXALT_DEBIL = {
    "Sun":     (1, 7),
    "Moon":    (2, 8),
    "Mars":    (10, 4),
    "Mercury": (6, 12),
    "Jupiter": (4, 10),
    "Venus":   (12, 6),
    "Saturn":  (7, 1),
}

# Combustion orb, degrees — classical Parashara standard values.
# (documented assumption: the course PDF's own table is an image, not
# extractable text; see README "Documented Assumptions")
COMBUST_ORB = {
    "Moon": 12, "Mars": 17, "Mercury": 14, "Jupiter": 11, "Venus": 10, "Saturn": 15,
}

# House classification (from Lagna)
KENDRA_TRIKONA = {1, 4, 5, 7, 9, 10}   # "strong" houses (Step 2, +100%)
DUSTHANA = {6, 8, 12}                   # malefic-task houses

# ---------------------------------------------------------------------------
# Nakshatras (27), each 13d20m wide, starting at 0 Aries.
# Lord cycle used both for identifying nakshatra-lord and for Vimshottari Dasha.
# ---------------------------------------------------------------------------
NAKSHATRA_EN = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
    "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni",
    "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha",
    "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana", "Dhanishta", "Shatabhisha",
    "Purva Bhadrapada", "Uttara Bhadrapada", "Revati",
]
NAKSHATRA_MM = [
    "အဿဝနီ", "ဘရဏီ", "ကြတ္တိကာ", "ရောဟိဏီ", "မြိဂသီရိုဟ်", "အာဒြာ",
    "ပုနပုသု", "ပုဿ", "အသလိသ", "မာခ", "ပုဗ္ဗာဖန္ဂုနီ", "ဥတ္တရဖန္ဂုနီ",
    "ဟဿ", "စိတြ", "သွာတိ", "ဝိသာခါ", "အနုရာဓာ", "ဇေဋ္ဌ",
    "မူလ", "ပုဗ္ဗာသဠ်", "ဥတ္တရာသဠ်", "သရဝန်", "ဓနိဌ", "သတဘိသက်",
    "ပုဗ္ဗာဘဒြ", "ဥတ္တရာဘဒြ", "ရေဝတီ",
]
# 9-lord repeating cycle, starting with Ashwini = Ketu
DASHA_LORD_CYCLE = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]

# Vimshottari Mahadasha lengths in years (total = 120)
VIMSHOTTARI_YEARS = {
    "Ketu": 7, "Venus": 20, "Sun": 6, "Moon": 10, "Mars": 7,
    "Rahu": 18, "Jupiter": 16, "Saturn": 19, "Mercury": 17,
}
VIMSHOTTARI_TOTAL = 120

NAKSHATRA_SPAN = 360.0 / 27.0  # 13 deg 20'
