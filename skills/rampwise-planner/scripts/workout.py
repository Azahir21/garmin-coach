#!/usr/bin/env python3
"""Structured workouts in the Garmin format: warm-up, steady / interval / tempo steps, recovery and rest, cool-down,
repeat blocks, each step with a duration and a target (heart-rate range or zone, pace, speed, cadence, or open).

One workout object is turned into
  * plain text (calendar notes, and for typing it into Garmin Connect by hand), and
  * a FIT workout file (.fit) that can be copied to the watch.

FIT facts used (field numbers, enums and units from the official FIT profile that ships inside the fitdecode library;
structure rules from Garmin's "Workout Files" article):
  * file order: file_id (type 5 = workout), workout (sport, num_valid_steps, name), then workout_step messages;
  * step time is stored in milliseconds, distance in centimetres, speed in mm/s (m/s x 1000);
  * a heart-rate range is stored as bpm + 100 (values 0-100 mean % of max HR); a zone is stored as 1-5 with low/high 0;
  * a repeat step: duration type "repeat_until_steps_cmplt" (6), duration_value = index of the first step to repeat,
    target_value = number of repetitions, target type open.
NOT stated by Garmin and therefore unverified here: maximum name lengths (names are kept short) and how every watch model
loads the file (copying to GARMIN/NewFiles over USB is the usual route; reports are mixed). The file is checked by decoding it
again (CRC and field values) but has NOT been tried on a real watch.

  workout.py --selftest        build one workout of each kind, encode, decode and print them
"""
import io
import struct
import sys
from datetime import datetime, timezone

SPORT = {"running": 1, "cycling": 2}
INTENSITY = {"active": 0, "rest": 1, "warmup": 2, "cooldown": 3, "recovery": 4, "interval": 5, "other": 6}
INT_NAME = {"warmup": "Warm-up", "cooldown": "Cool-down", "recovery": "Recovery", "rest": "Rest", "interval": "Interval", "active": "Steady", "other": "Other"}
T_SPEED, T_HR, T_OPEN, T_CADENCE = 0, 1, 2, 3
D_TIME, D_DISTANCE, D_OPEN, D_REPEAT_STEPS = 0, 1, 5, 6
NAME_MAX = 15              # step names stay short: Garmin does not state a limit


# ---------------------------------------------------------------- targets and steps
OPEN = {"type": "open"}


def hr_range(low, high):
    return {"type": "hr_range", "low": int(low), "high": int(high)}


def hr_zone(zone, low=None, high=None):
    d = {"type": "hr_zone", "zone": int(zone)}
    if low is not None:
        d.update(low=int(low), high=int(high))
    return d


# The athlete's own watch zones, per sport ("running" / "cycling"), set by build_plan from athlete.json hr.zone_sets. Nothing is built in.
ZONES = {}
TOLERANCE = 3              # a zone "covers" a band when both ends are within this many bpm


def set_zones(zones, tolerance=3):
    """zones: {"running": {"floors": [z1..z5 lower edges], "top": max_hr, "label": "..."}, "cycling": {...}}. Empty = custom bpm everywhere."""
    global TOLERANCE
    ZONES.clear()
    ZONES.update(zones or {})
    TOLERANCE = tolerance


def hr_band(low, high, sport):
    """Zone first, custom second: use the watch's own zone when ONE zone covers the band (both ends within TOLERANCE bpm), else a custom bpm range.
    Zone targets follow the athlete if the zones change; custom bpm does not. describe() says which one was used."""
    z = ZONES.get(sport)
    if z and z.get("floors"):
        f = list(z["floors"]) + [z.get("top") or z["floors"][-1]]
        for i in range(len(z["floors"])):
            lo, hi = f[i], f[i + 1]
            if abs(lo - low) <= TOLERANCE and abs(hi - high) <= TOLERANCE:
                return hr_zone(i + 1, lo, hi)
    return hr_range(low, high)


def cap(ceiling, extra=""):
    """Warm-up and cool-down have no heart-rate alert (so no range that overlaps the main step); the cap is written in the step note."""
    return f"keep HR under {int(ceiling)}" + (f", {extra}" if extra else "")


def zone_name(t, word):
    return (f"Zone {t['zone']} {word}" if t["type"] == "hr_zone" else f"Easy {word}").strip()


def pace_range(slow_s_per_km, fast_s_per_km):
    """Pace target as seconds per km (slow end, fast end). Stored in the file as speed."""
    return {"type": "pace", "slow": int(slow_s_per_km), "fast": int(fast_s_per_km)}


def speed_range(low_kmh, high_kmh):
    return {"type": "speed", "low": float(low_kmh), "high": float(high_kmh)}


