# #!/usr/bin/env python3
# """
# Script to update accessories in extracted recipe folders.
# Creates both extracted output folders AND zip files.

# Input structure: extracted/recipe1/recipe1.txt
# Output: 
#   - updated_extracted/ (folder with updated files)
#   - updated_zips/ (folder with zip files)
# """

# import os
# import json
# import zipfile
# import shutil
# import re
# from pathlib import Path

# # Accessory mapping dictionary
# ACCESSORY_MAPPING = {
#     "1 Grill Mesh": "Mesh Mats",
#     "1 Large Non Stick Mat": "MP Mats Big",
#     "1 Non Stick": "Mesh Mats",
#     "2 Grill Mesh": "Mesh Mats",
#     "Cake Mold And Stirrer": "Cake Kit",
#     "Coated Pan": "Pan Honeycomb (Non-Stick)",
#     "Frying Basket": "Frying Kit",
#     "Frying Basket & Stirrer": "Frying Kit",
#     "Frying Basket And Stirrer": "Frying Kit",
#     "FRYING BASKET AND STIRRER": "Frying Kit",
#     "Frying Stirrer": "Frying Kit",
#     "Gravy Stirrer": "Gravy Stirrer",
#     "Grill Mesh": "Grill Mesh",
#     "Grill Pan": "Grill Pan",
#     "Idli Mold & Stirrer": "Idli Mold & Stirrer",
#     "Large Non-Stick Mat": "MP Mats Big",
#     "Momo Basket": "Momo Kit",
#     "Momo Basket & Stirrer": "Momo Kit",
#     "Momo Stirrer": "Momo Kit",
#     "Non Coated Pan": "Pan Non-Coated (SS)",
#     "NON COATED PAN": "Pan Non-Coated (SS)",
#     "Non-Coated Pan": "Pan Non-Coated (SS)",
#     "Noodles Starter": "Noodles Stirrer",
#     "Noodles Stirrer": "Noodles Stirrer",
#     "Pizza Basket & Stirrer": "Pizza Kit",
#     "Pizza Basket With Stirrer": "Pizza Kit",
#     "Pressure Cooker": "Pressure Cooker",
#     "Rice Stirrer": "Rice Stirrer",
#     "S. S Pan": "Pan Non-Coated (SS)",
#     "S.S Pan": "Pan Non-Coated (SS)",
#     "S S Pan": "Pan Non-Coated (SS)",
#     "Silicon Rice Stirrer": "Rice Stirrer",
#     "Silicon Starter": "Silicone Stirrer",
#     "Silicon Stirer": "Silicone Stirrer",
#     "Silicon Stirrer": "Silicone Stirrer",
#     "Silicone Stirer": "Silicone Stirrer",
#     "Silicone Stirrer": "Silicone Stirrer",
#     "Silicone Stirrer With Hood": "Silicone Stirrer",
#     "Small Non Stick Mat": "MP Mats Small",
#     "Small Non-Stick Mat": "MP Mats Small",
#     "Small Teflon Sheet": "Teflon Plate",
#     "SS Pan": "Pan Non-Coated (SS)",
#     "PAN NON COATED (SS)": "Pan Non-Coated (SS)",
# }


# def update_accessories_in_description(description, accessory_mapping):
#     """
#     Update accessories in the description with standardized names.
#     """
#     if "ACCESSORIES" not in description.upper():
#         return description
    
#     # Split description into parts
#     parts = re.split(r'(ACCESSORIES\s*\n)', description, flags=re.IGNORECASE)
    
#     if len(parts) < 3:
#         return description
    
#     before_accessories = parts[0]
#     accessories_header = parts[1]
#     after_accessories = parts[2]
    
#     # Extract and update accessories
#     lines = after_accessories.split('\n')
#     updated_lines = []
#     accessories_section_ended = False
    
#     for line in lines:
#         original_line = line
#         line_stripped = line.strip()
        
#         # Check if we've moved past the accessories section
#         # Empty line doesn't end the section, but certain keywords do
#         if line_stripped and (line_stripped.upper().startswith('FINAL') or \
#            line_stripped.upper().startswith('NORMAL')):
#             accessories_section_ended = True
#             updated_lines.append(original_line)
#             continue
        
#         # If section ended, just add the line as-is
#         if accessories_section_ended:
#             updated_lines.append(original_line)
#             continue
        
