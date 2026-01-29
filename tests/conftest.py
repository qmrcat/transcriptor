import pytest
import tempfile
import os
import json


@pytest.fixture
def temp_dir():
    """Crea un directori temporal per als tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def sample_tiquet_json():
    """Retorna un JSON d'exemple d'un tiquet processat."""
    return {
        "establiment": "Supermercat Test",
        "nifEstabliment": "B12345678",
        "numeroFacturaRebutTiquet": "T-001",
        "data": "15/01/2024",
        "hora": "14:30",
        "total": "25,50",
        "impostos": [
            {
                "percentatgeIVA": "21%",
                "importBaseIVA": "21,07",
                "quotaIVA": "4,43"
            }
        ],
        "articles": [
            {
                "descripció": "Pa de motlle",
                "quantitat": 2,
                "preu": "1,50",
                "importBase": "2,48",
                "percentatgeIVA": "21%",
                "importIVA": "0,52",
                "importTotal": "3,00"
            },
            {
                "descripció": "Llet sencera 1L",
                "quantitat": 3,
                "preu": "1,20",
                "importBase": "2,98",
                "percentatgeIVA": "21%",
                "importIVA": "0,62",
                "importTotal": "3,60"
            }
        ],
        "forma_pagament": "Targeta"
    }


@pytest.fixture
def mock_env(monkeypatch, temp_dir):
    """Configura variables d'entorn per als tests."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-api-key-12345")
    monkeypatch.setenv("ENABLE_SOUND", "FALSE")
    monkeypatch.chdir(temp_dir)
    return temp_dir
