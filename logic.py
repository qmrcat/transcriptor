import pytesseract
from PIL import Image
import pdf2image
import json
import os
import base64
import tempfile
from openai import OpenAI
from dotenv import load_dotenv
from utils import GestorLogging, mesurar_temps, log_excepcions

load_dotenv()

class TranscriptorTiquets:
    def __init__(self, api_key=None, base_url=None):
        self.logger = GestorLogging.obtenir_logger("logic.TranscriptorTiquets")
        self.logger.info("Inicialitzant TranscriptorTiquets")

        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        # Permet Ollama/LM Studio o OpenAI oficial
        self.client = OpenAI(api_key=self.api_key, base_url=base_url) if self.api_key else None

        if self.client:
            self.logger.info(f"Client OpenAI configurat (base_url: {base_url or 'default'})")
        else:
            self.logger.warning("Client OpenAI no configurat - falta API key")

        # Client per Ollama (IA Local)
        # Per defecte Ollama escolta al port 11434
        ollama_url = os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434/v1"
        self.client_ollama = OpenAI(
            base_url=ollama_url,
            api_key="ollama"  # Ollama no necessita clau real, però la llibreria la demana
        )
        self.logger.debug(f"Client Ollama configurat (url: {ollama_url})")

    # Prompt compartit per OpenAI i Ollama
    PROMPT_SISTEMA = """Ets un expert en comptabilitat i digitalització de documents.

Analitza la imatge d'un tiquet, albarà o factura i retorna EXCLUSIVAMENT un objecte JSON.
No afegeixis cap text fora del JSON.
No facis explicacions.
No dedueixis, no estimis ni inventis cap dada.

Si una informació no apareix explícitament al document o no es pot calcular de manera directa i fiable, posa null.

El JSON ha de tenir exactament aquest format:

{
  "establiment": "Nom",
  "nifEstabliment": "CIF/NIF",
  "numeroFacturaRebutTiquet": "ID",
  "data": "DD/MM/YYYY",
  "hora": "HH:MM",
  "total": "0,00",
  "impostos": [
    {
    "percentatgeIVA": "21%",
    "importBaseIVA": "0,00",
    "quotaIVA": "0,00"
    }
  ],
  "articles": [
    {
    "descripció": "Producte/article",
    "quantitat": 1,
    "preu": "0,00",
    "importBase": "0,00",
    "percentatgeIVA": "21%",
    "importIVA": "0,00",
    "importTotal": "0,00"
    }
  ],
  "forma_pagament": "Targeta/Efectiu"
}

Regles generals:
- Tots els imports monetaris han de ser strings amb coma decimal (ex: "12,50") i sense símbol €.
- Els percentatges d'IVA han de ser strings amb el símbol % (ex: "21%").
- La quantitat ha de ser numèrica (sense cometes).
- Si un camp concret d'un article no es pot determinar, posa null només en aquell camp.
- Si no hi ha articles detallats, retorna l'array "articles" buit.

Aclariments importants:
- "data" ha d'estar en format DD/MM/YYYY.
- Els tiquets poden estar en català, castellà o barrejats.
- A vegades els tiquets no tenen NIF o desglossament d'IVA: posa null en aquests camps.
- Si hi ha diversos tipus d'IVA, inclou-los tots a l'array "impostos".
- No afegeixis totals globals d'impostos si ja apareixen desglossats.
- L'array "articles" ha de contenir tots els productes o serveis detallats.

Correspondència de columnes habituals:
- "descripció": pot aparèixer com descripcio, concepte, detall, producte, article o nom.
- "quantitat": pot aparèixer com cant, unitats, uni, quantitat, QT, qty o no aparèixer.
- "preu": pot aparèixer com preu, precio, PVP o base.
- "importBase": pot aparèixer com base, import base, importe base o subtotal.
- "percentatgeIVA": pot aparèixer com %IVA, tipus IVA, % IVA o %.
- "importIVA": pot aparèixer com IVA, I.V.A., quota IVA o import IVA.
- "importTotal": pot aparèixer com total, import, import total o total article.

Casos especials:
- Alguns articles poden estar repartits en dues files (descripció en una, quantitat i preu en una altra). Intenta combinar-los correctament.
- Algunes línies poden ser textos explicatius (ofertes, promocions, descomptes, aclariments). Ignora-les.
- La quantitat i el preu poden aparèixer junts (ex: "2 x 3,50"). Separa correctament quantitat i preu.
- Si el preu inclou IVA, només calcula import base i quota d'IVA si el percentatge apareix explícitament.
- La separació decimal pot ser amb coma o punt segons l'idioma del tiquet, però retorna sempre els imports amb coma.

La "forma_pagament" ha de ser una cadena curta indicant el mètode de pagament (Targeta, Efectiu, Bizum, Transferència, etc.).
"""

    def _codificar_imatge_base64(self, ruta_imatge):
        """Converteix un fitxer d'imatge en una cadena Base64 per a l'API."""
        self.logger.debug(f"Codificant imatge a base64: {ruta_imatge}")
        with open(ruta_imatge, "rb") as fitxer_imatge:
            return base64.b64encode(fitxer_imatge.read()).decode('utf-8')

    def _preparar_imatge_per_api(self, ruta_imatge):
        """
        Prepara una imatge per enviar a l'API (converteix PDF si cal).
        Retorna (base64_image, ruta_temporal) on ruta_temporal és None si no s'ha creat.
        """
        ruta_temporal = None

        if ruta_imatge.lower().endswith(".pdf"):
            self.logger.debug(f"Convertint PDF a imatge: {ruta_imatge}")
            pagines = pdf2image.convert_from_path(ruta_imatge)
            if not pagines:
                self.logger.error("El PDF no conté cap pàgina")
                raise ValueError("El PDF no conté cap pàgina.")
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                ruta_temporal = tmp.name
            pagines[0].save(ruta_temporal, "JPEG")
            self.logger.debug(f"PDF convertit a: {ruta_temporal}")
            ruta_imatge = ruta_temporal

        base64_image = self._codificar_imatge_base64(ruta_imatge)
        return base64_image, ruta_temporal

    def _netejar_fitxer_temporal(self, ruta_temporal):
        """Elimina el fitxer temporal si existeix."""
        if ruta_temporal and os.path.exists(ruta_temporal):
            try:
                os.remove(ruta_temporal)
                self.logger.debug(f"Fitxer temporal eliminat: {ruta_temporal}")
            except OSError as e:
                self.logger.warning(f"No s'ha pogut eliminar fitxer temporal: {e}")

    @mesurar_temps("processament_ocr")
    def processar_imatge_ocr(self, ruta_imatge, idioma='cat+spa'):
        """OCR Local amb Tesseract"""
        self.logger.info(f"Processant amb OCR: {ruta_imatge} (idioma: {idioma})")
        try:
            imatge = Image.open(ruta_imatge)
            text = pytesseract.image_to_string(imatge, lang=idioma)
            self.logger.info(f"OCR completat: {len(text)} caràcters extrets")
            self.logger.debug(f"Text OCR (primers 200 chars): {text[:200]}...")
            return text
        except Exception as e:
            self.logger.error(f"Error en OCR: {e}")
            raise

    @mesurar_temps("processament_openai")
    def processar_amb_openai(self, ruta_imatge, text_ocr=None):
        """Implementació real d'OpenAI Vision per extreure JSON estructurat."""
        self.logger.info(f"Processant amb OpenAI: {ruta_imatge}")

        if not self.client:
            self.logger.error("Intent de processar sense API key configurada")
            return {"error": "API Key no configurada al fitxer .env o a la interfície."}

        ruta_temporal = None
        try:
            base64_image, ruta_temporal = self._preparar_imatge_per_api(ruta_imatge)
        except ValueError as e:
            self.logger.error(f"Error preparant imatge: {e}")
            return {"error": str(e)}

        model = os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
        self.logger.debug(f"Enviant petició a OpenAI (model: {model})")

        try:
            resposta = self.client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": self.PROMPT_SISTEMA},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                            },
                        ],
                    }
                ],
                max_tokens=1000,
                response_format={"type": "json_object"}
            )

            contingut = resposta.choices[0].message.content
            tokens_in = resposta.usage.prompt_tokens
            tokens_out = resposta.usage.completion_tokens

            self.logger.info(f"OpenAI resposta rebuda: tokens_in={tokens_in}, tokens_out={tokens_out}")

            if hasattr(self, 'registrar_cost'):
                self.registrar_cost(model, tokens_in, tokens_out)

            resultat = json.loads(contingut)
            self.logger.debug(f"JSON parsejat correctament: {list(resultat.keys())}")
            return resultat

        except Exception as e:
            self.logger.error(f"Error en crida a OpenAI: {e}", exc_info=True)
            return {"error": f"Error en la crida a OpenAI: {str(e)}"}

        finally:
            self._netejar_fitxer_temporal(ruta_temporal)
    
    @mesurar_temps("processament_ollama")
    def processar_amb_ollama(self, ruta_imatge):
        """Processament mitjançant Ollama Local (Gratuït i Privat)."""
        self.logger.info(f"Processant amb Ollama: {ruta_imatge}")

        ruta_temporal = None
        try:
            base64_image, ruta_temporal = self._preparar_imatge_per_api(ruta_imatge)
        except ValueError as e:
            self.logger.error(f"Error preparant imatge per Ollama: {e}")
            return {"error": str(e)}

        model = os.getenv("OLLAMA_MODEL") or "llama3.2-vision"
        self.logger.debug(f"Enviant petició a Ollama (model: {model})")

        try:
            resposta = self.client_ollama.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": self.PROMPT_SISTEMA},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                            },
                        ],
                    }
                ],
                response_format={"type": "json_object"}
            )

            resultat = json.loads(resposta.choices[0].message.content)
            self.logger.info(f"Ollama resposta rebuda correctament")
            self.logger.debug(f"JSON parsejat: {list(resultat.keys())}")
            return resultat

        except Exception as e:
            self.logger.error(f"Error en crida a Ollama: {e}", exc_info=True)
            return {"error": f"Ollama no respon: {str(e)}. Revisa si el servidor està actiu."}

        finally:
            self._netejar_fitxer_temporal(ruta_temporal)

class TranscriptorAmbCostos(TranscriptorTiquets):
    def __init__(self, api_key=None):
        super().__init__(api_key)
        from utils import CalculadoraCostos
        self.gestor_costos = CalculadoraCostos()
        # Preus per 1M de tokens
        self.preus = {"gpt-4o-mini": {"input": 0.15 / 1e6, "output": 0.60 / 1e6}}
        self.logger.info("TranscriptorAmbCostos inicialitzat amb seguiment de costos")

    def registrar_cost(self, model, tokens_in, tokens_out):
        if model not in self.preus:
            self.logger.warning(f"Model {model} no té preus definits, usant gpt-4o-mini")
            model = "gpt-4o-mini"

        cost = (tokens_in * self.preus[model]["input"]) + (tokens_out * self.preus[model]["output"])
        self.gestor_costos.registrar_transaccio(model, tokens_in, tokens_out, cost)
        self.logger.debug(f"Cost registrat: ${cost:.6f}")
        return cost