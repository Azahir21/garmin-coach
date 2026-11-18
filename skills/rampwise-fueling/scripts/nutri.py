"""Shared engine for the rampwise-fueling skill: energy and macro targets (cut, maintain, bulk), safeguards, and a meal builder.

Every number here is either (a) a published figure named next to it (label "research"), (b) a coaching convention (label "practice"), or
(c) an estimate that the weight trend then corrects. The evidence is in ../references/evidence-map.md. Standard library only.

Not medical advice. The gates in `check_gates` must be answered by the athlete; an unanswered gate stops the plan.
"""
import json
import os
from datetime import date, timedelta
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
KCAL_PER_KG = 7700.0           # rule of thumb for body-weight change (Helms 2014 quotes 3500 kcal per lb); the real change is dynamic (Hall 2011), so the weight trend corrects it

DAY_TYPES = ("rest", "light", "moderate", "hard", "long")
# Daily carbohydrate, g per kg body mass: (lowest we plan on a cut, target). The bands behind them are from Kerksick 2018: 3-5 general,
# 5-8 for 2-3 h of intense training a day, 8-10 for 3-6 h. Mapping our duration tiers onto them is PRACTICE.
CARB_G_PER_KG = {"rest": (3.0, 3.5), "light": (3.0, 4.0), "moderate": (4.0, 5.0), "hard": (5.0, 6.5), "long": (6.0, 8.0)}
LIFESTYLE = {"sedentary": 1.2, "light": 1.3, "active": 1.45}        # non-exercise activity multiplier on resting energy: PRACTICE (no source read)
KCAL_PER_KG_HOUR = 8.0         # fallback exercise cost for mixed endurance work when the watch gives none: PRACTICE, rough; the weight trend corrects it
DIETS = {                      # tags removed from the food list
    "omnivore": set(), "vegetarian": {"poultry", "beef", "pork", "fish", "shellfish"}, "vegan": {"poultry", "beef", "pork", "fish", "shellfish", "egg", "dairy"},
    "pescatarian": {"poultry", "beef", "pork"}, "halal": {"pork"},
}
ALLERGENS = {"peanut", "treenut", "dairy", "egg", "gluten", "soy", "fish", "shellfish", "sesame"}


def data_dir():
    env = os.environ.get("RAMPWISE_DATA") or os.environ.get("GARMIN_COACH_DATA")
    if env:
        return Path(env)
    new, old = Path.home() / "rampwise-data", Path.home() / "garmin-coach-data"
    return old if (old.exists() and not new.exists()) else new


# ------------------------------------------------------------------ foods
def load_foods(extra=True):
    """The shipped USDA list plus the athlete's own foods in $RAMPWISE_DATA/foods.json (same fields; per100g needs kcal, protein, carb, fat)."""
    foods = {f["key"]: f for f in json.loads((SKILL / "data" / "foods.json").read_text(encoding="utf-8"))["foods"]}
    mine = data_dir() / "foods.json"
    if extra and mine.exists():
        for f in json.loads(mine.read_text(encoding="utf-8")).get("foods", []):
            f.setdefault("group", "extra"); f.setdefault("tags", []); f.setdefault("aliases", []); f.setdefault("unit", None); f["custom"] = True
            f["per100g"].setdefault("fiber", 0.0)
            foods[f["key"]] = f
    return foods


def search_foods(foods, q):
    q = q.lower().strip()
    hit = [f for f in foods.values() if q in f["key"] or q in f["name"].lower() or any(q in a.lower() for a in f.get("aliases", []))]
    return sorted(hit, key=lambda f: (q not in f["name"].lower(), f["name"]))


def macros(food, grams):
    p = food["per100g"]
    return {k: p[k] * grams / 100.0 for k in ("kcal", "protein", "carb", "fat", "fiber")}


def allowed_foods(foods, diet="omnivore", exclude_tags=(), exclude_keys=()):
    bad = set(DIETS.get(diet, set())) | set(exclude_tags)
    return {k: f for k, f in foods.items() if k not in set(exclude_keys) and not (bad & set(f.get("tags", [])))}


# ------------------------------------------------------------------ gates
GATE_QUESTIONS = {
    "adult": "Are you 18 or older? (Under 18: growth and development change the needs; this skill does not plan weight change for minors.)",
    "pregnant_or_breastfeeding": "Are you pregnant or breastfeeding? (Needs change; see a dietitian or doctor.)",
    "eating_disorder": "Do you have, or have you had, an eating disorder, or does cutting calories make you anxious or preoccupied with food? (Cutting can worsen this; see a clinician first.)",
    "medical_diet": "Do you have a medical condition that changes how you should eat (diabetes, kidney, heart or gut disease, a thyroid condition, medicines that affect weight or appetite)?",
}


