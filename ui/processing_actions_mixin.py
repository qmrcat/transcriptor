import json
import os
import threading
import time
from tkinter import filedialog, messagebox

import pandas as pd
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
import pygame

from utils import ValidadorJSONTranscripcio


class ProcessingActionsMixin:
    def _processar_fitxer(self):
        if self.processant:
            self.logger.debug("Ja hi ha un procés en marxa, s'ignora una nova petició")
            return

        if not self.ruta_fitxer_actual:
            self.logger.warning("Intent de processar sense fitxer seleccionat")
            messagebox.showwarning("Atenció", "Selecciona un document primer.")
            return

        # Validació prèvia segons el mètode seleccionat
        metode = self.metode_var.get()
        self.logger.info(f"Iniciant processament amb mètode: {metode}")

        error_config = self.transcription_service.validar_configuracio_metode(metode)
        if error_config:
            self.logger.error(f"Configuració invàlida per mètode {metode}: {error_config}")
            messagebox.showerror(
                "API Key no configurada",
                error_config
            )
            return

        if metode == "ollama":
            # Comprovació ràpida de connexió amb Ollama
            try:
                import socket
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                result = sock.connect_ex(('localhost', 11434))
                sock.close()
                if result != 0:
                    self.logger.error("Ollama no disponible a localhost:11434")
                    messagebox.showerror(
                        "Ollama no disponible",
                        "No es pot connectar amb el servidor Ollama a localhost:11434.\n"
                        "Assegura't que Ollama estigui en execució."
                    )
                    return
                self.logger.debug("Connexió amb Ollama verificada")
            except Exception as e:
                self.logger.debug(f"Comprovació Ollama fallida (ignorant): {e}")

        self.logger.info(f"Processant fitxer: {self.ruta_fitxer_actual}")
        ruta = self.ruta_fitxer_actual
        instruccions = self._obtenir_instruccions_usuari()

        # 1. Preparem la interfície per a l'espera
        self.btn_processar.configure(state="disabled", text="PROCESSANT...")
        self.progress_bar.pack(fill="x", pady=5)
        self.progress_bar.start()  # Activa l'animació de "spinner"
        self.btn_stop.pack(side="left", padx=5)
        self.btn_stop.configure(text="Aturar", state="normal")
        self.txt_resultat.delete("1.0", "end")
        self.txt_resultat.insert("end", "⏳ Connectant amb el servidor de IA...")

        # 2. Iniciem el cronòmetre i el fil de processament
        self._cancel_event.clear()
        self.cancellar_proces = False
        self.inici_temps = time.time()
        self.processant = True
        self._actualitzar_cronometre_visual()

        # Executem la IA en un fil a part perquè la GUI no es congeli
        self._worker_thread = threading.Thread(
            target=self._executar_logica_ia,
            args=(metode, ruta, instruccions),
            daemon=True
        )
        self._worker_thread.start()

    def _actualitzar_cronometre_visual(self):
        """Actualitza el text del temps cada 100ms mentre es processa."""
        if self.processant:
            temps_tardat = time.time() - self.inici_temps
            self.lbl_cronometre.configure(text=f"Temps: {temps_tardat:.1f}s")
            self.after(100, self._actualitzar_cronometre_visual)

    def _executar_logica_ia(self, metode, ruta_fitxer, instruccions):
        """Aquest mètode corre en segon pla."""
        self.logger.debug(f"Fil de processament iniciat (mètode: {metode}, instruccions: {bool(instruccions)})")

        try:
            if self._cancel_event.is_set():
                self.after(0, lambda: self._finalitzar_processament({"cancelled": True}))
                return

            res = self.transcription_service.processar(
                metode=metode,
                ruta_fitxer=ruta_fitxer,
                idioma="cat+spa",
                instruccions_extra=instruccions,
                cancel_event=self._cancel_event
            )

            self.logger.debug("Processament completat, tornant al fil principal")
            # Un cop tenim la resposta, tornem al fil principal per actualitzar la GUI
            if self._cancel_event.is_set():
                self.after(0, lambda: self._finalitzar_processament({"cancelled": True}))
                return
            self.after(0, lambda: self._finalitzar_processament(res))

        except Exception as e:
            self.logger.error(f"Error en fil de processament: {e}", exc_info=True)
            self.after(0, lambda: self._finalitzar_processament({"error": str(e)}))

    def _sollicitar_aturada(self):
        """Activa la bandera per aturar el processament per lots."""
        if not self.processant:
            return
        self.cancellar_proces = True
        self._cancel_event.set()
        self.btn_stop.configure(text="Aturant...", state="disabled")
        self.txt_resultat.delete("1.0", "end")
        self.txt_resultat.insert("end", "🛑 Cancel·lació sol·licitada. Esperant finalització segura...")

    def _reproduir_notificacio(self):
        """Reprodueix un so de notificació si està activat al .env."""
        if self.config_dades.get("enable_sound"):
            try:
                if not self._audio_inicialitzat:
                    pygame.mixer.init()
                    self._audio_inicialitzat = True

                ruta_so = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "notification.mp3")
                ruta_so = os.path.abspath(ruta_so)
                pygame.mixer.music.load(ruta_so)
                pygame.mixer.music.play()
            except Exception as e:
                self.logger.warning(f"No s'ha pogut reproduir el so de notificació: {e}")

    def _finalitzar_processament(self, resultat):
        """Restaura la interfície i mostra el resultat final."""
        self.processant = False
        self._worker_thread = None
        temps_final = time.time() - self.inici_temps

        # Verificar si hi ha error
        if isinstance(resultat, dict) and resultat.get("cancelled"):
            self.logger.info("Processament cancel·lat per l'usuari")
        elif isinstance(resultat, dict) and "error" in resultat:
            self.logger.error(f"Processament finalitzat amb error: {resultat['error']}")
        else:
            self.logger.info(f"Processament completat en {temps_final:.2f}s")

        self.progress_bar.stop()
        self.progress_bar.pack_forget()  # Amaguem la barra
        self.btn_processar.configure(state="normal", text="🚀 ANALITZAR DOCUMENT")

        self.btn_stop.pack_forget()  # Amaguem el botó Stop
        self.btn_stop.configure(text="Aturar", state="normal")

        self.txt_resultat.delete("1.0", "end")
        if isinstance(resultat, dict) and resultat.get("cancelled"):
            self.txt_resultat.insert("end", "🛑 Procés cancel·lat per l'usuari.")
            self.btn_editar.configure(state="disabled")
            self.btn_desar_bd.configure(state="disabled")
        elif isinstance(resultat, dict):
            self.txt_resultat.insert("end", json.dumps(resultat, indent=4, ensure_ascii=False))
            # Activar botons d'edició i desar BD si el resultat és un dict vàlid i no és un error
            if "error" not in resultat:
                self.btn_editar.configure(state="normal")
                self.btn_desar_bd.configure(state="normal")
            else:
                self.btn_editar.configure(state="disabled")
                self.btn_desar_bd.configure(state="disabled")
        else:
            self.txt_resultat.insert("end", str(resultat))
            self.btn_editar.configure(state="disabled")
            self.btn_desar_bd.configure(state="disabled")

        self.lbl_cronometre.configure(text=f"Finalitzat en: {temps_final:.2f}s")

        # REPRODUIR SO DE FINALITZACIÓ
        self._reproduir_notificacio()

    def _copiar_resultats(self):
        self.clipboard_clear()
        self.clipboard_append(self.txt_resultat.get("1.0", "end"))
        messagebox.showinfo("Copiat", "Resultat enviat al porta-retalls.")

    def _exportar_excel(self):
        self.logger.debug("Iniciant exportació a Excel")
        contingut = self.txt_resultat.get("1.0", "end").strip()
        try:
            dades = json.loads(contingut)
            valid, errors = ValidadorJSONTranscripcio.validar(dades)
            if not valid:
                self.logger.warning(f"Exportació Excel bloquejada per JSON invàlid: {errors[:3]}")
                messagebox.showerror(
                    "Error d'exportació",
                    "El JSON no compleix l'esquema esperat.\n"
                    f"Primer error: {errors[0]}"
                )
                return
            df = pd.DataFrame(dades.get("articles", []))
            ruta = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")])
            if ruta:
                df.to_excel(ruta, index=False)
                self.logger.info(f"Excel exportat correctament: {ruta}")
                messagebox.showinfo("Èxit", "Dades exportades correctament a Excel.")
        except json.JSONDecodeError as e:
            self.logger.error(f"Error JSON en exportació: {e}")
            messagebox.showerror("Error d'exportació", "El contingut no és JSON vàlid. Utilitza el mètode IA per obtenir resultats exportables.")
        except (KeyError, TypeError) as e:
            self.logger.error(f"Error de format en exportació: {e}")
            messagebox.showerror("Error d'exportació", f"Format de dades incorrecte: {e}")
        except PermissionError as e:
            self.logger.error(f"Error de permisos en exportació: {e}")
            messagebox.showerror("Error d'exportació", "No es pot escriure al fitxer. Comprova que no estigui obert.")
        except Exception as e:
            self.logger.error(f"Error inesperat en exportació: {e}", exc_info=True)
            messagebox.showerror("Error d'exportació", f"Error inesperat: {e}")

    def _netejar(self):
        self.txt_resultat.delete("1.0", "end")
        self.btn_editar.configure(state="disabled")
        self.btn_desar_bd.configure(state="disabled")
        self.canvas_imatge.delete("all")
        self.txt_ajuda_canvas = self.canvas_imatge.create_text(250, 250, text="Arrossega un document aquí\no prem 'Obrir fitxer...'", fill="#666666", font=("Arial", 12))
        self.ruta_fitxer_actual = None
        self.imatge_original = None
        self.zoom_level = 1.0
        self.lbl_zoom.configure(text="100%")
        # Netejar variables PDF
        self.ruta_pdf_actual = None
        self.total_pagines_pdf = 0
        self.pagina_actual = 0
        self.cache_pagines_pdf = {}
        # Netejar instruccions
        self.txt_instruccions.delete("1.0", "end")
        self._mostrar_placeholder_instruccions()
        # Resetejar plantilla
        self.plantilla_actual_id = None
        self.plantilla_var.set("Cap (configuració manual)")
        self.btn_veure_doc_ref.configure(state="disabled")
        self.btn_eliminar_plantilla.configure(state="disabled")
