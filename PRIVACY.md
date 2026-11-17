# Privacy

- **Your data stays on your computer.** The scripts read your Garmin data through the `garmin-personal-mcp` server on your machine and your own saved key (`garmin-personal-mcp auth`). Nothing is uploaded by this project.
- **Where your personal files live:** `$RAMPWISE_DATA` (default `~/rampwise-data`; the older `GARMIN_COACH_DATA` and `~/garmin-coach-data` are still honoured): `athlete.json` (goals, injuries, heart-rate data, equipment, notes), `plans/`, and optional outputs. This folder is **outside** the plugin, so plugin updates never touch it and it is never part of a git commit of this repository. Back it up yourself.
- **Generated files** (plans, reports, exports, the dashboard) go to `~/rampwise-coach` by default (setting `preferences.output_dir`, `RAMPWISE_OUT`, or `--here`). They contain your training and health data: they are never part of the plugin and never uploaded by it.
- **Cached Garmin files:** FIT downloads are cached in `~/Downloads/garmin/coach` (a folder the Garmin server allows). GPS tracks are not kept by the scripts.
- **What the AI model sees:** whatever the coach prints during a session (numbers from the scripts, your `athlete.json` summary). That goes to the model provider you use, under their terms. Do not put secrets in `athlete.json`.
- **Optional online services, only with your consent:**
  - Weather: Open-Meteo (coordinates of your start point or home town; see CREDITS.md).
  - Calendar: your own calendar connector, only if you ask for the plan to be written there.
  - Papers: Europe PMC when you run `tools/fetch_papers.py`.
- **Do not publish** your `athlete.json`, plans or `.fit` files. The repository's `.gitignore` and `tests/check_repo.py` guard against it.
