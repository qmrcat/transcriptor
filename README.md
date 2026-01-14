# 🧾 Transcriptor de Tiquets i Factures

Aplicació professional per a la digitalització de documents de compra mitjançant OCR local i Intel·ligència Artificial (OpenAI Vision).

## ✨ Característiques
- **Multi-mètode:** Tesseract (Offline), OpenAI Vision (Núvol), o Híbrid.
- **Formats:** JPG, PNG, WEBP, GIF i PDF.
- **Privacitat:** Suport per a models locals via Ollama/LM Studio.
- **Control de Costos:** Seguiment detallat de la despesa de l'API.

## 🚀 Instal·lació en Windows
1. Instal·la [Python 3.10+](https://www.python.org/).
2. Instal·la [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki).
3. Descarrega [Poppler](https://github.com/oschwartz10612/poppler-windows/releases) i afegeix-lo al PATH.
4. Executa `iniciar.bat`.

## 🛠️ Configuració
Crea un fitxer `.env` basat en `.env.example` i afegeix la teva `OPENAI_API_KEY`.


## 🧾 Transcriptor de Tiquets Pro (IA + OCR)

Una eina avançada de digitalització per a la gestió de despeses que utilitza Intel·ligència Artificial (OpenAI Vision) i OCR local (Tesseract) per extreure dades estructurades de tiquets i factures amb precisió professional.
✨ Característiques Principals
🖥️ Interfície d'Usuari Avançada

    Suport Multi-format: Processa imatges (JPG, PNG, WebP) i fitxers PDF.

    Drag & Drop: Arrossega fitxers directament a l'aplicació o fes servir el botó de càrrega manual.

    Previsualització Interactiva:

        Zoom dinàmic: Fins al 500% per llegir la lletra més petita.

        Navegació de PDF: Botons per passar pàgines en documents multi-pàgina.

        Scroll amb ratolí: Navegació fluida amb la roda del ratolí i suport per a Ctrl + Roda per fer zoom.

## 🧠 Intel·ligència d'Extracció

    Mode IA (OpenAI Vision): Extreu automàticament l'establiment, NIF, data, impostos detallats i desglossament d'articles en format JSON.

    Mode OCR Local: Processament ràpid i gratuït mitjançant Tesseract OCR per a extraccions de text simple.

    Exportació a Excel: Converteix el JSON analitzat en un full de càlcul .xlsx amb un sol clic.

## 💰 Gestió i Control

    Monitor de Costos: Script dedicat per controlar la despesa real de l'API d'OpenAI i fer estimacions de pressupost.

    Seguretat: Gestió de claus API mitjançant variables d'entorn (.env).

## 🚀 Instal·lació
1. Requisits del sistema

    Python 3.10+

    Tesseract OCR: Descarregar aquí.

    Poppler (per a PDFs): Descarregar binaris i afegir la carpeta bin al PATH.

2. Clonar i instal·lar dependències
Bash

git clone https://github.com/el-teu-usuari/transcriptor-tiquets.git
cd transcriptor-tiquets
pip install -r requirements.txt

3. Configuració

Crea un fitxer .env a l'arrel del projecte:
Fragment de codi

OPENAI_API_KEY=la_teva_clau_aquí

## 🛠️ Estructura del Projecte
Fitxer	Descripció
main.py	Punt d'entrada de l'aplicació.
gui.py	Tota la lògica de la interfície gràfica (Tkinter/CustomTkinter).
logic.py	Integració amb OpenAI Vision i Tesseract OCR.
utils.py	Gestor de configuració i registre d'historial de costos.
consultar_costos_openai.py	Eina d'auditoria de despeses.
exemple_us.py	Script per al processament automatitzat per lots.

## 📖 Com s'utilitza

    Execució: Llença l'aplicació amb python main.py.

    Càrrega: Arrossega un tiquet al panell esquerre.

    Ajust: Fes zoom o navega per les pàgines si és un PDF.

    Processament: Tria el mètode (IA o OCR) i prem Analitzar.

    Validació: Revisa el JSON generat al panell dret (pots editar-lo manualment).

    Exportació: Prem el botó Excel per desar la informació estructurada.

## 🔒 Privacitat i Costos

Aquesta eina permet l'ús de models locals (via BASE_URL a l'API) per a màxima privacitat. Per defecte, el mètode OpenAI utilitza el model gpt-4o-mini, optimitzat per a una alta precisió amb el cost més baix possible.