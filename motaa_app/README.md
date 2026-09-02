# MOTAA ဇာတာ တွက်စက် (Chart Calculator)

Swiss Ephemeris (real astronomical positions) + MOTAA Astrology Course Level-1
(Lesson 6 & 7) methodology + Vimshottari Dasha — as a local web app you run on
your own Mac.

## Why a local app instead of Excel?

Excel formulas cannot call the Swiss Ephemeris library — real planetary
position calculation requires actual astronomical algorithms (VSOP/lunar
theory), which is not something spreadsheet formulas can do. On Windows,
Excel/VBA can call the Swiss Ephemeris DLL directly, but **Mac Excel does not
support that VBA/DLL feature at all**. A small local Python web app is the
most accurate and most Mac-friendly way to get this working — and it uses the
*real* Swiss Ephemeris library (via `pyswisseph`), not an approximation.

## Setup (macOS)

1. **Install Python 3** if you don't have it already (macOS usually ships one,
   but Homebrew's is more reliable): `brew install python`
2. **Download this folder** and open Terminal in it.
3. **Create a virtual environment** (keeps this project's packages separate
   from the rest of your system):
   ```
   python3 -m venv venv
   source venv/bin/activate
   ```
4. **Install dependencies**:
   ```
   pip install -r requirements.txt
   ```
   (`pyswisseph` compiles a small C extension on install — this is normal and
   takes a minute the first time.)
5. **Run the app**:
   ```
   python app.py
   ```
6. Open **http://127.0.0.1:5000** in your browser (Safari, Chrome, or Firefox
   all work — the chart layout uses CSS Grid, well supported by all of them).

Each time you want to use the app again later: open Terminal in this folder,
run `source venv/bin/activate` then `python app.py`.

## What it computes

1. **Ephemeris** (`astro/ephemeris.py`) — real sidereal (Nirayana) planetary
   longitudes via Swiss Ephemeris, Lahiri ayanamsa by default (the standard
   for Myanmar/Vedic astrology), Ascendant via `swe.houses_ex`.
   - Uses the built-in **Moshier** approximation (`swe.FLG_MOSEPH`) so the app
     works immediately with zero extra downloads. Accuracy is a few
     arc-seconds — entirely sufficient for sign/house/degree-level astrology.
   - If you want JPL-grade precision, download the `.se1` ephemeris files from
     <https://www.astro.com/ftp/swisseph/ephe/> and call
     `ephemeris.set_ephe_path("/path/to/files")` once at app start, then switch
     `_CALC_FLAG` in `ephemeris.py` from `FLG_MOSEPH` to `FLG_SWIEPH`.
2. **House systems** — selectable in the UI: MOTAA's own **Bhava-Madhya**
   (Ascendant = house-1 midpoint, equal 30° houses — the default, matching
   the course), plus real Swiss Ephemeris systems **VEqual, Equal, Placidus,
   Koch, Porphyrius, Regiomontanus, Campanus**. Everything downstream (bhava
   placement, bhava-madhya, and the per-house orb used in the influence
   formula) is computed generically from the 12 house cusps returned by
   whichever system you pick, so unequal-house systems (Placidus/Koch/...)
   scale the influence orb to *half that house's own width* rather than
   assuming a fixed 15°. "VPlacidus" (seen in some reference apps) is **not**
   a standard Swiss Ephemeris system and its exact definition couldn't be
   verified, so it isn't offered — everything else in that dropdown is real.
3. **Three chart displays** — ရာသီ (Rashi, whole-sign houses), ဘာဝ (Bhava,
   using whichever house system you picked), and နဝင်း (Navamsa/D9), all
   drawn in the traditional Myanmar diamond-chart style: a 3×3 grid where the
   4 corners are each split by a diagonal into 2 triangular houses, the 4
   edge-cells are the Kendra houses (1/4/7/10), and the center is unused.
   This geometry was reverse-engineered and pixel-verified against a
   screenshot of a real Myanmar astrology app, not guessed at — see
   `astro/chart_svg.py` for the coordinate derivation. The same geometry is
   drawn twice: once as inline SVG for the web page (`chart_svg.py`) and once
   as native reportlab shapes for the PDF (`reports/pdf_report.py`) — no
   external SVG-to-PDF conversion library needed.
