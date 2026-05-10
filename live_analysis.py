# live_analysis.py
import json
import requests
import yaml
import sys
from datetime import datetime
from pathlib import Path
from src.composition.scorer import CompositionScorer

# ------------------------------------------------------------
# 0. PRECARGA DEL MOTOR Y MAPEO DE CAMPEONES
# ------------------------------------------------------------
def inicializar_recursos():
    print("Cargando motor y mapeo de campeones...")
    try:
        # 1. Obtener la version actual de Data Dragon dinamicamente
        v_url = "https://ddragon.leagueoflegends.com/api/versions.json"
        version = requests.get(v_url).json()[0]
        
        # 2. Descargar mapeo con la version correcta
        url_ddragon = f"https://ddragon.leagueoflegends.com/cdn/{version}/data/es_MX/champion.json"
        resp = requests.get(url_ddragon, timeout=5)
        resp.raise_for_status()
        data_dd = resp.json()
        
        mapeo = {}
        for info in data_dd["data"].values():
            # Usamos info["id"] (ej: 'JarvanIV') en lugar de info['name'] ('Jarvan IV')
            # para evitar problemas de espacios en el Scorer.
            mapeo[int(info["key"])] = info["id"]
            
        print(f"Motor listo (Version {version}). {len(mapeo)} campeones mapeados.\n")
        return CompositionScorer(), mapeo
    except Exception as e:
        print(f"Error critico al iniciar: {e}")
        sys.exit(1)

scorer, MAPEO_CAMPEONES = inicializar_recursos()

# ------------------------------------------------------------
# 1. CARGAR CONFIGURACION
# ------------------------------------------------------------
def cargar_secretos():
    secrets_path = Path("config/secrets.yaml")
    if not secrets_path.exists():
        raise FileNotFoundError("No se encontro config/secrets.yaml.")
    with open(secrets_path, "r") as f:
        return yaml.safe_load(f)

try:
    secretos = cargar_secretos()
    API_KEY = secretos["riot_api_key"]
    SUMMONER_NAME = secretos["summoner_name"]
except KeyError as e:
    print(f"Falta una clave en secrets.yaml: {e}")
    sys.exit(1)

PLATAFORMA = "LA1"  # LAN
CLUSTER = "americas"
HEADERS = {"X-Riot-Token": API_KEY}

# ------------------------------------------------------------
# 2. FUNCION DE LOGGING
# ------------------------------------------------------------
def guardar_log(game_data, enemigos, resultado):
    log_entry = {
        "fecha": datetime.now().isoformat(),
        "modo": game_data.get("gameMode", "DESCONOCIDO"),
        "enemigos": enemigos,
        "resultado": {
            "primary_identity": resultado["primary_identity"],
            "confidence": resultado["confidence"],
            "recommended_defense": {k: v for k, v in resultado["recommended_defense"].items() if v},
            "secondary_threats": resultado.get("secondary_threats", []),
            "hint_tags": resultado.get("hint_tags", [])
        }
    }
    
    # Crear carpeta output si no existe
    Path("output").mkdir(exist_ok=True)
    
    with open("output/log_analisis.json", "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    
    print("Log guardado en output/log_analisis.json")

# ------------------------------------------------------------
# 3. OBTENER PARTIDA EN VIVO
# ------------------------------------------------------------
def obtener_partida_en_vivo(full_riot_id):
    if "#" in full_riot_id:
        game_name, tag_line = full_riot_id.split("#", 1)
    else:
        game_name, tag_line = full_riot_id, "LAN"

    # 1. Obtener PUUID (Account-V1)
    url_account = f"https://{CLUSTER}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
    try:
        resp = requests.get(url_account, headers=HEADERS, timeout=5)
        resp.raise_for_status()
        account_data = resp.json()
        puuid = account_data["puuid"]
        print(f"Invocador encontrado: {account_data.get('gameName')}#{account_data.get('tagLine')}")
    except requests.exceptions.RequestException as e:
        print(f"Error al buscar cuenta: {e}")
        return None, None

    # 2. Obtener partida activa (Spectator-V5)
    url_spectator = f"https://{PLATAFORMA}.api.riotgames.com/lol/spectator/v5/active-games/by-summoner/{puuid}"
    try:
        resp = requests.get(url_spectator, headers=HEADERS, timeout=5)
        if resp.status_code == 404:
            return None, puuid  # Jugador existe pero no esta en partida
        resp.raise_for_status()
        return resp.json(), puuid
    except requests.exceptions.RequestException as e:
        print(f"Error al buscar partida: {e}")
        return None, None

# ------------------------------------------------------------
# 4. ANALISIS DE COMPOSICION
# ------------------------------------------------------------
def analizar_enemigos_en_vivo(game_data, puuid_jugador):
    participantes = game_data["participants"]
    
    # Identificar equipo por PUUID
    mi_equipo = next((p["teamId"] for p in participantes if p.get("puuid") == puuid_jugador), None)

    if mi_equipo is None:
        print("Error: No te encontre en la lista de participantes.")
        return

    # Filtrar enemigos y traducir IDs a Nombres
    enemigos = []
    for p in participantes:
        if p["teamId"] != mi_equipo:
            nombre_champ = MAPEO_CAMPEONES.get(p["championId"], f"Unknown_{p['championId']}")
            enemigos.append(nombre_champ)

    if not enemigos:
        print("No se detectaron enemigos (partida de practica?).")
        return

    print(f"Enemigos detectados: {', '.join(enemigos)}")
    print("Analizando composicion...")
    
    # Llamada al motor de clasificacion
    resultado = scorer.classify_composition(enemigos)
    
    # --- Interfaz de resultados ---
    print(f"\n>>> RESULTADO: {resultado['primary_identity']} (Confianza: {resultado['confidence']:.2f})")
    
    if resultado.get("secondary_identity"):
        print(f"   Secundaria: {resultado['secondary_identity']}")
    
    print("\nDEFENSAS RECOMENDADAS:")
    for clave, valor in resultado["recommended_defense"].items():
        if valor:
            print(f"   {clave}")

    if resultado["secondary_threats"]:
        print("\nAMENAZAS INDIVIDUALES:")
        for amenaza in resultado["secondary_threats"]:
            print(f"   - {amenaza['champion']}: {amenaza['advice']}")

    if resultado["hint_tags"]:
        print("\nALERTAS:")
        for tag in resultado["hint_tags"]:
            print(f"   - {tag}")

    print("\nScores por categoria:")
    for cat, score in resultado["scores"].items():
        barra = "|" * int(score * 5)
        print(f"   {cat}: {score:.2f} {barra}")

    # --- GUARDAR LOG ---
    guardar_log(game_data, enemigos, resultado)

    return resultado

# ------------------------------------------------------------
# 5. EJECUCION
# ------------------------------------------------------------
if __name__ == "__main__":
    print(f"Buscando partida para: {SUMMONER_NAME}...")
    partida, puuid = obtener_partida_en_vivo(SUMMONER_NAME)

    if partida:
        analizar_enemigos_en_vivo(partida, puuid)
    elif puuid:
        print("Estado: El usuario existe pero NO esta en partida activa.")
    else:
        print("Estado: No se pudo obtener la informacion del usuario.")