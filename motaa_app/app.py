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
from datetime import datetime

from flask import Flask, render_template, request, send_file, session, redirect, url_for

from astro.charts import BirthInput, build_chart, build_diamond_chart_data
from astro.constants import GRAHA_MM, RASHI_MM, GRAHA9
from astro.ephemeris import HOUSE_SYSTEMS
from astro.chart_svg import render_diamond_svg
from reports.pdf_report import generate_pdf

app = Flask(__name__)
app.secret_key = "motaa-dev-secret-change-me"   # change this if you deploy beyond localhost

HOUSE_SYSTEM_LABELS = [
    ("bhava_madhya", "ဘာဝစနစ် (MOTAA Bhava-Madhya)"),
    ("vequal", "VEqual (Vehlow Equal)"),
    ("equal", "Equal"),
    ("placidus", "Placidus"),
    ("koch", "Koch"),
    ("porphyrius", "Porphyrius"),
    ("regiomontanus", "Regiomontanus"),
    ("campanus", "Campanus"),
]

CITY_PRESETS = {
    "ရန်ကုန် (Yangon)": (16.8409, 96.1735, 6.5),
    "မန္တလေး (Mandalay)": (21.9588, 96.0891, 6.5),
    "နေပြည်တော် (Naypyidaw)": (19.7633, 96.0785, 6.5),
    "တောင်ကြီး (Taunggyi)": (20.7897, 97.0378, 6.5),
    "မြစ်ကြီးနား (Myitkyina)": (25.3833, 97.4000, 6.5),
    "-- ကိုယ်တိုင် Latitude/Longitude ရိုက်ရန် --": (None, None, 6.5),
}


def _chart_to_session_input(form) -> BirthInput:
    hsys = form.get("house_system", "bhava_madhya")
    if hsys not in HOUSE_SYSTEMS:
        hsys = "bhava_madhya"
    return BirthInput(
        name=form.get("name", "").strip() or "အမည်မသိ",
        year=int(form["year"]), month=int(form["month"]), day=int(form["day"]),
        hour=int(form["hour"]), minute=int(form["minute"]), second=int(form.get("second", 0) or 0),
        tz_offset_hours=float(form["tz_offset_hours"]),
        latitude=float(form["latitude"]), longitude=float(form["longitude"]),
        ayanamsa=form.get("ayanamsa", "lahiri"),
        node_mode=form.get("node_mode", "mean"),
        house_system=hsys,
    )


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", cities=CITY_PRESETS, house_systems=HOUSE_SYSTEM_LABELS)


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
    }

    # group grahas by house, for the diamond-chart grid display
    house_planets = {h: [] for h in range(1, 13)}
    for name in GRAHA9:
        gp = chart["positions"][name]
        house_planets[gp.house].append(GRAHA_MM[name])

    diamonds = build_diamond_chart_data(chart)
    chart_svgs = {
        "rashi": render_diamond_svg(diamonds["rashi"], center_title=binput.name,
                                     center_sub=f"ရာသီ ဇယား — {chart['lagna_rashi_mm']} လဂ်"),
        "bhava": render_diamond_svg(diamonds["bhava"], center_title=binput.name,
                                     center_sub="ဘာဝ ဇယား",
                                     position_labels=diamonds["bhava_position_labels"]),
        "navamsa": render_diamond_svg(diamonds["navamsa"], center_title=binput.name,
                                       center_sub="နဝင်း (D9) ဇယား"),
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
