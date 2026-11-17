#!/usr/bin/env python3
"""Activities that do not come from Garmin's server: a FIT file from ANY watch brand, or Strava API data saved as JSON.

Why this exists: FIT is one public file format (Garmin's FIT SDK) that Garmin, Wahoo, COROS, Suunto, Polar and others write, but each maker fills in
different optional fields (some files carry no speed, some no heart rate, some store altitude under another name), and the manufacturer and product IDs
differ. These readers are tolerant: they use what is there, derive speed from distance when needed, and say so when something is missing.

Both loaders return one dict:
  {"summary": {id, name, type, sport, start, km, min, gain_m, avg_hr, avg_power, lat, lon, location},
   "recs":     [{t, hr, speed, alt, power, cadence, dist}, ...]      per-second records (GPS positions are never read)
   "laps":     [{start, end, intensity}, ...]                        laps marked by the watch (FIT only)
   "lap_msgs": [raw FIT lap dicts],  "session_msgs": [raw FIT session dicts]   (FIT only: used for swims and multisport)
   "origin":   {"kind", "manufacturer", "product", "device", "notes": [...]}}

Strava route: Strava's API gives summary fields and "streams" (time, heartrate, velocity_smooth, altitude, cadence, watts, distance), not the original FIT
file. An agent fetches them with whichever Strava MCP server or script you use and saves one JSON file: {"activity": {...}, "streams": {...}}. Stream sets
are accepted as {"heartrate": {"data": [...]}}, as {"heartrate": [...]}, or as a list of {"type": "heartrate", "data": [...]}. This reader follows the field
names in Strava's API reference (developers.strava.com) and has NOT been run against a live Strava account.
"""
import io
import json
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

import gcommon

NO_GPS = ("position_", "start_position", "end_position", "nec_", "swc_")


# ---------------------------------------------------------------- FIT file from any brand
def read_messages(data, kinds=("file_id", "session", "lap", "record", "activity")):
    """Raw FIT messages of the given kinds as plain dicts (GPS positions are dropped)."""
    try:
        import fitdecode
    except ImportError:
        raise SystemExit("the fitdecode package is missing: add it once with pip (README, Setup)")
    out = {k: [] for k in kinds}
    try:
        with fitdecode.FitReader(io.BytesIO(data), error_handling=fitdecode.ErrorHandling.IGNORE) as fr:
            for f in fr:
                if isinstance(f, fitdecode.FitDataMessage) and f.name in out:
                    out[f.name].append({fld.name: fld.value for fld in f.fields if not fld.name.startswith(NO_GPS)})
    except Exception as e:                                   # a damaged file: keep what was read, say so
        out.setdefault("_error", []).append(str(e))
    return out


def _sport_key(sport, sub):
    s, u = str(sport or "").lower(), str(sub or "").lower()
    if s in ("training", "fitness_equipment") and ("strength" in u or u in ("strength_training", "hiit")):
        return "strength_training"
    if s in ("multisport", "triathlon") or "multi" in s:
        return "multisport"
    if s == "swimming":
        return "open_water_swimming" if "open" in u else "lap_swimming"
    if s == "cycling" and "e_bike" in u:
        return "cycling"
    return s or "other"


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def _derive_speed(recs, window_s=5.0):
    """Speed (m/s) from distance and time when a device wrote no speed field. Returns True if anything was derived."""
    if any(r.get("speed") is not None for r in recs) or sum(1 for r in recs if r.get("dist") is not None) < 10:
        return False
    k = 0
    for i, r in enumerate(recs):
        if r.get("dist") is None or i == 0:
            continue
        while k < i - 1 and r["t"] - recs[k]["t"] > window_s:
            k += 1
        kk = min(k, i - 1)
        while kk < i - 1 and recs[kk].get("dist") is None:
            kk += 1
        dt = r["t"] - recs[kk]["t"]
        if recs[kk].get("dist") is not None and dt >= 1:
            r["speed"] = max(0.0, (r["dist"] - recs[kk]["dist"]) / dt)
    return True


