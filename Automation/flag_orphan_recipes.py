#!/usr/bin/env python3
"""
flag_orphan_recipes.py

Final pipeline step. Reads the finished recipes_fix.json (after
sync_description has already fixed any stale description names, and
parse_to_json has re-run to pick that up) and flags any recipe still
orphaned as hidden.

Orphan logic:

  The ZIP-stem check is the PRIMARY trigger. The Recipe Name check is a
  CROSS-CHECK, not an independent trigger — a recipe is only auto-hidden
  when BOTH signals agree it's orphaned. This avoids false positives where
  a Recipe Name was edited/retyped slightly differently on Smartsheet
  (extra space, renamed dish, punctuation) but the ZIP itself is still
  validly attached — that recipe should NOT be hidden just because of a
  name mismatch.

  1. ZIP-stem check (primary): the recipe's own ZIP is no longer attached
     to ANY row on Smartsheet at all.

  2. Recipe Name check (cross-check): the recipe's final Recipe Name has
     no matching row at all. Used to CONFIRM a zip-orphan finding (both
     must agree to hide). If a recipe has no Image path at all (so the zip
     check can't run), the name check is used alone as a fallback safety
     net.

  3. In-file duplicate check (separate, narrowly scoped): catches the
     "re-uploaded under a new ZIP, old folder never deleted" scenario —
     TWO entries with the exact same Recipe Name already sitting side by
     side in THIS SAME recipes_fix.json. Only fires within such a group.
     Of the group, whichever entry's zip stem is currently a valid
     Smartsheet attachment is kept; the other(s) are hidden. If the group
     is ambiguous (none or more than one member currently valid), nothing
     is auto-hidden — it's printed as NEEDS MANUAL REVIEW instead.

     IMPORTANT: this check never runs against singleton recipes (only one
     entry with that name in the file). A previous version of this script
     compared every recipe's Image-stem against a Smartsheet-wide
     name→stem map and mass-hid ~200 recipes because that stem comparison
     is not resilient to minor filename formatting differences unrelated
     to actual duplication. Do not reintroduce that pattern — any
     comparison broad enough to span the whole file is too risky to run
     unattended. Duplicates must be found locally, inside this file, first.

This must run LAST, after sync_description + the final parse_to_json
re-run — never before. If it ran earlier, a recipe whose description name
hadn't been synced yet would look like an orphan and get wrongly hidden,
even though it actually has a Smartsheet match under its corrected name.

Usage:
  python flag_orphan_recipes.py             # dry run — prints what WOULD change, writes nothing
  python flag_orphan_recipes.py --apply      # actually writes hidden/hiddenReason to OUTPUT_JSON
"""

import sys
import json
import shutil
from datetime import datetime
from pathlib import Path
from collections import defaultdict

import download_zips
from parse_txt_to_json import (
    OUTPUT_JSON,
    IMAGE_DIR,
    PROTECTED_FIELDS,
    load_smartsheet_data,
)

NO_SMARTSHEET_MATCH_REASON = "not needed anymore"
DUPLICATE_SUPERSEDED_REASON = "superseded by newer ZIP under same Recipe Name"


def _recipe_key_from_image_path(image_path: str) -> str:
    """
    recipes_fix.json doesn't store the recipe's zip stem directly, but
    parse_txt_to_json.py always writes Image as f"{IMAGE_DIR}/{recipe_key}.jpg"
    — so the stem of the Image path IS the recipe_key (== zip stem).
    """
    if not image_path:
        return ""
    return Path(image_path).stem.upper()


def _find_in_file_duplicate_groups(recipes):
    """
    Groups recipe indices by exact Recipe Name (upper/stripped), restricted
    to names that appear MORE THAN ONCE in this file. This is a purely
    local, in-file grouping — no Smartsheet data involved — so it can never
    mislabel a singleton recipe no matter what naming drift exists on the
    Smartsheet side.
    """
    by_name = defaultdict(list)
    for i, r in enumerate(recipes):
        name = r.get("Recipe Name", "").strip().upper()
        if name:
            by_name[name].append(i)
    return {name: idxs for name, idxs in by_name.items() if len(idxs) > 1}


