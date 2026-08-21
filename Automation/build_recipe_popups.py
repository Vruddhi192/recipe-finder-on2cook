#!/usr/bin/env python3
"""
build_recipe_popups.py

Replaces the old 3-script pipeline

    generate_popup_images.py  ->  final_corrected_recipe_generator.py
                              ->  add_disclaimer_onpopup_pdf.py

with ONE pass per recipe ZIP that produces ONE final PDF, stacked exactly
like add_disclaimer_onpopup_pdf.py used to do it:

    1. [optional] ingredient-collage image   (if found for this recipe)
    2. the recipe PDF content                 (image / times / ingredients /
                                                 timeline -- unchanged logic,
                                                 generated in-memory)
    3. bilingual (Hindi + English) step disclaimer

There is no more "base pdf in test_popup_images/" followed by a second
"merged pdf in popup_images_with_cover/" pass -- one zip in, one finished
PDF out.

------------------------------------------------------------------------
PATCH NOTES (this version) -- ROOT CAUSE FOUND
------------------------------------------------------------------------
Symptom reported: the final PDF skips both the ingredient image and the
disclaimer step text entirely.

Confirmed NOT the cause: build_ingredient_image_html() and
build_addition_html() (in add_disclaimer_onpopup_pdf.py /
add_recipe_cover_pages.py) are both correct on their own --
build_ingredient_image_html() already writes an absolute file:// URI via
`image_path.resolve().as_uri()`, and build_addition_html() embeds the
step text directly into the HTML. No bug there.

ACTUAL ROOT CAUSE: this script's own `find_ingredient_image()` was
re-implementing a lookup that already has a single authoritative source.
recipes_fix.json carries a precomputed "IngredientImage" field per recipe
(written once by parse_txt_to_json.py -- see the correct pattern in
add_recipe_cover_pages.py's own find_ingredient_image(recipe), which just
reads recipe["IngredientImage"] and confirms the file exists). This
script instead guessed by matching the ZIP's filename stem against
ingredient-image filenames character-for-character (case/whitespace
insensitive only) -- so any naming mismatch (spaces vs underscores, an
extra word, different capitalization convention) makes the lookup return
None silently, and the image segment never gets added. That's the
"duplicated lookup logic" failure mode.

FIX: this script now loads recipes_fix.json once, builds an index keyed
by the same folder-stem convention download_zips.py/all-in-one.py already
use (Path(recipe["Image"]).stem), and looks up the recipe entry for each
zip so it can use recipe["IngredientImage"] directly -- the same
authoritative field, instead of re-deriving a guess. If recipes_fix.json
can't be found/loaded, or a given recipe has no entry there, it falls
back to the old filename-stem guess (better than nothing, logged clearly
as a fallback so it's obvious in the output which path was used).

Also fixed: exceptions during rendering were being shown as `str(e)`
only, which can hide the real cause (e.g. wkhtmltopdf failing for a
reason unrelated to "not found"). Both segments' except blocks now print
the full traceback, so a failure is never silently reduced to a vague
one-line note.

`--debug-html` CLI flag is still available: keeps the intermediate
.src.html files instead of deleting them, so you can open them in a
browser and see exactly what wkhtmltopdf was given.
------------------------------------------------------------------------

WIDTH IS FIXED, HEIGHT IS NOT -- BUT IT STILL TERMINATES
-----------------------------------------------------------
The page width is fixed: it's always taken from the base recipe PDF
(210mm, same as final_corrected_recipe_generator.py has always used).

The page HEIGHT is deliberately NOT fixed and NOT capped -- it is exactly
the sum of however tall the ingredient-image segment, the recipe segment,
and the disclaimer segment each turn out to be, plus small fixed gaps
between them. Nothing is truncated or scaled down to hit a target height;
a recipe with more steps just gets a taller disclaimer block, a recipe
with no ingredient image just doesn't get that segment at all.

What stops this from being open-ended is the render mechanism itself, not
a content limit: each add-on segment is first rendered by wkhtmltopdf onto
a generously tall (but finite) throwaway canvas
(RENDER_CANVAS_HEIGHT_MM), then immediately measured and cropped down
(crop_to_content, via PyMuPDF) to the exact pixel height its real content
used. That crop step is what guarantees the process always terminates with
a page sized to its content -- it never "keeps going."

Usage:
    python build_recipe_popups.py <zip_file>                 [output_dir]
    python build_recipe_popups.py --dir <zip_dir_or_glob>     <output_dir>
    python build_recipe_popups.py <zip_file> --debug-html     # keep .src.html for inspection
"""

