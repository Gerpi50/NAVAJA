"""
ui/editor_panel.py — Escribir un texto acá mismo y guardarlo en el formato
que haga falta (o simplemente copiarlo).

Faltaba lo obvio: para pasar un texto a PDF había que escribirlo en otro
programa, guardarlo, traerlo a la cola y recién ahí convertirlo. Acá se
escribe de una, se ve cómo va a quedar y se guarda como MD, TXT, PDF, DOCX,
ODT, HTML o EPUB. Y si sólo era para copiar y pegar —un prompt, por ejemplo—
está el botón de copiar y no hace falta guardar nada.

Se escribe **como se escribe siempre**, sin aprender Markdown: el programa
deduce la estructura de la forma en que uno ya escribe (mayúsculas para los
títulos, incisos a) b), guiones para las viñetas, el punto para cerrar la
oración). Eso lo traduce `core/texto_natural.py`. El que sí sabe Markdown
puede cambiar el modo y escribirlo directo.

El borrador se guarda solo: si se cierra el programa, el texto sigue ahí.
"""
import os

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QPlainTextEdit,
    QTextBrowser, QSplitter, QFileDialog, QMessageBox, QCheckBox,
    QApplication, QComboBox, QFrame,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer

from core.paths import BASE_DIR, TEMP_DIR


# Formatos ofrecidos al guardar. MD y TXT se escriben derecho; el resto pasa
# por los motores de conversión, tomando el texto como Markdown.
FORMATOS = [
    ("md",   "Markdown (*.md)",            "Markdown"),
    ("txt",  "Texto plano (*.txt)",        "Texto plano"),
    ("pdf",  "PDF (*.pdf)",                "PDF"),
    ("docx", "Documento Word (*.docx)",    "Word"),
    ("odt",  "OpenDocument (*.odt)",       "OpenDocument"),
    ("html", "Página web (*.html)",        "Página web"),
    ("epub", "Libro digital (*.epub)",     "Libro digital"),
]

DIRECTOS = ("md", "txt")     # se escriben tal cual, sin convertir

MODO_COMUN    = "comun"      # se escribe normal y el programa interpreta
MODO_MARKDOWN = "markdown"   # el usuario escribe Markdown a mano

VISTA_RESULTADO = "resultado"   # se ve el texto con el formato aplicado
VISTA_MARKDOWN  = "markdown"    # se ve el código Markdown, para copiarlo


def _tabla_reglas() -> str:
    """La leyenda de cómo escribir, para mostrar arriba del editor."""
    from core.texto_natural import REGLAS
    filas = []
    for icono, nombre, regla, ejemplo in REGLAS:
        ej = (f"<code style='color:#0f766e'>{ejemplo}</code>"
              if ejemplo else "")
        filas.append(
            f"<tr>"
            f"<td style='padding-right:6px'>{icono}</td>"
            f"<td style='padding-right:8px'><b>{nombre}</b></td>"
            f"<td>{regla} {ej}</td>"
            f"</tr>")
    return ("<table style='font-size:11px'>" + "".join(filas) + "</table>")


LEYENDA_MARKDOWN = (
    "<span style='font-size:11px'>"
    "Escribiendo Markdown a mano: <code># Título</code> · "
    "<code>## Subtítulo</code> · <code>**negrita**</code> · "
    "<code>*cursiva*</code> · <code>- viñeta</code> · "
    "<code>1. numerada</code>"
    "</span>")


def formatos_disponibles() -> list:
    """Los formatos que este equipo puede generar de verdad."""
    disponibles = []
    for ext, filtro, nombre in FORMATOS:
        if ext in DIRECTOS:
            disponibles.append((ext, filtro, nombre))
            continue
        try:
            from core.graph import graph
            if graph.direct_motor("md", ext) or graph.find_path("md", ext):
                disponibles.append((ext, filtro, nombre))
        except Exception:
            pass
    return disponibles


# ── Worker: guardar (y convertir si hace falta) ──────────────────────────

