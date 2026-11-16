#!/usr/bin/env python3
"""Build a rolling multi-week plan (run, ride, strength) from the athlete's own Garmin history and athlete.json.

Every run and ride is a structured Garmin workout (warm-up, steady / interval / tempo, rest, cool-down, each with a target),
built with workout.py, with a plain-language "why it matters" note (why.py). The user's own layout is the unit:
session sizes (warm-up, steady block, cool-down, long run) come from athlete.json preferences.easy_run and preferences.easy_ride.

Design rules (see ../references/evidence-map.md for what is research and what is practice):
  * Aerobic base first, but quality sessions (tempo, strides, time trial, interval run, ride intervals) are ON by default. They are locked for a user ONLY
    when that user's own data says so: an ACTIVE injury note (athlete.json), the reset week (RED readiness, long streak, load jump), the optional
    preferences.quality.requires_gate (an optional rule the user can set), or a type listed in preferences.quality.locked. Nothing about one athlete is hard-wired.
  * An optional monthly MAF-style test (athlete.json tests.maf: a fixed heart rate and laps) is not gated: it replaces the long run of the
    deload week, so it adds no volume.
  * A climb ride (athlete.json preferences.climb: target total ascent 200 m) replaces the Thursday aerobic ride every 2nd build week. There are few
    hills near home, so the target is total ascent and a short climb is repeated.
  * Run sessions follow the athlete's usual sizes. Cycling takes the rest of the weekly minutes. A reset week (x0.70 of the weekly total) trims the RIDES.
  * An active injury note freezes progression: no extra volume, no quality. Long run <= +10 % over the longest run so far (Frandsen 2025 reference).
  * Weekly total starts from the athlete's own last three full weeks; each build week is at most +10 %; every 4th week is a deload (x0.75).
  * Hard time <= 20 % of weekly endurance time (the share used in Neal 2013, Festa 2019, Stoggl 2014).
  * Strength 2 x per week in the evening (>= 3 h after cardio), home equipment only, no push-ups or pull-ups. Rest day on the athlete's rest weekday.

  build_plan.py [--start YYYY-MM-DD] [--weeks 4] [--readiness green|amber|red|unknown] [--gate auto|passed|open]
                [--days-per-week 5|6] [--out plan.json]
"""
import argparse
import json
import math
import re
import statistics
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

