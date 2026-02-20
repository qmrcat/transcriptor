import os
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.transcription_service import TranscriptionService


class _FakeTranscriptor:
    def __init__(self):
        self.client = object()
        self.client_claude = object()

    def processar_imatge_ocr(self, ruta, idioma):
        return f"ocr:{ruta}:{idioma}"

    def processar_amb_openai(self, ruta, text_ocr=None, instruccions_extra=None):
        return {"metode": "openai", "ruta": ruta, "ocr": text_ocr, "instr": instruccions_extra}

    def processar_amb_claude(self, ruta, instruccions_extra=None):
        return {"metode": "claude", "ruta": ruta, "instr": instruccions_extra}

    def processar_amb_ollama(self, ruta, instruccions_extra=None):
        return {"metode": "ollama", "ruta": ruta, "instr": instruccions_extra}


def test_processar_ocr_openai_ruta():
    service = TranscriptionService(api_key=None)
    service.transcriptor = _FakeTranscriptor()

    resultat = service.processar("ocr-openai", "doc.jpg", idioma="cat+spa", instruccions_extra="x")

    assert resultat["metode"] == "openai"
    assert resultat["ocr"] == "ocr:doc.jpg:cat+spa"


def test_processar_cancel_event():
    service = TranscriptionService(api_key=None)
    service.transcriptor = _FakeTranscriptor()
    cancel = threading.Event()
    cancel.set()

    resultat = service.processar("openai", "doc.jpg", cancel_event=cancel)
    assert resultat == {"cancelled": True}
