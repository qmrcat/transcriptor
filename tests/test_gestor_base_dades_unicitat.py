import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import GestorBaseDades


def test_no_permet_duplicat_nif_factura(temp_dir, monkeypatch):
    monkeypatch.chdir(temp_dir)
    gestor = GestorBaseDades("test.db")

    gestor.inserir_transcripcio(
        nom="Botiga A",
        nif="B12345678",
        factura="F-001",
        total=10.0,
        contingut_json='{"establiment":"Botiga A","total":"10,00","articles":[],"impostos":[]}',
        nom_document="a.pdf",
    )

    with pytest.raises(sqlite3.IntegrityError):
        gestor.inserir_transcripcio(
            nom="Botiga A",
            nif="B12345678",
            factura="F-001",
            total=10.0,
            contingut_json='{"establiment":"Botiga A","total":"10,00","articles":[],"impostos":[]}',
            nom_document="b.pdf",
        )


def test_permet_insercio_si_nif_o_factura_buits(temp_dir, monkeypatch):
    monkeypatch.chdir(temp_dir)
    gestor = GestorBaseDades("test.db")

    id1 = gestor.inserir_transcripcio(
        nom="Sense NIF",
        nif="",
        factura="F-010",
        total=5.0,
        contingut_json='{"establiment":"Sense NIF","total":"5,00","articles":[],"impostos":[]}',
        nom_document="a.pdf",
    )
    id2 = gestor.inserir_transcripcio(
        nom="Sense NIF 2",
        nif="",
        factura="F-010",
        total=5.0,
        contingut_json='{"establiment":"Sense NIF 2","total":"5,00","articles":[],"impostos":[]}',
        nom_document="b.pdf",
    )

    assert isinstance(id1, int)
    assert isinstance(id2, int)
