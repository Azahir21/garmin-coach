#!/usr/bin/env python3
"""Aerobic analysis of ONE activity from its FIT data (runs and rides: efficiency, decoupling, drift; swims: pace per 100 m, rest share and a lap-based decoupling; multisport: the legs): efficiency factor, decoupling, HR drift,
durability, cadence fade (bike), time in HR zones, and whether the numbers can be trusted.

Usage:
  analyze_activity.py ACTIVITY_ID [--json]            a Garmin activity (downloaded through your own Garmin server)
  analyze_activity.py --fit-file FILE [--sport run|bike|swim] [--json]    a .fit file (or the .zip Garmin exports) from ANY watch brand: Garmin, Wahoo, COROS, Suunto, Polar ...
  analyze_activity.py --strava-json FILE [--sport run|bike] [--json]      Strava API data an agent saved as JSON (see activity_sources.py; not run against a live account)
Files from other brands are read tolerantly: missing speed is worked out from distance, missing heart rate or ascent is reported, and Garmin-only extras (HR zones from
your Garmin account, watch-marked warm-up laps on other brands) are used only when present.

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
sys.path.insert(0, str(HERE.parents[1] / "rampwise" / "scripts"))

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


def _fit_messages(zip_path, names):
    """Raw FIT messages of the given kinds (lap, session) as plain dicts, from a .fit file or the .zip Garmin exports. GPS positions are not read."""
    import activity_sources
    return activity_sources.read_messages(gcommon.fit_bytes(zip_path), tuple(names))


def swim_analysis(laps_in, summary):
    """Aerobic reading of a swim from its LAP messages (the per-second records of a pool swim carry heart rate but no speed): pace per 100 m of swimming time, rest share,
    and decoupling = percent drop of (speed / heart rate) from the first to the second half of the swimming distance. Wrist heart rate in water can be unreliable:
    use it as a trend within the athlete's own swims, ideally with a chest strap (practice; no source read). Thresholds are the same coaching conventions as for runs and rides."""
    act = [l for l in laps_in if (l.get("total_distance") or 0) > 0 and (l.get("total_timer_time") or 0) > 0]
    res = {"kind": "swim", "id": summary["id"], "name": summary["name"], "start": str(summary["start"]), "elapsed_min": round(summary["min"]), "avg_hr": summary["avg_hr"]}
    flags = []
    if not act:
        res["error"] = "no swimming laps with distance in this file"
        return res
    dist = sum(l["total_distance"] for l in act)
    t_swim = sum(l["total_timer_time"] for l in act)
    res.update({"swim_m": round(dist), "swim_min": round(t_swim / 60.0, 1), "pace_s_per_100m": round(t_swim / dist * 100.0), "laps": len(act),
                "rest_share_pct": round(max(0.0, 1.0 - t_swim / (summary["min"] * 60.0)) * 100.0) if summary["min"] else None})
    paces = [l["total_timer_time"] / l["total_distance"] * 100.0 for l in act]
    mean_p = sum(paces) / len(paces)
    cv = (sum((p - mean_p) ** 2 for p in paces) / len(paces)) ** 0.5 / mean_p if mean_p else 0
    res["pace_variation_pct"] = round(cv * 100.0, 1)
    if dist < 800 or len(act) < 8:
        flags.append("too short for a drift reading (needs about 800 m and 8 swimming laps or more)")
    if res["rest_share_pct"] is not None and res["rest_share_pct"] > 35:
        flags.append("a lot of rest between laps: an interval or drill session, not a steady swim")
    if cv > 0.12:
        flags.append("pace varies a lot from lap to lap: not a steady swim")
    hr_laps = [l for l in act if l.get("avg_heart_rate")]
    if len(hr_laps) < len(act) * 0.8:
        flags.append("heart rate missing for many laps (wrist heart rate often drops out in water): no efficiency reading")
    else:
        half = dist / 2.0
        acc, a1, a2 = 0.0, [], []
        for l in hr_laps:
            (a1 if acc < half else a2).append(l)
            acc += l["total_distance"]

        def ef(ls):
            d = sum(x["total_distance"] for x in ls)
            t = sum(x["total_timer_time"] for x in ls)
            hr = sum(x["avg_heart_rate"] * x["total_distance"] for x in ls) / d
            return (d / t) * 60.0 / hr if t and hr else None
        e1, e2 = ef(a1), ef(a2)
        res["ef_m_per_min_per_bpm"] = round(ef(hr_laps), 2)
        if e1 and e2:
            res["decoupling_pct"] = round((e1 - e2) / e1 * 100.0, 1)
            res["hr_first_half"] = round(sum(x["avg_heart_rate"] for x in a1) / len(a1))
            res["hr_second_half"] = round(sum(x["avg_heart_rate"] for x in a2) / len(a2))
    res["reliable"] = not flags
    res["flags"] = flags
    res["note"] = "Compare only with your own earlier swims in the same pool or water, similar effort. Pool and open water differ; wrist heart rate in water can be unreliable."
    return res


