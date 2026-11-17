#!/usr/bin/env python3
"""Analyse one activity (the latest, or one you name) and compare it with the last similar one.

  latest_activity.py [--id ACTIVITY_ID] [--days 3] [--json]

Runs and rides: the aerobic analysis from rampwise-aerobic-base (heart-rate drift, steadiness, time in your heart-rate zones, efficiency) and a
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
sys.path.insert(0, str(SKILLS / "rampwise" / "scripts"))
sys.path.insert(0, str(SKILLS / "rampwise-aerobic-base" / "scripts"))
sys.path.insert(0, str(SKILLS / "rampwise-strength" / "scripts"))
sys.path.insert(0, str(HERE))
import gcommon as gc  # noqa: E402
import analysis  # noqa: E402


def similar(acts, target, tol=0.35):
    """The most recent earlier activity of the same sport with a similar duration."""
    c = [a for a in acts if a["sport"] == target["sport"] and a["id"] != target["id"] and a["start"] < target["start"] and abs(a["min"] / target["min"] - 1) <= tol]
    return max(c, key=lambda a: a["start"]) if c else None


def swim_pace(speed_kmh):
    if not speed_kmh:
        return "-"
    s = 360.0 / speed_kmh
    return f"{int(s // 60)}:{int(s % 60):02d}/100 m"


def brick_analysis(acts, target):
    """If the target is part of a brick (bike then run within 45 minutes), compare the run with the last similar run that was NOT after cycling: pace and heart rate.
    Running after cycling costs more energy (Millet and Vleck 2000; Walsh 2019); one session says little, so the numbers are shown, not judged."""
    bricks = gc.find_bricks(acts)
    mine = next((b for b in bricks if b["kind"] == "bike-run" and target["id"] in (b["bike"]["id"], b["run"]["id"])), None)
    if not mine:
        return None
    brun, bike = mine["run"], mine["bike"]
    in_brick = {b["run"]["id"] for b in bricks if b["kind"] == "bike-run"}
    base = [x for x in acts if x["sport"] == "run" and x["id"] not in in_brick and x["start"] < brun["start"] and brun["min"] and abs(x["min"] / brun["min"] - 1) <= 0.5]
    prev = max(base, key=lambda x: x["start"]) if base else None

    def pace(x):
        mov = x.get("moving_min") or x["min"]
        return mov * 60.0 / x["km"] if x["km"] > 0 and mov > 0 else None
    out = {"gap_min": mine["gap_min"], "bike": {"id": bike["id"], "minutes": round(bike["min"]), "km": round(bike["km"], 1), "avg_hr": bike.get("avg_hr")},
           "run": {"id": brun["id"], "minutes": round(brun["min"]), "km": round(brun["km"], 2), "avg_hr": brun.get("avg_hr"), "pace_s_per_km": round(pace(brun)) if pace(brun) else None}}
    if prev and pace(prev) and pace(brun):
        out["vs_standalone_run"] = {"date": str(prev["date"]), "pace_s_per_km": round(pace(prev)), "avg_hr": prev.get("avg_hr"), "pace_diff_s_per_km": round(pace(brun) - pace(prev)),
                                    "hr_diff_bpm": (brun["avg_hr"] - prev["avg_hr"]) if brun.get("avg_hr") and prev.get("avg_hr") else None}
    return out


def side_by_side(a, b):
    def spd(x):
        mov = x.get("moving_min") or x["min"]
        return x["km"] / (mov / 60.0) if x["km"] > 0 and mov > 0 else None
    rows = {"date": (str(a["date"]), str(b["date"])), "minutes": (round(a["min"]), round(b["min"])), "km": (round(a["km"], 1), round(b["km"], 1)),
            "avg_hr": (a.get("avg_hr"), b.get("avg_hr")), "climb_m": (round(a.get("gain_m") or 0), round(b.get("gain_m") or 0))}
    sa, sb = spd(a), spd(b)
    if a["sport"] == "run":
        rows["pace"] = (analysis.pace_str(sa), analysis.pace_str(sb))
    elif a["sport"] == "swim":
        rows["pace_100m"] = (swim_pace(sa), swim_pace(sb))
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
        out["brick"] = brick_analysis(acts, target)
        prev = similar(acts, target)
        if prev:
            out["compare_with"] = {"id": prev["id"], "name": prev["name"], "table": side_by_side(target, prev)}
        if target["sport"] in ("run", "bike", "swim", "multi"):
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
    if out.get("brick"):
        b = out["brick"]
        print(f"\nBRICK: bike {b['bike']['minutes']} min ({b['bike']['km']} km, HR {b['bike']['avg_hr']}), then run {b['run']['minutes']} min ({b['run']['km']} km, HR {b['run']['avg_hr']}) after {b['gap_min']} min.")
        v = b.get("vs_standalone_run")
        if v:
            print(f"  Against your last run not after cycling ({v['date']}): pace {v['pace_diff_s_per_km']:+d} s/km, heart rate {v['hr_diff_bpm'] if v['hr_diff_bpm'] is not None else 'n/a'} bpm. "
                  "Running after cycling costs more; one session proves little (route, weather, effort).")
        else:
            print("  No earlier run that was not after cycling to compare with.")
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
