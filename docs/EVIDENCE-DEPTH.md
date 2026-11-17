# How deeply each paper was read

Reading only an abstract can hide the sample, the effect size and the limits. This page says, per paper, what was actually read, so a rule is never stronger than its reading.

- **Full text read**: the whole paper was read; the evidence map can quote sample sizes, effects and limits.
- **Abstract only**: only the abstract was read (the paper is paywalled, or the free record returned no text). The evidence map then says so and claims no more than the abstract does.
- **Getting more**: open-access papers can be fetched in full on demand (`skills/rampwise/scripts/paper_fetch.py "Author year"`, which the coach runs when it needs the detail). Paywalled papers cannot be fetched legally: put your own PDF in the skill's `references/papers/` folder and ask the coach to read it.

| Paper | Used for | Read |
|---|---|---|
| Frandsen 2025 (BJSM, 5,205 runners) | the 10 % single-run rule | **full text read 2026-11-17** (sample, counts, limits now in the maps) |
| Fokkema 2020, Buchheit 2014, Craven 2022 | volume, readiness, sleep | **full text read 2026-11-17** |
| Stoggl 2014, Schumann 2022, Eddens 2018, Blagrove 2018, Vickers 2016 | intensity distribution, strength, race prediction | **full text read 2026-11-17** |
| Gabbett 2016 | load paradox | full text (open access; read earlier) |
| Walsh 2019 (Sports) | brick runs, cadence, run pacing, leg-pain history | **full text read 2026-11-17** |
| Bosquet 2007 (taper meta-analysis) | 2-week taper | abstract only (paywalled): effect size and how studies were pooled not read |
| Munoz 2014, Neal 2011 (Ironman intensity distribution) | about 70-80 % easy | abstract only (paywalled) |
| Figueiredo 2016 (swim/bike/run contribution) | swim share | abstract only (paywalled) |
| Andersen 2013 (Ironman overuse injuries) | injury burden | abstract only (paywalled) |
| Johnston 2018, von Rosen 2017, Silbernagel 2007 | injury-watch flags | abstract only (paywalled) |
| Nielsen 2014, Damsted 2018 and 2019, Buist 2008, Impellizzeri 2020 | week-to-week volume rules | abstract only (paywalled or no text returned) |
| Millet and Vleck 2000, Berry 2016 | cycle-run transition, duathlon | abstract only (the free record returned no text) |

## Where the paper files are
Every paper in a skill's `references/library.md` has a local file in that skill's `references/papers/` folder, and `references/papers/INDEX.md` lists each file with its **read depth**. They are built by `python tools/build_paper_files.py` (full text for open-access papers, the abstract with the full citation for the rest). The files stay on your computer: they are not part of the public repository because licences differ. After installing from the repository run the tool once to build your own copy; the coach then opens the file before quoting a paper.

## How to close the gaps
Paywalled papers cannot be fetched legally by the tool. If you have access (a library, an institution, or the authors' own copy), put the PDFs in a folder, tell the coach where it is, and it will read them in full and update the evidence maps with what the papers actually say (sample, effect size, limits). Priority order: the injury-related papers first (Andersen 2013, Johnston 2018, Nielsen 2014, Damsted 2019, Buist 2008, Silbernagel 2007, von Rosen 2017), then Bosquet 2007 and the Ironman intensity papers.
Full texts stay on your computer: some of these papers forbid redistribution, so they are never added to the public repository.
