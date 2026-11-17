#!/usr/bin/env python3
"""Export an event plan (event_plan.py JSON) to files other tools read.

  export_plan.py PLAN.json --format ics|zwo|mrc|csv|all [--out DIR] [--from YYYY-MM-DD] [--days N]

  ics   one calendar file with every session as an event (floating local times, so it lands at the same clock time wherever you are). Import it into
        Google, Apple or Outlook calendar. Titles start with "[RW]" and descriptions end with the line "rampwise-plan" so you can find and remove them.
  zwo   one Zwift workout file per ride (swim and run sessions have no Zwift format). Power is written as a FRACTION of FTP, so Zwift scales it to your FTP.
  mrc   one ERG/MRC file per ride (minutes and percent of FTP), the layout used by trainer apps such as TrainerRoad. Format follows the common MRC layout;
        not tested in every app.
  fit   Garmin .fit workout files for runs and rides, with YOUR heart-rate bands (zone first, custom bpm second); only when the plan has heart-rate workouts, i.e. your heart-rate
        data are known. Not tried on every watch: check each file on your watch. Swims have no .fit export.
  csv   one spreadsheet with every session (date, sport, title, minutes, effort, description).
Effort to FTP share is a practice scale (easy 65 %, steady 78 %, tempo 88 %, threshold 100 %, hard 112 %): no paper read sets those numbers, they are the
conventional zone mid-points. Garmin .fit workout files for plans built from your Garmin history come from export_workouts.py (they need your heart-rate data).
"""
import argparse
import csv
import json
import re
import sys
from datetime import date, datetime, timedelta
from html import escape
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from plan import EFFORT  # noqa: E402

MARK = "rampwise-plan"
PREFIX = "[RW]"


def slug(s, n=48):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:n]


def ics_escape(t):
    return t.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def fold(line):
    out, b = [], line.encode("utf-8")
    while len(b) > 74:
        cut = 74
        while cut > 0 and (b[cut] & 0xC0) == 0x80:
            cut -= 1
        out.append(b[:cut].decode("utf-8"))
        b = b[cut:]
        b = b" " + b
    out.append(b.decode("utf-8"))
    return "\r\n".join(out)


def to_ics(meta, sessions, prefix=PREFIX):
    now = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Rampwise//Event plan//EN", "CALSCALE:GREGORIAN", f"X-WR-CALNAME:{ics_escape(meta['event_label'] + ' plan')}"]
    for s in sessions:
        st = datetime.fromisoformat(s["start"])
        en = datetime.fromisoformat(s["end"]) if s["minutes"] else st + timedelta(hours=1)
        label = f"{prefix} {s['title']}" + (f" ({s['minutes']} min)" if s["minutes"] else "")
        desc = f"{s['desc']}\n\nWeek {s['week']} ({s['week_tag']}). Not medical advice; pain that changes how you move means stop.\n{MARK}"
        uid = f"{s['date']}-{s['kind']}-{slug(s['title'], 20)}@rampwise"
        lines += ["BEGIN:VEVENT", f"UID:{uid}", f"DTSTAMP:{now}", f"DTSTART:{st:%Y%m%dT%H%M%S}", f"DTEND:{en:%Y%m%dT%H%M%S}", f"SUMMARY:{ics_escape(label)}", f"DESCRIPTION:{ics_escape(desc)}", "TRANSP:TRANSPARENT", "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return "\r\n".join(fold(x) for x in lines) + "\r\n"


def flat_steps(blocks):
    """Expand repeats into (minutes, effort) segments."""
    out = []
    for b in blocks:
        if "repeat" in b:
            for _ in range(b["repeat"]):
                out += [(b["on"]["minutes"], b["on"]["effort"]), (b["off"]["minutes"], b["off"]["effort"])]
        else:
            out.append((b["minutes"], b["effort"]))
    return out


def to_zwo(s):
    f = lambda e: EFFORT[e][2]
    body = []
    for b in s["blocks"]:
        if "repeat" in b:
            body.append(f'    <IntervalsT Repeat="{b["repeat"]}" OnDuration="{int(b["on"]["minutes"] * 60)}" OffDuration="{int(b["off"]["minutes"] * 60)}" OnPower="{f(b["on"]["effort"]):.2f}" OffPower="{f(b["off"]["effort"]):.2f}"/>')
        elif b["effort"] == "warm":
            body.append(f'    <Warmup Duration="{int(b["minutes"] * 60)}" PowerLow="0.50" PowerHigh="{f("easy"):.2f}"/>')
        elif b["effort"] == "cool":
            body.append(f'    <Cooldown Duration="{int(b["minutes"] * 60)}" PowerLow="{f("easy"):.2f}" PowerHigh="0.45"/>')
        else:
            body.append(f'    <SteadyState Duration="{int(b["minutes"] * 60)}" Power="{f(b["effort"]):.2f}"/>')
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<workout_file>\n  <author>Rampwise</author>\n'
            f'  <name>{escape(s["title"])}</name>\n  <description>{escape(s["desc"][:400])} (power is a share of FTP)</description>\n  <sportType>bike</sportType>\n  <tags><tag name="Rampwise"/></tags>\n  <workout>\n'
            + "\n".join(body) + "\n  </workout>\n</workout_file>\n")


