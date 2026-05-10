# gameapp.py
import requests
import pandas as pd 
import yaml
import json
from datetime import datetime

from pathlib import Path
from src.composition.scorer import CompositionScorer

# ------------------------------------------------------------
# 1. CARGAR CONFIGURACIÓN SEGURA
# ------------------------------------------------------------
def cargar_api_key():
    """Carga la API Key desde el archivo de secretos."""
    secrets_path = Path("config/secrets.yaml")
    if not secrets_path.exists():
        raise FileNotFoundError(
            "No se encontró config/secrets.yaml. Crea el archivo con la clave 'riot_api_key'."
        )
    with open(secrets_path, "r") as f:
        secrets = yaml.safe_load(f)
    return secrets["riot_api_key"]

API_KEY = cargar_api_key()
BASE_URL = "https://la1.api.riotgames.com"  # Cambia según tu servidor


# ------------------------------------------------------------
# 2. OBTENER PARTIDA (igual que antes)
# ------------------------------------------------------------
def obtener_detalles_partida(match_id):
    url = f"https://americas.api.riotgames.com/lol/match/v5/matches/{match_id}"
    headers = {"X-Riot-Token": API_KEY}
    response = requests.get(url, headers=headers)
    data = response.json()
    if "status" in data:
        print(f"Error {data['status']['status_code']}: {data['status']['message']}")
        return None
    return data


# ------------------------------------------------------------
# 3. EXPORTAR A CSV (tu código original)
# ------------------------------------------------------------
def exportar_partida_a_csv(partida, archivo_objetos="objetos_grieta.csv"):
    if not partida:
        print("No hay datos de partida para exportar.")
        return

    try:
        df_items = pd.read_csv(archivo_objetos)
        diccionario_items = dict(zip(df_items["ID"].astype(int), df_items["Nombre"]))
    except Exception:
        diccionario_items = {}
        print("Aviso: No se encontró el CSV de objetos, se usarán IDs numéricos.")

    info = partida["info"]
    match_id = partida["metadata"]["matchId"]
    participantes = info["participants"]

    lista_filas = []
    for p in participantes:
        items_jugador = []
        for i in range(7):
            item_id = p[f"item{i}"]
            if item_id > 0:
                nombre_item = diccionario_items.get(item_id, f"ID:{item_id}")
                items_jugador.append(nombre_item)

        fila = {
            "Match_ID": match_id,
            "Equipo": "Azul" if p["teamId"] == 100 else "Rojo",
            "Resultado": "Victoria" if p["win"] else "Derrota",
            "Rol": p["individualPosition"],
            "Campeon": p["championName"],
            "Kills": p["kills"],
            "Deaths": p["deaths"],
            "Assists": p["assists"],
            "Oro_Total": p["goldEarned"],
            "Daño_Campeones": p.get("totalDamageDealtToChampions", 0),
            "Items": " | ".join(items_jugador),
        }
        lista_filas.append(fila)

    df_resultado = pd.DataFrame(lista_filas)
    orden_roles = {"TOP": 0, "JUNGLE": 1, "MIDDLE": 2, "BOTTOM": 3, "UTILITY": 4}
    df_resultado["orden"] = df_resultado["Rol"].map(orden_roles)
    df_resultado = df_resultado.sort_values(["Equipo", "orden"]).drop(columns=["orden"])

    nombre_archivo = f"output/analisis_{match_id}.csv"
    df_resultado.to_csv(nombre_archivo, index=False, encoding="utf-8-sig")
    print(f"CSV exportado: {nombre_archivo}")
    return nombre_archivo


# ------------------------------------------------------------
# 4. ANÁLISIS DE COMPOSICIÓN ENEMIGA 
# ------------------------------------------------------------
def analizar_composicion_enemiga(partida, mi_equipo=100):
    """Extrae los campeones del equipo contrario al especificado."""
    if not partida:
        return

    participantes = partida["info"]["participants"]
    enemigos = []
    for p in participantes:
        if p["teamId"] != mi_equipo:   # El otro equipo
            enemigos.append(p["championName"])

    if len(enemigos) != 5:
        print(f"Advertencia: Se esperaban 5 enemigos, pero se encontraron {len(enemigos)}.")
        if len(enemigos) == 0:
            return

    print("\n=== ANÁLISIS DE COMPOSICIÓN ENEMIGA ===")
    print(f"Campeones enemigos: {', '.join(enemigos)}")
    
    # Invocar al scorer
    scorer = CompositionScorer()
    resultado = scorer.classify_composition(enemigos)

    # Guardar en archivo de log
    log_entry = {
        "match_id": partida['metadata']['matchId'],
        "fecha": datetime.now().isoformat(),
        "enemigos": enemigos,
        "resultado": resultado
    }
    with open("output/resultados_pruebas.json", "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

    # Mostrar resultados formateados
    print(f"\nClasificación: {resultado['primary_identity']}")
    if resultado.get("secondary_identity"):
        print(f"Secundaria: {resultado['secondary_identity']}")
    print(f"Confianza: {resultado['confidence_label']} ({resultado['confidence']:.2f})")

    print("\n--- Defensas recomendadas ---")
    for clave, valor in resultado["recommended_defense"].items():
        if valor:
            print(f"   {clave}")

    if resultado["secondary_threats"]:
        print("\n--- Amenazas individuales ---")
        for amenaza in resultado["secondary_threats"]:
            print(f"    {amenaza['champion']}: {amenaza['advice']}")

    if resultado["hint_tags"]:
        print("\n--- Alertas ---")
        for tag in resultado["hint_tags"]:
            print(f"    {tag}")

    print("\n--- Scores por categoría ---")
    for cat, score in resultado["scores"].items():
        print(f"  {cat}: {score:.2f}")

    return resultado


# ------------------------------------------------------------
# 5. BLOQUE PRINCIPAL
# ------------------------------------------------------------
if __name__ == "__main__":
    id_partida = str(input("Ingrese el ID de la partida (sin prefijo): "))
    mi_equipo = int(input("¿En qué equipo estabas? (100 = Azul, 200 = Rojo): "))
    partida = obtener_detalles_partida("LA1_" + id_partida)

    if partida:
        exportar_partida_a_csv(partida)
        analizar_composicion_enemiga(partida, mi_equipo)