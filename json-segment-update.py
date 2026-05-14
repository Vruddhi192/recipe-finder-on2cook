import json

# File paths
input_file = 'recipes.json'  # Change this to your input file name
output_file = 'recipes_updated.json'  # Output file name

def to_filename(recipe_name):
    """Convert recipe name to title case with hyphens"""
    words = recipe_name.lower().split()
    title_case_words = [word.capitalize() for word in words]
    return '-'.join(title_case_words)

try:
    # Read the JSON file
    with open(input_file, 'r', encoding='utf-8') as f:
        recipes = json.load(f)
    
    # Update each recipe
    for recipe in recipes:
        if 'Recipe Name' in recipe and recipe['Recipe Name']:
            filename = to_filename(recipe['Recipe Name'])
            recipe['Image'] = f"images/{filename}.png"
            recipe['PopupImage'] = f"popup_images/{recipe['Recipe Name']}.png"
    
    # Write the updated JSON to a new file
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(recipes, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Successfully updated {len(recipes)} recipes!")
    print(f"📁 Output saved to: {output_file}")
    
    # Display a sample of changes
    print('\n📋 Sample of updated recipes:')
    for recipe in recipes[:3]:
        print(f"\n\"{recipe['Recipe Name']}\"")
        print(f"  Image: {recipe['Image']}")
        print(f"  PopupImage: {recipe['PopupImage']}")

except FileNotFoundError:
    print(f"❌ Error: Could not find '{input_file}'")
    print("\nMake sure the input file exists in the same directory")
except json.JSONDecodeError:
    print("❌ Error: Invalid JSON format")
    print("Make sure your JSON file is properly formatted")
except Exception as e:
    print(f"❌ Error: {str(e)}")
    print("\nMake sure:")
    print("1. The input file exists and is named correctly")
    print("2. The JSON is valid")
    print("3. You have read/write permissions")