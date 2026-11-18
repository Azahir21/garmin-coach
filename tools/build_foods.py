#!/usr/bin/env python3
"""Build skills/rampwise-fueling/data/foods.json from the USDA FoodData Central "SR Legacy" CSV download.

  python tools/build_foods.py PATH/TO/FoodData_Central_sr_legacy_food_csv_2018-04

Source: USDA FoodData Central, SR Legacy (public domain, CC0): https://fdc.nal.usda.gov/download-datasets
Only the nutrient values used by the meal planner are kept (energy, protein, carbohydrate, fat, fibre per 100 g), each food keeps its
USDA ID, and household measures are copied from the USDA portion table. Nothing is guessed: a food that cannot be found by its ID or
exact description stops the build. Names and Southeast Asian/other aliases are written here by hand and only help search.
"""
import csv
import json
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "skills" / "rampwise-fueling" / "data" / "foods.json"
NUTRIENTS = {1008: "kcal", 1003: "protein", 1005: "carb", 1004: "fat", 1079: "fiber"}

# key, USDA id or exact description, display name, group, tags, aliases, portion keyword (matched in the USDA portion text)
# tags: poultry beef pork fish shellfish egg dairy gluten peanut treenut soy sesame  (used for diet and allergy filters)
F = [
    # ---- protein
    ("chicken_breast", 171477, "Chicken breast, cooked, no skin", "protein", ["poultry"], ["ayam", "dada ayam", "chicken"], "breast"),
    ("chicken_thigh", 172388, "Chicken thigh, cooked, no skin", "protein", ["poultry"], ["ayam", "paha ayam"], "thigh"),
    ("turkey_mince", 172848, "Turkey mince (fat free), cooked", "protein", ["poultry"], ["kalkun"], None),
    ("beef_lean_mince", 174028, "Lean beef mince (95/5), cooked", "protein", ["beef"], ["daging sapi", "sapi", "beef"], None),
    ("beef_round", 170235, "Beef top round, lean, braised", "protein", ["beef"], ["daging sapi", "sapi"], None),
    ("pork_loin", 168233, "Pork loin, lean, roasted", "protein", ["pork"], ["babi", "pork"], None),
    ("egg_boiled", 173424, "Egg, hard-boiled", "protein", ["egg"], ["telur", "telur rebus", "egg"], "large"),
    ("egg_scrambled", 172187, "Egg, scrambled", "protein", ["egg", "dairy"], ["telur dadar", "telur orak-arik"], None),
    ("egg_white", 172183, "Egg white, raw", "protein", ["egg"], ["putih telur"], "large"),
    ("tuna_canned", 173709, "Tuna, light, canned in water", "protein", ["fish"], ["tuna", "ikan tuna kaleng"], None),
    ("salmon", 175168, "Salmon, farmed, cooked", "protein", ["fish"], ["salmon"], None),
    ("cod", 171956, "Cod, cooked", "protein", ["fish"], ["ikan kod"], None),
    ("tilapia", 175177, "Tilapia, cooked", "protein", ["fish"], ["nila", "ikan nila", "ikan"], None),
    ("mackerel", 171994, "Mackerel (Pacific/jack), cooked", "protein", ["fish"], ["kembung", "ikan kembung", "makerel"], None),
    ("milkfish", 171995, "Milkfish, cooked", "protein", ["fish"], ["bandeng", "ikan bandeng"], None),
    ("catfish", 175166, "Catfish (farmed), cooked", "protein", ["fish"], ["lele", "ikan lele"], None),
    ("snapper", 173699, "Snapper, cooked", "protein", ["fish"], ["kakap", "ikan kakap"], None),
    ("sardine_canned", 175139, "Sardines, canned in oil, drained", "protein", ["fish"], ["sarden"], None),
    ("shrimp", 171971, "Shrimp, cooked", "protein", ["shellfish"], ["udang", "prawn"], None),
    ("tofu_firm", 172448, "Tofu, firm", "protein", ["soy"], ["tahu", "tofu"], None),
    ("tempeh", 172467, "Tempeh, cooked", "protein", ["soy"], ["tempe", "tempeh"], None),
    ("whey_protein", 173180, "Whey protein powder", "protein", ["dairy"], ["whey", "protein powder"], None),
    ("soy_protein_powder", 173181, "Soy protein powder", "protein", ["soy"], ["protein kedelai", "soy protein"], None),
    # ---- dairy
    ("milk_lowfat", 170872, "Milk, 1 % fat", "dairy", ["dairy"], ["susu", "susu rendah lemak"], "cup"),
    ("milk_whole", 171265, "Milk, whole", "dairy", ["dairy"], ["susu", "susu full cream"], "cup"),
    ("yogurt_greek", 170894, "Greek yoghurt, plain, non-fat", "dairy", ["dairy"], ["yogurt", "yoghurt", "greek yogurt"], None),
    ("yogurt_plain", 170886, "Yoghurt, plain, low-fat", "dairy", ["dairy"], ["yogurt", "yoghurt"], None),
    ("cottage_cheese", 168114, "Cottage cheese, low-fat", "dairy", ["dairy"], ["keju cottage"], None),
    ("cheese_mozzarella", 170847, "Mozzarella, part skim", "dairy", ["dairy"], ["keju"], None),
    ("cheese_cheddar", 173414, "Cheddar cheese", "dairy", ["dairy"], ["keju"], None),
    ("soymilk", 172446, "Soy milk, unsweetened", "dairy", ["soy"], ["susu kedelai", "susu soya"], "cup"),
    # ---- legumes
    ("lentils", 172421, "Lentils, boiled", "legume", [], ["lentil", "dal"], None),
    ("chickpeas", 173757, "Chickpeas, boiled", "legume", [], ["kacang arab", "garbanzo"], None),
    ("black_beans", 173735, "Black beans, boiled", "legume", [], ["kacang hitam"], None),
    ("kidney_beans", 173740, "Kidney beans, boiled", "legume", [], ["kacang merah"], None),
    ("white_beans", 175203, "White beans, boiled", "legume", [], ["kacang putih"], None),
    ("mung_beans", 174257, "Mung beans, boiled", "legume", [], ["kacang hijau"], None),
    ("edamame", 168411, "Edamame, prepared", "legume", ["soy"], ["edamame", "kedelai muda"], None),
    ("soybeans", 174271, "Soybeans, boiled", "legume", ["soy"], ["kedelai", "kacang kedelai"], None),
    # ---- carbohydrate staples
    ("rice_white", 168878, "White rice, cooked", "carb", [], ["nasi", "nasi putih", "beras", "rice"], "cup"),
    ("rice_brown", 169704, "Brown rice, cooked", "carb", [], ["nasi merah", "nasi beras merah", "beras merah"], "cup"),
    ("rice_sticky", 169711, "Sticky (glutinous) rice, cooked", "carb", [], ["ketan", "beras ketan", "nasi ketan"], "cup"),
    ("rice_noodles", 168914, "Rice noodles, cooked", "carb", [], ["bihun", "kwetiau", "mi beras", "vermicelli"], "cup"),
    ("egg_noodles", 168919, "Egg noodles, cooked", "carb", ["gluten", "egg"], ["mie", "mie telur"], "cup"),
    ("pasta", 169737, "Pasta, cooked", "carb", ["gluten"], ["pasta", "spaghetti", "makaroni"], "cup"),
    ("pasta_whole", 168910, "Whole-wheat pasta, cooked", "carb", ["gluten"], ["pasta gandum"], "cup"),
    ("oats", 173904, "Rolled oats, dry", "carb", [], ["oat", "oatmeal", "havermut", "gandum"], "cup"),
    ("bread_whole", 172688, "Whole-wheat bread", "carb", ["gluten"], ["roti gandum", "roti"], "slice"),
    ("bread_white", 174924, "White bread", "carb", ["gluten"], ["roti tawar", "roti putih", "roti"], "slice"),
    ("potato", 170438, "Potato, boiled", "carb", [], ["kentang"], "medium"),
    ("sweet_potato", 168483, "Sweet potato, baked", "carb", [], ["ubi", "ubi jalar", "ubi manis"], "medium"),
    ("cassava", 169985, "Cassava, RAW weight", "carb", [], ["singkong", "ubi kayu", "ketela pohon"], None),
    ("taro", 168486, "Taro, cooked", "carb", [], ["talas", "keladi"], None),
    ("plantain_green", 168216, "Plantain, green, boiled", "carb", [], ["pisang kepok rebus", "pisang tanduk", "plantain"], None),
    ("plantain_yellow", 169131, "Plantain, ripe, baked", "carb", [], ["pisang kepok", "pisang tanduk"], None),
    ("couscous", 169700, "Couscous, cooked", "carb", ["gluten"], ["couscous"], "cup"),
    ("quinoa", 168917, "Quinoa, cooked", "carb", [], ["quinoa"], "cup"),
    ("barley", 170285, "Pearl barley, cooked", "carb", ["gluten"], ["jelai", "barley"], "cup"),
    ("bulgur", 170287, "Bulgur, cooked", "carb", ["gluten"], ["bulgur"], "cup"),
    ("millet", 168871, "Millet, cooked", "carb", [], ["jawawut", "millet"], "cup"),
    ("soba", 168907, "Soba noodles, cooked", "carb", ["gluten"], ["soba"], "cup"),
    ("corn_cooked", 169999, "Sweet corn, boiled", "carb", [], ["jagung", "jagung rebus"], "cup"),
    ("corn_tortilla", 175036, "Corn tortilla", "carb", [], ["tortilla jagung"], None),
    ("pita_whole", 174916, "Whole-wheat pita", "carb", ["gluten"], ["pita"], None),
    ("naan", 171845, "Naan", "carb", ["gluten", "dairy"], ["naan"], None),
    ("rice_cake", 168107, "Rice cake (cracker)", "carb", [], ["kerupuk beras", "rice cake"], None),
    ("granola", 171646, "Granola, homemade", "carb", ["gluten", "treenut"], ["granola"], "cup"),
    # ---- fruit
    ("banana", 173944, "Banana", "fruit", [], ["pisang", "banana"], "medium"),
    ("apple", 171688, "Apple", "fruit", [], ["apel"], "medium"),
    ("orange", 169097, "Orange", "fruit", [], ["jeruk"], "fruit"),
    ("mango", 169910, "Mango", "fruit", [], ["mangga"], None),
    ("papaya", 169926, "Papaya", "fruit", [], ["pepaya"], None),
    ("pineapple", 169124, "Pineapple", "fruit", [], ["nanas"], None),
    ("watermelon", 167765, "Watermelon", "fruit", [], ["semangka"], None),
    ("strawberries", 167762, "Strawberries", "fruit", [], ["stroberi"], None),
    ("grapes", 174683, "Grapes", "fruit", [], ["anggur"], None),
    ("kiwi", 168153, "Kiwifruit", "fruit", [], ["kiwi"], None),
    ("pear", 167776, "Pear", "fruit", [], ["pir"], None),
    ("jackfruit", 174687, "Jackfruit", "fruit", [], ["nangka", "cempedak"], None),
    ("durian", 168192, "Durian", "fruit", [], ["durian"], None),
    ("passion_fruit", 169108, "Passion fruit", "fruit", [], ["markisa"], None),
    ("pomegranate", 169134, "Pomegranate", "fruit", [], ["delima"], None),
    ("dates", 168191, "Dates (medjool)", "fruit", [], ["kurma", "dates"], None),
    ("raisins", 168165, "Raisins", "fruit", [], ["kismis", "raisin"], None),
    ("orange_juice", 169098, "Orange juice", "fruit", [], ["jus jeruk", "air jeruk"], "cup"),
    ("coconut_water", 174831, "Coconut water", "fruit", [], ["air kelapa"], "cup"),
    # ---- vegetables
    ("broccoli", 169967, "Broccoli, boiled", "veg", [], ["brokoli"], None),
    ("spinach", 168462, "Spinach, raw", "veg", [], ["bayam"], None),
    ("kale", 168421, "Kale, raw", "veg", [], ["kale"], None),
    ("pak_choi", 170390, "Pak choi, raw", "veg", [], ["sawi", "pakcoy", "sawi putih", "bok choy"], None),
    ("cabbage", 169975, "Cabbage, raw", "veg", [], ["kol", "kubis"], None),
    ("carrot", 170393, "Carrot, raw", "veg", [], ["wortel"], "medium"),
    ("tomato", 170457, "Tomato, raw", "veg", [], ["tomat"], "medium"),
    ("cucumber", 168409, "Cucumber, raw", "veg", [], ["timun", "mentimun"], None),
    ("green_beans", 169141, "Green beans, boiled", "veg", [], ["buncis"], None),
    ("yardlong_bean", 169223, "Yardlong bean, boiled", "veg", [], ["kacang panjang"], None),
    ("bean_sprouts", 169957, "Mung bean sprouts, raw", "veg", [], ["tauge", "kecambah"], None),
    ("bell_pepper", 170108, "Red bell pepper, raw", "veg", [], ["paprika", "cabai besar"], None),
    ("mushrooms", 169251, "Mushrooms, raw", "veg", [], ["jamur"], None),
    ("pumpkin", 168449, "Pumpkin, boiled", "veg", [], ["labu", "labu kuning"], None),
    ("eggplant", 169229, "Eggplant, boiled", "veg", [], ["terong"], None),
    ("okra", 169261, "Okra, boiled", "veg", [], ["okra"], None),
    ("cauliflower", 169986, "Cauliflower, raw", "veg", [], ["kembang kol"], None),
    ("zucchini", 169291, "Zucchini, raw", "veg", [], ["zukini"], None),
    ("chayote", 170402, "Chayote, raw", "veg", [], ["labu siam"], None),
    ("bamboo_shoots", 169210, "Bamboo shoots, raw", "veg", [], ["rebung"], None),
    ("onion", 170000, "Onion, raw", "veg", [], ["bawang bombay", "bawang merah", "bawang"], None),
    ("garlic", 169230, "Garlic, raw", "veg", [], ["bawang putih"], None),
    ("lettuce", 169247, "Romaine lettuce, raw", "veg", [], ["selada"], None),
    # ---- fats, nuts, seeds
    ("olive_oil", 171413, "Olive oil", "fat", [], ["minyak zaitun"], "tablespoon"),
    ("canola_oil", 172336, "Canola oil", "fat", [], ["minyak canola"], "tablespoon"),
    ("coconut_oil", 171412, "Coconut oil", "fat", [], ["minyak kelapa"], "tablespoon"),
    ("palm_oil", 171015, "Palm oil", "fat", [], ["minyak sawit", "minyak goreng"], "tablespoon"),
    ("butter", 173430, "Butter", "fat", ["dairy"], ["mentega"], "tablespoon"),
    ("peanut_butter", 174294, "Peanut butter", "fat", ["peanut"], ["selai kacang", "kacang tanah"], "tablespoon"),
    ("peanuts", 173806, "Peanuts, dry-roasted", "fat", ["peanut"], ["kacang tanah", "kacang"], None),
    ("almonds", "Nuts, almonds", "Almonds", "fat", ["treenut"], ["almond"], None),
    ("walnuts", 170187, "Walnuts", "fat", ["treenut"], ["kenari"], None),
    ("cashews", 170162, "Cashews, raw", "fat", ["treenut"], ["mete", "kacang mete"], None),
    ("avocado", 171705, "Avocado", "fat", [], ["alpukat", "avokad"], None),
    ("coconut_milk", 170173, "Coconut milk, canned", "fat", [], ["santan"], None),
    ("coconut_meat", 170169, "Coconut meat, raw", "fat", [], ["kelapa", "kelapa parut"], None),
    ("chia", 170554, "Chia seeds", "fat", [], ["chia"], None),
    ("flax", 169414, "Flaxseed", "fat", [], ["biji rami"], None),
    ("sesame", 170150, "Sesame seeds", "fat", ["sesame"], ["wijen"], None),
    ("tahini", 170189, "Tahini", "fat", ["sesame"], ["tahini"], None),
    ("hummus", 174289, "Hummus", "fat", ["sesame"], ["hummus"], None),
    # ---- sugars and extras
    ("honey", 169640, "Honey", "sugar", [], ["madu"], "tablespoon"),
    ("sugar", 169655, "Sugar", "sugar", [], ["gula"], "tablespoon"),
    ("jam", 169641, "Jam", "sugar", [], ["selai"], "tablespoon"),
    ("dark_chocolate", 170273, "Dark chocolate (70-85 %)", "sugar", ["dairy"], ["coklat hitam"], None),
    ("soy_sauce", 174277, "Soy sauce", "extra", ["soy", "gluten"], ["kecap asin"], "tablespoon"),
    ("fish_sauce", 174531, "Fish sauce", "extra", ["fish"], ["kecap ikan"], "tablespoon"),
]


