import json
import os
import sys
import gzip
import shutil
import logging
import functools
import time
import threading
import sqlite3
from logging.handlers import RotatingFileHandler
from datetime import datetime
from contextlib import contextmanager
from dotenv import load_dotenv

load_dotenv()


# =============================================================================
# SISTEMA DE LOGGING CENTRALITZAT
# =============================================================================

class FormatterAmbColors(logging.Formatter):
    """Formatter que afegeix colors ANSI als logs de consola."""

    # Codis de color ANSI
    COLORS = {
        'DEBUG': '\033[36m',     # Cian
        'INFO': '\033[32m',      # Verd
        'WARNING': '\033[33m',   # Groc
        'ERROR': '\033[31m',     # Vermell
        'CRITICAL': '\033[41m',  # Fons vermell
    }
    RESET = '\033[0m'
    GRIS = '\033[90m'

    def __init__(self, format_str, datefmt=None, usar_colors=True):
        super().__init__(format_str, datefmt)
        self.usar_colors = usar_colors and sys.stdout.isatty()

    def format(self, record):
        if self.usar_colors:
            color = self.COLORS.get(record.levelname, '')
            record.levelname = f"{color}{record.levelname:<8}{self.RESET}"
            record.name = f"{self.GRIS}{record.name}{self.RESET}"
        return super().format(record)


class FormatterJSON(logging.Formatter):
    """Formatter que genera logs en format JSON estructurat."""

    def format(self, record):
        log_obj = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "nivell": record.levelname,
            "modul": record.name,
            "missatge": record.getMessage(),
            "fitxer": record.filename,
            "linia": record.lineno,
        }

        if record.exc_info:
            log_obj["excepcio"] = self.formatException(record.exc_info)

        # Afegir camps extra si existeixen
        if hasattr(record, 'durada'):
            log_obj["durada_ms"] = record.durada
        if hasattr(record, 'operacio'):
            log_obj["operacio"] = record.operacio

        return json.dumps(log_obj, ensure_ascii=False)


class FiltreMòduls(logging.Filter):
    """Filtra logs segons el mòdul d'origen."""

    def __init__(self, moduls_permesos=None, moduls_exclosos=None):
        super().__init__()
        self.moduls_permesos = moduls_permesos or []
        self.moduls_exclosos = moduls_exclosos or []

    def filter(self, record):
        # Si hi ha mòduls exclosos, filtrar-los
        for modul in self.moduls_exclosos:
            if record.name.startswith(modul):
                return False

        # Si hi ha mòduls permesos, només permetre'ls
        if self.moduls_permesos:
            for modul in self.moduls_permesos:
                if record.name.startswith(modul):
                    return True
            return False

        return True


class RotatingFileHandlerAmbCompressio(RotatingFileHandler):
    """Handler amb rotació que comprimeix els fitxers antics."""

    def __init__(self, *args, comprimir=True, **kwargs):
        self.comprimir = comprimir
        super().__init__(*args, **kwargs)

    def doRollover(self):
        super().doRollover()

        if self.comprimir:
            # Comprimir el fitxer rotat més antic
            for i in range(self.backupCount, 0, -1):
                fitxer_rotat = f"{self.baseFilename}.{i}"
                fitxer_gz = f"{fitxer_rotat}.gz"

                if os.path.exists(fitxer_rotat) and not os.path.exists(fitxer_gz):
                    try:
                        with open(fitxer_rotat, 'rb') as f_in:
                            with gzip.open(fitxer_gz, 'wb') as f_out:
                                shutil.copyfileobj(f_in, f_out)
                        os.remove(fitxer_rotat)
                    except Exception:
                        pass  # Si falla la compressió, mantenim el fitxer original


