#!/usr/bin/env python3
"""Build the public sample report (docs/sample/index.html and docs/examples/) from SYNTHETIC data, so the demo contains nobody's health data.

  python tools/make_sample_report.py
"""
import random
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for sub in ("rampwise", "rampwise-analyze", "rampwise-report", "rampwise-adapt", "rampwise-planner"):
    sys.path.insert(0, str(ROOT / "skills" / sub / "scripts"))
import analysis  # noqa: E402
import report as rp  # noqa: E402

random.seed(11)
today = date(2026, 11, 15)
acts, n = [], 0
for k in range(0, 110):
    d = today - timedelta(days=k)
    if random.random() < 0.28:
        continue
    sport = random.choice(["run", "run", "bike", "strength"])
    mins = random.uniform(35, 75) if sport != "bike" else random.uniform(60, 130)
    gain = (110 - k) / 110.0                         # a gentle improvement over the 110 days
    if sport == "run":
        speed = 9.2 + 1.1 * gain + random.uniform(-0.5, 0.5)       # km/h, about 6:30 to 5:40 per km
    elif sport == "bike":
        speed = 20.5 + 3.0 * gain + random.uniform(-1.2, 1.2)      # km/h
    else:
        speed = 0
    km = speed * mins * 0.95 / 60
    n += 1
    acts.append({"id": n, "name": f"{sport} {n}", "sport": sport, "date": d, "start": f"{d}T07:00:00", "km": km, "min": mins, "moving_min": mins * 0.95,
                 "avg_hr": 138 + random.randint(-6, 8), "gain_m": random.randint(10, 160), "te_aerobic": random.choice([2.4, 2.9, 3.2, 4.1])})
rows = [{"date": str(today - timedelta(days=k)), "hrv": 62 + random.randint(-9, 9), "rhr": 51 + random.randint(-2, 4), "sleep_h": round(random.uniform(5.6, 8.4), 1)} for k in range(110)]
ath = {"goals": [{"title": "Ride 60 km at 25 km/h", "target_speed_kmh": 25.0, "target_distance_km": 60},
                 {"title": "Run 10 km in 55:00", "target_pace_s_per_km": 330},
                 {"title": "Train 5 days a week", "track": {"metric": "training_days_per_week", "target": 5, "unit": "days"}}],
       "preferences": {"units": {"run": "pace", "bike": "kmh"}}, "injuries": [], "checkins": []}
plan = {"sessions": [{"date": str(today - timedelta(days=k)), "sport": "run", "title": "Easy run", "minutes": 40} for k in range(1, 12, 2)]
        + [{"date": str(today + timedelta(days=k)), "sport": s, "title": t, "minutes": m} for k, s, t, m in ((1, "bike", "Easy ride", 70), (2, "run", "Tempo run", 45), (4, "run", "Long run", 80), (5, "strength", "Strength", 40))]}
ready = {"verdict": "GREEN", "flags": [], "hrv": 64, "hrv7": 63, "band_lo": 56, "band_hi": 70, "hrv_state": "inside", "rhr": 51, "rhr7": 52, "sleep_h": 7.4}
inj = analysis.injury_flags(acts, rows, ath, today, ready)
cmp = analysis.compare(acts, today)
R = rp.build("weekly", today, acts, rows, ath, plan, None, ready, inj, cmp, None, None)
R["blocks"].insert(1, ("p", "SAMPLE with synthetic data (random numbers, nobody's health data). Real reports are made on your own computer from your own Garmin data."))
out = ROOT / "docs" / "examples" / "weekly"
rp.write_report(R, out, "both")
html = (out / "report.html").read_text(encoding="utf-8")
import re
html = re.sub(r"<title>.*?</title>", "<title>Rampwise: sample weekly report (AI endurance coach for Garmin data)</title>"
              '<meta name="description" content="A sample weekly report from Rampwise, a free open-source AI endurance coach that reads your own Garmin data: recovery, week-over-week comparison, injury-risk watch, plan adherence and goal meters. Synthetic data.">', html, count=1, flags=re.S)
html = html.replace("<main>", '<main><p><a href="../">Rampwise home</a> | <a href="https://github.com/Azahir21/rampwise">Rampwise on GitHub</a> (free, Apache-2.0). Independent project, not affiliated with Garmin Ltd.</p>', 1)
(ROOT / "docs" / "sample").mkdir(exist_ok=True)
(ROOT / "docs" / "sample" / "index.html").write_text(html, encoding="utf-8")
latest = out.parent / "latest-weekly.html"
if latest.exists():
    latest.unlink()
import brand_pages                                  # logo favicon on every page, also after regenerating
brand_pages.run()
print("wrote", ROOT / "docs" / "sample" / "index.html", "and", out)
