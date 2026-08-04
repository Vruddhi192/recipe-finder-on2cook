import os
import json
import re
import zipfile
import tempfile
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, black, white
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from math import sin, cos, radians
from svglib.svglib import svg2rlg
from reportlab.graphics import renderPDF

# New imports for Dropbox + QR
import qrcode
from PIL import Image
import dropbox
from dropbox.exceptions import ApiError, AuthError

# =========================
# Configuration for QR/Dropbox
# =========================
DB_DEFAULT_FOLDER = '/Recipe Booklet'
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(SCRIPT_DIR, 'image.jfif')
LOGO_RATIO = 4

def safe_int(value, default=0):
    """Safely convert a value to integer, returning default for invalid inputs."""
    try:
        if value is None:
            return default
        if isinstance(value, int):
            return value
        value_str = str(value).strip()
        if value_str == '':
            return default
        return int(value_str)
    except (ValueError, TypeError):
        return default

def sanitize_filename(name):
    """Sanitize a string to be a safe filename (keeps alnum, space, dash, underscore, dot)."""
    if not name:
        return "recipe"
    sanitized = re.sub(r'[^A-Za-z0-9._ \-]+', '_', name)
    sanitized = sanitized.strip().strip('.')
    return sanitized or "recipe"

def clean_time_and_units_text(text):
    """Clean time formatting and unit abbreviations according to requirements"""
    import re
    
    # Replace 'gm' with 'g' everywhere (case insensitive) - INCLUDING INSTRUCTIONS
    text = re.sub(r'\bgm\b', 'g', text, flags=re.IGNORECASE)
    
    # Replace 'sec.' with 'secs.'
    text = re.sub(r'\bsec\.', 'secs.', text)
    
    # Fix time formatting: 1:00 mins -> 1:00 min, but keep other times as mins
    def fix_time_format(match):
        time_part = match.group(1)
        if time_part == '1:00':
            return '1:00 min'
        else:
            return f'{time_part} mins'
    
    # Handle time patterns like "1:00 mins" or "2:30 mins"
    text = re.sub(r'(\d+:\d+)\s*mins?\.?', fix_time_format, text)
    
    return text

def clean_recipe_data(recipe_data):
    """Clean all recipe data fields according to formatting requirements"""
    import copy
    
    # Create a deep copy to avoid modifying original data
    cleaned_data = copy.deepcopy(recipe_data)
    
    # Clean Instructions - specifically targeting 'gm' to 'g' conversion
    if 'Instruction' in cleaned_data:
        for instruction in cleaned_data['Instruction']:
            if 'Text' in instruction:
                # Clean the instruction text
                original_text = instruction['Text']
                cleaned_text = clean_time_and_units_text(original_text)
                instruction['Text'] = cleaned_text
                
                # Debug log to show gm -> g conversions
                if 'gm' in original_text.lower():
                    print(f"🔄 Instruction cleaned: '{original_text}' → '{cleaned_text}'")
    
    # Clean Ingredients weights
    if 'Ingredients' in cleaned_data:
        for ingredient in cleaned_data['Ingredients']:
            if 'weight' in ingredient:
                ingredient['weight'] = clean_time_and_units_text(ingredient['weight'])
            if 'text' in ingredient:
                ingredient['text'] = clean_time_and_units_text(ingredient['text'])
            if 'title' in ingredient:
                ingredient['title'] = clean_time_and_units_text(ingredient['title'])
    
    # Clean description
    if 'description' in cleaned_data:
        cleaned_data['description'] = clean_time_and_units_text(cleaned_data['description'])
    
    return cleaned_data

def _default_output_path_from(source_path, candidate_name):
    """Build a default PDF path next to source_path using candidate_name as basename."""
    directory = os.path.dirname(os.path.abspath(source_path)) if source_path else os.getcwd()
    base = sanitize_filename(candidate_name)
    return os.path.join(directory, f"{base}.pdf")

def _resolve_output_pdf_path(output_pdf_path, candidate_name, source_path, recipe_data=None):
    """Respect explicit output path; otherwise derive from recipe name or candidate/source."""
    # If a directory was provided, place the derived filename inside it
    if output_pdf_path and os.path.isdir(output_pdf_path):
        directory = output_pdf_path
        if recipe_data and recipe_data.get('name'):
            base = sanitize_filename(recipe_data.get('name', ['recipe'])[0])
        else:
            base = sanitize_filename(candidate_name)
        return os.path.join(directory, f"{base}.pdf")

    # Treat blank/None and common default names as signals to derive a name
    def _looks_like_default(path_str):
        if not path_str:
            return True
        base = os.path.basename(path_str).lower()
        default_names = {
            'recipe_output.pdf',
            'recipe output.pdf',
            'recepie_output.pdf',
            'recepie output.pdf',
            'output.pdf',
            'default.pdf'
        }
        if base in default_names:
            return True
        return re.match(r'^(recip(e|ie)[ _-]?output)(\.pdf)?$', base or '') is not None

    if not _looks_like_default(output_pdf_path):
        return output_pdf_path

    # Use recipe name if available, otherwise fall back to candidate/source
    if recipe_data and recipe_data.get('name'):
        base = sanitize_filename(recipe_data.get('name', ['recipe'])[0])
        return os.path.join(os.path.dirname(os.path.abspath(source_path)) if source_path else os.getcwd(), f"{base}.pdf")
    return _default_output_path_from(source_path, candidate_name)

