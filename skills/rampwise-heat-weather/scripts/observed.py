#!/usr/bin/env python3
"""Observed weather for a past (or current) session, from Open-Meteo (no key).

Only coordinates (rounded to 2 decimals, ~1 km) and dates are sent to open-meteo.com. Never Garmin data,
names or anything else. Callers must have the user's approval first (see weather_check.py).

Source choice: the forecast API serves the last ~92 days (including yesterday), the archive API serves
older dates (it lags a few days). Heat adjustment comes from `weather.heat_pct` (upstream, MIT).
"""
import json
import statistics
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta

FORECAST = "https://api.open-meteo.com/v1/forecast"
ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
HOURLY = ("temperature_2m,relative_humidity_2m,dew_point_2m,apparent_temperature,wind_speed_10m,"
          "wind_direction_10m,precipitation,cloud_cover,shortwave_radiation")
KEYS = ("temperature_2m", "relative_humidity_2m", "dew_point_2m", "apparent_temperature", "wind_speed_10m",
        "wind_direction_10m", "precipitation", "cloud_cover", "shortwave_radiation")


def _get(url, params):
    with urllib.request.urlopen(f"{url}?{urllib.parse.urlencode(params)}", timeout=20) as r:
        return json.load(r)


def conditions(lat, lon, start, minutes):
    """Mean conditions over a session. start: naive local datetime. Returns dict or {'error': ...}."""
    lat, lon = round(float(lat), 2), round(float(lon), 2)
    end = start + timedelta(minutes=max(minutes, 30))
    days_ago = (date.today() - start.date()).days
    url = FORECAST if days_ago <= 90 else ARCHIVE
    try:
        data = _get(url, {"latitude": lat, "longitude": lon, "hourly": HOURLY, "timezone": "auto",
                          "start_date": start.date().isoformat(), "end_date": end.date().isoformat()})
    except Exception as e:                      # offline, API change, lag: analysis goes on without weather
        return {"error": str(e)}
    h = data.get("hourly") or {}
    lo = start.replace(minute=0, second=0, microsecond=0)
    rows = []
    for i, t in enumerate(h.get("time", [])):
        dt = datetime.fromisoformat(t)
        if lo <= dt <= end:
            rows.append({k: h[k][i] for k in KEYS if h.get(k) and h[k][i] is not None})
    if not rows:
        return {"error": "no hourly rows (archive lags ~5 days for the most recent dates)"}

    def mean(k):
        v = [r[k] for r in rows if k in r]
        return round(statistics.mean(v), 1) if v else None

    out = {"source": "forecast-api" if url == FORECAST else "archive-api", "hours": len(rows),
           "temp_c": mean("temperature_2m"), "temp_max_c": max(r["temperature_2m"] for r in rows if "temperature_2m" in r),
           "dew_c": mean("dew_point_2m"), "humidity_pct": mean("relative_humidity_2m"),
           "apparent_c": mean("apparent_temperature"), "wind_kmh": mean("wind_speed_10m"),
           "wind_dir_deg": mean("wind_direction_10m"), "rain_mm": round(sum(r.get("precipitation", 0) for r in rows), 1),
           "cloud_pct": mean("cloud_cover"), "solar_wm2": mean("shortwave_radiation")}
    return out


def comparability_key(c):
    """Sessions are comparable for HR/pace trends when temperature and dew point are close.
    Practical bins (a working rule, not a published threshold): 3 C wide."""
    if not c or c.get("temp_c") is None:
        return None
    return (round(c["temp_c"] / 3), round((c.get("dew_c") or 0) / 3))
