#!/usr/bin/env python3
"""Training-load and injury-risk check from your real Garmin activity history.

Usage:
  load_check.py [--weeks 8] [--today YYYY-MM-DD] [--json]

What it checks (all numbers come from your activities; the rules and their evidence strength are in
../references/evidence-map.md):
  1. SINGLE-SESSION SPIKE (running). Each run vs the longest run of the previous 30 days. A single run more than
     10 % longer was associated with a higher rate of running-related overuse injury in a 5,205-runner cohort
     (Frandsen 2025, Br J Sports Med); the week-to-week ratio showed no relationship. Also prints the longest run
     that stays within +10 % today. For rides the same arithmetic is shown as an EXTRAPOLATION: no cycling study
     was found for it.
  2. WEEKLY VOLUME CHANGE (run + bike + swim minutes, complete weeks). >+20 % in a week or >+30 % over two weeks is flagged
     as a caution. Evidence: observational and mixed (Nielsen 2014, Damsted 2019; a graded "10 % rule" programme did not
     prevent injuries in an RCT, Buist 2008; the acute:chronic workload ratio is not recommended, Impellizzeri 2020).
     Use as a prompt to look closer, never as pass/fail.
  3. REST. Days without any activity in the last 7 / 14 days, and the current run of consecutive training days.
  4. HARD DAYS. Back-to-back days with Garmin aerobic training effect >= 4.0 (Garmin's own metric; a practice rule).
Fixed thresholds below are labelled in code; change them only with a reason.
"""
import argparse
import json
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "rampwise" / "scripts"))
import gcommon  # noqa: E402

SPIKE_PCT = 10.0                  # Frandsen 2025: reference category is "up to 10 % increase"
SPIKE_CATEGORIES = ((100.0, "large spike (>100 %)"), (30.0, "moderate spike (30-100 %)"), (10.0, "small spike (10-30 %)"))
SPIKE_TOL_KM = 0.3                # rounding slack
WEEK_WARN_PCT = 20.0              # practice (observational support: Damsted 2019 found 20-60 % at 21 days)
TWO_WEEK_WARN_PCT = 30.0          # Nielsen 2014: >30 % over two weeks, association not significant overall
SMALL_STEP_MIN = 30               # tiny absolute steps at low volume are not a concern (practice)
HARD_TE = 4.0                     # Garmin aerobic training effect (practice)


