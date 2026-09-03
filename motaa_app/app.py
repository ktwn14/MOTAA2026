# -*- coding: utf-8 -*-
"""
MOTAA Chart Calculator — Flask app.

Run with:
    python app.py
then open http://127.0.0.1:5000 in your browser.

See README.md for setup (pip install steps) and architecture notes.
"""
import io
import json
import re
from datetime import datetime

from flask import Flask, render_template, request, send_file, session, redirect, url_for

from astro.charts import BirthInput, build_chart, build_diamond_chart_data
from astro.constants import GRAHA_MM, RASHI_MM, GRAHA9
from astro.ephemeris import HOUSE_SYSTEMS, HOUSE_SYSTEM_LABELS, HOUSE_SYSTEM_LABEL_MAP
from astro.chart_svg import render_diamond_svg
from reports.pdf_report import generate_pdf

app = Flask(__name__)
app.secret_key = "motaa-dev-secret-change-me"   # change this if you deploy beyond localhost

CITY_PRESETS = {
    "ရန်ကုန် (Yangon)": (16.8409, 96.1735, 6.5),
    "မန္တလေး (Mandalay)": (21.9588, 96.0891, 6.5),
    "နေပြည်တော် (Naypyidaw)": (19.7633, 96.0785, 6.5),
    "တောင်ကြီး (Taunggyi)": (20.7897, 97.0378, 6.5),
    "မြစ်ကြီးနား (Myitkyina)": (25.3833, 97.4000, 6.5),
    "-- ကိုယ်တိုင် Latitude/Longitude ရိုက်ရန် --": (None, None, 6.5),
}


def _parse_dms(dms_str: str, direction: str) -> float:
    """Parse a "dd:mm:ss" (or "dd:mm", or "dd") string plus a N/S/E/W
    direction letter into a signed decimal-degree float."""
    parts = [p for p in re.split(r"[:\s]+", (dms_str or "").strip()) if p]
    if not parts:
        raise ValueError("Latitude/Longitude (dd:mm:ss) ကို ဖြည့်ပါ")
    deg = float(parts[0])
    minute = float(parts[1]) if len(parts) > 1 else 0.0
    sec = float(parts[2]) if len(parts) > 2 else 0.0
    value = deg + minute / 60.0 + sec / 3600.0
    return -value if direction in ("S", "W") else value


def _dms_parts(value: float, pos_dir: str, neg_dir: str):
    """Same dd:mm:ss math as _decimal_to_dms, but returns (dms_str,
    direction) as two separate values — used to prefill the birth-data
    form, where the direction is its own <select>, not part of the same
    text field as the degrees."""
    direction = pos_dir if value >= 0 else neg_dir
    value = abs(value)
    deg = int(value)
    minute_full = (value - deg) * 60.0
    minute = int(minute_full)
    sec = round((minute_full - minute) * 60.0)
    if sec == 60:
        sec, minute = 0, minute + 1
    if minute == 60:
        minute, deg = 0, deg + 1
    return f"{deg}:{minute:02d}:{sec:02d}", direction


def _decimal_to_dms(value: float, pos_dir: str, neg_dir: str) -> str:
    """Format a signed decimal-degree float as "dd:mm:ss D" for display."""
    dms_str, direction = _dms_parts(value, pos_dir, neg_dir)
    return f"{dms_str} {direction}"


def _decimal_to_dms_symbols(value: float) -> str:
    """Format an unsigned decimal-degree float (e.g. an ayanamsa value) as
    "dd°mm'ss\"" — no direction letter, since it isn't a coordinate."""
    deg = int(value)
    minute_full = (value - deg) * 60.0
    minute = int(minute_full)
    sec = round((minute_full - minute) * 60.0)
    if sec == 60:
        sec, minute = 0, minute + 1
    if minute == 60:
        minute, deg = 0, deg + 1
    return f"{deg}°{minute:02d}'{sec:02d}\""


