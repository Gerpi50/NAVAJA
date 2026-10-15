"""
ui/video_splitter_panel.py — Panel para partir videos en partes.
"""
import os
import platform
import subprocess

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSpinBox, QProgressBar, QListWidget, QListWidgetItem,
    QFileDialog, QFrame, QSizePolicy,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

from ui.informe_widget import InformeSection
from core.salidas import carpeta_destino, etiqueta_destino


class _SplitWorker(QThread):
    progress      = pyqtSignal(str)
    pct           = pyqtSignal(int)      # avance del paso en curso (0–100)
    finished      = pyqtSignal(list)
    informe_ready = pyqtSignal(str)
    error         = pyqtSignal(str)

    def __init__(self, src: str, out_dir: str, max_mb: float):
        super().__init__()
        self.src    = src
        self.out_dir = out_dir
        self.max_mb = max_mb

    def run(self):
        try:
            from motors.motor_video_splitter import split_video
            parts = split_video(
                self.src, self.out_dir, self.max_mb,
                progress_cb=self.progress.emit,
                pct_cb=self.pct.emit,
            )

            # Build informe
            try:
                from core.informe import build_informe, file_info
                self.progress.emit(
                    "🔐  Calculando el hash del video original…")
                orig    = file_info(self.src, self.pct.emit)
                self.progress.emit("🔐  Calculando el hash de las partes…")
                results = []
                for n, p in enumerate(parts, start=1):
                    if os.path.exists(p):
                        results.append(file_info(p))
                    self.pct.emit(int(n * 100 / len(parts)))
                texto   = build_informe(
                    accion="dividir en partes",
                    originals=[orig],
                    results=results,
                    objeto="archivo de video",
                    parametros=f"máximo {self.max_mb} MB por parte",
                )
                self.informe_ready.emit(texto)
            except Exception:
                pass

            self.finished.emit(parts)
        except Exception as e:
            self.error.emit(str(e))


