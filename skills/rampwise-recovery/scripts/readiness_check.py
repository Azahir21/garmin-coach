#!/usr/bin/env python3
"""Daily readiness (GREEN / AMBER / RED) from your own Garmin HRV, resting HR and sleep.

Pulls ~75 days of data from the local garmin server, then applies the readiness logic of
`readiness.py` (MIT, from tomasstankovic/running-coach, copied unmodified): the 7-day rolling mean of
ln(nightly HRV) against the athlete's own baseline band (mean +/- 0.5 SD of the previous 28-60 days),
resting-HR flags, short sleep and sleep debt. One bad number is never enough on its own.

Usage:
  readiness_check.py [--date YYYY-MM-DD] [--days 75] [--stress 1-5] [--brief | --json | --trend N]

Evidence labels are in references/sources.md (HRV-guided training: small, uncertain benefit;
resting-HR and sleep thresholds are practice-based).
"""
import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "rampwise" / "scripts"))

import gcommon  # noqa: E402
import readiness  # noqa: E402


def build_rows(g, start, end):
    hrv = g.call("garmin_get_hrv_summaries", start=str(start), end=str(end))
    sleep = g.call("garmin_get_sleep_summaries", start=str(start), end=str(end))
    daily = g.call("garmin_get_daily_summaries", start=str(start), end=str(end))
    rows = {}

    def row(d):
        return rows.setdefault(d, {"date": d})

    garmin_view = {}
    for h in (hrv.get("hrvSummaries") or []):
        d = h.get("calendarDate")
        if d and h.get("lastNightAvg"):
            row(d)["hrv"] = float(h["lastNightAvg"])
            garmin_view[d] = {"status": h.get("status"), "weekly_avg": h.get("weeklyAvg"),
                              "band": [(h.get("baseline") or {}).get("balancedLow"),
                                       (h.get("baseline") or {}).get("balancedUpper")]}
    for s in (sleep.get("results") or []):
        d = s.get("calendarDate")
        if d and s.get("sleepTimeSeconds"):
            row(d)["sleep_h"] = s["sleepTimeSeconds"] / 3600.0
            score = ((s.get("sleepScores") or {}).get("overall") or {}).get("value")
            if score is not None:
                row(d)["sleep_score"] = score
    for x in (daily.get("data") or []):
        d = x.get("calendarDate")
        rhr = (x.get("heartRate") or {}).get("restingValue")
        if d and rhr:
            row(d)["rhr"] = float(rhr)
    return [rows[k] for k in sorted(rows)], garmin_view


def main():
    gcommon.utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", help="day to assess (default: latest day with data)")
    ap.add_argument("--days", type=int, default=75, help="history to pull (>= 35 recommended; baseline needs 21+ HRV days)")
    ap.add_argument("--stress", type=int, choices=range(1, 6), metavar="1-5", help="your own rating of non-training load today")
    ap.add_argument("--brief", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--trend", type=int, metavar="N")
    a = ap.parse_args()

    end = date.fromisoformat(a.date) if a.date else date.today()
    start = end - timedelta(days=a.days)
    with gcommon.Garmin() as g:
        rows, gview = build_rows(g, start, end)
    if not rows:
        sys.exit("no HRV / sleep / resting-HR data returned for that period")

    if a.trend:
        out = [x for x in (readiness.assess(rows, r["date"]) for r in rows[-a.trend:]) if x and x["hrv7"]]
        print(json.dumps([{k: x[k] for k in ("date", "verdict", "reasons", "hrv", "hrv7", "hrv_state", "band_lo",
                                              "band_hi", "rhr", "rhr7", "sleep_h")} for x in out]))
        return

    target = a.date or rows[-1]["date"]
    res = readiness.assess(rows, target, a.stress)
    if res is None:
        have = rows[-1]["date"]
        print(f"note: no data for {target} yet (the watch may not have synced); using {have}", file=sys.stderr)
        target = have
        res = readiness.assess(rows, target, a.stress)
    n_hrv = sum(1 for r in rows if "hrv" in r)
    res["baseline_days_hrv"] = n_hrv
    res["garmin_status"] = gview.get(target)
    if a.json:
        print(json.dumps(res, ensure_ascii=False, default=str))
        return
    if a.brief:
        reasons = "; ".join(m for _, m in res["flags"]) or "all within your normal range"
        print(f"{target} {res['verdict']}: {reasons}")
        return
    print(f"{target}: {res['verdict_text']}   (HRV nights in history: {n_hrv})")
    for lvl, msg in res["flags"]:
        print(f"  {lvl.upper():<5} {msg}")
    for n in res["notes"]:
        print(f"  ·     {n}")
    gv = res["garmin_status"]
    if gv:
        print(f"  ·     Garmin's own view: HRV status {gv['status']}, weekly avg {gv['weekly_avg']}, "
              f"balanced band {gv['band'][0]}-{gv['band'][1]} (cross-check only; the verdict above uses your own baseline)")


if __name__ == "__main__":
    main()
