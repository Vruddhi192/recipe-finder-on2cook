"""
Recipe Booklet Updater
======================
Run this script any time to:
  1. Download the master recipe booklet PDF from Google Drive.
  2. Parse pages 7-10 (index pages) to extract recipe names already in the booklet.
  3. Compare against your local JSON file to find NEW recipes (not yet in the booklet).
  4. Build two PDFs and upload them to the target Google Drive folder:
       - new_recipes.pdf           : only the new recipe pages (A-Z)
       - latest_recipe_booklet.pdf : pages 1-6 (unchanged) + updated index + all recipe pages (A-Z)

SETUP
-----
1.  Go to https://console.cloud.google.com/
2.  Create a project → Enable "Google Drive API"
3.  Create OAuth 2.0 credentials (Desktop app) → Download as `credentials.json`
4.  Place `credentials.json` in the same folder as this script.
5.  On first run the browser opens once; token is cached in `token.json` for future runs.

CONFIGURATION  ← edit these two lines
"""

# ── USER CONFIG ──────────────────────────────────────────────────────────────
JSON_FILE        = "../recipes_fix.json"          # path to your local recipe JSON file
SOURCE_FILE_ID   = "1J8Jub3XxDGULo6tZMnWtZZYob9HGBHoT"  # Google Drive file ID of master booklet
TARGET_FOLDER_ID = "13Ce1yR1GtRX_6nJqYnvhLBnXQxkOvO07"  # Google Drive folder ID for output
# ─────────────────────────────────────────────────────────────────────────────

import io
import json
import os
import re
import unicodedata
from pathlib import Path

import pdfplumber
from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

SCOPES = ["https://www.googleapis.com/auth/drive"]

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR       = Path(__file__).parent
CREDENTIALS_FILE = SCRIPT_DIR / "credentials.json"
TOKEN_FILE       = SCRIPT_DIR / "token.json"
TEMP_BOOKLET     = SCRIPT_DIR / "_master_booklet.pdf"
OUT_NEW          = SCRIPT_DIR / "new_recipes.pdf"
OUT_LATEST       = SCRIPT_DIR / "latest_recipe_booklet.pdf"


# ─────────────────────────────────────────────────────────────────────────────
# 1. Google Drive authentication
# ─────────────────────────────────────────────────────────────────────────────
def get_drive_service():
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_FILE.exists():
                raise FileNotFoundError(
                    f"Missing {CREDENTIALS_FILE}.\n"
                    "Download your OAuth credentials JSON from Google Cloud Console\n"
                    "and place it next to this script as 'credentials.json'."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE), SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
    return build("drive", "v3", credentials=creds)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Download file from Drive
# ─────────────────────────────────────────────────────────────────────────────
def download_file(service, file_id: str, dest: Path):
    print(f"  Downloading master booklet → {dest.name} …")
    request = service.files().get_media(fileId=file_id)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    dest.write_bytes(buf.getvalue())
    print(f"  ✓ Downloaded ({dest.stat().st_size // 1024} KB)")


# ─────────────────────────────────────────────────────────────────────────────
# 3. Parse index pages (7–10, i.e. 0-indexed 6–9) for recipe names
# ─────────────────────────────────────────────────────────────────────────────
def normalise(name: str) -> str:
    """Uppercase, strip accents, collapse whitespace for fuzzy matching."""
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", name).strip().upper()


def parse_index_pages(pdf_path: Path, start_page=7, end_page=10) -> list[str]:
    """
    Extract recipe names from the index pages.
    Index pages typically contain lines like:
        AALNI BHAAT ..... 11
    We capture everything before the dots / page-number.
    Returns a list of normalised recipe names.
    """
    names = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page_num in range(start_page - 1, min(end_page, len(pdf.pages))):
            page = pdf.pages[page_num]
            text = page.extract_text() or ""
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                # Remove trailing page numbers and dot leaders
                clean = re.sub(r"[\.\s]+\d+\s*$", "", line).strip()
                # Skip very short lines (headers, page numbers, etc.)
                if len(clean) < 3:
                    continue
                # Skip lines that look like section headers (all digits, or contain "INDEX")
                if re.match(r"^\d+$", clean) or "INDEX" in clean.upper():
                    continue
                names.append(normalise(clean))
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for n in names:
        if n not in seen:
            seen.add(n)
            unique.append(n)
    print(f"  ✓ Parsed {len(unique)} recipe names from index pages {start_page}–{end_page}")
    return unique


