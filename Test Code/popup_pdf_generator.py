#!/usr/bin/env python3
"""
Batch Recipe PDF Generator - IMPROVED VERSION
- Shows ALL ingredients (not just 5)
- Bigger circular recipe image
- Fixed logo display
- Shows all accessories and steps
"""

import json
import os
import zipfile
import sys
import re
from pathlib import Path
from fpdf import FPDF
from PIL import Image, ImageDraw
import io

def calculate_total_time(instructions):
    total_seconds = sum(item.get('durationInSec', 0) for item in instructions)
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes}:{seconds:02d} mins"

def parse_recipe_info(description):
    accessories = []
    output = "1000g"
    clean_steps = []
    
    lines = description.split('\n')
    for line in lines:
        line = line.strip().upper()
        if 'OUTPUT' in line:
            match = re.search(r'OUTPUT\s+(\d+\s*(?:G|GM|KG))', line, re.IGNORECASE)
            if match:
                output = match.group(1).replace('GM', 'g').replace('G', 'g').replace('KG', 'kg')
        elif 'ACCESSORIES' in line:
            acc_match = re.search(r'ACCESSORIES\s+(.+)', line, re.IGNORECASE)
            if acc_match:
                accessories = [acc.strip() for acc in acc_match.group(1).split(',')]
        elif len(line) > 10 and not any(kw in line for kw in ['NORMAL TIME', 'OUTPUT', 'ACCESSORIES']):
            clean_steps.append(line)
    
    return accessories, output, clean_steps

def create_circular_image(image_path, output_px=600):
    """
    High-res circular image.
    Crops to square, resizes once (LANCZOS), no blur.
    """
    img = Image.open(image_path).convert("RGBA")

    # --- center crop to square ---
    w, h = img.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    img = img.crop((left, top, left + side, top + side))

    # --- resize ONCE (high quality) ---
    img = img.resize((output_px, output_px), Image.LANCZOS)

    # --- circular mask ---
    mask = Image.new("L", (output_px, output_px), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, output_px, output_px), fill=255)

    img.putalpha(mask)

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


