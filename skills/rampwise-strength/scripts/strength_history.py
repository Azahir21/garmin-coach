"""Strength history from Garmin: exercises, sets, reps and weights per session (read-only).

Garmin stores a strength session's sets in the activity FIT file ("set" messages: exercise category, exercise name, repetitions, weight, duration,
and rest sets). Sessions logged without a structured workout have only time and heart rate, so some sessions can show no sets.

  strength_history.py [--days 200] [--json OUT.json]

Prints one block per session: exercise, then its sets as reps x kg. Weight is as Garmin stores it (kilograms; not verified whether it is per hand or total).
Other scripts import `load_history(g, days)` and `last_sets(history, exercise_key)`.
"""
import argparse
import io
import json
import sys
import zipfile
from datetime import date, timedelta
from pathlib import Path

SKILLS = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(SKILLS / "rampwise" / "scripts"))
import gcommon as gc  # noqa: E402

try:
    import fitdecode
    import fitdecode.profile as FP
except ImportError:                                   # pragma: no cover
    sys.exit("the fitdecode package is needed: add it once with pip (README, Setup)")

CAT = FP.FIELD_TYPES["exercise_category"].enum


def exercise_name(category, subtype):
    """Garmin category + subtype -> (category name, exercise name or None) using the FIT profile."""
    cname = CAT.get(category, f"category_{category}")
    if subtype is None:
        return cname, None
    t = FP.FIELD_TYPES.get(f"{cname}_exercise_name")
    return cname, (t.enum.get(subtype) if t else None)


def _first(v):
    if isinstance(v, (tuple, list)):
        return next((x for x in v if x is not None), None)
    return v


def read_sets(zip_path):
    """Active sets of one strength FIT file, grouped by consecutive same exercise."""
    zf = zipfile.ZipFile(zip_path)
    fn = next(n for n in zf.namelist() if n.lower().endswith(".fit"))
    sets = []
    with fitdecode.FitReader(io.BytesIO(zf.read(fn))) as fr:
        for fm in fr:
            if isinstance(fm, fitdecode.FitDataMessage) and fm.name == "set":
                d = {f.name: f.value for f in fm.fields}
                if d.get("set_type") != "active":
                    continue
                cat, sub = _first(d.get("category")), _first(d.get("category_subtype"))
                cname, ename = exercise_name(cat, sub)
                sets.append({"category": cname, "exercise": ename, "reps": d.get("repetitions"), "kg": d.get("weight"),
                             "seconds": round(d.get("duration") or 0)})
    out = []
    for s in sets:
        key = (s["category"], s["exercise"])
        if out and out[-1]["key"] == list(key):
            out[-1]["sets"].append({k: s[k] for k in ("reps", "kg", "seconds")})
        else:
            out.append({"key": list(key), "sets": [{k: s[k] for k in ("reps", "kg", "seconds")}]})
    return out


def load_history(g, days=200):
    acts = gc.list_activities(g, date.today() - timedelta(days=days), date.today())
    hist = []
    for a in sorted((x for x in acts if x["sport"] == "strength"), key=lambda x: x["date"]):
        try:
            blocks = read_sets(gc.fit_zip(g, a["id"]))
        except Exception as e:                        # a file without sets or an unreadable file
            blocks = []
        hist.append({"date": str(a["date"]), "name": a["name"], "minutes": round(a["min"]), "avg_hr": a["avg_hr"], "exercises": blocks})
    return hist


def last_sets(history, category, exercise=None):
    """Most recent session's sets for an exercise (category, exercise name or None = any exercise of that category)."""
    for s in reversed(history):
        for b in s["exercises"]:
            if b["key"][0] == category and (exercise is None or b["key"][1] == exercise):
                return s["date"], b["sets"]
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=int, default=200)
    ap.add_argument("--json")
    a = ap.parse_args()
    gc.utf8_stdout()
    with gc.Garmin() as g:
        hist = load_history(g, a.days)
    if a.json:
        Path(a.json).write_text(json.dumps(hist, indent=1), encoding="utf-8")
    print(f"{len(hist)} strength sessions in the last {a.days} days")
    for s in hist:
        print(f"\n{s['date']}  {s['name']}  {s['minutes']} min  avg HR {s['avg_hr']}")
        if not s["exercises"]:
            print("   (no sets stored: time and heart rate only)")
        for b in s["exercises"]:
            nm = b["key"][1] or b["key"][0]
            print(f"   {b['key'][0]}/{nm}: " + ", ".join(f"{x['reps']}x{x['kg']:g}kg" if x["kg"] else f"{x['reps']}x bodyweight" for x in b["sets"]))


if __name__ == "__main__":
    main()