# ─────────────────────────────────────────────────────────────────────────────
# 4. Load JSON and identify new recipes
# ─────────────────────────────────────────────────────────────────────────────
def load_json_recipes(json_path: Path) -> list[dict]:
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"  ✓ Loaded {len(data)} recipes from {json_path.name}")
    return data


def find_new_recipes(json_recipes: list[dict], existing_names: list[str]) -> list[dict]:
    existing_set = set(existing_names)
    new_ones = [r for r in json_recipes if normalise(r["Recipe Name"]) not in existing_set]
    new_ones.sort(key=lambda r: normalise(r["Recipe Name"]))
    print(f"  ✓ Found {len(new_ones)} NEW recipes not in the current booklet")
    for r in new_ones:
        print(f"      + {r['Recipe Name']}")
    return new_ones


# ─────────────────────────────────────────────────────────────────────────────
# 5. Determine which PDF page each existing recipe maps to
#    (recipe pages start at PDF page 11, i.e. 0-indexed 10)
# ─────────────────────────────────────────────────────────────────────────────
def map_recipes_to_pages(pdf_path: Path, recipe_start_page=11) -> dict[str, int]:
    """
    Returns {normalised_recipe_name: 0-indexed page number} for every
    recipe page found in the booklet (pages 11 onwards).
    Strategy: extract text from each page, take the first non-empty line
    as the recipe name candidate.
    """
    mapping = {}
    with pdfplumber.open(str(pdf_path)) as pdf:
        total = len(pdf.pages)
        for i in range(recipe_start_page - 1, total):
            page = pdf.pages[i]
            text = page.extract_text() or ""
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            if lines:
                candidate = normalise(lines[0])
                mapping[candidate] = i   # 0-indexed
    print(f"  ✓ Mapped {len(mapping)} recipe pages (pages {recipe_start_page}–{total})")
    return mapping


# ─────────────────────────────────────────────────────────────────────────────
# 6. Load a recipe's PDF page from its PopupImage path
# ─────────────────────────────────────────────────────────────────────────────
def load_recipe_pdf(recipe: dict, json_dir: Path) -> bytes:
    """
    Read the pre-made recipe PDF from the PopupImage path stored in the JSON.
    PopupImage paths like '../test_popup_images/NAME.pdf' are relative to the
    JSON file itself, so we resolve from json_dir (the JSON file's parent folder).
    """
    popup = recipe.get("PopupImage", "")
    if not popup:
        raise ValueError(f"No PopupImage defined for recipe: {recipe.get('Recipe Name')}")

    # Normalise path separators (handles both / and \)
    popup_clean = Path(popup.replace("\\", "/"))

    # Resolve relative to the JSON file's own directory
    pdf_path = (json_dir / popup_clean).resolve()

    if not pdf_path.exists():
        raise FileNotFoundError(
            f"PopupImage PDF not found for '{recipe.get('Recipe Name')}':\n"
            f"  Expected: {pdf_path}\n"
            f"  Check that the path in JSON is correct relative to: {json_dir}"
        )

    return pdf_path.read_bytes()

