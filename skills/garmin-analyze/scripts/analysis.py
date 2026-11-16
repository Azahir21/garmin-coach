"""Shared analysis functions: week-over-week comparison and injury-risk flags. Pure functions (activity rows in, numbers out), so they can be tested without a Garmin account.

Activity rows are the dicts made by garmin-coach/scripts/gcommon.py `normalize` (date, start, sport, km, min, moving_min, avg_hr, gain_m, te_aerobic ...).
Readiness rows come from garmin-recovery/scripts/garmin_readiness.py `build_rows` (date, hrv, rhr, sleep_h).

Honesty: these are RISK FLAGS from data, not diagnoses. Watch data cannot see an injury. Every flag carries its evidence label (research / practice / gap)
and the rules are explained in ../references/evidence-map.md.
"""
from datetime import date, timedelta
from statistics import mean

SPORTS = ("run", "bike", "strength", "other")
# thresholds, each labelled (see references/evidence-map.md)
SPIKE_PCT = 10.0            # research: Frandsen 2025, single run vs longest run of the previous 30 days
SPIKE_RED_PCT = 100.0       # research: the largest hazard ratio was above +100 %; the colour mapping is practice
SPIKE_MIN_REF_KM = 3.0      # practice: ignore tiny bases
WEEK_JUMP_PCT = 20.0        # practice with mixed observational support (Nielsen 2014, Damsted 2019)
SMALL_BASE_MIN = 60         # practice: a change on a tiny base is not a signal
NO_REST_AMBER, NO_REST_RED = 7, 14      # practice
HARD_TE = 4.0               # Garmin's aerobic training effect, practice
SHORT_SLEEP_H = 6.0         # practice (limited evidence; see evidence map)
EFFICIENCY_DROP_PCT = 5.0   # practice
PAIN_AMBER, PAIN_RED = 3, 6 # practice thresholds on a 0-10 scale; gait change is always red


def week_start(d):
    return d - timedelta(days=d.weekday())


def _in(acts, start, end):
    return [a for a in acts if start <= a["date"] <= end]


def aggregate(acts):
    """Per-sport and total numbers for a list of activities."""
    out = {}
    for sport in SPORTS:
        xs = [a for a in acts if a["sport"] == sport]
        mins = sum(a["min"] for a in xs)
        mov = sum(a.get("moving_min") or a["min"] for a in xs)
        km = sum(a["km"] for a in xs)
        hr_xs = [a for a in xs if a.get("avg_hr")]
        hr = sum(a["avg_hr"] * a["min"] for a in hr_xs) / sum(a["min"] for a in hr_xs) if hr_xs else None
        speeds = [a["km"] / ((a.get("moving_min") or a["min"]) / 60.0) for a in xs if a["km"] > 0 and (a.get("moving_min") or a["min"]) > 0]
        out[sport] = {
            "sessions": len(xs), "minutes": round(mins), "km": round(km, 1), "gain_m": round(sum(a.get("gain_m") or 0 for a in xs)),
            "avg_hr": round(hr) if hr else None,
            "avg_speed_kmh": round(km / (mov / 60.0), 2) if km > 0 and mov > 0 else None,
            "longest_min": round(max((a["min"] for a in xs), default=0)), "longest_km": round(max((a["km"] for a in xs), default=0), 1),
            "hard_sessions": sum(1 for a in xs if (a.get("te_aerobic") or 0) >= HARD_TE),
            "days": len({a["date"] for a in xs}),
        }
    endur = [a for a in acts if a["sport"] in ("run", "bike")]
    out["endurance_minutes"] = round(sum(a["min"] for a in endur))
    out["training_days"] = len({a["date"] for a in acts if a["sport"] in ("run", "bike", "strength")})
    out["sessions"] = len([a for a in acts if a["sport"] in ("run", "bike", "strength")])
    return out


def _delta(now, before, min_base=0):
    if now is None or before is None:
        return {"abs": None, "pct": None}
    d = now - before
    pct = round(d / before * 100, 1) if before and before >= min_base else None
    return {"abs": round(d, 2), "pct": pct}


