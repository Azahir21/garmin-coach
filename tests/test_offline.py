#!/usr/bin/env python3
"""Offline tests (no Garmin account): memory file, ask-first rules, strength generator, workout files, planner and calendar payloads on a synthetic user.

  python tests/test_offline.py
"""
import json
import os
import subprocess
import sys
import tempfile
import types
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SK = ROOT / "skills"
TMP = Path(tempfile.mkdtemp(prefix="gc-test-"))
os.environ["GARMIN_COACH_DATA"] = str(TMP)
sys.path.insert(0, str(SK / "garmin-coach" / "scripts"))
sys.path.insert(0, str(SK / "garmin-planner" / "scripts"))
sys.path.insert(0, str(SK / "garmin-strength" / "scripts"))
failed = []


def check(name, cond, extra=""):
    print(("ok   " if cond else "FAIL ") + name + (f" ({extra})" if extra and not cond else ""))
    if not cond:
        failed.append(name)


def run(*args, env=None):
    return subprocess.run([sys.executable, "-X", "utf8", *map(str, args)], capture_output=True, text=True, encoding="utf-8", env={**os.environ, **(env or {})})


# ---------------------------------------------------------------- memory file
r = run(SK / "garmin-coach" / "scripts" / "athlete.py", "show")
check("show without a file says to run init", r.returncode != 0 and "init" in (r.stdout + r.stderr))
r = run(SK / "garmin-coach" / "scripts" / "athlete.py", "init")
check("init creates athlete.json outside the plugin", r.returncode == 0 and (TMP / "athlete.json").exists())
r = run(SK / "garmin-coach" / "scripts" / "athlete.py", "init")
check("init never overwrites", r.returncode != 0)
r = run(SK / "garmin-coach" / "scripts" / "athlete.py", "show")
check("show on a blank file asks for heart-rate data", "NOT RECORDED" in r.stdout and "never assume" in r.stdout)
run(SK / "garmin-coach" / "scripts" / "athlete.py", "goal-add", "--id", "run-5k", "--title", "5 km in 25:00", "--rank", "1")
ath = json.loads((TMP / "athlete.json").read_text(encoding="utf-8"))
check("goal-add writes the goal", any(g["id"] == "run-5k" for g in ath["goals"]))

# ---------------------------------------------------------------- ask-first: strength equipment
r = run(SK / "garmin-strength" / "scripts" / "strength_plan.py", "--no-history", "--weeks", "1")
check("strength planner stops and asks without an equipment list", r.returncode == 2 and "NO EQUIPMENT LIST" in r.stdout)

# ---------------------------------------------------------------- strength generator: every profile, every size, banned exercises
import strength_plan as sp  # noqa: E402
prof = sp.load_profiles()["goals"]
ath["equipment"]["tags"] = ["bodyweight", "dumbbell", "barbell", "plates", "band", "step"]
ath["constraints"]["no_exercises"] = ["push-ups", "pull-ups", "chin-ups"]
count = 0
for g in prof:
    for ver in ("short", "mid", "full"):
        sessions, meta = sp.make_week(ath, [], 3, goal=g, version=ver)
        n_ok = all(len(s["lines"]) >= 3 for s in sessions) and len(sessions) == prof[g]["sessions_per_week"]
        banned = any(x in " ".join(s["lines"]).lower() for s in sessions for x in ("push-up", "pull-up", "chin-up"))
        check(f"strength {g}/{ver}: sessions with at least 3 moves, no banned exercise", n_ok and not banned, f"{[len(s['lines']) for s in sessions]} banned={banned}")
        count += 1
s1, _ = sp.make_week(ath, [], 4, goal="endurance", version="mid")
s2, _ = sp.make_week(ath, [], 4, goal="endurance", version="mid")
check("strength generation is deterministic for a week", [s["exercises"] for s in s1] == [s["exercises"] for s in s2])
hist = [{"date": "2026-01-01", "name": "x", "minutes": 30, "avg_hr": 100, "exercises": [{"key": ["squat", "dumbbell_split_squat"], "sets": [{"reps": 12, "kg": 10.0, "seconds": 40}] * 3}]}]
s3, _ = sp.make_week(ath, hist, 0, goal="endurance", version="full")
txt = " ".join(" ".join(s["lines"]) for s in s3)
check("history drives progression text", "Last time (2026-01-01)" in txt and "add the smallest plate step" in txt)
ath["constraints"]["no_exercises"] = []
s4, _ = sp.make_week({**ath, "equipment": {**ath["equipment"], "tags": ["bodyweight", "pullup_bar"]}}, [], 0, goal="general", version="full")
check("a user who can do pull-ups and push-ups may get them", any("pull-up" in l.lower() or "push-up" in l.lower() for s in s4 for l in s["lines"]))

