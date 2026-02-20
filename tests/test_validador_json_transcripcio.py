import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import FormatTranscripcio, ValidadorJSONTranscripcio


def test_validador_accepta_json_valid(sample_tiquet_json):
    valid, errors = ValidadorJSONTranscripcio.validar(sample_tiquet_json)
    assert valid is True
    assert errors == []


def test_validador_rebutja_import_numeric_no_string(sample_tiquet_json):
    dades = dict(sample_tiquet_json)
    dades["total"] = 25.5

    valid, errors = ValidadorJSONTranscripcio.validar(dades)

    assert valid is False
    assert any("'total'" in err for err in errors)


def test_validador_rebutja_percentatge_sense_simbol(sample_tiquet_json):
    dades = dict(sample_tiquet_json)
    dades["impostos"] = [{"percentatgeIVA": "21", "importBaseIVA": "10,00", "quotaIVA": "2,10"}]

    valid, errors = ValidadorJSONTranscripcio.validar(dades)

    assert valid is False
    assert any("percentatgeIVA" in err for err in errors)


def test_format_normalitza_import_percent_i_quantitat():
    assert FormatTranscripcio.normalitzar_import("12.50") == "12,50"
    assert FormatTranscripcio.normalitzar_percentatge("21") == "21%"
    assert FormatTranscripcio.parsejar_quantitat("2,5") == 2.5