def compare(acts, today):
    """Rolling last 7 days vs the 7 days before, and the calendar week so far vs the same days last week and vs the last full week.
    Works on any day, whether or not there was an activity today."""
    r_this, r_prev = (today - timedelta(days=6), today), (today - timedelta(days=13), today - timedelta(days=7))
    ws = week_start(today)
    span = (today - ws).days
    c_this, c_same, c_full = (ws, today), (ws - timedelta(days=7), ws - timedelta(days=7) + timedelta(days=span)), (ws - timedelta(days=7), ws - timedelta(days=1))
    res = {"today": str(today)}
    for key, (a_rng, b_rng) in {"rolling": (r_this, r_prev), "calendar_same_days": (c_this, c_same), "calendar_vs_last_full_week": (c_this, c_full)}.items():
        A, B = aggregate(_in(acts, *a_rng)), aggregate(_in(acts, *b_rng))
        d = {}
        for sport in ("run", "bike", "strength"):
            d[sport] = {k: _delta(A[sport][k], B[sport][k], SMALL_BASE_MIN if k == "minutes" else 0) for k in ("sessions", "minutes", "km", "gain_m", "avg_hr", "avg_speed_kmh", "longest_min", "hard_sessions")}
        d["endurance_minutes"] = _delta(A["endurance_minutes"], B["endurance_minutes"], SMALL_BASE_MIN)
        d["training_days"] = _delta(A["training_days"], B["training_days"])
        res[key] = {"this": {"from": str(a_rng[0]), "to": str(a_rng[1]), **A}, "before": {"from": str(b_rng[0]), "to": str(b_rng[1]), **B}, "delta": d}
    return res


def recovery_means(rows, start, end):
    xs = [r for r in rows if str(start) <= r["date"] <= str(end)]
    out = {}
    for k in ("hrv", "rhr", "sleep_h"):
        v = [r[k] for r in xs if r.get(k) is not None]
        out[k] = round(mean(v), 1) if v else None
        out[k + "_n"] = len(v)
    return out


def pace_str(speed_kmh):
    if not speed_kmh:
        return "-"
    s = 3600.0 / speed_kmh
    return f"{int(s // 60)}:{int(s % 60):02d}/km"


def insights(cmp, units=None):
    """Plain sentences from a compare() result (rolling window). Numbers only; no advice."""
    units = units or {}
    d = cmp["rolling"]["delta"]
    A, B = cmp["rolling"]["this"], cmp["rolling"]["before"]
    out = []

    def phr(name, key="minutes", unit="min"):
        x = d[name][key]
        if x["abs"] is None or (A[name]["sessions"] == 0 and B[name]["sessions"] == 0):
            return None
        word = "up" if x["abs"] > 0 else "down" if x["abs"] < 0 else "unchanged"
        pct = f" ({x['pct']:+.0f} %)" if x["pct"] is not None else ""
        u = unit if A[name][key] != 1 or unit != "sessions" else "session"
        return f"{name} {key}: {A[name][key]} {u} vs {B[name][key]} before, {word}{pct}"

    for sport in ("run", "bike", "strength"):
        s = phr(sport, "minutes" if sport != "strength" else "sessions", "min" if sport != "strength" else "sessions")
        if s:
            out.append(s)
    for sport in ("run", "bike"):
        a, b = A[sport]["avg_speed_kmh"], B[sport]["avg_speed_kmh"]
        if a and b:
            if sport == "run" and units.get("run", "pace") == "pace":
                out.append(f"run average pace {pace_str(a)} vs {pace_str(b)} before (average HR {A[sport]['avg_hr']} vs {B[sport]['avg_hr']}); pace depends on the route, weather and the mix of easy and hard runs")
            else:
                out.append(f"{sport} average speed {a} km/h vs {b} km/h before (average HR {A[sport]['avg_hr']} vs {B[sport]['avg_hr']})")
    if A["sessions"] == 0:
        out.append("no sessions in the last 7 days")
    return out


# ---------------------------------------------------------------- injury-risk flags
def _flag(level, fid, text, evidence, action):
    return {"level": level, "id": fid, "text": text, "evidence": evidence, "action": action}


def consecutive_days(acts, today):
    days = {a["date"] for a in acts if a["sport"] in ("run", "bike", "strength")}
    d = today if today in days else today - timedelta(days=1)
    n = 0
    while d in days:
        n += 1
        d -= timedelta(days=1)
    return n