# ─────────────────────────────────────────────────────────────────────────────
# 7. Regenerate index pages using ReportLab
# ─────────────────────────────────────────────────────────────────────────────
def build_index_pages(all_recipes_sorted: list[str], first_recipe_pdf_page: int) -> bytes:
    """
    Build index pages (like the originals) listing recipe name → page number.
    all_recipes_sorted : list of recipe names (display form) in A-Z order
    first_recipe_pdf_page : the page number (1-indexed, as printed) of the first recipe
    Returns PDF bytes of the index section only.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )
    styles = getSampleStyleSheet()

    heading_style = ParagraphStyle(
        "IndexHeading",
        parent=styles["Heading1"],
        fontSize=22,
        textColor=colors.HexColor("#E8232A"),
        spaceAfter=14,
    )
    entry_style = ParagraphStyle(
        "IndexEntry",
        parent=styles["Normal"],
        fontSize=10,
        leading=16,
        textColor=colors.HexColor("#000807"),
    )

    story = []
    story.append(Paragraph("RECIPE INDEX", heading_style))
    story.append(Spacer(1, 0.3 * cm))

    # Build two-column table: name | page
    rows = []
    for i, name in enumerate(all_recipes_sorted):
        page_num = first_recipe_pdf_page + i
        rows.append(
            [
                Paragraph(name.upper(), entry_style),
                Paragraph(str(page_num), entry_style),
            ]
        )

    # Split into two visual columns on the page
    mid = (len(rows) + 1) // 2
    left_rows  = rows[:mid]
    right_rows = rows[mid:]

    # Pad right side if shorter
    while len(right_rows) < len(left_rows):
        right_rows.append([Paragraph("", entry_style), Paragraph("", entry_style)])

    combined = []
    for l, r in zip(left_rows, right_rows):
        combined.append(l + r)

    page_w = A4[0] - 4 * cm   # usable width
    col_w  = page_w / 4        # name | page | name | page
    tbl = Table(combined, colWidths=[col_w * 1.6, col_w * 0.4, col_w * 1.6, col_w * 0.4])
    tbl.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#F6F7EB")]),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#DDDDDD")),
            ]
        )
    )
    story.append(tbl)

    doc.build(story)
    buf.seek(0)
    return buf.read()


# ─────────────────────────────────────────────────────────────────────────────
# 8. Assemble final PDFs
# ─────────────────────────────────────────────────────────────────────────────
def assemble_pdfs(
    master_pdf: Path,
    new_recipes: list[dict],
    json_recipes: list[dict],
    existing_page_map: dict[str, int],   # kept for reference but no longer used for page content
    json_dir: Path,                       # ← NEW: directory of the JSON file
) -> tuple[bytes, bytes]:
    """
    Returns (new_recipes_pdf_bytes, latest_booklet_pdf_bytes).

    Layout of latest_recipe_booklet.pdf:
      Pages 1–6  : from master (unchanged front matter)
      Pages 7–?  : regenerated index (one or more pages)
      Pages ?+1… : ALL recipe pages A–Z (existing from master + new rendered)
    """

    reader = PdfReader(str(master_pdf))
    total_master = len(reader.pages)

    # ── Collect all recipe display names (JSON is source of truth for names) ──
    all_recipe_names_sorted = sorted(
        [r["Recipe Name"] for r in json_recipes], key=lambda n: normalise(n)
    )

    # ── Page 7 (1-indexed) is the first index page.
    #    Recipe pages start at page 11 (index 10) in the original.
    #    In our new booklet, front matter = pages 1-6 (indices 0-5).
    #    Index will follow, then recipes.
    #    We don't know index page count yet — build it first with placeholder,
    #    then patch page numbers after we know the offset.

    FRONT_MATTER_PAGES = 6   # pages 1–6 kept as-is
    # Recipe pages will start at: FRONT_MATTER_PAGES + index_page_count + 1 (1-indexed)
    # We'll build a draft index first with a temporary offset, then rebuild with correct offset.

    # Build recipe pages bytes dict: normalised_name → pdf_bytes
    # Build recipe pages bytes dict: normalised_name → pdf_bytes
    print("\n  Building recipe page bytes …")
    recipe_page_bytes: dict[str, bytes] = {}

    for recipe in json_recipes:
        norm = normalise(recipe["Recipe Name"])
        recipe_page_bytes[norm] = load_recipe_pdf(recipe, SCRIPT_DIR)

    # ── Build index (draft pass to measure page count) ──
    DRAFT_FIRST_RECIPE_PAGE = 99  # placeholder
    draft_index_bytes = build_index_pages(all_recipe_names_sorted, DRAFT_FIRST_RECIPE_PAGE)
    draft_index_reader = PdfReader(io.BytesIO(draft_index_bytes))
    index_page_count = len(draft_index_reader.pages)

    # ── Now we know the real first recipe page number ──
    first_recipe_page_number = FRONT_MATTER_PAGES + index_page_count + 1  # 1-indexed printed

    # Rebuild index with correct page numbers
    print(f"  Index will be {index_page_count} page(s). First recipe on printed page {first_recipe_page_number}.")
    index_bytes = build_index_pages(all_recipe_names_sorted, first_recipe_page_number)

    # ── Assemble latest_recipe_booklet ──
    writer_latest = PdfWriter()

    # Front matter pages 1–6
    for i in range(FRONT_MATTER_PAGES):
        if i < total_master:
            writer_latest.add_page(reader.pages[i])

    # Index pages
    index_reader = PdfReader(io.BytesIO(index_bytes))
    for pg in index_reader.pages:
        writer_latest.add_page(pg)

    # All recipe pages A–Z
    for name in all_recipe_names_sorted:
        norm = normalise(name)
        page_bytes = recipe_page_bytes.get(norm)
        if page_bytes:
            rdr = PdfReader(io.BytesIO(page_bytes))
            writer_latest.add_page(rdr.pages[0])
        else:
            print(f"  ⚠ No page found for: {name}")

    buf_latest = io.BytesIO()
    writer_latest.write(buf_latest)

    # ── Assemble new_recipes PDF ──
    writer_new = PdfWriter()

    # Index for new recipes only
    new_recipe_names_sorted = sorted(
        [r["Recipe Name"] for r in new_recipes], key=lambda n: normalise(n)
    )
    if new_recipe_names_sorted:
        new_index_bytes = build_index_pages(new_recipe_names_sorted, 2)  # page 1 = index, recipes from page 2
        new_idx_reader = PdfReader(io.BytesIO(new_index_bytes))
        for pg in new_idx_reader.pages:
            writer_new.add_page(pg)

        for name in new_recipe_names_sorted:
            norm = normalise(name)
            page_bytes = recipe_page_bytes.get(norm)
            if page_bytes:
                rdr = PdfReader(io.BytesIO(page_bytes))
                writer_new.add_page(rdr.pages[0])

    buf_new = io.BytesIO()
    writer_new.write(buf_new)

    return buf_new.getvalue(), buf_latest.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# 9. Upload to Google Drive (replace if exists, else create)
# ─────────────────────────────────────────────────────────────────────────────
def upload_or_replace(service, folder_id: str, filename: str, data: bytes):
    mime = "application/pdf"

    # Check if file already exists in the folder
    query = (
        f"name='{filename}' and '{folder_id}' in parents "
        f"and mimeType='{mime}' and trashed=false"
    )
    results = service.files().list(q=query, fields="files(id, name)").execute()
    existing = results.get("files", [])

    media = MediaIoBaseUpload(io.BytesIO(data), mimetype=mime, resumable=True)

    if existing:
        file_id = existing[0]["id"]
        service.files().update(fileId=file_id, media_body=media).execute()
        print(f"  ✓ Updated  '{filename}' (id: {file_id})")
    else:
        meta = {"name": filename, "parents": [folder_id]}
        f = service.files().create(body=meta, media_body=media, fields="id").execute()
        print(f"  ✓ Uploaded '{filename}' (id: {f['id']})")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
def main():
    print("\n═══════════════════════════════════════════════")
    print("  Recipe Booklet Updater")
    print("═══════════════════════════════════════════════\n")

    # 1. Authenticate
    print("[ 1 / 6 ]  Authenticating with Google Drive …")
    service = get_drive_service()
    print("  ✓ Authenticated\n")

    # 2. Download master booklet
    print("[ 2 / 6 ]  Downloading master booklet …")
    download_file(service, SOURCE_FILE_ID, TEMP_BOOKLET)
    print()

    # 3. Parse index pages
    print("[ 3 / 6 ]  Parsing index pages (7–10) for existing recipe names …")
    existing_names = parse_index_pages(TEMP_BOOKLET, start_page=7, end_page=10)
    print()

    # 4. Load JSON + find new recipes
    print("[ 4 / 6 ]  Loading local JSON and identifying new recipes …")
    json_path = SCRIPT_DIR / JSON_FILE
    if not json_path.exists():
        raise FileNotFoundError(f"JSON file not found: {json_path}")
    json_recipes = load_json_recipes(json_path)
    new_recipes  = find_new_recipes(json_recipes, existing_names)
    print()

    if not new_recipes:
        print("  ℹ No new recipes found. Nothing to do.")
        return

    # 5. Map existing recipe pages
    print("[ 5 / 6 ]  Assembling PDFs …")
    existing_page_map = map_recipes_to_pages(TEMP_BOOKLET, recipe_start_page=11)
    json_dir = json_path.parent
    new_pdf_bytes, latest_pdf_bytes = assemble_pdfs(
        TEMP_BOOKLET, new_recipes, json_recipes, existing_page_map, json_dir
    )
    print(
        f"  ✓ new_recipes.pdf          : {len(new_pdf_bytes) // 1024} KB\n"
        f"  ✓ latest_recipe_booklet.pdf: {len(latest_pdf_bytes) // 1024} KB\n"
    )

    # Save local copies
    OUT_NEW.write_bytes(new_pdf_bytes)
    OUT_LATEST.write_bytes(latest_pdf_bytes)

    # 6. Upload to Drive
    print("[ 6 / 6 ]  Uploading to Google Drive …")
    upload_or_replace(service, TARGET_FOLDER_ID, "new_recipes.pdf", new_pdf_bytes)
    upload_or_replace(service, TARGET_FOLDER_ID, "latest_recipe_booklet.pdf", latest_pdf_bytes)

    print("\n  ✓ Done! Both PDFs are live in your Drive folder.\n")


if __name__ == "__main__":
    main()