def cadence_range(low, high):
    return {"type": "cadence", "low": int(low), "high": int(high)}


def step(name, intensity, minutes=None, seconds=None, km=None, target=OPEN, note=""):
    """One step. Duration: minutes or seconds (time), km (distance), or none (open: ends with the lap button)."""
    d = {"kind": "step", "name": name[:NAME_MAX], "intensity": intensity, "target": target, "note": note}
    if km is not None:
        d["km"] = float(km)
    elif seconds is not None or minutes is not None:
        d["seconds"] = int(round(seconds if seconds is not None else minutes * 60))
    return d


def repeat(times, *steps):
    return {"kind": "repeat", "times": int(times), "steps": list(steps)}


def workout(name, sport, *steps):
    return {"name": name[:30], "sport": sport, "steps": list(steps)}


# ---------------------------------------------------------------- templates (practice layouts; see ../references/evidence-map.md)
def easy(sport, total_min, ceiling, floor, warm=10, cool=5, label=None):
    """Warm-up, one steady block at the easy heart rate, cool-down. The layout (warm-up + steady + cool-down) is the user's setting."""
    main = max(5, total_min - warm - cool)
    t = hr_band(floor, ceiling, sport)
    return workout(label or f"Easy {total_min} min", sport,
                   step("Warm-up", "warmup", minutes=warm, target=OPEN, note=cap(ceiling, "easy, build slowly")),
                   step(zone_name(t, "run" if sport == "running" else "ride"), "active", minutes=main, target=t),
                   step("Cool-down", "cooldown", minutes=cool, target=OPEN, note=cap(ceiling, "easy, let HR drop")))


def easy_with_strides(total_min, ceiling, floor, strides=6, stride_s=20, rest_s=70, warm=10, cool=5):
    """Easy run with short relaxed fast strides after the steady block (practice)."""
    block = strides * (stride_s + rest_s) / 60.0
    main = max(5, total_min - warm - cool - block)
    t = hr_band(floor, ceiling, "running")
    return workout(f"Strides {total_min} min", "running",
                   step("Warm-up", "warmup", minutes=warm, target=OPEN, note=cap(ceiling)),
                   step(zone_name(t, "run"), "active", seconds=main * 60, target=t),
                   repeat(strides, step("Stride", "interval", seconds=stride_s, target=OPEN, note="fast but relaxed"),
                          step("Rest", "rest", seconds=rest_s, target=OPEN, note="walk or jog easy")),
                   step("Cool-down", "cooldown", minutes=cool, target=OPEN, note=cap(ceiling)))


def intervals(sport, total_min, reps, hard_min, rest_min, hard_target, ceiling, floor, warm=10, cool=10):
    """Warm-up, optional easy steady block, repeats of hard + recovery, cool-down. Hard target is set by the caller (zone, custom bpm or open)."""
    block = reps * (hard_min + rest_min)
    steady = max(0, total_min - warm - cool - block)
    steps = [step("Warm-up", "warmup", minutes=warm, target=OPEN, note=cap(ceiling))]
    if steady >= 5:
        t = hr_band(floor, ceiling, sport)
        steps.append(step(zone_name(t, ""), "active", minutes=steady, target=t))
    steps.append(repeat(reps, step(f"Hard {hard_min:g} min", "interval", minutes=hard_min, target=hard_target,
                                   note="" if hard_target["type"] != "open" else "hard but controlled, a few words at a time"),
                        step("Recovery", "recovery", minutes=rest_min, target=OPEN, note="easy until HR drops")))
    steps.append(step("Cool-down", "cooldown", minutes=cool, target=OPEN, note=cap(ceiling)))
    return workout(f"Intervals {reps}x{hard_min:g}", sport, *steps)


def tempo(sport, reps, tempo_min, rest_min, tempo_target, ceiling, warm=10, cool=10):
    """Warm-up, a steady 'tempo' block (one block, or repeats with a rest), cool-down (practice)."""
    note = "hard but steady" if tempo_target["type"] != "open" else "hard but steady, a few words at a time"
    if reps == 1:
        return workout(f"Tempo {tempo_min:g} min", sport,
                       step("Warm-up", "warmup", minutes=warm, target=OPEN, note=cap(ceiling)),
                       step("Tempo", "interval", minutes=tempo_min, target=tempo_target, note=note),
                       step("Cool-down", "cooldown", minutes=cool, target=OPEN, note=cap(ceiling)))
    return workout(f"Tempo {reps}x{tempo_min:g}", sport,
                   step("Warm-up", "warmup", minutes=warm, target=OPEN, note=cap(ceiling)),
                   repeat(reps, step(f"Tempo {tempo_min:g} min", "interval", minutes=tempo_min, target=tempo_target),
                          step("Rest", "rest", minutes=rest_min, target=OPEN)),
                   step("Cool-down", "cooldown", minutes=cool, target=OPEN, note=cap(ceiling)))