#         # If empty line or whitespace, keep it
#         if not line_stripped:
#             updated_lines.append(original_line)
#             continue
        
#         # Try to match and replace accessory
#         replaced = False
#         best_match = None
#         best_match_len = 0
        
#         # Find the best (longest) matching accessory
#         for old_acc, new_acc in accessory_mapping.items():
#             # Exact match with case insensitivity
#             if line_stripped.upper() == old_acc.upper():
#                 best_match = new_acc
#                 best_match_len = len(old_acc)
#                 break
#             # Check if the line contains this accessory
#             elif old_acc.upper() in line_stripped.upper():
#                 if len(old_acc) > best_match_len:
#                     best_match = new_acc
#                     best_match_len = len(old_acc)
        
#         if best_match:
#             updated_lines.append(best_match)
#         else:
#             # Keep original line if no match found
#             updated_lines.append(original_line)
    
#     # Reconstruct description
#     updated_description = before_accessories + accessories_header + '\n'.join(updated_lines)
    
#     return updated_description


# def process_txt_file(txt_file_path, accessory_mapping):
#     """
#     Process a single txt file: read JSON, update accessories, return updated data.
#     """
#     try:
#         # Read the file
#         with open(txt_file_path, 'r', encoding='utf-8') as f:
#             content = f.read()
        
#         # Parse JSON
#         data = json.loads(content)
        
#         # Update description if it exists
#         changed = False
#         if 'description' in data:
#             original_desc = data['description']
#             updated_desc = update_accessories_in_description(original_desc, accessory_mapping)
            
#             if original_desc != updated_desc:
#                 data['description'] = updated_desc
#                 changed = True
        
#         return data, changed
        
#     except json.JSONDecodeError as e:
#         print(f"  ✗ Error parsing JSON: {e}")
#         return None, False
#     except Exception as e:
#         print(f"  ✗ Error processing file: {e}")
#         return None, False


# def process_recipe_folder(recipe_folder_path, output_extracted_dir, output_zips_dir, accessory_mapping):
#     """
#     Process a single recipe folder.
#     Creates both extracted output and zip file.
#     """
#     recipe_name = os.path.basename(recipe_folder_path)
#     print(f"\n{'='*60}")
#     print(f"Processing: {recipe_name}")
#     print(f"{'='*60}")
    
#     # Create output extracted folder for this recipe
#     output_recipe_folder = os.path.join(output_extracted_dir, recipe_name)
#     os.makedirs(output_recipe_folder, exist_ok=True)
    
#     # Track if any changes were made
#     any_changes = False
#     processed_files = 0
    
#     # Process all files in the recipe folder
#     for filename in os.listdir(recipe_folder_path):
#         source_file = os.path.join(recipe_folder_path, filename)
#         dest_file = os.path.join(output_recipe_folder, filename)
        
#         # If it's a txt file, process it
#         if filename.endswith('.txt'):
#             print(f"  Processing: {filename}")
#             updated_data, changed = process_txt_file(source_file, accessory_mapping)
            
#             if updated_data:
#                 # Write updated JSON to destination
#                 with open(dest_file, 'w', encoding='utf-8') as f:
#                     json.dump(updated_data, f, ensure_ascii=False)
                
#                 if changed:
#                     print(f"    ✓ Updated accessories")
#                     any_changes = True
#                 else:
#                     print(f"    - No changes needed")
                
#                 processed_files += 1
#             else:
#                 # Copy original if processing failed
#                 shutil.copy2(source_file, dest_file)
#                 print(f"    ✗ Failed to process, copied original")
#         else:
#             # Copy other files (images, etc.) as-is
#             shutil.copy2(source_file, dest_file)
    
#     # Create zip file from the output extracted folder
#     zip_path = os.path.join(output_zips_dir, f"{recipe_name}.zip")
#     print(f"  Creating ZIP: {recipe_name}.zip")
    
#     with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
#         for root, dirs, files in os.walk(output_recipe_folder):
#             for file in files:
#                 file_path = os.path.join(root, file)
#                 arcname = os.path.relpath(file_path, output_recipe_folder)
#                 zipf.write(file_path, arcname)
    
#     print(f"  ✓ Created ZIP file")
    
#     return processed_files, any_changes


