#!/usr/bin/env python3
"""Shared Garmin data layer for the rampwise skills.

What it does
  * talks to the LOCAL garmin-personal-mcp server over stdio (the same program Claude Code starts),
    so the scripts can fetch data themselves and large JSON never has to pass through the model;
  * lists and normalizes activities (sport = run | bike | strength | other);
  * downloads an activity's original FIT file (via the server's garmin_download_activity, which only
    allows the folder ~/Downloads/garmin/coach) and reads the per-second records.

Needs: Python 3.10+, the garmin-personal-mcp program with a saved key (`garmin-personal-mcp auth`),
and for FIT reading `python -m pip install --user fitdecode`.

Privacy: reads only your own Garmin data through your own server. GPS positions from FIT files are
never kept: only the start coordinates that Garmin already returns in the activity summary are used,
and only for the opt-in weather lookup.
"""
import io
import json
import os
import shutil
import subprocess
import sys
import threading
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path

def _data_dir():
    """RAMPWISE_DATA, else the older GARMIN_COACH_DATA, else ~/rampwise-data (or the older ~/garmin-coach-data if only that exists)."""
    env = os.environ.get("RAMPWISE_DATA") or os.environ.get("GARMIN_COACH_DATA")
    if env:
        return Path(env)
    new, old = Path.home() / "rampwise-data", Path.home() / "garmin-coach-data"
    return old if (old.exists() and not new.exists()) else new


DATA_DIR = _data_dir()
ATHLETE_PATH = DATA_DIR / "athlete.json"
FIT_SUBDIR = "coach"                      # the server only accepts folders inside ~/Downloads/garmin
SERVER_TIMEOUT_S = 180


def utf8_stdout():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except Exception:
            pass


def find_exe():
    """The command that starts the Garmin MCP server, as a list: GARMIN_MCP_EXE, the installed program, or uvx / uv tool run (no install needed)."""
    cand = [os.environ.get("GARMIN_MCP_EXE"), shutil.which("garmin-personal-mcp"),
            str(Path.home() / ".local" / "bin" / "garmin-personal-mcp.exe"),
            str(Path.home() / ".local" / "bin" / "garmin-personal-mcp")]
    for c in cand:
        if c and Path(c).exists():
            return [c]
    if shutil.which("uvx"):
        return ["uvx", "--python", "3.12", "garmin-personal-mcp"]
    if shutil.which("uv"):
        return ["uv", "tool", "run", "--python", "3.12", "garmin-personal-mcp"]
    raise SystemExit("garmin-personal-mcp not found. Install uv (https://docs.astral.sh/uv/) and run: uv tool install --python 3.12 garmin-personal-mcp "
                     "then: garmin-personal-mcp auth. Or set GARMIN_MCP_EXE to the program's full path.")


class GarminError(RuntimeError):
    pass


class Garmin:
    """Context manager: one server process, many tool calls."""

    def __init__(self):
        self._id = 1
        self.p = subprocess.Popen(find_exe(), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL, text=True, encoding="utf-8")
        self._timer = threading.Timer(SERVER_TIMEOUT_S, self.p.kill)
        self._timer.daemon = True
        self._timer.start()
        self._rpc("initialize", {"protocolVersion": "2025-03-26", "capabilities": {},
                                 "clientInfo": {"name": "rampwise", "version": "1"}})
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def _send(self, m):
        self.p.stdin.write(json.dumps(m) + "\n")
        self.p.stdin.flush()

    def _rpc(self, method, params):
        self._id += 1
        want = self._id
        self._send({"jsonrpc": "2.0", "id": want, "method": method, "params": params})
        while True:
            line = self.p.stdout.readline()
            if not line:
                raise GarminError("garmin server closed the connection (timeout or crash)")
            try:
                m = json.loads(line)
            except ValueError:
                continue
            if m.get("id") == want:
                if "error" in m:
                    raise GarminError(str(m["error"]))
                return m.get("result")

    def call(self, tool, **args):
        res = self._rpc("tools/call", {"name": tool, "arguments": {k: v for k, v in args.items() if v is not None}})
        text = (res.get("content") or [{}])[0].get("text", "")
        if res.get("isError"):
            raise GarminError(text[:400])
        try:
            return json.loads(text)
        except ValueError:
            return text

    def close(self):
        self._timer.cancel()
        try:
            self.p.stdin.close()
            self.p.wait(timeout=10)
        except Exception:
            self.p.kill()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


