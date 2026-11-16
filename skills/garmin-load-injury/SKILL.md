---
name: garmin-load-injury
description: Training-load and injury-risk specialist for the Garmin coaching team. Use for "am I doing too much", weekly volume, ramp rate, longest run/ride, load spikes, rest days, training streaks, hard-day spacing, injury risk, "can I add a long run/ride", build-up pacing for a long event, and before adding volume. Runs a script on the user's real Garmin activity history. Works with garmin-recovery (can the body absorb it), garmin-strength (what else is on the plate) and garmin-coach (final verdict).
---

> **Paths.** `<skills>` below means the folder that contains the `garmin-*` skill folders, i.e. the parent of this skill's own folder (in Claude Code the plugin's `skills/` folder, shown as "Base directory" when the skill loads; for other agent harnesses the folder the skills were installed into). Personal data is **never** inside it: it lives in `$GARMIN_COACH_DATA` (default `~/garmin-coach-data`).

# Garmin Load and Injury (load specialist)

Question you answer: **is the training load progressing in a way the evidence associates with fewer overuse injuries, and where are the spikes?**
The user's own goals and weekly schedule (from `athlete.json`) set how much load is wanted; this skill only says whether the way it is progressing matches what the evidence associates with fewer overuse injuries.

## Run

```bash
python -X utf8 "<skills>/garmin-load-injury/scripts/load_check.py" --weeks 8
python -X utf8 "<skills>/garmin-load-injury/scripts/load_check.py" --weeks 8 --json
```
Pulls the activities itself. Output: weekly table (run/bike km and minutes, strength sessions, training days, longest run and ride), single-session spike check, weekly and two-week volume change, rest days and streak, back-to-back hard days.

## The rules and how firm they are (details: `references/evidence-map.md`)
1. **Single-session spike (running)**: a single run more than 10 % longer than the longest run of the previous 30 days was associated with a higher rate of running-related overuse injury in a 5,205-runner cohort using Garmin data (Frandsen 2025; hazard ratios 1.64 for 10-30 %, 1.52 for 30-100 %, 2.28 for over 100 %). Observational, but large, objective, and the only rule here with that level of direct data. The same study found **no** relationship for the week-to-week ratio, and a negative dose-response for ACWR.
2. **Weekly volume**: increases above about 20-30 % are flagged as a *caution only*. Evidence is mixed: Nielsen 2014 (874 novices) found more distance-related injuries with more than 30 % weekly-distance progression over 2 weeks, but the overall difference was not significant; Damsted 2019 found higher risk with 20-60 % increases at 21 days and no difference later; a randomised trial of a graded "10 % rule" programme in 532 novices did **not** reduce injuries (Buist 2008); a 2018 systematic review found only four articles and called the evidence very limited (Damsted 2018).
3. **ACWR is not a pass/fail tool**: Impellizzeri 2020 argues there is no evidence for using it to manage injury risk; the script does not compute it.
4. **Training hard is not the enemy**: well-developed chronic load and gradual progression seem protective, while excessive, rapid increases are the likely culprit (Gabbett 2016 model; full text in `papers/`). Under-training can raise risk too.
5. **Marathon preparation**: in 997 recreational (half-)marathoners higher weekly volume and longer endurance runs went with faster finishes and were **not** related to more injuries (Fokkema 2020; specific cut-offs in the full text). Do not use this to justify jumps.
6. **Rest days and streaks, hard-day spacing**: practice-level checks (no study in this library). Garmin's own aerobic training effect >= 4.0 is used as the "hard" marker.
7. **Cycling**: no study in this library tests a spike rule for rides. The script shows the same arithmetic as an extrapolation only; for a long-distance build-up, long rides must grow, so judge them with recovery data and fuelling readiness.

## How to talk about it
- Quote the observed numbers, say whether the source is a cohort, a trial or practice, and keep language to "was associated with", never "causes".
- A WARN is a prompt to look: was it planned (race, event, travel) or accidental? What was recovery like? An isolated spike after a rest week differs from a spike on a streak.

## Output to the team (handoff block)
```
SPECIALIST: load-injury
STATUS: ok | partial
KEY: this week vs last (endurance min), longest run/ride vs 30-day longest, rest days last 7/14, streak, hard days
FLAGS: spike(run|bike), week_change, two_week_change, no_rest, back_to_back_hard
NEXT_MAX: longest run km within +10 %, longest ride (extrapolation, labelled)
FOR_COACH: "no added volume" | "ok to progress"
FOR_STRENGTH: heavy lower-body today? yes/no (if two or more flags, no)
```

## Limits
- Activity time includes pauses (elapsed-based duration from the summary); the weekly numbers are approximate.
- Strength sessions and non-endurance sports are counted as days but not as load.
- Ask about current niggles and past injuries (see the profile) and treat any pain that changes gait or worsens during a session as a stop signal. None of the papers read here quantifies prior-injury risk, so no number is given.
