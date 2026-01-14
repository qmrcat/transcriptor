Automatització: Pots processar carpetes senceres mitjançant un script de bash o PowerShell cridant a python main.py carpeta/*.jpg.

Millora de precisió: Per a tiquets molt arrugats, utilitza el mètode openai directament, ja que és més robust que l'OCR tradicional davant de distorsions.

📄 GUIA_AVANCADA.md
🚀 Guia Avançada del Transcriptor de Tiquets

Aquest document detalla configuracions tècniques per a optimitzar el rendiment, estalviar costos i automatitzar el processament.
🏠 1. Ús de IAs en Local (Ollama / LM Studio)

Si vols privacitat total i cost zero per tiquet, pots utilitzar models de llenguatge en local. L'aplicació és compatible amb qualsevol servei que exposi una API compatible amb OpenAI.
Passos per a Ollama:

    Instal·la Ollama des de ollama.com.

    Descarrega un model Vision: Recomanem llama3-vision o llava.
    Bash

    ollama run llama3-vision

    Configura l'aplicació:

        Obre el fitxer .env.

        Canvia la BASE_URL a http://localhost:11434/v1.

        Al codi de logic.py, assegura't que el model seleccionat sigui el que has descarregat.

🛠️ 2. Preprocessament d'Imatges (Millora d'OCR)

L'OCR local (Tesseract) pot fallar si la il·luminació és dolenta. Pots millorar la precisió afegint aquestes tècniques a logic.py abans de passar la imatge al transcriptor:

    Escala de grisos: Elimina soroll de color.

    Binarització (Thresholding): Converteix la imatge a blanc i negre pur per ressaltar el text.

    Correcció de rotació (Deskewing): Redreça tiquets que s'han escanejat torts.

📊 3. Integració amb Bases de Dades

Si vols guardar els tiquets directament en una base de dades (SQLite o PostgreSQL), pots estendre la funció _exportar_excel a gui.py:
Python

import sqlite3

def desar_a_db(dades):
    conn = sqlite3.connect("comptabilitat.db")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS factures 
        (establiment TEXT, data TEXT, total REAL)''')
    cursor.execute("INSERT INTO factures VALUES (?, ?, ?)", 
        (dades['establiment'], dades['data'], dades['total']))
    conn.commit()
    conn.close()

🤖 4. Automatització i Processament per Lots

L'script exemple_us.py es pot programar com una Tasca Programada de Windows (Task Scheduler) per processar una carpeta cada nit a les 00:00.

    Crea un fitxer .bat que executi el teu entorn virtual i l'script.

    Configura la tasca de Windows perquè executi el .bat.

    Tots els tiquets que hagis escanejat durant el dia apareixeran digitalitzats l'endemà al matí.

📉 5. Optimització de Costos (OpenAI)

Per a empreses amb gran volum de factures, recomanem el flux Híbrid:

    Filtre OCR Local: Executa Tesseract primer.

    Validació: Si Tesseract extreu el "Total" amb claredat, no enviïs la imatge a OpenAI.

    IA com a Suport: Envia a OpenAI només aquells tiquets on l'OCR local hagi donat una confiança baixa o dades incompletes.

⚠️ Solució de Problemes Freqüents
Problema	Solució
TesseractNotFoundError	Comprova que el camí a tesseract.exe és correcte a logic.py o al PATH del sistema.
Error Poppler	Necessari per a PDFs. Descarrega els binaris de Poppler i afegeix la carpeta bin a les variables d'entorn.
Lentitud en OpenAI	Comprova la teva connexió. El model gpt-4o-mini és el més ràpid; evita models més grans si no és necessari.

Necessites ajuda per implementar la connexió específica amb una base de dades SQL o prefereixes que revisem algun punt de la instal·lació de Poppler?