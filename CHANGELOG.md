# Changelog

## 0.2.0 - analysis, adaptation and reports
- **garmin-analyze**: week-over-week comparison (last 7 days against the 7 before; works with or without an activity today; calendar week from Wednesday), latest session against the last similar one, and an **injury-risk watch** (single-run spike, week jump, no rest day, back-to-back hard days, low recovery, short sleep, efficiency drop, injury list, pain check-ins). Every flag carries an evidence label; flags are prompts, not a diagnosis. Three new papers verified at abstract level (Johnston 2018, von Rosen 2017, Silbernagel 2007).
- **garmin-adapt**: adapts the next planned session(s) to readiness, the watch and plan adherence (keep, small progression, easy swap, shorter, recovery spin, rest), builds the changed workout (optional .fit) and prepares the calendar update; the main session applies it after approval. Progression only when everything is green, rarely and in small steps.
- **garmin-report**: daily, weekly and monthly reports as Markdown with SVG figures and as one interactive HTML file (offline, no scripts, light/dark, period buttons, hover values, goal meters). Goals and units follow the user's settings; this replaces the private dashboard that was left out of 0.1.0.
- Two new subagents (coach-analyze, coach-adapt); head coach routing, README and AGENTS.md updated. Personal data (reports, adapt state) stays in `$GARMIN_COACH_DATA`.
- `athlete.py check-in` records pain and gait changes; `athlete.json` gains `preferences.units` and `checkins`.
- Removed the last user-specific wording from skills and agents (goals now always come from `athlete.json`).
- Offline tests cover the new functions and report rendering. Still not tested on other users or watches.

## 0.1.0 - first public release (experimental)
- Eight skills: head coach, recovery, aerobic base, heat and weather, load and injury, strength, fueling, planner, and seven subagents. (A dashboard exists in the author's private setup but is tied to one user's goals, so it is not part of this release.)
- Planner: rolling plans (run, ride, strength) from your Garmin history, Garmin workout files (.fit) with heart-rate zones or custom bpm, calendar payloads, quality sessions on by default and locked only by your own data.
- Strength: 11 goal profiles (endurance, runner and cyclist goals, triathlon, sprint, general), a 60-exercise library, progression from your own logged sets.
- Ask-first rules: no assumed heart-rate data, equipment or starting loads.
- Evidence maps and libraries for every skill (research / practice / gap labels).
- Not tested on a real watch or on other users yet. A three-month field test by the first user starts at release (docs/FIELD-TEST.md).
