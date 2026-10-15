"""
ui/audio_enhance_panel.py — Panel «Mejorar audio»: perillas tipo ecualizador
y prueba de unos segundos sobre el archivo real.

Sirve para audios y para el audio de un video (está en los dos módulos). Los
ajustes se eligen a oído: se mueve una perilla, se escuchan cinco segundos del
propio archivo y se compara con el original, antes de procesarlo entero.
"""
import os
import platform
import subprocess

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSlider,
    QSpinBox, QProgressBar, QFileDialog, QFrame, QMessageBox,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

from ui.informe_widget import InformeSection
from core.salidas import carpeta_destino, etiqueta_destino
from core.paths import TEMP_DIR
from motors.motor_audio_enhance import (
    PERILLAS, PREAJUSTES, AJUSTES_EN_CERO, EXT_AUDIO, EXT_VIDEO,
)

try:
    import winsound
except ImportError:          # fuera de Windows no hay con qué reproducir
    winsound = None


def _filtro_archivos() -> str:
    audio = " ".join(f"*{e}" for e in sorted(EXT_AUDIO))
    video = " ".join(f"*{e}" for e in sorted(EXT_VIDEO))
    return (f"Audio y video ({audio} {video});;Audio ({audio});;"
            f"Video ({video});;Todos los archivos (*.*)")


def _mmss(segundos: float) -> str:
    s = int(max(0, segundos))
    if s >= 3600:
        return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}"
    return f"{s // 60:02d}:{s % 60:02d}"


# ── Workers ───────────────────────────────────────────────────────────────

class _MuestraWorker(QThread):
    lista = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, src, dst, desde, segundos, ajustes):
        super().__init__()
        self.args = (src, dst, desde, segundos, ajustes)

    def run(self):
        try:
            from motors.motor_audio_enhance import muestra
            self.lista.emit(muestra(*self.args))
        except Exception as e:
            self.error.emit(str(e))


class _MejorarWorker(QThread):
    progress      = pyqtSignal(str)
    pct           = pyqtSignal(int)
    finished      = pyqtSignal(str)
    informe_ready = pyqtSignal(str)
    error         = pyqtSignal(str)

    def __init__(self, src, dst, ajustes, es_video):
        super().__init__()
        self.src, self.dst = src, dst
        self.ajustes, self.es_video = ajustes, es_video

    def run(self):
        try:
            from motors.motor_audio_enhance import mejorar, descripcion
            mejorar(self.src, self.dst, self.ajustes,
                    progress_cb=self.progress.emit, pct_cb=self.pct.emit)
            try:
                from core.informe import build_informe, file_info
                self.progress.emit("🔐  Calculando los hashes…")
                original = file_info(self.src, self.pct.emit)
                resultado = file_info(self.dst, self.pct.emit)
                nota = ("El archivo original no fue modificado. El resultado "
                        "es una copia procesada para facilitar la escucha"
                        + (": la imagen es la misma del original, sin "
                           "recodificar, y sólo cambia el audio."
                           if self.es_video else "."))
                self.informe_ready.emit(build_informe(
                    accion="procesar con filtros de mejora de audio",
                    originals=[original], results=[resultado],
                    objeto="archivo de video" if self.es_video
                           else "archivo de audio",
                    parametros=descripcion(self.ajustes),
                    extra_lines=nota,
                ))
            except Exception:
                pass
            self.finished.emit(self.dst)
        except Exception as e:
            self.error.emit(str(e))


# ── Panel ─────────────────────────────────────────────────────────────────

