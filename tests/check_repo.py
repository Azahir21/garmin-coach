#!/usr/bin/env python3
"""Static checks for the repository: manifests, Agent Skills rules, data integrity and a privacy scan. No Garmin account needed.

  python tests/check_repo.py

Put extra personal words to catch (your name, town, bike model ...) in a local, git-ignored file `.privacy-tokens`, one per line.
Exit code 0 = all good, 1 = at least one problem.
"""
import json
import py_compile
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
problems = []


def bad(msg):
    problems.append(msg)
    print("FAIL", msg)


def ok(msg):
    print("ok  ", msg)


def files(patterns, skip=("papers", ".git", "__pycache__", ".omc", ".venv", "node_modules")):
    for pat in patterns:
        for p in ROOT.rglob(pat):
            if p.is_file() and not any(s in p.parts for s in skip):
                yield p


# ---------------------------------------------------------------- 1. JSON files parse
n = 0
for p in files(["*.json"]):
    try:
        json.loads(p.read_text(encoding="utf-8"))
        n += 1
    except ValueError as e:
        bad(f"{p.relative_to(ROOT)}: invalid JSON ({e})")
ok(f"{n} JSON files parse")

# ---------------------------------------------------------------- 2. manifests agree
cm = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
mk = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
px = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))
entry = mk["plugins"][0]
if not (cm["name"] == entry["name"] == px["name"]):
    bad("plugin name differs between plugin.json, marketplace.json and root plugin.json")
if not (cm["version"] == entry.get("version") == px["version"] == mk["metadata"]["version"]):
    bad("version differs between the manifests (bump all of them together)")
if not re.match(r"^\d+\.\d+\.\d+$", cm["version"]):
    bad("version is not semver x.y.z")
