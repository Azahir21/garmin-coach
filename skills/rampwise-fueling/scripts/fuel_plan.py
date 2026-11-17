#!/usr/bin/env python3
"""Carbohydrate-per-hour plan for a long session or event, straight from the guideline tiers of Jeukendrup 2014
(Sports Med 44 Suppl 1:S25-33; full text in references/papers/).

Usage:
  fuel_plan.py --hours 7 [--intensity low|moderate|high] [--gut-now 40] [--weeks 6]

Tiers (all from that paper):
  up to ~1 h        mouth rinse or small amounts of carbohydrate
  1-2 h             30-60 g/h (the range the paper attributes to the ACSM guideline)
  2-3 h             up to ~60 g/h of a single carbohydrate source
  2.5 h+ / ultra    up to ~90 g/h, which must be MULTIPLE TRANSPORTABLE carbohydrates (e.g. glucose + fructose)
                    to be absorbed; performance benefit of multiple transportable carbs is mainly seen at 2.5 h or longer
Rules from the same paper: advice is in absolute grams per hour (not per kg of body weight); at low absolute
exercise intensity the amount should be adjusted DOWN (the paper gives no factor, so none is applied here); solid food
and very concentrated drinks reduce fluid absorption; practise the strategy in training (limited human evidence that the
gut adapts, but it is recommended). A multicentre study (Smith et al., 51 cyclists/triathletes, 2-h ride then 20-km
time trial) found performance improved with dose and was greatest at 60-80 g/h.
Intakes of 100-120 g/h: Podlogar and Wallis 2022 (full text) report higher exogenous carbohydrate oxidation at 120 g/h
than at 90 g/h in highly trained athletes, but whether that adds performance is unclear, and they conclude that the
recommended maximum should not be changed from up to 90 g/h at present. This script therefore caps at 90 g/h.
The gut-training ramp is a PRACTICE suggestion (+10 g/h per week), not a published protocol.
"""
import argparse


def tier(hours):
    if hours <= 1.0:
        return "mouth rinse or small amounts", 0, 0, "up to ~1 h"
    if hours <= 2.0:
        return "30-60 g/h", 30, 60, "1-2 h (range attributed to ACSM in the paper)"
    if hours <= 2.5:
        return "up to ~60 g/h (single source is enough)", 45, 60, "2-3 h"
    return "up to ~90 g/h, multiple transportable carbohydrates (glucose + fructose)", 60, 90, "2.5 h+ / ultra"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hours", type=float, required=True, help="expected duration")
    ap.add_argument("--intensity", choices=("low", "moderate", "high"), default="moderate")
    ap.add_argument("--gut-now", type=float, help="g/h you tolerate in training today")
    ap.add_argument("--weeks", type=int, default=6, help="weeks available to practise")
    a = ap.parse_args()

    label, lo, hi, name = tier(a.hours)
    print(f"Duration {a.hours:g} h -> tier '{name}': {label}")
    if hi:
        print(f"Event total at the range: {lo * a.hours:.0f}-{hi * a.hours:.0f} g carbohydrate ({lo}-{hi} g/h x {a.hours:g} h)")
        if a.intensity == "low":
            print("Intensity low: the paper says to adjust DOWNWARD (e.g. a slow 5-h marathoner may not need 90 g/h). "
                  "No factor is published: start at the low end of the range and use appetite and gut comfort.")
        elif a.intensity == "high":
            print("Intensity high: the paper expects carbohydrate use to rise with intensity; the upper part of the range applies, "
                  "if the gut tolerates it.")
        if hi > 60:
            print("Above ~60 g/h the carbohydrate must come from several transportable sources (glucose + fructose); "
                  "one source alone saturates at ~60 g/h.")
    print("Fluid: balance carbohydrate with a fluid plan (see sweat_rate.py); solid food and highly concentrated solutions slow absorption.")

    if a.gut_now is not None and hi and a.gut_now < hi:
        print(f"\nGut-training ramp (practice suggestion, +10 g/h per week on long sessions): you tolerate {a.gut_now:g} g/h, target {hi} g/h")
        cur = a.gut_now
        for w in range(1, a.weeks + 1):
            cur = min(hi, cur + 10)
            print(f"  week {w}: {cur:g} g/h on the long ride/run")
            if cur >= hi:
                break
        if cur < hi:
            print(f"  not reached in {a.weeks} weeks: the target for race day is {cur:g} g/h, not {hi}")


if __name__ == "__main__":
    main()
