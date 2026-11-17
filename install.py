#!/usr/bin/env python3
"""Install Rampwise for your AI coding agent.

  python install.py --list                         every supported tool, where its skills go, how well it was checked
  python install.py --tool codex                   skills for one tool (user level: all your projects)
  python install.py --tool cursor,zed,goose        several tools at once (shared folders are written once)
  python install.py --tool all --dry-run           show what would be written, write nothing
  python install.py --tool cursor --scope project --project ~/my-repo      skills inside one project instead
  python install.py --tool aider --project ~/my-repo                       tools without skills get an instructions file in the project
  python install.py --tool codex --uninstall       remove what this installer wrote
  python install.py --update --tool codex          git pull --ff-only first, then install again
  python install.py --link                         symlink instead of copy (development)

Older forms still work: --target agents | claude | both, and --dest DIR.

Personal data is NOT in these folders: it lives in $RAMPWISE_DATA (default ~/rampwise-data) and is never touched.
Skills are plain Agent Skills folders (SKILL.md plus Python scripts). The scripts run on YOUR computer and read your own Garmin data,
so the agent must run on your machine and be allowed to run Python. Cloud-only agents cannot coach you (see docs/INSTALL.md).
"""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SKILLS = ROOT / "skills"
AGENTS = ROOT / "agents"
BEGIN, END = "<!-- rampwise:begin -->", "<!-- rampwise:end -->"
SHARED = "~/.agents/skills"                      # the cross-tool folder of the Agent Skills standard (agentskills.io)

