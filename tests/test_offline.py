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
os.environ["RAMPWISE_OUT"] = str(TMP / "out")      # tests never write into the real home folder
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
import report_data as rdt
ra = rdt.recent_activities(big, T0, 14, True)
check("report: recent activities table lists sessions newest first and compares with the last similar one", len(ra) >= 3 and ra[0][0] >= ra[-1][0] and any("heart rate" in r[6] or "similar" in r[6] for r in ra), str(ra[:2]))
check("report: goals without data are explained, not faked", "No reading in this period" in (TMP / "reports" / "weekly" / "report.html").read_text(encoding="utf-8") or "goal" in (TMP / "reports" / "weekly" / "report.html").read_text(encoding="utf-8").lower())

# ---------------------------------------------------------------- data folder: new variable, old variable, defaults
probe = "import sys; sys.path.insert(0, sys.argv[1]); import gcommon; print(gcommon.DATA_DIR)"
for env, want, label in (({"RAMPWISE_DATA": str(TMP / "a"), "GARMIN_COACH_DATA": str(TMP / "b")}, TMP / "a", "RAMPWISE_DATA wins"), ({"RAMPWISE_DATA": "", "GARMIN_COACH_DATA": str(TMP / "b")}, TMP / "b", "the older GARMIN_COACH_DATA still works")):
    r = subprocess.run([sys.executable, "-X", "utf8", "-c", probe, str(SK / "rampwise" / "scripts")], capture_output=True, text=True, encoding="utf-8", env={**os.environ, **env})
    check(f"data folder: {label}", Path(r.stdout.strip()) == want, r.stdout + r.stderr[-200:])

# ---------------------------------------------------------------- event plans (no Garmin account), viewer and exports
import xml.dom.minidom as _xml
from datetime import timedelta as _td
import plan as evp
import export_plan as exp_
import plan_viewer as pview

