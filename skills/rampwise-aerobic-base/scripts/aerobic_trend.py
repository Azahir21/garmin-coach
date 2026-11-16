#!/usr/bin/env python3
"""Aerobic trend over the last weeks: one row per steady-ish session (EF, decoupling, easy share, weather).

Usage:
  aerobic_trend.py [--days 56] [--sport run|bike|all] [--min-min 40] [--max 20] [--weather-approved] [--json]

Downloads the FIT file of each qualifying activity (cached), analyses it with analyze_activity.py, optionally adds
the observed weather (opt-in: coordinates + dates go to open-meteo.com), and prints a table. Only sessions marked
reliable are used for the trend line, and only against sessions in similar weather when weather is available.
The honest reading: with fewer than 4 comparable sessions there is NO trend yet, only data points.
"""
import argparse
import json
import statistics
import sys
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "rampwise" / "scripts"))
sys.path.insert(0, str(HERE.parents[1] / "rampwise-heat-weather" / "scripts"))

import analyze_activity as A  # noqa: E402
import gcommon  # noqa: E402


def main():
    gcommon.utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=int, default=56)
    ap.add_argument("--sport", choices=("run", "bike", "all"), default="all")
    ap.add_argument("--min-min", type=float, default=40.0, help="minimum session length in minutes")
    ap.add_argument("--max", type=int, default=20, help="analyse at most this many (newest first)")
    ap.add_argument("--weather-approved", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    end = date.today()
    start = end - timedelta(days=a.days)
    with gcommon.Garmin() as g:
        acts = [r for r in gcommon.list_activities(g, start, end)
                if r["sport"] in (("run", "bike") if a.sport == "all" else (a.sport,)) and r["min"] >= a.min_min]
        acts = acts[-a.max:]
        zones = None
        try:
            zones = g.call("garmin_get_heart_rate_zones")
        except gcommon.GarminError:
            pass
        rows = []
        for act in acts:
            try:
                r = A.analyze(g, act["id"], zones)
            except Exception as e:                       # one bad file must not stop the table
                r = {"id": act["id"], "sport": act["sport"], "start": str(act["start"]), "error": str(e)[:120]}
            if a.weather_approved and act["lat"] is not None and not r.get("error"):
                import observed
                c = observed.conditions(act["lat"], act["lon"], act["start"], act["min"])
                if not c.get("error"):
                    r["weather"] = {k: c[k] for k in ("temp_c", "dew_c", "humidity_pct", "wind_kmh", "rain_mm")}
                    r["weather_bin"] = observed.comparability_key(c)
            rows.append(r)

    if a.json:
        print(json.dumps(rows, ensure_ascii=False, default=str))
        return

    print(f"{'date':<11}{'sport':<6}{'min':>5}{'avgHR':>6}{'EF':>7}{'decoup%':>9}{'easy%':>6}  {'temp/dew':<10}notes")
    for r in rows:
        if r.get("error"):
            print(f"{r['start'][:10]:<11}{r['sport']:<6}  skipped: {r['error']}")
            continue
        z = r.get("zones")
        easy = ""
        if z:
            m = z["minutes_below_z1_z1_z2_z3_z4_z5"]
            easy = f"{(m[0] + m[1] + m[2]) / (sum(m) or 1) * 100:.0f}"
        w = r.get("weather")
        wtxt = f"{w['temp_c']:.0f}/{w['dew_c']:.0f}C" if w else "-"
        dec = f"{r['decoupling_pct']:+.1f}" if "decoupling_pct" in r else "-"
        note = "ok" if r.get("reliable") else "unreliable: " + "; ".join(f.split(":")[0] for f in r.get("flags", []))
        print(f"{r['start'][:10]:<11}{r['sport']:<6}{r['moving_min']:>5}{(r['avg_hr'] or 0):>6.0f}{r['ef']:>7.3f}{dec:>9}{easy:>6}  {wtxt:<10}{note}")

    print()
    for sport in ("run", "bike"):
        good = [r for r in rows if r.get("reliable") and r["sport"] == sport]
        if not good:
            if any(r["sport"] == sport for r in rows):
                print(f"{sport}: no reliable steady session in this window, so no aerobic trend can be read yet "
                      f"(unsteady terrain, intervals, or too short). Plan 1 steady 60-90 min session on flat terrain at a fixed HR.")
            continue
        if len(good) < 4:
            print(f"{sport}: {len(good)} reliable session(s): data points only, not a trend (need 4+ in similar weather).")
            continue
        half = len(good) // 2
        first, last = good[:half], good[-half:]
        d_ef = statistics.median(r["ef"] for r in last) / statistics.median(r["ef"] for r in first) * 100 - 100
        d_dec = statistics.median(r["decoupling_pct"] for r in last) - statistics.median(r["decoupling_pct"] for r in first)
        print(f"{sport}: EF median {d_ef:+.1f} % (later vs earlier half, n={len(good)}); decoupling median {d_dec:+.1f} points. "
              f"Check weather and terrain of those sessions before calling it fitness.")


if __name__ == "__main__":
    main()
