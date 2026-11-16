# Report design notes

Choices made for `charts.py` and `report.py`, so that changes stay consistent.

- **Form follows the question.** Change over time = line; amounts per period = columns (stacked by sport); distance to a goal = meter; consistency = calendar heatmap. No pie charts, no dual axes (two measures = two charts).
- **Colour = sport, always.** Run `--s1` blue, ride `--s2` orange, strength `--s3` green, anything neutral (planned minutes, HRV, sleep) grey or a series colour only when it belongs to a sport. The same sport never changes colour between charts. Status colours (good, warning, critical) are used only for flag labels and always come with text.
- **Light and dark** are separate palettes (tokens in `charts.TOKENS` and `report.HTML_CSS`), not an inversion. The Markdown figures embed the tokens, so each SVG renders on its own.
- **No JavaScript, no network.** Period buttons are radio inputs and labels; tooltips are native `<title>` elements; sections are `<details>`; printing shows every period.
- **Axes:** small counts (sessions) use whole-number ticks; pace is plotted inverted (faster at the top) with m:ss labels; the heart-rate-variability chart shades the user's own normal band.
- **Honest scales:** columns start at zero; lines are scaled to the data and say so by their labelled ticks; line charts leave gaps where data are missing instead of drawing zeros.
- **Accessibility:** every SVG has a title and a text description; the Markdown report carries the comparisons in tables; interactive controls are keyboard-focusable.
- **Privacy:** reports contain the user's health data and stay in `$RAMPWISE_DATA/reports`. They are never part of the plugin, never committed, and are shared only if the user chooses.
