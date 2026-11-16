#!/usr/bin/env python3
"""Install the skills (and subagents) for harnesses that do not use the Claude Code plugin marketplace.

  python install.py --target agents          skills -> ~/.agents/skills        (Codex and other Agent Skills clients)
  python install.py --target claude          skills -> ~/.claude/skills, subagents -> ~/.claude/agents
  python install.py --target both
  python install.py --dest DIR               skills -> DIR (any folder your harness reads)
  python install.py --update                 git pull --ff-only first, then install again
  python install.py --link                   symlink instead of copy (development)

Personal data is NOT in these folders: it lives in $GARMIN_COACH_DATA (default ~/garmin-coach-data) and is never touched.
Existing folders with the same name are replaced; your athlete.json is not inside them.
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SKILLS = ROOT / "skills"
AGENTS = ROOT / "agents"


def place(src: Path, dst: Path, link: bool):
    if dst.is_symlink() or dst.is_file():
        dst.unlink()
    elif dst.exists():
        shutil.rmtree(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if link:
        try:
            dst.symlink_to(src, target_is_directory=src.is_dir())
            return "linked"
        except OSError:
            pass
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc")) if src.is_dir() else shutil.copy2(src, dst)
    return "copied"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", choices=["agents", "claude", "both"])
    ap.add_argument("--dest")
    ap.add_argument("--update", action="store_true")
    ap.add_argument("--link", action="store_true")
    a = ap.parse_args()
    if not (a.target or a.dest):
        ap.error("choose --target or --dest")
    if a.update:
        r = subprocess.run(["git", "-C", str(ROOT), "pull", "--ff-only"])
        if r.returncode:
            sys.exit("git pull failed: resolve it, then run again")
    dests = []
    if a.dest:
        dests.append((Path(a.dest).expanduser(), None))
    if a.target in ("agents", "both"):
        dests.append((Path.home() / ".agents" / "skills", None))
    if a.target in ("claude", "both"):
        dests.append((Path.home() / ".claude" / "skills", Path.home() / ".claude" / "agents"))
    for sk_dest, ag_dest in dests:
        for s in sorted(SKILLS.iterdir()):
            if s.is_dir():
                print(f"{place(s, sk_dest / s.name, a.link):7} {sk_dest / s.name}")
        if ag_dest:
            for f in sorted(AGENTS.glob("*.md")):
                print(f"{place(f, ag_dest / f.name, a.link):7} {ag_dest / f.name}")
    print("\nDone. Next: pip install fitdecode ; garmin-personal-mcp auth ; ask your agent: Set up my Garmin coach.")


if __name__ == "__main__":
    main()
