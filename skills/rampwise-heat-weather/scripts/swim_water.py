#!/usr/bin/env python3
"""Open-water swimming: guidance bands for a water temperature, from the review by Tipton, Tipton and Bradford 2014 (Extreme Physiology and Medicine 3:12, full text read).

  swim_water.py --temp-c 14 [--km 1.5] [--json]

These are GUIDANCE numbers quoted in that review (British Triathlon rules, the FINA/ITU/IOC upper limit), not proven safe limits: the authors say the evidence base is limited and
virtually absent for warm water. Local rules and event organisers come first. Never swim open water alone; do not trust how warm or cold you feel (acclimatisation hides the body's state).
"""
import argparse
import json


def bands(t, km=None, wetsuit=None):
    out = []
    if t < 11:
        out.append(("stop", "Below 11 C: British Triathlon guidance (quoted by Tipton 2014) recommends no open-water swimming."))
    elif t < 14:
        cap = 500 if t < 12 else 1000 if t < 13 else 2000
        out.append(("caution", f"11-14 C: the quoted UK limit at this temperature is about {cap} m, and a wetsuit is needed (wetsuits are optional only from 14 C)."))
    if 10 <= t <= 15:
        out.append(("caution", "10-15 C is where the cold-shock response peaks (gasping, uncontrolled breathing, fast heart rate); get in slowly, breathe calmly, stay close to the edge for the first minutes."))
    if t < 25:
        out.append(("info", "Below about 25 C swimming cools the body faster than lying still: the longer and slower the swim, the more you cool."))
    if 25 <= t <= 31:
        out.append(("info", "25-31 C: inside the FINA/ITU/IOC guideline (31 C upper limit). Long hard swims still add heat; sun can add up to 1,000 W per square metre."))
    if t > 31:
        out.append(("stop", "Above 31 C: over the FINA/ITU/IOC upper limit guideline for open-water swimming. In water around 32 C long hard swims risk 'insidious hyperthermia' because it feels comfortable."))
    if km:
        m = km * 1000
        if m < 1500:
            lo, hi = 14, 22
        elif m <= 3000:
            lo, hi = 15, 23
        elif m <= 4000:
            lo, hi = 16, 24
        else:
            lo, hi = None, None
        if lo is not None:
            if t < lo:
                out.append(("caution", f"For a {km:g} km swim the quoted UK rules make a wetsuit mandatory below {lo} C."))
            elif t > hi:
                out.append(("info", f"For a {km:g} km swim the quoted UK rules forbid a wetsuit above {hi} C (heat)."))
    out.append(("always", "Always: swim with someone or a safety buoy, expect most problems in the first 400 m, avoid crowding and breath-holding at the start, get out if you shiver hard, lose control of breathing or feel dizzy. Cardiac problems are thought to cause most deaths in events."))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--temp-c", type=float, required=True)
    ap.add_argument("--km", type=float)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    b = bands(a.temp_c, a.km)
    if a.json:
        print(json.dumps([{"level": l, "text": t} for l, t in b], ensure_ascii=False))
        return
    print(f"Water {a.temp_c:g} C" + (f", swim {a.km:g} km" if a.km else "") + ":")
    for level, text in b:
        print(f"  [{level}] {text}")
    print("Evidence: review (Tipton 2014), authors call the evidence for these limits weak. Local rules and organisers first. Not medical advice.")


if __name__ == "__main__":
    main()