def check_gates(g, goal):
    """Returns (ok, reasons). g: dict with adult (True needed), pregnant_or_breastfeeding / eating_disorder / medical_diet (False needed). None = not asked yet."""
    g = g or {}
    need = {"adult": True, "pregnant_or_breastfeeding": False, "eating_disorder": False, "medical_diet": False}
    unknown = [k for k in need if g.get(k) is None]
    if unknown:
        return False, ["not asked yet: " + "; ".join(GATE_QUESTIONS[k] for k in unknown)]
    bad = [k for k, v in need.items() if g[k] != v]
    if bad:
        return False, ["a plan from this skill is not appropriate (" + ", ".join(bad) + "): refer to a registered sports dietitian or doctor"]
    return True, []


# ------------------------------------------------------------------ energy
def ree_mifflin(sex, kg, cm, age):
    """Resting energy expenditure, Mifflin-St Jeor 1990 (kcal/day). Frankenfield 2005: within 10 % of measured for more people than the other common equations, but individual errors are real."""
    return 10 * kg + 6.25 * cm - 5 * age + (5 if sex == "male" else -161)


def bmi(kg, cm):
    return kg / (cm / 100.0) ** 2


def ffm_kg(kg, bf_pct):
    return kg * (1 - bf_pct / 100.0) if bf_pct else None


def day_type(hours):
    return "rest" if hours <= 0.05 else "light" if hours < 1 else "moderate" if hours < 2 else "hard" if hours <= 3 else "long"


def exercise_kcal(hours, kg, kcal_per_hour=None):
    return hours * (kcal_per_hour if kcal_per_hour else KCAL_PER_KG_HOUR * kg)


def maintenance(profile, hours_by_day, kcal_per_hour=None):
    """Per day-of-week maintenance kcal: REE x lifestyle + that day's exercise. Estimate (practice); the weight trend corrects it."""
    ree = ree_mifflin(profile["sex"], profile["kg"], profile["cm"], profile["age"])
    base = ree * LIFESTYLE[profile.get("lifestyle", "light")]
    return ree, [base + exercise_kcal(h, profile["kg"], kcal_per_hour) for h in hours_by_day]


