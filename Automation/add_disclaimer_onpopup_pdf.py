"""
add_recipe_cover_pages.py

Appends a bilingual (Hindi + English) instruction block BELOW the existing
content of every recipe's popup PDF -- it does NOT add a new page in front.
The page simply grows taller to fit the added text; it is never forced to
A4/A5 or any other fixed paper size.

For every recipe in recipes_fix.json this script:
  1. Finds the recipe's raw step data. It looks for the original TXT (JSON)
     file inside EXTRACT_ROOT/<recipe_key>/  -- <recipe_key> is taken from the
     "Image" field of the recipe (this is exactly how download_zips.py /
     all-in-one.py name that folder, so it lines up 1:1).
     If that folder/txt can't be found, it falls back to the "Ingredients"
     list that is already stored in recipes_fix.json for that recipe.
  2. Sends that raw step/ingredient data to the Groq API, which returns:
       - clean, natural-sounding English step sentences
       - natural (not word-for-word) Hindi translations of those same steps
     This replaces the old Google-Translate-based literal translation, so
     both the English phrasing and the Hindi translation actually read
     sensibly.
  3. Builds an HTML block (Hindi first, then English) listing:
        - "Thank you for downloading <Recipe Name>"
        - "Place the pan on the On2Cook device"
        - "Step 1: ...", "Step 2: ...", one line per step
        - a closing line: "Once the device stops cooking, open the lid and
          take out the food."
  4. Renders that block with wkhtmltopdf (so Hindi/Devanagari text shapes
     correctly -- reportlab alone does NOT reorder/combine Devanagari matras
     and conjuncts correctly) at the SAME WIDTH as the existing recipe PDF,
     rendered tall, then crops it down to the exact height its content
     actually uses (via PyMuPDF), so the added block is only as tall as it
     needs to be.
  5. Takes the existing recipe PDF's last page, grows its page height by
     that amount, keeps the existing content pinned at the top exactly as
     it was, and places the new Hindi/English block directly underneath it
     on the SAME page.

Requirements:
    pip install pypdf pymupdf requests --break-system-packages
    wkhtmltopdf must be installed and on PATH (sudo apt-get install wkhtmltopdf)
    A Groq API key must be available as the GROQ_API_KEY environment variable
    (https://console.groq.com/keys)

Usage:
    python3 add_recipe_cover_pages.py
    python3 add_recipe_cover_pages.py --overwrite      # write back into POPUP_DIR
    python3 add_recipe_cover_pages.py --limit 5         # test on first 5 recipes
    python3 add_recipe_cover_pages.py --recipe "CHICKEN BIRYANI"
"""

import argparse
import json
import os
import platform
import shutil
import subprocess
from pathlib import Path

import fitz  # PyMuPDF
import requests
from pypdf import PageObject, PdfReader, PdfWriter, Transformation

# ===============================
# CONFIG -- adjust these to match your real folders
# ===============================
BASE_DIR = Path(__file__).parent

RECIPES_JSON = BASE_DIR / ".." / "recipes_fix.json"        # same file all-in-one.py writes
EXTRACT_ROOT = (Path(__file__).parent / ".." / "updated_extracted").resolve()     # unzipped recipe folders (has the .txt files)
POPUP_DIR = (Path(__file__).parent / ".." / "test_popup_images").resolve()        # your EXISTING recipe pdfs live here
OUTPUT_DIR = (Path(__file__).parent / ".." / "popup_images_with_cover").resolve()  # NEW pdfs (existing + appended block) go here

FONT_NAME = "Noto Sans Devanagari"
FONT_FILE = Path(__file__).parent / ".." / "Fonts" / "NotoSansDevanagari.ttf"
SKIP_HIDDEN = True   # skip recipes marked "hidden": true in recipes_fix.json
font_url = FONT_FILE.resolve().as_uri()

PT_PER_MM = 72 / 25.4

# ===============================
# GROQ CONFIG (replaces the old Google-Translate step)
# ===============================
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

CLOSING_NOTE_EN = "Once the device stops cooking, open the lid and take out the food."
CLOSING_NOTE_HI = "जब डिवाइस पर खाना पकना बंद हो जाए, तो ढक्कन खोलकर खाना निकाल लें।"


