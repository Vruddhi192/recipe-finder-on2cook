import os
import zipfile
import shutil
from pathlib import Path

ZIP_ROOT = "zips"
EXTRACT_ROOT = "extracted"
IMAGE_DIR = "test_images"

def normalize_name(name):
    return name.replace(" ", "-").replace("/", "-").replace("-", " ").upper().strip()

def extract_all_zips():
    Path(EXTRACT_ROOT).mkdir(exist_ok=True)
    Path(IMAGE_DIR).mkdir(exist_ok=True)

    total = 0

    for root, dirs, files in os.walk(ZIP_ROOT):
        for file in files:
            if not file.lower().endswith(".zip"):
                continue

            zip_path = os.path.join(root, file)
            recipe_key = normalize_name(Path(file).stem)

            recipe_extract_dir = os.path.join(EXTRACT_ROOT, recipe_key)
            if os.path.exists(recipe_extract_dir):
                print(f"⏭ Already extracted: {recipe_key}")
                continue

            os.makedirs(recipe_extract_dir)

            print(f"📦 Extracting: {file}")
            with zipfile.ZipFile(zip_path, 'r') as z:
                z.extractall(recipe_extract_dir)

            # Find JPG and TXT recursively
            jpg = None
            txt = None

            for root2, dirs2, files2 in os.walk(recipe_extract_dir):
                for f in files2:
                    full_path = os.path.join(root2, f)
                    if f.lower().endswith(".jpg") and jpg is None:
                        jpg = full_path
                    elif f.lower().endswith(".txt") and txt is None:
                        txt = full_path

            if not txt:
                print(f"⚠ No TXT found in {recipe_key}")
                continue

            if jpg:
                final_img_name = f"{recipe_key}.jpg"
                shutil.copy(jpg, os.path.join(IMAGE_DIR, final_img_name))
                print(f"🖼 Image saved: {IMAGE_DIR}/{final_img_name}")
            else:
                print(f"⚠ No JPG found in {recipe_key}")

            total += 1

    print(f"\n Extraction complete: {total} recipes processed")
    return total


if __name__ == "__main__":
    extract_all_zips()
