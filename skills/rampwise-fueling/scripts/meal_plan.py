#!/usr/bin/env python3
"""A day-by-day meal plan with grams, built from the athlete's calorie and macro targets and a food list with USDA nutrient values.

  meal_plan.py --sex male --age 22 --height-cm 183 --weight-kg 85 --goal cut --hours-by-day 0,1,1.5,0,1,2.5,3 \
      --adult yes --pregnant no --eating-disorder no --medical-diet no --meals 4 --cuisine seasian --diet halal --days 7 --start 2026-11-23

Each day follows the target of its day type (rest, light, moderate, hard, long): more carbohydrate on the heavy days, protein spread evenly over the meals
(0.25-0.55 g/kg per meal, Schoenfeld 2018, Iraki 2019, Jager 2017), and, if you give the hour each session starts (--start-hours), the carbohydrate-richer
meals sit before and after it (Kerksick 2017, 2018). Meals are built from basic foods; Southeast Asian-style meals are approximations built from ingredients
(tempeh, tofu, rice, fish, greens...), not the restaurant dish. Your own foods go in $RAMPWISE_DATA/foods.json (see foods.py). Weights are cooked unless the name says raw.
It writes meal-plan.md and meal-plan.json to the nutrition folder under your outputs. Not medical advice.
"""
import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "rampwise" / "scripts"))
import nutri  # noqa: E402
import nutri_args as na  # noqa: E402

DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def clock(h):
    return f"{int(h):02d}:{int(round((h % 1) * 60)):02d}"


