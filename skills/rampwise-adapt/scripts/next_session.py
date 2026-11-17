#!/usr/bin/env python3
"""Adapt the next planned session(s) to how you are doing, and prepare the calendar update.

  next_session.py [--date YYYY-MM-DD] [--days 1] [--plan PLAN.json] [--write-fit] [--record] [--json] [--assume-readiness GREEN|AMBER|RED]

Reads your latest saved plan, today's readiness, the injury-risk watch (load, recovery, your injury list, pain check-ins) and how much of the last two weeks'
plan you did. For each planned session on the target date(s) it decides: keep, progress (a small step up), easy_swap (quality becomes easy), reduce
(shorter), recovery (20-30 min easy spin, only if pain-free) or rest. It builds the changed workout with the same builders as the planner, optionally writes
the .fit file, and prints the calendar event update for the coach to apply (the script never writes to your calendar).
--record stores the date of a progression so the next one waits a week. Rules and evidence: ../references/evidence-map.md.
"""
import argparse
import json
import math
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILLS = HERE.parent.parent
for sub in ("rampwise", "rampwise-planner", "rampwise-strength", "rampwise-recovery", "rampwise-analyze", "rampwise-adapt"):
    sys.path.insert(0, str(SKILLS / sub / "scripts"))
import gcommon as gc  # noqa: E402
import analysis  # noqa: E402
import adapt_logic as al  # noqa: E402
import workout as wk  # noqa: E402
import build_plan as bp  # noqa: E402

STATE = gc.DATA_DIR / "adapt_state.json"


def latest_plan(path=None):
    p = Path(path) if path else max(gc.plan_files("plan-*.json"), default=None, key=lambda x: x.name)
    if not p:
        sys.exit(f"no saved plan in {gc.out_root() / 'plans'}: build one first (build_plan.py saves it there)")
    return json.loads(p.read_text(encoding="utf-8")), p


def snap5(x):
    return max(5, int(round(x / 5.0)) * 5)


