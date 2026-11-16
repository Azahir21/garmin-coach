#!/usr/bin/env python3
"""Hold check: how long can the athlete hold a pace while heart rate stays under the easy ceiling?

For each run (or ride) it reads the second-by-second FIT data and reports, using only continuous running
(no walking, no stops; walking found from cadence as in garmin-planner/scripts/run_gate.py):

  steady stretch  longest stretch within +/-10 % of the session's most common pace (minutes)
  HOLD            longest stretch at that pace with HR (30 s average) at or under the ceiling (minutes)
  to-ceiling      minutes until HR first stays above the ceiling for 60 s (counted after minute 10), or "not crossed"
  drift           HR rise per 10 min inside the steady stretch (least squares, first 5 min of it skipped)
  speed@band      mean speed while HR is inside the band [ceiling - 15, ceiling] on flat ground (after minute 10)

Then a within-athlete trend (only with >= 4 usable sessions) that compares the change with the session-to-session
variation (typical error) before calling it real. Nothing here is a published cut-off:
  * The ceiling comes from athlete.json (watch zones, method unconfirmed). Percent-of-max zones are weak anchors (Jamnick 2020).
  * "Speed at a given HR" as a monitoring signal is supported for standardised tests (Vesterinen 2016/2017, Buchheit 2014);
    this free-form version is practice. A lower HR at the same pace is not always fitter (Ten Haaf 2019): read with sleep, HRV, load.
  * Heat raises HR at the same pace (Lafrenz 2008): compare sessions at similar temperature (use --weather-approved).

  hold_check.py [--sport run|bike] [--days 42] [--ceiling N] [--weather-approved] [--json]
"""
import argparse
import json
import statistics
import sys
from collections import deque
from datetime import date, timedelta
from pathlib import Path

SKILLS = Path(__file__).resolve().parent.parent.parent
DATA_DIR = Path(__import__("os").environ.get("GARMIN_COACH_DATA") or Path.home() / "garmin-coach-data")   # personal data lives OUTSIDE the plugin folder, so updates never touch it
ATHLETE_JSON = DATA_DIR / "athlete.json"
sys.path.insert(0, str(SKILLS / "garmin-coach" / "scripts"))
sys.path.insert(0, str(SKILLS / "garmin-planner" / "scripts"))
sys.path.insert(0, str(SKILLS / "garmin-heat-weather" / "scripts"))
import gcommon as gc  # noqa: E402
import run_gate  # noqa: E402

SMOOTH_S = 30          # HR and speed smoothing window (trailing)
PACE_TOL = 0.10        # "same pace" = within +/-10 % of the session's most common pace (practice)
BAND_WIDTH = 15        # bpm below the ceiling that count as "at the easy HR" for speed@band (practice)
SKIP_S = 600           # ignore the first 10 min for crossing / band measures: HR is still rising (practice; Buchheit 2014: >= 3-4 min to steady state)
CROSS_S = 60           # HR must stay above the ceiling this long to count as a crossing
GAP_OK_S = 20          # a brief break inside a stretch is merged
MIN_BAND_S = 900       # speed@band needs 15 min of data
MIN_DRIFT_S = 900      # drift slope needs a 15-min steady stretch
FLAT_GRADE = 0.02      # |grade| <= 2 % counts as flat for speed@band (practice)
MIN_TREND = 4