import argparse
import glob
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import traceback
import zipfile
from pathlib import Path
from urllib.parse import quote, urlparse
from urllib.request import url2pathname
import fitz  # PyMuPDF -- only used to crop rendered segments to content height
from pypdf import PageObject, PdfReader, PdfWriter, Transformation
from reportlab.lib.units import mm

# The two existing scripts are kept as-is and imported as libraries --
# nothing about their own internal logic changes, we just call into them.
from final_corrected_recipe_generator import (
    RecipePDFGenerator,
    safe_int,
    sanitize_filename,
)

# PATCH: the module name that actually holds these functions on disk may be
# add_disclaimer_onpopup_pdf.py OR add_recipe_cover_pages.py depending on
# which version is currently deployed -- try both so this script doesn't
# silently import a stale/wrong copy of build_ingredient_image_html /
# build_addition_html.
try:
    from add_disclaimer_onpopup_pdf import (
        escape_html,
        build_addition_html,
        build_ingredient_image_html,
        ensure_hindi_font_installed,
        find_wkhtmltopdf,
        groq_build_steps,
        GROQ_API_KEY,
        FONT_FILE,
        CLOSING_NOTE_EN,
        CLOSING_NOTE_HI,
    )
    _SOURCE_MODULE = "add_disclaimer_onpopup_pdf"
except ImportError:
    from add_recipe_cover_pages import (
        escape_html,
        build_addition_html,
        build_ingredient_image_html,
        ensure_hindi_font_installed,
        find_wkhtmltopdf,
        groq_build_steps,
        GROQ_API_KEY,
        FONT_FILE,
        CLOSING_NOTE_EN,
        CLOSING_NOTE_HI,
    )
    _SOURCE_MODULE = "add_recipe_cover_pages"

# ===============================
# CONFIG
# ===============================
INGREDIENT_IMAGE_DIR = (Path(__file__).parent / ".." / "ingredient_images").resolve()
DEFAULT_OUTPUT_DIR = (Path(__file__).parent / ".." / "final_recipe_pdfs").resolve()
RECIPES_JSON = (Path(__file__).parent / ".." / "recipes_fix.json").resolve()
FONTS_DIR = Path(__file__).parent / ".." / "Fonts"
STIRRER_SVG = Path(__file__).parent / ".." / "Stirrer.svg"
PT_PER_MM = 72 / 25.4
GAP_PT = 10  # vertical gap between stacked segments

# Set at runtime by --debug-html
KEEP_DEBUG_HTML = False

# ---- height guardrail --------------------------------------------------
# The page WIDTH is fixed (it comes from the base recipe PDF, always
# 210mm). The page HEIGHT is never fixed -- it's the sum of however tall
# the image segment, recipe segment, and disclaimer segment actually turn
# out to be. Nothing is capped or truncated to force a target height.
#
# The only thing RENDER_CANVAS_HEIGHT_MM controls is the throwaway canvas
# wkhtmltopdf renders each add-on segment onto *before* it gets measured
# and cropped down to its real content height (see crop_to_content below).
# It just needs to be "larger than any real segment could plausibly be" so
# that wkhtmltopdf never runs out of room mid-content -- it is NOT a limit
# on the final page. This is what stops the process from being genuinely
# open-ended/unbounded while still letting the final height track content
# exactly.
RENDER_CANVAS_HEIGHT_MM = 4000.0
# -------------------------------------------------------------------------


