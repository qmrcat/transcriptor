import customtkinter as ctk
from tkinter import filedialog, messagebox
from tkinterdnd2 import DND_FILES, TkinterDnD
from PIL import Image, ImageTk
import os
import json
import pandas as pd
from logic import TranscriptorTiquets, TranscriptorAmbCostos
import pdf2image
import time
import threading  # Perquè la interfície no es bloquegi mentre esperem la IA
import winsound  # Per a Windows
from utils import GestorConfiguracio, GestorLogging

os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
import pygame


class InterficieGrafica(TkinterDnD.Tk):

    def __init__(self):
        super().__init__()

        # Inicialitzar logger
        self.logger = GestorLogging.obtenir_logger("gui.InterficieGrafica")
        self.logger.info("Iniciant interfície gràfica")

        self.config_dades = GestorConfiguracio.carregar_config()
        self.logger.debug(f"Configuració carregada: so={self.config_dades.get('enable_sound')}")

        self.title("Transcriptor de Tiquets Pro - Digitalització")
        self.geometry("1300x850")
        ctk.set_appearance_mode("dark")

        # Inicialització lògica
        self.transcriptor = TranscriptorAmbCostos(api_key=self.config_dades.get("api_key"))

        self.ruta_fitxer_actual = None
        self.imatge_original = None
        self.zoom_level = 1.0

        # Variables per a PDFs (lazy loading)
        self.ruta_pdf_actual = None
        self.total_pagines_pdf = 0
        self.pagina_actual = 0
        self.cache_pagines_pdf = {}  # Cache per pàgines ja carregades

        self.cancellar_proces = False

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

        # Selector de Mètode
        self.radio_frame = ctk.CTkFrame(self.frame_dret)
        self.radio_frame.pack(pady=15, padx=15, fill="x")
        self.metode_var = ctk.StringVar(value="ocr")
        ctk.CTkLabel(self.radio_frame, text="Mètode d'extracció:", font=("Arial", 12, "bold")).pack(side="left", padx=15)
        ctk.CTkRadioButton(self.radio_frame, text="OCR Local", variable=self.metode_var, value="ocr").pack(side="left", padx=10)
        ctk.CTkRadioButton(self.radio_frame, text="IA (OpenAI)", variable=self.metode_var, value="openai").pack(side="left", padx=10)
        ctk.CTkRadioButton(self.radio_frame, text="Ollama (Local)", variable=self.metode_var, value="ollama").pack(side="left", padx=10)

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
        ctk.CTkButton(self.subframe_botons, text="Netejar", width=90, fg_color="#e74c3c", command=self._netejar).pack(side="right", padx=5)


    def _seleccionar_fitxer_manual(self):
        tipus = [("Tots els documents", "*.jpg *.jpeg *.png *.webp *.pdf"), ("Imatges", "*.jpg *.jpeg *.png *.webp"), ("PDF", "*.pdf")]
        ruta = filedialog.askopenfilename(filetypes=tipus)
        if ruta:
            self.logger.info(f"Fitxer seleccionat manualment: {ruta}")
            self.ruta_fitxer_actual = ruta
            self._mostrar_preview(ruta)


    def _configurar_dnd(self):
        self.canvas_imatge.drop_target_register(DND_FILES)
        self.canvas_imatge.dnd_bind('<<Drop>>', self._al_deixar_anar_fitxer)
        self.canvas_imatge.dnd_bind('<<DropEnter>>', lambda e: self.canvas_imatge.config(highlightbackground="#2ecc71"))
        self.canvas_imatge.dnd_bind('<<DropLeave>>', lambda e: self.canvas_imatge.config(highlightbackground="#444444"))
        self.canvas_imatge.bind("<ButtonPress-3>", lambda e: self.canvas_imatge.scan_mark(e.x, e.y))
        self.canvas_imatge.bind("<B2-Motion>", lambda e: self.canvas_imatge.scan_dragto(e.x, e.y, gain=1))
        # Nota: En alguns ratolins és el botó 2 (roda) o 3 (dret).

        # Vincular la roda del ratolí al desplaçament vertical
        # self.canvas_imatge.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas_imatge.bind_all("<MouseWheel>", self._gestionar_roda)

        # Si també vols scroll horitzontal amb Shift + Roda (molt útil per a zoom gran)
        self.canvas_imatge.bind_all("<Shift-MouseWheel>", self._on_mousewheel_h)


    def _on_mousewheel(self, event):
        """Gestiona el scroll vertical amb la roda del ratolí."""
        # En Windows, event.delta és 120 o -120. En Linux/macOS pot variar.
        # Dividim per -120 per fer que el moviment sigui suau i en la direcció correcta.
        self.canvas_imatge.yview_scroll(int(-1 * (event.delta / 120)), "units")


    def _on_mousewheel_h(self, event):
        """Gestiona el scroll horitzontal amb Shift + Roda del ratolí."""
        self.canvas_imatge.xview_scroll(int(-1 * (event.delta / 120)), "units")


    def _gestionar_roda(self, event):
        # Si la tecla Control està premuda, fem Zoom
        if event.state & 0x0004: # 0x0004 és el codi per a la tecla Ctrl
            if event.delta > 0:
                self._zoom(0.1)
            else:
                self._zoom(-0.1)
        else:
            # Si no, fem Scroll vertical normal
            self.canvas_imatge.yview_scroll(int(-1 * (event.delta / 120)), "units")   


    def _al_deixar_anar_fitxer(self, event):
        ruta = event.data.strip('{}')
        if ruta.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.pdf')):
            self.logger.info(f"Fitxer arrossegat: {ruta}")
            self.ruta_fitxer_actual = ruta
            self._mostrar_preview(ruta)
        else:
            self.logger.warning(f"Format no vàlid arrossegat: {ruta}")
            messagebox.showwarning("Format no vàlid", "Només acceptem imatges i PDFs.")


    def _mostrar_preview(self, ruta):
        """Carrega i mostra el document (Imatge o PDF) al canvas."""
        self.logger.debug(f"Mostrant preview de: {ruta}")
        self.canvas_imatge.delete("all")
        self.zoom_level = 1.0  # Reset zoom en carregar nou fitxer

        try:
            if ruta.lower().endswith(".pdf"):
                self.logger.debug("Detectat PDF, iniciant lazy loading")
                # Lazy loading: només obtenim el nombre de pàgines i carreguem la primera
                self.ruta_pdf_actual = ruta
                self.cache_pagines_pdf = {}  # Netejar cache anterior

                # Obtenir nombre total de pàgines sense carregar-les totes
                try:
                    info = pdf2image.pdfinfo_from_path(ruta)
                    self.total_pagines_pdf = info.get("Pages", 1)
                except Exception as e:
                    self.logger.debug(f"pdfinfo fallback: {e}")
                    # Fallback: carregar primera pàgina per obtenir info
                    primera = pdf2image.convert_from_path(ruta, first_page=1, last_page=1)
                    self.total_pagines_pdf = 1 if primera else 0

                self.logger.info(f"PDF carregat: {self.total_pagines_pdf} pàgines")
                self.pagina_actual = 0
                self.imatge_original = self._carregar_pagina_pdf(0)
                self._actualitzar_status_pagines()
            else:
                self.imatge_original = Image.open(ruta)
                self.logger.info(f"Imatge carregada: {self.imatge_original.size}")
                self.ruta_pdf_actual = None
                self.total_pagines_pdf = 0
                self.cache_pagines_pdf = {}
                self.lbl_pagines.configure(text="Imatge única")

            self._actualitzar_canvas()

        except Exception as e:
            self.logger.error(f"Error mostrant preview: {e}", exc_info=True)
            self.canvas_imatge.create_text(250, 250,
                text=f"❌ Error de previsualització:\n{str(e)}",
                fill="red", font=("Arial", 10), justify="center")
            messagebox.showerror("Error de lectura", f"No es pot previsualitzar el fitxer: {e}")

    def _carregar_pagina_pdf(self, num_pagina):
        """Carrega una pàgina específica del PDF (lazy loading amb cache)."""
        if num_pagina in self.cache_pagines_pdf:
            return self.cache_pagines_pdf[num_pagina]

        if not self.ruta_pdf_actual:
            return None

        # pdf2image usa índex 1-based
        pagines = pdf2image.convert_from_path(
            self.ruta_pdf_actual,
            first_page=num_pagina + 1,
            last_page=num_pagina + 1
        )

        if pagines:
            self.cache_pagines_pdf[num_pagina] = pagines[0]
            # Limitar cache a 5 pàgines per estalviar memòria
            if len(self.cache_pagines_pdf) > 5:
                oldest = min(k for k in self.cache_pagines_pdf if k != num_pagina)
                del self.cache_pagines_pdf[oldest]
            return pagines[0]
        return None


    def _actualitzar_status_pagines(self):
        total = self.total_pagines_pdf
        self.lbl_pagines.configure(text=f"Pàgina: {self.pagina_actual + 1} / {total}")

        # Desactivar botons si no hi ha més pàgines
        self.btn_prev.configure(state="normal" if self.pagina_actual > 0 else "disabled")
        self.btn_next.configure(state="normal" if self.pagina_actual < total - 1 else "disabled")


    def _pagina_anterior(self):
        if self.pagina_actual > 0:
            self.pagina_actual -= 1
            self.imatge_original = self._carregar_pagina_pdf(self.pagina_actual)
            self._actualitzar_status_pagines()
            self._actualitzar_canvas()

    def _pagina_seguent(self):
        if self.pagina_actual < self.total_pagines_pdf - 1:
            self.pagina_actual += 1
            self.imatge_original = self._carregar_pagina_pdf(self.pagina_actual)
            self._actualitzar_status_pagines()
            self._actualitzar_canvas()      


    def _actualitzar_canvas(self):
        if self.imatge_original:
            # Calculem la mida segons el zoom
            w_orig, h_orig = self.imatge_original.size
            
            # El zoom ara escala la imatge de veritat
            new_w = int(w_orig * self.zoom_level)
            new_h = int(h_orig * self.zoom_level)
            
            img_resized = self.imatge_original.resize((new_w, new_h), Image.Resampling.LANCZOS)
            self.tk_img = ImageTk.PhotoImage(img_resized)
            
            # Netegem i dibuixem
            self.canvas_imatge.delete("all")
            # Anchor "nw" (North-West) és millor per al sistema de scroll
            self.canvas_imatge.create_image(0, 0, anchor="nw", image=self.tk_img)
            
            # ACTUALITZACIÓ CLAU: Definim la regió de scroll segons la nova mida
            self.canvas_imatge.config(scrollregion=(0, 0, new_w, new_h))


    def _zoom(self, delta):
        # Ara permetem un zoom molt més gran (fins a 5.0x) per veure lletra petita
        self.zoom_level = max(0.1, min(5.0, self.zoom_level + delta))
        self.lbl_zoom.configure(text=f"{int(self.zoom_level * 100)}%")
        self._actualitzar_canvas()


    def _processar_fitxer(self):
        if not self.ruta_fitxer_actual:
            self.logger.warning("Intent de processar sense fitxer seleccionat")
            messagebox.showwarning("Atenció", "Selecciona un document primer.")
            return

        # Validació prèvia segons el mètode seleccionat
        metode = self.metode_var.get()
        self.logger.info(f"Iniciant processament amb mètode: {metode}")

        if metode == "openai" and not self.transcriptor.client:
            self.logger.error("Intent d'usar OpenAI sense API key")
            messagebox.showerror(
                "API Key no configurada",
                "Per utilitzar OpenAI, configura OPENAI_API_KEY al fitxer .env o config.json"
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

        # 1. Preparem la interfície per a l'espera
        self.btn_processar.configure(state="disabled", text="PROCESSANT...")
        self.progress_bar.pack(fill="x", pady=5)
        self.progress_bar.start()  # Activa l'animació de "spinner"
        self.txt_resultat.delete("1.0", "end")
        self.txt_resultat.insert("end", "⏳ Connectant amb el servidor de IA...")

        # 2. Iniciem el cronòmetre i el fil de processament
        self.inici_temps = time.time()
        self.processant = True
        self._actualitzar_cronometre_visual()

        # Executem la IA en un fil a part perquè la GUI no es congeli
        thread = threading.Thread(target=self._executar_logica_ia)
        thread.start()


    def _actualitzar_cronometre_visual(self):
        """Actualitza el text del temps cada 100ms mentre es processa."""
        if self.processant:
            temps_tardat = time.time() - self.inici_temps
            self.lbl_cronometre.configure(text=f"Temps: {temps_tardat:.1f}s")
            self.after(100, self._actualitzar_cronometre_visual)


    def _executar_logica_ia(self):
        """Aquest mètode corre en segon pla."""
        metode = self.metode_var.get()
        self.logger.debug(f"Fil de processament iniciat (mètode: {metode})")

        try:
            if metode == "ocr":
                res = self.transcriptor.processar_imatge_ocr(self.ruta_fitxer_actual)
            elif metode == "openai":
                res = self.transcriptor.processar_amb_openai(self.ruta_fitxer_actual)
            elif metode == "ollama":
                res = self.transcriptor.processar_amb_ollama(self.ruta_fitxer_actual)

            self.logger.debug("Processament completat, tornant al fil principal")
            # Un cop tenim la resposta, tornem al fil principal per actualitzar la GUI
            self.after(0, lambda: self._finalitzar_processament(res))

        except Exception as e:
            self.logger.error(f"Error en fil de processament: {e}", exc_info=True)
            self.after(0, lambda: self._finalitzar_processament({"error": str(e)}))

    def _sollicitar_aturada(self):
        """Activa la bandera per aturar el processament per lots."""
        self.cancellar_proces = True
        self.btn_stop.configure(text="Aturant...", state="disabled")


    # def _executar_logica_ia(self):
    #     metode = self.metode_var.get()
    #     resultats_acumulats = []
    #     self.cancellar_proces = False # Reset al començar
        
    #     # Mostrem el botó d'aturar al fil principal
    #     self.after(0, lambda: self.btn_stop.pack(side="left", padx=5))

    #     fitxers = self.cua_processament if hasattr(self, 'cua_processament') and self.cua_processament else [self.ruta_fitxer_actual]

    #     for i, ruta in enumerate(fitxers):
    #         # COMPROVACIÓ D'ATURADA: Si l'usuari ha premut Stop, sortim del bucle
    #         if self.cancellar_proces:
    #             self.after(0, lambda: self.txt_resultat.insert("end", "\n🛑 Procés cancel·lat per l'usuari.\n"))
    #             break

    #         self.after(0, lambda r=ruta, n=i+1: self.txt_resultat.insert("end", f"\n---\n📄 ({n}/{len(fitxers)}) {os.path.basename(r)}\n"))
            
    #         try:
    #             if metode == "ocr":
    #                 res = self.transcriptor.processar_imatge_ocr(ruta)
    #             elif metode == "openai":
    #                 res = self.transcriptor.processar_amb_openai(ruta)
    #             elif metode == "ollama":
    #                 res = self.transcriptor.processar_amb_ollama(ruta)
                
    #             resultats_acumulats.append(res)
    #         except Exception as e:
    #             resultats_acumulats.append({"error": str(e), "fitxer": ruta})

    #     self.after(0, lambda: self._finalitzar_processament(resultats_acumulats))


    def _reproduir_notificacio(self):
        """Reprodueix un so de notificació si està activat al .env."""
        import platform
        if self.config_dades.get("enable_sound"):
            try:
                if platform.system() == "Windows":
                    # So tipus "Asterisk" de Windows (suau i professional)
                    # winsound.Beep(1000, 200)
                    # Fallback per a altres sistemes operatius
                    # import pygame
                    pygame.mixer.init()
                    pygame.mixer.music.load('notification.mp3')  # Assegura't que aquest fitxer existeix
                    pygame.mixer.music.play()                    
                else:
                    # Fallback per a altres sistemes operatius
                    # import pygame
                    pygame.mixer.init()
                    pygame.mixer.music.load('notification.mp3')  # Assegura't que aquest fitxer existeix
                    pygame.mixer.music.play()
            except Exception as e:
                print(f"No s'ha pogut reproduir el so: {e}")


    def _finalitzar_processament(self, resultat):
        """Restaura la interfície i mostra el resultat final."""
        self.processant = False
        temps_final = time.time() - self.inici_temps

        # Verificar si hi ha error
        if isinstance(resultat, dict) and "error" in resultat:
            self.logger.error(f"Processament finalitzat amb error: {resultat['error']}")
        else:
            self.logger.info(f"Processament completat en {temps_final:.2f}s")

        self.progress_bar.stop()
        self.progress_bar.pack_forget()  # Amaguem la barra
        self.btn_processar.configure(state="normal", text="🚀 ANALITZAR DOCUMENT")

        self.btn_stop.pack_forget()  # Amaguem el botó Stop
        self.btn_stop.configure(text="Aturar", state="normal")

        self.txt_resultat.delete("1.0", "end")
        if isinstance(resultat, dict):
            self.txt_resultat.insert("end", json.dumps(resultat, indent=4, ensure_ascii=False))
        else:
            self.txt_resultat.insert("end", str(resultat))

        self.lbl_cronometre.configure(text=f"Finalitzat en: {temps_final:.2f}s")

        # REPRODUIR SO DE FINALITZACIÓ
        self._reproduir_notificacio()


    # def _finalitzar_processament(self, resultats):
    #     self.processant = False
    #     temps_final = time.time() - self.inici_temps
        
    #     self.progress_bar.stop()
    #     self.progress_bar.pack_forget()
    #     self.btn_stop.pack_forget()
    #     self.btn_processar.configure(state="normal", text="🚀 ANALITZAR DOCUMENT")
        
    #     self.txt_resultat.delete("1.0", "end")
        
    #     # Cas A: Hem processat diversos fitxers (Llista)
    #     if isinstance(resultats, list):
    #         # Formatem la llista per a que es vegi bé al Textbox
    #         text_formatat = json.dumps(resultats, indent=4, ensure_ascii=False)
    #         self.txt_resultat.insert("end", text_formatat)
            
    #         # self.txt_resultat.insert("end", f"\n\n✅ Processament per lots finalitzat.")
    #         self.txt_resultat.insert("end", f"\n\n✅ Processament finalitzat.")
            
    #         # # Preguntar per l'exportació col·lectiva
    #         # if messagebox.askyesno("Exportar tot", f"S'han processat {len(resultats)} tiquets. Vols exportar-los a un sol Excel?"):
    #         #     self._exportar_tots_a_excel(resultats)
        
    #     # Cas B: Procés individual (Diccionari)
    #     else:
    #         text_formatat = json.dumps(resultats, indent=4, ensure_ascii=False)
    #         self.txt_resultat.insert("end", text_formatat)

    #     self.lbl_cronometre.configure(text=f"Finalitzat en: {temps_final:.2f}s")
    #     self._reproduir_notificacio()


    def _copiar_resultats(self):
        self.clipboard_clear()
        self.clipboard_append(self.txt_resultat.get("1.0", "end"))
        messagebox.showinfo("Copiat", "Resultat enviat al porta-retalls.")


    def _exportar_excel(self):
        self.logger.debug("Iniciant exportació a Excel")
        contingut = self.txt_resultat.get("1.0", "end").strip()
        try:
            dades = json.loads(contingut)
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

