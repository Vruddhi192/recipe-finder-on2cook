#!/usr/bin/env python3
"""
Script to update accessories in extracted recipe folders.
Creates both extracted output folders AND zip files.

Input structure: extracted/recipe1/recipe1.txt
Output: 
  - updated_extracted/ (folder with updated files)
  - updated_zips/ (folder with zip files)
"""

import os
import json
import zipfile
import shutil
import re
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
EXTRACT_ROOT      = "../extracted"
UPDATED_EXTRACTED = "../updated_extracted"
UPDATED_ZIPS      = "../updated_zips"

# Accessory mapping dictionary
ACCESSORY_MAPPING = {
    "1 Grill Mesh": "Mesh Mats",
    "1 Large Non Stick Mat": "MP Mats Big",
    "1 Non Stick": "Mesh Mats",
    "2 Grill Mesh": "Mesh Mats",
    "Cake Mold And Stirrer": "Cake Kit",
    "Coated Pan": "Pan Honeycomb (Non-Stick)",
    "Frying Basket": "Frying Kit",
    "Frying Basket & Stirrer": "Frying Kit",
    "Frying Basket And Stirrer": "Frying Kit",
    " Frying Basket And Stirrer": "Frying Kit",
    "FRYING BASKET AND STIRRER": "Frying Kit",
    "Frying Stirrer": "Frying Kit",
    "Gravy Stirrer": "Gravy Stirrer",
    "Grill Mesh": "Grill Mesh",
    "Grill Pan": "Grill Pan",
    "Idli Mold & Stirrer": "Idli Mold & Stirrer",
    "Large Non-Stick Mat": "MP Mats Big",
    "Momo Basket": "Momo Kit",
    "Momo Basket & Stirrer": "Momo Kit",
    "Momo Stirrer": "Momo Kit",
    "Non Coated Pan": "Pan Non-Coated (SS)",
    "NON COATED PAN": "Pan Non-Coated (SS)",
    "Non-Coated Pan": "Pan Non-Coated (SS)",
    "Noodles Starter": "Noodles Stirrer",
    "Noodles Stirrer": "Noodles Stirrer",
    "Pizza Basket & Stirrer": "Pizza Kit",
    "Pizza Basket With Stirrer": "Pizza Kit",
    "Pressure Cooker": "Pressure Cooker",
    "Rice Stirrer": "Rice Stirrer",
    "S. S Pan": "Pan Non-Coated (SS)",
    "S.S Pan": "Pan Non-Coated (SS)",
    "S S Pan": "Pan Non-Coated (SS)",
    "Silicon Rice Stirrer": "Rice Stirrer",
    "Silicon Starter": "Silicone Stirrer",
    "Silicon Stirer": "Silicone Stirrer",
    "Silicon Stirrer": "Silicone Stirrer",
    "Silicone Stirer": "Silicone Stirrer",
    "Silicone Stirrer": "Silicone Stirrer",
    "Silicone Stirrer With Hood": "Silicone Stirrer",
    "Small Non Stick Mat": "MP Mats Small",
    "Small Non-Stick Mat": "MP Mats Small",
    "Small Teflon Sheet": "Teflon Plate",
    "2 Teflon Plate": "Teflon Plate",
    "SS Pan": "Pan Non-Coated (SS)",
    "PAN NON COATED (SS)": "Pan Non-Coated (SS)",
    "Pan Non Coated  Ss": "Pan Non-Coated (SS)",
    "Pan Non Coated Ss": "Pan Non-Coated (SS)",
    "Pan Honeycomb (Coated)": "Pan Honeycomb (Non-Stick)",
    ":": "",
    " Pan Non Coated Ss": "Pan Non-Coated (SS)",
    "New Grilled Pan (Pre-Heated 90S)": "Grill Pan",
    "Teflon Plate/Sheet": "Teflon Plate",
    "Pan Honeycomb Coated": "Pan Honeycomb (Non-Stick)",
    "Honeycomb Pan": "Pan Honeycomb (Non-Stick)",
}


