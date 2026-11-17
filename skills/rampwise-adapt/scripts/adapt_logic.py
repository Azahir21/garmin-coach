"""Decision rules for adapting a planned session to today's state. Pure functions (no Garmin calls), so they can be tested offline.

Each rule is labelled research or practice in ../references/evidence-map.md. The default direction is conservative: when the signals say "not today",
the session gets easier or shorter; progression is small, rare and only when everything is green. The user can always override.
"""
from datetime import timedelta

FACTORS = {"reduce": 0.7, "easy_swap": 0.9}      # practice
PROGRESS_MIN_ADHERENCE = 0.85                    # practice: only add load for someone who is doing the plan
PROGRESS_MAX_WEEK_CHANGE_PCT = 10.0              # practice: do not stack progressions on a week that already went up
PROGRESS_EVERY_DAYS = 7                          # practice: at most one progression a week
LONG_CAP = 1.10                                  # research: Frandsen 2025 (+10 % over the longest run of the last 30 days); applied to rides as an extrapolation


def classify(s):
    """Session category from the plan session (workout name first, then kind)."""
    name = (s.get("workout") or {}).get("name", "") if isinstance(s.get("workout"), dict) else ""
    n = (name or s.get("title", "")).lower()
    if s["sport"] == "strength":
        return {"cat": "strength", "q": None}
    if s.get("phase") == "RACE" or s.get("kind") == "race":
        return {"cat": "race", "q": None}
    if s.get("kind") == "brick_run":
        return {"cat": "brick", "q": None}
    if "blocks" in s:                                   # a session from an event plan (event_plan.py)
        if s.get("quality"):
            return {"cat": "quality", "q": "event"}
        if str(s.get("kind", "")).endswith("_long"):
            return {"cat": "long", "q": None}
        return {"cat": "easy", "q": None}
    for key, q in (("tempo", "tempo"), ("intervals", "intervals"), ("strides", "strides"), ("time trial", "tt")):
        if key in n:
            return {"cat": "quality", "q": q}
    if "maf" in n:
        return {"cat": "test", "q": None}
    if "climb" in n:
        return {"cat": "climb", "q": None}
    if s.get("kind") in ("runL", "rideL") or n.startswith("long"):
        return {"cat": "long", "q": None}
    return {"cat": "easy", "q": None}


def adherence(plan_sessions, acts, today, days=14):
    """Share of planned run/bike/strength sessions in the last `days` days that were done (same sport, same day, at least half the planned minutes)."""
    start = today - timedelta(days=days)
    planned = [s for s in plan_sessions if start <= _d(s["date"]) < today and s["sport"] in ("run", "bike", "swim", "strength")]
    if len(planned) < 3:
        return None
    done = 0
    for s in planned:
        got = sum(a["min"] for a in acts if str(a["date"]) == s["date"] and a["sport"] == s["sport"])
        if got >= 0.5 * s["minutes"]:
            done += 1
    return round(done / len(planned), 2)


def _d(x):
    from datetime import date
    return date.fromisoformat(x)