top = re.search(r"^## (\d+\.\d+\.\d+)", (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"), re.M)
if not top or top.group(1) != cm["version"]:
    bad("CHANGELOG.md top entry does not match the plugin version")
if cm.get("license") != "Apache-2.0" or px.get("license") != "Apache-2.0":
    bad("manifest license must be Apache-2.0")
if not (ROOT / "NOTICE").exists() or "Apache License" not in (ROOT / "LICENSE").read_text(encoding="utf-8"):
    bad("LICENSE (Apache-2.0 text) and NOTICE must exist")
ok(f"manifests agree (version {cm['version']}, licence Apache-2.0)")

# ---------------------------------------------------------------- 3. Agent Skills rules
skills = sorted(p for p in (ROOT / "skills").iterdir() if p.is_dir() and not p.name.startswith("."))
for d in skills:
    sm = d / "SKILL.md"
    if not sm.exists():
        bad(f"{d.name}: no SKILL.md")
        continue
    s = sm.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", s, re.S)
    if not m:
        bad(f"{d.name}: no front matter")
        continue
    fm = m.group(1)
    name = re.search(r"^name:\s*(.+)$", fm, re.M)
    desc = re.search(r"^description:\s*(.+?)(?=\n[a-z-]+:|\Z)", fm, re.S | re.M)
    if not name or name.group(1).strip() != d.name:
        bad(f"{d.name}: name must equal the folder name")
    if not re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", d.name) or len(d.name) > 64:
        bad(f"{d.name}: name violates the Agent Skills naming rule")
    if not desc or not (1 <= len(desc.group(1).strip()) <= 1024):
        bad(f"{d.name}: description missing or over 1024 characters")
    if s.count("\n") >= 500:
        bad(f"{d.name}: SKILL.md has 500 or more lines")
    if "$HOME/.claude/skills" in s or "~/.claude/skills" in s:
        bad(f"{d.name}: hard-coded ~/.claude/skills path (use <skills>)")
ok(f"{len(skills)} skills follow the Agent Skills rules")
for a in sorted((ROOT / "agents").glob("*.md")):
    s = a.read_text(encoding="utf-8")
    if not re.search(r"^name:\s*\S+", s, re.M) or not re.search(r"^description:\s*\S+", s, re.M):
        bad(f"agents/{a.name}: name or description missing")
    if "$HOME/.claude/skills" in s or "~/.claude/skills" in s:
        bad(f"agents/{a.name}: hard-coded path")
ok("subagent files have name and description")

# ---------------------------------------------------------------- 4. python compiles
for p in files(["*.py"]):
    try:
        py_compile.compile(str(p), doraise=True, cfile=str(Path(__import__("tempfile").gettempdir()) / "gc_check.pyc"))
    except py_compile.PyCompileError as e:
        bad(f"{p.relative_to(ROOT)}: does not compile ({e.msg[:80]})")
ok("python files compile")

# ---------------------------------------------------------------- 5. strength library and profiles are consistent
ref = ROOT / "skills" / "rampwise-strength" / "references"
lib = json.loads((ref / "exercise_library.json").read_text(encoding="utf-8"))
prof = json.loads((ref / "goal_profiles.json").read_text(encoding="utf-8"))
ids = [e["id"] for e in lib["exercises"]]
if len(ids) != len(set(ids)):
    bad("exercise library has duplicate ids")
patterns = {e["pattern"] for e in lib["exercises"]}
tags = set(lib["equipment_tags"])
for e in lib["exercises"]:
    for r in e["requires"]:
        if r not in tags:
            bad(f"exercise {e['id']} requires unknown equipment tag {r}")
    if e["kind"] not in ("heavy", "bw", "iso", "plyo", "speed"):
        bad(f"exercise {e['id']}: bad kind")
for g, c in prof["goals"].items():
    if g == "_about":
        continue
    if not c.get("basis") or not any(b.startswith("research") for b in c["basis"]) and not any(b.startswith("gap") or b.startswith("practice") for b in c["basis"]):
        bad(f"profile {g}: basis lines must carry research / practice / gap labels")
    for lbl in c["basis"]:
        if not re.match(r"^(research|practice|gap)", lbl):
            bad(f"profile {g}: basis line without a label: {lbl[:50]}")
    for s in c["sessions"]:
        for cy in s["cycle"]:
            for sl in cy["slots"]:
                if sl["pattern"] not in patterns:
                    bad(f"profile {g}: unknown pattern {sl['pattern']}")
    for k in ("heavy", "bw", "iso", "plyo", "speed"):
        if k not in c["prescription"]:
            bad(f"profile {g}: prescription missing {k}")
ok(f"strength library ({len(ids)} exercises) and {len(prof['goals'])} goal profiles are consistent")

# ---------------------------------------------------------------- 6. nothing that must not ship
forbidden = [r"(^|/)athlete\.json$", r"\.fit$", r"\.zip$", r"(^|/)profile\.md$", r"(^|/)plans/", r"references/papers/.+\.md$"]
for p in ROOT.rglob("*"):
    if p.is_file() and ".git" not in p.parts:
        rel = p.relative_to(ROOT).as_posix()
        if any(re.search(f, rel) for f in forbidden):
            bad(f"{rel}: must not be committed")
ok("no personal or licensed files in the tree")

# ---------------------------------------------------------------- 7. privacy scan
tokens = []
tf = ROOT / ".privacy-tokens"
if tf.exists():
    tokens = [t.strip() for t in tf.read_text(encoding="utf-8").splitlines() if t.strip()]
PAT = [(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[a-z]{2,}", "email address"), (r"[A-Za-z]:[\\/]Users[\\/]", "Windows user path"), (r"/Users/[A-Za-z]", "macOS user path"), (r"/home/[a-z]", "Linux home path"),
       (r"\b[A-Z]:/(?!\*)[A-Za-z]", "drive path"), (r"(?i)(api[_-]?key|secret|token)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{16,}", "key-like value"),
       (r"(?<![\w./-])\d{10,}(?![\w./-])", "long number (activity id?)")]
ALLOW_EMAIL = {"noreply@anthropic.com", "noreply@github.com"}
hits = 0
for p in files(["*.md", "*.py", "*.json", "*.html", "*.yml", "*.txt"]):
    if p.name in ("check_repo.py", "package-lock.json"):
        continue
    t = p.read_text(encoding="utf-8", errors="replace")
    for rx, label in PAT:
        for m in re.finditer(rx, t):
            val = m.group(0)
            if label == "email address" and (val in ALLOW_EMAIL or val.endswith(("@example.com", "@users.noreply.github.com"))):
                continue
            if label == "drive path" and ("D:/" not in val and "C:/" not in val):
                continue
            if label == "long number (activity id?)" and p.name in ("default.spec.json", "template.html", "exercise_library.json"):
                continue
            hits += 1
            bad(f"{p.relative_to(ROOT)}: {label}: {val[:40]}")
            break
    for tok in tokens:
        if tok.lower() in t.lower():
            hits += 1
            bad(f"{p.relative_to(ROOT)}: contains private token from .privacy-tokens")
            break
if not hits:
    ok(f"privacy scan clean ({len(tokens)} private tokens checked)")

# ---------------------------------------------------------------- 8. release gate: placeholders must be replaced (python tests/check_repo.py --release)
if "--release" in sys.argv:
    PH1, PH2 = "{{" + "GITHUB_OWNER" + "}}", "{{" + "AUTHOR_NAME" + "}}"
    left = [str(p.relative_to(ROOT)) for p in files(["*.md", "*.json", "*.py", "*.yml"]) if p.name not in ("set_owner.py", "check_repo.py") and (PH1 in p.read_text(encoding="utf-8") or PH2 in p.read_text(encoding="utf-8"))]
    if left:
        bad("placeholders still present (run tools/set_owner.py): " + ", ".join(left[:6]))
    else:
        ok("no placeholders left")

print()
print("ALL OK" if not problems else f"{len(problems)} problem(s)")
sys.exit(1 if problems else 0)
