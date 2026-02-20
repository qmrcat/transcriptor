"""
Aplicació de Manteniment de Base de Dades de Transcripcions.

Permet consultar, crear, editar, eliminar i exportar registres
de la base de dades SQLite de transcripcions.

Execució:
    python manteniment_bd.py
"""

import customtkinter as ctk
from tkinter import filedialog, messagebox
import json
import os
import csv
import math
from datetime import datetime

from utils import GestorBaseDades, GestorLogging


# =============================================================================
# EDITOR JSON - Clonat i adaptat de gui.py
# =============================================================================

class EditorJSON(ctk.CTkToplevel):
    """
    Editor visual de JSON per a transcripcions.

    Modes:
        - "crear": Formulari buit per crear un registre nou.
        - "editar": Formulari pre-omplert per editar un registre existent.
        - "veure": Formulari en només lectura.
    """

    def __init__(self, parent, mode="veure", dades_json=None, dades_bd=None, on_desar=None):
        """
        Args:
            parent: Finestra pare.
            mode: "crear", "editar" o "veure".
            dades_json: Dict amb el contingut JSON parsejat (articles, impostos, etc.).
            dades_bd: Dict amb camps de BD (nom, nif, factura, total, nomDocument).
            on_desar: Callback(dades_bd, dades_json) cridat al desar.
        """
        super().__init__(parent)

        self.mode = mode
        self.on_desar = on_desar
        self.dades_json = dades_json or {}
        self.dades_bd = dades_bd or {}

        titols = {"crear": "Nou Registre", "editar": "Editar Registre", "veure": "Veure Registre"}
        self.title(titols.get(mode, "Registre"))
        self.geometry("1000x800")
        self.resizable(True, True)
        self.transient(parent)
        self.grab_set()

        # Centrar
        parent.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 1000) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 800) // 2
        self.geometry(f"1000x800+{x}+{y}")

        self.after(50, lambda: self.focus_force())

        # Estructures per widgets
        self.entries_bd = {}
        self.entries_capcalera = {}
        self.files_articles = []
        self.files_impostos = []

        # Contenidor principal amb scroll
        self.scroll_principal = ctk.CTkScrollableFrame(self)
        self.scroll_principal.pack(fill="both", expand=True, padx=10, pady=10)

        self._crear_seccio_bd(self.scroll_principal)
        self._crear_seccio_capcalera(self.scroll_principal)
        self._crear_seccio_articles(self.scroll_principal)
        self._crear_seccio_impostos(self.scroll_principal)
        self._crear_botons(self)

        self.protocol("WM_DELETE_WINDOW", self._tancar)

    def _crear_seccio_bd(self, parent):
        """Camps de base de dades (nom, nif, factura, total, nomDocument)."""
        frame = ctk.CTkFrame(parent)
        frame.pack(fill="x", padx=5, pady=(5, 10))

        ctk.CTkLabel(frame, text="Dades de Base de Dades", font=("Arial", 14, "bold")).pack(
            anchor="w", padx=10, pady=5
        )

        fila = ctk.CTkFrame(frame, fg_color="transparent")
        fila.pack(fill="x", padx=10, pady=5)

        camps = [
            ("nom", "Establiment", 200),
            ("nif", "NIF", 120),
            ("factura", "Factura", 130),
            ("total", "Total", 100),
            ("nomDocument", "Document", 200),
        ]

        for camp, etiqueta, amplada in camps:
            subframe = ctk.CTkFrame(fila, fg_color="transparent")
            subframe.pack(side="left", padx=5)
            ctk.CTkLabel(subframe, text=etiqueta, font=("Arial", 10)).pack(anchor="w")
            entry = ctk.CTkEntry(subframe, width=amplada)
            entry.pack()
            valor = self.dades_bd.get(camp, "") or ""
            entry.insert(0, str(valor))
            if self.mode == "veure":
                entry.configure(state="disabled")
            self.entries_bd[camp] = entry

    def _crear_seccio_capcalera(self, parent):
        """Camps de capçalera del JSON (establiment, data, hora, total, forma_pagament)."""
        frame = ctk.CTkFrame(parent)
        frame.pack(fill="x", padx=5, pady=5)

        ctk.CTkLabel(frame, text="Capçalera JSON", font=("Arial", 14, "bold")).pack(
            anchor="w", padx=10, pady=5
        )

        camps_fila1 = [
            ("establiment", "Establiment", 200),
            ("nifEstabliment", "NIF", 120),
            ("numeroFacturaRebutTiquet", "Número", 120),
            ("data", "Data", 100),
        ]
        camps_fila2 = [
            ("hora", "Hora", 80),
            ("total", "Total", 100),
            ("forma_pagament", "Forma pagament", 150),
        ]

        for camps, fila_parent in [(camps_fila1, frame), (camps_fila2, frame)]:
            fila = ctk.CTkFrame(fila_parent, fg_color="transparent")
            fila.pack(fill="x", padx=10, pady=3)
            for camp, etiqueta, amplada in camps:
                subframe = ctk.CTkFrame(fila, fg_color="transparent")
                subframe.pack(side="left", padx=5)
                ctk.CTkLabel(subframe, text=etiqueta, font=("Arial", 10)).pack(anchor="w")
                entry = ctk.CTkEntry(subframe, width=amplada)
                entry.pack()
                valor = self.dades_json.get(camp, "")
                if valor is not None:
                    entry.insert(0, str(valor))
                if self.mode == "veure":
                    entry.configure(state="disabled")
                self.entries_capcalera[camp] = entry

    def _crear_seccio_articles(self, parent):
        """Secció d'articles amb taula editable."""
        frame = ctk.CTkFrame(parent)
        frame.pack(fill="both", expand=True, padx=5, pady=5)

        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(header, text="Articles", font=("Arial", 14, "bold")).pack(side="left")
        if self.mode != "veure":
            ctk.CTkButton(
                header, text="+ Afegir article", width=120,
                command=self._afegir_fila_article
            ).pack(side="right")

        # Capçaleres de columna
        header_cols = ctk.CTkFrame(frame, fg_color="transparent")
        header_cols.pack(fill="x", padx=10)
        columnes = [
            ("Descripció", 180), ("Quantitat", 70), ("Preu", 80),
            ("Import Base", 80), ("%IVA", 60), ("Import IVA", 80),
            ("Import Total", 80),
        ]
        if self.mode != "veure":
            columnes.append(("", 30))
        for text, amplada in columnes:
            ctk.CTkLabel(header_cols, text=text, font=("Arial", 10, "bold"), width=amplada).pack(
                side="left", padx=2
            )

        self.scroll_articles = ctk.CTkScrollableFrame(frame, height=200)
        self.scroll_articles.pack(fill="both", expand=True, padx=10, pady=5)

        for article in self.dades_json.get("articles", []):
            self._afegir_fila_article(article)

    def _afegir_fila_article(self, dades=None):
        if dades is None:
            dades = {}

        fila = ctk.CTkFrame(self.scroll_articles, fg_color="transparent")
        fila.pack(fill="x", pady=2)

        camps = [
            ("descripció", 180), ("quantitat", 70), ("preu", 80),
            ("importBase", 80), ("percentatgeIVA", 60), ("importIVA", 80),
            ("importTotal", 80),
        ]

        entries = {}
        for camp, amplada in camps:
            entry = ctk.CTkEntry(fila, width=amplada)
            entry.pack(side="left", padx=2)
            valor = dades.get(camp, "")
            if valor is not None:
                entry.insert(0, str(valor))
            if self.mode == "veure":
                entry.configure(state="disabled")
            entries[camp] = entry

        if self.mode != "veure":
            btn = ctk.CTkButton(
                fila, text="X", width=30, fg_color="#e74c3c", hover_color="#c0392b",
                command=lambda f=fila: self._eliminar_fila(f, self.files_articles)
            )
            btn.pack(side="left", padx=2)

        self.files_articles.append((fila, entries))

    def _crear_seccio_impostos(self, parent):
        """Secció d'impostos amb taula editable."""
        frame = ctk.CTkFrame(parent)
        frame.pack(fill="x", padx=5, pady=5)

        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(header, text="Impostos", font=("Arial", 14, "bold")).pack(side="left")
        if self.mode != "veure":
            ctk.CTkButton(
                header, text="+ Afegir impost", width=120,
                command=self._afegir_fila_impost
            ).pack(side="right")

        header_cols = ctk.CTkFrame(frame, fg_color="transparent")
        header_cols.pack(fill="x", padx=10)
        columnes = [("% IVA", 100), ("Import Base IVA", 150), ("Quota IVA", 150)]
        if self.mode != "veure":
            columnes.append(("", 30))
        for text, amplada in columnes:
            ctk.CTkLabel(header_cols, text=text, font=("Arial", 10, "bold"), width=amplada).pack(
                side="left", padx=5
            )

        self.frame_impostos = ctk.CTkFrame(frame, fg_color="transparent")
        self.frame_impostos.pack(fill="x", padx=10, pady=5)

        for impost in self.dades_json.get("impostos", []):
            self._afegir_fila_impost(impost)

    def _afegir_fila_impost(self, dades=None):
        if dades is None:
            dades = {}

        fila = ctk.CTkFrame(self.frame_impostos, fg_color="transparent")
        fila.pack(fill="x", pady=2)

        camps = [("percentatgeIVA", 100), ("importBaseIVA", 150), ("quotaIVA", 150)]

        entries = {}
        for camp, amplada in camps:
            entry = ctk.CTkEntry(fila, width=amplada)
            entry.pack(side="left", padx=5)
            valor = dades.get(camp, "")
            if valor is not None:
                entry.insert(0, str(valor))
            if self.mode == "veure":
                entry.configure(state="disabled")
            entries[camp] = entry

        if self.mode != "veure":
            btn = ctk.CTkButton(
                fila, text="X", width=30, fg_color="#e74c3c", hover_color="#c0392b",
                command=lambda f=fila: self._eliminar_fila(f, self.files_impostos)
            )
            btn.pack(side="left", padx=5)

        self.files_impostos.append((fila, entries))

    def _eliminar_fila(self, fila, llista):
        for i, (f, _) in enumerate(llista):
            if f == fila:
                fila.destroy()
                del llista[i]
                break

    def _crear_botons(self, parent):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", padx=15, pady=10)

        if self.mode != "veure":
            ctk.CTkButton(
                frame, text="Desar", width=120,
                fg_color="#2ecc71", hover_color="#27ae60",
                command=self._desar
            ).pack(side="left", padx=10)

        ctk.CTkButton(
            frame, text="Tancar" if self.mode == "veure" else "Cancel\u00b7lar",
            width=120, fg_color="#e74c3c", hover_color="#c0392b",
            command=self._tancar
        ).pack(side="right", padx=10)

    def _construir_json(self):
        """Recull els valors del formulari i retorna el dict JSON."""
        resultat = {}

        for camp, entry in self.entries_capcalera.items():
            valor = entry.get().strip()
            if camp == "total" and valor:
                try:
                    valor = float(valor.replace(",", "."))
                except ValueError:
                    pass
            resultat[camp] = valor if valor else None

        articles = []
        for _, entries in self.files_articles:
            article = {}
            for camp, entry in entries.items():
                valor = entry.get().strip()
                if camp in ("quantitat", "preu", "importBase", "percentatgeIVA", "importIVA", "importTotal") and valor:
                    try:
                        valor = float(valor.replace(",", "."))
                    except ValueError:
                        pass
                article[camp] = valor if valor else None
            articles.append(article)
        resultat["articles"] = articles

        impostos = []
        for _, entries in self.files_impostos:
            impost = {}
            for camp, entry in entries.items():
                valor = entry.get().strip()
                if valor:
                    try:
                        valor = float(valor.replace(",", "."))
                    except ValueError:
                        pass
                impost[camp] = valor if valor else None
            impostos.append(impost)
        resultat["impostos"] = impostos

        return resultat

    def _recollir_dades_bd(self):
        """Recull els camps de BD del formulari."""
        dades = {}
        for camp, entry in self.entries_bd.items():
            valor = entry.get().strip()
            if camp == "total" and valor:
                try:
                    valor = float(valor.replace(",", "."))
                except ValueError:
                    pass
            dades[camp] = valor if valor else None
        return dades

    def _desar(self):
        dades_bd = self._recollir_dades_bd()
        dades_json = self._construir_json()

        if not dades_bd.get("nom"):
            messagebox.showwarning("Atenció", "El camp Establiment és obligatori.", parent=self)
            return

        if self.on_desar:
            self.on_desar(dades_bd, dades_json)
        self._tancar()

    def _tancar(self):
        self.grab_release()
        self.destroy()