def groq_build_steps(recipe_name, raw_steps):
    """
    Sends the raw (sometimes messy) per-step ingredient strings to Groq and
    asks for two aligned lists back: clean English step sentences, and a
    natural (not literal word-for-word) Hindi translation of each one.
    Raises on any failure -- caller decides the fallback.
    """
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY environment variable is not set.")

    system_msg = (
    "You are a careful bilingual (English/Hindi) recipe-instruction editor. "
    "You will be given raw step/ingredient text extracted from a cooking "
    "machine's recipe file. Turn it into a short, clear, natural-sounding "
    "ordered list of English steps describing exactly what to add or do, "
    "then give a natural Hindi translation of each step. "
    "Keep the number of Hindi steps EXACTLY equal to the number of English "
    "steps, in the same order. Do not invent cooking actions or ingredients "
    "that are not implied by the data. "
    "IMPORTANT LID INSTRUCTIONS:\n"
    "- Every single step MUST explicitly mention whether it is performed with "
    "the lid OPEN or the lid CLOSED.\n"
    "- If the raw recipe text explicitly indicates that a step is performed "
    "with the lid open, preserve that and state 'with the lid open'.\n"
    "- Otherwise, state 'Close the lid' or 'with the lid closed' as appropriate "
    "so that every step clearly specifies the lid position.\n"
    "- Never leave the lid state unspecified.\n"
    "- Reflect the same meaning naturally in the Hindi translation "
    "(ढक्कन खुला रखें / ढक्कन बंद करें / ढक्कन बंद रखें).\n"
    "Return ONLY valid JSON, no markdown fences, no commentary, in exactly "
    'this shape: {"english_steps": ["...", "..."], "hindi_steps": ["...", "..."]}'
)

    user_msg = (
    f"Recipe name: {recipe_name}\n\n"
    "Each item contains:\n"
    "- step : raw cooking instruction\n"
    "- lid  : 'open' or 'close'\n\n"
    f"{json.dumps(raw_steps, ensure_ascii=False, indent=2)}"
    )

    resp = requests.post(
        GROQ_URL,
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": GROQ_MODEL,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            "response_format": {"type": "json_object"},
        },
        timeout=60,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    data = json.loads(content)

    english_steps = [s.strip() for s in data.get("english_steps", []) if s.strip()]
    hindi_steps = [s.strip() for s in data.get("hindi_steps", []) if s.strip()]

    if len(english_steps) != len(hindi_steps):
        n = min(len(english_steps), len(hindi_steps))
        english_steps, hindi_steps = english_steps[:n], hindi_steps[:n]

    if not english_steps:
        raise RuntimeError("Groq returned no usable steps.")

    return english_steps, hindi_steps


# ===============================
# FONT SETUP (Devanagari / Hindi)
# ===============================

def ensure_hindi_font_installed():
    """
    On Windows we simply verify the font file exists.
    On Linux we install it into ~/.fonts and refresh fontconfig.
    """
    if not FONT_FILE.exists():
        print(f"WARNING: Hindi font not found at {FONT_FILE}")
        return

    if platform.system() == "Windows":
        return

    user_fonts_dir = Path.home() / ".fonts"
    user_fonts_dir.mkdir(parents=True, exist_ok=True)

    dest = user_fonts_dir / FONT_FILE.name
    if not dest.exists():
        shutil.copy(FONT_FILE, dest)

    subprocess.run(["fc-cache", "-f", str(user_fonts_dir)], capture_output=True, check=False)


def find_wkhtmltopdf():
    exe = shutil.which("wkhtmltopdf")
    if exe:
        return exe
    windows_default = r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
    if Path(windows_default).exists():
        return windows_default
    raise RuntimeError(
        "wkhtmltopdf not found on PATH (and not at the default Windows install "
        "location). Install it (e.g. `sudo apt-get install wkhtmltopdf`) or add "
        "it to PATH."
    )


# ===============================
# LOAD RECIPES
# ===============================

