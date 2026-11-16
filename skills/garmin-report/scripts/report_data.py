"""Data shaping for the reports. Pure functions: activity rows, readiness rows and the athlete file in, plain numbers out (testable without a Garmin account)."""
import sys
from datetime import date, timedelta
from pathlib import Path
from statistics import mean

HERE = Path(__file__).resolve().parent
SKILLS = HERE.parent.parent
sys.path.insert(0, str(SKILLS / "garmin-analyze" / "scripts"))
import analysis  # noqa: E402

SPORT_LABEL = {"run": "Run", "bike": "Ride", "strength": "Strength"}


def pace_s(speed_kmh):
    return 3600.0 / speed_kmh if speed_kmh else None


def mmss(sec):
    if sec is None:
        return "-"
    return f"{int(sec // 60)}:{int(sec % 60):02d}"


def day_list(end, n):
    return [end - timedelta(days=n - 1 - i) for i in range(n)]


def daily_minutes(acts, days):
    out = {s: [0.0] * len(days) for s in ("run", "bike", "strength")}
    idx = {d: i for i, d in enumerate(days)}
    for a in acts:
        if a["date"] in idx and a["sport"] in out:
            out[a["sport"]][idx[a["date"]]] += a["min"]
    return {k: [round(v) for v in vs] for k, vs in out.items()}


def week_starts(today, n):
    ws = analysis.week_start(today)
    return [ws - timedelta(weeks=n - 1 - i) for i in range(n)]


def weekly_series(acts, rows, today, n):
    """Per calendar week (oldest first, the current week is partial): minutes, km, sessions per sport, longest run and ride, average speed, run efficiency, recovery means."""
    starts = week_starts(today, n)
    out = {"labels": [], "week_start": [str(s) for s in starts], "partial_last": True}
    keys = ("run_min", "bike_min", "strength_sessions", "run_km", "bike_km", "longest_run_km", "longest_ride_km", "run_speed", "bike_speed", "run_hr", "bike_hr", "run_ef", "hrv", "rhr", "sleep_h", "training_days", "hard")
    for k in keys:
        out[k] = []
    for s in starts:
        e = min(s + timedelta(days=6), today)
        xs = [a for a in acts if s <= a["date"] <= e]
        ag = analysis.aggregate(xs)
        out["labels"].append(f"{s.day} {analysis.__dict__.get('MONTHS', ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'])[s.month - 1]}")
        out["run_min"].append(ag["run"]["minutes"])
        out["bike_min"].append(ag["bike"]["minutes"])
        out["strength_sessions"].append(ag["strength"]["sessions"])
        out["run_km"].append(ag["run"]["km"])
        out["bike_km"].append(ag["bike"]["km"])
        out["longest_run_km"].append(ag["run"]["longest_km"] or None)
        out["longest_ride_km"].append(ag["bike"]["longest_km"] or None)
        out["run_speed"].append(ag["run"]["avg_speed_kmh"])
        out["bike_speed"].append(ag["bike"]["avg_speed_kmh"])
        out["run_hr"].append(ag["run"]["avg_hr"])
        out["bike_hr"].append(ag["bike"]["avg_hr"])
        efs = []
        for a in xs:
            mov = a.get("moving_min") or a["min"]
            if a["sport"] == "run" and a["min"] >= 25 and a["km"] > 0 and a.get("avg_hr") and mov > 0:
                efs.append((a["km"] * 1000.0 / mov) / a["avg_hr"])
        out["run_ef"].append(round(mean(efs), 3) if efs else None)
        rm = analysis.recovery_means(rows, s, e)
        out["hrv"].append(rm["hrv"])
        out["rhr"].append(rm["rhr"])
        out["sleep_h"].append(rm["sleep_h"])
        out["training_days"].append(ag["training_days"])
        out["hard"].append(sum(ag[sp]["hard_sessions"] for sp in ("run", "bike")))
    return out


def recovery_daily(rows, days):
    by = {r["date"]: r for r in rows}
    return {k: [(by.get(str(d)) or {}).get(k) for d in days] for k in ("hrv", "rhr", "sleep_h")}


def plan_vs_done(plan, acts, days):
    """Planned and done minutes per day (run + ride + strength) for the given days."""
    pl = {str(d): 0 for d in days}
    for s in (plan or {}).get("sessions", []):
        if s["date"] in pl and s["sport"] in ("run", "bike", "strength"):
            pl[s["date"]] += s["minutes"]
    dn = {str(d): 0 for d in days}
    for a in acts:
        if str(a["date"]) in dn and a["sport"] in ("run", "bike", "strength"):
            dn[str(a["date"])] += a["min"]
    return [pl[str(d)] for d in days], [round(dn[str(d)]) for d in days]


