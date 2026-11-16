# Evidence map: rampwise-load-injury

Source names refer to `library.md` in this folder. "Verified" = read in the abstract or full text (2026-11-16).
Strength: **research** = trial/cohort/meta-analysis/consensus; **practice** = convention without a study in this library; **gap** = unsupported.

| Rule used by `load_check.py` | What the source says (verified) | Strength | Notes |
|---|---|---|---|
| No single run more than 10 % longer than the longest run of the last 30 days | Frandsen 2025 (BJSM; 5,205 adult runners, 18-month cohort, 588,071 sessions, distance data from Garmin devices; 1,820 injuries): relative to up to 10 % increase, injury rates were higher for small spikes >10-30 % (HRR 1.64, 95 % CI 1.31-2.05), moderate >30-100 % (HRR 1.52, 1.16-2.00) and large >100 % (HRR 2.28, 1.50-3.48) in single-session distance. Conclusion: higher rate of overuse injury when a session exceeded 10 % of the longest run in the last 30 days. Week-to-week ratio: no relationship; ACWR: negative dose-response. Self-reported injuries. | research (large observational) | Full text in `papers/` (CC BY-NC). Association, not proof of cause; adults mostly 45 +/- 10 y |
| Weekly distance jumps above ~30 % are a caution | Nielsen 2014 (874 novice runners, 1 year, GPS): rates did not differ significantly across groups (<10 %, 10-30 %, >30 %); distance-related injuries were more frequent with >30 % (HR 1.59, 95 % CI 0.96-2.66, P=.07). Damsted 2019 (261 runners, 14 weeks, half-marathon preparation): at 21 days more runners were injured after 20-60 % weekly increases (risk difference 22.6 %, 95 % CI 0.9-44.3 %), no significant difference after 56 and 98 days. Damsted 2018 (systematic review, 4 articles): "very limited evidence" that sudden load change is associated with injury. | research (observational; limited) | Used as NOTE only |
| A graded "10 % rule" plan is not proven protective | Buist 2008 (RCT, 532 novice runners, 13-week graded programme based on the 10 % rule vs 8-week standard): injury incidence 20.8 % vs 20.3 %, no effect. | research (RCT, novices) | Why weekly 10 % is not enforced |
| Do not use ACWR as a pass/fail | Impellizzeri 2020 (critical review): no evidence supporting ACWR for training-load management or recommendations aimed at lowering injury risk; statistical problems of ratios. Gabbett 2016 (full text) promotes ACWR as a best-practice monitoring variable in team sport; this disagreement is real. Frandsen 2025 found no positive association for ACWR in runners. | research (contested) | Script does not compute ACWR |
| Training load is not simply harmful | Gabbett 2016: "training-injury prevention paradox": athletes accustomed to high loads have fewer injuries; excessive and rapid increases likely cause many non-contact soft-tissue injuries; under-training may also raise risk. | research (conceptual model + evidence summary) | Basis for gradual progression, not for avoiding load |
| IOC guidance on load | Soligard 2016 (IOC consensus, abstract): poor load management is a major risk factor; rapid changes in training load, competition congestion, psychological load and travel are all load; guidelines for prescription and monitoring. | research (consensus) | Abstract only; no numbers used |
| Marathon preparation volume | Fokkema 2020 (full text; 556 half-marathon and 441 marathon participants): higher weekly volume and long endurance runs went with faster finish times and were not related to higher injury risk; details by distance in the paper. | research (observational) | Do not use to justify spikes |
| Rest day every week; no long streaks | No study in this library. | practice | Script flags 7 days without rest |
| Hard days not back to back (Garmin aerobic training effect >= 4.0) | No study in this library; the training-effect scale is Garmin's own. | practice | |
| Cycling: same 10 % arithmetic | No study found for cyclists. | gap (extrapolation, labelled) | Ultra build-up needs longer rides |

## Not supported (do not claim)
- That staying under 10 % per week prevents injury (the RCT found no effect).
- A pass/fail ACWR band.
- Any numeric rule for rides, for strength, or for double sessions.
- That the numbers apply to injury types other than running-related overuse in the studied populations (adult recreational, novice or mixed).
