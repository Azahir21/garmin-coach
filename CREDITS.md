# Credits and licences

This project stands on other people's work. Thank you.

## Code and services
| What | By | Licence | How it is used |
|---|---|---|---|
| [running-coach](https://github.com/tomasstankovic/running-coach) | Tomas Stankovic | MIT (kept as is; compatible with Apache-2.0) | `readiness.py`, `weather.py` and `paces.py` are unmodified copies (commit and licence in `skills/rampwise/third_party/`); the activity-analysis formulas in `analyze_activity.py` are adapted from it |
| [garmin-personal-mcp](https://github.com/Mason-Levyy/garmin-personal-mcp) | Mason Levy | MIT | The MCP server that reads your data from Garmin's official Personal API; started by the scripts and by `.mcp.json` |
| [fitdecode](https://github.com/polyvertex/fitdecode) | Jean-Charles Lefebvre | MIT | Reads Garmin FIT files; its bundled FIT profile was used to check the workout-file encoder |
| Garmin FIT file format | Garmin Ltd. | Garmin FIT SDK terms | The workout writer follows the published format and Garmin's "Workout Files" article; verified only by decoding our own files, not on every watch |
| [Open-Meteo](https://open-meteo.com) | Open-Meteo.com | Data CC BY 4.0; free API for non-commercial use | Optional weather lookups (heat adjustment); attribution required, commercial use needs their licence |
| [USDA FoodData Central](https://fdc.nal.usda.gov) (SR Legacy) | U.S. Department of Agriculture | Public domain (CC0) | Nutrient values per 100 g in `skills/rampwise-fueling/data/foods.json`, each food with its USDA ID; built by `tools/build_foods.py` |
| [Europe PMC](https://europepmc.org) | EMBL-EBI | Open access API | Literature search and open-access full texts used to build the evidence maps |
| Agent Skills format | Anthropic and community ([agentskills.io](https://agentskills.io)) | Open standard | The skills follow the `SKILL.md` layout so several agent harnesses can load them |

## Research
The rules in the evidence maps come from the papers listed in [docs/PAPERS.md](docs/PAPERS.md) (generated from each skill's `references/library.md`). Authors keep their copyright. Open-access full texts were read for the build but are **not redistributed** here: some carry non-commercial or no-derivative licences. Run `tools/fetch_papers.py` to download open-access texts for your own reading. Please cite the original papers, not this repository.

Special thanks to the authors of the studies behind the heart-rate, strength, load, heat and recovery rules, including (not exhaustively) Seiler, Buchheit, Maffetone and Laursen, Stoggl and Sperlich, Blagrove, Berryman, Ronnestad and Mujika, Schumann, Haugen, Seitz, Lopez, Lu and colleagues, Heiber and colleagues, Craven, Jeukendrup, Frandsen and Buist.

## People
See the git history for contributors. If you used this and it helped (or hurt), please tell us in an issue.