def plan_targets(p, hours_by_day, kcal_per_hour=None, weeks=None):
    """Daily energy and macros for each day of a week.

    p: sex, age, cm, kg, goal (cut|maintain|bulk), rate_pct (per week, cut: loss, bulk: gain), body_fat_pct, experience (novice|intermediate|advanced),
       lifestyle, gates{...}. Returns dict with status ("ok" | "needs-info" | "refer" | "no-cut"), days[], weekly, flags[], notes[]."""
    goal = p.get("goal", "maintain")
    flags, notes = [], []
    ok, why = check_gates(p.get("gates"), goal)
    if not ok:
        return {"status": "needs-info" if why[0].startswith("not asked") else "refer", "reasons": why, "days": [], "flags": [], "notes": []}
    kg, cm = p["kg"], p["cm"]
    b = bmi(kg, cm)
    bf = p.get("body_fat_pct")
    ffm = ffm_kg(kg, bf)
    if goal == "cut":
        if b < 20:
            return {"status": "no-cut", "reasons": [f"BMI {b:.1f} is under 20: no weight-loss plan (practice limit; a very lean athlete loses muscle first, Helms 2014). Maintain or bulk instead, or see a dietitian."], "days": [], "flags": [], "notes": []}
        if bf and bf <= (10 if p["sex"] == "male" else 17):
            return {"status": "no-cut", "reasons": [f"Body fat {bf:g} % is at or under {10 if p['sex'] == 'male' else 17} %: no weight-loss plan (practice limit)."], "days": [], "flags": [], "notes": []}
    ree, maint = maintenance(p, hours_by_day, kcal_per_hour)
    week_m = sum(maint)
    avg_m = week_m / 7.0

    adj_week = 0.0
    rate = p.get("rate_pct")
    if goal == "cut":
        rate = 0.5 if rate is None else rate
        if rate > 1.0:
            flags.append(f"rate {rate:g} %/week is over 1 %: capped at 1 % (Helms 2014 range 0.5-1 %)")
            rate = 1.0
        if rate > 0.7:
            flags.append("above 0.7 %/week: in the one trial that compared 0.7 with 1.4 %/week, only the slower rate kept and gained lean mass (Garthe 2011, 24 athletes)")
        adj_week = -rate / 100.0 * kg * KCAL_PER_KG
        cap = -0.25 * week_m
        if adj_week < cap:
            flags.append("deficit capped at 25 % of estimated maintenance (practice; the faster arm of Garthe 2011 cut intake by 30 %, the slower one by 19 %)")
            adj_week = cap
            rate = -adj_week / kg / KCAL_PER_KG * 100
        notes.append(f"Planned loss about {rate:.2f} % of body weight per week ({kg * rate / 100:.2f} kg/week). Estimate: check against the weight trend after 2-3 weeks (Hall 2011: the body adapts, so a fixed 7700 kcal per kg overestimates late loss).")
        if weeks is None:
            weeks = 12
        notes.append(f"Plan the cut for up to about {weeks} weeks, then return to maintenance for 2-4 weeks (Helms 2014: 2-4 months of dieting; the break length is practice; the one diet-break trial, Byrne 2018, was in men with obesity).")
    elif goal == "bulk":
        exp = p.get("experience", "intermediate")
        pct = {"novice": 0.20, "intermediate": 0.15, "advanced": 0.10}[exp]
        adj_week = pct * week_m
        if exp == "advanced":
            adj_week = min(adj_week, 300 * 7)
        rate = adj_week / KCAL_PER_KG / kg * 100
        if rate > 0.5:
            adj_week = 0.5 / 100 * kg * KCAL_PER_KG
            rate = 0.5
        notes.append(f"Planned gain about {rate:.2f} % of body weight per week. Iraki 2019: surplus about 10-20 % over maintenance and 0.25-0.5 % per week, more cautious for advanced lifters; Slater 2019: no study has found the best surplus, so adjust to your own weight trend.")
        if p.get("endurance_priority"):
            notes.append("Endurance first: keep the surplus small enough that run and ride quality does not drop; extra body mass costs speed on the bike and the run.")

    # day by day: spread the weekly adjustment evenly first; then protect carbohydrate on hard days
    days = []
    adj_day = [adj_week / 7.0] * 7
    pro_gkg = _protein_g_per_kg(goal, ffm, kg)
    prot_g = pro_gkg * kg
    for i, h in enumerate(hours_by_day):
        days.append({"dow": i, "hours": h, "type": day_type(h), "maint": maint[i]})
    for _ in range(4):
        for i, d in enumerate(days):
            E = d["maint"] + adj_day[i]
            F = _fat_g(E, kg, goal)
            C = (E - 4 * prot_g - 9 * F) / 4.0
            low, target = CARB_G_PER_KG[d["type"]]
            d.update(E=E, F=F, C=C, low=low * kg, target=target * kg)
        if goal != "cut":
            break
        short = [(i, d["low"] - d["C"]) for i, d in enumerate(days) if d["C"] < d["low"]]
        if not short:
            break
        need = sum(4 * s for _, s in short)               # kcal needed to lift those days to their carbohydrate floor
        donors = [i for i, d in enumerate(days) if d["C"] >= d["low"] + 20]
        if not donors:
            flags.append("carbohydrate is below the planned minimum on some days even with the deficit shared out: lower the rate or maintain")
            break
        for i, s in short:
            adj_day[i] += 4 * s
        take = need / len(donors)
        for i in donors:
            adj_day[i] -= take
    for i, d in enumerate(days):
        E = d["maint"] + adj_day[i]
        if goal == "cut":
            E = max(E, ree)
        F = _fat_g(E, kg, goal)
        C = max(0.0, (E - 4 * prot_g - 9 * F) / 4.0)
        d.update(E=round(E), P=round(prot_g), F=round(F), C=round(C), cho_gkg=round(C / kg, 1))
        if C < d["low"] - 1:
            flags.append(f"{_DOW[i]}: carbohydrate {C / kg:.1f} g/kg is under the {d['low'] / kg:.0f} g/kg planned for a {d['type']} day (Kerksick 2018 bands): consider a slower rate")
    avg_E = sum(d["E"] for d in days) / 7.0
    avg_ex = sum(exercise_kcal(h, kg, kcal_per_hour) for h in hours_by_day) / 7.0
    ea = None
    if ffm:
        ea = (avg_E - avg_ex) / ffm
        if ea < 30:
            flags.append(f"energy availability about {ea:.0f} kcal per kg fat-free mass is under 30, the figure usually cited as problematic (IOC REDs 2023 says it cannot be measured accurately in the field): raise intake")
        elif ea < 45:
            notes.append(f"Energy availability about {ea:.0f} kcal per kg fat-free mass: between the 30 and 45 usually quoted as low and healthy; fine for a limited cut, not for months. A rough figure.")
    else:
        notes.append("Body fat % not given, so energy availability is not checked; the 25 % deficit cap and the resting-energy floor still apply.")
    if goal == "cut" and avg_E < ree:
        flags.append("average intake is under resting energy: not planned")
    return {"status": "ok", "goal": goal, "rate_pct": rate, "ree": round(ree), "maintenance_avg": round(avg_m), "avg_target": round(avg_E),
            "protein_g_per_kg": round(pro_gkg, 2), "energy_availability": None if ea is None else round(ea), "bmi": round(b, 1), "days": days,
            "flags": flags, "notes": notes, "weeks": weeks}


_DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _protein_g_per_kg(goal, ffm, kg):
    if goal == "cut":
        # Helms 2014 and Jager 2017: 2.3-3.1 g per kg lean mass in hypocaloric periods; the low end is used. Without body fat: 2.0 g/kg body mass (inside the 1.8-2.7 range Helms cites).
        return min(3.1, 2.3 * ffm / kg) if ffm else 2.0
    if goal == "bulk":
        return 1.8                       # Iraki 2019: 1.6-2.2 g/kg/day
    return 1.6                           # Morton 2018: no further gain in lean mass above about 1.6 g/kg/day; Jager 2017: 1.4-2.0


def _fat_g(E, kg, goal):
    lo = max(0.20 * E / 9.0, 0.5 * kg)          # Slater 2019: discourage under 15-20 % of energy; Iraki 2019: 0.5-1.5 g/kg
    hi = (0.30 if goal == "cut" else 0.35) * E / 9.0   # Helms 2014: 15-30 % on a cut; ACSM 20-35 % (quoted in Slater 2019)
    return min(max(0.25 * E / 9.0, lo), hi) if hi >= lo else lo


# ------------------------------------------------------------------ meal templates
# role: P protein source (scaled), C carbohydrate source (scaled), F fat source (scaled), V vegetables/fruit/extras (fixed amount, grams).
# "opts" are food keys; the builder picks the first allowed one in a rotating order. Cuisine "id" = Southeast Asian-style, built from basic ingredients (approximate, not the restaurant dish).
def _t(name, cuisine, slots, parts, tags=()):
    return {"name": name, "cuisine": cuisine, "slots": slots, "parts": parts, "tags": list(tags)}


def _p(role, opts, g, lo=None, hi=None):
    return {"role": role, "opts": opts, "g": g, "min": lo if lo is not None else g * 0.3, "max": hi if hi is not None else g * 3}


