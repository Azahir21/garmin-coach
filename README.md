# Garmin Coach

**Evidence-labelled endurance coaching for AI agents.** Running, cycling and strength plans built from *your own* Garmin data, with specialists for recovery, load, heat, fueling and heart-rate zones. Works as a Claude Code plugin, a Codex plugin, or as plain Agent Skills in other harnesses.

> **Status: v0.2.0, experimental.** Built by one runner and cyclist for their own training, then generalised. It has **not** been tested on other people, other watches, or over a full training cycle. There is no promise it works for you. The first user tests it on their own body for three months and will publish an honest update ([docs/FIELD-TEST.md](docs/FIELD-TEST.md)). Read [DISCLAIMER.md](DISCLAIMER.md) first.

## What it does
- **Plans**: rolling 4-week plans (easy, long, tempo, strides, intervals, climb and MAF-test sessions; rides; strength) from your last weeks of training, with reset and deload weeks and a +10 % step cap.
- **Garmin workouts**: writes structured `.fit` workout files (warm-up, steady, intervals, rest, cool-down) with your watch's own heart-rate **zone** when one covers the band, otherwise a custom bpm range, and says which it used. Not verified on every watch.
- **Specialists**: recovery (HRV, sleep, resting HR to a GREEN/AMBER/RED readiness), aerobic base (pace at a heart rate, drift), load and injury flags, heat and weather adjustment, fueling and sweat-rate maths, strength placement.
- **Analyse**: your latest session against the last similar one, and the last 7 days against the 7 before (works on any day, activity or not), plus an **injury-risk watch** that combines load, recovery and what you tell it about pain. Flags are prompts with an evidence label, never a diagnosis.
- **Adapt**: each morning it re-checks tomorrow's planned session against your readiness, the watch and how much of the plan you actually did: keep, a small step up (only when everything is green), easier, shorter, or rest. It prepares the calendar update; it changes your calendar only after you agree.
- **Reports**: daily, weekly and monthly reports as Markdown with figures and as an interactive single-file HTML page (offline, light/dark): recovery, week-over-week, injury watch, plan against done, pace/speed and efficiency trends, strength logs and goal meters. Goals are optional and follow your own settings.
- **Strength generator**: 11 goal profiles (endurance, runner 5K to marathon, trail and ultra, middle distance, cyclist road / sprint / bone health, triathlon, sprint, general), a 60-exercise library, progression from your own logged sets.
- **Memory**: goals, injuries, equipment and preferences persist in a file on your computer.
- **Honesty**: every rule is tagged *research*, *practice* or *gap* in an evidence map; the papers are listed in [docs/PAPERS.md](docs/PAPERS.md). It asks instead of assuming (heart-rate data, equipment, starting weights) and falls back to your activity trend only if you do not answer.
- Adaptive by design: quality sessions are on for everyone and locked only by *your* data (an active injury, a RED reset week, your own settings).

## Requirements
- A Garmin account with the official **Personal API** access, and the [`garmin-personal-mcp`](https://github.com/Mason-Levyy/garmin-personal-mcp) server (MIT, by Mason Levy). Install [uv](https://docs.astral.sh/uv/), then once: `uv tool install --python 3.12 garmin-personal-mcp` and `garmin-personal-mcp auth` (follow that project's README for the key).
- Python 3.10 or newer, and `pip install fitdecode` (reads FIT files).
- An AI agent harness that loads Agent Skills (Claude Code, Codex, others).

## Install

**Claude Code** (plugin marketplace):
```text
/plugin marketplace add Azahir21/garmin-coach
/plugin install garmin-coach@garmin-coach
```
Skills appear as `/garmin-coach:garmin-coach`, `/garmin-coach:garmin-planner` and so on; subagents as `garmin-coach:coach-recovery`, etc.

**Codex** (per OpenAI's plugin docs; **not tested by us**):
```text
codex plugin marketplace add Azahir21/garmin-coach
```
then open `/plugins` and install *garmin-coach*. Codex plugins do not ship subagents: the skills work without them.

**Any other harness that supports Agent Skills**, or if you prefer plain files:
```text
git clone https://github.com/Azahir21/garmin-coach
python garmin-coach/install.py --target agents      # copies skills to ~/.agents/skills
python garmin-coach/install.py --target claude      # copies skills and subagents to ~/.claude
```

## Updates (auto-update)
- **Claude Code:** third-party marketplaces do **not** auto-update by default. Turn it on: `/plugin` -> *Marketplaces* -> *garmin-coach* -> *Enable auto-update*. A plugin updates when its `version` changes, and this repository bumps the version on every release. Manual: `claude plugin update garmin-coach@garmin-coach`, then `/reload-plugins`.
- **Claude Code, always on:** per Anthropic's docs the marketplace entry in your settings can carry `autoUpdate` (`extraKnownMarketplaces`); check the current docs for the exact shape, and note that updates apply after `/reload-plugins` or the next launch.
- **Codex:** `codex plugin marketplace upgrade garmin-coach` (the docs do not describe automatic plugin updates).
- **install.py users:** `python install.py --update` runs `git pull --ff-only` and reinstalls.
- Your personal data is **not** in the plugin folder, so updates never overwrite it.

## First run
Ask your agent: *"Set up my Garmin coach."* The head coach creates your `athlete.json` (`athlete.py init`), interviews you (goals, injuries and how you feel today, equipment, exercises you cannot do, schedule, and whether you want to share your watch's heart-rate zones), checks the Garmin connection, then builds your first plan. After that: *"How am I today?"*, *"Plan the next two weeks"*, *"Build my workouts"*, *"Why did my heart rate drift?"*.

**A day with it:** morning, *"Daily report"* (readiness, injury watch, yesterday's session against the last similar one, tomorrow adapted) and *"adjust tomorrow"* (updates your `[GC]` calendar event after you agree). Sunday, *"Weekly report"*. First of the month, *"Monthly report"*. Reports land in `~/garmin-coach-data/reports/` (override with `GARMIN_COACH_DATA`); `latest-weekly.html` is always the newest.

## Safety and evidence
Not medical advice. See [DISCLAIMER.md](DISCLAIMER.md). The planner never promises a date for a goal; targets are checked against your data. See [PRIVACY.md](PRIVACY.md) for what stays on your machine.

## Repository layout
```text
.claude-plugin/        Claude Code plugin and marketplace manifests
plugin.json            portable manifest (Codex)
.agents/plugins/       Codex marketplace catalogue
.mcp.json              the Garmin data server
skills/                eleven Agent Skills (SKILL.md + scripts + references)
agents/                nine subagent prompts (Claude Code)
tools/                 install, owner placeholders, paper fetcher
tests/                 repo checks and offline tests (no Garmin account needed)
docs/                  papers, field-test protocol, harness notes
```

## Contributing
Issues and pull requests are welcome, especially: users on other watches, new goal profiles backed by papers, translations, and new report sections. See [CONTRIBUTING.md](CONTRIBUTING.md). Credits and licences: [CREDITS.md](CREDITS.md). Licence: [Apache-2.0](LICENSE) (code, docs and evidence maps); third-party code keeps its own licence, see [NOTICE](NOTICE) and [CREDITS.md](CREDITS.md).
