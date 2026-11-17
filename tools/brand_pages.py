#!/usr/bin/env python3
"""Put the Rampwise logo into every public page: a favicon (SVG, with PNG fallbacks) and the Apple touch icon.

  python tools/brand_pages.py

Safe to run again: pages that already have the links are left alone. The demo-plan and sample-report builders call it after they write their pages, so regenerating
them does not drop the icon. The logo files are docs/img/logo.svg, logo-192.png and logo-180.png.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
SKIP = {"google68744608bca52bbd.html"}               # the Search Console verification file must stay exactly as Google gave it


def links(prefix):
    return (f'<link rel="icon" type="image/svg+xml" href="{prefix}img/logo.svg">'
            f'<link rel="icon" type="image/png" sizes="192x192" href="{prefix}img/logo-192.png">'
            f'<link rel="apple-touch-icon" href="{prefix}img/logo-180.png">')


def brand(path: Path):
    raw = path.read_bytes().decode("utf-8")
    if 'rel="icon"' in raw or path.name in SKIP:
        return False
    depth = len(path.relative_to(DOCS).parts) - 1
    tag = links("../" * depth)
    new = re.sub(r"(<meta charset=\"utf-8\">)", lambda m: m.group(1) + tag, raw, count=1)
    if new == raw:
        return False
    path.write_bytes(new.encode("utf-8"))
    return True


def run():
    n = 0
    for p in sorted(DOCS.rglob("*.html")):
        n += brand(p)
    return n


if __name__ == "__main__":
    print(f"favicon added to {run()} page(s)")