TEMPLATES = [
    # ---- Southeast Asian-style
    _t("Nasi plate, Southeast Asian style", "id", ["lunch", "dinner"], [_p("P", ["chicken_breast", "chicken_thigh"], 130, 60, 300), _p("C", ["rice_white", "rice_brown"], 220, 80, 450), _p("F", ["tempeh", "tofu_firm"], 60, 0, 150), _p("V", ["cabbage", "green_beans", "yardlong_bean"], 100), _p("V", ["tomato", "cucumber"], 60), _p("X", ["palm_oil", "canola_oil", "olive_oil"], 8, 0, 25)]),
    _t("Nasi with fish and greens, Southeast Asian style", "id", ["lunch", "dinner"], [_p("P", ["tilapia", "mackerel", "milkfish", "catfish", "snapper"], 150, 70, 300), _p("C", ["rice_white", "rice_brown"], 220, 80, 450), _p("F", ["tofu_firm", "tempeh"], 80, 0, 200), _p("V", ["pak_choi", "spinach", "bean_sprouts"], 120), _p("X", ["palm_oil", "canola_oil", "olive_oil"], 8, 0, 25)]),
    _t("Nasi with egg and tempeh, Southeast Asian style", "id", ["breakfast", "lunch"], [_p("P", ["egg_boiled", "egg_scrambled"], 100, 50, 250), _p("C", ["rice_white", "rice_brown", "rice_sticky"], 200, 80, 400), _p("F", ["tempeh", "tofu_firm"], 60, 0, 140), _p("V", ["cucumber", "tomato"], 80), _p("X", ["palm_oil", "canola_oil"], 6, 0, 20)]),
    _t("Gado-gado style plate: protein, root vegetable, vegetables and peanut sauce", "id", ["lunch", "dinner"], [_p("P", ["tofu_firm", "tempeh", "egg_boiled"], 120, 60, 250), _p("C", ["potato", "sweet_potato", "cassava"], 200, 80, 400), _p("F", ["peanut_butter", "peanuts"], 25, 0, 60), _p("V", ["cabbage", "bean_sprouts", "green_beans"], 150), _p("V", ["cucumber", "tomato"], 60), _p("X", ["coconut_milk"], 20)], tags=["peanut"]),
    _t("Rice noodle (bihun) soup, Southeast Asian style", "id", ["lunch", "dinner"], [_p("P", ["chicken_breast", "chicken_thigh", "tofu_firm"], 110, 60, 250), _p("C", ["rice_noodles"], 250, 100, 450), _p("F", ["egg_boiled"], 50, 0, 100), _p("V", ["bean_sprouts", "cabbage", "pak_choi"], 100), _p("X", ["onion"], 20)]),
    _t("Root vegetable with egg or tempeh, Southeast Asian style", "id", ["snack", "breakfast", "pre"], [_p("P", ["egg_boiled", "tempeh", "tofu_firm"], 100, 50, 200), _p("C", ["sweet_potato", "cassava", "taro", "plantain_yellow"], 200, 80, 400), _p("V", ["cucumber", "tomato"], 40)]),
    _t("Oat bowl with banana, milk or yoghurt and nut butter", "id", ["breakfast", "snack", "pre"], [_p("C", ["oats"], 60, 30, 130), _p("P", ["milk_lowfat", "soymilk", "yogurt_greek"], 250, 100, 450), _p("F", ["peanut_butter", "almonds", "walnuts"], 15, 0, 40), _p("V", ["banana"], 100)]),
    _t("Banana and nut butter on bread with milk or yoghurt", "id", ["snack", "pre"], [_p("C", ["bread_whole", "bread_white"], 70, 30, 160), _p("F", ["peanut_butter", "almonds", "walnuts"], 20, 0, 40), _p("P", ["milk_lowfat", "yogurt_greek", "soymilk"], 200, 0, 400), _p("V", ["banana"], 100)]),
    _t("Nasi with meat and vegetables, Southeast Asian style", "id", ["lunch", "dinner"], [_p("P", ["beef_lean_mince", "beef_round", "chicken_thigh"], 120, 60, 260), _p("C", ["rice_white", "rice_brown"], 220, 80, 450), _p("F", ["tempeh", "tofu_firm", "egg_boiled"], 60, 0, 140), _p("V", ["carrot", "green_beans", "cabbage", "chayote"], 120), _p("X", ["palm_oil", "canola_oil"], 8, 0, 25)]),
    _t("Nasi with seafood and greens, Southeast Asian style", "id", ["lunch", "dinner"], [_p("P", ["shrimp", "sardine_canned", "tuna_canned"], 120, 60, 250), _p("C", ["rice_white", "rice_brown"], 220, 80, 450), _p("F", ["tofu_firm", "tempeh"], 60, 0, 150), _p("V", ["spinach", "pak_choi", "okra"], 120), _p("X", ["palm_oil", "canola_oil"], 8, 0, 25)]),
    # ---- global
    _t("Yoghurt or cottage cheese bowl with oats, fruit and nuts", "global", ["breakfast", "snack", "pre"], [_p("P", ["yogurt_greek", "cottage_cheese", "soy_protein_powder", "whey_protein"], 200, 80, 400), _p("C", ["oats", "granola"], 50, 25, 120), _p("F", ["almonds", "walnuts", "peanut_butter", "chia", "cashews"], 15, 0, 40), _p("V", ["banana", "strawberries", "apple", "mango"], 120)]),
    _t("Eggs on toast with fruit", "global", ["breakfast"], [_p("P", ["egg_scrambled", "egg_boiled"], 150, 60, 300), _p("C", ["bread_whole", "bread_white"], 90, 40, 200), _p("F", ["avocado", "butter", "olive_oil"], 40, 0, 100), _p("V", ["orange", "apple", "kiwi"], 130)]),
    _t("Tofu scramble on toast", "global", ["breakfast", "lunch"], [_p("P", ["tofu_firm", "tempeh"], 150, 60, 300), _p("C", ["bread_whole", "bread_white"], 90, 40, 200), _p("F", ["avocado", "olive_oil", "peanut_butter"], 30, 0, 80), _p("V", ["tomato", "spinach", "mushrooms"], 100), _p("V", ["banana", "orange"], 120)]),
    _t("Rice bowl with a lean protein and vegetables", "global", ["lunch", "dinner"], [_p("P", ["chicken_breast", "chicken_thigh", "turkey_mince", "tofu_firm"], 140, 60, 300), _p("C", ["rice_white", "rice_brown", "quinoa", "couscous"], 200, 80, 450), _p("F", ["olive_oil", "avocado", "almonds"], 12, 0, 40), _p("V", ["broccoli", "green_beans", "cauliflower"], 150)]),
    _t("Fish, potato and greens plate", "global", ["lunch", "dinner"], [_p("P", ["salmon", "cod", "tilapia", "tuna_canned", "mackerel"], 150, 70, 300), _p("C", ["potato", "sweet_potato", "couscous"], 250, 100, 500), _p("F", ["olive_oil", "butter", "avocado"], 8, 0, 30), _p("V", ["spinach", "broccoli", "zucchini"], 150)]),
    _t("Pasta with lean protein and tomato", "global", ["lunch", "dinner"], [_p("P", ["beef_lean_mince", "turkey_mince", "chicken_breast", "lentils"], 130, 60, 280), _p("C", ["pasta", "pasta_whole"], 220, 100, 450), _p("F", ["olive_oil", "cheese_mozzarella", "almonds"], 10, 0, 40), _p("V", ["tomato", "onion", "mushrooms", "bell_pepper"], 150)]),
    _t("Lentil or chickpea rice bowl", "global", ["lunch", "dinner"], [_p("P", ["lentils", "chickpeas", "black_beans", "kidney_beans", "soybeans"], 180, 80, 400), _p("C", ["rice_white", "rice_brown", "quinoa", "bulgur"], 180, 70, 400), _p("F", ["olive_oil", "tahini", "avocado", "peanuts"], 12, 0, 40), _p("V", ["spinach", "carrot", "tomato", "bell_pepper"], 150)]),
    _t("Tofu stir-fry with rice noodles", "global", ["lunch", "dinner"], [_p("P", ["tofu_firm", "tempeh", "edamame", "shrimp"], 160, 80, 320), _p("C", ["rice_noodles", "soba", "rice_white"], 240, 100, 450), _p("F", ["sesame", "peanuts", "canola_oil", "olive_oil"], 10, 0, 35), _p("V", ["broccoli", "carrot", "pak_choi", "bell_pepper"], 160), _p("X", ["soy_sauce"], 8)], tags=["soy"]),
    _t("Tuna or chicken sandwich with salad", "global", ["lunch", "snack"], [_p("P", ["tuna_canned", "chicken_breast", "egg_boiled", "cottage_cheese"], 100, 50, 220), _p("C", ["bread_whole", "bread_white", "pita_whole"], 110, 50, 240), _p("F", ["olive_oil", "avocado", "cheese_cheddar"], 12, 0, 40), _p("V", ["lettuce", "tomato", "cucumber"], 100)]),
    _t("Burrito bowl: beans, rice and chicken", "global", ["lunch", "dinner"], [_p("P", ["chicken_breast", "black_beans", "beef_lean_mince", "kidney_beans"], 130, 60, 280), _p("C", ["rice_white", "rice_brown", "corn_tortilla", "corn_cooked"], 200, 80, 420), _p("F", ["avocado", "cheese_cheddar", "olive_oil"], 40, 0, 90), _p("V", ["tomato", "bell_pepper", "onion", "lettuce"], 120)]),
    _t("Dairy or protein snack with fruit and honey", "global", ["snack", "post"], [_p("P", ["cottage_cheese", "yogurt_greek", "yogurt_plain", "whey_protein", "soy_protein_powder"], 200, 60, 400), _p("C", ["banana", "mango", "grapes", "apple", "dates", "raisins"], 150, 60, 350), _p("F", ["almonds", "walnuts", "chia"], 10, 0, 30), _p("X", ["honey"], 10)]),
    _t("Recovery shake: milk or soy milk, banana, protein powder", "global", ["post", "snack"], [_p("P", ["whey_protein", "soy_protein_powder", "yogurt_greek"], 30, 15, 60), _p("C", ["banana", "orange_juice", "mango", "dates"], 200, 80, 420), _p("V", ["milk_lowfat", "soymilk", "milk_whole"], 300)]),
    _t("Rice cakes or toast with jam and a boiled egg", "global", ["pre", "snack"], [_p("C", ["bread_white", "rice_cake", "bread_whole"], 80, 30, 200), _p("P", ["egg_boiled", "yogurt_greek", "cottage_cheese"], 60, 0, 200), _p("X", ["jam", "honey"], 20), _p("V", ["banana", "orange"], 100)]),
    _t("Chickpea and potato curry-style plate", "global", ["lunch", "dinner"], [_p("P", ["chickpeas", "lentils", "tofu_firm", "chicken_thigh"], 170, 80, 350), _p("C", ["rice_white", "naan", "potato", "rice_brown"], 200, 80, 420), _p("F", ["coconut_milk", "olive_oil", "canola_oil"], 25, 0, 70), _p("V", ["spinach", "cauliflower", "tomato", "onion"], 150)]),
]

