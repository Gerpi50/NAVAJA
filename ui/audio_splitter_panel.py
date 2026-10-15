"""
ui/audio_splitter_panel.py — Panel para cortar audio en partes.
Modos: por segundos o por kilobytes.
"""
import os
import platform
import subprocess

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSpinBox, QProgressBar, QListWidget, QFileDialog,
    QFrame, QButtonGroup, QRadioButton,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

from ui.informe_widget import InformeSection
from core.salidas import carpeta_destino, etiqueta_destino


AUDIO_FILTER = (
    "Audio (*.mp3 *.wav *.flac *.aac *.ogg *.opus *.m4a *.m4b "
    "*.wma *.aiff *.aif *.au *.ac3 *.ape *.mka *.caf *.ra *.dts)"
)


class _SplitWorker(QThread):
    progress      = pyqtSignal(str)
    finished      = pyqtSignal(list)
    informe_ready = pyqtSignal(str)
    error         = pyqtSignal(str)

    def __init__(self, src, out_dir, mode, value):
        super().__init__()
        self.src     = src
        self.out_dir = out_dir
        self.mode    = mode   # "seconds" | "kb"
        self.value   = value

    def run(self):
        try:
            if self.mode == "seconds":
                from motors.motor_audio_splitter import split_audio_by_seconds
                parts = split_audio_by_seconds(
                    self.src, self.out_dir, float(self.value),
                    progress_cb=self.progress.emit,
                )
            else:
                from motors.motor_audio_splitter import split_audio_by_kb
                parts = split_audio_by_kb(
                    self.src, self.out_dir, float(self.value),
                    progress_cb=self.progress.emit,
                )

            # Build informe
            try:
                from core.informe import build_informe, file_info
                orig = file_info(self.src)
                results = [file_info(p) for p in parts if os.path.exists(p)]
                modo = f"por {'duración de ' + str(self.value) + ' segundos' if self.mode == 'seconds' else 'tamaño de ' + str(self.value) + ' KB'}"
                texto = build_informe(
                    accion="dividir en partes",
                    originals=[orig],
                    results=results,
                    objeto="archivo de audio",
                    parametros=modo,
                )
                self.informe_ready.emit(texto)
            except Exception:
                pass

            self.finished.emit(parts)
        except Exception as e:
            self.error.emit(str(e))


