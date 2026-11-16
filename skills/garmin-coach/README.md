# Garmin coaching team

One head coach, seven specialists (skill + subagent each, the seventh is the planner), calculation scripts that read your own Garmin data, and a verified research library per specialist.

```
<skills>/
  garmin-coach/          head coach: orchestration, profile.md, handoff contract, paces.py, gcommon.py (Garmin data layer)
  garmin-recovery/       HRV, resting HR, sleep -> GREEN/AMBER/RED          (garmin_readiness.py)
  garmin-aerobic-base/   EF, decoupling, durability, zones, trend            (analyze_activity.py, aerobic_trend.py, hold_check.py)
  garmin-heat-weather/   observed weather, heat adjustment, acclimation      (garmin_weather.py, acclimation_decay.py)
  garmin-load-injury/    spikes, ramp, rest days, hard-day spacing           (load_check.py)
  garmin-strength/       strength timing/frequency next to cardio            (strength_check.py)
  garmin-fueling/        carbs per hour, sweat rate                          (fuel_plan.py, sweat_rate.py)
  garmin-planner/        plan, optional run gate, goal tracking, calendar (build_plan.py, run_gate.py, ride_check.py, cycling_power.py, calendar_events.py)
the agents folder/        coach-recovery, coach-aerobic, coach-heat, coach-load, coach-strength, coach-fueling, coach-planner
```
Each skill folder: `SKILL.md` (use), `references/evidence-map.md` (rule -> paper -> what was verified -> strength), `references/library.md` (every paper with DOI/PMID and status), `references/papers/` (open-access full texts with license and DOI at the top).

## Memory
`garmin-coach/athlete.json` (read with `scripts/athlete.py show`) stores goals with ranks, the run gate, injuries and their restrictions, schedule, HR ceilings and dated notes. Every coach reads it first; only the head coach writes it. It is local to this laptop. Remove or edit it any time.

## How the evidence was handled
- Every paper was looked up in Europe PMC (PubMed index); title, authors, journal, DOI and PMID come from that record, and the abstract was read before a rule was written from it.
- Open-access papers (CC BY / CC BY-NC) are saved as full text in `papers/`. Paywalled papers are cited by DOI and only abstract-level claims are used. Books are not included (copyright, and none was read).
- Rules are labelled **research**, **practice** (coaching convention) or **gap**. The decoupling cut-offs (5 % / 10 %), resting-HR flags, the 18-hour strength window and the gut-training ramp are practice.
- Blog and commercial-site claims seen during research that could not be verified are listed as "not supported" in the evidence maps.

## Third-party code
`readiness.py`, `weather.py` and `paces.py` are unmodified copies from https://github.com/tomasstankovic/running-coach (MIT, commit in `third_party/running-coach-COMMIT.txt`, license in `third_party/`). Everything that reads Garmin data, parses FIT files, and the load, strength, fuelling and aerobic scripts are new.

## Setup
1. `python -m pip install --user fitdecode`
2. `garmin-personal-mcp auth --check` must report "Connected to Garmin Connect".
3. Start a **new** Claude Code session (skills and agents are loaded at start).

## Privacy
- Scripts talk to your own local Garmin server; nothing leaves the machine except the opt-in weather lookup (rounded start coordinates and dates to open-meteo.com, only after you approve).
- FIT files (they contain GPS) are cached in `~/Downloads/garmin/coach`. Delete the folder any time.
- `profile.md` holds your goals and preferences; `log.md` is only created if you agree.

## Try it
- "Should I train hard today?" (quick path: readiness + load)
- "Weekly check" (all analysts in two stages, then next week's plan)
- "Build my plan" / "put the next two weeks in my calendar" (planner; calendar events are titled [GC])
- "Is my run gate met?" (only if you set one)
- "How long can I hold my pace under my HR ceiling?" (hold check)
- "How far am I from my ride goal?"
- "I have knee pain since yesterday" (the coach records it and adapts the plan)
- "Analyze my last long ride"
- "Plan a fuelling strategy for a 200 km ride"
