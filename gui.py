import customtkinter as ctk
from tkinter import filedialog, messagebox
from tkinterdnd2 import TkinterDnD
import os
import json
import subprocess
import sys
from utils import (
    GestorConfiguracio,
    GestorLogging,
    GestorPlantilles,
    ValidadorJSONTranscripcio,
)
from services.transcription_service import TranscriptionService
from services.storage_service import StorageService, DuplicateDocumentError
from ui.json_form_utils import construir_json_transcripcio
from ui.pdf_viewer_mixin import PDFViewerMixin
from ui.processing_actions_mixin import ProcessingActionsMixin

os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
import pygame


class InterficieGrafica(PDFViewerMixin, ProcessingActionsMixin, TkinterDnD.Tk):
    # Mètodes requerits per compatibilitat amb CustomTkinter DPI scaling
    # Necessaris perquè heretem de TkinterDnD.Tk en lloc de CTk
    _block_update_dimensions_event = False

    def block_update_dimensions_event(self):
        self._block_update_dimensions_event = True

    def unblock_update_dimensions_event(self):
        self._block_update_dimensions_event = False

    def __init__(self):
        super().__init__()

        # Inicialitzar logger
        self.logger = GestorLogging.obtenir_logger("gui.InterficieGrafica")
        self.logger.info("Iniciant interfície gràfica")

        self.config_dades = GestorConfiguracio.carregar_config()
        self.logger.debug(f"Configuració carregada: so={self.config_dades.get('enable_sound')}")

        self.title("Transcriptor de Tiquets Pro - Digitalització")
        self.geometry("1300x850")
        self.state('zoomed')  # Maximitzar finestra a l'inici
        ctk.set_appearance_mode("dark")

        # Inicialització lògica
        self.transcription_service = TranscriptionService(api_key=self.config_dades.get("api_key"))
        self.transcriptor = self.transcription_service.transcriptor
        self.gestor_plantilles = GestorPlantilles()
        self.storage_service = StorageService()
        self.gestor_bd = self.storage_service.gestor_bd
        self.plantilla_actual_id = None  # ID de la plantilla seleccionada
        self._estat_finestra_anterior = 'zoomed'  # Estat per defecte

        self.ruta_fitxer_actual = None
        self.imatge_original = None
        self.zoom_level = 1.0

        # Variables per a PDFs (lazy loading)
        self.ruta_pdf_actual = None
        self.total_pagines_pdf = 0
        self.pagina_actual = 0
        self.cache_pagines_pdf = {}  # Cache per pàgines ja carregades

        self.processant = False
        self.cancellar_proces = False
        self._cancel_event = threading.Event()
        self._worker_thread = None
        self._audio_inicialitzat = False

        self._configurar_layout()
        self._configurar_dnd()

        self.logger.info("Interfície gràfica inicialitzada correctament")


    def _configurar_layout(self):
        self.grid_columnconfigure(0, weight=1) 
        self.grid_columnconfigure(1, weight=1) 
        self.grid_rowconfigure(0, weight=1)

        # --- PANELL ESQUERRE ---
        self.frame_esquerre = ctk.CTkFrame(self)
        self.frame_esquerre.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        
        # Capçalera i Botó de Càrrega Manual
        self.header_esquerre = ctk.CTkFrame(self.frame_esquerre, fg_color="transparent")
        self.header_esquerre.pack(pady=10, fill="x", padx=20)
        
        self.lbl_info = ctk.CTkLabel(self.header_esquerre, text="Document per processar", font=("Arial", 16, "bold"))
        self.lbl_info.pack(side="left")
        
        self.btn_carregar = ctk.CTkButton(self.header_esquerre, text="Obrir fitxer...", width=120, command=self._seleccionar_fitxer_manual)
        self.btn_carregar.pack(side="right")

        # # Àrea de visualització (Canvas)
        # self.canvas_imatge = ctk.CTkCanvas(self.frame_esquerre, bg="#1a1a1a", highlightthickness=2, highlightbackground="#444444")
        # self.canvas_imatge.pack(fill="both", expand=True, padx=20, pady=5)

        # Creem un frame contenidor per al Canvas i les Scrollbars
        self.container_canvas = ctk.CTkFrame(self.frame_esquerre, fg_color="#1a1a1a")
        self.container_canvas.pack(fill="both", expand=True, padx=20, pady=5)

        # Scrollbars (estil estàndard de tkinter per a màxima compatibilitat amb el Canvas)
        self.v_scroll = ctk.CTkScrollbar(self.container_canvas, orientation="vertical")
        self.v_scroll.pack(side="right", fill="y")
        
        self.h_scroll = ctk.CTkScrollbar(self.container_canvas, orientation="horizontal")
        self.h_scroll.pack(side="bottom", fill="x")

        # Configurem el Canvas amb les scrollbars
        self.canvas_imatge = ctk.CTkCanvas(
            self.container_canvas, 
            bg="#1a1a1a", 
            highlightthickness=0,
            xscrollcommand=self.h_scroll.set,
            yscrollcommand=self.v_scroll.set
        )
        self.canvas_imatge.pack(side="left", fill="both", expand=True)

        self.v_scroll.configure(command=self.canvas_imatge.yview)
        self.h_scroll.configure(command=self.canvas_imatge.xview)

        
        # Indicador visual d'ajuda
        self.txt_ajuda_canvas = self.canvas_imatge.create_text(250, 250, text="Arrossega un document aquí\no prem 'Obrir fitxer...'", fill="#666666", font=("Arial", 12))

        # --- NOVA BARRA DE NAVEGACIÓ PDF ---
        self.nav_bar = ctk.CTkFrame(self.frame_esquerre, fg_color="transparent")
        self.nav_bar.pack(fill="x", pady=2)
        
        self.btn_prev = ctk.CTkButton(self.nav_bar, text="◀ Anterior", width=80, command=self._pagina_anterior)
        self.btn_prev.pack(side="left", padx=20)
        
        self.lbl_pagines = ctk.CTkLabel(self.nav_bar, text="Pàgina: 0 / 0")
        self.lbl_pagines.pack(side="left", expand=True)
        
        self.btn_next = ctk.CTkButton(self.nav_bar, text="Següent ▶", width=80, command=self._pagina_seguent)
        self.btn_next.pack(side="right", padx=20)

        # Controls de Zoom
        self.frame_zoom = ctk.CTkFrame(self.frame_esquerre, fg_color="transparent")
        self.frame_zoom.pack(fill="x", pady=5, padx=10)
        ctk.CTkButton(self.frame_zoom, text="-", width=40, command=lambda: self._zoom(-0.1)).pack(side="left", padx=10)
        self.lbl_zoom = ctk.CTkLabel(self.frame_zoom, text="100%")
        self.lbl_zoom.pack(side="left", padx=5)
        ctk.CTkButton(self.frame_zoom, text="+", width=40, command=lambda: self._zoom(0.1)).pack(side="left", padx=5)

        # --- PANELL DRET ---
        self.frame_dret = ctk.CTkFrame(self)
        self.frame_dret.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)

        # Selector de Plantilles
        self.frame_plantilles = ctk.CTkFrame(self.frame_dret)
        self.frame_plantilles.pack(pady=10, padx=15, fill="x")

        ctk.CTkLabel(self.frame_plantilles, text="Plantilla:", font=("Arial", 12, "bold")).pack(side="left", padx=(15, 10))

        self.plantilla_var = ctk.StringVar(value="Cap (configuració manual)")
        self.combo_plantilles = ctk.CTkComboBox(
            self.frame_plantilles,
            variable=self.plantilla_var,
            values=["Cap (configuració manual)"],
            width=250,
            command=self._on_plantilla_seleccionada
        )
        self.combo_plantilles.pack(side="left", padx=5)
        self._actualitzar_llista_plantilles()

        self.btn_desar_plantilla = ctk.CTkButton(
            self.frame_plantilles, text="💾 Desar", width=80,
            command=self._mostrar_dialeg_desar_plantilla
        )
        self.btn_desar_plantilla.pack(side="left", padx=5)

        self.btn_veure_doc_ref = ctk.CTkButton(
            self.frame_plantilles, text="👁 Doc. Ref.", width=90,
            command=self._veure_document_referencia,
            state="disabled"
        )
        self.btn_veure_doc_ref.pack(side="left", padx=5)

        self.btn_eliminar_plantilla = ctk.CTkButton(
            self.frame_plantilles, text="🗑", width=30,
            fg_color="#e74c3c", hover_color="#c0392b",
            command=self._eliminar_plantilla_actual,
            state="disabled"
        )
        self.btn_eliminar_plantilla.pack(side="left", padx=5)

        # Selector de Mètode
        self.radio_frame = ctk.CTkFrame(self.frame_dret)
        self.radio_frame.pack(pady=15, padx=15, fill="x")
        self.metode_var = ctk.StringVar(value="ocr")
        ctk.CTkLabel(self.radio_frame, text="Mètode d'extracció:", font=("Arial", 12, "bold")).pack(side="left", padx=15)
        ctk.CTkRadioButton(self.radio_frame, text="OCR Local", variable=self.metode_var, value="ocr").pack(side="left", padx=10)
        ctk.CTkRadioButton(self.radio_frame, text="IA (OpenAI)", variable=self.metode_var, value="openai").pack(side="left", padx=10)
        ctk.CTkRadioButton(self.radio_frame, text="IA (Claude)", variable=self.metode_var, value="claude").pack(side="left", padx=10)
        ctk.CTkRadioButton(self.radio_frame, text="Ollama (Local)", variable=self.metode_var, value="ollama").pack(side="left", padx=10)

        # Instruccions addicionals per al prompt
        self.frame_instruccions = ctk.CTkFrame(self.frame_dret)
        self.frame_instruccions.pack(pady=10, padx=15, fill="x")
        ctk.CTkLabel(self.frame_instruccions, text="Instruccions addicionals (opcional):", font=("Arial", 11)).pack(anchor="w", padx=5)
        self.txt_instruccions = ctk.CTkTextbox(self.frame_instruccions, height=60, font=("Consolas", 11))
        self.txt_instruccions.pack(fill="x", padx=5, pady=5)
        self.txt_instruccions.insert("1.0", "")
        # Placeholder amb text d'ajuda
        self.txt_instruccions.bind("<FocusIn>", self._on_instruccions_focus_in)
        self.txt_instruccions.bind("<FocusOut>", self._on_instruccions_focus_out)
        self._mostrar_placeholder_instruccions()

        # Àrea de resultats
        self.txt_resultat = ctk.CTkTextbox(self.frame_dret, font=("Consolas", 12), border_width=2)
        self.txt_resultat.pack(fill="both", expand=True, padx=15, pady=5)

        # Botonera Inferior
        self.frame_botons = ctk.CTkFrame(self.frame_dret, fg_color="transparent")
        self.frame_botons.pack(fill="x", side="bottom", pady=20, padx=15)

        self.btn_processar = ctk.CTkButton(self.frame_botons, text="🚀 ANALITZAR DOCUMENT", fg_color="#2ecc71", hover_color="#27ae60", height=45, font=("Arial", 14, "bold"), command=self._processar_fitxer)
        self.btn_processar.pack(fill="x", pady=(0, 15))

        # Àrea d'estat (Sota el botó Analitzar)
        self.frame_status = ctk.CTkFrame(self.frame_botons, fg_color="transparent")
        self.frame_status.pack(fill="x", pady=5)

        self.progress_bar = ctk.CTkProgressBar(self.frame_status, orientation="horizontal", height=10)
        self.progress_bar.set(0) # Inicialment buida

        # Dins de _configurar_layout (a la zona de la barra de progrés)
        self.btn_stop = ctk.CTkButton(
            self.frame_status, 
            text="Aturar", 
            fg_color="#e74c3c", 
            hover_color="#c0392b", 
            width=60, 
            height=20,
            command=self._sollicitar_aturada
        )
        # El botó estarà amagat fins que comenci el procés
        self.btn_stop.pack_forget()
        
        self.lbl_cronometre = ctk.CTkLabel(self.frame_status, text="Temps: 0.0s", font=("Arial", 11))
        self.lbl_cronometre.pack(side="right", padx=10)

        self.subframe_botons = ctk.CTkFrame(self.frame_botons, fg_color="transparent")
        self.subframe_botons.pack(fill="x")
        ctk.CTkButton(self.subframe_botons, text="Copiar", width=90, command=self._copiar_resultats).pack(side="left", padx=5)
        ctk.CTkButton(self.subframe_botons, text="Excel", width=90, fg_color="#2980b9", command=self._exportar_excel).pack(side="left", padx=5)
        self.btn_editar = ctk.CTkButton(self.subframe_botons, text="Editar", width=90, fg_color="#9b59b6", hover_color="#8e44ad", command=self._obrir_editor_json, state="disabled")
        self.btn_editar.pack(side="left", padx=5)
        self.btn_desar_bd = ctk.CTkButton(self.subframe_botons, text="Desar BD", width=90, fg_color="#16a085", hover_color="#1abc9c", command=self._obrir_dialeg_desar_bd, state="disabled")
        self.btn_desar_bd.pack(side="left", padx=5)
        ctk.CTkButton(self.subframe_botons, text="Manteniment BD", width=110, fg_color="#f39c12", hover_color="#e67e22", command=self._obrir_manteniment_bd).pack(side="left", padx=5)
        ctk.CTkButton(self.subframe_botons, text="Netejar", width=90, fg_color="#e74c3c", command=self._netejar).pack(side="right", padx=5)


    # Gestió del placeholder per instruccions
    def _mostrar_placeholder_instruccions(self):
        """Mostra el text d'ajuda (placeholder) al camp d'instruccions."""
        self.placeholder_instruccions = "Ex: El preu ja inclou IVA, ignora la columna descompte..."
        self.txt_instruccions.delete("1.0", "end")
        self.txt_instruccions.insert("1.0", self.placeholder_instruccions)
        self.txt_instruccions.configure(text_color="gray")

    def _on_instruccions_focus_in(self, event):
        """Esborra el placeholder quan l'usuari fa clic al camp."""
        if self.txt_instruccions.get("1.0", "end").strip() == self.placeholder_instruccions:
            self.txt_instruccions.delete("1.0", "end")
            self.txt_instruccions.configure(text_color="white")

    def _on_instruccions_focus_out(self, event):
        """Restaura el placeholder si el camp queda buit."""
        if not self.txt_instruccions.get("1.0", "end").strip():
            self._mostrar_placeholder_instruccions()

    def _obtenir_instruccions_usuari(self):
        """Retorna les instruccions de l'usuari o None si només hi ha el placeholder."""
        text = self.txt_instruccions.get("1.0", "end").strip()
        if text and text != self.placeholder_instruccions:
            return text
        return None

    # =========================================================================
    # GESTIÓ DE PLANTILLES
    # =========================================================================

    def _actualitzar_llista_plantilles(self):
        """Actualitza el combobox amb les plantilles disponibles."""
        plantilles = self.gestor_plantilles.llistar_plantilles()
        valors = ["Cap (configuració manual)"]
        self._mapa_plantilles = {"Cap (configuració manual)": None}

        for p in plantilles:
            text = f"{p['nom']} ({p['metode']})"
            valors.append(text)
            self._mapa_plantilles[text] = p['id']

        self.combo_plantilles.configure(values=valors)
        self.logger.debug(f"Llista de plantilles actualitzada: {len(plantilles)} plantilles")

    def _on_plantilla_seleccionada(self, seleccio):
        """Carrega la plantilla seleccionada i omple els camps."""
        plantilla_id = self._mapa_plantilles.get(seleccio)
        self.plantilla_actual_id = plantilla_id

        if plantilla_id is None:
            # Configuració manual - netejar camps
            self.btn_veure_doc_ref.configure(state="disabled")
            self.btn_eliminar_plantilla.configure(state="disabled")
            return

        plantilla = self.gestor_plantilles.obtenir_plantilla(plantilla_id)
        if not plantilla:
            return

        self.logger.info(f"Plantilla carregada: {plantilla['nom']}")

        # Aplicar mètode d'extracció
        metode = plantilla.get("metode", "ocr")
        if metode in ["ocr", "openai", "claude", "ollama"]:
            self.metode_var.set(metode)

        # Aplicar instruccions addicionals
        instruccions = plantilla.get("instruccions_extra", "")
        self.txt_instruccions.delete("1.0", "end")
        if instruccions:
            self.txt_instruccions.configure(text_color="white")
            self.txt_instruccions.insert("1.0", instruccions)
        else:
            self._mostrar_placeholder_instruccions()

        # Activar/desactivar botons
        te_document = bool(plantilla.get("document_referencia"))
        self.btn_veure_doc_ref.configure(state="normal" if te_document else "disabled")
        self.btn_eliminar_plantilla.configure(state="normal")

        # Mostrar descripció
        if plantilla.get("descripcio"):
            messagebox.showinfo(
                f"Plantilla: {plantilla['nom']}",
                f"Descripció: {plantilla['descripcio']}\n\n"
                f"Mètode: {plantilla['metode']}\n"
                f"Model: {plantilla.get('model', 'Per defecte')}"
            )

    def _mostrar_dialeg_desar_plantilla(self):
        """Mostra el diàleg per desar una nova plantilla o actualitzar l'existent."""
        # Desar l'estat actual de la finestra principal
        self._estat_finestra_anterior = self.state()

        dialeg = ctk.CTkToplevel()
        dialeg.title("Desar Plantilla")
        dialeg.geometry("500x450")
        dialeg.resizable(False, False)
        dialeg.transient(self)  # Associar amb la finestra principal
        dialeg.grab_set()  # Modal: bloquejar interacció amb la finestra principal

        # Centrar el diàleg
        self.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 500) // 2
        y = self.winfo_y() + (self.winfo_height() - 450) // 2
        dialeg.geometry(f"500x450+{x}+{y}")

        # Donar focus al diàleg
        dialeg.after(50, lambda: dialeg.focus_force())

        # Obtenir dades actuals per pre-omplir
        plantilla_existent = None
        if self.plantilla_actual_id:
            plantilla_existent = self.gestor_plantilles.obtenir_plantilla(self.plantilla_actual_id)

        # Nom de la plantilla
        ctk.CTkLabel(dialeg, text="Nom de la plantilla:", font=("Arial", 12, "bold")).pack(pady=(20, 5), padx=20, anchor="w")
        entry_nom = ctk.CTkEntry(dialeg, width=450)
        entry_nom.pack(padx=20)
        if plantilla_existent:
            entry_nom.insert(0, plantilla_existent.get("nom", ""))

        # Descripció
        ctk.CTkLabel(dialeg, text="Descripció:", font=("Arial", 12, "bold")).pack(pady=(15, 5), padx=20, anchor="w")
        txt_descripcio = ctk.CTkTextbox(dialeg, height=80, width=450)
        txt_descripcio.pack(padx=20)
        if plantilla_existent:
            txt_descripcio.insert("1.0", plantilla_existent.get("descripcio", ""))

        # Tipus de document
        ctk.CTkLabel(dialeg, text="Tipus de document:", font=("Arial", 12, "bold")).pack(pady=(15, 5), padx=20, anchor="w")
        tipus_var = ctk.StringVar(value=plantilla_existent.get("tipus", "general") if plantilla_existent else "general")
        frame_tipus = ctk.CTkFrame(dialeg, fg_color="transparent")
        frame_tipus.pack(padx=20, anchor="w")
        for tipus, text in [("tiquet", "Tiquet"), ("factura", "Factura"), ("albara", "Albarà"), ("general", "General")]:
            ctk.CTkRadioButton(frame_tipus, text=text, variable=tipus_var, value=tipus).pack(side="left", padx=10)

        # Checkbox per desar document de referència
        desar_doc_var = ctk.BooleanVar(value=True)
        if self.ruta_fitxer_actual:
            ctk.CTkCheckBox(
                dialeg,
                text=f"Desar document de referència: {os.path.basename(self.ruta_fitxer_actual)}",
                variable=desar_doc_var
            ).pack(pady=(15, 5), padx=20, anchor="w")
        else:
            ctk.CTkLabel(dialeg, text="⚠ No hi ha cap document carregat per usar com a referència", text_color="orange").pack(pady=(15, 5), padx=20, anchor="w")

        # Model actual
        metode_actual = self.metode_var.get()
        model_actual = self._obtenir_model_actual(metode_actual)
        ctk.CTkLabel(dialeg, text=f"Mètode: {metode_actual} | Model: {model_actual}", text_color="gray").pack(pady=(15, 5), padx=20, anchor="w")

        # Botons
        frame_botons = ctk.CTkFrame(dialeg, fg_color="transparent")
        frame_botons.pack(pady=20, fill="x", padx=20)

        def _desar():
            nom = entry_nom.get().strip()
            if not nom:
                messagebox.showwarning("Atenció", "Has d'introduir un nom per la plantilla.")
                return

            descripcio = txt_descripcio.get("1.0", "end").strip()
            instruccions = self._obtenir_instruccions_usuari()
            document = self.ruta_fitxer_actual if desar_doc_var.get() else None

            try:
                plantilla_id = self.gestor_plantilles.desar_plantilla(
                    nom=nom,
                    descripcio=descripcio,
                    metode=metode_actual,
                    model=model_actual,
                    instruccions_extra=instruccions,
                    document_original=document,
                    tipus=tipus_var.get(),
                    plantilla_id=self.plantilla_actual_id  # None si és nova
                )

                self._actualitzar_llista_plantilles()
                self.plantilla_actual_id = plantilla_id

                # Seleccionar la plantilla al combobox
                for text, pid in self._mapa_plantilles.items():
                    if pid == plantilla_id:
                        self.plantilla_var.set(text)
                        break

                accio = "actualitzada" if plantilla_existent else "creada"
                dialeg.grab_release()
                dialeg.destroy()
                # Restaurar estat de la finestra principal
                if self._estat_finestra_anterior == 'zoomed':
                    self.after(50, lambda: self.state('zoomed'))
                messagebox.showinfo("Èxit", f"Plantilla {accio} correctament!")

            except Exception as e:
                self.logger.error(f"Error desant plantilla: {e}")
                messagebox.showerror("Error", f"Error desant la plantilla: {e}")

        def _tancar():
            dialeg.grab_release()
            dialeg.destroy()
            # Restaurar estat de la finestra principal
            if self._estat_finestra_anterior == 'zoomed':
                self.after(50, lambda: self.state('zoomed'))

        ctk.CTkButton(frame_botons, text="Desar", fg_color="#2ecc71", hover_color="#27ae60", command=_desar).pack(side="left", padx=10)
        ctk.CTkButton(frame_botons, text="Cancel·lar", fg_color="#e74c3c", hover_color="#c0392b", command=_tancar).pack(side="right", padx=10)

        # Gestionar tancament amb la X
        dialeg.protocol("WM_DELETE_WINDOW", _tancar)

    def _obtenir_model_actual(self, metode):
        """Retorna el model actual segons el mètode seleccionat."""
        import os as _os
        if metode == "openai":
            return _os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        elif metode == "claude":
            return _os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
        elif metode == "ollama":
            return _os.getenv("OLLAMA_MODEL", "llama3.2-vision")
        return "N/A"

    def _veure_document_referencia(self):
        """Mostra el document de referència de la plantilla actual."""
        if not self.plantilla_actual_id:
            return

        ruta = self.gestor_plantilles.obtenir_ruta_document(self.plantilla_actual_id)
        if ruta and os.path.exists(ruta):
            self.logger.info(f"Mostrant document de referència: {ruta}")
            self._mostrar_preview(ruta)
        else:
            messagebox.showwarning("Atenció", "No s'ha trobat el document de referència.")

    def _restaurar_finestra_principal(self):
        """Restaura la finestra principal després de tancar un diàleg."""
        try:
            self.attributes('-alpha', 1.0)  # Assegurar opacitat completa
            self.deiconify()
            # Restaurar l'estat anterior (maximitzat si ho estava)
            if hasattr(self, '_estat_finestra_anterior') and self._estat_finestra_anterior == 'zoomed':
                self.state('zoomed')
            self.lift()
            self.focus_force()
        except Exception as e:
            self.logger.warning(f"No s'ha pogut restaurar la finestra principal: {e}")

    def _eliminar_plantilla_actual(self):
        """Elimina la plantilla seleccionada."""
        if not self.plantilla_actual_id:
            return

        plantilla = self.gestor_plantilles.obtenir_plantilla(self.plantilla_actual_id)
        if not plantilla:
            return

        confirmar = messagebox.askyesno(
            "Confirmar eliminació",
            f"Segur que vols eliminar la plantilla '{plantilla['nom']}'?\n\n"
            "Aquesta acció no es pot desfer."
        )

        if confirmar:
            if self.gestor_plantilles.eliminar_plantilla(self.plantilla_actual_id):
                self.logger.info(f"Plantilla eliminada: {self.plantilla_actual_id}")
                self.plantilla_actual_id = None
                self._actualitzar_llista_plantilles()
                self.plantilla_var.set("Cap (configuració manual)")
                self.btn_veure_doc_ref.configure(state="disabled")
                self.btn_eliminar_plantilla.configure(state="disabled")
                messagebox.showinfo("Èxit", "Plantilla eliminada correctament.")

    # =========================================================================
    # EDITOR DE JSON TRANSCRIT
    # =========================================================================

    def _obrir_editor_json(self):
        """Obre el diàleg d'edició del JSON transcrit."""
        contingut = self.txt_resultat.get("1.0", "end").strip()
        try:
            dades = json.loads(contingut)
        except json.JSONDecodeError:
            messagebox.showerror("Error", "El contingut no és JSON vàlid.")
            return

        # Desar l'estat actual de la finestra principal
        self._estat_finestra_anterior = self.state()

        # Crear finestra modal
        self.dialeg_editor = ctk.CTkToplevel()
        self.dialeg_editor.title("Editar JSON Transcrit")
        self.dialeg_editor.geometry("950x750")
        self.dialeg_editor.resizable(True, True)
        self.dialeg_editor.transient(self)
        self.dialeg_editor.grab_set()

        # Centrar el diàleg
        self.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 950) // 2
        y = self.winfo_y() + (self.winfo_height() - 750) // 2
        self.dialeg_editor.geometry(f"950x750+{x}+{y}")

        # Donar focus al diàleg
        self.dialeg_editor.after(50, lambda: self.dialeg_editor.focus_force())

        # Estructures per guardar els widgets d'entrada
        self.editor_entries_capcalera = {}
        self.editor_files_articles = []
        self.editor_files_impostos = []

        # Crear les seccions
        self._crear_seccio_capcalera(self.dialeg_editor, dades)
        self._crear_seccio_articles(self.dialeg_editor, dades.get("articles", []))
        self._crear_seccio_impostos(self.dialeg_editor, dades.get("impostos", []))
        self._crear_botons_accio_editor(self.dialeg_editor)

        # Gestionar tancament amb la X
        self.dialeg_editor.protocol("WM_DELETE_WINDOW", self._tancar_editor)

    def _crear_seccio_capcalera(self, parent, dades):
        """Crea la secció de capçalera amb els camps editables."""
        frame = ctk.CTkFrame(parent)
        frame.pack(fill="x", padx=15, pady=(15, 10))

        ctk.CTkLabel(frame, text="Capçalera", font=("Arial", 14, "bold")).pack(anchor="w", padx=10, pady=5)

        # Camps de capçalera en dues files
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

        fila1 = ctk.CTkFrame(frame, fg_color="transparent")
        fila1.pack(fill="x", padx=10, pady=5)
        for camp, etiqueta, amplada in camps_fila1:
            subframe = ctk.CTkFrame(fila1, fg_color="transparent")
            subframe.pack(side="left", padx=5)
            ctk.CTkLabel(subframe, text=etiqueta, font=("Arial", 10)).pack(anchor="w")
            entry = ctk.CTkEntry(subframe, width=amplada)
            entry.pack()
            valor = dades.get(camp, "")
            if valor is not None:
                entry.insert(0, str(valor))
            self.editor_entries_capcalera[camp] = entry

        fila2 = ctk.CTkFrame(frame, fg_color="transparent")
        fila2.pack(fill="x", padx=10, pady=5)
        for camp, etiqueta, amplada in camps_fila2:
            subframe = ctk.CTkFrame(fila2, fg_color="transparent")
            subframe.pack(side="left", padx=5)
            ctk.CTkLabel(subframe, text=etiqueta, font=("Arial", 10)).pack(anchor="w")
            entry = ctk.CTkEntry(subframe, width=amplada)
            entry.pack()
            valor = dades.get(camp, "")
            if valor is not None:
                entry.insert(0, str(valor))
            self.editor_entries_capcalera[camp] = entry

    def _crear_seccio_articles(self, parent, articles):
        """Crea la secció d'articles amb taula editable i scroll."""
        frame = ctk.CTkFrame(parent)
        frame.pack(fill="both", expand=True, padx=15, pady=10)

        # Capçalera de la secció
        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(header, text="Articles", font=("Arial", 14, "bold")).pack(side="left")
        ctk.CTkButton(header, text="+ Afegir article", width=120, command=self._afegir_fila_article).pack(side="right")

        # Capçaleres de columna
        header_cols = ctk.CTkFrame(frame, fg_color="transparent")
        header_cols.pack(fill="x", padx=10)
        columnes = [("Descripció", 180), ("Quantitat", 70), ("Preu", 80), ("Import Base", 80),
                    ("%IVA", 60), ("Import IVA", 80), ("Import Total", 80), ("", 30)]
        for text, amplada in columnes:
            ctk.CTkLabel(header_cols, text=text, font=("Arial", 10, "bold"), width=amplada).pack(side="left", padx=2)

        # Scrollable frame per als articles
        self.scroll_articles = ctk.CTkScrollableFrame(frame, height=200)
        self.scroll_articles.pack(fill="both", expand=True, padx=10, pady=5)

        # Afegir files existents
        for article in articles:
            self._afegir_fila_article(article)

    def _afegir_fila_article(self, dades=None):
        """Afegeix una fila d'article editable."""
        if dades is None:
            dades = {}

        fila = ctk.CTkFrame(self.scroll_articles, fg_color="transparent")
        fila.pack(fill="x", pady=2)

        camps = [
            ("descripció", 180), ("quantitat", 70), ("preu", 80), ("importBase", 80),
            ("percentatgeIVA", 60), ("importIVA", 80), ("importTotal", 80)
        ]

        entries = {}
        for camp, amplada in camps:
            entry = ctk.CTkEntry(fila, width=amplada)
            entry.pack(side="left", padx=2)
            valor = dades.get(camp, "")
            if valor is not None:
                entry.insert(0, str(valor))
            entries[camp] = entry

        # Botó eliminar
        btn_eliminar = ctk.CTkButton(
            fila, text="X", width=30, fg_color="#e74c3c", hover_color="#c0392b",
            command=lambda f=fila: self._eliminar_fila_article(f)
        )
        btn_eliminar.pack(side="left", padx=2)

        self.editor_files_articles.append((fila, entries))

    def _eliminar_fila_article(self, fila):
        """Elimina una fila d'article."""
        for i, (f, entries) in enumerate(self.editor_files_articles):
            if f == fila:
                fila.destroy()
                del self.editor_files_articles[i]
                break

    def _crear_seccio_impostos(self, parent, impostos):
        """Crea la secció d'impostos amb taula editable."""
        frame = ctk.CTkFrame(parent)
        frame.pack(fill="x", padx=15, pady=10)

        # Capçalera de la secció
        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(header, text="Impostos", font=("Arial", 14, "bold")).pack(side="left")
        ctk.CTkButton(header, text="+ Afegir impost", width=120, command=self._afegir_fila_impost).pack(side="right")

        # Capçaleres de columna
        header_cols = ctk.CTkFrame(frame, fg_color="transparent")
        header_cols.pack(fill="x", padx=10)
        columnes = [("% IVA", 100), ("Import Base IVA", 150), ("Quota IVA", 150), ("", 30)]
        for text, amplada in columnes:
            ctk.CTkLabel(header_cols, text=text, font=("Arial", 10, "bold"), width=amplada).pack(side="left", padx=5)

        # Frame per als impostos
        self.frame_impostos = ctk.CTkFrame(frame, fg_color="transparent")
        self.frame_impostos.pack(fill="x", padx=10, pady=5)

        # Afegir files existents
        for impost in impostos:
            self._afegir_fila_impost(impost)

    def _afegir_fila_impost(self, dades=None):
        """Afegeix una fila d'impost editable."""
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
            entries[camp] = entry

        # Botó eliminar
        btn_eliminar = ctk.CTkButton(
            fila, text="X", width=30, fg_color="#e74c3c", hover_color="#c0392b",
            command=lambda f=fila: self._eliminar_fila_impost(f)
        )
        btn_eliminar.pack(side="left", padx=5)

        self.editor_files_impostos.append((fila, entries))

    def _eliminar_fila_impost(self, fila):
        """Elimina una fila d'impost."""
        for i, (f, entries) in enumerate(self.editor_files_impostos):
            if f == fila:
                fila.destroy()
                del self.editor_files_impostos[i]
                break

    def _crear_botons_accio_editor(self, parent):
        """Crea els botons d'acció (Desar/Cancel·lar) de l'editor."""
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", padx=15, pady=15)

        ctk.CTkButton(
            frame, text="Desar", width=120, fg_color="#2ecc71", hover_color="#27ae60",
            command=self._desar_edicio
        ).pack(side="left", padx=10)

        ctk.CTkButton(
            frame, text="Cancel·lar", width=120, fg_color="#e74c3c", hover_color="#c0392b",
            command=self._tancar_editor
        ).pack(side="right", padx=10)

    def _construir_json_des_de_formulari(self):
        """Recull tots els valors dels widgets i genera el diccionari."""
        return construir_json_transcripcio(
            self.editor_entries_capcalera,
            self.editor_files_articles,
            self.editor_files_impostos
        )

    def _desar_edicio(self):
        """Desa l'edició i actualitza l'àrea de resultats."""
        try:
            dades = self._construir_json_des_de_formulari()
            valid, errors = ValidadorJSONTranscripcio.validar(dades)
            if not valid:
                messagebox.showerror("Error de validació", f"JSON invàlid:\n{errors[0]}")
                return
            json_formatat = json.dumps(dades, indent=4, ensure_ascii=False)

            # Actualitzar l'àrea de resultats
            self.txt_resultat.delete("1.0", "end")
            self.txt_resultat.insert("end", json_formatat)

            self.logger.info("JSON editat i desat correctament")
            self._tancar_editor()

        except Exception as e:
            self.logger.error(f"Error desant l'edició: {e}")
            messagebox.showerror("Error", f"Error desant l'edició: {e}")

    def _tancar_editor(self):
        """Tanca el diàleg d'edició."""
        if hasattr(self, 'dialeg_editor') and self.dialeg_editor:
            self.dialeg_editor.grab_release()
            self.dialeg_editor.destroy()
            self.dialeg_editor = None
        # Restaurar estat de la finestra principal
        if self._estat_finestra_anterior == 'zoomed':
            self.after(50, lambda: self.state('zoomed'))

    # =========================================================================
    # DESAR A BASE DE DADES
    # =========================================================================

    def _obrir_manteniment_bd(self):
        """Obre l'aplicació de manteniment de la base de dades en un procés separat."""
        try:
            script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "manteniment_bd.py")
            subprocess.Popen([sys.executable, script])
            self.logger.info("Aplicació de manteniment BD oberta")
        except Exception as e:
            self.logger.error(f"Error obrint manteniment BD: {e}")
            messagebox.showerror("Error", f"No s'ha pogut obrir l'aplicació de manteniment:\n{e}")

    def _obrir_dialeg_desar_bd(self):
        """Obre el diàleg per validar i desar la transcripció a la base de dades."""
        contingut = self.txt_resultat.get("1.0", "end").strip()
        try:
            dades = json.loads(contingut)
        except json.JSONDecodeError:
            messagebox.showerror("Error", "El contingut no és JSON vàlid.")
            return

        valid, errors = ValidadorJSONTranscripcio.validar(dades)
        if not valid:
            messagebox.showerror(
                "Error de validació",
                "No es pot desar a BD perquè el JSON no compleix l'esquema.\n"
                f"Primer error: {errors[0]}"
            )
            return

        # Desar l'estat actual de la finestra principal
        self._estat_finestra_anterior = self.state()

        # Crear finestra modal
        self.dialeg_desar_bd = ctk.CTkToplevel()
        self.dialeg_desar_bd.title("Desar a Base de Dades")
        self.dialeg_desar_bd.geometry("550x400")
        self.dialeg_desar_bd.resizable(False, False)
        self.dialeg_desar_bd.transient(self)
        self.dialeg_desar_bd.grab_set()

        # Centrar el diàleg
        self.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 550) // 2
        y = self.winfo_y() + (self.winfo_height() - 400) // 2
        self.dialeg_desar_bd.geometry(f"550x400+{x}+{y}")

        # Donar focus al diàleg
        self.dialeg_desar_bd.after(50, lambda: self.dialeg_desar_bd.focus_force())

        # Extreure dades del JSON
        nom = dades.get("establiment", "") or ""
        nif = dades.get("nifEstabliment", "") or ""
        factura = dades.get("numeroFacturaRebutTiquet", "") or ""
        total = dades.get("total", "")
        if total is not None:
            total = str(total)
        else:
            total = ""

        # Nom del document
        nom_document = ""
        if self.ruta_fitxer_actual:
            nom_document = os.path.basename(self.ruta_fitxer_actual)

        # Frame principal
        frame = ctk.CTkFrame(self.dialeg_desar_bd)
        frame.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(frame, text="Validar dades abans de desar", font=("Arial", 16, "bold")).pack(pady=(0, 15))

        # Guardar les entrades per poder-les llegir després
        self.entries_desar_bd = {}

        # Camps editables
        camps = [
            ("nom", "Establiment:", nom),
            ("nif", "NIF:", nif),
            ("factura", "Núm. Factura/Tiquet:", factura),
            ("total", "Total:", total),
            ("nomDocument", "Nom Document:", nom_document),
        ]

        for camp_id, etiqueta, valor in camps:
            subframe = ctk.CTkFrame(frame, fg_color="transparent")
            subframe.pack(fill="x", pady=5)

            lbl = ctk.CTkLabel(subframe, text=etiqueta, width=150, anchor="w")
            lbl.pack(side="left", padx=5)

            entry = ctk.CTkEntry(subframe, width=350)
            entry.pack(side="left", padx=5)
            entry.insert(0, valor)

            # Marcar camps obligatoris buits
            if not valor and camp_id in ("nom", "factura"):
                entry.configure(border_color="#e74c3c")

            self.entries_desar_bd[camp_id] = entry

        # Advertència per a camps obligatoris
        self.lbl_advertencia_bd = ctk.CTkLabel(
            frame,
            text="",
            text_color="#e74c3c",
            font=("Arial", 11)
        )
        self.lbl_advertencia_bd.pack(pady=10)

        # Comprovar si la factura ja existeix
        if nif and factura:
            if self.storage_service.existeix_factura(nif, factura):
                self.lbl_advertencia_bd.configure(
                    text="⚠ Ja existeix una factura amb aquest NIF i número!"
                )

        # Guardar el JSON complet per inserir-lo
        self._json_a_desar = contingut

        # Botons
        frame_botons = ctk.CTkFrame(frame, fg_color="transparent")
        frame_botons.pack(fill="x", pady=(20, 0))

        ctk.CTkButton(
            frame_botons, text="Editar JSON", width=100,
            fg_color="#9b59b6", hover_color="#8e44ad",
            command=self._editar_abans_de_desar
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            frame_botons, text="Desar", width=100,
            fg_color="#2ecc71", hover_color="#27ae60",
            command=self._desar_a_bd
        ).pack(side="right", padx=5)

        ctk.CTkButton(
            frame_botons, text="Cancel·lar", width=100,
            fg_color="#e74c3c", hover_color="#c0392b",
            command=self._tancar_dialeg_desar_bd
        ).pack(side="right", padx=5)

        # Gestionar tancament amb la X
        self.dialeg_desar_bd.protocol("WM_DELETE_WINDOW", self._tancar_dialeg_desar_bd)

    def _editar_abans_de_desar(self):
        """Tanca el diàleg de desar i obre l'editor JSON."""
        self._tancar_dialeg_desar_bd()
        self._obrir_editor_json()

    def _desar_a_bd(self):
        """Valida les dades i les desa a la base de dades."""
        # Recollir dades dels camps
        nom = self.entries_desar_bd["nom"].get().strip()
        nif = self.entries_desar_bd["nif"].get().strip()
        factura = self.entries_desar_bd["factura"].get().strip()
        total_str = self.entries_desar_bd["total"].get().strip()
        nom_document = self.entries_desar_bd["nomDocument"].get().strip()

        # Validar camps obligatoris
        camps_buits = []
        if not nom:
            camps_buits.append("Establiment")
            self.entries_desar_bd["nom"].configure(border_color="#e74c3c")
        else:
            self.entries_desar_bd["nom"].configure(border_color=["#979DA2", "#565B5E"])

        if not factura:
            camps_buits.append("Núm. Factura/Tiquet")
            self.entries_desar_bd["factura"].configure(border_color="#e74c3c")
        else:
            self.entries_desar_bd["factura"].configure(border_color=["#979DA2", "#565B5E"])

        if camps_buits:
            self.lbl_advertencia_bd.configure(
                text=f"⚠ Camps obligatoris buits: {', '.join(camps_buits)}"
            )
            return

        # Convertir total a número
        total = None
        if total_str:
            try:
                total = float(total_str.replace(",", "."))
            except ValueError:
                self.lbl_advertencia_bd.configure(text="⚠ El total ha de ser un número vàlid")
                return

        # Comprovar si ja existeix
        if nif and factura and self.storage_service.existeix_factura(nif, factura):
            confirmar = messagebox.askyesno(
                "Duplicat detectat",
                f"Ja existeix una factura amb NIF '{nif}' i número '{factura}'.\n\n"
                "Vols desar-la igualment?"
            )
            if not confirmar:
                return

        try:
            # Inserir a la base de dades
            registre_id = self.storage_service.inserir_transcripcio(
                nom=nom,
                nif=nif,
                factura=factura,
                total=total,
                contingut_json=self._json_a_desar,
                nom_document=nom_document
            )

            self.logger.info(f"Transcripció desada a BD: ID={registre_id}")
            self._tancar_dialeg_desar_bd()
            messagebox.showinfo("Èxit", f"Transcripció desada correctament!\nID: {registre_id}")

        except DuplicateDocumentError:
            self.logger.warning("Duplicat detectat per restricció de BD (nif, factura)")
            self.lbl_advertencia_bd.configure(
                text="⚠ Ja existeix una factura amb aquest NIF i número (bloquejat per BD)"
            )
        except Exception as e:
            self.logger.error(f"Error desant a BD: {e}")
            messagebox.showerror("Error", f"Error desant a la base de dades:\n{e}")

    def _tancar_dialeg_desar_bd(self):
        """Tanca el diàleg de desar a BD."""
        if hasattr(self, 'dialeg_desar_bd') and self.dialeg_desar_bd:
            self.dialeg_desar_bd.grab_release()
            self.dialeg_desar_bd.destroy()
            self.dialeg_desar_bd = None
        # Restaurar estat de la finestra principal
        if self._estat_finestra_anterior == 'zoomed':
            self.after(50, lambda: self.state('zoomed'))

