#!/usr/bin/env python3
"""Persistent athlete memory for the Garmin coaching team.

The coach and every specialist run `athlete.py show` first, so goals, gates, injuries and
preferences are never forgotten between sessions. State lives in $GARMIN_COACH_DATA/athlete.json (default ~/garmin-coach-data/athlete.json), never inside the plugin folder.

  athlete.py show                          compact context block (give this to every subagent)
  athlete.py injury-add --area "left knee" --note "pain on stairs" [--restrict "no downhill running"] [--started 2026-11-10]
  athlete.py injury-update ID [--note ..] [--restrict ..] [--status active|monitoring|resolved]
  athlete.py injury-none                   record that the athlete reported no injury history
  athlete.py note --text "..."             dated note (feeling, constraint, decision)
  athlete.py set PATH VALUE_JSON           e.g. set preferences.days_per_week 5 ; set goals.ride-100k-25.date '"2027-03-01"'
  athlete.py goal-add --id ID --title T [--rank N] [--date YYYY-MM-DD] [--detail D]
  athlete.py goal-done ID                  mark a goal reached
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

import os
DATA_DIR = Path(os.environ.get("GARMIN_COACH_DATA") or Path.home() / "garmin-coach-data")   # personal data lives OUTSIDE the plugin folder
PATH = DATA_DIR / "athlete.json"


TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "athlete.template.json"


def load():
    if not PATH.exists():
        raise SystemExit(f"No athlete file at {PATH}. Run: athlete.py init   (creates it from a blank template; then interview the user and record the answers).")
    return json.loads(PATH.read_text(encoding="utf-8"))


def save(d):
    d["updated"] = str(date.today())
    PATH.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def show(d):
    p = d["preferences"]
    print("ATHLETE CONTEXT (athlete.json, updated %s)" % d["updated"])
    print("GOALS (rank 1 = main focus now):")
    for g in sorted(d["goals"], key=lambda g: (g.get("rank", 9), g["id"])):
        extra = []
        if g.get("done"):
            extra.append("DONE")
        if g.get("date"):
            extra.append("date " + g["date"])
        print(f"  [{g.get('rank', '-')}] {g['id']}: {g['title']}" + (f"  ({', '.join(extra)})" if extra else ""))
    gate = next((g for g in d["goals"] if g["kind"] == "gate"), None)
    if gate:
        c = gate["criteria"]
        print(f"GATE {gate['id']}: >= {c['min_session_minutes']} min session, warm-up to cool-down jogged, walking <= {c['max_walk_seconds']} s "
              f"(walk = cadence < {c['walk_cadence_spm_below']} spm for >= {c['min_walk_segment_s']} s); unlocks: {gate['unlocks']}. "
              f"Status: run garmin-planner/scripts/run_gate.py")
    act = [i for i in d["injuries"] if i.get("status") != "resolved"]
    if act:
        print("INJURIES / NIGGLES (active):")
        for i in act:
            print(f"  #{i['id']} {i['area']} [{i['status']}] since {i.get('started', '?')}: {i.get('note', '')}"
                  + (f" | RESTRICT: {i['restrict']}" if i.get("restrict") else ""))
    else:
        print("INJURIES: none recorded" + ("" if d.get("injury_history_known") else " (history NOT yet asked: ask before planning heavier work)"))
    done = [i for i in d["injuries"] if i.get("status") == "resolved"]
    if done:
        print("PAST INJURIES: " + "; ".join(f"{i['area']} (resolved {i.get('resolved', '?')})" for i in done))
    pr = d.get("profile") or {}
    if pr:
        print("BODY: " + ", ".join(f"{k.replace('_', ' ')} {v}" for k, v in pr.items() if v not in (None, "")))
    eq = d.get("equipment") or {}
    if eq:
        print("EQUIPMENT: " + ("no gym membership. " if eq.get("gym") is False else "") + "; ".join(eq.get("items", [])))
        for b in eq.get("bikes", []):
            bits = [b.get("type") or "", b.get("fork") or "", b.get("drivetrain") or ""]
            if b.get("chainring_t"):
                bits.append(f"{b['chainring_t']}T chainring; " + "; ".join(f"{s['mode']}: {s['cog_t']}T" if isinstance(s['cog_t'], int) else f"{s['mode']}: {s['cog_t']}" for s in b.get("setups", [])))
            print(f"  BIKE {b['id']}: {b['name']} | " + " | ".join(x for x in bits if x))
        if eq.get("unknown"):
            print("  not yet known: " + "; ".join(eq["unknown"]))
    cons = d.get("constraints") or {}
    if cons.get("no_exercises"):
        print("NEVER PRESCRIBE (athlete cannot do them): " + ", ".join(cons["no_exercises"]) + ". " + cons.get("note", ""))
    print(f"SCHEDULE: {p.get('days_per_week')} days/wk; {p.get('cardio_slot')} cardio {p.get('cardio_start')}, {p.get('strength_slot')} strength {p.get('strength_start')}; "
          f"rest {p.get('rest_day')}; long ride {p.get('long_ride_day')}, long run {p.get('long_run_day')}; strength {'/'.join(p.get('strength_days') or [])}")
    h = d.get("hr") or {}
    eb = h.get("easy_band") or {}
    if eb or h.get("run_easy_max"):
        run_c = (eb.get("run") or [None, h.get("run_easy_max")])[1]
        bike_c = (eb.get("bike") or [None, h.get("bike_easy_max")])[1]
        print(f"HR EASY CEILINGS: run <= {run_c}, bike <= {bike_c} ({h.get('source') or 'source not recorded'})")
    else:
        print("HR: NOT RECORDED. Ask the user for their watch zones (max HR, LTHR, resting HR, method) or what heart rate they call easy; never assume.")
    if d.get("notes"):
        print("RECENT NOTES:")
        for n in d["notes"][-5:]:
            print(f"  {n['date']}: {n['text']}")


def find_goal(d, gid):
    return next((g for g in d["goals"] if g["id"] == gid), None)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("show")
    sub.add_parser("init")
    a = sub.add_parser("injury-add"); a.add_argument("--area", required=True); a.add_argument("--note", default=""); a.add_argument("--restrict", default=""); a.add_argument("--started", default=str(date.today()))
    u = sub.add_parser("injury-update"); u.add_argument("id", type=int); u.add_argument("--note"); u.add_argument("--restrict"); u.add_argument("--status", choices=["active", "monitoring", "resolved"])
    sub.add_parser("injury-none")
    n = sub.add_parser("note"); n.add_argument("--text", required=True)
    s = sub.add_parser("set"); s.add_argument("path"); s.add_argument("value")
    g = sub.add_parser("goal-add"); g.add_argument("--id", required=True); g.add_argument("--title", required=True); g.add_argument("--rank", type=int, default=3); g.add_argument("--date"); g.add_argument("--detail", default="")
    gd = sub.add_parser("goal-done"); gd.add_argument("id")
    args = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if args.cmd == "init":
        if PATH.exists():
            raise SystemExit(f"{PATH} already exists: not overwritten. Use athlete.py show / set / note.")
        PATH.parent.mkdir(parents=True, exist_ok=True)
        d = json.loads(TEMPLATE.read_text(encoding="utf-8"))
        save(d)
        print(f"created {PATH} from the blank template. Next: interview the user (goals, injuries, equipment, banned exercises, schedule, heart-rate data) and record each answer.")
        return
    d = load()
    if args.cmd == "show":
        show(d); return
    if args.cmd == "injury-add":
        nid = max([i["id"] for i in d["injuries"]] + [0]) + 1
        d["injuries"].append({"id": nid, "area": args.area, "note": args.note, "restrict": args.restrict, "status": "active", "started": args.started})
        d["injury_history_known"] = True
        print(f"added injury #{nid}")
    elif args.cmd == "injury-update":
        i = next((x for x in d["injuries"] if x["id"] == args.id), None)
        if not i:
            raise SystemExit("no such injury id")
        for k in ("note", "restrict", "status"):
            v = getattr(args, k)
            if v is not None:
                i[k] = v
        if args.status == "resolved":
            i["resolved"] = str(date.today())
        print("updated")
    elif args.cmd == "injury-none":
        d["injury_history_known"] = True
        print("recorded: no injury history reported")
    elif args.cmd == "note":
        d["notes"].append({"date": str(date.today()), "text": args.text})
        print("note saved")
    elif args.cmd == "set":
        parts = args.path.split(".")
        cur = d
        for k in parts[:-1]:
            if isinstance(cur, list):
                cur = next(x for x in cur if x.get("id") == k)
            else:
                cur = cur.setdefault(k, {})   # new sections (profile, equipment, constraints) are created on demand
        val = json.loads(args.value)
        if isinstance(cur, list):
            raise SystemExit("point set at a field, not a list")
        cur[parts[-1]] = val
        print("set", args.path)
    elif args.cmd == "goal-add":
        if find_goal(d, args.id):
            raise SystemExit("goal id exists")
        d["goals"].append({"id": args.id, "rank": args.rank, "title": args.title, "detail": args.detail, "kind": "target", "date": args.date})
        print("goal added")
    elif args.cmd == "goal-done":
        gl = find_goal(d, args.id)
        if not gl:
            raise SystemExit("no such goal")
        gl["done"] = str(date.today())
        print("goal marked done")
    save(d)


if __name__ == "__main__":
    main()
