# Rampwise: instructions for AI agents

This repository is a set of **Agent Skills** (`skills/<name>/SKILL.md`) plus subagent prompts (`agents/*.md`) and Python scripts that coach a runner and cyclist from their own Garmin data.

## How to work here
- Start with the **`rampwise`** skill (head coach). It tells you which specialist skill to load and which script to run. Specialists: `rampwise-recovery`, `rampwise-aerobic-base`, `rampwise-heat-weather`, `rampwise-load-injury`, `rampwise-strength`, `rampwise-fueling`, `rampwise-planner` (also `event_plan.py`: race plans for 17 events without Garmin data, `plan_viewer.py`, `export_plan.py`), `rampwise-analyze` (week comparison, injury-risk watch), `rampwise-adapt` (adapt tomorrow's session, calendar payload), `rampwise-report` (daily/weekly/monthly reports).
- Scripts are Python 3.10+ and are run from the command line: `python -X utf8 <skills>/<skill>/scripts/<file>.py`. `<skills>` is the folder holding the `rampwise-*` skill folders. Numbers must come from the scripts, rules from each skill's `references/evidence-map.md`. Never invent a number, a paper or a timeline.
- Garmin data comes from the `garmin-personal-mcp` server (`.mcp.json`; `garmin-personal-mcp auth` stores the key once). The scripts start it themselves.
- Installing for other tools: `python install.py --list` and `docs/INSTALL.md` (the registry of tool folders is in `install.py`; every entry cites a page read on a stated date: do not add a tool or a path from memory).
- Personal data lives in `$RAMPWISE_DATA` (default `~/rampwise-data`). First run: `athlete.py init`, then interview the user.

## Non-negotiable rules
1. **Ask, never assume**: heart-rate zones, equipment, banned exercises, starting weights, injuries. If the user does not answer, use the documented fallback and label it an estimate.
2. **Label evidence**: research / practice / gap. Do not claim more than the evidence map says.
3. **Adapt to this user**: locks and limits come from the user's own data, never from another person's history.
4. **Safety**: pain that changes gait or worsens, chest pain, fainting: stop and recommend a clinician. This is not medical advice.
5. **Privacy**: never commit or print `athlete.json` contents beyond what the session needs; never write to the user's calendar without being asked.

## Development
- Checks: `python tests/check_repo.py && python tests/test_offline.py` (no Garmin account needed).
- Do not add personal data, API keys, `.fit` files or paper full texts. Follow `CONTRIBUTING.md`.
