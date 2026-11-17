"""Dependency-free SVG charts for the reports (no matplotlib, no JavaScript, no network).

Every function returns an SVG string. `standalone=True` embeds the colour tokens (with a dark-mode media query) so the file renders well on its own,
for example as an image in a Markdown report; inline in the HTML report the page supplies the tokens. Hover text uses native <title> tooltips.
Sport colours are fixed everywhere: run = blue (--s1), bike = orange (--s2), strength = green (--s3), neutral = grey (--all).
"""
from html import escape

TOKENS = """:root{--ink:#0b0b0b;--ink2:#52514e;--muted:#898781;--grid:#e1e0d9;--axis:#c3c2b7;--s1:#2a78d6;--s2:#eb6834;--s3:#1baf7a;--s4:#7c5cd6;--all:#898781;--track:#cde2fb;--good:#0ca30c;--warn:#fab219;--crit:#d03b3b;--band:rgba(42,120,214,.12)}
@media (prefers-color-scheme:dark){:root{--ink:#f0efec;--ink2:#c3c2b7;--grid:#2c2c2a;--axis:#383835;--s1:#3987e5;--s2:#d95926;--s3:#199e70;--s4:#9b82e8;--track:#184f95;--band:rgba(57,135,229,.18)}}"""
CSS = """.t{font:12px system-ui,-apple-system,Segoe UI,sans-serif;fill:var(--ink2)}.tt{font:600 13px system-ui,-apple-system,Segoe UI,sans-serif;fill:var(--ink)}
.g{stroke:var(--grid);stroke-width:1}.a{stroke:var(--axis);stroke-width:1}.s1{fill:var(--s1);stroke:var(--s1)}.s2{fill:var(--s2);stroke:var(--s2)}.s3{fill:var(--s3);stroke:var(--s3)}.s4{fill:var(--s4);stroke:var(--s4)}.s0{fill:var(--all);stroke:var(--all)}
.l{fill:none;stroke-width:2.2;stroke-linejoin:round;stroke-linecap:round}.p{stroke:none}.band{fill:var(--band);stroke:none}.bar{stroke:none}.cell0{fill:var(--grid)}"""
MONTH = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _wrap(body, w, h, title, desc, standalone):
    style = f"<style>{TOKENS}{CSS}</style>" if standalone else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="100%" role="img" aria-label="{escape(title)}" preserveAspectRatio="xMidYMid meet">'
            f"<title>{escape(title)}</title><desc>{escape(desc)}</desc>{style}{body}</svg>")


def _nice_max(v):
    if v <= 0:
        return 1
    import math
    e = 10 ** math.floor(math.log10(v))
    for m in (1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10):
        if v <= m * e:
            return m * e
    return 10 * e


def _fmt(v, dec=0):
    return f"{v:.{dec}f}".rstrip("0").rstrip(".") if dec else f"{round(v)}"


def legend(items, x, y):
    out, cx = [], x
    for name, cls in items:
        out.append(f'<rect x="{cx}" y="{y - 9}" width="10" height="10" rx="2" class="{cls} bar"/><text x="{cx + 14}" y="{y}" class="t">{escape(name)}</text>')
        cx += 14 + 7 * len(name) + 14
    return "".join(out)


def bars(labels, series, title, unit="min", stacked=True, height=230, standalone=False, desc="", tick_every=None, dec=0):
    """Column chart. series = [(name, values, css_class)]. Stacked or grouped. Tooltips list every series."""
    W, H, L, R, T, B = 640, height, 44, 12, 34, 40
    n = len(labels)
    totals = [sum((s[1][i] or 0) for s in series) for i in range(n)] if stacked else [max((s[1][i] or 0) for s in series) for i in range(n)]
    ymax = _nice_max(max(totals + [1]))
    steps = 4
    if dec == 0 and max(totals + [1]) <= 6:      # small counts (sessions): whole-number ticks
        import math
        ymax = steps = max(1, math.ceil(max(totals + [1])))
    pw, ph = W - L - R, H - T - B
    slot = pw / max(n, 1)
    bw = min(34, slot * 0.7)
    body = [f'<text x="{L}" y="18" class="tt">{escape(title)}</text>', legend([(s[0], s[2]) for s in series], L + 0, H - 8)]
    for k in range(steps + 1):
        v = ymax * k / steps
        y = T + ph - ph * k / steps
        body.append(f'<line x1="{L}" x2="{W - R}" y1="{y:.1f}" y2="{y:.1f}" class="g"/><text x="{L - 6}" y="{y + 4:.1f}" class="t" text-anchor="end">{_fmt(v, dec if (ymax / steps) % 1 else 0)}</text>')
    body.append(f'<text x="{W - R}" y="18" class="t" text-anchor="end">{escape(unit)}</text>')
    every = tick_every or max(1, round(n / 8))
    for i, lab in enumerate(labels):
        cx = L + slot * i + slot / 2
        tip = escape(f"{lab}: " + ", ".join(f"{s[0]} {_fmt(s[1][i] or 0, dec)} {unit}" for s in series))
        if stacked:
            base = 0.0
            for name, vals, cls in series:
                v = vals[i] or 0
                if v <= 0:
                    continue
                h = ph * v / ymax
                y = T + ph - ph * (base + v) / ymax
                body.append(f'<rect x="{cx - bw / 2:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{max(h - 1, 0.5):.1f}" rx="2" class="{cls} bar"><title>{tip}</title></rect>')
                base += v
        else:
            gw = bw / len(series)
            for j, (name, vals, cls) in enumerate(series):
                v = vals[i] or 0
                h = ph * v / ymax
                body.append(f'<rect x="{cx - bw / 2 + j * gw:.1f}" y="{T + ph - h:.1f}" width="{gw - 1:.1f}" height="{max(h, 0.5):.1f}" rx="2" class="{cls} bar"><title>{tip}</title></rect>')
        if i % every == 0:
            body.append(f'<text x="{cx:.1f}" y="{T + ph + 16}" class="t" text-anchor="middle">{escape(str(lab))}</text>')
    body.append(f'<line x1="{L}" x2="{W - R}" y1="{T + ph}" y2="{T + ph}" class="a"/>')
    return _wrap("".join(body), W, H, title, desc or f"{title}: " + "; ".join(f"{lab} {_fmt(t)} {unit}" for lab, t in zip(labels, totals)), standalone)