class AudioEnhancePanel(QWidget):
    """Mejorar el audio de una grabación, probando antes unos segundos."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(520)
        self._src_path = ""
        self._out_dir = ""
        self._last_out = ""
        self._ficha = None
        self._worker = None
        self._muestra = None
        self._n_muestra = 0
        self._sliders = {}
        self._valores = {}
        self._setup_ui()

    # ── Construcción ─────────────────────────────────────────────────────
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        hdr = QLabel("🎚  Mejorar audio")
        hdr.setStyleSheet("font-size: 16px; font-weight: 800;")
        layout.addWidget(hdr)

        sub = QLabel(
            "Para grabaciones donde la voz se escucha mal: ruido de fondo, "
            "micrófono de ambiente, alguien que habla bajito. Mové las "
            "perillas, escuchá unos segundos del propio archivo y, cuando "
            "suene mejor, guardá una copia. El original no se toca.")
        sub.setStyleSheet("font-size: 11px; color: #64748b;")
        sub.setWordWrap(True)
        layout.addWidget(sub)

        try:
            from motors.motor_audio_enhance import is_available
            if not is_available():
                warn = QLabel(
                    "⚠️  Esta herramienta necesita FFmpeg.\n"
                    "Colocá ffmpeg.exe y ffprobe.exe en la carpeta bin/ del "
                    "programa.")
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
        self.lbl_file = QLabel("No se eligió ningún archivo")
        self.lbl_file.setStyleSheet("font-size: 11px; color: #64748b;")
        self.lbl_file.setWordWrap(True)
        fila.addWidget(self.lbl_file, stretch=1)
        btn_pick = QPushButton("📁 Elegir audio o video")
        btn_pick.setObjectName("ghostBtn")
        btn_pick.clicked.connect(self._elegir)
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

        # ── Perillas ─────────────────────────────────────────────────────
        card2 = QFrame()
        card2.setObjectName("card")
        c2 = QVBoxLayout(card2)
        c2.setContentsMargins(12, 10, 12, 10)
        c2.setSpacing(8)

        pre = QHBoxLayout()
        pre.addWidget(QLabel("Puntos de partida:"))
        for nombre, valores in PREAJUSTES:
            btn = QPushButton(nombre)
            btn.setObjectName("presetBtn")
            btn.setToolTip("Acomoda las perillas para empezar; después "
                           "corregí a oído con la prueba.")
            btn.clicked.connect(lambda _=False, v=valores: self._poner(v))
            pre.addWidget(btn)
        btn_cero = QPushButton("Todo en cero")
        btn_cero.setObjectName("presetBtn")
        btn_cero.setToolTip("Vuelve todas las perillas a cero (sonido original).")
        btn_cero.clicked.connect(lambda: self._poner(AJUSTES_EN_CERO))
        pre.addWidget(btn_cero)
        pre.addStretch()
        c2.addLayout(pre)

        mesa = QHBoxLayout()
        mesa.setSpacing(6)
        for clave, nombre, minimo, maximo, ayuda in PERILLAS:
            col = QVBoxLayout()
            col.setSpacing(4)
            valor = QLabel("0")
            valor.setAlignment(Qt.AlignmentFlag.AlignCenter)
            valor.setStyleSheet("font-size: 12px; font-weight: 700;")
            col.addWidget(valor)

            slider = QSlider(Qt.Orientation.Vertical)
            slider.setRange(minimo, maximo)
            slider.setValue(0)
            slider.setPageStep(1)
            slider.setTickPosition(QSlider.TickPosition.TicksBothSides)
            slider.setTickInterval(1 if maximo <= 10 else 5)
            slider.setMinimumHeight(150)
            slider.setToolTip(ayuda)
            slider.valueChanged.connect(
                lambda v, c=clave: self._perilla_movida(c, v))
            col.addWidget(slider, alignment=Qt.AlignmentFlag.AlignHCenter)

            rotulo = QLabel(nombre)
            rotulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
            rotulo.setWordWrap(True)
            rotulo.setStyleSheet("font-size: 11px;")
            rotulo.setToolTip(ayuda)
            rotulo.setMinimumWidth(78)
            col.addWidget(rotulo)

            self._sliders[clave] = slider
            self._valores[clave] = valor
            mesa.addLayout(col, stretch=1)
        c2.addLayout(mesa)

        ayuda_gral = QLabel(
            "Dejá el mouse sobre una perilla para ver qué hace. Subí de a "
            "poco: de más, la voz suena artificial.")
        ayuda_gral.setStyleSheet("font-size: 11px; color: #64748b;")
        ayuda_gral.setWordWrap(True)
        c2.addWidget(ayuda_gral)
        layout.addWidget(card2)

        # ── Probar ───────────────────────────────────────────────────────
        card3 = QFrame()
        card3.setObjectName("card")
        c3 = QVBoxLayout(card3)
        c3.setContentsMargins(12, 10, 12, 10)
        c3.setSpacing(8)
        c3.addWidget(QLabel("Probar con una parte del archivo:"))

        donde = QHBoxLayout()
        donde.addWidget(QLabel("Desde"))
        self.slider_pos = QSlider(Qt.Orientation.Horizontal)
        self.slider_pos.setRange(0, 0)
        self.slider_pos.setEnabled(False)
        self.slider_pos.valueChanged.connect(self._posicion_movida)
        donde.addWidget(self.slider_pos, stretch=1)
        self.lbl_pos = QLabel("00:00")
        self.lbl_pos.setMinimumWidth(110)
        donde.addWidget(self.lbl_pos)
        donde.addWidget(QLabel("durante"))
        self.spin_seg = QSpinBox()
        self.spin_seg.setRange(2, 30)
        self.spin_seg.setValue(5)
        self.spin_seg.setSuffix(" s")
        donde.addWidget(self.spin_seg)
        c3.addLayout(donde)

        botones = QHBoxLayout()
        self.btn_orig = QPushButton("▶  Escuchar el original")
        self.btn_orig.setObjectName("ghostBtn")
        self.btn_orig.clicked.connect(lambda: self._probar(False))
        botones.addWidget(self.btn_orig)
        self.btn_mejor = QPushButton("▶  Escuchar con los ajustes")
        self.btn_mejor.setObjectName("ghostBtn")
        self.btn_mejor.clicked.connect(lambda: self._probar(True))
        botones.addWidget(self.btn_mejor)
        self.btn_parar = QPushButton("⏹  Detener")
        self.btn_parar.setObjectName("ghostBtn")
        self.btn_parar.clicked.connect(self._parar)
        botones.addWidget(self.btn_parar)
        botones.addStretch()
        c3.addLayout(botones)

        self.lbl_prueba = QLabel("")
        self.lbl_prueba.setStyleSheet("font-size: 11px; color: #475569;")
        self.lbl_prueba.setWordWrap(True)
        c3.addWidget(self.lbl_prueba)
        layout.addWidget(card3)

        # ── Salida ───────────────────────────────────────────────────────
        card4 = QFrame()
        card4.setObjectName("card")
        c4 = QHBoxLayout(card4)
        c4.setContentsMargins(12, 10, 12, 10)
        c4.addWidget(QLabel("Carpeta de salida:"))
        self.lbl_out = QLabel(etiqueta_destino(""))
        self.lbl_out.setStyleSheet("font-size: 11px; color: #64748b;")
        self.lbl_out.setWordWrap(True)
        c4.addWidget(self.lbl_out, stretch=1)
        btn_out = QPushButton("Cambiar")
        btn_out.setObjectName("ghostBtn")
        btn_out.clicked.connect(self._elegir_carpeta)
        c4.addWidget(btn_out)
        layout.addWidget(card4)

        self.pbar = QProgressBar()
        self.pbar.setRange(0, 0)
        self.pbar.setVisible(False)
        layout.addWidget(self.pbar)

        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("font-size: 11px; color: #475569;")
        self.lbl_status.setWordWrap(True)
        layout.addWidget(self.lbl_status)

        self.btn_run = QPushButton("🎚  Guardar una copia con el audio mejorado")
        self.btn_run.setObjectName("convertBtn")
        self.btn_run.clicked.connect(self._procesar)
        layout.addWidget(self.btn_run)

        self.btn_open = QPushButton("📂 Abrir carpeta de resultados")
        self.btn_open.setObjectName("ghostBtn")
        self.btn_open.setVisible(False)
        self.btn_open.clicked.connect(self._abrir_carpeta)
        layout.addWidget(self.btn_open)

        self.informe_section = InformeSection()
        layout.addWidget(self.informe_section)

        layout.addStretch()
        self._habilitar()

    # ── Archivo ──────────────────────────────────────────────────────────
    def _elegir(self):
        ruta, _ = QFileDialog.getOpenFileName(
            self, "Elegir audio o video", "", _filtro_archivos())
        if ruta:
            self.cargar(ruta)

    def cargar(self, ruta: str):
        try:
            from motors.motor_audio_enhance import info
            ficha = info(ruta)
        except Exception as e:
            QMessageBox.warning(self, "Mejorar audio",
                                f"No pude leer ese archivo:\n{e}")
            return
        if not ficha["tiene_audio"]:
            QMessageBox.warning(self, "Mejorar audio",
                                "Ese archivo no tiene audio.")
            return

        self._parar()
        self._src_path = ruta
        self._ficha = ficha
        self.lbl_file.setText(os.path.basename(ruta))
        self.lbl_out.setText(carpeta_destino(ruta, self._out_dir))
        tipo = "Video" if ficha["tiene_video"] else "Audio"
        canales = {1: "mono", 2: "estéreo"}.get(ficha["canales"],
                                                f"{ficha['canales']} canales")
        self.lbl_ficha.setText(
            f"{tipo}  ·  {_mmss(ficha['duracion'])}  ·  audio "
            f"{ficha['codec']} {canales}"
            + (f" {ficha['muestreo']} Hz" if ficha["muestreo"] else ""))

        # La prueba arranca a un tercio del archivo: al principio suele
        # haber silencio o todavía no habla nadie.
        tope = max(0, int(ficha["duracion"]) - self.spin_seg.value())
        self.slider_pos.setRange(0, tope)
        self.slider_pos.setValue(tope // 3)
        self._posicion_movida(self.slider_pos.value())
        self.lbl_prueba.setText("")
        self.lbl_status.setText("")
        self.btn_open.setVisible(False)
        self.informe_section.setVisible(False)
        self._habilitar()

    def _limpiar(self):
        if self._worker and self._worker.isRunning():
            return
        self._parar()
        self._src_path = ""
        self._out_dir = ""
        self._last_out = ""
        self._ficha = None
        self.lbl_file.setText("No se eligió ningún archivo")
        self.lbl_ficha.setText("")
        self.lbl_out.setText(etiqueta_destino(""))
        self._poner(AJUSTES_EN_CERO)
        self.slider_pos.setRange(0, 0)
        self.lbl_pos.setText("00:00")
        self.spin_seg.setValue(5)
        self.lbl_prueba.setText("")
        self.lbl_status.setText("")
        self.pbar.setVisible(False)
        self.btn_open.setVisible(False)
        self.informe_section.setVisible(False)
        self._habilitar()

    def _elegir_carpeta(self):
        d = QFileDialog.getExistingDirectory(self, "Carpeta de salida")
        if d:
            self._out_dir = d
            self.lbl_out.setText(d)

    # ── Perillas ─────────────────────────────────────────────────────────
    def ajustes(self) -> dict:
        return {clave: s.value() for clave, s in self._sliders.items()}

    def _poner(self, valores: dict):
        for clave, slider in self._sliders.items():
            slider.setValue(int(valores.get(clave, 0)))

    def _perilla_movida(self, clave: str, valor: int):
        texto = f"{valor:+d} dB" if clave == "volumen" and valor else str(valor)
        self._valores[clave].setText(texto)
        self._valores[clave].setStyleSheet(
            "font-size: 12px; font-weight: 700;"
            + (" color: #2563eb;" if valor else ""))

    def _posicion_movida(self, valor: int):
        total = self._ficha["duracion"] if self._ficha else 0
        self.lbl_pos.setText(f"{_mmss(valor)} de {_mmss(total)}")

    def _habilitar(self):
        hay = bool(self._src_path)
        ocupado = bool(self._worker and self._worker.isRunning())
        self.slider_pos.setEnabled(hay)
        for b in (self.btn_orig, self.btn_mejor, self.btn_parar):
            b.setEnabled(hay and winsound is not None)
        self.btn_run.setEnabled(hay and not ocupado)

    # ── Probar ───────────────────────────────────────────────────────────
    def _probar(self, con_ajustes: bool):
        if not self._src_path:
            return
        if self._muestra and self._muestra.isRunning():
            return
        if con_ajustes and not any(self.ajustes().values()):
            self.lbl_prueba.setText(
                "Todas las perillas están en cero: va a sonar igual que el "
                "original. Mové alguna o elegí un punto de partida.")
        else:
            self.lbl_prueba.setText("Preparando la prueba…")
        self._parar(borrar=False)

        # Un archivo nuevo cada vez: el anterior puede estar todavía en uso.
        self._n_muestra += 1
        destino = os.path.join(
            str(TEMP_DIR),
            f"prueba_audio_{os.getpid()}_{id(self)}_{self._n_muestra}.wav")
        os.makedirs(str(TEMP_DIR), exist_ok=True)
        self._que_suena = ("con los ajustes" if con_ajustes
                           else "el original")
        self._muestra = _MuestraWorker(
            self._src_path, destino, float(self.slider_pos.value()),
            float(self.spin_seg.value()),
            self.ajustes() if con_ajustes else None)
        self._muestra.lista.connect(self._muestra_lista)
        self._muestra.error.connect(
            lambda m: self.lbl_prueba.setText(f"❌  {m}"))
        self._muestra.start()

    def _muestra_lista(self, ruta: str):
        self._borrar_muestras(menos=ruta)
        if winsound is None:
            return
        try:
            winsound.PlaySound(
                ruta, winsound.SND_FILENAME | winsound.SND_ASYNC
                | winsound.SND_NODEFAULT)
            self.lbl_prueba.setText(
                f"🔊  Sonando {self._que_suena}: {self.spin_seg.value()} s "
                f"desde {_mmss(self.slider_pos.value())}.")
        except Exception as e:
            self.lbl_prueba.setText(f"❌  No pude reproducir la prueba: {e}")

    def _parar(self, borrar: bool = True):
        if winsound is not None:
            try:
                winsound.PlaySound(None, winsound.SND_PURGE)
            except Exception:
                pass
        if borrar:
            self._borrar_muestras()
            if hasattr(self, "lbl_prueba"):
                self.lbl_prueba.setText("")

    def _borrar_muestras(self, menos: str = ""):
        prefijo = f"prueba_audio_{os.getpid()}_{id(self)}_"
        try:
            for nombre in os.listdir(str(TEMP_DIR)):
                ruta = os.path.join(str(TEMP_DIR), nombre)
                if nombre.startswith(prefijo) and ruta != menos:
                    try:
                        os.remove(ruta)
                    except OSError:
                        pass
        except OSError:
            pass

    # ── Procesar ─────────────────────────────────────────────────────────
    def _procesar(self):
        if not self._src_path or (self._worker and self._worker.isRunning()):
            return
        if not any(self.ajustes().values()):
            QMessageBox.information(
                self, "Mejorar audio",
                "Todas las perillas están en cero: no hay nada para mejorar.\n"
                "Mové alguna o elegí un punto de partida.")
            return
        if not os.path.isfile(self._src_path):
            QMessageBox.warning(
                self, "Mejorar audio",
                "El archivo que habías elegido ya no está en esa carpeta. "
                "Volvé a elegirlo.")
            return
        self._parar()

        from motors.motor_audio_enhance import nombre_salida
        carpeta = carpeta_destino(self._src_path, self._out_dir)
        os.makedirs(carpeta, exist_ok=True)
        destino = nombre_salida(self._src_path, carpeta, self._ficha)
        self._last_out = carpeta

        self.btn_open.setVisible(False)
        self.informe_section.setVisible(False)
        self.pbar.setRange(0, 0)
        self.pbar.setVisible(True)
        self.lbl_status.setText("Procesando…")

        self._worker = _MejorarWorker(self._src_path, destino, self.ajustes(),
                                      self._ficha["tiene_video"])
        self._worker.progress.connect(self.lbl_status.setText)
        self._worker.pct.connect(self._on_pct)
        self._worker.finished.connect(self._listo)
        self._worker.informe_ready.connect(
            lambda txt: self.informe_section.set_informe(txt, carpeta))
        self._worker.error.connect(self._error)
        self._worker.start()
        self._habilitar()

    def _on_pct(self, valor: int):
        if self.pbar.maximum() == 0:
            self.pbar.setRange(0, 100)
            self.pbar.setFormat("%p%")
            self.pbar.setTextVisible(True)
        self.pbar.setValue(valor)

    def _listo(self, destino: str):
        self.pbar.setVisible(False)
        mb = os.path.getsize(destino) / 1048576 if os.path.isfile(destino) else 0
        self.lbl_status.setText(
            f"✅  Guardado: {os.path.basename(destino)}  ({mb:.1f} MB)")
        self.btn_open.setVisible(True)
        self._habilitar()

    def _error(self, msg: str):
        self.pbar.setVisible(False)
        self.lbl_status.setText(f"❌  {msg}")
        self._habilitar()

    def _abrir_carpeta(self):
        carpeta = self._last_out or self._out_dir
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

    # ── Ciclo de vida ────────────────────────────────────────────────────
    def hideEvent(self, event):
        # Al cambiar de solapa o de módulo, la prueba deja de sonar.
        self._parar(borrar=False)
        super().hideEvent(event)

    def closeEvent(self, event):
        self._parar()
        super().closeEvent(event)
