"""
ui/video_map_panel.py — Mapa del video: toda la grabación en una sola imagen.

Lo que en fotografía se llama "hoja de contactos": muchas miniaturas ordenadas
en una grilla, cada una con su minuto y segundo. En una grabación de tres horas
evita tener que arrastrar la barra a ciegas: se ve la película entera de un
vistazo, se ubica el tramo que interesa y se salta directo ahí.

El mapa no es la prueba: las miniaturas están reducidas. Sirve para encontrar
el momento; el fotograma en tamaño real se saca en la otra solapa, y por eso
un clic sobre cualquier miniatura lleva justo a ese punto.
"""
import os
import platform
import subprocess

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QDoubleSpinBox, QSpinBox, QCheckBox, QComboBox, QFileDialog, QMessageBox,
    QSizePolicy,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QPixmap

from core.salidas import carpeta_destino, etiqueta_destino, preparar_destino

VIDEO_FILTRO = ("Videos (*.mp4 *.mkv *.avi *.mov *.webm *.flv *.wmv *.m4v "
                "*.3gp *.ts *.mpg *.mpeg *.ogv *.vob *.f4v *.dav *.asf)")


class _MapaWorker(QThread):
    """Arma el mapa en segundo plano: son muchas miniaturas y tarda."""
    listo = pyqtSignal(dict, list)
    aviso = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, **kw):
        super().__init__()
        self.kw = kw

    def run(self):
        try:
            from motors import motor_video_frames as mvf

            src = self.kw["src"]
            destino = preparar_destino(src, self.kw["out_dir"])
            stem = os.path.splitext(os.path.basename(src))[0]
            final = os.path.join(destino, f"{stem}_mapa.png")

            datos = mvf.mapa_del_video(
                src, final,
                cada=self.kw["cada"],
                columnas=self.kw["columnas"],
                ancho_celda=self.kw["ancho_celda"],
                progress_cb=self.aviso.emit,
            )
            generados = [final]

            if self.kw.get("con_constancia", True):
                self.aviso.emit("🔢 Calculando hashes para la constancia…")
                texto = mvf.constancia_mapa(
                    datos["ficha"], final, datos["cada"], len(datos["celdas"]),
                    herramienta=self.kw.get("herramienta", ""))
                acta = os.path.splitext(final)[0] + "_constancia.txt"
                with open(acta, "w", encoding="utf-8") as f:
                    f.write(texto)
                generados.append(acta)

            self.listo.emit(datos, generados)
        except Exception as e:
            self.error.emit(str(e))