# One entry per tool. skills = user-level folder, project = project-level folder (both from the tool's own documentation).
# mode "skills": the tool reads SKILL.md folders. mode "rules": no skills feature found, so an instructions file points the agent at the skills.
# status "read": the official documentation page was read on 2026-11-17 (see docs/INSTALL.md for the pages). "unverified": it could not be read.
TOOLS = {
    "claude-code": dict(name="Claude Code", mode="skills", skills="~/.claude/skills", project=".claude/skills", agents="~/.claude/agents", status="read",
                        notes=["Easier: the plugin marketplace (see the README). This copies skills and subagents."]),
    "codex": dict(name="OpenAI Codex", mode="skills", skills=SHARED, project=".agents/skills", status="read", notes=["Restart Codex after installing."]),
    "hermes": dict(name="Hermes Agent", mode="skills", skills="~/.hermes/skills", project=".hermes/skills", status="read",
                   notes=["Project skills are ignored until you run `hermes skills trust` in the repository."]),
    "openclaw": dict(name="OpenClaw", mode="skills", skills="~/.openclaw/skills", project=".agents/skills", status="read",
                     notes=["User folder is the shared 'managed' folder (what `openclaw skills install --global` uses). Treat skills as code you must trust."]),
    "gemini": dict(name="Gemini CLI", mode="skills", skills=SHARED, project=".agents/skills", status="read",
                   notes=["Google's Gemini CLI docs carry a banner saying it was replaced by Antigravity CLI on 2026-06-18; install both if you use either.",
                          "Check with `gemini skills list`."]),
    "antigravity": dict(name="Google Antigravity", mode="skills", skills="~/.gemini/config/skills", project=".agents/skills", status="read",
                        notes=["Global folder from Google's current docs. Older guides say ~/.gemini/antigravity/skills (the IDE still reads it) and .agent/skills (still read)."]),
    "cursor": dict(name="Cursor", mode="skills", skills=SHARED, project=".agents/skills", status="read", notes=["Cursor also reads ~/.claude/skills; the same skill in two folders can show twice."]),
    "copilot": dict(name="GitHub Copilot", mode="skills", skills=SHARED, project=".github/skills", status="read",
                    notes=["Skills work in Copilot CLI, the coding agent and agent mode; which folders count depends on the surface.",
                           "Copilot cloud agent runs on GitHub, not on your machine: it cannot reach your Garmin data."]),
    "windsurf": dict(name="Windsurf", mode="skills", skills=SHARED, project=".agents/skills", status="read",
                     notes=["Windsurf's docs redirect to Devin Desktop's, which reads ~/.agents/skills, .agents/skills and the older .windsurf/skills."]),
    "aider": dict(name="Aider", mode="rules", rules="aider", status="read",
                  notes=["Aider has no skills feature. This writes RAMPWISE.md in the project and tells you the one line to add to .aider.conf.yml (`read: RAMPWISE.md`).",
                         "Aider does not run commands by itself: it suggests them (/run); coaching is limited."]),
    "cline": dict(name="Cline", mode="skills", skills="~/.cline/skills", project=".cline/skills", status="read",
                  notes=["A global skill beats a project skill of the same name."]),
    "opencode": dict(name="OpenCode", mode="skills", skills=SHARED, project=".agents/skills", status="read",
                     notes=["OpenCode's own folders are ~/.config/opencode/skills and .opencode/skills; it also reads the shared one."]),
    "devin": dict(name="Devin (CLI, Desktop and repo skills)", mode="skills", skills=SHARED, project=".agents/skills", status="read",
                  notes=["Devin CLI and Desktop read your folders; the Devin cloud product only reads skills committed to a repo, and cannot reach your Garmin data."]),
    "amazonq": dict(name="Amazon Q Developer", mode="rules", rules="amazonq", status="read",
                    notes=["Only the IDE project-rules folder (.amazonq/rules) could be verified; no skills feature was found in AWS's documentation.",
                           "The Q Developer CLI's agent format could not be read, so nothing is installed for it."]),
    "kilo": dict(name="Kilo Code", mode="skills", skills=SHARED, project=".agents/skills", status="read",
                 notes=["Kilo's own folders are ~/.kilo/skills and .kilo/skills (the old .kilocode/skills name appears only in older guides)."]),
    "roo": dict(name="Roo Code", mode="skills", skills=SHARED, project=".agents/skills", status="read",
                notes=["WARNING: Roo Code's docs home page says the extension was shut down on May 15th (2026). Install only if you still run a fork."]),
    "goose": dict(name="Goose", mode="skills", skills=SHARED, project=".agents/skills", status="read", notes=["List with `goose skills list`."]),
    "continue": dict(name="Continue.dev", mode="rules", rules="continue", status="read",
                     notes=["Continue's documentation has rules but no skills feature. This writes .continue/rules/rampwise.md (always applied)."]),
    "zed": dict(name="Zed", mode="skills", skills=SHARED, project=".agents/skills", status="read",
                notes=["Zed wants each skill as a direct child of the folder (this installer does that). Project skills load only from trusted worktrees."]),
    "amp": dict(name="Amp", mode="skills", skills=SHARED, project=".agents/skills", status="read", notes=["Amp can also install: `amp skill add <path or git url> --global`."]),
    "jules": dict(name="Google Jules", mode="rules", rules="jules", status="read",
                  notes=["Jules runs in a cloud virtual machine: it cannot reach your Garmin data or local scripts. Only an AGENTS.md pointer and skills in the repo are written; it cannot coach you."]),
    "augment": dict(name="Augment Code", mode="skills", skills=SHARED, project=".agents/skills", status="read",
                    notes=["Auggie CLI reads it; in the IDE, skills are a Public Beta you switch on in Settings."]),
    "kiro": dict(name="Kiro", mode="skills", skills="~/.kiro/skills", project=".kiro/skills", status="read",
                 notes=["Custom Kiro agents do not load skills by default: add skill://.kiro/skills/*/SKILL.md and skill://~/.kiro/skills/*/SKILL.md to the agent's resources."]),
    "vibe": dict(name="Mistral Vibe", mode="skills", skills=SHARED, project=".agents/skills", status="read",
                 notes=["Project skills load only in a trusted folder. Run /reload in a running session."]),
    "gitlab": dict(name="GitLab Duo", mode="skills", skills=SHARED, project=".agents/skills", status="read",
                   notes=["User-level skills work only in the Duo CLI and are an experiment: start it with `duo --enable-global-skills true` (or GITLAB_ENABLE_GLOBAL_SKILLS=true).",
                          "Duo flows run in GitLab, not on your machine: they cannot reach your Garmin data. Use the Duo CLI."]),
    "trae": dict(name="Trae AI", mode="skills", skills="~/.trae/skills", project=".trae/skills", status="unverified",
                 notes=["UNVERIFIED: Trae's official documentation pages returned no text, so these folders come from third-party guides only. Check Trae's Rules & Skills settings after installing."]),
    "qwen": dict(name="Qwen Code", mode="skills", skills=SHARED, project=".agents/skills", status="read",
                 notes=["Qwen Code's own folders are ~/.qwen/skills and .qwen/skills (they win over the shared one). Restart it after installing."]),
    "warp": dict(name="Warp", mode="skills", skills=SHARED, project=".agents/skills", status="read", notes=[]),
    "junie": dict(name="JetBrains Junie", mode="skills", skills=SHARED, project=".agents/skills", status="read",
                  notes=["Junie's own folders are ~/.junie/skills and .junie/skills; it also loads the shared one."]),
    "factory": dict(name="Factory (Droid)", mode="skills", skills="~/.factory/skills", project=".factory/skills", status="read", notes=["Factory also reads .agents/skills."]),
}
REQUIRED = ["codex", "hermes", "openclaw", "gemini", "antigravity", "cursor", "copilot", "windsurf", "aider", "cline", "opencode", "devin", "amazonq", "kilo", "roo",
            "goose", "continue", "zed", "amp", "jules", "augment", "kiro", "vibe", "gitlab", "trae", "qwen", "warp", "junie", "factory"]

