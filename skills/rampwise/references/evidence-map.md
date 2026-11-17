# Evidence map: rampwise (head coach)

The specialists keep their own evidence maps. This page covers what the head coach adds: race preparation, taper, race prediction, and the rules for combining signals.
Source names refer to `library.md` in this folder. Strength: **research** / **practice** / **gap**.

| Rule or output | What the source says (verified) | Strength | Notes |
|---|---|---|---|
| Taper before a goal event | Bosquet 2007 (meta-analysis, 27 of 182 studies, competitive athletes; abstract): best strategy was a 2-week taper with training volume reduced exponentially by 41-60 %; intensity and frequency changes were the other variables analysed. | research (meta-analysis; mostly shorter events) | Ultra cycling tapers are not studied here |
| Marathon preparation volume and the longest run | Fokkema 2020 (full text, 997 recreational (half-)marathoners): higher weekly volume and long endurance runs associated with faster finish and not with more injuries; details by distance in the paper. Muniz-Pumares 2025 (151,813 marathons, abstract): faster runners trained over three times more volume, mainly more easy running; pyramidal distribution most common. | research (observational) | Association, not a prescription |
| Marathon time prediction | Vickers and Vertosick 2016 (full text; 2,303 recreational runners): the Riegel formula was well calibrated up to the half marathon but "dramatically underestimated marathon time", at least 10 min too fast for half of runners; two models using one or two prior races plus weekly training reduced the error (mean squared error 381 for Riegel vs 228 and 208). | research (survey-based prediction study) | `scripts/paces.py predict` prints Riegel with this caveat and a Vickers estimate. The Tanda model in `paces.py` is cited by the upstream repo and was **not verified** here |
| Pace zones from % of threshold | `paces.py` default zone ratios come from a coaching model (Fitzgerald 80/20; TrainingPeaks) | practice | Not used by the skills unless the athlete asks |
| Combining signals into one verdict (precedence list in `SKILL.md`) | No study defines this. It follows the specialist evidence maps and the principle that the more conservative signal wins for the next session. | practice | Say so when asked |
| Ultra-distance ride build-up (200+ km) | No study in this library on training or tapering for ultra-distance cycling. Fueling evidence is in `rampwise-fueling`; durability concepts in `rampwise-aerobic-base`. | gap | Use long-ride duration progression with recovery data; do not invent an ultra plan from running rules |

## Not supported (do not claim)
- A taper length or volume cut for ultra cycling.
- That a predicted marathon time is reliable without recent long runs and weekly volume (use the slowest credible estimate).
- That the precedence rules are research-derived.

## Full-text reading notes (read in full 2026-11-18)
What the full texts add to the rows above: sample, effect, and the limits the authors state. Where a row above says more than this, this section wins.

- **Fokkema 2020 (Scand J Med Sci Sports; full text read).** Questionnaires before and after the event: 556 half-marathon and 441 marathon recreational runners, training and injuries self-reported. In the half marathon >32 km/week (beta -4.19, 95 % CI -6.52 to -1.85) and a longest run >21 km went with faster finishes; in the marathon <40 km/week went with slower (beta 6.33) and >65 km/week with faster finishes (beta -14.09), and a longest run <25 km with slower (beta 13.44); no association with injuries was found. Limits: self-report; 14.7 % of the half-marathon group also ran the marathon; many runners were excluded and the excluded were younger, heavier and less experienced (groups with higher injury risk), which may bias the injury result; speed ("talent") may confound; low-volume high-intensity plans were not tested. **So:** "no association found" is not proof that high volume is safe; the long-run and volume caps in the plans stay practice informed by this study.
- **Vickers 2016 (BMC Sports Sci Med Rehabil; full text read).** Internet survey of 2,303 recreational runners (younger and faster than a big-city marathon field); the Riegel formula was well calibrated up to the half marathon but gave marathon times at least 10 minutes too fast for half of the runners; mean squared error 381 for Riegel against 228 (model using one prior race) and 208 (two prior races). Few older runners (21 marathon runners over 60). **So:** use the model built on prior races for marathon estimates and say the estimate is uncertain, especially for older runners.