class _VistaMapa(QLabel):
    """La imagen del mapa, que además avisa dónde se hizo clic."""
    clic_en = pyqtSignal(int, int)     # coordenadas dentro de la imagen real

    def __init__(self, parent=None):
        super().__init__(parent)
        self._original = None
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumHeight(300)
        self.setStyleSheet(
            "background: #0f172a; color: #64748b; border-radius: 8px; "
            "font-size: 12px;")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def poner_mapa(self, ruta: str):
        self._original = QPixmap(ruta)
        self._reescalar()

    def vaciar(self, texto: str):
        self._original = None
        self.clear()
        self.setText(texto)

    def _reescalar(self):
        if self._original and not self._original.isNull():
            self.setPixmap(self._original.scaled(
                self.size(), Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reescalar()

    def mousePressEvent(self, event):
        """Traduce el clic sobre la imagen achicada a la imagen real."""
        if not self._original or self._original.isNull():
            return
        mostrado = self.pixmap()
        if mostrado is None or mostrado.isNull():
            return
        # La imagen está centrada dentro del recuadro: hay que descontar los
        # bordes vacíos antes de convertir la coordenada.
        borde_x = (self.width() - mostrado.width()) / 2
        borde_y = (self.height() - mostrado.height()) / 2
        x = event.position().x() - borde_x
        y = event.position().y() - borde_y
        if x < 0 or y < 0 or x > mostrado.width() or y > mostrado.height():
            return
        factor = self._original.width() / mostrado.width()
        self.clic_en.emit(int(x * factor), int(y * factor))


class VideoMapPanel(QWidget):
    """Panel del mapa del video."""

    # Avisa que el usuario eligió un momento: el módulo Video lo lleva a la
    # solapa de captura, ya parado en ese fotograma.
    momento_elegido = pyqtSignal(str, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(520)
        self._src_path = ""
        self._out_dir = ""
        self._ficha = None
        self._datos = None
        self._momento = None
        self._worker = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        hdr = QLabel("🗺️  Mapa del video")
        hdr.setStyleSheet("font-size: 16px; font-weight: 800;")
        layout.addWidget(hdr)

        sub = QLabel(
            "Toda la grabación en una sola imagen, con el minuto y segundo de "
            "cada miniatura. Sirve para ubicar el momento sin tener que mirar "
            "el video entero."
        )
        sub.setStyleSheet("font-size: 11px; color: #64748b;")
        sub.setWordWrap(True)
        layout.addWidget(sub)

        try:
            from motors.motor_video_frames import is_available
            if not is_available():
                warn = QLabel(
                    "⚠️  El mapa del video necesita FFmpeg.\n"
                    "Pedile al administrador que coloque ffmpeg.exe y "
                    "ffprobe.exe en la carpeta bin/ del programa.")
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
        layout.addWidget(card1)

        # ── Opciones ─────────────────────────────────────────────────────
        card2 = QFrame()
        card2.setObjectName("card")
        c2 = QVBoxLayout(card2)
        c2.setContentsMargins(12, 10, 12, 10)
        c2.setSpacing(8)

        f1 = QHBoxLayout()
        f1.addWidget(QLabel("Una miniatura cada"))
        self.spin_cada = QDoubleSpinBox()
        self.spin_cada.setRange(0.2, 3600.0)
        self.spin_cada.setValue(10.0)
        self.spin_cada.setDecimals(1)
        self.spin_cada.setSuffix(" segundos")
        self.spin_cada.setEnabled(False)
        f1.addWidget(self.spin_cada)
        self.chk_auto = QCheckBox("Automático")
        self.chk_auto.setChecked(True)
        self.chk_auto.setToolTip(
            "Reparte alrededor de 60 miniaturas a lo largo del video,\n"
            "en un intervalo redondo (30 s, 1 min, 5 min…).")
        self.chk_auto.stateChanged.connect(self._cambiar_auto)
        f1.addWidget(self.chk_auto)
        f1.addStretch()
        c2.addLayout(f1)

        f2 = QHBoxLayout()
        f2.addWidget(QLabel("Columnas:"))
        self.spin_col = QSpinBox()
        self.spin_col.setRange(1, 12)
        self.spin_col.setValue(5)
        f2.addWidget(self.spin_col)
        f2.addSpacing(16)
        f2.addWidget(QLabel("Tamaño de cada miniatura:"))
        self.combo_tam = QComboBox()
        self.combo_tam.addItem("Chica (240 px)", 240)
        self.combo_tam.addItem("Mediana (320 px)", 320)
        self.combo_tam.addItem("Grande (480 px)", 480)
        self.combo_tam.setCurrentIndex(1)
        f2.addWidget(self.combo_tam)
        f2.addStretch()
        c2.addLayout(f2)

        self.lbl_estimado = QLabel("")
        self.lbl_estimado.setStyleSheet(
            "font-size: 11px; color: #475569; font-style: italic;")
        c2.addWidget(self.lbl_estimado)
        layout.addWidget(card2)

        for control in (self.spin_cada, self.spin_col):
            control.valueChanged.connect(self._actualizar_estimado)

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
        c3.addWidget(self.chk_constancia)
        layout.addWidget(card3)

        self.btn_armar = QPushButton("🗺️  Armar el mapa")
        self.btn_armar.setObjectName("convertBtn")
        self.btn_armar.setEnabled(False)
        self.btn_armar.clicked.connect(self._armar)
        layout.addWidget(self.btn_armar)

        self.lbl_estado = QLabel("")
        self.lbl_estado.setStyleSheet("font-size: 11px; color: #475569;")
        self.lbl_estado.setWordWrap(True)
        layout.addWidget(self.lbl_estado)

        # ── El mapa ──────────────────────────────────────────────────────
        self.vista = _VistaMapa()
        self.vista.setText("Elegí un video y tocá «Armar el mapa»")
        self.vista.clic_en.connect(self._clic_en_mapa)
        layout.addWidget(self.vista, stretch=1)

        self.lbl_momento = QLabel(
            "Cuando el mapa esté armado, tocá cualquier miniatura para saber "
            "de qué momento es.")
        self.lbl_momento.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_momento.setStyleSheet(
            "font-size: 12px; color: #475569; background: #f1f5f9; "
            "border-radius: 6px; padding: 6px;")
        self.lbl_momento.setWordWrap(True)
        layout.addWidget(self.lbl_momento)

        acciones = QHBoxLayout()
        self.btn_ir = QPushButton("📸  Abrir este momento en «Capturar fotograma»")
        self.btn_ir.setObjectName("ghostBtn")
        self.btn_ir.setEnabled(False)
        self.btn_ir.clicked.connect(self._ir_a_captura)
        acciones.addWidget(self.btn_ir, stretch=1)

        self.btn_abrir = QPushButton("📂 Abrir carpeta")
        self.btn_abrir.setObjectName("ghostBtn")
        self.btn_abrir.setVisible(False)
        self.btn_abrir.clicked.connect(self._abrir_carpeta)
        acciones.addWidget(self.btn_abrir)
        layout.addLayout(acciones)

    # ── Archivo y opciones ───────────────────────────────────────────────
    def _elegir_video(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Elegir video", "", VIDEO_FILTRO)
        if path:
            self.cargar_video(path)

    def cargar_video(self, path: str):
        try:
            from motors import motor_video_frames as mvf
            ficha = mvf.info_video(path)
        except Exception as e:
            QMessageBox.warning(self, "No se pudo leer el video", str(e))
            return

        self._src_path = path
        self._ficha = ficha
        self._datos = None
        self._momento = None
        self.btn_ir.setEnabled(False)
        self.lbl_file.setText(os.path.basename(path))
        self.lbl_out.setText(carpeta_destino(path, self._out_dir))
        self.lbl_ficha.setText(
            f"{ficha['duracion_hms']}  ·  {ficha['ancho']}x{ficha['alto']} px  "
            f"·  {ficha['codec']}")
        self.btn_armar.setEnabled(True)

        if self.chk_auto.isChecked():
            from motors.motor_video_frames import _intervalo_redondo
            self.spin_cada.setValue(_intervalo_redondo(ficha["duracion"], 60))
        self._actualizar_estimado()

    def _limpiar(self):
        if self._worker and self._worker.isRunning():
            return
        self._src_path = ""
        self._out_dir = ""
        self._ultima_carpeta = ""
        self._ficha = None
        self._datos = None
        self._momento = None
        self.lbl_file.setText("No se eligió ningún video")
        self.lbl_ficha.setText("")
        self.lbl_out.setText(etiqueta_destino(""))
        self.lbl_estado.setText("")
        self.btn_armar.setEnabled(False)
        self.btn_ir.setEnabled(False)
        self.btn_abrir.setVisible(False)
        self.vista.vaciar("Elegí un video y tocá «Armar el mapa»")
        self.lbl_momento.setText(
            "Cuando el mapa esté armado, tocá cualquier miniatura para saber "
            "de qué momento es.")
        self._actualizar_estimado()

    def _cambiar_auto(self):
        automatico = self.chk_auto.isChecked()
        self.spin_cada.setEnabled(not automatico)
        if automatico and self._ficha:
            from motors.motor_video_frames import _intervalo_redondo
            self.spin_cada.setValue(_intervalo_redondo(self._ficha["duracion"], 60))
        self._actualizar_estimado()

    def _actualizar_estimado(self):
        if not self._ficha:
            self.lbl_estimado.setText("")
            return
        cada = self.spin_cada.value()
        cuantas = max(1, int(self._ficha["duracion"] / cada))
        filas = (cuantas + self.spin_col.value() - 1) // self.spin_col.value()
        aviso = ""
        if cuantas > 200:
            aviso = ("   ⚠️ son muchas: el mapa va a tardar y va a quedar una "
                     "imagen enorme. Probá con un intervalo más grande.")
        self.lbl_estimado.setText(
            f"Van a salir unas {cuantas} miniaturas en {filas} filas.{aviso}")

    def _elegir_carpeta(self):
        d = QFileDialog.getExistingDirectory(self, "Carpeta de salida")
        if d:
            self._out_dir = d
            self.lbl_out.setText(d)

    # ── Armar ────────────────────────────────────────────────────────────
    def _armar(self):
        if not self._src_path or (self._worker and self._worker.isRunning()):
            return
        self.btn_armar.setEnabled(False)
        self.btn_ir.setEnabled(False)
        self.lbl_estado.setText("🗺️  Armando el mapa…")
        self._worker = _MapaWorker(
            src=self._src_path,
            out_dir=self._out_dir,
            cada=self.spin_cada.value(),
            columnas=self.spin_col.value(),
            ancho_celda=self.combo_tam.currentData(),
            con_constancia=self.chk_constancia.isChecked(),
            herramienta=self._version(),
        )
        self._worker.aviso.connect(self.lbl_estado.setText)
        self._worker.listo.connect(self._mapa_listo)
        self._worker.error.connect(self._mapa_error)
        self._worker.start()

    def _mapa_listo(self, datos: dict, generados: list):
        self._datos = datos
        self.btn_armar.setEnabled(True)
        self.vista.poner_mapa(datos["archivo"])
        self.lbl_estado.setText(
            f"✅ Mapa guardado: {os.path.basename(datos['archivo'])}  "
            f"({len(datos['celdas'])} miniaturas)")
        self.lbl_momento.setText(
            "Tocá cualquier miniatura para saber de qué momento es.")
        self._ultima_carpeta = os.path.dirname(datos["archivo"])
        self.btn_abrir.setVisible(True)

    def _mapa_error(self, msg: str):
        self.btn_armar.setEnabled(True)
        self.lbl_estado.setText(f"❌ {msg}")

    # ── Clic sobre una miniatura ─────────────────────────────────────────
    def _clic_en_mapa(self, x: int, y: int):
        if not self._datos:
            return
        for celda in self._datos["celdas"]:
            if (celda["x"] <= x <= celda["x"] + celda["w"]
                    and celda["y"] <= y <= celda["y"] + celda["h"]):
                self._momento = celda["t"]
                self.lbl_momento.setText(
                    f"⏱️  Esa miniatura es del momento {celda['t_hms']}")
                self.btn_ir.setEnabled(True)
                # El mapa es alto y la respuesta al clic queda abajo, fuera de
                # la pantalla: si no se la trae a la vista, el usuario toca
                # una miniatura y parece que no pasó nada.
                self._mostrar(self.btn_ir)
                return
        self.lbl_momento.setText(
            "Ahí no hay ninguna miniatura: tocá sobre una imagen.")

    def _ir_a_captura(self):
        if self._src_path and self._momento is not None:
            self.momento_elegido.emit(self._src_path, self._momento)

    # ── Varios ───────────────────────────────────────────────────────────
    def _mostrar(self, widget):
        """Trae un widget a la vista dentro de la pantalla que lo contiene."""
        from PyQt6.QtWidgets import QScrollArea

        padre = self.parentWidget()
        while padre is not None:
            if isinstance(padre, QScrollArea):
                padre.ensureWidgetVisible(widget, 0, 60)
                return
            padre = padre.parentWidget()

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