DESCRIPTION_FIXES = {
    "AMUL PARATHA ALOO": "AMUL ALOO PARATHA",
    "AMUL HASH BROWN & ALOO TIKKI": "AMUL HASH BROWN",
    "AMUL MASALA PANEER NUGGETS":"AMUL PANEER NUGGETS",
    "KOFTA FOR INDIAN RECIPES": "FRIED KOFTA",
    "GULAB JAMUN F": "GULAB JAMUN",
    "KERALA STYLE ULIWADA": "ULIWADA",
    "VADA FRY FOR VADA PAV":"VADA FRY",
    "CL STIR FRY SAU":"CHINESE CLEAR STIR FRY SAUCE",
    "STUFFED MIRCHI ROAST":"BHARELA MIRCHI",
    "PINEAPPLE SHEERA (PINEAPPLE KESARI BATH)":"KESARI BHAAT",
    "VEG THAI CURRY G":"THAI VEG GREEN CURRY",
    "BHARLA KARELA": "BHARELA KARELA",
    "NAMAK PARA (NAMKEEN)": "NAMAK PARA",
    "TANDOORI CHICKEN HALF": "TANDOORI CHICKEN",
    "FRESH ALOO SAMOSA": "ALOO SAMOSA",
    "FRESH CHEESE CORN SAMOSA": "CHEESE CORN SAMOSA",
    "FRESH CHICKEN SAMOSA": "CHICKEN SAMOSA",
    "BENGALI STYLE CHINGRI MALAI CURRY": "CHINGRI MALAI",
    "MAPPAS PRAWNS": "PRAWNS MAPPAS",
    "FRESH PANEER SAMOSA": "PANEER SAMOSA",
    "DAL DHOKLI (WHEAT DUMPLINGS IN LENTILS)": "DAL DHOKLI",
    "EGG CURRY DHABA STYLE": "EGG CURRY",
    "MALABAR PRAWN CURRY":"MALABAR PRAWN",
    "MAPPAS MUSHROOM": "MUSHROOM MAPPAS",
    "MUSHROOMS GHEE ROAST": "MUSHROOM GHEE ROAST",
    "RAJWADI DHOKLI SUBZI": "RAJWADI DHOKLI",
    "VEGETABLES JAIPURI":"VEG JAIPURI",
    "CHICKEN HANDI V2":"CHICKEN HANDI",
    "ESPAGNOLE SAUCE - CLASSIC FRENCH CUISINE BASE SAUCE":"ESPAGNOLE SAUCE",
    "VALOR PAPDI SHAK (BROAD BEAN STIRFRY)":"VALOR PAPDI SHAK",
    "MANGALOREAN CHICHEN CURRY":"KORI GASSI 2200 G",
    "MANGALOREAN CHICKEN CURRY":"KORI GASSI 650 G",
    "PANCHKUTIYU SHAK (GUJARATI STYLE WINTER VEG CURRY)":"PANCHKUTIYU SHAK",
    "SOAJI PANEER": "SAOJI PANEER",
    "VEGETABLES SUKTO": "VEG SUKTO",
    "CHICKEN CURRY VARUTHARACHA": "CHICKEN VARUTHARACHA",
    "CHICKEN KOSHA (BENGALI CUISINE)": "CHICKEN KOSHA",
    "SHORSHE LLISH":"SHORSHE ILISH",
    "SOAJI CHICKEN": "SAOJI CHICKEN",
    "SOAJI MUSHROOM": "SAOJI MUSHROOM",
    "VEGETABLE KURMA":"VEGETABLE KORMA",
    "LAKSA MALAYSIAN COCONUT BASED SOUP":"LAKSA SOUP",
    "BATHUA SUBZI (WHITE GOOSEFOOT LEAVES)" : "BATHUA SUBZI",
    "STEAM RICE WHITE & BROWN": "STEAM RICE",
    "ANDHARA MUSHROOM CURRY": "ANDHRA MUSHROOM CURRY",
    "ANDHARA PANEER CURRY": "ANDHRA PANEER CURRY",
    "CHICKEN SPAGHETTI V2": "CHICKEN SPAGHETTI",
    "ARRABBIATA BASE SAUCE": "ARRABBIATA SAUCE",
    "NORMAL COOK TIME 35 MINUTES":"ROSE SAUCE PASTA",
    "VIETNAMESE CHICKEN SOUP":"VIETNAMESE SOUP",
    "NOLEN GURER PAYES (BENGALI DESSERT)":"NOLEN GUR PAYES",
    "RAVA UPMA 2500GM": "RAVA UPMA 2500 G",
    "MAKHANI INDIAN BASE GRAVY": "MAKHANI GRAVY",
    "RAJMA MASALA GANDHINAGAR": "RAJMA MASALA",
    "BHUNA BESAN GANDHINAGAR": "BHUNA BESAN",
    "SOAJI CHICKEN": "SAOJI CHICKEN",
    "VEG BIRYANI 2800": "VEG BIRYANI 2800G",
    "VEG BIRYANI 3000": "VEG BIRYANI 3000G",
    "VEG BIRYANI 3200": "VEG BIRYANI 3200G",
    "CHICKEN BIRYANI 2800": "CHICKEN BIRYANI 2800G",
    "GHEE RICE GANDHINAGAR": "GHEE RICE",
    "PUNJABI KADHI GANDHINAGAR": "PUNJABI KADHI",
    "ONION RICE GANDHINAGAR": "ONION RICE",
    "PINDI CHOLE GANDHINAGAR": "PINDI CHOLE",
    "PINDI CHOLE MASALA GANDHINAGAR": "PINDI CHOLE MASALA",
    "KOFTA FRY GANDHINAGAR": "VEG KOFTA FRY",
    "PAV BHAJI GANDHINAGAR": "PAV BHAJI",
    "PANCHMEL DAL GANDHINAGAR": "PANCHMEL DAL",
    "GALOUTI KABAB": "GALOUTI KEBAB",
    "CHICKEN CACCIATORE ITALIAN STEW": "CHICKEN CACCIATORE",
    # "BAIGAN BHARTA": "BAINGAN BHARTA",
    "FISH MASALA CURRY":"FISH MASALA CURRY (MACHER JHOL)",
    "GUJARATI DAL GANDHINAGAR": "GUJARATI DAL",
    "BOILING CHOLE GANDHINAGAR": "BOILED CHOLE",
    "PENNE RED SAUCE PASTA ANTUNES":"PENNE RED SAUCE PASTA",
    "SAUTE POTATOES ANTUNE": "SAUTE POTATOES",
    "SAUTE CARROT ANTUNE": "SAUTE CARROT",
    "BROCCOLI & CAULIFLOWER SAUTE":"SAUTE BROCCOLI",
    "CHICKEN SAOJI":"SAOJI CHICKEN",
    "PENNE PASTA ANTUNE": "PENNE PASTA",
    "RAGI AMBALI (KANJI)":"RAGI AMBALI (KANJI)",
    "RAGI MILLET CAKE":"RAGI MILLET CAKE (FINGER MILLET CAKE)",
    "MILLET CHILLA (BAJRA - PEARL MILLET)":"MILLET CHILLA (BAJRA/PEARL MILLET)",
    "KOREAN RAMEN": "KOREAN RAMEN (NISSIN PKT)",
    "SCHEZWAN MOMO (FRY)":"SCHEZWAN MOMO (CHICKEN)",
    "DADU BIRYANI (THE SAME APPLICATION APPLIES TO ALL FIVE TYPES OF DADU'S BIRYANI)":"DADDU BIRYANI (SAME APPLICATION APPLIES TO ALL FIVE TYPES OF DADU'S BIRYANI)",
    
    "BOILED PASTA": "BOILED PASTA (PENNE)",
    "BROCCOLI  ANTUNES": "SAUTE BROCCOLI (ANTUNE)",
    "DALMA": "DALMA (WITH SOAKED TOOR DAL)",
    "FRY MOMO": "FRY MOMO (BATTER FRY CHICKEN MOMO)",
    "GRILL CHICKEN": "GRILL CHICKEN (NEW GRILL PAN)",
    "GRILL SANDWICH": "GRILL SANDWICH (NEW GRILL PAN)",
    "LEMON CORIANDER": "LEMON CORIANDER ( CHICKEN SOUP)",
    "MAGGI PREMIX": "MAGGI PREMIX (PENNE MAGGI WHITE SAUCE PREMIX PASTA)",
    "MALABAR BIRYANI": "MALABAR BIRYANI (CHICKEN JEERAKASAL RICE BIRYANI)",
    "ONION TOMATO 3KG": "ONION TOMATO 3KG (GRAVY)",
    "PANEER TIKKA DRY": "PANEER TIKKA DRY (NEW GRILL PAN)",
    "PENNE AL DENTE": "PENNE AL DENTE (PASTA ANTUNE)",
    "PENNE ALFREDO": "PENNE ALFREDO (ALFREDO SAUCE - WHITE SAUCE PASTA)",
    "PENNE ARR MAG": "PENNE ARRABIATA (MAGGI PREMIX)",
    "PENNE ARRABIATA": "PENNE ARRABIATA (WITH FRESH ARRABIATA SAUCE)",
    "PENNE PASTA 300G": "PENNE PASTA 300G (ALFREDO SAUCE - WHITE SAUCE PASTA)",
    "PENNE PESTO": "PENNE PESTO  (WITH FRESH BASIL PESTO)",
    "PENNE PESTO 300G": "PENNE PESTO 300G (WITH FRESH BASIL PESTO)",
    "PENNE PINK SAUCE": "PENNE PINK SAUCE (PASTA)",
    "PENNE RED A": "PENNE RED (RED SAUCE PASTA ANTUNE)",
    "PENNE RED SAUCE": "PENNE RED SAUCE (WITH FRESH ARRABIATA SAUCE)",
    "PENNE WHITE": "PENNE WHITE (PENNE MAGGI WHITE SAUCE PREMIX PASTA)",
    "PRASUMA CHI MOMO": "PRASUMA CHI MOMO (FROZEN CHICKEN MOMO 20PCS)",
    "RED SAUCE 300G": "RED SAUCE 300G (PENNE PASTA WITH FRESH TOMATO PUREE)",
    "RED SAUCE MAGGI": "RED SAUCE MAGGI (PENNE MAGGI RED SAUCE PREMIX PASTA)",
    "SAUTE CARROT A": "SAUTE CARROT (ANTUNE)",
    "SAUTE POTATOES A": "SAUTE POTATOES (ANTUNE)",
    "THAI CHI CURRY G": "THAI GREEN CURRY CHICKEN",
    "VEG CLUB SANDWICH": "VEG CLUB SANDWICH (WITH NEW GRILL PAN)",
    "LE CORIANDER SP": "VEG LEMON CORIANDER SOUP",
    "MAC N CHA MAG": "MAC AND CHEESE (MAGGI PREMIX)",
    "PENNE ALF MAG": "PENNE ALFREDO (MAGGI PREMIX)",
    "RED MAC MAG": "RED MACRONI PASTA (MAGGI PREMIX)",
}