def create_recipe_pdf(json_data, output_filename, logo_path=None, recipe_bg_path=None):
    pdf = FPDF(unit='mm', format=[210, 280])
    pdf.add_page()
    pdf.set_margins(0, 0, 0)
    
    # 1. BLACK HEADER WITH OUTPUT BOX
    pdf.set_fill_color(0, 0, 0)
    pdf.rect(0, 0, 210, 75, style='F')
    
    # Output box
    pdf.set_fill_color(200, 200, 200)
    pdf.rect(140, 15, 60, 25, style='F')
    pdf.set_font('Arial', 'B', 14)
    pdf.set_text_color(0, 0, 0)
    pdf.set_xy(155, 20)
    pdf.cell(35, 6, 'OUTPUT', ln=1, align='C')
    
    accessories, output_val, steps = parse_recipe_info(json_data.get('description', ''))
    pdf.set_xy(155, 28)
    pdf.set_font('Arial', 'B', 18)
    pdf.cell(35, 8, output_val, ln=0, align='C')
    
    # 2. LOGO - FIXED PATH HANDLING
    print(f"🖼️ Logo check: {logo_path}")
    if logo_path and os.path.exists(logo_path):
        try:
            # Using absolute path and specifying format
            pdf.image(logo_path, x=15, y=10, w=28)
            print(f"✅ LOGO LOADED SUCCESSFULLY")
        except Exception as e:
            print(f"❌ Logo load failed: {e}")
    else:
        print(f"❌ Logo file not found at: {logo_path}")
    
    # 3. HEADER TEXT
    pdf.set_font('Arial', 'B', 24)
    pdf.set_text_color(255, 255, 255)
    title = json_data['name'][0] if isinstance(json_data['name'], list) else json_data['name']
    pdf.set_xy(20, 30)
    pdf.cell(110, 12, title.upper(), ln=0)
    
    pdf.set_font('Arial', 'B', 15)
    pdf.set_xy(20, 44)
    pdf.cell(110, 10, 'BY ON2COOK', ln=0)
    
    pdf.set_font('Arial', '', 12)
    total_time = calculate_total_time(json_data['Instruction'])
    pdf.set_xy(20, 57)
    pdf.cell(110, 8, f'@on2cook | {total_time}', ln=0)
    
    # 4. INGREDIENTS SECTION - SHOW ALL INGREDIENTS
    ingredients = json_data['Ingredients']
    num_ingredients = len(ingredients)
    
    # Calculate height needed for ingredients (6mm per ingredient + header)
    ingredients_height = min(num_ingredients * 7 + 15, 60)  # Cap at 60mm
    
    pdf.set_fill_color(255, 255, 255)
    pdf.set_text_color(0, 0, 0)
    pdf.rect(15, 85, 180, ingredients_height, style='F')
    
    pdf.set_font('Arial', 'B', 18)
    pdf.set_xy(25, 92)
    pdf.cell(0, 8, 'INGREDIENTS', ln=0)
    
    pdf.set_font('Arial', '', 11)
    y_pos = 104
    max_y = 85 + ingredients_height - 5  # Leave 5mm padding at bottom
    
    for ing in ingredients:
        if y_pos > max_y:
            break
        weight = ing.get('weight', '').strip()
        title = ing.get('title', '').strip()
        if weight and title:
            pdf.set_xy(25, y_pos)
            pdf.cell(160, 6, f"{weight.ljust(12)} {title[:50]}", ln=0)
            y_pos += 6.5
    
    # 5. ACCESSORIES & STEPS SECTION
    recipe_start_y = 85 + ingredients_height + 5
    recipe_height = 65
    
    pdf.rect(15, recipe_start_y, 180, recipe_height, style='F')
    
    pdf.set_font('Arial', 'B', 18)
    pdf.set_xy(25, recipe_start_y + 7)
    pdf.cell(0, 8, 'ACCESSORIES & STEPS', ln=0)
    
    content_y = recipe_start_y + 20
    
    # Show accessories if available
    if accessories:
        pdf.set_font('Arial', 'B', 13)
        pdf.set_xy(25, content_y)
        pdf.cell(0, 6, 'Accessories:', ln=0)
        content_y += 7
        
        pdf.set_font('Arial', '', 11)
        for acc in accessories[:4]:  # Show up to 4 accessories
            if content_y > recipe_start_y + recipe_height - 5:
                break
            pdf.set_xy(25, content_y)
            pdf.cell(160, 5, f"• {acc[:55]}", ln=0)
            content_y += 6
        
        content_y += 3  # Add spacing before steps
    
    # Show steps
    if steps:
        pdf.set_font('Arial', 'B', 13)
        pdf.set_xy(25, content_y)
        pdf.cell(0, 6, 'Steps:', ln=0)
        content_y += 7
        
        pdf.set_font('Arial', '', 11)
        for i, step in enumerate(steps[:4]):  # Show up to 4 steps
            if content_y > recipe_start_y + recipe_height - 5:
                break
            pdf.set_xy(25, content_y)
            pdf.cell(160, 5, f"{i+1}. {step[:60]}", ln=0)
            content_y += 6
    
    # 6. BIGGER CIRCULAR RECIPE IMAGE - RIGHT BOTTOM CORNER
    print(f"🖼️ Recipe image: {recipe_bg_path}")
    if recipe_bg_path and os.path.exists(recipe_bg_path):
        circular_buffer = create_circular_image(recipe_bg_path, output_px=800)  # Higher resolution

        if circular_buffer:
            # Position in right-bottom corner
            circle_radius = 55  # Bigger radius
            circle_center_x = 210 - circle_radius - 0  # 10mm from right edge
            circle_center_y = 280 - circle_radius - 0  # 10mm from bottom edge
            
            # Circle background
            pdf.set_fill_color(245, 245, 245)
            pdf.circle(circle_center_x, circle_center_y, circle_radius, style='F')
            pdf.set_draw_color(180, 180, 180)
            pdf.set_line_width(1.5)
            pdf.circle(circle_center_x, circle_center_y, circle_radius, style='D')
            
            # Bigger circular image (110mm diameter)
            image_size = 110
            image_x = circle_center_x - (image_size / 2)
            image_y = circle_center_y - (image_size / 2)
            
            circular_buffer.seek(0)
            pdf.image(io.BytesIO(circular_buffer.read()), image_x, image_y, image_size, image_size)
            print(f"✅ CIRCULAR IMAGE IN RIGHT BOTTOM CORNER! (110mm)")
        else:
            # Fallback position - right bottom
            pdf.circle(145, 215, 55, style='F')
            pdf.image(recipe_bg_path, 90, 160, 110, 110)
            print(f"✅ Fallback image loaded")
    else:
        print(f"❌ No recipe image at: {recipe_bg_path}")
    
    pdf.output(output_filename)
    print(f"✅ PDF CREATED: {output_filename}")

