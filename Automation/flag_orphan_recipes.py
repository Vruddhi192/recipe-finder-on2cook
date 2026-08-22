#!/usr/bin/env python3
"""
flag_orphan_recipes.py

Final pipeline step. Reads the finished recipes_fix.json (after
sync_description has already fixed any stale description names, and
parse_to_json has re-run to pick that up) and flags any recipe still
orphaned as hidden.

Orphan logic (updated):

  The ZIP-stem check is the PRIMARY trigger. The Recipe Name check is a
  CROSS-CHECK, not an independent trigger — a recipe is only auto-hidden
  when BOTH signals agree it's orphaned. This avoids false positives where
  a Recipe Name was edited/retyped slightly differently on Smartsheet
  (extra space, renamed dish, punctuation) but the ZIP itself is still
  validly attached — that recipe should NOT be hidden just because of a
  name mismatch.

  1. ZIP-stem check (primary): the recipe's own ZIP is no longer attached
     to ANY row on Smartsheet at all. This is what catches the common
     duplicate scenario — a recipe gets re-uploaded under a new ZIP
     filename (same dish name), a new folder gets extracted for the new
     stem, but the OLD folder is never deleted. The old folder's internal
     name still equals the (unchanged) Smartsheet Recipe Name, so the
     name-based check alone would wave it through as "matched" — two
     entries, same name, both visible. Comparing zip stems directly closes
     that gap regardless of what the name says.

  2. Recipe Name check (cross-check): the recipe's final Recipe Name has
     no matching row at all. Used to CONFIRM a zip-orphan finding (both
     must agree to hide). If a recipe has no Image path at all (so the zip
     check can't run), the name check is used alone as a fallback safety
     net.

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
    hiddenReason="not needed anymore" if:

      - its own ZIP is no longer attached to any Smartsheet row AND its
        Recipe Name also has no matching row (both must agree), OR
      - it has no Image path at all (zip check can't run) AND its Recipe
        Name has no matching row (name-only fallback),

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

    stem_to_row_id  = download_zips.get_zip_stem_to_row_id()
    valid_zip_stems = set(stem_to_row_id.keys())
    row_id_to_stem  = {v: k for k, v in stem_to_row_id.items()}

    smartsheet_map   = load_smartsheet_data()
    smartsheet_names = set(smartsheet_map.keys())

    # For every Smartsheet row, find the ONE zip stem currently attached to
    # it. This is the piece the old logic was missing: "does this Recipe
    # Name exist somewhere in Smartsheet" is a different question from
    # "does this Recipe Name's row currently own THIS recipe's zip." A
    # re-uploaded dish keeps the same name on a NEW row/zip, so the old
    # name-only check always passed for both the stale and current entry.
    name_to_current_stem = {
        name: row_id_to_stem[row_data["_row_id"]]
        for name, row_data in smartsheet_map.items()
        if row_data.get("_row_id") in row_id_to_stem
    }

    newly_flagged = 0

    for recipe in recipes:
        if "hidden" in recipe:
            # Already has a hidden value (manual or previously auto-set) — leave it alone.
            continue

        name = recipe.get("Recipe Name", "").strip().upper()
        recipe_key = _recipe_key_from_image_path(recipe.get("Image", ""))

        has_image      = bool(recipe_key)
        zip_is_orphan  = has_image and recipe_key not in valid_zip_stems
        name_is_orphan = name not in smartsheet_names

        current_stem_for_name = name_to_current_stem.get(name)
        is_stale_duplicate = (
            has_image
            and current_stem_for_name is not None
            and recipe_key != current_stem_for_name
        )

        should_hide = False
        reason = ""

        if is_stale_duplicate:
            # This entry's own zip is not the one currently attached to
            # this Recipe Name's row anymore — a newer zip superseded it.
            # Fires even though the Recipe Name still "exists" in Smartsheet.
            should_hide = True
            reason = "superseded by a newer ZIP under the same Recipe Name"
        elif has_image:
            # ZIP check is the trigger, name check is a cross-check.
            # Both must agree before we hide anything.
            if zip_is_orphan and name_is_orphan:
                should_hide = True
                reason = "ZIP gone from Smartsheet + no Recipe Name match"
        else:
            # No image path, so the zip check can't run at all —
            # fall back to the name check alone as a safety net.
            if name_is_orphan:
                should_hide = True
                reason = "no image path, no Recipe Name match"

        if should_hide:
            recipe["hidden"] = True
            recipe["hiddenReason"] = NO_SMARTSHEET_MATCH_REASON
            newly_flagged += 1
            print(f"🚫 Auto-hidden ({reason}): {name} [{recipe_key or 'no image path'}]")

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(recipes, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Orphan check complete: {newly_flagged} recipe(s) newly flagged as hidden")
    print(f"   (hidden only when BOTH the ZIP-stem check and Recipe Name check agree, "
          f"or when there's no image path at all)")
    print(f"   hiddenReason = '{NO_SMARTSHEET_MATCH_REASON}'")
    print(f"   Recipes with a pre-existing 'hidden' value were left untouched.")

    return newly_flagged


if __name__ == "__main__":
    flag_orphan_recipes()