4. **MOTAA Level-1 analysis** (`astro/motaa.py`) — Bhava classification,
   Karaka Soma/Papa determination, and the 6-step planetary strength method
   from Lessons 6–7. **Step 6 (dispositor strength)** was corrected in this
   version to use the dispositor's full Steps 1–5 aggregate (matching the
   course's own worked table, which feeds a "Steps 0+2+3+4+5"-style running
   total into the next planet's Step-6 lookup) rather than the narrower
   Steps 1-3 average used in an earlier draft. This is still provably
   non-circular: Step 6 only ever reads *other* planets' Steps 1–5, never
   anyone's Step 6, even under mutual sign-exchange (Parivartana).
5. **Vimshottari Dasha** (`astro/dasha.py`) — standard 120-year Mahadasha
   cycle + Antardasha sub-periods, derived from the Moon's nakshatra position
   at birth.
6. **PDF report** (`reports/pdf_report.py`) — via `reportlab`. Bundles the
   **Padauk** Myanmar Unicode font (`static/fonts/Padauk-Regular.ttf`, SIL
   Open Font License) so Burmese text renders correctly in the PDF out of
   the box on any machine — macOS, Linux, a fresh Codespace — with no
   system font install required. If you have the **"Masterpiece Uni
   Round"** font installed instead (used automatically in the web UI's
   CSS) and want the PDF to match it, point `_CANDIDATE_FONTS` in
   `reports/pdf_report.py` at its `.ttf` file — it's tried first if
   present, see the comments at the top of that file for the exact paths.

## Project layout (for future editing/extension)

```
app.py                  Flask routes (/ , /calculate , /pdf)
astro/
  constants.py          All reference tables (rashi, nakshatra, dasha years,
                         friendship, exaltation/debilitation, combustion orb)
  ephemeris.py           <- only file that talks to pyswisseph; house-system
                            selection (Bhava-Madhya/Equal/Placidus/Koch/...)
                            lives here
  motaa.py               <- MOTAA strength/bhava-influence calculations,
                            generalized to work off any 12-cusp house system;
                            also has the Navamsa (D9) sign calculation
  dasha.py               <- Vimshottari Mahadasha/Antardasha math
  chart_svg.py           <- Myanmar-style diamond chart geometry (3x3 grid,
                            corner triangles) + SVG string builder — shared
                            by both the web page and the PDF
  charts.py              <- ties everything above together (BirthInput ->
                            chart dict -> per-chart-style house content)
reports/
  pdf_report.py           PDF generation, including diamond charts drawn
                           with reportlab shapes (same geometry as chart_svg.py)
templates/               Jinja2 HTML pages
static/style.css         All styling (font: "Masterpiece Uni Round", with
                         system-font fallbacks)
```

Because the ephemeris, MOTAA-math, dasha, and chart-geometry logic are
cleanly separated into their own modules with plain-Python interfaces (no
framework dependencies), each is independently testable and each is a
natural place to extend later — e.g. add Pratyantardasha (3rd-level
sub-periods), Ashtakavarga, Yogas, more divisional charts (D10, D12, ...), or
a second ayanamsa comparison, without touching the others.

## Known issues fixed along the way

- **"list index out of range" / wrong rashi & house placements** — an earlier
  version called `swe.houses_ex()` with the sidereal flag in a position that
  (depending on the installed pyswisseph build) could be silently
  mis-ordered, which had two visible symptoms: a crash reading house cusps,
  and — more subtly — planets and signs coming out shifted by roughly one
  sign from where they should be (because the ascendant ended up computed in
  *tropical* coordinates while the planets, via the unambiguous `calc_ut()`
  signature, stayed correctly sidereal). Fixed by switching to the plainer,
  unambiguously-documented `swe.houses()` call and subtracting the ayanamsa
  ourselves — the same pattern pyswisseph's own documentation recommends for
  sidereal house cusps. See the docstring on
  `ephemeris.sidereal_ascendant_and_cusps()` for the full explanation.