class MetriquesLogging:
    """Recull mètriques i estadístiques dels logs."""

    def __init__(self):
        self._comptadors = {
            'DEBUG': 0,
            'INFO': 0,
            'WARNING': 0,
            'ERROR': 0,
            'CRITICAL': 0
        }
        self._errors_per_modul = {}
        self._temps_operacions = {}
        self._lock = threading.Lock()

    def registrar_event(self, nivell, modul=None):
        with self._lock:
            if nivell in self._comptadors:
                self._comptadors[nivell] += 1

            if nivell in ('ERROR', 'CRITICAL') and modul:
                self._errors_per_modul[modul] = self._errors_per_modul.get(modul, 0) + 1

    def registrar_temps(self, operacio, durada_ms):
        with self._lock:
            if operacio not in self._temps_operacions:
                self._temps_operacions[operacio] = []
            self._temps_operacions[operacio].append(durada_ms)

    def obtenir_resum(self):
        with self._lock:
            resum = {
                "total_events": sum(self._comptadors.values()),
                "per_nivell": dict(self._comptadors),
                "errors_per_modul": dict(self._errors_per_modul),
            }

            # Calcular mitjanes de temps
            temps_mitjans = {}
            for op, temps in self._temps_operacions.items():
                if temps:
                    temps_mitjans[op] = {
                        "mitjana_ms": sum(temps) / len(temps),
                        "minim_ms": min(temps),
                        "maxim_ms": max(temps),
                        "total_execucions": len(temps)
                    }
            resum["rendiment"] = temps_mitjans

            return resum

    def reiniciar(self):
        with self._lock:
            for key in self._comptadors:
                self._comptadors[key] = 0
            self._errors_per_modul.clear()
            self._temps_operacions.clear()


class HandlerMetriques(logging.Handler):
    """Handler que registra mètriques de cada log."""

    def __init__(self, metriques):
        super().__init__()
        self.metriques = metriques

    def emit(self, record):
        self.metriques.registrar_event(record.levelname, record.name)


