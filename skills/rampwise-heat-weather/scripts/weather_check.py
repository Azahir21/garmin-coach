#!/usr/bin/env python3
"""Weather and heat context for a Garmin session (opt-in: sends coordinates + dates to open-meteo.com).

Usage:
  weather_check.py --activity-id ACTIVITY_ID --approved [--json]
  weather_check.py --lat 51.5 --lon -0.12 --start "2026-11-14 04:51" --minutes 193 --approved [--json]

Consent gate: without --approved (or env RAMPWISE_WEATHER_OK=1) nothing is sent anywhere.
Heat adjustment: `weather.heat_pct` from tomasstankovic/running-coach (MIT): above 15 C air temperature,
1-2 % slower per 5 C, the upper end when dew point >= 15 C. It is a coaching estimate, not a validated
formula; see ../references/sources.md for what the papers do and do not support (air temperature is the
dominant parameter in El Helou 2012; dew point/humidity showed no significant effect in that dataset).
For heart-rate-led training the useful reading is: expect HR to run higher at the same pace in the heat,
so hold HR and let pace/speed fall.
"""
import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "rampwise" / "scripts"))

import gcommon  # noqa: E402
import observed  # noqa: E402
import weather  # noqa: E402  (upstream, unmodified)


def main():
    gcommon.utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--activity-id", type=int)
    ap.add_argument("--lat", type=float)
    ap.add_argument("--lon", type=float)
    ap.add_argument("--start", help='local start, "YYYY-MM-DD HH:MM"')
    ap.add_argument("--minutes", type=float, default=60)
    ap.add_argument("--approved", action="store_true", help="the user approved the weather lookup")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    if not (a.approved or (os.environ.get("RAMPWISE_WEATHER_OK") or os.environ.get("GARMIN_COACH_WEATHER_OK")) == "1"):
        sys.exit("Weather lookup not approved. It sends only rounded coordinates and dates to open-meteo.com. "
                 "Ask the user, record the answer in profile.md, then run again with --approved.")

    if a.activity_id:
        with gcommon.Garmin() as g:
            s = gcommon.activity_summary(g, a.activity_id)
        lat, lon, start, minutes = s["lat"], s["lon"], s["start"], s["min"]
        label = f"{s['sport']} {s['start']:%Y-%m-%d %H:%M}, {s['min']:.0f} min"
        if lat is None or lon is None:
            sys.exit("this activity has no start position (indoor?): weather does not apply")
    else:
        if None in (a.lat, a.lon, a.start):
            sys.exit("give --activity-id, or --lat --lon --start")
        lat, lon, start, minutes = a.lat, a.lon, datetime.fromisoformat(a.start), a.minutes
        label = f"{start:%Y-%m-%d %H:%M}, {minutes:.0f} min"

    c = observed.conditions(lat, lon, start, minutes)
    if c.get("error"):
        sys.exit(f"no weather: {c['error']}")
    lo, hi = weather.heat_pct({"temp_c": c["temp_c"], "dew_c": c["dew_c"], "source": "forecast"})
    c["heat_pct"] = [lo, hi]
    c["humid"] = bool((c.get("dew_c") or 0) >= weather.HUMID_DEW)
    c["comparability_bin"] = observed.comparability_key(c)
    c["label"] = label
    if a.json:
        print(json.dumps(c, ensure_ascii=False))
        return
    print(f"{label}: {c['temp_c']} C (max {c['temp_max_c']}), feels {c['apparent_c']} C, dew point {c['dew_c']} C, "
          f"humidity {c['humidity_pct']}%, wind {c['wind_kmh']} km/h, rain {c['rain_mm']} mm, cloud {c['cloud_pct']}%, "
          f"sun {c['solar_wm2']} W/m2  [{c['source']}]")
    print("heat: no pace adjustment expected" if not hi else
          f"heat: about {lo:g}-{hi:g} % slower than in cool weather (coaching estimate); HR runs higher at a given pace"
          + ("; dew point >= 15 C, so the upper end is shown. That humid-weather step is a coaching convention: in El Helou 2012 "
             "dew point and humidity had no significant effect once air temperature was accounted for" if c["humid"] else ""))


if __name__ == "__main__":
    main()