# def main():
#     """
#     Main function to process all recipe folders.
#     """
#     print("Accessory Update Tool - Extracted Folders Edition")
#     print("=" * 60)
#     print("Processes extracted folders and creates:")
#     print("  1. Updated extracted folders")
#     print("  2. Updated zip files")
#     print("=" * 60)
    
#     # Get input directory (the "extracted" folder)
#     input_dir = input("\nEnter path to 'extracted' folder: ").strip()
    
#     if not os.path.isdir(input_dir):
#         print(f"Error: Directory '{input_dir}' does not exist!")
#         return
    
#     # Get parent directory for creating output folders
#     parent_dir = os.path.dirname(input_dir) or '.'
    
#     # Create output directories
#     output_extracted_dir = os.path.join(parent_dir, 'updated_extracted')
#     output_zips_dir = os.path.join(parent_dir, 'updated_zips')
    
#     os.makedirs(output_extracted_dir, exist_ok=True)
#     os.makedirs(output_zips_dir, exist_ok=True)
    
#     print(f"\nInput directory: {input_dir}")
#     print(f"Output extracted: {output_extracted_dir}")
#     print(f"Output zips: {output_zips_dir}")
    
#     # Find all recipe folders (subdirectories)
#     recipe_folders = [f for f in os.listdir(input_dir) 
#                      if os.path.isdir(os.path.join(input_dir, f))]
    
#     if not recipe_folders:
#         print("\nNo subdirectories found in the input directory!")
#         return
    
#     print(f"\nFound {len(recipe_folders)} recipe folders")
#     print(f"Using {len(ACCESSORY_MAPPING)} accessory mappings")
    
#     # Process each recipe folder
#     total_processed = 0
#     total_changed = 0
#     success_count = 0
    
#     for recipe_folder in sorted(recipe_folders):
#         recipe_path = os.path.join(input_dir, recipe_folder)
#         try:
#             processed, changed = process_recipe_folder(
#                 recipe_path, 
#                 output_extracted_dir, 
#                 output_zips_dir, 
#                 ACCESSORY_MAPPING
#             )
#             total_processed += processed
#             if changed:
#                 total_changed += 1
#             success_count += 1
#         except Exception as e:
#             print(f"  ✗ Error processing folder: {e}")
    
#     # Print summary
#     print(f"\n{'='*60}")
#     print(f"SUMMARY")
#     print(f"{'='*60}")
#     print(f"Total recipe folders: {len(recipe_folders)}")
#     print(f"Successfully processed: {success_count}")
#     print(f"Failed: {len(recipe_folders) - success_count}")
#     print(f"Total txt files processed: {total_processed}")
#     print(f"Recipes with accessory changes: {total_changed}")
#     print(f"\n✓ Updated extracted folders: {output_extracted_dir}")
#     print(f"✓ Updated zip files: {output_zips_dir}")


# if __name__ == "__main__":
#     main()

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
    "SS Pan": "Pan Non-Coated (SS)",
    "PAN NON COATED (SS)": "Pan Non-Coated (SS)",
    "Pan Non Coated  Ss": "Pan Non-Coated (SS)",
    "Pan Non Coated Ss": "Pan Non-Coated (SS)",
    "Pan Honeycomb (Coated)": "Pan Honeycomb (Non-Stick)",
    ":": "",
    " Pan Non Coated Ss": "Pan Non-Coated (SS)",
    "New Grilled Pan (Pre-Heated 90S)": "Grill Pan",
    "Teflon Plate/Sheet": "Teflon Plate",
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
    "MILLET CHILLA (BAJRA - PEARL MILLET)":"MILLET CHILLA (BAJRA/PEARL MILLET)"
    
}
def fix_description_text(description):
    if not description:
        return description

    updated_description = description

    for old_text, new_text in DESCRIPTION_FIXES.items():
        updated_description = re.sub(
            re.escape(old_text),
            new_text,
            updated_description,
            flags=re.IGNORECASE
        )

    return updated_description


