import os
import json
import re
import requests
from pathlib import Path

# ===============================
# CONFIG
# ===============================
EXTRACT_ROOT = "updated_extracted"
IMAGE_DIR = "test_images"
POPUP_DIR = "test_popup_images"
OUTPUT_JSON = "recipes_fix.json"

SMARTSHEET_TOKEN = "7xcmOm3neR6SXBXda7fY9qis3Bg9z9VsBZ6T6"
SMARTSHEET_SHEET_ID = "7220178429366148"

SMARTSHEET_HEADERS = {
    "Authorization": f"Bearer {SMARTSHEET_TOKEN}",
    "Content-Type": "application/json"
}

# 🔒 PROTECTED FIELDS — these are NEVER overwritten if already present in existing JSON
PROTECTED_FIELDS = {"hidden", "clubbedWith"}


# ===============================
# HELPERS
# ===============================

def safe_int(val, default=0):
    try:
        return int(val)
    except:
        return default


def clean_line(text):
    return text.replace(":", "").replace("-", "").strip()


def normalize_minutes(text):
    text = text.upper().strip()
    match = re.search(r"(\d+)", text)
    if not match:
        return ""
    return f"{match.group(1)} mins"


# ===============================
# 🔒 LOAD EXISTING JSON (for protected field preservation)
# ===============================

def load_existing_recipes(path):
    """
    Returns a dict keyed by Recipe Name (uppercase) → existing recipe dict.
    Used to restore protected fields (hidden, clubbedWith) after a regeneration.
    """
    if not os.path.exists(path):
        return {}

    with open(path, "r", encoding="utf-8") as f:
        try:
            existing = json.load(f)
        except json.JSONDecodeError:
            print(f"⚠ Could not parse existing {path}, starting fresh.")
            return {}

    lookup = {}
    for entry in existing:
        name = entry.get("Recipe Name", "").strip().upper()
        if name:
            lookup[name] = entry

    print(f"🔒 Loaded {len(lookup)} existing entries for protected-field preservation")
    return lookup


# ===============================
# SMARTSHEET LOGIC
# ===============================

def load_smartsheet_data():
    print("📡 Fetching Smartsheet data...")

    url = f"https://api.smartsheet.com/2.0/sheets/{SMARTSHEET_SHEET_ID}"
    response = requests.get(url, headers=SMARTSHEET_HEADERS)

    if response.status_code != 200:
        raise Exception(f"Smartsheet API error: {response.status_code} - {response.text}")

    sheet = response.json()

    column_map = {col["id"]: col["title"] for col in sheet["columns"]}

    lookup = {}

    for row in sheet["rows"]:
        row_data = {}
        recipe_name = None

        for cell in row["cells"]:
            col_name = column_map.get(cell["columnId"])
            value = cell.get("value", "")

            if col_name == "Recipe Name":
                recipe_name = str(value).strip().upper()
            elif col_name in ["Veg/Non Veg", "Cooking Mode", "Cuisine", "Category"]:
                row_data[col_name] = str(value).strip().upper()

        if recipe_name:
            lookup[recipe_name] = row_data

    print(f"✅ Loaded {len(lookup)} recipes from Smartsheet")
    return lookup


# ===============================
# TXT PARSER
# ===============================

