# Transcriptor de Tiquets Pro

Eina de digitalització de tiquets, factures i albarans que extreu dades estructurades mitjançant **IA (OpenAI Vision, Claude/Anthropic, Ollama)** i **OCR local (Tesseract)**. Inclou interfície gràfica amb CustomTkinter, editor visual de JSON, persistència en SQLite i una aplicació de manteniment de base de dades.

## Característiques

### Interficie grafica (gui.py)

- **Multi-format**: imatges (JPG, PNG, WebP) i PDF multi-pagina.
- **Drag & Drop**: arrossega fitxers al canvas o carrega manualment.
- **Previsualitzacio interactiva**: zoom fins al 500%, scroll amb roda del ratoli, `Ctrl+Roda` per zoom, navegacio de pagines PDF amb lazy loading i cache.
- **4 metodes d'extraccio**: OCR local (Tesseract), OpenAI Vision, Claude/Anthropic, Ollama (LLM local).
- **Instruccions addicionals**: camp de text per personalitzar el prompt enviat a la IA.
- **Editor visual de JSON**: edicio de capcalera, articles i impostos amb formulari grafic.
- **Exportacio**: copiar al porta-retalls, exportar a Excel (.xlsx).
- **Desar a BD**: validacio de camps i deteccio de duplicats abans d'inserir a SQLite.
- **Gestio de plantilles**: desar/carregar/eliminar configuracions de metode, model i instruccions.
- **Boto Manteniment BD**: obre l'aplicacio de manteniment de base de dades directament des de la GUI principal.
- **Notificacio sonora**: so al finalitzar el processament (configurable).

### Manteniment de base de dades (manteniment_bd.py)

Aplicacio autonoma per gestionar els registres de transcripcions desats a SQLite.

- **Taula de registres**: visualitzacio amb seleccio multiple (checkboxes), files alternades, doble clic per veure detalls.
- **CRUD complet**: crear, veure, editar i eliminar registres.
- **Editor JSON integrat**: formulari visual amb modes crear/editar/veure (nomes lectura).
- **Cerca**: per text lliure o filtrat per columna especifica (Establiment, NIF, Factura, Document).
- **Paginacio**: 25, 50 o 100 registres per pagina amb navegacio.
- **Exportacio JSON**: registres seleccionats amb `contingutJSON` parsejat com a objecte.
- **Exportacio CSV**: camps de BD + camps extrets del JSON (forma_pagament, data_document, num_articles), delimitador `;`, codificacio UTF-8 amb BOM.
- **Barra d'estat**: total de registres, seleccionats, fitxer de BD actiu.

### Logica de processament (logic.py)

- `TranscriptorTiquets`: classe base amb `processar_imatge_ocr()`, `processar_amb_openai()`, `processar_amb_claude()`, `processar_amb_ollama()`.
- `TranscriptorAmbCostos`: hereda de la base i afegeix seguiment de costos per transaccio.
- Prompt estructurat que retorna JSON amb: establiment, NIF, numero de factura, data, hora, total, forma de pagament, articles (descripcio, quantitat, preu, imports, IVA) i impostos.

### Utilitats (utils.py)

- `GestorLogging`: logging centralitzat amb rotacio, compressio gzip, format JSON opcional, metriques i decorador `@mesurar_temps`.
- `GestorConfiguracio`: carrega/desa configuracio des de `config.json` i `.env`.
- `GestorPlantilles`: gestio de plantilles de documents a `plantilles.json`.
- `CalculadoraCostos`: registre d'historial de costos API a `historial_costos.json`.
- `GestorBaseDades`: persistencia SQLite amb CRUD complet, cerca amb filtre per columna, paginacio i deteccio de duplicats.

## Estructura del projecte

