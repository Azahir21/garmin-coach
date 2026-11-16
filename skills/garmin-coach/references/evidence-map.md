# Evidence map: garmin-coach (head coach)

The specialists keep their own evidence maps. This page covers what the head coach adds: race preparation, taper, race prediction, and the rules for combining signals.
Source names refer to `library.md` in this folder. Strength: **research** / **practice** / **gap**.

| Rule or output | What the source says (verified) | Strength | Notes |
|---|---|---|---|
| Taper before a goal event | Bosquet 2007 (meta-analysis, 27 of 182 studies, competitive athletes; abstract): best strategy was a 2-week taper with training volume reduced exponentially by 41-60 %; intensity and frequency changes were the other variables analysed. | research (meta-analysis; mostly shorter events) | Ultra cycling tapers are not studied here |
| Marathon preparation volume and the longest run | Fokkema 2020 (full text, 997 recreational (half-)marathoners): higher weekly volume and long endurance runs associated with faster finish and not with more injuries; details by distance in the paper. Muniz-Pumares 2025 (151,813 marathons, abstract): faster runners trained over three times more volume, mainly more easy running; pyramidal distribution most common. | research (observational) | Association, not a prescription |
| Marathon time prediction | Vickers and Vertosick 2016 (full text; 2,303 recreational runners): the Riegel formula was well calibrated up to the half marathon but "dramatically underestimated marathon time", at least 10 min too fast for half of runners; two models using one or two prior races plus weekly training reduced the error (mean squared error 381 for Riegel vs 228 and 208). | research (survey-based prediction study) | `scripts/paces.py predict` prints Riegel with this caveat and a Vickers estimate. The Tanda model in `paces.py` is cited by the upstream repo and was **not verified** here |
| Pace zones from % of threshold | `paces.py` default zone ratios come from a coaching model (Fitzgerald 80/20; TrainingPeaks) | practice | Not used by the skills unless the athlete asks |
| Combining signals into one verdict (precedence list in `SKILL.md`) | No study defines this. It follows the specialist evidence maps and the principle that the more conservative signal wins for the next session. | practice | Say so when asked |
| Ultra-distance ride build-up (200+ km) | No study in this library on training or tapering for ultra-distance cycling. Fueling evidence is in `garmin-fueling`; durability concepts in `garmin-aerobic-base`. | gap | Use long-ride duration progression with recovery data; do not invent an ultra plan from running rules |

## Not supported (do not claim)
- A taper length or volume cut for ultra cycling.
- That a predicted marathon time is reliable without recent long runs and weekly volume (use the slowest credible estimate).
- That the precedence rules are research-derived.