POINTER = """## Rampwise (AI endurance coach)
Rampwise skills are installed in `{skills}`. For any training question (readiness, a plan, a report, an injury, heat, fuelling, strength) read `{skills}/rampwise/SKILL.md` first and follow it.
Run its Python scripts with `python -X utf8 "{skills}/<skill>/scripts/<file>.py"`. They read the athlete's own Garmin data on this machine.
Ask the athlete; never guess heart-rate zones, equipment, injuries or starting weights. This is not medical advice."""


def home_path(t: str) -> Path:
    return Path(t.replace("~", str(Path.home()), 1)) if t.startswith("~") else Path(t)


PAPERS = Path("references") / "papers"        # local paper files (tools/build_paper_files.py): git-ignored, never in the repository, so an install or uninstall must not delete them


def stash_papers(dst: Path):
    """Move a skill's local papers folder out of the way before the folder is replaced. Returns the temporary path, or None."""
    pp = dst / PAPERS
    if dst.is_symlink() or not pp.is_dir():
        return None
    keep = dst.parent / f".{dst.name}-papers-keep"
    if keep.exists():
        shutil.rmtree(keep)
    shutil.move(str(pp), str(keep))
    return keep


def restore_papers(keep, dst: Path):
    if keep is None:
        return
    target = dst / PAPERS
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not target.is_symlink():
        for f in keep.iterdir():                         # the new folder already has some: add the rest, never overwrite
            if not (target / f.name).exists():
                shutil.move(str(f), str(target / f.name))
        shutil.rmtree(keep)
    else:
        shutil.move(str(keep), str(target))


