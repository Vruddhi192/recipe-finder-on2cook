#!/usr/bin/env python3
"""
download_zips.py

Fetches new/updated recipe ZIPs from Smartsheet.

Fast path: a single sheet-level /attachments call fetches every attachment
in one shot (instead of the old row-by-row approach, which was 1 API call
per row). Per-attachment detail calls are still needed to get a fresh
download URL + updatedAt timestamp, but the expensive "find all attachments"
step is now O(1) API calls instead of O(rows).

Usage:
  python download_zips.py
"""

import os
import requests
from pathlib import Path
from datetime import datetime, timezone

# ── Config ────────────────────────────────────────────────────────────────────
SMARTSHEET_TOKEN    = os.environ["SMARTSHEET_TOKEN"]
SMARTSHEET_SHEET_ID = os.environ["SMARTSHEET_SHEET_ID"]
SMARTSHEET_HEADERS  = {
    "Authorization": f"Bearer {SMARTSHEET_TOKEN}",
    "Content-Type":  "application/json",
}

ZIP_ROOT = "../zips"


def parse_smartsheet_timestamp(ts_str):
    if not ts_str:
        return None
    return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))


def get_local_mtime(file_path):
    return datetime.fromtimestamp(os.path.getmtime(file_path), tz=timezone.utc)


def download_all_zips() -> set:
    """
    Downloads all new/updated ZIP attachments from Smartsheet into ZIP_ROOT.

    Returns:
        set of recipe stems (uppercased, e.g. "CHICKEN BIRYANI") that were
        newly added or updated this run — used by later pipeline steps to
        decide what needs reprocessing instead of redoing everything.
    """
    Path(ZIP_ROOT).mkdir(exist_ok=True)

    # Single call: fetch ALL row-level attachments at once.
    print("📡 Fetching all attachments (single API call)...")
    resp = requests.get(
        f"https://api.smartsheet.com/2.0/sheets/{SMARTSHEET_SHEET_ID}/attachments",
        headers=SMARTSHEET_HEADERS,
        params={"includeAll": "true"},
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Attachments fetch failed: {resp.status_code} – {resp.text}")

    all_attachments = [
        a for a in resp.json().get("data", [])
        if a.get("parentType") == "ROW" and a.get("name", "").lower().endswith(".zip")
    ]
    print(f"   → {len(all_attachments)} ZIP attachments found")

    newly_added   = []
    updated       = []
    updated_stems = set()
    skipped       = 0
    failed        = []

    for i, att in enumerate(all_attachments, 1):
        att_id   = att["id"]
        att_name = att.get("name", f"attachment_{att_id}")
        file_path = os.path.join(ZIP_ROOT, att_name)

        print(f"[{i}/{len(all_attachments)}] {att_name}")

        # Fetch full details to get a fresh download URL + updatedAt
        detail_resp = requests.get(
            f"https://api.smartsheet.com/2.0/sheets/{SMARTSHEET_SHEET_ID}/attachments/{att_id}",
            headers=SMARTSHEET_HEADERS,
        )
        if detail_resp.status_code != 200:
            print(f"  ❌ Could not fetch details, skipping.")
            failed.append(att_name)
            continue

        details     = detail_resp.json()
        url         = details.get("url")
        remote_time = parse_smartsheet_timestamp(details.get("updatedAt") or details.get("createdAt"))

        if not url:
            print(f"  ❌ No download URL, skipping.")
            failed.append(att_name)
            continue

        # Skip if local file is already up-to-date
        if os.path.exists(file_path) and remote_time:
            local_time = get_local_mtime(file_path)
            if remote_time <= local_time:
                print(f"  ⏭  Up to date, skipping.")
                skipped += 1
                continue
            else:
                print(f"  🔄 Updated on Smartsheet, replacing...")

        # Download
        try:
            dl_resp = requests.get(url, stream=True)
            dl_resp.raise_for_status()
            with open(file_path, "wb") as f:
                for chunk in dl_resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            print(f"  ✓ Saved.")
            if os.path.exists(file_path) and remote_time:
                updated.append(att_name)
            else:
                newly_added.append(att_name)
            updated_stems.add(Path(att_name).stem.upper())
        except Exception as e:
            print(f"  ❌ Download failed: {e}")
            failed.append(att_name)

    print(f"\n  New      : {len(newly_added)}")
    print(f"  Updated  : {len(updated)}")
    print(f"  Skipped  : {skipped}")
    print(f"  Failed   : {len(failed)}")
    if failed:
        for f in failed:
            print(f"    ✗ {f}")

    return updated_stems


if __name__ == "__main__":
    download_all_zips()