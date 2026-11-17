#!/usr/bin/env python3
"""Week-over-week comparison of your training, on any day (with or without an activity today).

  week_compare.py [--today YYYY-MM-DD] [--json]

Compares (1) the last 7 days with the 7 days before, (2) the calendar week so far with the same days last week, (3) the calendar week so far with the last
full week. Per sport: sessions, minutes, km, climbing, average heart rate, average speed or pace, longest session, hard sessions. Also the average of
HRV, resting heart rate and sleep for the two rolling weeks. The numbers are plain differences; they do not say a change is good or bad. Use
injury_watch.py for risk flags and rampwise-report for the figures.
"""
import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILLS = HERE.parent.parent
sys.path.insert(0, str(SKILLS / "rampwise" / "scripts"))
sys.path.insert(0, str(SKILLS / "rampwise-recovery" / "scripts"))
sys.path.insert(0, str(HERE))
import gcommon as gc  # noqa: E402
import analysis  # noqa: E402


def collect(today):
    """Activities (6 weeks) and readiness rows (4 weeks) for the comparison."""
    import readiness_check  # noqa: E402
    with gc.Garmin() as g:
        acts = [a for a in gc.list_activities(g, today - timedelta(days=45), today) if a["date"] <= today]
        rows, _ = readiness_check.build_rows(g, today - timedelta(days=30), today)
    return acts, rows


def build(acts, rows, today, units=None):
    cmp = analysis.compare(acts, today)
    r = cmp["rolling"]
    cmp["recovery"] = {"this": analysis.recovery_means(rows, date.fromisoformat(r["this"]["from"]), today),
                       "before": analysis.recovery_means(rows, date.fromisoformat(r["before"]["from"]), date.fromisoformat(r["before"]["to"]))}
    cmp["insights"] = analysis.insights(cmp, units)
    return cmp


def print_text(c):
    def block(title, key):
        x = c[key]
        print(f"\n{title}: {x['this']['from']} to {x['this']['to']}  vs  {x['before']['from']} to {x['before']['to']}")
        print(f"  {'':10}{'now':>10}{'before':>10}{'change':>10}")
        for sport, unit in (("run", "min"), ("bike", "min"), ("swim", "min"), ("strength", "sessions")):
            k = "minutes" if sport != "strength" else "sessions"
            a, b, d = x["this"][sport][k], x["before"][sport][k], x["delta"][sport][k]
            pct = f"{d['pct']:+.0f}%" if d["pct"] is not None else (f"{d['abs']:+g}" if d["abs"] is not None else "-")
            print(f"  {sport + ' ' + unit:10}{a:>10}{b:>10}{pct:>10}")
        for sport in ("run", "bike"):
            a, b = x["this"][sport], x["before"][sport]
            if a["km"] or b["km"]:
                print(f"  {sport + ' km':10}{a['km']:>10}{b['km']:>10}")
        print(f"  {'training days':10}{x['this']['training_days']:>10}{x['before']['training_days']:>10}")
    block("LAST 7 DAYS vs the 7 days before", "rolling")
    ws = analysis.week_start(date.fromisoformat(c["today"]))
    if (date.fromisoformat(c["today"]) - ws).days >= 2:
        block("THIS CALENDAR WEEK so far vs the same days last week", "calendar_same_days")
        block("THIS CALENDAR WEEK so far vs the last full week", "calendar_vs_last_full_week")
    else:
        print("\n(Calendar-week comparisons start on Wednesday: with one or two days they are not meaningful. The rolling comparison above always works.)")
    rv = c["recovery"]
    print("\nRECOVERY (rolling weeks): " + "; ".join(f"{k} {rv['this'][k]} vs {rv['before'][k]}" for k in ("hrv", "rhr", "sleep_h") if rv["this"].get(k) is not None))
    print("\nWHAT CHANGED:")
    for s in c["insights"]:
        print("  - " + s)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--today")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    gc.utf8_stdout()
    today = date.fromisoformat(a.today) if a.today else date.today()
    acts, rows = collect(today)
    try:
        units = (json.loads(gc.ATHLETE_PATH.read_text(encoding="utf-8")).get("preferences") or {}).get("units")
    except Exception:
        units = None
    res = build(acts, rows, today, units)
    print(json.dumps(res, indent=1, default=str)) if a.json else print_text(res)


if __name__ == "__main__":
    main()