def lines(labels, series, title, unit="", band=None, height=230, standalone=False, desc="", dec=0, invert=False, ymin=None, ymax=None, tick_every=None, fmt=None):
    """Line chart with gaps for missing values. series = [(name, values, css_class)]. band = (lo, hi) shaded range. invert=True puts smaller values at the top (pace)."""
    W, H, L, R, T, B = 640, height, 48, 12, 34, 40
    vals = [v for s in series for v in s[1] if v is not None] + ([band[0], band[1]] if band else [])
    if not vals:
        return _wrap(f'<text x="{L}" y="18" class="tt">{escape(title)}</text><text x="{L}" y="{H / 2}" class="t">No data in this period</text>', W, H, title, "no data", standalone)
    lo = min(vals) if ymin is None else ymin
    hi = max(vals) if ymax is None else ymax
    pad = (hi - lo) * 0.12 or max(abs(hi) * 0.05, 1)
    lo, hi = (lo - pad if ymin is None else lo), (hi + pad if ymax is None else hi)
    pw, ph = W - L - R, H - T - B
    n = len(labels)
    xs = [L + (pw * i / max(n - 1, 1)) for i in range(n)]

    def Y(v):
        f = (v - lo) / (hi - lo)
        return T + (ph * f if invert else ph - ph * f)
    body = [f'<text x="{L}" y="18" class="tt">{escape(title)}</text>', legend([(s[0], s[2]) for s in series], L, H - 8)]
    for k in range(5):
        v = lo + (hi - lo) * k / 4
        y = Y(v)
        label = fmt(v) if fmt else _fmt(v, dec)
        body.append(f'<line x1="{L}" x2="{W - R}" y1="{y:.1f}" y2="{y:.1f}" class="g"/><text x="{L - 6}" y="{y + 4:.1f}" class="t" text-anchor="end">{escape(label)}</text>')
    if unit:
        body.append(f'<text x="{W - R}" y="18" class="t" text-anchor="end">{escape(unit)}</text>')
    if band:
        y1, y2 = sorted((Y(band[0]), Y(band[1])))
        body.append(f'<rect x="{L}" y="{y1:.1f}" width="{pw}" height="{y2 - y1:.1f}" class="band"><title>normal band {_fmt(band[0], dec)} to {_fmt(band[1], dec)}</title></rect>')
    every = tick_every or max(1, round(n / 8))
    for i, lab in enumerate(labels):
        if i % every == 0 or i == n - 1 and (n - 1) % every >= every / 2:
            anchor = "end" if i == n - 1 else "start" if i == 0 else "middle"
            body.append(f'<text x="{xs[i]:.1f}" y="{T + ph + 16}" class="t" text-anchor="{anchor}">{escape(str(lab))}</text>')
    for name, v, cls in series:
        seg = []
        for i, val in enumerate(v):
            if val is None:
                if len(seg) > 1:
                    body.append(f'<polyline class="l {cls}" points="{" ".join(seg)}"/>')
                seg = []
                continue
            seg.append(f"{xs[i]:.1f},{Y(val):.1f}")
        if len(seg) > 1:
            body.append(f'<polyline class="l {cls}" points="{" ".join(seg)}"/>')
        for i, val in enumerate(v):
            if val is not None:
                shown = fmt(val) if fmt else _fmt(val, dec)
                body.append(f'<circle cx="{xs[i]:.1f}" cy="{Y(val):.1f}" r="3.2" class="{cls} p"><title>{escape(f"{labels[i]}: {name} {shown} {unit}".strip())}</title></circle>')
    body.append(f'<line x1="{L}" x2="{W - R}" y1="{T + ph}" y2="{T + ph}" class="a"/>')
    return _wrap("".join(body), W, H, title, desc or f"{title}: " + "; ".join(f"{s[0]} from {next((x for x in s[1] if x is not None), '-')} to {next((x for x in reversed(s[1]) if x is not None), '-')}" for s in series), standalone)