# ===============================
# INGREDIENT IMAGE LOOKUP
# ===============================
# PRIMARY path: recipes_fix.json's precomputed "IngredientImage" field
# (the single source of truth -- see add_recipe_cover_pages.py's own
# find_ingredient_image(recipe)). FALLBACK path: guess by matching the
# zip's filename stem against files in INGREDIENT_IMAGE_DIR, kept only
# for recipes that have no recipes_fix.json entry yet.

_RECIPES_INDEX = None  # lazy-loaded, keyed by folder-stem.upper()


def _load_recipes_index():
    """
    Loads recipes_fix.json once per run and indexes it by the same
    folder-stem convention download_zips.py / all-in-one.py already use:
    Path(recipe["Image"]).stem (see recipe_folder_name() in
    add_recipe_cover_pages.py). Returns {} (not None) on any failure so
    callers can treat "no index" and "empty index" the same way.
    """
    global _RECIPES_INDEX
    if _RECIPES_INDEX is not None:
        return _RECIPES_INDEX

    _RECIPES_INDEX = {}
    if not RECIPES_JSON.exists():
        print(f"  \u26A0\uFE0F  recipes_fix.json not found at {RECIPES_JSON} -- "
              f"ingredient-image lookup will fall back to filename-stem guessing "
              f"for every recipe (this is the less reliable path).")
        return _RECIPES_INDEX

    try:
        with open(RECIPES_JSON, "r", encoding="utf-8") as f:
            recipes = json.load(f)
    except Exception as e:
        print(f"  \u26A0\uFE0F  Could not read recipes_fix.json ({e}) -- "
              f"falling back to filename-stem guessing for every recipe.")
        return _RECIPES_INDEX

    for recipe in recipes:
        image_field = recipe.get("Image", "")
        if not image_field:
            continue
        stem = Path(image_field).stem.strip().upper()
        if stem:
            _RECIPES_INDEX[stem] = recipe

    print(f"  \u2705 Loaded recipes_fix.json: {len(_RECIPES_INDEX)} recipe(s) indexed "
          f"by folder stem")
    return _RECIPES_INDEX


def _find_ingredient_image_via_field(recipe_stem):
    """Authoritative lookup: recipes_fix.json's precomputed IngredientImage field."""
    index = _load_recipes_index()
    recipe = index.get(recipe_stem.strip().upper())
    if recipe is None:
        return None, "no recipes_fix.json entry for this stem"

    field = recipe.get("IngredientImage", "")
    if not field:
        return None, "recipes_fix.json entry has no IngredientImage field"

    candidate = INGREDIENT_IMAGE_DIR / Path(field).name
    if not candidate.exists():
        return None, f"IngredientImage field points to {candidate}, which doesn't exist on disk"

    return candidate, None


def _find_ingredient_image_via_stem_guess(recipe_stem):
    """Fallback only: guess by matching the zip's filename stem against
    files in INGREDIENT_IMAGE_DIR. Less reliable than the field lookup --
    only used when recipes_fix.json has no entry for this recipe."""
    if not INGREDIENT_IMAGE_DIR.is_dir():
        return None
    candidates = []
    for ext in ("jpg", "jpeg", "png", "webp"):
        candidates.extend(INGREDIENT_IMAGE_DIR.glob(f"*.{ext}"))
    stem_lower = recipe_stem.strip().lower()
    for candidate in candidates:
        if candidate.stem.strip().lower() == stem_lower:
            return candidate
    return None


def find_ingredient_image(recipe_stem):
    image, reason = _find_ingredient_image_via_field(recipe_stem)
    if image is not None:
        print(f"  \U0001F5BC  Found ingredient image for '{recipe_stem}' via recipes_fix.json "
              f"IngredientImage field: {image}")
        return image

    print(f"  \u2139\uFE0F  Authoritative lookup failed for '{recipe_stem}' ({reason}) -- "
          f"trying filename-stem fallback...")
    image = _find_ingredient_image_via_stem_guess(recipe_stem)
    if image is not None:
        print(f"  \U0001F5BC  Found ingredient image for '{recipe_stem}' via filename-stem "
              f"fallback: {image}")
    return image


# ===============================
# PATCH: fix relative/broken <img src="..."> before wkhtmltopdf ever sees it
# ===============================

