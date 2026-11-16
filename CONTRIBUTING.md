# Contributing

Thank you. This project's value is that every rule is traceable, so contributions are judged on evidence and honesty first.

## Licence of contributions
By submitting a contribution you agree it is licensed under the Apache License 2.0 (section 5 of the licence), like the rest of the project.

## Ground rules
1. **No personal data.** No `athlete.json`, plans, `.fit` files, activity ids, names, locations, API keys or screenshots of your health data. `python tests/check_repo.py` scans for common leaks; add your own tokens to a local, git-ignored `.privacy-tokens` file (one per line).
2. **Evidence labels.** A new rule gets a row in the skill's `references/evidence-map.md` with *research*, *practice* or *gap*, the paper (authors, year, what the abstract or text actually says) and the limits. Only cite a paper you read. Add it to the skill's `references/library.md` (PMID, DOI, status). Do not commit paper full texts (licences differ); `tools/fetch_papers.py` downloads open-access ones locally.
3. **Ask, never assume.** New features that need user data must ask, record the answer in `athlete.json`, and have a documented fallback that is labelled an estimate.
4. **Adaptive, not personal.** Locks and limits come from the user's own data. Nothing may be hard-wired to one person.
5. **Safety wording** stays: pain is a stop sign; not medical advice.

## Add a strength goal or exercise
Edit `skills/rampwise-strength/references/goal_profiles.json` or `exercise_library.json` (plain JSON), list the evidence in the profile's `basis` lines (research vs practice), run the checks, open a pull request.

## Checks
```text
python tests/check_repo.py
python tests/test_offline.py
```
Both run without a Garmin account. CI runs them on Linux and Windows.

## Releases
Bump the version in `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` and `plugin.json` (and add a CHANGELOG entry). Claude Code updates a plugin only when its version changes.