# ---------------------------------------------------------------- workouts and heart-rate targets
import workout as wk  # noqa: E402
r = run(SK / "garmin-planner" / "scripts" / "workout.py", "--selftest")
check("workout.py self test (FIT encode, decode, CRC)", r.returncode == 0 and "selftest ok" in r.stdout, r.stdout[-200:] + r.stderr[-200:])
wk.set_zones({"running": {"floors": [105, 126, 147, 168, 189], "top": 210, "label": "test set"}})
check("a zone that covers the band is used", wk.hr_band(126, 146, "running")["type"] == "hr_zone")
check("custom bpm when no zone covers the band", wk.hr_band(160, 170, "running")["type"] == "hr_range")
check("no zones recorded means custom bpm", (wk.set_zones({}) or wk.hr_band(126, 146, "running"))["type"] == "hr_range")

# ---------------------------------------------------------------- ask-first: heart-rate data
import build_plan as bp  # noqa: E402
try:
    bp.ensure_hr({"hr": {}}, None, date.today(), False)
    check("planner stops without heart-rate data", False)
except SystemExit as e:
    check("planner stops (exit 2) without heart-rate data", e.code == 2)

# ---------------------------------------------------------------- planner on a synthetic user
ath["hr"] = {"easy_band": {"run": [120, 140], "bike": [120, 140]}}
ath["workouts"] = {"output_dir": str(TMP / "workouts")}
(TMP / "athlete.json").write_text(json.dumps(ath), encoding="utf-8")
a = types.SimpleNamespace(readiness="green", gate="auto", reset="auto", days_per_week=6, start="2026-12-07", weeks=4, hr_from_trend=False, out=None)
h = {"weekly_min_last3": [200, 240, 260], "base_min": 233.0, "last_week_min": 260, "longest_run_min": 40.0, "longest_run_km": 6.0, "longest_ride_min": 90.0, "longest_ride_km": 30.0, "streak_days": 2}
wk.set_zones({})
meta, sess = bp.plan(a, h, ath, date(2026, 12, 7))
kinds = {s["sport"] for s in sess}
check("plan has run, bike and strength sessions", kinds >= {"run", "bike", "strength"})
check("every strength session has exercises", all(s["strength"]["exercises"] for s in sess if s["sport"] == "strength"))
check("plan has quality sessions by default", any(s.get("quality") for s in sess))
a2 = types.SimpleNamespace(**{**vars(a), "readiness": "red"})
meta2, sess2 = bp.plan(a2, h, ath, date(2026, 12, 7))
check("a RED readiness week has no quality session in the first week", not any(s.get("quality") for s in sess2 if s["week"] == 1))
ath_inj = json.loads(json.dumps(ath))
ath_inj["injuries"] = [{"id": 1, "area": "left knee", "note": "pain", "restrict": "", "status": "active", "started": "2026-12-01"}]
_, sess3 = bp.plan(a, h, ath_inj, date(2026, 12, 7))
check("an ACTIVE injury locks quality sessions for that user only", not any(s.get("quality") for s in sess3) and any(s.get("quality") for s in sess))

# ---------------------------------------------------------------- files from the plan
plan_file = TMP / "plan.json"
plan_file.write_text(json.dumps({"meta": meta, "sessions": sess}, default=str), encoding="utf-8")
r = run(SK / "garmin-planner" / "scripts" / "export_workouts.py", plan_file, "--from", "2026-12-07", "--days", "14")
fits = list((TMP / "workouts").glob("*.fit"))
check("export writes decodable .fit files", r.returncode == 0 and len(fits) >= 8, r.stdout[-200:] + r.stderr[-200:])
r = run(SK / "garmin-planner" / "scripts" / "calendar_events.py", plan_file, "--from", "2026-12-07", "--json")
try:
    ev = json.loads(r.stdout)["events"]
except ValueError:
    ev = []
check("calendar payload has events with titles and the marker", len(ev) >= 8 and all(e["summary"].startswith("[GC]") for e in ev) and all("garmin-coach-plan" in e["description"] for e in ev), r.stderr[-200:])

print()
print("ALL OK" if not failed else f"{len(failed)} FAILED: {failed}")
sys.exit(1 if failed else 0)