class RecipePDFGenerator:
    def __init__(self, qr_image=None):
        # Page width updated to 210mm
        self.page_width = 210 * mm
        # Page height will be calculated dynamically
        self.page_height = None  # Will be set in generate_pdf
        
        # Left and right section widths updated to 105mm
        self.left_section_width = 105 * mm
        self.right_section_width = 105 * mm
        self.left_margin = 0 * mm
        
        # Image dimensions updated to 105mm x 97mm
        self.image_width = 105 * mm
        self.image_height = 97 * mm
        
        # Colors
        self.bar_orange = HexColor('#fbc0a7')  # Updated orange color
        self.bar_red = HexColor('#e89ca5')     # Updated red color
        self.bar_gray = HexColor('#E8E8E8')
        self.orange_color = HexColor('#F37029')  # Induction
        self.red_color = HexColor('#BE1E2D')     # Microwave/Magnetron
        self.blue_color = HexColor('#add8e6')    # Blue color for pump-on periods
        self.green_color = HexColor('#3CB371')   # Green color for regular periods
        self.skin_color = HexColor('#FDF4CB')
        self.light_gray = HexColor('#E8E8E8')
        self.dark_gray = HexColor('#666666')
        self.green_time = HexColor('#C1D040')
        self.gold_step = HexColor('#FFD700')
        self.line_color = HexColor('#ed1c24')    # New color for underlines
        
        # Circle diameter for induction/magnetron indicators: 18.459mm
        self.circle_diameter = 18.459 * mm
        
        # Font sizes
        self.recipe_name_size = 22  # Updated to 22pt
        self.section_title_size = 11  # Updated to 11pt
        self.section_detail_size = 10
        self.step_title_size = 15
        self.instruction_size = 10  # Updated to 10pt
        
        # QR image (PIL Image) provided externally
        self.qr_image = qr_image  # if provided, will be drawn on PDF
        
        # Setup fonts
        self.setup_fonts()
    
    def setup_fonts(self):
        """Setup custom fonts from fonts folder"""
        try:
            # Get the directory where this script is located
            script_dir = os.path.dirname(os.path.abspath(__file__))
            
            # Build font paths relative to the script directory
            montserrat_path = os.path.join(script_dir, 'Fonts', 'Montserrat-Medium.ttf')
            din_bold_path = os.path.join(script_dir, 'Fonts', 'DINBold.ttf')
            din_medium_path = os.path.join(script_dir, 'Fonts', 'DINMedium.ttf')
            
            print(f"🔍 Font paths:")
            print(f"   Montserrat: {montserrat_path}")
            print(f"   DIN-Bold: {din_bold_path}")
            print(f"   DIN-Medium: {din_medium_path}")
            
            # Check if font files exist
            if not os.path.exists(montserrat_path):
                print(f"❌ Font file not found: {montserrat_path}")
            if not os.path.exists(din_bold_path):
                print(f"❌ Font file not found: {din_bold_path}")
            if not os.path.exists(din_medium_path):
                print(f"❌ Font file not found: {din_medium_path}")
            
            pdfmetrics.registerFont(TTFont('Montserrat-Medium', montserrat_path))
            pdfmetrics.registerFont(TTFont('DIN-Bold', din_bold_path))
            pdfmetrics.registerFont(TTFont('DIN-Medium', din_medium_path))
            
            self.recipe_name_font = 'Montserrat-Medium'
            self.section_title_font = 'DIN-Bold'
            self.section_detail_font = 'DIN-Medium'
            self.step_title_font = 'DIN-Bold'
            self.instruction_font = 'DIN-Medium'
            
            print("✅ Custom fonts loaded successfully!")
            
        except Exception as e:
            print(f"❌ Font loading error: {e}")
            print("🔄 Falling back to system fonts...")
            # Fallback to system fonts
            self.recipe_name_font = 'Helvetica-Bold'
            self.section_title_font = 'Helvetica-Bold'
            self.section_detail_font = 'Helvetica'
            self.step_title_font = 'Helvetica-Bold'
            self.instruction_font = 'Helvetica'
            print("✅ System fonts loaded as fallback")

    def calculate_required_page_height(self, recipe_data, seconds_per_bar):
        """Calculate the required page height based on recipe content"""
        # Calculate left section height
        left_height = self.calculate_left_section_height(recipe_data)
        
        # Calculate right section height
        right_height = self.calculate_right_section_height(recipe_data, seconds_per_bar)
        
        # Take the maximum and add some padding
        required_height = max(left_height, right_height) + 20*mm  # 20mm padding
        
        # Minimum height should be at least the original size
        min_height = 228*mm
        
        return max(required_height, min_height)

    def calculate_left_section_height(self, recipe_data):
        height = 0
        height += self.image_height  # 97mm
        height += 15*mm  # Recipe name
        height += 7*mm   # Recipe name actual height
        height += 7*mm   # Cooking time header
        cooking_times = self.extract_cooking_time(recipe_data)
        height += len(cooking_times) * 6*mm
        height += 6*mm   # Accessories header
        accessories = self.extract_accessories(recipe_data)
        if accessories:
            if len(accessories) >= 2:
                height += 6*mm
                height += (len(accessories) - 2) * 6*mm
            else:
                height += 6*mm
        else:
            height += 6*mm
        height += 3*mm + 8*mm  # Ingredients header
        ingredients = self.extract_ingredients(recipe_data)
        height += len(ingredients) * 5*mm  # 5mm per ingredient line (main and sub-ingredients)
        return height
    def calculate_right_section_height(self, recipe_data, seconds_per_bar):
        """Calculate required height for right section (timeline)"""
        # Top margin for QR code and circles
        height = 50*mm
        
        # Calculate timeline height
        instructions = recipe_data.get('Instruction', [])
        if 'Instruction' in recipe_data:
            merged_instructions = self.merge_zero_duration_steps(recipe_data['Instruction'])
        else:
            merged_instructions = instructions
            
        total_time_sec = sum(int(instr.get('durationInSec', 0)) for instr in merged_instructions)
        first_duration = safe_int(merged_instructions[0].get('durationInSec', 0)) if merged_instructions else 0
        extra_bars = 5 if first_duration == 0 else 0
        time_bars = max(1, int(total_time_sec / seconds_per_bar))
        total_bars = time_bars + extra_bars
        
        # Timeline bars height
        bar_height = 1*mm
        bar_spacing = 1*mm
        timeline_height = total_bars * (bar_height + bar_spacing)
        height += timeline_height
        
        # Step blocks height (approximate)
        consolidated_steps = self.consolidate_timeline_steps(merged_instructions)
        vertical_spacing = 10*mm
        block_height = 6*mm
        
        for step in consolidated_steps:
            height += vertical_spacing
            instruction_text = step.get('Text', '')
            if instruction_text:
                lines = self.parse_instruction_with_weight(instruction_text, recipe_data,step)
                num_lines = len(lines)
                line_height = 4*mm
                instruction_height = num_lines * line_height
                height += block_height + instruction_height + 8*mm  # 8mm for power circles
        
        # Bottom margin
        height -= 210*mm
        
        return height

    def merge_zero_duration_steps(self, instructions):
        if not instructions:
            return instructions
        print("=== STEP MERGING DEBUG ===")
        print("Original steps:")
        for i, step in enumerate(instructions):
            duration = safe_int(step.get('durationInSec', 0))
            text = step.get('Text', '')[:40]
            weight = step.get('Weight', '')[:20]
            print(f"  Step {i+1}: '{text}...' Weight: {weight}, Duration: {duration}s")
        merged_steps = []
        i = 0
        while i < len(instructions):
            current_step = instructions[i]
            if i == 0:
                merged_steps.append(current_step)
                print(f"✓ Keeping Step 1 (first step): '{current_step.get('Text', '')[:30]}...'")
                i += 1
                continue
            if safe_int(current_step.get('durationInSec', 0)) == 0:
                print(f"→ Found zero-duration step {i+1}: '{current_step.get('Text', '')[:30]}...'")
                zero_steps = [current_step]
                j = i + 1
                while j < len(instructions) and safe_int(instructions[j].get('durationInSec', 0)) == 0:
                    zero_steps.append(instructions[j])
                    print(f"→ Also collecting zero-duration step {j+1}: '{instructions[j].get('Text', '')[:30]}...'")
                    j += 1
                if j < len(instructions):
                    target_step = instructions[j].copy()
                    print(f"→ Merging with step {j+1}: '{target_step.get('Text', '')[:30]}...' ({target_step.get('durationInSec', 0)}s)")
                    # Collect texts with weights for zero-duration steps
                    texts = []
                    for step in zero_steps:
                        text = step.get('Text', '').strip()
                        weight = step.get('Weight', '').strip()
                        if text and weight:
                            texts.append(f"{weight} {text}")
                        elif text:
                            texts.append(text)
                    # Add target step's text and weight
                    target_text = target_step.get('Text', '').strip()
                    target_weight = target_step.get('Weight', '').strip()
                    if target_text and target_weight:
                        texts.append(f"{target_weight} {target_text}")
                    elif target_text:
                        texts.append(target_text)
                    target_step['Text'] = ', '.join(texts)
                    merged_steps.append(target_step)
                    print(f"✓ Created merged step: '{target_step['Text'][:50]}...' ({target_step.get('durationInSec', 0)}s)")
                    i = j + 1
                else:
                    merged_steps.extend(zero_steps)
                    print(f"✗ No target step found, keeping zero steps as-is")
                    i = j
            else:
                merged_steps.append(current_step)
                print(f"✓ Keeping step {i+1}: '{current_step.get('Text', '')[:30]}...' ({current_step.get('durationInSec', 0)}s)")
                i += 1
        print("\nFinal merged steps:")
        for i, step in enumerate(merged_steps):
            duration = safe_int(step.get('durationInSec', 0))
            text = step.get('Text', '')[:40]
            print(f"  Step {i+1}: '{text}...' Duration: {duration}s")
        print("=== END MERGE DEBUG ===\n")
        return merged_steps
    def process_zip_file(self, zip_path, output_pdf_path, seconds_per_bar):
        """Main function to process zip file and generate PDF"""
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            with tempfile.TemporaryDirectory() as temp_dir:
                zip_ref.extractall(temp_dir)
                
                json_file = None
                image_file = None
                
                for file in os.listdir(temp_dir):
                    if file.endswith('.txt') or file.endswith('.json'):
                        json_file = os.path.join(temp_dir, file)
                    elif file.lower().endswith(('.jpg', '.jpeg', '.png')):
                        image_file = os.path.join(temp_dir, file)
                
                if not json_file:
                    raise ValueError("No JSON/TXT file found in zip")
                
                with open(json_file, 'r', encoding='utf-8') as f:
                    recipe_data = json.load(f)
                
                # APPLY STEP MERGING HERE
                if 'Instruction' in recipe_data:
                    recipe_data['Instruction'] = self.merge_zero_duration_steps(recipe_data['Instruction'])

                # Use recipe name from JSON for output path
                candidate_name = recipe_data.get('name', ['recipe'])[0]
                final_output_path = _resolve_output_pdf_path(output_pdf_path, candidate_name, zip_path, recipe_data)

                self.generate_pdf(recipe_data, image_file, final_output_path, seconds_per_bar)
                return final_output_path

    def process_multiple_zip_files_individually(self, zip_file_paths, output_directory, seconds_per_bar, dropbox_token=None):
        """Process multiple zip files and generate separate PDFs for each"""
        print(f"🔍 === PROCESSING {len(zip_file_paths)} ZIP FILES INDIVIDUALLY ===")
        
        # Ensure output directory exists
        os.makedirs(output_directory, exist_ok=True)
        
        results = []
        
        for i, zip_path in enumerate(zip_file_paths, 1):
            print(f"\n📦 Processing file {i}/{len(zip_file_paths)}: {os.path.basename(zip_path)}")
            
            try:
                # Generate unique output PDF path for this zip using recipe name from JSON
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    with tempfile.TemporaryDirectory() as temp_dir:
                        zip_ref.extractall(temp_dir)
                        json_file = None
                        for file in os.listdir(temp_dir):
                            if file.endswith('.txt') or file.endswith('.json'):
                                json_file = os.path.join(temp_dir, file)
                                break
                        if not json_file:
                            raise ValueError("No JSON/TXT file found in zip")
                        with open(json_file, 'r', encoding='utf-8') as f:
                            recipe_data = json.load(f)
                zip_basename = sanitize_filename(recipe_data.get('name', ['recipe'])[0])
                output_pdf_path = os.path.join(output_directory, f"{zip_basename}.pdf")
                
                # Process this individual zip file using existing method
                final_output_path = self.process_zip_file(zip_path, output_pdf_path, seconds_per_bar)
                
                # Record success
                file_size = os.path.getsize(final_output_path) if os.path.exists(final_output_path) else 0
                results.append({
                    'status': 'success',
                    'input_zip': zip_path,
                    'output_pdf': final_output_path,
                    'file_size': file_size,
                    'file_size_mb': round(file_size / (1024 * 1024), 2)
                })
                
                print(f"✅ Generated: {os.path.basename(final_output_path)} ({results[-1]['file_size_mb']} MB)")
                
            except Exception as e:
                print(f"❌ Error processing {os.path.basename(zip_path)}: {e}")
                results.append({
                    'status': 'error',
                    'input_zip': zip_path,
                    'output_pdf': None,
                    'error': str(e)
                })
        
        # Print summary
        successful = [r for r in results if r['status'] == 'success']
        failed = [r for r in results if r['status'] == 'error']
        
        print(f"\n📊 === PROCESSING SUMMARY ===")
        print(f"✅ Successful: {len(successful)}")
        print(f"❌ Failed: {len(failed)}")
        print(f"📁 Output directory: {output_directory}")
        
        if successful:
            total_size_mb = sum(r['file_size_mb'] for r in successful)
            print(f"📄 Total PDF size: {total_size_mb:.2f} MB")
            print("\n✅ Generated PDFs:")
            for result in successful:
                print(f"   • {os.path.basename(result['output_pdf'])} ({result['file_size_mb']} MB)")
        
        if failed:
            print("\n❌ Failed files:")
            for result in failed:
                print(f"   • {os.path.basename(result['input_zip'])}: {result['error']}")
        
        return results

    def process_json_and_image(self, json_path, image_path, output_pdf_path, seconds_per_bar, dropbox_token):
        """Process separate JSON and image files, upload to Dropbox, generate QR, and create PDF."""
        import json
        with open(json_path, 'r', encoding='utf-8') as f:
            recipe_data = json.load(f)
        # Dropbox upload (if token provided)
        qr_img = None
        direct_url = None
        if dropbox_token:
            try:
                from final_corrected_recipe_generator import upload_to_dropbox_and_get_direct_url, generate_qr_with_center_logo, LOGO_PATH, LOGO_RATIO, DB_DEFAULT_FOLDER
                # Upload both files as a zip to Dropbox for compatibility
                import zipfile
                import tempfile
                with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as temp_zip:
                    with zipfile.ZipFile(temp_zip.name, 'w') as zipf:
                        zipf.write(json_path, arcname=os.path.basename(json_path))
                        zipf.write(image_path, arcname=os.path.basename(image_path))
                    direct_url = upload_to_dropbox_and_get_direct_url(temp_zip.name, dropbox_token, DB_DEFAULT_FOLDER)
                qr_img = generate_qr_with_center_logo(direct_url, LOGO_PATH, LOGO_RATIO)
            except Exception as e:
                print(f"Dropbox/QR step warning: {e}. Proceeding to generate PDF without QR.")
        self.qr_image = qr_img

        # Use recipe name from JSON
        candidate_name = recipe_data.get('name', ['recipe'])[0]
        final_output_path = _resolve_output_pdf_path(output_pdf_path, candidate_name, json_path or image_path, recipe_data)
        self.generate_pdf(recipe_data, image_path, final_output_path, seconds_per_bar)
        return final_output_path

    def process_txt_and_image(self, txt_path, image_path, output_pdf_path, seconds_per_bar, dropbox_token):
        """Process separate TXT and image files, upload to Dropbox, generate QR, and create PDF."""
        print("🔍 === STARTING TXT AND IMAGE PROCESSING ===")
        print(f"📁 TXT file path: {txt_path}")
        print(f"🖼️ Image file path: {image_path}")
        print(f"⚙️ Seconds per bar: {seconds_per_bar}")
        print(f"🔑 Dropbox token provided: {'Yes' if dropbox_token else 'No'}")
        
        import json
        with open(txt_path, 'r', encoding='utf-8') as f:
            recipe_data = json.load(f)
        print(f" Recipe data loaded successfully. Keys: {list(recipe_data.keys())}")
        
        qr_img = None
        direct_url = None
        
        if dropbox_token:
            print("🚀 Starting Dropbox upload process...")
            try:
                from final_corrected_recipe_generator import upload_to_dropbox_and_get_direct_url, generate_qr_with_center_logo, LOGO_PATH, LOGO_RATIO, DB_DEFAULT_FOLDER
                print(f"📦 Logo path: {LOGO_PATH}")
                print(f"📏 Logo ratio: {LOGO_RATIO}")
                print(f"📁 Dropbox folder: {DB_DEFAULT_FOLDER}")
                
                import zipfile
                import tempfile
                with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as temp_zip:
                    with zipfile.ZipFile(temp_zip.name, 'w') as zipf:
                        zipf.write(txt_path, arcname=os.path.basename(txt_path))
                        zipf.write(image_path, arcname=os.path.basename(image_path))
                    print(f"📦 Temporary ZIP created: {temp_zip.name}")
                    
                    direct_url = upload_to_dropbox_and_get_direct_url(temp_zip.name, dropbox_token, DB_DEFAULT_FOLDER)
                    print(f"✅ Dropbox upload successful!")
                    print(f"🔗 Direct URL: {direct_url}")
                    
                print("🎯 Starting QR code generation...")
                qr_img = generate_qr_with_center_logo(direct_url, LOGO_PATH, LOGO_RATIO)
                print(f"✅ QR code generated successfully: {qr_img is not None}")
                if qr_img:
                    print(f"📐 QR image dimensions: {qr_img.size}")
                    print(f" QR image mode: {qr_img.mode}")
                    
            except Exception as e:
                print(f"❌ Dropbox/QR step error: {e}")
                import traceback
                traceback.print_exc()
        else:
            print("ℹ️ No Dropbox token provided, skipping QR generation")
        
        print(f"🔍 Setting qr_image: {qr_img is not None}")
        self.qr_image = qr_img
        
        print("📄 Starting PDF generation...")
        candidate_name = recipe_data.get('name', ['recipe'])[0]
        final_output_path = _resolve_output_pdf_path(output_pdf_path, candidate_name, txt_path or image_path, recipe_data)
        self.generate_pdf(recipe_data, image_path, final_output_path, seconds_per_bar)
        print(f"📄 Output path used: {final_output_path}")
        print("✅ TXT and image processing completed!")
        return final_output_path

    def generate_pdf(self, recipe_data, image_path, output_path, seconds_per_bar):
        print("🔍 === STARTING PDF GENERATION ===")
        print(f"DEBUG: Raw description before cleaning: {recipe_data.get('description', '')!r}")
        
        # Clean recipe data
        print("🔍 Cleaning recipe data formatting...")
        recipe_data = clean_recipe_data(recipe_data)
        print(f"DEBUG: Description after cleaning: {recipe_data.get('description', '')!r}")
        print("✅ Recipe data cleaned (time formats and units)")
        
        # CRITICAL FIX: Apply step merging IMMEDIATELY and consistently
        if 'Instruction' in recipe_data:
            print("🔍 Applying step merging in generate_pdf...")
            original_count = len(recipe_data['Instruction'])
            recipe_data['Instruction'] = self.merge_zero_duration_steps(recipe_data['Instruction'])
            merged_count = len(recipe_data['Instruction'])
            print(f"✅ Step merging applied: {original_count} → {merged_count} steps")
            
            # VALIDATION: Log merged steps to confirm
            for i, step in enumerate(recipe_data['Instruction']):
                duration = safe_int(step.get('durationInSec', 0))
                text = step.get('Text', '')[:30]
                print(f"  Merged Step {i+1}: '{text}...' Duration: {duration}s")
        
        print(f"📏 Page width: {self.page_width/mm:.1f}mm")
        print(f"🎯 QR image status: {self.qr_image is not None}")
        
        # Rest of existing code remains the same...
        self.page_height = self.calculate_required_page_height(recipe_data, seconds_per_bar)
        print(f"📏 Calculated page height: {self.page_height/mm:.1f}mm")
        
        c = canvas.Canvas(output_path, pagesize=(self.page_width, self.page_height))
        self.draw_left_section(c, recipe_data, image_path)
        self.draw_right_section(c, recipe_data, seconds_per_bar)
        c.showPage()
        c.save()
        
        print(f"📄 PDF generated successfully: {output_path}")
        print("✅ PDF generation completed!")

    def draw_vertical_center_bar_with_timing(self, c, induction_x, magnetron_x, base_y, total_bars, recipe_data):
        """Draw simple black vertical bar (no blue/green coloring)"""
        center_x = (induction_x + magnetron_x) / 2
        bar_height = 1*mm
        bar_spacing = 1*mm
        total_height = (total_bars * bar_height) + ((total_bars) * bar_spacing)
        bar_width = 4*mm
        bar_end_y = base_y - total_height
        c.setFillColor(black)
        c.setStrokeColor(black)
        c.rect(center_x - (bar_width/2), bar_end_y + 1*mm, bar_width, total_height, stroke=0, fill=1)

    def consolidate_timeline_steps(self, instructions):
        """Consolidate instructions with correct cumulative time tracking"""
        if not instructions:
            return []
        
        # SAFETY CHECK: Ensure we're working with merged instructions
        print(f"🔍 Consolidating {len(instructions)} instructions...")
        for i, instr in enumerate(instructions):
            duration = safe_int(instr.get('durationInSec', 0))
            text = instr.get('Text', '')[:30]
            print(f"  Input Step {i+1}: '{text}...' Duration: {duration}s")
        
        consolidated_steps = []
        cumulative_time = 0
        step_number = 1
        
        for i, instruction in enumerate(instructions):
            duration = safe_int(instruction.get('durationInSec', 0))
            instruction_copy = instruction.copy()
            instruction_copy['step_number'] = step_number
            instruction_copy['start_time'] = cumulative_time
            instruction_copy['duration'] = duration
            instruction_copy['combined_instructions'] = [instruction]
            instruction_copy['Induction_power'] = instruction.get('Induction_power', '0')
            instruction_copy['Magnetron_power'] = instruction.get('Magnetron_power', '0')
            consolidated_steps.append(instruction_copy)
            
            if duration > 0:
                cumulative_time += duration
            step_number += 1
        
        print(f"✅ Consolidated to {len(consolidated_steps)} steps")
        return consolidated_steps

    def wrap_text_for_instruction(self, text, max_width_mm, font_name, font_size):
        """Wrap text to fit within specified width, breaking at word boundaries"""
        import textwrap
        from reportlab.pdfgen import canvas
        
        # Create a temporary canvas to measure text width
        temp_canvas = canvas.Canvas("temp")
        temp_canvas.setFont(font_name, font_size)
        
        # Calculate approximate characters per line based on average character width
        avg_char_width = temp_canvas.stringWidth("M", font_name, font_size)  # Use 'M' as average
        approx_chars_per_line = int((max_width_mm * mm) / avg_char_width)
        
        # Start with textwrap estimate, then refine
        wrapped_lines = textwrap.wrap(text, width=max(30, approx_chars_per_line + 5))
        
        # Refine by checking actual pixel width
        final_lines = []
        for line in wrapped_lines:
            line_width = temp_canvas.stringWidth(line, font_name, font_size)
            
            # If line is still too long, break it further
            while line_width > (max_width_mm * mm):
                # Find break point by reducing characters
                words = line.split()
                if len(words) <= 1:
                    # Single long word - break it forcefully
                    break_point = len(line) // 2
                    final_lines.append(line[:break_point] + "-")
                    line = line[break_point:]
                else:
                    # Remove last word and try again
                    line = " ".join(words[:-1])
                    remaining_words = words[-1:]
                    
                    # Add current line and continue with remaining
                    if line:
                        final_lines.append(line)
                    line = " ".join(remaining_words)
                
                line_width = temp_canvas.stringWidth(line, font_name, font_size)
            
            if line.strip():  # Don't add empty lines
                final_lines.append(line)
        
        print(f"📝 Wrapped text: '{text}' -> {len(final_lines)} lines")
        for i, line in enumerate(final_lines):
            print(f"   Line {i+1}: '{line}'")
        
        return final_lines

    def draw_step_intersection_circles(self, c, consolidated_steps, center_x, scale_y, total_bars, extra_bars, bar_height, bar_spacing, seconds_per_bar): 
        circle_radius = 2*mm
        print(f"Drawing {len(consolidated_steps)} intersection circles")
        
        elapsed_time = 0
        for i, step in enumerate(consolidated_steps):
            step_number = i + 1
            duration = step.get('durationInSec', 0)
            
            # Special handling for first step with duration 0 - position at TOP of timeline
            if step_number == 1 and duration == 0:
                target_bar_y = scale_y + 1*mm
                print(f"Circle {step_number}: positioned at TOP of timeline Y={target_bar_y} (duration=0)")
            else:
                # NEW: Use bar-based rounding for accurate positioning
                bar_position = self.calculate_bar_position_with_rounding(elapsed_time, seconds_per_bar)
                target_bar_y = scale_y - (extra_bars * (bar_height + bar_spacing)) - (bar_position * (bar_height + bar_spacing))
                print(f"Circle {step_number}: positioned at bar {bar_position} Y={target_bar_y} (start_time={elapsed_time}s)")
            
            # Draw the circle and step number
            c.saveState()
            c.setFillColor(self.skin_color)
            c.setStrokeColor(black)
            c.setLineWidth(0.5)
            c.circle(center_x, target_bar_y, circle_radius, fill=1, stroke=1)
            c.setFillColor(black)
            c.setFont(self.instruction_font, 8)
            c.drawCentredString(center_x, target_bar_y - 0.8*mm, str(step_number))
            c.restoreState()
            
            elapsed_time += duration

    def draw_step_blocks_with_timing(self, c, x_offset, scale_y, recipe_data, total_time_sec, total_bars, extra_bars, seconds_per_bar):
        """Draw step blocks with proper timing connections and text wrapping"""
        instructions = recipe_data.get('Instruction', [])
        consolidated_steps = self.consolidate_timeline_steps(instructions)
        block_width = 17 * mm
        block_height = 6 * mm
        corner_radius = 5 * mm
        vertical_spacing = 7 * mm
        circle_radius = self.circle_diameter / 2
        magnetron_x = self.page_width - 15 * mm
        induction_x = magnetron_x - 23 * mm
        center_x = (induction_x + magnetron_x) / 2
        bar_height = 1 * mm
        bar_spacing = 1 * mm
        
        # Calculate maximum text width to avoid timeline overlap
        text_start_x = x_offset + 6 * mm
        timeline_left_boundary = induction_x - circle_radius # 10mm buffer
        max_text_width_mm = (timeline_left_boundary - text_start_x) / mm
        
        print(f"📏 Text boundary: {max_text_width_mm:.1f}mm (from {text_start_x/mm:.1f}mm to {timeline_left_boundary/mm:.1f}mm)")
        
        print(f"Total time: {total_time_sec}s, Total bars: {total_bars}, Extra bars: {extra_bars}")
        for i, step in enumerate(consolidated_steps):
            print(f"Step {i + 1}: start_time={step.get('start_time', 0)}s, duration={step.get('durationInSec', 0)}s")
        
        current_y = scale_y
        for i, step in enumerate(consolidated_steps):
            step_number = i + 1
            step_y = current_y - (i * vertical_spacing)
            
            # Draw step block
            self.draw_top_rounded_rect(c, x_offset + 4 * mm, step_y + 1*mm,
                                    block_width, block_height, corner_radius, self.skin_color)
            c.setFillColor(black)
            c.setFont(self.step_title_font, 11)
            c.drawString(x_offset + 4 * mm + 2*mm, step_y + 2* mm, f"Step {step_number}")  # Left-aligned
            
            # Draw duration
            duration = step.get('durationInSec', 0)
            if duration >= 0:
                mins, secs = divmod(int(duration), 60)
                # UPDATED: Apply time formatting rules
                if mins > 0:
                    if mins == 1 and secs == 0:
                        duration_text = "1:00 min"  # Remove 's' for exactly 1:00
                    else:
                        duration_text = f"{mins}:{secs:02d} mins"  # Keep 's' for other times
                else:
                    duration_text = f"0:{secs:02d} secs"  # Change sec. to secs.
                
                circle_x = x_offset + 1* mm + block_width + 15 * mm
                small_r = 1.5* mm
                c.setFillColor(self.green_time)
                c.circle(circle_x - 1*mm, step_y + 3.5* mm, small_r, fill=1, stroke=0)
                c.setFillColor(black)
                c.setFont(self.section_detail_font, 11)
                c.drawString(circle_x + small_r + 0 * mm, step_y + 2 * mm, duration_text)
            
            # Handle instruction text with wrapping
            instruction_text = step.get('Text', '')
            if instruction_text:
                # Get weighted instruction lines
                lines = self.parse_instruction_with_weight(instruction_text, recipe_data, step)
                
                # Apply text wrapping to each line
                wrapped_lines = []
                for line in lines:
                    wrapped = self.wrap_text_for_instruction(
                        line, 
                        max_text_width_mm, 
                        self.section_detail_font, 
                        9
                    )
                    wrapped_lines.extend(wrapped)
                
                # Calculate space needed for wrapped text
                num_lines = len(wrapped_lines)
                line_height = 4 * mm
                instruction_height = num_lines * line_height
                
                # Draw power circles
                power_y = step_y - block_height / 2 - 4 * mm - instruction_height
                self.draw_power_circles_with_values(c, x_offset + 3 * mm, power_y - 0*mm, step)
                
                # Draw wrapped instruction text
                c.setFillColor(black)
                c.setFont(self.section_detail_font, 9)
                instruction_y = power_y + 7 * mm
                
                for j, line in enumerate(wrapped_lines):
                    c.drawString(text_start_x, instruction_y + (j * line_height), line)
                    print(f"   📝 Drew line {j+1}: '{line}' at Y={instruction_y + (j * line_height)}")
            
            # Draw connection lines
            line_start_x = x_offset - 13 * mm + block_width
            line_start_y = step_y + 1 * mm
            step_start_time = step.get('start_time', 0)
            
            c.setStrokeColor(HexColor('#ed1c24'))
            c.setLineWidth(0.5)
            if step_number == 1 and step.get('durationInSec', 0) == 0:
                top_timeline_y = scale_y + 1*mm
                c.line(line_start_x, line_start_y, center_x, top_timeline_y)
                print(f"Step {step_number}: Connected to TOP of timeline at Y={top_timeline_y} (start_time={step_start_time}s)")
            else:
                bar_position = self.calculate_bar_position_with_rounding(step_start_time, seconds_per_bar)
                target_timeline_y = scale_y - (extra_bars * (bar_height + bar_spacing)) - (bar_position * (bar_height + bar_spacing))
                
                horizontal_extension = 47 * mm
                inter_x = line_start_x + (horizontal_extension + (step_number*1*mm))
                c.line(line_start_x, line_start_y, inter_x, line_start_y)
                c.line(inter_x, line_start_y, inter_x, target_timeline_y+1*mm)
                c.line(inter_x, target_timeline_y+1*mm, center_x, target_timeline_y+1*mm)
                print(f"Step {step_number}: Connected to bar {bar_position} at Y={target_timeline_y} (start_time={step_start_time}s)")
            
            # Update spacing calculation for wrapped text
            if instruction_text:
                current_y -= (block_height / 2 + 4 * mm + instruction_height + 2 * mm)
            else:
                current_y -= vertical_spacing
        
        # Draw circles and stirrer bars
        self.draw_step_intersection_circles(c, consolidated_steps, center_x, scale_y,
                                        total_bars, extra_bars, bar_height, bar_spacing, seconds_per_bar)
        self.draw_stirrer_speed_bars(c, consolidated_steps, center_x, scale_y,
                                    total_time_sec, total_bars, extra_bars, seconds_per_bar)

    def draw_timeline(self, c, x_offset, start_y, recipe_data, seconds_per_bar):
        """Draw timeline with ruler, bars, vertical bar, step blocks"""
        circle_radius = self.circle_diameter / 2
        magnetron_x = self.page_width - 15*mm
        induction_x = magnetron_x - 23*mm
        instructions = recipe_data.get('Instruction', [])
        total_time_sec = sum(int(instr.get('durationInSec', 0)) for instr in instructions)
        first_duration = safe_int(instructions[0].get('durationInSec', 0)) if instructions else 0
        extra_bars = 5 if first_duration == 0 else 0
        
        # Use rounding logic for total bars calculation
        time_bars = self.calculate_bar_position_with_rounding(total_time_sec, seconds_per_bar)
        total_bars = time_bars + extra_bars
        
        # ADD DEBUG: Verify the calculation
        print(f"DEBUG: total_time_sec={total_time_sec}, seconds_per_bar={seconds_per_bar}")
        print(f"DEBUG: time_bars={time_bars}, extra_bars={extra_bars}, total_bars={total_bars}")
        
        scale_y = start_y + 20*mm
        self.draw_ruler_ticks(c, induction_x, magnetron_x, scale_y)
        self.draw_time_based_horizontal_bars(c, induction_x, magnetron_x, scale_y, total_bars, recipe_data, extra_bars, seconds_per_bar)
        self.draw_vertical_center_bar_with_timing(c, induction_x, magnetron_x, scale_y, total_bars, recipe_data)
        self.draw_step_blocks_with_timing(c, x_offset, scale_y, recipe_data, total_time_sec, total_bars, extra_bars, seconds_per_bar)
        bar_height = 1*mm
        bar_spacing = 1*mm
        self.draw_timeline_completion_tick(c, induction_x, magnetron_x, scale_y, total_bars, bar_height, bar_spacing)

    def debug_power_values(self, recipe_data):
        instructions = recipe_data.get('Instruction', [])
        print("=== DEBUG: Power Values ===")
        for i, instr in enumerate(instructions):
            duration = instr.get('durationInSec', 0)
            induction = instr.get('Induction_power', 0)
            magnetron = instr.get('Magnetron_power', 0)
            text = instr.get('Text', '')
            print(f"Instruction {i+1}: {text[:30]}... Duration: {duration}s, Induction: {induction}, Magnetron: {magnetron}")

    def draw_colored_power_bars(self, c, induction_x, magnetron_x, base_y, recipe_data, total_bars, extra_bars, seconds_per_bar):
        """Draw horizontal bars with power coloring and blue for pump-on periods, using Induction_on_time and Magnetron_on_time separately."""
        instructions = recipe_data.get('Instruction', [])
        bar_height = 1*mm
        bar_spacing = 1*mm
        circle_radius = self.circle_diameter / 2
        line_start_x = induction_x - circle_radius
        line_end_x = magnetron_x + circle_radius
        total_width = line_end_x - line_start_x
        half_width = total_width / 2
        center_x = line_start_x + half_width
        print("=== PUMP BAR COLORING DEBUG (with separate Induction/Magnetron times) ===")
        current_time = 0
        for i, instr in enumerate(instructions):
            duration = safe_int(instr.get('durationInSec', 0))
            induction_power = safe_int(instr.get('Induction_power', 0))
            magnetron_power = safe_int(instr.get('Magnetron_power', 0))
            induction_time = safe_int(instr.get('Induction_on_time', 0))
            magnetron_time = safe_int(instr.get('Magnetron_on_time', 0))
            pump_on = safe_int(instr.get('pump_on', 0))
            print(f"Instruction {i+1}: duration={duration}s, induction_time={induction_time}s, magnetron_time={magnetron_time}s, pump_on={pump_on}s, start_time={current_time}s")
            if duration > 0:
                # Calculate bar positions for induction
                induction_start_bar = self.calculate_bar_position_with_rounding(current_time, seconds_per_bar)
                induction_end_bar = self.calculate_bar_position_with_rounding(current_time + induction_time, seconds_per_bar) if induction_time > 0 else induction_start_bar
                # Calculate bar positions for magnetron
                magnetron_start_bar = self.calculate_bar_position_with_rounding(current_time, seconds_per_bar)
                magnetron_end_bar = self.calculate_bar_position_with_rounding(current_time + magnetron_time, seconds_per_bar) if magnetron_time > 0 else magnetron_start_bar
                # Calculate pump period
                pump_end_time = current_time + pump_on if pump_on > 0 else current_time
                pump_end_bar = self.calculate_bar_position_with_rounding(pump_end_time, seconds_per_bar) if pump_on > 0 else induction_start_bar
                print(f"  Induction bars: {induction_start_bar} to {induction_end_bar}")
                print(f"  Magnetron bars: {magnetron_start_bar} to {magnetron_end_bar}")
                print(f"  Pump period: {current_time}s to {pump_end_time}s (bars {induction_start_bar} to {pump_end_bar})")
                # Determine the maximum end bar for this instruction to prevent exceeding timeline
                max_end_bar = max(induction_end_bar, magnetron_end_bar, pump_end_bar)
                max_bar_position = min(max_end_bar, total_bars - extra_bars - 1)
                print(f"  Adjusted max bar range: {induction_start_bar} to {max_bar_position}")
                # Draw bars for this instruction
                for bar_position in range(induction_start_bar, max_bar_position + 1):
                    actual_bar_index = extra_bars + bar_position
                    if actual_bar_index >= total_bars:
                        print(f"    BOUNDARY: Skipping bar {bar_position} (index {actual_bar_index}) - exceeds total_bars {total_bars}")
                        break
                    bar_y = base_y - (actual_bar_index * (bar_height + bar_spacing))
                    if bar_y < 0:
                        print(f"    CLIPPING: Skipping bar {bar_position} - Y position {bar_y/mm:.1f}mm is negative")
                        break
                    # Check if this bar is within pump period
                    is_pump_period = (pump_on > 0 and bar_position < pump_end_bar)
                    if is_pump_period:
                        print(f"    Bar {bar_position} (index {actual_bar_index}): BLUE at Y={bar_y/mm:.1f}mm")
                        c.setFillColor(self.blue_color)
                        c.rect(line_start_x, bar_y, total_width, bar_height, stroke=0, fill=1)
                    else:
                        # Draw induction bars
                        if induction_power > 0 and induction_start_bar <= bar_position < induction_end_bar:
                            power_ratio = min(induction_power / 100.0, 1.0)
                            induction_width = half_width * power_ratio
                            induction_x_pos = center_x - induction_width
                            c.setFillColor(self.bar_orange)
                            c.rect(induction_x_pos, bar_y, induction_width, bar_height, stroke=0, fill=1)
                            print(f"    Bar {bar_position} (index {actual_bar_index}): ORANGE at Y={bar_y/mm:.1f}mm (I:{induction_power})")
                        # Draw magnetron bars
                        if magnetron_power > 0 and magnetron_start_bar <= bar_position < magnetron_end_bar:
                            power_ratio = min(magnetron_power / 100.0, 1.0)
                            magnetron_width = half_width * power_ratio
                            c.setFillColor(self.bar_red)
                            c.rect(center_x, bar_y, magnetron_width, bar_height, stroke=0, fill=1)
                            print(f"    Bar {bar_position} (index {actual_bar_index}): RED at Y={bar_y/mm:.1f}mm (M:{magnetron_power})")
            current_time += duration
        print("=== END PUMP BAR DEBUG ===")
    def draw_left_section(self, c, recipe_data, image_path):
        # Draw image or placeholder
        if image_path and os.path.exists(image_path):
            try:
                c.drawImage(image_path, 0, self.page_height - self.image_height,
                            width=self.image_width, height=self.image_height,
                            preserveAspectRatio=False, anchor='nw')
            except Exception as e:
                print(f"Image processing error: {e}")
                c.setFillColor(self.skin_color)
                c.rect(0, self.page_height - self.image_height,
                    self.image_width, self.image_height, fill=1)
        else:
            c.setFillColor(self.skin_color)
            c.rect(0, self.page_height - self.image_height,
                self.image_width, self.image_height, fill=1)
        
        text_margin = 8 * mm
        y_pos = self.page_height - self.image_height - 15 * mm
        
        # Draw recipe name
        recipe_name = recipe_data.get('name', ['Unknown Recipe'])
        if isinstance(recipe_name, list):
            recipe_name = recipe_name[0] if recipe_name else 'Unknown Recipe'
        recipe_name = ' '.join(word.capitalize() for word in recipe_name.split())
        reduced_name_size = 18
        c.setFont(self.recipe_name_font, reduced_name_size)
        c.setFillColor(black)
        max_width = self.image_width - (2 * text_margin)
        text_width = c.stringWidth(recipe_name, self.recipe_name_font, reduced_name_size)
        if text_width > max_width:
            scale_factor = max_width / text_width
            adjusted_size = reduced_name_size * scale_factor
            c.setFont(self.recipe_name_font, adjusted_size)
        c.drawString(text_margin, y_pos, recipe_name)
        y_pos -= 7 * mm
        
        def draw_underlined_header(text, ypos):
            c.setFont(self.section_title_font, self.section_title_size)
            c.setFillColor(black)
            c.drawString(text_margin, ypos, text)
            word_width = c.stringWidth(text, self.section_title_font, self.section_title_size)
            line_start = text_margin + word_width + 3 * mm
            line_end = self.image_width - 8 * mm
            c.setLineWidth(0.1 * mm)
            c.setStrokeColor(self.line_color)
            c.line(line_start, ypos - 1, line_end, ypos - 1)
        
        # Cooking Time
        draw_underlined_header("Cooking Time", y_pos)
        y_pos -= 7 * mm
        c.setFont(self.section_detail_font, self.section_detail_size)
        cooking_times = self.extract_cooking_time(recipe_data)
        for time_line in cooking_times:
            c.drawString(text_margin, y_pos, time_line)
            y_pos -= 6 * mm
        y_pos -= 0 * mm
        
        # Accessories - Bold title, normal content, no underline
        accessories = self.extract_accessories(recipe_data)
        c.setFont(self.section_title_font, self.section_title_size)  # Bold for "Accessories:"
        c.setFillColor(black)
        title_text = "Accessories:"
        c.drawString(text_margin, y_pos, title_text)
        title_width = c.stringWidth(title_text, self.section_title_font, self.section_title_size)
        
        c.setFont(self.section_detail_font, self.section_detail_size)  # Normal font for content
        if accessories:
            if len(accessories) >= 2:
                content_text = f" {accessories[0]}, {accessories[1]}"  # Space for alignment
                c.drawString(text_margin + title_width, y_pos, content_text)
                y_pos -= 6 * mm
                for acc in accessories[2:]:
                    c.drawString(text_margin + 20 * mm, y_pos, acc)
                    y_pos -= 6 * mm
            else:
                content_text = f" {accessories[0]}"  # Space for alignment
                c.drawString(text_margin + title_width, y_pos, content_text)
                y_pos -= 6 * mm
        else:
            content_text = " N/A"  # Space for alignment
            c.drawString(text_margin + title_width, y_pos, content_text)
            y_pos -= 6 * mm
        
        # Ingredients
        y_pos -= 3 * mm
        draw_underlined_header("Ingredients", y_pos)
        y_pos -= 8 * mm
        
        c.setFont(self.section_detail_font, self.section_detail_size)
        ingredients = self.extract_ingredients(recipe_data)
        for ingredient in ingredients:
            if y_pos < 10 * mm:
                break
            if ingredient.startswith('  '):
                c.setFont(self.section_detail_font, self.section_detail_size)
                c.drawString(text_margin + 20 * mm, y_pos, ingredient.strip())
            else:
                c.setFont(self.section_detail_font, self.section_detail_size)
                if '\t' in ingredient:
                    weight, name = ingredient.split('\t', 1)
                    c.drawString(text_margin, y_pos, weight)
                    c.drawString(text_margin + 20 * mm, y_pos, name)
                else:
                    c.drawString(text_margin, y_pos, ingredient)
            y_pos -= 5 * mm
        
        # Other Essentials
        other_essentials = self.extract_other_essentials(recipe_data)
        if other_essentials:
            y_pos -= 3 * mm
            draw_underlined_header("Other Essentials", y_pos)
            y_pos -= 8 * mm
            
            c.setFont(self.section_detail_font, 10)
            for essential in other_essentials:
                if y_pos < 20 * mm:
                    break
                if essential.startswith('  '):
                    c.setFont(self.section_detail_font, 10)
                    c.drawString(text_margin + 20 * mm, y_pos, essential.strip())
                else:
                    c.setFont(self.section_detail_font, 10)
                    if '\t' in essential:
                        weight, name = essential.split('\t', 1)
                        c.drawString(text_margin, y_pos, weight)
                        c.drawString(text_margin + 20 * mm, y_pos, name)
                    else:
                        c.drawString(text_margin, y_pos, essential)
                y_pos -= 5 * mm
    def draw_top_rounded_rect(self, c, x, y, width, height, radius, fill_color):
        """Draw rectangle with only top corners rounded"""
        c.saveState()
        c.setFillColor(fill_color)
        c.setStrokeColor(fill_color)
        path = c.beginPath()
        path.moveTo(x, y)
        path.lineTo(x + width, y)
        path.lineTo(x + width, y + height - radius)
        path.arcTo(x + width - radius, y + height - radius, x + width, y + height, startAng=0, extent=90)
        path.lineTo(x + radius, y + height)
        path.arcTo(x, y + height - radius, x + radius, y + height, startAng=90, extent=90)
        path.lineTo(x, y)
        c.drawPath(path, stroke=0, fill=1)
        c.restoreState()

    def draw_step_to_ruler_lines(self, c, consolidated_steps, block_x, block_width, ruler_left_x, start_y, vertical_spacing, extra_bars, bar_height, bar_spacing):
        """Draw connecting lines from step blocks to ruler, adjusting for extra bars when first step has zero duration"""
        c.saveState()
        c.setStrokeColor(HexColor('#800000'))
        c.setLineWidth(0.5)
        for i, step in enumerate(consolidated_steps):
            step_y = start_y - (i * vertical_spacing)
            line_start_x = block_x + block_width
            line_start_y = step_y + 1 * mm
            line_end_x = ruler_left_x
            if i == 0 and safe_int(step.get('durationInSec', 0)) == 0:
                line_end_y = start_y - (extra_bars * (bar_height + bar_spacing))
            else:
                line_end_y = step_y + 1 * mm
            c.line(line_start_x, line_start_y, line_end_x, line_end_y)
        c.restoreState()

    def draw_power_circles_with_values(self, c, x_pos, y_pos, step):
        """Draw larger orange and red circles with 'I' and 'M' labels inside"""
        induction_power = step.get('Induction_power', '0')
        magnetron_power = step.get('Magnetron_power', '0')
        circle_radius = 2.0*mm
        circle_spacing = 20*mm
        c.setFillColor(self.orange_color)
        c.circle(x_pos+5.5*mm, y_pos+3*mm, circle_radius, fill=1, stroke=0)
        c.setFillColor(white)
        c.setFont(self.section_detail_font, 8)
        c.drawCentredString(x_pos+5.5*mm, y_pos+2*mm, "I")
        c.setFillColor(black)
        c.setFont(self.section_detail_font, 11)
        c.drawString(x_pos + circle_radius + 6.5*mm, y_pos + 2*mm, induction_power)
        red_circle_x = x_pos + circle_spacing
        c.setFillColor(self.red_color)
        c.circle(red_circle_x+2.5*mm, y_pos+3*mm, circle_radius, fill=1, stroke=0)
        c.setFillColor(white)
        c.setFont(self.section_detail_font, 8)
        c.drawCentredString(red_circle_x+2.5*mm, y_pos+2*mm, "M")
        c.setFillColor(black)
        c.setFont(self.section_detail_font, 11)
        c.drawString(red_circle_x + circle_radius + 3.5*mm, y_pos + 2*mm, magnetron_power)

    def draw_total_output(self, c, x_offset, recipe_data, seconds_per_bar):
        """Draw the total output at the bottom of the timeline with formatting from the old version."""
        # Extract the output value using the existing method
        total_output = self.extract_output(recipe_data)
        
        # Set font and color
        c.setFont(self.section_title_font, 10)
        c.setFillColor(black)
        
        # Calculate center_x as the timeline's vertical center bar position
        magnetron_x = self.page_width - 15 * mm
        induction_x = magnetron_x - 23 * mm
        center_x = (induction_x + magnetron_x) / 2
        
        # Calculate timeline bottom position
        instructions = recipe_data.get('Instruction', [])
        total_time_sec = sum(int(instr.get('durationInSec', 0)) for instr in instructions)
        first_duration = safe_int(instructions[0].get('durationInSec', 0)) if instructions else 0
        extra_bars = 5 if first_duration == 0 else 0
        time_bars = self.calculate_bar_position_with_rounding(total_time_sec, seconds_per_bar)
        total_bars = time_bars + extra_bars
        
        bar_height = 1 * mm
        bar_spacing = 1 * mm
        timeline_start_y = (self.page_height - 30 * mm) - 35 * mm
        timeline_end_y = timeline_start_y - (total_bars * (bar_height + bar_spacing))
        
        # Place output value 8 mm above bottom, "Total Output" 4 mm above it
        output_y = 8 * mm
        total_output_y = 12 * mm
        
        # Ensure text is below timeline
        if output_y <= timeline_end_y <= total_output_y:
            total_output_y = timeline_end_y - 4 * mm
            output_y = timeline_end_y - 8 * mm
        
        # Draw the text
        c.drawCentredString(center_x, total_output_y, "Total Output:")
        c.drawCentredString(center_x, output_y, total_output)
        print("🔍 Drawing total output...")

    def parse_instruction_with_weight(self, instruction_text, recipe_data, current_step=None):
        instruction_text = clean_time_and_units_text(instruction_text)
        exclude_cooking_actions = [
            'dum', 'mix', 'marinate', 'stir', 'cook', 'saute', 'heat', 
            'fry', 'boil', 'grill', 'roast', 'bake', 'steam', 'simmer',
            'blend', 'whisk', 'knead', 'rest', 'cool', 'chill', 'freeze',
            'serve', 'garnish', 'season', 'taste', 'adjust', 'cover',
            'uncover', 'turn', 'flip', 'drain', 'strain', 'filter'
        ]
        if any(action in instruction_text.lower() for action in exclude_cooking_actions):
            print(f"🚫 Excluding cooking action: '{instruction_text}' (no weight added)")
            return [instruction_text]
        lines = []
        # If the instruction text already contains weights (from merging), use it as-is
        if re.search(r'\d+\s*(g|gm|ml|kg|l|number|Nos|inch)\b', instruction_text, re.IGNORECASE):
            print(f"🎯 Instruction already contains weights: '{instruction_text}'")
            return [instruction_text]
        # Fallback: Split instruction and look up weights
        if ', ' in instruction_text:
            instruction_parts = instruction_text.split(', ')
        else:
            instruction_parts = [instruction_text]
        ingredients = recipe_data.get('Ingredients', [])
        for instruction in instruction_parts:
            instruction = instruction.strip()
            weight_found = False
            display_line = instruction
            if current_step and current_step.get('Weight'):
                step_weight = current_step.get('Weight', '').strip()
                step_weight = clean_time_and_units_text(step_weight)
                if step_weight:
                    display_line = f"{step_weight} {instruction}"
                    weight_found = True
                    print(f"🎯 Using step weight: {step_weight} for '{instruction}'")
            if not weight_found:
                for ingredient in ingredients:
                    ing_title = ingredient.get('title', '').strip()
                    ing_weight = ingredient.get('weight', '').strip()
                    ing_weight = clean_time_and_units_text(ing_weight)
                    if ing_title.lower() == instruction.lower():
                        if ing_weight:
                            display_line = f"{ing_weight} {instruction}"
                            weight_found = True
                            print(f"🔍 Using ingredient weight: {ing_weight} for '{instruction}' (exact match)")
                            break
                if not weight_found:
                    for ingredient in ingredients:
                        ing_title = ingredient.get('title', '').strip()
                        ing_weight = ingredient.get('weight', '').strip()
                        ing_weight = clean_time_and_units_text(ing_weight)
                        if ing_title.lower() in instruction.lower():
                            if ing_weight:
                                display_line = f"{ing_weight} {instruction}"
                                weight_found = True
                                print(f"🔍 Using ingredient weight: {ing_weight} for '{instruction}' (partial match)")
                                break
            if not weight_found:
                display_line = instruction
            lines.append(display_line)
        return lines
    def draw_right_section(self, c, recipe_data, seconds_per_bar):
        print("🔍 === DRAWING RIGHT SECTION ===")
        print(f" QR image available: {self.qr_image is not None}")
        
        x_offset = self.left_section_width + self.left_margin
        circle_y = self.page_height - 30*mm
        circle_radius = self.circle_diameter / 2
        magnetron_x = self.page_width - 15*mm
        induction_x = magnetron_x - 23*mm
        
        # Draw QR code at top-left of right section if available
        if self.qr_image:
            print(" Drawing QR code on PDF...")
            try:
                # Convert PIL image to a temporary file for ReportLab
                tmp_qr_path = os.path.join(tempfile.gettempdir(), "qr_temp_image.png")
                print(f"💾 Saving QR to temp file: {tmp_qr_path}")
                self.qr_image.save(tmp_qr_path)
                print(f"✅ QR saved to temp file successfully")
                
                # Position: top-left of right section
                qr_margin_x = x_offset + 5*mm
                qr_margin_y = self.page_height - 5*mm

                qr_size = 24*mm
                print(f" QR position: x={qr_margin_x/mm:.1f}mm, y={qr_margin_y/mm:.1f}mm, size={qr_size/mm:.1f}mm")
                
                c.drawImage(tmp_qr_path, qr_margin_x, qr_margin_y - qr_size,
                            width=qr_size, height=qr_size, preserveAspectRatio=True, mask='auto')
                print("✅ QR code drawn on PDF successfully!")
                
                # Add text on the right side of QR code
                text_x = qr_margin_x + qr_size + 3*mm
                text_start_y = qr_margin_y - 3*mm
                
                # Set font and color for QR text
                c.setFont(self.section_detail_font, 9)
                c.setFillColor(black)
                
                # Draw the three lines of text
                line_spacing = 4*mm
                c.drawString(text_x, text_start_y, "Scan to")
                c.drawString(text_x, text_start_y - line_spacing, "Download")
                c.drawString(text_x, text_start_y - (2 * line_spacing), "The Recipe")
                print("✅ QR text labels drawn successfully!")
                
            except Exception as e:
                print(f"❌ QR draw error: {e}")
                import traceback
                traceback.print_exc()
        else:
            print("ℹ️ No QR image available, skipping QR drawing")
        
        print("🔍 Drawing INDUCTION and MICROWAVE circles...")
        # INDUCTION circle
        c.setFillColor(self.orange_color)
        c.circle(induction_x, circle_y, circle_radius, fill=1, stroke=0)
        c.setFillColor(white)
        c.setFont(self.section_title_font, 7)
        c.drawCentredString(induction_x, circle_y - 2, "INDUCTION")
        
        # MICROWAVE circle
        c.setFillColor(self.red_color)
        c.circle(magnetron_x, circle_y, circle_radius, fill=1, stroke=0)
        c.setFillColor(white)
        c.setFont(self.section_title_font, 7)
        c.drawCentredString(magnetron_x, circle_y - 2, "MICROWAVE")
        if self.has_stirrer_activity(recipe_data):
            print("🔍 Stirrer activity detected, drawing stirrer SVG...")
            # Calculate center position between induction and microwave circles
            stirrer_x = (induction_x + magnetron_x) / 2
            stirrer_y = circle_y
            
            # Draw the stirrer SVG (adjust scale as needed)
            self.draw_stirrer_svg(c, 
                                stirrer_x - 2.3*mm,  # Offset to center the SVG
                                stirrer_y - 10*mm,  # Offset to center the SVG
                                'Stirrer.svg',      # SVG file path
                                scale=0.6)          # Scale factor (adjust as needed)
        else:
            print("ℹ️ No stirrer activity detected, skipping stirrer SVG")
        timeline_start_y = circle_y - 35*mm
        print("🔍 Drawing timeline...")
        self.draw_timeline(c, x_offset, timeline_start_y, recipe_data, seconds_per_bar)
        print("🔍 Drawing total output...")
        self.draw_total_output(c, x_offset, recipe_data, seconds_per_bar)  # Pass parameter
        print("✅ Right section drawing completed!")

    def draw_stirrer_speed_bars(self, c, consolidated_steps, center_x, scale_y, total_time_sec, total_bars, extra_bars, seconds_per_bar):
        """Draw thin VERTICAL stirrer bars with proper timing and colors based on speed"""
        stirrer_colors = {
            'off': None, '0': None, '': None,
            'low': white, '1': white,
            'medium': HexColor('#08a045'), '2': HexColor('#08a045'), 
            'high': HexColor('#FFA500'), '3': HexColor('#FFA500'),
            'very high': HexColor('#FF0000'), '4': HexColor('#FF0000'),
        }
        
        bar_height = 1*mm
        bar_spacing = 1*mm
        thin_bar_width = 0.5*mm  # Slightly wider for better visibility
        circle_radius = 2*mm
        circle_buffer = 0.5*mm  # Reduced buffer for tighter spacing
        
        print("=== STIRRER SPEED VERTICAL BARS DEBUG (Proper timing) ===")
        
        # Calculate circle positions using same coordinate system as step connections
        circle_positions = []
        elapsed_time = 0
        for i, step in enumerate(consolidated_steps):
            step_number = i + 1
            duration = step.get('durationInSec', 0)
            
            if step_number == 1 and duration == 0:
                # First step with zero duration - position at top
                circle_y = scale_y + 1*mm
            else:
                # Use bar-based rounding for accurate positioning
                bar_position = self.calculate_bar_position_with_rounding(elapsed_time, seconds_per_bar)
                circle_y = scale_y - (extra_bars * (bar_height + bar_spacing)) - (bar_position * (bar_height + bar_spacing))
            
            circle_positions.append(circle_y)
            elapsed_time += duration
        
        # Draw stirrer bars using proper timing calculations
        current_time = 0
        for i, step in enumerate(consolidated_steps):
            duration = step.get('durationInSec', 0)
            stirrer_speed = str(step.get('stirrer_on', '0')).strip().lower()
            
            if duration <= 0:
                current_time += duration
                continue
                
            color = stirrer_colors.get(stirrer_speed, None)
            if color is None:
                print(f"  Step {i+1}: No stirrer (speed: {stirrer_speed})")
                current_time += duration
                continue
            
            # Calculate bar positions using rounding logic
            start_bar_position = self.calculate_bar_position_with_rounding(current_time, seconds_per_bar)
            end_bar_position = self.calculate_bar_position_with_rounding(current_time + duration, seconds_per_bar)
            
            # Convert to Y coordinates using same system as power bars
            start_y = scale_y - (extra_bars * (bar_height + bar_spacing)) - (start_bar_position * (bar_height + bar_spacing))
            end_y = scale_y - (extra_bars * (bar_height + bar_spacing)) - (end_bar_position * (bar_height + bar_spacing))
            
            segment_height = start_y - end_y
            
            # Avoid drawing over step circles
            segments_to_draw = [(end_y, segment_height)]
            
            for circle_y in circle_positions:
                new_segments = []
                for seg_y, seg_height in segments_to_draw:
                    seg_top = seg_y + seg_height
                    
                    # Check if circle intersects this segment
                    if (seg_y <= circle_y <= seg_top):
                        # Split segment around circle
                        circle_top = circle_y + circle_radius + circle_buffer
                        circle_bottom = circle_y - circle_radius - circle_buffer
                        
                        # Segment above circle
                        if seg_top > circle_top:
                            above_height = seg_top - circle_top
                            new_segments.append((circle_top, above_height))
                        
                        # Segment below circle  
                        if seg_y < circle_bottom:
                            below_height = circle_bottom - seg_y
                            new_segments.append((seg_y, below_height))
                    else:
                        # No intersection, keep original segment
                        new_segments.append((seg_y, seg_height))
                
                segments_to_draw = new_segments
            
            # Draw all segments for this step
            total_drawn_height = 0
            for seg_y, seg_height in segments_to_draw:
                if seg_height > 0.5*mm:  # Only draw segments larger than 0.5mm
                    c.setFillColor(color)
                    c.setStrokeColor(color)
                    c.setLineWidth(0.2)
                    c.rect(center_x - thin_bar_width/2, seg_y, thin_bar_width, seg_height, stroke=1, fill=1)
                    total_drawn_height += seg_height
            
            print(f"  Step {i+1}: Drew stirrer bar (speed: {stirrer_speed}, color: {color}, height: {total_drawn_height/mm:.1f}mm)")
            current_time += duration
        
        print("=== END STIRRER SPEED DEBUG ===")

    def draw_ruler_ticks(self, c, induction_x, magnetron_x, base_y):
        """Draw ruler ticks with alternating heights"""
        circle_radius = self.circle_diameter / 2
        c.setStrokeColor(black)
        c.setLineWidth(0.3)
        tick_count = 10
        tick_height_small = 2*mm
        tick_height_large = 3*mm
        tick_spacing = self.circle_diameter / tick_count
        left_tick_start = induction_x - circle_radius
        for i in range(tick_count + 1):
            x_pos = left_tick_start + (i * tick_spacing)
            tick_height = tick_height_large if i % 2 == 0 else tick_height_small
            c.line(x_pos, base_y, x_pos, base_y + tick_height)
        right_tick_start = magnetron_x - circle_radius
        for i in range(tick_count + 1):
            x_pos = right_tick_start + (i * tick_spacing)
            tick_height = tick_height_large if i % 2 == 0 else tick_height_small
            c.line(x_pos, base_y, x_pos, base_y + tick_height)
        line_start_x = left_tick_start
        line_end_x = right_tick_start + self.circle_diameter
        c.setLineWidth(0.3)

    def draw_timeline_completion_tick(self, c, induction_x, magnetron_x, scale_y, total_bars, bar_height, bar_spacing):
        """Draw a tick mark at the end of the timeline to indicate completion"""
        circle_radius = self.circle_diameter / 2
        line_start_x = induction_x - circle_radius
        line_end_x = magnetron_x + circle_radius
        last_bar_y = scale_y - (total_bars * (bar_height + bar_spacing))
        center_x = (line_start_x + line_end_x) / 2
        tick_y = last_bar_y
        tick_circle_radius = 2*mm
        c.setFillColor(self.skin_color)
        c.setStrokeColor(black)
        c.setLineWidth(0.5)
        c.circle(center_x, tick_y, tick_circle_radius, fill=1, stroke=1)
        c.setFillColor(black)
        c.setFont('Helvetica-Bold', 8)
        c.drawCentredString(center_x, tick_y - 1*mm, "✓")
        print(f"Drew completion tick at ({center_x}, {tick_y})")

    def draw_time_based_horizontal_bars(self, c, induction_x, magnetron_x, base_y, total_bars, recipe_data, extra_bars, seconds_per_bar):
        circle_radius = self.circle_diameter / 2
        bar_height = 1*mm
        bar_spacing = 1*mm
        line_start_x = induction_x - circle_radius
        line_end_x = magnetron_x + circle_radius
        total_width = line_end_x - line_start_x
        
        for i in range(total_bars):
            bar_y = base_y - (i * (bar_height + bar_spacing))
            if i < extra_bars:
                c.setFillColor('#F5F5F5')
                c.setStrokeColor(HexColor('#F5F5F5'))
                c.rect(line_start_x, bar_y, total_width, bar_height, stroke=1, fill=1)
            else:
                c.setFillColor(HexColor('#F5F5F5'))
                c.setStrokeColor(HexColor('#F5F5F5'))
                c.rect(line_start_x, bar_y, total_width, bar_height, stroke=0, fill=1)
        
        # ✅ FIXED: Pass the same base_y coordinate to power bars
        self.draw_colored_power_bars(c, induction_x, magnetron_x, base_y, recipe_data, total_bars, extra_bars, seconds_per_bar)
    def extract_cooking_time(self, recipe_data):
        """Extract cooking time with 3x on2cook time when normal cooking is N/A"""
        total_sec = sum(int(i.get("durationInSec", 0)) for i in recipe_data.get("Instruction", []))
        on2_minutes = total_sec // 60
        on2_seconds = total_sec % 60
        
        # ✅ UPDATED: Apply time formatting rules
        if on2_minutes == 1 and on2_seconds == 0:
            on2 = "On2Cook: 1:00 min"
        else:
            on2 = f"On2Cook: {on2_minutes}:{on2_seconds:02d} mins"
        
        desc = recipe_data.get("description", "")
        match = re.search(r"NORMAL COOKING TIME\s*(\d+)\s*MINUTES", desc.upper())
        
        if match:
            normal_mins = int(match.group(1))
            if normal_mins == 1:
                normal = "Normal Cooking: 1 min"
            else:
                normal = f"Normal Cooking: {normal_mins} mins"
        else:
            # Calculate 3x the on2cook time when normal cooking is N/A
            normal_total_sec = total_sec * 3
            normal_minutes = normal_total_sec // 60
            normal_seconds = normal_total_sec % 60
            
            if normal_minutes == 1 and normal_seconds == 0:
                normal = "Normal Cooking: 1:00 min"
            else:
                normal = f"Normal Cooking: {normal_minutes}:{normal_seconds:02d} mins"
        
        return [f"{on2}    {normal}"]
    
    def extract_output(self, recipe_data):
        """Extract the output (e.g., '400 GM' or '400 g') from the description field."""
        import re
        description = recipe_data.get('description', '').strip()
        print(f"DEBUG: Raw description in extract_output: {description!r}")
        print(f"DEBUG: Description bytes: {description.encode('utf-8')!r}")
        
        # Normalize only spaces and tabs (preserve newlines for line-based capture)
        description = re.sub(r'[ \t]+', ' ', description).strip()
        print(f"DEBUG: Normalized description (spaces/tabs only): {description!r}")
        
        # Remove BOM or other control characters
        description = description.encode('utf-8').decode('utf-8-sig').strip()
        print(f"DEBUG: Cleaned description: {description!r}")
        
        # Match 'OUTPUT' followed by content until newline (preserves line structure)
        match = re.search(r'OUTPUT\s+([^\n\r]+)', description, re.IGNORECASE)
        if match:
            output_value = match.group(1).strip()
            print(f"🔍 Extracted Output from description: {output_value}")
            # Clean units (GM to g) for consistency
            output_value = re.sub(r'\bGM\b', 'g', output_value, flags=re.IGNORECASE)
            print(f"🔍 Final output value after unit cleaning: {output_value}")
            return output_value
        else:
            print("🔍 No OUTPUT found in description, defaulting to 'n/a'")
            print(f"DEBUG: Regex pattern used: r'OUTPUT\s+([^\n\r]+)'")
            return 'n/a'
    def extract_accessories(self, recipe_data):
        description = recipe_data.get('description', '')
        accessories = []
        if 'ACCESSORIES' in description.upper():
            lines = description.split('\n')
            collecting = False
            for line in lines:
                line = line.strip()
                if line.upper() == 'ACCESSORIES':
                    collecting = True
                    continue
                elif collecting and line:
                    if any(keyword in line.upper() for keyword in ['OUTPUT', 'NORMAL', 'COOKING', 'OTHER ESSENTIALS']):
                        break
                    accessories.append(line.title())
        return accessories

    # Units seen in real recipe data (extend here as new units show up)
    _QTY_UNITS = (
        r'gm|g|kg|ml|l|liter|litre|number|no|nos|inch|pinch|'
        r'tsp|tbsp|pcs|pc|strand|strands|string|strings|slice|slices|cup|cups'
    )
    # Equipment/accessory names that sometimes leak into the Ingredients list.
    # Matched as whole words/phrases so "pan" doesn't also catch "Paneer",
    # "stand" doesn't catch "Standard Roux", etc.
    _SKIP_TERMS = ['grill mesh', 'cake mold', 'stirrer', 'pan', 'tray', 'rack', 'stand']
    _SKIP_RE = re.compile(
        r'\b(?:' + '|'.join(re.escape(t) for t in _SKIP_TERMS) + r')\b', re.I
    )

    def extract_ingredients(self, recipe_data):
        qty_token = re.compile(rf'^\d+(?:\.\d+)?(?:{self._QTY_UNITS})$', re.I)

        def squash_qty(tokens):
            out, i = [], 0
            while i < len(tokens):
                if (i + 1 < len(tokens) and
                    re.fullmatch(r'\d+(?:\.\d+)?', tokens[i]) and
                    re.fullmatch(self._QTY_UNITS, tokens[i + 1], re.I)):
                    out.append(tokens[i] + tokens[i + 1])
                    i += 2
                else:
                    out.append(tokens[i])
                    i += 1
            return out

        ingredients = []
        for ing in recipe_data.get('Ingredients', []):
            wt = ing.get('weight', '').strip()
            ttl = ing.get('title', '').strip()
            txt = ing.get('text', '').replace(',', ' ').strip()
            txt = re.sub(r'\([^)]*\)', '', txt).strip()
            print(f"DEBUG: Processing ingredient - weight: '{wt}', title: '{ttl}', text: '{txt}'")
            if self._SKIP_RE.search(ttl):
                continue
            if wt and ttl:
                wt_standardized = re.sub(r'\bgm\b', 'g', wt, flags=re.IGNORECASE)
                ingredients.append(f"{wt_standardized}\t{ttl}")
                print(f"DEBUG: Added main ingredient: '{wt_standardized}\t{ttl}'")
            if not txt:
                continue
            toks = squash_qty(txt.split())
            print(f"DEBUG: Tokens after squash_qty: {toks}")
            prev_qty_at = -1
            pairs = []
            for i, tok in enumerate(toks):
                if qty_token.match(tok):
                    name_tokens = toks[prev_qty_at + 1 : i]
                    if name_tokens:
                        ingredient = ' '.join(name_tokens)
                        qty_fixed = re.sub(r'(?<=\d)(?=[a-zA-Z])',' ', tok)
                        qty_standardized = re.sub(r'\bgm\b', 'g', qty_fixed, flags=re.IGNORECASE)
                        pairs.append(f"{qty_standardized} {ingredient}")
                    prev_qty_at = i
            tail = toks[prev_qty_at + 1 :]
            if tail:
                pairs.append(''.join(tail))
            print(f"DEBUG: Pairs for text: {pairs}")
            line, char_limit = '', 35
            for p in pairs:
                if not line:
                    line = p
                elif len(line) + len(p) + 2 <= char_limit:
                    line += ', ' + p
                else:
                    ingredients.append('  ' + line)
                    print(f"DEBUG: Added sub-ingredient line: '  {line}'")
                    line = p
            if line:
                ingredients.append('  ' + line)
                print(f"DEBUG: Added final sub-ingredient line: '  {line}'")
        print(f"DEBUG: Final ingredients list: {ingredients}")
        return ingredients
    def extract_other_essentials(self, recipe_data):
        """Extract Other Essentials from description field"""
        import re
        
        description = recipe_data.get('description', '')
        other_essentials = []
        
        if 'OTHER ESSENTIALS' in description.upper():
            lines = description.split('\n')
            collecting = False
            
            for line in lines:
                line = line.strip()
                if line.upper() == 'OTHER ESSENTIALS':
                    collecting = True
                    continue
                elif collecting and line:
                    # Stop collecting if we hit another section or empty line
                    if any(keyword in line.upper() for keyword in ['OUTPUT', 'NORMAL', 'ACCESSORIES', 'COOKING']):
                        break
                    
                    # Parse the line to extract quantity and item
                    # Handle formats like "1L PRE-HEATED OIL 180° C" or "1 UNIT BOWL FOR TOSSING"
                    
                    # Try to match quantity at the beginning
                    quantity_match = re.match(r'^(\d+(?:\.\d+)?)\s*([A-Za-z]+)\s+(.+)', line)
                    if quantity_match:
                        quantity = quantity_match.group(1)
                        unit = quantity_match.group(2).lower()
                        item = quantity_match.group(3).title()
                        
                        # Convert "gm" to "g" if present
                        if unit == 'gm':
                            unit = 'g'
                        
                        formatted_line = f"{quantity} {unit}\t{item}"
                        other_essentials.append(formatted_line)
                    else:
                        # If no clear quantity pattern, add as-is but formatted
                        other_essentials.append(line.title())
        
        return other_essentials
    
    def has_stirrer_activity(self, recipe_data):
        """Check if any instruction has stirrer activity"""
        instructions = recipe_data.get('Instruction', [])
        for instruction in instructions:
            stirrer_on = str(instruction.get('stirrer_on', '0')).strip().lower()
            if stirrer_on not in ['0', 'off', '']:
                return True
        return False

    def draw_stirrer_svg(self, c, x, y, svg_path, scale=1.0):
        """Draw SVG file on canvas at specified position"""
        try:
            # Get the directory where this script is located
            script_dir = os.path.dirname(os.path.abspath(__file__))
            full_svg_path = os.path.join(script_dir, svg_path)
            
            if os.path.exists(full_svg_path):
                drawing = svg2rlg(full_svg_path)
                # Scale the drawing
                drawing.width = drawing.minWidth() * scale
                drawing.height = drawing.height * scale
                drawing.scale(scale, scale)
                # Draw it on the canvas
                renderPDF.draw(drawing, c, x, y)
                print(f"✅ Stirrer SVG drawn at ({x/mm:.1f}mm, {y/mm:.1f}mm)")
            else:
                print(f"❌ Stirrer SVG not found at: {full_svg_path}")
        except Exception as e:
            print(f"❌ Error drawing stirrer SVG: {e}")
    def calculate_bar_position_with_rounding(self, time_seconds, seconds_per_bar):
        """Calculate bar position with rounding: >=5 seconds rounds up, <5 rounds down"""
        if time_seconds <= 0:
            return 0
        
        full_bars = time_seconds // seconds_per_bar
        remainder = time_seconds % seconds_per_bar
        
        print(f"DEBUG: {time_seconds}s ÷ {seconds_per_bar} = {full_bars} bars + {remainder}s remainder")
        
        if remainder >= 5:
            result = full_bars + 1
            print(f"DEBUG: {remainder} ≥ 5, rounding UP to {result}")
            return result
        else:
            result = full_bars
            print(f"DEBUG: {remainder} < 5, rounding DOWN to {result}")
            return result