_IMG_SRC_RE = re.compile(r'(<img\b[^>]*\bsrc=)(["\'])(.*?)\2', re.IGNORECASE)


def _to_file_uri(path_str, base_dir=None):
    if path_str.startswith(("http://", "https://", "data:", "file://")):
        return path_str
    p = Path(path_str)
    if not p.is_absolute() and base_dir is not None:
        p = Path(base_dir) / p
    p = p.resolve()
    return p.as_uri()   # correctly handles Windows drive letters + spaces


def _fix_relative_img_srcs(html, fallback_image_path=None):
    def _replace(m):
        prefix, quote_char, src = m.group(1), m.group(2), m.group(3)
        fixed = _to_file_uri(src)
        if fixed.startswith("file://"):
            local_path = Path(url2pathname(urlparse(fixed).path))
            if not local_path.exists() and fallback_image_path is not None:
                fixed = _to_file_uri(str(fallback_image_path))
        return f"{prefix}{quote_char}{fixed}{quote_char}"

    return _IMG_SRC_RE.sub(_replace, html)


# ===============================
# RAW STEP DATA (built directly from the zip's own parsed JSON)
# ===============================

def build_raw_steps(recipe_data):
    """
    Mirrors add_disclaimer_onpopup_pdf.get_step_ingredients(), but reads
    straight from the JSON we already unzipped -- no EXTRACT_ROOT re-scan.
    IMPORTANT: call this BEFORE generator.generate_pdf() runs, since that
    call merges zero-duration steps into their neighbours in place, which
    would otherwise collapse some of the narration steps.
    """
    steps = []
    for step in recipe_data.get("Instruction", []):
        text = step.get("app_audio") or f"{step.get('Audio', '')} {step.get('Text', '')}".strip()
        steps.append({
            "step": text,
            "lid": str(step.get("lid", "")).lower(),
            "duration": step.get("durationInSec"),
        })
    if steps:
        return steps
    # fallback: no Instruction list, use raw ingredient titles
    return [{"step": ing.get("title", ""), "lid": ""} for ing in recipe_data.get("Ingredients", [])]


def _raw_fallback_steps(raw_steps):
    """Builds english_steps/hindi_steps straight from raw_steps, no Groq."""
    english_steps, hindi_steps = [], []
    for s in raw_steps:
        step, lid = s.get("step", ""), (s.get("lid") or "").lower()
        if lid == "open":
            english_steps.append(f"{step} (Lid Open)")
            hindi_steps.append(f"{step} (ढक्कन खुला रखें)")
        elif lid == "close":
            english_steps.append(f"{step} (Lid Closed)")
            hindi_steps.append(f"{step} (ढक्कन बंद रखें)")
        else:
            english_steps.append(step)
            hindi_steps.append(step)
    return english_steps, hindi_steps


# ===============================
# SEGMENT RENDERING (capped -- this IS the guardrail)
# ===============================