class GestorLogging:
    """Gestiona la configuració centralitzada del logging per a tota l'aplicació."""

    _inicialitzat = False
    _directori_logs = "logs"
    _metriques = MetriquesLogging()

    @classmethod
    def configurar(cls, nivell=None, directori_logs=None, usar_colors=None,
                   format_json=None, comprimir_rotats=None):
        """
        Configura el sistema de logging per a tota l'aplicació.

        Args:
            nivell: Nivell de logging (DEBUG, INFO, WARNING, ERROR). Per defecte INFO.
            directori_logs: Directori on guardar els fitxers de log.
            usar_colors: Activar colors a la consola (per defecte True).
            format_json: Generar logs JSON a fitxer separat (per defecte False).
            comprimir_rotats: Comprimir fitxers rotats amb gzip (per defecte True).
        """
        if cls._inicialitzat:
            return

        # Configuració des de variables d'entorn
        nivell = nivell or os.getenv("LOG_LEVEL", "INFO").upper()
        cls._directori_logs = directori_logs or os.getenv("LOG_DIR", "logs")
        usar_colors = usar_colors if usar_colors is not None else os.getenv("LOG_COLORS", "TRUE").upper() == "TRUE"
        format_json = format_json if format_json is not None else os.getenv("LOG_JSON", "FALSE").upper() == "TRUE"
        comprimir_rotats = comprimir_rotats if comprimir_rotats is not None else os.getenv("LOG_COMPRESS", "TRUE").upper() == "TRUE"

        # Mòduls a filtrar (opcional)
        moduls_exclosos = os.getenv("LOG_EXCLUDE_MODULES", "").split(",")
        moduls_exclosos = [m.strip() for m in moduls_exclosos if m.strip()]

        # Crear directori de logs si no existeix
        if not os.path.exists(cls._directori_logs):
            os.makedirs(cls._directori_logs)

        # Format del log
        format_log = os.getenv("LOG_FORMAT", "%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s")
        format_data = "%Y-%m-%d %H:%M:%S"

        # Obtenir el logger arrel
        logger_arrel = logging.getLogger()
        logger_arrel.setLevel(getattr(logging, nivell, logging.INFO))

        # Netejar handlers existents (per reconfiguració)
        logger_arrel.handlers.clear()

        # Filtre de mòduls
        filtre_moduls = FiltreMòduls(moduls_exclosos=moduls_exclosos) if moduls_exclosos else None

        # Handler per a consola (amb colors)
        consola_handler = logging.StreamHandler()
        consola_handler.setLevel(logging.WARNING)
        formatter_consola = FormatterAmbColors(format_log, format_data, usar_colors=usar_colors)
        consola_handler.setFormatter(formatter_consola)
        if filtre_moduls:
            consola_handler.addFilter(filtre_moduls)
        logger_arrel.addHandler(consola_handler)

        # Handler per a fitxer principal (amb rotació i compressió)
        fitxer_principal = os.path.join(cls._directori_logs, "transcriptor.log")
        fitxer_handler = RotatingFileHandlerAmbCompressio(
            fitxer_principal,
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=5,
            encoding="utf-8",
            comprimir=comprimir_rotats
        )
        fitxer_handler.setLevel(logging.DEBUG)
        fitxer_handler.setFormatter(logging.Formatter(format_log, format_data))
        if filtre_moduls:
            fitxer_handler.addFilter(filtre_moduls)
        logger_arrel.addHandler(fitxer_handler)

        # Handler per a errors (fitxer separat)
        fitxer_errors = os.path.join(cls._directori_logs, "errors.log")
        error_handler = RotatingFileHandlerAmbCompressio(
            fitxer_errors,
            maxBytes=2 * 1024 * 1024,  # 2 MB
            backupCount=3,
            encoding="utf-8",
            comprimir=comprimir_rotats
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(logging.Formatter(format_log, format_data))
        logger_arrel.addHandler(error_handler)

        # Handler per a logs JSON (opcional)
        if format_json:
            fitxer_json = os.path.join(cls._directori_logs, "transcriptor.json.log")
            json_handler = RotatingFileHandlerAmbCompressio(
                fitxer_json,
                maxBytes=5 * 1024 * 1024,
                backupCount=3,
                encoding="utf-8",
                comprimir=comprimir_rotats
            )
            json_handler.setLevel(logging.DEBUG)
            json_handler.setFormatter(FormatterJSON())
            logger_arrel.addHandler(json_handler)

        # Handler per mètriques
        metriques_handler = HandlerMetriques(cls._metriques)
        metriques_handler.setLevel(logging.DEBUG)
        logger_arrel.addHandler(metriques_handler)

        cls._inicialitzat = True

        # Log inicial
        logger = logging.getLogger("utils.GestorLogging")
        config_info = f"nivell={nivell}, colors={usar_colors}, json={format_json}, compressió={comprimir_rotats}"
        logger.info(f"Sistema de logging inicialitzat ({config_info})")

    @classmethod
    def obtenir_logger(cls, nom):
        """
        Obté un logger amb el nom especificat.

        Args:
            nom: Nom del mòdul o classe.

        Returns:
            Logger configurat.
        """
        if not cls._inicialitzat:
            cls.configurar()
        return logging.getLogger(nom)

    @classmethod
    def obtenir_metriques(cls):
        """Retorna les mètriques actuals del sistema de logging."""
        return cls._metriques.obtenir_resum()

    @classmethod
    def reiniciar_metriques(cls):
        """Reinicia les mètriques a zero."""
        cls._metriques.reiniciar()

    @classmethod
    @contextmanager
    def operacio(cls, nom_operacio, logger=None):
        """
        Context manager per mesurar i registrar la durada d'una operació.

        Ús:
            with GestorLogging.operacio("processament_imatge", logger):
                # codi a mesurar

        Args:
            nom_operacio: Nom descriptiu de l'operació.
            logger: Logger a utilitzar (opcional).
        """
        logger = logger or cls.obtenir_logger("operacio")
        inici = time.perf_counter()
        logger.debug(f"Iniciant operació: {nom_operacio}")

        try:
            yield
        except Exception as e:
            durada = (time.perf_counter() - inici) * 1000
            logger.error(f"Error en operació '{nom_operacio}' després de {durada:.2f}ms: {e}")
            cls._metriques.registrar_temps(nom_operacio, durada)
            raise
        else:
            durada = (time.perf_counter() - inici) * 1000
            logger.info(f"Operació '{nom_operacio}' completada en {durada:.2f}ms")
            cls._metriques.registrar_temps(nom_operacio, durada)


def mesurar_temps(nom_operacio=None, nivell=logging.INFO):
    """
    Decorador per mesurar i registrar el temps d'execució d'una funció.

    Ús:
        @mesurar_temps("processament_openai")
        def processar_amb_openai(self, ruta):
            ...

    Args:
        nom_operacio: Nom de l'operació (per defecte, nom de la funció).
        nivell: Nivell de log per al missatge de temps.
    """
    def decorador(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            operacio = nom_operacio or func.__name__
            logger = GestorLogging.obtenir_logger(func.__module__ or "decorador")

            inici = time.perf_counter()
            try:
                resultat = func(*args, **kwargs)
                durada = (time.perf_counter() - inici) * 1000
                logger.log(nivell, f"{operacio} completat en {durada:.2f}ms")
                GestorLogging._metriques.registrar_temps(operacio, durada)
                return resultat
            except Exception as e:
                durada = (time.perf_counter() - inici) * 1000
                logger.error(f"{operacio} ha fallat després de {durada:.2f}ms: {e}")
                GestorLogging._metriques.registrar_temps(operacio, durada)
                raise

        return wrapper
    return decorador


def log_excepcions(logger=None, reraise=True):
    """
    Decorador per capturar i registrar excepcions automàticament.

    Ús:
        @log_excepcions()
        def funcio_arriscada():
            ...

    Args:
        logger: Logger a utilitzar (opcional).
        reraise: Si True, re-llença l'excepció després de registrar-la.
    """
    def decorador(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            _logger = logger or GestorLogging.obtenir_logger(func.__module__ or "decorador")
            try:
                return func(*args, **kwargs)
            except Exception as e:
                _logger.exception(f"Excepció en {func.__name__}: {e}")
                if reraise:
                    raise
                return None

        return wrapper
    return decorador

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
    _logger = None

    @classmethod
    def _get_logger(cls):
        if cls._logger is None:
            cls._logger = GestorLogging.obtenir_logger("utils.GestorConfiguracio")
        return cls._logger

    @staticmethod
    def desar_config(dades):
        logger = GestorConfiguracio._get_logger()
        try:
            with open("config.json", "w", encoding="utf-8") as f:
                json.dump(dades, f, indent=4)
            logger.info("Configuració desada correctament a config.json")
        except Exception as e:
            logger.error(f"Error desant configuració: {e}")
            raise

    @staticmethod
    def carregar_config():
        logger = GestorConfiguracio._get_logger()
        config = {}

        try:
            if os.path.exists("config.json"):
                with open("config.json", "r", encoding="utf-8") as f:
                    config = json.load(f)
                logger.debug("Configuració carregada des de config.json")
            else:
                logger.debug("config.json no existeix, usant valors per defecte")
        except json.JSONDecodeError as e:
            logger.error(f"Error parsejant config.json: {e}")
        except Exception as e:
            logger.error(f"Error llegint config.json: {e}")

        # Incorporem la API Key des del .env si no està al JSON
        if "api_key" not in config:
            config["api_key"] = os.getenv("OPENAI_API_KEY", "")
            if config["api_key"]:
                logger.debug("API key carregada des de .env")

        # Afegim el control del so (per defecte True si no hi és)
        if "enable_sound" not in config:
            config["enable_sound"] = os.getenv("ENABLE_SOUND", "TRUE").upper() == "TRUE"

        logger.info(f"Configuració carregada - so: {config.get('enable_sound')}, api_key: {'[configurat]' if config.get('api_key') else '[no configurat]'}")

        return config

# =============================================================================
# GESTIÓ DE PLANTILLES
# =============================================================================

class GestorPlantilles:
    """Gestiona les plantilles de documents (tiquets, factures, albarans)."""

    CARPETA_PLANTILLES = "plantilles"
    CARPETA_DOCUMENTS = os.path.join(CARPETA_PLANTILLES, "documents")
    FITXER_PLANTILLES = os.path.join(CARPETA_PLANTILLES, "plantilles.json")

    def __init__(self):
        self.logger = GestorLogging.obtenir_logger("utils.GestorPlantilles")
        self._assegurar_carpetes()
        self.logger.debug("GestorPlantilles inicialitzat")

    def _assegurar_carpetes(self):
        """Crea les carpetes necessàries si no existeixen."""
        for carpeta in [self.CARPETA_PLANTILLES, self.CARPETA_DOCUMENTS]:
            if not os.path.exists(carpeta):
                os.makedirs(carpeta)
                self.logger.info(f"Carpeta creada: {carpeta}")

    def _carregar_plantilles(self):
        """Carrega totes les plantilles del fitxer JSON."""
        if not os.path.exists(self.FITXER_PLANTILLES):
            return {}
        try:
            with open(self.FITXER_PLANTILLES, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, Exception) as e:
            self.logger.error(f"Error carregant plantilles: {e}")
            return {}

    def _desar_plantilles(self, plantilles):
        """Desa totes les plantilles al fitxer JSON."""
        try:
            with open(self.FITXER_PLANTILLES, "w", encoding="utf-8") as f:
                json.dump(plantilles, f, indent=4, ensure_ascii=False)
            self.logger.debug("Plantilles desades correctament")
        except Exception as e:
            self.logger.error(f"Error desant plantilles: {e}")
            raise

    def llistar_plantilles(self):
        """Retorna una llista de totes les plantilles disponibles."""
        plantilles = self._carregar_plantilles()
        return [
            {
                "id": pid,
                "nom": p.get("nom", "Sense nom"),
                "descripcio": p.get("descripcio", ""),
                "metode": p.get("metode", ""),
                "tipus": p.get("tipus", "general")
            }
            for pid, p in plantilles.items()
        ]

    def obtenir_plantilla(self, plantilla_id):
        """Obté una plantilla pel seu ID."""
        plantilles = self._carregar_plantilles()
        return plantilles.get(plantilla_id)

    def desar_plantilla(self, nom, descripcio, metode, model, instruccions_extra,
                        document_original=None, tipus="general", plantilla_id=None):
        """
        Desa o actualitza una plantilla.

        Args:
            nom: Nom de la plantilla
            descripcio: Descripció del tipus de document
            metode: Mètode d'extracció (ocr, openai, claude, ollama)
            model: Model utilitzat (gpt-4o-mini, claude-sonnet-4-20250514, etc.)
            instruccions_extra: Instruccions addicionals per al prompt
            document_original: Ruta al document de referència (es copiarà)
            tipus: Tipus de document (tiquet, factura, albara, general)
            plantilla_id: ID existent per actualitzar, o None per crear nova

        Returns:
            ID de la plantilla desada
        """
        plantilles = self._carregar_plantilles()
        ara = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Generar ID si és nova
        if plantilla_id is None:
            # Crear ID basat en el nom (slug)
            plantilla_id = self._generar_id(nom)
            # Assegurar que és únic
            base_id = plantilla_id
            comptador = 1
            while plantilla_id in plantilles:
                plantilla_id = f"{base_id}_{comptador}"
                comptador += 1

        # Copiar document de referència si s'ha proporcionat
        document_referencia = None
        if document_original and os.path.exists(document_original):
            ext = os.path.splitext(document_original)[1]
            nom_document = f"{plantilla_id}{ext}"
            ruta_desti = os.path.join(self.CARPETA_DOCUMENTS, nom_document)
            try:
                shutil.copy2(document_original, ruta_desti)
                document_referencia = nom_document
                self.logger.info(f"Document de referència copiat: {nom_document}")
            except Exception as e:
                self.logger.error(f"Error copiant document: {e}")

        # Crear o actualitzar plantilla
        es_nova = plantilla_id not in plantilles
        plantilla = {
            "nom": nom,
            "descripcio": descripcio,
            "tipus": tipus,
            "metode": metode,
            "model": model,
            "instruccions_extra": instruccions_extra or "",
            "document_referencia": document_referencia or plantilles.get(plantilla_id, {}).get("document_referencia"),
            "data_creacio": plantilles.get(plantilla_id, {}).get("data_creacio", ara),
            "data_modificacio": ara
        }

        plantilles[plantilla_id] = plantilla
        self._desar_plantilles(plantilles)

        accio = "creada" if es_nova else "actualitzada"
        self.logger.info(f"Plantilla {accio}: {nom} (ID: {plantilla_id})")
        return plantilla_id

    def eliminar_plantilla(self, plantilla_id):
        """Elimina una plantilla i el seu document de referència."""
        plantilles = self._carregar_plantilles()
        if plantilla_id not in plantilles:
            return False

        plantilla = plantilles[plantilla_id]

        # Eliminar document de referència si existeix
        if plantilla.get("document_referencia"):
            ruta_doc = os.path.join(self.CARPETA_DOCUMENTS, plantilla["document_referencia"])
            if os.path.exists(ruta_doc):
                try:
                    os.remove(ruta_doc)
                    self.logger.debug(f"Document eliminat: {ruta_doc}")
                except Exception as e:
                    self.logger.warning(f"No s'ha pogut eliminar document: {e}")

        del plantilles[plantilla_id]
        self._desar_plantilles(plantilles)
        self.logger.info(f"Plantilla eliminada: {plantilla_id}")
        return True

    def obtenir_ruta_document(self, plantilla_id):
        """Obté la ruta completa al document de referència d'una plantilla."""
        plantilla = self.obtenir_plantilla(plantilla_id)
        if plantilla and plantilla.get("document_referencia"):
            return os.path.join(self.CARPETA_DOCUMENTS, plantilla["document_referencia"])
        return None

    def _generar_id(self, nom):
        """Genera un ID vàlid a partir del nom."""
        import re
        # Convertir a minúscules, reemplaçar espais i caràcters especials
        slug = nom.lower()
        slug = re.sub(r'[àáâãäå]', 'a', slug)
        slug = re.sub(r'[èéêë]', 'e', slug)
        slug = re.sub(r'[ìíîï]', 'i', slug)
        slug = re.sub(r'[òóôõö]', 'o', slug)
        slug = re.sub(r'[ùúûü]', 'u', slug)
        slug = re.sub(r'[ç]', 'c', slug)
        slug = re.sub(r'[ñ]', 'n', slug)
        slug = re.sub(r'[^a-z0-9]+', '_', slug)
        slug = slug.strip('_')
        return slug or "plantilla"


class CalculadoraCostos:
    def __init__(self):
        self.fitxer_historial = "historial_costos.json"
        self.logger = GestorLogging.obtenir_logger("utils.CalculadoraCostos")
        self.logger.debug("CalculadoraCostos inicialitzat")

    def registrar_transaccio(self, model, tokens_in, tokens_out, cost):
        registre = {
            "data": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "model": model,
            "tokens_input": tokens_in,
            "tokens_output": tokens_out,
            "cost_usd": cost
        }

        try:
            historial = self.carregar_historial()
            historial.append(registre)
            with open(self.fitxer_historial, "w", encoding="utf-8") as f:
                json.dump(historial, f, indent=4)
            self.logger.info(f"Cost registrat: model={model}, tokens_in={tokens_in}, tokens_out={tokens_out}, cost=${cost:.6f}")
        except Exception as e:
            self.logger.error(f"Error registrant transacció: {e}")
            raise

    def carregar_historial(self):
        try:
            if os.path.exists(self.fitxer_historial):
                with open(self.fitxer_historial, "r", encoding="utf-8") as f:
                    historial = json.load(f)
                self.logger.debug(f"Historial carregat: {len(historial)} registres")
                return historial
        except json.JSONDecodeError as e:
            self.logger.error(f"Error parsejant historial de costos: {e}")
        except Exception as e:
            self.logger.error(f"Error llegint historial de costos: {e}")
        return []


# =============================================================================
# GESTIÓ DE BASE DE DADES - TRANSCRIPCIONS
# =============================================================================

class GestorBaseDades:
    """Gestiona la persistència de transcripcions en una base de dades SQLite."""

    FITXER_BD = "transcripcions.db"

    def __init__(self, fitxer_bd=None):
        self.fitxer_bd = fitxer_bd or self.FITXER_BD
        self.logger = GestorLogging.obtenir_logger("utils.GestorBaseDades")
        self._inicialitzar_bd()
        self.logger.debug(f"GestorBaseDades inicialitzat: {self.fitxer_bd}")

    def _inicialitzar_bd(self):
        """Crea la taula de transcripcions si no existeix."""
        try:
            with sqlite3.connect(self.fitxer_bd) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS transcripcions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        nom TEXT,
                        nif TEXT,
                        factura TEXT,
                        total REAL,
                        contingutJSON TEXT NOT NULL,
                        nomDocument TEXT,
                        dataAlta TEXT NOT NULL
                    )
                """)
                conn.commit()
                self.logger.info("Taula de transcripcions verificada/creada")
        except sqlite3.Error as e:
            self.logger.error(f"Error inicialitzant base de dades: {e}")
            raise

    def inserir_transcripcio(self, nom, nif, factura, total, contingut_json, nom_document):
        """
        Insereix una nova transcripció a la base de dades.

        Args:
            nom: Nom de l'establiment
            nif: NIF de l'establiment
            factura: Número de factura/tiquet/rebut
            total: Total del document
            contingut_json: JSON complet de la transcripció (com a string)
            nom_document: Nom del fitxer original escanejat

        Returns:
            ID del registre inserit
        """
        data_alta = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        try:
            with sqlite3.connect(self.fitxer_bd) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO transcripcions (nom, nif, factura, total, contingutJSON, nomDocument, dataAlta)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (nom, nif, factura, total, contingut_json, nom_document, data_alta))
                conn.commit()
                registre_id = cursor.lastrowid
                self.logger.info(f"Transcripció inserida: ID={registre_id}, establiment={nom}")
                return registre_id
        except sqlite3.Error as e:
            self.logger.error(f"Error inserint transcripció: {e}")
            raise

    def obtenir_transcripcio(self, registre_id):
        """Obté una transcripció pel seu ID."""
        try:
            with sqlite3.connect(self.fitxer_bd) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM transcripcions WHERE id = ?", (registre_id,))
                fila = cursor.fetchone()
                if fila:
                    return dict(fila)
                return None
        except sqlite3.Error as e:
            self.logger.error(f"Error obtenint transcripció {registre_id}: {e}")
            raise

    def llistar_transcripcions(self, limit=100, offset=0):
        """
        Llista les transcripcions amb paginació.

        Args:
            limit: Nombre màxim de registres a retornar
            offset: Nombre de registres a saltar

        Returns:
            Llista de diccionaris amb les transcripcions
        """
        try:
            with sqlite3.connect(self.fitxer_bd) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, nom, nif, factura, total, nomDocument, dataAlta
                    FROM transcripcions
                    ORDER BY dataAlta DESC
                    LIMIT ? OFFSET ?
                """, (limit, offset))
                files = cursor.fetchall()
                return [dict(fila) for fila in files]
        except sqlite3.Error as e:
            self.logger.error(f"Error llistant transcripcions: {e}")
            raise

    def cercar_transcripcions(self, terme, columna=None, limit=None, offset=0):
        """
        Cerca transcripcions per nom d'establiment, NIF o número de factura.

        Args:
            terme: Text a cercar
            columna: Columna específica per filtrar (nom, nif, factura, nomDocument).
                     Si és None, cerca a nom, nif i factura.
            limit: Nombre màxim de registres a retornar (None = sense límit)
            offset: Nombre de registres a saltar

        Returns:
            Llista de transcripcions coincidents
        """
        try:
            with sqlite3.connect(self.fitxer_bd) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cerca = f"%{terme}%"

                columnes_valides = {"nom", "nif", "factura", "nomDocument", "total"}
                if columna and columna in columnes_valides:
                    query = f"""
                        SELECT id, nom, nif, factura, total, nomDocument, dataAlta
                        FROM transcripcions
                        WHERE {columna} LIKE ?
                        ORDER BY dataAlta DESC
                    """
                    params = [cerca]
                else:
                    query = """
                        SELECT id, nom, nif, factura, total, nomDocument, dataAlta
                        FROM transcripcions
                        WHERE nom LIKE ? OR nif LIKE ? OR factura LIKE ?
                        ORDER BY dataAlta DESC
                    """
                    params = [cerca, cerca, cerca]

                if limit is not None:
                    query += " LIMIT ? OFFSET ?"
                    params.extend([limit, offset])

                cursor.execute(query, params)
                files = cursor.fetchall()
                return [dict(fila) for fila in files]
        except sqlite3.Error as e:
            self.logger.error(f"Error cercant transcripcions: {e}")
            raise

    def actualitzar_transcripcio(self, registre_id, nom, nif, factura, total, contingut_json, nom_document):
        """
        Actualitza una transcripció existent a la base de dades.

        Args:
            registre_id: ID del registre a actualitzar
            nom: Nom de l'establiment
            nif: NIF de l'establiment
            factura: Número de factura/tiquet/rebut
            total: Total del document
            contingut_json: JSON complet de la transcripció (com a string)
            nom_document: Nom del fitxer original escanejat

        Returns:
            True si s'ha actualitzat correctament
        """
        try:
            with sqlite3.connect(self.fitxer_bd) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE transcripcions
                    SET nom = ?, nif = ?, factura = ?, total = ?, contingutJSON = ?, nomDocument = ?
                    WHERE id = ?
                """, (nom, nif, factura, total, contingut_json, nom_document, registre_id))
                conn.commit()
                actualitzats = cursor.rowcount
                if actualitzats > 0:
                    self.logger.info(f"Transcripció actualitzada: ID={registre_id}, establiment={nom}")
                return actualitzats > 0
        except sqlite3.Error as e:
            self.logger.error(f"Error actualitzant transcripció {registre_id}: {e}")
            raise

    def eliminar_transcripcio(self, registre_id):
        """Elimina una transcripció pel seu ID."""
        try:
            with sqlite3.connect(self.fitxer_bd) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM transcripcions WHERE id = ?", (registre_id,))
                conn.commit()
                eliminats = cursor.rowcount
                if eliminats > 0:
                    self.logger.info(f"Transcripció eliminada: ID={registre_id}")
                return eliminats > 0
        except sqlite3.Error as e:
            self.logger.error(f"Error eliminant transcripció {registre_id}: {e}")
            raise

    def comptar_transcripcions(self):
        """Retorna el nombre total de transcripcions."""
        try:
            with sqlite3.connect(self.fitxer_bd) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM transcripcions")
                return cursor.fetchone()[0]
        except sqlite3.Error as e:
            self.logger.error(f"Error comptant transcripcions: {e}")
            raise

    def existeix_factura(self, nif, factura):
        """
        Comprova si ja existeix una factura amb el mateix NIF i número.

        Args:
            nif: NIF de l'establiment
            factura: Número de factura

        Returns:
            True si existeix, False si no
        """
        if not nif or not factura:
            return False
        try:
            with sqlite3.connect(self.fitxer_bd) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT COUNT(*) FROM transcripcions
                    WHERE nif = ? AND factura = ?
                """, (nif, factura))
                return cursor.fetchone()[0] > 0
        except sqlite3.Error as e:
            self.logger.error(f"Error comprovant existència de factura: {e}")
            return False