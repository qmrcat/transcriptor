from utils import FormatTranscripcio


def construir_json_transcripcio(entries_capcalera, files_articles, files_impostos):
    """Construeix un JSON de transcripció des de widgets de formulari."""
    resultat = {}

    for camp, entry in entries_capcalera.items():
        valor = _valor_entry(entry)
        if camp == "total":
            valor = FormatTranscripcio.normalitzar_import(valor)
        resultat[camp] = valor if valor else None

    articles = []
    for _, entries in files_articles:
        article = {}
        for camp, entry in entries.items():
            valor = _valor_entry(entry)
            if camp == "quantitat":
                valor = FormatTranscripcio.parsejar_quantitat(valor)
            elif camp in ("preu", "importBase", "importIVA", "importTotal"):
                valor = FormatTranscripcio.normalitzar_import(valor)
            elif camp == "percentatgeIVA":
                valor = FormatTranscripcio.normalitzar_percentatge(valor)
            article[camp] = valor if valor else None
        articles.append(article)
    resultat["articles"] = articles

    impostos = []
    for _, entries in files_impostos:
        impost = {}
        for camp, entry in entries.items():
            valor = _valor_entry(entry)
            if camp in ("importBaseIVA", "quotaIVA"):
                valor = FormatTranscripcio.normalitzar_import(valor)
            elif camp == "percentatgeIVA":
                valor = FormatTranscripcio.normalitzar_percentatge(valor)
            impost[camp] = valor if valor else None
        impostos.append(impost)
    resultat["impostos"] = impostos

    return resultat


def _valor_entry(entry):
    valor = entry.get()
    return valor.strip() if isinstance(valor, str) else valor