def render(days, prof, targets, shop, foods, label):
    L = [f"# Meal plan: {label}", "",
         f"Goal **{targets['goal']}**, about {targets['avg_target']} kcal/day on average, protein {targets['protein_g_per_kg']} g/kg. "
         "Targets are estimates; check them against your weight trend (`weight_trend.py`). Not medical advice.", ""]
    for n in targets["notes"]:
        L.append(f"- {n}")
    for f in targets["flags"]:
        L.append(f"- **Flag:** {f}")
    L.append("")
    for d in days:
        t = d["target"]
        L.append(f"## {d['date']} {DOW[d['dow']]}: {d['type']} day" + (f" ({d['hours']:g} h training" + (f", starts {clock(d['start'])}" if d.get("start") else "") + ")" if d["hours"] else ""))
        L.append(f"Target {t['E']} kcal, protein {t['P']} g, carbohydrate {t['C']} g ({t['cho_gkg']} g/kg), fat {t['F']} g. Planned: **{d['totals']['kcal']:.0f} kcal**, "
                 f"protein {d['totals']['protein']:.0f} g, carbohydrate {d['totals']['carb']:.0f} g, fat {d['totals']['fat']:.0f} g, fibre {d['totals']['fiber']:.0f} g.")
        L.append("")
        for m in d["meals"]:
            r = m["result"]
            tag = {"pre": " (before training)", "post": " (after training)"}.get(m["role"], "")
            if not r:
                L.append(f"### {m['slot'].title()}{tag}: no meal fits your diet and exclusions; add foods with `foods.py add` or relax a filter\n")
                continue
            tt = r["totals"]
            main = ", ".join(it["food"]["name"].split(",")[0] for it in r["items"] if it["role"] in ("P", "C", "F"))
            L.append(f"### {m['slot'].title()}{tag}: {r['template']['name']} ({main}); {tt['kcal']:.0f} kcal, P {tt['protein']:.0f} / C {tt['carb']:.0f} / F {tt['fat']:.0f} g")
            for it in r["items"]:
                ut = nutri.unit_text(it["food"], it["g"])
                L.append(f"- {it['food']['name']}: **{it['g']:.0f} g**" + (f" (about {ut})" if ut else ""))
            L.append("")
    L.append("## Shopping list for the plan (grams, as listed: cooked foods are cooked weight)")
    for name, g in sorted(shop.items(), key=lambda kv: (kv[1]["group"], kv[0])):
        L.append(f"- {name}: {g['g']:.0f} g")
    L.append("")
    L.append("Food values: USDA FoodData Central, SR Legacy (public domain)" + (" and your own foods.json entries" if any(f.get("custom") for f in foods.values()) else "")
             + ". Cooking, brands and recipes change the numbers; a food that you weigh differently needs a custom entry. Swap freely between foods of the same role.")
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    na.add_profile_args(ap)
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--start", help="first date, YYYY-MM-DD (default today)")
    ap.add_argument("--meals", type=int, choices=(3, 4, 5, 6), help="meals per day, snacks included (3-6 all work equally well for muscle: Helms 2014)")
    ap.add_argument("--cuisine", choices=("seasian", "global", "mixed"))
    ap.add_argument("--diet", choices=tuple(nutri.DIETS))
    ap.add_argument("--exclude", help="comma list of allergens/tags to leave out: " + ",".join(sorted(nutri.ALLERGENS)))
    ap.add_argument("--exclude-food", help="comma list of food keys to leave out (see foods.py search)")
    ap.add_argument("--start-hours", help="hour each session starts Monday to Sunday (0 = none), e.g. 0,17,6.5,0,17,7,7")
    ap.add_argument("--out", help="output folder (default: nutrition folder under your outputs)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    p, missing, hours = na.profile_from_args(a)
    nut = na.load_athlete().get("nutrition", {})
    meals = a.meals or nut.get("meals_per_day") or 4
    cuisine = a.cuisine or nut.get("cuisine") or "mixed"
    diet = a.diet or nut.get("diet") or "omnivore"
    excl = [x for x in (a.exclude.split(",") if a.exclude is not None else nut.get("exclude", [])) if x]
    excl_food = [x for x in (a.exclude_food.split(",") if a.exclude_food is not None else nut.get("exclude_food", [])) if x]
    sh = [float(x) for x in a.start_hours.split(",")] if a.start_hours else nut.get("start_hours")
    if a.save:
        na.save_nutrition({"sex": p["sex"], "body_fat_pct": p["body_fat_pct"], "goal": p["goal"], "rate_pct": p["rate_pct"], "experience": p["experience"], "lifestyle": p["lifestyle"],
                           "gates": p["gates"], "hours_by_day": hours, "meals_per_day": meals, "cuisine": cuisine, "diet": diet, "exclude": excl, "exclude_food": excl_food, "start_hours": sh})
    bad = [x for x in excl if x not in nutri.ALLERGENS]
    if bad:
        print("unknown --exclude tag(s):", ", ".join(bad), "; use:", ", ".join(sorted(nutri.ALLERGENS)))
        return 2
    if missing or hours is None:
        print("STATUS: needs-info\nAsk the athlete for: " + ", ".join(missing + ([] if hours else ["training hours per day (Mon..Sun)"])) + " (never assume them).")
        return 2
    targets = nutri.plan_targets(p, hours, a.kcal_per_hour, a.weeks)
    if targets["status"] != "ok":
        print("STATUS:", targets["status"])
        for x in targets["reasons"]:
            print(" -", x)
        return 2
    foods = nutri.allowed_foods(nutri.load_foods(), diet, excl, excl_food)
    start = date.fromisoformat(a.start) if a.start else date.today()
    used, days, shop = {}, [], {}
    for i in range(a.days):
        d = start + timedelta(days=i)
        dt = targets["days"][d.weekday()]
        st = (sh[d.weekday()] if sh else 0) or None
        session = {"start": st, "hours": dt["hours"]} if st and dt["hours"] >= 1.0 else None
        ms = nutri.plan_day(dt, foods, meals, cuisine, used, session, p["kg"], offset=i)
        tot = nutri.day_totals(ms)
        days.append({"date": str(d), "dow": d.weekday(), "type": dt["type"], "hours": dt["hours"], "start": st, "target": dt, "meals": ms, "totals": tot})
        for m in ms:
            if m["result"]:
                for it in m["result"]["items"]:
                    e = shop.setdefault(it["food"]["name"], {"g": 0.0, "group": it["food"].get("group", "")})
                    e["g"] += it["g"]
    label = f"{start} to {start + timedelta(days=a.days - 1)} ({targets['goal']}, {cuisine}, {diet})"
    outdir = Path(a.out) if a.out else None
    if outdir is None:
        try:
            import gcommon
            outdir = gcommon.out_dir("nutrition", f"{start}-{targets['goal']}")
        except Exception:
            outdir = Path.home() / "rampwise-coach" / "nutrition" / f"{start}-{targets['goal']}"
    outdir.mkdir(parents=True, exist_ok=True)
    md = render(days, p, targets, shop, foods, label)
    (outdir / "meal-plan.md").write_text(md, encoding="utf-8")
    js = {"label": label, "targets": {k: v for k, v in targets.items() if k != "days"}, "days": [
        {"date": d["date"], "type": d["type"], "target": {k: d["target"][k] for k in ("E", "P", "C", "F")}, "totals": {k: round(v, 1) for k, v in d["totals"].items()},
         "meals": [{"slot": m["slot"], "role": m["role"], "name": m["result"]["template"]["name"] if m["result"] else None,
                    "items": [{"food": it["food"]["name"], "key": it["food"]["key"], "g": round(it["g"])} for it in (m["result"]["items"] if m["result"] else [])]} for m in d["meals"]]} for d in days]}
    (outdir / "meal-plan.json").write_text(json.dumps(js, indent=1, ensure_ascii=False), encoding="utf-8")
    if a.json:
        print(json.dumps(js, indent=1, ensure_ascii=False))
        return 0
    print(f"STATUS: ok   wrote {outdir / 'meal-plan.md'}")
    for d in days:
        t = d["target"]
        print(f"{d['date']} {DOW[d['dow']]} {d['type']:<9} target {t['E']} kcal  planned {d['totals']['kcal']:.0f} kcal  P {d['totals']['protein']:.0f}/{t['P']}  C {d['totals']['carb']:.0f}/{t['C']}  F {d['totals']['fat']:.0f}/{t['F']}")
    for f in targets["flags"]:
        print("FLAG:", f)
    return 0


if __name__ == "__main__":
    sys.exit(main())
