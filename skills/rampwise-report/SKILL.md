---
name: rampwise-report
description: Daily, weekly and monthly training reports from the user's own Garmin data, as Markdown with figures and as an interactive single-file HTML page (works offline, light and dark mode, period buttons, hover tooltips). Use for "give me a report", "daily/weekly/monthly summary", "show my progress", "dashboard", "how did my week go", "how am I doing against my goal", and for sharing or archiving a training review. Includes recovery, week-over-week comparison, injury-risk watch, plan against what was done, pace/speed/efficiency trends, strength logs, goal meters and tomorrow's adapted session. Goals and units follow the user's own settings; nothing is compared with other people. Uses rampwise-analyze, rampwise-adapt and rampwise-recovery for the numbers.
---

> **Paths.** `<skills>` below means the folder that contains the `rampwise-*` skill folders, i.e. the parent of this skill's own folder. Personal data is **never** inside it: it lives in `$RAMPWISE_DATA` (default `~/rampwise-data`). Reports are written there, never into the plugin folder.

# Garmin Report (daily, weekly, monthly)

Question you answer: **what actually happened, and is it moving toward the user's goals?** One command builds the report; you then read it with the user and explain what stands out.

## Run

```bash
python -X utf8 "<skills>/rampwise-report/scripts/report.py" daily
python -X utf8 "<skills>/rampwise-report/scripts/report.py" weekly
python -X utf8 "<skills>/rampwise-report/scripts/report.py" monthly --format html
```
Options: `--date YYYY-MM-DD` (report as of that day), `--format md|html|both` (default both), `--out DIR`, `--no-deep` (skip the FIT-file analysis of the latest activity), `--no-adapt` (skip tomorrow's adaptation). A weekly report takes about half a minute because it reads Garmin live.

Output: `$RAMPWISE_DATA/reports/<date>-<mode>/` with
- `report.md` plus `figures/*.svg` (Markdown with real figures; the SVGs carry their own colours and dark-mode rules),
- `report.html` (single file, no network, no scripts: period buttons are pure CSS, charts show values on hover, collapsible sections, prints cleanly),
- `reports/latest-<mode>.html`, always the newest one (bookmark it).

Tell the user where the files are; if they want to see the HTML in the chat, publish it as an Artifact or open it in a browser. Do not paste raw health data anywhere outside their machine without asking.

## What is in each report
| Section | Daily | Weekly | Monthly |
|---|---|---|---|
| What stands out (readiness, watch level, biggest changes) | yes | yes | yes |
| Recovery: HRV against the normal band, resting HR, sleep | 14 or 28 days | 14 or 28 days | 14 or 28 days |
| Injury-risk watch: flags with evidence labels, questions | yes | yes | yes |
| This week against last week (rolling 7 days; calendar week from Wednesday) | yes | yes | yes |
| Minutes per day by sport | 14 or 28 days | 14 or 28 days | 14 or 28 days |
| Latest activity against the last similar one, aerobic reading | yes | | |
| Tomorrow, adapted (`rampwise-adapt`) | yes | | |
| Minutes per week by sport; consistency heatmap | | 4/8/12 weeks | 12 weeks, heatmap |
| Running pace, run efficiency, longest run; riding speed, longest ride | | 4/8/12 weeks | 4/8/12 weeks |
| Strength sessions per week, top set per exercise (first against latest) | | yes | yes |
| Weekly recovery means (HRV, resting HR) | | yes | yes |
| Plan against done, next 7 days of the plan | | yes | yes |
| Goal meters | yes | yes | yes |

Sections appear only when there is data for them (no cycling, no cycling charts). Running is shown as pace (min/km) and cycling as km/h unless `preferences.units` in `athlete.json` says otherwise.

## Goals (meters)
A meter shows the start value, the latest reading and the target. The start is the goal's recorded baseline if there is one, else the first reading in the last 12 weeks; "now" is the best reading of the last 28 days. Supported automatically: a ride-speed goal (`target_speed_kmh`, flat rides of at least half the target distance), a running-pace goal (`target_pace_s_per_km`) and tracked goals in `athlete.json` (`goals[].track = {metric, target, unit}` with metric `weekly_minutes`, `long_run_km`, `long_ride_km`, `training_days_per_week` or `strength_sessions_per_week`). No goal set means no meters: say so and offer to add one with `athlete.py goal-add`.
**A meter is a distance to the goal, never a forecast.** No paper read gives a rate of improvement for one person; never write "you will reach it by ...".

## How to present it
1. Read the "What stands out" list and the injury-risk watch first. If the watch is AMBER or RED or readiness is RED, say so before any good news.
2. Pick 2 or 3 findings that the user can act on (a drop or a jump, a trend, a flag). Quote the figure, not a verdict.
3. Efficiency, pace and speed move with heat, hills, wind, illness and the easy/hard mix: say "compare similar sessions" instead of "you got fitter".
4. Ask the questions the report lists (pain, how they feel). Record answers (`athlete.py check-in`).
5. Offer the next step: `rampwise-adapt` for tomorrow, `rampwise-planner` for the week.
Keep the chat answer short; the report holds the detail.

## Design notes (`references/design.md`)
Fixed colours per sport (run blue, ride orange, strength green, neutral grey), thin marks, a legend whenever there are two or more series, values on hover (HTML) and comparison tables (both formats), light and dark palettes, and no JavaScript.

## Limits
- Charts are as good as the data: missing nights leave gaps, a watch without heart-rate data has no efficiency chart.
- The report states "not medical advice"; flags come from data and the user's own reports.
- Strength top sets need sets saved on the watch (`strength_history.py` reads them).
