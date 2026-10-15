"""
ui/audio_merger_panel.py — Panel para unir múltiples archivos de audio.
"""
import os
import platform
import subprocess

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QDoubleSpinBox, QProgressBar, QTextEdit, QFrame, QFileDialog,
)
from PyQt6.QtCore import QThread, pyqtSignal

from ui.informe_widget import InformeSection
from core.salidas import carpeta_destino, etiqueta_destino


class _MergeWorker(QThread):
    log_msg       = pyqtSignal(str)
    finished      = pyqtSignal(list)
    informe_ready = pyqtSignal(str)
    error         = pyqtSignal(str)

    def __init__(self, files, output_dir, max_mb):
        super().__init__()
        self.files      = files
        self.output_dir = output_dir
        self.max_mb     = max_mb

    def run(self):
        try:
            from motors.motor_audio_merger import merge_audio
            parts = merge_audio(
                self.files,
                self.output_dir,
                self.max_mb,
                progress_cb=self.log_msg.emit,
            )

            # Build informe
            try:
                from core.informe import build_informe, file_info
                originals = [file_info(f) for f in self.files]
                results   = [file_info(p) for p in parts if os.path.exists(p)]
                texto = build_informe(
                    accion="unir",
                    originals=originals,
                    results=results,
                    objeto="archivo de audio",
                    parametros=f"partes de máximo {self.max_mb} MB",
                )
                self.informe_ready.emit(texto)
            except Exception:
                pass

            self.finished.emit(parts)
        except Exception as e:
            self.error.emit(str(e))