class VideoSplitterPanel(QWidget):
    """Panel lateral para partir videos grandes en partes más pequeñas."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(380)
        self._src_path = ""
        self._out_dir  = ""
        self._info     = None       # ficha del video (se lee una sola vez)
        self._worker   = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Encabezado
        hdr = QLabel("✂️  Partir video")
        hdr.setStyleSheet("font-size: 16px; font-weight: 800;")
        layout.addWidget(hdr)

        sub = QLabel("Dividí un video grande en partes más pequeñas\nsin perder calidad de imagen ni sonido.")
        sub.setStyleSheet("font-size: 11px; color: #64748b;")
        sub.setWordWrap(True)
        layout.addWidget(sub)

        # Verificar FFmpeg
        try:
            from motors.motor_video_splitter import is_available
            if not is_available():
                warn = QLabel(
                    "⚠️  El partidor de video necesita FFmpeg.\n"
                    "Pedile al administrador que coloque ffmpeg.exe\n"
                    "en la carpeta bin/ del programa."
                )
                warn.setStyleSheet(
                    "background: #fffbeb; border: 1px solid #f59e0b; "
                    "border-radius: 6px; padding: 10px; color: #92400e;"
                )
                warn.setWordWrap(True)
                layout.addWidget(warn)
                layout.addStretch()
                return
        except Exception:
            pass

        # Selección de archivo
        card1 = QFrame()
        card1.setObjectName("card")
        c1 = QVBoxLayout(card1)
        c1.setContentsMargins(12, 10, 12, 10)
        c1.setSpacing(8)

        c1.addWidget(QLabel("Video a partir:"))
        file_row = QHBoxLayout()
        self.lbl_file = QLabel("No se eligió ningún video")
        self.lbl_file.setStyleSheet("font-size: 11px; color: #64748b;")
        self.lbl_file.setWordWrap(True)
        file_row.addWidget(self.lbl_file, stretch=1)
        btn_pick = QPushButton("📁 Elegir video")
        btn_pick.setObjectName("ghostBtn")
        btn_pick.clicked.connect(self._pick_video)
        file_row.addWidget(btn_pick)
        btn_limpiar = QPushButton("🗑 Limpiar")
        btn_limpiar.setObjectName("ghostBtn")
        btn_limpiar.setToolTip(
            "Deja la solapa como recién abierta, para empezar con otro "
            "archivo.\nNo borra nada del disco.")
        btn_limpiar.clicked.connect(self._limpiar)
        file_row.addWidget(btn_limpiar)
        c1.addLayout(file_row)

        self.lbl_info = QLabel("")
        self.lbl_info.setStyleSheet("font-size: 11px; color: #475569;")
        self.lbl_info.setWordWrap(True)
        c1.addWidget(self.lbl_info)
        layout.addWidget(card1)

        # Tamaño de partes
        card2 = QFrame()
        card2.setObjectName("card")
        c2 = QVBoxLayout(card2)
        c2.setContentsMargins(12, 10, 12, 10)
        c2.setSpacing(8)

        c2.addWidget(QLabel("Tamaño máximo de cada parte:"))

        size_row = QHBoxLayout()
        self.spin_size = QSpinBox()
        self.spin_size.setRange(1, 2048)
        self.spin_size.setValue(25)
        self.spin_size.setSuffix(" MB")
        self.spin_size.valueChanged.connect(self._update_estimate)
        size_row.addWidget(self.spin_size)
        size_row.addStretch()
        c2.addLayout(size_row)

        # Presets
        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel("Presets:"))
        for mb in [5, 16, 25, 50, 100]:
            btn = QPushButton(f"{mb} MB")
            btn.setObjectName("presetBtn")
            btn.setMinimumWidth(58)
            btn.setToolTip(
                "Elegí el tamaño según dónde compartirás el video:\n"
                "WhatsApp acepta hasta 16 MB,\n"
                "correo electrónico hasta 25 MB."
            )
            btn.clicked.connect(lambda checked, v=mb: self.spin_size.setValue(v))
            preset_row.addWidget(btn)
        c2.addLayout(preset_row)

        self.lbl_estimate = QLabel("")
        self.lbl_estimate.setStyleSheet("font-size: 11px; color: #475569; font-style: italic;")
        c2.addWidget(self.lbl_estimate)

        # Aviso partes pequeñas
        self.warn_small = QLabel(
            "⚠️  Con partes tan pequeñas se generarán muchos archivos.\n"
            "El mínimo recomendado es 5 MB."
        )
        self.warn_small.setStyleSheet(
            "background: #fffbeb; border: 1px solid #f59e0b; "
            "border-radius: 6px; padding: 8px; color: #92400e; font-size: 11px;"
        )
        self.warn_small.setWordWrap(True)
        self.warn_small.setVisible(False)
        c2.addWidget(self.warn_small)

        layout.addWidget(card2)

        # Carpeta de salida
        card3 = QFrame()
        card3.setObjectName("card")
        c3 = QVBoxLayout(card3)
        c3.setContentsMargins(12, 10, 12, 10)
        c3.setSpacing(8)

        c3.addWidget(QLabel("Carpeta de salida:"))
        out_row = QHBoxLayout()
        self.lbl_out = QLabel(etiqueta_destino(""))
        self.lbl_out.setStyleSheet("font-size: 11px; color: #64748b;")
        out_row.addWidget(self.lbl_out, stretch=1)
        btn_out = QPushButton("Cambiar")
        btn_out.setObjectName("ghostBtn")
        btn_out.clicked.connect(self._pick_out_dir)
        out_row.addWidget(btn_out)
        c3.addLayout(out_row)
        layout.addWidget(card3)

        # Progreso
        self.pbar = QProgressBar()
        self.pbar.setRange(0, 0)  # indeterminate
        self.pbar.setVisible(False)
        layout.addWidget(self.pbar)

        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("font-size: 11px; color: #475569;")
        self.lbl_status.setWordWrap(True)
        layout.addWidget(self.lbl_status)

        # Botón principal
        self.btn_split = QPushButton("✂️  Partir video")
        self.btn_split.setObjectName("convertBtn")
        self.btn_split.setEnabled(False)
        self.btn_split.clicked.connect(self._start_split)
        layout.addWidget(self.btn_split)

        # Lista de resultados
        self.result_list = QListWidget()
        self.result_list.setMaximumHeight(150)
        self.result_list.setVisible(False)
        layout.addWidget(self.result_list)

        self.btn_open_folder = QPushButton("📂 Abrir carpeta de resultados")
        self.btn_open_folder.setObjectName("ghostBtn")
        self.btn_open_folder.setVisible(False)
        self.btn_open_folder.clicked.connect(self._open_output_folder)
        layout.addWidget(self.btn_open_folder)

        # ── Informe técnico ───────────────────────────────────────────
        self.informe_section = InformeSection()
        layout.addWidget(self.informe_section)

        layout.addStretch()

    # ── Handlers ─────────────────────────────────────────────────────

    def _pick_video(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Elegir video",
            "",
            "Videos (*.mp4 *.mkv *.avi *.mov *.webm *.flv *.wmv *.m4v *.3gp *.ts *.mpg *.mpeg *.ogv)"
        )
        if path:
            self._src_path = path
            self.lbl_file.setText(os.path.basename(path))
            self.lbl_out.setText(carpeta_destino(path, self._out_dir))
            self.btn_split.setEnabled(True)
            self._load_video_info(path)
            self._update_estimate()

    def _load_video_info(self, path: str):
        self._info = None
        size_mb = os.path.getsize(path) / (1024*1024)
        info_txt = f"Tamaño: {size_mb:.1f} MB"

        try:
            from motors.motor_video_splitter import get_video_info
            info = get_video_info(path)
            self._info = info
            dur = info.get("duration", 0)
            mins = int(dur) // 60
            secs = int(dur) % 60
            info_txt += f"  |  Duración: {mins}m {secs}s"
        except Exception:
            pass

        if size_mb > 2048:
            info_txt += f"\n⚠️  Este video es muy grande ({size_mb/1024:.1f} GB).\n" \
                        f"El proceso puede tardar varios minutos.\n" \
                        f"No cerrés el programa mientras trabaja."
        self.lbl_info.setText(info_txt)

    def _update_estimate(self):
        mb = self.spin_size.value()
        self.warn_small.setVisible(mb < 5)
        if self._src_path:
            try:
                from motors.motor_video_splitter import estimate_parts
                parts = estimate_parts(self._src_path, mb, self._info)
                if parts > 0:
                    self.lbl_estimate.setText(
                        f"Se generarán aproximadamente {parts} parte{'s' if parts != 1 else ''} de ~{mb} MB cada una."
                    )
                    return
            except Exception:
                pass
        self.lbl_estimate.setText("")

    def _limpiar(self):
        if self._worker and self._worker.isRunning():
            return
        self._src_path = ""
        self._info = None
        self._out_dir = ""
        self._last_out = ""
        self.lbl_file.setText("No se eligió ningún video")
        self.lbl_info.setText("")
        self.lbl_out.setText(etiqueta_destino(""))
        self.btn_split.setEnabled(False)
        self.pbar.setVisible(False)
        self.lbl_status.setText("")
        self.result_list.clear()
        self.result_list.setVisible(False)
        self.btn_open_folder.setVisible(False)
        self.informe_section.setVisible(False)
        self._update_estimate()

    def _pick_out_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Carpeta de salida")
        if d:
            self._out_dir = d
            self.lbl_out.setText(d)

    def _start_split(self):
        if not self._src_path:
            return
        out_dir = carpeta_destino(self._src_path, self._out_dir)
        self._last_out = out_dir
        os.makedirs(out_dir, exist_ok=True)

        self.btn_split.setEnabled(False)
        self.pbar.setRange(0, 0)        # "trabajando" hasta el primer aviso
        self.pbar.setVisible(True)
        self.result_list.clear()
        self.result_list.setVisible(False)
        self.btn_open_folder.setVisible(False)
        self.informe_section.setVisible(False)
        self.lbl_status.setText("Partiendo el video...")

        self._worker = _SplitWorker(self._src_path, out_dir, float(self.spin_size.value()))
        self._worker.progress.connect(self.lbl_status.setText)
        self._worker.pct.connect(self._on_pct)
        self._worker.finished.connect(self._on_split_done)
        self._worker.informe_ready.connect(
            lambda txt: self.informe_section.set_informe(txt, out_dir)
        )
        self._worker.error.connect(self._on_split_error)
        self._worker.start()

    def _on_pct(self, valor: int):
        if self.pbar.maximum() == 0:
            self.pbar.setRange(0, 100)
            self.pbar.setFormat("%p%")
            self.pbar.setTextVisible(True)
        self.pbar.setValue(valor)

    def _on_split_done(self, parts: list):
        self.pbar.setVisible(False)
        self.btn_split.setEnabled(True)
        if parts:
            self.lbl_status.setText(f"✅ Video dividido en {len(parts)} partes.")
            self.result_list.setVisible(True)
            self.btn_open_folder.setVisible(True)
            for p in parts:
                size = os.path.getsize(p) / (1024*1024)
                self.result_list.addItem(f"  {os.path.basename(p)}  ({size:.1f} MB)")
        else:
            self.lbl_status.setText("⚠️  No se generaron partes.")

    def _on_split_error(self, msg: str):
        self.pbar.setVisible(False)
        self.btn_split.setEnabled(True)
        self.lbl_status.setText(f"❌  {msg}")

    def _open_output_folder(self):
        target = getattr(self, "_last_out", "") or self._out_dir or ""
        if target and os.path.isdir(target):
            try:
                if platform.system() == "Windows":
                    os.startfile(target)
                elif platform.system() == "Darwin":
                    subprocess.run(["open", target])
                else:
                    subprocess.run(["xdg-open", target])
            except Exception:
                pass