def process_recipes_batch(zip_folder_path, output_folder, start_index=0, end_index=None):
    os.makedirs(output_folder, exist_ok=True)
    stats = {'total_found': 0, 'processed': 0, 'success': 0, 'failed': 0}
    
    zip_folder = Path(zip_folder_path)
    if not zip_folder.exists():
        print(f"❌ ZIP folder not found!")
        return stats
    
    zip_files = sorted(list(zip_folder.glob('*.zip')))
    stats['total_found'] = len(zip_files)
    
    if end_index is None:
        end_index = len(zip_files)
    
    zip_files_to_process = zip_files[start_index:end_index]
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    logo_path = os.path.join(script_dir, r"D:\one drive\OneDrive\Desktop\on2cook-recipe-finder\on2cook logo_White 1.png")
    recipe_images_dir = os.path.join(script_dir, "recipe_images")
    
    print(f"🎯 SCRIPT DIR: {script_dir}")
    print(f"🏷️  LOGO: {logo_path} {'✅' if os.path.exists(logo_path) else '❌'}")
    print(f"📁 IMAGES: {recipe_images_dir} {'✅' if os.path.exists(recipe_images_dir) else '❌'}")
    
    for idx, zip_path in enumerate(zip_files_to_process, start=start_index):
        recipe_name = zip_path.stem.replace(" ", "_")
        print(f"\n[{idx+1}/{end_index}] {recipe_name}")
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                txt_files = [f for f in zip_ref.namelist() if f.endswith('.txt')]
                if not txt_files:
                    print(f"   No txt file")
                    stats['failed'] += 1
                    continue
                
                with zip_ref.open(txt_files[0]) as f:
                    recipe_data = json.loads(f.read().decode('utf-8'))
                
                output_pdf = os.path.join(output_folder, f"{recipe_name}.pdf")
                
                recipe_bg_path = None
                for ext in ['.jpg', '.jpeg', '.png']:
                    test1 = os.path.join(recipe_images_dir, f"{recipe_name}{ext}")
                    test2 = os.path.join(recipe_images_dir, f"{zip_path.stem}{ext}")
                    if os.path.exists(test1):
                        recipe_bg_path = test1
                        break
                    if os.path.exists(test2):
                        recipe_bg_path = test2
                        break
                
                create_recipe_pdf(recipe_data, output_pdf, logo_path, recipe_bg_path)
                print(f"✅ SUCCESS!")
                stats['success'] += 1
                stats['processed'] += 1
                
        except Exception as e:
            print(f"❌ ERROR: {e}")
            stats['failed'] += 1
    
    return stats

def print_summary(stats):
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"SUCCESS: {stats['success']}/{stats['total_found']}")
    print("="*80)

def main():
    zip_folder = r"D:\one drive\OneDrive\Desktop\on2cook-recipe-finder\updated_zips"
    output_folder = "output_pdfs"
    start_index = 0
    end_index = 400
    
    if len(sys.argv) >= 2: zip_folder = sys.argv[1]
    if len(sys.argv) >= 3: output_folder = sys.argv[2]
    if len(sys.argv) >= 4: start_index = int(sys.argv[3])
    if len(sys.argv) >= 5: end_index = int(sys.argv[4])
    
    stats = process_recipes_batch(zip_folder, output_folder, start_index, end_index)
    print_summary(stats)

if __name__ == "__main__":
    main()