def is_valid_accessory(line: str) -> bool:
    """
    Returns True if the line matches a known accessory — either a raw alias
    key in ACCESSORY_MAPPING (e.g. "Frying Basket And Stirrer") or its
    canonical mapped name (e.g. "Frying Kit"). Checking only canonical names
    would incorrectly reject every line still in its raw/alias form, since
    mapping happens AFTER this check, not before.
    """
    cleaned = line.strip().upper()
    if not cleaned:
        return False
    for old_acc, new_acc in ACCESSORY_MAPPING.items():
        if not old_acc:
            continue
        if old_acc.upper() in cleaned or cleaned in old_acc.upper():
            return True
        if new_acc and new_acc.upper() in cleaned:
            return True
    return False


def fix_description_text(description):
    # SYNC_PATCH: first-line-only — applied by sync_description_fixes.py
    # Only replaces on the first non-empty line to prevent double-suffix
    # corruption when the RHS contains the LHS as a substring.
    if not description:
        return description

    lines = description.split("\n")
    first_idx = next((i for i, l in enumerate(lines) if l.strip()), None)
    if first_idx is None:
        return description

    first_line = lines[first_idx]
    for old_text, new_text in DESCRIPTION_FIXES.items():
        new_first = re.sub(
            re.escape(old_text),
            new_text,
            first_line,
            flags=re.IGNORECASE
        )
        if new_first != first_line:
            lines[first_idx] = new_first
            break   # one fix per description — no chained matches

    return "\n".join(lines)