def maf_test(hr, band_low, laps=5, lap_km=1.0, warm_km=1.0, cool_km=0.5):
    """The athlete's monthly MAF test: a short warm-up, then equal laps at the same heart rate (the pace of each lap is the result), then a cool-down.
    Same course each time. Practice: the concept (pace at a fixed heart rate) is supported (Vesterinen 2016/2017); the 180 - age formula is not validated."""
    return workout(f"MAF test {hr} bpm", "running",
                   step("Warm-up", "warmup", km=warm_km, target=OPEN, note=cap(hr, "easy, HR rises to MAF")),
                   repeat(laps, step("MAF km", "active", km=lap_km, target=hr_band(band_low, hr, "running"))),
                   step("Cool-down", "cooldown", km=cool_km, target=OPEN, note=cap(hr)))


def climb_ride(total_min, target_m, ceiling, floor, climb_height_m=None, warm=10, cool=10, climb_hr=None):
    """Easy ride with climb repeats. There are few hills, so the target is the TOTAL ASCENT: repeat a short climb until the watch shows it.
    If the height of one climb is known the repeats are target / height, else 6. The climb step ends with the lap button.
    climb_hr = (low, high) from athlete.json preferences.climb.hr_band, or None for no heart-rate alert on the climb."""
    import math
    reps = math.ceil(target_m / climb_height_m) if climb_height_m else 6
    steady = max(10, total_min - warm - cool - reps * 5)
    t = hr_band(floor, ceiling, "cycling")
    ct = hr_band(climb_hr[0], climb_hr[1], "cycling") if climb_hr else OPEN
    return workout(f"Climb ride {target_m} m", "cycling",
                   step("Warm-up", "warmup", minutes=warm, target=OPEN, note=cap(ceiling)),
                   step(zone_name(t, "ride"), "active", minutes=steady, target=t),
                   repeat(reps, step("Climb", "interval", target=ct, note="seated, steady, lap button at the top"),
                          step("Recovery", "recovery", minutes=2, target=OPEN, note="roll down easy")),
                   step("Cool-down", "cooldown", minutes=cool, target=OPEN, note=cap(ceiling)))


def time_trial_3k(ceiling, warm=10, cool=10):
    """Warm-up, 3 km as evenly as possible (open target, ends after 3 km), cool-down."""
    return workout("3 km time trial", "running",
                   step("Warm-up", "warmup", minutes=warm, target=OPEN, note=cap(ceiling)),
                   step("3 km even", "interval", km=3.0, target=OPEN, note="even pace, not a sprint"),
                   step("Cool-down", "cooldown", minutes=cool, target=OPEN, note=cap(ceiling)))


# ---------------------------------------------------------------- reading a workout
def flat(w):
    """Steps in file order, repeat blocks expanded into [steps..., repeat-marker]; returns list of dicts with 'index'."""
    out = []

    def add(s):
        s = dict(s)
        s["index"] = len(out)
        out.append(s)
        return s["index"]

    for s in w["steps"]:
        if s["kind"] == "step":
            add(s)
        else:
            first = None
            for inner in s["steps"]:
                i = add(inner)
                first = i if first is None else first
            add({"kind": "repeat", "name": "Repeat", "from": first, "times": s["times"], "target": OPEN, "intensity": "active"})
    return out


def est_minutes(w, pace_s_per_km=600):
    """Rough total length; a distance step is turned into minutes with an assumed pace."""
    def one(s):
        if s.get("seconds") is not None:
            return s["seconds"] / 60.0
        if s.get("km") is not None:
            return s["km"] * pace_s_per_km / 60.0
        return 0.0
    tot = 0.0
    for s in w["steps"]:
        tot += one(s) if s["kind"] == "step" else s["times"] * sum(one(i) for i in s["steps"])
    return tot


def _fmt_dur(s):
    if s.get("km") is not None:
        return f"{s['km']:g} km"
    if s.get("seconds") is None:
        return "until lap button"
    m, sec = divmod(s["seconds"], 60)
    return f"{m}:{sec:02d}" if sec else f"{m} min"


def _mmss(sec):
    return f"{sec // 60}:{sec % 60:02d}"