def render_html_to_pdf(html, out_path, width_mm, canvas_height_mm=RENDER_CANVAS_HEIGHT_MM):
    if html is None:
        raise RuntimeError("render_html_to_pdf received None instead of HTML string — "
                            "check _fix_relative_img_srcs() has a return statement.")
    html_path = out_path.with_suffix(".src.html")
    html_path.write_text(html, encoding="utf-8")

    wkhtmltopdf = find_wkhtmltopdf()
    cmd = [
        wkhtmltopdf,
        "--enable-local-file-access",
        "--quiet",
        # PATCH: prevents a single failed resource (image/font) from aborting
        # the ENTIRE render with a non-zero exit code (which is what turned
        # "ContentOperationNotPermittedError" into a hard failure that wiped
        # out the whole segment). With these set to "ignore", wkhtmltopdf
        # renders whatever it can and still returns success -- the local
        # temp-dir copy fix above should mean this never actually triggers,
        # but it's a safety net against the segment vanishing entirely if a
        # resource issue crops up again for a different reason.
        "--load-error-handling", "ignore",
        "--load-media-error-handling", "ignore",
        "--page-width", f"{width_mm}mm",
        "--page-height", f"{canvas_height_mm}mm",
        "--margin-top", "0mm",
        "--margin-bottom", "0mm",
        "--margin-left", "0mm",
        "--margin-right", "0mm",
        "--encoding", "utf-8",
        str(html_path),
        str(out_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)

    if KEEP_DEBUG_HTML:
        print(f"  [debug-html] kept: {html_path}")
    else:
        html_path.unlink(missing_ok=True)

    if result.returncode != 0:
        raise RuntimeError(result.stderr)


def crop_to_content(src_path, dst_path, bottom_margin_mm=6):
    """Identical logic to add_disclaimer_onpopup_pdf.crop_to_content: crop the
    rendered page down to however much content it actually has (which, with
    the capped page-height above, can never exceed the budget we gave it)."""
    doc = fitz.open(str(src_path))
    page = doc[0]

    max_y1 = 0.0
    text_blocks = page.get_text("blocks")
    if text_blocks:
        max_y1 = max(b[3] for b in text_blocks)
    for img in page.get_image_info():
        bbox = img.get("bbox")
        if bbox:
            max_y1 = max(max_y1, bbox[3])
    if max_y1 <= 0:
        max_y1 = page.rect.height

    bottom_margin_pt = bottom_margin_mm * PT_PER_MM
    content_height_pt = min(max_y1 + bottom_margin_pt, page.rect.height)

    rect = fitz.Rect(0, 0, page.rect.width, content_height_pt)
    page.set_cropbox(rect)
    page.set_mediabox(rect)

    doc.save(str(dst_path))
    doc.close()
    return content_height_pt


def build_segment_pdf(html, tmp_dir, stem_tag, width_mm):
    """Render -> crop to real content height. Returns
    (cropped_pdf_path, content_height_pt) or raises RuntimeError."""
    raw_pdf = tmp_dir / f"{stem_tag}.raw.pdf"
    cropped_pdf = tmp_dir / f"{stem_tag}.pdf"
    render_html_to_pdf(html, raw_pdf, width_mm)
    content_height_pt = crop_to_content(raw_pdf, cropped_pdf)
    raw_pdf.unlink(missing_ok=True)
    return cropped_pdf, content_height_pt


# ===============================
# STACKING (same mechanics as add_disclaimer_onpopup_pdf.stack_segments)
# ===============================

def stack_segments(base_pdf_path, top_segments, bottom_segments, out_path, gap_pt=GAP_PT):
    reader_base = PdfReader(str(base_pdf_path))
    top_pages = [(PdfReader(str(p)).pages[0], h) for p, h in top_segments]
    bottom_pages = [(PdfReader(str(p)).pages[0], h) for p, h in bottom_segments]

    top_extra = sum(h + gap_pt for _, h in top_pages)
    bottom_extra = sum(h + gap_pt for _, h in bottom_pages)

    writer = PdfWriter()
    n_pages = len(reader_base.pages)

    for i, page in enumerate(reader_base.pages):
        if i < n_pages - 1:
            writer.add_page(page)
            continue

        orig_w = float(page.mediabox.width)
        orig_h = float(page.mediabox.height)
        new_h = orig_h + top_extra + bottom_extra

        grown_page = PageObject.create_blank_page(width=orig_w, height=new_h)
        grown_page.merge_transformed_page(page, Transformation().translate(tx=0, ty=bottom_extra))

        cursor_y = new_h
        for seg_page, seg_h in top_pages:
            cursor_y -= seg_h
            grown_page.merge_transformed_page(seg_page, Transformation().translate(tx=0, ty=cursor_y))
            cursor_y -= gap_pt

        cursor_y = bottom_extra
        for idx, (seg_page, seg_h) in enumerate(bottom_pages):
            if idx > 0:
                cursor_y -= gap_pt
            cursor_y -= seg_h
            grown_page.merge_transformed_page(seg_page, Transformation().translate(tx=0, ty=cursor_y))

        writer.add_page(grown_page)

    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Write to a LOCAL, non-OneDrive-synced temp location first. OneDrive's
    # Files On-Demand sync can hold a transient exclusive lock on a file the
    # instant it's created/modified inside a synced folder -- writing there
    # directly is exactly what was causing the repeated PermissionError,
    # even with retries, because the lock can outlast a few retry attempts.
    local_tmp = Path(tempfile.gettempdir()) / f"_popup_build_{out_path.name}"
    with open(local_tmp, "wb") as f:
        writer.write(f)

    # Now move the finished file from local disk into the OneDrive folder.
    # Retry with backoff, and clear any stale read-only flag OneDrive
    # sometimes leaves on the destination after a sync conflict.
    last_err = None
    for attempt in range(8):
        try:
            if out_path.exists():
                try:
                    os.chmod(out_path, stat.S_IWRITE)
                except OSError:
                    pass
                out_path.unlink()
            shutil.move(str(local_tmp), str(out_path))
            last_err = None
            break
        except (PermissionError, OSError) as e:
            last_err = e
            wait = min(1 * (attempt + 1), 5)
            print(f"  ⚠️  '{out_path.name}' locked by OneDrive/another process "
                  f"(attempt {attempt + 1}/8) -- retrying in {wait}s...")
            time.sleep(wait)

    if last_err is not None:
        # Give up moving into OneDrive -- the file is safe on local disk
        # either way, so the run still succeeds and nothing is lost.
        print(f"  ⚠️  Could not move into OneDrive folder after retries "
              f"({last_err}). Finished PDF is available locally at:\n"
              f"      {local_tmp}")
        return local_tmp

    return out_path

def get_page_width_mm(pdf_path):
    reader = PdfReader(str(pdf_path))
    width_pt = float(reader.pages[-1].mediabox.width)
    return width_pt / PT_PER_MM


def get_page_height_mm(pdf_path):
    reader = PdfReader(str(pdf_path))
    height_pt = float(reader.pages[-1].mediabox.height)
    return height_pt / PT_PER_MM


# ===============================
# MAIN PER-RECIPE PIPELINE
# ===============================

def process_recipe_zip(zip_path, output_dir, seconds_per_bar=9):
    zip_path = Path(zip_path)
    output_dir = Path(output_dir)
    recipe_stem = zip_path.stem  # same convention download_zips.py uses as the recipe key

    with tempfile.TemporaryDirectory() as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)

        # --- 1. unzip and load the recipe JSON + image -----------------
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(tmp_dir)
        json_file = image_file = None
        for f in tmp_dir.iterdir():
            if f.suffix.lower() in (".txt", ".json"):
                json_file = f
            elif f.suffix.lower() in (".jpg", ".jpeg", ".png"):
                image_file = f
        if not json_file:
            return f"FAIL  {recipe_stem}: no JSON/TXT found in zip"

        with open(json_file, "r", encoding="utf-8") as f:
            recipe_data = json.load(f)

        recipe_name = recipe_data.get("name", [recipe_stem])[0]

        # Capture raw step data for narration BEFORE generate_pdf() merges
        # zero-duration steps into their neighbours in place.
        raw_steps = build_raw_steps(recipe_data)

        # --- 2. generate the base recipe PDF (in-memory logic unchanged) ---
        base_pdf_path = tmp_dir / "base.pdf"
        generator = RecipePDFGenerator()
        generator.generate_pdf(recipe_data, str(image_file) if image_file else None,
                                str(base_pdf_path), seconds_per_bar)

        width_mm = get_page_width_mm(base_pdf_path)  # fixed width, taken from the base recipe page
        note = ""

        # --- ingredient image segment (top), sized to its own content ---
        top_segments = []
        ingredient_image = find_ingredient_image(recipe_stem)  # logs its own outcome
        if ingredient_image:
            try:
                # PATCH (root cause found via user's traceback):
                # wkhtmltopdf raises "ContentOperationNotPermittedError" when the
                # rendered HTML (in Python's temp dir, e.g. C:\...\AppData\Local\Temp\...)
                # references an image on a DIFFERENT DRIVE (e.g. D:\...\ingredient_images\...).
                # Qt WebKit's local-file security policy blocks this cross-drive access
                # even with --enable-local-file-access set. Copying the image into the
                # SAME temp dir as the HTML makes it same-drive/same-folder, which
                # resolves the restriction at the source.
                local_image_copy = tmp_dir / f"ingredient_source{ingredient_image.suffix}"
                shutil.copy(ingredient_image, local_image_copy)

                img_html = build_ingredient_image_html(recipe_name, local_image_copy, width_mm)
                # Safety net only -- build_ingredient_image_html() already writes an
                # absolute file:// URI via .resolve().as_uri(), so this is normally a
                # no-op. Kept in case a future version of that function regresses.
                img_html = _fix_relative_img_srcs(img_html, fallback_image_path=local_image_copy)
                img_pdf, img_h = build_segment_pdf(img_html, tmp_dir, "ingredients", width_mm)
                top_segments.append((img_pdf, img_h))
                print(f"  \u2705 Ingredient image segment rendered ({img_h / PT_PER_MM:.0f}mm tall)")
            except Exception as e:
                print(f"  \u274C Ingredient image segment FAILED to render:")
                traceback.print_exc()
                note += f" [ingredient image failed: {e}]"
        else:
            print(f"  \u2139\uFE0F  No ingredient image found for '{recipe_stem}' "
                  f"(checked both recipes_fix.json's IngredientImage field and "
                  f"filename-stem matching in {INGREDIENT_IMAGE_DIR})")

        # --- disclaimer segment (bottom), sized to its own content -------
        english_steps, hindi_steps = [], []
        groq_failed_or_empty = False
        try:
            english_steps, hindi_steps = groq_build_steps(recipe_name, raw_steps)
            if raw_steps and not english_steps and not hindi_steps:
                # PATCH: Groq "succeeded" but returned nothing usable --
                # previously this silently produced a blank disclaimer.
                print(f"  \u26A0\uFE0F  Groq returned empty steps for {recipe_name} despite "
                      f"{len(raw_steps)} raw step(s) -- falling back to raw text.")
                groq_failed_or_empty = True
        except Exception as e:
            print(f"  ! Groq step-cleanup/translation failed for {recipe_name}: {e}. Using raw fallback text.")
            if not GROQ_API_KEY:
                print("     (GROQ_API_KEY is not set -- this is expected; raw fallback text will be used.)")
            else:
                traceback.print_exc()
            groq_failed_or_empty = True

        if groq_failed_or_empty:
            english_steps, hindi_steps = _raw_fallback_steps(raw_steps)

        bottom_segments = []
        disclaimer_html = build_addition_html(recipe_name, english_steps, hindi_steps, width_mm)
        # PATCH: same relative-src safety net, in case the disclaimer template
        # references any local image/background asset.
        disclaimer_html = _fix_relative_img_srcs(disclaimer_html)
        try:
            disclaimer_pdf, disclaimer_h = build_segment_pdf(disclaimer_html, tmp_dir, "disclaimer", width_mm)
            bottom_segments.append((disclaimer_pdf, disclaimer_h))
            print(f"  \u2705 Disclaimer segment rendered ({disclaimer_h / PT_PER_MM:.0f}mm tall, "
                  f"{len(english_steps)} step(s))")
        except Exception as e:
            print(f"  \u274C Disclaimer segment FAILED to render:")
            traceback.print_exc()
            note += f" [disclaimer failed: {e}]"

        # --- 3. stack everything into ONE final PDF ---------------------
        final_path = output_dir / f"{sanitize_filename(recipe_name)}.pdf"
        final_path = stack_segments(base_pdf_path, top_segments, bottom_segments, final_path)

        final_h = get_page_height_mm(final_path)
        img_tag = "+img" if top_segments else "no-img"
        return f"OK    {recipe_name}: {img_tag}, final height {final_h:.0f}mm -> {final_path}{note}"


