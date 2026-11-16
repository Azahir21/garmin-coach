"""Strength session generator: goal profile + the user's equipment + constraints + their own Garmin history -> sessions.

Nothing here is about one athlete. All athlete facts come from athlete.json (preferences.strength, equipment.tags, constraints.no_exercises) and from the
athlete's own strength history in Garmin (strength_history.py). Library: references/exercise_library.json. Profiles: references/goal_profiles.json
(endurance, sprint, general), each number labelled research or practice in the profile's 'basis' lines and in references/evidence-map.md.

  strength_plan.py [--goal endurance|sprint|general] [--weeks 4] [--version short|mid|full] [--no-history]

Ask-first rules (the planner never assumes):
  * no equipment.tags in athlete.json -> exit code 2 and the questions to ask;
  * a loadable exercise with no history -> the session says "pick a starting weight" and lists it in NEEDS (the coach asks the user).
Library and profile are plain JSON so the community can add exercises and goals.
"""
import argparse
import json
import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REF = HERE.parent / "references"
SKILLS = HERE.parent.parent
DATA_DIR = Path(__import__("os").environ.get("GARMIN_COACH_DATA") or Path.home() / "garmin-coach-data")   # personal data lives OUTSIDE the plugin folder, so updates never touch it
ATHLETE_JSON = DATA_DIR / "athlete.json"
SLOTS_FOR = {"short": 3, "mid": 4, "full": 99}
ASK_EQUIPMENT = """NO EQUIPMENT LIST for this athlete (athlete.json equipment.tags). Do not guess: ask what they can use, then record it.
  Tags: bodyweight, dumbbell, barbell, plates, band, band_anchor (a sturdy anchor for a band), step (stair/box/chair), bench, rack, pullup_bar, slider (towel on a smooth floor),
  anchor_feet (something to hook the heels under), box (plyometric box), sled, hill, track (30 m of flat space), gym.
  Record: athlete.py set equipment.tags '["bodyweight","dumbbell",...]'. Also ask: which exercises can they NOT do (constraints.no_exercises)."""


def load_library():
    return json.loads((REF / "exercise_library.json").read_text(encoding="utf-8"))


def load_profiles():
    return json.loads((REF / "goal_profiles.json").read_text(encoding="utf-8"))


def banned_tags(athlete):
    out = set()
    for x in (athlete.get("constraints") or {}).get("no_exercises", []):
        t = re.sub(r"s$", "", x.strip().lower().replace(" ", "-"))
        out.add(t)
    return out


def history_index(history, lib):
    """exercise id -> list of (date, sets) newest first, from the athlete's own Garmin sessions."""
    key_to_id = {}
    for e in lib["exercises"]:
        for k in e.get("garmin", []):
            key_to_id.setdefault(k, e["id"])
    out = {}
    for s in sorted(history or [], key=lambda x: x["date"], reverse=True):
        for b in s["exercises"]:
            eid = key_to_id.get(f"{b['key'][0]}/{b['key'][1]}")
            if eid:
                out.setdefault(eid, []).append((s["date"], b["sets"]))
    return out


def candidates(lib, pattern, goal, tags, banned, max_level):
    res = []
    for e in lib["exercises"]:
        if e["pattern"] != pattern or goal not in e["goals"] or e["level"] > max_level:
            continue
        if not set(e["requires"]) <= tags:
            continue
        if e.get("banned_tag") in banned:
            continue
        res.append(e)
    return res


