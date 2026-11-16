---
name: garmin-heat-weather
description: Heat, weather and external-conditions specialist for the Garmin coaching team. Use when heart rate runs high or pace/speed is slow and the athlete asks why, for "was it the heat", weather during a session, how hot weather changes training or racing, heat acclimatisation, hydration in the heat, wind/rain/humidity effects, and before judging any HR-based trend. Looks up the observed weather of a Garmin session (opt-in, only coordinates and dates leave the machine) and applies evidence-labelled heat adjustments. Works with garmin-aerobic-base (corrects its comparisons), garmin-fueling (hydration in heat), garmin-recovery and garmin-coach.
---

> **Paths.** `<skills>` below means the folder that contains the `garmin-*` skill folders, i.e. the parent of this skill's own folder (in Claude Code the plugin's `skills/` folder, shown as "Base directory" when the skill loads; for other agent harnesses the folder the skills were installed into). Personal data is **never** inside it: it lives in `$GARMIN_COACH_DATA` (default `~/garmin-coach-data`).

# Garmin Heat and Weather (external-conditions specialist)

Question you answer: **how much of what we see in HR, speed and drift is the weather, and how should training or racing adapt?**
When the goal is heart rate as low as possible for the work done, heat is the biggest confounder: a hot session will show a higher HR at the same speed and must not be read against a cool one.

## Consent first (privacy)
The weather lookup sends **only rounded start coordinates and dates** to open-meteo.com (no key, no Garmin data, no name). It is opt-in:
1. Check `garmin-coach/profile.md` for `weather_lookup_approved`. If blank, ask once: "May I look up the weather for your sessions? Only the start location (rounded to about 1 km) and the date are sent to open-meteo.com." Record yes/no in the profile.
2. Pass `--approved` to the scripts only after a yes. Without it the script refuses and sends nothing.
3. Indoor activities have no start position: weather does not apply.

## Run

```bash
python -X utf8 "<skills>/garmin-heat-weather/scripts/garmin_weather.py" --activity-id ACTIVITY_ID --approved
python -X utf8 "<skills>/garmin-heat-weather/scripts/garmin_weather.py" --activity-id ACTIVITY_ID --approved --json
python -X utf8 "<skills>/garmin-heat-weather/scripts/acclimation_decay.py" --days-since-heat 14
# forecast for planning (up to 16 days ahead; upstream script, coordinates of the athlete's town; needs consent too)
python -X utf8 "<skills>/garmin-heat-weather/scripts/weather.py" --lat 00.00 --lon 00.00 --date 2026-12-05 --start 05:30 --hours 2
```
`garmin_weather.py` returns temperature, dew point, humidity, apparent temperature, wind, rain, cloud, solar radiation, a heat adjustment and a comparability bin (3 C temperature and 3 C dew-point bins; sessions in the same bin can be compared for HR/speed trends).

## How to read it (evidence in `references/evidence-map.md`)
- **Air temperature is the main factor** in the largest dataset read (El Helou 2012, about 1.8 million marathon finishes): performance followed a quadratic curve with temperature, the best temperature depends on runner level, and above it speed falls and withdrawal rises. Humidity, dew point and pressure had **no significant effect** there; ozone mattered only together with temperature.
- Magnitude: in marathon results across WBGT bands of 5-25 C, top men were 1.7 %, 2.5 %, 3.3 % and 4.5 % slower than course record from the coolest to the warmest band; slower runners are affected more (Ely 2007). In 11 elite cyclists a 30-min time trial at 32 C (60 % humidity) produced 6.5 % lower power than at 23 C, with similar rectal temperature (Tatterson 2000).
- The script's pace estimate (above 15 C: 1-2 % slower per 5 C) comes from the upstream repo and is the same order of magnitude as Ely 2007. It is a **coaching estimate, not a validated formula**; the extra step for humid weather is a convention that El Helou 2012 does not support.
- **For HR-led training: hold the HR zone and let pace/speed fall.** In heat the same speed costs more heart rate, so judge aerobic work by effort/HR and compare like with like.
- **Acclimatisation**: repeated exercise-heat exposure over 1-2 weeks is the single most important intervention (Racinais 2015 consensus); longer regimens worked better than shorter ones in a 96-article meta-analysis (Tyler 2016). Gains fade without exposure at about 2.3 % (HR) and 2.6 % (core temperature) of the adaptation per day (Daanen 2018): `acclimation_decay.py`.
- **Safety**: exertional heat stroke is among the leading life-threatening conditions in sport but is preventable and treatable (Racinais 2023 IOC consensus). There is **no universal WBGT cut-off**: the same 30.6 C WBGT was "orange", "red" and "black" in different governing bodies' systems. Recommend earlier/cooler sessions, shade, cooling, euhydration and shorter or indoor sessions in dangerous heat; and for confusion, collapse or stopped sweating, treat as an emergency.

## Output to the team (handoff block)
```
SPECIALIST: heat-weather
STATUS: ok | no-consent | no-position | lookup-failed
PER_SESSION: id, temp C, dew C, humidity, wind, rain, heat_pct range, comparability bin
ADJUST: "expect HR +X at same speed" is NOT quantified here; say "HR will run higher; hold zone, let pace fall"
COMPARABLE_WITH: other session ids in the same bin
RISK: none | caution | high (qualitative; no universal WBGT cut-off)
```

## Limits
- Weather comes from gridded model data for the start location, not from a station on the exact road. Wind direction relative to the route is not known.
- No heat-index numbers beyond the upstream estimate are validated for cycling; only Tatterson 2000 gives a cycling data point.
- Altitude, surface, hills and shade are not modelled here.
