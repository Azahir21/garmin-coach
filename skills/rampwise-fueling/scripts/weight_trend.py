#!/usr/bin/env python3
"""Log body weight, show the 7-day average trend, and say whether to change calories on a cut or a bulk.

  weight_trend.py add --kg 84.6 [--date 2026-11-24]
  weight_trend.py show
  weight_trend.py advise --goal cut --rate 0.5 --kcal-now 2860 [--symptoms fatigue,illness] [--recovery RED]

Why a trend and not a single weigh-in: day-to-day weight moves with water, food in the gut and salt, so only the average of the week means anything
(Iraki 2019 suggests averaging several weigh-ins per week). The target rate and the size of a change come from Helms 2014 (0.5-1 %/week; a change of
100-200 kcal) and Iraki 2019 (gain 0.25-0.5 %/week); waiting two weeks before changing anything and the exact thresholds are PRACTICE. The body adapts to a long
deficit (Hall 2011), so the estimate from nutrition_targets.py is a starting point and this is the correction. Weights are stored in $RAMPWISE_DATA/weight_log.json.
Stop-and-refer rules for a cut use a symptom list that overlaps the IOC REDs 2023 framework; the symptoms are generic (Jeukendrup 2024) and the counts are practice. Not medical advice.
"""
import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nutri  # noqa: E402

SYMPTOMS = {"fatigue": "persistent fatigue or poor recovery", "illness": "frequent illness", "injury": "a new or repeated injury or stress-fracture signs",
            "mood": "low mood or irritability", "sleep": "poor sleep", "cold": "feeling cold all the time", "libido": "low libido or morning erections gone (men)",
            "menstrual": "missed or irregular periods (women)", "preoccupation": "thinking about food or weight all the time, or fear of eating"}
ALWAYS_STOP = {"preoccupation", "menstrual", "injury"}


def log_path():
    return nutri.data_dir() / "weight_log.json"


def load_log():
    try:
        return json.loads(log_path().read_text(encoding="utf-8")).get("entries", [])
    except Exception:
        return []


def save_log(entries):
    p = log_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"entries": sorted(entries, key=lambda e: e["date"])}, indent=1) + "\n", encoding="utf-8")


def window_mean(entries, end, days=7):
    xs = [e["kg"] for e in entries if end - timedelta(days=days - 1) <= date.fromisoformat(e["date"]) <= end]
    return (sum(xs) / len(xs), len(xs)) if xs else (None, 0)


def weekly_means(entries, today, weeks=4):
    out = []
    for w in range(weeks):
        end = today - timedelta(days=7 * w)
        m, n = window_mean(entries, end)
        out.append({"week_ending": str(end), "mean_kg": None if m is None else round(m, 2), "weigh_ins": n})
    return list(reversed(out))


