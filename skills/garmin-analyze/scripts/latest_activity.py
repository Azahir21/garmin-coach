#!/usr/bin/env python3
"""Analyse one activity (the latest, or one you name) and compare it with the last similar one.

  latest_activity.py [--id ACTIVITY_ID] [--days 3] [--json]

Runs and rides: the aerobic analysis from garmin-aerobic-base (heart-rate drift, steadiness, time in your heart-rate zones, efficiency) and a
side-by-side with the previous similar activity (same sport, duration within +/- 35 %): distance, duration, average heart rate, speed or pace,
climb, drift. Strength: the sets, reps and weights logged on the watch against the last session that shared exercises. If there is no activity
in the last --days, it says so (use week_compare.py to compare weeks without one).
Differences between two activities depend on route, weather and what you intended; the script prints numbers, you and the coach read them.
"""
import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILLS = HERE.parent.parent
sys.path.insert(0, str(SKILLS / "garmin-coach" / "scripts"))
sys.path.insert(0, str(SKILLS / "garmin-aerobic-base" / "scripts"))
sys.path.insert(0, str(SKILLS / "garmin-strength" / "scripts"))
sys.path.insert(0, str(HERE))
import gcommon as gc  # noqa: E402
import analysis  # noqa: E402


def similar(acts, target, tol=0.35):
    """The most recent earlier activity of the same sport with a similar duration."""
    c = [a for a in acts if a["sport"] == target["sport"] and a["id"] != target["id"] and a["start"] < target["start"] and abs(a["min"] / target["min"] - 1) <= tol]
    return max(c, key=lambda a: a["start"]) if c else None


def side_by_side(a, b):
    def spd(x):
        mov = x.get("moving_min") or x["min"]
        return x["km"] / (mov / 60.0) if x["km"] > 0 and mov > 0 else None
    rows = {"date": (str(a["date"]), str(b["date"])), "minutes": (round(a["min"]), round(b["min"])), "km": (round(a["km"], 1), round(b["km"], 1)),
            "avg_hr": (a.get("avg_hr"), b.get("avg_hr")), "climb_m": (round(a.get("gain_m") or 0), round(b.get("gain_m") or 0))}
    sa, sb = spd(a), spd(b)
    if a["sport"] == "run":
        rows["pace"] = (analysis.pace_str(sa), analysis.pace_str(sb))
    else:
        rows["speed_kmh"] = (round(sa, 1) if sa else None, round(sb, 1) if sb else None)
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--id", type=int)
    ap.add_argument("--days", type=int, default=3)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    gc.utf8_stdout()
    today = date.today()
    out = {"today": str(today)}
    with gc.Garmin() as g:
        acts = gc.list_activities(g, today - timedelta(days=75), today)
        target = next((x for x in acts if x["id"] == a.id), None) if a.id else None
        if a.id and not target:
            sys.exit(f"activity {a.id} not found in the last 75 days")
        if not target:
            recent = [x for x in acts if (today - x["date"]).days <= a.days]
            if not recent:
                print(f"No activity in the last {a.days} days. Use week_compare.py to compare this week with last week anyway.")
                return
            target = max(recent, key=lambda x: x["start"])
        out["activity"] = {"id": target["id"], "name": target["name"], "sport": target["sport"], "date": str(target["date"]), "minutes": round(target["min"]), "km": round(target["km"], 1), "avg_hr": target.get("avg_hr")}
        prev = similar(acts, target)
        if prev:
            out["compare_with"] = {"id": prev["id"], "name": prev["name"], "table": side_by_side(target, prev)}
        if target["sport"] in ("run", "bike"):
            import analyze_activity  # noqa: E402
            try:
                zones = g.call("garmin_get_heart_rate_zones")
            except gc.GarminError:
                zones = None
            out["aerobic"] = analyze_activity.analyze(g, target["id"], zones)
        elif target["sport"] == "strength":
            import strength_history as sh  # noqa: E402
            hist = sh.load_history(g, 120)
            cur = next((s for s in hist if s["date"] == str(target["date"])), None)
            others = [s for s in hist if cur and s["date"] < cur["date"] and {tuple(b["key"]) for b in s["exercises"]} & {tuple(b["key"]) for b in cur["exercises"]}]
            out["strength"] = {"session": cur, "last_with_shared_exercises": others[-1] if others else None}
    if a.json:
        print(json.dumps(out, indent=1, default=str))
        return
    t = out["activity"]
    print(f"ACTIVITY {t['date']}: {t['name']} ({t['sport']}), {t['minutes']} min, {t['km']} km, avg HR {t['avg_hr']}")
    if "aerobic" in out:
        import analyze_activity  # noqa: E402
        analyze_activity.print_report(out["aerobic"])
    if "strength" in out and out["strength"]["session"]:
        s, p = out["strength"]["session"], out["strength"]["last_with_shared_exercises"]
        for b in s["exercises"]:
            sets = ", ".join(f"{x['reps']}x{x['kg']:g}kg" if x["kg"] else f"{x['reps']}x bodyweight" for x in b["sets"])
            print(f"  {b['key'][1] or b['key'][0]}: {sets}")
        if p:
            print(f"Previous session with shared exercises: {p['date']} ({p['name']})")
    if "compare_with" in out:
        c = out["compare_with"]
        print(f"\nCOMPARED WITH THE LAST SIMILAR ACTIVITY ({c['name']}):")
        for k, (now, before) in c["table"].items():
            print(f"  {k:10} now {now}   before {before}")
    else:
        print("\nNo earlier similar activity (same sport, similar duration) in the last 75 days to compare with.")


if __name__ == "__main__":
    main()
