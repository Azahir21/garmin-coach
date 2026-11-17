#!/usr/bin/env python3
"""Put a readable file for EVERY paper in the skills' library.md tables into each skill's references/papers/ folder, plus an INDEX.md that says what each file is.

  python tools/build_paper_files.py [--dest ~/.claude/skills] [--skill rampwise-planner] [--dry-run]

For each library row with a PMID (or DOI) that has no file yet:
  - open-access paper with a licence in Europe PMC  -> the full text, converted to Markdown       (Read depth: full text)
  - everything else (paywalled)                      -> the abstract with the full citation        (Read depth: abstract only)
  - no abstract at all                               -> a stub with the citation                   (Read depth: title only)
Existing files are never overwritten. The files are for YOUR local reading by the skills and the coach: do not commit or redistribute them (licences differ, and the public
repository refuses papers/*.md files). A paper that is not open access cannot be fetched legally; if you have a PDF, put it in the same folder and ask the coach to read it.
"""
import argparse
import json
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_papers import BASE, UA, render, text_of  # noqa: E402


def get_json(url):
    return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40))


def lookup(pmid, doi):
    for q in ([f"EXT_ID:{pmid} AND SRC:MED"] if pmid else []) + ([f'DOI:"{doi}"'] if doi else []):
        r = get_json(BASE + "/search?" + urllib.parse.urlencode({"query": q, "format": "json", "resultType": "core"}))["resultList"]["result"]
        if r:
            return r[0]
    return None


def ascii_slug(s, n=60):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-")[:n] or "paper"


def clean(t):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t or "")).strip()


def header(m, depth, extra=""):
    ji = (m.get("journalInfo") or {}).get("journal", {}).get("title") or m.get("journalTitle") or ""
    return [f"# {clean(m.get('title'))}\n", f"- Authors: {m.get('authorString')}", f"- Journal: {ji} ({m.get('pubYear')}) {m.get('pageInfo') or ''}".rstrip(),
            f"- DOI: https://doi.org/{m.get('doi')}" if m.get("doi") else "- DOI: not recorded", f"- PMID: {m.get('pmid') or m.get('id')} | PMCID: {m.get('pmcid') or 'none'}",
            f"- Licence: {m.get('license') or 'not an open licence (abstract is reproduced only for your private reading)'}",
            f"- **Read depth: {depth}**{extra}", f"- Retrieved {date.today()} from the Europe PMC REST API. Local use only; cite the DOI, not this file.\n"]


def full_text(m):
    xml = urllib.request.urlopen(urllib.request.Request(f"{BASE}/{m['pmcid']}/fullTextXML", headers=UA), timeout=120).read()
    root = ET.fromstring(xml)
    out = header(m, "full text", " (figures and the reference list are omitted)")
    a = root.find(".//front//abstract")
    if a is not None:
        out += ["\n## Abstract\n", text_of(a) + "\n"]
    body = root.find(".//body")
    n = 0
    if body is not None:
        for ch in body:
            if ch.tag == "sec":
                render(ch, 2, out)
                n += 1
            elif ch.tag == "p":
                out.append(text_of(ch) + "\n")
                n += 1
    return out if n else None


def rows_of(lib):
    for ln in lib.read_text(encoding="utf-8").splitlines():
        if not re.match(r"^\| \d+ \|", ln):
            continue
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(cells) < 4:
            continue
        doi = next((re.search(r"10\.\d{4,9}/\S+", c).group(0).rstrip(").,;") for c in cells if re.search(r"10\.\d{4,9}/\S+", c)), None)
        pm = next((c for c in cells[2:] if re.fullmatch(r"\d{6,9}", c)), None)
        yield cells[1], doi, pm


def existing_ids(folder):
    ids = set()
    for f in folder.glob("*.md"):
        head = f.read_text(encoding="utf-8", errors="ignore")[:1500]
        ids |= set(re.findall(r"PMID: (\d{6,9})", head))
        ids |= {d.lower().rstrip("/") for d in re.findall(r"doi\.org/(10\.\S+)", head)}
    return ids


def write_index(folder, skill):
    lines = [f"# Papers for {skill}", "",
             "One file per paper in `../library.md`. **Read depth** says how much of the paper the coach can actually read: `full text` (open access), `abstract only` (paywalled: the claim strength is capped by what the abstract says), or `title only`.",
             "A rule in `../evidence-map.md` must never claim more than its file here shows. To close a gap, put the paper's PDF in this folder and ask the coach to read it and update the evidence map.", "",
             "| File | Read depth | Paper |", "|---|---|---|"]
    for f in sorted(folder.glob("*.md")):
        if f.name == "INDEX.md":
            continue
        head = f.read_text(encoding="utf-8", errors="ignore")[:2500]
        title = (re.match(r"# (.+)", head) or [None, f.stem])[1][:110]
        depth = (re.search(r"Read depth: ([a-z ]+)", head) or [None, "full text (older file)" if "Abstract" in head else "unknown"])[1].strip()
        lines.append(f"| `{f.name}` | {depth} | {title} |")
    (folder / "INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dest", default=str(Path.home() / ".claude" / "skills"))
    ap.add_argument("--skill")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    dest_root = Path(a.dest).expanduser()
    stats = {"full text": 0, "abstract only": 0, "title only": 0, "skipped (have it)": 0, "failed": 0}
    for lib in sorted((ROOT / "skills").glob("*/references/library.md")):
        skill = lib.parent.parent.name
        if a.skill and skill != a.skill:
            continue
        folder = dest_root / skill / "references" / "papers"
        if not (dest_root / skill).exists():
            continue
        folder.mkdir(parents=True, exist_ok=True)
        have = existing_ids(folder)
        for cite, doi, pmid in rows_of(lib):
            if (pmid and pmid in have) or (doi and doi.lower().rstrip("/") in have):
                stats["skipped (have it)"] += 1
                continue
            if not pmid and not doi:
                continue
            try:
                m = lookup(pmid, doi)
                time.sleep(0.25)
                if not m:
                    stats["failed"] += 1
                    print(f"  {skill}: not found in Europe PMC: {cite[:60]}")
                    continue
                au = (m.get("authorString") or "Unknown").split(",")[0].split(" ")[0]
                base = f"{ascii_slug(au, 20)}_{m.get('pubYear')}_{ascii_slug(m.get('title') or cite, 55)}"
                lines, depth = None, None
                if m.get("pmcid") and m.get("license") and not a.dry_run:
                    try:
                        lines, depth = full_text(m), "full text"
                    except Exception:
                        lines = None
                if lines is None:
                    ab = clean(m.get("abstractText"))
                    if ab:
                        lines, depth = header(m, "abstract only", " (the full text is behind a paywall or was not returned; claims are limited to what this abstract says)") + ["\n## Abstract\n", ab + "\n"], "abstract only"
                    else:
                        lines, depth = header(m, "title only", " (no abstract in the record)") + [f"\nCitation as listed: {cite}\n"], "title only"
                    base += "_ABSTRACT-ONLY" if depth == "abstract only" else "_TITLE-ONLY"
                stats[depth] += 1
                print(f"  {skill}: {depth:14} {base[:70]}")
                if not a.dry_run:
                    (folder / f"{base}.md").write_text("\n".join(lines), encoding="utf-8")
                    have.add(str(m.get("pmid") or ""))
            except Exception as e:
                stats["failed"] += 1
                print(f"  {skill}: failed ({str(e)[:60]}): {cite[:50]}")
        if not a.dry_run:
            write_index(folder, skill)
    print("\n" + ", ".join(f"{k}: {v}" for k, v in stats.items()))


if __name__ == "__main__":
    main()
