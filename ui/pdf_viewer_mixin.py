from tkinter import filedialog, messagebox

from tkinterdnd2 import DND_FILES
from PIL import Image, ImageTk
import pdf2image


class PDFViewerMixin:
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
        if event.state & 0x0004:  # 0x0004 és el codi per a la tecla Ctrl
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