## Documented assumptions / simplifications

(Carried over from the Excel-workbook version, still applicable here — see
that workbook's own README tab for the original writeup)

1. **Moolatrikona simplified to standard whole-sign rulership** — each of the
   12 signs has exactly one "lord" used both for ordinary rulership and for
   MOTAA's Karaka-Soma/Papa classification. The classical BPHS distinction
   between a planet's *moolatrikona* portion vs its plain *own sign* (for the
   5 dual-sign-owning planets) is not modeled.
2. **Dual-sign-owning planet, mixed houses** — if a planet owns one soma-house
   and one dusthana (6/8/12) house, it is classified **Karaka Papa** (the
   dusthana lordship dominates). This is a documented judgment call — the
   course text states the dusthana-lordship rule as an unqualified "basic
   law" without carving out an exception for e.g. simultaneously owning the
   Lagna, so this app applies it literally. If your own reading of MOTAA
   differs for a specific case (e.g. Libra Lagna's Venus, who rules both
   1 and 8), you can override this in `astro/motaa.py::graha_karaka_status`.
3. **Absolute Positional Strength (Step 1)** — own sign = full +100%;
   otherwise a continuous linear score between the graha's exaltation point
   and debilitation point (both fixed at the sign's 15° midpoint per MOTAA
   convention, course Lesson 6 p32-33), rather than separately scoring
   friend/enemy sign residency.
4. **Combustion orbs** — classical Parashara standard values (Moon 12°, Mars
   17°, Mercury 14°, Jupiter 11°, Venus 10°, Saturn 15°) since the course
   PDF's own table is an embedded image, not extractable as text.
5. **Rahu/Ketu** — always Karaka Papa, per the course text. Their *severity*
   is stated by the course to depend on nakshatra/navamsa dispositor quality,
   which is Level-2 material not modeled here yet.
6. **Step 6 (dispositor strength)** uses the dispositor's Steps 1+2+3+4+5
   aggregate (not the final score, which would include the dispositor's own
   Step 6) to avoid a circular reference when two planets are mutually
   placed in each other's signs. This matches the course's own worked table
   more closely than an earlier draft of this tool, which used only Steps
   1-3 for this lookup.
7. **Vimshottari Dasha** — Mahadasha/Antardasha only (no Pratyantardasha yet).
   Year length used for date math: 365.2425 days (Gregorian civil year).
8. **Ayanamsa** — Lahiri by default (standard for Myanmar/Vedic astrology);
   Raman and Krishnamurti (KP) offered as alternates in the dropdown.
9. **Node mode** — Mean Node by default (traditional Vedic convention); True
   Node offered as an alternate.
10. **Diamond chart geometry** — the traditional Myanmar 3x3-grid-with-
    corner-triangles layout was reverse-engineered from a real app screenshot
    rather than assumed; within each ambiguous corner cell (where one
    triangle geometrically touches both neighbouring Kendra houses) the
    "inner" triangle was assigned the earlier house number and the "outer
    tip" triangle the later one, by convention — see `astro/chart_svg.py`
    for the full derivation and reasoning.
11. **"VPlacidus"** (seen in some reference apps' house-system menus) is not
    a standard Swiss Ephemeris house system and its exact definition
    couldn't be verified, so it's omitted from the dropdown. Everything else
    offered (Bhava-Madhya, VEqual, Equal, Placidus, Koch, Porphyrius,
    Regiomontanus, Campanus) is computed from real Swiss Ephemeris cusps
    (except Bhava-Madhya, which is MOTAA's own equal-house formula).

This tool is a working aid for MOTAA Level-1 study, not a replacement for a
qualified astrologer's judgment — Yogas, planetary war (Graha Yuddha),
divisional charts, and detailed Dasha/Gochara interaction (all flagged by the
course itself as Level-2+ topics) are not modeled.
