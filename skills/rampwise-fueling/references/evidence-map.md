# Evidence map: rampwise-fueling

Source names refer to `library.md` in this folder. "Verified" = read in the abstract or full text (2026-11-16).
Strength: **research** = review/consensus/trial; **practice** = convention without a study in this library; **gap** = unsupported.

| Rule used by the scripts | What the source says (verified) | Strength | Notes |
|---|---|---|---|
| Duration tiers for carbohydrate | Jeukendrup 2014 (Sports Med; full text): about 1 h: mouth rinse or small amounts of carbohydrate can improve performance; ACSM guideline (cited in the paper): 30-60 g/h over 1 h; a single source oxidises up to about 60 g/h, recommended for 2-3 h; ultra-endurance: about 90 g/h, from multiple transportable carbohydrates; multiple-carb benefit seen mostly in studies of 2.5 h or longer. | research (review/guideline) | Basis of `fuel_plan.py` |
| Absolute g/h, not per kg | Same paper: no correlation between body weight and exogenous carbohydrate oxidation; limiting factor is absorption. | research | |
| Lower the amount at low absolute intensity | Same paper: "adjusted (downwards)"; no factor given; example of a 5-h marathoner who may not need 90 g/h. | research (qualitative) | No multiplier applied |
| Dose-response and the 60-80 g/h optimum | Same paper describes Smith et al.: 51 cyclists/triathletes, 2-h ride at moderate-high intensity then 20-km time trial, 12 glucose:fructose doses from 10-120 g/h; performance improved dose-dependently, greatest at 60-80 g/h. | research (multicentre trial, described in a review) | |
| Cap at 90 g/h | Podlogar and Wallis 2022 (narrative review; full text): recommended maximum up to 90 g/h; glucose+fructose mixtures advised above 2.5 h and 60-90 g/h; 120 g/h gave higher exogenous oxidation in highly trained athletes but performance benefit is unclear and "at present it cannot be recommended to alter the currently recommended maximal carbohydrate ingestion dose". | research (review) | Commercial pages quoting 100-120 g/h are not supported as a general recommendation |
| Practise the plan / gut training | Jeukendrup 2014: gut adaptation shown in animals and one human study (28 days of high carbohydrate intake raised exogenous oxidation); limited human evidence, but practising is "highly recommended". Jeukendrup 2017 (periodised nutrition review; full text): adaptations include better intestinal absorptive capacity and tolerance to dehydration; some methods well supported, others theory. | research (limited) | The +10 g/h per week ramp is **practice**, not from a paper |
| Fluid: customise; avoid > 2 % body-mass loss | ACSM position stand 2007 (abstract): goal of drinking is to prevent excessive (> 2 % body weight loss from water deficit) dehydration and excessive electrolyte change; individual sweat rates vary, so customised plans; sweat rate can be estimated from body weight before and after; electrolyte/carbohydrate drinks can help over water alone in some circumstances. | research (position stand) | Basis of `sweat_rate.py` |
| Solid food and concentrated drinks reduce fluid absorption | Jeukendrup 2014 (full text). | research (review) | |
| Late-session fade is not only fuel | Grivas 2026 (narrative review): wall/late collapse emerges from metabolic, thermoregulatory, dehydration, GI, neuromuscular, perceptual and pacing factors. Wang 2026: decoupling onset related to core-temperature rise and sodium loss per km; late decoupling related to glucose change (13 adolescent runners). | research (review + small study) | |
| General sports-nutrition framework | Thomas, Erdman and Burke 2016 (ACSM/AND/DC position, abstract only): performance and recovery enhanced by well-chosen nutrition; refer athletes to a registered dietitian for personalised plans. | research (position) | Basis for referral wording |
| Hyponatraemia and sodium guidance | Hew-Butler 2015 consensus statement is in PubMed **without an abstract** and no full text was available. | gap | No sodium numbers are given anywhere |

## Not supported (do not claim)
- Sodium or electrolyte targets (g/L, mg/h).
- 100-120 g/h as a general recommendation.
- A multiplier for low intensity.
- That the +10 g/h per week ramp is a studied protocol.
- Fuelling advice for low energy availability or medical conditions: refer.
