# src/data_loader/extract_roles.py
"""
Extrae los metadatos de rol (SearchTags, SearchTagsSecondary, Roles)
de los JSON crudos y los guarda en champion_roles.json.
"""
import json
from pathlib import Path
import yaml

from .raw_parser import (
    load_raw_champion,
    extract_character_record,
    find_item_by_key,
)


def load_config():
    config_path = Path('config/settings.yaml')
    if not config_path.exists():
        print("Error: config/settings.yaml no encontrado.")
        return None
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def extract_roles_from_crude(raw_json: dict) -> dict:
    """Extrae los roles de un JSON crudo."""
    char_record = extract_character_record(raw_json)
    if not char_record:
        return {}

    # Buscar CharacterToolData
    tool_data = find_item_by_key(char_record, 'CharacterToolData')
    if not tool_data:
        tool_data = {}
    tool_items = tool_data.get('items', [])

    search_tags = ""
    secondary_tags = ""
    roles = ""

    for item in tool_items:
        if not isinstance(item, dict):
            continue
        key = item.get('key')
        if key == 'SearchTags':
            search_tags = item.get('value', '')
        elif key == 'SearchTagsSecondary':
            secondary_tags = item.get('value', '')
        elif key == 'Roles':
            roles = item.get('value', '')

    return {
        'search_tags': search_tags,
        'secondary_tags': secondary_tags,
        'roles': roles
    }


def main():
    config = load_config()
    if not config:
        return

    raw_dir = Path(config.get('raw_crudes_path', 'data/raw'))
    output_file = Path(config.get('roles_output', 'data/processed/champion_roles.json'))

    if not raw_dir.exists():
        print(f"Error: No se encuentra la carpeta de JSON crudos: {raw_dir}")
        return

    champion_roles = {}
    json_files = sorted(raw_dir.glob('*.json'))

    for filepath in json_files:
        try:
            raw = load_raw_champion(filepath)
            name = None
            char_record = extract_character_record(raw)
            if char_record:
                name = find_item_by_key(char_record, 'mCharacterName')
            if not name:
                name = filepath.stem

            roles_data = extract_roles_from_crude(raw)
            champion_roles[name.lower()] = roles_data
            print(f"Roles extraídos: {name} -> {roles_data['roles']} ({roles_data['search_tags']})")

        except Exception as e:
            print(f"Error procesando {filepath.name}: {e}")

    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(champion_roles, f, indent=2, ensure_ascii=False)

    print(f"\n Roles de {len(champion_roles)} campeones guardados en {output_file}")


if __name__ == "__main__":
    main()