def target_text(t):
    k = t["type"]
    return {"open": lambda: "no target", "hr_range": lambda: f"HR {t['low']}-{t['high']} bpm", "hr_zone": lambda: (f"HR Zone {t['zone']} ({t['low']}-{t['high']} bpm on your watch)" if "low" in t else f"HR Zone {t['zone']}"),
            "pace": lambda: f"pace {_mmss(t['slow'])}-{_mmss(t['fast'])} /km", "speed": lambda: f"speed {t['low']:g}-{t['high']:g} km/h",
            "cadence": lambda: f"cadence {t['low']}-{t['high']} rpm"}[k]()


def describe(w):
    """Numbered plain-text steps, the way they are entered in Garmin Connect (repeats shown as a block)."""
    lines, n = [], 0
    for s in w["steps"]:
        if s["kind"] == "step":
            n += 1
            lines.append(f"{n}. {s['name']} {_fmt_dur(s)} - {target_text(s['target'])}" + (f" ({s['note']})" if s.get("note") else ""))
        else:
            n += 1
            lines.append(f"{n}. Repeat {s['times']} times:")
            for j, i in enumerate(s["steps"]):
                lines.append(f"     {'ab'[j] if j < 2 else j + 1}) {i['name']} {_fmt_dur(i)} - {target_text(i['target'])}" + (f" ({i['note']})" if i.get("note") else ""))
    lines.append(f"Total about {est_minutes(w):.0f} min")
    lines.extend(_hr_statement(w))
    return "\n".join(lines)


def _hr_statement(w):
    """Say which heart-rate targets are watch zones and which are custom bpm, so the plan never hides that choice."""
    zs, customs = [], []

    def scan(st):
        for x in st:
            if x["kind"] == "repeat":
                scan(x["steps"])
            elif x["target"]["type"] == "hr_zone":
                zs.append(x["target"]["zone"])
            elif x["target"]["type"] == "hr_range":
                customs.append(f"{x['target']['low']}-{x['target']['high']}")

    scan(w["steps"])
    label = (ZONES.get(w["sport"]) or {}).get("label")
    out = []
    if zs:
        out.append(f"Zone targets (Zone {', '.join(str(z) for z in sorted(set(zs)))}) use your watch's {label or w['sport']} zones, so they follow you if you change your zones.")
    if customs:
        why = f"your {label} zones do not cover this band." if label else "no watch zones are recorded for this sport."
        out.append(f"Custom bpm ({', '.join(sorted(set(customs)))}): {why}")
    return out


# ---------------------------------------------------------------- FIT encoding
_CRC = [0x0000, 0xCC01, 0xD801, 0x1400, 0xF001, 0x3C00, 0x2800, 0xE401, 0xA001, 0x6C00, 0x7800, 0xB401, 0x5000, 0x9C01, 0x8801, 0x4400]


def crc16(data, crc=0):
    for b in data:
        t = _CRC[crc & 0xF]
        crc = (crc >> 4) & 0x0FFF
        crc = crc ^ t ^ _CRC[b & 0xF]
        t = _CRC[crc & 0xF]
        crc = (crc >> 4) & 0x0FFF
        crc = crc ^ t ^ _CRC[(b >> 4) & 0xF]
    return crc


ENUM, UINT16, UINT32, UINT32Z, STRING = 0x00, 0x84, 0x86, 0x8C, 0x07
_SIZE = {ENUM: 1, UINT16: 2, UINT32: 4, UINT32Z: 4}


def _definition(local, global_num, fields):
    out = bytes([0x40 | local, 0, 0]) + struct.pack("<H", global_num) + bytes([len(fields)])
    for num, size, base in fields:
        out += bytes([num, size, base])
    return out


def _data(local, fields, values):
    out = bytes([local])
    for (num, size, base), v in zip(fields, values):
        if base == STRING:
            b = str(v).encode("ascii", "replace")[: size - 1]
            out += b + bytes(size - len(b))
        else:
            out += int(v).to_bytes(_SIZE[base], "little")
    return out


def _target_fields(t):
    """(target_type, target_value, custom_low, custom_high) as stored in the file."""
    k = t["type"]
    if k == "open":
        return T_OPEN, 0, 0, 0
    if k == "hr_zone":
        return T_HR, t["zone"], 0, 0                                   # zones start at 1; custom low/high are 0
    if k == "hr_range":
        return T_HR, 0, t["low"] + 100, t["high"] + 100                # bpm are stored offset by 100
    if k == "pace":
        return T_SPEED, 0, round(1000 * 1000.0 / t["slow"]), round(1000 * 1000.0 / t["fast"])   # m/s x 1000, slow end first
    if k == "speed":
        return T_SPEED, 0, round(t["low"] / 3.6 * 1000), round(t["high"] / 3.6 * 1000)
    if k == "cadence":
        return T_CADENCE, 0, t["low"], t["high"]
    raise ValueError(k)


