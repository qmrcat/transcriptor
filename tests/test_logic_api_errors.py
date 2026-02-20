import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logic = pytest.importorskip("logic")
TranscriptorTiquets = logic.TranscriptorTiquets


def test_openai_sense_api_key_retorna_error(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    transcriptor = TranscriptorTiquets(api_key=None)
    resultat = transcriptor.processar_amb_openai("fitxer_inexistent.jpg")

    assert isinstance(resultat, dict)
    assert "error" in resultat
    assert "API Key" in resultat["error"]


def test_claude_sense_api_key_retorna_error(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    transcriptor = TranscriptorTiquets(api_key="dummy-openai-key")
    resultat = transcriptor.processar_amb_claude("fitxer_inexistent.jpg")

    assert isinstance(resultat, dict)
    assert "error" in resultat
    assert "Claude" in resultat["error"] or "ANTHROPIC_API_KEY" in resultat["error"]
