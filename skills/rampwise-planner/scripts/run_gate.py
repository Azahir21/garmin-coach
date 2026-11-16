#!/usr/bin/env python3
"""Run gate: did a whole session (warm-up to cool-down) get jogged with no walking?

An OPTIONAL goal the user can set (athlete.json goal "run-gate"): a consistency rule such as running a whole session without walking. once a full session of at least
`min_session_minutes` is jogged without walking, pace/speed training may start. This script finds walking
from the FIT cadence of each run, because Garmin summaries do not say which minutes were walked.

Walking = cadence below `walk_cadence_spm_below` (steps/min, both feet) while moving, lasting at least
`min_walk_segment_s`. The cut-off (125 spm) is an engineering threshold from one runner's files (jogging about 140-160 spm, walking about 100-115 spm), not a published one; change it in the goal criteria if it does not fit.
It is an engineering threshold, not a published one: say so if asked.

  run_gate.py [--days 28] [--json] [--record]
--record writes the result into athlete.json (gate passed date, or a dated note on how close the last run was).
"""
import argparse
import json
import statistics
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILLS = HERE.parent.parent
DATA_DIR = Path(__import__("os").environ.get("RAMPWISE_DATA") or __import__("os").environ.get("GARMIN_COACH_DATA") or (Path.home() / "garmin-coach-data" if (Path.home() / "garmin-coach-data").exists() and not (Path.home() / "rampwise-data").exists() else Path.home() / "rampwise-data"))   # personal data lives OUTSIDE the plugin folder, so updates never touch it
ATHLETE_JSON = DATA_DIR / "athlete.json"
sys.path.insert(0, str(SKILLS / "rampwise" / "scripts"))
import gcommon as gc  # noqa: E402

ATHLETE = ATHLETE_JSON
MOVING_MS = 0.7          # below this the athlete is standing still (traffic light, pause)
SMOOTH_S = 7             # median window for cadence (one-second glitches are not walking)
EDGE_S = 600             # first / last 10 min = warm-up / cool-down for labelling only


def classify(recs, walk_below, min_seg):
    """Return per-second labels: 'jog' | 'walk' | 'stop' | '?' (moving without usable cadence)."""
    n = len(recs)
    cad = []
    for r in recs:
        c = r.get("cadence")
        cad.append(None if c is None else float(c) * 2.0)   # FIT run cadence is per leg
    lab = []
    half = SMOOTH_S // 2
    for i, r in enumerate(recs):
        sp = r.get("speed") or 0.0
        if sp < MOVING_MS:
            lab.append("stop")
            continue
        win = [c for c in cad[max(0, i - half): i + half + 1] if c is not None and c > 0]
        if len(win) < 3:
            lab.append("?")
            continue
        m = statistics.median(win)
        lab.append("jog" if m >= walk_below else "walk")
    # drop walk blips shorter than min_seg (turn them back to jog)
    i = 0
    while i < n:
        if lab[i] == "walk":
            j = i
            while j < n and lab[j] == "walk":
                j += 1
            if recs[j - 1]["t"] - recs[i]["t"] + 1 < min_seg:
                for k in range(i, j):
                    lab[k] = "jog"
            i = j
        else:
            i += 1
    return lab


def segments(recs, lab, kind):
    out, i, n = [], 0, len(recs)
    while i < n:
        if lab[i] == kind:
            j = i
            while j < n and lab[j] == kind:
                j += 1
            out.append((recs[i]["t"], recs[j - 1]["t"] - recs[i]["t"] + 1))
            i = j
        else:
            i += 1
    return out


def analyze(recs, crit, hr_cap):
    lab = classify(recs, crit["walk_cadence_spm_below"], crit["min_walk_segment_s"])
    total = recs[-1]["t"] - recs[0]["t"] + 1
    walks = segments(recs, lab, "walk")
    walk_s = sum(d for _, d in walks)
    stops_s = sum(1 for x in lab if x == "stop")
    unk_s = sum(1 for x in lab if x == "?")
    jog_idx = [i for i, x in enumerate(lab) if x == "jog"]
    hrs = [recs[i]["hr"] for i in jog_idx if recs[i].get("hr")]
    sps = [recs[i]["speed"] for i in jog_idx if recs[i].get("speed")]
    # longest uninterrupted jog (walk or a stop of 15 s or more breaks it)
    longest, cur, gap = 0.0, 0.0, 0
    for x in lab:
        if x == "jog":
            cur += 1 + gap; gap = 0
        elif x == "stop" and gap < 15:
            gap += 1
        else:
            longest = max(longest, cur); cur = 0.0; gap = 0
    longest = max(longest, cur)
    where = {"warm-up": 0, "main": 0, "cool-down": 0}
    for t0, d in walks:
        mid = t0 + d / 2
        where["warm-up" if mid < EDGE_S else "cool-down" if mid > total - EDGE_S else "main"] += d
    above = None
    if hrs and hr_cap:
        above = round(100.0 * sum(1 for h in hrs if h > hr_cap) / len(hrs))
    return {
        "minutes": round(total / 60, 1), "walk_s": int(walk_s), "walk_segments": [(round(t / 60, 1), int(d)) for t, d in walks],
        "walk_where_s": {k: int(v) for k, v in where.items()}, "stops_s": int(stops_s), "unknown_s": int(unk_s),
        "longest_jog_min": round(longest / 60, 1),
        "jog_avg_hr": round(statistics.mean(hrs)) if hrs else None,
        "jog_speed_kmh": round(statistics.median(sps) * 3.6, 2) if sps else None,
        "jog_pace_min_km": None,
        "pct_jog_above_hr_cap": above,
        "qualifies": bool(total / 60 >= crit["min_session_minutes"] and walk_s <= crit["max_walk_seconds"]),
    }