def update_accessories_in_description(description, accessory_mapping):
    if "ACCESSORIES" not in description.upper():
        return description

    lines = description.split('\n')
    updated_lines = []
    in_accessories = False

    for line in lines:
        stripped = line.strip()

        # Check if this line contains the ACCESSORIES header
        acc_match = re.match(r'^ACCESSORIES\s*(.*)', stripped, flags=re.IGNORECASE)
        if acc_match:
            in_accessories = True
            inline_item = acc_match.group(1).strip()  # text after "ACCESSORIES" on same line

            updated_lines.append('ACCESSORIES')  # write header cleanly

            # If there's an accessory inline, process and append it
            if inline_item:
                mapped = map_accessory(inline_item, accessory_mapping)
                if mapped:
                    updated_lines.append(mapped)
            continue

        # End accessories section on these keywords
        if in_accessories and stripped and (
            stripped.upper().startswith('FINAL') or
            stripped.upper().startswith('NORMAL') or
            stripped.upper().startswith('OTHER')
        ):
            in_accessories = False

        if in_accessories and stripped:
            if is_valid_accessory(stripped):
                mapped = map_accessory(stripped, accessory_mapping)
                updated_lines.append(mapped if mapped else line)
            else:
                # Unrecognized line inside the accessories block — treat it
                # as the end of the section rather than mapping/keeping it.
                in_accessories = False
                updated_lines.append(line)
        else:
            updated_lines.append(line)

    return '\n'.join(updated_lines)


