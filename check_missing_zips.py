"""
Checks every recipe's zip file on the live On2Cook Recipe Finder site and
reports which ones are missing (404 / not downloadable).

Mirrors the exact logic from script.js -> downloadSingleRecipeZip():
    baseName = PopupImage filename, minus ".pdf"
    zipUrl   = f"{SITE}/zips/{baseName}.zip"
    HEAD request -> if not 200, it's "not downloadable"

Usage:
    pip install requests
    python check_missing_zips.py
"""

import json
import sys
from pathlib import Path
from urllib.parse import quote

import requests

SITE = "https://on2cook-recipe-finder.vercel.app"
RECIPES_JSON_URL = f"{SITE}/recipes_fix.json"
LOCAL_FALLBACK = Path(__file__).parent / "recipe finder" / "recipes_fix.json"

TIMEOUT = 10


def load_recipes():
    """Try to fetch the live recipes_fix.json; fall back to a local copy."""
    try:
        resp = requests.get(RECIPES_JSON_URL, timeout=TIMEOUT)
        resp.raise_for_status()
        print(f"Loaded {RECIPES_JSON_URL} (live)")
        return resp.json()
    except Exception as e:
        print(f"Could not fetch live JSON ({e}), falling back to local file.")
        if LOCAL_FALLBACK.exists():
            with open(LOCAL_FALLBACK, encoding="utf-8") as f:
                return json.load(f)
        print("No local fallback found either. Aborting.")
        sys.exit(1)


def base_name_from_popup(popup_image: str) -> str:
    """Replicates: PopupImage.split('?')[0] -> basename -> strip .pdf"""
    path = popup_image.split("?")[0]
    filename = path.rstrip("/").split("/")[-1]
    if filename.lower().endswith(".pdf"):
        filename = filename[: -len(".pdf")]
    return filename


def check_one_url(session, url):
    """Returns (ok: bool, reason: str|None)."""
    try:
        resp = session.head(url, timeout=TIMEOUT, allow_redirects=True)
        if not resp.ok:
            return False, f"Server error: {resp.status_code}"

        content_type = (resp.headers.get("Content-Type") or "").lower()
        if "zip" not in content_type and "octet-stream" not in content_type:
            return False, f"Not a ZIP file (Content-Type: {content_type or 'missing'})"

        # Confirm body actually starts with ZIP magic bytes 'PK'
        try:
            get_resp = session.get(url, timeout=TIMEOUT, stream=True, allow_redirects=True)
            first_bytes = next(get_resp.iter_content(chunk_size=4), b"")
            get_resp.close()
            if not first_bytes.startswith(b"PK"):
                return False, "Body is not a valid ZIP (missing 'PK' signature)"
        except Exception as e:
            return False, f"Could not verify file body: {e}"

        return True, None
    except Exception as e:
        return False, f"ERROR: {e}"


# Folders to try, in order. The site's fetch() call now uses /updated_zips/
# as of the script.js fix -- that's the folder that matters for "is this
# recipe actually downloadable on the live site right now". /zips/ is kept
# as a secondary check purely for visibility into legacy files.
CANDIDATE_FOLDERS = ["updated_zips", "zips"]


def main():
    recipes = load_recipes()
    print(f"Total recipes: {len(recipes)}\n")

    missing = []
    ok_count = 0

    session = requests.Session()

    for i, r in enumerate(recipes, start=1):
        recipe_name = r.get("Recipe Name", "UNKNOWN")
        popup_image = r.get("PopupImage", "")

        if not popup_image:
            missing.append((recipe_name, "NO_POPUP_IMAGE", "-"))
            continue

        base_name = base_name_from_popup(popup_image)

        reason = None
        found_in = None
        for folder in CANDIDATE_FOLDERS:
            zip_url = f"{SITE}/{folder}/{quote(base_name)}.zip"
            ok, why = check_one_url(session, zip_url)
            if ok:
                found_in = folder
                break
            else:
                # keep the reason from the FIRST (primary) folder tried,
                # since that's what the live site's code actually uses
                if reason is None:
                    reason = why

        if found_in == CANDIDATE_FOLDERS[0]:
            ok_count += 1
        elif found_in is not None:
            # File exists, but only under a DIFFERENT folder than what the
            # site's code queries -- this is the "zip exists but 404s" case.
            missing.append(
                (
                    recipe_name,
                    base_name,
                    f"MISMATCH: code fetches /{CANDIDATE_FOLDERS[0]}/ (fails: {reason}), "
                    f"but file actually exists under /{found_in}/",
                )
            )
        else:
            missing.append((recipe_name, base_name, reason))

        if i % 50 == 0:
            print(f"...checked {i}/{len(recipes)}")

    print(f"\nDone. {ok_count} downloadable, {len(missing)} missing/failed.\n")

    if missing:
        print("Missing / failed zips:")
        print("-" * 70)
        for recipe_name, base_name, status in missing:
            print(f"{recipe_name:<40} | {base_name:<25} | {status}")

        # Also write a CSV for easy sharing
        out_path = Path(__file__).parent / "missing_zips.csv"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("Recipe Name,Base Name,Status\n")
            for recipe_name, base_name, status in missing:
                f.write(f'"{recipe_name}","{base_name}","{status}"\n')
        print(f"\nSaved CSV to: {out_path}")
    else:
        print("All zips downloadable. Nothing missing!")


if __name__ == "__main__":
    main()