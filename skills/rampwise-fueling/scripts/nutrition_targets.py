#!/usr/bin/env python3
"""Daily calories and macros for cutting, maintaining or bulking, for an endurance athlete, with the safeguards that go with them.

  nutrition_targets.py --sex male --age 22 --height-cm 183 --weight-kg 85 --goal cut --hours-by-day 0,1,1.5,0,1,2.5,3 \
      --adult yes --pregnant no --eating-disorder no --medical-diet no

What it does (every rule is labelled in ../references/evidence-map.md):
  * stops and says what to ask if the four safety questions are not answered, or refers to a dietitian if an answer is a no-go;
  * resting energy from Mifflin-St Jeor, a non-training activity factor (practice) and the day's training energy = estimated maintenance;
  * cut: 0.5 %/week by default (range 0.5-1 %, Helms 2014; 0.7 beat 1.4 in Garthe 2011), deficit capped at 25 %, carbohydrate protected on hard days;
  * bulk: surplus of about 10-20 % (Iraki 2019), smaller for advanced lifters; protein 1.6-2.2 g/kg; fat 20-35 % of energy;
  * a plan is refused, not softened, if the athlete is under 18, pregnant or breastfeeding, has an eating-disorder history or concern, has a diet-relevant
    medical condition, or (for a cut) has a BMI under 20 or very low body fat.
The numbers are estimates. The weight trend (weight_trend.py) corrects them after 2-3 weeks. Not medical advice.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nutri  # noqa: E402
import nutri_args as na  # noqa: E402

DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    na.add_profile_args(ap)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    p, missing, hours = na.profile_from_args(a)
    if a.save:
        na.save_nutrition({"sex": p["sex"], "body_fat_pct": p["body_fat_pct"], "goal": p["goal"], "rate_pct": p["rate_pct"], "experience": p["experience"],
                           "lifestyle": p["lifestyle"], "gates": p["gates"], "hours_by_day": hours})
    if missing:
        print("STATUS: needs-info\nAsk the athlete for: " + ", ".join(missing) + " (never assume them).")
        return 2
    if hours is None:
        print("STATUS: needs-info\nAsk for training hours per day (Monday to Sunday) or hours per week, and the watch's average kcal per training hour if known.")
        return 2
    r = nutri.plan_targets(p, hours, a.kcal_per_hour, a.weeks)
    if a.json:
        print(json.dumps(r, indent=1, default=str))
        return 0 if r["status"] == "ok" else 2
    if r["status"] != "ok":
        print("STATUS:", r["status"])
        for x in r["reasons"]:
            print(" -", x)
        if r["status"] == "needs-info":
            print("Ask the athlete these questions themselves; do not answer for them.")
        return 2
    print(f"STATUS: ok   goal: {r['goal']}   BMI {r['bmi']}   resting energy (Mifflin-St Jeor) {r['ree']} kcal   estimated maintenance {r['maintenance_avg']} kcal/day on average")
    print(f"Average target {r['avg_target']} kcal/day; protein {r['protein_g_per_kg']} g/kg"
          + (f"; energy availability about {r['energy_availability']} kcal/kg fat-free mass" if r["energy_availability"] else ""))
    print()
    print("Day  Type      Train h  kcal   protein  carb   fat   carb g/kg")
    for d in r["days"]:
        print(f"{DOW[d['dow']]:<4} {d['type']:<9} {d['hours']:<7.2g} {d['E']:<6} {d['P']:<8} {d['C']:<6} {d['F']:<5} {d['cho_gkg']}")
    print()
    for f in r["flags"]:
        print("FLAG:", f)
    for n in r["notes"]:
        print("NOTE:", n)
    print("\nLabels: protein, fat and the cut/bulk rates are research-based (see evidence-map); the activity factor, training energy, day-type carbohydrate mapping and the 25 % cap are "
          "practice; all of it is an estimate to be checked against your weight trend. Not medical advice: a registered sports dietitian is the right person for anything beyond this.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
