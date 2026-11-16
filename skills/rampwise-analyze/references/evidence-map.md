# Evidence map: rampwise-analyze

"Verified" = the abstract or full text was read (see `library.md`). Strength: **research** = trial, cohort, meta-analysis or systematic review; **practice** = convention without a study in this library; **gap** = unsupported.
The thresholds live in `scripts/analysis.py`. This skill raises flags to look closer. It does not predict injuries: no paper read here gives a rule that predicts injury in one person.

| Rule used by `analysis.py` | What the source says (verified) | Strength | Notes |
|---|---|---|---|
| Single run more than 10 % longer than the longest run of the previous 30 days is a flag; red above 100 % | Frandsen 2025 (BJSM; 5,205 runners, Garmin data): higher injury rate after such sessions, rising with the size of the jump. Full text in `rampwise-load-injury`. | research (observational cohort) | The red/amber colours are practice. Applies to running only. |
| Week-over-week run + ride minutes up 20 % or more is an amber flag | Nielsen 2014 and Damsted 2019: some association at some horizons, not all; Buist 2008 RCT: a graded 10 % plan did not reduce injuries. Maps in `rampwise-load-injury`. | practice with mixed support | A prompt, not a verdict. Ignored on a base under 60 minutes. |
| Rest days: 7 amber, 14 red | No study in this library. | practice | |
| Two hard days in a row (Garmin aerobic training effect 4.0 or more) | Garmin's own scale; no study. | practice | |
| Recovery AMBER or RED adds a flag | Buchheit 2014 (full text): judge heart-rate based measures against the athlete's own baseline; Craven 2022 (meta-analysis): sleep loss lowers performance. | research for the signals; **gap** for "low recovery causes injury" | |
| Last 3 nights under 6 h average | von Rosen 2017 (abstract; 340 adolescent elite athletes, questionnaire): more than 8 h of sleep on weekdays went with 61 % lower odds of injury (OR 0.39, 95 % CI 0.16 to 0.99); poor diet was also a factor. | limited research (adolescents, self-report); adults: **gap** | The 6 h line is practice (also used by `rampwise-recovery`). |
| Run efficiency (speed per heartbeat) down 5 % or more against the 4 weeks before | The concept appears in Buchheit 2014; the 5 % line is not from a paper. | practice | Heat, hills, illness and wrist-heart-rate error move it. Needs 3 steady runs of 25 minutes or more in each window. |
| Recently resolved injury (60 days) is noted | Johnston 2018 (abstract; systematic review of 12 endurance-sport studies: running, triathlon, rowing): a history of previous injury was associated with a higher rate of injury or pain (medium effect). The same review linked high total weekly or monthly distance, and fewer than 2 sessions a week, to higher risk (medium effects). | research (systematic review) | The 60-day window is practice. Information only. |
| Pain check-in: 3 amber, 6 red, a change in gait always red | Silbernagel 2007 (abstract; RCT, 38 patients with Achilles tendinopathy): continued running and jumping inside a pain-monitoring model showed no significant difference in recovery from stopping them, and no negative effects were demonstrated. | research for the idea of monitoring pain; the numeric thresholds here are **practice** | Rehab population, one tendon. Not a rule for healthy runners. |
| Active or monitored injury in `athlete.json` | The user's own record. | n/a | The restriction written by the user or a clinician always wins. |
| Week-over-week comparison itself | Arithmetic on the user's own data. | n/a | Pace and speed depend on route, weather and easy/hard mix; the output says so. |

## Not supported (do not claim)
- That any flag predicts an injury in this person. They are associations from groups.
- That staying under 10 % per week prevents injury (Buist 2008 found no effect).
- That watch data detects tendon, bone or joint problems. Only the user can report pain.
- That a low heart-rate variability or short sleep "causes" an injury: no paper read shows that in adults.
- Cycling rules: no study here tests a spike rule for rides.
