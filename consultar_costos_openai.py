import json
import os
from datetime import datetime

class ConsultorCostos:
    def __init__(self, fitxer_historial="historial_costos.json"):
        self.fitxer_historial = fitxer_historial
        # Preus per 1M de tokens (Gener 2024 - Referència gpt-4o-mini i gpt-4o)
        self.preus_referencia = {
            "gpt-4o-mini": {"input": 0.15, "output": 0.60},
            "gpt-4o": {"input": 5.00, "output": 15.00}
        }

    def carregar_dades(self):
        if not os.path.exists(self.fitxer_historial):
            return []
        with open(self.fitxer_historial, "r", encoding="utf-8") as f:
            return json.load(f)

    def mostrar_resum_total(self):
        dades = self.carregar_dades()
        if not dades:
            print("\n[!] No hi ha historial de costos disponible.")
            return

        total_usd = sum(item['cost_usd'] for item in dades)
        total_tokens = sum(item['tokens_input'] + item['tokens_output'] for item in dades)
        num_peticions = len(dades)

        print("\n" + "="*40)
        print("📊 RESUM DE COSTOS DE L'ESTACIÓ")
        print("="*40)
        print(f"Peticions totals:  {num_peticions}")
        print(f"Tokens consumits:  {total_tokens:,}")
        print(f"Cost total acumulat: ${total_usd:.4f}")
        print(f"Cost mitjà/tiquet:  ${(total_usd/num_peticions) if num_peticions > 0 else 0:.4f}")
        print("-"*40)

    def comparativa_models(self):
        print("\n🔍 COMPARATIVA DE MODELS (Preu per 1.000 tiquets aprox.)")
        print(f"{'Model':<15} | {'Cost Estimat':<12}")
        print("-" * 30)
        
        # Estimació basada en un tiquet mitjà de 1.000 tokens input / 500 tokens output
        t_in, t_out = 1000, 500
        for model, preus in self.preus_referencia.items():
            cost_1k = ((t_in * preus['input']) + (t_out * preus['output'])) / 1000
            print(f"{model:<15} | ${cost_1k:.3f}")

    def calculadora_pressupost(self):
        print("\n🧮 CALCULADORA DE PRESSUPOST")
        try:
            num_tiquets = int(input("Quants tiquets vols processar? "))
            print(f"\nEstimació per a {num_tiquets} tiquets:")
            for model, preus in self.preus_referencia.items():
                # Estimació conservadora
                cost_est = (((1200 * preus['input']) + (600 * preus['output'])) / 1e6) * num_tiquets
                print(f" > {model}: ${cost_est:.2f}")
        except ValueError:
            print("Entrada no vàlida.")

def menu():
    consultor = ConsultorCostos()
    while True:
        print("\n--- GESTOR DE COSTOS OPENAI ---")
        print("1. Veure historial i despesa real")
        print("2. Comparar preus de models")
        print("3. Calculadora de pressupost (estimació)")
        print("4. Sortir")
        
        opcio = input("\nSelecciona una opció: ")
        
        if opcio == "1":
            consultor.mostrar_resum_total()
        elif opcio == "2":
            consultor.comparativa_models()
        elif opcio == "3":
            consultor.calculadora_pressupost()
        elif opcio == "4":
            break
        else:
            print("Opció no vàlida.")

if __name__ == "__main__":
    menu()