# ---------------------------------------------------------------- goals
def _first_and_best(vals, better):
    vals = [v for v in vals if v is not None]
    if not vals:
        return None, None
    return vals[0], (max(vals) if better == "higher" else min(vals))


def goal_progress(athlete, acts, today, period_days=84):
    """One meter per goal the user has set and the data can measure. Baseline = the goal's own recorded baseline, else the first reading in the period;
    now = the best reading of the last 28 days. A distance to the goal, never a forecast."""
    out = []
    start = today - timedelta(days=period_days)
    recent = today - timedelta(days=28)
    bike_log = athlete.get("bike_log") or {}
    for g in athlete.get("goals", []):
        if g.get("done"):
            continue
        if g.get("target_speed_kmh"):
            flat = g.get("flat_max_m_per_km", 8.0)
            long_km = g.get("long_ride_km") or 0.5 * (g.get("target_distance_km") or 100)
            rides = [a for a in acts if a["sport"] == "bike" and start <= a["date"] and a["km"] >= long_km and (a["gain_m"] / a["km"] if a["km"] else 99) <= flat and (a.get("moving_min") or a["min"]) > 0]
            sp = [(a["date"], a["km"] / ((a.get("moving_min") or a["min"]) / 60.0)) for a in rides]
            first, _ = _first_and_best([v for _, v in sp], "higher")
            now = max([v for d, v in sp if d >= recent], default=None)
            base = (g.get("baseline") or {}).get("moving_kmh") or first
            out.append({"label": g["title"], "baseline": base, "now": now, "target": g["target_speed_kmh"], "better": "higher", "unit": "km/h",
                        "note": f"flat rides of {long_km:g} km or more", "n": len(sp)})
        elif g.get("target_pace_s_per_km"):
            runs = [(a["date"], (a.get("moving_min") or a["min"]) * 60.0 / a["km"]) for a in acts if a["sport"] == "run" and a["km"] >= 3 and start <= a["date"]]
            first, _ = _first_and_best([v for _, v in runs], "lower")
            now = min([v for d, v in runs if d >= recent], default=None)
            out.append({"label": g["title"], "baseline": first, "now": now, "target": g["target_pace_s_per_km"], "better": "lower", "unit": "pace",
                        "note": "best pace of a run of 3 km or more (not a race forecast)", "n": len(runs)})
        elif isinstance(g.get("track"), dict):
            t = g["track"]
            m, target = t.get("metric"), t.get("target")
            ws = weekly_series(acts, [], today, 12)
            if m == "weekly_minutes":
                series = [r + b for r, b in zip(ws["run_min"], ws["bike_min"])][:-1]
                base, now = (series[0] if series else None), (series[-1] if series else None)
            elif m == "long_run_km":
                v = [x for x in ws["longest_run_km"] if x]
                base, now = (v[0] if v else None), (max(v[-4:]) if v else None)
            elif m == "long_ride_km":
                v = [x for x in ws["longest_ride_km"] if x]
                base, now = (v[0] if v else None), (max(v[-4:]) if v else None)
            elif m == "training_days_per_week":
                v = ws["training_days"][:-1]
                base, now = (v[0] if v else None), (v[-1] if v else None)
            elif m == "strength_sessions_per_week":
                v = ws["strength_sessions"][:-1]
                base, now = (v[0] if v else None), (v[-1] if v else None)
            else:
                continue
            out.append({"label": g["title"], "baseline": base, "now": now, "target": target, "better": t.get("better", "higher"), "unit": t.get("unit", ""), "note": m.replace("_", " "), "n": 0})
    return out


# ---------------------------------------------------------------- strength
def strength_summary(hist, today, weeks=12):
    """Sessions per week and the top set per exercise (first vs latest) from the sets logged on the watch."""
    if not hist:
        return None
    starts = week_starts(today, weeks)
    per_week = [0] * weeks
    for s in hist:
        d = date.fromisoformat(s["date"])
        for i, ws in enumerate(starts):
            if ws <= d <= ws + timedelta(days=6):
                per_week[i] += 1
    tops = {}
    for s in sorted(hist, key=lambda x: x["date"]):
        for b in s["exercises"]:
            key = (b["key"][1] or b["key"][0])
            best = max((x for x in b["sets"] if x.get("reps")), key=lambda x: ((x.get("kg") or 0), x["reps"]), default=None)
            if best:
                tops.setdefault(key, []).append((s["date"], best.get("kg") or 0, best["reps"]))
    rows = []
    for k, v in tops.items():
        if len(v) >= 2:
            rows.append({"exercise": k.replace("_", " "), "sessions": len(v), "first": v[0], "latest": v[-1]})
    rows.sort(key=lambda r: -r["sessions"])
    return {"per_week": per_week, "labels": [f"{s.day}/{s.month}" for s in starts], "top_sets": rows[:8]}
