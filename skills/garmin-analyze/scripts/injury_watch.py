#!/usr/bin/env python3
"""Injury-risk watch: flags from your load, recovery, the user's injury list and pain check-ins. Not a diagnosis.

  injury_watch.py [--today YYYY-MM-DD] [--json]

Looks at: single-run spikes, week-over-week jumps, rest days, back-to-back hard days, low recovery (readiness, short sleep), falling run efficiency,
injuries recorded in athlete.json and pain check-ins of the last 3 days (record one with `athlete.py check-in`). Every flag has an evidence label
(research / practice / gap) and a suggested action. The output also lists the questions the coach should ask: the user's own report is the strongest signal.
"""
import argparse
import json
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILLS = HERE.parent.parent
sys.path.insert(0, str(SKILLS / "garmin-coach" / "scripts"))
sys.path.insert(0, str(SKILLS / "garmin-recovery" / "scripts"))
sys.path.insert(0, str(HERE))
import gcommon as gc  # noqa: E402
import analysis  # noqa: E402


def readiness_json():
    """Today's readiness from the recovery skill (None if it cannot be read)."""
    try:
        r = subprocess.run([sys.executable, "-X", "utf8", str(SKILLS / "garmin-recovery" / "scripts" / "garmin_readiness.py"), "--json"], capture_output=True, text=True, encoding="utf-8", timeout=180)
        return json.loads(r.stdout)
    except Exception:
        return None


def collect(today):
    import garmin_readiness  # noqa: E402
    with gc.Garmin() as g:
        acts = [a for a in gc.list_activities(g, today - timedelta(days=75), today) if a["date"] <= today]
        rows, _ = garmin_readiness.build_rows(g, today - timedelta(days=10), today)
    return acts, rows


def athlete_data():
    try:
        return json.loads(gc.ATHLETE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def run(today, with_readiness=True):
    acts, rows = collect(today)
    res = analysis.injury_flags(acts, rows, athlete_data(), today, readiness_json() if with_readiness else None)
    res["today"] = str(today)
    return res


def print_text(r):
    print(f"INJURY-RISK WATCH {r['today']}: {r['level']}  ({len(r['flags'])} flags)")
    sym = {"red": "RED  ", "amber": "AMBER", "info": "info "}
    for f in r["flags"]:
        print(f"  [{sym[f['level']]}] {f['text']}\n          evidence: {f['evidence']}\n          action:   {f['action']}")
    if not r["flags"]:
        print("  no flags from load, recovery or your own reports")
    if r["questions"]:
        print("ASK THE USER:")
        for q in r["questions"]:
            print("  - " + q)
    print("NOTE: " + r["note"])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--today")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-readiness", action="store_true", help="skip the readiness call (faster)")
    a = ap.parse_args()
    gc.utf8_stdout()
    today = date.fromisoformat(a.today) if a.today else date.today()
    r = run(today, not a.no_readiness)
    print(json.dumps(r, indent=1, default=str)) if a.json else print_text(r)


if __name__ == "__main__":
    main()
