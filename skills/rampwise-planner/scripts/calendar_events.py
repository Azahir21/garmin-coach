#!/usr/bin/env python3
"""Turn a saved plan (build_plan.py --out) into Google Calendar event payloads for the calendar connector.

This script only prepares JSON. The coach (main session) creates the events with the connector tools
(`create_event`) so the athlete's calendar is only written where they asked. Rolling window: only the next
`window_weeks` (athlete.json calendar.window_weeks) or, if that is empty, `window_days` (calendar.window_days, default 14) are written, because the plan adapts to readiness,
the run gate and load every week; re-sync weekly.

Every event title starts with the prefix "[GC]" and every description ends with the marker line
"rampwise-plan" so old coach events can be found (list_events fullText) and replaced without touching anything else.

  calendar_events.py PLAN.json [--weeks 4 | --days 14] [--from YYYY-MM-DD] [--json]
How far ahead to write: --days, then --weeks, then calendar.window_weeks, then calendar.window_days, then 14 days.
Output: JSON {"calendar_id", "marker", "window": [start, end], "events": [...]} ready for create_event calls
(fields: summary, startTime, endTime, description, colorId, allDay, availability, overrideReminders).
"""
import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILLS = HERE.parent.parent
DATA_DIR = Path(__import__("os").environ.get("RAMPWISE_DATA") or __import__("os").environ.get("GARMIN_COACH_DATA") or (Path.home() / "garmin-coach-data" if (Path.home() / "garmin-coach-data").exists() and not (Path.home() / "rampwise-data").exists() else Path.home() / "rampwise-data"))   # personal data lives OUTSIDE the plugin folder, so updates never touch it
ATHLETE_JSON = DATA_DIR / "athlete.json"
sys.path.insert(0, str(HERE))
from export_workouts import fit_filename  # noqa: E402
COLORS = {"run": "6", "bike": "9", "strength": "3", "week": "8"}      # tangerine, blueberry, grape, graphite
FOCUS = {
    "RESET": "Reset week: the rides are trimmed after 14 days without rest and a RED readiness; your runs keep their usual size (easy run = 10 min warm-up + 35 min zone 2 + 5 min cool-down). Easy only. Sleep is the training.",
    "BUILD": "Build week: aerobic base first, easy effort, HR under the ceiling; the quality sessions in it replace easy ones, so they add no volume. {hold}",
    "DELOAD": "Deload week: about 25 % less volume to absorb the last weeks.",
    "BASE": "Base week: mostly easy aerobic work, effort by feel or heart rate; the quality sessions replace easy ones, so they add no volume. {hold}",
    "PEAK": "Peak week: the most specific work of the plan, still mostly easy. {hold}",
    "TAPER": "Taper week: less volume, a little intensity kept, rest well.",
    "RECOVERY": "Lighter week: about 25 % less volume (and the standardised aerobic test in a base plan).",
    "RACE": "Race week.",
}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan")
    ap.add_argument("--days", type=int, default=None)
    ap.add_argument("--weeks", type=int, default=None, help="write this many weeks ahead (7 days each)")
    ap.add_argument("--from", dest="frm", default=None)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ath = json.loads((ATHLETE_JSON).read_text(encoding="utf-8"))
    cal = ath["calendar"]
    plan = json.loads(Path(a.plan).read_text(encoding="utf-8"))
    meta, sess = plan["meta"], plan["sessions"]
    days = a.days or ((a.weeks or cal.get("window_weeks") or 0) * 7) or cal.get("window_days", 14)
    start = datetime.strptime(a.frm or meta["start"], "%Y-%m-%d").date()
    end = start + timedelta(days=days)
    prefix, marker = cal["title_prefix"], cal["marker"]
    events, seen_weeks = [], set()
    for s in sess:
        d = datetime.strptime(s["date"], "%Y-%m-%d").date()
        if not (start <= d < end):
            continue
        wk = next(w for w in meta["weekly_targets"] if w["week"] == s["week"])
        if s["week"] not in seen_weeks:
            seen_weeks.add(s["week"])
            events.append({
                "summary": f"{prefix} Week {wk['week']}: {wk['tag']} (about {wk['endurance_min']} min cardio)",
                "startTime": f"{d.isoformat()}T00:00:00", "endTime": f"{(d + timedelta(days=1)).isoformat()}T00:00:00", "allDay": True,
                "description": FOCUS.get(wk["tag"], "").format(hold=("Same volume as the week before while an injury note is active (no extra volume)." if meta.get("hold_progression") else "")).strip() + f"\n\n{marker}:{meta['generated']}", "colorId": COLORS["week"], "availability": "AVAILABILITY_FREE",
            })
        events.append({
            "summary": f"{prefix} {s['title']} - {s['minutes']} min",
            "startTime": s["start"] + ":00", "endTime": s["end"] + ":00",
            "description": s["desc"] + (f"\n\nWATCH FILE: {fit_filename(s)} (folder: workouts)" if s["sport"] in ("run", "bike") else "") + f"\n\n{marker}:{meta['generated']}",
            "colorId": COLORS[s["sport"]], "allDay": False, "availability": "AVAILABILITY_BUSY",
            "overrideReminders": [{"method": "popup", "minutes": 30}],
        })
    out = {"calendar_id": cal["calendar_id"], "marker": marker, "prefix": prefix, "window": [str(start), str(end)], "count": len(events), "events": events}
    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    else:
        print(f"{len(events)} events for {start} .. {end - timedelta(days=1)} on calendar '{cal['calendar_id']}'")
        for e in events:
            print(f"  {e['startTime'][:16]}  {e['summary']}")
        print(f"Find old coach events with list_events fullText='{marker}' (and title prefix {prefix}) before re-syncing.")


if __name__ == "__main__":
    main()