def to_mrc(s):
    rows, t = [], 0.0
    for minutes, effort in flat_steps(s["blocks"]):
        p = round(EFFORT[effort][2] * 100)
        rows += [f"{t:.2f}\t{p}", f"{t + minutes:.2f}\t{p}"]
        t += minutes
    return ("[COURSE HEADER]\nVERSION = 2\nUNITS = ENGLISH\n"
            f"DESCRIPTION = {s['title']} (Rampwise; percent of FTP)\nFILE NAME = {slug(s['title'])}\nMINUTES PERCENT\n[END COURSE HEADER]\n[COURSE DATA]\n" + "\n".join(rows) + "\n[END COURSE DATA]\n")


def to_csv(path, sessions):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["date", "weekday", "week", "phase", "sport", "title", "minutes", "quality", "description"])
        for s in sessions:
            w.writerow([s["date"], s["weekday"], s["week"], s["week_tag"], s["sport"], s["title"], s["minutes"], "yes" if s["quality"] else "", s["desc"]])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan")
    ap.add_argument("--format", choices=["ics", "zwo", "mrc", "csv", "fit", "all"], default="all")
    ap.add_argument("--out")
    ap.add_argument("--from", dest="start")
    ap.add_argument("--days", type=int)
    a = ap.parse_args()
    data = json.loads(Path(a.plan).read_text(encoding="utf-8"))
    meta, sess = data["meta"], data["sessions"]
    if a.start:
        sess = [s for s in sess if s["date"] >= a.start]
    if a.days:
        lo = a.start or sess[0]["date"]
        hi = str(date.fromisoformat(lo) + timedelta(days=a.days))
        sess = [s for s in sess if lo <= s["date"] < hi]
    out = Path(a.out) if a.out else Path(a.plan).parent / "exports"
    out.mkdir(parents=True, exist_ok=True)
    made = []
    if a.format in ("ics", "all"):
        (out / "plan.ics").write_text(to_ics(meta, sess), encoding="utf-8", newline="")
        made.append("plan.ics")
    if a.format in ("csv", "all"):
        to_csv(out / "plan.csv", sess)
        made.append("plan.csv")
    if a.format in ("fit", "all"):
        n_fit = [s for s in sess if s.get("workout")]
        if n_fit:
            import subprocess
            tmp = out / "plan_for_fit.json"
            tmp.write_text(json.dumps({"meta": meta, "sessions": sess}, default=str), encoding="utf-8")
            r = subprocess.run([sys.executable, "-X", "utf8", str(HERE / "export_workouts.py"), str(tmp), "--days", "400", "--from", sess[0]["date"], "--out", str(out / "fit")], capture_output=True, text=True, encoding="utf-8")
            tmp.unlink()
            made.append(f"{len(n_fit)} Garmin .fit workouts (fit/)" if r.returncode == 0 else "fit export failed: " + (r.stderr or r.stdout)[-160:])
        elif a.format == "fit":
            print("No heart-rate workouts in this plan: .fit files need your heart-rate data (ask the athlete for max HR / LTHR or their watch zones, record them in athlete.json, then re-run plan.py). Swim sessions have no .fit export.")
    rides = [s for s in sess if s["sport"] == "bike" and s["blocks"]]
    if a.format in ("zwo", "mrc", "all"):
        (out / "zwift").mkdir(exist_ok=True)
        (out / "mrc").mkdir(exist_ok=True)
        for s in rides:
            name = f"{s['date']}_{slug(s['title'])}"
            if a.format in ("zwo", "all"):
                (out / "zwift" / f"{name}.zwo").write_text(to_zwo(s), encoding="utf-8")
            if a.format in ("mrc", "all"):
                (out / "mrc" / f"{name}.mrc").write_text(to_mrc(s), encoding="utf-8")
        made.append(f"{len(rides)} ride workouts (zwo/mrc)")
    print(f"wrote to {out}: " + ", ".join(made))
    print("Swim and run sessions are in plan.ics and plan.csv only (Zwift and MRC are ride formats).")


if __name__ == "__main__":
    main()