class AudioMergerPanel(QWidget):
    """Panel lateral para unir múltiples audios y partir por tamaño."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(400)
        self._folder  = ""
        self._files   = []
        self._out_dir = ""
        self._worker  = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        hdr = QLabel("🎵  Unir archivos de audio")
        hdr.setStyleSheet("font-size: 16px; font-weight: 800;")
        layout.addWidget(hdr)

        sub = QLabel(
            "Concatená múltiples audios de una carpeta en orden alfabético\n"
            "y partí el resultado en partes del tamaño que necesitás."
        )
        sub.setStyleSheet("font-size: 11px; color: #64748b;")
        sub.setWordWrap(True)
        layout.addWidget(sub)

        try:
            from motors.motor_audio_merger import is_available
            if not is_available():
                warn = QLabel(
                    "⚠️  Esta herramienta necesita FFmpeg.\n"
                    "Colocá ffmpeg.exe en la carpeta bin/ del programa."
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

        # ── Carpeta de entrada ───────────────────────────────────────
        card1 = QFrame()
        card1.setObjectName("card")
        c1 = QVBoxLayout(card1)
        c1.setContentsMargins(12, 10, 12, 10)
        c1.setSpacing(8)

        c1.addWidget(QLabel("Carpeta con los archivos de audio:"))
        row1 = QHBoxLayout()
        self.lbl_folder = QLabel("Ninguna carpeta seleccionada")
        self.lbl_folder.setStyleSheet("font-size: 11px; color: #64748b;")
        self.lbl_folder.setWordWrap(True)
        row1.addWidget(self.lbl_folder, stretch=1)
        btn_pick = QPushButton("📁 Elegir carpeta")
        btn_pick.setObjectName("ghostBtn")
        btn_pick.clicked.connect(self._pick_folder)
        row1.addWidget(btn_pick)
        btn_limpiar = QPushButton("🗑 Limpiar")
        btn_limpiar.setObjectName("ghostBtn")
        btn_limpiar.setToolTip(
            "Deja la solapa como recién abierta, para empezar con otra "
            "carpeta.\nNo borra nada del disco.")
        btn_limpiar.clicked.connect(self._limpiar)
        row1.addWidget(btn_limpiar)
        c1.addLayout(row1)

        self.lbl_folder_info = QLabel("")
        self.lbl_folder_info.setStyleSheet("font-size: 11px; color: #475569;")
        c1.addWidget(self.lbl_folder_info)
        layout.addWidget(card1)

        # ── Tamaño máximo ────────────────────────────────────────────
        card2 = QFrame()
        card2.setObjectName("card")
        c2 = QVBoxLayout(card2)
        c2.setContentsMargins(12, 10, 12, 10)
        c2.setSpacing(8)

        c2.addWidget(QLabel("Tamaño máximo de cada parte:"))
        size_row = QHBoxLayout()
        self.spin_size = QDoubleSpinBox()
        self.spin_size.setRange(0.5, 500)
        self.spin_size.setValue(10.0)
        self.spin_size.setDecimals(1)
        self.spin_size.setSuffix(" MB")
        size_row.addWidget(self.spin_size)
        size_row.addStretch()
        c2.addLayout(size_row)

        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel("Presets:"))
        for mb, tip in [(5, "Email estándar"), (9, "Queda bajo un límite de 10 MB"), (10, "Email extendido"), (15, "WhatsApp"), (20, "Uso general")]:
            btn = QPushButton(f"{mb} MB")
            btn.setObjectName("presetBtn")
            btn.setMinimumWidth(58)
            btn.setToolTip(tip)
            btn.clicked.connect(lambda checked, v=float(mb): self.spin_size.setValue(v))
            preset_row.addWidget(btn)
        c2.addLayout(preset_row)
        layout.addWidget(card2)

        # ── Carpeta de salida ────────────────────────────────────────
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

        # ── Progreso ─────────────────────────────────────────────────
        self.pbar = QProgressBar()
        self.pbar.setRange(0, 0)
        self.pbar.setVisible(False)
        layout.addWidget(self.pbar)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setStyleSheet(
            "background: #111111; color: #00ff41; "
            "font-family: Consolas, monospace; font-size: 11px; "
            "border-radius: 6px;"
        )
        self.log.setMinimumHeight(100)
        self.log.setMaximumHeight(180)
        self.log.setVisible(False)
        layout.addWidget(self.log)

        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("font-size: 11px; color: #475569;")
        self.lbl_status.setWordWrap(True)
        layout.addWidget(self.lbl_status)

        self.btn_run = QPushButton("🎵  Unir archivos de audio")
        self.btn_run.setObjectName("convertBtn")
        self.btn_run.setEnabled(False)
        self.btn_run.clicked.connect(self._start)
        layout.addWidget(self.btn_run)

        self.btn_open = QPushButton("📂 Abrir carpeta de resultados")
        self.btn_open.setObjectName("ghostBtn")
        self.btn_open.setVisible(False)
        self.btn_open.clicked.connect(self._open_output)
        layout.addWidget(self.btn_open)

        # ── Informe técnico ───────────────────────────────────────────
        self.informe_section = InformeSection()
        layout.addWidget(self.informe_section)

        layout.addStretch()

    # ── Handlers ─────────────────────────────────────────────────────

    def _pick_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Carpeta con archivos de audio")
        if not folder:
            return
        self._folder = folder
        self.lbl_folder.setText(os.path.basename(folder) or folder)
        self.lbl_folder.setToolTip(folder)

        from motors.motor_audio_merger import collect_audio_files
        self._files = collect_audio_files(folder)

        if self._files:
            from collections import Counter
            exts = Counter(os.path.splitext(f)[1].lower() for f in self._files)
            ext_txt = "  |  ".join(f"{v} {k.upper()}" for k, v in sorted(exts.items()))
            self.lbl_folder_info.setText(
                f"{len(self._files)} archivo{'s' if len(self._files)!=1 else ''} encontrado{'s' if len(self._files)!=1 else ''}:  {ext_txt}"
            )
            self.btn_run.setEnabled(True)
            self.lbl_out.setText(carpeta_destino(folder, self._out_dir))
        else:
            self.lbl_folder_info.setText("⚠  No hay archivos de audio en esta carpeta.")
            self.btn_run.setEnabled(False)

    def _limpiar(self):
        if self._worker and self._worker.isRunning():
            return
        self._folder = ""
        self._files = []
        self._out_dir = ""
        self._last_out = ""
        self.lbl_folder.setText("Ninguna carpeta seleccionada")
        self.lbl_folder.setToolTip("")
        self.lbl_folder_info.setText("")
        self.lbl_out.setText(etiqueta_destino(""))
        self.btn_run.setEnabled(False)
        self.pbar.setVisible(False)
        self.log.clear()
        self.log.setVisible(False)
        self.lbl_status.setText("")
        self.btn_open.setVisible(False)
        self.informe_section.setVisible(False)

    def _pick_out_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Carpeta de salida")
        if d:
            self._out_dir = d
            self.lbl_out.setText(d)

    def _start(self):
        if not self._files:
            return

        out_dir = carpeta_destino(self._folder, self._out_dir)
        self._last_out = out_dir
        os.makedirs(out_dir, exist_ok=True)

        self.btn_run.setEnabled(False)
        self.btn_open.setVisible(False)
        self.informe_section.setVisible(False)
        self.log.clear()
        self.log.setVisible(True)
        self.pbar.setVisible(True)
        self.lbl_status.setText("Procesando…")

        self._worker = _MergeWorker(self._files, out_dir, self.spin_size.value())
        self._worker.log_msg.connect(self._append_log)
        self._worker.finished.connect(self._on_done)
        self._worker.informe_ready.connect(
            lambda txt: self.informe_section.set_informe(txt, out_dir)
        )
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _append_log(self, text: str):
        self.log.append(text)
        self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())

    def _on_done(self, parts: list):
        self.pbar.setVisible(False)
        self.btn_run.setEnabled(True)
        self.lbl_status.setText(
            f"✅  {len(self._files)} archivos unidos  →  "
            f"{len(parts)} parte{'s' if len(parts)!=1 else ''} generada{'s' if len(parts)!=1 else ''}"
        )
        self.btn_open.setVisible(True)

    def _on_error(self, msg: str):
        self.pbar.setVisible(False)
        self.btn_run.setEnabled(True)
        self.lbl_status.setText(f"❌  {msg}")

    def _open_output(self):
        folder = getattr(self, "_last_out", "") or self._out_dir
        if folder and os.path.isdir(folder):
            try:
                if platform.system() == "Windows":
                    os.startfile(folder)
                elif platform.system() == "Darwin":
                    subprocess.run(["open", folder])
                else:
                    subprocess.run(["xdg-open", folder])
            except Exception:
                pass
