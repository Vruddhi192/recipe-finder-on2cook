#!/usr/bin/env python3
"""
flag_orphan_recipes.py

Final pipeline step. Reads the finished recipes_fix.json (after
sync_description has already fixed any stale description names, and
parse_to_json has re-run to pick that up) and flags any recipe that still
has no matching row in Smartsheet at all as hidden.

This must run LAST, after sync_description + the final parse_to_json
re-run — never before. If it ran earlier, a recipe whose description name
hadn't been synced yet would look like an orphan and get wrongly hidden,
even though it actually has a Smartsheet match under its corrected name.

Usage:
  python flag_orphan_recipes.py
"""

import json
from pathlib import Path

from parse_txt_to_json import (
    OUTPUT_JSON,
    PROTECTED_FIELDS,
    load_smartsheet_data,
)

NO_SMARTSHEET_MATCH_REASON = "not needed anymore"


def flag_orphan_recipes() -> int:
    """
    Loads OUTPUT_JSON, flags any recipe with no Smartsheet match as
    hidden=true / hiddenReason="not needed anymore" — UNLESS it already
    has a 'hidden' value (manual or previously auto-set), which is left
    untouched.

    Returns:
        Number of recipes newly flagged this run.
    """
    if not Path(OUTPUT_JSON).exists():
        print(f"⚠ {OUTPUT_JSON} not found — nothing to flag.")
        return 0

    with open(OUTPUT_JSON, "r", encoding="utf-8") as f:
        recipes = json.load(f)

    smartsheet_map = load_smartsheet_data()
    smartsheet_names = set(smartsheet_map.keys())

    newly_flagged = 0

    for recipe in recipes:
        name = recipe.get("Recipe Name", "").strip().upper()

        if "hidden" in recipe:
            # Already has a hidden value (manual or previously auto-set) — leave it alone.
            continue

        if name not in smartsheet_names:
            recipe["hidden"] = True
            recipe["hiddenReason"] = NO_SMARTSHEET_MATCH_REASON
            newly_flagged += 1
            print(f"🚫 Auto-hidden (no Smartsheet match): {name}")

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(recipes, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Orphan check complete: {newly_flagged} recipe(s) newly flagged as hidden")
    print(f"   (hidden = {{recipe has no matching Smartsheet row}}, hiddenReason = '{NO_SMARTSHEET_MATCH_REASON}')")
    print(f"   Recipes with a pre-existing 'hidden' value were left untouched.")

    return newly_flagged


if __name__ == "__main__":
    flag_orphan_recipes()