#!/usr/bin/env python3
"""Sweat rate and body-weight change for one session (the field method of the ACSM position stand on fluid
replacement, Sawka 2007: weigh before and after; individual sweat rates vary widely, so customised plans are recommended).

Usage:
  sweat_rate.py --pre-kg 70.2 --post-kg 69.1 --fluid-l 0.9 --hours 1.5 [--urine-l 0]

  sweat loss (L) = (pre - post) kg + fluid drunk (L) - urine (L)      [1 kg of body mass ~ 1 L]
  sweat rate (L/h) = sweat loss / hours
  body-mass change (%) = (post - pre) / pre x 100

Reading (from the ACSM abstract that was read): the goal of drinking during exercise is to prevent excessive
(> 2 % body mass lost to a water deficit) dehydration and large electrolyte changes. Gaining weight during a session
means you drank more than you sweated; do not try to "drink ahead" of losses. NOTE: the 2015 consensus statement on
exercise-associated hyponatraemia was found in PubMed without an abstract, so no sodium numbers are given here;
get sweat-sodium advice from a sports dietitian or a sweat test.
Weigh nude or in the same dry clothing, after towelling off, and note temperature and intensity: the rate only applies to similar conditions.
"""
import argparse


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pre-kg", type=float, required=True)
    ap.add_argument("--post-kg", type=float, required=True)
    ap.add_argument("--fluid-l", type=float, default=0.0, help="fluid drunk during the session")
    ap.add_argument("--urine-l", type=float, default=0.0)
    ap.add_argument("--hours", type=float, required=True)
    a = ap.parse_args()

    loss = (a.pre_kg - a.post_kg) + a.fluid_l - a.urine_l
    rate = loss / a.hours
    change = (a.post_kg - a.pre_kg) / a.pre_kg * 100
    print(f"sweat loss {loss:.2f} L over {a.hours:g} h -> sweat rate {rate:.2f} L/h")
    print(f"body-mass change {change:+.1f} % (fluid drunk {a.fluid_l:g} L)")
    if change <= -2.0:
        print("NOTE: lost 2 % or more of body mass: the ACSM stand aims to prevent this level of water deficit; plan to drink more in similar conditions.")
    elif change > 0:
        print("NOTE: body mass went UP: you drank more than you sweated. Drink less next time in similar conditions.")
    else:
        print("OK: within the < 2 % loss the ACSM stand aims for.")
    print(f"This rate applies to similar intensity and weather only. Repeat in hot and cool sessions to see your range; "
          f"customised plans are the ACSM recommendation because sweat rates vary widely between people.")


if __name__ == "__main__":
    main()