def build_new(s, dec, ath, B, longest):
    """The changed session as {title, minutes, workout, desc, why_key}. Uses the planner's own builders and bands."""
    sport = "running" if s["sport"] == "run" else "cycling"
    prefs = ath["preferences"]
    er, ep = prefs.get("easy_run", {}), prefs.get("easy_ride", {})
    warm = er.get("warmup_min", 10) if s["sport"] == "run" else ep.get("warmup_min", 10)
    cool = er.get("cooldown_min", 5) if s["sport"] == "run" else ep.get("cooldown_min", 5)
    ceil, floor = (B["ceil_r"], B["floor"]) if s["sport"] == "run" else (B["ceil_b"], B["floor_b"])
    restr = [f"{i['area']}: {i.get('restrict') or 'ask the athlete what to avoid'}" for i in ath.get("injuries", []) if i.get("status") != "resolved"]
    fmt = {"ceil": ceil, "lo": B["t_lo"], "hi": B["t_hi"], "target": 0, "maf": 0}
    d = dec["decision"]
    orig = s["minutes"]
    if d == "rest":
        return {"title": "Rest day (adapted)", "minutes": 0, "workout": None, "why_key": None, "desc": None}
    if d == "recovery":
        w = wk.easy("cycling", 25, B["ceil_b"], B["floor_b"], warm=5, cool=5, label="Recovery spin 25 min")
        return {"title": "Recovery spin 25 min (adapted)", "minutes": 25, "workout": w, "why_key": "ride_easy", "desc": bp.cardio_desc("ride_easy", w, "Only if it is pain-free; otherwise rest or a short easy walk.", restr, **fmt)}
    if d in ("easy_swap", "reduce"):
        mins = snap5(orig * (dec["factor"] or 0.9))
        mins = max(mins, warm + cool + 10)
        w = wk.easy(sport, mins, ceil, floor, warm=warm, cool=cool, label=f"Easy {mins} min")
        key = "run_easy" if s["sport"] == "run" else "ride_easy"
        return {"title": f"Easy {'run' if s['sport'] == 'run' else 'ride'} ({warm}+{mins - warm - cool}+{cool}) (adapted)", "minutes": mins, "workout": w, "why_key": key,
                "desc": bp.cardio_desc(key, w, "Kept easy on purpose: heart rate under your easy ceiling.", restr, **fmt)}
    if d == "progress":
        cat, q = dec["progress"]["category"], dec["progress"]["q"]
        steps = s["workout"]["steps"]
        if q == "tempo":
            blk = next(x for x in steps if x.get("name") == "Tempo")
            new_blk = min(30, blk["seconds"] / 60 + 5)
            if new_blk <= blk["seconds"] / 60:
                return None
            w = wk.tempo("running", 1, new_blk, 0, bp.HR["tempo"], ceil, warm=warm, cool=cool)
            return {"title": f"Tempo run ({warm}+{new_blk:g}+{cool}) (progressed)", "minutes": round(wk.est_minutes(w)), "workout": w, "why_key": "run_tempo",
                    "desc": bp.cardio_desc("run_tempo", w, f"One step up: the tempo block is {new_blk:g} min instead of {blk['seconds'] / 60:g}.", restr, **fmt)}
        if q == "intervals":
            rep = next(x for x in steps if x["kind"] == "repeat")
            reps, hard, rest = rep["times"], rep["steps"][0]["seconds"] / 60, rep["steps"][1]["seconds"] / 60
            if reps >= 6:
                return None
            total = orig + hard + rest
            hard_t = bp.HR["hard_run"] if s["sport"] == "run" else bp.HR["hard_bike"]
            w = wk.intervals(sport, total, reps + 1, hard, rest, hard_t, ceil, floor, warm=warm, cool=cool)
            key = "run_intervals" if s["sport"] == "run" else "ride_intervals"
            return {"title": f"Intervals {reps + 1} x {hard:g} min (progressed)", "minutes": round(wk.est_minutes(w)), "workout": w, "why_key": key,
                    "desc": bp.cardio_desc(key, w, f"One step up: {reps + 1} hard repeats instead of {reps}.", restr, **fmt)}
        if cat in ("long", "easy"):
            ref = longest.get(s["sport"], 0)
            cap = math.floor(ref * al.LONG_CAP / 5) * 5 if ref else orig
            step = 5 if s["sport"] == "run" else 10
            new = min(orig + step, cap) if cat == "long" else orig + 5
            if new <= orig:
                return None
            w = wk.easy(sport, new, ceil, floor, warm=warm, cool=cool, label=f"{'Long' if cat == 'long' else 'Easy'} {new} min")
            key = ("run_long" if cat == "long" else "run_easy") if s["sport"] == "run" else ("ride_long" if cat == "long" else "ride_easy")
            return {"title": f"{'Long' if cat == 'long' else 'Easy'} {'run' if s['sport'] == 'run' else 'ride'} ({warm}+{new - warm - cool}+{cool}) (progressed)", "minutes": new, "workout": w, "why_key": key,
                    "desc": bp.cardio_desc(key, w, f"One step up: {new} min instead of {orig} (capped at +10 % over your recent longest).", restr, **fmt)}
    return None