# =========================
# Dropbox + QR helpers
# =========================

def upload_to_dropbox_and_get_direct_url(zip_file_path, token, folder):
    """Uploads the ZIP to Dropbox and returns a direct download URL."""
    if not token:
        raise ValueError("Dropbox token not provided.")
    dbx = dropbox.Dropbox(token)
    try:
        _ = dbx.users_get_current_account()
    except AuthError:
        raise ValueError("Invalid or expired Dropbox token.")
    file_name = os.path.basename(zip_file_path)
    dest_path = f"{folder.rstrip('/')}/{file_name}"
    with open(zip_file_path, 'rb') as f:
        dbx.files_upload(f.read(), dest_path, mode=dropbox.files.WriteMode.overwrite)
    settings = dropbox.sharing.SharedLinkSettings(
        requested_visibility=dropbox.sharing.RequestedVisibility.public
    )
    link_meta = dbx.sharing_create_shared_link_with_settings(dest_path, settings)
    direct_url = link_meta.url.replace('www.dropbox.com', 'dl.dropboxusercontent.com').replace('?dl=0', '')
    return direct_url

def generate_qr_with_center_logo(data_url, logo_path=LOGO_PATH, logo_ratio=LOGO_RATIO):
    """Generates a QR PIL image with a center logo if available."""
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H)
    qr.add_data(data_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color='black', back_color='white').convert('RGB')
    try:
        if os.path.exists(logo_path):
            logo = Image.open(logo_path).convert("RGBA")
            w, h = img.size
            logo_size = (w // logo_ratio, h // logo_ratio)
            logo = logo.resize(logo_size, Image.LANCZOS)
            lw, lh = logo.size
            pos = ((w - lw) // 2, (h - lh) // 2)
            img.paste(logo, pos, mask=logo)
        else:
            print(f"Logo not found at {logo_path}. Generating QR without logo.")
    except Exception as e:
        print(f"Logo paste error: {e}. Generating QR without logo overlay.")
    return img

# =========================
# Main CLI
# =========================

def main():
    import sys
    import glob
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  Single file: python script.py <zip_file_path> [output_pdf_path] [seconds_per_bar] [dropbox_token]")
        print("  Multiple files: python script.py --multiple <zip_pattern_or_directory> <output_directory> [seconds_per_bar] [dropbox_token]")
        print("\nExamples:")
        print("  python script.py recipe1.zip")
        print("  python script.py --multiple 'recipes/*.zip' ./output_pdfs/")
        print("  python script.py --multiple ./recipe_folder/ ./output_pdfs/")
        return
    
    if sys.argv[1] == '--multiple':
        # Multiple file processing - separate PDFs for each zip
        if len(sys.argv) < 4:
            print("❌ Error: --multiple requires <zip_pattern_or_directory> and <output_directory>")
            return
        
        zip_input = sys.argv[2]
        output_directory = sys.argv[3]
        seconds_per_bar = safe_int(sys.argv[4]) if len(sys.argv) > 4 else 9
        dropbox_token = sys.argv[5] if len(sys.argv) > 5 else os.environ.get("DROPBOX_TOKEN", "").strip()
        
        # Find zip files
        zip_files = []
        
        if os.path.isdir(zip_input):
            # If directory provided, find all zip files in it
            zip_files = glob.glob(os.path.join(zip_input, "*.zip"))
        else:
            # If pattern provided, use glob to find matching files
            zip_files = glob.glob(zip_input)
        
        if not zip_files:
            print(f"❌ No zip files found matching: {zip_input}")
            return
        
        print(f"🔍 Found {len(zip_files)} zip files to process:")
        for zip_file in zip_files:
            print(f"   • {os.path.basename(zip_file)}")
        
        # Process all files individually
        try:
            generator = RecipePDFGenerator()
            results = generator.process_multiple_zip_files_individually(
                zip_files, output_directory, seconds_per_bar, dropbox_token
            )
            
            # Final summary
            successful_count = len([r for r in results if r['status'] == 'success'])
            if successful_count > 0:
                print(f"\n🎉 Successfully generated {successful_count} PDF(s) in: {output_directory}")
            else:
                print(f"\n😞 No PDFs were generated successfully")
                
        except Exception as e:
            print(f"❌ Fatal error during processing: {e}")
            import traceback
            traceback.print_exc()
    
    else:
        # Single file processing (your existing code)
        zip_file_path = sys.argv[1]
        output_pdf_path = sys.argv[2] if len(sys.argv) > 2 else "recipe_output.pdf"
        seconds_per_bar = safe_int(sys.argv[3]) if len(sys.argv) > 3 else 9
        dropbox_token = sys.argv[4] if len(sys.argv) > 4 else os.environ.get("DROPBOX_TOKEN", "").strip()
        dropbox_folder = sys.argv[5] if len(sys.argv) > 5 else DB_DEFAULT_FOLDER

        # Your existing single file processing code here...
        qr_img = None
        try:
            direct_url = upload_to_dropbox_and_get_direct_url(zip_file_path, dropbox_token, dropbox_folder)
            qr_img = generate_qr_with_center_logo(direct_url, LOGO_PATH, LOGO_RATIO)
        except Exception as e:
            print(f"Dropbox/QR step warning: {e}. Proceeding to generate PDF without QR.")

        try:
            generator = RecipePDFGenerator(qr_image=qr_img)
            actual_output = generator.process_zip_file(zip_file_path, output_pdf_path, seconds_per_bar)
            print(f"✅ Recipe PDF generated successfully: {actual_output}")
            if os.path.exists(actual_output):
                file_size = os.path.getsize(actual_output)
                print(f"📄 File size: {file_size:,} bytes")
                print(f"📁 Location: {os.path.abspath(actual_output)}")
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()