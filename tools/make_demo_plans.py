#!/usr/bin/env python3
"""Build the public demo plans (docs/races/*.html plus .ics and .csv downloads) for every event, from a SYNTHETIC athlete (no personal data).

  python tools/make_demo_plans.py
"""
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for sub in ("rampwise", "rampwise-planner", "rampwise-report", "rampwise-strength"):
    sys.path.insert(0, str(ROOT / "skills" / sub / "scripts"))
import event_plan as ep  # noqa: E402
import export_plan as ex  # noqa: E402
import plan_viewer as pv  # noqa: E402

ATHLETE = {"equipment": {"tags": ["bodyweight", "dumbbell", "band", "step"]}, "preferences": {"cardio_start": "06:30", "strength_start": "18:30"}}
# event -> (race date, hours now, max hours, longest run/ride/swim minutes now); dates are examples, every plan is built for the dates you give
DEMOS = {
    "5k": ("2027-10-10", 3, 5, (30, 45, 20)), "10k": ("2027-10-10", 4, 6, (45, 60, 20)), "half": ("2027-10-10", 5, 7, (60, 75, 20)),
    "marathon": ("2027-10-10", 6, 9, (75, 90, 20)), "ultra-50k": ("2027-10-10", 7, 10, (90, 120, 20)),
    "sprint-tri": ("2027-10-10", 4, 6, (35, 60, 20)), "olympic-tri": ("2027-10-10", 6, 9, (50, 90, 30)),
    "70.3": ("2027-10-10", 8, 11, (70, 120, 35)), "ironman": ("2027-10-10", 10, 14, (90, 150, 40)),
    "duathlon-sprint": ("x", 4, 6, (40, 60, 20)), "duathlon-standard": ("x", 6, 8.5, (60, 90, 20)),
    "gran-fondo": ("x", 4.5, 7.5, (40, 120, 20)), "century": ("x", 5.5, 9, (40, 150, 20)), "ultra-ride": ("x", 7, 12, (40, 210, 20)),
    "swim-1500": ("x", 3, 5, (30, 45, 35)), "swim-5k": ("x", 5, 8, (30, 45, 60)), "swim-10k": ("x", 7, 10, (30, 45, 90)),
}
TAGS = {"tri": ("TRIATHLON", "tri"), "du": ("DUATHLON", "du"), "run": ("RUNNING", "run"), "bike": ("CYCLING", "bike"), "swim": ("SWIMMING", "swim")}
ORDER = ["tri", "du", "run", "bike", "swim"]


def gallery(index):
    cards = []
    for kind in ORDER:
        for e in [x for x in index if x["kind"] == kind]:
            tag, cls = TAGS[kind]
            peak = f"{e['peak_hours']:g}"
            cards.append(f'    <div class="card plan {cls}"><div class="bar"></div><span class="tag {cls}">{tag}</span><h3><a class="stretch" href="races/{e["key"]}.html">{e["label"]}</a></h3>'
                         f'<p class="meta">{e["weeks"]} weeks · peak about {peak} h/week</p><p class="dl"><a href="races/{e["key"]}/plan.ics">.ics</a> · <a href="races/{e["key"]}/plan.csv">.csv</a></p></div>')
    return "\n".join(cards)
INTRO = {"intermediate": "Example plan for a runner or triathlete at intermediate level, built from made-up numbers. Give your own numbers to get your own plan."}


def main():
    out = ROOT / "docs" / "races"
    out.mkdir(parents=True, exist_ok=True)
    index = []
    start = date(2026, 11, 23)                  # a Monday
    for key, (_, hours, mx, (lr, lb, ls)) in DEMOS.items():
        lo, hi = ep.EVENTS[key]["weeks"]
        race = start + timedelta(weeks=(lo + hi) // 2 - 1, days=6)     # a Sunday, a usual number of weeks away
        for _ in range(10):                       # made-up longest sessions, raised until they are consistent with the weekly hours (no shortfall warning)
            meta, sess = ep.build(key, race, start, "intermediate", hours, mx, 6, {"longest_run_min": lr, "longest_ride_min": lb, "longest_swim_min": ls}, ATHLETE)
            if not any(w.startswith("Week 1 plans") for w in meta["warnings"]):
                break
            lr, lb, ls = lr * 1.12, lb * 1.12, ls * 1.05
        title = f"{ep.EVENTS[key]['label']}: {meta['weeks']}-week example plan"
        html = pv.render(meta, sess, title, footer_extra="This page is an example built from made-up numbers.")
        (out / f"{key}.html").write_text(html, encoding="utf-8")
        d = out / key
        d.mkdir(exist_ok=True)
        (d / "plan.ics").write_text(ex.to_ics(meta, sess), encoding="utf-8", newline="")
        ex.to_csv(d / "plan.csv", sess)
        index.append({"key": key, "label": ep.EVENTS[key]["label"], "kind": ep.EVENTS[key]["kind"], "weeks": meta["weeks"], "peak_hours": meta["peak_hours"], "sessions": len(sess)})
        print(f"{key:12} {meta['weeks']:2} weeks  peak {meta['peak_hours']:>4} h  {len(sess)} sessions")
    (out / "index.json").write_text(json.dumps(index, indent=1), encoding="utf-8")
    page = ROOT / "docs" / "index.html"
    html = page.read_text(encoding="utf-8")
    new = re.sub(r"<!--PLANS-->.*?<!--/PLANS-->", lambda m: "<!--PLANS-->\n" + gallery(index) + "\n    <!--/PLANS-->", html, flags=re.S)
    page.write_text(new, encoding="utf-8")
    import brand_pages                              # logo favicon on every page, also after regenerating
    brand_pages.run()


if __name__ == "__main__":
    main()