SLOT_SHARES = {
    3: [("breakfast", 0.30), ("lunch", 0.35), ("dinner", 0.35)],
    4: [("breakfast", 0.25), ("lunch", 0.30), ("snack", 0.15), ("dinner", 0.30)],
    5: [("breakfast", 0.22), ("snack", 0.10), ("lunch", 0.28), ("snack", 0.10), ("dinner", 0.30)],
    6: [("breakfast", 0.20), ("snack", 0.10), ("lunch", 0.25), ("snack", 0.10), ("dinner", 0.25), ("snack", 0.10)],
}


def _solve3(A, b):
    """Gaussian elimination, 3 x 3 (A rows = macro, columns = scalable part)."""
    n = len(b)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(M[r][c]))
        if abs(M[piv][c]) < 1e-9:
            return None
        M[c], M[piv] = M[piv], M[c]
        for r in range(n):
            if r != c:
                f = M[r][c] / M[c][c]
                M[r] = [x - f * y for x, y in zip(M[r], M[c])]
    return [M[i][n] / M[i][i] for i in range(n)]


def build_meal(template, foods, target, rot=0, scale_fixed=1.0):
    """Fill one meal template to a target {kcal, protein, carb, fat}. Picks, for each part, an allowed food (rotating by `rot`), then solves the grams of the
    protein, carbohydrate and fat sources so the meal hits the target, within each part's min/max. Returns {items, totals, miss} or None if a part has no allowed food."""
    chosen = []
    for k, part in enumerate(template["parts"]):
        opts = [o for o in part["opts"] if o in foods]
        if not opts:
            if part["role"] in ("P", "C"):
                return None
            continue                                  # an optional fat or vegetable part with nothing allowed is dropped
        chosen.append((part, foods[opts[(rot + k) % len(opts)]]))
    fixed = {"protein": 0.0, "carb": 0.0, "fat": 0.0, "kcal": 0.0}
    scal = []
    items = []
    for part, f in chosen:
        if part["role"] in ("V", "X"):
            g = part["g"] * scale_fixed
            m = macros(f, g)
            for k in fixed:
                fixed[k] += m[k]
            items.append({"food": f, "g": g, "role": part["role"]})
        else:
            scal.append((part, f))
            items.append({"food": f, "g": part["g"], "role": part["role"]})
    # solve for the scalable parts on (protein, carb, fat); with fewer than 3 scalable parts, solve least-squares on the macros we can control
    names = ("protein", "carb", "fat")
    want = {k: target[k] - fixed[k] for k in names}
    fr = {id(p): None for p, _ in scal}
    cols = [[f["per100g"][n] / 100.0 for n in names] for _, f in scal]
    roles = [p["role"] for p, _ in scal]
    x = [p["g"] for p, _ in scal]
    # the role decides which macro each part is responsible for: P -> protein, C -> carb, F -> fat
    resp = {"P": 0, "C": 1, "F": 2}
    free = list(range(len(scal)))
    fixed_g = {}
    for _ in range(4):
        idx = [i for i in free]
        rows = sorted({resp[roles[i]] for i in idx})
        if not idx:
            break
        A = [[cols[i][r] for i in idx] for r in rows]
        # remaining target for the macros these parts own, after the already-clamped parts
        b = [want[names[r]] - sum(cols[j][r] * g for j, g in fixed_g.items()) for r in rows]
        # parts own one macro each, but they also add the other macros; solve the square system when sizes match, else scale each part for its own macro
        if len(rows) == len(idx):
            sol = _solve3(A, b) if len(idx) == 3 else _small(A, b)
        else:
            sol = None
        if sol is None:
            sol = [max(0.0, (want[names[resp[roles[i]]]] - sum(cols[j][resp[roles[i]]] * g for j, g in fixed_g.items())) / max(cols[i][resp[roles[i]]], 1e-6)) for i in idx]
        clamped = False
        for pos, i in enumerate(idx):
            lo, hi = scal[i][0]["min"], scal[i][0]["max"]
            g = sol[pos]
            if g < lo or g > hi:
                fixed_g[i] = min(max(g, lo), hi)
                free.remove(i)
                clamped = True
            else:
                x[i] = g
        if not clamped:
            break
    for i, g in fixed_g.items():
        x[i] = g
    n = 0
    for it in items:
        if it["role"] in ("P", "C", "F"):
            it["g"] = max(0.0, x[n]); n += 1
    tot = {k: 0.0 for k in ("kcal", "protein", "carb", "fat", "fiber")}
    for it in items:
        m = macros(it["food"], it["g"])
        it["m"] = m
        for k in tot:
            tot[k] += m[k]
    miss = {k: tot[k] - target[k] for k in ("kcal", "protein", "carb", "fat")}
    return {"template": template, "items": items, "totals": tot, "miss": miss}


