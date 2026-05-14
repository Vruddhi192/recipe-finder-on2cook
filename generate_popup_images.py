# import os
# import subprocess
# from pathlib import Path

# # Root where your downloaded ZIPs live
# ZIP_ROOT = "zips"

# # Where popup images must be saved
# POPUP_DIR = "test_popup_images"

# # Script that processes ONE zip
# RECIPE_GENERATOR_SCRIPT = "final_corrected_recipe_generator.py"


# def process_zip(zip_path):
#     """
#     Runs:
#     python final_corrected_recipe_generator.py "<zip_path>" "test_popup_images"
#     """
#     cmd = [
#         "python",
#         RECIPE_GENERATOR_SCRIPT,
#         zip_path,
#         POPUP_DIR
#     ]

#     print(f"⚙ Running: {' '.join(cmd)}")

#     try:
#         subprocess.run(cmd, check=True)
#         print(f"🖼 Popup generated for: {zip_path}")
#         return True
#     except subprocess.CalledProcessError as e:
#         print(f"❌ Failed: {zip_path}\n{e}")
#         return False


# def process_all_zips():
#     Path(POPUP_DIR).mkdir(exist_ok=True)

#     processed = 0
#     failed = 0

#     for root, dirs, files in os.walk(ZIP_ROOT):
#         for file in files:
#             if not file.lower().endswith(".zip"):
#                 continue

#             zip_path = os.path.join(root, file)
#             success = process_zip(zip_path)

#             if success:
#                 processed += 1
#             else:
#                 failed += 1

#     print("\n==============================")
#     print("Popup image generation completed")
#     print(f"Processed: {processed}")
#     print(f"Failed:    {failed}")
#     print(f"Saved in:  {os.path.abspath(POPUP_DIR)}")
#     print("==============================")

#     return processed


# if __name__ == "__main__":
#     process_all_zips()
import os
import subprocess
from pathlib import Path

# Root where your ZIP files are stored
ZIP_ROOT = "updated_zips"

# Where popup images must be saved
POPUP_DIR = "test_popup_images"

# Script that processes ONE zip and generates ONE image
RECIPE_GENERATOR_SCRIPT = "final_corrected_recipe_generator.py"


def process_zip(zip_path):
    """
    Runs:
    python final_corrected_recipe_generator.py "<zip_path>" "test_popup_images"

    The generator itself must save:
    test_popup_images/<RECIPE_NAME>.jpg
    """

    cmd = [
        "python",
        RECIPE_GENERATOR_SCRIPT,
        zip_path,
        POPUP_DIR
    ]

    print(f"⚙ Running: {' '.join(cmd)}")

    try:
        subprocess.run(cmd, check=True)
        print(f"🖼 Popup image generated for: {zip_path}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to generate popup for: {zip_path}")
        print(e)
        return False
## Optional: If you want to process only specific ZIP files, you can use this function instead of process_all_zips.
def process_selected_zips(names: list[str]):
    """Pass a list of zip filenames (without path) to process."""
    Path(POPUP_DIR).mkdir(exist_ok=True)
    processed = 0
    failed = 0

    for root, dirs, files in os.walk(ZIP_ROOT):
        for file in files:
            if file not in names:
                continue

            zip_path = os.path.join(root, file)
            success = process_zip(zip_path)
            processed += 1 if success else 0
            failed += 0 if success else 1

    print(f"\nProcessed: {processed} | Failed: {failed}")
    

def process_all_zips():
    # Make sure popup directory exists
    Path(POPUP_DIR).mkdir(exist_ok=True)

    processed = 0
    failed = 0

    for root, dirs, files in os.walk(ZIP_ROOT):
        for file in files:
            if not file.lower().endswith(".zip"):
                continue

            zip_path = os.path.join(root, file)
            success = process_zip(zip_path)

            if success:
                processed += 1
            else:
                failed += 1

    print("\n==============================")
    print("Popup image generation completed")
    print(f"Processed: {processed}")
    print(f"Failed:    {failed}")
    print(f"Saved in:  {os.path.abspath(POPUP_DIR)}")
    print("==============================")

    return processed


if __name__ == "__main__":
    # process_all_zips()
    process_selected_zips(["AALNI BHAAT.zip", "CHICKEN SUKKA.zip","KODOMILLET BATH.zip","LITTLE MILLET.zip"])