def load_recipes():
    with open(RECIPES_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


# ===============================
# STEP / INGREDIENT LOOKUP
# ===============================

def recipe_folder_name(recipe):
    """
    The download pipeline names Image/PopupImage after the recipe's folder
    name inside EXTRACT_ROOT (see all-in-one.py: recipe["Image"] =
    f"{IMAGE_DIR}/{recipe_key}.jpg"). So the stem of "Image" IS the folder
    name we need to look inside for the .txt file.
    """
    image_path = recipe.get("Image", "")
    if not image_path:
        return None
    return Path(image_path).stem


def find_txt_file(recipe):
    folder_name = recipe_folder_name(recipe)
    if not folder_name:
        return None
    folder = EXTRACT_ROOT / folder_name
    if not folder.is_dir():
        return None
    for f in folder.iterdir():
        if f.suffix.lower() == ".txt":
            return f
    return None


def get_step_ingredients(recipe):
    """
    Returns the ordered cooking steps along with lid state.
    """

    txt_path = find_txt_file(recipe)
    if txt_path:
        try:
            with open(txt_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            steps = []
            for step in data.get("Instruction", []):
                steps.append({
                    "step": step.get("app_audio")
                            or f"{step.get('Audio','')} {step.get('Text','')}".strip(),
                    "lid": step.get("lid", "").lower(),
                    "duration": step.get("durationInSec"),
                })

            if steps:
                return steps

        except Exception as e:
            print(f"Could not read {txt_path}: {e}")

    # fallback
    return [{"step": s, "lid": ""} for s in recipe.get("Ingredients", [])]

# ===============================
# HINDI + ENGLISH ADDITION BLOCK (HTML -> PDF)
# ===============================

def escape_html(text):
    return (text.replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def build_addition_html(recipe_name, english_steps, hindi_steps, width_mm):
    name = escape_html(recipe_name.title())
    side_margin_mm = max(4.0, width_mm * 0.05)

    hindi_items = "".join(
        f"<li><b>चरण {i}:</b> {escape_html(step)}</li>"
        for i, step in enumerate(hindi_steps, start=1)
    ) or "<li>रेसिपी के निर्देशों के अनुसार सामग्री डालें।</li>"

    english_items = "".join(
        f"<li><b>Step {i}:</b> {escape_html(step)}</li>"
        for i, step in enumerate(english_steps, start=1)
    ) or "<li>Add ingredients as per the recipe instructions.</li>"

    return f"""<!DOCTYPE html>
<html lang="hi">
<head>
<meta charset="utf-8">
<style>
  @font-face {{
      font-family: 'Hindi';
      src: url('{font_url}') format('truetype');
  }}
  * {{ box-sizing: border-box; }}
  body {{
      margin: 0;
      padding: 6mm {side_margin_mm:.1f}mm 4mm;
      width: {width_mm}mm;
      font-family: 'Hindi', sans-serif;
      color: #1a1a1a;
      font-size: 11.5pt;
      line-height: 1.45;
  }}
  .en {{ font-family: Arial, sans-serif; }}
  h2 {{ font-size: 12.5pt; margin: 0 0 2mm; }}
  p {{ margin: 0 0 2mm; }}
  ol {{ margin: 1mm 0 2mm 4mm; padding-left: 4mm; }}
  li {{ margin-bottom: 1.5mm; }}
  hr {{ border: none; border-top: 1px solid #ccc; margin: 4mm 0; }}
  .note {{ margin-top: 2mm; font-style: italic; }}
</style>
</head>
<body>
  <div class="block">
    <h2>&#128077; रेसिपी "{name}" डाउनलोड करने के लिए धन्यवाद!</h2>
    <p>कृपया पैन को On2Cook डिवाइस पर रखें, फिर नीचे दिए गए क्रम में सामग्री डालें:</p>
    <ol>{hindi_items}</ol>
    <p class="note">{CLOSING_NOTE_HI}</p>
  </div>

  <hr>

  <div class="block en">
    <h2>Thank you for downloading "{name}"!</h2>
    <p>Please place the pan on the On2Cook device, then add the ingredients in the order below:</p>
    <ol>{english_items}</ol>
    <p class="note">{CLOSING_NOTE_EN}</p>
  </div>
</body>
</html>
"""


def get_page_width_mm(pdf_path):
    """Read the existing recipe PDF's page width so the appended block is
    rendered at that same width (its height is auto-fit separately)."""
    try:
        reader = PdfReader(str(pdf_path))
        width_pt = float(reader.pages[-1].mediabox.width)
        return width_pt / PT_PER_MM
    except Exception:
        return 105  # ~A6 width fallback, only used if the PDF can't be read


def render_addition_pdf(html, out_path, width_mm, max_height_mm=4000):
    """
    wkhtmltopdf has no "auto height" option, so we render at a generous
    fixed height (4000mm -- comfortably more than any recipe's step list
    will ever need) and then crop it down to the real content height in
    crop_to_content(). Width matches the existing recipe PDF exactly.
    """
    html_path = out_path.with_suffix(".addition.html")
    html_path.write_text(html, encoding="utf-8")

    wkhtmltopdf = find_wkhtmltopdf()
    cmd = [
        wkhtmltopdf,
        "--enable-local-file-access",
        "--quiet",
        "--page-width", f"{width_mm}mm",
        "--page-height", f"{max_height_mm}mm",
        "--margin-top", "0mm",
        "--margin-bottom", "0mm",
        "--margin-left", "0mm",
        "--margin-right", "0mm",
        "--encoding", "utf-8",
        str(html_path),
        str(out_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    html_path.unlink(missing_ok=True)

    if result.returncode != 0:
        raise RuntimeError(result.stderr)


def crop_to_content(src_path, dst_path, bottom_margin_mm=6):
    """
    Measures where the rendered text actually ends (via PyMuPDF) and crops
    the tall placeholder page down to that real height, so the block we
    append is never taller than it needs to be -- no fixed A4/A5 sizing.
    Returns the final content height in points.
    """
    doc = fitz.open(str(src_path))
    page = doc[0]
    blocks = page.get_text("blocks")
    max_y1 = max((b[3] for b in blocks), default=page.rect.height)

    bottom_margin_pt = bottom_margin_mm * PT_PER_MM
    content_height_pt = min(max_y1 + bottom_margin_pt, page.rect.height)

    rect = fitz.Rect(0, 0, page.rect.width, content_height_pt)
    page.set_cropbox(rect)
    page.set_mediabox(rect)

    doc.save(str(dst_path))
    doc.close()
    return content_height_pt


# ===============================
# APPEND ADDITION BELOW EXISTING PAGE CONTENT
# ===============================

def append_below(existing_pdf_path, addition_pdf_path, addition_height_pt, out_path, gap_pt=10):
    """
    Grows the existing recipe PDF's LAST page downward by exactly the height
    of the addition block, keeps all of the original content pinned at the
    top exactly where it was, and places the new Hindi/English block right
    underneath it on that same (now taller) page. Every other page (if any)
    is copied through unchanged. The final page size is whatever it needs
    to be -- never forced to A4/A5/etc.
    """
    reader_existing = PdfReader(str(existing_pdf_path))
    reader_addition = PdfReader(str(addition_pdf_path))
    addition_page = reader_addition.pages[0]

    writer = PdfWriter()
    n_pages = len(reader_existing.pages)

    for i, page in enumerate(reader_existing.pages):
        if i < n_pages - 1:
            writer.add_page(page)
            continue

        orig_w = float(page.mediabox.width)
        orig_h = float(page.mediabox.height)
        new_h = orig_h + gap_pt + addition_height_pt

        grown_page = PageObject.create_blank_page(width=orig_w, height=new_h)
        # push the ORIGINAL content up so it keeps sitting at the top,
        # unchanged, exactly as it looked before
        grown_page.merge_transformed_page(
            page, Transformation().translate(tx=0, ty=gap_pt + addition_height_pt)
        )
        # the new Hindi/English block sits at the bottom (y=0)
        grown_page.merge_page(addition_page)

        writer.add_page(grown_page)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "wb") as f:
        writer.write(f)


# ===============================
# MAIN
# ===============================

def process_recipe(recipe, tmp_dir):
    name = recipe.get("Recipe Name", "UNKNOWN")

    popup_rel = recipe.get("PopupImage", "")
    if not popup_rel:
        return f"SKIP  {name}: no PopupImage field"

    existing_pdf = POPUP_DIR / Path(popup_rel).name
    if not existing_pdf.exists():
        return f"SKIP  {name}: existing pdf not found -> {existing_pdf}"

    raw_steps = get_step_ingredients(recipe)

    try:
        english_steps, hindi_steps = groq_build_steps(name, raw_steps)

    except Exception as e:
        print(f"  ! Groq step-cleanup/translation failed for {name}: {e}. Using raw fallback text.")

        english_steps = []
        hindi_steps = []

        for s in raw_steps:
            step = s.get("step", "")
            lid = s.get("lid", "").lower()

            if lid == "open":
                english_steps.append(f"{step} (Lid Open)")
                hindi_steps.append(f"{step} (ढक्कन खुला रखें)")
            elif lid == "close":
                english_steps.append(f"{step} (Lid Closed)")
                hindi_steps.append(f"{step} (ढक्कन बंद रखें)")
            else:
                english_steps.append(step)
                hindi_steps.append(step)

    width_mm = get_page_width_mm(existing_pdf)
    html = build_addition_html(name, english_steps, hindi_steps, width_mm)

    addition_raw_pdf = tmp_dir / f"{existing_pdf.stem}.addition.raw.pdf"
    addition_cropped_pdf = tmp_dir / f"{existing_pdf.stem}.addition.pdf"

    try:
        render_addition_pdf(html, addition_raw_pdf, width_mm)

        shutil.copy(addition_raw_pdf, addition_cropped_pdf)

        reader = PdfReader(str(addition_cropped_pdf))
        content_height_pt = float(reader.pages[0].mediabox.height)
    except RuntimeError as e:
        return f"FAIL  {name}: {e}"

    final_path = OUTPUT_DIR / existing_pdf.name
    append_below(existing_pdf, addition_cropped_pdf, content_height_pt, final_path)

    # addition_raw_pdf.unlink(missing_ok=True)
    # addition_cropped_pdf.unlink(missing_ok=True)

    return f"OK    {name}: {len(english_steps)} step(s) -> {final_path}"


def _process_recipes(recipes) -> tuple:
    """Shared processing loop used by both the CLI and the pipeline entry point."""
    tmp_dir = OUTPUT_DIR / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    print(f"Processing {len(recipes)} recipe(s)...\n")
    ok = fail = skip = 0
    for recipe in recipes:
        result = process_recipe(recipe, tmp_dir)
        print(result)
        if result.startswith("OK"):
            ok += 1
        elif result.startswith("SKIP"):
            skip += 1
        else:
            fail += 1

    shutil.rmtree(tmp_dir, ignore_errors=True)
    print(f"\nDone. {ok} created, {skip} skipped, {fail} failed.")
    return ok, skip, fail


def add_disclaimers_for_updated(updated_stems: set) -> tuple:
    """
    Pipeline entry point (called from all-in-one.py).

    Only processes recipes whose folder stem (derived from the "Image"
    field, same convention as download_zips.py / extract_zips.py) is in
    updated_stems -- i.e. only recipes that were newly downloaded or
    changed this run. This avoids re-running the Groq translation + PDF
    merge (slow, costs API calls) for the ~500+ recipes that didn't change.

    If updated_stems is empty, nothing is processed -- this is expected on
    a run where Smartsheet had no new/changed ZIPs.
    """
    ensure_hindi_font_installed()

    if not GROQ_API_KEY:
        print("WARNING: GROQ_API_KEY is not set -- every recipe will fall back "
              "to raw, untranslated text.")

    if not updated_stems:
        print("No updated recipes this run -- skipping disclaimer generation.")
        return 0, 0, 0

    recipes = load_recipes()
    if SKIP_HIDDEN:
        recipes = [r for r in recipes if not r.get("hidden")]

    recipes = [
        r for r in recipes
        if (stem := recipe_folder_name(r)) and stem.upper() in updated_stems
    ]

    return _process_recipes(recipes)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--overwrite", action="store_true",
                         help="write the merged pdf back into POPUP_DIR "
                              "(replacing the original) instead of OUTPUT_DIR")
    parser.add_argument("--limit", type=int, default=None,
                         help="only process the first N recipes (for testing)")
    parser.add_argument("--recipe", type=str, default=None,
                         help="only process the recipe with this exact name")
    args = parser.parse_args()

    global OUTPUT_DIR
    if args.overwrite:
        OUTPUT_DIR = POPUP_DIR

    if not GROQ_API_KEY:
        print("WARNING: GROQ_API_KEY is not set -- every recipe will fall back "
              "to raw, untranslated text. Set it with:\n"
              "  export GROQ_API_KEY=your_key_here\n")

    ensure_hindi_font_installed()
    recipes = load_recipes()

    if args.recipe:
        recipes = [r for r in recipes if r.get("Recipe Name") == args.recipe]

    if SKIP_HIDDEN:
        recipes = [r for r in recipes if not r.get("hidden")]

    if args.limit:
        recipes = recipes[:args.limit]

    _process_recipes(recipes)


if __name__ == "__main__":
    main()