SKILLS = Path(__file__).resolve().parent.parent.parent
DATA_DIR = Path(__import__("os").environ.get("GARMIN_COACH_DATA") or Path.home() / "garmin-coach-data")   # personal data lives OUTSIDE the plugin folder, so updates never touch it
ATHLETE_JSON = DATA_DIR / "athlete.json"
sys.path.insert(0, str(SKILLS / "garmin-coach" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import gcommon as gc  # noqa: E402
import workout as wk  # noqa: E402
sys.path.insert(0, str(SKILLS / "garmin-strength" / "scripts"))
import strength_plan as sp  # noqa: E402
from why import check_text, why_text  # noqa: E402

BUILD_PCT = 0.10          # max weekly rise between build weeks (practice; Buist 2008: graded 10 % plan did not reduce injuries)
RESET_FACTOR = 0.70       # practice
DELOAD_FACTOR = 0.75      # practice
LONG_RUN_CAP = 1.10       # Frandsen 2025 reference category: up to +10 % over the longest run so far
LONG_RIDE_CAP = 1.10      # same cap applied to rides as an extrapolation
HARD_SHARE = 0.20         # <= 20 % of endurance time at high intensity
MIN_BIKE, MIN_LONG_RIDE = 40, 60
HR = {}                   # heart-rate targets resolved from the athlete's own data (athlete.json hr, preferences); filled in plan()
QUALITY_ROTATION = ["strides", "tt", "tempo", "intervals"]     # default order of the Run A quality sessions (override: preferences.quality.rotation)
WD = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

try:
    ATHLETE_BANNED = json.loads((ATHLETE_JSON).read_text(encoding="utf-8")).get("constraints", {}).get("no_exercises", [])
except Exception:
    ATHLETE_BANNED = ["push-ups", "pull-ups", "chin-ups"]


def r5(x):
    return int(5 * round(x / 5.0))


def fl5(x):
    return int(5 * (x // 5))


def history(g, today):
    ws0 = gc.week_start(today)
    acts = gc.list_activities(g, ws0 - timedelta(days=35), today)
    weeks = {}
    for a in acts:
        if a["sport"] in ("run", "bike"):
            w = weeks.setdefault(gc.week_start(a["date"]), {"run": 0.0, "bike": 0.0})
            w[a["sport"]] += a["min"]
    done = [ws0 - timedelta(days=7 * k) for k in (3, 2, 1)]
    tot = [sum(weeks.get(w, {"run": 0, "bike": 0}).values()) for w in done]
    d30 = today - timedelta(days=30)
    runs30 = [a for a in acts if a["sport"] == "run" and a["date"] >= d30]
    rides30 = [a for a in acts if a["sport"] == "bike" and a["date"] >= d30]
    days = sorted({a["date"] for a in acts if a["sport"] in ("run", "bike", "strength")})
    streak, d = 0, today if today in days else today - timedelta(days=1)
    while d in days:
        streak += 1
        d -= timedelta(days=1)
    return {
        "weekly_min_last3": [round(x) for x in tot], "base_min": statistics.mean(tot) if tot else 240.0, "last_week_min": tot[-1] if tot else 0,
        "longest_run_min": max((a["min"] for a in runs30), default=40.0), "longest_run_km": max((a["km"] for a in runs30), default=0.0),
        "longest_ride_min": max((a["min"] for a in rides30), default=90.0), "longest_ride_km": max((a["km"] for a in rides30), default=0.0),
        "streak_days": streak,
    }


# ---------------------------------------------------------------- strength (text only: Garmin strength workouts need exercise codes)
STRENGTH_FULL = {
    # Home equipment only (athlete.json equipment): convertible dumbbell/barbell with about 19 kg of small plates, a resistance band, the floor.
    # No gym, rack, bench, pull-up bar or anchor point is assumed. No push-ups or pull-ups (the athlete cannot do them).
    "A": ("Strength A (lower focus, full body, home)", 45,
          ["Goblet squat with one loaded handle (3 s down, 1 s pause) 3x10-12; add the band under your feet and over your shoulders when it feels easy",
           "Single-leg Romanian deadlift with dumbbell or barbell 3x8-10 each leg (touch a wall with one hand for balance)",
           "Static split squat with dumbbells 3x8-12 each leg (3 s lowering)",
           "Reverse lunge with dumbbells 2x8 each leg",
           "Glute bridge on the floor, barbell on the hips (single-leg when easy) 3x10-12",
           "Single-leg calf raise, dumbbell in hand 3x12-15 each leg",
           "Bent-over row with the barbell or dumbbells 3x8-12",
           "Side plank 2x30 s each side"]),
    "B": ("Strength B (upper + core, light legs, home)", 35,
          ["Floor press with dumbbells or the barbell 3x8-12 (lie on the floor)",
           "Standing overhead press with one or two dumbbells 3x8-10",
           "One-arm dumbbell row, free hand on your thigh or a chair 3x8-12 each arm",
           "Band pull-apart 3x15 (no anchor needed)",
           "Single-leg Romanian deadlift, light 2x8 each leg",
           "Dead bug 2x10 each side and bird dog 2x10 each side",
           "Mobility: hips, calves, thoracic spine 8-10 min"]),
}


# Shorter versions of the same two sessions. Evidence (garmin-strength evidence map): no verified paper supports a specific number of exercises or sets for
# athletes who also train endurance; 2-3 sessions a week, maximal-force emphasis and a >= 3 h gap after cardio are the researched parts. The number of moves
# is the athlete's choice: athlete.json preferences.strength.version = "short" (3 moves, default), "mid" (4 moves) or "full" (7-8 moves).
STRENGTH_MID = {
    "A": ("Strength A (lower body, 4 moves, home)", 30,
          ["Static split squat with dumbbells 3x8-12 each leg (3 s lowering)",
           "Single-leg Romanian deadlift with dumbbell or barbell 3x8-10 each leg (touch a wall with one hand for balance)",
           "Single-leg calf raise, dumbbell in hand 3x12-15 each leg",
           "Side plank 2x30 s each side"]),
    "B": ("Strength B (upper + core, 4 moves, home)", 25,
          ["Floor press with dumbbells or the barbell 3x8-12 (lie on the floor)",
           "One-arm dumbbell row, free hand on your thigh or a chair 3x8-12 each arm",
           "Band pull-apart 3x15 (no anchor needed)",
           "Dead bug 2x10 each side, then bird dog 2x10 each side"]),
}
STRENGTH_SHORT = {
    "A": ("Strength A (lower body, 3 moves, home)", 25,
          ["Static split squat with dumbbells 3x8-12 each leg (3 s lowering)",
           "Single-leg Romanian deadlift with dumbbell or barbell 3x8-10 each leg (touch a wall with one hand for balance)",
           "Single-leg calf raise, dumbbell in hand 3x12-15 each leg"]),
    "B": ("Strength B (upper + core, 3 moves, home)", 20,
          ["Floor press with dumbbells or the barbell 3x8-12 (lie on the floor)",
           "One-arm dumbbell row, free hand on your thigh or a chair 3x8-12 each arm",
           "Dead bug 2x10 each side, then bird dog 2x10 each side"]),
}
STRENGTH = {}             # filled in plan() from preferences.strength.version


def safety_text(restr):
    t = "Each morning: if the coach's readiness says RED, swap this for rest or a 20-30 min easy spin. Stop if pain changes your gait or keeps rising."
    return t + (" INJURY NOTE: " + "; ".join(x.rstrip(".") for x in restr) + "." if restr else "")


def strength_desc(kind, restr, light):
    title, mins, ex = STRENGTH[kind]
    lines = ["WHY IT MATTERS", why_text("strength_" + kind), "", f"THE SESSION: {title}, about {mins} min. Start at least 3 h after your cardio (Eddens 2018: order and gap matter; Schumann 2022: concurrent training does not blunt strength gains)."]
    lines += ["  - " + e for e in ex]
    lines.append("Load: pick a weight where the last 2 reps are hard with 2-3 reps still in reserve; if the plates feel too light, slow the lowering to 3 s, add a pause or add band tension instead of rushing. If readiness is RED or sleep < 6 h: half the sets.")
    if light:
        lines.append("LIGHT WEEK: use the light version (half the sets, lighter loads).")
    lines += ["", "CHECK AFTER", check_text("strength_" + kind), "", "SAFETY", safety_text(restr)]
    text = "\n".join(lines)
    for term in ATHLETE_BANNED:                       # exercises the athlete cannot do (athlete.json constraints.no_exercises)
        stem = re.escape(term.rstrip("s")).replace(r"\-", "[ -]?")
        if re.search(stem, text, re.I):
            raise SystemExit(f"strength text contains '{term}', which the athlete cannot do; fix STRENGTH in build_plan.py")
    return text


def strength_desc2(sess, meta, restr, light):
    """Calendar text for a generated strength session (garmin-strength/scripts/strength_plan.py)."""
    first = meta["basis"][0] if meta.get("basis") else ""
    lines = ["WHY IT MATTERS", sess["why"], f"Goal profile: {meta['label']}. Basis: {first} (all numbers are labelled research or practice in the profile and in garmin-strength/references/evidence-map.md).", "",
             f"THE SESSION: {sess['title']}, about {sess['minutes']} min. Start at least 3 h after your cardio (Eddens 2018: order and gap matter; Schumann 2022: concurrent training does not blunt strength gains)."]
    lines += ["  - " + x for x in sess["lines"]]
    lines.append("If readiness is RED or sleep < 6 h: half the sets.")
    if light:
        lines.append("LIGHT WEEK: use the light version (half the sets, lighter loads).")
    if sess.get("needs"):
        lines.append("NEEDED FROM YOU: " + "; ".join(sess["needs"]) + ". Log the session in Garmin (exercise, weight, reps) and the next plan builds on it.")
    if sess.get("notes"):
        lines.append("NOTE: " + "; ".join(sess["notes"]) + ".")
    lines += ["", "CHECK AFTER", sess["check"], "", "SAFETY", safety_text(restr)]
    text = "\n".join(lines)
    for term in ATHLETE_BANNED:
        stem = re.escape(term.rstrip("s")).replace(r"\-", "[ -]?")
        if re.search(stem, text, re.I):
            raise SystemExit(f"strength text contains '{term}', which the athlete cannot do; fix the library or constraints")
    return text


# ---------------------------------------------------------------- cardio sessions as Garmin workouts
def split_parts(mins, warm, cool):
    warm = min(warm, 10)
    main = max(10, mins - warm - cool)
    return warm, main, cool


def cardio_desc(why_key, w, extra, restr, **fmt):
    parts = ["WHY IT MATTERS", why_text(why_key, **fmt), "", f'ON YOUR WATCH (Garmin workout "{w["name"]}")', wk.describe(w)]
    if extra:
        parts += ["", extra]
    parts += ["", "CHECK AFTER", check_text(why_key, **fmt), "", "SAFETY", safety_text(restr)]
    return "\n".join(parts)


def previews(ceil_r, floor, ceil_b, tempo_cfg, maf):
    """Previews of every quality session type with their Garmin steps, so the user can see them (and load them) before they are scheduled."""
    t_lo, t_hi = tempo_cfg.get("hr_low"), tempo_cfg.get("hr_high")
    items = [
        ("run_strides", "Easy run with strides", wk.easy_with_strides(50, ceil_r, floor), {"ceil": ceil_r}),
        ("run_tt", "3 km time trial", wk.time_trial_3k(ceil_r), {"ceil": ceil_r}),
        ("run_tempo", "Tempo run (10+20+10)", wk.tempo("running", 1, tempo_cfg["block_min"], 0, HR["tempo"], ceil_r, warm=tempo_cfg["warmup_min"], cool=tempo_cfg["cooldown_min"]), {"lo": t_lo, "hi": t_hi}),
        ("run_intervals", "Interval run 5 x 3 min", wk.intervals("running", 50, 5, 3, 3, HR["hard_run"], ceil_r, floor, warm=10, cool=10), {"ceil": ceil_r}),
        ("ride_intervals", "Ride with hard intervals", wk.intervals("cycling", 70, 5, 3, 3, HR["hard_bike"], ceil_b, HR["floor_b"], warm=10, cool=10), {"ceil": ceil_b}),
    ]
    out = []
    for key, title, w, fmt in items:
        out.append({"kind": key, "title": title, "workout": w, "minutes": round(wk.est_minutes(w)),
                    "desc": cardio_desc(key, w, "PREVIEW: this is a quality session type. It is scheduled when your own data allows it (see the plan).", [], **fmt)})
    return out


def zone_sets(hr):
    """The athlete's own watch zones per sport from athlete.json hr.zone_sets, or {} (custom bpm everywhere). hr.target_mode.prefer = "custom" turns zone targets off."""
    if (hr.get("target_mode") or {}).get("prefer") == "custom":
        return {}
    out = {}
    for key, name in (("run", "running"), ("bike", "cycling")):
        z = (hr.get("zone_sets") or {}).get(key)
        if z and z.get("floors"):
            out[name] = {"floors": z["floors"], "top": z.get("top"), "label": z.get("method") or name}
    return out


ASK_HR = """NO HEART-RATE DATA for this athlete in athlete.json. Do not guess: ask them first.
  1. Do they want to share their watch zones? Max HR, LTHR, resting HR and which method the watch uses (%max, %HRR or %LTHR); a screenshot of the zones page is enough.
  2. What heart rate do they call "easy" (the ceiling)? And a tempo / hard-effort band if they have one.
Record it: athlete.py set hr.easy_band '{"run":[LOW,HIGH],"bike":[LOW,HIGH]}'  and  athlete.py set hr.zone_sets '{"run":{"method":"..","floors":[z1..z5],"top":MAX},"bike":{..}}'.
If they do not answer, rerun with --hr-from-trend: it estimates an easy band from their own recent activities (custom bpm only, labelled an estimate)."""


def ensure_hr(athlete, g, today, from_trend):
    """Ask-first rule: with no stored heart-rate bands the builder stops (exit 2) unless --hr-from-trend is given.
    Trend estimate (practice, NOT a zone): easy ceiling = median average HR of steady sessions (>= 30 min) in the last 60 days for that sport, floor = ceiling - 20."""
    hr = athlete.setdefault("hr", {})
    if hr.get("easy_band") or hr.get("run_easy_max"):
        return None
    if not from_trend:
        print(ASK_HR)
        sys.exit(2)
    acts = gc.list_activities(g, today - timedelta(days=60), today)
    bands, notes = {}, []
    for key in ("run", "bike"):
        hrs = [x["avg_hr"] for x in acts if x["sport"] == key and x["min"] >= 30 and x["avg_hr"]]
        if len(hrs) < 5:
            print(f"Not enough {key} sessions with heart rate (found {len(hrs)}, need 5) to estimate a band. Ask the athlete (see above).\n" + ASK_HR)
            sys.exit(2)
        c = round(statistics.median(hrs))
        bands[key] = [c - 20, c]
        notes.append(f"{key} {c - 20}-{c} (median of {len(hrs)} steady sessions)")
    hr["easy_band"] = bands
    hr["source"] = "trend estimate"
    return "HR bands are an ESTIMATE from activity trend (not zones, not shared by the athlete): " + "; ".join(notes) + ". Ask the athlete to confirm or share their zones."


def plan(a, g_hist, athlete, today):
    prefs, hr = athlete["preferences"], athlete["hr"]
    str_prefs = prefs.get("strength") or {}
    str_cache, str_meta = {}, {}
    str_hist = athlete.get("_strength_hist") or []

    def strength_week(day, light):
        """Sessions of the strength week that contains `day`. The rotation follows the ISO week number, so re-planning never reshuffles a week."""
        ws = gc.week_start(day)
        if (ws, light) not in str_cache:
            iso = ws.isocalendar()[1]
            pstart = str_prefs.get("program_start")
            pw = (ws - gc.week_start(datetime.strptime(pstart, "%Y-%m-%d").date())).days // 7 if pstart else iso
            sessions, m = sp.make_week(athlete, str_hist, iso, light=light, program_week=pw)
            str_cache[(ws, light)] = sessions
            str_meta.update(m)
        return str_cache[(ws, light)]
    er = prefs.get("easy_run", {"total_min": 50, "warmup_min": 10, "cooldown_min": 5, "short_min": 35})
    ep = prefs.get("easy_ride", {"warmup_min": 10, "cooldown_min": 5, "long_cooldown_min": 10})
    std, short_min, warm_r, cool_r = er["total_min"], er["short_min"], er["warmup_min"], er["cooldown_min"]
    lr_std = er.get("long_min", std)
    quality_pref = prefs.get("quality", {"requires_gate": False})
    tempo_cfg = {"warmup_min": 10, "block_min": 20, "cooldown_min": 10, **quality_pref.get("tempo", {})}      # hr_low / hr_high only if the athlete has a tempo band
    maf = (athlete.get("tests") or {}).get("maf")
    climb = prefs.get("climb")
    eb = hr.get("easy_band") or {}                                          # the athlete's own easy band [low, high] per sport (practice decision, athlete.json)
    run_b = eb.get("run") or [hr["run_zone_floors"][1], hr["run_easy_max"]]
    bike_b = eb.get("bike") or [run_b[0], hr.get("bike_easy_max", run_b[1])]
    floor, ceil_r = run_b
    floor_b, ceil_b = bike_b
    hb, t_lo, t_hi = hr.get("hard_band") or {}, tempo_cfg.get("hr_low"), tempo_cfg.get("hr_high")
    # Zone first, custom bpm second (workout.hr_band); no band known -> open target, "by feel".
    HR.update(floor_b=floor_b,
              hard_run=wk.hr_band(*hb["run"], "running") if hb.get("run") else wk.OPEN,
              hard_bike=wk.hr_band(*hb["bike"], "cycling") if hb.get("bike") else wk.OPEN,
              tempo=wk.hr_band(t_lo, t_hi, "running") if t_lo and t_hi else wk.OPEN,
              climb=tuple(climb["hr_band"]) if climb and climb.get("hr_band") else None)
    gate = gc.goal_by(athlete, "run-gate", "criteria") or {}
    has_gate = bool(gate.get("criteria"))
    gate_passed = a.gate == "passed" or (a.gate == "auto" and bool(gate.get("passed")))
    active_inj = [i for i in athlete["injuries"] if i.get("status") != "resolved"]        # notes shown in the session texts
    blocking_inj = [i for i in active_inj if i.get("status") == "active"]                 # only an ACTIVE injury freezes volume and locks quality
    restr = [f"{i['area']}: {i.get('restrict') or 'ask the athlete what to avoid'}" for i in active_inj]
    hold = bool(blocking_inj)
    red = a.readiness in ("red", "amber")
    reasons = []
    if a.readiness in ("red", "amber"):
        reasons.append("readiness " + a.readiness.upper())
    if g_hist["streak_days"] >= 14:
        reasons.append(f"{g_hist['streak_days']} days in a row without a rest day")
    if g_hist["weekly_min_last3"] and g_hist["weekly_min_last3"][-1] > 1.2 * statistics.mean(g_hist["weekly_min_last3"][:-1] or [g_hist["weekly_min_last3"][-1]]):
        reasons.append("last week > 20 % above the two weeks before")
    if blocking_inj:
        reasons.append("active injury note: no extra volume")
    reset = bool(reasons) if a.reset == "auto" else a.reset == "yes"
    quality_blockers = ([] if gate_passed or not quality_pref.get("requires_gate", False) else ["run gate not passed"]) + (["active injury note"] if blocking_inj else [])
    unlocked = set(quality_pref.get("unlocked", []))                       # types the athlete unlocked despite a blocker
    locked = set(quality_pref.get("locked", []))                           # types this athlete locked for themselves
    rotation = quality_pref.get("rotation", QUALITY_ROTATION)
    # Today's readiness is NOT used here: quality only appears in build weeks (never the reset week) and every session says "RED morning: swap for rest".
    allowed = [q for q in rotation if q not in locked and (not quality_blockers or q in unlocked)]
    quality_ok = bool(allowed)
    ride_int_ok = "intervals" not in locked and (not quality_blockers or "intervals" in unlocked)

    # weekly targets: total endurance minutes, and the long run of each week
    base = g_hist["base_min"]
    weeks, prev_build, last_lr, ref_run, build_idx = [], None, lr_std, max(g_hist["longest_run_min"], lr_std), 0
    for w in range(1, a.weeks + 1):
        if w == 1 and reset:
            tag, m, lr = "RESET", base * RESET_FACTOR, lr_std
        elif w % 4 == 0:
            tag, m, lr = "DELOAD", (prev_build or base) * DELOAD_FACTOR, r5(lr_std * 0.8)
        else:
            tag = "BUILD"
            m = base if (prev_build is None or hold) else prev_build * (1 + BUILD_PCT)
            prev_build = m
            lr = lr_std if hold else min(r5(last_lr * (1 + BUILD_PCT)), fl5(ref_run * LONG_RUN_CAP))
            last_lr = lr
            ref_run = max(ref_run, lr)
        weeks.append({"week": w, "tag": tag, "total": r5(m), "long_run": lr, "build_idx": build_idx if tag == "BUILD" else None})
        if tag == "BUILD":
            build_idx += 1

    tpl = {"Mon": [("AM", "runA")], "Tue": [("AM", "rideE")], "Wed": [("AM", "runL")],
           "Thu": [("AM", "rideM")], "Fri": [], "Sat": [("AM", "rideL")], "Sun": [("AM", "runB")]}
    n_str = sp.load_profiles()["goals"][str_prefs.get("goal") or sp.load_profiles()["default_goal"]]["sessions_per_week"]
    str_days = str_prefs.get("days") or {2: ["Mon", "Wed"], 3: ["Mon", "Wed", "Sat"]}.get(n_str, ["Mon", "Wed"])
    for i, wd in enumerate(str_days[:n_str]):
        tpl[wd] = tpl[wd] + [("PM", f"str{i + 1}")]
    weights_bike = {"rideE": 0.22, "rideM": 0.28, "rideL": 0.50}
    if a.days_per_week == 5:
        tpl["Tue"] = []
        weights_bike = {"rideM": 0.38, "rideL": 0.62}
    start = datetime.strptime(a.start, "%Y-%m-%d").date()
    end = gc.week_start(start) + timedelta(days=7 * a.weeks)
    ref_bike = g_hist["longest_ride_min"]
    sess, d = [], start
    while d < end:
        wi = (gc.week_start(d) - gc.week_start(start)).days // 7
        W = weeks[min(wi, len(weeks) - 1)]
        wnum, tag = W["week"], W["tag"]
        a_min = std if tag != "DELOAD" else r5(std * 0.8)
        b_min = short_min if tag != "DELOAD" else max(30, r5(short_min * 0.85))
        run_total = a_min + W["long_run"] + b_min
        bike_tot = max(W["total"] - run_total, MIN_BIKE * 2 + MIN_LONG_RIDE)
        for slot, kind in tpl[WD[d.weekday()]]:
            e = dict(date=str(d), weekday=WD[d.weekday()], slot=slot, week=wnum, week_tag=tag, kind=kind)
            if kind.startswith("run"):
                mins = {"runA": a_min, "runL": W["long_run"], "runB": b_min}[kind]
                wu, main, cd = split_parts(mins, warm_r, cool_r)
                extra, why_key, quality, fmt = "", {"runA": "run_easy", "runL": "run_long", "runB": "run_short"}[kind], False, {"ceil": ceil_r}
                if kind == "runL" and maf and tag == "DELOAD":
                    w = wk.maf_test(maf["hr"], maf["band_low"], maf["laps"], maf["lap_km"], maf["warmup_km"], maf["cooldown_km"])
                    mins, why_key, title, fmt = round(wk.est_minutes(w)), "run_maf", f"MAF test ({maf['warmup_km']:g} + {maf['laps']} x {maf['lap_km']:g} + {maf['cooldown_km']:g} km)", {"maf": maf["hr"]}
                    extra = ("Your monthly test: same course as last time, same time of day, and keep the heart rate between "
                             f"{maf['band_low']} and {maf['hr']}. It replaces this week's long run. Result = the pace of each test kilometre.")
                elif kind == "runA" and tag == "BUILD" and quality_ok:
                    quality = True
                    q = allowed[W["build_idx"] % len(allowed)]
                    if q == "strides":
                        w, why_key, title = wk.easy_with_strides(mins, ceil_r, floor, warm=wu, cool=cd), "run_strides", "Easy run with strides"
                    elif q == "tt":
                        w, why_key, title = wk.time_trial_3k(ceil_r), "run_tt", "3 km time trial"
                        mins = round(wk.est_minutes(w))
                    elif q == "tempo":
                        w = wk.tempo("running", 1, tempo_cfg["block_min"], 0, HR["tempo"], ceil_r, warm=tempo_cfg["warmup_min"], cool=tempo_cfg["cooldown_min"])
                        why_key, title, fmt = "run_tempo", f"Tempo run ({tempo_cfg['warmup_min']}+{tempo_cfg['block_min']}+{tempo_cfg['cooldown_min']})", {"lo": t_lo, "hi": t_hi}
                        mins = round(wk.est_minutes(w))
                    else:
                        w, why_key, title = wk.intervals("running", mins, 5, 3, 3, HR["hard_run"], ceil_r, floor, warm=10, cool=10), "run_intervals", "Interval run 5 x 3 min"
                    extra = (f"Quality day. It replaces an easy run, so it adds no volume, and hard time stays at {int(HARD_SHARE * 100)}% of the week or less. "
                             + ("You unlocked this type yourself although " + " and ".join(quality_blockers) + ". " if quality_blockers else "")
                             + "Do it only if your readiness is not RED, warm up fully, and stop if something hurts: pain is a stop sign. If it hurts afterwards, tell the coach and this type gets locked for you.")
                else:
                    label = {"runA": "Easy run", "runL": "Long run", "runB": "Short easy run"}[kind]
                    w = wk.easy("running", mins, ceil_r, floor, warm=wu, cool=cd, label=f"{label} {mins} min")
                    title = f"{label} ({wu}+{main}+{cd})"
                    if kind == "runL":
                        extra = f"Cap: at most +10% over your longest run so far ({g_hist['longest_run_min']:.0f} min in the last 30 days; the plan chains from there)."
                    if has_gate and mins >= gate["criteria"]["min_session_minutes"] and not gate_passed and kind in ("runA", "runL"):
                        extra = (extra + " " if extra else "") + "GATE ATTEMPT: this session is long enough to pass the no-walking gate. If you run all of it, ask the coach to check the gate."
                e.update(sport="run", minutes=mins, title=title, workout=w, intensity=f"easy, HR {floor}-{ceil_r}", quality=quality)
                e["desc"] = cardio_desc(why_key, w, extra, restr, **fmt)
            elif kind.startswith("ride"):
                share = weights_bike[kind]
                mins = max(MIN_BIKE, r5(bike_tot * share))
                cool = ep["long_cooldown_min"] if kind == "rideL" else ep["cooldown_min"]
                warm = ep["warmup_min"]
                extra, quality, fmt = "", False, {"ceil": ceil_b}
                if kind == "rideL":
                    mins = max(MIN_LONG_RIDE, min(mins, fl5(ref_bike * LONG_RIDE_CAP)))
                    ref_bike = max(ref_bike, mins)
                    rg = gc.goal_by(athlete, "ride-100k-25", "target_speed_kmh")
                    goal_txt = ""
                    if rg and rg.get("target_speed_kmh") and rg.get("target_distance_km"):
                        goal_txt = f" Your goal is {rg['target_speed_kmh']:.0f} km/h average over {rg['target_distance_km']:.0f} km on the flat."
                        bl = rg.get("baseline")
                        if bl and bl.get("km") and bl.get("moving_kmh"):
                            goal_txt += f" Your baseline: {bl['km']} km at {bl['moving_kmh']} km/h."
                    extra = (f"Ride the same bike on the same route when you can.{goal_txt} Cap: at most +10% over your longest ride so far ({g_hist['longest_ride_min']:.0f} min in the last 30 days). "
                             "For 90+ min plan food and drink with the fueling coach.")
                if kind == "rideM" and climb and tag == "BUILD" and W["build_idx"] % climb.get("every_n_build_weeks", 2) == 0:
                    target = climb["target_ascent_m"]
                    w = wk.climb_ride(mins, target, ceil_b, floor_b, climb.get("known_climb_height_m"), warm=warm, cool=cool, climb_hr=HR["climb"])
                    title, why_key, fmt = f"Climb ride ({target} m total climb)", "ride_climb", {"target": target}
                    h_known = climb.get("known_climb_height_m")
                    extra = (f"TOTAL CLIMB TARGET: {target} m {(' (' + climb['reference'] + ')') if climb.get('reference') else ''}. If hills are few you do not need a big one. Repeat a short climb (a bridge, an overpass, a ramp) until the watch shows {target} m of ascent"
                             + (f"; one climb is {h_known} m, so about {math.ceil(target / h_known)} repeats" if h_known else "; tell the coach the height of one climb and the plan will set the number of repeats")
                             + (f". Which bike: {climb['bike_hint']}" if climb.get("bike_hint") else ". Which bike: use your easiest-geared bike")
                             + (f". Stay seated, keep it steady, heart rate cap {HR['climb'][1]}, and stop if something complains." if HR["climb"] else ". Stay seated, keep it steady, and stop if something complains."))
                elif kind == "rideM" and ride_int_ok and tag == "BUILD" and wnum >= 2:
                    quality = True
                    w = wk.intervals("cycling", mins, 5, 3, 3, HR["hard_bike"], ceil_b, floor_b, warm=warm, cool=cool)
                    title, why_key = "Ride with hard intervals", "ride_intervals"
                    extra = f"Quality day. It replaces an easy ride, so it adds no volume, and hard time stays at {int(HARD_SHARE * 100)}% of the week or less."
                else:
                    label = {"rideE": "Easy ride", "rideM": "Aerobic ride", "rideL": "Long ride"}[kind]
                    w = wk.easy("cycling", mins, ceil_b, floor_b, warm=warm, cool=cool, label=f"{label} {mins} min")
                    title, why_key = f"{label} ({warm}+{mins - warm - cool}+{cool})", ("ride_long" if kind == "rideL" else "ride_easy")
                e.update(sport="bike", minutes=mins, title=title, workout=w, intensity=f"easy, HR {floor_b}-{ceil_b}", quality=quality)
                if why_key == "ride_climb":
                    e["target_ascent_m"] = climb["target_ascent_m"]
                e["desc"] = cardio_desc(why_key, w, extra, restr, **fmt)
            else:
                light = tag == "RESET" or (red and wnum == 1)
                wk_sessions = strength_week(d, light)
                idx = int(kind[3:]) - 1
                if idx >= len(wk_sessions):
                    continue
                ss = wk_sessions[idx]
                e.update(sport="strength", minutes=ss["minutes"], title=ss["title"] + (" (light)" if light else ""), intensity="RPE 6-7", quality=False)
                e["desc"] = strength_desc2(ss, str_meta, restr, light)
                e["strength"] = {"exercises": ss["exercises"], "volume": ss["volume"], "needs": ss["needs"]}
            e["short"] = e["desc"]
            sess.append(e)
        d += timedelta(days=1)
    # keep only sessions on or after start; assign clock times
    for e in sess:
        day = datetime.strptime(e["date"], "%Y-%m-%d").date()
        if e["slot"] == "AM":
            hh, mm = (int(x) for x in prefs["cardio_start"].split(":"))
            if e["minutes"] > 120:                                           # long sessions start 15 minutes earlier
                t = hh * 60 + mm - 15
                hh, mm = divmod(t, 60)
        else:
            hh, mm = (int(x) for x in prefs["strength_start"].split(":"))
        st = datetime(day.year, day.month, day.day, hh, mm)
        e["start"] = st.isoformat(timespec="minutes")
        e["end"] = (st + timedelta(minutes=e["minutes"])).isoformat(timespec="minutes")
    sess = [e for e in sess if e["date"] >= a.start]
    by_day = {}
    for e in sess:
        by_day.setdefault(e["date"], []).append(e)
    for dstr, es in by_day.items():                                          # strength must start >= 3 h after cardio ends
        for s in (x for x in es if x["sport"] == "strength"):
            for c in (x for x in es if x["sport"] != "strength"):
                gap = (datetime.fromisoformat(s["start"]) - datetime.fromisoformat(c["end"])).total_seconds() / 3600
                assert gap >= 3, f"strength gap {gap:.1f} h on {dstr}"
    meta = {"generated": str(today), "start": a.start, "weeks": a.weeks, "readiness": a.readiness, "gate_passed": gate_passed, "has_gate": has_gate,
            "reset": reset, "reset_reasons": reasons, "hold_progression": hold, "quality_blockers": quality_blockers,
            "weekly_targets": [{"week": w["week"], "tag": w["tag"], "endurance_min": w["total"], "long_run_min": w["long_run"]} for w in weeks],
            "history": g_hist, "restrictions": restr, "standard_easy_run_min": std, "long_run_min": lr_std,
            "strength": {"goal": str_meta.get("goal"), "label": str_meta.get("label"), "version": str_meta.get("version"),
                         "needs": sorted({n for ss in sum(str_cache.values(), []) for n in ss["needs"]})},
            "quality_types_on": allowed, "quality_types_locked": sorted(locked), "previews": previews(ceil_r, floor, ceil_b, tempo_cfg, maf)}
    return meta, sess


def to_md(meta, sess):
    h = meta["history"]
    out = [f"# Plan {meta['start']} ({meta['weeks']} weeks)",
           f"Phase: BASE + quality{'' if not meta.get('has_gate') else (' (no-walking goal reached)' if meta['gate_passed'] else ' (no-walking goal still tracked)')} | readiness {meta['readiness']} | "
           f"{'RESET week first: ' + '; '.join(meta['reset_reasons']) if meta['reset'] else 'no reset needed'}"
           f"{' | progression frozen by an injury note' if meta['hold_progression'] else ''}",
           f"History: last 3 full weeks {h['weekly_min_last3']} min (run+bike), base {h['base_min']:.0f} min/wk, longest run 30 d {h['longest_run_min']:.0f} min, "
           f"longest ride 30 d {h['longest_ride_min']:.0f} min ({h['longest_ride_km']:.0f} km). Easy run {meta['standard_easy_run_min']} min, long run {meta['long_run_min']} min.",
           (f"Quality sessions on: {', '.join(meta['quality_types_on']) or 'none'}" + (f" | locked for this athlete: {', '.join(meta['quality_types_locked'])}" if meta["quality_types_locked"] else "")
            + (f" | blocked by: {', '.join(meta['quality_blockers'])}" if meta["quality_blockers"] else "") + ". Previews of every type are in workouts/after-gate."), ""]
    for w in meta["weekly_targets"]:
        wkd = [e for e in sess if e["week"] == w["week"]]
        em = sum(e["minutes"] for e in wkd if e["sport"] != "strength")
        out.append(f"## Week {w['week']} - {w['tag']} (target {w['endurance_min']} min; scheduled {em} min cardio, {sum(1 for e in wkd if e['sport'] == 'strength')} strength)")
        for e in sorted(wkd, key=lambda x: x["start"]):
            q = " **[quality]**" if e.get("quality") else ""
            out.append(f"- {e['date']} {e['weekday']} {e['start'][11:]} - {e['title']} ({e['minutes']} min){q}")
        out.append("")
    out.append("## Quality session types (previews)")
    for p in meta["previews"]:
        out.append(f"- {p['title']} (about {p['minutes']} min)")
    if meta["restrictions"]:
        out += ["", "Injury notes applied: " + "; ".join(meta["restrictions"])]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--start", default=str(date.today() + timedelta(days=1)))
    ap.add_argument("--weeks", type=int, default=4)
    ap.add_argument("--readiness", choices=["green", "amber", "red", "unknown"], default="unknown")
    ap.add_argument("--gate", choices=["auto", "passed", "open"], default="auto")
    ap.add_argument("--reset", choices=["auto", "yes", "no"], default="auto")
    ap.add_argument("--hr-from-trend", action="store_true", help="the athlete shared no heart-rate data: estimate an easy band from their activities")
    ap.add_argument("--days-per-week", type=int, choices=[5, 6], default=None)
    ap.add_argument("--out")
    a = ap.parse_args()
    gc.utf8_stdout()
    athlete = json.loads((ATHLETE_JSON).read_text(encoding="utf-8"))
    a.days_per_week = a.days_per_week or athlete["preferences"]["days_per_week"]
    today = date.today()
    with gc.Garmin() as g:
        h = history(g, today)
        hr_note = ensure_hr(athlete, g, today, a.hr_from_trend)
        try:
            import strength_history as sh  # noqa: E402
            athlete["_strength_hist"] = sh.load_history(g, 240)
        except Exception as ex:                                              # no history or unreadable: the plan then asks for starting weights
            print(f"(strength history not read: {ex})")
            athlete["_strength_hist"] = []
    wk.set_zones(zone_sets(athlete["hr"]), (athlete["hr"].get("target_mode") or {}).get("tolerance_bpm", 3))
    meta, sess = plan(a, h, athlete, today)
    meta["hr_note"] = hr_note
    meta["zone_sets_used"] = sorted(wk.ZONES)
    print(to_md(meta, sess))
    if hr_note:
        print("\n" + hr_note)
    if meta.get("strength", {}).get("needs"):
        print("\nASK THE ATHLETE (strength): " + "; ".join(meta["strength"]["needs"]))
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps({"meta": meta, "sessions": sess}, indent=1, default=str), encoding="utf-8")
        print(f"\n(saved {a.out})")


if __name__ == "__main__":
    main()
