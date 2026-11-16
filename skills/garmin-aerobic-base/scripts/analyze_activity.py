#!/usr/bin/env python3
"""Aerobic analysis of ONE Garmin activity from its FIT file: efficiency factor, decoupling, HR drift,
durability, cadence fade (bike), time in HR zones, and whether the numbers can be trusted.

Usage:
  analyze_activity.py ACTIVITY_ID [--json] [--lthr N]

Method (formulas and thresholds adapted from tomasstankovic/running-coach `analyze_session.py`, MIT; the
FIT reading, moving-time handling and reliability checks are new):
  * moving time only (stops removed); the first 10 minutes of moving time are skipped (warm-up);
  * decoupling = percent drop of (speed or power) / HR from the first to the second half of the rest;
  * efficiency factor (EF) = speed in m/min (or watts) per heartbeat; compare only with your own similar sessions;
  * durability (90+ min only) = percent EF lost in the last quarter vs the early part (after warm-up);
  * cadence fade (bike, if cadence recorded) = mean cadence 2nd half minus 1st half.
Reliability: steady effort needed. The result is flagged when the session is short (< 60 min moving), unsteady
(high speed variation, walk/run or intervals), hilly (>= 10 m of climbing per km), or has no heart rate.
Thresholds (5 % / 10 % decoupling, 3 % / 6 % durability) are coaching conventions, not published cut-offs; use them
as a trend within YOUR data. Evidence notes: ../references/sources.md.
"""
import argparse
import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "garmin-coach" / "scripts"))

import gcommon  # noqa: E402

DECOUPLING_GOOD, DECOUPLING_HIGH = 5.0, 10.0      # % (Friel / TrainingPeaks convention: practice)
MIN_STEADY_MIN = 60                               # decoupling means little on shorter efforts
WARMUP_SKIP_S = 600
DURABILITY_MIN_S = 5400
DURABILITY_OK, DURABILITY_HIGH = 3.0, 6.0         # % EF lost late in the session (practice)
STEADY_CV_MAX = 0.25                              # speed variation (1-min smoothing) above this = not steady (working rule)
HILLY_M_PER_KM = 10.0
MIN_SPEED = {"run": 1.2, "bike": 1.0, "other": 1.0}   # m/s below which the athlete is stopped / walking


def moving_points(recs, sport, exclude=()):
    """(moving_time_s, speed, hr, power, cadence) with stops removed and time gaps capped at 10 s.
    exclude: (start, end) ranges in seconds (warm-up / cool-down / rest laps marked by the watch)."""
    pts, mt, prev_t = [], 0.0, None
    floor = MIN_SPEED.get(sport, 1.0)
    for r in recs:
        t = r["t"]
        dt = 0.0 if prev_t is None else min(t - prev_t, 10.0)
        prev_t = t
        sp, hr = r.get("speed"), r.get("hr")
        if sp is None or sp < floor or not hr:
            continue
        if any(a <= t < b for a, b in exclude):
            continue
        mt += dt
        pts.append((mt, sp, hr, r.get("power"), r.get("cadence")))
    return pts, mt


def mean(xs):
    xs = list(xs)
    return statistics.mean(xs) if xs else None


def halves(pts, use_power):
    """Decoupling between the two halves of the post-warm-up part."""
    if len(pts) < 60:
        return None
    mid = (pts[0][0] + pts[-1][0]) / 2
    a = [p for p in pts if p[0] < mid]
    b = [p for p in pts if p[0] >= mid]
    out_idx = 3 if use_power else 1
    ra = mean(p[out_idx] for p in a) / mean(p[2] for p in a)
    rb = mean(p[out_idx] for p in b) / mean(p[2] for p in b)
    return {"decoupling_pct": (ra - rb) / ra * 100.0, "hr_first": mean(p[2] for p in a), "hr_second": mean(p[2] for p in b),
            "out_first": mean(p[out_idx] for p in a), "out_second": mean(p[out_idx] for p in b),
            "cad_first": mean(p[4] for p in a if p[4]), "cad_second": mean(p[4] for p in b if p[4])}


def durability(pts, total_mt, use_power, skip=WARMUP_SKIP_S):
    if total_mt < DURABILITY_MIN_S or len(pts) < 120:
        return None
    end = pts[-1][0]
    early = [p for p in pts if skip <= p[0] <= skip + (end - skip) * 0.4]
    late = [p for p in pts if p[0] >= end * 0.75]
    if len(early) < 30 or len(late) < 30:
        return None
    idx = 3 if use_power else 1
    ef = lambda xs: mean(p[idx] for p in xs) / mean(p[2] for p in xs)
    return {"durability_ef_loss_pct": (ef(early) - ef(late)) / ef(early) * 100.0,
            "hr_early": mean(p[2] for p in early), "hr_late": mean(p[2] for p in late)}