def _small(A, b):
    n = len(b)
    if n == 1:
        return [b[0] / A[0][0]] if abs(A[0][0]) > 1e-9 else None
    if n == 2:
        det = A[0][0] * A[1][1] - A[0][1] * A[1][0]
        if abs(det) < 1e-9:
            return None
        return [(b[0] * A[1][1] - A[0][1] * b[1]) / det, (A[0][0] * b[1] - b[0] * A[1][0]) / det]
    return None


def meal_score(res, target):
    if not res:
        return 1e9
    m = res["miss"]
    return abs(m["kcal"]) / max(target["kcal"], 1) * 100 + abs(m["protein"]) / max(target["protein"], 1) * 60 + abs(m["carb"]) / max(target["carb"], 1) * 25 + abs(m["fat"]) / max(target["fat"], 1) * 25


def slot_split(day, n_meals, session=None, kg=70):
    """Split a day's targets over the meals. session = {"start": hour (0-24), "hours": h} puts more carbohydrate in the meal 1-3 h before and the first meal after.
    Protein is spread evenly (Schoenfeld 2018, Iraki 2019: about 0.4-0.55 g/kg per meal over 3-6 meals, Jager 2017: 20-40 g, 0.25 g/kg)."""
    shares = SLOT_SHARES[n_meals]
    slots = [s for s, _ in shares]
    kc = [w for _, w in shares]
    cw = list(kc)
    roles = ["" for _ in slots]
    if session and session.get("hours", 0) >= 1.0:
        times = _meal_times(slots)
        st = session["start"]
        pre = max((i for i, t in enumerate(times) if t <= st - 1.0), default=None)       # the last meal at least 1 h before
        post = min((i for i, t in enumerate(times) if t >= st + session["hours"]), default=None)
        if pre is not None:
            cw[pre] *= 1.5; roles[pre] = "pre"
        if post is not None:
            cw[post] *= 1.4; roles[post] = "post"
    s = sum(cw)
    cw = [w / s for w in cw]
    P = day["P"] / n_meals
    out = []
    for i, sl in enumerate(slots):
        C = day["C"] * cw[i]
        F = day["F"] * kc[i] * (0.6 if roles[i] == "pre" else 1.0)
        out.append({"slot": sl, "role": roles[i], "protein": P, "carb": C, "fat": F})
    # re-balance fat so the day total still matches
    ft = sum(o["fat"] for o in out)
    for o in out:
        o["fat"] = o["fat"] * day["F"] / ft if ft else 0
        o["kcal"] = 4 * o["protein"] + 4 * o["carb"] + 9 * o["fat"]
    return out


