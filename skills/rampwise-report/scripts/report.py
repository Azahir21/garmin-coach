#!/usr/bin/env python3
"""Daily, weekly and monthly training reports: Markdown with figures, and an interactive single-file HTML page.

  report.py daily|weekly|monthly [--date YYYY-MM-DD] [--format md|html|both] [--out DIR] [--no-deep] [--no-adapt]

Output folder (default <output folder>/reports/<date>-<mode>/, normally ~/rampwise-coach; --here uses ./rampwise-coach): report.md, figures/*.svg, report.html (all inline, no network, works offline; period buttons
and hover tooltips, light and dark mode), and reports/latest-<mode>.html. Everything comes from your own Garmin data, your plan and athlete.json:
week-over-week comparison, recovery, injury-risk watch, plan adherence, goal meters (baseline, now, target; a distance, never a forecast), strength logs,
and tomorrow's adapted session. Goals and units follow the user's settings (preferences.units: run "pace" or "kmh", bike "kmh"); no goals set = no meters.
"""
import argparse
import json
import re
import subprocess
import sys
from datetime import date, datetime, timedelta
from html import escape
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILLS = HERE.parent.parent
for sub in ("rampwise", "rampwise-planner", "rampwise-strength", "rampwise-recovery", "rampwise-analyze", "rampwise-adapt", "rampwise-aerobic-base"):
    sys.path.insert(0, str(SKILLS / sub / "scripts"))
sys.path.insert(0, str(HERE))
import gcommon as gc  # noqa: E402
import analysis  # noqa: E402
import charts as ch  # noqa: E402
import report_data as rd  # noqa: E402

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
LABELS = {"avg_hr": "average heart rate (bpm)", "climb_m": "climb (m)", "speed_kmh": "speed (km/h)", "minutes": "minutes", "km": "distance (km)"}
DISCLAIMER = "Data from Garmin devices, read from your own account; not affiliated with Garmin Ltd. Not medical advice. Risk flags come from your data and your own reports; watch data cannot see an injury. Pain that changes how you move or lasts more than a few days needs a clinician. Evidence labels: research = a paper supports the direction; practice = a convention; gap = nothing read supports it."


# ---------------------------------------------------------------- building blocks
def pace_fmt(sec):
    return rd.mmss(sec)


def variants_weekly(fn, series_len, periods=((4, "4 weeks"), (8, "8 weeks"), (12, "12 weeks"))):
    """Chart variants for the last N weeks. fn(n) -> svg for the last n weeks of the series."""
    return {label: fn(min(n, series_len)) for n, label in periods if n <= series_len or n == periods[0][0]}


def tail(v, n):
    return v[-n:]


def flags_block(inj):
    return ("flags", inj)


def summary_points(cmp, inj, ready, units):
    pts = []
    if ready and ready.get("verdict"):
        pts.append(f"Readiness today is {ready['verdict']}" + (": " + "; ".join(f[1] for f in ready.get("flags", [])[:2]) if ready.get("flags") else "") + ".")
    pts.append(f"Injury-risk watch: {inj['level']} ({len(inj['flags'])} signals).")
    pts += cmp["insights"][:5]
    return pts


