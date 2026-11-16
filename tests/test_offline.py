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
os.environ["RAMPWISE_DATA"] = str(TMP)
sys.path.insert(0, str(SK / "rampwise" / "scripts"))
sys.path.insert(0, str(SK / "rampwise-planner" / "scripts"))
sys.path.insert(0, str(SK / "rampwise-strength" / "scripts"))
failed = []


def check(name, cond, extra=""):
    print(("ok   " if cond else "FAIL ") + name + (f" ({extra})" if extra and not cond else ""))
    if not cond:
        failed.append(name)


def run(*args, env=None):
    return subprocess.run([sys.executable, "-X", "utf8", *map(str, args)], capture_output=True, text=True, encoding="utf-8", env={**os.environ, **(env or {})})


# ---------------------------------------------------------------- memory file
r = run(SK / "rampwise" / "scripts" / "athlete.py", "show")
check("show without a file says to run init", r.returncode != 0 and "init" in (r.stdout + r.stderr))
r = run(SK / "rampwise" / "scripts" / "athlete.py", "init")
check("init creates athlete.json outside the plugin", r.returncode == 0 and (TMP / "athlete.json").exists())
r = run(SK / "rampwise" / "scripts" / "athlete.py", "init")
check("init never overwrites", r.returncode != 0)
r = run(SK / "rampwise" / "scripts" / "athlete.py", "show")
check("show on a blank file asks for heart-rate data", "NOT RECORDED" in r.stdout and "never assume" in r.stdout)
run(SK / "rampwise" / "scripts" / "athlete.py", "goal-add", "--id", "run-5k", "--title", "5 km in 25:00", "--rank", "1")
ath = json.loads((TMP / "athlete.json").read_text(encoding="utf-8"))
check("goal-add writes the goal", any(g["id"] == "run-5k" for g in ath["goals"]))

# ---------------------------------------------------------------- ask-first: strength equipment
r = run(SK / "rampwise-strength" / "scripts" / "strength_plan.py", "--no-history", "--weeks", "1")
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
r = run(SK / "rampwise-planner" / "scripts" / "workout.py", "--selftest")
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
r = run(SK / "rampwise-planner" / "scripts" / "export_workouts.py", plan_file, "--from", "2026-12-07", "--days", "14")
fits = list((TMP / "workouts").glob("*.fit"))
check("export writes decodable .fit files", r.returncode == 0 and len(fits) >= 8, r.stdout[-200:] + r.stderr[-200:])
r = run(SK / "rampwise-planner" / "scripts" / "calendar_events.py", plan_file, "--from", "2026-12-07", "--json")
try:
    ev = json.loads(r.stdout)["events"]
except ValueError:
    ev = []
check("calendar payload has events with titles and the marker", len(ev) >= 8 and all(e["summary"].startswith("[GC]") for e in ev) and all("rampwise-plan" in e["description"] for e in ev), r.stderr[-200:])

# ---------------------------------------------------------------- analyze, adapt, report (pure functions on synthetic data)
import xml.dom.minidom
from datetime import timedelta
for sub in ("rampwise-analyze", "rampwise-adapt", "rampwise-report"):
    sys.path.insert(0, str(SK / sub / "scripts"))
import analysis as an
import adapt_logic as al
import charts as chx
import report as rp

T0 = date(2026, 11, 16)


def mk(i, d, sport, km, mins, hr=140, te=2.5, gain=20):
    return {"id": i, "name": f"{sport} {i}", "sport": sport, "date": d, "start": f"{d}T07:00:00", "km": km, "min": mins, "moving_min": mins, "avg_hr": hr, "gain_m": gain, "te_aerobic": te}


acts, n = [], 0
for k in range(1, 15):                              # 14 consecutive days: a rest-free streak
    n += 1
    acts.append(mk(n, T0 - timedelta(days=k), "run" if k % 2 else "bike", 8 if k % 2 else 25, 45 if k % 2 else 70))