def read(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def main(src):
    src = Path(src)
    food = {r["fdc_id"]: r["description"] for r in read(src / "food.csv")}
    by_desc = {}
    for i, d in food.items():
        by_desc.setdefault(d.lower(), []).append(i)
    nut = {}
    wanted = set()
    for k, ref, *_ in F:
        if isinstance(ref, int):
            if str(ref) not in food:
                sys.exit(f"{k}: USDA id {ref} not in SR Legacy")
            wanted.add(str(ref))
        else:
            ids = by_desc.get(ref.lower())
            if not ids or len(ids) != 1:
                sys.exit(f"{k}: description {ref!r} gave {ids}")
    for r in read(src / "food_nutrient.csv"):
        n = int(r["nutrient_id"])
        if n in NUTRIENTS:
            nut.setdefault(r["fdc_id"], {})[NUTRIENTS[n]] = float(r["amount"] or 0)
    ports = {}
    for r in read(src / "food_portion.csv"):
        txt = (r["portion_description"] + " " + r["modifier"]).strip()
        if r["gram_weight"]:
            ports.setdefault(r["fdc_id"], []).append((float(r["amount"] or 1), txt, float(r["gram_weight"])))
    out, seen = [], set()
    for k, ref, name, group, tags, aliases, pk in F:
        fid = str(ref) if isinstance(ref, int) else by_desc[ref.lower()][0]
        if k in seen:
            sys.exit("duplicate key " + k)
        seen.add(k)
        n = nut.get(fid, {})
        miss = [x for x in ("kcal", "protein", "carb", "fat") if x not in n]
        if miss:
            sys.exit(f"{k} ({fid}) has no {miss}")
        unit = None
        if pk:
            for amt, txt, g in ports.get(fid, []):
                t = txt.lower()
                if pk in t or (pk == "tablespoon" and "tbsp" in t) or (pk == "medium" and "medium" in t):
                    unit = {"label": ("1 " + txt).strip(), "g": round(g / amt, 1)}
                    break
        out.append({"key": k, "name": name, "group": group, "tags": tags, "aliases": aliases, "fdc_id": int(fid), "usda": food[fid],
                    "per100g": {x: round(n.get(x, 0.0), 2) for x in ("kcal", "protein", "carb", "fat", "fiber")}, "unit": unit})
    data = {"source": "USDA FoodData Central, SR Legacy (April 2018), public domain (CC0), https://fdc.nal.usda.gov",
            "note": "Values per 100 g of the food in the state named (cooked foods are cooked weights). Names and aliases are the project's own and only help search.",
            "foods": out}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({len(out)} foods)")
    for f in out:
        if f["unit"] is None and any(x[6] for x in F if x[0] == f["key"]):
            print("  no household measure found for", f["key"])


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