def build(mode, today, acts, rows, ath, plan, hist, ready, inj, cmp, adapt, latest=None, units=None):
    units = units or (ath.get("preferences") or {}).get("units") or {"run": "pace", "bike": "kmh"}
    n_weeks = 12 if mode == "monthly" else 8
    ws = rd.weekly_series(acts, rows, today, 12)
    days14, days28 = rd.day_list(today, 14), rd.day_list(today, 28)
    blocks, figs = [], {}
    title = {"daily": f"Daily report: {today:%A %d %B %Y}", "weekly": f"Weekly report: week ending {today:%d %B %Y}", "monthly": f"Monthly report: {today:%B %Y}"}[mode]

    def chart(key, ttl, caption, variants, default):
        figs[key] = {"title": ttl, "caption": caption, "variants": variants, "default": default}
        blocks.append(("chart", key))

    def weekly_chart(key, ttl, caption, builder, default="8 weeks", **kw):
        chart(key, ttl, caption, {label: builder(n) for n, label in ((4, "4 weeks"), (8, "8 weeks"), (12, "12 weeks"))}, default)

    blocks.append(("h1", title))
    blocks.append(("p", f"Generated {datetime.now():%Y-%m-%d %H:%M} from your own Garmin data. Units: running {'pace (min/km)' if units.get('run', 'pace') == 'pace' else 'km/h'}, cycling km/h."))
    blocks.append(("h2", "What stands out"))
    cmp.setdefault("insights", analysis.insights(cmp, units))
    blocks.append(("ul", summary_points(cmp, inj, ready, units)))

    # ---- recovery
    if mode in ("daily", "weekly", "monthly"):
        blocks.append(("h2", "Recovery"))
        if ready and ready.get("hrv") is not None:
            blocks.append(("table", ["Signal", "Today", "7-day", "Normal band / note"], [
                ["HRV (ms)", ready.get("hrv"), ready.get("hrv7"), f"{ready.get('band_lo')} to {ready.get('band_hi')} ({ready.get('hrv_state')})"],
                ["Resting HR (bpm)", ready.get("rhr"), ready.get("rhr7"), "lower is calmer"],
                ["Sleep last night (h)", ready.get("sleep_h"), "", "under 6 h counts as short"]]))
        rec = rd.recovery_daily(rows, days28 if mode != "daily" else days14)
        labs = [f"{d.day}" for d in (days28 if mode != "daily" else days14)]
        band = (ready.get("band_lo"), ready.get("band_hi")) if ready and ready.get("band_lo") else None
        chart("recovery_hrv", "Heart-rate variability (nightly, ms)", "Shaded = your normal band. A 7-day mean below the band for several days means recovery is low.",
              {"14 days": ch.lines(labs[-14:], [("HRV", tail(rec["hrv"], 14), "s0")], "HRV, last 14 days", "ms", band=band, dec=0), "28 days": ch.lines(labs, [("HRV", rec["hrv"], "s0")], "HRV, last 28 days", "ms", band=band, dec=0)}, "14 days")
        chart("recovery_rhr_sleep", "Resting heart rate and sleep", "Resting heart rate (bpm) and sleep (hours) per night.",
              {"14 days": ch.lines(labs[-14:], [("Resting HR", tail(rec["rhr"], 14), "s0")], "Resting heart rate, last 14 days", "bpm", dec=0),
               "28 days": ch.lines(labs, [("Resting HR", rec["rhr"], "s0")], "Resting heart rate, last 28 days", "bpm", dec=0)}, "14 days")
        chart("recovery_sleep", "Sleep per night", "Hours of sleep recorded by the watch.",
              {"14 days": ch.bars(labs[-14:], [("Sleep", [round(x, 1) if x else 0 for x in tail(rec["sleep_h"], 14)], "s0")], "Sleep, last 14 days", "h", stacked=True, dec=1),
               "28 days": ch.bars(labs, [("Sleep", [round(x, 1) if x else 0 for x in rec["sleep_h"]], "s0")], "Sleep, last 28 days", "h", stacked=True, dec=1)}, "14 days")

    # ---- injury watch
    blocks.append(("h2", "Injury-risk watch"))
    blocks.append(("flags", inj))

    # ---- week over week
    blocks.append(("h2", "This week against last week"))
    cr = cmp["rolling"]
    rows_t = []
    for sport, lab in (("run", "Running"), ("bike", "Cycling"), ("swim", "Swimming"), ("strength", "Strength")):
        if sport == "swim" and not (cr["this"]["swim"]["sessions"] or cr["before"]["swim"]["sessions"]):
            continue
        a, b, d = cr["this"][sport], cr["before"][sport], cr["delta"][sport]
        key = "minutes" if sport != "strength" else "sessions"
        pct = f"{d['minutes' if sport != 'strength' else 'sessions']['pct']:+.0f} %" if d[key]["pct"] is not None else (f"{d[key]['abs']:+g}" if d[key]["abs"] is not None else "-")
        swim_pace = (lambda v: (rd.mmss(360.0 / v) + "/100 m") if v else "-")
        sp_a = (rd.mmss(rd.pace_s(a["avg_speed_kmh"])) + "/km") if sport == "run" and a["avg_speed_kmh"] and units.get("run", "pace") == "pace" else (f"{a['avg_speed_kmh']} km/h" if a["avg_speed_kmh"] else "-")
        sp_b = (rd.mmss(rd.pace_s(b["avg_speed_kmh"])) + "/km") if sport == "run" and b["avg_speed_kmh"] and units.get("run", "pace") == "pace" else (f"{b['avg_speed_kmh']} km/h" if b["avg_speed_kmh"] else "-")
        if sport == "swim":
            sp_a, sp_b = swim_pace(a["avg_speed_kmh"]), swim_pace(b["avg_speed_kmh"])
        rows_t.append([lab, f"{a[key]} {'min' if key == 'minutes' else 'session' + ('' if a[key] == 1 else 's')}", f"{b[key]} {'min' if key == 'minutes' else 'session' + ('' if b[key] == 1 else 's')}", pct, f"{a['km']} / {b['km']} km" if sport != "strength" else "-", f"{sp_a} / {sp_b}" if sport != "strength" else "-"])
    blocks.append(("p", f"Last 7 days ({cr['this']['from']} to {cr['this']['to']}) against the 7 days before ({cr['before']['from']} to {cr['before']['to']}). Works whether or not there was an activity today."))
    blocks.append(("table", ["Sport", "Last 7 days", "Before", "Change", "km now / before", "Pace or speed now / before"], rows_t))
    if (today - analysis.week_start(today)).days >= 2:
        cs = cmp["calendar_same_days"]
        blocks.append(("p", f"Calendar week so far ({cs['this']['from']} to {cs['this']['to']}): {cs['this']['endurance_minutes']} run + ride minutes against {cs['before']['endurance_minutes']} on the same days last week."))
    else:
        blocks.append(("p", "Calendar-week comparisons start on Wednesday; the rolling comparison above always works."))
    blocks.append(("ul", cmp["insights"]))
    labs14 = [f"{d.day}" for d in days14]
    dm = rd.daily_minutes(acts, days14)
    pl14, dn14 = rd.plan_vs_done(plan, acts, days14)
    chart("daily_minutes", "Minutes per day by sport", "Stacked by sport. Rest days are empty columns.",
          {"14 days": ch.bars(labs14, [("Run", dm["run"], "s1"), ("Ride", dm["bike"], "s2")] + ([("Swim", dm["swim"], "s4")] if any(dm["swim"]) else []) + [("Strength", dm["strength"], "s3")], "Minutes per day, last 14 days", "min"),
           "28 days": ch.bars([f"{d.day}" for d in days28], [("Run", rd.daily_minutes(acts, days28)["run"], "s1"), ("Ride", rd.daily_minutes(acts, days28)["bike"], "s2")] + ([("Swim", rd.daily_minutes(acts, days28)["swim"], "s4")] if any(rd.daily_minutes(acts, days28)["swim"]) else []) + [("Strength", rd.daily_minutes(acts, days28)["strength"], "s3")], "Minutes per day, last 28 days", "min", tick_every=2)}, "14 days")

    # ---- the latest activity (daily) and tomorrow
    if mode == "daily":
        blocks.append(("h2", "Latest activity"))
        if latest and latest.get("activity"):
            t = latest["activity"]
            blocks.append(("p", f"{t['date']}: {t['name']} ({t['sport']}), {t['minutes']} min, {t['km']} km, average heart rate {t['avg_hr']}."))
            if latest.get("compare_with"):
                tab = latest["compare_with"]["table"]
                blocks.append(("p", f"Against the last similar activity ({latest['compare_with']['name']}):"))
                blocks.append(("table", ["", "This one", "Last similar"], [[LABELS.get(k, k.replace("_", " ")), v[0], v[1]] for k, v in tab.items()]))
            ae = latest.get("aerobic")
            if ae and not ae.get("error"):
                keys = [(k, ae[k]) for k in ("ef", "decoupling_pct", "reliable") if k in ae]
                if keys:
                    blocks.append(("p", "Aerobic analysis: " + ", ".join(f"{k.replace('_', ' ')} {v}" for k, v in keys) + ". Compare only with your own similar sessions in similar weather."))
        else:
            blocks.append(("p", "No activity in the last 3 days."))
    if adapt and adapt.get("days"):
        blocks.append(("h2", "Tomorrow, adapted to how you are doing" if mode == "daily" else "Next session, adapted"))
        for e in adapt["days"]:
            blocks.append(("p", f"{e['date']}: {e['original']['title']} ({e['original']['minutes']} min) -> {e['decision'].upper()}" + (" (provisional)" if e.get("provisional") else "")))
            if e["reasons"]:
                blocks.append(("ul", e["reasons"]))
            if e.get("new"):
                blocks.append(("p", f"Instead: {e['new']['title']} ({e['new']['minutes']} min)."))
            if e.get("strength_advice"):
                blocks.append(("p", f"Strength: {e['strength_advice']}."))
        blocks.append(("p", "The coach applies the change to the calendar event after you agree (or when calendar updates are pre-approved)."))

    br, nmulti = rd.brick_rows(acts, today, 28, units.get("run", "pace") == "pace")
    if br or nmulti:
        blocks.append(("h2", "Bricks (bike then run, last 28 days)"))
        if br:
            blocks.append(("table", ["Date", "Bike", "Run", "Run HR", "Gap", "Run against your last normal run"], br))
        if nmulti:
            blocks.append(("p", f"{nmulti} multisport activit{'y' if nmulti == 1 else 'ies'} recorded as one activity (legs are not split here)."))
        blocks.append(("p", "Running straight after cycling costs more energy (Millet and Vleck 2000, abstract; Walsh 2019, full text), so a slower pace or higher heart rate than a normal run is expected; one session proves little (route, weather, effort). Whether brick sessions train anything is unproven, so the plans keep them short and drop them when recovery is low or an injury is active."))
    if mode in ("weekly", "monthly"):
        ra = rd.recent_activities(acts, today, 14, units.get("run", "pace") == "pace")
        blocks.append(("h2", "Recent activities (last 14 days)"))
        if ra:
            blocks.append(("table", ["Date", "Sport", "Time", "km", "Pace / speed", "Avg HR", "Against the last similar one"], ra))
            blocks.append(("p", "Each row is compared with your last earlier session of the same sport and a similar length. Differences also depend on route, weather and what you intended."))
        else:
            blocks.append(("p", "No activities in the last 14 days."))
        # ---- volume
        blocks.append(("h2", "Volume over the weeks"))
        weekly_chart("weekly_minutes", "Minutes per week by sport", "The last column is the week so far. Reset and deload weeks show as dips.",
                     lambda n: ch.bars(tail(ws["labels"], n), [("Run", tail(ws["run_min"], n), "s1"), ("Ride", tail(ws["bike_min"], n), "s2")] + ([("Swim", tail(ws["swim_min"], n), "s4")] if any(ws["swim_min"]) else []), f"Minutes per week by sport, last {n} weeks", "min"), "12 weeks" if mode == "monthly" else "8 weeks")
        if mode == "monthly":
            ds = [today - timedelta(days=i) for i in range(83, -1, -1)]
            mins = [sum(a["min"] for a in acts if a["date"] == d and a["sport"] in ("run", "bike", "swim", "strength")) for d in ds]
            chart("heatmap", "Training days", "Darker = more minutes that day.", {"12 weeks": ch.heatmap(ds, mins, "Training calendar, last 12 weeks")}, "12 weeks")
        # ---- running
        if any(ws["run_min"]):
            blocks.append(("h2", "Running"))
            ps = [rd.pace_s(x) if x else None for x in ws["run_speed"]]
            if units.get("run", "pace") == "pace":
                weekly_chart("run_pace", "Average running pace per week", "Lower is faster. Pace depends on route, weather and the mix of easy and hard runs.",
                             lambda n: ch.lines(tail(ws["labels"], n), [("Pace", tail(ps, n), "s1")], f"Average pace per week, last {n} weeks", "min/km", invert=True, fmt=pace_fmt))
            else:
                weekly_chart("run_pace", "Average running speed per week", "Higher is faster.", lambda n: ch.lines(tail(ws["labels"], n), [("Speed", tail(ws["run_speed"], n), "s1")], f"Average speed per week, last {n} weeks", "km/h", dec=1))
            weekly_chart("run_ef", "Running efficiency (speed per heartbeat)", "Steady runs of 25 minutes or more. Higher = more speed for the same heart rate; heat, hills and illness lower it. Compare with your own history only.",
                         lambda n: ch.lines(tail(ws["labels"], n), [("Efficiency", tail(ws["run_ef"], n), "s1")], f"Run efficiency per week, last {n} weeks", "m/min per bpm", dec=2))
            weekly_chart("longest_run", "Longest run per week", "Long runs should grow gradually: no more than about 10 % over the recent longest.", lambda n: ch.bars(tail(ws["labels"], n), [("Longest run", [x or 0 for x in tail(ws["longest_run_km"], n)], "s1")], f"Longest run per week, last {n} weeks", "km", dec=1))
        # ---- cycling
        if any(ws["bike_min"]):
            blocks.append(("h2", "Cycling"))
            weekly_chart("bike_speed", "Average riding speed per week", "Wind, stops and hills move this; compare similar rides.", lambda n: ch.lines(tail(ws["labels"], n), [("Speed", tail(ws["bike_speed"], n), "s2")], f"Average speed per week, last {n} weeks", "km/h", dec=1))
            weekly_chart("longest_ride", "Longest ride per week", "", lambda n: ch.bars(tail(ws["labels"], n), [("Longest ride", [x or 0 for x in tail(ws["longest_ride_km"], n)], "s2")], f"Longest ride per week, last {n} weeks", "km", dec=1))
        # ---- strength
        sm = rd.strength_summary(hist, today, 12) if hist else None
        if sm or any(ws["strength_sessions"]):
            blocks.append(("h2", "Strength"))
            weekly_chart("strength_sessions", "Strength sessions per week", "", lambda n: ch.bars(tail(ws["labels"], n), [("Sessions", tail(ws["strength_sessions"], n), "s3")], f"Strength sessions per week, last {n} weeks", "sessions"))
            if sm and sm["top_sets"]:
                blocks.append(("p", "Top set per exercise, first logged against latest (weight x reps), from the sets saved on the watch:"))
                blocks.append(("table", ["Exercise", "Sessions", "First", "Latest"], [[r["exercise"], r["sessions"], f"{r['first'][0]}: {r['first'][1]:g} kg x {r['first'][2]}", f"{r['latest'][0]}: {r['latest'][1]:g} kg x {r['latest'][2]}"] for r in sm["top_sets"]]))
        # ---- recovery trend
        blocks.append(("h2", "Recovery trend"))
        weekly_chart("rec_week", "Weekly means: HRV, resting heart rate, sleep", "Average of the nights in each week.",
                     lambda n: ch.lines(tail(ws["labels"], n), [("HRV (ms)", tail(ws["hrv"], n), "s0")], f"Average HRV per week, last {n} weeks", "ms", dec=0))
        weekly_chart("rhr_week", "Resting heart rate per week", "", lambda n: ch.lines(tail(ws["labels"], n), [("Resting HR", tail(ws["rhr"], n), "s0")], f"Average resting heart rate per week, last {n} weeks", "bpm", dec=1))
        # ---- plan adherence
        if plan:
            blocks.append(("h2", "Plan against what was done"))
            done = sum(1 for p, d in zip(pl14, dn14) if p and d >= 0.5 * p)
            planned_days = sum(1 for p in pl14 if p)
            adh = f"{done} of {planned_days} planned days done (at least half the planned minutes)" if planned_days else "no planned sessions in this window"
            blocks.append(("p", f"Last 14 days: {adh}."))
            chart("plan_vs_done", "Planned and done minutes", "Grey = planned in the saved plan, blue = done.", {"14 days": ch.bars(labs14, [("Planned", pl14, "s0"), ("Done", dn14, "s1")], "Planned and done minutes, last 14 days", "min", stacked=False)}, "14 days")

    # ---- goals
    blocks.append(("h2", "Goals"))
    gp = rd.goal_progress(ath, acts, today, 84)
    if not gp:
        blocks.append(("p", "No measurable goal is set yet. Tell the coach a goal (a race time, a ride speed, weekly minutes) and it will be tracked here."))
    for m in gp:
        fmt = (lambda v: rd.mmss(v) + "/km") if m["unit"] == "pace" else (lambda v, u=m["unit"]: f"{v:.1f} {u}".strip())
        figs[f"goal_{re.sub(r'[^a-z0-9]+', '_', m['label'].lower())[:30]}"] = {"title": m["label"], "caption": "", "variants": {"goal": ch.meter(m["label"], m["baseline"], m["now"], m["target"], fmt, m["better"], m["note"])}, "default": "goal"}
        blocks.append(("chart", f"goal_{re.sub(r'[^a-z0-9]+', '_', m['label'].lower())[:30]}"))
    if gp:
        blocks.append(("p", "A meter shows the distance from where you started (the first reading in the last 12 weeks, or your recorded baseline) to the target. It is not a forecast: no paper gives a rate of improvement for one person."))

    # ---- next week
    if plan and mode in ("weekly", "monthly"):
        up = [s for s in plan["sessions"] if str(today) < s["date"] <= str(today + timedelta(days=7))]
        if up:
            blocks.append(("h2", "Coming up (next 7 days of the saved plan)"))
            blocks.append(("table", ["Date", "Session", "Minutes"], [[s["date"], s["title"], s["minutes"]] for s in up]))
    blocks.append(("p", DISCLAIMER))
    return {"mode": mode, "title": title, "today": str(today), "blocks": blocks, "figs": figs}


