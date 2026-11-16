# Field test: one person, three months

**Honest framing.** This is a single-person, uncontrolled test (n = 1). It can show whether the plans were practical and whether the numbers the user chose to track moved. It cannot show that the system caused any change: sleep, weather, motivation, illness and other life factors are not controlled.

## Who and what
The author follows the plans for 3 months from the release date and reports honestly, including failures. Goals and numbers are the user's own and are not claimed as typical.

## What is tracked (from the user's own Garmin data and settings)
| Measure | How | Frequency |
|---|---|---|
| Progress on each of the user's own goals | the script that matches the goal (for example `ride_check.py`, `run_gate.py`, `paces.py`) | monthly |
| Pace (or speed) at a fixed easy heart rate | a MAF-style test on the same course, if the user uses one | monthly |
| Resting HR, HRV band, sleep | `garmin_readiness.py` | weekly |
| Weekly volume, rest days, spikes | `load_check.py` | weekly |
| Sessions done as planned (%), sessions skipped and why | the user's notes | weekly |
| Injuries or pain episodes | `athlete.py` notes | as they happen |
| What was wrong, confusing or unsafe in the plans | the user's notes | as they happen |

## What gets published
Only what the author approves: trends in general terms and the list of problems found. No raw health data, locations or identifiers. Updates are added below with the date and the release version used.

## Results log
| Date | Release | Summary | Problems found |
|---|---|---|---|
| (starts at release) | | | |