# =============================================================================
# TAULA DE TRANSCRIPCIONS
# =============================================================================

class TaulaTranscripcions(ctk.CTkFrame):
    """Taula de registres amb selecció múltiple i paginació."""

    # Definició de columnes: (nom_capçalera, clau_registre, amplada_pixels)
    COLUMNES = [
        ("ID", "id", 50),
        ("Establiment", "nom", 180),
        ("NIF", "nif", 120),
        ("Factura", "factura", 130),
        ("Total", "total", 80),
        ("Document", "nomDocument", 170),
        ("Data", "dataAlta", 140),
    ]
    COL_CHECKBOX_AMPLADA = 40

    def __init__(self, parent, on_doble_clic=None):
        super().__init__(parent)
        self.on_doble_clic = on_doble_clic
        self.files_widgets = []  # [(frame, checkbox_var, registre_dict), ...]
        self.registres_actuals = []
        self.columna_ordenacio = None  # clau de la columna ordenada
        self.ordre_ascendent = True
        self.labels_capcalera = {}  # clau -> CTkLabel

        self._crear_capcalera()

        self.scroll_frame = ctk.CTkScrollableFrame(self)
        self.scroll_frame.pack(fill="both", expand=True)

    def _configurar_grid_fila(self, frame):
        """Configura les columnes del grid per a un frame (capçalera o fila de dades)."""
        frame.grid_columnconfigure(0, minsize=self.COL_CHECKBOX_AMPLADA, weight=0)
        for i, (_, _, amplada) in enumerate(self.COLUMNES):
            frame.grid_columnconfigure(i + 1, minsize=amplada, weight=0)

    def _truncar_text(self, text, max_chars):
        """Trunca el text si supera el nombre màxim de caràcters."""
        if len(text) > max_chars:
            return text[:max_chars - 2] + ".."
        return text

    def _crear_capcalera(self):
        """Crea la fila de capçalera amb noms de columna i checkbox 'Tots'."""
        header = ctk.CTkFrame(self, fg_color="#2b2b2b", corner_radius=0)
        header.pack(fill="x")
        self._configurar_grid_fila(header)

        self.var_tots = ctk.BooleanVar(value=False)
        cb_tots = ctk.CTkCheckBox(
            header, text="", variable=self.var_tots, width=20,
            command=self._toggle_tots, checkbox_width=18, checkbox_height=18
        )
        cb_tots.grid(row=0, column=0, padx=(10, 2), pady=5, sticky="w")

        for i, (text, clau, amplada) in enumerate(self.COLUMNES):
            lbl = ctk.CTkLabel(
                header, text=text, font=("Arial", 11, "bold"),
                width=amplada, anchor="w", cursor="hand2"
            )
            lbl.grid(row=0, column=i + 1, padx=3, pady=5, sticky="w")
            lbl.bind("<Button-1>", lambda e, c=clau: self._ordenar_per_columna(c))
            self.labels_capcalera[clau] = (text, lbl)

    def _toggle_tots(self):
        valor = self.var_tots.get()
        for _, var, _ in self.files_widgets:
            var.set(valor)

    def _ordenar_per_columna(self, clau):
        """Ordena la taula per la columna indicada. Alterna la direcció si ja està ordenada."""
        if self.columna_ordenacio == clau:
            self.ordre_ascendent = not self.ordre_ascendent
        else:
            self.columna_ordenacio = clau
            self.ordre_ascendent = True

        self._actualitzar_fletxes()

        def clau_ordenacio(reg):
            valor = reg.get(clau)
            if valor is None:
                return ""
            if clau in ("id", "total"):
                try:
                    return float(valor)
                except (ValueError, TypeError):
                    return 0
            return str(valor).lower()

        self.registres_actuals.sort(key=clau_ordenacio, reverse=not self.ordre_ascendent)
        self._renderitzar_files()

    def _actualitzar_fletxes(self):
        """Actualitza les etiquetes de capçalera amb la fletxa de direcció."""
        for clau, (text_base, lbl) in self.labels_capcalera.items():
            if clau == self.columna_ordenacio:
                fletxa = " ▲" if self.ordre_ascendent else " ▼"
                lbl.configure(text=text_base + fletxa)
            else:
                lbl.configure(text=text_base)

    def _renderitzar_files(self):
        """Renderitza les files a partir de self.registres_actuals."""
        for frame, _, _ in self.files_widgets:
            frame.destroy()
        self.files_widgets.clear()
        self.var_tots.set(False)

        for registre in self.registres_actuals:
            self._afegir_fila(registre)

    def carregar_dades(self, registres):
        """Neteja la taula i carrega els registres donats."""
        self.registres_actuals = list(registres)

        if self.columna_ordenacio:
            def clau_ordenacio(reg):
                valor = reg.get(self.columna_ordenacio)
                if valor is None:
                    return ""
                if self.columna_ordenacio in ("id", "total"):
                    try:
                        return float(valor)
                    except (ValueError, TypeError):
                        return 0
                return str(valor).lower()

            self.registres_actuals.sort(key=clau_ordenacio, reverse=not self.ordre_ascendent)

        self._renderitzar_files()

    def _afegir_fila(self, registre):
        color_fons = "#333333" if len(self.files_widgets) % 2 == 0 else "#2b2b2b"
        fila = ctk.CTkFrame(self.scroll_frame, fg_color=color_fons, corner_radius=0)
        fila.pack(fill="x", pady=0)
        self._configurar_grid_fila(fila)

        var = ctk.BooleanVar(value=False)
        cb = ctk.CTkCheckBox(
            fila, text="", variable=var, width=20,
            checkbox_width=18, checkbox_height=18
        )
        cb.grid(row=0, column=0, padx=(10, 2), pady=4, sticky="w")

        for i, (_, camp, amplada) in enumerate(self.COLUMNES):
            valor = registre.get(camp, "")
            if valor is None:
                valor = ""
            if camp == "total" and valor != "":
                try:
                    valor = f"{float(valor):.2f}"
                except (ValueError, TypeError):
                    pass

            text = str(valor)
            # Truncar segons l'amplada (aprox 1 char = 8px amb Consolas 11)
            max_chars = max(4, amplada // 8)
            text = self._truncar_text(text, max_chars)

            lbl = ctk.CTkLabel(
                fila, text=text, width=amplada, anchor="w",
                font=("Consolas", 11)
            )
            lbl.grid(row=0, column=i + 1, padx=3, pady=4, sticky="w")

        # Cursor mà i clic per editar
        fila.configure(cursor="hand2")
        fila.bind("<Button-1>", lambda e, r=registre: self._on_clic_fila(r))
        for widget in fila.winfo_children():
            if isinstance(widget, ctk.CTkLabel):
                widget.configure(cursor="hand2")
                widget.bind("<Button-1>", lambda e, r=registre: self._on_clic_fila(r))

        self.files_widgets.append((fila, var, registre))

    def _on_clic_fila(self, registre):
        if self.on_doble_clic:
            self.on_doble_clic(registre)

    def obtenir_seleccionats(self):
        """Retorna la llista de registres seleccionats."""
        return [reg for _, var, reg in self.files_widgets if var.get()]

    def obtenir_tots(self):
        """Retorna tots els registres actuals de la taula."""
        return [reg for _, _, reg in self.files_widgets]


# =============================================================================
# APLICACIÓ PRINCIPAL
# =============================================================================

class AplicacioManteniment(ctk.CTk):
    """Finestra principal de manteniment de la base de dades."""

    def __init__(self):
        super().__init__()

        self.logger = GestorLogging.obtenir_logger("manteniment.AplicacioManteniment")
        self.gestor_bd = GestorBaseDades()

        self.title("Manteniment BD - Transcripcions")
        self.geometry("1100x700")
        ctk.set_appearance_mode("dark")

        # Paginació
        self.registres_per_pagina = 25
        self.pagina_actual = 0
        self.total_registres = 0
        self.cerca_activa = False
        self.terme_cerca = ""
        self.columna_cerca = None

        self._crear_layout()
        self._carregar_dades()

        self.logger.info("Aplicació de manteniment iniciada")

    def _crear_layout(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._crear_barra_eines()
        self._crear_barra_cerca()
        self._crear_taula()
        self._crear_paginacio()
        self._crear_barra_estat()

    def _crear_barra_eines(self):
        toolbar = ctk.CTkFrame(self)
        toolbar.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))

        botons = [
            ("+ Nou", "#2ecc71", "#27ae60", self._nou_registre),
            ("Veure", "#3498db", "#2980b9", self._veure_registre),
            ("Editar", "#9b59b6", "#8e44ad", self._editar_registre),
            ("Eliminar", "#e74c3c", "#c0392b", self._eliminar_registres),
            ("Exportar JSON", "#16a085", "#1abc9c", self._exportar_json),
            ("Exportar CSV", "#2980b9", "#2471a3", self._exportar_csv),
        ]

        for text, fg, hover, cmd in botons:
            ctk.CTkButton(
                toolbar, text=text, width=110,
                fg_color=fg, hover_color=hover,
                command=cmd
            ).pack(side="left", padx=5, pady=5)

        # Selector de registres per pàgina
        ctk.CTkLabel(toolbar, text="Per pàgina:").pack(side="right", padx=(10, 5))
        self.combo_per_pagina = ctk.CTkComboBox(
            toolbar, values=["25", "50", "100"], width=70,
            command=self._canviar_registres_per_pagina
        )
        self.combo_per_pagina.set("25")
        self.combo_per_pagina.pack(side="right", padx=5, pady=5)

    def _crear_barra_cerca(self):
        frame = ctk.CTkFrame(self)
        frame.grid(row=1, column=0, sticky="ew", padx=10, pady=5)

        ctk.CTkLabel(frame, text="Cerca:", font=("Arial", 12)).pack(side="left", padx=(10, 5))

        self.entry_cerca = ctk.CTkEntry(frame, width=300, placeholder_text="Text a cercar...")
        self.entry_cerca.pack(side="left", padx=5)
        self.entry_cerca.bind("<Return>", lambda e: self._cercar())

        ctk.CTkLabel(frame, text="Columna:").pack(side="left", padx=(15, 5))
        self.combo_columna = ctk.CTkComboBox(
            frame,
            values=["Totes", "Establiment", "NIF", "Factura", "Document"],
            width=130
        )
        self.combo_columna.set("Totes")
        self.combo_columna.pack(side="left", padx=5)

        ctk.CTkButton(frame, text="Cercar", width=80, command=self._cercar).pack(
            side="left", padx=5
        )
        ctk.CTkButton(
            frame, text="Netejar", width=80,
            fg_color="#555555", hover_color="#666666",
            command=self._netejar_cerca
        ).pack(side="left", padx=5)

    def _crear_taula(self):
        self.taula = TaulaTranscripcions(self, on_doble_clic=self._on_doble_clic_taula)
        self.taula.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)

    def _crear_paginacio(self):
        frame = ctk.CTkFrame(self)
        frame.grid(row=3, column=0, sticky="ew", padx=10, pady=5)

        self.btn_anterior = ctk.CTkButton(
            frame, text="<< Anterior", width=100, command=self._pagina_anterior
        )
        self.btn_anterior.pack(side="left", padx=10)

        self.lbl_pagina = ctk.CTkLabel(frame, text="Pàg 1 de 1 (0 registres)", font=("Arial", 12))
        self.lbl_pagina.pack(side="left", expand=True)

        self.btn_seguent = ctk.CTkButton(
            frame, text="Següent >>", width=100, command=self._pagina_seguent
        )
        self.btn_seguent.pack(side="right", padx=10)

    def _crear_barra_estat(self):
        frame = ctk.CTkFrame(self, fg_color="#1a1a1a", corner_radius=0)
        frame.grid(row=4, column=0, sticky="ew")

        self.lbl_total = ctk.CTkLabel(frame, text="Total: 0", font=("Arial", 11))
        self.lbl_total.pack(side="left", padx=15, pady=5)

        self.lbl_seleccionats = ctk.CTkLabel(frame, text="Seleccionats: 0", font=("Arial", 11))
        self.lbl_seleccionats.pack(side="left", padx=15, pady=5)

        self.lbl_fitxer = ctk.CTkLabel(
            frame, text=f"BD: {self.gestor_bd.fitxer_bd}",
            font=("Arial", 11), text_color="gray"
        )
        self.lbl_fitxer.pack(side="right", padx=15, pady=5)

        # Actualitzar seleccionats periòdicament
        self._actualitzar_seleccionats()

    def _actualitzar_seleccionats(self):
        n = len(self.taula.obtenir_seleccionats())
        self.lbl_seleccionats.configure(text=f"Seleccionats: {n}")
        self.after(500, self._actualitzar_seleccionats)

    # =====================================================================
    # Càrrega de dades i paginació
    # =====================================================================

    def _carregar_dades(self):
        """Carrega registres segons l'estat actual (cerca o llistat)."""
        try:
            self.total_registres = self.gestor_bd.comptar_transcripcions()
            offset = self.pagina_actual * self.registres_per_pagina

            if self.cerca_activa and self.terme_cerca:
                registres = self.gestor_bd.cercar_transcripcions(
                    self.terme_cerca,
                    columna=self.columna_cerca,
                    limit=self.registres_per_pagina,
                    offset=offset
                )
                # Per a la cerca, obtenim el total de resultats
                tots_resultats = self.gestor_bd.cercar_transcripcions(
                    self.terme_cerca, columna=self.columna_cerca
                )
                self.total_registres = len(tots_resultats)
            else:
                registres = self.gestor_bd.llistar_transcripcions(
                    limit=self.registres_per_pagina, offset=offset
                )

            self.taula.carregar_dades(registres)
            self._actualitzar_paginacio()

        except Exception as e:
            self.logger.error(f"Error carregant dades: {e}")
            messagebox.showerror("Error", f"Error carregant dades:\n{e}")

    def _actualitzar_paginacio(self):
        total_pagines = max(1, math.ceil(self.total_registres / self.registres_per_pagina))
        pagina_mostrada = self.pagina_actual + 1

        self.lbl_pagina.configure(
            text=f"Pàg {pagina_mostrada} de {total_pagines} ({self.total_registres} registres)"
        )
        self.lbl_total.configure(text=f"Total: {self.total_registres}")

        self.btn_anterior.configure(state="normal" if self.pagina_actual > 0 else "disabled")
        self.btn_seguent.configure(
            state="normal" if pagina_mostrada < total_pagines else "disabled"
        )

    def _pagina_anterior(self):
        if self.pagina_actual > 0:
            self.pagina_actual -= 1
            self._carregar_dades()

    def _pagina_seguent(self):
        total_pagines = max(1, math.ceil(self.total_registres / self.registres_per_pagina))
        if self.pagina_actual + 1 < total_pagines:
            self.pagina_actual += 1
            self._carregar_dades()

    def _canviar_registres_per_pagina(self, valor):
        try:
            self.registres_per_pagina = int(valor)
        except ValueError:
            self.registres_per_pagina = 25
        self.pagina_actual = 0
        self._carregar_dades()

    # =====================================================================
    # Cerca
    # =====================================================================

    def _cercar(self):
        terme = self.entry_cerca.get().strip()
        if not terme:
            self._netejar_cerca()
            return

        mapa_columnes = {
            "Totes": None,
            "Establiment": "nom",
            "NIF": "nif",
            "Factura": "factura",
            "Document": "nomDocument",
        }

        self.terme_cerca = terme
        self.columna_cerca = mapa_columnes.get(self.combo_columna.get())
        self.cerca_activa = True
        self.pagina_actual = 0
        self._carregar_dades()

    def _netejar_cerca(self):
        self.entry_cerca.delete(0, "end")
        self.combo_columna.set("Totes")
        self.terme_cerca = ""
        self.columna_cerca = None
        self.cerca_activa = False
        self.pagina_actual = 0
        self._carregar_dades()

    # =====================================================================
    # Operacions CRUD
    # =====================================================================

    def _on_doble_clic_taula(self, registre):
        self._obrir_editor("editar", registre)

    def _nou_registre(self):
        self._obrir_editor("crear")

    def _veure_registre(self):
        seleccionats = self.taula.obtenir_seleccionats()
        if not seleccionats:
            messagebox.showinfo("Atenció", "Selecciona un registre per veure.", parent=self)
            return
        self._obrir_editor("veure", seleccionats[0])

    def _editar_registre(self):
        seleccionats = self.taula.obtenir_seleccionats()
        if not seleccionats:
            messagebox.showinfo("Atenció", "Selecciona un registre per editar.", parent=self)
            return
        self._obrir_editor("editar", seleccionats[0])

    def _obrir_editor(self, mode, registre=None):
        """Obre l'EditorJSON amb el mode i registre indicats."""
        dades_json = {}
        dades_bd = {}

        if registre:
            # Obtenir el registre complet amb contingutJSON
            reg_complet = self.gestor_bd.obtenir_transcripcio(registre["id"])
            if reg_complet:
                try:
                    dades_json = json.loads(reg_complet.get("contingutJSON", "{}"))
                except (json.JSONDecodeError, TypeError):
                    dades_json = {}
                dades_bd = {
                    "nom": reg_complet.get("nom", ""),
                    "nif": reg_complet.get("nif", ""),
                    "factura": reg_complet.get("factura", ""),
                    "total": reg_complet.get("total", ""),
                    "nomDocument": reg_complet.get("nomDocument", ""),
                }

        def on_desar(dades_bd_form, dades_json_form):
            contingut_json = json.dumps(dades_json_form, indent=4, ensure_ascii=False)
            total = dades_bd_form.get("total")
            if isinstance(total, str) and total:
                try:
                    total = float(total.replace(",", "."))
                except ValueError:
                    total = None

            try:
                if mode == "crear":
                    self.gestor_bd.inserir_transcripcio(
                        nom=dades_bd_form.get("nom", ""),
                        nif=dades_bd_form.get("nif", ""),
                        factura=dades_bd_form.get("factura", ""),
                        total=total,
                        contingut_json=contingut_json,
                        nom_document=dades_bd_form.get("nomDocument", ""),
                    )
                    self.logger.info("Registre creat")
                elif mode == "editar" and registre:
                    self.gestor_bd.actualitzar_transcripcio(
                        registre_id=registre["id"],
                        nom=dades_bd_form.get("nom", ""),
                        nif=dades_bd_form.get("nif", ""),
                        factura=dades_bd_form.get("factura", ""),
                        total=total,
                        contingut_json=contingut_json,
                        nom_document=dades_bd_form.get("nomDocument", ""),
                    )
                    self.logger.info(f"Registre actualitzat: ID={registre['id']}")

                self._carregar_dades()
            except Exception as e:
                self.logger.error(f"Error desant registre: {e}")
                messagebox.showerror("Error", f"Error desant registre:\n{e}")

        callback = on_desar if mode != "veure" else None
        EditorJSON(self, mode=mode, dades_json=dades_json, dades_bd=dades_bd, on_desar=callback)

    def _eliminar_registres(self):
        seleccionats = self.taula.obtenir_seleccionats()
        if not seleccionats:
            messagebox.showinfo("Atenció", "Selecciona un o més registres per eliminar.", parent=self)
            return

        n = len(seleccionats)
        confirmar = messagebox.askyesno(
            "Confirmar eliminació",
            f"Segur que vols eliminar {n} registre(s)?\n\nAquesta acció no es pot desfer.",
            parent=self
        )
        if not confirmar:
            return

        errors = 0
        for reg in seleccionats:
            try:
                self.gestor_bd.eliminar_transcripcio(reg["id"])
            except Exception as e:
                self.logger.warning(f"No s'ha pogut eliminar el registre ID={reg.get('id')}: {e}")
                errors += 1

        if errors:
            messagebox.showwarning("Atenció", f"{errors} registre(s) no s'han pogut eliminar.", parent=self)

        self.logger.info(f"Eliminats {n - errors} registre(s)")
        self._carregar_dades()

    # =====================================================================
    # Exportació
    # =====================================================================

    def _exportar_json(self):
        seleccionats = self.taula.obtenir_seleccionats()
        if not seleccionats:
            messagebox.showinfo("Atenció", "Selecciona registres per exportar.", parent=self)
            return

        ruta = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
            title="Exportar a JSON",
            parent=self
        )
        if not ruta:
            return

        dades_export = []
        for reg in seleccionats:
            reg_complet = self.gestor_bd.obtenir_transcripcio(reg["id"])
            if reg_complet:
                item = dict(reg_complet)
                # Parsejar contingutJSON com a dict
                try:
                    item["contingutJSON"] = json.loads(item.get("contingutJSON", "{}"))
                except (json.JSONDecodeError, TypeError):
                    pass
                dades_export.append(item)

        try:
            with open(ruta, "w", encoding="utf-8") as f:
                json.dump(dades_export, f, indent=4, ensure_ascii=False)
            self.logger.info(f"Exportat JSON: {len(dades_export)} registres a {ruta}")
            messagebox.showinfo("Exportació", f"{len(dades_export)} registre(s) exportats a JSON.", parent=self)
        except Exception as e:
            self.logger.error(f"Error exportant JSON: {e}")
            messagebox.showerror("Error", f"Error exportant:\n{e}", parent=self)

    def _exportar_csv(self):
        seleccionats = self.taula.obtenir_seleccionats()
        if not seleccionats:
            messagebox.showinfo("Atenció", "Selecciona registres per exportar.", parent=self)
            return

        ruta = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            title="Exportar a CSV",
            parent=self
        )
        if not ruta:
            return

        try:
            files_csv = []
            for reg in seleccionats:
                reg_complet = self.gestor_bd.obtenir_transcripcio(reg["id"])
                if not reg_complet:
                    continue

                fila = {
                    "id": reg_complet.get("id"),
                    "nom": reg_complet.get("nom"),
                    "nif": reg_complet.get("nif"),
                    "factura": reg_complet.get("factura"),
                    "total": reg_complet.get("total"),
                    "nomDocument": reg_complet.get("nomDocument"),
                    "dataAlta": reg_complet.get("dataAlta"),
                }

                # Extreure camps del JSON
                try:
                    dades_json = json.loads(reg_complet.get("contingutJSON", "{}"))
                    fila["forma_pagament"] = dades_json.get("forma_pagament", "")
                    fila["data_document"] = dades_json.get("data", "")
                    articles = dades_json.get("articles", [])
                    fila["num_articles"] = len(articles)
                except (json.JSONDecodeError, TypeError):
                    fila["forma_pagament"] = ""
                    fila["data_document"] = ""
                    fila["num_articles"] = 0

                files_csv.append(fila)

            if files_csv:
                camps = list(files_csv[0].keys())
                with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
                    writer = csv.DictWriter(f, fieldnames=camps, delimiter=";")
                    writer.writeheader()
                    writer.writerows(files_csv)

                self.logger.info(f"Exportat CSV: {len(files_csv)} registres a {ruta}")
                messagebox.showinfo("Exportació", f"{len(files_csv)} registre(s) exportats a CSV.", parent=self)

        except Exception as e:
            self.logger.error(f"Error exportant CSV: {e}")
            messagebox.showerror("Error", f"Error exportant:\n{e}", parent=self)


# =============================================================================
# PUNT D'ENTRADA
# =============================================================================

if __name__ == "__main__":
    GestorLogging.configurar()
    app = AplicacioManteniment()
    app.mainloop()
