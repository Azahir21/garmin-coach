#!/usr/bin/env python3
"""Download the open-access full texts listed in the skills' library.md files, for your own reading (not committed).

  python tools/fetch_papers.py [--skill rampwise-strength]

Reads each `skills/*/references/library.md` row whose status says `full text` and names a file under references/papers/, looks the PMID up in Europe PMC and
saves the JATS full text converted to Markdown. Licences differ (some are non-commercial or no-derivatives): keep the files local, do not redistribute them.
"""
import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest"
UA = {"User-Agent": "rampwise-paper-fetcher/1.0 (open-access full texts via Europe PMC REST API)"}
sys.path.insert(0, str(ROOT / "skills" / "rampwise" / "scripts"))
from paper_fetch import render, text_of  # noqa: E402  (shared with the on-demand fetch)




def fetch(pmid, dest):
    q = BASE + "/search?" + urllib.parse.urlencode({"query": f"EXT_ID:{pmid} AND SRC:MED", "format": "json", "resultType": "core"})
    m = json.load(urllib.request.urlopen(urllib.request.Request(q, headers=UA), timeout=40))["resultList"]["result"][0]
    pmcid = m.get("pmcid")
    if not pmcid:
        return "no open-access full text"
    xml = urllib.request.urlopen(urllib.request.Request(f"{BASE}/{pmcid}/fullTextXML", headers=UA), timeout=120).read()
    root = ET.fromstring(xml)
    out = [f"# {m.get('title')}\n", f"- Authors: {m.get('authorString')}", f"- DOI: https://doi.org/{m.get('doi')}", f"- PMID: {pmid} | PMCID: {pmcid} | licence: {m.get('license')}",
           "- Converted from JATS XML for personal reading; figures and references omitted. Cite the DOI.\n"]
    a = root.find(".//front//abstract")
    if a is not None:
        out += ["\n## Abstract\n", text_of(a) + "\n"]
    body = root.find(".//body")
    if body is not None:
        for ch in body:
            if ch.tag == "sec":
                render(ch, 2, out)
            elif ch.tag == "p":
                out.append(text_of(ch) + "\n")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(out), encoding="utf-8")
    return f"saved ({m.get('license')})"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--skill")
    a = ap.parse_args()
    for lib in sorted((ROOT / "skills").glob("*/references/library.md")):
        if a.skill and lib.parent.parent.name != a.skill:
            continue
        for ln in lib.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^\| \d+ \|.*\| (\d{6,9}) \| full text.*`(references/papers/[^`]+)`", ln)
            if m:
                dest = lib.parent.parent / m.group(2)
                print(f"{lib.parent.parent.name}: {dest.name} ... ", end="", flush=True)
                try:
                    print(dest.exists() and "already there" or fetch(m.group(1), dest))
                except Exception as e:                    # network or format problem: keep going
                    print("failed:", e)


if __name__ == "__main__":
    main()