# ---------------------------------------------------------------- renderers
def md_cell(x):
    return str(x if x is not None else "").replace("|", "/")


def _standalone(svg):
    """Insert the colour tokens into an inline SVG so it renders alone."""
    return svg.replace("</desc>", f"</desc><style>{ch.TOKENS}{ch.CSS}</style>", 1)


def render_md_full(R, outdir):
    """Markdown with real tables (kept separate so the block loop above stays simple)."""
    fig_dir = outdir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    out = []
    for blk in R["blocks"]:
        kind, val = blk[0], (blk[1] if len(blk) == 2 else blk[1:])
        if kind == "h1":
            out.append(f"# {val}\n")
        elif kind == "h2":
            out.append(f"\n## {val}\n")
        elif kind == "p":
            out.append(val + "\n")
        elif kind == "ul":
            out += [f"- {x}" for x in val] + [""]
        elif kind == "table":
            head, rows = val
            out.append("| " + " | ".join(md_cell(h) for h in head) + " |")
            out.append("|" + "|".join("---" for _ in head) + "|")
            out += ["| " + " | ".join(md_cell(c) for c in r) + " |" for r in rows] + [""]
        elif kind == "flags":
            inj = val
            out.append(f"**{inj['level']}**: " + (f"{len(inj['flags'])} signals." if inj["flags"] else "no flags from your load, recovery or your own reports.") + "\n")
            for f in inj["flags"]:
                out.append(f"- **{f['level'].upper()}** {f['text']}  \n  *Evidence:* {f['evidence']}.  \n  *Suggested:* {f['action']}")
            if inj["questions"]:
                out.append("\nQuestions for you:\n" + "\n".join(f"- {q}" for q in inj["questions"]))
            out.append("\n> " + inj["note"] + "\n")
        elif kind == "chart":
            f = R["figs"][val]
            svg = _standalone(f["variants"][f["default"]])
            (fig_dir / f"{val}.svg").write_text(svg, encoding="utf-8")
            out.append(f"![{f['title']}](figures/{val}.svg)\n" + (f"*{f['caption']}*\n" if f["caption"] else ""))
    return "\n".join(out) + "\n"