# ---------------------------------------------------------------- activities

RUN_KEYS = ("running",)
BIKE_KEYS = ("cycling", "biking", "bike", "ride", "gravel", "virtual_ride")
STRENGTH_KEYS = ("strength", "hiit", "fitness_equipment")


def sport_of(type_key):
    k = (type_key or "").lower()
    if any(x in k for x in RUN_KEYS):
        return "run"
    if any(x in k for x in BIKE_KEYS):
        return "bike"
    if any(x in k for x in STRENGTH_KEYS):
        return "strength"
    return "other"


def parse_local(s):
    return datetime.fromisoformat(str(s).replace("T", " ")[:19])


def normalize(a):
    """One row from garmin_search_activities results (summary level)."""
    start = parse_local(a["startTimeLocal"])
    dur = float(a.get("duration") or 0)
    return {
        "id": a["activityId"], "name": a.get("activityName"),
        "type": (a.get("activityType") or {}).get("typeKey"),
        "sport": sport_of((a.get("activityType") or {}).get("typeKey")),
        "start": start, "date": start.date(), "end": start + timedelta(seconds=dur),
        "km": float(a.get("distance") or 0) / 1000.0, "min": dur / 60.0,
        "moving_min": float(a.get("movingDuration") or dur) / 60.0,
        "avg_hr": a.get("averageHR"), "max_hr": a.get("maxHR"),
        "gain_m": float(a.get("elevationGain") or 0),
        "te_aerobic": a.get("aerobicTrainingEffect"), "te_anaerobic": a.get("anaerobicTrainingEffect"),
        "lat": a.get("startLatitude"), "lon": a.get("startLongitude"),
    }


def list_activities(g, start, end, page=100, max_pages=10):
    rows, offset = [], 0
    for _ in range(max_pages):
        res = g.call("garmin_search_activities", start=str(start), end=str(end), limit=page, offset=offset)
        chunk = res.get("results", []) if isinstance(res, dict) else []
        rows += [normalize(a) for a in chunk]
        if len(chunk) < page:
            break
        offset += page
    rows.sort(key=lambda r: r["start"])
    return rows


def activity_summary(g, activity_id):
    """Summary of one activity (start position, duration, elevation, HR, power)."""
    d = g.call("garmin_get_activity", activity_id=int(activity_id))
    s = d.get("summaryDTO", {})
    t = (d.get("activityTypeDTO") or {}).get("typeKey")
    return {
        "id": d.get("activityId"), "name": d.get("activityName"), "type": t, "sport": sport_of(t),
        "start": parse_local(s["startTimeLocal"]), "lat": s.get("startLatitude"), "lon": s.get("startLongitude"),
        "km": float(s.get("distance") or 0) / 1000.0, "min": float(s.get("duration") or 0) / 60.0,
        "gain_m": float(s.get("elevationGain") or 0), "avg_hr": s.get("averageHR"),
        "avg_power": s.get("averagePower"), "location": d.get("locationName"),
    }


# ---------------------------------------------------------------- FIT files

def fit_zip(g, activity_id):
    """Path of the downloaded ZIP (cached: an existing file is reused)."""
    p = Path.home() / "Downloads" / "garmin" / FIT_SUBDIR / f"activity-{int(activity_id)}.zip"
    if p.exists() and p.stat().st_size > 0:
        return p
    res = g.call("garmin_download_activity", activity_id=int(activity_id), directory=FIT_SUBDIR)
    path = Path(res["path"]) if isinstance(res, dict) and res.get("path") else p
    if not path.exists():
        raise GarminError(f"download reported {path} but the file is missing")
    return path