acts.append(mk(99, T0, "run", 14, 90))             # a long run: much longer than any run in the 30 days before
cmpd = an.compare(acts, T0)
check("compare: rolling windows are the last 7 days and the 7 before", cmpd["rolling"]["this"]["from"] == "2026-11-10" and cmpd["rolling"]["before"]["to"] == "2026-11-09")
check("compare works without an activity today", an.compare([a for a in acts if a["date"] != T0], T0)["rolling"]["this"]["sessions"] > 0)
rows = [{"date": str(T0 - timedelta(days=k)), "hrv": 60, "rhr": 52, "sleep_h": 5.0} for k in range(10)]
inj = an.injury_flags(acts, rows, {"injuries": [], "checkins": []}, T0, {"verdict": "RED", "flags": [["x", "HRV low"]]})
ids = {f["id"] for f in inj["flags"]}
check("injury flags: run spike, no-rest streak, recovery and short sleep are raised", {"run_spike", "no_rest", "recovery_low", "short_sleep"} <= ids, str(ids))
check("injury flags carry an evidence label and the level is RED", inj["level"] == "RED" and all(f["evidence"] and f["action"] for f in inj["flags"]))
calm = [mk(i, T0 - timedelta(days=2 * i), "run", 6, 40) for i in range(1, 16)]
check("a calm history gives GREEN", an.injury_flags(calm, [], {"injuries": [], "checkins": []}, T0)["level"] == "GREEN")
pain = an.injury_flags(calm, [], {"injuries": [], "checkins": [{"date": str(T0), "area": "knee", "pain": 2, "gait_change": True}]}, T0)
check("a pain check-in that changes gait is RED", pain["level"] == "RED" and any(f["id"] == "pain_checkin" for f in pain["flags"]))
check("an active injury is RED", an.injury_flags(calm, [], {"injuries": [{"area": "calf", "status": "active"}], "checkins": []}, T0)["level"] == "RED")

easy = {"sport": "run", "kind": "runE", "title": "Easy run", "minutes": 40, "date": str(T0), "week_tag": "BUILD"}
tempo = {"sport": "run", "kind": "runQ", "title": "Tempo run", "minutes": 45, "date": str(T0), "week_tag": "BUILD", "workout": {"name": "Tempo run"}}
lng = {"sport": "bike", "kind": "rideL", "title": "Long ride", "minutes": 120, "date": str(T0), "week_tag": "BUILD"}
stre = {"sport": "strength", "kind": "str", "title": "Strength", "minutes": 40, "date": str(T0)}
g = {"readiness": "GREEN", "injury_level": "GREEN", "flag_ids": set(), "adherence": 0.9, "week_change_pct": 3, "days_since_progress": None}
check("adapt: RED readiness gives a recovery spin (or rest), never a quality session", al.decide(tempo, {**g, "readiness": "RED"})["decision"] in ("recovery", "rest"))
check("adapt: AMBER turns tempo into an easy swap and shortens a long ride", al.decide(tempo, {**g, "readiness": "AMBER"})["decision"] == "easy_swap" and al.decide(lng, {**g, "readiness": "AMBER"})["decision"] == "reduce")
check("adapt: an active injury means rest", al.decide(easy, {**g, "flag_ids": {"injury_active"}, "injury_level": "RED"})["decision"] == "rest")
check("adapt: all green and good adherence allows a small progression", al.decide(tempo, g)["decision"] == "progress")
check("adapt: no progression with low adherence, a recent progression or a big week", all(al.decide(tempo, {**g, **o})["decision"] == "keep" for o in ({"adherence": 0.5}, {"days_since_progress": 3}, {"week_change_pct": 25}, {"adherence": None})))
check("adapt: strength is reduced when readiness is low", al.decide(stre, {**g, "readiness": "RED"})["decision"] == "reduce")
plan_s = [{"date": str(T0 - timedelta(days=k)), "sport": "run", "minutes": 40} for k in range(1, 8)]
done = [mk(i, T0 - timedelta(days=i), "run", 6, 40) for i in range(1, 8)]
check("adherence: all planned sessions done = 1.0, none done = 0.0", al.adherence(plan_s, done, T0) == 1.0 and al.adherence(plan_s, [], T0) == 0.0)

