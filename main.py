import argparse
import sys
import os
import json
from utils import GestorLogging
from services.transcription_service import TranscriptionService

# Inicialitzar logging abans que res
GestorLogging.configurar()
logger = GestorLogging.obtenir_logger("main")

from gui import InterficieGrafica


def executar_cli(args):
    logger.info(f"Mode CLI - Processant: {args.fitxer}")
    logger.debug(f"Paràmetres: metode={args.metode}, idioma={args.idioma}")

    transcripcio_service = TranscriptionService(api_key=args.api_key, usar_costos=False)
    print(f"--- Processant: {args.fitxer} ---")

    try:
        resultat = transcripcio_service.processar(
            metode=args.metode,
            ruta_fitxer=args.fitxer,
            idioma=args.idioma
        )

        if args.sortida:
            with open(args.sortida, "w", encoding="utf-8") as f:
                if isinstance(resultat, (dict, list)):
                    json.dump(resultat, f, ensure_ascii=False, indent=2)
                else:
                    f.write(str(resultat))
            logger.info(f"Resultat desat a: {args.sortida}")
            print(f"Resultat desat a: {args.sortida}")
        else:
            print(resultat)

        logger.info("Processament CLI completat")

    except Exception as e:
        logger.error(f"Error en processament CLI: {e}", exc_info=True)
        print(f"Error: {e}")
        sys.exit(1)


def mostrar_metriques():
    """Mostra les mètriques del sistema de logging."""
    metriques = GestorLogging.obtenir_metriques()

    print("\n" + "=" * 60)
    print("  METRIQUES DEL SISTEMA DE LOGGING")
    print("=" * 60)

    print(f"\n[*] Total d'events registrats: {metriques['total_events']}")

    print("\n[+] Events per nivell:")
    for nivell, count in metriques['per_nivell'].items():
        barra = "#" * min(count, 50)
        print(f"   {nivell:<10} {count:>5}  {barra}")

    if metriques['errors_per_modul']:
        print("\n[!] Errors per modul:")
        for modul, count in sorted(metriques['errors_per_modul'].items(), key=lambda x: -x[1]):
            print(f"   {modul:<30} {count:>5} errors")

    if metriques['rendiment']:
        print("\n[T] Rendiment d'operacions:")
        for op, stats in metriques['rendiment'].items():
            print(f"   {op}:")
            print(f"      Mitjana: {stats['mitjana_ms']:.2f}ms")
            print(f"      Minim:  {stats['minim_ms']:.2f}ms")
            print(f"      Maxim:  {stats['maxim_ms']:.2f}ms")
            print(f"      Execucions: {stats['total_execucions']}")

    print("\n" + "=" * 60)


def mostrar_logs_recents(num_linies=50):
    """Mostra les ultimes linies del fitxer de log."""
    fitxer_log = os.path.join(GestorLogging._directori_logs, "transcriptor.log")

    if not os.path.exists(fitxer_log):
        print("No hi ha fitxer de log disponible.")
        return

    print(f"\n[LOG] Ultimes {num_linies} linies de {fitxer_log}:\n")
    print("-" * 80)

    try:
        with open(fitxer_log, 'r', encoding='utf-8') as f:
            linies = f.readlines()
            for linia in linies[-num_linies:]:
                # Afegir color segons el nivell (si la consola ho suporta)
                try:
                    if "ERROR" in linia or "CRITICAL" in linia:
                        print(f"\033[31m{linia.rstrip()}\033[0m")
                    elif "WARNING" in linia:
                        print(f"\033[33m{linia.rstrip()}\033[0m")
                    elif "DEBUG" in linia:
                        print(f"\033[90m{linia.rstrip()}\033[0m")
                    else:
                        print(linia.rstrip())
                except UnicodeEncodeError:
                    # Fallback sense colors si hi ha problemes d'encoding
                    print(linia.rstrip().encode('ascii', 'replace').decode())
    except Exception as e:
        print(f"Error llegint el fitxer de log: {e}")

    print("-" * 80)


def main():
    parser = argparse.ArgumentParser(description="Transcriptor de Tiquets i Factures")
    parser.add_argument("fitxer", nargs="?", help="Ruta al fitxer (imatge o PDF)")
    parser.add_argument("--metode", choices=["ocr", "openai", "ocr-openai"], default="ocr")
    parser.add_argument("--api-key", help="Clau d'OpenAI API")
    parser.add_argument("--idioma", default="cat+spa", help="Idiomes per OCR (ex: cat+spa)")
    parser.add_argument("--sortida", help="Desar resultat en un fitxer JSON")
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], help="Nivell de logging")
    parser.add_argument("--metriques", action="store_true", help="Mostra mètriques del sistema de logging")
    parser.add_argument("--logs", nargs="?", type=int, const=50, metavar="N",
                        help="Mostra les últimes N línies del log (per defecte 50)")

    args = parser.parse_args()

    # Reconfigurar logging si s'especifica nivell
    if args.log_level:
        GestorLogging._inicialitzat = False
        GestorLogging.configurar(nivell=args.log_level)

    # Mostrar mètriques si es demana
    if args.metriques:
        mostrar_metriques()
        return

    # Mostrar logs recents si es demana
    if args.logs is not None:
        mostrar_logs_recents(args.logs)
        return

    logger.info("Transcriptor de Tiquets iniciat")

    if args.fitxer:
        executar_cli(args)
    else:
        # Si no hi ha arguments, obrim la interfície gràfica
        logger.info("Iniciant mode GUI")
        try:
            app = InterficieGrafica()
            app.mainloop()
            logger.info("Aplicació tancada correctament")
        except Exception as e:
            logger.critical(f"Error crític en GUI: {e}", exc_info=True)
            raise


if __name__ == "__main__":
    main()
