# Other watch brands and Strava

Rampwise reads your Garmin account through a local server, so most of its coaching (readiness, load, reports) is Garmin-only today. One part now works for any watch: the **aerobic analysis of a single activity** (efficiency, heart-rate drift, durability for runs and rides; pace per 100 m and drift for pool swims; the legs of a multisport file).

```text
python analyze_activity.py --fit-file my_run.fit                  # any brand; also the .zip Garmin exports
python analyze_activity.py --fit-file my_swim.fit --sport swim    # --sport only when the file does not say it
python analyze_activity.py --strava-json strava_run.json          # Strava API data saved as JSON (see below)
```
(`analyze_activity.py` is in `skills/rampwise-aerobic-base/scripts/`.) Add `--json` for machine-readable output.

## What "FIT from another brand" means
FIT is one public file format, defined by Garmin's FIT SDK, that Garmin, Wahoo, COROS, Suunto and Polar all write ([Garmin FIT protocol](https://developer.garmin.com/fit/articles/fit-protocol/fit_protocol.html); a [general guide](https://the5krunner.com/tools/fit-file/); [Polar's export page](https://support.polar.com/us-en/export-training-sessions-flow) lists FIT). Every maker has its own manufacturer and product IDs and fills in different optional fields; one analysis found vertical speed only in Suunto files and satellite data only in COROS files ([the5krunner](https://the5krunner.com/2024/02/12/garmin-fit-files-welcomed-improvements-for-2023-4-is-there-a-downside/)). So the reader is tolerant:

| What a file may lack | What Rampwise does |
|---|---|
| speed | works it out from distance and time (5-second window) and says so |
| altitude under the usual name | reads either altitude field |
| total ascent | skips the hilly-ground check and says so |
| heart rate | stops with "no heart-rate data in this file" |
| local-time offset | shows UTC and says so |
| a damaged tail | uses what could be read and says so |
| lap data (swims, multisport) | no swim drift; says to use the watch's own FIT export |

It never reads GPS positions. Garmin heart-rate zones come from your Garmin account, so for other files the time-in-zone line is left out.

**Tested only on synthetic files** built from the public FIT layout (`tests/make_fit_activity.py`), not on real files from COROS, Wahoo, Suunto or Polar watches. If a real file fails, please open an issue with the message (not the file: it holds your route).

## Getting a FIT file out of each app
Only the facts below were seen in vendor or search sources on 2026-11-17; check your own app, they change.
- **Garmin Connect:** activity page, gear menu, Export Original (a .zip that works as is).
- **Polar Flow (web):** export a session as GPX, TCX, CSV or FIT ([Polar](https://support.polar.com/us-en/export-training-sessions-flow)); web only, not the phone app.
- **COROS:** the COROS support page covers importing .fit and .tcx ([COROS](https://support.coros.com/hc/en-us/articles/23909104424084)); exporting a single activity as FIT was described only by a third-party guide.
- **Wahoo and Suunto:** no official page was read. Wahoo is reported to record FIT; Suunto's FIT export is reported inconsistently.
- **Apple Watch, Fitbit, Amazfit:** not checked; they do not use FIT as their main format as far as this project knows.

## Strava
**Status: written to Strava's documented field names, never run against a real account** (the maintainer has no Strava subscription). Treat it as a draft until someone reports back.

What Strava's API gives (official [API reference](https://developers.strava.com/docs/reference/), read 2026-11-17): activity summary fields (`id`, `name`, `sport_type`, `start_date_local`, `elapsed_time`, `moving_time`, `distance`, `average_heartrate`, `average_watts`, `total_elevation_gain`, `device_name`) and **streams** (`GET /activities/{id}/streams` with `key_by_type=true`: `time` in seconds, `heartrate` in bpm, `velocity_smooth` in m/s, `altitude` in m, `cadence`, `watts`, `distance` in m). It does **not** give the original FIT file, so there are no watch-marked laps, no swim lengths and no multisport legs: Strava swims and multisport cannot be analysed this way (use the watch's own FIT export). Strava's speed stream is smoothed.

How to use it with a Strava MCP server or script:
1. Ask the agent to fetch the activity and its streams (`time`, `heartrate`, `velocity_smooth`, `altitude`, `cadence`, `watts`, `distance`) through your Strava tool.
2. Save them as one JSON file: `{"activity": {...}, "streams": {...}}`. `streams` may be `{"heartrate": {"data": [...]}}`, `{"heartrate": [...]}` or a list of `{"type": "heartrate", "data": [...]}`, because servers differ.
3. Run `analyze_activity.py --strava-json FILE`.

Things to know before you connect Strava:
- **Creating a Strava API app needs a Strava subscription** ("A Strava subscription is a prerequisite for creating an app", [getting started](https://developers.strava.com/docs/getting-started/)). A new app starts in single-athlete mode (only your own account), with 200 requests per 15 minutes and 2,000 per day.
- **Terms.** The API Agreement (effective 2026-06-01, [strava.com/legal/api](https://www.strava.com/legal/api)) says data from a user may only be displayed or disclosed to that user in your application. The page we read had no clause about AI or machine learning, but 2024-2026 news reports describe such a restriction and whether sending your own data to an AI assistant is allowed was reported as unresolved ([TechRepublic](https://techrepublic.com/article/news-strava-api-scraping-crackdown)). **Read the current agreement yourself and decide**; Rampwise itself only reads the JSON file you give it and sends nothing anywhere, but the AI model you use will see that data.
- **MCP servers** for Strava exist (for example gcoombe/strava-mcp, [tomekkorbak/strava-mcp-server](https://github.com/tomekkorbak/strava-mcp-server) and r-huijts/strava-mcp, as listed by search results). We have not read or run any of them. They are third-party code that holds your Strava token: read before you install.

## What is still Garmin-only
`latest_activity.py`, `week_compare.py`, `load_check.py`, readiness, reports, the dashboard and the daily adaptation read activities and sleep/HRV from your Garmin account. Supporting another brand end to end would need a data source for each of them; that is not built. A plan from `plan.py` works for anyone (it asks for your numbers), and the plan's calendar, spreadsheet, Zwift and trainer-app files work with any watch; the Garmin `.fit` workout files are Garmin's workout layout.
