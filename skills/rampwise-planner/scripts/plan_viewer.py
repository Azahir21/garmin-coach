#!/usr/bin/env python3
"""Plan viewer: turn an event plan (event_plan.py JSON) into ONE self-contained HTML page. Weeks open and close, every session opens to its steps,
a volume chart shows the build and the taper, and the rule labels (research / practice / gap) are at the bottom. No scripts, no network, light and dark mode, prints cleanly.

  plan_viewer.py PLAN.json [--out FILE] [--title "My Olympic plan"]
"""
import argparse
import json
import sys
from datetime import date, datetime
from html import escape
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILLS = HERE.parent.parent
sys.path.insert(0, str(SKILLS / "rampwise-report" / "scripts"))
sys.path.insert(0, str(HERE))
import charts as ch  # noqa: E402
from event_plan import EFFORT, WD, fmt_blocks  # noqa: E402

SPORT = {"swim": ("Swim", "s4"), "bike": ("Ride", "s2"), "run": ("Run", "s1"), "strength": ("Strength", "s3")}
PHASE_LABEL = {"BASE": "Base", "BUILD": "Build", "PEAK": "Peak", "TAPER": "Taper", "RACE": "Race", "RECOVERY": "Recovery week"}
MONTH = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

CSS = """:root{color-scheme:light dark;--page:#f4f4f1;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--muted:#898781;--grid:#e1e0d9;--axis:#c3c2b7;--border:rgba(11,11,11,.1);--s1:#2a78d6;--s2:#eb6834;--s3:#1baf7a;--s4:#7c5cd6;--all:#898781;--crit:#d03b3b;--accent:#2a78d6;--ph-base:#9db8e6;--ph-build:#2a78d6;--ph-peak:#eb6834;--ph-taper:#1baf7a;--ph-race:#d03b3b;--ph-recovery:#c3c2b7}
@media (prefers-color-scheme:dark){:root{--page:#0d0d0d;--surface:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--grid:#2c2c2a;--axis:#383835;--border:rgba(255,255,255,.1);--s1:#3987e5;--s2:#d95926;--s3:#199e70;--s4:#9b82e8;--accent:#3987e5;--ph-base:#35507f;--ph-build:#3987e5;--ph-peak:#d95926;--ph-taper:#199e70;--ph-race:#e5574f;--ph-recovery:#383835}}
*{box-sizing:border-box}body{margin:0;background:var(--page);color:var(--ink);font:16px/1.55 system-ui,-apple-system,Segoe UI,sans-serif}main{max-width:1060px;margin:0 auto;padding:22px 16px 70px}
.hero{background:linear-gradient(135deg,var(--s4),var(--s1) 45%,var(--s2));color:#fff;border-radius:20px;padding:26px 24px;margin-bottom:16px}.hero h1{margin:0 0 4px;font-size:1.7rem;line-height:1.2}.hero p{margin:.2em 0;opacity:.95}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}.chip{background:rgba(255,255,255,.2);border-radius:999px;padding:3px 12px;font-size:.85rem;font-weight:600}
.warn{background:var(--surface);border:1px solid var(--border);border-left:5px solid var(--ph-peak);border-radius:10px;padding:8px 14px;margin:10px 0;font-size:.92rem}
.band{display:flex;height:16px;border-radius:8px;overflow:hidden;margin:10px 0 4px}.band i{display:block;height:100%}.legend{display:flex;flex-wrap:wrap;gap:14px;font-size:.82rem;color:var(--ink2);margin-bottom:8px}.legend b{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:5px}
.panel{background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:12px 16px;margin:14px 0}h2{font-size:1.15rem;margin:.2em 0 .5em}
details.week{background:var(--surface);border:1px solid var(--border);border-radius:16px;margin:12px 0;padding:0 14px}details.week>summary{cursor:pointer;list-style:none;padding:12px 0;display:flex;align-items:center;gap:12px;flex-wrap:wrap}details.week>summary::-webkit-details-marker{display:none}
.wn{font-weight:700}.tag{border-radius:999px;padding:1px 10px;font-size:.78rem;font-weight:700;color:#fff}.hrs{color:var(--ink2);font-size:.9rem}.mini{display:flex;height:8px;width:140px;border-radius:4px;overflow:hidden;margin-left:auto;background:var(--grid)}.mini i{display:block;height:100%}
.grid{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:8px;padding:2px 0 14px}.day{min-width:0}.dn{font-size:.78rem;color:var(--muted);margin:0 0 4px;font-weight:600}
.card{border:1px solid var(--border);border-left:5px solid var(--all);border-radius:10px;margin:0 0 6px;background:var(--page);padding:0 8px}.card summary{cursor:pointer;list-style:none;padding:6px 0;font-size:.82rem;line-height:1.3}.card summary::-webkit-details-marker{display:none}
.card.swim{border-left-color:var(--s4)}.card.bike{border-left-color:var(--s2)}.card.run{border-left-color:var(--s1)}.card.strength{border-left-color:var(--s3)}.card.race{border-left-color:var(--ph-race);background:rgba(208,59,59,.08)}
.sp{display:block;font-size:.68rem;font-weight:800;letter-spacing:.06em;text-transform:uppercase;color:var(--ink2)}.mn{color:var(--ink2)}.body{font-size:.82rem;color:var(--ink2);padding:0 0 8px}.body ul{margin:.3em 0;padding-left:1.1em}.q{color:var(--ph-peak);font-weight:700}
.rest{color:var(--muted);font-size:.8rem;padding:6px 2px}
@media (max-width:820px){.grid{grid-template-columns:1fr}.dn{margin-top:6px}.mini{margin-left:0}}
.foot{color:var(--muted);font-size:.84rem;margin-top:26px}ul.basis li{margin:.35em 0}a{color:var(--accent)}
@media print{details.week{break-inside:avoid}details>*{display:block!important}}
.t{font:12px system-ui,-apple-system,Segoe UI,sans-serif;fill:var(--ink2)}.tt{font:600 13px system-ui,-apple-system,Segoe UI,sans-serif;fill:var(--ink)}.g{stroke:var(--grid);stroke-width:1}.a{stroke:var(--axis);stroke-width:1}.s1{fill:var(--s1);stroke:var(--s1)}.s2{fill:var(--s2);stroke:var(--s2)}.s3{fill:var(--s3);stroke:var(--s3)}.s4{fill:var(--s4);stroke:var(--s4)}.s0{fill:var(--all);stroke:var(--all)}.bar{stroke:none}svg{display:block}"""


