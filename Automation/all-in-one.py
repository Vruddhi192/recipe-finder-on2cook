#!/usr/bin/env python3
"""
all-in-one.py
=============
Full recipe pipeline orchestrator. Runs all steps sequentially with no
human input.

This file no longer contains any pipeline logic itself — each step lives
in its own standalone, independently-runnable file. This file just imports
each one and calls it in order, passing `updated_stems` along the chain so
later steps know which recipes were actually new/changed this run instead
of reprocessing everything.

Steps:
  1. download_zips      — fetch new/updated ZIPs from Smartsheet
  2. extract_zips        — extract ZIPs → extracted/
  3. accessory_mapping    — map accessories + fix descriptions → updated_extracted/ + updated_zips/
  4. generate_popups     — generate popup PDFs (skips if PDF already exists)
  5. parse_to_json       — generate recipes_fix.json from updated_extracted/
  6. add_disclaimer      — append bilingual (Hindi/English) instruction block to
                            popup PDFs, only for recipes updated this run (needs
                            recipes_fix.json from step 5, hence it runs right after)
  7. sync_description    — patch description first lines from Smartsheet Recipe Names
  8. parse_to_json       — re-run to pick up sync_description changes
  9. flag_orphan_recipes — hide recipes with no Smartsheet match (must run LAST,
                            after sync_description has had its chance to fix names)

Usage:
  python all-in-one.py
"""

import sys
from datetime import datetime

import download_zips
import extract_zips
import accessory_mapping
import generate_popup_images
import parse_txt_to_json
import add_disclaimer_onpopup_pdf
import sync_description
import flag_orphan_recipes


def banner(title: str):
    print(f"\n{'═'*60}")
    print(f"  {title}")
    print(f"{'═'*60}")


def step_header(n: int, title: str):
    print(f"\n{'─'*60}")
    print(f"  STEP {n}: {title}")
    print(f"{'─'*60}")


def main():
    start = datetime.now()
    banner("RECIPE PIPELINE — Full Run")
    print(f"  Started: {start.strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        step_header(1, "Download ZIPs from Smartsheet")
        updated_stems = download_zips.download_all_zips()

        step_header(2, "Extract ZIPs")
        extract_zips.extract_all_zips(updated_stems)

        step_header(3, "Accessory mapping + description fixes")
        accessory_mapping.process_all_accessories(updated_stems)

        step_header(4, "Generate popup PDFs")
        generate_popup_images.generate_all_popups(updated_stems)

        step_header(5, "Parse to JSON")
        parse_txt_to_json.generate_recipes_json()

        step_header(6, "Add bilingual disclaimer to updated popup PDFs")
        add_disclaimer_onpopup_pdf.add_disclaimers_for_updated(updated_stems)

        step_header(7, "Sync description first lines from Smartsheet Recipe Names")
        sync_description.main()

        step_header(8, "Parse to JSON (re-run to pick up sync_description changes)")
        parse_txt_to_json.generate_recipes_json()

        step_header(9, "Flag orphan recipes (no Smartsheet match) as hidden")
        flag_orphan_recipes.flag_orphan_recipes()

    except Exception as e:
        print(f"\n💥 PIPELINE FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    elapsed = (datetime.now() - start).total_seconds()
    banner(f"PIPELINE COMPLETE  ({elapsed:.0f}s)")


if __name__ == "__main__":
    main()