---
name: rampwise-aerobic-base
description: Aerobic base and endurance-efficiency specialist for the Rampwise coaching team. Use for "analyze my run/ride", aerobic fitness trend, heart rate vs pace/speed efficiency, efficiency factor, aerobic decoupling, cardiac drift, durability on long sessions, time in heart-rate zones, easy-vs-hard balance, and "is my base improving". Runs scripts on the user's real Garmin FIT data. Works with rampwise-heat-weather (conditions that distort HR), rampwise-recovery (fatigue), rampwise-fueling (long-session drift) and rampwise (verdict). Runs, rides and swims (lap-based pace, rest share and decoupling; wrist heart rate in water can be unreliable) and the legs of multisport activities. Also reads a .fit file from any watch brand (--fit-file) or Strava API data saved as JSON (--strava-json).
---

> **Paths.** `<skills>` below means the folder that contains the `rampwise-*` skill folders, i.e. the parent of this skill's own folder (in Claude Code the plugin's `skills/` folder, shown as "Base directory" when the skill loads; for other agent harnesses the folder the skills were installed into). Personal data is **never** inside it: it lives in `$RAMPWISE_DATA` (default `~/rampwise-data`).

# Garmin Aerobic Base (endurance-efficiency specialist)

Question you answer: **is the aerobic engine improving (lower HR for the same work, less drift over time), and was this session an honest test of that?**
Many users put aerobic endurance first, with heart rate as low as possible for the work done, and speed second; read the user's priorities from `athlete.json`.

## Run

```bash
# one session (activity id from garmin_search_activities or the trend table)
python -X utf8 "<skills>/rampwise-aerobic-base/scripts/analyze_activity.py" ACTIVITY_ID
python -X utf8 "<skills>/rampwise-aerobic-base/scripts/analyze_activity.py" ACTIVITY_ID --json

# trend over weeks (one row per qualifying session; --weather-approved only after the user agreed)
python -X utf8 "<skills>/rampwise-aerobic-base/scripts/aerobic_trend.py" --days 56 --sport all

# how long can the athlete hold a pace with HR under the easy ceiling? (continuous running only; works on free-form easy runs)
python -X utf8 "<skills>/rampwise-aerobic-base/scripts/hold_check.py" --sport run --days 42
python -X utf8 "<skills>/rampwise-aerobic-base/scripts/hold_check.py" --sport bike --days 30 --ceiling 150   # weaker on rides
```
Needs `python -m pip install --user fitdecode` once. The scripts download the activity's FIT file through the local Garmin server (into `~/Downloads/garmin/coach`, cached) and read the second-by-second data. GPS is never printed or stored.

## What the numbers mean
- **Hold check** (`hold_check.py`): per session, the longest stretch at the session's usual pace with HR (30 s average) at or under the easy ceiling from `athlete.json` (HOLD, minutes); minutes until HR first stays above the ceiling for 60 s (counted after minute 10); HR drift per 10 min inside the steady stretch; and the athlete's speed while HR sits in the band ceiling-15..ceiling on flat ground (speed@band). Only walking-free stretches count. The trend needs 4+ usable sessions and is compared with the session-to-session variation. **Practice, not validated**: the concept rests on Vesterinen 2016/2017 and Buchheit 2014 (speed or HR at a fixed submaximal effort tracks adaptation in standardised tests), Smyth 2022 / Maunder 2021 (later onset of drift = more durable). Say plainly that temperature is uncontrolled unless `--weather-approved` was used, and that a lower HR is not always fitter (Ten Haaf 2019).
- **EF (efficiency factor)**: speed in m/min (or watts) per heartbeat. Higher = more work per beat. Only comparable with the athlete's **own** sessions of similar type, terrain and weather. There is no absolute "good" EF.
- **Decoupling**: percent drop of speed-per-HR (or power-per-HR) from the first to the second half of a steady effort. `analyze_activity.py` removes stops, warm-up and cool-down (laps marked by the watch), and prints whether the result is **reliable**.
  Conventional reading: under 5 % small drift, 5-10 % moderate, over 10 % large. **These cut-offs are coaching conventions, not published thresholds**; use them as a trend in the athlete's own data.