def flag_orphan_recipes(apply: bool = False) -> int:
    """
    Loads OUTPUT_JSON and identifies recipes to hide via two independent,
    narrowly-scoped checks. By default this is a DRY RUN: it prints what
    would change and writes nothing. Pass apply=True (or --apply on the
    CLI) to actually write hidden/hiddenReason back to OUTPUT_JSON.

    Check A — true orphan (existing logic, unchanged):
      - its own ZIP is no longer attached to any Smartsheet row AND its
        Recipe Name also has no matching row (both must agree), OR
      - it has no Image path at all (zip check can't run) AND its Recipe
        Name has no matching row (name-only fallback).

    Check B — in-file stale duplicate (see module docstring):
      - only considered for names that appear more than once in THIS file
      - of such a group, the member(s) whose zip stem is NOT a current
        Smartsheet attachment are hidden, but only if exactly one member
        of the group IS current (unambiguous winner). Ambiguous groups are
        printed for manual review and left untouched.

    Recipes that already have a 'hidden' value (manual or previously
    auto-set) are left untouched by both checks.

    Returns:
        Number of recipes that would be (or were) newly flagged this run.
    """
    if not Path(OUTPUT_JSON).exists():
        print(f"⚠ {OUTPUT_JSON} not found — nothing to flag.")
        return 0

    with open(OUTPUT_JSON, "r", encoding="utf-8") as f:
        recipes = json.load(f)

    valid_zip_stems  = set(download_zips.get_zip_stem_to_row_id().keys())
    smartsheet_map   = load_smartsheet_data()
    smartsheet_names = set(smartsheet_map.keys())

    duplicate_groups = _find_in_file_duplicate_groups(recipes)
    if duplicate_groups:
        print(f"🔎 Found {len(duplicate_groups)} Recipe Name(s) with multiple entries in {OUTPUT_JSON}:")
        for name, idxs in duplicate_groups.items():
            stems = [_recipe_key_from_image_path(recipes[i].get("Image", "")) for i in idxs]
            print(f"   - {name}: {list(zip(stems, idxs))}")
        print()

    to_hide = {}  # index -> reason

    # --- Check B: in-file stale duplicates, resolved only within each group ---
    for name, idxs in duplicate_groups.items():
        members = []
        for i in idxs:
            if "hidden" in recipes[i]:
                continue  # already decided, don't touch
            stem = _recipe_key_from_image_path(recipes[i].get("Image", ""))
            members.append((i, stem, stem in valid_zip_stems))

        current = [m for m in members if m[2]]
        stale   = [m for m in members if not m[2]]

        if len(current) == 1 and stale:
            for i, stem, _ in stale:
                to_hide[i] = DUPLICATE_SUPERSEDED_REASON
        elif members:
            print(f"⚠ NEEDS MANUAL REVIEW — ambiguous duplicate group '{name}': "
                  f"{[(stem, 'current' if is_cur else 'stale') for _, stem, is_cur in members]}")

    # --- Check A: true orphans (unchanged original logic) ---
    for i, recipe in enumerate(recipes):
        if "hidden" in recipe or i in to_hide:
            continue

        name = recipe.get("Recipe Name", "").strip().upper()
        recipe_key = _recipe_key_from_image_path(recipe.get("Image", ""))

        has_image      = bool(recipe_key)
        zip_is_orphan  = has_image and recipe_key not in valid_zip_stems
        name_is_orphan = name not in smartsheet_names

        if has_image:
            if zip_is_orphan and name_is_orphan:
                to_hide[i] = "ZIP gone from Smartsheet + no Recipe Name match"
        else:
            if name_is_orphan:
                to_hide[i] = "no image path, no Recipe Name match"

    for i, reason in to_hide.items():
        name = recipes[i].get("Recipe Name", "")
        recipe_key = _recipe_key_from_image_path(recipes[i].get("Image", ""))
        tag = "Would hide" if not apply else "Hiding"
        print(f"🚫 {tag} ({reason}): {name} [{recipe_key or 'no image path'}]")
        if apply:
            recipes[i]["hidden"] = True
            recipes[i]["hiddenReason"] = NO_SMARTSHEET_MATCH_REASON

    if apply and to_hide:
        backup_path = f"{OUTPUT_JSON}.bak.{datetime.now().strftime('%Y%m%d%H%M%S')}"
        shutil.copy2(OUTPUT_JSON, backup_path)
        print(f"\n💾 Backup written to {backup_path}")

        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump(recipes, f, indent=2, ensure_ascii=False)

    verb = "flagged" if apply else "would be flagged"
    print(f"\n✅ Orphan check complete: {len(to_hide)} recipe(s) {verb} as hidden"
          + ("" if apply else " (DRY RUN — nothing written; re-run with --apply to commit)"))

    return len(to_hide)


if __name__ == "__main__":
    flag_orphan_recipes(apply="--apply" in sys.argv)