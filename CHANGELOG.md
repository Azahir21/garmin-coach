# Changelog

## 0.4.0 - event plans for 17 events, plan viewer, exports, swimming
- **Event plans** (`event_plan.py`): a periodised plan (base, build, peak, taper, a lighter week every 4th, +10 % weekly cap, long-session caps) for 17 events: 5K, 10K, half, marathon, 50 km ultra; sprint, Olympic, 70.3 and Ironman triathlon; sprint and standard duathlon; gran fondo, century and 300 km ultra ride; 1.5 km, 5 km and 10 km open-water swims. It works **without a Garmin account** from a few numbers (event, date, level, hours now, hours available, days per week) and stops to ask when something is missing. It says so when the weeks left cannot reach the usual peak, or when your longest sessions are short for the hours you report.
- **Plan viewer** (`plan_viewer.py`): one interactive HTML page per plan (weekly hours chart, phase band, expandable weeks and sessions, rule labels). 17 example plans from made-up numbers are on the project page.
- **Exports** (`export_plan.py`): calendar (.ics), spreadsheet (.csv), Zwift (.zwo) and ERG/MRC ride workouts with power as a share of FTP. Garmin .fit files still come from the Garmin-history planner. Import into Zwift and TrainerRoad is not tested.
- **Swimming** is now counted in the Garmin-side analysis, injury watch and reports (violet in the charts); swim sessions are not adapted automatically yet.
- **Evidence:** six papers verified at abstract level (taper meta-analysis, Ironman intensity distribution x2, swim/bike/run contribution, Ironman overuse injuries, training volume). Cycling, swimming and duathlon plans have no study behind them and are labelled practice or gap.
- **Project page** redesigned; the sample report moved to `/sample/`; `llms.txt`, sitemap, `CITATION.cff`.
- Release assets now include `rampwise-skills.zip`.
- **Output folder:** everything generated now goes to one main folder, `~/rampwise-coach/`, with subfolders (`plans/<event>-<date>/`, `reports/`, `workouts/`, `dashboard/`), so files are easy to find. Your data stays in `~/rampwise-data`. Change the folder without moving anything (`preferences.output_dir`, `RAMPWISE_OUT`, or `--here` for the current directory). Older plans in the data folder are still found. `build_plan.py` now saves its plan by default.
- **Evidence, read in depth:** brick-run, cadence and run-pacing rules now rest on Walsh 2019, read in full (open access); the plan drops brick runs while an injury is active and cuts them to 10 minutes with a history of exercise-related leg pain, and says that the training benefit of bricks is unproven. `docs/EVIDENCE-DEPTH.md` lists, paper by paper, whether the full text or only the abstract was read, and how to supply paywalled papers.
- **Paper library tool** (`tools/build_paper_files.py`): builds a local file for every paper in the libraries (full text when openly licensed, else the abstract with its citation) and an `INDEX.md` per skill with the read depth; the head coach and the handoff contract tell the coach to open the file before quoting a paper.
- **Full texts read:** Frandsen 2025, Fokkema 2020, Craven 2022, Buchheit 2014, Stoggl 2014, Schumann 2022, Eddens 2018, Blagrove 2018, Vickers 2016 and Walsh 2019 were read in full; every evidence map has a "Full-text reading notes" section with sample, effect and the authors' limits. One consequence: the week-over-week jump flag is now labelled weak (the largest cohort found no week-to-week association); the single-run 10 % flag stays research but observational.
- **Weekly and monthly reports** gain a "Recent activities" table (last 14 days, each session against the last similar one).

## 0.3.1 - no more garmin_* script names
- `garmin_readiness.py` is now `readiness_check.py` and `garmin_weather.py` is now `weather_check.py` (same options). The default folder for exported workout files is `~/rampwise-workouts` (the older `~/garmin-workouts` is still used if it is the only one that exists).
- Still named after the data source, on purpose: the `garmin-personal-mcp` server and its `garmin_*` tools (third-party), and the FIT cache folder `~/Downloads/garmin/coach` that the server allows.

## 0.3.0 - renamed to Rampwise
- The project is now **Rampwise** (was "Garmin Coach") so it does not use another company's trademark. Skills are `rampwise-*`, the plugin and marketplace are `rampwise`, the repository is `Azahir21/rampwise` (GitHub redirects the old address). "Garmin" is used only descriptively, to say which data the tool reads.
- Compatibility: `RAMPWISE_DATA` falls back to `GARMIN_COACH_DATA`, then `~/garmin-coach-data`; `RAMPWISE_WEATHER_OK` falls back to `GARMIN_COACH_WEATHER_OK`; calendar events with the old marker `garmin-coach-plan` are still found (`legacy_marker`). Reinstall the plugin under its new name.
- Added a non-affiliation notice (README, DISCLAIMER, manifests) and a "Data from Garmin devices" line in reports.
- Script and MCP tool names that describe the data source (`garmin_readiness.py`, `garmin_*` tools of `garmin-personal-mcp`) are unchanged.

## 0.2.0 - analysis, adaptation and reports
- **rampwise-analyze**: week-over-week comparison (last 7 days against the 7 before; works with or without an activity today; calendar week from Wednesday), latest session against the last similar one, and an **injury-risk watch** (single-run spike, week jump, no rest day, back-to-back hard days, low recovery, short sleep, efficiency drop, injury list, pain check-ins). Every flag carries an evidence label; flags are prompts, not a diagnosis. Three new papers verified at abstract level (Johnston 2018, von Rosen 2017, Silbernagel 2007).
- **rampwise-adapt**: adapts the next planned session(s) to readiness, the watch and plan adherence (keep, small progression, easy swap, shorter, recovery spin, rest), builds the changed workout (optional .fit) and prepares the calendar update; the main session applies it after approval. Progression only when everything is green, rarely and in small steps.
- **rampwise-report**: daily, weekly and monthly reports as Markdown with SVG figures and as one interactive HTML file (offline, no scripts, light/dark, period buttons, hover values, goal meters). Goals and units follow the user's settings; this replaces the private dashboard that was left out of 0.1.0.
- Two new subagents (coach-analyze, coach-adapt); head coach routing, README and AGENTS.md updated. Personal data (reports, adapt state) stays in `$RAMPWISE_DATA`.
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
