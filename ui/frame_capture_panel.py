"""
ui/frame_capture_panel.py — Navegador de fotogramas y captura del momento exacto.

El caso que resuelve: el investigador mira la grabación de una cámara de
seguridad, encuentra el instante del hecho y necesita llevarse esa imagen con
el minuto y segundo precisos, con constancia de hashes.

Por qué un navegador y no un reproductor: acá la imagen la decodifica FFmpeg,
el mismo que después guarda la captura. Así el fotograma que se ve es
exactamente el que se guarda, y además abre cualquier códec raro que salga de
un DVR, sin depender de los códecs que tenga instalado Windows.
"""
import os
import platform
import shutil
import subprocess

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QSlider, QLineEdit, QCheckBox, QDoubleSpinBox, QFileDialog, QListWidget,
    QSizePolicy, QMessageBox,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QMutex, QWaitCondition
from PyQt6.QtGui import QPixmap, QShortcut, QKeySequence

from core.salidas import carpeta_destino, etiqueta_destino, preparar_destino
from core.paths import TEMP_DIR


VIDEO_FILTRO = ("Videos (*.mp4 *.mkv *.avi *.mov *.webm *.flv *.wmv *.m4v "
                "*.3gp *.ts *.mpg *.mpeg *.ogv *.vob *.f4v *.dav *.asf)")


# ── Hilo que va a buscar los fotogramas ──────────────────────────────────────

class _NavegadorWorker(QThread):
    """Extrae el fotograma pedido sin congelar la ventana.

    Guarda un solo pedido pendiente: si el usuario arrastra el slider, los
    tiempos intermedios se descartan y solo se busca el último. Sin esto, se
    encolarían decenas de extracciones y la imagen llegaría siempre tarde.
    """
    listo = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._mutex = QMutex()
        self._espera = QWaitCondition()
        self._pedido = None
        self._activo = True
        self._turno = 0

    def pedir(self, src: str, t: float, desentrelazar: bool, paso: int = 0):
        """paso: 0 = ir al tiempo t; -1/+1 = un fotograma antes/después de t."""
        self._mutex.lock()
        self._turno += 1
        self._pedido = (src, t, desentrelazar, paso, self._turno)
        self._espera.wakeAll()
        self._mutex.unlock()

    def detener(self):
        self._mutex.lock()
        self._activo = False
        self._espera.wakeAll()
        self._mutex.unlock()
        self.wait(3000)

    def run(self):
        from motors import motor_video_frames as mvf

        while True:
            self._mutex.lock()
            while self._activo and self._pedido is None:
                self._espera.wait(self._mutex)
            if not self._activo:
                self._mutex.unlock()
                return
            src, t, desentrelazar, paso, turno = self._pedido
            self._pedido = None
            self._mutex.unlock()

            try:
                if paso:
                    t = mvf.fotograma_vecino(src, t, paso)
                # Se rotan cuatro nombres: si se reusara uno solo, FFmpeg
                # podría estar escribiéndolo justo cuando Qt lo lee.
                destino = os.path.join(TEMP_DIR, f"vista_previa_{turno % 4}.png")
                datos = mvf.extraer_fotograma(src, t, destino, desentrelazar)
                if self._pedido is None:      # nadie pidió algo más nuevo
                    self.listo.emit(datos)
            except Exception as e:
                self.error.emit(str(e))


