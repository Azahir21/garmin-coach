# Install Rampwise in your AI tool

Rampwise is a folder of **Agent Skills** (`skills/<name>/SKILL.md` plus Python scripts). Any agent that reads Agent Skills ([agentskills.io](https://agentskills.io)) can use it; for the rest there is an instructions-file fallback. One command does it:

```text
git clone https://github.com/Azahir21/rampwise
python rampwise/install.py --list                      # every tool, where its skills go, how well we checked it
python rampwise/install.py --tool codex                # one tool
python rampwise/install.py --tool cursor,zed,goose     # several; shared folders are written once
python rampwise/install.py --tool all --dry-run        # show everything it would write, write nothing
```

Then: `pip install fitdecode`, `garmin-personal-mcp auth`, restart your tool, and ask it: *Set up my Rampwise coach.*
Remove everything the installer wrote with the same command plus `--uninstall`. Your data (`~/rampwise-data`) and your generated files (`~/rampwise-coach`) are never touched.

## It must run on your computer
The scripts read **your own Garmin data** through a local server and write your plans next to your files. So the agent has to run on your machine and be allowed to run Python. These cannot coach you, even with the skills installed: **Google Jules** (cloud virtual machine), the **GitHub Copilot cloud agent**, **GitLab Duo flows** and the **Devin cloud product** (they run on a server, not on your machine). Their local versions can: Copilot CLI and agent mode, the Duo CLI, Devin CLI and Desktop.

## Other ways to install
- **Vercel's `skills` CLI** (works with many of the tools above): `npx skills add Azahir21/rampwise`. Checked: `npx skills@1.4.0 add Azahir21/rampwise --list` finds all 11 skills (newer `skills` releases need Node 22.20 or later). An install through it was not tried. It lists your skills on skills.sh through anonymous install counts.
- **Hermes Agent**: `hermes skills tap add Azahir21/rampwise`, then `hermes skills install Azahir21/rampwise/skills/rampwise` (from Hermes's documentation; not tried with this repo).

## What "checked" means here
For every tool below, the official documentation page was **read on 2026-11-17** and the folder names come from it. **We did not run these tools ourselves**: only Claude Code has been used with Rampwise. If a tool's behaviour differs from its documentation, please open an issue ([field report](../.github/ISSUE_TEMPLATE/field-report.md)). Tool vendors rename and move folders often; `python install.py --list` shows what this version of Rampwise assumes.

Two things could not be verified: **Trae AI** (its documentation pages returned no text, so its folders come from third-party guides and the installer says so) and the **Amazon Q Developer CLI** (the AWS page was empty; only the IDE project-rules folder was verified, and Amazon Q has no skills feature we could find).

## Where each tool reads skills
`~/.agents/skills` is the shared folder of the standard. Most tools read it, so installing for several of them writes the files once.

| `--tool` | Tool | User-level skills (all projects) | Project folder (`--scope project`) | Notes |
|---|---|---|---|---|
| `codex` | OpenAI Codex | `~/.agents/skills` | `.agents/skills` | Reads `AGENTS.md`. Restart Codex. |
| `hermes` | Hermes Agent | `~/.hermes/skills` | `.hermes/skills` | Project skills need `hermes skills trust`. |
| `openclaw` | OpenClaw | `~/.openclaw/skills` | `.agents/skills` | Treat skills as code you trust. |
| `gemini` | Gemini CLI | `~/.agents/skills` (alias `~/.gemini/skills`) | `.agents/skills` | Docs say it was replaced by Antigravity CLI on 2026-06-18. `gemini skills list` to check. |
| `antigravity` | Google Antigravity | `~/.gemini/config/skills` | `.agents/skills` | Older guides: `~/.gemini/antigravity/skills`, `.agent/skills` (still read). |
| `cursor` | Cursor | `~/.agents/skills` | `.agents/skills` | Also reads `~/.claude/skills`: may show a skill twice. |
| `copilot` | GitHub Copilot | `~/.agents/skills` | `.github/skills` | CLI, agent mode, cloud agent (cloud cannot reach your data). |
| `windsurf` | Windsurf | `~/.agents/skills` | `.agents/skills` | Docs redirect to Devin Desktop's. |
| `aider` | Aider | none (no skills feature) | `RAMPWISE.md` | Add `read: RAMPWISE.md` to `.aider.conf.yml`. Aider only suggests commands; limited. |
| `cline` | Cline | `~/.cline/skills` | `.cline/skills` | Global beats project of the same name. |
| `opencode` | OpenCode | `~/.agents/skills` | `.agents/skills` | Own folders: `~/.config/opencode/skills`, `.opencode/skills`. |
| `devin` | Devin (CLI, Desktop) | `~/.agents/skills` | `.agents/skills` | The cloud product reads repo skills only. |
| `amazonq` | Amazon Q Developer | none | `.amazonq/rules/rampwise.md` | IDE rules only; see above. |
| `kilo` | Kilo Code | `~/.agents/skills` | `.agents/skills` | Own folder `~/.kilo/skills`; `.kilocode/skills` is the old name. |
| `roo` | Roo Code | `~/.agents/skills` | `.agents/skills` | **Docs say the extension was shut down on May 15th (2026).** |
| `goose` | Goose | `~/.agents/skills` | `.agents/skills` | `goose skills list`. |
| `continue` | Continue.dev | none (rules only) | `.continue/rules/rampwise.md` | Always-applied rule. |
| `zed` | Zed | `~/.agents/skills` | `.agents/skills` | Each skill a direct child of the folder; trusted worktrees only. |
| `amp` | Amp | `~/.agents/skills` | `.agents/skills` | `amp skill add <path> --global` also works. |
| `jules` | Google Jules | none | `AGENTS.md` + `.agents/skills` | Cloud VM: cannot coach you. |
| `augment` | Augment Code | `~/.agents/skills` | `.agents/skills` | IDE skills are a Public Beta in Settings; Auggie CLI reads them. |
| `kiro` | Kiro | `~/.kiro/skills` | `.kiro/skills` | Custom agents need `skill://` entries in `resources`. |
| `vibe` | Mistral Vibe | `~/.agents/skills` | `.agents/skills` | Trusted folders only for project skills; `/reload`. |
| `gitlab` | GitLab Duo | `~/.agents/skills` | `.agents/skills` | User-level skills: Duo CLI only, experimental (`--enable-global-skills true`). |
| `trae` | Trae AI | `~/.trae/skills` | `.trae/skills` | **Unverified** (see above). |
| `qwen` | Qwen Code | `~/.agents/skills` | `.agents/skills` | Own folders `~/.qwen/skills`, `.qwen/skills` win. |
| `warp` | Warp | `~/.agents/skills` | `.agents/skills` | |
| `junie` | JetBrains Junie | `~/.agents/skills` | `.agents/skills` | Own folders `~/.junie/skills`, `.junie/skills`. |
| `factory` | Factory (Droid) | `~/.factory/skills` | `.factory/skills` | Also reads `.agents/skills`. |
| `claude-code` | Claude Code | `~/.claude/skills` (+ subagents) | `.claude/skills` | The plugin marketplace is easier: see the README. |

**Tools without skills** (`aider`, `amazonq`, `continue`, `jules`) get the skills in the shared folder plus a small instructions file in a project you name with `--project DIR` that tells the agent to read `rampwise/SKILL.md` first. The installer only writes between `<!-- rampwise:begin -->` and `<!-- rampwise:end -->` markers and never edits your other text. `--tool all` skips these four unless you pass `--project`.

**Subagents** (`agents/*.md`) are a Claude Code feature and are only installed for `claude-code`. The skills work on their own everywhere else.

## Official pages read (2026-11-17)
- Standard: [agentskills.io specification and client guide](https://agentskills.io/specification.md), [adding skills support](https://agentskills.io/client-implementation/adding-skills-support)
- Codex: [skills](https://developers.openai.com/codex/skills.md), [AGENTS.md](https://developers.openai.com/codex/guides/agents-md)
- Gemini CLI: [skills](https://geminicli.com/docs/cli/skills/), [GEMINI.md](https://geminicli.com/docs/cli/gemini-md/) · Antigravity: [skills](https://antigravity.google/docs/skills), [rules](https://antigravity.google/docs/rules)
- Cursor: [skills](https://cursor.com/docs/skills), [rules](https://cursor.com/docs/context/rules) · GitHub Copilot: [about agent skills](https://docs.github.com/en/copilot/concepts/agents/about-agent-skills)
- Windsurf / Devin: [Windsurf skills](https://docs.windsurf.com/windsurf/cascade/skills), [Devin CLI skills](https://docs.devin.ai/cli/extensibility/skills.md), [Devin skills guide](https://docs.devin.ai/product-guides/skills)
- Aider: [conventions](https://aider.chat/docs/usage/conventions.html), [config file](https://aider.chat/docs/config/aider_conf.html) · Cline: [skills](https://docs.cline.bot/customization/skills.md), [rules](https://docs.cline.bot/customization/cline-rules)
- OpenCode: [skills](https://opencode.ai/docs/skills), [rules](https://opencode.ai/docs/rules) · Kilo Code: [skills](https://kilo.ai/docs/customize/skills) · Roo Code: [skills](https://roocodeinc.github.io/Roo-Code/features/skills)
- Goose: [skills](https://goose-docs.ai/docs/guides/context-engineering/using-skills) · Continue: [rules](https://docs.continue.dev/customize/rules) · Zed: [skills](https://zed.dev/docs/ai/skills), [instructions](https://zed.dev/docs/ai/instructions)
- Amp: [agent skills](https://ampcode.com/manual/agent-skills.md) · Jules: [getting started](https://jules.google/docs) · Augment: [CLI skills](https://docs.augmentcode.com/cli/skills.md)
- Kiro: [skills](https://kiro.dev/docs/skills/) · Mistral Vibe: [skills](https://docs.mistral.ai/vibe/code/cli/skills.md) · GitLab Duo: [agent skills](https://docs.gitlab.com/user/duo_agent_platform/customize/agent_skills/)
- Qwen Code: [skills](https://qwenlm.github.io/qwen-code-docs/en/users/features/skills/) · Warp: [skills](https://docs.warp.dev/agents/capabilities/skills/) · Junie: [agent skills](https://junie.jetbrains.com/docs/agent-skills.html) · Factory: [skills](https://docs.factory.com/cli/configuration/skills)
- Hermes Agent: [skills](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills) · OpenClaw: [skills](https://docs.openclaw.ai/tools/skills.md) · Amazon Q Developer: [project rules](https://docs.aws.amazon.com/amazonq/latest/qdeveloper-ug/context-project-rules.html)

Some pages were read through a model summary of long pages; where a page did not state a path (for example Windows paths for most tools) the installer uses the home-folder form and this document says "not stated" rather than guessing.

## Security
A skill can run scripts. Read what you install: Rampwise's scripts are in `skills/*/scripts`, are plain Python, talk only to your local Garmin server, and ask before any network call that is not Garmin (the weather lookup).
