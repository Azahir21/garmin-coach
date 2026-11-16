#!/usr/bin/env python3
"""Write the planned runs and rides as Garmin workout files (.fit), one per session, plus a readable summary.

  export_workouts.py PLAN.json [--days 14] [--from YYYY-MM-DD] [--out DIR]

Output folder: athlete.json workouts.output_dir (default ~/garmin-workouts). Each file is decoded again after it is written
(CRC, step count, step values) before it is kept. The files have NOT been tried on a real watch. Usual route: connect the watch by
USB and copy the .fit files into GARMIN/NewFiles (community reports on how reliably this works are mixed: copy a few at a time,
eject, and check Training > Workouts on the watch). Strength sessions are not exported (Garmin strength workouts need exercise codes);
they stay as text in the calendar.
"""
import argparse
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILLS = HERE.parent.parent
DATA_DIR = Path(__import__("os").environ.get("RAMPWISE_DATA") or __import__("os").environ.get("GARMIN_COACH_DATA") or (Path.home() / "garmin-coach-data" if (Path.home() / "garmin-coach-data").exists() and not (Path.home() / "rampwise-data").exists() else Path.home() / "rampwise-data"))   # personal data lives OUTSIDE the plugin folder, so updates never touch it
ATHLETE_JSON = DATA_DIR / "athlete.json"
sys.path.insert(0, str(HERE))
import workout as wk  # noqa: E402


def fit_filename(e):
    """Deterministic file name for a planned session: 2026-11-17_0515_run_easy-run-10-35-5.fit"""
    slug = re.sub(r"[^a-z0-9]+", "-", e["title"].lower()).strip("-")
    return f"{e['date']}_{e['start'][11:16].replace(':', '')}_{e['sport']}_{slug}.fit"


def watch_name(e):
    """Name shown on the watch: date first so repeated sessions are told apart (kept short)."""
    d = datetime.strptime(e["date"], "%Y-%m-%d")
    return f"{d.day}{d:%b} {e['workout']['name']}"[:30]


def out_dir():
    try:
        ath = json.loads((ATHLETE_JSON).read_text(encoding="utf-8"))
        d = (ath.get("workouts") or {}).get("output_dir")
    except Exception:
        d = None
    p = Path(d).expanduser() if d else Path.home() / "garmin-workouts"
    p.mkdir(parents=True, exist_ok=True)
    return p


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan")
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--from", dest="frm", default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    plan = json.loads(Path(a.plan).read_text(encoding="utf-8"))
    start = datetime.strptime(a.frm or plan["meta"]["start"], "%Y-%m-%d").date()
    end = start + timedelta(days=a.days)
    out = Path(a.out) if a.out else out_dir()
    out.mkdir(parents=True, exist_ok=True)
    ag = out / "after-gate"
    ag.mkdir(exist_ok=True)
    for old in list(out.glob("*.fit")) + list(ag.glob("*.fit")):    # keep the folder equal to the current plan
        old.unlink()
    lines = ["# Workouts for your watch", "",
             "Copy the .fit files into GARMIN/NewFiles on the watch (USB), eject, then look under Training > Workouts. "
             "Not tried on your watch yet. If a name looks cut off, it is only the name; the steps are what matter.", ""]
    n = 0
    for e in plan["sessions"]:
        d = datetime.strptime(e["date"], "%Y-%m-%d").date()
        if e["sport"] not in ("run", "bike") or not (start <= d < end):
            continue
        w = dict(e["workout"])
        w["name"] = watch_name(e)
        data = wk.encode_fit(w)
        header, steps = wk.decode_check(data)                      # raises if the file does not read back correctly
        name = fit_filename(e)
        (out / name).write_bytes(data)
        n += 1
        lines += [f"## {e['date']} {e['start'][11:]} - {e['title']} ({e['minutes']} min)", f"File: {name} | watch name: {w['name']} | {header['num_valid_steps']} steps", "", "```", wk.describe(e["workout"]), "```", ""]
        print(f"ok  {name}  ({len(steps)} steps, {len(data)} bytes)")
    pv = plan["meta"].get("previews", [])
    if pv:
        lines += ["# Quality session previews (not scheduled unless the plan lists them)", "",
                  "Quality sessions are on by default and locked only by your own data (an active injury, a RED reset week, your settings). "
                  "The files are in the after-gate folder so you can see the steps; the plan lists the ones that are scheduled.", ""]
        for item in pv:
            w = dict(item["workout"])
            w["name"] = f"After gate {w['name']}"[:30]
            data = wk.encode_fit(w)
            wk.decode_check(data)
            fname = f"after-gate_{item['kind']}.fit"
            (ag / fname).write_bytes(data)
            lines += [f"## {item['title']} (about {item['minutes']} min)", f"File: after-gate/{fname}", "", "```", wk.describe(item["workout"]), "```", ""]
            print(f"ok  after-gate/{fname}")
    (out / "workouts.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"\n{n} workout files written to {out}")


if __name__ == "__main__":
    main()
