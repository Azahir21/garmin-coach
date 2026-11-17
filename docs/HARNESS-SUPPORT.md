# Harness support

| Harness | How to install | Status |
|---|---|---|
| Claude Code | `/plugin marketplace add Azahir21/rampwise` | Built for and used with it. `claude plugin validate` was not available in the build environment; the manifests follow Anthropic's documented schema |
| Codex (OpenAI) | `codex plugin marketplace add Azahir21/rampwise` | Manifests follow OpenAI's plugin docs as read on 2026-11-16 (portable `plugin.json`, `.agents/plugins/marketplace.json`). **Not tested.** Skills only: Codex plugins do not ship subagents |
| 29 other AI coding tools (Codex, Gemini CLI, Antigravity, Cursor, Copilot, Windsurf, Cline, OpenCode, Devin, Kilo, Goose, Zed, Amp, Augment, Kiro, Vibe, GitLab Duo, Qwen Code, Warp, Junie, Factory, Hermes, OpenClaw, Trae, Roo and more) | `python install.py --tool <name>` (see `--list`) | Skills follow the open Agent Skills layout (name = folder, description under 1024 characters, SKILL.md under 500 lines). Folders per tool come from each tool's official documentation read on 2026-11-17: see [INSTALL.md](INSTALL.md). Not tested outside Claude Code |

Things that differ between harnesses:
- **Script paths.** Skill instructions say `<skills>/<skill>/scripts/...`; the agent resolves `<skills>` from where the skills were installed.
- **Subagents** (`agents/*.md`) are Claude Code prompts. Other harnesses can run the same steps in the main session.
- **Calendar and browser tools** are optional connectors; without them the plan is printed instead of written.
- **Auto-update** differs: see README.

If you test on another harness, please open an issue with what worked and what did not.