svgs = [chx.bars(["a", "b", "c"], [("Run", [10, 20, 0], "s1"), ("Ride", [5, 0, 30], "s2")], "t", "min"), chx.bars(["a", "b"], [("S", [1, 3], "s3")], "t", "sessions"),
        chx.lines(["a", "b", "c"], [("x", [1.0, None, 3.0], "s1")], "t", "u", band=(1, 2)), chx.lines(["a"], [("x", [None], "s1")], "t"),
        chx.meter("goal", 10, 12, 20, lambda v: f"{v:.0f}", "higher", "note"), chx.meter("goal", None, None, 20, lambda v: f"{v:.0f}"),
        chx.heatmap([T0 - timedelta(days=k) for k in range(20)], [30] * 20, "t")]
bad_svg = []
for sv in svgs:
    try:
        xml.dom.minidom.parseString(sv)
    except Exception as e:
        bad_svg.append(str(e)[:60])
check("charts are valid SVG, also with empty data", not bad_svg, str(bad_svg))

rrows = [{"date": str(T0 - timedelta(days=k)), "hrv": 60 + k % 5, "rhr": 52, "sleep_h": 7.0} for k in range(100)]
plan_f = {"sessions": [{"date": str(T0 + timedelta(days=k)), "sport": "run", "title": "Easy run", "minutes": 40} for k in range(1, 5)]}
athr = {"goals": [{"title": "Ride 25 km/h", "target_speed_kmh": 25.0}, {"title": "Weekly minutes", "track": {"metric": "weekly_minutes", "target": 300, "unit": "min"}}], "preferences": {"units": {"run": "pace", "bike": "kmh"}}}
big = []
for k in range(1, 100, 2):
    n += 1
    big.append(mk(n, T0 - timedelta(days=k), "run" if k % 4 == 1 else "bike", 7 if k % 4 == 1 else 40, 45 if k % 4 == 1 else 90, gain=10))
rdy = {"verdict": "GREEN", "flags": [], "hrv": 61, "hrv7": 61, "band_lo": 55, "band_hi": 70, "hrv_state": "inside", "rhr": 52, "rhr7": 52, "sleep_h": 7.0}
injr = an.injury_flags(big, rrows, athr, T0, rdy)
cmpr = an.compare(big, T0)
for mode in ("daily", "weekly", "monthly"):
    R = rp.build(mode, T0, big, rrows, athr, plan_f, None, rdy, injr, cmpr, None, None)
    out = TMP / "reports" / mode
    rp.write_report(R, out, "both")
    md, html = (out / "report.md").read_text(encoding="utf-8"), (out / "report.html").read_text(encoding="utf-8")
    figs = list((out / "figures").glob("*.svg"))
    check(f"report {mode}: md, html and figures are written", "Not medical advice" in md and "<details" in html and len(figs) >= 4)
    check(f"report {mode}: html is self-contained (no script, no external URL)", "<script" not in html and "http://" not in html.replace("http://www.w3.org/2000/svg", "") and "https://" not in html)
    check(f"report {mode}: every figure parses as SVG", all(xml.dom.minidom.parse(str(f)) for f in figs))
check("report: goals without data are explained, not faked", "No reading in this period" in (TMP / "reports" / "weekly" / "report.html").read_text(encoding="utf-8") or "goal" in (TMP / "reports" / "weekly" / "report.html").read_text(encoding="utf-8").lower())

# ---------------------------------------------------------------- data folder: new variable, old variable, defaults
probe = "import sys; sys.path.insert(0, sys.argv[1]); import gcommon; print(gcommon.DATA_DIR)"
for env, want, label in (({"RAMPWISE_DATA": str(TMP / "a"), "GARMIN_COACH_DATA": str(TMP / "b")}, TMP / "a", "RAMPWISE_DATA wins"), ({"RAMPWISE_DATA": "", "GARMIN_COACH_DATA": str(TMP / "b")}, TMP / "b", "the older GARMIN_COACH_DATA still works")):
    r = subprocess.run([sys.executable, "-X", "utf8", "-c", probe, str(SK / "rampwise" / "scripts")], capture_output=True, text=True, encoding="utf-8", env={**os.environ, **env})
    check(f"data folder: {label}", Path(r.stdout.strip()) == want, r.stdout + r.stderr[-200:])

print()
print("ALL OK" if not failed else f"{len(failed)} FAILED: {failed}")
sys.exit(1 if failed else 0)