def trailing_mean(vals, w):
    out, q, s, n = [], deque(), 0.0, 0
    for v in vals:
        q.append(v)
        if v is not None:
            s += v; n += 1
        if len(q) > w:
            o = q.popleft()
            if o is not None:
                s -= o; n -= 1
        out.append(s / n if n >= max(5, w // 3) else None)
    return out


def grade_series(recs, half=30):
    """Slope over +/-half seconds from altitude and distance; None when unavailable."""
    n, out = len(recs), []
    for i in range(n):
        a, b = max(0, i - half), min(n - 1, i + half)
        al0, al1, d0, d1 = recs[a].get("alt"), recs[b].get("alt"), recs[a].get("dist"), recs[b].get("dist")
        if None in (al0, al1, d0, d1) or d1 - d0 < 20:
            out.append(None)
        else:
            out.append((al1 - al0) / (d1 - d0))
    return out


def runs_of(flags):
    """[(start_idx, end_idx_inclusive)] of consecutive True."""
    out, i, n = [], 0, len(flags)
    while i < n:
        if flags[i]:
            j = i
            while j < n and flags[j]:
                j += 1
            out.append((i, j - 1)); i = j
        else:
            i += 1
    return out


def merge(runs, recs, gap):
    if not runs:
        return []
    m = [list(runs[0])]
    for a, b in runs[1:]:
        if recs[a]["t"] - recs[m[-1][1]]["t"] - 1 <= gap:
            m[-1][1] = b
        else:
            m.append([a, b])
    return [tuple(x) for x in m]


def longest(runs, recs):
    best = None
    for a, b in runs:
        d = recs[b]["t"] - recs[a]["t"] + 1
        if best is None or d > best[0]:
            best = (d, a, b)
    return best


def analyze(recs, sport, ceiling, crit):
    n = len(recs)
    if sport == "run":
        lab = run_gate.classify(recs, crit["walk_cadence_spm_below"], crit["min_walk_segment_s"])
        moving = [x == "jog" for x in lab]
        walk_s = sum(d for _, d in run_gate.segments(recs, lab, "walk"))
    else:
        moving = [(r.get("speed") or 0) >= 1.5 for r in recs]
        walk_s = 0
    sp = trailing_mean([r.get("speed") for r in recs], SMOOTH_S)
    hr = trailing_mean([r.get("hr") for r in recs], SMOOTH_S)
    gr = grade_series(recs)
    total_s = recs[-1]["t"] - recs[0]["t"] + 1
    mov_idx = [i for i in range(n) if moving[i] and sp[i] is not None]
    if len(mov_idx) < 600:
        return {"error": "less than 10 min of continuous moving data"}
    # most common speed (0.5 km/h bins) among moving seconds after the skip
    bins = {}
    for i in mov_idx:
        if recs[i]["t"] >= SKIP_S:
            k = round(sp[i] * 3.6 * 2) / 2.0
            bins[k] = bins.get(k, 0) + 1
    if not bins:
        return {"error": "session shorter than the 10-min skip"}
    ref_kmh = max(bins, key=bins.get)
    ref = ref_kmh / 3.6
    near = [moving[i] and sp[i] is not None and abs(sp[i] - ref) <= PACE_TOL * ref for i in range(n)]
    steady_runs = merge(runs_of(near), recs, GAP_OK_S)
    st = longest(steady_runs, recs)
    ok = [near[i] and hr[i] is not None and hr[i] <= ceiling for i in range(n)]
    hold_runs = merge(runs_of(ok), recs, GAP_OK_S)
    hd = longest(hold_runs, recs)
    # first sustained crossing after the skip, while moving at the common pace
    cross_t = None
    streak = 0
    for i in range(n):
        if recs[i]["t"] < SKIP_S or not near[i] or hr[i] is None:   # only counts while moving at the common pace
            streak = 0
            continue
        streak = streak + 1 if hr[i] > ceiling else 0
        if streak >= CROSS_S:
            cross_t = recs[i - CROSS_S + 1]["t"] / 60.0
            break
    # drift slope inside the longest steady stretch (skip its first 5 min)
    slope = None
    if st and st[0] >= MIN_DRIFT_S:
        a, b = st[1], st[2]
        pts = [(recs[i]["t"] / 60.0, hr[i]) for i in range(a, b + 1)
               if hr[i] is not None and recs[i]["t"] - recs[a]["t"] >= 300 and recs[i]["t"] >= SKIP_S and near[i]]
        if len(pts) >= 600:          # at least 10 min of steady data after the warm-up rise
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            mx, my = statistics.mean(xs), statistics.mean(ys)
            den = sum((x - mx) ** 2 for x in xs)
            if den > 0:
                slope = 10.0 * sum((x - mx) * (y - my) for x, y in pts) / den
    # speed at the easy HR band, flat ground, after the skip
    lo = ceiling - BAND_WIDTH
    band = [i for i in mov_idx if recs[i]["t"] >= SKIP_S and hr[i] is not None and lo <= hr[i] <= ceiling
            and gr[i] is not None and abs(gr[i]) <= FLAT_GRADE]
    band_s = len(band)
    band_kmh = round(statistics.mean(sp[i] for i in band) * 3.6, 2) if band_s >= MIN_BAND_S else None
    mov_s = len(mov_idx)
    return {
        "total_min": round(total_s / 60, 1), "moving_min": round(mov_s / 60, 1), "walk_s": int(walk_s),
        "ref_kmh": ref_kmh, "steady_min": round(st[0] / 60, 1) if st else 0.0,
        "hold_min": round(hd[0] / 60, 1) if hd else 0.0,
        "hold_share_of_steady": round(100.0 * hd[0] / st[0]) if (hd and st and st[0] > 0) else None,
        "to_ceiling_min": round(cross_t, 1) if cross_t is not None else None,
        "crossed": cross_t is not None, "drift_bpm_per_10min": round(slope, 1) if slope is not None else None,
        "band_min": round(band_s / 60, 1), "band_kmh": band_kmh,
        "avg_hr_moving": round(statistics.mean(r["hr"] for r in (recs[i] for i in mov_idx) if r.get("hr"))) if any(recs[i].get("hr") for i in mov_idx) else None,
    }


def pace_str(kmh):
    if not kmh:
        return "n/a"
    p = 60.0 / kmh
    return f"{int(p)}:{int(round((p % 1) * 60)):02d}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sport", choices=["run", "bike"], default="run")
    ap.add_argument("--days", type=int, default=42)
    ap.add_argument("--ceiling", type=int, default=None)
    ap.add_argument("--weather-approved", action="store_true", help="look up observed air temperature (sends rounded start coordinates and dates to open-meteo.com)")
    ap.add_argument("--bike", default="all", help="rides only: a bike name from athlete.json bike_log, or all (default)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    gc.utf8_stdout()
    ath = json.loads((ATHLETE_JSON).read_text(encoding="utf-8"))
    ceiling = a.ceiling or (ath["hr"]["run_easy_max"] if a.sport == "run" else ath["hr"]["bike_easy_max"])
    crit = (gc.goal_by(ath, "run-gate", "criteria") or {}).get("criteria") or {"min_session_minutes": 45, "max_walk_seconds": 0, "walk_cadence_spm_below": 125, "min_walk_segment_s": 15}
    observed = None
    if a.weather_approved:
        import observed  # noqa: F811
    end = date.today()
    rows = []
    with gc.Garmin() as g:
        acts = [r for r in gc.list_activities(g, end - timedelta(days=a.days), end) if r["sport"] == a.sport and r["min"] >= 20 and (a.sport != "bike" or gc.bike_ok(r["id"], a.bike))]
        for r in sorted(acts, key=lambda x: x["start"]):
            try:
                recs = gc.read_fit(gc.fit_zip(g, r["id"]))
                if len(recs) < 600:
                    continue
                res = analyze(recs, a.sport, ceiling, crit)
            except Exception as e:
                res = {"error": str(e)}
            res.update({"id": r["id"], "date": str(r["date"]), "gain_per_km": round(r["gain_m"] / r["km"], 1) if r["km"] else None})
            if observed and r.get("lat") and r.get("lon") and "error" not in res:
                c = observed.conditions(r["lat"], r["lon"], r["start"], r["min"])
                res["temp_c"] = c.get("temp_c")
            rows.append(res)
    good = [x for x in rows if "error" not in x]
    usable = [x for x in good if x["band_kmh"] is not None and (x["gain_per_km"] or 0) <= 10]
    noise = None
    trend = None
    if len(usable) >= 2:
        v = [x["band_kmh"] for x in usable]
        noise = round(100 * statistics.pstdev(v) / statistics.mean(v), 1)
    if len(usable) >= MIN_TREND:
        v = [x["band_kmh"] for x in usable]
        early, late = statistics.mean(v[:-3]), statistics.mean(v[-3:])
        change = 100 * (late / early - 1)
        trend = {"early_kmh": round(early, 2), "late_kmh": round(late, 2), "change_pct": round(change, 1),
                 "beyond_noise": abs(change) > (noise or 0)}
    out = {"sport": a.sport, "ceiling": ceiling, "band": [ceiling - BAND_WIDTH, ceiling], "sessions": rows,
           "usable_for_trend": len(usable), "noise_cv_pct": noise, "trend": trend}
    if a.json:
        print(json.dumps(out, indent=1, default=str)); return
    unit = "pace/km" if a.sport == "run" else "km/h"
    print(f"HOLD CHECK ({a.sport}, last {a.days} days): easy HR ceiling {ceiling} bpm (athlete.json), band {ceiling - BAND_WIDTH}-{ceiling}. "
          f"Only continuous {'running (no walking)' if a.sport == 'run' else 'riding'} counts; first 10 min skipped for crossing and band numbers.")
    hdr = f"{'date':10} {'min':>4} {'common':>7} {'steady':>7} {'HOLD':>6} {'to ceiling':>10} {'drift/10m':>9} {'speed@band':>14} {'walk s':>6}" + ("  temp" if observed else "")
    print(hdr)
    for x in rows:
        if "error" in x:
            print(f"{x['date']:10} skipped: {x['error']}"); continue
        com = ("~" + pace_str(x["ref_kmh"])) if a.sport == "run" else f"~{x['ref_kmh']:.1f}"
        sb = (f"{pace_str(x['band_kmh'])}" if a.sport == "run" else f"{x['band_kmh']:.1f}") + f" ({x['band_min']:.0f}m)" if x["band_kmh"] else f"<15 min ({x['band_min']:.0f}m)"
        tc = f"{x['to_ceiling_min']:.0f} min" if x["crossed"] else "not crossed"
        dr = f"{x['drift_bpm_per_10min']:+.1f}" if x["drift_bpm_per_10min"] is not None else "n/a"
        tmp = f"  {x.get('temp_c')}C" if observed else ""
        print(f"{x['date']:10} {x['total_min']:4.0f} {com:>7} {x['steady_min']:6.0f}m {x['hold_min']:5.0f}m {tc:>10} {dr:>9} {sb:>14} {x['walk_s']:6d}{tmp}")
    print(f"\n(common = most frequent {unit}; steady = longest stretch within +/-10 % of it; HOLD = longest steady stretch with HR <= {ceiling}.)")
    best = max(good, key=lambda x: x["hold_min"], default=None)
    if best:
        print(f"Best hold: {best['hold_min']:.0f} min at {pace_str(best['ref_kmh']) if a.sport == 'run' else format(best['ref_kmh'], '.1f')} ({best['date']}).")
    if a.sport == "run" and good:
        walked = sum(1 for x in good if x["walk_s"] >= 120)
        hr_cut = sum(1 for x in good if x["steady_min"] - x["hold_min"] >= 2 and x["steady_min"] >= 10)
        print(f"What limits the runs: walking of 2+ min in {walked} of {len(good)} sessions (breaks the steady stretch); "
              f"HR above {ceiling} cut a steady stretch short by 2+ min in {hr_cut} of {len(good)}.")
    if a.sport == "bike":
        print("Ride note: speed on rides swings with traffic, wind and terrain, so steady stretches are short and HOLD / to-ceiling are weak here; "
              "speed@band on flat ground is the more useful column. The default bike ceiling may sit above your usual ride HR: pass --ceiling to match your easy HR.")
    print("\nTREND (within-athlete; practice, not a validated score):")
    if trend is None:
        print(f"  Not readable yet: {len(usable)} usable session(s) (need {MIN_TREND}: 15+ min at the easy HR on flat ground, no heavy climbing). "
              "Do repeat easy sessions on the same flat route.")
    else:
        u = "km/h"
        print(f"  speed@band earlier {trend['early_kmh']} {u} vs latest 3 {trend['late_kmh']} {u}: {trend['change_pct']:+.1f} % "
              f"(session-to-session variation {noise} %). "
              + (f"Larger than the variation, but with only {len(usable)} sessions and uncontrolled temperature treat it as a hint, not proof."
                 if trend["beyond_noise"] else "Within the variation: not a real change yet."))
    if noise is not None and trend is None:
        print(f"  Session-to-session variation so far: {noise} % (the change must exceed this to mean anything).")
    print("Cautions: lower HR at the same pace is not always fitter (Ten Haaf 2019): check sleep/HRV and load. Heat raises HR (Lafrenz 2008): "
          + ("temperature shown." if observed else "temperature NOT controlled (weather lookup not approved)."))


if __name__ == "__main__":
    main()