class _TareaWorker(QThread):
    """Captura, ráfaga y recorte: tareas puntuales que pueden tardar."""
    listo = pyqtSignal(str, list)     # mensaje, archivos generados
    aviso = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, tarea, **kw):
        super().__init__()
        self.tarea = tarea
        self.kw = kw

    def run(self):
        try:
            getattr(self, f"_{self.tarea}")()
        except Exception as e:
            self.error.emit(str(e))

    # ── Capturar el fotograma que se está viendo ─────────────────────────
    def _capturar(self):
        from motors import motor_video_frames as mvf

        ficha = self.kw["ficha"]
        captura = dict(self.kw["captura"])
        destino = preparar_destino(ficha["path"], self.kw["out_dir"])
        stem = os.path.splitext(os.path.basename(ficha["path"]))[0]
        nombre = f"{stem}_{mvf._nombre_de_tiempo(captura['t'])}.png"
        final = os.path.join(destino, nombre)

        # Se copia el PNG que ya está en pantalla: lo que se ve es lo que se
        # guarda, sin volver a decodificar nada.
        shutil.copy2(captura["archivo"], final)
        captura["archivo"] = final
        generados = [final]

        if self.kw.get("con_constancia", True):
            self.aviso.emit("🔢 Calculando hashes para la constancia…")
            texto = mvf.constancia(ficha, captura, [final],
                                   herramienta=self.kw.get("herramienta", ""))
            acta = os.path.splitext(final)[0] + "_constancia.txt"
            with open(acta, "w", encoding="utf-8") as f:
                f.write(texto)
            generados.append(acta)

        self.listo.emit(f"✅ Fotograma capturado: {nombre}", generados)

    # ── Ráfaga alrededor del momento ─────────────────────────────────────
    def _rafaga(self):
        from motors import motor_video_frames as mvf

        ficha = self.kw["ficha"]
        t = self.kw["t"]
        margen = self.kw["margen"]
        destino = preparar_destino(ficha["path"], self.kw["out_dir"])
        stem = os.path.splitext(os.path.basename(ficha["path"]))[0]
        carpeta = os.path.join(
            destino, f"{stem}_rafaga_{mvf._nombre_de_tiempo(t)}")

        frames = mvf.rafaga(ficha["path"], t - margen, t + margen, carpeta,
                            self.kw.get("desentrelazar", False),
                            progress_cb=self.aviso.emit)
        generados = [f["archivo"] for f in frames]

        if self.kw.get("con_constancia", True) and frames:
            self.aviso.emit("🔢 Calculando hashes para la constancia…")
            centro = min(frames, key=lambda f: abs(f["t"] - t))
            texto = mvf.constancia(ficha, centro, generados,
                                   herramienta=self.kw.get("herramienta", ""))
            acta = os.path.join(carpeta, "constancia.txt")
            with open(acta, "w", encoding="utf-8") as f:
                f.write(texto)
            generados.append(acta)

        self.listo.emit(
            f"✅ {len(frames)} fotogramas guardados en «{os.path.basename(carpeta)}»",
            generados)

    # ── Pedazo del video original, sin recodificar ───────────────────────
    def _segmento(self):
        from motors import motor_video_frames as mvf

        ficha = self.kw["ficha"]
        t = self.kw["t"]
        margen = self.kw["margen"]
        destino = preparar_destino(ficha["path"], self.kw["out_dir"])
        stem, ext = os.path.splitext(os.path.basename(ficha["path"]))
        final = os.path.join(
            destino, f"{stem}_segmento_{mvf._nombre_de_tiempo(t)}{ext}")

        self.aviso.emit("✂️  Recortando sin recodificar…")
        mvf.recortar_original(ficha["path"], t - margen, t + margen, final)
        self.listo.emit(
            f"✅ Segmento guardado: {os.path.basename(final)}", [final])


# ── Panel ────────────────────────────────────────────────────────────────────

