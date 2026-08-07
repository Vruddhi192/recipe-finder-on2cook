#!/usr/bin/env python3
"""
resync_from_zip_content.py

Manual, on-demand full reconciliation pass — run this by hand, not on a
schedule.

Unlike all-in-one.py (which trusts Smartsheet's row-modified timestamp to
decide what changed), this script trusts nothing but the ZIP's own bytes:
it force-downloads every recipe ZIP from Smartsheet unconditionally, hashes
each one, and compares that hash against what was recorded the last time
this script ran. Anything whose content is new or different gets pushed
through the full downstream pipeline (extract → accessory mapping → popup
PDF → JSON → disclaimer → description sync → orphan flagging).

Why this exists: before the row-modified/mtime bug was fixed, some recipes
edited in Smartsheet were silently never re-pulled locally — and because
pipeline_state.json still recorded their Smartsheet modifiedAt as "seen"
(the timestamp was fetched even though the download itself was skipped),
all-in-one.py's incremental diff has no way to know those recipes are
still stale. It'll see "no change" forever. This script sidesteps that
completely by ignoring timestamps and checking actual content instead, so
it will always find and fix that backlog — including on its very first
run, when every recipe will look "changed" (nothing's been hashed yet)
and everything gets reprocessed once to get fully caught up.

After that first run, use this periodically as a safety net alongside the
normal all-in-one.py runs — it's heavier (fetches every ZIP every time)
so it's not meant to replace all-in-one.py, just to catch anything that
slips through it.

Usage:
  python resync_from_zip_content.py
"""

import os
import sys
import json
import hashlib
from pathlib import Path
from datetime import datetime

import download_zips
import extract_zips
import accessory_mapping
import generate_popup_images
import parse_txt_to_json
import add_disclaimer_onpopup_pdf
import sync_description
import flag_orphan_recipes
import pipeline_state

ZIP_ROOT           = "../zips"
CONTENT_STATE_FILE = "../zip_content_state.json"


def load_content_state() -> dict:
    """Returns {recipe_stem_upper: sha256_of_zip_bytes}."""
    if not os.path.exists(CONTENT_STATE_FILE):
        print(f"ℹ  No {CONTENT_STATE_FILE} yet — treating every recipe's content as new.")
        return {}
    try:
        with open(CONTENT_STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)
        print(f"📂 Loaded zip content state ({len(state)} recipes) ← {CONTENT_STATE_FILE}")
        return state
    except (json.JSONDecodeError, OSError) as e:
        print(f"⚠ Could not read {CONTENT_STATE_FILE} ({e}), starting with empty state.")
        return {}


def save_content_state(state: dict):
    with open(CONTENT_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2, sort_keys=True)
    print(f"💾 Saved zip content state ({len(state)} recipes) → {CONTENT_STATE_FILE}")


def hash_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    start = datetime.now()
    print("═" * 60)
    print("  MANUAL RESYNC — verify every recipe's ZIP content")
    print("═" * 60)
    print(f"  Started: {start.strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        # 1️⃣ Force-download every ZIP, unconditionally. Every stem is
        # passed in as "stale" so download_all_zips() skips nothing based
        # on any timestamp — the only thing that decides "changed" here is
        # the content hash comparison in step 2.
        print("\n📡 Determining full set of recipe stems on Smartsheet...")
        all_stems = set(download_zips.get_zip_stem_to_row_id().keys())
        print(f"   → {len(all_stems)} recipes on Smartsheet")

        print("\n⬇️  Force-downloading every ZIP (bypassing staleness checks)...")
        download_zips.download_all_zips(stale_stems=all_stems)

        # 2️⃣ Hash every ZIP now on disk, compare to last recorded hash.
        print("\n🔍 Hashing local ZIPs and comparing to last known content...")
        previous_content = load_content_state()
        current_content  = {}
        content_changed_stems = set()

        for root, dirs, files in os.walk(ZIP_ROOT):
            for file in sorted(files):
                if not file.lower().endswith(".zip"):
                    continue
                stem      = Path(file).stem.upper()
                file_path = os.path.join(root, file)
                digest    = hash_file(file_path)
                current_content[stem] = digest

                if previous_content.get(stem) != digest:
                    content_changed_stems.add(stem)

        if content_changed_stems:
            print(f"\n  🔁 {len(content_changed_stems)} recipe(s) have different ZIP content than last recorded:")
            for s in sorted(content_changed_stems):
                print(f"       - {s}")
        else:
            print("\n  ✔  No content changes found — everything already matches.")
            elapsed = (datetime.now() - start).total_seconds()
            print(f"\nTotal time: {elapsed:.0f}s")
            return

        # 3️⃣ Push only the genuinely-changed recipes through the rest of
        # the pipeline — same steps all-in-one.py runs, scoped down to
        # content_changed_stems.
        print("\n" + "─" * 60)
        print("  Re-extracting, re-mapping accessories, regenerating popups...")
        print("─" * 60)
        extract_zips.extract_all_zips(content_changed_stems)
        accessory_mapping.process_all_accessories(content_changed_stems)
        generate_popup_images.generate_all_popups(content_changed_stems)

        print("\n" + "─" * 60)
        print("  Rebuilding recipes_fix.json...")
        print("─" * 60)
        parse_txt_to_json.generate_recipes_json()

        print("\n" + "─" * 60)
        print("  Adding disclaimers + syncing descriptions...")
        print("─" * 60)
        add_disclaimer_onpopup_pdf.add_disclaimers_for_updated(content_changed_stems)
        sync_description.main()
        parse_txt_to_json.generate_recipes_json()

        print("\n" + "─" * 60)
        print("  Flagging orphan recipes...")
        print("─" * 60)
        flag_orphan_recipes.flag_orphan_recipes()

        # 4️⃣ Persist BOTH state files. Content state so this script knows
        # what it's already caught up on next time; pipeline_state.json too
        # so all-in-one.py's own timestamp-based diff agrees these recipes
        # are current and doesn't redundantly reprocess them again on its
        # very next run.
        save_content_state(current_content)
        current_modified = download_zips.get_sheet_modified_map()
        pipeline_state.save_state(current_modified)

    except Exception as e:
        print(f"\n💥 RESYNC FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    elapsed = (datetime.now() - start).total_seconds()
    print("\n" + "═" * 60)
    print(f"  RESYNC COMPLETE  ({elapsed:.0f}s)")
    print("═" * 60)


if __name__ == "__main__":
    main()
