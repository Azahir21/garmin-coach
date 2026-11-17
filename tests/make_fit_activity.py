"""Build small synthetic FIT ACTIVITY files for the tests (no real person's data). Uses the CRC from the workout encoder.

  make(path, sport="running", minutes=70, manufacturer=1, with_speed=True, with_altitude=True, laps=None, sessions=None, hr0=140, hr_rise=8)

Field numbers and base types come from the public FIT profile (file_id 0, session 18, lap 19, record 20); fitdecode reads them back with scale and offset applied.
"""
import struct
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skills" / "rampwise-planner" / "scripts"))
import workout as wk  # noqa: E402

ENUM, UINT8, UINT16, UINT32 = 0x00, 0x02, 0x84, 0x86
SIZE = {ENUM: 1, UINT8: 1, UINT16: 2, UINT32: 4}
EPOCH = datetime(1989, 12, 31, tzinfo=timezone.utc)
SPORT = {"running": 1, "cycling": 2, "swimming": 5, "multisport": 18}
SUB = {"generic": 0, "lap_swimming": 17, "open_water": 18}
INTENSITY = {"active": 0, "rest": 1, "warmup": 2, "cooldown": 3}


def _def(local, num, fields):
    return bytes([0x40 | local, 0, 0]) + struct.pack("<H", num) + bytes([len(fields)]) + b"".join(bytes([n, SIZE[b], b]) for n, b in fields)


def _row(local, fields, values):
    return bytes([local]) + b"".join(int(v).to_bytes(SIZE[b], "little") for (n, b), v in zip(fields, values))


def _ts(dt):
    return int((dt - EPOCH).total_seconds())


def make(path, sport="running", minutes=70, manufacturer=1, with_speed=True, with_altitude=True, laps=None, sessions=None, hr0=140, hr_rise=8, speed=2.9, with_hr=True, power=85,
         start=datetime(2026, 11, 1, 6, 0, tzinfo=timezone.utc), swim_laps=None):
    """laps: list of (start_s, elapsed_s, intensity). sessions: list of (sport, sub, seconds, metres, avg_hr) for multisport.
    swim_laps: list of (metres, seconds, hr) per length for a pool swim (records then carry heart rate but no speed)."""
    body = b""
    f_id = [(0, ENUM), (1, UINT16), (2, UINT16), (4, UINT32)]
    body += _def(0, 0, f_id) + _row(0, f_id, [4, manufacturer, 7, _ts(start)])
    rec = [(253, UINT32), (3, UINT8), (5, UINT32), (4, UINT8), (7, UINT16)]
    if with_speed:
        rec.append((73, UINT32))
    if with_altitude:
        rec.append((2, UINT16))
    body += _def(1, 20, rec)
    n = minutes * 60
    dist = 0.0
    for i in range(n):
        dist += speed
        hr = int(hr0 + hr_rise * i / n) if with_hr else 0
        vals = [_ts(start) + i, hr, int(dist * 100), 180, power]
        if with_speed:
            vals.append(int(speed * 1000))
        if with_altitude:
            vals.append(int((100 + 500) * 5))
        body += _row(1, rec, vals)
    lap_f = [(253, UINT32), (2, UINT32), (7, UINT32), (8, UINT32), (9, UINT32), (23, ENUM), (15, UINT8)]
    body += _def(2, 19, lap_f)
    for st, el, inten in (laps or []):
        body += _row(2, lap_f, [_ts(start) + st + el, _ts(start) + st, el * 1000, el * 1000, int(el * speed * 100), INTENSITY[inten], hr0])
    for m_, s_, h_ in (swim_laps or []):
        body += _row(2, lap_f, [_ts(start) + n, _ts(start), s_ * 1000, s_ * 1000, m_ * 100, INTENSITY["active"], h_])
    ses_f = [(253, UINT32), (2, UINT32), (7, UINT32), (8, UINT32), (9, UINT32), (5, ENUM), (6, ENUM), (16, UINT8), (22, UINT16), (254, UINT16)]
    body += _def(3, 18, ses_f)
    if sessions:
        for k, (sp, sub, secs, metres, hr) in enumerate(sessions):
            body += _row(3, ses_f, [_ts(start) + secs, _ts(start), secs * 1000, secs * 1000, metres * 100, SPORT[sp], SUB[sub], hr, 0, k])
    else:
        sp = SPORT[sport]
        body += _row(3, ses_f, [_ts(start) + n, _ts(start), n * 1000, n * 1000, int(dist * 100), sp, SUB["lap_swimming"] if sport == "swimming" else 0, int(hr0 + hr_rise / 2), 0, 0])
    header = bytes([14, 0x20]) + struct.pack("<HI", 2140, len(body)) + b".FIT"
    header += struct.pack("<H", wk.crc16(header))
    Path(path).write_bytes(header + body + struct.pack("<H", wk.crc16(header + body)))
    return Path(path)
