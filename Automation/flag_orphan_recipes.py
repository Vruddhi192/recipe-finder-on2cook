#!/usr/bin/env python3
"""
flag_orphan_recipes.py

Final pipeline step. Reads the finished recipes_fix.json (after
sync_description has already fixed any stale description names, and
parse_to_json has re-run to pick that up) and flags any recipe still
orphaned as hidden.

Two independent orphan checks, either one is enough to hide a recipe:

  1. ZIP-stem check (primary): the recipe's own ZIP is no longer attached
     to ANY row on Smartsheet at all. This is what catches the common
     duplicate scenario — a recipe gets re-uploaded under a new ZIP
     filename (same dish name), a new folder gets extracted for the new
     stem, but the OLD folder is never deleted. The old folder's internal
     name still equals the (unchanged) Smartsheet Recipe Name, so the
     name-based check alone would wave it through as "matched" — two
     entries, same name, both visible. Comparing zip stems directly closes
     that gap regardless of what the name says.

  2. Recipe Name check (secondary/fallback): the recipe's final Recipe
     Name has no matching row at all. Kept as a safety net for any entry
     where the stem can't be recovered from its Image path.

This must run LAST, after sync_description + the final parse_to_json
re-run — never before. If it ran earlier, a recipe whose description name
hadn't been synced yet would look like an orphan and get wrongly hidden,
even though it actually has a Smartsheet match under its corrected name.

Usage:
  python flag_orphan_recipes.py
"""

import json
from pathlib import Path

import download_zips
from parse_txt_to_json import (
    OUTPUT_JSON,
    IMAGE_DIR,
    PROTECTED_FIELDS,
    load_smartsheet_data,
)

NO_SMARTSHEET_MATCH_REASON = "not needed anymore"


def _recipe_key_from_image_path(image_path: str) -> str:
    """
    recipes_fix.json doesn't store the recipe's zip stem directly, but
    parse_txt_to_json.py always writes Image as f"{IMAGE_DIR}/{recipe_key}.jpg"
    — so the stem of the Image path IS the recipe_key (== zip stem).
    """
    if not image_path:
        return ""
    return Path(image_path).stem.upper()


def flag_orphan_recipes() -> int:
    """
    Loads OUTPUT_JSON, flags any recipe as hidden=true /
    hiddenReason="not needed anymore" if EITHER:
      - its own ZIP is no longer attached to any Smartsheet row, or
      - its Recipe Name has no matching row at all,
    UNLESS it already has a 'hidden' value (manual or previously
    auto-set), which is left untouched.

    Returns:
        Number of recipes newly flagged this run.
    """
    if not Path(OUTPUT_JSON).exists():
        print(f"⚠ {OUTPUT_JSON} not found — nothing to flag.")
        return 0

    with open(OUTPUT_JSON, "r", encoding="utf-8") as f:
        recipes = json.load(f)

    valid_zip_stems = set(download_zips.get_zip_stem_to_row_id().keys())
    smartsheet_map  = load_smartsheet_data()
    smartsheet_names = set(smartsheet_map.keys())

    newly_flagged = 0

    for recipe in recipes:
        if "hidden" in recipe:
            # Already has a hidden value (manual or previously auto-set) — leave it alone.
            continue

        name = recipe.get("Recipe Name", "").strip().upper()
        recipe_key = _recipe_key_from_image_path(recipe.get("Image", ""))

        zip_is_orphan  = bool(recipe_key) and recipe_key not in valid_zip_stems
        name_is_orphan = name not in smartsheet_names

        if zip_is_orphan or name_is_orphan:
            recipe["hidden"] = True
            recipe["hiddenReason"] = NO_SMARTSHEET_MATCH_REASON
            newly_flagged += 1
            reason = "ZIP no longer on Smartsheet" if zip_is_orphan else "no Recipe Name match"
            print(f"🚫 Auto-hidden ({reason}): {name} [{recipe_key or 'no image path'}]")

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(recipes, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Orphan check complete: {newly_flagged} recipe(s) newly flagged as hidden")
    print(f"   (hidden = {{recipe's ZIP is gone from Smartsheet, or its name has no match}}, "
          f"hiddenReason = '{NO_SMARTSHEET_MATCH_REASON}')")
    print(f"   Recipes with a pre-existing 'hidden' value were left untouched.")

    return newly_flagged


if __name__ == "__main__":
    flag_orphan_recipes()