# ===============================
# CLI
# ===============================

def find_zip_files(zip_input):
    zip_input = str(zip_input)
    if os.path.isdir(zip_input):
        return sorted(glob.glob(os.path.join(zip_input, "*.zip")))
    return sorted(glob.glob(zip_input))


def preflight_checks():
    """
    Runs once at startup and prints a clear pass/fail for every dependency
    that would otherwise cause the ingredient-image and disclaimer segments
    to silently disappear (both go through wkhtmltopdf, so if it's missing
    BOTH segments vanish and the output looks like just the base recipe PDF
    -- which is confusing unless you know to look here first).
    """
    print("=== Preflight checks ===")
    print(f"  \u2139\uFE0F  build_addition_html / build_ingredient_image_html imported from: "
          f"{_SOURCE_MODULE}.py")

    if RECIPES_JSON.exists():
        print(f"  \u2705 recipes_fix.json found: {RECIPES_JSON}")
    else:
        print(f"  \u26A0\uFE0F  recipes_fix.json NOT found at: {RECIPES_JSON} -- "
              "ingredient-image lookup will fall back to filename-stem guessing "
              "for every recipe, which is less reliable.")

    try:
        exe = find_wkhtmltopdf()
        print(f"  \u2705 wkhtmltopdf found: {exe}")
    except RuntimeError as e:
        print(f"  \u274C wkhtmltopdf NOT found: {e}")
        print("     -> Both the ingredient-image and disclaimer segments render through "
              "wkhtmltopdf. If it's missing, every recipe will silently come out as just "
              "the base recipe PDF with nothing stacked on top or bottom.")
        print("     -> Install it (e.g. `sudo apt-get install wkhtmltopdf` on Linux, or "
              "download it for Windows/Mac) and make sure it's on PATH.")

    if GROQ_API_KEY:
        print("  \u2705 GROQ_API_KEY is set")
    else:
        print("  \u26A0\uFE0F  GROQ_API_KEY is NOT set -- disclaimers will still render, "
              "but with raw/untranslated fallback text instead of Groq-cleaned steps.")

    if FONT_FILE.exists():
        print(f"  \u2705 Hindi font found: {FONT_FILE}")
    else:
        print(f"  \u274C Hindi font NOT found at: {FONT_FILE} -- Devanagari text may not render correctly.")

    if INGREDIENT_IMAGE_DIR.is_dir():
        n = sum(1 for _ in INGREDIENT_IMAGE_DIR.glob("*"))
        print(f"  \u2705 Ingredient image dir found: {INGREDIENT_IMAGE_DIR} ({n} file(s))")
    else:
        print(f"  \u26A0\uFE0F  Ingredient image dir NOT found: {INGREDIENT_IMAGE_DIR} -- "
              "every recipe will simply have no top image segment (this is expected/OK "
              "for recipes with no collage image, but not OK if the folder itself is missing).")

    print("========================\n")


