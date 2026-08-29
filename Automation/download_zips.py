#!/usr/bin/env python3
"""
download_zips.py

Fetches new/changed recipe ZIPs from Smartsheet.

Fast path: a single sheet-level /attachments call fetches every attachment
in one shot (instead of the old row-by-row approach, which was 1 API call
per row). Per-attachment detail calls are still needed to get a fresh
download URL — the expensive "find all attachments" step is O(1) API calls
instead of O(rows).

Freshness is decided by the caller (all-in-one.py), not by comparing local
file mtimes: it passes in `stale_stems`, computed from Smartsheet's
row-level modifiedAt vs. what was recorded last run (pipeline_state.py).
A stem in that set gets redownloaded unconditionally; anything else is
downloaded only if there's no local copy at all yet.

Usage:
  python download_zips.py
"""

import os
import time
import requests
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
SMARTSHEET_TOKEN    = os.environ["SMARTSHEET_TOKEN"]
SMARTSHEET_SHEET_ID = os.environ["SMARTSHEET_SHEET_ID"]
SMARTSHEET_HEADERS  = {
    "Authorization": f"Bearer {SMARTSHEET_TOKEN}",
    "Content-Type":  "application/json",
}

ZIP_ROOT = "../zips"

# Status codes worth retrying: 403 (Smartsheet has historically returned this
# for transient/rate-limit conditions, not just real permission denials —
# see errorCode 4003), 429 (explicit rate limit), and 5xx (their servers,
# not our request, temporarily broken). A 401 is NOT retried — that means
# the token itself is malformed/missing, which retrying can't fix.
_RETRYABLE_STATUSES = {403, 429, 500, 502, 503, 504}
_MAX_ATTEMPTS = 4
_BACKOFF_BASE_SECONDS = 3  # 3s, 6s, 12s between attempts


def _smartsheet_get(url: str, **kwargs) -> requests.Response:
    """
    requests.get wrapper for Smartsheet API calls with automatic retry on
    transient-looking failures (403/429/5xx). Returns the LAST response
    either way — a final failing response after all retries is returned
    as-is (not raised), so callers keep their existing
    `if resp.status_code != 200:` checks and error messages unchanged.

    This exists because a 403 from Smartsheet isn't reliably "permanent
    access denied" — it has also been observed for transient conditions.
    Retrying costs a few seconds; not retrying costs a whole pipeline run
    for something that would've worked seconds later.
    """
    kwargs.setdefault("timeout", 30)
    resp = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        resp = requests.get(url, **kwargs)
        if resp.status_code == 200:
            return resp
        if resp.status_code not in _RETRYABLE_STATUSES or attempt == _MAX_ATTEMPTS:
            return resp
        wait = _BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
        print(f"   ⚠ {resp.status_code} from Smartsheet (attempt {attempt}/{_MAX_ATTEMPTS}) "
              f"— retrying in {wait}s...")
        time.sleep(wait)
    return resp


def _describe_403(resp) -> str:
    """
    On a 403, ask Smartsheet who this token actually belongs to
    (/2.0/users/me) so the error tells you WHICH account was denied,
    instead of just that a denial happened. errorCode 4003 specifically
    means "this user is not a collaborator on this sheet" — so the
    account below is the one that needs to be re-shared on the sheet
    (Sheet > Share), or the one whose token needs regenerating if it's
    missing/deactivated entirely.
    Never raises — this is best-effort context for the real error above.
    """
    if resp.status_code != 403:
        return ""
    try:
        who = requests.get(
            "https://api.smartsheet.com/2.0/users/me",
            headers=SMARTSHEET_HEADERS,
            timeout=10,
        )
        if who.status_code == 200:
            info = who.json()
            return (
                f"\n    ↳ SMARTSHEET_TOKEN belongs to: {info.get('email', '?')} "
                f"(account status: {info.get('status', '?')}). "
                f"If errorCode is 4003, add this account as a collaborator "
                f"on the sheet (Share in Smartsheet). If this call ALSO "
                f"fails, the token itself is invalid/revoked — generate a "
                f"new one under Account > Personal Settings > API Access."
            )
        return (
            f"\n    ↳ Could not identify the token's own account either "
            f"({who.status_code}) — the token itself is likely invalid, "
            f"expired, or revoked. Generate a new one under Account > "
            f"Personal Settings > API Access."
        )
    except requests.RequestException:
        return ""