def update_accessories_in_description(description, accessory_mapping):
    """
    Update accessories in the description with standardized names.
    """
    if "ACCESSORIES" not in description.upper():
        return description
    
    # Split description into parts
    parts = re.split(r'(ACCESSORIES\s*\n)', description, flags=re.IGNORECASE)
    
    if len(parts) < 3:
        return description
    
    before_accessories = parts[0]
    accessories_header = parts[1]
    after_accessories = parts[2]
    
    # Extract and update accessories
    lines = after_accessories.split('\n')
    updated_lines = []
    accessories_section_ended = False
    
    for line in lines:
        original_line = line
        line_stripped = line.strip()
        
        # Check if we've moved past the accessories section
        # Empty line doesn't end the section, but certain keywords do
        if line_stripped and (line_stripped.upper().startswith('FINAL') or \
           line_stripped.upper().startswith('NORMAL')):
            accessories_section_ended = True
            updated_lines.append(original_line)
            continue
        
        # If section ended, just add the line as-is
        if accessories_section_ended:
            updated_lines.append(original_line)
            continue
        
        # If empty line or whitespace, keep it
        if not line_stripped:
            updated_lines.append(original_line)
            continue
        
        # Try to match and replace accessory
        replaced = False
        best_match = None
        best_match_len = 0
        
        # Find the best (longest) matching accessory
        for old_acc, new_acc in accessory_mapping.items():
            # Exact match with case insensitivity
            if line_stripped.upper() == old_acc.upper():
                best_match = new_acc
                best_match_len = len(old_acc)
                break
            # Check if the line contains this accessory
            elif old_acc.upper() in line_stripped.upper():
                if len(old_acc) > best_match_len:
                    best_match = new_acc
                    best_match_len = len(old_acc)
        
        if best_match:
            updated_lines.append(best_match)
        else:
            # Keep original line if no match found
            updated_lines.append(original_line)
    
    # Reconstruct description
    updated_description = before_accessories + accessories_header + '\n'.join(updated_lines)
    
    return updated_description


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


def process_recipe_folder(recipe_folder_path, output_extracted_dir, output_zips_dir, accessory_mapping):
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


def main():
    """
    Main function to process all recipe folders.
    """
    print("Accessory Update Tool - Extracted Folders Edition")
    print("=" * 60)
    print("Processes extracted folders and creates:")
    print("  1. Updated extracted folders")
    print("  2. Updated zip files")
    print("Features:")
    print("  - Updates accessories to standard names")
    print("  - Fixes description text (e.g., 'AMUL PARATHA ALOO' -> 'AMUL ALOO PARATHA')")
    print("=" * 60)
    
    # Get input directory (the "extracted" folder)
    input_dir = input("\nEnter path to 'extracted' folder: ").strip()
    
    if not os.path.isdir(input_dir):
        print(f"Error: Directory '{input_dir}' does not exist!")
        return
    
    # Get parent directory for creating output folders
    parent_dir = os.path.dirname(input_dir) or '.'
    
    # Create output directories
    output_extracted_dir = os.path.join(parent_dir, 'updated_extracted')
    output_zips_dir = os.path.join(parent_dir, 'updated_zips')
    
    os.makedirs(output_extracted_dir, exist_ok=True)
    os.makedirs(output_zips_dir, exist_ok=True)
    
    print(f"\nInput directory: {input_dir}")
    print(f"Output extracted: {output_extracted_dir}")
    print(f"Output zips: {output_zips_dir}")
    
    # Find all recipe folders (subdirectories)
    recipe_folders = [f for f in os.listdir(input_dir) 
                     if os.path.isdir(os.path.join(input_dir, f))]
    
    if not recipe_folders:
        print("\nNo subdirectories found in the input directory!")
        return
    
    print(f"\nFound {len(recipe_folders)} recipe folders")
    print(f"Using {len(ACCESSORY_MAPPING)} accessory mappings")
    
    # Process each recipe folder
    total_processed = 0
    total_changed = 0
    success_count = 0
    
    for recipe_folder in sorted(recipe_folders):
        recipe_path = os.path.join(input_dir, recipe_folder)
        try:
            processed, changed = process_recipe_folder(
                recipe_path, 
                output_extracted_dir, 
                output_zips_dir, 
                ACCESSORY_MAPPING
            )
            total_processed += processed
            if changed:
                total_changed += 1
            success_count += 1
        except Exception as e:
            print(f"  ✗ Error processing folder: {e}")
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"Total recipe folders: {len(recipe_folders)}")
    print(f"Successfully processed: {success_count}")
    print(f"Failed: {len(recipe_folders) - success_count}")
    print(f"Total txt files processed: {total_processed}")
    print(f"Recipes with changes: {total_changed}")
    print(f"\n✓ Updated extracted folders: {output_extracted_dir}")
    print(f"✓ Updated zip files: {output_zips_dir}")


if __name__ == "__main__":
    main()