class FrameCapturePanel(QWidget):
    """Navegador de fotogramas con captura del momento exacto."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(520)
        self._src_path = ""
        self._out_dir = ""
        self._ficha = None
        self._captura = None        # último fotograma mostrado
        self._nav = None
        self._tarea = None
        self._arrastrando = False
        self._setup_ui()

    # ── Construcción ─────────────────────────────────────────────────────
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        hdr = QLabel("📸  Capturar fotograma")
        hdr.setStyleSheet("font-size: 16px; font-weight: 800;")
        layout.addWidget(hdr)

        sub = QLabel(
            "Buscá el momento exacto de la grabación y llevate esa imagen con "
            "su minuto y segundo, más una constancia con los hashes."
        )
        sub.setStyleSheet("font-size: 11px; color: #64748b;")
        sub.setWordWrap(True)
        layout.addWidget(sub)

        try:
            from motors.motor_video_frames import is_available
            if not is_available():
                warn = QLabel(
                    "⚠️  La captura de fotogramas necesita FFmpeg.\n"
                    "Pedile al administrador que coloque ffmpeg.exe y "
                    "ffprobe.exe en la carpeta bin/ del programa."
                )
                warn.setStyleSheet(
                    "background: #fffbeb; border: 1px solid #f59e0b; "
                    "border-radius: 6px; padding: 10px; color: #92400e;")
                warn.setWordWrap(True)
                layout.addWidget(warn)
                layout.addStretch()
                return
        except Exception:
            pass

        # ── Archivo ──────────────────────────────────────────────────────
        card1 = QFrame()
        card1.setObjectName("card")
        c1 = QVBoxLayout(card1)
        c1.setContentsMargins(12, 10, 12, 10)
        c1.setSpacing(8)

        fila = QHBoxLayout()
        self.lbl_file = QLabel("No se eligió ningún video")
        self.lbl_file.setStyleSheet("font-size: 11px; color: #64748b;")
        self.lbl_file.setWordWrap(True)
        fila.addWidget(self.lbl_file, stretch=1)
        btn_pick = QPushButton("📁 Elegir video")
        btn_pick.setObjectName("ghostBtn")
        btn_pick.clicked.connect(self._elegir_video)
        fila.addWidget(btn_pick)
        btn_limpiar = QPushButton("🗑 Limpiar")
        btn_limpiar.setObjectName("ghostBtn")
        btn_limpiar.setToolTip(
            "Deja la solapa como recién abierta, para empezar con otro "
            "archivo.\nNo borra nada del disco.")
        btn_limpiar.clicked.connect(self._limpiar)
        fila.addWidget(btn_limpiar)
        c1.addLayout(fila)

        self.lbl_ficha = QLabel("")
        self.lbl_ficha.setStyleSheet("font-size: 11px; color: #475569;")
        self.lbl_ficha.setWordWrap(True)
        c1.addWidget(self.lbl_ficha)

        self.lbl_alertas = QLabel("")
        self.lbl_alertas.setStyleSheet(
            "background: #fffbeb; border: 1px solid #f59e0b; border-radius: 6px; "
            "padding: 8px; color: #92400e; font-size: 11px;")
        self.lbl_alertas.setWordWrap(True)
        self.lbl_alertas.setVisible(False)
        c1.addWidget(self.lbl_alertas)
        layout.addWidget(card1)

        # ── Imagen ───────────────────────────────────────────────────────
        self.vista = QLabel("Elegí un video para empezar")
        self.vista.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # 320 px empujaban el botón de capturar fuera de la pantalla en un
        # monitor común. La imagen igual crece con la ventana.
        self.vista.setMinimumHeight(260)
        self.vista.setStyleSheet(
            "background: #0f172a; color: #64748b; border-radius: 8px; "
            "font-size: 12px;")
        self.vista.setSizePolicy(QSizePolicy.Policy.Expanding,
                                 QSizePolicy.Policy.Expanding)
        layout.addWidget(self.vista, stretch=1)

        # ── Dónde estamos ────────────────────────────────────────────────
        self.lbl_momento = QLabel("—")
        self.lbl_momento.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_momento.setStyleSheet(
            "font-size: 13px; font-weight: 700; color: #1e3a8a; "
            "background: #dbeafe; border-radius: 6px; padding: 6px;")
        self.lbl_momento.setWordWrap(True)
        layout.addWidget(self.lbl_momento)

        # ── Línea de tiempo ──────────────────────────────────────────────
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.setEnabled(False)
        self.slider.sliderPressed.connect(lambda: setattr(self, "_arrastrando", True))
        self.slider.sliderReleased.connect(self._soltar_slider)
        self.slider.valueChanged.connect(self._mover_slider)
        layout.addWidget(self.slider)

        # ── Botonera de paso ─────────────────────────────────────────────
        pasos = QHBoxLayout()
        pasos.setSpacing(4)
        self._botones_paso = []
        for etiqueta, accion, ayuda in [
            ("⏪ -10s", ("salto", -10.0), "Diez segundos atrás"),
            ("◀ -1s", ("salto", -1.0), "Un segundo atrás"),
            ("◁ -1", ("paso", -1), "Un fotograma atrás  (flecha izquierda)"),
            ("+1 ▷", ("paso", 1), "Un fotograma adelante  (flecha derecha)"),
            ("+1s ▶", ("salto", 1.0), "Un segundo adelante"),
            ("+10s ⏩", ("salto", 10.0), "Diez segundos adelante"),
        ]:
            btn = QPushButton(etiqueta)
            btn.setObjectName("presetBtn")
            btn.setToolTip(ayuda)
            btn.setEnabled(False)
            btn.clicked.connect(lambda _, a=accion: self._navegar(*a))
            pasos.addWidget(btn)
            self._botones_paso.append(btn)
        layout.addLayout(pasos)

        # ── Ir a un tiempo escrito ───────────────────────────────────────
        ir = QHBoxLayout()
        ir.addWidget(QLabel("Ir al tiempo:"))
        self.txt_tiempo = QLineEdit()
        self.txt_tiempo.setPlaceholderText("00:04:17.320")
        self.txt_tiempo.setMaximumWidth(140)
        self.txt_tiempo.returnPressed.connect(self._ir_a_tiempo)
        ir.addWidget(self.txt_tiempo)
        self.btn_ir = QPushButton("Ir")
        self.btn_ir.setObjectName("ghostBtn")
        self.btn_ir.setEnabled(False)
        self.btn_ir.clicked.connect(self._ir_a_tiempo)
        ir.addWidget(self.btn_ir)
        ir.addStretch()
        self.chk_deint = QCheckBox("Desentrelazar")
        self.chk_deint.setToolTip(
            "Solo si la grabación se ve con el efecto peine.\n"
            "Cambia los píxeles de la imagen, así que queda anotado\n"
            "en la constancia.")
        self.chk_deint.stateChanged.connect(lambda _: self._navegar("salto", 0.0))
        ir.addWidget(self.chk_deint)
        layout.addLayout(ir)

        # Primero la acción, después los ajustes: el botón de capturar es
        # lo que el usuario viene a tocar y estaba debajo del borde de la
        # pantalla, tapado por la carpeta de salida y la constancia.
        # ── Acciones ─────────────────────────────────────────────────────
        self.btn_capturar = QPushButton("📸  Capturar este fotograma")
        self.btn_capturar.setObjectName("convertBtn")
        self.btn_capturar.setEnabled(False)
        self.btn_capturar.clicked.connect(self._capturar)
        layout.addWidget(self.btn_capturar)

        extras = QHBoxLayout()
        self.btn_rafaga = QPushButton("🎞️  Ráfaga de")
        self.btn_rafaga.setObjectName("ghostBtn")
        self.btn_rafaga.setEnabled(False)
        self.btn_rafaga.setToolTip(
            "Guarda todos los fotogramas alrededor del momento elegido.\n"
            "El hecho no siempre cae en el fotograma que uno eligió primero.")
        self.btn_rafaga.clicked.connect(self._rafaga)
        extras.addWidget(self.btn_rafaga)

        self.spin_rafaga = QDoubleSpinBox()
        self.spin_rafaga.setRange(0.1, 30.0)
        self.spin_rafaga.setValue(2.0)
        self.spin_rafaga.setSingleStep(0.5)
        self.spin_rafaga.setSuffix(" s antes y después")
        extras.addWidget(self.spin_rafaga)
        extras.addStretch()
        layout.addLayout(extras)

        extras2 = QHBoxLayout()
        self.btn_segmento = QPushButton("✂️  Guardar el video original de")
        self.btn_segmento.setObjectName("ghostBtn")
        self.btn_segmento.setEnabled(False)
        self.btn_segmento.setToolTip(
            "Recorta un pedazo del video sin recodificar: los bits son los\n"
            "del original. El corte se pega al cuadro clave anterior, así que\n"
            "puede arrancar unos segundos antes de lo pedido.")
        self.btn_segmento.clicked.connect(self._segmento)
        extras2.addWidget(self.btn_segmento)

        self.spin_segmento = QDoubleSpinBox()
        self.spin_segmento.setRange(1.0, 300.0)
        self.spin_segmento.setValue(5.0)
        self.spin_segmento.setSuffix(" s antes y después")
        extras2.addWidget(self.spin_segmento)
        extras2.addStretch()
        layout.addLayout(extras2)

        # ── Salida ───────────────────────────────────────────────────────
        card3 = QFrame()
        card3.setObjectName("card")
        c3 = QVBoxLayout(card3)
        c3.setContentsMargins(12, 10, 12, 10)
        c3.setSpacing(8)

        out_row = QHBoxLayout()
        out_row.addWidget(QLabel("Carpeta de salida:"))
        self.lbl_out = QLabel(etiqueta_destino(""))
        self.lbl_out.setStyleSheet("font-size: 11px; color: #64748b;")
        self.lbl_out.setWordWrap(True)
        out_row.addWidget(self.lbl_out, stretch=1)
        btn_out = QPushButton("Cambiar")
        btn_out.setObjectName("ghostBtn")
        btn_out.clicked.connect(self._elegir_carpeta)
        out_row.addWidget(btn_out)
        c3.addLayout(out_row)

        self.chk_constancia = QCheckBox(
            "Generar constancia con los hashes (SHA-256 y MD5)")
        self.chk_constancia.setChecked(True)
        self.chk_constancia.setToolTip(
            "Deja al lado de la imagen un texto con el tiempo exacto y los\n"
            "hashes del video y de la foto: con eso cualquiera puede verificar\n"
            "después que la imagen salió de ese video y que nadie la tocó.")
        c3.addWidget(self.chk_constancia)
        layout.addWidget(card3)

        self.lbl_estado = QLabel("")
        self.lbl_estado.setStyleSheet("font-size: 11px; color: #475569;")
        self.lbl_estado.setWordWrap(True)
        layout.addWidget(self.lbl_estado)

        self.lista = QListWidget()
        self.lista.setMaximumHeight(110)
        self.lista.setVisible(False)
        layout.addWidget(self.lista)

        self.btn_abrir = QPushButton("📂 Abrir carpeta de resultados")
        self.btn_abrir.setObjectName("ghostBtn")
        self.btn_abrir.setVisible(False)
        self.btn_abrir.clicked.connect(self._abrir_carpeta)
        layout.addWidget(self.btn_abrir)

        # Atajos: las flechas son la forma natural de recorrer fotogramas.
        for secuencia, accion in [
            ("Left", ("paso", -1)), ("Right", ("paso", 1)),
            ("Shift+Left", ("salto", -1.0)), ("Shift+Right", ("salto", 1.0)),
            ("PgUp", ("salto", -10.0)), ("PgDown", ("salto", 10.0)),
        ]:
            atajo = QShortcut(QKeySequence(secuencia), self)
            atajo.activated.connect(lambda a=accion: self._navegar(*a))

    # ── Elegir archivo y carpeta ─────────────────────────────────────────
    def _elegir_video(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Elegir video de la cámara", "", VIDEO_FILTRO)
        if path:
            self.cargar_video(path)

    def cargar_video(self, path: str, momento: float = 0.0):
        """Carga un video y se para en `momento`.

        Es pública porque el mapa del video la usa: al tocar una miniatura,
        esta solapa abre el mismo archivo ya parado en ese punto.
        """
        try:
            from motors import motor_video_frames as mvf
            ficha = mvf.info_video(path)
        except Exception as e:
            QMessageBox.warning(self, "No se pudo leer el video", str(e))
            return

        self._src_path = path
        self._ficha = ficha
        self._captura = None
        self.lbl_file.setText(os.path.basename(path))
        self.lbl_out.setText(carpeta_destino(path, self._out_dir))

        cadencia = f"{ficha['fps']:.2f} cuadros/s" if ficha["fps"] else "cadencia desconocida"
        partes = [ficha["duracion_hms"],
                  f"{ficha['ancho']}x{ficha['alto']} px",
                  ficha["codec"], cadencia]
        if ficha["inicio_grabacion"]:
            partes.append(f"inicio {ficha['inicio_grabacion'][:19].replace('T', ' ')}")
        self.lbl_ficha.setText("  ·  ".join(partes))

        alertas = []
        if ficha["vfr"]:
            alertas.append(
                "Este video es de cadencia variable: no se puede numerar los "
                "fotogramas, se informa el tiempo exacto de cada uno.")
        if not ficha["inicio_grabacion"]:
            alertas.append(
                "El archivo no declara la hora de inicio de la grabación, así "
                "que no se puede calcular la hora real del hecho. Si la cámara "
                "imprime la hora sobre la imagen, esa es la que vale.")
        if ficha["entrelazado"]:
            alertas.append(
                "La grabación es entrelazada: si ves el efecto peine, probá "
                "la casilla «Desentrelazar».")
        self.lbl_alertas.setText("⚠️  " + "\n\n⚠️  ".join(alertas) if alertas else "")
        self.lbl_alertas.setVisible(bool(alertas))

        # El slider trabaja en milésimas para poder pararse en cualquier lado.
        self.slider.setRange(0, max(1, int(ficha["duracion"] * 1000)))
        self.slider.setEnabled(True)
        self.btn_ir.setEnabled(True)
        for btn in self._botones_paso:
            btn.setEnabled(True)

        self._arrancar_navegador()
        self._navegar("salto", 0.0, desde=max(0.0, momento))

    def _limpiar(self):
        if self._tarea and self._tarea.isRunning():
            return
        self._src_path = ""
        self._out_dir = ""
        self._ultima_carpeta = ""
        self._ficha = None
        self._captura = None
        self.lbl_file.setText("No se eligió ningún video")
        self.lbl_ficha.setText("")
        self.lbl_alertas.setVisible(False)
        self.lbl_out.setText(etiqueta_destino(""))
        self.vista.clear()
        self.vista.setText("Elegí un video para empezar")
        self.lbl_momento.setText("—")
        self.slider.blockSignals(True)
        self.slider.setRange(0, 0)
        self.slider.blockSignals(False)
        self.slider.setEnabled(False)
        self.txt_tiempo.clear()
        for btn in (self.btn_ir, self.btn_capturar, self.btn_rafaga,
                    self.btn_segmento, *self._botones_paso):
            btn.setEnabled(False)
        self.lbl_estado.setText("")
        self.lista.clear()
        self.lista.setVisible(False)
        self.btn_abrir.setVisible(False)

    def ir_a_momento(self, path: str, t: float):
        """Abre el video (si no estaba abierto) y se para en ese momento.

        Lo llama el mapa del video cuando se toca una miniatura. Si es el
        mismo archivo que ya está cargado no se vuelve a leer la ficha: se
        salta y listo.
        """
        if self._src_path and os.path.abspath(path) == os.path.abspath(self._src_path):
            self._navegar("salto", 0.0, desde=t)
        else:
            self.cargar_video(path, t)

    def _elegir_carpeta(self):
        d = QFileDialog.getExistingDirectory(self, "Carpeta de salida")
        if d:
            self._out_dir = d
            self.lbl_out.setText(d)

    # ── Navegación ───────────────────────────────────────────────────────
    def _arrancar_navegador(self):
        if self._nav is None:
            self._nav = _NavegadorWorker()
            self._nav.listo.connect(self._mostrar_fotograma)
            self._nav.error.connect(self._error_navegando)
            self._nav.start()

    def _tiempo_actual(self) -> float:
        if self._captura:
            return self._captura["t"]
        return self.slider.value() / 1000.0

    def _navegar(self, modo: str, valor: float, desde: float = None):
        if not self._src_path or self._nav is None:
            return
        base = self._tiempo_actual() if desde is None else desde
        if modo == "paso":
            self._nav.pedir(self._src_path, base, self.chk_deint.isChecked(),
                            int(valor))
        else:
            destino = base + valor
            if self._ficha:
                destino = max(0.0, min(destino, max(0.0, self._ficha["duracion"] - 0.001)))
            self._nav.pedir(self._src_path, destino, self.chk_deint.isChecked())

    def _mover_slider(self, valor: int):
        # Mientras se arrastra no se pide nada: se espera a que suelte, si no
        # se dispararían decenas de extracciones por cada movimiento.
        if self._arrastrando or not self._src_path or self._nav is None:
            return
        self._nav.pedir(self._src_path, valor / 1000.0, self.chk_deint.isChecked())

    def _soltar_slider(self):
        self._arrastrando = False
        self._mover_slider(self.slider.value())

    def _ir_a_tiempo(self):
        from motors import motor_video_frames as mvf
        t = mvf.segundos(self.txt_tiempo.text())
        if t is None:
            self.lbl_estado.setText(
                "⚠️  No entendí ese tiempo. Escribilo como 00:04:17.320")
            return
        self._navegar("salto", 0.0, desde=t)

    def _mostrar_fotograma(self, datos: dict):
        from motors import motor_video_frames as mvf

        # Fotograma que llega tarde, después de «Limpiar»: no se muestra.
        if not self._src_path:
            return

        self._captura = datos
        pix = QPixmap(datos["archivo"])
        if not pix.isNull():
            self.vista.setPixmap(pix.scaled(
                self.vista.size(), Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))

        partes = [f"⏱️  {datos['t_hms']}"]
        n = mvf.numero_de_fotograma(self._ficha, datos["t"])
        if n is not None:
            partes.append(f"fotograma n.º {n}")
        partes.append(f"cuadro {datos.get('tipo', '?')}"
                      + (" (clave)" if datos.get("clave") else ""))
        hora = mvf.hora_real(self._ficha, datos["t"])
        if hora:
            partes.append(f"hora estimada {hora.strftime('%d/%m/%Y %H:%M:%S')}")
        self.lbl_momento.setText("   ·   ".join(partes))

        # El slider sigue al fotograma real sin volver a disparar la búsqueda.
        self.slider.blockSignals(True)
        self.slider.setValue(int(datos["t"] * 1000))
        self.slider.blockSignals(False)

        for btn in (self.btn_capturar, self.btn_rafaga, self.btn_segmento):
            btn.setEnabled(True)

    def _error_navegando(self, msg: str):
        self.lbl_estado.setText(f"⚠️  {msg}")

    # ── Acciones ─────────────────────────────────────────────────────────
    def _ocupado(self, si: bool):
        for btn in (self.btn_capturar, self.btn_rafaga, self.btn_segmento):
            btn.setEnabled(not si)

    def _lanzar(self, tarea: str, **kw):
        if self._tarea and self._tarea.isRunning():
            return
        self._ocupado(True)
        self.lista.setVisible(False)
        self._tarea = _TareaWorker(tarea, out_dir=self._out_dir,
                                   con_constancia=self.chk_constancia.isChecked(),
                                   herramienta=self._version(), **kw)
        self._tarea.aviso.connect(self.lbl_estado.setText)
        self._tarea.listo.connect(self._tarea_lista)
        self._tarea.error.connect(self._tarea_error)
        self._tarea.start()

    def _capturar(self):
        if not self._captura:
            return
        self._lanzar("capturar", ficha=self._ficha, captura=self._captura)

    def _rafaga(self):
        if not self._captura:
            return
        self._lanzar("rafaga", ficha=self._ficha, t=self._captura["t"],
                     margen=self.spin_rafaga.value(),
                     desentrelazar=self.chk_deint.isChecked())

    def _segmento(self):
        if not self._captura:
            return
        self._lanzar("segmento", ficha=self._ficha, t=self._captura["t"],
                     margen=self.spin_segmento.value())

    def _tarea_lista(self, mensaje: str, archivos: list):
        self._ocupado(False)
        self.lbl_estado.setText(mensaje)
        self.lista.clear()
        for a in archivos[:200]:
            self.lista.addItem(os.path.basename(a))
        self.lista.setVisible(bool(archivos))
        if archivos:
            self._ultima_carpeta = os.path.dirname(archivos[0])
            self.btn_abrir.setVisible(True)

    def _tarea_error(self, msg: str):
        self._ocupado(False)
        self.lbl_estado.setText(f"❌ {msg}")

    def _abrir_carpeta(self):
        carpeta = getattr(self, "_ultima_carpeta", "") or self._out_dir
        if not carpeta or not os.path.isdir(carpeta):
            return
        try:
            if platform.system() == "Windows":
                os.startfile(carpeta)
            elif platform.system() == "Darwin":
                subprocess.run(["open", carpeta])
            else:
                subprocess.run(["xdg-open", carpeta])
        except Exception:
            pass

    def _version(self) -> str:
        try:
            from core.paths import APP_NAME, APP_VERSION
            return f"{APP_NAME} {APP_VERSION}"
        except Exception:
            return "Navaja"

    # ── Ciclo de vida ────────────────────────────────────────────────────
    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Al agrandar la ventana, la imagen se vuelve a escalar desde el
        # archivo original: si se escalara el pixmap ya escalado se pierde
        # nitidez a cada cambio de tamaño.
        if self._captura:
            pix = QPixmap(self._captura["archivo"])
            if not pix.isNull():
                self.vista.setPixmap(pix.scaled(
                    self.vista.size(), Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation))

    def closeEvent(self, event):
        if self._nav:
            self._nav.detener()
        super().closeEvent(event)
