#!/usr/bin/env python3
"""
pipeline_state.py

Tracks, across runs, the last Smartsheet row-modified timestamp we
successfully processed for each recipe (keyed by ZIP stem, uppercased —
the same key used for `updated_stems` everywhere else in the pipeline).

Why this exists:
  download_zips.py only detects "changed" by comparing the ZIP
  attachment's own updatedAt to the local file's mtime. If someone edits
  a row in Smartsheet (Recipe Name, Cuisine, Category, etc.) WITHOUT
  re-uploading the ZIP, the attachment's updatedAt never changes, so
  download_zips sees nothing new — and every downstream step that's
  gated on `updated_stems` (extract, accessory mapping, popup
  generation, disclaimers) silently skips that recipe.

  This module lets all-in-one.py also compare Smartsheet's native
  per-row `modifiedAt` (bumped on ANY cell edit, no extra column needed)
  against what we recorded last run, and fold any row that's newer into
  `updated_stems` too — so a plain row edit forces the same reprocessing
  a new ZIP upload would.

State file: ../pipeline_state.json
  { "CHICKEN BIRYANI": "2026-08-01T10:22:00+00:00", ... }
"""

import json
import os

STATE_FILE = "../pipeline_state.json"


def load_state() -> dict:
    """Returns {recipe_stem_upper: last_processed_modified_iso}."""
    if not os.path.exists(STATE_FILE):
        print(f"ℹ  No {STATE_FILE} yet — treating every recipe as new.")
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)
        print(f"📂 Loaded pipeline state ({len(state)} recipes) ← {STATE_FILE}")
        return state
    except (json.JSONDecodeError, OSError) as e:
        print(f"⚠ Could not read {STATE_FILE} ({e}), starting with empty state.")
        return {}


def save_state(state: dict):
    """Overwrites the state file with the full current snapshot."""
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2, sort_keys=True)
    print(f"💾 Saved pipeline state ({len(state)} recipes) → {STATE_FILE}")


def get_changed_stems(current_modified: dict, previous_state: dict) -> set:
    """
    Compares current Smartsheet row-modified timestamps against what was
    recorded last run. A recipe is "changed" if:
      - it's not in previous_state at all (new recipe), or
      - its current modifiedAt is strictly newer than the recorded one.

    Timestamps are ISO 8601 strings from Smartsheet (e.g.
    "2026-08-01T10:22:00Z") which sort correctly as plain strings, so no
    datetime parsing is needed for the comparison.
    """
    changed = set()
    for stem, modified in current_modified.items():
        prev = previous_state.get(stem)
        if not prev or modified > prev:
            changed.add(stem)
    return changed