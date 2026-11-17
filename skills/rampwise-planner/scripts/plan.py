#!/usr/bin/env python3
"""The planner: ONE engine for every plan. The goal is a race (5 km to ultra, sprint triathlon to Ironman, duathlon, cycling, open-water swim) or, with no target at all,
"base": build endurance and aerobic base for the sports you choose. Works WITHOUT a Garmin account; with one, it reads your real training (--from-garmin) and, when your
heart-rate data are known, writes heart-rate workouts that export to .fit files for the watch (export_plan.py --format fit).

  plan.py --event olympic-tri --event-date 2027-06-20 [--start YYYY-MM-DD] [--level beginner|intermediate|advanced]
                [--hours-now 6] [--max-hours 9] [--days 5|6|7] [--longest-run-min 60] [--longest-ride-min 90] [--longest-swim-min 30]
                [--strength 2] [--no-cross-train] [--out FILE] [--md] [--json] [--list-events]
  plan.py --goal base --sports run,bike,swim [--weeks 12] [--from-garmin] [--readiness red|amber|green]     (no race, no target: aerobic base)

Inputs come from the flags, else from athlete.json ("manual_baseline" and "event"), else asking-first defaults are refused: the script stops and prints
what it needs (current weekly hours, hours available, days a week, level) instead of guessing. Garmin data are NOT required; if you have them, the
Garmin-history planner (build_plan.py) builds rolling plans from your real training instead.

Shape of the plan (rules and their labels: ../references/evidence-map.md, section "Event plans"):
  base -> build -> peak -> taper, a recovery week every 4th week, weekly volume +10 % at most, long sessions capped, about 70-80 % easy,
  a taper that cuts volume and keeps some intensity (2 weeks for most events), a swim/bike/run split for triathlon, strength twice a week.
The plan never promises a result. If the weeks you have cannot reach the volume the event usually needs at +10 % a week, it says so and peaks lower.
"""
import argparse
import json
import math
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILLS = HERE.parent.parent
for sub in ("rampwise", "rampwise-strength"):
    sys.path.insert(0, str(SKILLS / sub / "scripts"))
import gcommon as gc  # noqa: E402
sys.path.insert(0, str(HERE))

RACE_SPORT = {"run": "run", "du": "run", "tri": "bike", "bike": "bike", "swim": "swim"}
RACE_WORD = {"run": "run", "du": "run", "tri": "spin", "bike": "spin", "swim": "swim"}
WD = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
GROWTH = 0.10            # practice: weekly volume step cap (a cap, not a safety guarantee: a 10 % plan did not prevent injuries in an RCT, Buist 2008)
RECOVERY_EVERY = 4       # practice: every 4th week is a lighter week
RECOVERY_FACTOR = 0.75   # practice
LONG_CAP = 1.10          # research for running (Frandsen 2025: +10 % over the longest run); extrapolated to rides and swims
MIN_MIN = {"run": 25, "bike": 40, "swim": 20}
MID_CAP = {"run": 90, "bike": 150, "swim": 75}   # practice: a weekday session stays under this, however long the long one is
TAPER_FACTORS = {1: [0.55], 2: [0.70, 0.50], 3: [0.75, 0.60, 0.45]}     # research: Bosquet 2007 (2-week taper, volume cut about 41-60 %, intensity kept)

# effort scale (practice): label, how it feels, fraction of FTP for bike exports (conventional zone mid-points, no paper read)
EFFORT = {"easy": ("easy", "RPE 2-3, you can talk in full sentences", 0.65), "steady": ("steady", "RPE 4-5", 0.78),
          "tempo": ("tempo", "RPE 6, comfortably hard", 0.88), "threshold": ("threshold", "RPE 7, hard but controlled", 1.00),
          "hard": ("hard", "RPE 8-9", 1.12), "recover": ("recovery", "RPE 1-2", 0.50), "warm": ("warm-up", "RPE 2, getting easier into it", 0.60),
          "cool": ("cool-down", "RPE 1-2", 0.50)}

EVENTS = {
    "5k":         dict(label="5 km run", kind="run", peak={"beginner": 3.5, "intermediate": 5, "advanced": 7}, taper=1, long_run=60, weeks=(8, 12), strength="runner_distance"),
    "10k":        dict(label="10 km run", kind="run", peak={"beginner": 4, "intermediate": 6, "advanced": 8}, taper=1, long_run=80, weeks=(8, 14), strength="runner_distance"),
    "half":       dict(label="Half marathon", kind="run", peak={"beginner": 5, "intermediate": 7, "advanced": 9}, taper=2, long_run=110, weeks=(10, 16), strength="runner_distance"),
    "marathon":   dict(label="Marathon", kind="run", peak={"beginner": 6, "intermediate": 8.5, "advanced": 11}, taper=2, long_run=165, weeks=(14, 20), strength="runner_marathon"),
    "ultra-50k":  dict(label="50 km ultra", kind="run", peak={"beginner": 7, "intermediate": 10, "advanced": 13}, taper=2, long_run=210, weeks=(16, 22), strength="runner_trail_ultra"),
    "sprint-tri": dict(label="Sprint triathlon", kind="tri", peak={"beginner": 5, "intermediate": 7, "advanced": 9}, taper=1, long_run=50, long_bike=80, long_swim=40, weeks=(8, 12),
                       shares={"swim": 0.20, "bike": 0.45, "run": 0.35}, brick=(10, 15), strength="triathlon"),
    "olympic-tri": dict(label="Olympic triathlon", kind="tri", peak={"beginner": 7, "intermediate": 9.5, "advanced": 12}, taper=2, long_run=70, long_bike=120, long_swim=50, weeks=(10, 16),
                        shares={"swim": 0.18, "bike": 0.44, "run": 0.38}, brick=(15, 20), strength="triathlon"),
    "70.3":       dict(label="Half-distance triathlon (70.3)", kind="tri", peak={"beginner": 8, "intermediate": 11, "advanced": 14}, taper=2, long_run=105, long_bike=210, long_swim=60, weeks=(14, 20),
                       shares={"swim": 0.15, "bike": 0.50, "run": 0.35}, brick=(15, 25), strength="triathlon"),
    "base":       dict(label="Aerobic base (no race)", kind="mix", peak={"beginner": 4, "intermediate": 6, "advanced": 9}, taper=0, long_run=90, long_bike=180, long_swim=60, weeks=(8, 16),
                       shares={}, strength="endurance"),
    "gran-fondo": dict(label="Gran fondo (100 km ride)", kind="bike", peak={"beginner": 5, "intermediate": 7.5, "advanced": 10}, taper=1, long_bike=240, weeks=(10, 16), shares={"bike": 1.0}, strength="cyclist_road"),
    "century":    dict(label="Century ride (160 km)", kind="bike", peak={"beginner": 6, "intermediate": 9, "advanced": 12}, taper=2, long_bike=330, weeks=(12, 18), shares={"bike": 1.0}, strength="cyclist_road"),
    "ultra-ride": dict(label="Ultra-distance ride (300 km)", kind="bike", peak={"beginner": 8, "intermediate": 12, "advanced": 16}, taper=2, long_bike=480, weeks=(16, 24), shares={"bike": 1.0}, strength="cyclist_road"),
    "swim-1500":  dict(label="Open-water swim 1.5 km", kind="swim", peak={"beginner": 3, "intermediate": 5, "advanced": 7}, taper=1, long_swim=60, weeks=(8, 14), shares={"swim": 0.78, "bike": 0.22}, strength="endurance"),
    "swim-5k":    dict(label="Open-water swim 5 km", kind="swim", peak={"beginner": 5, "intermediate": 8, "advanced": 11}, taper=2, long_swim=120, weeks=(12, 20), shares={"swim": 0.78, "bike": 0.22}, strength="endurance"),
    "swim-10k":   dict(label="Marathon swim 10 km", kind="swim", peak={"beginner": 7, "intermediate": 10, "advanced": 14}, taper=2, long_swim=180, weeks=(16, 24), shares={"swim": 0.78, "bike": 0.22}, strength="endurance"),
    "duathlon-sprint":   dict(label="Sprint duathlon (run, ride, run)", kind="du", peak={"beginner": 4, "intermediate": 6, "advanced": 8}, taper=1, long_run=45, long_bike=75, weeks=(8, 12), shares={"run": 0.42, "bike": 0.58}, brick=(10, 15), strength="triathlon"),
    "duathlon-standard": dict(label="Standard duathlon (run, ride, run)", kind="du", peak={"beginner": 6, "intermediate": 8.5, "advanced": 11}, taper=2, long_run=70, long_bike=120, weeks=(10, 16), shares={"run": 0.42, "bike": 0.58}, brick=(15, 25), strength="triathlon"),
    "ironman":    dict(label="Full-distance triathlon (Ironman)", kind="tri", peak={"beginner": 10, "intermediate": 14, "advanced": 18}, taper=2, long_run=150, long_bike=300, long_swim=75, weeks=(18, 24),
                       shares={"swim": 0.13, "bike": 0.55, "run": 0.32}, brick=(15, 30), strength="triathlon"),
}
LEVELS = ("beginner", "intermediate", "advanced")

