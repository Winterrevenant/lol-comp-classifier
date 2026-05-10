# src/composition/rules.py
import json
from pathlib import Path
import yaml
from typing import Dict, List, Optional

class CompositionRules:
    """Carga y aplica la taxonomía de composiciones (lol_taxonomy_v2.0.0.json)."""
    
    def __init__(self, config_path: str = "config/settings.yaml"):
        self.config = self._load_config(config_path)
        taxonomy_path = Path(self.config["taxonomy_path"])
        with open(taxonomy_path, 'r', encoding='utf-8') as f:
            self.data = json.load(f)
            
        self.scoring = self.data["scoring_model"]
        self.composition = self.data["composition_rules"]
        self.categories = self.data["categories"]
        self.output_schema = self.data["output_schema"]

    def _load_config(self, config_path: str) -> dict:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)

    @property
    def base_weights(self) -> Dict[str, float]:
        return self.scoring["base_weights"]

    @property
    def flag_multipliers(self) -> Dict:
        return self.scoring["flag_multipliers"]

    @property
    def absolute_threshold(self) -> float:
        return self.composition["absolute_threshold"]["min_score"]

    @property
    def priority_hierarchy(self) -> List[str]:
        return self.composition["priority_hierarchy"]["fallback_if_no_condition"]

    @property
    def hybrid_synergies(self) -> List[Dict]:
        return self.composition["hybrid_synergies"]

    @property
    def hint_tag_rules(self) -> List[Dict]:
        return self.composition["hint_tag_detection"]["rules"]

    @property
    def detection_thresholds(self) -> Dict:
        return self.scoring["detection_thresholds"]

    @property
    def confidence_thresholds(self) -> Dict:
        return self.scoring["confidence"]["thresholds"]

    def get_category_info(self, category_id: str) -> Dict:
        return self.categories.get(category_id, {})

    def get_synergy(self, name: str) -> Optional[Dict]:
        for sname, syn in self.hybrid_synergies.items():
            if sname.lower() == name.lower():
                return syn
        return None

    def is_synergy_applicable(self, synergy: Dict, present_categories: Dict[str, float]) -> bool:
        required = synergy.get("required", [])
        for cat in required:
            if present_categories.get(cat, 0) < self.detection_thresholds["min_for_present"]:
                return False
        for key, min_val in synergy.items():
            if key.startswith("min_"):
                cat = key[4:]
                if present_categories.get(cat, 0) < min_val:
                    return False
        return True

    def evaluate_hint_tags(self, flags_distribution: Dict[str, bool]) -> List[Dict]:
        triggered = []
        for rule in self.hint_tag_rules:
            condition = rule["condition"]
            if self._evaluate_simple_condition(condition, flags_distribution):
                triggered.append(rule)
        return triggered

    def _evaluate_simple_condition(self, condition: str, flags: Dict[str, bool]) -> bool:
        mapping = {
            "is_splitpusher": "is_splitpusher",
            "has_global_ult": "has_global_ult",
            "has_lifedrain": "has_lifedrain"
        }
        for text_key, flag_key in mapping.items():
            if text_key in condition:
                if "== true" in condition:
                    return any(flags.get(flag_key, False) for _ in [1])
        return False