# Sport coverage: what each skill does for triathlon, duathlon, running, cycling, swimming and strength

Checked against the code on 2026-11-17 (updated after the one-planner change). **yes** = works for that sport; **partial** = counted or shown but no sport-specific rule; **no** = not covered (a known gap).

| Skill | Run | Ride | Swim | Brick (bike then run) | Strength | Gap or note |
|---|---|---|---|---|---|---|
| rampwise (head coach) | yes | yes | yes | yes | yes | routing covers event plans, brick check |
| rampwise-recovery | yes | yes | yes | yes | yes | sport-neutral (HRV, sleep, resting heart rate) |
| rampwise-aerobic-base | yes | yes | yes | legs | n/a | swims from lap data (reliability flags; wrist HR in water can drop out); multisport shown as legs; trend and hold checks stay run and ride; `--fit-file` / `--strava-json` read one activity from any watch brand or Strava (synthetic tests only, see OTHER-WATCHES.md) |
| rampwise-heat-weather | yes | yes | yes (open water) | partial | n/a | `swim_water.py` gives water-temperature guidance (weak evidence); stop rule for all sports; no WBGT cut-off (no source read) |
| rampwise-load-injury | yes | yes (extrapolation) | partial (no rule: none supported) | partial | partial | swims and multisport counted in weekly minutes; bricks counted, more than 2 in 7 days is noted; the 10 % single-run rule is research for running only; chronic/acute load (CTL, ATL, TSB) comes from Garmin's per-activity load for any sport the watch scores, context only (practice), no flag |
| rampwise-strength | n/a | n/a | n/a | n/a | yes | swims and multisport count as cardio for the 3-hour gap; goal profiles for runner, cyclist, triathlon |
| rampwise-fueling | partial | partial | no | no | n/a | hydration and carbohydrate principles for all sports (ACSM 2007, Jeukendrup 2011, Mougin 2025); daily cut, bulk and meal-plan targets come from resistance-training and physique research and sports-nutrition position stands (Helms 2014, Iraki 2019, Morton 2018, Kerksick 2017, 2018), reasonable for endurance athletes but not proven for them; race-day timeline from Kerksick 2017; no source read for triathlon-specific targets, swim or duathlon fuelling |
| rampwise-planner: one planner (`plan.py`; `build_plan.py` forwards) | yes | yes | yes | yes | yes | race or no-target base goal; `--from-garmin`; heart-rate workouts and .fit for run and ride when HR data are known |
| rampwise-analyze | yes | yes | yes | yes | yes | swim pace per 100 m (moving time, rests excluded); brick run against your last normal run; injury flags count swim minutes |
| rampwise-adapt | yes | yes | yes | yes | yes | event plans and Garmin-history plans; no `.fit` file for event plans; swim and brick rules are practice |
| rampwise-report | yes | yes | yes | yes | yes | swim in charts and tables; a Bricks section when there are bricks |
| rampwise-dashboard (private) | yes | yes | yes | yes | yes | Swimming and Multisport pages added |

## Rules specific to swim and brick (labels)
- Brick runs: research for the extra energy cost of running after cycling (Walsh 2019 full text; Millet and Vleck 2000 abstract), gap for any training benefit; dropped by the adapter on amber or red, cut to 10 minutes with leg-pain history. See `rampwise-planner/references/evidence-map.md`.
- Swim adaptation (shorter, easy, or a short technique-only swim on red): practice; no study read.
- Swim injury risk (for example shoulder load): **no study read, no rule**. Ask the athlete about shoulder pain; record it with `athlete.py check-in`.

## Still open
Triathlon-specific fuelling targets, a WBGT cut-off, a swim volume rule and a ride spike rule (no study read for any), run-bike-run sessions for duathlon, `.fit` for swims, per-leg drift for multisport, and removing `build_plan.py --legacy`.