def load_fit_file(path, sport=None):
    p = Path(path).expanduser()
    if not p.exists():
        raise SystemExit(f"file not found: {p}")
    data = gcommon.fit_bytes(p)
    m = read_messages(data)
    notes = []
    if m.get("_error"):
        notes.append(f"the file is damaged or was cut short ({m['_error'][0][:80]}): the part that could be read is used")
    sessions, recs_raw = m["session"], m["record"]
    if not recs_raw:
        raise SystemExit("no per-second records in this file (is it an activity file? workout and course files have none)")
    fid = (m["file_id"] or [{}])[0]
    manu, prod = fid.get("manufacturer"), fid.get("garmin_product") or fid.get("product")
    first = sessions[0] if sessions else {}
    if len(sessions) > 1:
        key = "multisport"
    else:
        key = _sport_key(first.get("sport"), first.get("sub_sport"))
    t0 = next((r["timestamp"] for r in recs_raw if r.get("timestamp") is not None), None)
    recs = []
    for r in recs_raw:
        ts = r.get("timestamp")
        if ts is None:
            continue
        sp = r.get("enhanced_speed")
        if sp is None:
            sp = r.get("speed")
        alt = r.get("enhanced_altitude")
        if alt is None:
            alt = r.get("altitude")
        recs.append({"t": (ts - t0).total_seconds(), "hr": r.get("heart_rate"), "speed": sp, "alt": alt, "power": r.get("power"),
                     "cadence": r.get("cadence"), "dist": r.get("distance")})
    if _derive_speed(recs) and any((r.get("speed") or 0) > 0 for r in recs):
        notes.append("this device wrote no speed field: speed was worked out from distance and time (5-second window)")
    laps = []
    for l in m["lap"]:
        st, el = l.get("start_time"), l.get("total_elapsed_time")
        if st is not None and el is not None and t0 is not None:
            s = (st - t0).total_seconds()
            laps.append({"start": s, "end": s + float(el), "intensity": str(l.get("intensity") or "").lower()})
    start = first.get("start_time") or t0
    act = (m.get("activity") or [{}])[0]
    if start is not None and act.get("local_timestamp") is not None and act.get("timestamp") is not None:
        start = start + (act["local_timestamp"] - act["timestamp"])           # the file carries the local-time offset
    elif start is not None:
        notes.append("the file has no local-time offset: times are UTC")
    dist_m = first.get("total_distance") if first.get("total_distance") is not None else next((r["dist"] for r in reversed(recs) if r.get("dist") is not None), 0)
    if len(sessions) > 1:
        dist_m = sum((x.get("total_distance") or 0) for x in sessions)
    elapsed = first.get("total_elapsed_time") if len(sessions) <= 1 and first.get("total_elapsed_time") is not None else (recs[-1]["t"] if recs else 0)
    if len(sessions) > 1:
        elapsed = sum((x.get("total_elapsed_time") or 0) for x in sessions)
    gain = first.get("total_ascent")
    avg_hr = first.get("avg_heart_rate") if first.get("avg_heart_rate") is not None else _mean(r["hr"] for r in recs)
    if not any(r["hr"] for r in recs):
        notes.append("no heart-rate data in this file: efficiency and drift cannot be calculated")
    name = f"{manu or 'unknown'} {prod or ''} {key}".replace("  ", " ").strip()
    summary = {"id": p.stem, "name": name, "type": key, "sport": gcommon.sport_of(key), "start": start.replace(tzinfo=None) if start else datetime.now(),
               "lat": None, "lon": None, "km": float(dist_m or 0) / 1000.0, "min": float(elapsed or 0) / 60.0, "gain_m": float(gain or 0),
               "avg_hr": avg_hr, "avg_power": first.get("avg_power"), "location": None}
    if gain is None:
        notes.append("no total ascent in this file: the hilly-ground check is skipped")
    if sport:
        summary["sport"], summary["type"] = sport, {"run": "running", "bike": "cycling", "swim": "lap_swimming"}.get(sport, sport)
    return {"summary": summary, "recs": recs, "laps": laps, "lap_msgs": m["lap"], "session_msgs": sessions,
            "origin": {"kind": "fit-file", "file": p.name, "manufacturer": str(manu) if manu is not None else None, "product": str(prod) if prod is not None else None, "notes": notes}}


# ---------------------------------------------------------------- Strava API data saved as JSON
STRAVA_TYPE = {"run": "running", "trailrun": "running", "virtualrun": "running", "ride": "cycling", "mountainbikeride": "cycling", "gravelride": "cycling",
               "ebikeride": "cycling", "emountainbikeride": "cycling", "virtualride": "cycling", "handcycle": "cycling", "velomobile": "cycling",
               "swim": "lap_swimming", "weighttraining": "strength_training", "workout": "strength_training", "crossfit": "strength_training"}