def get_sheet_modified_map() -> dict:
    """
    Returns {zip_stem_upper: row_modifiedAt_iso} for every Smartsheet row
    that has a ZIP attachment — using Smartsheet's own row-level modified
    timestamp, which is tracked natively and bumped on ANY cell edit (no
    extra "Modified" column needs to exist on the sheet for this to work).

    Keyed by ZIP stem (not by the Recipe Name cell) so it lines up exactly
    with `updated_stems` everywhere else in the pipeline.
    """
    print("📡 Fetching Smartsheet row-modified timestamps...")
    resp = _smartsheet_get(
        f"https://api.smartsheet.com/2.0/sheets/{SMARTSHEET_SHEET_ID}",
        headers=SMARTSHEET_HEADERS,
    )
    if resp.status_code != 200:
        raise RuntimeError(
            f"Sheet fetch failed: {resp.status_code} – {resp.text}"
            f"{_describe_403(resp)}"
        )

    sheet = resp.json()
    row_modified = {
        str(row["id"]): (row.get("modifiedAt") or row.get("createdAt") or "")
        for row in sheet["rows"]
    }

    resp = _smartsheet_get(
        f"https://api.smartsheet.com/2.0/sheets/{SMARTSHEET_SHEET_ID}/attachments",
        headers=SMARTSHEET_HEADERS,
        params={"includeAll": "true"},
    )
    if resp.status_code != 200:
        raise RuntimeError(
            f"Attachments fetch failed: {resp.status_code} – {resp.text}"
            f"{_describe_403(resp)}"
        )

    stem_modified = {}
    for att in resp.json().get("data", []):
        if att.get("parentType") != "ROW":
            continue
        name = att.get("name", "")
        if not name.lower().endswith(".zip"):
            continue
        stem     = Path(name).stem.upper()
        row_id   = str(att.get("parentId", ""))
        modified = row_modified.get(row_id, "")
        if modified:
            # If a row somehow has >1 zip attachment, keep the newest.
            if stem not in stem_modified or modified > stem_modified[stem]:
                stem_modified[stem] = modified

    print(f"   → {len(stem_modified)} recipes with row-modified timestamps")
    return stem_modified


def get_zip_stem_to_row_id() -> dict:
    """
    Returns {zip_stem_upper: row_id} for every Smartsheet row that has a ZIP
    attachment.

    This is the reliable join key between a locally-extracted recipe folder
    (named after its own ZIP's stem — see extract_zips.py) and its exact
    Smartsheet row. parse_txt_to_json.py uses this to fetch a recipe's
    Recipe Name (and every other column) directly from the row that ZIP
    belongs to, instead of text-matching the name baked into the ZIP's
    internal .txt file against the sheet — which drifts whenever that
    internal name doesn't exactly match what's typed in the Recipe Name
    column.
    """
    print("📡 Fetching ZIP attachments to build stem → row ID map...")
    resp = _smartsheet_get(
        f"https://api.smartsheet.com/2.0/sheets/{SMARTSHEET_SHEET_ID}/attachments",
        headers=SMARTSHEET_HEADERS,
        params={"includeAll": "true"},
    )
    if resp.status_code != 200:
        raise RuntimeError(
            f"Attachments fetch failed: {resp.status_code} – {resp.text}"
            f"{_describe_403(resp)}"
        )

    stem_to_row_id = {}
    for att in resp.json().get("data", []):
        if att.get("parentType") != "ROW":
            continue
        name = att.get("name", "")
        if not name.lower().endswith(".zip"):
            continue
        stem = Path(name).stem.upper()
        row_id = att.get("parentId")
        if row_id is not None:
            # If a row somehow has >1 zip attachment, last one wins — same
            # tie-break behavior as get_sheet_modified_map above.
            stem_to_row_id[stem] = str(row_id)

    print(f"   → {len(stem_to_row_id)} ZIP → row ID mappings")
    return stem_to_row_id