def map_accessory(item, accessory_mapping):
    """Map a single accessory string to its standardized name."""
    best_match = None
    best_len = 0
    for old_acc, new_acc in accessory_mapping.items():
        if item.upper() == old_acc.upper():
            return new_acc  # exact match, return immediately
        elif old_acc.upper() in item.upper():
            if len(old_acc) > best_len:
                best_match = new_acc
                best_len = len(old_acc)
    return best_match  # None if no match found


def process_txt_file(txt_file_path, accessory_mapping):
    """
    Process a single txt file: read JSON, update accessories and description, return updated data.
    """
    try:
        # Read the file
        with open(txt_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse JSON
        data = json.loads(content)
        
        # Update description if it exists
        changed = False
        if 'description' in data:
            original_desc = data['description']
            
            # Step 1: Fix description text patterns
            fixed_desc = fix_description_text(original_desc)
            
            # Step 2: Update accessories
            updated_desc = update_accessories_in_description(fixed_desc, accessory_mapping)
            
            if original_desc != updated_desc:
                data['description'] = updated_desc
                changed = True
        
        return data, changed
        
    except json.JSONDecodeError as e:
        print(f"  ✗ Error parsing JSON: {e}")
        return None, False
    except Exception as e:
        print(f"  ✗ Error processing file: {e}")
        return None, False


def process_recipe_folder(recipe_folder_path, output_extracted_dir, output_zips_dir, accessory_mapping, updated_stems=None):
    """
    Process a single recipe folder.
    Creates both extracted output and zip file.
    """
    recipe_name = os.path.basename(recipe_folder_path)
    print(f"\n{'='*60}")
    print(f"Processing: {recipe_name}")
    print(f"{'='*60}")

    # Create output extracted folder for this recipe
    output_recipe_folder = os.path.join(output_extracted_dir, recipe_name)
    if os.path.exists(output_recipe_folder) and updated_stems and recipe_name.upper() in updated_stems:
        shutil.rmtree(output_recipe_folder, ignore_errors=True)
        print(f"  🔄 Clearing stale updated_extracted for: {recipe_name}")
    os.makedirs(output_recipe_folder, exist_ok=True)
    
    # Track if any changes were made
    any_changes = False
    processed_files = 0
    
    # Process all files in the recipe folder
    for filename in os.listdir(recipe_folder_path):
        source_file = os.path.join(recipe_folder_path, filename)
        dest_file = os.path.join(output_recipe_folder, filename)
        
        # If it's a txt file, process it
        if filename.endswith('.txt'):
            print(f"  Processing: {filename}")
            updated_data, changed = process_txt_file(source_file, accessory_mapping)
            
            if updated_data:
                # Write updated JSON to destination
                with open(dest_file, 'w', encoding='utf-8') as f:
                    json.dump(updated_data, f, ensure_ascii=False)
                
                if changed:
                    print(f"    ✓ Updated accessories/description")
                    any_changes = True
                else:
                    print(f"    - No changes needed")
                
                processed_files += 1
            else:
                # Copy original if processing failed
                shutil.copy2(source_file, dest_file)
                print(f"    ✗ Failed to process, copied original")
        else:
            # Copy other files (images, etc.) as-is
            shutil.copy2(source_file, dest_file)
    
    # Create zip file from the output extracted folder
    zip_path = os.path.join(output_zips_dir, f"{recipe_name}.zip")
    print(f"  Creating ZIP: {recipe_name}.zip")
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(output_recipe_folder):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, output_recipe_folder)
                zipf.write(file_path, arcname)
    
    print(f"  ✓ Created ZIP file")
    
    return processed_files, any_changes