def dlabel(d):
    return f"{d.day} {MONTH[d.month - 1]}"


def render(meta, sessions, title=None, repo_url="https://github.com/Azahir21/rampwise", footer_extra=""):
    ev_date = date.fromisoformat(meta["event_date"])
    title = title or f"{meta['event_label']} plan"
    by_week = {}
    for s in sessions:
        by_week.setdefault(s["week"], []).append(s)
    parts = [f'<section class="hero"><h1>{escape(title)}</h1><p>{meta["weeks"]} weeks to {dlabel(ev_date)} {ev_date.year}. Level {escape(meta["level"])}, {meta["days_per_week"]} training days a week.</p>'
             f'<div class="chips"><span class="chip">now {meta["hours_now"]:g} h/week</span><span class="chip">peak about {meta["peak_hours"]:g} h/week</span><span class="chip">taper {sum(1 for p in meta["phases"] if p == "TAPER")} week(s)</span>'
             f'<span class="chip">about {int(round(meta.get("hard_share_estimate", 0) * 100))} % hard (estimate)</span></div></section>']
    for w in meta.get("warnings", []):
        parts.append(f'<div class="warn"><b>Heads-up.</b> {escape(w)}</div>')
    # phase band
    n = len(meta["phases"])
    segs = "".join(f'<i style="width:{100 / n:.3f}%;background:var(--ph-{(w["tag"] if w["tag"] in ("RECOVERY",) else w["phase"]).lower()})" title="Week {w["week"]}: {escape(PHASE_LABEL.get(w["tag"], w["tag"]))}"></i>' for w in meta["weekly"])
    parts.append('<div class="panel"><h2>The shape of the plan</h2>'
                 f'<div class="band">{segs}</div><div class="legend">' + "".join(f'<span><b style="background:var(--ph-{k.lower()})"></b>{v}</span>' for k, v in PHASE_LABEL.items() if k != "RACE") + "</div>")
    labels = [dlabel(date.fromisoformat(w["monday"])) for w in meta["weekly"]]
    series = [(SPORT[sp][0], [round(w["by_sport"].get(sp, 0) / 60, 1) for w in meta["weekly"]], SPORT[sp][1]) for sp in ("swim", "bike", "run", "strength") if any(w["by_sport"].get(sp) for w in meta["weekly"])]
    parts.append(ch.bars(labels, series, "Planned hours per week", "h", stacked=True, dec=1, height=250, desc="Planned training hours per week by sport"))
    parts.append("</div>")
    # weeks
    for w in meta["weekly"]:
        wk = by_week.get(w["week"], [])
        tag = w["tag"]
        total = max(1, sum(w["by_sport"].values()))
        mini = "".join(f'<i class="s{SPORT[sp][1][1]}" style="width:{w["by_sport"][sp] / total * 100:.1f}%;background:var(--{SPORT[sp][1].replace("s", "s")})"></i>' for sp in ("swim", "bike", "run", "strength") if w["by_sport"].get(sp))
        mon = date.fromisoformat(w["monday"])
        cells = []
        for i, wd in enumerate(WD):
            day = [s for s in wk if s["weekday"] == wd]
            inner = []
            for s in sorted(day, key=lambda x: x["start"]):
                cls = "race" if s["phase"] == "RACE" else s["sport"]
                steps = ""
                if s.get("blocks"):
                    items = []
                    for b in s["blocks"]:
                        if "repeat" in b:
                            items.append(f"{b['repeat']} x ({b['on']['minutes']:g} min {EFFORT[b['on']['effort']][0]}, {b['off']['minutes']:g} min {EFFORT[b['off']['effort']][0]})")
                        else:
                            items.append(f"{b['minutes']:g} min {escape(b.get('label') or EFFORT[b['effort']][0])} <span class='mn'>({EFFORT[b['effort']][1]})</span>")
                    steps = "<ul>" + "".join(f"<li>{x}</li>" for x in items) + "</ul>"
                lines = ""
                if s.get("strength") and s["strength"].get("lines"):
                    lines = "<ul>" + "".join(f"<li>{escape(x)}</li>" for x in s["strength"]["lines"]) + "</ul>"
                need = ""
                if s.get("strength") and s["strength"].get("needs"):
                    need = "<p><b>Needs from you:</b> " + escape("; ".join(s["strength"]["needs"][:3])) + "</p>"
                mins = f' <span class="mn">{s["minutes"]} min</span>' if s["minutes"] else ""
                inner.append(f'<details class="card {cls}"><summary><span class="sp">{SPORT.get(s["sport"], ("", ""))[0] if s["phase"] != "RACE" else "Race"}{" · quality" if s["quality"] else ""}</span>{escape(s["title"])}{mins}</summary>'
                             f'<div class="body">{steps}{lines}<p>{escape(s["desc"].split(". ", 1)[-1] if s.get("blocks") and ". " in s["desc"] else s["desc"])}</p>{need}</div></details>')
            d = mon.fromordinal(mon.toordinal() + i)
            cells.append(f'<div class="day"><p class="dn">{wd} {dlabel(d)}</p>' + ("".join(inner) or '<div class="rest">Rest</div>') + "</div>")
        opened = " open" if w["week"] == 1 else ""
        parts.append(f'<details class="week"{opened}><summary><span class="wn">Week {w["week"]}</span><span class="tag" style="background:var(--ph-{(tag if tag == "RECOVERY" else w["phase"]).lower()})">{escape(PHASE_LABEL.get(tag, tag))}</span>'
                     f'<span class="hrs">{w["planned_min"] / 60:.1f} h · from {dlabel(mon)}</span><span class="mini">{mini}</span></summary><div class="grid">{"".join(cells)}</div></details>')
    parts.append('<div class="panel"><h2>Why the plan looks like this (rule labels)</h2><ul class="basis">' + "".join(f"<li>{escape(b)}</li>" for b in meta["basis"]) + "</ul></div>")
    parts.append('<p class="foot">' + " ".join(escape(n_) for n_ in meta["notes"]) + f' Generated by <a href="{repo_url}">Rampwise</a>, a free open-source AI endurance coach (independent, not affiliated with Garmin Ltd.). {footer_extra}</p>')
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)} | Rampwise</title>'
            f'<meta name="description" content="A {meta["weeks"]}-week {escape(meta["event_label"])} plan made by Rampwise: base, build, peak and taper, with evidence labels. Example plan, not medical advice.">'
            f'<style>{CSS}</style></head><body><main>{"".join(parts)}</main></body></html>')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan")
    ap.add_argument("--out")
    ap.add_argument("--title")
    a = ap.parse_args()
    data = json.loads(Path(a.plan).read_text(encoding="utf-8"))
    out = Path(a.out) if a.out else Path(a.plan).with_suffix(".html")
    out.write_text(render(data["meta"], data["sessions"], a.title), encoding="utf-8")
    print("wrote", out)


if __name__ == "__main__":
    main()