def download_all_zips(stale_stems: set = None) -> set:
    """
    Downloads ZIP attachments from Smartsheet into ZIP_ROOT.

    A recipe's ZIP is (re)downloaded when either:
      - `stale_stems` says its Smartsheet row is new or has changed since
        the last successful pipeline run (the authoritative check — see
        pipeline_state.py / get_sheet_modified_map above), or
      - there's no local copy of the ZIP on disk at all (belt-and-suspenders
        for a stem that isn't flagged stale but genuinely isn't there —
        e.g. it was deleted locally, or this is the very first run before
        pipeline_state.json exists).

    This intentionally does NOT compare the attachment's own timestamp
    against the local file's mtime anymore. That comparison is fragile:
    filesystem mtimes get reset by file copies, container rebuilds, git
    checkouts, redeploys, etc. — any of which makes a genuinely-updated
    recipe look "already current" (local mtime ends up newer than the
    remote timestamp simply because the file was touched more recently
    than it was actually uploaded) and it silently gets skipped forever.
    Smartsheet's row-level modifiedAt, persisted across runs in
    pipeline_state.json, is the single source of truth for staleness now.

    Args:
        stale_stems: set of recipe stems (uppercased) that are new or have
            changed since the last successful run. Pass the set returned by
            pipeline_state.get_changed_stems(). If None, only stems with no
            local ZIP at all are downloaded (nothing is treated as stale).

    Returns:
        set of recipe stems (uppercased) that were actually downloaded
        this run.
    """
    Path(ZIP_ROOT).mkdir(exist_ok=True)
    stale_stems = stale_stems or set()

    # Single call: fetch ALL row-level attachments at once.
    print("📡 Fetching all attachments (single API call)...")
    resp = _smartsheet_get(
        f"https://api.smartsheet.com/2.0/sheets/{SMARTSHEET_SHEET_ID}/attachments",
        headers=SMARTSHEET_HEADERS,
        params={"includeAll": "true"},
    )
    if resp.status_code != 200:
        raise RuntimeError(
            f"Attachments fetch failed: {resp.status_code} – {resp.text}"
            f"{_describe_403(resp)}"
        )

    all_attachments = [
        a for a in resp.json().get("data", [])
        if a.get("parentType") == "ROW" and a.get("name", "").lower().endswith(".zip")
    ]
    print(f"   → {len(all_attachments)} ZIP attachments found")

    downloaded_stems = set()
    skipped          = 0
    failed            = []

    for i, att in enumerate(all_attachments, 1):
        att_id   = att["id"]
        att_name = att.get("name", f"attachment_{att_id}")
        stem     = Path(att_name).stem.upper()
        file_path = os.path.join(ZIP_ROOT, att_name)

        is_stale     = stem in stale_stems
        has_local    = os.path.exists(file_path)
        needs_download = is_stale or not has_local

        if not needs_download:
            skipped += 1
            continue

        reason = "new/changed row" if is_stale else "no local copy"
        print(f"[{i}/{len(all_attachments)}] {att_name} — downloading ({reason})")

        # Fetch full details to get a fresh download URL
        detail_resp = _smartsheet_get(
            f"https://api.smartsheet.com/2.0/sheets/{SMARTSHEET_SHEET_ID}/attachments/{att_id}",
            headers=SMARTSHEET_HEADERS,
        )
        if detail_resp.status_code != 200:
            print(f"  ❌ Could not fetch details, skipping.")
            failed.append(att_name)
            continue

        url = detail_resp.json().get("url")
        if not url:
            print(f"  ❌ No download URL, skipping.")
            failed.append(att_name)
            continue

        try:
            dl_resp = requests.get(url, stream=True)
            dl_resp.raise_for_status()
            with open(file_path, "wb") as f:
                for chunk in dl_resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            print(f"  ✓ Saved.")
            downloaded_stems.add(stem)
        except Exception as e:
            print(f"  ❌ Download failed: {e}")
            failed.append(att_name)

    print(f"\n  Downloaded : {len(downloaded_stems)}")
    print(f"  Skipped    : {skipped}")
    print(f"  Failed     : {len(failed)}")
    if failed:
        for f in failed:
            print(f"    ✗ {f}")

    return downloaded_stems


if __name__ == "__main__":
    print("ℹ  Running standalone — no stale_stems passed in, so only ZIPs with")
    print("   no local copy at all will be downloaded. Row edits without a new")
    print("   ZIP won't be caught this way; run all-in-one.py for that.")
    download_all_zips()