HTML_CSS = """:root{color-scheme:light dark;--page:#f4f4f1;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--muted:#898781;--grid:#e1e0d9;--axis:#c3c2b7;--border:rgba(11,11,11,.08);--s1:#2a78d6;--s2:#eb6834;--s3:#1baf7a;--s4:#7c5cd6;--all:#898781;--track:#cde2fb;--good:#0ca30c;--warn:#fab219;--crit:#d03b3b;--band:rgba(42,120,214,.12)}
@media (prefers-color-scheme:dark){:root{--page:#0d0d0d;--surface:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--grid:#2c2c2a;--axis:#383835;--border:rgba(255,255,255,.08);--s1:#3987e5;--s2:#d95926;--s3:#199e70;--s4:#9b82e8;--track:#184f95;--band:rgba(57,135,229,.18)}}
*{box-sizing:border-box}body{margin:0;background:var(--page);color:var(--ink);font:16px/1.55 system-ui,-apple-system,Segoe UI,sans-serif}main{max-width:860px;margin:0 auto;padding:20px 16px 60px}
h1{font-size:1.6rem;margin:.2em 0}h2{font-size:1.15rem;margin:0;padding:14px 0 6px}details{background:var(--surface);border:1px solid var(--border);border-radius:14px;margin:14px 0;padding:0 16px}summary{cursor:pointer;font-weight:650;font-size:1.1rem;padding:14px 0;list-style:none}summary::-webkit-details-marker{display:none}summary::after{content:"+";float:right;color:var(--muted)}details[open] summary::after{content:"-"}
.lede{color:var(--ink2)}table{border-collapse:collapse;width:100%;margin:8px 0 14px;font-size:.92rem}th,td{text-align:left;padding:7px 8px;border-bottom:1px solid var(--grid);vertical-align:top}th{color:var(--ink2);font-weight:600}
.pill{display:inline-block;border-radius:999px;padding:2px 10px;font-weight:650;font-size:.82rem;color:#fff}.RED,.red{background:var(--crit)}.AMBER,.amber{background:#b57a00}.GREEN{background:var(--good)}.info{background:var(--muted)}
.flag{border-left:4px solid var(--grid);padding:6px 12px;margin:10px 0;background:rgba(127,127,127,.06);border-radius:0 8px 8px 0}.flag.red{border-color:var(--crit)}.flag.amber{border-color:var(--warn)}.flag small{color:var(--ink2);display:block}
.chart{margin:14px 0}.chart .cap{color:var(--ink2);font-size:.88rem;margin:2px 0 8px}.chart>input{position:absolute;opacity:0;pointer-events:none}.chart>label{display:inline-block;border:1px solid var(--border);border-radius:999px;padding:3px 12px;margin:0 6px 8px 0;cursor:pointer;font-size:.85rem;color:var(--ink2);background:var(--surface)}
.chart>input:checked+label{background:var(--ink);color:var(--page);border-color:var(--ink)}.chart>input:focus-visible+label{outline:2px solid var(--s1);outline-offset:2px}.pane{display:none}.r0:checked~.p0,.r1:checked~.p1,.r2:checked~.p2,.r3:checked~.p3{display:block}
.disc{color:var(--muted);font-size:.82rem;margin-top:24px}ul{padding-left:1.2rem}@media print{details{break-inside:avoid}.chart>input,.chart>label{display:none}.pane{display:block!important}}
.t{font:12px system-ui,-apple-system,Segoe UI,sans-serif;fill:var(--ink2)}.tt{font:600 13px system-ui,-apple-system,Segoe UI,sans-serif;fill:var(--ink)}.g{stroke:var(--grid);stroke-width:1}.a{stroke:var(--axis);stroke-width:1}.s1{fill:var(--s1);stroke:var(--s1)}.s2{fill:var(--s2);stroke:var(--s2)}.s3{fill:var(--s3);stroke:var(--s3)}.s4{fill:var(--s4);stroke:var(--s4)}.s0{fill:var(--all);stroke:var(--all)}
.l{fill:none;stroke-width:2.2;stroke-linejoin:round;stroke-linecap:round}.p,.bar{stroke:none}.band{fill:var(--band);stroke:none}.cell0{fill:var(--grid)}svg{display:block}"""