def _stream(streams, key):
    """List of values for a stream key from any of the shapes an MCP server may return, else None."""
    if isinstance(streams, list):
        for s in streams:
            if isinstance(s, dict) and s.get("type") == key:
                return s.get("data")
        return None
    if isinstance(streams, dict):
        v = streams.get(key)
        if isinstance(v, dict):
            return v.get("data")
        if isinstance(v, list):
            return v
    return None


def _first(*vals):
    for v in vals:
        if v is not None:
            return v
    return None


def load_strava_json(path, sport=None):
    p = Path(path).expanduser()
    obj = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(obj, list):
        act, streams = {}, obj
    else:
        act = obj.get("activity") or obj.get("summary") or {k: v for k, v in obj.items() if k not in ("streams", "stream_set", "laps")}
        streams = _first(obj.get("streams"), obj.get("stream_set"))
        if streams is None:
            streams = {k: obj[k] for k in obj if k in ("time", "heartrate", "velocity_smooth", "altitude", "cadence", "watts", "distance")}
    time = _stream(streams, "time")
    if not time:
        raise SystemExit("no 'time' stream in this JSON: ask the Strava tool for the streams time, heartrate, velocity_smooth, altitude, cadence, watts and distance")
    hr, vel, alt = _stream(streams, "heartrate"), _stream(streams, "velocity_smooth"), _stream(streams, "altitude")
    cad, pw, dist = _stream(streams, "cadence"), _stream(streams, "watts"), _stream(streams, "distance")
    at = lambda arr, i: (arr[i] if arr is not None and i < len(arr) else None)
    recs = [{"t": float(time[i]), "hr": at(hr, i), "speed": at(vel, i), "alt": at(alt, i), "power": at(pw, i), "cadence": at(cad, i), "dist": at(dist, i)} for i in range(len(time))]
    notes = []
    if hr is None:
        notes.append("no heartrate stream: efficiency and drift cannot be calculated")
    if _derive_speed(recs) and any((r.get("speed") or 0) > 0 for r in recs):
        notes.append("no velocity_smooth stream: speed was worked out from the distance stream")
    stype = str(act.get("sport_type") or act.get("type") or "").lower()
    key = STRAVA_TYPE.get(stype, stype or "other")
    start_s = act.get("start_date_local") or act.get("start_date")
    try:
        start = datetime.fromisoformat(str(start_s).replace("Z", "")[:19])
    except Exception:
        start = datetime.now()
        notes.append("no start time in the activity data")
    summary = {"id": act.get("id") or p.stem, "name": act.get("name") or p.stem, "type": key, "sport": gcommon.sport_of(key), "start": start, "lat": None, "lon": None,
               "km": float(act.get("distance") or 0) / 1000.0, "min": float(act.get("elapsed_time") or (recs[-1]["t"] if recs else 0)) / 60.0,
               "gain_m": float(act.get("total_elevation_gain") or 0), "avg_hr": _first(act.get("average_heartrate"), _mean(r["hr"] for r in recs)),
               "avg_power": act.get("average_watts"), "location": None}
    if sport:
        summary["sport"], summary["type"] = sport, {"run": "running", "bike": "cycling", "swim": "lap_swimming"}.get(sport, sport)
    notes.append("Strava gives no watch-marked warm-up or rest laps and its speed stream is smoothed: the first 10 minutes are skipped as warm-up")
    return {"summary": summary, "recs": recs, "laps": [], "lap_msgs": [], "session_msgs": [],
            "origin": {"kind": "strava-json", "file": p.name, "manufacturer": None, "product": None, "device": act.get("device_name"), "notes": notes}}


if __name__ == "__main__":
    import sys
    src = load_fit_file(sys.argv[1]) if sys.argv[1].lower().endswith((".fit", ".zip")) else load_strava_json(sys.argv[1])
    s = src["summary"]
    print(f"{s['name']}: {s['sport']}, {s['km']:.1f} km, {s['min']:.0f} min, {len(src['recs'])} records, {len(src['laps'])} laps")
    for n in src["origin"]["notes"]:
        print("note:", n)