# (session key, weekday) in the order days are dropped: with fewer training days the last entries go first
TRI_DAYS = [("bike_long", "Sat"), ("run_long", "Sun"), ("run1", "Tue"), ("swim1", "Mon"), ("swim2", "Thu"), ("bike1", "Wed"), ("swim3", "Fri")]
BIKE_DAYS = [("bike_long", "Sat"), ("bike1", "Tue"), ("bike2", "Thu"), ("bike3", "Wed"), ("bike4", "Sun"), ("bike5", "Fri")]
SWIM_DAYS = [("swim_long", "Sat"), ("swim2", "Wed"), ("swim1", "Mon"), ("swim3", "Fri"), ("bike_x", "Sun"), ("swim4", "Tue"), ("swim5", "Thu")]
DU_DAYS = [("bike_long", "Sat"), ("run_long", "Sun"), ("run1", "Tue"), ("bike1", "Wed"), ("run2", "Thu"), ("bike2", "Fri")]
MIX_DAYS = [("run_long", "Sun"), ("bike_long", "Sat"), ("run1", "Tue"), ("bike1", "Wed"), ("swim1", "Mon"), ("swim2", "Thu"), ("run2", "Fri"), ("swim3", "Fri")]
RUN_DAYS = [("run_long", "Sun"), ("run1", "Tue"), ("run2", "Thu"), ("run3", "Sat"), ("bike_x", "Wed"), ("run4", "Fri")]

BASIS = [
    "research (meta-analysis of 27 studies in competitive athletes, not triathlon-specific): a 2-week taper with training volume cut by about 41-60 % and intensity and frequency kept gave the best performance gain (Bosquet 2007). The plan tapers 2 weeks (1 for short events) and keeps a few short fast efforts.",
    "research (observational, small samples): Ironman triathletes spent about 68-69 % of training time in the lowest intensity zone, and more time there went with better race times in one study of 9 triathletes (Munoz 2014; Neal 2011, 10 triathletes). The plan keeps about 70-80 % easy. This is association, not proof.",
    "research (observational, elite): swimming is the smallest share of race time in Olympic and Ironman triathlon, about 18 % on average (Figueiredo 2016). The training split gives swimming the smallest share; frequency still matters for a technique sport (practice).",
    "research (cohort, 174 iron-distance triathletes): overuse problems were common (56 % average prevalence) at the knee, lower leg and lower back (Andersen 2013). Hence volume caps, recovery weeks and the injury-risk watch of rampwise-analyze.",
    "research for running (Frandsen 2025, cohort): a single run more than 10 % longer than the recent longest went with higher injury rates; the long-run chain is capped at +10 %. Extrapolated to rides and swims (gap).",
    "practice: weekly volume step of at most 10 % (a cap, not a safety guarantee: a graded 10 % plan did not reduce injuries in an RCT, Buist 2008); a lighter week every 4th week; the base/build/peak split; the swim/bike/run time shares per event; long-session caps per event; RPE and power-fraction effort scale.",
    "research (narrative review, FULL TEXT read: Walsh 2019; Millet and Vleck 2000, abstract only): running straight after cycling costs more energy than running fresh (+1.6 % to +11.6 % depending on ability), changes muscle recruitment in some elite triathletes, and the one 6-week study of repeated cycle-run sessions that Walsh describes found no improvement in cycle-run performance. So brick runs stay short and easy-steady, at most one a week in build and peak weeks. That they train anything is unproven (gap).",
    "research (small study, abstract only: Berry 2016, 7 highly trained multisport athletes): after a 10 km run and a 30 km ride, running speed at the ventilatory threshold fell and a 5 km run took more than 2 minutes longer. Direction only. Duathlon plans end the long ride with a brick run; a run-then-ride-then-run session is not built yet.",
    "research (Walsh 2019, citing small studies): high pedalling cadence (80-120 rpm) raised the oxygen cost of the following run; 70-80 rpm before a run was suggested and about 90 rpm freely chosen is biomechanically optimal. High-cadence drills here are separate skill work, never the last minutes before a run.",
    "research (Walsh 2019, citing one elite study): starting the run about 5 % slower than the average 10 km pace gave a better run than a fast start. The race-day text says so.",
    "injury (Walsh 2019, citing a small study of 10 elite triathletes): those with a history of exercise-related leg pain were about 2.4 times more likely to have difficulty replicating normal running muscle patterns after cycling. The plan asks about leg-pain history, cuts brick runs to 10 minutes if yes, and drops them while an injury is active.",
    "research (abstract only; see rampwise-aerobic-base): speed at a fixed heart rate tracks aerobic adaptation only if the test is standardised, and heat, hills and fatigue move it; so the aerobic base plan repeats ONE standardised test in each lighter week and compares only like with like (the test is practice).",
    "gap: the exact peak hours per event and level, the session mix, whether brick sessions train anything (one 6-week study, no improvement), and everything for cycling, swimming and duathlon plans beyond the points above.",
]


