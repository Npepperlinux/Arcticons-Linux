#!/usr/bin/python3
import argparse
import yaml
import zipfile
from pathlib import Path
from configparser import ConfigParser
from collections import defaultdict

# Mapping of Icon Contexts to folder names
ICON_TYPES = {
    "Actions": "actions",
    "Application": "apps",
    "Applications": "apps",
    "Categories": "categories",
    "Devices": "devices",
    "Emblems": "emblems",
    "Emotes": "emotes",
    "MimeTypes": "mimetypes",
    "Places": "places",
    "Status": "status",
    "Preferences": "preferences",
}

def get_icon_directories():
    """Finds all valid icon directories using theme metadata and hicolor fallback."""
    theme_files = {
        *set(Path("/usr/share/icons").glob("*/index.theme")),
        *set(Path("~/.local/share/icons").expanduser().glob("*/index.theme")),
    }
    
    valid_dirs = []
    for theme_file in theme_files:
        theme_file_config = ConfigParser()
        try:
            if str(theme_file) not in theme_file_config.read(theme_file):
                continue
            if "Icon Theme" not in theme_file_config or "Directories" not in theme_file_config["Icon Theme"]:
                continue

            for directory in theme_file_config["Icon Theme"]["Directories"].split(","):
                dir_path = theme_file.parent / directory
                if (dir_path.is_dir() and directory in theme_file_config 
                    and "Context" in theme_file_config[directory]):
                    ctx = theme_file_config[directory]["Context"]
                    if ctx in ICON_TYPES:
                        # Store theme_root, subdir, and context_name
                        valid_dirs.append((theme_file.parent, Path(directory), ICON_TYPES[ctx]))
        except Exception:
            continue

    # Hicolor fallback
    hicolor_path = Path("/usr/share/icons/hicolor")
    if hicolor_path.exists():
        for folder in hicolor_path.glob("*/*"):
            if folder.is_dir() and folder.name in ICON_TYPES.values():
                valid_dirs.append((hicolor_path, folder.relative_to(hicolor_path), folder.name))

    return valid_dirs

def create_comprehensive_bundle(yaml_path: str, output_zip: str):
    # 1. Load existing mappings
    try:
        with open(yaml_path, 'r') as f:
            already_mapped_data = yaml.safe_load(f) or {}
    except FileNotFoundError:
        already_mapped_data = {}
    
    existing_mappings = set()
    for icons in already_mapped_data.values():
        if isinstance(icons, list):
            existing_mappings.update(icons)

    # 2. Index all icons
    print("Indexing all system icons...")
    # Map: mapping_str -> list of (physical_file_path, theme_name, sub_path)
    system_database = defaultdict(list)
    for theme_root, sub_dir, context_name in get_icon_directories():
        actual_dir = theme_root / sub_dir
        for icon_file in actual_dir.glob("*.*"):
            if icon_file.suffix in ['.svg', '.png']:
                mapping_str = f"{context_name}/{icon_file.stem}"
                if mapping_str.endswith("-symbolic"):
                    mapping_str = mapping_str.removesuffix("-symbolic")
                
                system_database[mapping_str].append((icon_file, theme_root.name, sub_dir))

    # 3. Filter for missing
    missing_mappings = {k: v for k, v in system_database.items() if k not in existing_mappings}
    print(f"Found {len(missing_mappings)} missing mappings.")

    # 4. ZIP everything up
    with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
        new_yaml_entries = defaultdict(list)

        for map_str, variants in sorted(missing_mappings.items()):
            context, icon_name = map_str.split('/', 1)
            new_yaml_entries[icon_name].append(map_str)

            for icon_file, theme_name, sub_dir in variants:
                # Zip path: context/icon_name/ThemeName/SubDir_FileName
                # Replacing slashes in sub_dir to keep the zip structure clean but unique
                unique_sub = str(sub_dir).replace('/', '_')
                zip_path = f"{context}/{icon_name}/{theme_name}/{unique_sub}_{icon_file.name}"
                
                zipf.write(icon_file, arcname=zip_path)

        # 5. Add the YAML snippet
        yaml_content = yaml.dump(dict(new_yaml_entries), default_flow_style=False)
        zipf.writestr("missing_mappings_snippet.yaml", yaml_content)

    print(f"Done! Created bundle: {output_zip}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("yaml_path", help="Path to your existing mappings.yaml")
    parser.add_argument("-o", "--output", default="unmapped_system_icons.zip", help="Output filename")
    args = parser.parse_args()
    create_comprehensive_bundle(args.yaml_path, args.output)