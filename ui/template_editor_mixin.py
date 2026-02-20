import json
import os
from tkinter import messagebox

import customtkinter as ctk

from ui.json_form_utils import construir_json_transcripcio
from utils import ValidadorJSONTranscripcio


class TemplateEditorMixin:
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
        if metode == "claude":
            return _os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
        if metode == "ollama":
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

        if confirmar and self.gestor_plantilles.eliminar_plantilla(self.plantilla_actual_id):
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
        for i, (f, _entries) in enumerate(self.editor_files_articles):
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
        for i, (f, _entries) in enumerate(self.editor_files_impostos):
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