def main():
    global KEEP_DEBUG_HTML

    parser = argparse.ArgumentParser()
    parser.add_argument("zip_input", help="a single .zip file, a directory of .zip files, or a glob pattern")
    parser.add_argument("output_dir", nargs="?", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--seconds-per-bar", type=int, default=9)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--debug-html", action="store_true",
                         help="keep the intermediate .src.html files next to the output "
                              "(actually written into the OS temp dir path printed per-segment) "
                              "so you can open them in a browser to see exactly what wkhtmltopdf saw.")
    args = parser.parse_args()

    KEEP_DEBUG_HTML = args.debug_html

    preflight_checks()

    ensure_hindi_font_installed()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if os.path.isfile(args.zip_input) and args.zip_input.lower().endswith(".zip"):
        zip_files = [args.zip_input]
    else:
        zip_files = find_zip_files(args.zip_input)

    if not zip_files:
        print(f"No zip files found for: {args.zip_input}")
        return

    if args.limit:
        zip_files = zip_files[:args.limit]

    print(f"Processing {len(zip_files)} zip(s)...\n")
    ok = fail = 0
    for zip_path in zip_files:
        try:
            result = process_recipe_zip(zip_path, output_dir, args.seconds_per_bar)
        except Exception as e:
            result = f"FAIL  {Path(zip_path).stem}: {e}"
        print(result)
        (ok := ok + 1) if result.startswith("OK") else (fail := fail + 1)

    print(f"\nDone. {ok} created, {fail} failed. Output dir: {output_dir}")


if __name__ == "__main__":
    main()