def place(src: Path, dst: Path, link: bool):
    keep = stash_papers(dst) if src.is_dir() else None
    if dst.is_symlink() or dst.is_file():
        dst.unlink()
    elif dst.exists():
        shutil.rmtree(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if link:
        try:
            dst.symlink_to(src, target_is_directory=src.is_dir())
            restore_papers(keep, dst)                    # dst is the repository folder: the papers go into its git-ignored papers folder
            return "linked"
        except OSError:
            pass
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc")) if src.is_dir() else shutil.copy2(src, dst)
    restore_papers(keep, dst)
    return "copied"


def remove_skill(tgt: Path):
    """Uninstall one skill folder but keep its local papers (they were not written by this installer). Returns how many paper files were kept."""
    keep = stash_papers(tgt)
    if tgt.is_dir() and not tgt.is_symlink():
        shutil.rmtree(tgt)
    elif tgt.exists() or tgt.is_symlink():
        tgt.unlink()
    if keep is None:
        return 0
    n = sum(1 for _ in keep.rglob("*") if _.is_file())
    restore_papers(keep, tgt)
    return n


def upsert_block(path: Path, body: str, whole_file_header: str = ""):
    """Write a marked block into a file: replace it if it is there, else append. Never touches anything outside the markers."""
    block = f"{BEGIN}\n{body}\n{END}\n"
    text = path.read_text(encoding="utf-8") if path.exists() else whole_file_header
    if BEGIN in text and END in text:
        a, b = text.index(BEGIN), text.index(END) + len(END)
        text = text[:a] + block.rstrip("\n") + text[b:]
        if not text.endswith("\n"):
            text += "\n"
    else:
        text = (text.rstrip("\n") + "\n\n" if text.strip() else "") + block
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def prune_empty(path: Path, stop: Path):
    """Remove empty folders left behind by an uninstall, walking up but never removing `stop` (the home or project folder) or anything above it."""
    stop = stop.resolve()
    path = path.resolve()
    while path != stop and stop in path.parents:
        try:
            path.rmdir()
        except OSError:
            return
        path = path.parent


def remove_block(path: Path, header: str = ""):
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    if BEGIN not in text or END not in text:
        return False
    a, b = text.index(BEGIN), text.index(END) + len(END)
    rest = (text[:a].rstrip("\n") + "\n" + text[b:].lstrip("\n")).strip("\n")
    if not rest.strip() or rest.strip() == header.strip():
        path.unlink()
    else:
        path.write_text(rest + "\n", encoding="utf-8")
    return True


def rule_files(kind: str, project: Path, skills_dir: Path):
    """(file, body, header) for tools that have no skills feature."""
    body = POINTER.format(skills=str(skills_dir).replace("\\", "/"))
    if kind == "continue":
        return [(project / ".continue" / "rules" / "rampwise.md", body, "---\nname: Rampwise\nalwaysApply: true\n---\n\n")]
    if kind == "amazonq":
        return [(project / ".amazonq" / "rules" / "rampwise.md", body, "")]
    if kind == "jules":
        return [(project / "AGENTS.md", body, "")]
    if kind == "aider":
        return [(project / "RAMPWISE.md", body, "")]
    return []


def build_actions(tools, scope, project: Path):
    """List of ('skills', dest_dir, agents_dir_or_None) and ('rules', file, body, header, tool). Shared folders are listed once."""
    skill_dests, rules, notes = {}, [], []
    for key in tools:
        t = TOOLS[key]
        notes.append((key, t))
        if t["mode"] == "skills":
            d = (project / t["project"]) if scope == "project" else home_path(t["skills"])
            ag = home_path(t["agents"]) if t.get("agents") and scope == "user" else None
            skill_dests.setdefault(d, ag)
        else:
            # no skills feature: the skills sit in the shared folder (or, for a cloud agent, inside the repo) and an instructions file points at them
            sd = (project / ".agents" / "skills") if (key == "jules" or scope == "project") else home_path(SHARED)
            skill_dests.setdefault(sd, None)
            for f, body, header in rule_files(t["rules"], project, sd):
                rules.append((f, body, header, key))
    return skill_dests, rules, notes


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tool", help="tool name(s), comma separated, or 'all' (see --list)")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--scope", choices=["user", "project"], default="user", help="user = all your projects (default); project = inside --project only")
    ap.add_argument("--project", help="project folder (default: the current folder)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--uninstall", action="store_true")
    ap.add_argument("--target", choices=["agents", "claude", "both"], help="older form: agents = ~/.agents/skills, claude = ~/.claude")
    ap.add_argument("--dest")
    ap.add_argument("--update", action="store_true")
    ap.add_argument("--link", action="store_true")
    a = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if a.list:
        print(f"{'key':12} {'tool':34} {'user-level skills folder':26} {'project folder':18} checked")
        for k, t in TOOLS.items():
            where = t["skills"] if t["mode"] == "skills" else "(instructions file)"
            print(f"{k:12} {t['name']:34} {where:26} {t.get('project', '-'):18} {t['status']}")
        print("\n'read' = the tool's official documentation was read (2026-11-17), not that we ran the tool. See docs/INSTALL.md.")
        return
    tools = []
    if a.target in ("agents", "both"):
        tools.append("codex")
    if a.target in ("claude", "both"):
        tools.append("claude-code")
    if a.tool:
        tools += REQUIRED + ["claude-code"] if a.tool == "all" else [x.strip().lower() for x in a.tool.split(",") if x.strip()]
    tools = list(dict.fromkeys(tools))
    bad = [x for x in tools if x not in TOOLS]
    if bad:
        ap.error(f"unknown tool(s): {', '.join(bad)}. Run --list.")
    if not (tools or a.dest):
        ap.error("choose --tool (see --list), or --dest DIR")
    if a.update:
        r = subprocess.run(["git", "-C", str(ROOT), "pull", "--ff-only"])
        if r.returncode:
            sys.exit("git pull failed: resolve it, then run again")
    project = Path(a.project).expanduser().resolve() if a.project else Path.cwd()
    file_tools = [x for x in tools if TOOLS[x]["mode"] == "rules"]
    if file_tools and not a.project:
        if a.tool == "all":
            tools = [x for x in tools if x not in file_tools]
            print(f"Skipped (they write files into a project; add --project DIR): {', '.join(file_tools)}")
        elif not a.dry_run:
            ap.error(f"{', '.join(file_tools)} write an instructions file into a project: add --project DIR (or --dry-run to preview)")
    skill_dests, rules, notes = build_actions(tools, a.scope, project)
    if a.dest:
        skill_dests.setdefault(Path(a.dest).expanduser(), None)
    names = [s.name for s in sorted(SKILLS.iterdir()) if s.is_dir() and (s / "SKILL.md").exists()]
    verb = "remove" if a.uninstall else "install"
    for key, t in notes:
        if t["status"] != "read" and not a.uninstall:
            print(f"!! {t['name']}: {t['notes'][0]}")
    for dest, ag in skill_dests.items():
        for n in names:
            tgt = dest / n
            if a.uninstall:
                kept = 0
                if not a.dry_run and (tgt.exists() or tgt.is_symlink()):
                    kept = remove_skill(tgt)
                print(f"{'would remove' if a.dry_run else 'removed':12} {tgt}" + (f"   (kept {kept} local paper files in references/papers)" if kept else ""))
            else:
                print(f"{'would write' if a.dry_run else place(SKILLS / n, tgt, a.link):12} {tgt}")
        if a.uninstall and not a.dry_run:
            prune_empty(dest, project if project.resolve() in dest.resolve().parents else Path.home())
        if ag is not None and AGENTS.exists():
            for f in sorted(AGENTS.glob("*.md")):
                if a.uninstall:
                    if not a.dry_run and (ag / f.name).exists():
                        (ag / f.name).unlink()
                    print(f"{'would remove' if a.dry_run else 'removed':12} {ag / f.name}")
                else:
                    print(f"{'would write' if a.dry_run else place(f, ag / f.name, a.link):12} {ag / f.name}")
    for f, body, header, key in rules:
        if a.uninstall:
            if not a.dry_run:
                remove_block(f, header)
                prune_empty(f.parent, project)
            print(f"{'would clean' if a.dry_run else 'cleaned':12} {f}")
        else:
            if not a.dry_run:
                upsert_block(f, body, header)
            print(f"{'would write' if a.dry_run else 'wrote':12} {f}")
        if key == "aider" and not a.uninstall:
            print("             add this line to .aider.conf.yml (not edited for you):  read: RAMPWISE.md")
    if not a.uninstall:
        for key, t in notes:
            for n in t["notes"][(0 if t["status"] == "read" else 1):]:
                print(f"note ({t['name']}): {n}")
        old = sorted(x.name for d in skill_dests for x in d.glob("garmin-*") if x.is_dir() and (x / "SKILL.md").exists()) if not a.dry_run else []
        if old:
            print(f"\nNote: older skills from before the rename to Rampwise are still installed: {', '.join(old)}. They are superseded by the rampwise-* skills; remove them when you are ready (your data is not inside them).")
        print(f"\nDone ({verb}). Next: pip install fitdecode ; garmin-personal-mcp auth ; restart your tool ; ask it: Set up my Rampwise coach.")
    else:
        print("\nUninstalled. Your data in ~/rampwise-data and ~/rampwise-coach was not touched.")


if __name__ == "__main__":
    main()
