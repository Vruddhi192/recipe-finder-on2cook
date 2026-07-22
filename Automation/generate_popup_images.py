#!/usr/bin/env python3
"""
generate_popup_images.py

Generates popup PDFs for each recipe ZIP in UPDATED_ZIPS by calling
final_corrected_recipe_generator.py once per ZIP. Skips a recipe if its
PDF already exists, unless that recipe was updated this run.

Usage:
  python generate_popup_images.py
"""

import os
import sys
import subprocess
from pathlib import Path

ZIP_ROOT  = "../updated_zips"
POPUP_DIR = "../test_popup_images"

RECIPE_GENERATOR_SCRIPT = "final_corrected_recipe_generator.py"


def process_zip(zip_path):
    """
    Runs final_corrected_recipe_generator.py on a single zip, which saves
    POPUP_DIR/<RECIPE_NAME>.pdf
    """
    cmd = [sys.executable, RECIPE_GENERATOR_SCRIPT, zip_path, POPUP_DIR]
    print(f"⚙ Running: {' '.join(cmd)}")

    try:
        subprocess.run(cmd, check=True)
        print(f"🖼 Popup PDF generated for: {zip_path}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to generate popup for: {zip_path}")
        print(e)
        return False


def generate_all_popups(updated_stems: set = None) -> int:
    """
    Generates popup PDFs for every ZIP in ZIP_ROOT, skipping ones whose
    PDF already exists (unless their stem is in updated_stems, in which
    case the stale PDF is removed and regenerated).

    Returns:
        Number of PDFs generated this run.
    """
    Path(POPUP_DIR).mkdir(exist_ok=True)

    if not os.path.exists(RECIPE_GENERATOR_SCRIPT):
        print(f"  ⚠  {RECIPE_GENERATOR_SCRIPT} not found — skipping popup generation.")
        return 0

    processed = skipped = failed = 0

    for root, dirs, files in os.walk(ZIP_ROOT):
        for file in sorted(files):
            if not file.lower().endswith(".zip"):
                continue

            stem     = Path(file).stem
            pdf_path = os.path.join(POPUP_DIR, f"{stem}.pdf")

            if os.path.exists(pdf_path):
                if updated_stems and stem.upper() in updated_stems:
                    os.remove(pdf_path)
                    print(f"  🔄 Re-generating (updated): {stem}")
                else:
                    print(f"  ⏭  PDF exists, skipping: {stem}")
                    skipped += 1
                    continue

            zip_path = os.path.join(root, file)
            print(f"  ⚙  Generating: {stem}")
            if process_zip(zip_path):
                processed += 1
            else:
                failed += 1

    print("\n==============================")
    print("Popup image generation completed")
    print(f"Generated: {processed}")
    print(f"Skipped:   {skipped}")
    print(f"Failed:    {failed}")
    print(f"Saved in:  {os.path.abspath(POPUP_DIR)}")
    print("==============================")

    return processed


if __name__ == "__main__":
    generate_all_popups()

