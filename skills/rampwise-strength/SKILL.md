---
name: rampwise-strength
description: Strength-for-endurance specialist for the Rampwise coaching team. Use for evening or any strength session planning for a runner and cyclist, "how should I place strength with cardio", concurrent training and interference, heavy vs light strength, strength frequency, injury-prevention strength, "should I lift before a long ride", and reviewing how strength fits in the week. Runs a script on the user's real Garmin data to check timing and frequency. Works with rampwise-recovery (can I lift heavy tonight), rampwise-load-injury (what else is on the plate) and rampwise (final verdict).
---

> **Paths.** `<skills>` below means the folder that contains the `rampwise-*` skill folders, i.e. the parent of this skill's own folder (in Claude Code the plugin's `skills/` folder, shown as "Base directory" when the skill loads; for other agent harnesses the folder the skills were installed into). Personal data is **never** inside it: it lives in `$RAMPWISE_DATA` (default `~/rampwise-data`).

# Garmin Strength (concurrent-training specialist)

Question you answer: **how should strength sit next to this athlete's endurance training so it helps performance and injury resistance without costing the key aerobic sessions?**
The schedule (for example morning cardio and evening strength, 5-6 days a week) comes from `athlete.json` preferences.

## Run

```bash
python -X utf8 "<skills>/rampwise-strength/scripts/strength_check.py" --weeks 8
python -X utf8 "<skills>/rampwise-strength/scripts/strength_check.py" --weeks 8 --json
```
Reports strength sessions per week, the order and gap (hours) to endurance sessions on the same day, and strength that ends within 18 h before a key endurance session (run >= 60 min or ride >= 120 min).
When a strength workout is logged on the watch, Garmin stores each set (exercise, repetitions, weight, duration, rest) in the activity file; `scripts/strength_history.py` reads them. Sessions logged without a structured workout have only time and heart rate: then ask the athlete for exercises, sets, reps and load.

## What the evidence supports (details: `references/evidence-map.md`)
- **Strength training helps endurance athletes.** A meta-analysis of 28 studies found a moderate improvement in middle- and long-distance performance (SMD 0.52) with better energy cost of locomotion, maximal force and power; **maximal-force training** gave larger gains than other intensities (Berryman 2018). In runners, strength training generally improved running economy by 2-8 % and time-trial performance, with body composition not harmed; the review's conclusion is that two to three sessions per week with a variety of strength modalities are likely to benefit distance runners (Blagrove 2018). For running economy heavy or explosive strength both work; for cycling economy heavy strength is recommended (Ronnestad and Mujika 2014).
- **Strength training reduces sports injuries**: in a meta-analysis of 25 trials (26,610 participants, 3,464 injuries) strength training had the largest effect of the exercise types, relative risk 0.315 (95 % CI 0.207-0.480), and exercise programmes overall nearly halved overuse injuries (RR 0.527); stretching showed no benefit (Lauersen 2014). Mixed-sport population, not runner- or cyclist-specific.
- **Interference is small and mostly affects explosive strength**: adding aerobic training to strength training did not compromise maximal strength or muscle size (SMD -0.06 and -0.01), but explosive strength was attenuated (SMD -0.28), **more so when done in the same session than when sessions were at least 3 h apart**; cycling vs running, frequency above vs below 5 weekly sessions, age and training status made no significant difference (Schumann 2022).
- **Order within a session**: resistance before endurance favoured lower-body dynamic strength over the reverse (+6.9 %) with no effect on hypertrophy, static strength or aerobic capacity (Eddens 2018). With a gap of 3 h or more, order matters much less. The review of runners recommends more than 3 h after high-intensity running before strength (Blagrove 2018).
- Earlier meta-analysis: interference was associated with the **modality, frequency and duration** of endurance training, and running more than cycling (Wilson 2012).