def multisport_legs(sessions_in, summary):
    """Legs of a multisport activity (one file, several sessions): sport, time, distance, speed or pace, heart rate. Drift is not computed per leg."""
    legs = []
    for s in sessions_in:
        d, t = s.get("total_distance") or 0, s.get("total_timer_time") or s.get("total_elapsed_time") or 0
        sp = str(s.get("sport") or "other").lower()
        leg = {"sport": sp, "minutes": round(t / 60.0, 1), "km": round(d / 1000.0, 2), "avg_hr": s.get("avg_heart_rate")}
        if d and t:
            if sp == "running":
                leg["pace_s_per_km"] = round(t / (d / 1000.0))
            elif sp == "swimming":
                leg["pace_s_per_100m"] = round(t / d * 100.0)
            else:
                leg["speed_kmh"] = round(d / t * 3.6, 1)
        legs.append(leg)
    return {"kind": "multi", "id": summary["id"], "name": summary["name"], "start": str(summary["start"]), "legs": legs,
            "note": "One recorded activity, split into its legs. A run straight after a bike costs more energy (Millet and Vleck 2000; Walsh 2019); per-leg drift is not computed."}


def print_swim(r):
    print(f"SWIM {r['start'][:16]}: {r['name']}")
    if r.get("error"):
        print("  " + r["error"])
        return
    print(f"  {r['swim_m']} m swum in {r['swim_min']} min (session {r['elapsed_min']} min, rest {r['rest_share_pct']} %), {r['laps']} laps, pace {r['pace_s_per_100m'] // 60}:{r['pace_s_per_100m'] % 60:02d} per 100 m (moving time), pace variation {r['pace_variation_pct']} %")
    if "ef_m_per_min_per_bpm" in r:
        print(f"  efficiency {r['ef_m_per_min_per_bpm']} m/min per bpm" + (f", decoupling {r['decoupling_pct']:+.1f} % (HR {r['hr_first_half']} -> {r['hr_second_half']})" if "decoupling_pct" in r else ""))
    for f in r["flags"]:
        print("  NOT RELIABLE:" if not r["reliable"] else "  note:", f)
    print("  " + r["note"])


def print_multi(r):
    print(f"MULTISPORT {r['start'][:16]}: {r['name']}")
    if not r["legs"]:
        print("  " + r["note"])
        return
    for l in r["legs"]:
        extra = (f", pace {l['pace_s_per_km'] // 60}:{l['pace_s_per_km'] % 60:02d}/km" if "pace_s_per_km" in l else f", pace {l['pace_s_per_100m'] // 60}:{l['pace_s_per_100m'] % 60:02d}/100 m" if "pace_s_per_100m" in l else f", {l['speed_kmh']} km/h" if "speed_kmh" in l else "")
        print(f"  {l['sport']:10} {l['minutes']} min, {l['km']} km{extra}, HR {l['avg_hr']}")
    print("  " + r["note"])