def advise(entries, goal, rate, kcal_now=None, today=None, symptoms=(), recovery=None, min_weighins=3):
    """Pure function. Returns {"action": hold|raise|lower|stop|more-data, "kcal_change": int, "why": [...]}."""
    today = today or date.today()
    why = []
    sy = [s for s in symptoms if s in SYMPTOMS]
    if goal == "cut" and (any(s in ALWAYS_STOP for s in sy) or len(sy) >= 2):
        return {"action": "stop", "kcal_change": 0, "why": ["Stop the deficit and eat at maintenance; see a doctor or a registered sports dietitian: " + "; ".join(SYMPTOMS[s] for s in sy)
                                                           + " (these overlap with the signs described for low energy availability in the IOC REDs 2023 statement, but they are generic and have many causes, Jeukendrup 2024; the rule of two, or any one of preoccupation, missed periods or injury, is a conservative practice rule)."]}
    if goal == "cut" and recovery == "RED":
        return {"action": "hold", "kcal_change": 0, "why": ["Recovery is RED: hold the deficit and do not deepen it this week (practice)."]}
    m0, n0 = window_mean(entries, today)
    m1, n1 = window_mean(entries, today - timedelta(days=7))
    m2, n2 = window_mean(entries, today - timedelta(days=14))
    if n0 < min_weighins or n1 < min_weighins:
        return {"action": "more-data", "kcal_change": 0, "why": [f"Need at least {min_weighins} weigh-ins in each of the last two weeks (have {n0} and {n1}). Weigh at the same time, after the toilet, before eating."]}
    r1 = (m0 - m1) / m1 * 100.0
    r2 = (m1 - m2) / m2 * 100.0 if n2 >= min_weighins else None
    why.append(f"7-day average {m0:.1f} kg, a week ago {m1:.1f} kg: change {r1:+.2f} % per week" + (f" (week before: {r2:+.2f} %)" if r2 is not None else "") + ".")
    if goal == "cut":
        target = -abs(rate if rate is not None else 0.5)
        if r1 < -1.0:
            return {"action": "raise", "kcal_change": +150, "why": why + ["Losing faster than 1 % per week: add about 150 kcal a day, mostly carbohydrate (Helms 2014 uses 100-200 kcal steps; faster loss costs lean mass in Garthe 2011)."]}
        slow = r1 > target + 0.25 and (r2 is None or r2 > target + 0.25)
        if slow:
            return {"action": "lower", "kcal_change": -100, "why": why + [f"Losing slower than the {abs(target):.2f} % per week planned for two weeks: first check portions, weighing and weekend eating; if those are fine, take off about 100 kcal a day (Helms 2014: 100-200 kcal steps). Do not go under the resting-energy floor in nutrition_targets.py."]}
        return {"action": "hold", "kcal_change": 0, "why": why + ["On track for the planned rate: no change."]}
    if goal == "bulk":
        target = abs(rate if rate is not None else 0.35)
        if r1 > 0.5:
            return {"action": "lower", "kcal_change": -150, "why": why + ["Gaining faster than 0.5 % per week: take off about 100-150 kcal a day (Iraki 2019: 0.25-0.5 % per week limits fat gain)."]}
        if r1 < target - 0.2 and (r2 is None or r2 < target - 0.2):
            return {"action": "raise", "kcal_change": +150, "why": why + ["Gaining slower than planned for two weeks: add about 150 kcal a day. Also watch waist or body fat; weight alone cannot tell muscle from fat (Slater 2019: the best surplus is unknown)."]}
        return {"action": "hold", "kcal_change": 0, "why": why + ["On track: no change."]}
    if abs(r1) > 0.5:
        return {"action": "raise" if r1 < 0 else "lower", "kcal_change": 150 if r1 < 0 else -150, "why": why + ["Weight is moving more than 0.5 % a week at maintenance: adjust by about 150 kcal a day."]}
    return {"action": "hold", "kcal_change": 0, "why": why + ["Stable."]}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a_ = sub.add_parser("add")
    a_.add_argument("--kg", type=float, required=True)
    a_.add_argument("--date")
    sub.add_parser("show")
    v = sub.add_parser("advise")
    v.add_argument("--goal", choices=("cut", "maintain", "bulk"))
    v.add_argument("--rate", type=float)
    v.add_argument("--kcal-now", type=float)
    v.add_argument("--symptoms", default="", help="comma list: " + ",".join(SYMPTOMS))
    v.add_argument("--recovery", choices=("GREEN", "AMBER", "RED"))
    v.add_argument("--today")
    a = ap.parse_args(argv)
    ent = load_log()
    if a.cmd == "add":
        d = a.date or str(date.today())
        ent = [e for e in ent if e["date"] != d] + [{"date": d, "kg": a.kg}]
        save_log(ent)
        print(f"logged {a.kg:g} kg on {d} ({len(ent)} entries)")
        return 0
    today = date.today()
    if a.cmd == "show":
        for w in weekly_means(ent, today):
            print(f"week ending {w['week_ending']}: " + (f"{w['mean_kg']} kg average from {w['weigh_ins']} weigh-ins" if w["mean_kg"] else "no weigh-ins"))
        return 0
    nut = nutri.json.loads((nutri.data_dir() / "athlete.json").read_text(encoding="utf-8")).get("nutrition", {}) if (nutri.data_dir() / "athlete.json").exists() else {}
    goal = a.goal or nut.get("goal") or "maintain"
    rate = a.rate if a.rate is not None else nut.get("rate_pct")
    r = advise(ent, goal, rate, a.kcal_now, date.fromisoformat(a.today) if a.today else today, [s for s in a.symptoms.split(",") if s], a.recovery)
    print("ACTION:", r["action"].upper() + (f" ({r['kcal_change']:+d} kcal/day" + (f", new target about {a.kcal_now + r['kcal_change']:.0f}" if a.kcal_now else "") + ")" if r["kcal_change"] else ""))
    for w in r["why"]:
        print(" -", w)
    print("Not medical advice. Rules: the changes are research-informed steps, the two-week wait is practice.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
