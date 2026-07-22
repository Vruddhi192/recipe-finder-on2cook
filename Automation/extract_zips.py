#!/usr/bin/env python3
"""
extract_zips.py

Extracts recipe ZIPs from ZIP_ROOT into EXTRACT_ROOT, one subfolder per
recipe. Saves the recipe's JPG into IMAGE_DIR along the way.

If a recipe was newly downloaded or updated this run (passed in via
updated_stems), its existing extracted folder is wiped and re-extracted
fresh. Otherwise, an already-extracted folder is left alone.

Usage:
  python extract_zips.py
"""

import os
import stat
import time
import shutil
import zipfile
from pathlib import Path

ZIP_ROOT     = "../zips"
EXTRACT_ROOT = "../extracted"
IMAGE_DIR    = "../test_images"


def normalize_name(name):
    return name.replace("/", "-").replace("\\", "-").upper().strip()


def safe_rmtree(path, retries=6, delay=0.5):
    """
    Robust rmtree for Windows.

    Plain shutil.rmtree() throws WinError 5 ("Access is denied") when:
      - a file inside the tree is marked read-only (very common for files
        that came out of a ZIP — Windows won't unlink/rmdir those by default)
      - a file inside the tree is momentarily locked by OneDrive sync,
        an antivirus scan, Explorer's thumbnail cache, or a process that
        still has it open

    This clears read-only attributes on the fly and retries with a short
    delay before giving up, instead of crashing the whole pipeline.
    """
    def _on_exc(func, p, exc_info):
        try:
            os.chmod(p, stat.S_IWRITE)
        except Exception:
            pass
        try:
            func(p)
        except Exception:
            pass

    last_err = None
    for attempt in range(1, retries + 1):
        if not os.path.exists(path):
            return
        try:
            shutil.rmtree(path, onexc=_on_exc)
            return
        except Exception as e:
            last_err = e
            if attempt < retries:
                time.sleep(delay)

    raise RuntimeError(
        f"Could not delete '{path}' after {retries} attempts: {last_err}\n"
        f"    → This is almost always one of: a file inside that folder is open "
        f"in another program (Explorer preview, an editor, antivirus scan), or "
        f"OneDrive is still syncing it. Close anything that might have it open, "
        f"or pause OneDrive sync briefly, then rerun."
    ) from last_err


def extract_all_zips(updated_stems: set = None) -> int:
    """
    Extracts ZIPs from ZIP_ROOT into EXTRACT_ROOT.

    Args:
        updated_stems: set of recipe stems (uppercased) that were newly
            downloaded/updated this run. If a recipe's stem is in this set
            and it already has an extracted folder, that folder is wiped
            and re-extracted. If None, every ZIP without an existing
            extracted folder is extracted (first-run behavior).

    Returns:
        Number of recipes successfully extracted this run.
    """
    Path(EXTRACT_ROOT).mkdir(exist_ok=True)
    Path(IMAGE_DIR).mkdir(exist_ok=True)

    total    = 0
    failures = []

    for root, dirs, files in os.walk(ZIP_ROOT):
        for file in sorted(files):
            if not file.lower().endswith(".zip"):
                continue

            zip_path    = os.path.join(root, file)
            recipe_key  = normalize_name(Path(file).stem)
            extract_dir = os.path.join(EXTRACT_ROOT, recipe_key)

            if updated_stems and recipe_key in updated_stems:
                if os.path.exists(extract_dir):
                    safe_rmtree(extract_dir)
                    print(f"🔄 Re-extracting (updated): {recipe_key}")
                else:
                    print(f"🆕 Extracting (new): {recipe_key}")
            elif os.path.exists(extract_dir):
                print(f"⏭  Already extracted: {recipe_key}")
                continue
            else:
                print(f"🆕 Extracting (new): {recipe_key}")

            os.makedirs(extract_dir, exist_ok=True)
            print(f"📦 Extracting: {file}")

            try:
                with zipfile.ZipFile(zip_path, "r") as z:
                    z.extractall(extract_dir)
            except Exception as e:
                failures.append((recipe_key, f"ZIP error: {e}"))
                shutil.rmtree(extract_dir, ignore_errors=True)
                continue

            jpg = txt = None
            for r2, d2, f2 in os.walk(extract_dir):
                for fn in f2:
                    fp = os.path.join(r2, fn)
                    if fn.lower().endswith(".jpg") and jpg is None:
                        jpg = fp
                    elif fn.lower().endswith(".txt") and txt is None:
                        txt = fp

            if not txt:
                print(f"  ⚠  No TXT in {recipe_key}")
                failures.append((recipe_key, "Missing TXT"))
                continue

            if jpg:
                dest = os.path.join(IMAGE_DIR, f"{recipe_key}.jpg")
                shutil.copy(jpg, dest)
                print(f"  🖼  Image saved: {dest}")
            else:
                print(f"  ⚠  No JPG in {recipe_key}")
                failures.append((recipe_key, "Missing JPG"))

            total += 1

    print(f"\n✅ Extraction complete: {total} recipes processed")
    print(f"\n❌ Failed recipes: {len(failures)}")
    if failures:
        for name, reason in failures:
            print(f"   - {name}: {reason}")

    return total


if __name__ == "__main__":
    extract_all_zips()