def steadiness_cv(pts, window_s=60):
    """Coefficient of variation of 1-minute mean speeds (after warm-up)."""
    buckets, cur, t0 = [], [], pts[0][0]
    for p in pts:
        if p[0] - t0 >= window_s:
            buckets.append(mean(cur)); cur, t0 = [], p[0]
        cur.append(p[1])
    if len(buckets) < 5:
        return None
    m = statistics.mean(buckets)
    return statistics.pstdev(buckets) / m if m else None


def zone_minutes(pts, floors):
    """Minutes per Garmin HR zone (floors = [z1_floor, ..., z5_floor])."""
    out = [0.0] * 6                      # index 0 = below zone 1
    prev = None
    for p in pts:
        dt = 1.0 if prev is None else max(0.0, min(p[0] - prev, 10.0))
        prev = p[0]
        z = sum(1 for f in floors if p[2] >= f)
        out[z] += dt
    return [round(x / 60.0, 1) for x in out]


def pick_zones(zones_res, sport):
    rows = (zones_res or {}).get("results") or []
    want = {"run": "RUN", "bike": "CYCL"}.get(sport, "DEFAULT")
    row = next((r for r in rows if want in str(r.get("sport", "")).upper()), None) or \
        next((r for r in rows if "DEFAULT" in str(r.get("sport", "")).upper()), None) or (rows[0] if rows else None)
    if not row:
        return None
    floors = [row.get(f"zone{i}Floor") for i in range(1, 6)]
    if any(f is None for f in floors):
        return None
    return {"floors": floors, "max_hr": row.get("maxHeartRateUsed"), "lthr": row.get("lactateThresholdHeartRateUsed"),
            "sport": row.get("sport"), "method": row.get("trainingMethod")}