def process_all_accessories(updated_stems: set = None):
    """
    Processes all recipe folders in EXTRACT_ROOT, applying accessory mapping
    and description fixes, writing results to UPDATED_EXTRACTED + UPDATED_ZIPS.

    Args:
        updated_stems: set of recipe stems (uppercased) that were
            newly downloaded/updated this run. If a recipe's stem is in this
            set, its existing updated_extracted folder is cleared first so
            it's rebuilt fresh instead of merging with stale content.

    Returns:
        (success_count, total_changed) tuple.
    """
    input_dir = EXTRACT_ROOT
    output_extracted_dir = UPDATED_EXTRACTED
    output_zips_dir = UPDATED_ZIPS

    Path(output_extracted_dir).mkdir(exist_ok=True)
    Path(output_zips_dir).mkdir(exist_ok=True)

    print("Accessory Update Tool - Extracted Folders Edition")
    print("=" * 60)

    if not os.path.isdir(input_dir):
        print(f"Error: Directory '{input_dir}' does not exist!")
        return 0, 0

    recipe_folders = [f for f in os.listdir(input_dir)
                       if os.path.isdir(os.path.join(input_dir, f))]

    if not recipe_folders:
        print("\nNo subdirectories found in the input directory!")
        return 0, 0

    print(f"\nFound {len(recipe_folders)} recipe folders")
    print(f"Using {len(ACCESSORY_MAPPING)} accessory mappings")

    total_processed = 0
    total_changed = 0
    success_count = 0
    failed_folders = []

    for recipe_folder in sorted(recipe_folders):
        recipe_path = os.path.join(input_dir, recipe_folder)
        try:
            processed, changed = process_recipe_folder(
                recipe_path,
                output_extracted_dir,
                output_zips_dir,
                ACCESSORY_MAPPING,
                updated_stems,
            )
            total_processed += processed
            if changed:
                total_changed += 1
            success_count += 1
        except Exception as e:
            print(f"  ✗ Error processing folder: {e}")
            failed_folders.append((recipe_folder, str(e)))

    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"Total recipe folders: {len(recipe_folders)}")
    print(f"Successfully processed: {success_count}")
    print(f"Failed: {len(recipe_folders) - success_count}")
    if failed_folders:
        print(f"\nFailed folders:")
        for name, error in failed_folders:
            print(f"  - {name}: {error}")
    print(f"Total txt files processed: {total_processed}")
    print(f"Recipes with changes: {total_changed}")
    print(f"\n✓ Updated extracted folders: {output_extracted_dir}")
    print(f"✓ Updated zip files: {output_zips_dir}")

    return success_count, total_changed


if __name__ == "__main__":
    process_all_accessories()