def calendar_update(s, new, dec, today):
    start = datetime.fromisoformat(s["start"])
    head = f"ADAPTED ({dec['decision']}): " + "; ".join(dec["reasons"]) + f"\nOriginal plan: {s['title']}, {s['minutes']} min.\n\n"
    if new is None or new.get("workout") is None and new.get("minutes", 1) == 0:
        title = f"[GC] Rest day (adapted) - was {s['title']}"
        end = start + timedelta(minutes=30)
        body = head + "Rest today. If something hurts, tell the coach; pain that changes how you move or lasts more than a few days needs a clinician.\n\nrampwise-plan:adapted-" + str(today)
    else:
        title = f"[GC] {new['title']} - {new['minutes']} min"
        end = start + timedelta(minutes=new["minutes"])
        body = head + (new.get("desc") or "") + "\n\nrampwise-plan:adapted-" + str(today)
    return {"find": {"date": s["date"], "marker": "rampwise-plan", "legacy_marker": "garmin-coach-plan", "original_summary_contains": s["title"]},
            "update": {"summary": title, "startTime": start.isoformat(timespec="seconds"), "endTime": end.isoformat(timespec="seconds"), "description": body, "notificationLevel": "NONE"}}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date")
    ap.add_argument("--days", type=int, default=1)
    ap.add_argument("--plan")
    ap.add_argument("--write-fit", action="store_true")
    ap.add_argument("--record", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--assume-readiness", choices=["GREEN", "AMBER", "RED"], help="testing: skip the readiness call")
    gc.apply_here_flag()
    a = ap.parse_args()
    gc.utf8_stdout()
    today = date.today()
    target = date.fromisoformat(a.date) if a.date else today + timedelta(days=1)
    ath = json.loads(gc.ATHLETE_PATH.read_text(encoding="utf-8"))
    plan, plan_path = latest_plan(a.plan)
    B = bp.setup_hr(ath)
    wk.set_zones(bp.zone_sets(ath["hr"]), (ath["hr"].get("target_mode") or {}).get("tolerance_bpm", 3))
    import readiness_check  # noqa: E402
    with gc.Garmin() as g:
        acts = [x for x in gc.list_activities(g, today - timedelta(days=60), today) if x["date"] <= today]
        rows, _ = readiness_check.build_rows(g, today - timedelta(days=10), today)
    ready = None
    if a.assume_readiness:
        ready = {"verdict": a.assume_readiness, "flags": []}
    else:
        try:
            r = subprocess.run([sys.executable, "-X", "utf8", str(SKILLS / "rampwise-recovery" / "scripts" / "readiness_check.py"), "--json"], capture_output=True, text=True, encoding="utf-8", timeout=180)
            ready = json.loads(r.stdout)
        except Exception:
            ready = None
    inj = analysis.injury_flags(acts, rows, ath, today, ready)
    cmp = analysis.compare(acts, today)["rolling"]
    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    since = (today - date.fromisoformat(state["last_progress"])).days if state.get("last_progress") else None
    longest = {sp: max((x["min"] for x in acts if x["sport"] == sp and (today - x["date"]).days <= 30), default=0) for sp in ("run", "bike")}
    ctx = {"readiness": (ready or {}).get("verdict"), "injury_level": inj["level"], "flag_ids": {f["id"] for f in inj["flags"] if f["level"] != "info"},
           "adherence": al.adherence(plan["sessions"], acts, today), "week_change_pct": cmp["delta"]["endurance_minutes"]["pct"], "days_since_progress": since, "longest_min": longest}
    # Only the first day is decided on today's readiness. Later days are provisional: readiness cannot be known yet, so only persistent signals count
    # (an active injury, a pain check-in, a recent spike); the coach re-runs this every morning.
    persistent = {"injury_active", "pain_checkin", "run_spike"}
    pf = [f for f in inj["flags"] if f["id"] in persistent and f["level"] != "info"]
    ctx_later = {**ctx, "readiness": None, "flag_ids": {f["id"] for f in pf}, "injury_level": "RED" if any(f["level"] == "red" for f in pf) else "AMBER" if pf else "GREEN"}
    days = []
    for k in range(a.days):
        d = target + timedelta(days=k)
        for s in [x for x in plan["sessions"] if x["date"] == str(d)]:
            dec = al.decide(s, ctx if k == 0 else ctx_later)
            new = build_new(s, dec, ath, B, longest) if dec["decision"] not in ("keep",) and s["sport"] != "strength" else None
            if dec["decision"] == "progress" and new is None:
                dec = {**dec, "decision": "keep", "reasons": dec["reasons"] + ["no room to progress safely (already at the cap)"]}
            entry = {"provisional": k > 0, "date": str(d), "original": {"title": s["title"], "minutes": s["minutes"], "sport": s["sport"], "kind": s["kind"], "start": s["start"]}, "decision": dec["decision"], "factor": dec["factor"],
                     "reasons": dec["reasons"], "evidence": dec["evidence"]}
            if s["sport"] == "strength" and dec["decision"] != "keep":
                entry["strength_advice"] = {"rest": "skip it", "reduce": f"use the light version: about {int((dec['factor'] or 0.5) * 100)} % of the sets, lighter loads"}.get(dec["decision"], "skip it")
                entry["calendar"] = {"find": {"date": s["date"], "marker": "rampwise-plan", "legacy_marker": "garmin-coach-plan", "original_summary_contains": s["title"]},
                                     "update": {"description_prefix": f"ADAPTED ({dec['decision']}): " + "; ".join(dec["reasons"]) + f". {entry['strength_advice']}.\n\n", "notificationLevel": "NONE"}}
            elif new is not None:
                entry["new"] = {k2: v for k2, v in new.items() if k2 != "workout"}
                entry["calendar"] = calendar_update(s, new, dec, today)
                if a.write_fit and new.get("workout"):
                    import export_workouts as ew  # noqa: E402
                    out = ew.out_dir()
                    data = wk.encode_fit(new["workout"])
                    wk.decode_check(data)
                    fp = out / f"ADAPTED_{d}_{s['sport']}.fit"
                    fp.write_bytes(data)
                    entry["fit_file"] = str(fp)
            days.append(entry)
            if dec["decision"] == "progress" and new is not None and a.record:
                state["last_progress"] = str(today)
                STATE.write_text(json.dumps(state), encoding="utf-8")
    replan = {"readiness": (ctx["readiness"] or "unknown").lower(), "reset": "yes" if ctx["readiness"] == "RED" or inj["level"] == "RED" else "auto",
              "note": "run build_plan.py with these only if you want the whole coming week rebuilt, not just the next session"}
    out = {"today": str(today), "target": str(target), "plan_file": str(plan_path), "state": {"readiness": ctx["readiness"], "injury_watch": inj["level"], "flags": [f["id"] for f in inj["flags"]],
                                                                                       "adherence_14d": ctx["adherence"], "week_change_pct": ctx["week_change_pct"], "days_since_progress": since},
           "days": days, "questions_for_the_user": inj["questions"], "replan": replan,
           "note": "Apply calendar updates in the main session with update_event (never from a subagent). Nothing was written to the calendar by this script."}
    if a.json:
        print(json.dumps(out, indent=1, default=str))
        return
    s0 = out["state"]
    print(f"ADAPT {today} -> {target}: readiness {s0['readiness']}, injury watch {s0['injury_watch']}, adherence 14d {s0['adherence_14d']}, week change {s0['week_change_pct']}%")
    if not days:
        print("  no planned session on that date")
    for e in days:
        print(f"\n  {e['date']} {e['original']['title']} ({e['original']['minutes']} min) -> {e['decision'].upper()}" + ("  [provisional: re-checked each morning]" if e.get("provisional") else ""))
        for r in e["reasons"]:
            print(f"    why: {r}")
        if e.get("new"):
            print(f"    new: {e['new']['title']} ({e['new']['minutes']} min)")
        if e.get("strength_advice"):
            print(f"    strength: {e['strength_advice']}")
        if e.get("fit_file"):
            print(f"    watch file: {e['fit_file']}")
    if out["questions_for_the_user"]:
        print("\nASK THE USER:")
        for q in out["questions_for_the_user"]:
            print("  - " + q)


if __name__ == "__main__":
    main()
