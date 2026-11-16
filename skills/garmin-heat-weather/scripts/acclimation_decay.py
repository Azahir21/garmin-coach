#!/usr/bin/env python3
"""How much heat acclimation is left after a break? (Daanen 2018, Sports Med, systematic review + meta-analysis.)

Usage:
  acclimation_decay.py --days-since-heat 14

From the abstract/full text of Daanen, Racinais, Periard 2018 (12 studies; heat acclimation of at least 5 days, decay of
at least 7 days): decay is expressed as % of the adaptation lost (0 % = still acclimated, 100 % = back to unacclimated).
Without heat exposure, the end-exercise heart-rate adaptation decayed by 2.3 % per day and the core-temperature adaptation
by 2.6 % per day. Core-temperature adaptations lasted longer when the daily heat exposure had been longer and less intense.
Earlier literature suggested about 1 day of acclimation lost per 2 days of decay.

This script applies the per-day rates linearly. That is a simplification: the rate depends on how the acclimation
was built, it was estimated from studies of roughly 1-5 weeks of decay, and individual differences are large.
Re-acclimation (Daanen 2018 also covers it) is usually faster than the first acclimation; details are in the full text.
Use it for planning ("a week off in the cool: most of it is still there"), never as a measurement.
"""
import argparse

HR_PER_DAY, TC_PER_DAY = 2.3, 2.6


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days-since-heat", type=float, required=True)
    a = ap.parse_args()
    d = a.days_since_heat
    hr_left = max(0.0, 100 - HR_PER_DAY * d)
    tc_left = max(0.0, 100 - TC_PER_DAY * d)
    print(f"{d:g} days without heat exposure:")
    print(f"  heart-rate adaptation remaining: about {hr_left:.0f} % ({HR_PER_DAY} %/day lost, Daanen 2018)")
    print(f"  core-temperature adaptation remaining: about {tc_left:.0f} % ({TC_PER_DAY} %/day lost)")
    print(f"  older rule of thumb: about {d / 2:.0f} day(s) of acclimation lost")
    if d > 35:
        print("  beyond the span the studies covered; assume little is left")
    print("Racinais 2015 consensus: acclimatise with repeated exercise-heat exposures over 1-2 weeks.")


if __name__ == "__main__":
    main()
