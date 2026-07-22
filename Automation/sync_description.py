#!/usr/bin/env python3
"""
sync_description.py

1. Reads recipes_fix.json — finds entries with Cooking Mode == AUTO and no 'hidden' field
2. For each, extracts zip stem from the Image path
3. Looks up which Smartsheet row that zip is attached to → gets the Recipe Name
4. Opens updated_extracted/<zip_stem>/<file>.txt → replaces the first non-empty
   line of the 'description' field with the Smartsheet Recipe Name → saves it

That's it. No re-running other scripts, no patching anything.

Usage:
  python sync_description.py
"""

import os
import json
import requests
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
RECIPES_JSON      = "../recipes_fix.json"
UPDATED_EXTRACTED = "../updated_extracted"

SMARTSHEET_TOKEN    = os.environ["SMARTSHEET_TOKEN"]
SMARTSHEET_SHEET_ID = os.environ["SMARTSHEET_SHEET_ID"]
SMARTSHEET_HEADERS  = {
    "Authorization": f"Bearer {SMARTSHEET_TOKEN}",
    "Content-Type":  "application/json",
}


# ── Smartsheet ────────────────────────────────────────────────────────────────

def fetch_zip_to_recipe_name() -> dict:
    """Returns {zip_stem_upper: recipe_name_original_case}"""

    print("📡 Fetching Smartsheet sheet...")
    resp = requests.get(
        f"https://api.smartsheet.com/2.0/sheets/{SMARTSHEET_SHEET_ID}",
        headers=SMARTSHEET_HEADERS,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Sheet fetch failed: {resp.status_code} – {resp.text}")

    sheet   = resp.json()
    col_map = {col["id"]: col["title"] for col in sheet["columns"]}

    row_to_recipe = {}
    for row in sheet["rows"]:
        for cell in row["cells"]:
            if col_map.get(cell["columnId"]) == "Recipe Name":
                val = str(cell.get("value", "")).strip()
                if val:
                    row_to_recipe[str(row["id"])] = val
                break

    print(f"   → {len(row_to_recipe)} rows with Recipe Name")

    print("📡 Fetching Smartsheet attachments...")
    resp = requests.get(
        f"https://api.smartsheet.com/2.0/sheets/{SMARTSHEET_SHEET_ID}/attachments",
        headers=SMARTSHEET_HEADERS,
        params={"includeAll": "true"},
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Attachments fetch failed: {resp.status_code} – {resp.text}")

    zip_to_recipe = {}
    for att in resp.json().get("data", []):
        if att.get("parentType") != "ROW":
            continue
        name = att.get("name", "")
        if not name.lower().endswith(".zip"):
            continue
        stem      = Path(name).stem.strip().upper()
        row_id    = str(att.get("parentId", ""))
        recipe    = row_to_recipe.get(row_id)
        if recipe:
            zip_to_recipe[stem] = recipe

    print(f"   → {len(zip_to_recipe)} zip→recipe mappings built")
    return zip_to_recipe


# ── txt helpers ───────────────────────────────────────────────────────────────

def find_txt_file(zip_stem: str) -> str | None:
    """Case-insensitive search for the txt file inside updated_extracted/<zip_stem>/"""
    base = UPDATED_EXTRACTED

    # Try exact match first, then case-insensitive
    folder = os.path.join(base, zip_stem)
    if not os.path.isdir(folder):
        try:
            for entry in os.listdir(base):
                if entry.upper() == zip_stem:
                    folder = os.path.join(base, entry)
                    break
            else:
                return None
        except FileNotFoundError:
            return None

    for f in os.listdir(folder):
        if f.lower().endswith(".txt"):
            return os.path.join(folder, f)
    return None


def replace_description_first_line(txt_path: str, new_name: str) -> tuple[bool, str, str]:
    """
    Loads the JSON txt file, replaces the first non-empty line of 'description'
    with new_name, saves it back.

    Returns (changed: bool, old_first_line: str, new_first_line: str)
    """
    with open(txt_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    description = data.get("description", "")
    if not description:
        return False, "", new_name

    lines = description.split("\n")
    first_idx = next((i for i, l in enumerate(lines) if l.strip()), None)
    if first_idx is None:
        return False, "", new_name

    old_first = lines[first_idx].strip()

    if old_first == new_name:
        return False, old_first, new_name   # already correct, no write needed

    lines[first_idx] = new_name
    data["description"] = "\n".join(lines)

    with open(txt_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return True, old_first, new_name


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  fix_description_names.py")
    print("=" * 60)

    # 1. Load recipes_fix.json
    with open(RECIPES_JSON, "r", encoding="utf-8") as f:
        recipes = json.load(f)

    targets = [
        r for r in recipes
        if r.get("Cooking Mode", "").upper() == "AUTO"
        and (
            "hidden" not in r
            or r.get("hiddenReason") == "not needed anymore"
        )
    ]
    print(f"\n📋 {len(targets)} recipe(s) eligible for sync "
          f"(no 'hidden' field, or auto-hidden as 'not needed anymore')")

    if not targets:
        print("Nothing to do.")
        return

    # 2. Fetch Smartsheet mappings
    zip_to_recipe = fetch_zip_to_recipe_name()

    # 3. Process each target
    print(f"\n{'─'*60}")
    fixed      = []
    already_ok = []
    no_match   = []
    no_file    = []

    for entry in targets:
        image_path = entry.get("Image", "")
        if not image_path:
            no_match.append("(no Image field)")
            continue

        zip_stem = Path(image_path).stem.strip().upper()
        recipe_name = zip_to_recipe.get(zip_stem)

        if not recipe_name:
            print(f"  ⚠  No Smartsheet match:  {zip_stem}")
            no_match.append(zip_stem)
            continue

        txt_path = find_txt_file(zip_stem)
        if not txt_path:
            print(f"  ⚠  txt file not found:   {zip_stem}")
            no_file.append(zip_stem)
            continue

        changed, old, new = replace_description_first_line(txt_path, recipe_name)

        if changed:
            print(f"  ✅ Fixed:  {zip_stem}")
            print(f"       was: {old}")
            print(f"       now: {new}")
            fixed.append(zip_stem)
        else:
            print(f"  ✔  Already correct: {zip_stem}  →  {new}")
            already_ok.append(zip_stem)

    # 4. Summary
    print(f"\n{'═'*60}")
    print(f"  Summary")
    print(f"{'═'*60}")
    print(f"  Fixed        : {len(fixed)}")
    print(f"  Already OK   : {len(already_ok)}")
    print(f"  No SS match  : {len(no_match)}")
    print(f"  File missing : {len(no_file)}")
    print(f"{'═'*60}")


if __name__ == "__main__":
    main()