def parse_recipe_txt(txt_path):
    with open(txt_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    recipe_name = data.get("name", [""])[0].strip().upper()
    original_name = recipe_name

    ingredients = [ing.get("app_audio", "").strip() for ing in data.get("Ingredients", [])]

    total_on2cook_time_sec = sum(safe_int(step.get("durationInSec", 0)) for step in data.get("Instruction", []))
    total_on2cook_time_min = max(1, round(total_on2cook_time_sec / 60))

    description = data.get("description", "")
    desc_upper = description.upper()

    # -----------------------------
    # Final Output
    # -----------------------------
    total_output = ""
    if "FINAL OUTPUT" in desc_upper:
        try:
            total_output = clean_line(desc_upper.split("FINAL OUTPUT")[1].split("\n")[0])
        except:
            pass
    elif "OUTPUT" in desc_upper:
        try:
            total_output = clean_line(desc_upper.split("OUTPUT")[1].split("\n")[0])
        except:
            pass

    # -----------------------------
    # Accessories
    # -----------------------------
    accessories = ""
    if "ACCESSORIES" in desc_upper:
        try:
            part = description.split("ACCESSORIES", 1)[1]
            acc_list = []

            stop_keywords = [
                "FINAL OUTPUT", "OUTPUT", "NORMAL COOKING TIME", "NORMAL TIME",
                "OTHER ESSENTIALS", "INGREDIENTS", "NOTE", "SPECIAL INSTRUCTION", "KEY TIPS",
                "TRANSFER WARM DOUGH TO A GREASED PLATE; KNEAD BRIEFLY INTO A SMOOTH BALL WHILE STILL HOT. ROLL BETWEEN GREASED PARCHMENT PAPERS TO 3–5MM THICK; COOL",
                "THEN CUT INTO DIAMONDS. APPLY SILVER LEAF IF DESIRED. LET SET 15 MINUTES",
                "STIRRER NOT REQUIRED", "SIEVE & GARNISH", "SHREDDED CHICKEN 100 G",
                "RICE NOODLES 100 G", "SOUP STOCK 200 G", "(FIRST", " ADD GHEE AND SPICES",
                "FOLLOWED BY THE MARINATED CHICKEN. THEN, INCORPORATE THE SOAKED RICE),TAKE A PORTION OF THE MIXTURE (50G) AND MOLD IT EVENLY AROUND THE SKEWERS",
                "PRESSING GENTLY TO ENSURE IT ADHERES WELL."
            ]

            for line in part.splitlines():
                line = line.strip()
                if not line:
                    continue

                upper = line.upper()
                if any(keyword in upper for keyword in stop_keywords):
                    break

                acc_list.append(line.title())

            accessories = ", ".join(acc_list)

        except:
            pass

    # -----------------------------
    # Normal Cooking Time
    # -----------------------------
    normal_cooking_time = ""
    if "NORMAL COOKING TIME" in desc_upper:
        try:
            raw = clean_line(desc_upper.split("NORMAL COOKING TIME")[1].split("\n")[0])
            normal_cooking_time = normalize_minutes(raw)
        except:
            pass
    elif "NORMAL TIME" in desc_upper:
        try:
            raw = clean_line(desc_upper.split("NORMAL TIME")[1].split("\n")[0])
            normal_cooking_time = normalize_minutes(raw)
        except:
            pass

    recipe = {
        "Recipe Name": recipe_name,
        "Veg/Non Veg": "VEG",
        "Cooking Mode": "AUTO",
        "Cuisine": "GLOBAL CUISINE",
        "Category": "MAIN COURSE",
        "Cooking Time": total_on2cook_time_min,
        "Image": "",
        "PopupImage": "",
        "Ingredients": ingredients,
        "Accessories": accessories,
        "Total Output": total_output,
        "On2Cook Cooking Time": f"{total_on2cook_time_min}",
        "Normal Cooking Time": normal_cooking_time,
        "description": description,  # keep temporarily for fallback matching
        "_original_name": original_name
    }

    return recipe


# ===============================
# MAIN GENERATOR
# ===============================

def generate_recipes_json():
    recipes = []
    Path(POPUP_DIR).mkdir(exist_ok=True)

    # 🔒 Load existing JSON first so we can restore protected fields later
    existing_map = load_existing_recipes(OUTPUT_JSON)

    smartsheet_map = load_smartsheet_data()

    for recipe_key in os.listdir(EXTRACT_ROOT):
        recipe_dir = os.path.join(EXTRACT_ROOT, recipe_key)
        if not os.path.isdir(recipe_dir):
            continue

        txt_file = next((f for f in os.listdir(recipe_dir) if f.lower().endswith(".txt")), None)
        if not txt_file:
            print(f"⚠ No TXT file in {recipe_key}")
            continue

        recipe = parse_recipe_txt(os.path.join(recipe_dir, txt_file))

        name = recipe["Recipe Name"]
        original_name = recipe["_original_name"]

        matched_name = None

        # 1️⃣ Try matching JSON name first
        if name in smartsheet_map:
            matched_name = name
            print(f"✅ Matched using JSON name: {name}")

        else:
            # 2️⃣ Try description first line
            description = recipe.get("description", "")
            if description:
                first_line = description.strip().split("\n")[0].strip().upper()
                metadata_keywords = ["NORMAL COOKING TIME", "NORMAL TIME", "FINAL OUTPUT", "OUTPUT", "ACCESSORIES"]

                if first_line and not any(first_line.startswith(k) for k in metadata_keywords):
                    if first_line in smartsheet_map:
                        matched_name = first_line
                        recipe["Recipe Name"] = first_line
                        print(f"🔁 Matched using description name: {first_line}")

        # Apply Smartsheet overrides if matched
        if matched_name:
            ss = smartsheet_map[matched_name]
            for field in ["Veg/Non Veg", "Cooking Mode", "Cuisine", "Category"]:
                recipe[field] = ss.get(field, recipe[field])
        else:
            print(f"⚠ No Smartsheet match for {name}")

        popup_name = original_name.replace("/", "_").replace("\\", "_")

        recipe["Image"] = f"{IMAGE_DIR}/{recipe_key}.jpg"
        recipe["PopupImage"] = f"{POPUP_DIR}/{popup_name}.pdf"

        recipe.pop("_original_name", None)
        recipe.pop("description", None)

        # 🔒 RESTORE PROTECTED FIELDS from the existing JSON entry (if any)
        # We check both the current Recipe Name and original_name since it may have
        # been remapped via description matching above.
        existing_entry = existing_map.get(recipe["Recipe Name"].upper()) or existing_map.get(original_name.upper())
        if existing_entry:
            for field in PROTECTED_FIELDS:
                if field in existing_entry:
                    recipe[field] = existing_entry[field]
                    print(f"🔒 Preserved '{field}' for {recipe['Recipe Name']}: {existing_entry[field]}")

        recipes.append(recipe)
        print(f"🍽 Parsed: {recipe['Recipe Name']}")

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(recipes, f, indent=2, ensure_ascii=False)

    print(f"\n✅ {len(recipes)} recipes written to {OUTPUT_JSON}")
    print("📡 Smartsheet is the master for:")
    print("   - Veg/Non Veg")
    print("   - Cooking Mode")
    print("   - Cuisine")
    print("   - Category")
    print("🔒 Protected fields (never overwritten):")
    print("   - hidden")
    print("   - clubbedWith")


if __name__ == "__main__":
    generate_recipes_json()