def pick(cands, hist, week_idx, slot_idx, variety, used):
    order = sorted(cands, key=lambda e: (0 if e["id"] in hist else 1, 0 if e["kind"] in ("heavy", "plyo", "speed") else 1, e["level"], e["id"]))
    order = [e for e in order if e["id"] not in used] or order
    if not order:
        return None
    if variety == "rotate":
        pool = [e for e in order if e["kind"] == order[0]["kind"]]       # rotate among alternatives of the same kind, so variety never means a downgrade
        pool = pool if len(pool) > 1 else order
        k = min(3, len(pool))
        start = (week_idx // 2 + slot_idx) % k
        return pool[start]
    return order[0]


def _range(reps):
    m = re.match(r"(\d+)\s*-\s*(\d+)", str(reps))
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.match(r"(\d+)", str(reps))
    return (int(m.group(1)), int(m.group(1))) if m else (None, None)


def progression_text(ex, cfg, hist_sets, hist_date):
    """Double progression (practice): same weight until every set reaches the top of the range, then add the smallest plate step."""
    lo, hi = _range(cfg["reps"])
    if ex["kind"] != "heavy":
        return ""
    if not hist_sets:
        return "Start with a weight where the last 2 reps are hard; write it down (Garmin stores weight and reps, so the next plan builds on it)."
    done = [(s["reps"], s["kg"]) for s in hist_sets if s.get("reps")]
    if not done:
        return ""
    w = max(kg for _, kg in done if kg is not None) if any(kg for _, kg in done) else None
    reps = [r for r, _ in done]
    last = ", ".join(str(r) for r in reps) + (f" reps at {w:g} kg" if w else " reps")
    if lo is None:
        return f"Last time ({hist_date}): {last}."
    if min(reps) >= hi and w:
        return f"Last time ({hist_date}): {last}. Every set reached {hi}: add the smallest plate step and aim for {lo}+ reps."
    if min(reps) >= lo:
        return f"Last time ({hist_date}): {last}. Same weight; add a rep to the weakest set."
    return f"Last time ({hist_date}): {last}. Same weight; aim for {lo}+ reps in every set."


def _minutes(items):
    m = 5.0
    for it in items:
        ex, cfg, sets = it["ex"], it["cfg"], it["sets"]
        work = 45 * (2 if it["side"] else 1) if ex["kind"] in ("heavy", "bw") else (30 if ex["kind"] == "iso" else 20)
        m += sets * (work + cfg["rest_s"]) / 60
    return m


def build_session(sess_cfg, cycle_idx, goal, lib, hist, tags, banned, n_slots, week_idx, variety, max_level, prescription, light, max_minutes=None):
    cyc = sess_cfg["cycle"][cycle_idx % len(sess_cfg["cycle"])]
    slots = sorted(cyc["slots"], key=lambda s: s["priority"])
    used, items, needs, notes = set(), [], [], []
    for i, sl in enumerate(slots):
        if len(items) >= n_slots:
            break
        cands = candidates(lib, sl["pattern"], goal, tags, banned, max_level)
        ex = pick(cands, hist, week_idx, i, variety, used)
        if ex is None:                                # not available with this equipment or constraints: take the next slot instead
            notes.append(f"'{sl['pattern']}' skipped: nothing fits the equipment or constraints (more equipment would add options)")
            continue
        used.add(ex["id"])
        cfg = prescription[ex["kind"]]
        sets = max(1, math.ceil(cfg["sets"] / 2)) if light else cfg["sets"]
        side = ex["uni"] and ex["kind"] in ("iso", "bw", "heavy") and sl["pattern"] not in ("plyo", "speed")
        items.append({"sl": sl, "ex": ex, "cfg": cfg, "sets": sets, "side": side})
    # time budget: first trim sets of the lowest-priority slots (never below 2), then drop the last slot (never below 3 slots)
    if max_minutes:
        guard = 0
        while _minutes(items) > max_minutes and guard < 40:
            guard += 1
            trim = [it for it in sorted(items, key=lambda x: -x["sl"]["priority"]) if it["sets"] > 2]
            if trim:
                trim[0]["sets"] -= 1
            elif len(items) > 3:
                items.pop(max(range(len(items)), key=lambda k: items[k]["sl"]["priority"]))
            else:
                break
    trimmed = [it for it in items if it["sets"] < (max(1, math.ceil(it["cfg"]["sets"] / 2)) if light else it["cfg"]["sets"])]
    if trimmed:
        notes.append(f"sets trimmed to fit your {max_minutes}-minute limit ({len(trimmed)} exercises): the profile prescribes more")
    # order: jumps and speed work first (fresh), then by priority, trunk last
    items.sort(key=lambda it: (0 if it["ex"]["kind"] in ("plyo", "speed") else (2 if it["sl"]["pattern"] == "core" else 1), it["sl"]["priority"]))
    lines, vol = [], {}
    for it in items:
        ex, cfg, sets, side = it["ex"], it["cfg"], it["sets"], it["side"]
        rx = f"{sets}x{cfg['reps']}" + (" each side" if side else "")
        core = it["sl"]["pattern"] == "core"
        bits = [f"rest {cfg['rest_s']} s"] + ([cfg["tempo"]] if cfg.get("tempo") and not core else []) + ([f"{cfg['rir']} reps in reserve"] if cfg.get("rir") and not core and ex["kind"] != "plyo" else [])
        h = hist.get(ex["id"])
        prog = progression_text(ex, cfg, h[0][1] if h else None, h[0][0] if h else None)
        if ex["kind"] == "heavy" and not h:
            needs.append(f"starting weight for {ex['name']}")
        lines.append(f"{ex['name']} {rx} ({'; '.join(bits)}). {ex['cue']}." + (f" {prog}" if prog else ""))
        vol[it["sl"]["pattern"]] = vol.get(it["sl"]["pattern"], 0) + sets * (2 if side else 1)
    return {"id": sess_cfg["id"], "title": f"Strength: {sess_cfg['name']} ({cyc['name']})", "minutes": int(5 * round(_minutes(items) / 5)), "lines": lines, "why": sess_cfg["why"],
            "check": sess_cfg["check"], "needs": needs, "notes": notes, "volume": vol, "exercises": [it["ex"]["id"] for it in items]}


def prescription_for(cfg, program_week):
    """Profile prescription, with the override of the latest phase that has started (profiles with 'phases', e.g. triathlon moderate -> heavy)."""
    rx = {k: dict(v) for k, v in cfg["prescription"].items()}
    for ph in sorted(cfg.get("phases", []), key=lambda x: x["from_program_week"]):
        if program_week >= ph["from_program_week"]:
            for k, v in ph.items():
                if k != "from_program_week":
                    rx[k] = dict(v)
    return rx


def make_week(athlete, history, week_idx, light=False, goal=None, version=None, variety=None, program_week=None):
    """Sessions for one week. history = strength_history.load_history() (may be empty). program_week = weeks since the strength block started (default week_idx)."""
    prefs = (athlete.get("preferences") or {}).get("strength") or {}
    prof = load_profiles()
    goal = goal or prefs.get("goal") or prof["default_goal"]
    cfg = prof["goals"][goal]
    version = version or prefs.get("version", "short")
    variety = variety or prefs.get("variety", "rotate")
    max_level = prefs.get("max_level", 2)
    tags = set((athlete.get("equipment") or {}).get("tags") or [])
    if not tags:
        print(ASK_EQUIPMENT)
        sys.exit(2)
    lib = load_library()
    hist = history_index(history, lib)
    banned = banned_tags(athlete)
    n_slots = SLOTS_FOR[version]
    out = []
    for sess_cfg in cfg["sessions"][: cfg["sessions_per_week"]]:
        out.append(build_session(sess_cfg, week_idx if variety == "rotate" else 0, cfg.get("library_goal", goal), lib, hist, tags, banned, n_slots, week_idx, variety, max_level,
                                 prescription_for(cfg, week_idx if program_week is None else program_week), light, prefs.get("max_minutes", 35)))
    weekly = {}
    for sess in out:
        for k, v in sess["volume"].items():
            weekly[k] = weekly.get(k, 0) + v
    return out, {"goal": goal, "label": cfg["label"], "basis": cfg["basis"], "sessions_per_week": cfg["sessions_per_week"], "version": version, "weekly_sets": weekly}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--goal")
    ap.add_argument("--list-goals", action="store_true")
    ap.add_argument("--weeks", type=int, default=4)
    ap.add_argument("--version", choices=["short", "mid", "full"])
    ap.add_argument("--no-history", action="store_true")
    a = ap.parse_args()
    if a.list_goals:
        for k, v in load_profiles()["goals"].items():
            print(f"{k}: {v['label']} ({v['sessions_per_week']} sessions/week)")
        return
    sys.path.insert(0, str(SKILLS / "garmin-coach" / "scripts"))
    import gcommon as gc  # noqa: E402
    gc.utf8_stdout()
    athlete = json.loads((ATHLETE_JSON).read_text(encoding="utf-8"))
    history = []
    if not a.no_history:
        sys.path.insert(0, str(HERE))
        import strength_history as sh  # noqa: E402
        with gc.Garmin() as g:
            history = sh.load_history(g, 240)
    for w in range(a.weeks):
        sessions, meta = make_week(athlete, history, w, light=False, goal=a.goal, version=a.version)
        if w == 0:
            print(f"GOAL {meta['goal']}: {meta['label']} | {meta['sessions_per_week']} sessions/week | version {meta['version']} | history sessions: {len(history)}")
            for b in meta["basis"]:
                print("  basis:", b)
        print(f"\n=== Week {w + 1}")
        for s in sessions:
            print(f"- {s['title']} (about {s['minutes']} min) weekly sets so far: {s['volume']}")
            for ln in s["lines"]:
                print("    *", ln)
            if s["needs"]:
                print("    NEEDS:", "; ".join(s["needs"]))
            if s["notes"]:
                print("    note:", "; ".join(s["notes"]))
        print("  weekly hard sets per pattern:", meta["weekly_sets"])


if __name__ == "__main__":
    main()