def render_html(R):
    parts, open_section = [], False
    cid = 0
    first = True

    def close():
        nonlocal open_section
        if open_section:
            parts.append("</details>")
            open_section = False
    for blk in R["blocks"]:
        kind, val = blk[0], (blk[1] if len(blk) == 2 else blk[1:])
        if kind == "h1":
            parts.append(f"<h1>{escape(val)}</h1>")
        elif kind == "h2":
            close()
            parts.append(f"<details open><summary>{escape(val)}</summary>")
            open_section = True
        elif kind == "p":
            parts.append(f"<p>{escape(val)}</p>" if not val.startswith("Not medical advice") else f'<p class="disc">{escape(val)}</p>')
        elif kind == "ul":
            parts.append("<ul>" + "".join(f"<li>{escape(x)}</li>" for x in val) + "</ul>")
        elif kind == "table":
            head, rows = val
            parts.append("<table><thead><tr>" + "".join(f"<th>{escape(str(h))}</th>" for h in head) + "</tr></thead><tbody>" + "".join("<tr>" + "".join(f"<td>{escape(str(c if c is not None else ''))}</td>" for c in r) + "</tr>" for r in rows) + "</tbody></table>")
        elif kind == "flags":
            inj = val
            parts.append(f'<p><span class="pill {inj["level"]}">{inj["level"]}</span> ' + (f"{len(inj['flags'])} signals" if inj["flags"] else "no flags from your load, recovery or your own reports") + "</p>")
            for f in inj["flags"]:
                parts.append(f'<div class="flag {f["level"]}"><strong>{f["level"].upper()}</strong> {escape(f["text"])}<small>Evidence: {escape(f["evidence"])}.</small><small>Suggested: {escape(f["action"])}</small></div>')
            if inj["questions"]:
                parts.append("<p>Questions for you:</p><ul>" + "".join(f"<li>{escape(q)}</li>" for q in inj["questions"]) + "</ul>")
            parts.append(f'<p class="disc">{escape(inj["note"])}</p>')
        elif kind == "chart":
            f = R["figs"][val]
            cid += 1
            vs = list(f["variants"].items())
            name = f"c{cid}"
            controls = "".join(f'<input class="r{i}" type="radio" name="{name}" id="{name}_{i}"' + (" checked" if lab == f["default"] else "") + f'><label for="{name}_{i}">{escape(lab)}</label>' for i, (lab, _) in enumerate(vs)) if len(vs) > 1 else ""
            if len(vs) == 1:
                controls = f'<input class="r0" type="radio" name="{name}" id="{name}_0" checked>'
            panes = "".join(f'<div class="pane p{i}">{svg}</div>' for i, (_, svg) in enumerate(vs))
            parts.append(f'<div class="chart">{controls}{panes}' + (f'<div class="cap">{escape(f["caption"])}</div>' if f["caption"] else "") + "</div>")
    close()
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(R["title"])}</title><style>{HTML_CSS}</style></head>'
            f'<body><main>{"".join(parts)}</main></body></html>')


