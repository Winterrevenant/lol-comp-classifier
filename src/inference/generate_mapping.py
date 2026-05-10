# src/inference/generate_mapping.py
"""
Genera champion_mapping.json combinando:
- JSON limpios (estadísticas y habilidades)
- Roles oficiales extraídos de los JSON crudos
"""
import json
from pathlib import Path
import yaml

from .champ_classifier import (
    infer_is_melee,
    infer_range_score,
    infer_has_dash_from_limpio,
    infer_has_lifedrain_from_limpio,
    infer_can_disengage_from_limpio,
    infer_control_subtype_from_limpio,
    infer_mobility_score_from_limpio,
    infer_categories_from_roles_and_stats,
    infer_damage_type_from_roles_and_stats,
    infer_threat_timing_from_roles,
    infer_primary_win_condition,
)
from ..data_loader.raw_parser import find_item_by_key  # Solo necesitamos esta utilidad


def load_config():
    config_path = Path('config/settings.yaml')
    if not config_path.exists():
        print("Error: config/settings.yaml no encontrado.")
        return None
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def load_champion_roles(roles_path: Path) -> dict:
    """Carga el mapeo de roles (champion_name -> roles)."""
    if not roles_path.exists():
        print(f"Advertencia: No se encontró {roles_path}. Se usarán roles vacíos.")
        return {}
    with open(roles_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_limpio(limpio_path: Path) -> dict:
    """Carga un JSON limpio de campeón."""
    with open(limpio_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def process_champion(limpio: dict, roles_data: dict) -> dict:
    """Procesa un campeón a partir de sus datos limpios y roles oficiales."""
    name = limpio.get("nombre", "unknown")
    key = name.lower().replace(" ", "").replace("'", "")
    
    stats = limpio.get("stats_base", {})
    habilidades = limpio.get("habilidades", {})

    # Usar roles oficiales si existen, si no, diccionario vacío
    roles = roles_data.get(name.lower(), {})
    search_tags = roles.get("search_tags", "")
    secondary_tags = roles.get("secondary_tags", "")
    riot_roles = roles.get("roles", "")

    # ---------- Inferencias a partir de stats y habilidades ----------
    is_melee = infer_is_melee(stats)
    range_score = infer_range_score(stats)
    has_dash = infer_has_dash_from_limpio(habilidades, stats)
    has_lifedrain = infer_has_lifedrain_from_limpio(habilidades, stats)
    can_disengage = infer_can_disengage_from_limpio(habilidades, stats, has_dash)
    control_subtype = infer_control_subtype_from_limpio(habilidades, stats, is_melee)
    mobility_score = infer_mobility_score_from_limpio(habilidades, has_dash)
    is_splitpusher = False  # Se puede refinar después

    # Categorías A-F (usando roles oficiales + mecánicas)
    categories = infer_categories_from_roles_and_stats(
        search_tags, secondary_tags, riot_roles,
        is_melee, has_dash, has_lifedrain, control_subtype,
        habilidades, stats
    )

    damage_type = infer_damage_type_from_roles_and_stats(
        search_tags, riot_roles, stats
    )
    threat_timing = infer_threat_timing_from_roles(search_tags, riot_roles)
    primary_win_condition = infer_primary_win_condition(categories, control_subtype, is_melee)

    return {
        "name": name,
        "champion_key": key,
        "categories": categories,
        "control_subtype": control_subtype,
        "flags": {
            "is_melee": is_melee,
            "has_dash": has_dash,
            "has_global_ult": False,  # Se podría inferir con más análisis
            "is_splitpusher": is_splitpusher,
            "can_disengage": can_disengage,
            "has_lifedrain": has_lifedrain
        },
        "range_score": range_score,
        "mobility_score": mobility_score,
        "damage_type": damage_type,
        "threat_timing": threat_timing,
        "primary_win_condition": primary_win_condition,
        "last_review_patch": "15.9"
    }


def main():
    config = load_config()
    if not config:
        return

    limpios_dir = Path(config.get("limpios_path", "data/processed/json_limpios"))
    roles_file = Path(config.get("roles_output", "data/processed/champion_roles.json"))
    output_file = Path(config.get("mapping_output", "data/processed/champion_mapping.json"))

    if not limpios_dir.exists():
        print(f"Error: No se encuentra la carpeta de JSON limpios: {limpios_dir}")
        return

    champion_roles = load_champion_roles(roles_file)
    champion_mapping = []

    json_files = sorted(limpios_dir.glob("*.json"))
    for filepath in json_files:
        try:
            limpio = load_limpio(filepath)
            champ_data = process_champion(limpio, champion_roles)
            champion_mapping.append(champ_data)
            print(f"Procesado: {champ_data['name']} -> {champ_data['categories']}")
        except Exception as e:
            print(f"Error procesando {filepath.name}: {e}")
            import traceback
            traceback.print_exc()

    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(champion_mapping, f, indent=2, ensure_ascii=False)

    print(f"\nchampion_mapping.json generado con {len(champion_mapping)} campeones.")


if __name__ == "__main__":
    main()