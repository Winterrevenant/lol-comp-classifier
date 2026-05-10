import requests
import yaml
import sys
from pathlib import Path

# ------------------------------------------------------------
# 1. CARGAR CONFIGURACION SEGURA
# ------------------------------------------------------------
def cargar_secretos():
    secrets_path = Path("config/secrets.yaml")
    if not secrets_path.exists():
        raise FileNotFoundError("No se encontro config/secrets.yaml.")
    with open(secrets_path, "r") as f:
        return yaml.safe_load(f)
    
# --- CONFIGURACIÓN ---
secretos = cargar_secretos()

API_KEY = secretos["riot_api_key"]  
GAME_NAME = "Winter MainOveja"        # Sin el tag
TAG_LINE = "LAN"           # El código después del #
REGION = "la1"               # Ejemplo: la1, la2, na1, euw1
CLUSTER = "americas"         # Ejemplo: americas, europe, asia
PUUID = "7PRbTaDNbjF-DGvPVpDA4vhtIytufneeSfdengRkt4P6SmnMOaoyG0gXBGQxv0fBo1rLJ96Q3-sSYQ"
def check_live_game():

    headers = {"X-Riot-Token": API_KEY}
    url = f"https://{REGION}.api.riotgames.com/lol/spectator/v5/active-games/by-summoner/{PUUID}"
    
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        game_data = response.json()
        print(f"¡Estás en partida! 🎮")
        print(f"Modo de juego: {game_data['gameMode']}")
        print(f"Tiempo transcurrido: {game_data['gameLength']} segundos")
        
        print("\n--- Jugadores en la partida ---")
        for player in game_data['participants']:
            # Aquí puedes ver quién es quién
            equipo = "Azul" if player['teamId'] == 100 else "Rojo"
            print(f"[{equipo}] {player['riotId']} - Campeón ID: {player['championId']}")
            
    elif response.status_code == 404:
        print("El jugador no está actualmente en una partida activa.")
    elif response.status_code == 403:
        print("Error 403: Tu API Key expiró. Renuévala en el portal de Riot.")
    else:
        print(f"Error inesperado: {response.status_code}")
        print(response.json())

if __name__ == "__main__":
    check_live_game()