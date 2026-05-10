# src/inference/champ_classifier.py
"""
Motor de inferencia: funciones que convierten datos crudos/limpios
en los campos del champion_schema (categorías A-F, flags, etc.).
"""

# ------------------------------------------------------------
# Funciones originales (basadas en stats básicos)
# ------------------------------------------------------------
def infer_is_melee(stats: dict) -> bool:
    """Determina si el campeón es cuerpo a cuerpo por su rango de ataque."""
    rango = stats.get("Rango_Ataque", 175)
    return rango <= 175


def infer_range_score(stats: dict) -> int:
    """Convierte el rango de ataque en un score 0-3."""
    rango = stats.get("Rango_Ataque", 0)
    if rango <= 175:
        return 0
    elif rango <= 500:
        return 1
    elif rango <= 700:
        return 2
    else:
        return 3


def infer_primary_win_condition(categories: list, control_subtype: str, is_melee: bool) -> str:
    """Asigna una condición de victoria primaria según categorías y subtipo de control."""
    cats = ''.join(categories)
    if 'D' in cats and 'A' in cats:
        return 'pick_assassin'
    if 'D' in cats and control_subtype == 'D1':
        return 'cc_lockdown'
    if 'F' in cats and 'C' in cats:
        return 'protect_carry'
    if 'C' in cats and 'B' in cats:
        return 'scale_hypercarry'
    if 'E' in cats:
        return 'poke_siege'
    if control_subtype == 'D1' and is_melee:
        return 'cc_lockdown'
    if control_subtype == 'D2':
        return 'cc_lockdown'
    return 'unknown'


# ------------------------------------------------------------
# Nuevas funciones (basadas en JSON limpios + roles)
# ------------------------------------------------------------
def infer_has_dash_from_limpio(habilidades: dict, stats: dict) -> bool:
    """Determina si un campeón tiene dash a partir de los datos limpios."""
    for hab in habilidades.values():
        nombre = hab.get("nombre", "").lower()
        if any(word in nombre for word in ["dash", "blink", "leap", "jump", "slash"]):
            return True
        extra = hab.get("parametros_extra", {})
        for key in extra.keys():
            if "dash" in key.lower() or "blink" in key.lower():
                return True
    if stats.get("Vel_Movimiento", 0) >= 345 and stats.get("Rango_Ataque", 300) <= 175:
        for hab in habilidades.values():
            if hab.get("rango") and max(hab["rango"]) > 300:
                return True
    return False


def infer_has_lifedrain_from_limpio(habilidades: dict, stats: dict) -> bool:
    """Detecta si un campeón tiene drenaje de vida (lifesteal/spellvamp innato)."""
    for hab in habilidades.values():
        nombre = hab.get("nombre", "").lower()
        extra = hab.get("parametros_extra", {})
        if "vamp" in nombre or "drain" in nombre or "spellvamp" in nombre:
            return True
        for k, v in extra.items():
            if "vamp" in k.lower() or "healamp" in k.lower() or "drain" in k.lower():
                return True
    return False


def infer_can_disengage_from_limpio(habilidades: dict, stats: dict, has_dash: bool) -> bool:
    """Determina si un campeón puede desengancharse (disengage)."""
    if not has_dash:
        return False
    for hab in habilidades.values():
        nombre = hab.get("nombre", "").lower()
        extra = hab.get("parametros_extra", {})
        if "speed" in nombre or "movement" in nombre:
            return True
        if "shield" in str(extra).lower():
            return True
    return True


def infer_control_subtype_from_limpio(habilidades: dict, stats: dict, is_melee: bool):
    """Determina si el control de masas es de iniciación (D1) o peel/zoning (D2)."""
    for hab in habilidades.values():
        nombre = hab.get("nombre", "").lower()
        extra = hab.get("parametros_extra", {})
        for keyword in ["stun", "charm", "fear", "knock", "suppress", "root", "snare", "taunt"]:
            if keyword in nombre:
                rango = hab.get("rango", [0])
                if is_melee and (max(rango) > 300 or "aoe" in nombre):
                    return "D1"
                else:
                    return "D2"
        for k in extra.keys():
            if any(kw in k.lower() for kw in ["stun", "charm", "fear", "knock", "suppress"]):
                rango = hab.get("rango", [0])
                if is_melee and (max(rango) > 300 or "aoe" in nombre):
                    return "D1"
                else:
                    return "D2"
    return None


def infer_mobility_score_from_limpio(habilidades: dict, has_dash: bool) -> int:
    """Calcula el mobility_score basado en habilidades."""
    if not has_dash:
        return 0
    dash_count = 0
    for hab in habilidades.values():
        nombre = hab.get("nombre", "").lower()
        if any(w in nombre for w in ["dash", "blink", "leap"]):
            dash_count += 1
    return min(dash_count, 2)


def infer_categories_from_roles_and_stats(search_tags, secondary_tags, roles,
                                          is_melee, has_dash, has_lifedrain,
                                          control_subtype, habilidades, stats):
    """Combina roles oficiales con mecánicas para inferir categorías A-F."""
    cats = []
    tags = f"{search_tags} {secondary_tags} {roles}".lower()

    if "tank" in tags:
        cats.append("B")
    if "fighter" in tags or "brawler" in tags:
        if "B" not in cats:
            cats.append("B")
    if "assassin" in tags:
        cats.append("A")
    if "mage" in tags:
        max_range = 0
        for hab in habilidades.values():
            rangos = hab.get("rango", [0])
            if rangos:
                max_range = max(max_range, max(rangos))
        if max_range > 700:
            cats.append("E")
        else:
            cats.append("A")
    if "support" in tags:
        tiene_escudo = False
        for hab in habilidades.values():
            nombre = hab.get("nombre", "").lower()
            extra = hab.get("parametros_extra", {})
            if "heal" in nombre or "shield" in nombre or "cure" in nombre:
                tiene_escudo = True
                break
            if any("heal" in k.lower() or "shield" in k.lower() for k in extra.keys()):
                tiene_escudo = True
                break
        if tiene_escudo:
            cats.append("F")
        else:
            if control_subtype:
                cats.append("D")
            else:
                cats.append("F")
    if "marksman" in tags or "attacker" in tags:
        cats.append("C")

    # Ajustes por mecánicas
    if has_lifedrain and is_melee and "B" not in cats:
        cats.append("B")
    if control_subtype and "D" not in cats and "F" not in cats:
        if len(cats) < 2:
            cats.append("D")
    if not cats:
        cats = ["B"]

    return cats[:2]


def infer_damage_type_from_roles_and_stats(search_tags, roles, stats) -> str:
    """Tipo de daño predominante."""
    tags = f"{search_tags} {roles}".lower()
    if "marksman" in tags or "attacker" in tags:
        return "ad_sustained"
    if "mage" in tags or "assassin" in tags:
        if stats.get("Mana", 0) > 0:
            return "ap_burst"
        return "ad_burst"
    if "fighter" in tags or "brawler" in tags:
        return "ad_sustained"
    if "tank" in tags:
        return "ad_sustained"
    return "unknown"


def infer_threat_timing_from_roles(search_tags, roles):
    """Momento del juego en que es más peligroso."""
    tags = f"{search_tags} {roles}".lower()
    if "assassin" in tags or "fighter" in tags:
        return "early"
    if "mage" in tags or "marksman" in tags:
        return "mid"
    if "tank" in tags or "support" in tags:
        return "always"
    return "unknown"