# src/composition/scorer.py
import json
from pathlib import Path
from typing import Dict, List, Tuple
import yaml

from .rules import CompositionRules

class CompositionScorer:
    def __init__(self, mapping_path: str = None, rules: CompositionRules = None):
        self.rules = rules or CompositionRules()
        
        if mapping_path is None:
            with open("config/settings.yaml") as f:
                config = yaml.safe_load(f)
            mapping_path = config.get("mapping_output", "data/processed/champion_mapping.json")
            
        with open(mapping_path, 'r', encoding='utf-8') as f:
            self.champion_map = {c["champion_key"]: c for c in json.load(f)}

    def score_team(self, team_champs: List[str]) -> Tuple[Dict[str, float], Dict[str, bool]]:
        scores = {c: 0.0 for c in "ABCDEF"}
        flags_dist = {
            "has_global_ult": False,
            "has_lifedrain": False,
            "is_splitpusher": False,
            "can_disengage": False
        }
        
        for name in team_champs:
            champ = self._get_champion(name)
            if not champ:
                continue
                
            for cat in champ.get("categories", []):
                base_w = self.rules.base_weights.get(cat, 1.0)
                multiplier = 1.0
                
                flags = champ.get("flags", {})
                if flags.get("has_global_ult"):
                    multiplier *= 1.2
                if flags.get("has_dash"):
                    if cat in ("A", "D"):
                        multiplier *= 1.1
                if champ.get("range_score") == 3 and cat == "E":
                    multiplier *= 1.25
                if flags.get("can_disengage"):
                    if cat == "F":
                        multiplier *= 1.15
                    elif cat == "A":
                        multiplier *= 0.9
                        
                scores[cat] += base_w * multiplier

            for f in flags_dist:
                if champ.get("flags", {}).get(f):
                    flags_dist[f] = True

        return scores, flags_dist

    def classify_composition(self, team_champs: List[str]) -> Dict:
        scores, flags_dist = self.score_team(team_champs)
        
        #  PRIMERO: evaluar sinergias híbridas con is_override = true
        synergy_found = None
        for sname, syn in self.rules.hybrid_synergies.items():
            if isinstance(syn, dict) and syn.get("is_override") and self.rules.is_synergy_applicable(syn, scores):
                synergy_found = sname
                break

        if synergy_found:
            primary = synergy_found
            # Para la confianza, usar los scores de las categorías requeridas por la sinergia
            required_cats = syn.get("required", [])
            synergy_score = sum(scores.get(c, 0) for c in required_cats)
            total = sum(scores.values())
            confidence = synergy_score / total if total > 0 else 0.5
            secondary = max(scores, key=scores.get)
            confidence_label = "Composición clara" if confidence >= 0.75 else "Tendencia identificada"
            is_absolute = False
        else:
            # Buscar todas las categorías que superan el umbral y quedarse con la de mayor score
            candidatas = [(cat, score) for cat, score in scores.items() if score >= self.rules.absolute_threshold]
            if candidatas:
                absolute_cat = max(candidatas, key=lambda x: x[1])[0]
            else:
                absolute_cat = None
            
            if absolute_cat:
                primary = f"Absoluta {absolute_cat}"
                secondary = None
                confidence = 1.0
                confidence_label = "Composición clara"
                is_absolute = True
            else:
                sorted_cats = sorted(scores.items(), key=lambda x: x[1], reverse=True)
                primary_cat = sorted_cats[0][0]
                primary = primary_cat
                secondary = sorted_cats[1][0] if len(sorted_cats) > 1 else None
                
                total = sum(scores.values())
                confidence = sorted_cats[0][1] / total if total > 0 else 0.0
                if confidence >= 0.75:
                    confidence_label = "Composición clara"
                elif confidence >= 0.50:
                    confidence_label = "Tendencia identificada"
                else:
                    confidence_label = "Composición mixta"
                is_absolute = False
        hint_tags = []
        for rule in self.rules.hint_tag_rules:
            condition = rule.get("condition", "")
            if self._evaluate_hint(condition, flags_dist):
                hint_tags.append(rule["tag"])

        if any(self._get_champion(name) and self._get_champion(name).get("control_subtype") == "D1" for name in team_champs):
            hint_tags.append("+InitiationThreat")

        defense = {
            "anti_burst": scores.get("A", 0) >= 1.0,
            "anti_dps": scores.get("C", 0) >= 1.0,
            "anti_cc": scores.get("D", 0) >= 1.0,
            "anti_poke": scores.get("E", 0) >= 1.0,
            "anti_dive": scores.get("A", 0) >= 2.0 and scores.get("D", 0) >= 1.0,
            "focus_carry": "protect_carry" in primary.lower() or "protect_the_carry" in primary.lower(),
            "grievous_wounds_priority": flags_dist.get("has_lifedrain", False)
        }

        result = {
            "primary_identity": primary,
            "secondary_identity": secondary,
            "scores": scores,
            "confidence": round(confidence, 2),
            "confidence_label": confidence_label,
            "tiebreaker_method": None,
            "is_absolute": is_absolute,
            "recommended_defense": defense,
            "secondary_threats": self._build_secondary_threats(team_champs),
            "hint_tags": hint_tags,
            "fed_alert": None
        }
        return result

    def _get_champion(self, name_or_key: str) -> Dict:
        lookup = name_or_key.lower().replace(" ", "").replace("'", "")
        if lookup in self.champion_map:
            return self.champion_map[lookup]
        for champ in self.champion_map.values():
            if champ.get("name", "").lower().replace(" ", "") == lookup:
                return champ
        return None

    def _build_secondary_threats(self, team_champs: List[str]) -> List[Dict]:
        threats = []
        for name in team_champs:
            champ = self._get_champion(name)
            if not champ:
                continue
            cats = champ.get("categories", [])
            if "A" in cats:

                threats.append({
                    "champion": champ["name"],
                    "category": "A",
                    "control_subtype": champ.get("control_subtype"),
                    "advice": "Cuidado con el burst individual."
                })
            elif champ.get("control_subtype") == "D1":
                threats.append({
                    "champion": champ["name"],
                    "category": "D",
                    "control_subtype": "D1",
                    "advice": "Iniciador peligroso. Evita agruparte."
                })
        return threats

    def _evaluate_hint(self, condition: str, flags_dist: Dict[str, bool]) -> bool:
        if "is_splitpusher == true" in condition and flags_dist.get("is_splitpusher"):
            if "has_global_ult" in condition:
                return flags_dist.get("has_global_ult")
            return True
        if "has_lifedrain == true" in condition and flags_dist.get("has_lifedrain"):
            return True
        if "has_global_ult" in condition and "count" not in condition:
            return flags_dist.get("has_global_ult")
        return False


# Test rápido si se ejecuta directamente
if __name__ == "__main__":
    scorer = CompositionScorer()
    test_team = ["Leona", "Zed", "KogMaw", "Ornn", "Lulu"]
    result = scorer.classify_composition(test_team)
    print(json.dumps(result, indent=2))