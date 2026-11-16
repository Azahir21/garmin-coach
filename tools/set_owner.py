#!/usr/bin/env python3
"""Replace the {{GITHUB_OWNER}} and {{AUTHOR_NAME}} placeholders before the first commit.

  python tools/set_owner.py --owner your-github-username --name "Your Name or Handle"
"""
import argparse
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
EXT = {".md", ".json", ".py", ".yml", ".yaml", ".txt"}

ap = argparse.ArgumentParser()
ap.add_argument("--owner", required=True)
ap.add_argument("--name", required=True)
a = ap.parse_args()
n = 0
for p in ROOT.rglob("*"):
    if p.is_file() and p.suffix in EXT and ".git" not in p.parts and p.name not in ("set_owner.py", "check_repo.py"):
        t = p.read_text(encoding="utf-8")
        u = t.replace("{{GITHUB_OWNER}}", a.owner).replace("{{AUTHOR_NAME}}", a.name).replace("OWNER/garmin-coach", f"{a.owner}/garmin-coach")
        if u != t:
            p.write_text(u, encoding="utf-8")
            n += 1
print(f"updated {n} files")