def encode_fit(w, created=None):
    """Bytes of a FIT workout file: header, file_id, workout, workout_step messages, CRC."""
    steps = flat(w)
    created = created or datetime.now(timezone.utc)
    t_created = int((created - datetime(1989, 12, 31, tzinfo=timezone.utc)).total_seconds())
    body = b""
    fid = [(0, 1, ENUM), (1, 2, UINT16), (2, 2, UINT16), (3, 4, UINT32Z), (4, 4, UINT32)]
    body += _definition(0, 0, fid) + _data(0, fid, [5, 255, 0, 1, t_created])           # type 5 = workout, manufacturer 255 = development
    wf = [(4, 1, ENUM), (6, 2, UINT16), (8, 32, STRING)]
    body += _definition(1, 26, wf) + _data(1, wf, [SPORT[w["sport"]], len(steps), w["name"]])
    sf = [(254, 2, UINT16), (0, NAME_MAX + 1, STRING), (1, 1, ENUM), (2, 4, UINT32), (3, 1, ENUM), (4, 4, UINT32), (5, 4, UINT32), (6, 4, UINT32), (7, 1, ENUM)]
    body += _definition(2, 27, sf)
    for s in steps:
        if s["kind"] == "repeat":
            vals = [s["index"], s["name"], D_REPEAT_STEPS, s["from"], T_OPEN, s["times"], 0, 0, INTENSITY["active"]]
        else:
            tt, tv, lo, hi = _target_fields(s["target"])
            if s.get("km") is not None:
                dt, dv = D_DISTANCE, round(s["km"] * 1000 * 100)             # centimetres
            elif s.get("seconds") is not None:
                dt, dv = D_TIME, s["seconds"] * 1000                         # milliseconds
            else:
                dt, dv = D_OPEN, 0
            vals = [s["index"], s["name"], dt, dv, tt, tv, lo, hi, INTENSITY[s["intensity"]]]
        body += _data(2, sf, vals)
    header = bytes([14, 0x20]) + struct.pack("<HI", 2140, len(body)) + b".FIT"
    header += struct.pack("<H", crc16(header))
    return header + body + struct.pack("<H", crc16(header + body))


def decode_check(data):
    """Decode the bytes again with fitdecode (it checks both CRCs) and return a list of readable step dicts."""
    import fitdecode
    msgs = []
    with fitdecode.FitReader(io.BytesIO(data)) as fr:
        for m in fr:
            if isinstance(m, fitdecode.FitDataMessage):
                msgs.append((m.name, {f.name: f.value for f in m.fields}))
    names = [n for n, _ in msgs]
    assert names[0] == "file_id" and names[1] == "workout", names[:3]
    assert msgs[0][1]["type"] == "workout", msgs[0][1]
    steps = [d for n, d in msgs if n == "workout_step"]
    assert msgs[1][1]["num_valid_steps"] == len(steps), (msgs[1][1], len(steps))
    return msgs[1][1], steps


def selftest():
    zones = {"floor": 120, "ceil": 140}
    tests = [easy("running", 50, 146, 126), easy_with_strides(50, 146, 126),
             intervals("cycling", 70, 5, 3, 3, hr_range(168, 188), 146, 126), tempo("running", 2, 10, 3, hr_range(147, 167), 146),
             time_trial_3k(146), easy("cycling", 90, 146, 126, warm=10, cool=10),
             workout("Pace test", "running", step("Warm-up", "warmup", minutes=10), step("Fast", "interval", minutes=5, target=pace_range(390, 360)),
                     step("Spin", "interval", minutes=5, target=cadence_range(80, 90)), step("Ride", "active", minutes=5, target=speed_range(24, 26)))]
    for w in tests:
        data = encode_fit(w)
        wk, steps = decode_check(data)
        print(f"\n== {w['name']} ({w['sport']}): {len(data)} bytes, num_valid_steps {wk['num_valid_steps']}, decoded {len(steps)} steps, CRC ok")
        print(describe(w))
        for s in steps[:4]:
            print("   file step:", {k: v for k, v in s.items() if k in ("message_index", "wkt_step_name", "duration_type", "duration_time", "duration_distance", "duration_step", "target_type", "repeat_steps", "target_hr_zone", "custom_target_heart_rate_low", "custom_target_heart_rate_high", "custom_target_speed_low", "custom_target_speed_high", "custom_target_cadence_low", "intensity")})
    print("\nselftest ok")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if "--selftest" in sys.argv:
        selftest()
    else:
        print(__doc__)