def decide(s, ctx):
    """Decision for one planned session.

    ctx: readiness ('GREEN'|'AMBER'|'RED'|None), injury_level ('GREEN'|'AMBER'|'RED'), flag_ids (set), adherence (0-1 or None), week_change_pct (or None),
    days_since_progress (int or None), longest_min (dict sport -> minutes in the last 30 days).
    Returns {"decision": keep|progress|easy_swap|reduce|recovery|rest, "reasons": [...], "evidence": [...], "factor": float|None, "progress": {...}|None}.
    """
    c = classify(s)
    if c["cat"] == "race":
        return {"decision": "keep", "reasons": ["race day: not changed (if you are ill or hurt, see a clinician and decide for yourself)"], "evidence": ["practice"], "factor": None, "progress": None, "category": c}
    ready, inj, ids = ctx.get("readiness"), ctx.get("injury_level", "GREEN"), ctx.get("flag_ids", set())
    reasons, evidence = [], []
    out = {"decision": "keep", "reasons": reasons, "evidence": evidence, "factor": None, "progress": None, "category": c}

    pain_red = "pain_checkin" in ids and inj == "RED" or "injury_active" in ids
    if pain_red:
        reasons.append("a pain check-in or an active injury note says stop: " + ("; ".join(sorted(i for i in ids if i in ("pain_checkin", "injury_active")))))
        evidence.append("practice: pain that changes how you move is a stop sign (the pain-monitoring idea comes from a small Achilles rehab trial, Silbernagel 2007)")
        out["decision"] = "rest"
        return out
    if c["cat"] == "brick":
        if ready in ("RED", "AMBER") or inj in ("RED", "AMBER"):
            reasons.append("brick run dropped: running straight after cycling costs more energy and its training benefit is unproven, so it goes first when recovery or the injury watch is not green")
            evidence.append("research for the cost of run-after-bike, gap for the benefit (Walsh 2019 full text; Millet and Vleck 2000 abstract)")
            out["decision"] = "rest"
        return out
    if c["cat"] == "strength":
        if ready == "RED" or inj == "RED" or "short_sleep" in ids:
            reasons.append("recovery is low: half the sets, or skip")
            evidence.append("practice: the sleep-loss meta-analysis (Craven 2022) found afternoon and evening performance hurt most")
            out["decision"] = "reduce"
            out["factor"] = 0.5
        elif ready == "AMBER" or inj == "AMBER":
            reasons.append("amber signals: keep the legs light, no heavy lower-body work")
            out["decision"] = "reduce"
            out["factor"] = 0.7
        return out
    if ready == "RED":
        reasons.append("readiness is RED")
        evidence.append("practice: the plan's standing rule is rest or a 20-30 min easy spin on a RED morning (signals: Buchheit 2014, Craven 2022)")
        out["decision"] = "recovery" if c["cat"] in ("easy", "long", "climb", "test") and inj != "RED" else "rest" if inj == "RED" else "recovery"
        return out
    if inj == "RED":
        reasons.append("injury-risk watch is RED (" + ", ".join(sorted(ids)) + ")")
        evidence.append("research/practice mix: see the injury-watch flags (Frandsen 2025 for spikes; the colours are practice)")
        out["decision"] = "reduce"
        out["factor"] = FACTORS["reduce"]
        return out
    if ready == "AMBER" or inj == "AMBER":
        why = []
        if ready == "AMBER":
            why.append("readiness is AMBER")
        if inj == "AMBER":
            why.append("injury-risk watch is AMBER (" + ", ".join(sorted(ids)) + ")")
        reasons.append("; ".join(why))
        evidence.append("practice: amber means no quality session; easy volume continues")
        if c["cat"] in ("quality", "climb", "test"):
            out["decision"] = "easy_swap"
            out["factor"] = FACTORS["easy_swap"]
        elif c["cat"] == "long":
            out["decision"] = "reduce"
            out["factor"] = 0.85
        return out
    # all green: maybe a small progression
    ad, wk, ds = ctx.get("adherence"), ctx.get("week_change_pct"), ctx.get("days_since_progress")
    ok = (not ctx.get("no_progress") and ready == "GREEN" and inj == "GREEN" and ad is not None and ad >= PROGRESS_MIN_ADHERENCE and (wk is None or wk <= PROGRESS_MAX_WEEK_CHANGE_PCT)
          and (ds is None or ds >= PROGRESS_EVERY_DAYS) and s.get("week_tag") == "BUILD")
    if ok and c["cat"] in ("quality", "long", "easy"):
        out["decision"] = "progress"
        reasons.append(f"all green, {ad * 100:.0f} % of the last two weeks done, week change {wk if wk is not None else 0:+.0f} %: a small step up")
        evidence.append("practice: small, rare steps; long sessions are capped at +10 % over the recent longest (Frandsen 2025)")
        out["progress"] = {"category": c["cat"], "q": c["q"]}
    elif c["cat"] in ("quality", "long", "easy") and s.get("week_tag") == "BUILD":
        why = []
        if ready != "GREEN":
            why.append("readiness not confirmed green")
        if ad is None:
            why.append("not enough plan history to judge adherence")
        elif ad < PROGRESS_MIN_ADHERENCE:
            why.append(f"only {ad * 100:.0f} % of recent sessions done")
        if wk is not None and wk > PROGRESS_MAX_WEEK_CHANGE_PCT:
            why.append(f"this week is already up {wk:.0f} %")
        if ds is not None and ds < PROGRESS_EVERY_DAYS:
            why.append("a progression was made less than a week ago")
        if why:
            reasons.append("keep as planned (no progression: " + "; ".join(why) + ")")
    return out