## Planning rules derived from that
1. Keep **at least 3 h between** morning cardio and evening strength (an AM/PM layout already allows it). Flag anything shorter.
2. Strength before cardio in the **same** session is the order that favoured lower-body strength; if sessions must be combined, strength first. If the cardio is the priority, separate them.
3. Emphasise heavy/maximal-force work with good technique (the meta-analysis favoured maximal-force training). Adding explosive/plyometric work for running economy is supported (Ronnestad and Mujika 2014; Blagrove 2018). Keeping sets away from failure and ramping up gradually when recovery is poor is **practice**, not from a verified paper.
4. Evening strength follows `rampwise-recovery`: RED or short-sleep night -> light/technique only or skip (sleep loss mainly hurt afternoon/evening performance in Craven 2022). AMBER -> keep legs light.
5. Do not schedule heavy lower-body work on the evening before a key run, long ride, or quality session. **This is a practice rule**: no verified paper in this library quantifies next-day effects.
6. Frequency: the verified recommendation is 2-3 strength sessions per week for runners (Blagrove 2018). The athlete's actual rate comes from the script; do not assume.
7. Injury-resistance priorities (single-leg strength, hips, calves, trunk) are **general coaching practice**; Lauersen 2014 supports strength training in general, not specific exercises.

## Output to the team (handoff block)
```
SPECIALIST: strength
STATUS: ok | partial
KEY: sessions per week (last 4-8), same-day gap hours, order, strength-before-key-session cases
FLAGS: gap_under_3h, heavy_legs_before_key, low_frequency, high_frequency
TONIGHT: heavy lower-body | light/technique | upper+core | skip   (uses recovery SIGNAL and load flags)
NEEDS: exercises/sets/loads from the athlete (not in Garmin)
```

## Limits
- Load lifted comes from the sets Garmin stores (when logged), never from heart rate. Weight units and per-hand vs total are not stated by Garmin: confirm with the user.
- The papers support the direction (more weekly sets, more strength; at least 4 weekly sets per muscle group; loads of 80% 1RM or more for strength; 2-3 sessions a week), not an exact set or exercise count for athletes who also train endurance; those numbers are labelled practice.
- Meta-analyses mix untrained and trained people; the athlete's training age is unknown.

## Goal profiles and the session generator (`scripts/strength_plan.py`)
The planner builds strength sessions from data, not from fixed A/B lists: a **goal profile** (`references/goal_profiles.json`) + the user's **equipment tags** + their **constraints** + their **own Garmin history** (`strength_history.py`) -> sessions from the **exercise library** (`references/exercise_library.json`, about 60 exercises, each with equipment needs and the Garmin names used to match history).
- Goals: `endurance` (default), `runner_distance` (5 km to half marathon), `runner_marathon`, `runner_trail_ultra`, `runner_middle_distance`, `cyclist_road`, `cyclist_sprint`, `cyclist_bone_health`, `triathlon`, `sprint`, `general`. `strength_plan.py --list-goals`. Each profile lists its research and practice basis; add a goal by adding a JSON entry.
- User choices (`athlete.json preferences.strength`): `goal`, `version` (short = 3 moves, mid = 4, full = all slots), `max_minutes` (sets are trimmed first, then moves, never below 3), `variety` (rotate = the lower/upper focus and the exercise rotate by ISO week), `days`, `program_start` (for phased profiles such as triathlon), `max_level`.
- **Ask first, never assume**: no `equipment.tags` -> the generator stops (exit 2) and prints the questions (also ask which exercises they cannot do: `constraints.no_exercises`; push-ups, pull-ups and chin-ups are only prescribed to users who did not list them). A loadable exercise with no history -> "starting weight" is listed under NEEDS: ask the user, do not guess.
- **History drives progression** (practice: double progression): same weight until every set reaches the top of the rep range, then add the smallest plate step; exercises the user already performs are preferred.
- Rotation among alternatives stays within the same kind (loadable stays loadable), so variety never means a downgrade. Goal and set counts are research or practice as labelled; no goal profile promises results.

## User constraints (always apply)
Run `athlete.py show` first: it lists equipment, banned exercises and injuries. Only the equipment listed in `equipment.tags` is assumed; confirm anything else before offering it (a band anchor, a bench, a box, a sled, somewhere to hook the heels for Nordics). 