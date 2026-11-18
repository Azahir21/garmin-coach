#!/usr/bin/env python3
"""A race-day fuelling timeline with clock times: the days before, the pre-race meal, the hour before the start, what to take and when during the race, and recovery.

  race_day.py --start 06:30 --hours 5.5 --weight-kg 85 --gut-now 60 [--wake 04:30] [--next-hours 24] [--interval 15] [--out race-day.md]

Every step says where it comes from. What the sources read here support (details in ../references/evidence-map.md):
  * for hard efforts over about 90 minutes: a brief taper with at least 8 g carbohydrate per kg per day beforehand, a main meal rich in carbohydrate in the hours
    before (1-4 g/kg; one study fed 4 h before), and carbohydrate during the effort (Kerksick 2017, ISSN nutrient timing; Jeukendrup 2014 for the g/h by duration);
  * food 60 minutes or more before the start did not hurt performance in the studies reviewed; carbohydrate in the last hour can drop blood sugar in some athletes
    ("rebound"), which a warm-up reduces and taking it closer to the start (15 min versus 75 min) reduces further (Kerksick 2017);
  * carbohydrate during the effort is taken at regular intervals, about every 10-15 minutes in the studies reviewed (Kerksick 2017);
  * afterwards, if the next hard session is less than 4 h away: 1.2 g/kg/h carbohydrate, or 0.8 g/kg/h with 0.2-0.4 g/kg/h protein (Kerksick 2017).
NO source read says how many minutes a late meal or gel takes to give a "boost", and none says to wait: the safe reading is to eat the main meal early, keep the last hour
simple, and start taking carbohydrate in the race early rather than late. The start-early timing (first intake after 10-15 min) and the 2 g/kg default meal are PRACTICE.
No sodium numbers (none read). Practise the whole plan in a long training session first. Not medical advice.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fuel_plan  # noqa: E402


def hm(s):
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def clock(mins):
    mins = int(round(mins)) % (24 * 60)
    return f"{mins // 60:02d}:{mins % 60:02d}"


def plan(start, hours, kg, gut_now=None, wake=None, next_hours=None, interval=15, intensity="high"):
    """Pure function: returns a list of {"time": "HH:MM", "label": ..., "detail": ..., "source": ...} in order, plus notes."""
    s = hm(start) if isinstance(start, str) else start
    steps, notes = [], []
    long_hard = hours >= 1.5
    label, lo, hi, tname = fuel_plan.tier(hours)
    if long_hard:
        steps.append({"time": "2-3 days before", "label": "Taper and load carbohydrate", "detail": f"Reduce training and eat at least 8 g/kg/day carbohydrate (about {8 * kg:.0f} g/day for {kg:g} kg); familiar foods only; do not try anything new.",
                      "source": "Kerksick 2017 (ISSN nutrient timing, full text); the number of days is practice"})
    steps.append({"time": "Evening before", "label": "Normal, familiar dinner", "detail": "Carbohydrate-rich, not too much fibre, fat or alcohol; drink to thirst through the day.", "source": "practice; fibre and fat linked to gut trouble in Jeukendrup 2011 (abstract)"})
    meal_g = 2.0 * kg if long_hard else 1.0 * kg
    meal_at = s - 210 if long_hard else s - 150
    if wake is not None:
        w = hm(wake) if isinstance(wake, str) else wake
        if w + 15 > meal_at:
            meal_at = w + 15
            meal_g = max(1.0 * kg, 1.0 * kg)
            notes.append(f"You wake at {clock(w)}, later than the usual 3-4 h before the start: eat as soon as you can stomach it, make it smaller ({meal_g:.0f} g carbohydrate) and consider a liquid or soft carbohydrate (solid and liquid carbohydrate restored glycogen similarly in the studies reviewed, Kerksick 2017), and begin race fuelling a little earlier.")
    steps.append({"time": clock(meal_at), "label": "Main pre-race meal", "detail": f"About {meal_g:.0f} g carbohydrate ({meal_g / kg:.1f} g/kg; the range in the source is 1-4 g/kg), low in fat, fibre and protein: rice, white bread, oats, banana, noodles, a little jam or honey; fluids with it.",
                  "source": "Kerksick 2017 (1-4 g/kg in the hours before; a meal 4 h before raised glycogen and use in one study); the 2 g/kg default and low-fat/fibre advice are practice"})
    steps.append({"time": clock(s - 120), "label": "Sip fluids", "detail": "Start drinking small amounts; stop forcing fluids an hour out. Aim to start hydrated, not over-hydrated.", "source": "ACSM 2007 (abstract): start euhydrated"})
    steps.append({"time": clock(s - 60), "label": "Last solid food by here", "detail": "Anything solid should be finished by 60 minutes before the start. Studies feeding carbohydrate 60 minutes or more before exercise found no harm.",
                  "source": "Kerksick 2017 (cites Hawley and Burke 1997 review)"})
    if long_hard:
        steps.append({"time": clock(s - 15), "label": "Optional: 15-30 g quick carbohydrate", "detail": "Only if you have tried it in training. A small amount of carbohydrate close to the start is less likely to cause a blood-sugar dip than a larger one 30-75 minutes out; a warm-up also reduces the effect.",
                      "source": "Kerksick 2017 (rebound hypoglycaemia is individual; 15 min versus 75 min; warm-up); the 15-30 g amount is practice"})
    # in-race
    if hi:
        g_h = hi
        if gut_now is not None:
            g_h = min(hi, max(lo, gut_now))
            if gut_now < lo:
                notes.append(f"You tolerate {gut_now:g} g/h in training, below the {lo}-{hi} g/h range for {hours:g} h: plan {g_h:g} g/h and expect to fall short; a gut-training ramp in training weeks helps (fuel_plan.py).")
        else:
            g_h = lo
            notes.append(f"Gut tolerance in training not given, so the low end of the range ({lo} g/h) is planned. Never raise the amount on race day beyond what you have practised.")
        per = g_h * interval / 60.0
        t = 15
        n = 0
        while t < hours * 60 - 5 and n < 40:
            n += 1
            if n == 1:
                steps.append({"time": clock(s + t), "label": f"Start fuelling (minute {t})", "detail": f"Take about {per:.0f} g carbohydrate now, then every {interval} min (about {g_h:g} g/h). Do not wait until you feel empty: begin early.",
                              "source": f"Jeukendrup 2014 tier '{tname}': {label}; interval 10-15 min in Kerksick 2017; the minute-15 start is practice"})
            t += interval
        steps.append({"time": f"{clock(s + 15)} to the finish", "label": "Repeat", "detail": f"About {per:.0f} g every {interval} min. Above 60 g/h use more than one carbohydrate type (glucose plus fructose). Total for the race about {g_h * hours:.0f} g.", "source": "Jeukendrup 2014; Podlogar and Wallis 2022 (cap 90 g/h)"})
    else:
        steps.append({"time": clock(s), "label": "During", "detail": "Under about an hour: water; a mouth rinse or small amounts of carbohydrate can help in a hard effort.", "source": "Jeukendrup 2014"})
    steps.append({"time": clock(s + 15), "label": "Fluids", "detail": "Drink to a plan from your own sweat rate (sweat_rate.py): the target is to stay under about 2 % body-mass loss and not to over-drink. No sodium number is given here (none read).", "source": "ACSM 2007 (abstract); Jeukendrup 2011"})
    end = s + hours * 60
    if next_hours is not None and next_hours < 4:
        steps.append({"time": clock(end), "label": "Recovery fuelling (next hard session under 4 h away)", "detail": f"Carbohydrate 1.2 g/kg/h ({1.2 * kg:.0f} g/h) for the first hours, or 0.8 g/kg/h ({0.8 * kg:.0f} g/h) with protein 0.2-0.4 g/kg/h ({0.2 * kg:.0f}-{0.4 * kg:.0f} g/h).", "source": "Kerksick 2017"})
    else:
        steps.append({"time": clock(end), "label": "Recovery meal", "detail": f"Within about 2 hours: a carbohydrate-rich meal with protein 0.25-0.4 g/kg ({0.25 * kg:.0f}-{0.4 * kg:.0f} g), and fluids to replace the loss.", "source": "Kerksick 2017 (0.25-0.40 g/kg protein per dose, post-exercise intake within 2 h); carbohydrate amount follows the day's target in nutrition_targets.py"})
    def rel(step):
        t = step["time"]
        if len(t) >= 5 and t[2] == ":" and t[:2].isdigit():
            r = (hm(t[:5]) - s) % 1440
            return (1, r - 1440 if r > 1440 - 12 * 60 else r)
        return (0, 0)

    steps.sort(key=rel)           # stable: the "days before" lines stay first, clock times follow in order
    return steps, notes


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--start", required=True, help="race start, HH:MM (24 h)")
    ap.add_argument("--hours", type=float, required=True, help="expected race duration in hours")
    ap.add_argument("--weight-kg", type=float, required=True)
    ap.add_argument("--gut-now", type=float, help="g/h of carbohydrate you tolerate in long training today")
    ap.add_argument("--wake", help="when you will wake up on race morning, HH:MM")
    ap.add_argument("--next-hours", type=float, help="hours until your next hard session after the race")
    ap.add_argument("--interval", type=int, default=15, help="minutes between intakes (10-20)")
    ap.add_argument("--out", help="also write the timeline to this Markdown file")
    a = ap.parse_args(argv)
    steps, notes = plan(a.start, a.hours, a.weight_kg, a.gut_now, a.wake, a.next_hours, a.interval)
    lines = [f"Race-day fuelling plan: start {a.start}, about {a.hours:g} h, {a.weight_kg:g} kg", ""]
    for s in steps:
        lines.append(f"{s['time']:<16} {s['label']}")
        lines.append(f"{'':<16} {s['detail']}")
        lines.append(f"{'':<16} Source/label: {s['source']}")
    lines.append("")
    for n in notes:
        lines.append("NOTE: " + n)
    lines.append("NOTE: No source read gives a delay between a late meal or gel and a 'boost'; the supported advice is early main meal, simple last hour, early and regular carbohydrate in the race. Practise this exact plan in training.")
    print("\n".join(lines))
    if a.out:
        Path(a.out).write_text("# " + lines[0] + "\n\n" + "\n".join(f"- **{s['time']}** {s['label']}: {s['detail']} _({s['source']})_" for s in steps) + "\n\n" + "\n".join("- " + n for n in notes) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
