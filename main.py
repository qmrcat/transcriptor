import argparse
import sys
from logic import TranscriptorTiquets, TranscriptorAmbCostos
from gui import InterficieGrafica
import os


def executar_cli(args):
    transcriptor = TranscriptorTiquets(api_key=args.api_key)
    print(f"--- Processant: {args.fitxer} ---")
    
    if args.metode == "ocr":
        resultat = transcriptor.processar_imatge_ocr(args.fitxer, args.idioma)
    elif args.metode == "openai":
        resultat = transcriptor.processar_amb_openai(args.fitxer)
    
    if args.sortida:
        with open(args.sortida, "w", encoding="utf-8") as f:
            f.write(str(resultat))
        print(f"Resultat desat a: {args.sortida}")
    else:
        print(resultat)

def main():
    parser = argparse.ArgumentParser(description="Transcriptor de Tiquets i Factures")
    parser.add_argument("fitxer", nargs="?", help="Ruta al fitxer (imatge o PDF)")
    parser.add_argument("--metode", choices=["ocr", "openai", "ocr-openai"], default="ocr")
    parser.add_argument("--api-key", help="Clau d'OpenAI API")
    parser.add_argument("--idioma", default="cat+spa", help="Idiomes per OCR (ex: cat+spa)")
    parser.add_argument("--sortida", help="Desar resultat en un fitxer JSON")

    args = parser.parse_args()

    if args.fitxer:
        executar_cli(args)
    else:
        # Si no hi ha arguments, obrim la interfície gràfica
        app = InterficieGrafica()
        app.mainloop()

if __name__ == "__main__":
    main()