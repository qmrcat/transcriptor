import sqlite3

from utils import GestorBaseDades


class DuplicateDocumentError(Exception):
    """Error de domini per duplicat de document (nif, factura)."""


class StorageService:
    """Servei d'alt nivell per persistència de transcripcions."""

    def __init__(self, fitxer_bd=None):
        self.gestor_bd = GestorBaseDades(fitxer_bd=fitxer_bd)

    def existeix_factura(self, nif, factura):
        return self.gestor_bd.existeix_factura(nif, factura)

    def inserir_transcripcio(self, **kwargs):
        try:
            return self.gestor_bd.inserir_transcripcio(**kwargs)
        except sqlite3.IntegrityError as e:
            raise DuplicateDocumentError(str(e)) from e

    def actualitzar_transcripcio(self, **kwargs):
        try:
            return self.gestor_bd.actualitzar_transcripcio(**kwargs)
        except sqlite3.IntegrityError as e:
            raise DuplicateDocumentError(str(e)) from e

