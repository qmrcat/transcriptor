from logic import TranscriptorAmbCostos, TranscriptorTiquets


class TranscriptionService:
    """Servei d'alt nivell per al processament de documents."""

    def __init__(self, api_key=None, base_url=None, usar_costos=True):
        if usar_costos:
            self.transcriptor = TranscriptorAmbCostos(api_key=api_key)
        else:
            self.transcriptor = TranscriptorTiquets(api_key=api_key, base_url=base_url)

    def validar_configuracio_metode(self, metode):
        if metode == "openai" and not self.transcriptor.client:
            return "Per utilitzar OpenAI, configura OPENAI_API_KEY al fitxer .env o config.json"
        if metode == "claude" and not self.transcriptor.client_claude:
            return "Per utilitzar Claude, configura ANTHROPIC_API_KEY al fitxer .env"
        return None

    def processar(self, metode, ruta_fitxer, idioma="cat+spa", instruccions_extra=None, cancel_event=None):
        if cancel_event is not None and cancel_event.is_set():
            return {"cancelled": True}

        if metode == "ocr":
            resultat = self.transcriptor.processar_imatge_ocr(ruta_fitxer, idioma)
        elif metode == "openai":
            resultat = self.transcriptor.processar_amb_openai(ruta_fitxer, instruccions_extra=instruccions_extra)
        elif metode == "claude":
            resultat = self.transcriptor.processar_amb_claude(ruta_fitxer, instruccions_extra=instruccions_extra)
        elif metode == "ollama":
            resultat = self.transcriptor.processar_amb_ollama(ruta_fitxer, instruccions_extra=instruccions_extra)
        elif metode == "ocr-openai":
            text_ocr = self.transcriptor.processar_imatge_ocr(ruta_fitxer, idioma)
            if cancel_event is not None and cancel_event.is_set():
                return {"cancelled": True}
            resultat = self.transcriptor.processar_amb_openai(
                ruta_fitxer,
                text_ocr=text_ocr,
                instruccions_extra=instruccions_extra
            )
        else:
            return {"error": f"Mètode no suportat: {metode}"}

        if cancel_event is not None and cancel_event.is_set():
            return {"cancelled": True}
        return resultat