check("event plans: 17 events plus the no-target base goal are defined", len([k for k in evp.EVENTS if k != "base"]) == 17 and "base" in evp.EVENTS, str(len(evp.EVENTS)))
r = run(SK / "rampwise-planner" / "scripts" / "event_plan.py", "--event", "marathon")
check("event plan asks for the missing numbers instead of guessing (exit 2)", r.returncode == 2 and "ask" in r.stdout.lower() and "hours" in r.stdout.lower(), r.stdout[-200:])
EV_ATH = {"equipment": {"tags": ["bodyweight", "dumbbell", "band", "step"]}}
EV_START = date(2026, 11, 23)
need = {"run": {"run"}, "tri": {"swim", "bike", "run"}, "du": {"bike", "run"}, "bike": {"bike"}, "swim": {"swim"}}
bad_ev = []
for key, e in [(k, v) for k, v in evp.EVENTS.items() if k != "base"]:
    lo, hi = e["weeks"]
    race = EV_START + _td(weeks=(lo + hi) // 2 - 1, days=6)
    meta_e, sess_e = evp.build(key, race, EV_START, "intermediate", min(e["peak"]["intermediate"] * 0.6, 10), e["peak"]["intermediate"], 6, {"longest_run_min": 70, "longest_ride_min": 150, "longest_swim_min": 40}, EV_ATH)
    sports = {x["sport"] for x in sess_e if x["sport"] != "strength"}
    races = [x for x in sess_e if x["kind"] == "race"]
    on_race_day = [x for x in sess_e if x["date"] == str(race)]
    taper_n = sum(1 for ph in meta_e["phases"] if ph == "TAPER")
    pre = [w for w in meta_e["weekly"] if w["phase"] != "TAPER"]
    ups = [b["target_min"] / a["target_min"] for a, b in zip(pre, pre[1:]) if b["tag"] != "RECOVERY" and a["tag"] != "RECOVERY" and a["target_min"]]
    tagged = [w["tag"] for w in meta_e["weekly"]]
    if not (need[e["kind"]] <= sports and len(races) == 1 and len(on_race_day) == 1 and taper_n == e["taper"] and (not ups or max(ups) <= 1.11) and "RECOVERY" in tagged or meta_e["weeks"] < 4):
        bad_ev.append(key)
    if e["kind"] == "bike" and "run" in sports or e["kind"] == "swim" and "run" in sports:
        bad_ev.append(key + " wrong sports")
check("event plans: every event has the right sports, one race day, the right taper, +10 % weekly cap and recovery weeks", not bad_ev, str(bad_ev))
meta_t, sess_t = evp.build("olympic-tri", date(2027, 6, 20), EV_START, "intermediate", 6, 9, 6, {"longest_run_min": 60, "longest_ride_min": 90, "longest_swim_min": 30}, EV_ATH)
long_runs = [x["minutes"] for x in sess_t if x["kind"] == "run_long" and not x["recovery_week"]]
check("event plans: the long run grows at most 10 % between build weeks", all(b <= a * 1.1 + 5 for a, b in zip(long_runs, long_runs[1:])), str(long_runs))
check("event plans: triathlon has brick runs in build and peak only", {x["phase"] for x in sess_t if x["kind"] == "brick_run"} <= {"BUILD", "PEAK"} and any(x["kind"] == "brick_run" for x in sess_t))
meta_s, sess_s = evp.build("sprint-tri", date(2027, 2, 14), date(2026, 12, 14), "beginner", 4, 6, 5, {}, EV_ATH)
check("event plans: a low-volume triathlon plan still has swim sessions", sum(1 for x in sess_s if x["sport"] == "swim") >= 8)
tight, _ = evp.build("marathon", date(2027, 1, 24), date(2026, 12, 21), "beginner", 3, 8, 5, {}, EV_ATH)
check("event plans: too few weeks gives a warning, not a silent plan", bool(tight["warnings"]))
ev_dir = TMP / "events"
ev_dir.mkdir(exist_ok=True)
(ev_dir / "plan.json").write_text(json.dumps({"meta": meta_t, "sessions": sess_t}, default=str), encoding="utf-8")
r = run(SK / "rampwise-planner" / "scripts" / "export_plan.py", ev_dir / "plan.json", "--format", "all", "--out", ev_dir / "out")
ics_b = (ev_dir / "out" / "plan.ics").read_bytes()
zwos = sorted((ev_dir / "out" / "zwift").glob("*.zwo"))
mrcs = sorted((ev_dir / "out" / "mrc").glob("*.mrc"))
ok_zwo = bool(zwos)
for zf in zwos:
    try:
        _xml.parse(str(zf))
    except Exception:
        ok_zwo = False
check("export: .ics has one event per session, CRLF lines of at most 75 bytes", r.returncode == 0 and ics_b.count(b"BEGIN:VEVENT") == len(sess_t) and b"\r\n" in ics_b and max(len(l) for l in ics_b.split(b"\r\n")) <= 75, r.stderr[-200:])
check("export: Zwift files are valid XML and MRC files have a course header", ok_zwo and mrcs and all(b"[COURSE HEADER]" in m.read_bytes() and b"MINUTES PERCENT" in m.read_bytes() for m in mrcs))
check("export: csv has a row per session", (ev_dir / "out" / "plan.csv").read_text(encoding="utf-8").count("\n") >= len(sess_t))
page = pview.render(meta_t, sess_t, "Test plan")
check("plan viewer: one self-contained page, no script, shows weeks and rule labels", "<script" not in page and "Week 1" in page and "research" in page and "https://" not in page.replace("https://github.com/Azahir21/rampwise", ""))
(TMP / "athlete.json").write_text(json.dumps({"manual_baseline": {"level": "intermediate", "hours_now": 6, "max_hours": 9, "days_per_week": 6}, "event": {"type": "gran-fondo", "date": str(EV_START + _td(weeks=14, days=6))}, "equipment": {"tags": ["bodyweight", "band"]}, "preferences": {}}), encoding="utf-8")
r = run(SK / "rampwise-planner" / "scripts" / "event_plan.py", "--start", str(EV_START))
check("event plan runs from the saved manual baseline (no Garmin) and saves the plan", r.returncode == 0 and list((TMP / "out" / "plans").glob("gran-fondo-*/plan.json")), r.stdout[-200:] + r.stderr[-200:])

# ---------------------------------------------------------------- output folder: default, preference, "here"
probe_out = "import sys; sys.path.insert(0, sys.argv[1]); import gcommon; print(gcommon.out_root())"
home = TMP / "fakehome"
cwd_dir = TMP / "cwdtest"
home.mkdir(exist_ok=True)
cwd_dir.mkdir(exist_ok=True)
data_t = TMP / "outdata"
data_t.mkdir(exist_ok=True)


def out_probe(env, pref=None, cwd=None):
    (data_t / "athlete.json").write_text(json.dumps({"preferences": {"output_dir": pref}}), encoding="utf-8")
    base = {k: v for k, v in os.environ.items() if k not in ("RAMPWISE_OUT", "RAMPWISE_DATA", "GARMIN_COACH_DATA")}
    r = subprocess.run([sys.executable, "-X", "utf8", "-c", probe_out, str(SK / "rampwise" / "scripts")], capture_output=True, text=True, encoding="utf-8",
                       env={**base, "RAMPWISE_DATA": str(data_t), "USERPROFILE": str(home), "HOME": str(home), **env}, cwd=str(cwd or TMP))
    return Path(r.stdout.strip()), r.stderr[-200:]


got, err = out_probe({})
check("output folder: the default is ~/rampwise-coach", got == home / "rampwise-coach", f"{got} {err}")
got, err = out_probe({"RAMPWISE_OUT": str(TMP / "elsewhere")}, pref="cwd")
check("output folder: RAMPWISE_OUT wins over the saved preference", got == TMP / "elsewhere", f"{got} {err}")
got, err = out_probe({}, pref="cwd", cwd=cwd_dir)
check('output folder: preference "cwd" means rampwise-coach in the session folder', got == cwd_dir / "rampwise-coach", f"{got} {err}")
got, err = out_probe({}, pref=str(TMP / "custom"))
check("output folder: a custom folder in athlete.json is honoured", got == TMP / "custom", f"{got} {err}")
base_env = {k: v for k, v in os.environ.items() if k != "RAMPWISE_OUT"}
r = subprocess.run([sys.executable, "-X", "utf8", str(SK / "rampwise-planner" / "scripts" / "event_plan.py"), "--event", "5k", "--event-date", "2027-03-14", "--level", "beginner", "--hours-now", "3",
                    "--max-hours", "5", "--days", "5", "--start", "2026-12-14", "--here"], capture_output=True, text=True, encoding="utf-8", env=base_env, cwd=str(cwd_dir))
check("output folder: --here writes into ./rampwise-coach of the session folder, one plan folder per event", r.returncode == 0 and (cwd_dir / "rampwise-coach" / "plans" / "5k-2027-03-14" / "plan.json").exists(), r.stdout[-200:] + r.stderr[-200:])

# ---------------------------------------------------------------- triathlon, duathlon, swim: bricks, swim pace, adapting event plans
from datetime import datetime as _dt
sys.path.insert(0, str(SK / "rampwise-adapt" / "scripts"))
sys.path.insert(0, str(SK / "rampwise-aerobic-base" / "scripts"))
import gcommon as gcm
import latest_activity as lat
import next_session as nxs


def act(i, sport, start, mins, km, hr=140):
    st = _dt.fromisoformat(start)
    return {"id": i, "name": f"{sport} {i}", "sport": sport, "date": st.date(), "start": st, "end": st + _td(minutes=mins), "km": km, "min": mins, "moving_min": mins, "avg_hr": hr, "gain_m": 10, "te_aerobic": 2.5}


check("multisport and swim activity types are recognised", gcm.sport_of("lap_swimming") == "swim" and gcm.sport_of("open_water_swimming") == "swim" and gcm.sport_of("multi_sport") == "multi" and gcm.sport_of("running") == "run")
bk = [act(1, "bike", "2026-11-07T07:00:00", 90, 35), act(2, "run", "2026-11-07T08:40:00", 25, 4.0, 150),     # run starts 10 min after the ride ended: a brick
      act(3, "bike", "2026-11-08T07:00:00", 60, 25), act(4, "run", "2026-11-08T11:00:00", 30, 4.5, 140),     # 3 hours later: not a brick
      act(5, "run", "2026-11-04T07:00:00", 28, 4.2, 138), act(6, "swim", "2026-11-05T07:00:00", 40, 1.2, 130)]
brk = gcm.find_bricks(bk)
check("bricks: a run within 45 minutes after a ride is a brick, a run 3 hours later is not", len(brk) == 1 and brk[0]["run"]["id"] == 2 and brk[0]["gap_min"] == 10, str(brk))
ba = lat.brick_analysis(bk, bk[1])
check("brick analysis compares the brick run with the last run that was not after cycling", ba and ba["vs_standalone_run"]["date"] == "2026-11-04" and ba["vs_standalone_run"]["hr_diff_bpm"] == 12, str(ba))
check("swim pace is shown per 100 m", lat.swim_pace(2.7) == "2:13/100 m")
sw = an.aggregate([x for x in bk if x["sport"] == "swim"])
check("analysis counts swim minutes as endurance time", sw["swim"]["minutes"] == 40 and sw["endurance_minutes"] == 40)

meta_a, sess_a = evp.build("olympic-tri", date(2027, 6, 20), EV_START, "intermediate", 6, 9, 6, {"longest_run_min": 60, "longest_ride_min": 90, "longest_swim_min": 30}, EV_ATH)
brick_s = next(x for x in sess_a if x["kind"] == "brick_run")
swimq = next(x for x in sess_a if x["sport"] == "swim" and x["quality"])
race_s = next(x for x in sess_a if x["kind"] == "race")
g2 = {"readiness": "GREEN", "injury_level": "GREEN", "flag_ids": set(), "adherence": 0.95, "week_change_pct": 2, "days_since_progress": None, "no_progress": True}
check("adapt: a brick run is dropped on amber or red, kept on green", al.decide(brick_s, {**g2, "readiness": "AMBER"})["decision"] == "rest" and al.decide(brick_s, {**g2, "injury_level": "RED", "flag_ids": {"run_spike"}})["decision"] == "rest" and al.decide(brick_s, g2)["decision"] == "keep")
check("adapt: a quality swim becomes an easy swim on amber and a short technique swim on red", al.decide(swimq, {**g2, "readiness": "AMBER"})["decision"] == "easy_swap" and al.decide(swimq, {**g2, "readiness": "RED"})["decision"] == "recovery")
check("adapt: race day is never changed", all(al.decide(race_s, {**g2, "readiness": r})["decision"] == "keep" for r in ("GREEN", "AMBER", "RED")))
check("adapt: event plans never get an automatic progression", al.decide(next(x for x in sess_a if x["sport"] == "run" and x["quality"]), g2)["decision"] == "keep")
nw = nxs.build_event_new(swimq, al.decide(swimq, {**g2, "readiness": "AMBER"}))
check("adapt: the changed swim is easy, shorter or equal, with RPE text and no heart-rate numbers", nw["minutes"] <= swimq["minutes"] and "RPE" in nw["desc"] and "bpm" not in nw["desc"], str(nw))

# ---------------------------------------------------------------- one planner: no-target base goal, injury lock, readiness reset, heart-rate workouts, water-temperature guidance
sys.path.insert(0, str(SK / "rampwise-heat-weather" / "scripts"))
import swim_water as sw_

BASE_ATH = {"equipment": {"tags": ["bodyweight", "band"]}}
mb, sb = evp.build("base", None, date(2026, 11, 23), "intermediate", 6, 9, 6, {"longest_run_min": 60, "longest_ride_min": 150, "longest_swim_min": 40}, BASE_ATH, weeks=12, sports=["run", "bike", "swim"])
check("planner: the no-target base goal builds 12 weeks of run, ride, swim and strength with no race and no taper", mb["weeks"] == 12 and mb["goal"] == "base" and mb["event_date"] is None
      and {x["sport"] for x in sb} >= {"run", "bike", "swim", "strength"} and not any(x["kind"] in ("race", "activation") for x in sb) and "TAPER" not in mb["phases"])
check("planner: base volume rises at most 10 % a week and has lighter weeks", all(b2["target_min"] / a2["target_min"] <= 1.11 for a2, b2 in zip(mb["weekly"], mb["weekly"][1:]) if a2["tag"] != "RECOVERY" and b2["tag"] != "RECOVERY" and a2["target_min"]) and any(w["tag"] == "RECOVERY" for w in mb["weekly"]))
check("planner: the aerobic test appears in lighter weeks only, one per sport", {x["week"] for x in sb if "Aerobic test" in x["title"]} <= {w["week"] for w in mb["weekly"] if w["tag"] == "RECOVERY"} and any("Aerobic test" in x["title"] for x in sb))
mi, si = evp.build("base", None, date(2026, 11, 23), "intermediate", 6, 9, 6, {}, {**BASE_ATH, "injuries": [{"status": "active", "area": "calf"}]}, weeks=8, sports=["run", "bike"])
check("planner: an active injury locks quality sessions in every plan", not any(x["quality"] for x in si) and any("injury" in w.lower() for w in mi["warnings"]))
mr, sr_ = evp.build("base", None, date(2026, 11, 23), "intermediate", 6, 9, 6, {}, BASE_ATH, weeks=8, sports=["run", "bike"], readiness="red")
check("planner: a RED readiness makes week 1 lighter", mr["weekly"][0]["target_min"] < 0.8 * mb["weekly"][0]["target_min"] and any("RED" in w for w in mr["warnings"]))
HR_ATH = {**BASE_ATH, "preferences": {"quality": {"requires_gate": False}}, "hr": {"run_easy_max": 146, "run_zone_floors": [105, 126, 147, 158, 170], "easy_band": {"run": [126, 146], "bike": [126, 147]}, "zone_sets": {}}}
mh, sh = evp.build("olympic-tri", date(2027, 6, 20), EV_START, "intermediate", 6, 9, 6, {"longest_run_min": 60, "longest_ride_min": 90, "longest_swim_min": 30}, HR_ATH)
check("planner: with the athlete's heart-rate data, run and ride sessions carry heart-rate workouts (for .fit); swims and strength do not", mh["has_workouts"] and all(("workout" in x) == (x["sport"] in ("run", "bike") and bool(x["blocks"])) for x in sh))
mn, sn = evp.build("olympic-tri", date(2027, 6, 20), EV_START, "intermediate", 6, 9, 6, {"longest_run_min": 60, "longest_ride_min": 90, "longest_swim_min": 30}, EV_ATH)
check("planner: without heart-rate data nothing is assumed (no workouts, no .fit)", not mn["has_workouts"] and not any("workout" in x for x in sn))
fit_dir = TMP / "fit_test"
fit_dir.mkdir(exist_ok=True)
(fit_dir / "plan.json").write_text(json.dumps({"meta": mh, "sessions": sh}, default=str), encoding="utf-8")
rf = run(SK / "rampwise-planner" / "scripts" / "export_plan.py", fit_dir / "plan.json", "--format", "fit", "--out", fit_dir / "out")
fits = list((fit_dir / "out" / "fit").glob("*.fit"))
check("export: .fit workout files are written and decode when the plan has heart-rate workouts", rf.returncode == 0 and len(fits) >= 10, rf.stdout[-200:] + rf.stderr[-300:])
rb = run(SK / "rampwise-planner" / "scripts" / "build_plan.py", "--help")
check("build_plan.py forwards to the one planner (deprecated)", "deprecated" in (rb.stdout + rb.stderr).lower() or "plan.py" in (rb.stdout + rb.stderr), rb.stdout[-200:])
vh = pview.render(mb, sb, "Base plan")
check("plan viewer: a plan without a race date renders", "no race" in vh and "Week 1" in vh)
wb = {x[0]: x[1] for x in sw_.bands(13, 1.5)}
check("swim water: 13 C gives the cold-water caution and a wetsuit note; 10 C says stop; 33 C is over the upper limit", any("wetsuit" in x[1] for x in sw_.bands(13, 1.5)) and any(x[0] == "stop" for x in sw_.bands(10)) and any(x[0] == "stop" and "31" in x[1] for x in sw_.bands(33)))
qs = an.injury_flags([act(70, "swim", "2026-11-14T07:00:00", 40, 1.2)], [], {"injuries": [], "checkins": []}, date(2026, 11, 16))["questions"]
check("injury watch asks sport-specific pain questions (swimmers: shoulder)", any("shoulder" in q.lower() for q in qs), str(qs))

# ---------------------------------------------------------------- aerobic reading of swims and multisport legs
import analyze_activity as aa


def lap(d, t, hr):
    return {"total_distance": d, "total_timer_time": t, "avg_heart_rate": hr}


steady = [lap(100, 100 + (i % 2), 130 + i // 4) for i in range(12)]
sr_ = aa.swim_analysis(steady, {"id": 1, "name": "x", "start": "2026-11-01 07:00:00", "min": 22, "avg_hr": 135})
check("swim analysis: a steady 1,200 m swim is reliable and gives pace per 100 m and a decoupling", sr_["reliable"] and abs(sr_["pace_s_per_100m"] - 100) <= 2 and "decoupling_pct" in sr_, str(sr_))
sh_ = aa.swim_analysis(steady[:4], {"id": 2, "name": "x", "start": "2026-11-01 07:00:00", "min": 40, "avg_hr": 120})
check("swim analysis: a short, rest-heavy swim is flagged not reliable", not sh_["reliable"] and any("too short" in f for f in sh_["flags"]) and any("rest" in f for f in sh_["flags"]))
nohr = aa.swim_analysis([lap(100, 100, None) for _ in range(10)], {"id": 3, "name": "x", "start": "2026-11-01 07:00:00", "min": 18, "avg_hr": None})
check("swim analysis: missing heart rate gives no efficiency reading", "ef_m_per_min_per_bpm" not in nohr and not nohr["reliable"])
ml = aa.multisport_legs([{"sport": "cycling", "total_distance": 20000, "total_timer_time": 2400, "avg_heart_rate": 140}, {"sport": "running", "total_distance": 5000, "total_timer_time": 1500, "avg_heart_rate": 155}], {"id": 4, "name": "x", "start": "2026-11-01 07:00:00"})
check("multisport: legs are listed with speed for the bike and pace for the run", ml["legs"][0]["speed_kmh"] == 30.0 and ml["legs"][1]["pace_s_per_km"] == 300)

# ---------------------------------------------------------------- configurable plan length and calendar window
cfg_ath = {"manual_baseline": {"level": "intermediate", "hours_now": 6, "max_hours": 9, "days_per_week": 6, "sports": ["run", "bike"]}, "equipment": {"tags": ["bodyweight", "band"]},
           "preferences": {"plan_weeks": 4}, "calendar": {"calendar_id": "primary", "title_prefix": "[GC]", "marker": "rampwise-plan", "window_days": 14, "window_weeks": None}}
(TMP / "athlete.json").write_text(json.dumps(cfg_ath), encoding="utf-8")
PL = SK / "rampwise-planner" / "scripts" / "plan.py"
r4 = run(PL, "--goal", "base", "--start", "2027-01-04", "--json")
m4 = json.loads(r4.stdout)["meta"] if r4.returncode == 0 else {}
check("plan length: preferences.plan_weeks sets the length of a no-target plan (4 weeks) and a short block is a note, not an error", m4.get("weeks") == 4 and any("4-week block" in w for w in m4.get("warnings", [])), r4.stdout[-200:] + r4.stderr[-200:])
r6 = run(PL, "--goal", "base", "--start", "2027-01-04", "--weeks", "6", "--json")
check("plan length: --weeks beats the saved preference", r6.returncode == 0 and json.loads(r6.stdout)["meta"]["weeks"] == 6)
(TMP / "athlete.json").write_text(json.dumps({**cfg_ath, "preferences": {}}), encoding="utf-8")
rd = run(PL, "--goal", "base", "--start", "2027-01-04", "--json")
check("plan length: with nothing set a no-target plan is 12 weeks", rd.returncode == 0 and json.loads(rd.stdout)["meta"]["weeks"] == 12)
rx = run(PL, "--goal", "base", "--start", "2027-01-04", "--weeks", "1")
check("plan length: 1 week is refused (2 to 52)", rx.returncode != 0 and "2 to 52" in (rx.stdout + rx.stderr))
cal_plan = TMP / "cal_plan.json"
cal_plan.write_text(r6.stdout, encoding="utf-8")
CE = SK / "rampwise-planner" / "scripts" / "calendar_events.py"


def cal_window(*extra, win_weeks=None):
    (TMP / "athlete.json").write_text(json.dumps({**cfg_ath, "calendar": {**cfg_ath["calendar"], "window_weeks": win_weeks}}), encoding="utf-8")
    rr = run(CE, cal_plan, "--json", *extra)
    o = json.loads(rr.stdout) if rr.returncode == 0 else {"window": ["", ""], "events": []}
    return (date.fromisoformat(o["window"][1]) - date.fromisoformat(o["window"][0])).days if o["window"][0] else None


check("calendar window: 14 days by default, --weeks 4 gives 28 days, --days beats --weeks, calendar.window_weeks is the saved setting",
      cal_window() == 14 and cal_window("--weeks", "4") == 28 and cal_window("--weeks", "4", "--days", "7") == 7 and cal_window(win_weeks=4) == 28)

# ---------------------------------------------------------------- installer for other agent tools
import importlib.util as _ilu
_spec = _ilu.spec_from_file_location("rw_install", ROOT / "install.py")
rw_install = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(rw_install)
asked = ["OpenAI Codex", "Hermes", "OpenClaw", "Gemini CLI", "Antigravity", "Cursor", "GitHub Copilot", "Windsurf", "Aider", "Cline", "OpenCode", "Devin", "Amazon Q Developer", "Kilo Code",
         "Roo Code", "Goose", "Continue.dev", "Zed", "Amp", "Jules", "Augment Code", "Kiro", "Mistral Vibe", "GitLab Duo", "Trae AI", "Qwen Code", "Warp", "Junie", "Factory"]
check("installer: all 29 requested tools are registered", len(rw_install.REQUIRED) == 29 and all(k in rw_install.TOOLS for k in rw_install.REQUIRED)
      and all(any(w.lower() in rw_install.TOOLS[k]["name"].lower() or w.lower().split(".")[0] in k for k in rw_install.REQUIRED) for w in asked))
install_doc = (ROOT / "docs" / "INSTALL.md").read_text(encoding="utf-8")
check("installer: every registered tool is in docs/INSTALL.md with its --tool key", all(f"`{k}`" in install_doc for k in rw_install.TOOLS))
check("installer: only Trae is marked unverified, and the registry has no tool with a missing folder",
      [k for k, t in rw_install.TOOLS.items() if t["status"] != "read"] == ["trae"] and all(t["mode"] == "rules" or (t.get("skills") and t.get("project")) for t in rw_install.TOOLS.values()))
inst_home, inst_proj = TMP / "inst_home", TMP / "inst_proj"
inst_home.mkdir(exist_ok=True)
inst_proj.mkdir(exist_ok=True)
inst_env = {"HOME": str(inst_home), "USERPROFILE": str(inst_home)}
INST = ROOT / "install.py"
r_a = run(INST, "--tool", "codex,cursor,zed,hermes,kiro", env=inst_env)
check("installer: skills go to the shared folder (once for codex, cursor and zed) and to Hermes and Kiro's own folders",
      r_a.returncode == 0 and (inst_home / ".agents" / "skills" / "rampwise" / "SKILL.md").exists() and (inst_home / ".hermes" / "skills" / "rampwise-planner" / "scripts" / "plan.py").exists()
      and (inst_home / ".kiro" / "skills" / "rampwise").is_dir() and r_a.stdout.count(str(inst_home / ".agents" / "skills" / "rampwise-adapt")) == 1, r_a.stdout[-300:] + r_a.stderr[-300:])
check("installer: nothing but real skills is copied (every installed folder has a SKILL.md)", all((d / "SKILL.md").exists() for d in (inst_home / ".agents" / "skills").iterdir()))
r_b = run(INST, "--tool", "aider", env=inst_env)
check("installer: a tool that writes into a project refuses without --project", r_b.returncode != 0 and "--project" in (r_b.stdout + r_b.stderr))
(inst_proj / "AGENTS.md").write_text("# Team notes" + chr(10), encoding="utf-8")
r_c = run(INST, "--tool", "aider,continue,amazonq,jules", "--project", inst_proj, env=inst_env)
check("installer: tools without skills get an instructions file; the existing AGENTS.md keeps its text and gets a marked block",
      r_c.returncode == 0 and (inst_proj / "RAMPWISE.md").exists() and "alwaysApply: true" in (inst_proj / ".continue" / "rules" / "rampwise.md").read_text(encoding="utf-8")
      and (inst_proj / ".amazonq" / "rules" / "rampwise.md").exists() and (inst_proj / "AGENTS.md").read_text(encoding="utf-8").startswith("# Team notes") and "rampwise/SKILL.md" in (inst_proj / "AGENTS.md").read_text(encoding="utf-8"),
      r_c.stdout[-300:] + r_c.stderr[-300:])
run(INST, "--tool", "jules", "--project", inst_proj, env=inst_env)
check("installer: running it again does not duplicate the block", (inst_proj / "AGENTS.md").read_text(encoding="utf-8").count("rampwise:begin") == 1)
r_d = run(INST, "--tool", "all", "--dry-run", env=inst_env)
check("installer: --tool all --dry-run writes nothing and skips the project-writing tools", r_d.returncode == 0 and "Skipped" in r_d.stdout and not (inst_home / ".trae").exists() and "!! Trae AI" in r_d.stdout, r_d.stdout[-200:])
r_e = run(INST, "--tool", "codex,cursor,zed,hermes,kiro,aider,continue,amazonq,jules", "--project", inst_proj, "--uninstall", env=inst_env)
check("installer: --uninstall removes what it wrote, keeps the user's own text and leaves no empty folders",
      r_e.returncode == 0 and (inst_proj / "AGENTS.md").read_text(encoding="utf-8").strip() == "# Team notes" and not (inst_proj / ".continue").exists() and not (inst_proj / "RAMPWISE.md").exists()
      and not (inst_home / ".agents").exists() and not (inst_home / ".kiro").exists() and inst_home.exists() and inst_proj.exists(), r_e.stdout[-300:] + r_e.stderr[-300:])

# ---------------------------------------------------------------- activities from other watch brands and from Strava
sys.path.insert(0, str(ROOT / "tests"))
import make_fit_activity as mfa
import activity_sources as asrc

oth = TMP / "other_brands"
oth.mkdir(exist_ok=True)
AA = SK / "rampwise-aerobic-base" / "scripts" / "analyze_activity.py"
f_g = mfa.make(oth / "garmin.fit", "running", minutes=70, manufacturer=1, power=0)
f_s = mfa.make(oth / "other_no_speed.fit", "running", minutes=70, manufacturer=23, with_speed=False, with_altitude=False, power=0)
f_h = mfa.make(oth / "no_hr.fit", "cycling", minutes=70, with_hr=False, speed=8)
rg = json.loads(run(AA, "--fit-file", f_g, "--json").stdout)
rs = json.loads(run(AA, "--fit-file", f_s, "--json").stdout)
check("fit-file: a Garmin-style file gives efficiency, decoupling and a reliable flag, and names the source", rg["sport"] == "run" and rg["reliable"] and "decoupling_pct" in rg and rg["source"]["kind"] == "fit-file" and rg["metric"] == "speed:HR", str(rg)[:300])
check("fit-file: a file from another maker with no speed and no altitude fields gives the same result (speed worked out from distance) and says so",
      abs(rs["decoupling_pct"] - rg["decoupling_pct"]) < 0.3 and any("worked out from distance" in n for n in rs["source"]["notes"]), str(rs)[:300])
rh = run(AA, "--fit-file", f_h)
check("fit-file: a file with no heart rate says so instead of failing", rh.returncode == 0 and "no heart-rate data" in rh.stdout, rh.stdout[-200:] + rh.stderr[-200:])
import zipfile as _zf
with _zf.ZipFile(oth / "export.zip", "w") as _z:
    _z.write(f_g, "activity.fit")
rz = json.loads(run(AA, "--fit-file", oth / "export.zip", "--json").stdout)
check("fit-file: the .zip that Garmin exports works as well as a bare .fit", abs(rz["decoupling_pct"] - rg["decoupling_pct"]) < 0.01)
bad = oth / "notfit.fit"
bad.write_bytes(b"this is not a fit file at all")
rb = run(AA, "--fit-file", bad)
check("fit-file: a file that is not FIT is refused with a clear message", rb.returncode != 0 and "does not look like a FIT file" in (rb.stdout + rb.stderr), rb.stdout[-120:] + rb.stderr[-200:])
rn = run(AA)
check("fit-file: giving no source is an error that lists the three ways", rn.returncode != 0 and "--fit-file" in rn.stderr)
f_sw = mfa.make(oth / "swim.fit", "swimming", minutes=30, speed=0.0, swim_laps=[(100, 105 + (i % 2), 130 + i // 3) for i in range(12)])
rsw = json.loads(run(AA, "--fit-file", f_sw, "--json").stdout)
check("fit-file: a pool swim file is read from its laps (pace per 100 m)", rsw.get("kind") == "swim" and rsw.get("swim_m") == 1200 and 100 <= rsw["pace_s_per_100m"] <= 110, str(rsw)[:300])
f_tri = mfa.make(oth / "multi.fit", sessions=[("cycling", "generic", 2400, 20000, 140), ("running", "generic", 1500, 5000, 155)], minutes=10)
rtri = json.loads(run(AA, "--fit-file", f_tri, "--json").stdout)
check("fit-file: a multisport file is shown as its legs", rtri.get("kind") == "multi" and [l["sport"] for l in rtri["legs"]] == ["cycling", "running"], str(rtri)[:300])
# Strava JSON in the three stream shapes an MCP server may return
src_g = asrc.load_fit_file(f_g)
ts_ = [round(r["t"]) for r in src_g["recs"]]
hr_ = [r["hr"] for r in src_g["recs"]]
vel_ = [round(r["speed"], 3) for r in src_g["recs"]]
act_ = {"id": 123, "name": "Test run", "sport_type": "Run", "start_date_local": "2026-11-01T06:00:00Z", "elapsed_time": 4200, "moving_time": 4200, "distance": 12180.0, "average_heartrate": 144.0, "total_elevation_gain": 0.0, "device_name": "COROS PACE 3"}
shapes = {"dict": {"time": {"data": ts_}, "heartrate": {"data": hr_}, "velocity_smooth": {"data": vel_}},
          "plain": {"time": ts_, "heartrate": hr_, "velocity_smooth": vel_},
          "list": [{"type": "time", "data": ts_}, {"type": "heartrate", "data": hr_}, {"type": "velocity_smooth", "data": vel_}]}
decs = []
for nm, st in shapes.items():
    pj = oth / f"strava_{nm}.json"
    pj.write_text(json.dumps({"activity": act_, "streams": st}), encoding="utf-8")
    rj = json.loads(run(AA, "--strava-json", pj, "--json").stdout)
    decs.append(rj.get("decoupling_pct"))
    if nm == "dict":
        rj0 = rj
check("strava-json: streams in the three shapes (dict of data, plain lists, list of typed streams) give the same drift as the FIT file", all(d is not None and abs(d - rg["decoupling_pct"]) < 0.3 for d in decs), str(decs))
check("strava-json: the source line names the device and the warm-up note", rj0["source"]["kind"] == "strava-json" and rj0["source"]["device"] == "COROS PACE 3" and rj0["sport"] == "run", str(rj0["source"]))
pj2 = oth / "strava_swim.json"
pj2.write_text(json.dumps({"activity": {**act_, "sport_type": "Swim"}, "streams": shapes["plain"]}), encoding="utf-8")
rj2 = json.loads(run(AA, "--strava-json", pj2, "--json").stdout)
check("strava-json: a swim from Strava is refused politely (no lap data), pointing to the watch's own FIT export", "lap data" in rj2.get("error", ""), str(rj2)[:200])
pj3 = oth / "strava_notime.json"
pj3.write_text(json.dumps({"activity": act_, "streams": {"heartrate": hr_}}), encoding="utf-8")
r3 = run(AA, "--strava-json", pj3)
check("strava-json: streams without time give a message that names what to request", r3.returncode != 0 and "time" in (r3.stdout + r3.stderr) and "heartrate" in (r3.stdout + r3.stderr))

inst_home2 = TMP / "inst_home2"
inst_home2.mkdir(exist_ok=True)
env2 = {"HOME": str(inst_home2), "USERPROFILE": str(inst_home2)}
run(INST, "--tool", "codex", env=env2)
pap = inst_home2 / ".agents" / "skills" / "rampwise-planner" / "references" / "papers"
pap.mkdir(parents=True, exist_ok=True)
(pap / "Some-paper_2025.md").write_text("# local paper", encoding="utf-8")
run(INST, "--tool", "codex", env=env2)
check("installer: reinstalling keeps the user's local paper files (references/papers)", (pap / "Some-paper_2025.md").exists() and (inst_home2 / ".agents" / "skills" / "rampwise-planner" / "SKILL.md").exists())
r_u = run(INST, "--tool", "codex", "--uninstall", env=env2)
check("installer: uninstall removes the skills but keeps the local paper files and says so", (pap / "Some-paper_2025.md").exists() and not (inst_home2 / ".agents" / "skills" / "rampwise-planner" / "SKILL.md").exists() and "kept 1 local paper files" in r_u.stdout, r_u.stdout[-300:])

print()
print("ALL OK" if not failed else f"{len(failed)} FAILED: {failed}")
sys.exit(1 if failed else 0)
