#!/usr/bin/env python3
"""Cycling goal check: how far is the user from their ride speed goal (a target speed over a target distance on a flat route)?

Reads rides from Garmin (via the local MCP server), computes moving-average speed per ride, labels a ride "flat" when
climbing is at most `flat_max_m_per_km` (athlete.json; practice cut-off), and shows:
  - the baseline ride and the best flat rides by distance band,
  - speed per heart rate on flat rides of 60+ min (speed / avg HR, higher = more efficient), only as a trend when
    there are enough comparable rides,
  - the remaining gap to the target and the ladder step to aim at next.
Wind, stops and traffic are not in the summary, so speeds are context, not fitness measurements.

  ride_check.py [--days 150] [--json]
"""
import argparse
import json
import statistics
import sys
from datetime import date, timedelta
from pathlib import Path

SKILLS = Path(__file__).resolve().parent.parent.parent
DATA_DIR = Path(__import__("os").environ.get("GARMIN_COACH_DATA") or Path.home() / "garmin-coach-data")   # personal data lives OUTSIDE the plugin folder, so updates never touch it
ATHLETE_JSON = DATA_DIR / "athlete.json"
sys.path.insert(0, str(SKILLS / "garmin-coach" / "scripts"))
import gcommon as gc  # noqa: E402

BANDS = ((20, 40), (40, 70), (70, 100), (100, 400))
MIN_TREND_RIDES = 4          # honest-trend rule shared with aerobic_trend.py


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=int, default=150)
    ap.add_argument("--bike", default=None, help="a bike name from athlete.json bike_log (default: the default bike), or all")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    gc.utf8_stdout()
    ath = json.loads((ATHLETE_JSON).read_text(encoding="utf-8"))
    goal = gc.goal_by(ath, "ride-100k-25", "target_speed_kmh")
    if goal is None:
        print("No ride speed goal in athlete.json (a goal with target_speed_kmh and target_distance_km). Add one with athlete.py goal-add and athlete.py set, then run this again.")
        return
    a.bike = a.bike or (ath.get("bike_log") or {}).get("default_bike") or "main"
    flat_max = goal.get("flat_max_m_per_km", 8.0)
    tgt_v, tgt_km = goal["target_speed_kmh"], goal["target_distance_km"]
    long_km = goal.get("long_ride_km", 50)
    end = date.today()
    with gc.Garmin() as g:
        rides = [r for r in gc.list_activities(g, end - timedelta(days=a.days), end) if r["sport"] == "bike" and r["km"] >= 5 and gc.bike_ok(r["id"], a.bike)]
    rows = []
    for r in sorted(rides, key=lambda x: x["start"]):
        mv = r["km"] / r["moving_min"] * 60 if r["moving_min"] else 0
        gpk = r["gain_m"] / r["km"] if r["km"] else 0
        rows.append({"date": str(r["date"]), "km": round(r["km"], 1), "min": round(r["min"]), "moving_kmh": round(mv, 1),
                     "hr": r["avg_hr"], "m_per_km": round(gpk, 1), "flat": gpk <= flat_max,
                     "speed_per_hr": round(mv / r["avg_hr"], 3) if r["avg_hr"] else None})
    flat = [x for x in rows if x["flat"]]
    result = {"target": {"speed_kmh": tgt_v, "km": tgt_km, "flat_max_m_per_km": flat_max}, "rides": len(rows), "flat_rides": len(flat)}
    longest = max(rows, key=lambda x: x["km"]) if rows else None
    result["longest"] = longest
    bests = {}
    for lo, hi in BANDS:
        c = [x for x in flat if lo <= x["km"] < hi]
        if c:
            bests[f"{lo}-{hi if hi < 400 else '+'} km"] = max(c, key=lambda x: x["moving_kmh"])
    result["best_flat_by_band"] = bests
    comparable = [x for x in flat if x["min"] >= 60 and x["hr"] and x["hr"] <= ath["hr"]["bike_easy_max"]]
    result["comparable_n"] = len(comparable)
    if a.json:
        print(json.dumps(result, indent=1)); return
    print(f"BIKE: {a.bike} (rides count as the default bike unless their id is listed under another bike in athlete.json bike_log.other_bikes)")
    print(f"CYCLING GOAL: {tgt_km:.0f} km at {tgt_v:.0f} km/h average moving speed on a flat route (flat = <= {flat_max:g} m climbing per km, practice cut-off)")
    b = goal.get("baseline")
    if b:
        print(f"Baseline: {b['km']} km at {b['moving_kmh']} km/h moving (HR {b.get('avg_hr')}) on {b['date']}. Target time {tgt_km / tgt_v:.1f} h of moving time vs {b['km'] / b['moving_kmh']:.1f} h then.")
    print(f"\n{len(rows)} rides >= 5 km in {a.days} days, {len(flat)} flat. Best flat ride per distance band (moving km/h):")
    for k, v in bests.items():
        print(f"  {k:10} {v['km']:6.1f} km  {v['moving_kmh']:4.1f} km/h  HR {v['hr']}  {v['m_per_km']} m/km  {v['date']}")
    if longest:
        print(f"Longest ride: {longest['km']} km ({longest['date']}), {longest['moving_kmh']} km/h, {longest['m_per_km']} m/km")
    print(f"\nFlat rides of 60+ min with avg HR <= {ath['hr']['bike_easy_max']} (comparable set): {len(comparable)}")
    if len(comparable) >= MIN_TREND_RIDES:
        rec = comparable[-MIN_TREND_RIDES:]
        old = comparable[:max(1, len(comparable) - MIN_TREND_RIDES)]
        print(f"  speed per HR, earlier rides avg {statistics.mean(x['speed_per_hr'] for x in old):.3f} vs latest {len(rec)} rides {statistics.mean(x['speed_per_hr'] for x in rec):.3f} "
              "(higher = faster per heartbeat; wind and stops add noise)")
    else:
        print(f"  fewer than {MIN_TREND_RIDES}: no trend is readable yet. Ride the same flat route at easy HR to build a comparable set.")
    best100 = [x for x in flat if x["km"] >= 90]
    now = max((x["moving_kmh"] for x in flat if x["km"] >= long_km), default=None)
    print("\nGAP:")
    if now:
        print(f"  best flat ride of {long_km:g}+ km: {now} km/h -> {tgt_v - now:+.1f} km/h to the target ({(tgt_v / now - 1) * 100:.0f} % faster)")
    if b:
        print(f"  flat rides of {tgt_km * 0.9:.0f}+ km on record: {len(best100)}; the baseline ride had {b['moving_kmh']} km/h.")
    print("  Cube law: the air-drag part of power grows with the cube of speed, so a faster average needs far more power; see cycling_power.py (assumed parameters, validated model form).")
    print("  Next ladder step (practice): beat your best flat speed at a distance you already own by about 1 km/h at the same easy HR, then lengthen it.")


if __name__ == "__main__":
    main()
