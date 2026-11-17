---
name: rampwise-adapt
description: Adaptive next-day session for the Rampwise coaching team. Use for "what should I do tomorrow", "adjust tomorrow's session", "I slept badly, change my plan", "keep my calendar in sync with how I feel", "progress my training", daily or morning re-planning, and after a missed or hard session. Looks at the saved plan, today's readiness, the injury-risk watch (rampwise-analyze) and how much of the last two weeks' plan was done, then decides per planned session: keep, small progression, easy swap, shorter, recovery spin or rest. Builds the changed workout (and optional .fit file) and prepares the calendar update for the main session to apply after approval. Conservative by default; progression only when everything is green. Works with rampwise-planner, rampwise-recovery, rampwise-analyze and rampwise-report. Adapts event plans (all sports) and Garmin-history plans: swims shortened or easy, brick runs dropped on amber or red, race day never changed.
---

> **Paths.** `<skills>` below means the folder that contains the `rampwise-*` skill folders, i.e. the parent of this skill's own folder. Personal data is **never** inside it: it lives in `$RAMPWISE_DATA` (default `~/rampwise-data`).

# Garmin Adapt (adaptive next session, calendar-aware)

Question you answer: **given how the user is doing today, should the next planned session stay, get a small step up, get easier, or become rest?** The plan from `rampwise-planner` is the skeleton; this skill adjusts it day by day, so the plan follows the person, not the other way round.

## Run

```bash
python -X utf8 "<skills>/rampwise-adapt/scripts/next_session.py"                    # tomorrow
python -X utf8 "<skills>/rampwise-adapt/scripts/next_session.py" --days 3           # the next 3 days (days after tomorrow are provisional)
python -X utf8 "<skills>/rampwise-adapt/scripts/next_session.py" --json             # machine-readable, includes calendar update payloads
python -X utf8 "<skills>/rampwise-adapt/scripts/next_session.py" --write-fit        # also write the changed workout as a .fit file
python -X utf8 "<skills>/rampwise-adapt/scripts/next_session.py" --record           # remember that a progression was made (so the next waits a week)
```
Other options: `--date YYYY-MM-DD` (start day), `--plan FILE` (a specific saved plan; default is the latest in `$RAMPWISE_DATA/plans`), `--assume-readiness GREEN|AMBER|RED` (for what-if tests; skips the readiness call).

## Decisions (rules and evidence: `references/evidence-map.md`)
| Decision | When | What changes |
|---|---|---|
| **rest** | active injury or a pain check-in that says stop | no session; the calendar event becomes a rest day |
| **recovery** | readiness RED (and the injury watch is not RED) | a 25-minute easy spin or walk, only if pain-free; otherwise rest |
| **reduce** | injury watch RED, a long session on AMBER, or strength with low recovery | shorter (x0.7, or x0.85 for long sessions); strength at half or 70 % of the sets |
| **easy_swap** | AMBER readiness or AMBER watch on a quality, climb or test day | the session becomes easy at about 90 % of the minutes |
| **progress** | everything green, at least 85 % of the last 14 days of plan done, this week up 10 % or less, at least 7 days since the last progression, and a BUILD week | one small step: +5 min on a tempo block, +1 repeat (up to 6), +5 to +10 min on a long or easy session (long sessions capped at +10 % over the longest in the last 30 days) |
| **keep** | everything else | unchanged; the reason for not progressing is stated |

Days after tomorrow are **provisional**: tomorrow's readiness is unknown, so they use the plan and today's watch only. Re-run each morning; that is the point.

## Calendar (main session only; scripts never write to the calendar)
Each changed day returns `calendar.find` (the date, the marker `rampwise-plan`, the original title; events created before v0.3.0 carry the older marker `garmin-coach-plan`, given as `legacy_marker`) and `calendar.update` (new title starting with `[GC]`, times, description with the reasons, `notificationLevel: NONE`).
1. If `calendar.write_approved` is not true in `athlete.json`, show the proposed change and **ask first**. Never touch events that do not carry the `[GC]` title or the marker line.
2. (Strength days return `description_prefix` instead of a full rewrite: put it in front of the existing description and keep the rest.) Find the event (`list_events` for that day, `fullText` `rampwise-plan`), check the user's own events for clashes and tell them, then `update_event` with the payload. For a rest day the event stays as a short "[GC] Rest day (adapted)" so the change is visible.
3. If the connector is not authorised, give the change as text and the `.fit` file path if one was written.
4. After a progression the user accepted, run the script once more with `--record`.

## How to talk about it
- Start with the decision and one reason in plain words ("tomorrow: easy ride instead of tempo, readiness is amber and sleep was 4.8 h"). Then the new session. Say which parts are provisional.
- The user can always override. If they want the original session, say what the flags were and what the evidence is, once, then respect it unless a pain or injury rule applies.
- Ask, do not assume: how do they feel, any pain today (record with `athlete.py check-in`)? If heart-rate data are missing, the script uses the documented fallback and says so.
- Progress is small and rare on purpose. No paper read gives a rate of improvement for one person, so never promise a result or a date.

## Output to the team (handoff block)
```
SPECIALIST: adapt
STATUS: ok | partial
DAY: date, original session -> decision (reasons), provisional yes/no
NEW_SESSION: title, minutes, fit file path or none
CALENDAR: update payload ready | needs approval | connector missing
QUESTIONS: pain today? how do you feel?
FOR_COACH: one-line change summary
```

## Limits
- It reads the saved plan; no plan, nothing to adapt (run `rampwise-planner` first).
- Readiness is only as good as last night's watch data. Wrist heart rate and sleep staging are estimates.
- The thresholds are conventions (practice) unless the evidence map says research. They are conservative defaults, not individual truths.