class AudioSplitterPanel(QWidget):
    """Panel lateral para cortar audio en partes por segundos o por KB."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(380)
        self._src_path = ""
        self._out_dir  = ""
        self._worker   = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        hdr = QLabel("✂️  Cortar audio")
        hdr.setStyleSheet("font-size: 16px; font-weight: 800;")
        layout.addWidget(hdr)

        sub = QLabel("Dividí un archivo de audio en partes iguales\npor duración (segundos) o por tamaño (KB).")
        sub.setStyleSheet("font-size: 11px; color: #64748b;")
        sub.setWordWrap(True)
        layout.addWidget(sub)

        try:
            from motors.motor_audio_splitter import is_available
            if not is_available():
                warn = QLabel(
                    "⚠️  El cortador de audio necesita FFmpeg.\n"
                    "Colocá ffmpeg.exe y ffprobe.exe en la carpeta bin/ del programa."
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

        c1.addWidget(QLabel("Audio a cortar:"))
        file_row = QHBoxLayout()
        self.lbl_file = QLabel("No se eligió ningún archivo")
        self.lbl_file.setStyleSheet("font-size: 11px; color: #64748b;")
        self.lbl_file.setWordWrap(True)
        file_row.addWidget(self.lbl_file, stretch=1)
        btn_pick = QPushButton("🎵 Elegir audio")
        btn_pick.setObjectName("ghostBtn")
        btn_pick.clicked.connect(self._pick_audio)
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

        # Modo de corte
        card2 = QFrame()
        card2.setObjectName("card")
        c2 = QVBoxLayout(card2)
        c2.setContentsMargins(12, 10, 12, 10)
        c2.setSpacing(8)

        c2.addWidget(QLabel("Modo de corte:"))

        self.mode_group = QButtonGroup(self)
        mode_row = QHBoxLayout()
        self.rb_seconds = QRadioButton("Por segundos")
        self.rb_kb      = QRadioButton("Por kilobytes (KB)")
        self.rb_seconds.setChecked(True)
        self.mode_group.addButton(self.rb_seconds, 0)
        self.mode_group.addButton(self.rb_kb,      1)
        self.rb_seconds.toggled.connect(self._update_mode_ui)
        mode_row.addWidget(self.rb_seconds)
        mode_row.addWidget(self.rb_kb)
        mode_row.addStretch()
        c2.addLayout(mode_row)

        # Spin + unidad
        val_row = QHBoxLayout()
        self.spin_val = QSpinBox()
        self.spin_val.setRange(1, 99999)
        self.spin_val.setValue(30)
        self.spin_val.setSuffix(" seg")
        self.spin_val.valueChanged.connect(self._update_estimate)
        val_row.addWidget(self.spin_val)
        val_row.addStretch()
        c2.addLayout(val_row)

        # Presets dinámicos
        self.preset_label = QLabel("Presets:")
        c2.addWidget(self.preset_label)
        self.preset_row_secs = QHBoxLayout()
        self.preset_row_kb   = QHBoxLayout()

        for secs in [15, 30, 60, 120, 300]:
            label = f"{secs}s" if secs < 60 else f"{secs//60}m"
            btn = QPushButton(label)
            btn.setObjectName("presetBtn")
            btn.setMinimumWidth(50)
            btn.clicked.connect(lambda checked, v=secs: self.spin_val.setValue(v))
            self.preset_row_secs.addWidget(btn)
        self.preset_row_secs.addStretch()

        for kb in [256, 512, 1024, 2048, 4096, 9216]:  # 9 MB: queda bajo un límite de 10 MB
            label = f"{kb}KB" if kb < 1024 else f"{kb//1024}MB"
            btn = QPushButton(label)
            btn.setObjectName("presetBtn")
            btn.setMinimumWidth(50)
            btn.clicked.connect(lambda checked, v=kb: self.spin_val.setValue(v))
            self.preset_row_kb.addWidget(btn)
        self.preset_row_kb.addStretch()

        c2.addLayout(self.preset_row_secs)
        c2.addLayout(self.preset_row_kb)
        self._set_presets_visible(secs=True)

        self.lbl_estimate = QLabel("")
        self.lbl_estimate.setStyleSheet("font-size: 11px; color: #475569; font-style: italic;")
        c2.addWidget(self.lbl_estimate)

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
        self.pbar.setRange(0, 0)
        self.pbar.setVisible(False)
        layout.addWidget(self.pbar)

        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("font-size: 11px; color: #475569;")
        self.lbl_status.setWordWrap(True)
        layout.addWidget(self.lbl_status)

        self.btn_split = QPushButton("✂️  Cortar audio")
        self.btn_split.setObjectName("convertBtn")
        self.btn_split.setEnabled(False)
        self.btn_split.clicked.connect(self._start_split)
        layout.addWidget(self.btn_split)

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

    # ── Helpers ──────────────────────────────────────────────────────────

    def _set_presets_visible(self, secs: bool):
        for i in range(self.preset_row_secs.count()):
            w = self.preset_row_secs.itemAt(i).widget()
            if w:
                w.setVisible(secs)
        for i in range(self.preset_row_kb.count()):
            w = self.preset_row_kb.itemAt(i).widget()
            if w:
                w.setVisible(not secs)

    def _update_mode_ui(self):
        is_secs = self.rb_seconds.isChecked()
        if is_secs:
            self.spin_val.setSuffix(" seg")
            self.spin_val.setValue(30)
        else:
            self.spin_val.setSuffix(" KB")
            self.spin_val.setValue(512)
        self._set_presets_visible(is_secs)
        self._update_estimate()

    # ── Handlers ─────────────────────────────────────────────────────────

    def _pick_audio(self):
        path, _ = QFileDialog.getOpenFileName(self, "Elegir audio", "", AUDIO_FILTER)
        if path:
            self._src_path = path
            self.lbl_file.setText(os.path.basename(path))
            self.lbl_out.setText(carpeta_destino(path, self._out_dir))
            self.btn_split.setEnabled(True)
            self._load_audio_info(path)
            self._update_estimate()

    def _load_audio_info(self, path: str):
        size_kb = os.path.getsize(path) / 1024
        info_txt = f"Tamaño: {size_kb/1024:.2f} MB ({int(size_kb):,} KB)"
        try:
            from motors.motor_audio_splitter import get_audio_info
            info = get_audio_info(path)
            dur  = info.get("duration", 0)
            mins = int(dur) // 60
            secs = int(dur) % 60
            info_txt += f"  |  Duración: {mins}m {secs:02d}s"
        except Exception:
            pass
        self.lbl_info.setText(info_txt)

    def _update_estimate(self):
        if not self._src_path:
            self.lbl_estimate.setText("")
            return
        try:
            val = self.spin_val.value()
            if self.rb_seconds.isChecked():
                from motors.motor_audio_splitter import estimate_parts_by_seconds
                parts = estimate_parts_by_seconds(self._src_path, val)
                if parts > 0:
                    self.lbl_estimate.setText(
                        f"Se generarán ~{parts} parte{'s' if parts != 1 else ''} de {val} segundos cada una."
                    )
                    return
            else:
                from motors.motor_audio_splitter import estimate_parts_by_kb
                parts = estimate_parts_by_kb(self._src_path, val)
                if parts > 0:
                    self.lbl_estimate.setText(
                        f"Se generarán ~{parts} parte{'s' if parts != 1 else ''} de ~{val} KB cada una."
                    )
                    return
        except Exception:
            pass
        self.lbl_estimate.setText("")

    def _limpiar(self):
        if self._worker and self._worker.isRunning():
            return
        self._src_path = ""
        self._out_dir = ""
        self._last_out = ""
        self.lbl_file.setText("No se eligió ningún archivo")
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

        mode  = "seconds" if self.rb_seconds.isChecked() else "kb"
        value = self.spin_val.value()

        self.btn_split.setEnabled(False)
        self.pbar.setVisible(True)
        self.result_list.clear()
        self.result_list.setVisible(False)
        self.btn_open_folder.setVisible(False)
        self.informe_section.setVisible(False)
        self.lbl_status.setText("Cortando el audio...")

        self._worker = _SplitWorker(self._src_path, out_dir, mode, value)
        self._worker.progress.connect(self.lbl_status.setText)
        self._worker.finished.connect(self._on_done)
        self._worker.informe_ready.connect(
            lambda txt: self.informe_section.set_informe(txt, out_dir)
        )
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_done(self, parts: list):
        self.pbar.setVisible(False)
        self.btn_split.setEnabled(True)
        if parts:
            self.lbl_status.setText(f"✅ Audio dividido en {len(parts)} partes.")
            self.result_list.setVisible(True)
            self.btn_open_folder.setVisible(True)
            for p in parts:
                size_kb = os.path.getsize(p) / 1024
                self.result_list.addItem(f"  {os.path.basename(p)}  ({size_kb:.0f} KB)")
        else:
            self.lbl_status.setText("⚠️  No se generaron partes.")

    def _on_error(self, msg: str):
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