class _GuardarWorker(QThread):
    listo = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, texto: str, destino: str):
        super().__init__()
        self.texto   = texto
        self.destino = destino

    def run(self):
        try:
            ext = os.path.splitext(self.destino)[1].lower().lstrip(".")
            carpeta = os.path.dirname(os.path.abspath(self.destino))
            if carpeta:
                os.makedirs(carpeta, exist_ok=True)

            if ext in DIRECTOS or not ext:
                with open(self.destino, "w", encoding="utf-8") as f:
                    f.write(self.texto)
                self.listo.emit(self.destino)
                return

            # El resto se arma escribiendo un Markdown temporal y
            # convirtiéndolo con los motores que ya tiene el programa.
            import tempfile
            from core.graph import graph

            os.makedirs(str(TEMP_DIR), exist_ok=True)
            tmp = tempfile.mkdtemp(prefix="escrito_", dir=str(TEMP_DIR))
            origen = os.path.join(tmp, "texto.md")
            with open(origen, "w", encoding="utf-8") as f:
                f.write(self.texto)

            try:
                motor = graph.direct_motor("md", ext)
                if motor:
                    motor().convert(origen, self.destino, "md", ext)
                else:
                    ruta = graph.find_path("md", ext)
                    if not ruta:
                        raise RuntimeError(
                            f"No hay forma de generar un archivo .{ext} en "
                            "este equipo.")
                    actual = origen
                    for paso in range(len(ruta) - 1):
                        src_ext, dst_ext = ruta[paso], ruta[paso + 1]
                        m = graph.direct_motor(src_ext, dst_ext)
                        if not m:
                            raise RuntimeError(
                                f"Falta el motor {src_ext} → {dst_ext}.")
                        siguiente = (self.destino
                                     if paso == len(ruta) - 2
                                     else os.path.join(tmp, f"paso{paso}.{dst_ext}"))
                        m().convert(actual, siguiente, src_ext, dst_ext)
                        actual = siguiente
            finally:
                import shutil
                shutil.rmtree(tmp, ignore_errors=True)

            if not os.path.exists(self.destino):
                raise RuntimeError("La conversión no generó el archivo.")
            self.listo.emit(self.destino)

        except Exception as e:
            self.error.emit(str(e))


# ── Panel ────────────────────────────────────────────────────────────────

