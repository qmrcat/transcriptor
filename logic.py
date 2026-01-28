import pytesseract
from PIL import Image
import pdf2image
import json
import os
import base64
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

class TranscriptorTiquets:
    def __init__(self, api_key=None, base_url=None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        # Permet Ollama/LM Studio o OpenAI oficial
        self.client = OpenAI(api_key=self.api_key, base_url=base_url) if self.api_key else None

        # Client per Ollama (IA Local)
        # Per defecte Ollama escolta al port 11434
        self.client_ollama = OpenAI(
            base_url=os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434/v1",
            api_key="ollama" # Ollama no necessita clau real, però la llibreria la demana
        )

    def _codificar_imatge_base64(self, ruta_imatge):
        """Converteix un fitxer d'imatge en una cadena Base64 per a l'API."""
        with open(ruta_imatge, "rb") as fitxer_imatge:
            return base64.b64encode(fitxer_imatge.read()).decode('utf-8')

    def processar_imatge_ocr(self, ruta_imatge, idioma='cat+spa'):
        """OCR Local amb Tesseract"""
        imatge = Image.open(ruta_imatge)
        text = pytesseract.image_to_string(imatge, lang=idioma)
        return text

    def processar_amb_openai(self, ruta_imatge, text_ocr=None):
        """Implementació real d'OpenAI Vision per extreure JSON estructurat."""
        if not self.client:
            return {"error": "API Key no configurada al fitxer .env o a la interfície."}

        # Si és un PDF, el convertim a imatge primer (només la primera pàgina per a Vision)
        if ruta_imatge.lower().endswith(".pdf"):
            pagines = pdf2image.convert_from_path(ruta_imatge)
            ruta_temporal = "temp_vision.jpg"
            pagines[0].save(ruta_temporal, "JPEG")
            ruta_imatge = ruta_temporal

        base64_image = self._codificar_imatge_base64(ruta_imatge)

        # prompt_sistema = """Ets un expert en comptabilitat i digitalització de documents. 
        # Analitza la imatge del tiquet/albara/factura i retorna EXCLUSIVAMENT un objecte JSON amb el següent format:
        # {
        #   "establiment": "Nom", "nifEstabliment": "CIF/NIF", "numeroFacturaRebutTiquet": "ID",
        #   "data": "DD/MM/YYYY", "hora": "HH:MM", "total": "0.00 €",
        #   "impostos": [{"percentatgeIVA": "21%", "importBaseIVA": "0.00", "quotaIVA": "0.00"}],
        #   "articles": [{"descripció": "Producte/article", "quantitat": 1, "preu": "0.00 €", "importBase": "00.0", "percentatgeIVA": "00%", "importIVA": "0.00", "importTotal": "0.00"}],
        #   "forma_pagament": "Targeta/Efectiu"
        # }
        # Si no trobes alguna dada, posa null. No afegeixis text explicatiu.
        # Aclariments:
        # - "data" ha d'estar en format DD/MM/YYYY.
        # - A vegades els tiquets no tenen NIF o desglossament d'IVA, posa null en aquests camps.
        # - Si hi ha diversos tipus d'IVA, inclou-los tots a l'array "impostos", a vegades s'inclou un total dels impostos, no ho afegeixis.
        # - L'array "articles" ha de contenir tots els productes/serveis detallats al tiquet, a vegades la columna 'preu' li poden dir 'base'.
        # - La "forma_pagament" ha de ser una cadena curta indicant com s'ha pagat (Targeta, Efectiu, etc.).
        # - Els tiquet poden estar en català, castellà o barrejat, català i castellà.
        # - La columna "descripció" pot aparèixer com "descripcio", "concepte", "detall", "Producte", "article" o "nom". Aquesta pot estar separada (no sempre) en una fila.
        # - La columna "quantitat" pot aparèixer com "cant", "unitats", "uni", "quntitat", "QT", "qty" o no apareixer.
        # - La columna "preu" al tiquet pot aparèixer com a "preu", "precio", "PVP" o "base".
        # - La columna "importBase" pot aparèixer com a "base", "import base", "importe base" o "subtotal". Aquesta columna pot no aparèixer.
        # - La columna "percentatgeIVA" pot aparèixer com a "%IVA", "tipus IVA", "% IVA" o "%". Aquesta columna pot no aparèixer.
        # - La columna "quotaIVA" pot aparèixer com a "IVA", "I.V.A.", "quota IVA" o "import IVA". Aquesta columna pot no aparèixer.
        # - La columna "importTotal" pot aparèixer com a "total", "import", "Import total" o "total article". Aquesta columna és el total de l'article amb IVA inclòs, també pot no aparèixer, perquè solament es mostri l'import base.
        # - En algun cas, els articles estant en dues files (descripció i total en una fila, quantitat i preu en una altra), no sempre segueix aquest ordre, intenta combinar-los correctament.
        # - Algunes columnes poden que no tinguin títol, identifica-les pel contingut, o no apareguin.
        # - En alguns tiquet poden tenir una linia separa per alguns articles amb un text explicatiu (ex: "oferta especial", "promoció", "descompte client fidel", "pasta sense gluten", etc.), ignora aquestes línies.
        # - En alguns casos, la quantitat i el preu poden estar junts en la mateixa columna, separats per una "x" (ex: "2 x 3.50") "quantitat x preu", davant de la 'x' poden portar escrit 'unitats', 'unidades' o una paraula similar, separa'ls correctament.
        # - Tambe pot ser que el preu porti l'IVA inclòs, calcula l'import base i la quota d'IVA segons el percentatge indicat al tiquet, si no s'hi indica el percentatge d'IVA, posa null en els caps corresponents, pot ser que el tiquet indiqui en algun lloc, "IVA inclòs", "Impostos inclosos" o alguna cosa semblant.
        # - Recorda que en català o castellà la separació decimal és amb coma, però en l'anglès és amb punt, retorna sempre els imports amb coma.
        # """
        prompt_sistema = """Ets un expert en comptabilitat i digitalització de documents.

Analitza la imatge d’un tiquet, albarà o factura i retorna EXCLUSIVAMENT un objecte JSON.
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
- Els percentatges d’IVA han de ser strings amb el símbol % (ex: "21%").
- La quantitat ha de ser numèrica (sense cometes).
- Si un camp concret d’un article no es pot determinar, posa null només en aquell camp.
- Si no hi ha articles detallats, retorna l’array "articles" buit.

Aclariments importants:
- "data" ha d’estar en format DD/MM/YYYY.
- Els tiquets poden estar en català, castellà o barrejats.
- A vegades els tiquets no tenen NIF o desglossament d’IVA: posa null en aquests camps.
- Si hi ha diversos tipus d’IVA, inclou-los tots a l’array "impostos".
- No afegeixis totals globals d’impostos si ja apareixen desglossats.
- L’array "articles" ha de contenir tots els productes o serveis detallats.

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
- La quantitat i el preu poden aparèixer junts (ex: "2 x 3,50"), davant de la 'x' poden portar escrit 'unitats', 'unidades' o una paraula similar, en alguns casos la 'x' pot estar enganxada a la quantitat (2x) i un separador amb un caràcter ('@', '=', '#', ...). Separa correctament quantitat i preu.
- Si el preu inclou IVA:
    - Només calcula import base i quota d’IVA si el percentatge d’IVA apareix explícitament al tiquet.
    - Si no apareix el percentatge, posa null als camps relacionats amb IVA encara que indiqui "IVA inclòs".
- La separació decimal pot ser amb coma o punt segons l’idioma del tiquet, però retorna sempre els imports amb coma.

La "forma_pagament" ha de ser una cadena curta indicant el mètode de pagament (Targeta, Efectiu, Bizum, Transferència, etc.).
"""

        try:
            resposta = self.client.chat.completions.create(
                # model="gpt-4o-mini", # Model més ràpid i econòmic per a visió
                model=os.getenv("OPENAI_MODEL") or "gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt_sistema},
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
            
            # Extraure el resultat i els tokens per al seguiment de costos
            contingut = resposta.choices[0].message.content
            tokens_in = resposta.usage.prompt_tokens
            tokens_out = resposta.usage.completion_tokens
            
            # Si estem en la classe de costos, registrarem la transacció
            if hasattr(self, 'registrar_cost'):
                self.registrar_cost("gpt-4o-mini", tokens_in, tokens_out)

            return json.loads(contingut)

        except Exception as e:
            return {"error": f"Error en la crida a OpenAI: {str(e)}"}
    
    def processar_amb_ollama(self, ruta_imatge):
        """Processament mitjançant Ollama Local (Gratuït i Privat)."""
        base64_image = self._codificar_imatge_base64(ruta_imatge)
        
        prompt_sistema = "Analitza aquest tiquet i retorna un JSON amb: establiment, data, total i articles."
        
        try:
            resposta = self.client_ollama.chat.completions.create(
                # model="llama3-vision", # Assegura't de tenir-lo descarregat: 'ollama pull llama3-vision'
                model=os.getenv("OLLAMA_MODEL") or "llama3-vision",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt_sistema},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                            },
                        ],
                    }
                ],
                response_format={"type": "json_object"}
            )
            return json.loads(resposta.choices[0].message.content)
        except Exception as e:
            return {"error": f"Ollama no respon: {str(e)}. Revisa si el servidor està actiu."}

class TranscriptorAmbCostos(TranscriptorTiquets):
    def __init__(self, api_key=None):
        super().__init__(api_key)
        from utils import CalculadoraCostos
        self.gestor_costos = CalculadoraCostos()
        # Preus per 1M de tokens
        self.preus = {"gpt-4o-mini": {"input": 0.15 / 1e6, "output": 0.60 / 1e6}}

    def registrar_cost(self, model, tokens_in, tokens_out):
        cost = (tokens_in * self.preus[model]["input"]) + (tokens_out * self.preus[model]["output"])
        self.gestor_costos.registrar_transaccio(model, tokens_in, tokens_out, cost)
        return cost