# ---------------------------------------------------------------- data and CLI
def collect(today, mode, deep=True, adapt=True):
    import readiness_check  # noqa: E402
    import latest_activity as la  # noqa: E402
    import strength_history as sh  # noqa: E402
    ath = json.loads(gc.ATHLETE_PATH.read_text(encoding="utf-8")) if gc.ATHLETE_PATH.exists() else {}
    plan = None
    pf = max(gc.plan_files("plan-*.json"), default=None, key=lambda x: x.name)
    plan = json.loads(pf.read_text(encoding="utf-8")) if pf else None
    with gc.Garmin() as g:
        acts = [a for a in gc.list_activities(g, today - timedelta(days=130), today) if a["date"] <= today]
        rows, _ = readiness_check.build_rows(g, today - timedelta(days=100), today)
        try:
            hist = sh.load_history(g, 130) if mode != "daily" else None
        except Exception:
            hist = None
        latest = None
        recent = [a for a in acts if (today - a["date"]).days <= 3]
        if recent:
            t = max(recent, key=lambda x: x["start"])
            latest = {"activity": {"id": t["id"], "name": t["name"], "sport": t["sport"], "date": str(t["date"]), "minutes": round(t["min"]), "km": round(t["km"], 1), "avg_hr": t.get("avg_hr")}}
            prev = la.similar(acts, t)
            if prev:
                latest["compare_with"] = {"id": prev["id"], "name": prev["name"], "table": la.side_by_side(t, prev)}
            if deep and mode == "daily" and t["sport"] in ("run", "bike"):
                try:
                    import analyze_activity  # noqa: E402
                    latest["aerobic"] = analyze_activity.analyze(g, t["id"], g.call("garmin_get_heart_rate_zones"))
                except Exception:
                    pass
    try:
        r = subprocess.run([sys.executable, "-X", "utf8", str(SKILLS / "rampwise-recovery" / "scripts" / "readiness_check.py"), "--json"], capture_output=True, text=True, encoding="utf-8", timeout=180)
        ready = json.loads(r.stdout)
    except Exception:
        ready = None
    inj = analysis.injury_flags(acts, rows, ath, today, ready)
    cmp = analysis.compare(acts, today)
    r = cmp["rolling"]
    cmp["recovery"] = {"this": analysis.recovery_means(rows, date.fromisoformat(r["this"]["from"]), today), "before": analysis.recovery_means(rows, date.fromisoformat(r["before"]["from"]), date.fromisoformat(r["before"]["to"]))}
    cmp["insights"] = analysis.insights(cmp, (ath.get("preferences") or {}).get("units"))
    adapt_out = None
    if adapt and plan:
        try:
            r2 = subprocess.run([sys.executable, "-X", "utf8", str(SKILLS / "rampwise-adapt" / "scripts" / "next_session.py"), "--json", "--days", "1"], capture_output=True, text=True, encoding="utf-8", timeout=300)
            adapt_out = json.loads(r2.stdout)
        except Exception:
            adapt_out = None
    return acts, rows, ath, plan, hist, ready, inj, cmp, adapt_out, latest