def main():
    gcommon.utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--weeks", type=int, default=8)
    ap.add_argument("--today", help="override today's date (testing)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    today = date.fromisoformat(a.today) if a.today else date.today()
    start = gcommon.week_start(today) - timedelta(weeks=a.weeks + 4)
    with gcommon.Garmin() as g:
        acts = [r for r in gcommon.list_activities(g, start, today) if r["date"] <= today]
    if not acts:
        sys.exit("no activities returned")

    out = {"today": str(today), "flags": [], "weeks": [], "notes": []}
    flag = lambda level, msg: out["flags"].append({"level": level, "msg": msg})

    # ---------------- weekly table
    weeks = defaultdict(lambda: {"run_min": 0.0, "run_km": 0.0, "bike_min": 0.0, "bike_km": 0.0, "strength": 0, "other_min": 0.0, "swim_min": 0.0, "swim_km": 0.0, "multi_min": 0.0, "bricks": 0, "long_swim_min": 0.0,
                                 "days": set(), "long_run_km": 0.0, "long_bike_min": 0.0, "sessions": 0})
    for r in acts:
        w = weeks[gcommon.week_start(r["date"])]
        w["days"].add(r["date"])
        w["sessions"] += 1
        if r["sport"] == "run":
            w["run_min"] += r["min"]; w["run_km"] += r["km"]; w["long_run_km"] = max(w["long_run_km"], r["km"])
        elif r["sport"] == "bike":
            w["bike_min"] += r["min"]; w["bike_km"] += r["km"]; w["long_bike_min"] = max(w["long_bike_min"], r["min"])
        elif r["sport"] == "swim":
            w["swim_min"] += r["min"]; w["swim_km"] += r["km"]; w["long_swim_min"] = max(w["long_swim_min"], r["min"])
        elif r["sport"] == "multi":
            w["multi_min"] += r["min"]
        elif r["sport"] == "strength":
            w["strength"] += 1
        else:
            w["other_min"] += r["min"]
    bricks = gcommon.find_bricks(acts)
    for b in bricks:
        weeks[gcommon.week_start(b["date"])]["bricks"] += 1
    this_week = gcommon.week_start(today)
    keys = sorted(k for k in weeks if k >= this_week - timedelta(weeks=a.weeks))
    for k in keys:
        w = weeks[k]
        out["weeks"].append({"week_start": str(k), "run_km": round(w["run_km"], 1), "run_min": round(w["run_min"]),
                             "bike_km": round(w["bike_km"], 1), "bike_min": round(w["bike_min"]),
                             "swim_min": round(w["swim_min"]), "swim_km": round(w["swim_km"], 2), "multisport_min": round(w["multi_min"]), "bricks": w["bricks"],
                             "endurance_min": round(w["run_min"] + w["bike_min"] + w["swim_min"] + w["multi_min"]), "strength_sessions": w["strength"],
                             "training_days": len(w["days"]), "sessions": w["sessions"],
                             "longest_run_km": round(w["long_run_km"], 1), "longest_ride_min": round(w["long_bike_min"]),
                             "complete": k < this_week})

    # ---------------- 1. single-session spikes
    def spike_rows(sport, unit_key):
        rows = [r for r in acts if r["sport"] == sport and r[unit_key] > 0]
        res = []
        for r in rows:
            if (today - r["date"]).days > 21:
                continue
            prev = [p[unit_key] for p in rows if 0 < (r["date"] - p["date"]).days <= 30 or
                    (p["date"] == r["date"] and p["start"] < r["start"])]
            if not prev:
                continue
            ref = max(prev)
            over = r[unit_key] / ref * 100 - 100 if ref else 0
            res.append({"date": str(r["date"]), "value": round(r[unit_key], 1), "ref_30d_longest": round(ref, 1), "over_pct": round(over, 1)})
        return res

    for sport, key, unit in (("run", "km", "km"), ("bike", "min", "min")):
        rows = spike_rows(sport, key)
        out[f"{sport}_spikes"] = rows
        for r in rows:
            tol = SPIKE_TOL_KM if key == "km" else 3
            if r["value"] > r["ref_30d_longest"] * (1 + SPIKE_PCT / 100) + tol:
                cat = next(n for lim, n in SPIKE_CATEGORIES if r["over_pct"] > lim) if r["over_pct"] > 10 else "small spike"
                if sport == "run":
                    flag("WARN", f"run {r['date']}: {r['value']} km was {r['over_pct']:.0f} % longer than the 30-day longest "
                                 f"({r['ref_30d_longest']} km): {cat} in the Frandsen 2025 categories")
                else:
                    flag("NOTE", f"ride {r['date']}: {r['value']:.0f} min was {r['over_pct']:.0f} % longer than the 30-day longest "
                                 f"({r['ref_30d_longest']:.0f} min). No cycling evidence for a 10 % rule; for ultra build-up this is normal "
                                 f"progression, judge by recovery data")
        recent = [r for r in acts if r["sport"] == sport and 0 < (today - r["date"]).days <= 30 and r[key] > 0]
        if recent:
            longest = max(r[key] for r in recent)
            label = "" if sport == "run" else " (extrapolation: not studied in cyclists)"
            out[f"{sport}_next_max"] = round(longest * 1.10, 1)
            out["notes"].append(f"longest {sport} in the last 30 days {longest:.1f} {unit}; staying within +10 % means up to "
                                f"{longest * 1.10:.1f} {unit} next time{label}")

    # ---------------- 2. weekly volume change (complete weeks)
    comp = [w for w in out["weeks"] if w["complete"]]
    if len(comp) >= 2:
        last, prev = comp[-1], comp[-2]
        base = max(prev["endurance_min"], 1)
        ch = (last["endurance_min"] - base) / base * 100
        small = last["endurance_min"] - base <= SMALL_STEP_MIN and base < 240
        out["week_change_pct"] = round(ch, 1)
        if ch > WEEK_WARN_PCT and not small:
            flag("NOTE", f"endurance time {ch:+.0f} % last week ({prev['endurance_min']} -> {last['endurance_min']} min): "
                         f"above the +{WEEK_WARN_PCT:.0f} % caution level (observational evidence, not a rule)")
        if len(comp) >= 3:
            p2 = max(comp[-3]["endurance_min"], 1)
            ch2 = (last["endurance_min"] - p2) / p2 * 100
            out["two_week_change_pct"] = round(ch2, 1)
            if ch2 > TWO_WEEK_WARN_PCT and not small:
                flag("NOTE", f"endurance time {ch2:+.0f} % over two weeks: above +{TWO_WEEK_WARN_PCT:.0f} % "
                             f"(Nielsen 2014 association, not statistically significant overall)")
    else:
        out["notes"].append("fewer than 2 complete weeks of history: weekly progression cannot be judged yet")

    # ---------------- 3. rest
    days_with = {r["date"] for r in acts}
    # today may still be unfinished: count completed days only (yesterday and back), plus today if it already has a session
    end_day = today if today in days_with else today - timedelta(days=1)
    last7 = [end_day - timedelta(days=i) for i in range(7)]
    last14 = [end_day - timedelta(days=i) for i in range(14)]
    rest7 = sum(1 for d in last7 if d not in days_with)
    rest14 = sum(1 for d in last14 if d not in days_with)
    streak = 0
    d = end_day
    while d in days_with:
        streak += 1
        d -= timedelta(days=1)
    out["rest_days_last7"], out["rest_days_last14"], out["consecutive_training_days"] = rest7, rest14, streak
    if rest7 == 0:
        flag("NOTE", f"no rest day in the last 7 days (training streak {streak} days). Your target is 5-6 days a week: "
                     f"plan a full rest or very easy day")
    elif rest14 == 0:
        flag("NOTE", "no rest day in the last 14 days")

    # ---------------- 3b. brick sessions (bike then run): practice limit, evidence in rampwise-planner/references/evidence-map.md (Walsh 2019)
    recent_bricks = [b for b in bricks if 0 <= (today - b["date"]).days <= 6]
    out["bricks_last7"] = len(recent_bricks)
    if len(recent_bricks) > 2:
        flag("NOTE", f"{len(recent_bricks)} brick sessions (bike then run) in the last 7 days: running straight after cycling costs more energy and the training benefit of bricks is unproven "
                     "(Walsh 2019); one a week is the plan's limit (practice)")

    # ---------------- 4. hard days back to back
    hard_days = sorted({r["date"] for r in acts if (r["te_aerobic"] or 0) >= HARD_TE and r["sport"] in ("run", "bike", "swim", "multi")})
    out["hard_days_last14"] = [str(d) for d in hard_days if (today - d).days <= 14]
    for x, y in zip(hard_days, hard_days[1:]):
        if (y - x).days == 1 and (today - y).days <= 14:
            flag("NOTE", f"hard sessions back to back: {x} and {y} (Garmin aerobic training effect >= {HARD_TE})")

    if a.json:
        print(json.dumps(out, ensure_ascii=False, default=str))
        return
    print(f"Load check as of {today}  (history: {len(acts)} activities)\n")
    print(f"{'week of':<11}{'run km':>7}{'run min':>8}{'bike km':>8}{'bike min':>9}{'swim min':>9}{'bricks':>7}{'endur.min':>10}{'strength':>9}{'days':>5}  longest run / ride")
    for w in out["weeks"]:
        tag = "" if w["complete"] else "  (partial)"
        print(f"{w['week_start']:<11}{w['run_km']:>7}{w['run_min']:>8}{w['bike_km']:>8}{w['bike_min']:>9}{w['swim_min']:>9}{w['bricks']:>7}{w['endurance_min']:>10}"
              f"{w['strength_sessions']:>9}{w['training_days']:>5}  {w['longest_run_km']} km / {w['longest_ride_min']} min{tag}")
    print()
    for n in out["notes"]:
        print("info ", n)
    print(f"rest: {rest7} day(s) without activity in the last 7, {rest14} in the last 14; current training streak {streak} day(s)")
    print()
    if not out["flags"]:
        print("OK   no spike, volume or rest concern found in the data")
    for f in out["flags"]:
        print(f"{f['level']:<5}{f['msg']}")


if __name__ == "__main__":
    main()
