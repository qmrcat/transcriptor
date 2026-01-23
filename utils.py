import json
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# class GestorConfiguracio:
#     @staticmethod
#     def desar_config(dades):
#         with open("config.json", "w", encoding="utf-8") as f:
#             json.dump(dades, f, indent=4)

#     @staticmethod
#     def carregar_config():
#         if os.path.exists("config.json"):
#             with open("config.json", "r", encoding="utf-8") as f:
#                 return json.load(f)
#         return {}

class GestorConfiguracio:
    @staticmethod
    def desar_config(dades):
        with open("config.json", "w", encoding="utf-8") as f:
            json.dump(dades, f, indent=4)

    @staticmethod
    def carregar_config():
        config = {}
        if os.path.exists("config.json"):
            with open("config.json", "r", encoding="utf-8") as f:
                config = json.load(f)
        
        # Incorporem la API Key des del .env si no està al JSON
        if "api_key" not in config:
            config["api_key"] = os.getenv("OPENAI_API_KEY", "")
        
        # Afegim el control del so (per defecte True si no hi és)
        if "enable_sound" not in config:
            config["enable_sound"] = os.getenv("ENABLE_SOUND", "TRUE").upper() == "TRUE"

        print("Configuració carregada:", config)
        
        return config

class CalculadoraCostos:
    def __init__(self):
        self.fitxer_historial = "historial_costos.json"

    def registrar_transaccio(self, model, tokens_in, tokens_out, cost):
        registre = {
            "data": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "model": model,
            "tokens_input": tokens_in,
            "tokens_output": tokens_out,
            "cost_usd": cost
        }
        historial = self.carregar_historial()
        historial.append(registre)
        with open(self.fitxer_historial, "w", encoding="utf-8") as f:
            json.dump(historial, f, indent=4)

    def carregar_historial(self):
        if os.path.exists(self.fitxer_historial):
            with open(self.fitxer_historial, "r", encoding="utf-8") as f:
                return json.load(f)
        return []