import os
import json
from logic import TranscriptorAmbCostos
from utils import GestorConfiguracio

def processar_directori(ruta_entrada, ruta_sortida="resultats_comptabilitat"):
    """
    Processa tots els tiquets d'una carpeta i desa els resultats estructurats.
    """
    # 1. Configuració inicial
    config = GestorConfiguracio.carregar_config()
    api_key = config.get("api_key")
    
    if not api_key:
        print("❌ Error: No s'ha trobat cap API Key al fitxer de configuració o .env")
        return

    transcriptor = TranscriptorAmbCostos(api_key=api_key)
    
    # Crea la carpeta de sortida si no existeix
    if not os.path.exists(ruta_sortida):
        os.makedirs(ruta_sortida)

    print(f"🚀 Iniciant processament per lots a: {ruta_entrada}")
    print("-" * 50)

    extensions_suportades = ('.jpg', '.jpeg', '.png', '.webp', '.pdf')
    fitxers = [f for f in os.listdir(ruta_entrada) if f.lower().endswith(extensions_suportades)]

    resultats_totals = []

    for fitxer in fitxers:
        ruta_completa = os.path.join(ruta_entrada, fitxer)
        print(f"📄 Processant: {fitxer}...", end="\r")
        
        try:
            # Utilitzem OpenAI Vision per a l'automatització per la seva precisió
            dades = transcriptor.processar_amb_openai(ruta_completa)
            
            if "error" not in dades:
                # Afegim el nom del fitxer original al JSON per traçabilitat
                dades["fitxer_original"] = fitxer
                resultats_totals.append(dades)
                
                # Desem cada tiquet individualment en JSON
                nom_json = os.path.splitext(fitxer)[0] + ".json"
                with open(os.path.join(ruta_sortida, nom_json), "w", encoding="utf-8") as f:
                    json.dump(dades, f, indent=4, ensure_ascii=False)
            else:
                print(f"⚠️ Error en {fitxer}: {dades['error']}")

        except Exception as e:
            print(f"❌ Error crític en {fitxer}: {str(e)}")

    # 2. Resum final en un sol fitxer per facilitar la importació a Excel/ERP
    resum_final = os.path.join(ruta_sortida, "resum_total.json")
    with open(resum_final, "w", encoding="utf-8") as f:
        json.dump(resultats_totals, f, indent=4, ensure_ascii=False)

    print("-" * 50)
    print(f"✅ Procés finalitzat!")
    print(f"📁 Tiquets processats: {len(resultats_totals)}")
    print(f"📂 Resultats desats a la carpeta: '{ruta_sortida}'")

if __name__ == "__main__":
    # EXEMPLE D'ÚS: 
    # 1. Crea una carpeta anomenada 'factures_gener'
    # 2. Posa-hi alguns tiquets
    # 3. Executa aquest script
    
    # Pots canviar 'factures_pendents' per la teva carpeta real
    carpeta_test = "factures_pendents"
    
    if not os.path.exists(carpeta_test):
        os.makedirs(carpeta_test)
        print(f"ℹ️ S'ha creat la carpeta '{carpeta_test}'. Posa-hi imatges i torna a executar.")
    else:
        processar_directori(carpeta_test)