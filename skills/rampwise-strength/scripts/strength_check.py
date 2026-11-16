#!/usr/bin/env python3
"""Strength-session timing and frequency check from your real Garmin activities.

Usage:
  strength_check.py [--weeks 8] [--json]

Reports
  * strength sessions per week and their length;
  * for each strength session on a day with an endurance session: the order and the gap in hours;
    a gap under 3 h is flagged. Evidence: in a meta-analysis of 43 studies (Schumann 2022) the loss of explosive
    strength from concurrent training was larger when both were done in the same session (<= 20 min apart) and not
    significant when separated by at least 3 h; Blagrove 2018 (review of strength training in distance runners)
    recommends more than 3 h after high-intensity running. Cycling vs running made no significant difference.
  * strength sessions that END within 18 h before a KEY endurance session (run >= 60 min or ride >= 120 min):
    shown as context only. No verified paper in this library quantifies next-day effects; it is a practice-level heads-up.
Garmin records strength sessions as duration and heart rate only, so load (sets x reps x kg) is not available here.
"""
import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "rampwise" / "scripts"))
import gcommon  # noqa: E402

MIN_GAP_H = 3.0                 # Schumann 2022 subgroup (>= 3 h); Blagrove 2018 recommendation (> 3 h)
KEY_RUN_MIN, KEY_BIKE_MIN = 60, 120   # practice definitions of a "key" endurance session
PRE_KEY_WINDOW_H = 18


def main():
    gcommon.utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--weeks", type=int, default=8)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    today = date.today()
    start = gcommon.week_start(today) - timedelta(weeks=a.weeks)
    with gcommon.Garmin() as g:
        acts = gcommon.list_activities(g, start, today)
    strength = [r for r in acts if r["sport"] == "strength"]
    endur = [r for r in acts if r["sport"] in ("run", "bike")]
    out = {"weeks": [], "same_day": [], "pre_key": [], "flags": []}

    byweek = {}
    for r in strength:
        w = byweek.setdefault(gcommon.week_start(r["date"]), {"n": 0, "min": 0.0})
        w["n"] += 1
        w["min"] += r["min"]
    k = gcommon.week_start(start)
    while k <= gcommon.week_start(today):
        w = byweek.get(k, {"n": 0, "min": 0.0})
        out["weeks"].append({"week_start": str(k), "sessions": w["n"], "minutes": round(w["min"])})
        k += timedelta(days=7)

    for s in strength:
        for e in endur:
            if e["date"] != s["date"]:
                continue
            if s["start"] >= e["end"]:
                order, gap = "endurance -> strength", (s["start"] - e["end"]).total_seconds() / 3600
            elif e["start"] >= s["end"]:
                order, gap = "strength -> endurance", (e["start"] - s["end"]).total_seconds() / 3600
            else:
                order, gap = "overlap", 0.0
            row = {"date": str(s["date"]), "strength_start": s["start"].strftime("%H:%M"), "strength_min": round(s["min"]),
                   "endurance": f"{e['sport']} {e['min']:.0f} min {e['start']:%H:%M}", "order": order, "gap_h": round(gap, 1),
                   "endurance_avg_hr": e["avg_hr"]}
            out["same_day"].append(row)
            if gap < MIN_GAP_H:
                out["flags"].append(f"{row['date']}: {order}, only {gap:.1f} h apart (Schumann 2022: the explosive-strength penalty was larger "
                                    f"in the same session; with >= 3 h between sessions it was not significant)")

    for s in strength:
        for e in endur:
            key = (e["sport"] == "run" and e["min"] >= KEY_RUN_MIN) or (e["sport"] == "bike" and e["min"] >= KEY_BIKE_MIN)
            if not key:
                continue
            gap = (e["start"] - s["end"]).total_seconds() / 3600
            if 0 < gap <= PRE_KEY_WINDOW_H:
                out["pre_key"].append({"strength": f"{s['date']} {s['start']:%H:%M} ({s['min']:.0f} min)",
                                       "key_session": f"{e['sport']} {e['min']:.0f} min on {e['date']} {e['start']:%H:%M}", "gap_h": round(gap, 1)})

    if a.json:
        print(json.dumps(out, ensure_ascii=False, default=str))
        return
    print(f"Strength check (last {a.weeks} weeks, {len(strength)} strength sessions, {len(endur)} run/bike sessions)\n")
    print(f"{'week of':<11}{'sessions':>9}{'minutes':>9}")
    for w in out["weeks"]:
        print(f"{w['week_start']:<11}{w['sessions']:>9}{w['minutes']:>9}")
    print("\nSame-day pairs (strength with an endurance session):")
    if not out["same_day"]:
        print("  none")
    for r in out["same_day"]:
        print(f"  {r['date']}  {r['order']:<22} gap {r['gap_h']:>4} h   strength {r['strength_start']} ({r['strength_min']} min) | {r['endurance']}")
    if out["pre_key"]:
        print(f"\nStrength finishing within {PRE_KEY_WINDOW_H} h before a key endurance session (context only; practice-level, no verified paper):")
        for r in out["pre_key"]:
            print(f"  {r['strength']}  ->  {r['key_session']}  ({r['gap_h']} h later)")
    print()
    if not out["flags"]:
        print("OK   no strength session was squeezed against an endurance session (< 3 h)")
    for f in out["flags"]:
        print("WARN", f)
    print("\nNote: Garmin gives duration and HR for strength sessions, not exercises, sets or loads. Ask the athlete for those.")


if __name__ == "__main__":
    main()