def run_efficiency(acts, today):
    """Speed per heartbeat of steady runs (>= 25 min): last 14 days vs the 28 days before. None if fewer than 3 runs in either window."""
    def ef(a):
        mov = a.get("moving_min") or a["min"]
        return (a["km"] * 1000.0 / mov) / a["avg_hr"] if a["km"] > 0 and mov > 0 and a.get("avg_hr") else None

    def window(lo, hi):
        v = [ef(a) for a in acts if a["sport"] == "run" and a["min"] >= 25 and lo <= (today - a["date"]).days <= hi]
        return [x for x in v if x]
    now, before = window(0, 13), window(14, 41)
    if len(now) < 3 or len(before) < 3:
        return None
    return {"now": round(mean(now), 3), "before": round(mean(before), 3), "change_pct": round((mean(now) / mean(before) - 1) * 100, 1), "runs_now": len(now), "runs_before": len(before)}


def injury_flags(acts, rows, athlete, today, readiness=None):
    """Risk flags from activity data, recovery rows, the user's injury list and recent pain check-ins. Returns {"level", "flags", "questions", "note"}."""
    flags = []
    # 1. single-run spike (research)
    for r in [a for a in acts if a["sport"] == "run" and 0 <= (today - a["date"]).days <= 7]:
        prev = [p["km"] for p in acts if p["sport"] == "run" and p is not r and 0 < (r["date"] - p["date"]).days <= 30 or (p["sport"] == "run" and p is not r and p["date"] == r["date"] and p["start"] < r["start"])]
        if not prev:
            continue
        ref = max(prev)
        over = (r["km"] / ref - 1) * 100 if ref else 0
        if ref >= SPIKE_MIN_REF_KM and over > SPIKE_PCT and r["km"] - ref > 0.3:
            lvl = "red" if over > SPIKE_RED_PCT else "amber"
            flags.append(_flag(lvl, "run_spike", f"The run on {r['date']} ({r['km']:.1f} km) was {over:.0f} % longer than your longest run in the 30 days before ({ref:.1f} km).",
                               "research: Frandsen 2025 (5,205 runners): injury rates were higher after a single run more than 10 % longer than the recent longest",
                               f"Keep the next long run at or under {ref * 1.1:.1f} km until it is the new normal; watch for new pain."))
    # 2. week-over-week jump (practice, mixed evidence)
    c = compare(acts, today)["rolling"]
    d = c["delta"]["endurance_minutes"]
    if d["pct"] is not None and d["pct"] >= WEEK_JUMP_PCT:
        flags.append(_flag("amber", "week_jump", f"Run + ride minutes in the last 7 days are up {d['pct']:.0f} % on the 7 days before ({c['this']['endurance_minutes']} vs {c['before']['endurance_minutes']} min).",
                           "practice with mixed observational support (Nielsen 2014, Damsted 2019); a graded 10 % rule did not prevent injuries in an RCT (Buist 2008)", "Hold this week's volume instead of adding more; a prompt to look closer, not a verdict."))
    # 3. rest days
    n = consecutive_days(acts, today)
    if n >= NO_REST_AMBER:
        flags.append(_flag("red" if n >= NO_REST_RED else "amber", "no_rest", f"{n} training days in a row without a rest day.", "practice: no study in the library", "Take a full rest day or a very easy day."))
    # 4. hard days back to back
    hard_days = sorted({a["date"] for a in acts if (a.get("te_aerobic") or 0) >= HARD_TE and 0 <= (today - a["date"]).days <= 7})
    if any((b - a).days == 1 for a, b in zip(hard_days, hard_days[1:])):
        flags.append(_flag("amber", "hard_back_to_back", "Two hard days (Garmin aerobic training effect 4.0 or more) in a row in the last 7 days.", "practice: Garmin's own scale, no study", "Space hard sessions with an easy day between."))
    # 5. recovery context
    ver = (readiness or {}).get("verdict")
    if ver in ("RED", "AMBER"):
        lvl = "red" if ver == "RED" and (d["pct"] or 0) >= 10 else "amber"
        flags.append(_flag(lvl, "recovery_low", f"Readiness is {ver}: " + "; ".join(f[1] if isinstance(f, (list, tuple)) else str(f) for f in (readiness.get("flags") or [])[:3]) + ".",
                           "research for the signals (Buchheit 2014 on HRV and heart rate; Craven 2022 on sleep and performance); linking them to injury is a gap", "Do not add load while recovery is low."))
    sl = [r["sleep_h"] for r in rows if r.get("sleep_h") and 0 <= (today - date.fromisoformat(r["date"])).days <= 2]
    if len(sl) >= 3 and mean(sl) < SHORT_SLEEP_H:
        flags.append(_flag("amber", "short_sleep", f"Average sleep over the last 3 nights is {mean(sl):.1f} h.", "limited research: in 340 adolescent elite athletes more than 8 h of sleep went with lower odds of injury (von Rosen 2017); adults: gap", "Protect sleep before adding load."))
    # 6. efficiency
    ef = run_efficiency(acts, today)
    if ef and ef["change_pct"] <= -EFFICIENCY_DROP_PCT:
        flags.append(_flag("amber", "efficiency_drop", f"Speed per heartbeat on steady runs is {abs(ef['change_pct']):.0f} % lower than in the 4 weeks before ({ef['runs_now']} vs {ef['runs_before']} runs).",
                           "practice: the concept is used for fatigue and fitness tracking; heat, hills, illness and wrist-HR error also move it", "Check sleep, heat and how the legs feel; this is a prompt, not a diagnosis."))
    # 7. the user's own injury list and pain check-ins (the strongest signal: the user's report)
    for inj in (athlete.get("injuries") or []):
        st = inj.get("status")
        if st == "active":
            flags.append(_flag("red", "injury_active", f"Active injury note: {inj.get('area')}" + (f" ({inj.get('note')})" if inj.get("note") else "") + (f". Restriction: {inj['restrict']}" if inj.get("restrict") else "") + ".",
                               "the user's own record", "Follow the restriction; if it does not settle, see a clinician."))
        elif st == "monitoring":
            flags.append(_flag("amber", "injury_monitoring", f"Injury being monitored: {inj.get('area')}.", "the user's own record", "Ask how it feels today before any hard session."))
        elif st == "resolved" and inj.get("resolved") and (today - date.fromisoformat(inj["resolved"])).days <= 60:
            flags.append(_flag("info", "injury_history", f"{inj.get('area')} was resolved on {inj['resolved']} (less than 60 days ago).",
                               "research: a history of previous injury was associated with a higher rate of injury in endurance sports (Johnston 2018, medium effect)", "Progress gradually in that area."))
    for ci in (athlete.get("checkins") or []):
        age = (today - date.fromisoformat(ci["date"])).days
        if 0 <= age <= 3:
            pain = ci.get("pain", 0) or 0
            if ci.get("gait_change") or pain >= PAIN_RED:
                flags.append(_flag("red", "pain_checkin", f"Pain check-in on {ci['date']}: {ci.get('area') or 'area not stated'}, {pain}/10" + (", changes how you move" if ci.get("gait_change") else "") + ".",
                                   "practice thresholds; pain that changes gait is a stop sign. The pain-monitoring idea comes from a small Achilles rehab trial (Silbernagel 2007)", "Rest or a pain-free alternative; see a clinician if it lasts more than a few days or gets worse."))
            elif pain >= PAIN_AMBER:
                flags.append(_flag("amber", "pain_checkin", f"Pain check-in on {ci['date']}: {ci.get('area') or 'area not stated'}, {pain}/10.", "practice thresholds", "Keep it easy and pain-free; re-check tomorrow."))
            elif pain > 0:
                flags.append(_flag("info", "pain_checkin", f"Minor niggle on {ci['date']}: {ci.get('area') or 'area not stated'}, {pain}/10.", "practice", "Monitor it."))
    order = {"red": 3, "amber": 2, "info": 1}
    level = "GREEN"
    if any(f["level"] == "red" for f in flags):
        level = "RED"
    elif any(f["level"] == "amber" for f in flags):
        level = "AMBER"
    flags.sort(key=lambda f: -order[f["level"]])
    has_today = any(ci["date"] == str(today) for ci in (athlete.get("checkins") or []))
    questions = []
    if not has_today:
        questions = ["Any new pain or niggle today? Where, how bad (0-10), and does it change how you walk or run?", "Is anything worse the morning after training than it was the day before?"]
    if level != "GREEN":
        questions.append("Any recent changes: new shoes or a new bike setup, a new surface, a hard event, illness, poor sleep or stress?")
    return {"level": level, "flags": flags, "questions": questions, "efficiency": ef,
            "note": "Risk flags from data and your own reports, not a diagnosis. Watch data cannot see an injury: pain that changes your gait, keeps rising or lasts more than a few days needs a clinician."}
