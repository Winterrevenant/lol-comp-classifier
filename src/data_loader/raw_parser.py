# src/data_loader/raw_parser.py
import json
from pathlib import Path

def load_raw_champion(path: Path) -> dict:
    """Carga un JSON crudo de campeón desde la ruta dada."""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def safe_get(data, *keys, default=None):
    """Navega un diccionario anidado de forma segura."""
    for key in keys:
        if isinstance(data, dict):
            data = data.get(key, {})
        else:
            return default
    return data

def find_item_by_key(items, key_name):
    """Busca un ítem en una lista de objetos con clave 'key'."""
    if not isinstance(items, list):
        return None
    for item in items:
        if not isinstance(item, dict):
            continue
        item_key = item.get('key')
        if item_key == key_name or str(item_key) == str(key_name):
            return item.get('value', {})
    return None

def extract_character_record(raw_json: dict) -> list:
    entries = raw_json.get('entries', {}).get('value', {}).get('items', [])
    for entry in entries:
        key = entry.get('key', '')
        if isinstance(key, str) and 'CharacterRecords/Root' in key:
            return entry.get('value', {}).get('items', [])
    return []

def extract_spells(raw_json: dict) -> list:
    entries = raw_json.get('entries', {}).get('value', {}).get('items', [])
    spells = []
    for entry in entries:
        key = entry.get('key', '')
        if isinstance(key, str) and '/Spells/' in key and 'Ability' in key:
            spells.append(entry.get('value', {}).get('items', []))
    return spells

def get_spell_data_resource(spell: list) -> dict:
    """Extrae el SpellDataResource de una habilidad."""
    for item in spell:
        if item.get('key') == 'mSpell' and item.get('type') == 'pointer':
            return item.get('value', {}).get('items', [])
    return {}

def find_data_values(spell_resource: list) -> dict:
    """Busca DataValues en un SpellDataResource."""
    data_values = find_item_by_key(spell_resource, 'DataValues')
    return data_values.get('items', []) if data_values else []

def find_effect_amount(spell_resource: list) -> dict:
    """Busca mEffectAmount en un SpellDataResource."""
    effect_amount = find_item_by_key(spell_resource, 'mEffectAmount')
    return effect_amount.get('items', []) if effect_amount else []

def find_cast_range(spell_resource: list):
    """Busca CastRange en un SpellDataResource."""
    cast_range = find_item_by_key(spell_resource, 'CastRange')
    return cast_range.get('items', []) if cast_range else []

def find_spell_tags(spell_resource: list) -> list:
    """Busca mSpellTags en un SpellDataResource."""
    tags = find_item_by_key(spell_resource, 'mSpellTags')
    return tags.get('items', []) if tags else []

def find_field(spell_resource: list, field_name: str):
    """Busca un campo por nombre en el SpellDataResource (ej. 'CannotBeSuppressed')."""
    return find_item_by_key(spell_resource, field_name)