def garmin_source(g, activity_id):
    """The same dict activity_sources returns, for an activity on your own Garmin account."""
    s = gcommon.activity_summary(g, activity_id)
    z = gcommon.fit_zip(g, activity_id)
    if s["sport"] in ("swim", "multi"):
        m = _fit_messages(z, ("lap", "session"))
        return {"summary": s, "recs": [], "laps": [], "lap_msgs": m["lap"], "session_msgs": m["session"], "origin": {"kind": "garmin", "notes": []}}
    recs, laps = gcommon.read_fit(z, with_laps=True)
    return {"summary": s, "recs": recs, "laps": laps, "lap_msgs": [], "session_msgs": [], "origin": {"kind": "garmin", "notes": []}}


def analyze(g, activity_id, zones_res=None):
    return analyze_source(garmin_source(g, activity_id), zones_res)


def analyze_source(src, zones_res=None):
    s, recs, laps = src["summary"], src["recs"], src["laps"]
    res = _analyze(s, recs, laps, src, zones_res)
    res["source"] = {k: v for k, v in src["origin"].items() if v}
    return res


def _analyze(s, recs, laps, src, zones_res):
    if s["sport"] in ("swim", "multi"):
        if s["sport"] == "swim":
            if not src["lap_msgs"]:
                return {"kind": "swim", "id": s["id"], "name": s["name"], "start": str(s["start"]), "elapsed_min": round(s["min"]), "avg_hr": s["avg_hr"], "flags": [],
                        "error": "a swim needs lap data (distance and time per length); Strava streams and files without laps do not have it: export the FIT file from your watch's own app"}
            return swim_analysis(src["lap_msgs"], s)
        if not src["session_msgs"]:
            return {"kind": "multi", "id": s["id"], "name": s["name"], "start": str(s["start"]), "legs": [], "note": "no session data: a multisport activity needs the FIT file from the watch"}
        return multisport_legs(src["session_msgs"], s)
    sport = s["sport"]
    if sport == "strength":
        return {"id": s["id"], "name": s["name"], "type": s["type"], "sport": sport, "start": str(s["start"]), "error": "a strength session has no pace or speed: the aerobic analysis does not apply (use rampwise-strength)"}
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
        res["error"] = ("no heart-rate data in this activity: efficiency and drift need it" if not any(r.get("hr") for r in recs) else
                        "no speed data in this activity (and no distance to work it out from)" if not any(r.get("speed") for r in recs) else
                        "too little moving data with heart rate after the warm-up")
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


def print_source(r):
    o = r.get("source") or {}
    if o.get("kind") in ("fit-file", "strava-json"):
        who = " ".join(x for x in (o.get("manufacturer"), o.get("product"), o.get("device")) if x) or "unknown device"
        print(f"source: {'FIT file' if o['kind'] == 'fit-file' else 'Strava JSON'} {o.get('file', '')} ({who}). Garmin heart-rate zones are only available for Garmin activities.")
        for n in o.get("notes", []):
            print(f"note: {n}")


def print_report(r):
    print_source(r)
    if r.get("kind") == "swim":
        return print_swim(r)
    if r.get("kind") == "multi":
        return print_multi(r)
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
    ap.add_argument("activity_id", type=int, nargs="?", help="a Garmin activity id")
    ap.add_argument("--fit-file", help=".fit file (or the .zip Garmin exports) from any watch brand")
    ap.add_argument("--strava-json", help="Strava API activity + streams saved as JSON")
    ap.add_argument("--sport", choices=["run", "bike", "swim"], help="override the sport when the file does not say it")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    chosen = [x for x in (a.activity_id, a.fit_file, a.strava_json) if x is not None]
    if len(chosen) != 1:
        ap.error("give exactly one of: an ACTIVITY_ID (Garmin), --fit-file FILE, --strava-json FILE")
    if a.fit_file or a.strava_json:
        import activity_sources
        src = activity_sources.load_fit_file(a.fit_file, a.sport) if a.fit_file else activity_sources.load_strava_json(a.strava_json, a.sport)
        r = analyze_source(src)
    else:
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
