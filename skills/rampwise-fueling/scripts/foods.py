#!/usr/bin/env python3
"""Look up foods in the shipped USDA list, and add your own (local dishes, packaged foods from their label).

  foods.py search tempe            # also finds Southeast Asian and other aliases (tempe, tahu, nasi, ubi, singkong, bandeng ...)
  foods.py show tempeh
  foods.py add --key nasi_padang_rendang --name "Rendang, my portion" --kcal 195 --protein 22 --carb 4 --fat 10 [--fiber 1] [--alias rendang] [--tags beef] [--unit "1 piece" --unit-g 60]
  foods.py list [--group protein]
  foods.py remove nasi_padang_rendang

Values are per 100 g of the food as you weigh it. Your own foods are stored in $RAMPWISE_DATA/foods.json and are used by meal_plan.py next to the USDA list. The USDA
list covers basic ingredients (SR Legacy, public domain); local dishes are not in it, so copy the numbers from a food-composition table you trust or from the package label
and say where they came from with --source. Nothing is guessed.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nutri  # noqa: E402


def mine_path():
    return nutri.data_dir() / "foods.json"


def read_mine():
    try:
        return json.loads(mine_path().read_text(encoding="utf-8"))
    except Exception:
        return {"foods": []}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search"); s.add_argument("q")
    sh = sub.add_parser("show"); sh.add_argument("key")
    ls = sub.add_parser("list"); ls.add_argument("--group")
    ad = sub.add_parser("add")
    ad.add_argument("--key", required=True); ad.add_argument("--name", required=True)
    for n in ("kcal", "protein", "carb", "fat"):
        ad.add_argument("--" + n, type=float, required=True)
    ad.add_argument("--fiber", type=float, default=0.0)
    ad.add_argument("--group", default="extra", choices=("protein", "dairy", "legume", "carb", "fruit", "veg", "fat", "sugar", "extra"))
    ad.add_argument("--alias", action="append", default=[])
    ad.add_argument("--tags", default="", help="comma list from: " + ",".join(sorted(nutri.ALLERGENS | {"poultry", "beef", "pork"})))
    ad.add_argument("--unit"); ad.add_argument("--unit-g", type=float)
    ad.add_argument("--source", default="", help="where the numbers come from (label, table)")
    rm = sub.add_parser("remove"); rm.add_argument("key")
    a = ap.parse_args(argv)
    foods = nutri.load_foods()
    if a.cmd == "search":
        for f in nutri.search_foods(foods, a.q)[:30]:
            p = f["per100g"]
            print(f"{f['key']:<22} {f['name']:<44} {p['kcal']:>5.0f} kcal  P {p['protein']:>5.1f}  C {p['carb']:>5.1f}  F {p['fat']:>5.1f} per 100 g" + ("  [yours]" if f.get("custom") else ""))
        return 0
    if a.cmd == "show":
        f = foods.get(a.key)
        if not f:
            print("no such key; try: foods.py search <word>")
            return 2
        print(json.dumps(f, indent=1, ensure_ascii=False))
        return 0
    if a.cmd == "list":
        for f in sorted(foods.values(), key=lambda f: (f["group"], f["name"])):
            if not a.group or f["group"] == a.group:
                print(f"{f['group']:<8} {f['key']:<22} {f['name']}")
        return 0
    cur = read_mine()
    if a.cmd == "remove":
        cur["foods"] = [f for f in cur.get("foods", []) if f["key"] != a.key]
        mine_path().write_text(json.dumps(cur, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print("removed", a.key)
        return 0
    bad = [t for t in a.tags.split(",") if t and t not in nutri.ALLERGENS | {"poultry", "beef", "pork"}]
    if bad:
        print("unknown tag(s):", ", ".join(bad))
        return 2
    if a.key in foods and not foods[a.key].get("custom"):
        print("that key is in the USDA list; choose another key")
        return 2
    new = {"key": a.key, "name": a.name, "group": a.group, "aliases": a.alias, "tags": [t for t in a.tags.split(",") if t], "source": a.source,
           "per100g": {"kcal": a.kcal, "protein": a.protein, "carb": a.carb, "fat": a.fat, "fiber": a.fiber},
           "unit": {"label": "1 " + a.unit, "g": a.unit_g} if a.unit and a.unit_g else None}
    cur["foods"] = [f for f in cur.get("foods", []) if f["key"] != a.key] + [new]
    mine_path().parent.mkdir(parents=True, exist_ok=True)
    mine_path().write_text(json.dumps(cur, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print("added", a.key, "->", mine_path())
    return 0


if __name__ == "__main__":
    sys.exit(main())
