# Evidence map: garmin-adapt

"Verified" = the abstract or full text was read (see `../../garmin-analyze/references/library.md` and the other skills' libraries). Strength: **research** = trial, cohort, meta-analysis; **practice** = convention without a study in this library; **gap** = unsupported.
The decision rules are in `scripts/adapt_logic.py`. The honest summary: the direction (back off when recovery is low or risk flags are up; add load slowly and rarely) is conventional coaching practice with some supporting signals; the exact numbers are defaults, not findings.

| Rule | What the source says (verified) | Strength | Notes |
|---|---|---|---|
| Readiness RED: rest or 20-30 minute easy spin; no quality, no heavy lower-body strength | Signals: Buchheit 2014 (full text) on judging heart-rate-based measures against the athlete's own baseline; Craven 2022 (meta-analysis) on sleep loss lowering performance. The action ("rest or spin") is the plan's standing rule. | research for the signals, **practice** for the action | No paper read shows that backing off on a RED morning prevents injury or improves results. |
| Readiness AMBER or injury watch AMBER: quality becomes easy (x0.9); long session x0.85 | Same signals. | practice | Easy volume continues, in line with most training being easy (Seiler 2010, `garmin-aerobic-base`). |
| Injury watch RED: reduce to x0.7 | The watch's flags and their labels: `../../garmin-analyze/references/evidence-map.md`. | mixed (see that map) | |
| Active injury or a pain check-in that says stop: rest | The user's own record. Pain-monitoring idea: Silbernagel 2007 (abstract; RCT in 38 patients with Achilles tendinopathy; no significant difference from active rest and no negative effects). | the principle of monitoring pain is **research** (small, one tendon); the stop thresholds are **practice** | Medical advice always wins. |
| Short sleep: strength at half sets | Craven 2022: sleep loss mostly impaired afternoon and evening tasks. | practice | |
| Long sessions capped at +10 % over the longest in the last 30 days | Frandsen 2025 (full text in `garmin-load-injury`): injury rate was higher after a single run more than 10 % longer than the recent longest. | research (observational) for running; **gap** (extrapolation) for rides | |
| Progress only when readiness and the watch are GREEN, at least 85 % of the last 14 days of plan done, week change 10 % or less, at least 7 days since the last progression, BUILD week | No study gives these numbers. Context: a graded 10 % weekly plan did not reduce injuries in novices (Buist 2008, abstract); mixed association for weekly jumps (Nielsen 2014, Damsted 2019). | practice | Deliberately conservative: one small step, rarely. |
| Step sizes: +5 min tempo block, +1 repeat up to 6, +5 min (run) or +10 min (ride) on long sessions | None. | practice | |
| Later days are provisional | Tomorrow's readiness is not known today. | n/a | Re-run each morning. |

## Not supported (do not claim)
- That an adapted plan makes the user faster or injury-free. No evidence read shows that for this kind of rule set.
- A timeline or rate of improvement for any goal.
- That the thresholds fit everyone: they are defaults to be tuned with the user's own history.