def r5(x):
    return int(5 * round(x / 5.0))


def fl5(x):
    return int(5 * (x // 5))


def monday(d):
    return d - timedelta(days=d.weekday())


def fmt_blocks(blocks):
    out = []
    for b in blocks:
        if "repeat" in b:
            on, off = b["on"], b["off"]
            out.append(f"{b['repeat']} x ({on['minutes']:g} min {EFFORT[on['effort']][0]} + {off['minutes']:g} min {EFFORT[off['effort']][0]})")
        else:
            out.append(f"{b['minutes']:g} min {b.get('label') or EFFORT[b['effort']][0]}")
    return "; ".join(out)


def blk(minutes, effort, label=None):
    return {"minutes": minutes, "effort": effort, **({"label": label} if label else {})}


def reps(n, on_min, on_eff, off_min, off_eff="recover"):
    return {"repeat": n, "on": blk(on_min, on_eff), "off": blk(off_min, off_eff)}


def total_minutes(blocks):
    t = 0.0
    for b in blocks:
        t += b["repeat"] * (b["on"]["minutes"] + b["off"]["minutes"]) if "repeat" in b else b["minutes"]
    return t


def pad_easy(blocks, minutes, warm, cool):
    """Wrap main blocks with warm-up and cool-down and fill the rest of `minutes` with easy time after the warm-up."""
    main = total_minutes(blocks)
    fill = max(0, minutes - warm - cool - main)
    return [blk(warm, "warm")] + ([blk(round(fill), "easy")] if fill >= 5 else []) + blocks + [blk(cool, "cool")]


# ---------------------------------------------------------------- session builders (all RPE-based; no heart-rate numbers are assumed)
def run_session(kind, m, phase, ctx):
    ev, lvl = ctx["ev"], ctx["level"]
    easy_txt = "Easy means RPE 2-3: you can talk in full sentences. Use your watch's easy heart-rate zone if you have one."
    if kind in ("run_long",):
        tail = []
        if phase in ("BUILD", "PEAK") and ev["label"] in ("Half marathon", "Marathon", "50 km ultra") and not ctx["recovery"]:
            tail = [blk(max(10, round(m * 0.2)), "steady", "steady finish")]
        blocks = pad_easy(tail, m, 5, 5)
        return "Long run", blocks, False, easy_txt + (" The last part is steady (RPE 4-5): finish tired, not empty." if tail else "")
    if kind == "brick_run":
        return "Brick run (straight off the bike)", [blk(m, "steady", "easy-steady run, RPE 3-5")], False, "Legs often feel heavy for the first 5 minutes: normal. Keep it easy: running straight after cycling costs more energy than running fresh (Millet and Vleck 2000), and whether bricks improve that is unproven (Walsh 2019). Stop if anything hurts."
    if ctx.get("aerobic_test") and ctx["recovery"] and kind == "run1":
        return "Aerobic test run (standardised)", [blk(10, "warm"), blk(30, "easy", "steady at your easy ceiling, RPE 3"), blk(5, "cool")], False, "Same route, same time of day, same easy heart-rate ceiling or RPE 3 every time. Write down the average pace and heart rate. Compare only with earlier tests in similar weather; one test proves little (heat, hills, sleep and fatigue move it)."
    quality_ok = ctx["quality_ok"] and not ctx["recovery"] and kind == "run1" and phase != "RACE"
    if quality_ok and lvl == "beginner" and phase == "BASE":
        quality_ok = False
    if quality_ok:
        if phase == "BASE":
            blocks = pad_easy([reps(6, 0.33, "hard", 1.0, "easy")], m, 10, 5)
            return "Easy run with strides", blocks, True, "Six relaxed fast strides of about 20 s (RPE 7, smooth, not a sprint) with easy jogging between. " + easy_txt
        if phase == "BUILD":
            tempo = max(10, min(40, round(m * 0.30)))
            if lvl == "beginner":
                tempo = min(tempo, 15)
            blocks = pad_easy([blk(tempo, "tempo")], m, 10, 8)
            return f"Tempo run ({tempo} min tempo)", blocks, True, "Tempo is comfortably hard (RPE 6): short sentences only. Stop if anything hurts."
        if phase == "PEAK":
            if ev["label"] in ("5 km run", "10 km run") and lvl != "beginner":
                n = 5 if ev["label"] == "5 km run" else 4
                d = 3 if ev["label"] == "5 km run" else 5
                blocks = pad_easy([reps(n, d, "hard" if n == 5 else "threshold", 2, "easy")], m, 12, 8)
                return f"Race-effort intervals ({n} x {d} min)", blocks, True, "Hard but controlled; the last repeat should match the first. Stop if form falls apart."
            blk_len = max(8, min(20, round(m * 0.22)))
            blocks = pad_easy([reps(2, blk_len, "tempo", 4, "easy")], m, 10, 8)
            return f"Race-effort blocks (2 x {blk_len} min)", blocks, True, "Settle into the effort you plan to hold on race day (RPE 5-6). Practise your fuelling here."
        if phase == "TAPER":
            blocks = pad_easy([reps(4, 2, "threshold", 2, "easy")], m, 10, 8)
            return "Sharpener (4 x 2 min)", blocks, True, "Short and crisp, then stop. The taper keeps a little intensity while volume drops (Bosquet 2007)."
    label = "Easy run"
    return label, pad_easy([], m, 5, 5), False, easy_txt


def bike_session(kind, m, phase, ctx):
    ev, lvl = ctx["ev"], ctx["level"]
    easy_txt = "Mostly steady endurance (RPE 2-3, 56-75 % of FTP if you use power). Eat and drink on rides over 90 minutes."
    if kind == "bike_long":
        main = []
        if phase in ("BUILD", "PEAK") and (ev["kind"] == "bike" or ev["label"] in ("Half-distance triathlon (70.3)", "Full-distance triathlon (Ironman)")) and m >= 120 and not ctx["recovery"]:
            n = 2 if m < 180 else 3
            b = max(15, min(30, round(m * 0.12)))
            main = [reps(n, b, "steady", 8 if phase == "BUILD" else 5, "easy")]
        return "Long ride", pad_easy(main, m, 10, 10), False, easy_txt + (" Race-effort blocks (RPE 4-5): practise your race nutrition on these." if main else "")
    if kind == "bike_x":
        return "Easy ride (cross-training)", pad_easy([], m, 8, 5), False, "Low-impact aerobic work next to the running: " + easy_txt
    if ctx.get("aerobic_test") and ctx["recovery"] and kind == "bike1":
        return "Aerobic test ride (standardised)", [blk(10, "warm"), blk(40, "easy", "steady at your easy ceiling, RPE 3"), blk(5, "cool")], False, "Same route, same time of day, same easy heart-rate ceiling or RPE 3 every time. Write down the average speed and heart rate. Compare only with earlier tests in similar weather and wind; one test proves little."
    if kind == "bike2" and ev["kind"] in ("bike", "du") and ctx["quality_ok"] and not ctx["recovery"] and phase in ("BUILD", "PEAK") and lvl != "beginner":
        d = max(10, min(25, round(m * 0.2)))
        return f"Steady-tempo ride (2 x {d} min)", pad_easy([reps(2, d, "tempo", 5, "easy")], m, 12, 8), True, "Tempo is comfortably hard (RPE 6, about 76-90 % of FTP). Even power, seated. Practise your race fuelling on rides over 90 minutes."
    if kind == "bike1" and ctx["quality_ok"] and not ctx["recovery"] and phase != "RACE":
        if phase == "BASE":
            if lvl == "beginner":
                return "Easy ride", pad_easy([], m, 10, 8), False, easy_txt
            return "Ride with cadence drills", pad_easy([reps(6, 0.5, "steady", 2.5, "easy")], m, 10, 8), True, "Six short high-cadence spins (about 100 rpm, smooth), easy between. Skill, not strength. Do not do this right before a run: high cadence raises the cost of the run that follows (Walsh 2019)."
        if phase == "BUILD":
            n, d = (3, 8) if lvl != "beginner" else (2, 6)
            return f"Tempo ride ({n} x {d} min)", pad_easy([reps(n, d, "tempo", 4, "easy")], m, 12, 8), True, "Tempo is comfortably hard (RPE 6, about 76-90 % of FTP). Even power, seated."
        if phase == "PEAK":
            if ev["label"] in ("Sprint triathlon", "Olympic triathlon") and lvl != "beginner":
                return "Threshold ride (4 x 6 min)", pad_easy([reps(4, 6, "threshold", 4, "easy")], m, 12, 8), True, "Hard but controlled (RPE 7, about 95-105 % of FTP)."
            return "Race-effort ride (2 x 20 min)", pad_easy([reps(2, 20, "tempo", 6, "easy")], m, 12, 8), True, "Hold the effort you plan to ride on race day (RPE 5-6); practise fuelling."
        if phase == "TAPER":
            return "Sharpener ride (4 x 2 min)", pad_easy([reps(4, 2, "threshold", 3, "easy")], m, 12, 8), True, "Short and crisp, then stop (taper: volume down, intensity kept)."
    return "Easy ride", pad_easy([], m, 10, 8), False, easy_txt


def swim_session(kind, m, phase, ctx):
    lvl = ctx["level"]
    base_txt = "Swim time and effort, not distance: pools and paces differ. If you know your 100 m time, convert the minutes to metres. Rest 15-30 s between repeats."
    if kind == "swim_long":
        main = []
        if phase in ("BUILD", "PEAK") and not ctx["recovery"]:
            main = [reps(3, max(8, round(m * 0.15)), "steady", 3, "easy")]
        return "Long swim", pad_easy(main, m, 10, 5), False, "Continuous aerobic swimming (RPE 3-4). In open water practise sighting every 8-10 strokes. Never swim open water alone: use a partner or a safety buoy, check the water temperature first (rampwise-heat-weather/scripts/swim_water.py) and follow local rules." + (" Race-effort blocks (RPE 4-5)." if main else "") + " Swim time and effort, not distance."
    if kind == "swim1":
        main = max(10, m - 25)
        return "Swim: technique and aerobic", [blk(8, "warm", "easy swim + kick"), blk(10, "easy", "drills (catch-up, fingertip drag, sculling)"), blk(main, "easy", "steady aerobic, RPE 3"), blk(5, "cool")], False, base_txt
    if ctx["quality_ok"] and not ctx["recovery"] and phase in ("BUILD", "PEAK") and kind == "swim2" and lvl != "beginner":
        n = max(3, min(8, round((m - 20) / 4)))
        return f"Swim: main set ({n} x 3 min)", [blk(8, "warm", "easy swim + kick"), blk(6, "easy", "drills"), reps(n, 3, "tempo", 0.5, "recover"), blk(5, "cool")], True, "Steady-hard repeats (RPE 6), even pace from the first to the last. " + base_txt
    main = max(10, m - 20)
    return "Swim: aerobic endurance", [blk(8, "warm", "easy swim"), blk(main, "easy", "steady aerobic with a few 25 m kicks"), blk(5, "cool")], False, base_txt


def strength_session(ctx, week_idx, light, slot_idx):
    ath, ev = ctx["athlete"], ctx["ev"]
    try:
        import strength_plan as sp
        week, meta = sp.make_week(ath, [], week_idx, light=light, goal=ev["strength"], version=ctx.get("strength_version"))
        if slot_idx < len(week):
            s = week[slot_idx]
            return {"title": s["title"] + (" (light)" if light else ""), "minutes": s["minutes"], "desc": f"{meta['label']}. Lift with 2-3 reps in reserve, stop a set if form breaks. Strength starts at least 3 hours after cardio (practice).",
                    "strength": {"exercises": s["exercises"], "lines": s.get("lines", []), "volume": s["volume"], "needs": s["needs"]}}
    except SystemExit:
        pass
    except Exception:
        pass
    return {"title": "Strength (needs your equipment first)", "minutes": 30, "desc": "Tell the coach which equipment you have and which exercises you cannot do; the strength generator then writes this session. Asked, not assumed.", "strength": {"exercises": [], "volume": {}, "needs": ["equipment"]}}


# ---------------------------------------------------------------- the plan
def phases_for(weeks, taper):
    pre = max(1, weeks - taper)
    base = max(1, round(0.45 * pre))
    build = max(1, round(0.35 * pre))
    out = []
    for i in range(1, weeks + 1):
        if i > pre:
            out.append("TAPER")
        elif i <= base:
            out.append("BASE")
        elif i <= base + build:
            out.append("BUILD")
        else:
            out.append("PEAK")
    return out


def weekly_volumes(weeks, taper, v0, peak, phases):
    """Weekly endurance minutes: +10 % at most per build week, a recovery week every 4th week, then the taper. Returns (volumes, recovery flags, reachable_peak)."""
    vols, rec, prev = [], [], v0
    pre = weeks - taper
    for i in range(1, pre + 1):
        if i % RECOVERY_EVERY == 0 and i < pre:
            vols.append(prev * RECOVERY_FACTOR)
            rec.append(True)
        else:
            vols.append(prev if i == 1 else min(prev * (1 + GROWTH), max(peak, v0)))
            prev = vols[-1]
            rec.append(False)
    top = max(vols) if vols else v0
    factors = TAPER_FACTORS[min(max(taper, 1), 3)]
    for k in range(taper):
        vols.append(top * factors[min(k, len(factors) - 1)])
        rec.append(False)
    return vols, rec, top


def blocks_to_workout(sess, B, hrt, wk):
    """A heart-rate workout (for a .fit file) from a session's blocks, with the athlete's own bands. Zone first, custom bpm second, open target when no band is known (by feel)."""
    run = sess["sport"] == "run"
    sport = "running" if run else "cycling"
    ceil, floor = (B["ceil_r"], B["floor"]) if run else (B["ceil_b"], B["floor_b"])
    easy_t = wk.hr_band(floor, ceil, sport)
    word = "run" if run else "ride"

    def target(effort):
        if effort in ("easy", "steady"):
            return easy_t
        if effort == "tempo":
            return hrt.get("tempo") if run else wk.OPEN
        if effort in ("threshold", "hard"):
            return hrt.get("hard_run" if run else "hard_bike", wk.OPEN)
        return wk.OPEN

    def one(b):
        e = b["effort"]
        if e == "warm":
            return wk.step("Warm-up", "warmup", minutes=b["minutes"], target=wk.OPEN, note=wk.cap(ceil, "easy, build slowly"))
        if e == "cool":
            return wk.step("Cool-down", "cooldown", minutes=b["minutes"], target=wk.OPEN, note=wk.cap(ceil, "easy, let HR drop"))
        if e == "recover":
            return wk.step("Easy", "recovery", minutes=b["minutes"], target=wk.OPEN, note=wk.cap(ceil))
        t = target(e)
        if e in ("tempo", "threshold", "hard"):
            return wk.step(EFFORT[e][0].capitalize(), "interval", minutes=b["minutes"], target=t, note="" if t["type"] != "open" else "by feel: " + EFFORT[e][1])
        return wk.step(wk.zone_name(t, word) if e == "easy" else "Steady", "active", minutes=b["minutes"], target=t)

    steps = []
    for b in sess["blocks"]:
        if "repeat" in b:
            steps.append(wk.repeat(b["repeat"], one({**b["on"]}), one({**b["off"], "effort": "recover" if b["off"]["effort"] in ("recover", "easy") else b["off"]["effort"]})))
        else:
            steps.append(one(b))
    return wk.workout(sess["title"][:30], sport, *steps)


def attach_workouts(sessions, athlete):
    """Add a heart-rate `workout` to every run and ride session when the athlete's heart-rate data are known (ask-first: nothing is assumed). Returns True if any were added."""
    try:
        import build_plan as bp
        import workout as wk
        B = bp.setup_hr(athlete)
        wk.set_zones(bp.zone_sets(athlete["hr"]), (athlete["hr"].get("target_mode") or {}).get("tolerance_bpm", 3))
        hrt = dict(bp.HR)
    except Exception:
        return False
    n = 0
    for s_ in sessions:
        if s_["sport"] in ("run", "bike") and s_.get("blocks"):
            s_["workout"] = blocks_to_workout(s_, B, hrt, wk)
            n += 1
    return n > 0


def inputs_from_garmin(today=None):
    """Read the athlete's real training from Garmin: hours a week now, longest recent run/ride/swim, sports done, their share of time, and training days a week."""
    from datetime import date as _d
    today = today or _d.today()
    ws0 = gc.week_start(today)
    with gc.Garmin() as g:
        acts = gc.list_activities(g, ws0 - timedelta(days=35), today)
    sports = ("run", "bike", "swim")
    weeks = {}
    for a in acts:
        if a["sport"] in sports:
            w = weeks.setdefault(gc.week_start(a["date"]), {"min": 0.0, "days": set(), **{x: 0.0 for x in sports}})
            w["min"] += a["min"]
            w["days"].add(a["date"])
            w[a["sport"]] += a["min"]
    done = [weeks.get(ws0 - timedelta(days=7 * k)) for k in (3, 2, 1)]
    done = [w for w in done if w]
    tot = sum(w["min"] for w in done) / max(1, len(done)) if done else 0.0
    d30 = today - timedelta(days=30)

    def longest(sp):
        return max((a["min"] for a in acts if a["sport"] == sp and a["date"] >= d30), default=0)
    share = {sp: sum(w[sp] for w in done) for sp in sports}
    present = [sp for sp in sports if share[sp] > 0]
    days = round(sum(len(w["days"]) for w in done) / max(1, len(done))) if done else 0
    return {"hours_now": round(tot / 60.0, 1), "longest_run_min": round(longest("run")), "longest_ride_min": round(longest("bike")), "longest_swim_min": round(longest("swim")),
            "sports": present, "shares": {sp: share[sp] for sp in present}, "days_per_week": min(7, max(5, days)) if days else None, "weeks_of_data": len(done)}


def build(ev_key, event_date, start, level, hours_now, max_hours, days, base, athlete=None, strength=2, cross_train=True, strength_version=None, weeks=None, sports=None, shares=None, readiness=None):
    ev = dict(EVENTS[ev_key])
    athlete = athlete or {}
    is_base = ev_key == "base"
    warnings = []
    mix_shares = {}
    if is_base:
        sports = [x for x in (sports or ["run", "bike"]) if x in ("run", "bike", "swim")] or ["run", "bike"]
        raw = {x: float((shares or {}).get(x) or 1.0) for x in sports}
        mix_shares = {x: v / sum(raw.values()) for x, v in raw.items()}
        first_monday = monday(start)
        weeks_total = int(weeks or 12)
        race_week_monday = first_monday + timedelta(weeks=weeks_total - 1)
        event_date = race_week_monday + timedelta(days=8)          # beyond the plan: there is no race, nothing is cut
        lo, hi = ev["weeks"]
        if weeks_total < lo:
            warnings.append(f"A {weeks_total}-week block is short for a base phase ({lo}-{hi} is usual). That is fine as a rolling block: re-plan at the end from fresh data, and expect small changes in aerobic fitness in so few weeks.")
    else:
        event_date = date.fromisoformat(str(event_date))
        first_monday = monday(start)
        race_week_monday = monday(event_date)
        weeks_total = (race_week_monday - first_monday).days // 7 + 1
        lo, hi = ev["weeks"]
    if not is_base and weeks_total > hi + 4:
        first_monday = race_week_monday - timedelta(weeks=hi + 3)
        weeks_total = hi + 4
        warnings.append(f"The event is far away: the plan starts {weeks_total} weeks before it. Keep training easy and consistent until then.")
    if not is_base and weeks_total < lo:
        warnings.append(f"Only {weeks_total} weeks to the event; {lo}-{hi} weeks is usual for a {ev['label']}. The plan is compressed and will peak lower. Treat the result as a finish-it plan, not a target-time plan.")
    peak_h = min(hours_now * 1.35, max_hours) if is_base else min(ev["peak"][level], max_hours)
    v0 = hours_now * 60.0
    phases = ["BASE"] * weeks_total if is_base else phases_for(weeks_total, ev["taper"])
    vols, rec, top = weekly_volumes(weeks_total, ev["taper"], v0, peak_h * 60.0, phases)
    if readiness in ("red", "amber") and vols:
        vols[0] *= 0.7
        warnings.append(f"Readiness is {readiness.upper()}: week 1 is a lighter week (70 % of the planned volume).")
    if is_base:
        warnings.append("No target: the aim is a bigger aerobic engine. The plan raises weekly time by at most 10 %, keeps about 80 % easy, repeats one standardised aerobic test in each lighter week, and never promises a gain.")
    if not is_base and top < 0.95 * peak_h * 60 and top >= v0:
        warnings.append(f"At +10 % a week you reach {top / 60:.1f} h a week before the taper, not the {peak_h:.1f} h a {ev['label']} usually needs at your level. That is the honest ceiling for the weeks you have.")
    if not is_base and v0 > peak_h * 60:
        warnings.append(f"You already train more than the usual peak for this level ({peak_h:.1f} h): volume is held, not increased.")
    kind = ev["kind"]
    injury_block = any((i.get("status") in ("active", "monitoring")) for i in (athlete.get("injuries") or []))
    leg_pain = bool(base.get("leg_pain_history"))
    if injury_block:
        warnings.append("An injury is active or being monitored: no quality sessions in this plan (strides, drills, tempo, intervals), and volume is not increased beyond the plan's own cap. Follow the restriction you recorded.")
    if kind in ("tri", "du"):
        if injury_block:
            warnings.append("No brick runs while an injury is active or being monitored (running straight after cycling is harder on the legs; Walsh 2019).")
        elif leg_pain:
            warnings.append("Brick runs are kept to 10 minutes because of your history of exercise-related leg pain (Walsh 2019 reports more difficulty replicating running muscle patterns after cycling with such a history).")
    if kind == "mix":
        single = {"run": RUN_DAYS, "bike": BIKE_DAYS, "swim": SWIM_DAYS}
        order = single[sports[0]] if len(sports) == 1 else MIX_DAYS
        order = [(k, d) for k, d in order if __import__("re").sub(r"\d+$", "", k.split("_")[0]) in sports]
    else:
        order = {"tri": TRI_DAYS, "du": DU_DAYS, "bike": BIKE_DAYS, "swim": SWIM_DAYS}.get(kind, RUN_DAYS)
    chosen = order[:max(3, min(days, len(order)))]
    ctx = {"ev": ev, "level": level, "athlete": athlete, "strength_version": strength_version, "aerobic_test": is_base}
    # long-session chains start from the athlete's own longest sessions
    prev_long = {"run": max(base.get("longest_run_min", 40), 30), "bike": max(base.get("longest_ride_min", 60), 45), "swim": max(base.get("longest_swim_min", 25), 20)}
    cap_long = {"run": ev.get("long_run", 60), "bike": ev.get("long_bike", 120), "swim": ev.get("long_swim", 45)}
    prefs = athlete.get("preferences") or {}
    cardio_start = prefs.get("cardio_start", "06:30")
    strength_start = prefs.get("strength_start", "18:30")
    sessions, weekly = [], []
    for wi in range(weeks_total):
        wk_monday = first_monday + timedelta(weeks=wi)
        phase, recovery, total = phases[wi], rec[wi], vols[wi]
        is_race_week = (wk_monday == race_week_monday) and not is_base
        ctx.update(quality_ok=not injury_block, recovery=recovery)
        if kind == "mix":
            shares = mix_shares
        elif kind in ("tri", "du", "bike", "swim"):
            shares = ev["shares"]
        else:
            shares = {"run": 0.85, "bike": 0.15} if cross_train else {"run": 1.0}
        keys = [k for k, _ in chosen]
        by_sport = {s: total * f for s, f in shares.items()}
        plan_sessions = []                                   # (key, sport, minutes)
        brick = 0
        if kind in ("tri", "du") and "bike_long" in keys and phase in ("BUILD", "PEAK") and not recovery and not is_race_week:
            lo_b, hi_b = ev["brick"]
            brick = lo_b if phase == "BUILD" else hi_b
            if injury_block:
                brick = 0
            elif leg_pain:
                brick = min(brick, 10)
        def alloc(sport, keys_s, pool, long_key, long_w):
            """Split `pool` minutes over the sport's sessions. The long session gets its share but is capped (+10 % on the last long one, event cap);
            what the cap frees goes to the other sessions, none of which may exceed 85 % of the long one. Lighter weeks never exceed the last long session."""
            out = {}
            if not keys_s:
                return out
            others = [k for k in keys_s if k != long_key]
            if long_key in keys_s:
                m = pool * (long_w if others else 1.0)
                cap = min(cap_long[sport], prev_long[sport] * LONG_CAP)
                if recovery:
                    cap = min(cap, prev_long[sport])
                m = min(m, cap)
                out[long_key] = m
                if not recovery and m >= MIN_MIN[sport]:
                    prev_long[sport] = max(prev_long[sport], m)
                rest = pool - m
                others = others[:max(0, min(len(others), int(rest // MIN_MIN[sport])))] if others else []     # fewer, longer sessions beat many that are too short
                for k in others:
                    out[k] = min(rest / len(others), (0.85 * m if m >= MIN_MIN[sport] else rest), MID_CAP[sport])
            else:
                others = others[:max(1, min(len(others), int(pool // MIN_MIN[sport])))] if others else []
                for k in others:
                    out[k] = min(pool / len(others), MID_CAP[sport])
            return out

        run_keys = [k for k in keys if k.startswith("run")]
        bike_keys = [k for k in keys if k.startswith("bike")]
        swim_keys = [k for k in keys if k.startswith("swim")]
        for k, m in alloc("run", run_keys, max(0.0, by_sport.get("run", 0) - brick), "run_long", 0.42 if len(run_keys) > 2 else 0.55).items():
            plan_sessions.append((k, "run", r5(m)))
        for k, m in alloc("bike", bike_keys, by_sport.get("bike", 0), "bike_long", 0.5 if len(bike_keys) > 1 else 1.0).items():
            plan_sessions.append((k, "bike", r5(m)))
        if "swim_long" in swim_keys:
            for k, m in alloc("swim", swim_keys, by_sport.get("swim", 0), "swim_long", 0.34).items():
                plan_sessions.append((k, "swim", r5(max(m, 25))))
            swim_keys = []
        for k in swim_keys:
            m = min(max(by_sport.get("swim", 0) / len(swim_keys), 25), cap_long["swim"], max(prev_long["swim"] * LONG_CAP, 25))   # a swim session is never shorter than 25 min: technique needs frequency
            if not recovery and m >= MIN_MIN["swim"]:
                prev_long["swim"] = max(prev_long["swim"], m)
            plan_sessions.append((k, "swim", r5(m)))
        day_of = dict(chosen)
        built = []
        for key, sport, m in plan_sessions:
            if m < MIN_MIN[sport]:
                continue
            fn = {"run": run_session, "bike": bike_session, "swim": swim_session}[sport]
            title, blocks, quality, text = fn(key, m, phase, ctx)
            built.append(dict(key=key, sport=sport, minutes=m, title=title, blocks=blocks, quality=quality, text=text, weekday=day_of[key]))
        if brick:
            built.append(dict(key="brick_run", sport="run", minutes=brick, weekday="Sat", slot_after="bike_long", **dict(zip(("title", "blocks", "quality", "text"), run_session("brick_run", brick, phase, ctx)))))
        # strength
        str_days = [d for d in (["Tue", "Thu"] if kind in ("tri", "du") else ["Mon", "Thu"])][:strength]
        for si, sd in enumerate(str_days):
            if is_race_week or phase == "TAPER" and si > 0:
                continue
            s = strength_session(ctx, wk_monday.isocalendar()[1], recovery or phase == "TAPER", si)
            built.append(dict(key=f"str{si + 1}", sport="strength", minutes=s["minutes"], title=s["title"], blocks=[], quality=False, text=s["desc"], weekday=sd, strength=s["strength"]))
        # dates, times, descriptions
        for b in sorted(built, key=lambda x: WD.index(x["weekday"])):
            d = wk_monday + timedelta(days=WD.index(b["weekday"]))
            if d >= event_date - timedelta(days=1) or d < start:   # race day and the day before are written separately (activation, race)
                continue
            slot = "PM" if b["sport"] == "strength" or b.get("slot_after") else "AM"
            hh, mm = (int(x) for x in (strength_start if b["sport"] == "strength" else cardio_start).split(":"))
            if b.get("slot_after"):
                hh, mm = divmod(hh * 60 + mm + 150, 60)           # the brick run starts right after the long ride
            st = datetime(d.year, d.month, d.day, hh, mm)
            desc = b["text"]
            if b["blocks"]:
                desc = f"{fmt_blocks(b['blocks'])}. {desc}"
            tag = "RECOVERY" if recovery and phase != "TAPER" else phase
            sessions.append({"date": str(d), "weekday": b["weekday"], "slot": slot, "week": wi + 1, "phase": phase, "week_tag": tag, "recovery_week": recovery,
                             "sport": b["sport"], "kind": b["key"], "minutes": b["minutes"], "title": b["title"], "desc": desc, "blocks": b["blocks"], "quality": b["quality"],
                             "start": st.isoformat(timespec="minutes"), "end": (st + timedelta(minutes=b["minutes"])).isoformat(timespec="minutes"),
                             **({"strength": b["strength"]} if "strength" in b else {})})
        # day before the race: short activation; race day
        if is_race_week:
            eve = event_date - timedelta(days=1)
            if not any(s["date"] == str(eve) for s in sessions) and eve >= start:
                st = datetime(eve.year, eve.month, eve.day, 9, 0)
                sessions.append({"date": str(eve), "weekday": WD[eve.weekday()], "slot": "AM", "week": wi + 1, "phase": "TAPER", "week_tag": "TAPER", "recovery_week": False, "sport": RACE_SPORT[kind],
                                 "kind": "activation", "minutes": 20, "title": f"Activation (20 min easy {RACE_WORD[kind]} + 3 short pickups)", "desc": "20 min easy with 3 pickups of 15 s at race effort. Pack your kit, check your gear, eat normally, sleep.",
                                 "blocks": [blk(8, "warm"), blk(12, "easy")], "quality": False, "start": st.isoformat(timespec="minutes"), "end": (st + timedelta(minutes=20)).isoformat(timespec="minutes")})
            st = datetime(event_date.year, event_date.month, event_date.day, 8, 0)
            sessions.append({"date": str(event_date), "weekday": WD[event_date.weekday()], "slot": "AM", "week": wi + 1, "phase": "RACE", "week_tag": "RACE", "recovery_week": False, "sport": RACE_SPORT[kind],
                             "kind": "race", "minutes": 0, "title": f"RACE DAY: {ev['label']}", "desc": ("Run the first kilometre about 5 % slower than your planned pace (Walsh 2019, one elite study). " if kind in ("tri", "du") else "") + "Start easier than feels necessary for the first third. Eat and drink as practised, nothing new. It is a day to enjoy the work you did; no plan can promise a time.",
                             "blocks": [], "quality": False, "start": st.isoformat(timespec="minutes"), "end": st.isoformat(timespec="minutes")})
        wk_sessions = [s for s in sessions if s["week"] == wi + 1]
        weekly.append({"week": wi + 1, "monday": str(wk_monday), "phase": phase, "tag": "RECOVERY" if recovery and phase != "TAPER" else phase, "target_min": round(total),
                       "planned_min": sum(s["minutes"] for s in wk_sessions if s["sport"] != "strength"),
                       "by_sport": {sp_: sum(s["minutes"] for s in wk_sessions if s["sport"] == sp_) for sp_ in ("swim", "bike", "run", "strength") if any(s["sport"] == sp_ for s in wk_sessions)}})
    if weekly and weekly[0]["planned_min"] < 0.8 * weekly[0]["target_min"]:
        warnings.append(f"Week 1 plans {weekly[0]['planned_min'] / 60:.1f} h, below the {weekly[0]['target_min'] / 60:.1f} h you report, because your longest recent sessions are short and long sessions only grow +10 % a week. If your longest sessions were longer, give the real numbers.")
    quality_min = sum(s["minutes"] * 0.35 for s in sessions if s["quality"])
    endurance = sum(s["minutes"] for s in sessions if s["sport"] != "strength")
    has_workouts = attach_workouts(sessions, athlete)
    meta = {"kind": "event", "goal": "base" if is_base else "event", "event": ev_key, "event_label": ev["label"], "event_date": None if is_base else str(event_date), "start": str(first_monday), "weeks": weeks_total, "level": level,
            "has_workouts": has_workouts, "sports": sports if is_base else None, "weekly_targets": [{"week": w["week"], "tag": w["tag"], "endurance_min": w["target_min"], "long_run_min": next((x["minutes"] for x in sessions if x["week"] == w["week"] and x["kind"] == "run_long"), 0)} for w in weekly],
            "hours_now": hours_now, "peak_hours": round(top / 60, 1), "target_peak_hours": peak_h, "days_per_week": days, "phases": phases, "weekly": weekly,
            "warnings": warnings, "basis": BASIS, "generated": str(date.today()),
            "hard_share_estimate": round(quality_min / endurance, 2) if endurance else 0,
            "notes": ["Pain that changes how you move, chest pain or fainting: stop and see a clinician. Not medical advice.",
                      "Effort is given as RPE and, for rides, as a share of FTP; heart-rate targets are not assumed (ask-first).",
                      "No plan can promise a finish time. Targets are checked against your own data, not promised."] + (["Ask the athlete: any history of exercise-related leg pain, or an injury now? Brick runs are cut or dropped if yes."] if kind in ("tri", "du") else [])}
    return meta, sessions


def to_md(meta, sess):
    out = [f"# {meta['event_label']} plan: {meta['weeks']} weeks" + (f" to {meta['event_date']}" if meta.get("event_date") else ""), "",
           f"Level {meta['level']}, {meta['days_per_week']} days a week, now {meta['hours_now']} h a week, peak about {meta['peak_hours']} h (target {meta['target_peak_hours']} h).", ""]
    if meta["warnings"]:
        out += ["**Heads-up**", ""] + [f"- {w}" for w in meta["warnings"]] + [""]
    cur = None
    for s in sess:
        if s["week"] != cur:
            cur = s["week"]
            w = meta["weekly"][cur - 1]
            out += ["", f"## Week {cur}: {w['tag']} (about {w['target_min'] / 60:.1f} h)", ""]
        out.append(f"- **{s['date']} {s['weekday']}** {s['sport']}: {s['title']}" + (f" ({s['minutes']} min)" if s["minutes"] else ""))
        out.append(f"  - {s['desc']}")
    out += ["", "## Why (rule labels)", ""] + [f"- {b}" for b in meta["basis"]] + ["", "## Notes", ""] + [f"- {n}" for n in meta["notes"]]
    return "\n".join(out) + "\n"


def load_athlete():
    try:
        return json.loads(gc.ATHLETE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--event", choices=sorted(EVENTS))
    ap.add_argument("--goal", choices=["event", "base"], help="base = no race and no target: build endurance and aerobic base")
    ap.add_argument("--weeks", type=int, help="plan length in weeks for --goal base (2-52). Order: this flag, then preferences.plan_weeks in athlete.json, then 12. A race plan always runs to race day.")
    ap.add_argument("--sports", help="for --goal base: comma list of run, bike, swim")
    ap.add_argument("--from-garmin", action="store_true", help="read hours a week, longest sessions, sports and training days from your Garmin history")
    ap.add_argument("--readiness", choices=["red", "amber", "green"], help="today's readiness: red or amber makes week 1 a lighter week")
    ap.add_argument("--event-date")
    ap.add_argument("--start")
    ap.add_argument("--level", choices=LEVELS)
    ap.add_argument("--hours-now", type=float)
    ap.add_argument("--max-hours", type=float)
    ap.add_argument("--days", type=int, choices=[5, 6, 7])
    ap.add_argument("--longest-run-min", type=float)
    ap.add_argument("--longest-ride-min", type=float)
    ap.add_argument("--longest-swim-min", type=float)
    ap.add_argument("--strength", type=int, default=None)
    ap.add_argument("--no-cross-train", action="store_true")
    ap.add_argument("--leg-pain-history", action="store_true", help="history of exercise-related leg pain: brick runs are cut to 10 minutes")
    ap.add_argument("--out")
    ap.add_argument("--md", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--list-events", action="store_true")
    gc.apply_here_flag()
    a = ap.parse_args()
    gc.utf8_stdout()
    if a.list_events:
        for k, e in EVENTS.items():
            print(f"{k:12} {e['label']:36} usual plan length {e['weeks'][0]}-{e['weeks'][1]} weeks, taper {e['taper']} week(s)")
        return
    ath = load_athlete()
    mb = ath.get("manual_baseline") or {}
    evt = ath.get("event") or {}
    is_base = a.goal == "base" or a.event == "base"
    ev_key = "base" if is_base else (a.event or evt.get("type"))
    ev_date = None if is_base else (a.event_date or evt.get("date"))
    gar = None
    if a.from_garmin:
        gar = inputs_from_garmin()
        print(f"From your Garmin history ({gar['weeks_of_data']} complete weeks): {gar['hours_now']} h a week, longest run {gar['longest_run_min']} min, ride {gar['longest_ride_min']} min, swim {gar['longest_swim_min']} min, sports {gar['sports']}, days a week {gar['days_per_week']}.")
    level = a.level or mb.get("level")
    hours_now = a.hours_now if a.hours_now is not None else (gar["hours_now"] if gar and gar["hours_now"] else mb.get("hours_now"))
    max_hours = a.max_hours if a.max_hours is not None else mb.get("max_hours")
    days = a.days or (gar["days_per_week"] if gar else None) or mb.get("days_per_week")
    sports = [x.strip() for x in a.sports.split(",")] if a.sports else ((gar or {}).get("sports") or mb.get("sports"))
    asks = [("event (--event), or --goal base for no target", ev_key), ("level: beginner, intermediate or advanced (--level)", level),
            ("hours you train per week now (--hours-now, or --from-garmin)", hours_now), ("most hours per week you can train (--max-hours)", max_hours), ("training days per week, 5, 6 or 7 (--days)", days)]
    if is_base:
        asks.append(("which sports to build: run, bike, swim (--sports)", sports))
    else:
        asks.insert(1, ("event date (--event-date YYYY-MM-DD)", ev_date))
    missing = [n for n, v in asks if v in (None, "", [])]
    if missing:
        print("I need these from the athlete first (ask, do not guess):")
        for m in missing:
            print("  -", m)
        print("Optional but useful: longest recent run / ride / swim in minutes, equipment for strength, injuries and pain today, any history of exercise-related leg pain.")
        print('Record them: athlete.py set manual_baseline \'{"level":"intermediate","hours_now":6,"max_hours":9,"days_per_week":6,"sports":["run","bike"]}\'  and, for a race,  athlete.py set event \'{"type":"olympic-tri","date":"2027-06-20"}\'')
        sys.exit(2)
    start = date.fromisoformat(a.start) if a.start else date.today()
    base = {"longest_run_min": a.longest_run_min or (gar or {}).get("longest_run_min") or mb.get("longest_run_min", 40), "leg_pain_history": a.leg_pain_history or bool(mb.get("leg_pain_history")),
            "longest_ride_min": a.longest_ride_min or (gar or {}).get("longest_ride_min") or mb.get("longest_ride_min", 60), "longest_swim_min": a.longest_swim_min or (gar or {}).get("longest_swim_min") or mb.get("longest_swim_min", 25)}
    nstr = 2 if a.strength is None else a.strength
    plan_weeks = a.weeks or (ath.get("preferences") or {}).get("plan_weeks")
    if is_base and plan_weeks is not None and not (2 <= int(plan_weeks) <= 52):
        sys.exit("Plan length must be 2 to 52 weeks (--weeks, or preferences.plan_weeks in athlete.json).")
    meta, sess = build(ev_key, ev_date, start, level, float(hours_now), float(max_hours), int(days), base, ath, nstr, not a.no_cross_train, weeks=int(plan_weeks) if (is_base and plan_weeks) else None, sports=sports, shares=(gar or {}).get("shares"), readiness=a.readiness)
    tag = f"base-{start}" if is_base else f"{ev_key}-{ev_date}"
    out = Path(a.out) if a.out else gc.out_dir("plans", tag) / "plan.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"meta": meta, "sessions": sess}, indent=1, default=str), encoding="utf-8")
    fit_note = " (with heart-rate workouts for the watch: export_plan.py --format fit)" if meta.get("has_workouts") else ""
    if a.json:
        print(json.dumps({"meta": meta, "sessions": sess}, default=str))
    else:
        print(to_md(meta, sess) if a.md else f"{meta['event_label']}: {meta['weeks']} weeks, {len(sess)} sessions, peak about {meta['peak_hours']} h a week{fit_note}.\nSaved: {out}\nNext: plan_viewer.py \"{out}\" (one HTML page) and export_plan.py \"{out}\" (calendar, spreadsheet, Zwift, MRC); they write next to it.")
        for w in meta["warnings"]:
            print("HEADS-UP:", w)


if __name__ == "__main__":
    main()