| Fitxer | Descripcio |
|--------|------------|
| `main.py` | Punt d'entrada: parseja arguments CLI, obre la GUI si no n'hi ha |
| `gui.py` | Interficie grafica amb drag-drop, zoom, editor JSON, desar a BD |
| `logic.py` | Processament OCR, OpenAI, Claude i Ollama |
| `utils.py` | Configuracio, logging, plantilles, costos, base de dades |
| `services/transcription_service.py` | Capa de servei per orquestrar mètodes de transcripció |
| `services/storage_service.py` | Capa de servei per persistència i gestió d'errors de duplicat |
| `ui/json_form_utils.py` | Construcció/normalització compartida de JSON des de formularis |
| `ui/pdf_viewer_mixin.py` | Mixin UI per previsualització d'imatges/PDF, zoom i navegació |
| `ui/processing_actions_mixin.py` | Mixin UI per processament, cronòmetre, cancel·lació i exportació |
| `ui/template_editor_mixin.py` | Mixin UI per gestió de plantilles i editor visual de JSON |
| `manteniment_bd.py` | App autonoma de manteniment CRUD de la BD de transcripcions |
| `consultar_costos_openai.py` | Eina CLI d'auditoria de costos d'API |
| `exemple_us.py` | Script d'exemple per processament per lots |

## Installacio

### Requisits del sistema

- **Python 3.10+**
- **Tesseract OCR**: [descarregar](https://github.com/UB-Mannheim/tesseract/wiki)
- **Poppler** (per a PDFs): [descarregar binaris](https://github.com/oschwartz10612/poppler-windows/releases) i afegir `bin` al PATH
- **Ollama** (opcional): per a processament amb LLM local

### Installacio de dependencies

```bash
pip install -r requirements.txt
```

### Configuracio

Crea un fitxer `.env` a l'arrel del projecte:

```env
# API Keys
OPENAI_API_KEY=la_teva_clau
OPENAI_MODEL=gpt-4o-mini
ANTHROPIC_API_KEY=la_teva_clau
ANTHROPIC_MODEL=claude-sonnet-4-20250514

# OCR
TESSERACT_PATH=C:/Program Files/Tesseract-OCR/tesseract.exe
DEFAULT_LANGUAGE=cat+spa

# Ollama (opcional)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2-vision

# Altres
ENABLE_SOUND=TRUE
```

## Us

### GUI principal

```bash
python main.py
```

1. Arrossega un tiquet o factura al panell esquerre (o prem "Obrir fitxer...").
2. Selecciona el metode d'extraccio (OCR, OpenAI, Claude, Ollama).
3. Opcionalment, escriu instruccions addicionals o selecciona una plantilla.
4. Prem **Analitzar Document**.
5. Revisa el JSON al panell dret; edita'l amb el boto **Editar** si cal.
6. Exporta a Excel, copia al porta-retalls o desa a la base de dades amb **Desar BD**.
7. Obre **Manteniment BD** per gestionar els registres desats.

### Manteniment de base de dades

```bash
python manteniment_bd.py
```

O des de la GUI principal amb el boto **Manteniment BD**.

### CLI

```bash
# OCR
python main.py imatge.jpg --metode ocr --idioma cat+spa

# OpenAI Vision
python main.py factura.pdf --metode openai --api-key CLAU --sortida resultat.json

# Processament per lots
python exemple_us.py
```

### Auditoria de costos

```bash
python consultar_costos_openai.py
```

## Persistencia de dades

| Fitxer/BD | Contingut |
|-----------|-----------|
| `transcripcions.db` | Base de dades SQLite amb transcripcions |
| `config.json` | Configuracio de l'aplicacio |
| `plantilles/plantilles.json` | Plantilles de documents |
| `historial_costos.json` | Historial de costos d'API |
| `logs/` | Fitxers de log amb rotacio |

## Dependencies

- `customtkinter` - GUI moderna
- `Pillow` - Manipulacio d'imatges
- `pytesseract` - OCR local
- `pdf2image` - Conversio PDF a imatge
- `openai` - API OpenAI Vision
- `anthropic` - API Claude/Anthropic
- `python-dotenv` - Variables d'entorn
- `tkinterdnd2-universal` - Drag & Drop
- `pandas` - Exportacio Excel
- `pygame` - Notificacions sonores