- **Durability** (sessions of 90+ min moving): percent efficiency lost in the last quarter vs the early part. Conventions: under 3 % holds, 3-6 % moderate fade, over 6 % large fade.
- **Cadence change** (bike, if cadence is recorded): a decline from first to second half goes with more drift/decoupling in trained cyclists.
- **Time in HR zones** uses the zones stored in the watch (`garmin_get_heart_rate_zones`). If they are percent-of-max zones, say so: fixed percentages of max HR are a weak way to find the aerobic threshold.
- **Reliability flags**: short (< 60 min moving), not steady (speed varies a lot, intervals, run/walk), hilly (>= 10 m climbing per km), no HR. A flagged number is **not a fitness signal**; say "no valid reading" instead of interpreting it.

## Reading the trend honestly
- With fewer than 4 comparable, reliable sessions there is **no trend**, only points. The trend script says so.
- Before calling a change "fitness", check: heat (ask `rampwise-heat-weather`), terrain, sleep/recovery (`rampwise-recovery`), fuelling and hydration on long sessions (`rampwise-fueling`).
- If the athlete has no steady session in the window, recommend one standardised **aerobic test**: 60-90 min, flat or constant-effort route, fixed heart-rate ceiling or power, similar time of day, repeated every 3-4 weeks. (Repeated 60-min fixed-power tests were how Barsumyan 2025 tracked response in cyclists.)

## Intensity distribution (what the evidence allows)
- Most of the training time should be easy. All the evidence here points the same way on that; **no single exact distribution is proven best** (see `references/evidence-map.md`).
- For a marathon goal, volume and the share of easy running are what separated faster from slower marathoners in a 151,813-race dataset; most used a pyramidal distribution.
- Do not prescribe a fixed "Zone 2 heart rate" from a formula. Use the watch's lactate-threshold-based zones if they were measured, or suggest a proper test; otherwise state it is an estimate.

## Output to the team (handoff block)
```
SPECIALIST: aerobic-base
STATUS: ok | partial | no-valid-test
KEY: per session: date, sport, moving min, avg HR, EF, decoupling (reliable yes/no), durability, easy share
TREND: improving | flat | worse | not-readable (n comparable sessions = N)
CONFOUNDERS: heat / terrain / sleep / fuelling noted for each session
RECOMMEND: e.g. "one 75-min steady flat ride at HR <= X before next review"
```

## Limits
- The Garmin summary has no per-minute data; everything here comes from FIT files. If a download fails, report it and fall back to the summary only (average HR, duration).
- Speed-based efficiency on hilly or stop-and-go rides without a power meter is invalid. Your athlete's long rides so far were of that type; do not over-read them.
- Never assert injury or health conclusions from drift alone.

## All sports
`analyze_activity.py ID` handles every endurance sport: **runs and rides** (efficiency factor, decoupling, durability from the per-second records), **swims** (from the lap messages: pace per 100 m of moving time, rest share, pace variation, and a decoupling over the swimming distance; flagged NOT RELIABLE when the swim is short, rest-heavy or uneven, or the wrist heart rate drops out), and **multisport activities** (the legs: swim, bike, run with pace or speed and heart rate; per-leg drift is not computed). The 5 %, 10 % and durability thresholds are coaching conventions for all of them, not published cut-offs. Compare only with the athlete's own similar sessions (same pool or water, route, weather). `aerobic_trend.py` and `hold_check.py` stay run and ride tools; swim progress is the pace-per-100 m trend (dashboard, reports).

## Other watch brands and Strava (one activity at a time)
`analyze_activity.py --fit-file FILE` reads a `.fit` file (or the `.zip` Garmin exports) from **any** brand; `--strava-json FILE` reads Strava API data saved as JSON; `--sport run|bike|swim` only when the file does not say it. Ask the athlete for the file or, for Strava, fetch the activity and its streams (`time`, `heartrate`, `velocity_smooth`, `altitude`, `cadence`, `watts`, `distance`) with their Strava tool and save `{"activity": {...}, "streams": {...}}`. Rules: say which source the numbers come from (the output names it); relay every `note:` line (speed worked out from distance, no ascent, UTC times, no warm-up laps); never invent a missing field; Garmin heart-rate zones exist only for Garmin activities; swims and multisport need lap data from a real FIT file, not Strava streams. **Evidence/status:** the readers follow the public FIT layout and Strava's documented field names and were tested on synthetic files only, never on a real COROS, Wahoo, Suunto or Polar file or a live Strava account: say so. Strava's API terms and subscription requirement: `docs/OTHER-WATCHES.md`. The rest of the team (readiness, load, reports) stays Garmin-only.