def analyze(g, activity_id, zones_res=None):
    s = gcommon.activity_summary(g, activity_id)
    recs, laps = gcommon.read_fit(gcommon.fit_zip(g, activity_id), with_laps=True)
    sport = s["sport"]
    # laps the watch marked as warm-up / cool-down / rest are not part of the steady effort
    exclude = [(l["start"], l["end"]) for l in laps if l["intensity"] in ("warmup", "cooldown", "rest", "recovery")]
    has_warmup = any(l["intensity"] == "warmup" for l in laps)
    n_rest = sum(1 for l in laps if l["intensity"] in ("rest", "recovery"))
    skip = 0.0 if has_warmup else WARMUP_SKIP_S
    pts_all, total_mt = moving_points(recs, sport, exclude)
    res = {"id": s["id"], "name": s["name"], "type": s["type"], "sport": sport, "start": str(s["start"]),
           "km": round(s["km"], 1), "elapsed_min": round(s["min"]), "moving_min": round(total_mt / 60.0),
           "gain_m_per_km": round(s["gain_m"] / s["km"], 1) if s["km"] else None, "avg_hr": s["avg_hr"],
           "warmup_cooldown_removed": bool(exclude)}
    flags = []
    if not pts_all or total_mt < skip + 900:
        res["error"] = "too little moving data with heart rate after the warm-up"
        return res
    pts = [p for p in pts_all if p[0] >= skip]
    if n_rest >= 2:
        flags.append(f"not steady (structured workout with {n_rest} rest laps: intervals): decoupling not meaningful")
    power_share = sum(1 for p in pts if p[3]) / len(pts)
    use_power = sport in ("run", "bike") and power_share > 0.8 and (mean(p[3] for p in pts if p[3]) or 0) > 20
    res["metric"] = "power:HR" if use_power else "speed:HR"
    idx = 3 if use_power else 1

    h = halves(pts, use_power)
    if h:
        res.update({k: round(v, 2) if isinstance(v, float) else v for k, v in h.items() if v is not None})
    ef_num = mean(p[idx] for p in pts)
    ef_den = mean(p[2] for p in pts)
    res["ef"] = round((ef_num if use_power else ef_num * 60.0) / ef_den, 3)          # m/min per beat, or W per beat
    res["ef_unit"] = "W/bpm" if use_power else "m/min/bpm"
    res["hr_drift_pct"] = round((h["hr_second"] - h["hr_first"]) / h["hr_first"] * 100.0, 1) if h else None

    d = durability(pts_all, total_mt, use_power, skip)
    if d:
        res.update({k: round(v, 2) for k, v in d.items()})
    if sport == "bike" and h and h.get("cad_first") and h.get("cad_second"):
        res["cadence_change_rpm"] = round(h["cad_second"] - h["cad_first"], 1)

    cv = steadiness_cv(pts)
    res["steadiness_cv"] = round(cv, 2) if cv is not None else None
    if total_mt / 60.0 < MIN_STEADY_MIN:
        flags.append(f"short ({total_mt / 60:.0f} min moving): read decoupling loosely")
    if cv is not None and cv > STEADY_CV_MAX:
        flags.append(f"not steady (speed variation {cv:.2f}; intervals or walk/run): decoupling not meaningful")
    if res["gain_m_per_km"] and res["gain_m_per_km"] >= HILLY_M_PER_KM:
        flags.append(f"hilly ({res['gain_m_per_km']:.0f} m/km): speed:HR is distorted; use HR and perceived effort")
    res["reliable"] = not any(f.startswith(("not steady", "short")) for f in flags) and "decoupling_pct" in res
    res["flags"] = flags
    # per-quarter picture (speed or power, and HR): shows terrain / pacing / stops at a glance
    n = len(pts)
    res["quarters"] = [{"speed_kmh": round(mean(p[1] for p in pts[i * n // 4:(i + 1) * n // 4]) * 3.6, 1),
                        "hr": round(mean(p[2] for p in pts[i * n // 4:(i + 1) * n // 4])),
                        "power": round(mean(p[3] for p in pts[i * n // 4:(i + 1) * n // 4] if p[3]) or 0) if use_power else None}
                       for i in range(4)] if n >= 80 else []

    z = pick_zones(zones_res, sport)
    if z:
        res["zones"] = {"sport": z["sport"], "floors": z["floors"], "lthr": z["lthr"], "max_hr": z["max_hr"],
                        "minutes_below_z1_z1_z2_z3_z4_z5": zone_minutes(pts_all, z["floors"])}
    if "decoupling_pct" in res:
        v = res["decoupling_pct"]
        if not res["reliable"]:
            res["decoupling_label"] = "NOT MEANINGFUL for this session (see notes): do not use as a fitness signal"
        elif v < 0:
            res["decoupling_label"] = "negative: more efficient in the 2nd half (pace change, cooling, or a slow start); treat as no drift"
        else:
            res["decoupling_label"] = ("under 5 %: small drift (convention: good)" if v < DECOUPLING_GOOD else
                                       "5-10 %: moderate drift" if v < DECOUPLING_HIGH else "over 10 %: large drift")
    if "durability_ef_loss_pct" in res:
        v = res["durability_ef_loss_pct"]
        steady = not any(f.startswith("not steady") for f in flags)
        if not steady:
            res["durability_label"] = "NOT MEANINGFUL (pace/terrain varied a lot, so late-vs-early efficiency is confounded)"
        elif v < 0:
            res["durability_label"] = "negative: efficiency improved late (pacing change); no fade"
        else:
            res["durability_label"] = ("holds efficiency when tired" if v < DURABILITY_OK else
                                       "moderate late fade" if v < DURABILITY_HIGH else "large late fade")
    return res


def print_report(r):
    if r.get("error"):
        print(f"{r['id']}: {r['error']}")
        return
    print(f"{r['start'][:16]}  {r['type']}  {r['km']} km, {r['moving_min']} min moving ({r['elapsed_min']} elapsed), "
          f"avg HR {r['avg_hr']:.0f}, climbing {r['gain_m_per_km']} m/km   [{r['metric']}]")
    print(f"EF {r['ef']} {r['ef_unit']}   (compare with your own similar sessions in similar weather; higher = fitter)")
    if "decoupling_pct" in r:
        print(f"decoupling {r['decoupling_pct']:+.1f} %  ({r['decoupling_label']})   HR {r['hr_first']:.0f} -> {r['hr_second']:.0f} bpm "
              f"({r['hr_drift_pct']:+.1f} %)   reliable: {'yes' if r['reliable'] else 'NO'}")
    if "durability_ef_loss_pct" in r:
        print(f"durability: EF {r['durability_ef_loss_pct']:+.1f} % lost in the last quarter vs early ({r['durability_label']}); "
              f"HR {r['hr_early']:.0f} -> {r['hr_late']:.0f}")
    if "cadence_change_rpm" in r:
        print(f"cadence 2nd half vs 1st half: {r['cadence_change_rpm']:+.1f} rpm (a decline goes with more drift/decoupling in trained cyclists)")
    for f in r.get("flags", []):
        print(f"NOTE {f}")
    if r.get("warmup_cooldown_removed"):
        print("note: warm-up / cool-down / rest laps marked by the watch were removed before the calculation")
    if r.get("quarters"):
        print("by quarter (moving time):  " + "   ".join(
            f"Q{i + 1} {q['speed_kmh']} km/h" + (f" {q['power']} W" if q.get("power") else "") + f" @ {q['hr']} bpm"
            for i, q in enumerate(r["quarters"])))
    z = r.get("zones")
    if z:
        m = z["minutes_below_z1_z1_z2_z3_z4_z5"]
        tot = sum(m) or 1
        print("time in Garmin HR zones (min): " + ", ".join(f"{n} {v:g}" for n, v in zip(["<Z1", "Z1", "Z2", "Z3", "Z4", "Z5"], m))
              + f"   [{z['sport']}, LTHR {z['lthr']}, max {z['max_hr']}]  easy share (<=Z2): {(m[0] + m[1] + m[2]) / tot * 100:.0f} %")


def main():
    gcommon.utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("activity_id", type=int)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    with gcommon.Garmin() as g:
        try:
            zones = g.call("garmin_get_heart_rate_zones")
        except gcommon.GarminError:
            zones = None
        r = analyze(g, a.activity_id, zones)
    if a.json:
        print(json.dumps(r, ensure_ascii=False, default=str))
    else:
        print_report(r)


if __name__ == "__main__":
    main()