def _meal_times(slots):
    base = {"breakfast": 7.5, "lunch": 12.5, "dinner": 19.0}
    t, snack_n = [], 0
    snack_times = [10.0, 16.0, 21.0]
    for s in slots:
        if s == "snack":
            t.append(snack_times[snack_n % 3]); snack_n += 1
        else:
            t.append(base[s])
    if slots.count("snack") == 1:                  # one snack sits mid-afternoon
        t[slots.index("snack")] = 16.0
    return t


def plan_day(day, foods, n_meals, cuisine, used, session=None, kg=70, offset=0):
    split = slot_split(day, n_meals, session, kg)
    cu = "id" if cuisine in ("seasian", "id") else cuisine
    meals = []
    for tgt in split:
        slot = tgt["slot"]
        want = {"kcal": tgt["kcal"], "protein": tgt["protein"], "carb": tgt["carb"], "fat": tgt["fat"]}
        pool = [t for t in TEMPLATES if slot in t["slots"] and (cu == "mixed" or t["cuisine"] in (cu, "global"))]
        pref = tgt["role"] if slot == "snack" and tgt["role"] else None
        best = None
        for t in pool:
            for rot in range(3):
                res = build_meal(t, foods, want, rot=rot + offset)
                if not res:
                    continue
                sc = meal_score(res, want) + 6 * used.get(t["name"], 0) - (4 if pref and pref in t["slots"] else 0) - (3 if cu == "id" and t["cuisine"] == "id" else 0)
                if best is None or sc < best[0]:
                    best = (sc, res, t["name"])
        if best is None:
            meals.append({"slot": slot, "role": tgt["role"], "target": want, "result": None})
            continue
        used[best[2]] = used.get(best[2], 0) + 1
        meals.append({"slot": slot, "role": tgt["role"], "target": want, "result": best[1]})
    return meals


def day_totals(meals):
    tot = {k: 0.0 for k in ("kcal", "protein", "carb", "fat", "fiber")}
    for m in meals:
        if m["result"]:
            for k in tot:
                tot[k] += m["result"]["totals"][k]
    return tot


def unit_text(food, g):
    u = food.get("unit")
    if u and u.get("g"):
        n = g / u["g"]
        return f"{n:.1f} x {u['label'].replace('1 ', '', 1)}" if n >= 0.25 else ""
    return ""
