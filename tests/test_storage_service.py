import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.storage_service import DuplicateDocumentError, StorageService


def test_storage_service_converteix_integrity_error(temp_dir, monkeypatch):
    monkeypatch.chdir(temp_dir)
    service = StorageService("test.db")

    payload = {
        "nom": "Botiga",
        "nif": "B12345678",
        "factura": "F-001",
        "total": 10.0,
        "contingut_json": '{"establiment":"Botiga","total":"10,00","articles":[],"impostos":[]}',
        "nom_document": "a.pdf",
    }

    service.inserir_transcripcio(**payload)
    with pytest.raises(DuplicateDocumentError):
        service.inserir_transcripcio(**payload)