def write_report(R, outdir, fmt):
    outdir.mkdir(parents=True, exist_ok=True)
    paths = []
    if fmt in ("md", "both"):
        (outdir / "report.md").write_text(render_md_full(R, outdir), encoding="utf-8")
        paths.append(outdir / "report.md")
    if fmt in ("html", "both"):
        (outdir / "report.html").write_text(render_html(R), encoding="utf-8")
        paths.append(outdir / "report.html")
        latest = outdir.parent / f"latest-{R['mode']}.html"
        latest.write_text(render_html(R), encoding="utf-8")
    return paths


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["daily", "weekly", "monthly"])
    ap.add_argument("--date")
    ap.add_argument("--format", choices=["md", "html", "both"], default="both")
    ap.add_argument("--out")
    ap.add_argument("--no-deep", action="store_true", help="skip the FIT-file aerobic analysis of the latest activity (daily)")
    ap.add_argument("--no-adapt", action="store_true", help="skip the next-session adaptation")
    gc.apply_here_flag()
    a = ap.parse_args()
    gc.utf8_stdout()
    today = date.fromisoformat(a.date) if a.date else date.today()
    acts, rows, ath, plan, hist, ready, inj, cmp, adapt, latest = collect(today, a.mode, not a.no_deep, not a.no_adapt)
    R = build(a.mode, today, acts, rows, ath, plan, hist, ready, inj, cmp, adapt, latest)
    outdir = Path(a.out) if a.out else gc.out_dir("reports") / f"{today}-{a.mode}"
    for p in write_report(R, outdir, a.format):
        print("wrote", p)
    print(f"readiness {ready.get('verdict') if ready else 'unknown'} | injury watch {inj['level']} | {len(R['figs'])} figures")


if __name__ == "__main__":
    main()
