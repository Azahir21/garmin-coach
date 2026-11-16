---
name: rampwise-analyze
description: Activity analysis and injury-risk watch for the Rampwise coaching team. Use for "analyse my last run/ride/strength session", "how did this week compare with last week" (works whether or not there was an activity today), week-over-week or month-over-month change, pace/speed/efficiency trend, "am I at risk of getting injured", "is something off", overuse warning signs, pain check-ins, and before adding load. Compares the latest session with the last similar one, compares the last 7 days with the 7 days before (and the calendar week so far), and raises evidence-labelled injury-risk flags from load, recovery and the user's own pain reports. Flags are prompts to look, never a diagnosis. Works with rampwise-recovery, rampwise-load-injury, rampwise-aerobic-base, rampwise-adapt and rampwise-report.
---

> **Paths.** `<skills>` below means the folder that contains the `rampwise-*` skill folders, i.e. the parent of this skill's own folder. Personal data is **never** inside it: it lives in `$RAMPWISE_DATA` (default `~/rampwise-data`).

# Garmin Analyze (activity analysis and injury-risk watch)

Questions you answer: **what changed since last week, how did that session compare with the last similar one, and are there warning signs worth acting on?** All numbers come from the user's own Garmin data; nothing is compared with other people.

## Run

```bash
python -X utf8 "<skills>/rampwise-analyze/scripts/week_compare.py"              # last 7 days vs the 7 before; calendar week so far (from Wednesday)
python -X utf8 "<skills>/rampwise-analyze/scripts/latest_activity.py"           # newest session vs the last similar one (--id N for a specific one)
python -X utf8 "<skills>/rampwise-analyze/scripts/injury_watch.py"              # injury-risk flags (add --json for codes; --no-readiness is faster)
```
Add `--json` for machine-readable output and `--today YYYY-MM-DD` to analyse another day.

- **Week over week** is always available: the rolling window needs no activity today. The calendar-week comparison is skipped before Wednesday (a Monday "week so far" says nothing). Per sport: minutes, km, sessions, climb, average heart rate, speed or pace, longest session, hard sessions, plus recovery means (HRV, resting HR, sleep) for the two windows.
- **Latest activity**: running is shown as pace (min/km), cycling as km/h (or whatever `preferences.units` says). Aerobic analysis (efficiency, decoupling) comes from `rampwise-aerobic-base`; it is only readable for steady, comparable sessions. Strength is compared set by set with the last session that shares exercises.
- **Injury watch** combines load rules, recovery, and what the user told you (`athlete.py check-in`, injuries in `athlete.json`).

## The flags (each carries an evidence label; details in `references/evidence-map.md`)
| Flag | Trigger | Label |
|---|---|---|
| Single-run spike | a run more than 10 % over the longest run of the previous 30 days (red above 100 %) | research (Frandsen 2025); colours are practice |
| Week jump | run + ride minutes up 20 % or more on the week before (small bases ignored) | practice with mixed support (Nielsen 2014, Damsted 2019; a 10 % rule did not prevent injuries in an RCT, Buist 2008) |
| No rest day | 7 days (amber) or 14 days (red) in a row | practice |
| Hard days back to back | two sessions with Garmin aerobic training effect 4.0 or more on consecutive days | practice |
| Recovery low | readiness AMBER or RED from `rampwise-recovery` | research for the signals (Buchheit 2014, Craven 2022); linking them to injury is a gap |
| Short sleep | the last 3 nights average under 6 h (the 6 h line is practice) | limited research (von Rosen 2017, adolescent athletes only); adults: gap |
| Efficiency drop | run efficiency down 5 % or more on the user's own recent baseline | practice |
| Active or monitored injury | an injury in `athlete.json` with status active (red) or monitoring (amber); follow its restriction | the user's own record |
| Recent injury history | an injury marked resolved less than 60 days ago (information only) | research (Johnston 2018, systematic review of 12 endurance studies: a history of injury, medium effect); the 60-day window is practice |
| Pain check-in | the user reported pain 3 or more (amber), 6 or more (red), or a change in gait (red) | practice, in the spirit of the pain-monitoring model (Silbernagel 2007, one small Achilles trial) |

The thresholds are in `scripts/analysis.py`. Some are conventions, not findings; the output says which.

## How to talk about it
- Lead with the comparison ("run minutes down 45 %, ride up 98 %"), then the flags, then one suggested action per flag. Use "was associated with", never "causes".
- **Ask, do not assume.** The script lists questions (new pain? where, how bad 0-10, does it change how you walk or run? anything worse the morning after? new shoes, bike setup, surface, illness, stress?). Record answers with `athlete.py check-in --area .. --pain N [--gait-change]` or `injury-add`. Pain that changes gait, keeps rising or lasts more than a few days: stop and recommend a clinician.
- Watch data cannot see an injury. A GREEN watch means "nothing in the data", not "no injury".
- Never invent a cause. If the week drop is a holiday or illness, the user will say so; ask.

## Output to the team (handoff block)
```
SPECIALIST: analyze
STATUS: ok | partial
KEY: rolling 7 d vs previous 7 d per sport (minutes, km, speed or pace), latest session vs last similar
INJURY_WATCH: GREEN | AMBER | RED
FLAGS: spike, week_jump, no_rest, back_to_back_hard, recovery_low, short_sleep, efficiency_drop, injury_history, pain_checkin
QUESTIONS: what to ask the user
FOR_COACH: "no added load" | "ok to progress"
FOR_ADAPT: flag ids (rampwise-adapt reads them)
```

## Limits
- Elapsed time includes pauses for some devices; weekly numbers are approximate. Strength is counted in sessions, not load.
- Pace and speed depend on route, weather and the easy/hard mix; compare similar sessions and say so.
- Efficiency needs a heart-rate signal; wrist heart rate can drift. Never rank the user against anyone else.