class EditorPanel(QWidget):
    """Editor de texto con vista previa y guardado en varios formatos."""

    BORRADOR = os.path.join(BASE_DIR, "borrador.md")

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker = None
        self._ultima_carpeta = ""
        self._setup_ui()
        self._cargar_borrador()

    # ── Construcción ──────────────────────────────────────────────────
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        hdr = QLabel("✍️  Escribir")
        hdr.setObjectName("panelHeader")
        layout.addWidget(hdr)

        sub = QLabel(
            "Escribí como siempre —no hace falta saber Markdown— y copiá el "
            "texto, o guardalo como MD, TXT, PDF, Word, OpenDocument, HTML o "
            "EPUB. El borrador se guarda solo."
        )
        sub.setStyleSheet("font-size: 11px; color: #64748b;")
        sub.setWordWrap(True)
        layout.addWidget(sub)

        # ── Barra de botones ──────────────────────────────────────────
        barra = QHBoxLayout()

        btn_abrir = QPushButton("📂 Abrir")
        btn_abrir.setObjectName("ghostBtn")
        btn_abrir.setToolTip("Traer un .txt o .md que ya tengas para seguir "
                             "escribiéndolo.")
        btn_abrir.clicked.connect(self._abrir)
        barra.addWidget(btn_abrir)

        self.btn_copiar = QPushButton("📋 Copiar texto")
        self.btn_copiar.setObjectName("ghostBtn")
        self.btn_copiar.setToolTip("Copia el texto tal como lo escribiste.")
        self.btn_copiar.clicked.connect(self._copiar)
        barra.addWidget(self.btn_copiar)

        self.btn_copiar_md = QPushButton("📋 Copiar en Markdown")
        self.btn_copiar_md.setObjectName("ghostBtn")
        self.btn_copiar_md.setToolTip(
            "Copia el texto YA CONVERTIDO a Markdown, con los # de los "
            "títulos y los guiones de las listas.\n"
            "Sirve para pegarlo donde se espera Markdown, sin guardar nada.")
        self.btn_copiar_md.clicked.connect(self._copiar_markdown)
        barra.addWidget(self.btn_copiar_md)

        btn_limpiar = QPushButton("🗑 Limpiar")
        btn_limpiar.setObjectName("ghostBtn")
        btn_limpiar.clicked.connect(self._limpiar)
        barra.addWidget(btn_limpiar)

        self.chk_preview = QCheckBox("👁 Vista previa")
        self.chk_preview.setChecked(True)
        self.chk_preview.setToolTip(
            "Muestra cómo queda el texto con formato Markdown "
            "(# título, **negrita**, - listas).")
        self.chk_preview.toggled.connect(self._toggle_preview)
        barra.addWidget(self.chk_preview)
        barra.addStretch()
        layout.addLayout(barra)

        # Segunda fila: cómo se escribe y cómo se guarda. En una sola fila
        # no entraba con la ventana en su tamaño mínimo.
        fila_guardar = QHBoxLayout()
        fila_guardar.addWidget(QLabel("Escribo en:"))
        self.combo_modo = QComboBox()
        self.combo_modo.addItem("Texto común", MODO_COMUN)
        self.combo_modo.addItem("Markdown", MODO_MARKDOWN)
        self.combo_modo.setToolTip(
            "«Texto común»: escribí normal y el programa arma los títulos y "
            "las listas solo.\n"
            "«Markdown»: lo escribís vos, con # y **.")
        self.combo_modo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.combo_modo.setMinimumContentsLength(8)
        self.combo_modo.currentIndexChanged.connect(self._cambio_modo)
        fila_guardar.addWidget(self.combo_modo)

        self.btn_ayuda = QPushButton("❔ Cómo escribir")
        self.btn_ayuda.setObjectName("ghostBtn")
        self.btn_ayuda.setCheckable(True)
        self.btn_ayuda.setChecked(True)
        self.btn_ayuda.toggled.connect(self._toggle_leyenda)
        fila_guardar.addWidget(self.btn_ayuda)

        fila_guardar.addStretch()
        fila_guardar.addWidget(QLabel("Guardar como:"))
        self.combo_fmt = QComboBox()
        for ext, _filtro, nombre in formatos_disponibles():
            self.combo_fmt.addItem(f"{nombre}  (.{ext})", ext)
        self.combo_fmt.setToolTip("Formato con el que se va a guardar.")
        # Que pueda achicarse: si no, la fila no entra en la ventana chica.
        self.combo_fmt.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.combo_fmt.setMinimumContentsLength(8)
        fila_guardar.addWidget(self.combo_fmt)

        self.btn_guardar = QPushButton("💾 Guardar como...")
        self.btn_guardar.setObjectName("convertBtn")
        self.btn_guardar.setMinimumWidth(120)
        self.btn_guardar.clicked.connect(self._guardar_como)
        fila_guardar.addWidget(self.btn_guardar)
        layout.addLayout(fila_guardar)

        # ── Leyenda: cómo escribir para que salga bien ────────────────
        self.card_leyenda = QFrame()
        self.card_leyenda.setObjectName("card")
        cl = QVBoxLayout(self.card_leyenda)
        cl.setContentsMargins(12, 8, 12, 8)
        cl.setSpacing(2)
        self.lbl_leyenda = QLabel()
        self.lbl_leyenda.setWordWrap(True)
        self.lbl_leyenda.setMinimumWidth(120)
        self.lbl_leyenda.setMaximumWidth(1200)
        self.lbl_leyenda.setTextFormat(Qt.TextFormat.RichText)
        cl.addWidget(self.lbl_leyenda)
        layout.addWidget(self.card_leyenda)

        # ── Editor + vista previa ─────────────────────────────────────
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)

        self.editor = QPlainTextEdit()
        self.editor.setPlaceholderText(
            "Escribí acá, como escribirías en un Word.\n\n"
            "No hace falta saber nada raro: un renglón EN MAYÚSCULAS queda "
            "como título, los incisos a) b) quedan destacados, y un guión al "
            "principio del renglón arma una viñeta.\n\n"
            "Abajo, en «Cómo escribir», está la lista completa."
        )
        self.editor.setObjectName("docEditor")
        self.editor.setMinimumWidth(220)
        self.editor.textChanged.connect(self._on_cambio)
        self.splitter.addWidget(self.editor)

        # La vista previa tiene su propio encabezado: se puede ver "cómo
        # queda" o el Markdown que el programa armó, para copiarlo de ahí.
        caja_preview = QWidget()
        cp = QVBoxLayout(caja_preview)
        cp.setContentsMargins(0, 0, 0, 0)
        cp.setSpacing(4)

        fila_vista = QHBoxLayout()
        fila_vista.setContentsMargins(0, 0, 0, 0)
        fila_vista.addWidget(QLabel("Vista:"))
        self.combo_vista = QComboBox()
        self.combo_vista.addItem("Cómo queda", VISTA_RESULTADO)
        self.combo_vista.addItem("Markdown", VISTA_MARKDOWN)
        self.combo_vista.setToolTip(
            "«Cómo queda»: el texto con el formato ya aplicado.\n"
            "«Markdown»: el código Markdown que armó el programa, para "
            "copiarlo y pegarlo donde haga falta.")
        self.combo_vista.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.combo_vista.setMinimumContentsLength(8)
        self.combo_vista.currentIndexChanged.connect(self._refrescar_preview)
        fila_vista.addWidget(self.combo_vista)
        fila_vista.addStretch()
        cp.addLayout(fila_vista)

        self.preview = QTextBrowser()
        self.preview.setObjectName("docPreview")
        self.preview.setMinimumWidth(180)
        self.preview.setOpenExternalLinks(False)
        cp.addWidget(self.preview, stretch=1)

        self.caja_preview = caja_preview
        self.splitter.addWidget(caja_preview)
        self.splitter.setSizes([560, 440])

        layout.addWidget(self.splitter, stretch=1)

        # ── Pie: contadores y estado ──────────────────────────────────
        pie = QHBoxLayout()
        self.lbl_conteo = QLabel("")
        self.lbl_conteo.setStyleSheet("font-size: 11px; color: #64748b;")
        pie.addWidget(self.lbl_conteo)
        pie.addStretch()
        self.lbl_estado = QLabel("")
        self.lbl_estado.setStyleSheet("font-size: 11px; color: #475569;")
        self.lbl_estado.setWordWrap(True)
        pie.addWidget(self.lbl_estado)
        layout.addLayout(pie)

        # Vista previa y borrador con un respiro, para no recalcular en
        # cada tecla.
        self._t_preview = QTimer(self)
        self._t_preview.setSingleShot(True)
        self._t_preview.setInterval(250)
        self._t_preview.timeout.connect(self._refrescar_preview)

        self._t_borrador = QTimer(self)
        self._t_borrador.setSingleShot(True)
        self._t_borrador.setInterval(2000)
        self._t_borrador.timeout.connect(self._guardar_borrador)

        self._actualizar_conteo()
        self._actualizar_leyenda()
        self.btn_copiar_md.setVisible(self._modo() == MODO_COMUN)

    # ── Eventos del editor ────────────────────────────────────────────

    def _on_cambio(self):
        self._actualizar_conteo()
        if self.chk_preview.isChecked():
            self._t_preview.start()
        self._t_borrador.start()

    def _actualizar_conteo(self):
        texto = self.editor.toPlainText()
        palabras = len(texto.split())
        # Estimación gruesa: en español, alrededor de 4 caracteres por token.
        tokens = round(len(texto) / 4)
        self.lbl_conteo.setText(
            f"{len(texto):,} caracteres · {palabras:,} palabras · "
            f"~{tokens:,} tokens aprox.".replace(",", ".")
        )

    def _modo(self) -> str:
        return self.combo_modo.currentData() or MODO_COMUN

    def _markdown_actual(self) -> str:
        """El texto llevado a Markdown, según cómo esté escribiendo."""
        texto = self.editor.toPlainText()
        if self._modo() == MODO_MARKDOWN:
            return texto
        from core.texto_natural import a_markdown
        return a_markdown(texto)

    def _cambio_modo(self):
        # Escribiendo Markdown a mano, "copiar" y "copiar en Markdown" son lo
        # mismo: se deja uno solo para no confundir.
        self.btn_copiar_md.setVisible(self._modo() == MODO_COMUN)
        self._actualizar_leyenda()
        if self.chk_preview.isChecked():
            self._refrescar_preview()

    def _actualizar_leyenda(self):
        if self._modo() == MODO_MARKDOWN:
            self.lbl_leyenda.setText(LEYENDA_MARKDOWN)
        else:
            self.lbl_leyenda.setText(
                "<span style='font-size:11px;color:#475569'>"
                "Escribí normal, como en un Word. El programa arma los "
                "títulos y las listas con esto:</span>" + _tabla_reglas())

    def _toggle_leyenda(self, visible: bool):
        self.card_leyenda.setVisible(visible)
        self.btn_ayuda.setText("❔ Cómo escribir" if visible
                               else "❔ Cómo escribir")

    def _refrescar_preview(self):
        md = self._markdown_actual()
        if self.combo_vista.currentData() == VISTA_MARKDOWN:
            # El Markdown en crudo, para leerlo y copiarlo tal cual.
            self.preview.setPlainText(md)
            return
        try:
            self.preview.setMarkdown(md)
        except Exception:
            self.preview.setPlainText(self.editor.toPlainText())

    def _toggle_preview(self, activo: bool):
        self.caja_preview.setVisible(activo)
        if activo:
            self._refrescar_preview()

    # ── Botones ───────────────────────────────────────────────────────

    def _copiar(self):
        texto = self.editor.toPlainText()
        if not texto.strip():
            self.lbl_estado.setText("No hay nada para copiar.")
            return
        QApplication.clipboard().setText(texto)
        self.lbl_estado.setText("📋 Copiado al portapapeles.")

    def _copiar_markdown(self):
        md = self._markdown_actual()
        if not md.strip():
            self.lbl_estado.setText("No hay nada para copiar.")
            return
        QApplication.clipboard().setText(md)
        self.lbl_estado.setText(
            "📋 Copiado en Markdown (con los # y los guiones puestos).")

    def _limpiar(self):
        if self.editor.toPlainText().strip():
            r = QMessageBox.question(
                self, "Limpiar",
                "¿Borro todo lo escrito?\nEsto no se puede deshacer.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if r != QMessageBox.StandardButton.Yes:
                return
        self.editor.clear()
        self.preview.clear()
        self.lbl_estado.setText("")
        self._guardar_borrador()

    def _abrir(self):
        ruta, _ = QFileDialog.getOpenFileName(
            self, "Abrir un texto", self._ultima_carpeta,
            "Texto (*.txt *.md *.markdown);;Todos los archivos (*)")
        if not ruta:
            return
        try:
            with open(ruta, "r", encoding="utf-8", errors="replace") as f:
                contenido = f.read()
        except Exception as e:
            QMessageBox.warning(self, "Abrir", f"No pude abrir el archivo:\n{e}")
            return
        if self.editor.toPlainText().strip():
            r = QMessageBox.question(
                self, "Abrir",
                "Ya hay texto escrito. ¿Lo reemplazo por el del archivo?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if r != QMessageBox.StandardButton.Yes:
                return
        self._ultima_carpeta = os.path.dirname(ruta)
        self.editor.setPlainText(contenido)
        self.lbl_estado.setText(f"Abierto: {os.path.basename(ruta)}")

    def _guardar_como(self):
        texto = self.editor.toPlainText()
        if not texto.strip():
            QMessageBox.information(
                self, "Guardar", "Todavía no escribiste nada.")
            return

        ext = self.combo_fmt.currentData() or "md"
        filtros = {e: f for e, f, _n in FORMATOS}
        # El formato elegido primero, y el resto disponibles por si cambia
        # de idea en el mismo diálogo.
        orden = [filtros[ext]] + [f for e, f, _n in formatos_disponibles()
                                  if e != ext]
        sugerido = os.path.join(self._ultima_carpeta or "", f"texto.{ext}")

        ruta, filtro = QFileDialog.getSaveFileName(
            self, "Guardar como", sugerido, ";;".join(orden))
        if not ruta:
            return

        # Si el usuario cambió el filtro en el diálogo, manda ese.
        for e, f, _n in FORMATOS:
            if f == filtro:
                ext = e
                break
        if not os.path.splitext(ruta)[1]:
            ruta += f".{ext}"

        self._ultima_carpeta = os.path.dirname(ruta)
        self.btn_guardar.setEnabled(False)
        self.lbl_estado.setText(f"Guardando como .{ext}…")

        # El .txt sale tal cual se escribió; para todo lo demás se usa el
        # Markdown que el programa dedujo del texto.
        contenido = texto if ext == "txt" else self._markdown_actual()
        self._worker = _GuardarWorker(contenido, ruta)
        self._worker.listo.connect(self._guardado_ok)
        self._worker.error.connect(self._guardado_error)
        self._worker.start()

    def _guardado_ok(self, ruta: str):
        self.btn_guardar.setEnabled(True)
        try:
            mb = os.path.getsize(ruta) / 1024
            tam = f" ({mb:.0f} KB)" if mb >= 1 else ""
        except OSError:
            tam = ""
        self.lbl_estado.setText(f"✅ Guardado en {ruta}{tam}")

    def _guardado_error(self, msg: str):
        self.btn_guardar.setEnabled(True)
        self.lbl_estado.setText("")
        QMessageBox.warning(self, "Guardar", f"No se pudo guardar:\n{msg}")

    # ── Borrador ──────────────────────────────────────────────────────

    def _guardar_borrador(self):
        try:
            texto = self.editor.toPlainText()
            if texto.strip():
                with open(self.BORRADOR, "w", encoding="utf-8") as f:
                    f.write(texto)
            elif os.path.exists(self.BORRADOR):
                os.remove(self.BORRADOR)
        except Exception:
            pass      # el borrador es una comodidad, no puede romper nada

    def _cargar_borrador(self):
        try:
            if os.path.isfile(self.BORRADOR):
                with open(self.BORRADOR, "r", encoding="utf-8") as f:
                    texto = f.read()
                if texto.strip():
                    self.editor.setPlainText(texto)
                    self.lbl_estado.setText(
                        "Se recuperó el borrador de la vez anterior.")
        except Exception:
            pass