def fmt_pace(kmh):
    if not kmh:
        return "n/a"
    p = 60.0 / kmh
    return f"{int(p)}:{int(round((p % 1) * 60)):02d}/km"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=int, default=28)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--record", action="store_true")
    a = ap.parse_args()
    gc.utf8_stdout()
    ath = json.loads(ATHLETE.read_text(encoding="utf-8"))
    gate = gc.goal_by(ath, "run-gate", "criteria")
    if gate is None:
        print("No run-gate goal in athlete.json (it is optional: a whole session run with no walking). Add one with athlete.py goal-add or ignore this check.")
        return
    crit = gate["criteria"]
    hr_cap = ath["hr"].get("run_easy_max")
    end = date.today()
    start = end - timedelta(days=a.days)
    rows = []
    with gc.Garmin() as g:
        runs = [r for r in gc.list_activities(g, start, end) if r["sport"] == "run" and r["min"] >= 15]
        for r in sorted(runs, key=lambda x: x["start"]):
            try:
                recs = gc.read_fit(gc.fit_zip(g, r["id"]))
                if len(recs) < 120:
                    continue
                res = analyze(recs, crit, hr_cap)
            except Exception as e:  # keep going; one bad file should not hide the rest
                res = {"error": str(e)}
            res["pace"] = fmt_pace(res.get("jog_speed_kmh"))
            res.update({"id": r["id"], "date": str(r["date"])})
            rows.append(res)
    ok = [r for r in rows if r.get("qualifies")]
    passed = len(ok) >= crit["required_sessions"]
    out = {"gate": "run-gate", "criteria": crit, "sessions": rows, "qualifying": len(ok), "passed": passed}
    if a.json:
        print(json.dumps(out, indent=1, default=str))
    else:
        print(f"RUN GATE (last {a.days} days): session >= {crit['min_session_minutes']} min, walking <= {crit['max_walk_seconds']} s "
              f"(walk = cadence < {crit['walk_cadence_spm_below']} spm for >= {crit['min_walk_segment_s']} s)")
        print(f"{'date':10} {'min':>5} {'walk s':>7} {'where (warm/main/cool s)':>24} {'longest jog':>12} {'jog pace':>9} {'jog HR':>6} {'>HRcap':>6}  result")
        for r in rows:
            if "error" in r:
                print(r["date"], "ERROR", r["error"]); continue
            w = r["walk_where_s"]
            res = "PASS" if r["qualifies"] else ("too short" if r["minutes"] < crit["min_session_minutes"] and r["walk_s"] <= crit["max_walk_seconds"] else "walked")
            cap = f"{r['pct_jog_above_hr_cap']}%" if r["pct_jog_above_hr_cap"] is not None else "n/a"
            print(f"{r['date']:10} {r['minutes']:5.0f} {r['walk_s']:7d} {w['warm-up']:>7d}/{w['main']:>5d}/{w['cool-down']:>5d} "
                  f"{r['longest_jog_min']:10.1f}m {r['pace']:>9} {str(r['jog_avg_hr']):>6} {cap:>6}  {res}")
        print()
        print(f"GATE: {'PASSED' if passed else 'NOT YET'} ({len(ok)} of {crit['required_sessions']} required qualifying session(s) in {a.days} days)")
        if rows and not passed:
            best = min((r for r in rows if "error" not in r), key=lambda r: r["walk_s"])
            print(f"Closest: {best['date']}: walked {best['walk_s']} s (warm-up {best['walk_where_s']['warm-up']}, main {best['walk_where_s']['main']}, "
                  f"cool-down {best['walk_where_s']['cool-down']}); longest unbroken jog {best['longest_jog_min']} min.")
        print("Caveat: walking is inferred from cadence (engineering threshold, not a published cut-off); stops of a few seconds are not counted as walking.")
    if a.record:
        cmd = [sys.executable, str(SKILLS / "rampwise" / "scripts" / "athlete.py")]
        if passed:
            subprocess.run(cmd + ["set", "goals.run-gate.passed", json.dumps(str(end))], check=True)
            subprocess.run(cmd + ["note", "--text", "Run gate PASSED: " + ", ".join(r["date"] for r in ok)], check=True)
        else:
            subprocess.run(cmd + ["note", "--text", f"Run gate checked {end}: not yet ({len(ok)}/{crit['required_sessions']})"], check=True)


if __name__ == "__main__":
    main()