def _chart_to_session_input(form) -> BirthInput:
    hsys = form.get("house_system", "vequal")
    if hsys not in HOUSE_SYSTEMS:
        hsys = "vequal"
    latitude = _parse_dms(form.get("latitude_dms", ""), form.get("latitude_dir", "N"))
    longitude = _parse_dms(form.get("longitude_dms", ""), form.get("longitude_dir", "E"))
    return BirthInput(
        name=form.get("name", "").strip() or "အမည်မသိ",
        year=int(form["year"]), month=int(form["month"]), day=int(form["day"]),
        hour=int(form["hour"]), minute=int(form["minute"]), second=int(form.get("second", 0) or 0),
        tz_offset_hours=float(form["tz_offset_hours"]),
        latitude=latitude, longitude=longitude,
        ayanamsa=form.get("ayanamsa", "lahiri"),
        node_mode=form.get("node_mode", "mean"),
        house_system=hsys,
        location_name=form.get("location_name", "").strip(),
    )


app.jinja_env.globals["dms"] = _decimal_to_dms
app.jinja_env.globals["dms_sym"] = _decimal_to_dms_symbols
app.jinja_env.globals["house_system_label"] = lambda key: HOUSE_SYSTEM_LABEL_MAP.get(key, key)


@app.route("/", methods=["GET"])
def index():
    # Prefill the form from the last-computed chart's own inputs (location,
    # ayanamsa, node mode, house system, etc.) if there is one — so
    # recalculating a chart (or reloading this page) doesn't lose everything
    # and reset back to the hardcoded Yangon defaults below.
    last = session.get("last_input")
    if last:
        lat_dms, lat_dir = _dms_parts(last["latitude"], "N", "S")
        lon_dms, lon_dir = _dms_parts(last["longitude"], "E", "W")
        last = {**last, "latitude_dms": lat_dms, "latitude_dir": lat_dir,
                "longitude_dms": lon_dms, "longitude_dir": lon_dir}
    return render_template("index.html", cities=CITY_PRESETS, house_systems=HOUSE_SYSTEM_LABELS, last=last)


@app.route("/calculate", methods=["POST"])
def calculate():
    try:
        binput = _chart_to_session_input(request.form)
        chart = build_chart(binput)
    except Exception as exc:
        return render_template("error.html", message=str(exc)), 400

    # stash the raw inputs (not the computed objects) in session so /pdf can recompute
    session["last_input"] = {
        "name": binput.name, "year": binput.year, "month": binput.month, "day": binput.day,
        "hour": binput.hour, "minute": binput.minute, "second": binput.second,
        "tz_offset_hours": binput.tz_offset_hours, "latitude": binput.latitude,
        "longitude": binput.longitude, "ayanamsa": binput.ayanamsa,
        "node_mode": binput.node_mode, "house_system": binput.house_system,
        "location_name": binput.location_name,
    }

    # group grahas by house, for the diamond-chart grid display
    house_planets = {h: [] for h in range(1, 13)}
    for name in GRAHA9:
        gp = chart["positions"][name]
        house_planets[gp.house].append(GRAHA_MM[name])

    diamonds = build_diamond_chart_data(chart)
    chart_svgs = {
        "rashi": render_diamond_svg(diamonds["rashi"], center_label="ရာသီ"),
        "bhava": render_diamond_svg(diamonds["bhava"], center_label="ဘာဝ"),
        "navamsa": render_diamond_svg(diamonds["navamsa"], center_label="နဝင်း (D9)"),
    }

    return render_template(
        "result.html", chart=chart, GRAHA_MM=GRAHA_MM, RASHI_MM=RASHI_MM, GRAHA9=GRAHA9,
        house_planets=house_planets, diamonds=diamonds, chart_svgs=chart_svgs, now=datetime.now(),
    )


@app.route("/pdf")
def pdf():
    raw = session.get("last_input")
    if not raw:
        return redirect(url_for("index"))
    binput = BirthInput(**raw)
    chart = build_chart(binput)
    diamonds = build_diamond_chart_data(chart)
    buf = generate_pdf(chart, diamonds=diamonds)
    filename = f"MOTAA_Chart_{binput.name}_{binput.year}{binput.month:02d}{binput.day:02d}.pdf"
    return send_file(buf, mimetype="application/pdf", as_attachment=True, download_name=filename)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