def read_fit(zip_path, with_laps=False):
    """Per-second records: list of dicts with t (s since start), hr, speed (m/s), alt (m), power, cadence, dist (m).
    GPS positions are deliberately dropped. with_laps=True returns (records, laps) where each lap is
    {start, end, intensity} in the same seconds-since-start axis (intensity: active, warmup, cooldown, rest, recovery...)."""
    try:
        import fitdecode
    except ImportError:
        raise SystemExit("fitdecode is missing: run  python -m pip install --user fitdecode")
    with zipfile.ZipFile(zip_path) as z:
        name = next(n for n in z.namelist() if n.lower().endswith(".fit"))
        data = z.read(name)
    recs, t0, laps = [], None, []
    with fitdecode.FitReader(io.BytesIO(data)) as fr:
        for f in fr:
            if isinstance(f, fitdecode.FitDataMessage) and f.name == "lap":
                st = f.get_value("start_time", fallback=None)
                el = f.get_value("total_elapsed_time", fallback=None)
                if st is not None and el is not None:
                    laps.append({"start_ts": st, "elapsed": float(el), "intensity": str(f.get_value("intensity", fallback="") or "")})
                continue
            if not (isinstance(f, fitdecode.FitDataMessage) and f.name == "record"):
                continue
            ts = f.get_value("timestamp", fallback=None)
            if ts is None:
                continue
            t0 = t0 or ts
            recs.append({
                "t": (ts - t0).total_seconds(),
                "hr": f.get_value("heart_rate", fallback=None),
                "speed": f.get_value("enhanced_speed", fallback=None) if f.has_field("enhanced_speed") else f.get_value("speed", fallback=None),
                "alt": f.get_value("enhanced_altitude", fallback=None),
                "power": f.get_value("power", fallback=None),
                "cadence": f.get_value("cadence", fallback=None),
                "dist": f.get_value("distance", fallback=None),
            })
    if not with_laps:
        return recs
    out = []
    for l in laps:
        s = (l["start_ts"] - t0).total_seconds() if t0 else 0.0
        out.append({"start": s, "end": s + l["elapsed"], "intensity": l["intensity"].lower()})
    return recs, out


def week_start(d):
    return d - timedelta(days=d.weekday())


def fmt_hm(minutes):
    m = int(round(minutes))
    return f"{m // 60}h{m % 60:02d}" if m >= 60 else f"{m}min"


# ---------------------------------------------------------------- goals
def goal_by(ath, gid=None, key=None):
    """A goal from athlete.json: the one with this id, else the first goal that carries `key` (e.g. 'target_speed_kmh'). None when the user has no such goal."""
    goals = ath.get("goals") or []
    for g in goals:
        if gid and g.get("id") == gid:
            return g
    for g in goals:
        if key and key in g:
            return g
    return None


# ---------------------------------------------------------------- which bike
def bike_ok(activity_id, which):
    """True if a ride belongs to the requested bike name ('all' or None = every ride).
    Garmin's server does not say which bike a ride used, so the user's own log in athlete.json decides:
    bike_log = {"default_bike": "road", "other_bikes": {"mtb": [activity ids]}}. A ride counts as the default bike unless its id is listed under another bike.
"""
    if which in (None, "all"):
        return True
    try:
        import json
        log = (json.loads((DATA_DIR / "athlete.json").read_text(encoding="utf-8")).get("bike_log") or {})
    except Exception:
        log = {}
    others = {k: {int(x) for x in v} for k, v in (log.get("other_bikes") or {}).items()}
    aid = int(activity_id)
    owner = next((k for k, ids in others.items() if aid in ids), log.get("default_bike") or "main")
    return owner == which
