"""Command-line helpers shared by the nutrition scripts: the athlete's answers in athlete.json, and the common arguments."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nutri  # noqa: E402


def athlete_path():
    return nutri.data_dir() / "athlete.json"


def load_athlete():
    try:
        return json.loads(athlete_path().read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_nutrition(block):
    """Merge the given keys into athlete.json -> nutrition (only keys whose value is not None). The athlete's own answers, nothing else."""
    p = athlete_path()
    d = load_athlete()
    cur = d.setdefault("nutrition", {})
    for k, v in block.items():
        if v is not None:
            cur[k] = v
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def yn(v):
    return None if v is None else str(v).lower() in ("yes", "y", "true", "1")


def add_profile_args(ap):
    ap.add_argument("--sex", choices=("male", "female"), help="used only for the resting-energy equation")
    ap.add_argument("--age", type=int)
    ap.add_argument("--height-cm", type=float)
    ap.add_argument("--weight-kg", type=float)
    ap.add_argument("--body-fat", type=float, help="body fat %%, only if measured or estimated well (optional)")
    ap.add_argument("--goal", choices=("cut", "maintain", "bulk"))
    ap.add_argument("--rate", type=float, help="%% of body weight per week: loss on a cut, gain on a bulk (default cut 0.5)")
    ap.add_argument("--experience", choices=("novice", "intermediate", "advanced"), help="resistance-training experience (sets the bulk size)")
    ap.add_argument("--lifestyle", choices=tuple(nutri.LIFESTYLE), help="non-training activity: sedentary / light (default) / active")
    ap.add_argument("--hours-by-day", help="training hours Monday to Sunday, e.g. 0,1,1.5,0,1,2.5,3")
    ap.add_argument("--hours-week", type=float, help="weekly training hours (spread over 6 days) if there is no day-by-day plan")
    ap.add_argument("--kcal-per-hour", type=float, help="your watch's average kcal per training hour (otherwise a rough 8 kcal/kg/h)")
    ap.add_argument("--weeks", type=int, help="planned length of a cut in weeks")
    for g, h in (("adult", "18 or older"), ("pregnant", "pregnant or breastfeeding"), ("eating-disorder", "an eating disorder now or before, or anxious about food"),
                 ("medical-diet", "a medical condition that changes how you should eat")):
        ap.add_argument("--" + g, choices=("yes", "no"), help="the athlete's own answer: " + h)
    ap.add_argument("--save", action="store_true", help="store the answers in athlete.json under nutrition (only what you pass)")


def profile_from_args(a):
    ath = load_athlete()
    nut = ath.get("nutrition", {})
    pr = ath.get("profile", {})
    gates = dict(nut.get("gates") or {})
    for key, val in (("adult", a.adult), ("pregnant_or_breastfeeding", a.pregnant), ("eating_disorder", a.eating_disorder), ("medical_diet", a.medical_diet)):
        if val is not None:
            gates[key] = yn(val)
    p = {"sex": a.sex or nut.get("sex"), "age": a.age or pr.get("age_years"), "cm": a.height_cm or pr.get("height_cm"), "kg": a.weight_kg or pr.get("weight_kg"),
         "body_fat_pct": a.body_fat if a.body_fat is not None else nut.get("body_fat_pct"), "goal": a.goal or nut.get("goal") or "maintain",
         "rate_pct": a.rate if a.rate is not None else nut.get("rate_pct"), "experience": a.experience or nut.get("experience") or "intermediate",
         "lifestyle": a.lifestyle or nut.get("lifestyle") or "light", "gates": gates}
    missing = [k for k in ("sex", "age", "cm", "kg") if not p[k]]
    hours = None
    if a.hours_by_day:
        hours = [float(x) for x in a.hours_by_day.split(",")]
        if len(hours) != 7:
            raise SystemExit("--hours-by-day needs 7 numbers, Monday to Sunday")
    elif a.hours_week is not None:
        per = a.hours_week / 6.0
        hours = [per] * 6 + [0.0]
    elif nut.get("hours_by_day"):
        hours = nut["hours_by_day"]
    return p, missing, hours