def meter(label, baseline, now, target, fmt, better="higher", note="", standalone=False):
    """Goal meter: a track from the baseline (first reading) to the target, a marker for now. A distance to the goal, never a prediction."""
    W, H, L, R = 640, 86, 12, 12
    pw = W - L - R
    title = f"{label}: now {fmt(now) if now is not None else 'no reading'}, target {fmt(target) if target is not None else 'not set'}"
    if now is None or baseline is None or target is None or baseline == target:
        why = "No reading in this period" if now is None or baseline is None else "Target equals the starting value"
        body = (f'<text x="{L}" y="18" class="tt">{escape(label)}</text><text x="{W - R}" y="18" class="t" text-anchor="end">{escape(note)}</text>'
                f'<text x="{L}" y="48" class="t">{escape(why)} (target {escape(fmt(target) if target is not None else "not set")})</text>')
        return _wrap(body, W, H, title, title, standalone)
    span = (target - baseline) if better == "higher" else (baseline - target)
    got = (now - baseline) if better == "higher" else (baseline - now)
    frac = max(0.0, min(1.0, got / span)) if span else 0
    x = L + pw * frac
    anchor = "start" if frac < 0.15 else "end" if frac > 0.85 else "middle"
    nx = x - 8 if anchor == "start" and frac < 0.02 else x
    nx = L if anchor == "start" else (W - R if anchor == "end" else x)
    behind = " (behind the starting value)" if got < 0 else ""
    body = [f'<text x="{L}" y="16" class="tt">{escape(label)}</text>', f'<text x="{W - R}" y="16" class="t" text-anchor="end">{escape(note)}</text>',
            f'<text x="{nx:.1f}" y="36" class="tt" text-anchor="{anchor}">now {escape(fmt(now))}{behind}</text>',
            f'<rect x="{L}" y="46" width="{pw}" height="12" rx="6" fill="var(--track)"/>', f'<rect x="{L}" y="46" width="{max(pw * frac, 0):.1f}" height="12" rx="6" class="s1 bar"><title>{escape(title)}</title></rect>',
            f'<circle cx="{x:.1f}" cy="52" r="8" fill="var(--ink)" opacity=".9"/><circle cx="{x:.1f}" cy="52" r="4" class="s1 p"/>',
            f'<text x="{L}" y="78" class="t">start {escape(fmt(baseline))}</text><text x="{W - R}" y="78" class="t" text-anchor="end">target {escape(fmt(target))}</text>']
    return _wrap("".join(body), W, H, title, f"{title}; start {fmt(baseline)}; {frac * 100:.0f} % of the way", standalone)


def heatmap(days, minutes, title, standalone=False, weeks=12):
    """Training calendar: columns = weeks (oldest left), rows = Monday..Sunday, colour depth = minutes that day."""
    from datetime import date, timedelta
    W, L, T = 640, 40, 34
    cell, gap = 18, 3
    end = max(days)
    ws_end = end - timedelta(days=end.weekday())
    start = ws_end - timedelta(weeks=weeks - 1)
    by = {d: m for d, m in zip(days, minutes)}
    mx = max([m for m in minutes] + [1])
    H = T + 7 * (cell + gap) + 30
    body = [f'<text x="{L}" y="18" class="tt">{escape(title)}</text>']
    for r, name in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]):
        body.append(f'<text x="{L - 6}" y="{T + r * (cell + gap) + 13}" class="t" text-anchor="end">{name}</text>')
    for c in range(weeks):
        wk_start = start + timedelta(weeks=c)
        if c % 2 == 0:
            body.append(f'<text x="{L + c * (cell + gap)}" y="{T + 7 * (cell + gap) + 14}" class="t">{wk_start.day} {MONTH[wk_start.month - 1]}</text>')
        for r in range(7):
            d = wk_start + timedelta(days=r)
            if d > end:
                continue
            m = by.get(d, 0)
            op = 0 if m <= 0 else 0.25 + 0.75 * min(m / mx, 1)
            cls = "cell0" if m <= 0 else "s1"
            body.append(f'<rect x="{L + c * (cell + gap)}" y="{T + r * (cell + gap)}" width="{cell}" height="{cell}" rx="3" class="{cls} bar" ' + (f'fill-opacity="{op:.2f}"' if m > 0 else "") + f'><title>{d}: {round(m)} min</title></rect>')
    return _wrap("".join(body), W, H, title, f"{title}: {sum(1 for m in minutes if m > 0)} training days in {weeks} weeks", standalone)


def spark(values, w=120, h=26):
    vs = [v for v in values if v is not None]
    if len(vs) < 2:
        return ""
    lo, hi = min(vs), max(vs)
    rng = (hi - lo) or 1
    pts = " ".join(f"{i * (w - 4) / (len(values) - 1) + 2:.1f},{h - 3 - (v - lo) / rng * (h - 6):.1f}" for i, v in enumerate(values) if v is not None)
    return f'<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}" aria-hidden="true"><polyline points="{pts}" class="l s1"/></svg>'
