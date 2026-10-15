"""
ui/video_compress_panel.py — Ajustar el tamaño de un video: comprimirlo o
cortarlo en partes, con informe técnico y hash de cada archivo.
"""
import math
import os
import platform
import shutil
import subprocess
import time

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QListWidget, QListWidgetItem, QFileDialog,
    QFrame, QRadioButton, QButtonGroup, QDoubleSpinBox,
    QPlainTextEdit,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

from ui.informe_widget import InformeSection
from core.salidas import etiqueta_destino
from motors.motor_video_compress import TARGET_MAX_MB


VIDEO_EXTS = {
    ".mp4", ".mkv", ".avi", ".mov", ".webm",
    ".flv", ".wmv", ".m4v", ".3gp", ".ts",
    ".mpg", ".mpeg", ".ogv", ".vob",
}


# ── Worker ────────────────────────────────────────────────────────────────

class _HashAparte:
    """Calcula el SHA-256 de un archivo en segundo plano."""

    def __init__(self, ruta: str):
        import threading
        self.ruta = ruta
        self.pct = 0
        self.hash = ""
        self.error = None
        self._hilo = threading.Thread(target=self._calcular, daemon=True)

    def start(self):
        self._hilo.start()

    def _calcular(self):
        try:
            from motors.motor_video_compress import sha256_file
            self.hash = sha256_file(
                self.ruta, pct_cb=lambda p: setattr(self, "pct", p))
        except Exception as e:
            self.error = e

    def esperar(self, pct_cb) -> str:
        """Espera a que termine, avisando el avance; devuelve el hash."""
        while self._hilo.is_alive():
            pct_cb(self.pct)
            self._hilo.join(0.2)
        if self.error:
            raise self.error
        pct_cb(100)
        return self.hash


class _CompressWorker(QThread):
    progress      = pyqtSignal(str)
    pct           = pyqtSignal(int)         # avance del paso en curso (0–100)
    finished      = pyqtSignal(str, list)   # (informe_path, final_paths)
    informe_ready = pyqtSignal(str, str)    # (texto, op_dir)
    error         = pyqtSignal(str)

    def __init__(self, files: list, mode: str, custom_mb: float = TARGET_MAX_MB,
                 out_dir: str = ""):
        super().__init__()
        self.files     = files
        self.mode      = mode       # "half" | "third" | "target" | "custom" | "split"
        self.custom_mb = custom_mb
        self.out_dir   = out_dir    # "" = carpeta por defecto junto a los originales

    def run(self):
        try:
            from core.paths import TEMP_DIR
            from core.salidas import (
                preparar_destino, carpeta_de_archivo,
                repartir_en_tandas, cantidad_de_tandas,
            )
            from motors.motor_video_compress import (
                sha256_file, get_video_info, compress_video,
                split_video_by_size, write_informe,
            )

            is_split = (self.mode == "split")
            destino  = preparar_destino(self.files, self.out_dir)
            self.progress.emit(f"📁  Carpeta de destino: {destino}")

            # Se trabaja en TEMP y recién al final se mueve al destino: si el
            # destino es un pendrive lento, escribir directo tarda minutos.
            tmp_session = os.path.join(
                str(TEMP_DIR), f"compress_{os.getpid()}_{int(time.time()*1000)}"
            )
            os.makedirs(tmp_session, exist_ok=True)

            todos_originales = []
            todos_resultados = []
            final_paths      = []
            informe_path     = ""
            informe_texto    = ""
            informe_dir      = destino

            try:
                for indice, src in enumerate(self.files, start=1):
                    name = os.path.basename(src)
                    stem = os.path.splitext(name)[0]
                    self.progress.emit(f"\n📂  {name}  ({indice}/{len(self.files)})")

                    # El hash del original se calcula mientras se trabaja,
                    # no antes: con un video de una hora eran varios minutos
                    # sin que pasara nada a la vista. El original sólo se
                    # lee, así que el hash es el mismo antes que después.
                    hash_orig = _HashAparte(src)
                    hash_orig.start()

                    staging = os.path.join(tmp_session, f"{indice}_{stem}")
                    os.makedirs(staging, exist_ok=True)

                    if is_split:
                        generados = split_video_by_size(
                            src, staging, progress_cb=self.progress.emit,
                            pct_cb=self.pct.emit,
                        )
                    else:
                        info    = get_video_info(src)
                        size_mb = info["size_mb"]
                        if self.mode == "half":
                            target_mb = size_mb / 2
                        elif self.mode == "third":
                            target_mb = size_mb / 3
                        elif self.mode == "target":
                            target_mb = TARGET_MAX_MB
                        else:
                            target_mb = self.custom_mb

                        out_path = os.path.join(staging, f"{stem}_reducido.mp4")
                        compress_video(
                            src, out_path, target_mb,
                            progress_cb=self.progress.emit,
                            pct_cb=self.pct.emit,
                        )
                        generados = [out_path] if os.path.exists(out_path) else []

                    if not generados:
                        raise RuntimeError(
                            f"No se generó ningún archivo de salida para «{name}»."
                        )

                    # Auditoría: hash del original (ya venía calculándose)
                    self.progress.emit("🔐  Calculando SHA-256 del original…")
                    orig_hash = hash_orig.esperar(self.pct.emit)
                    orig_info = {"filename": name, "sha256": orig_hash}
                    todos_originales.append(orig_info)
                    self.progress.emit(f"   {orig_hash[:24]}…{orig_hash[-8:]}")

                    # Auditoría post: hash de resultantes (antes de mover a tandas)
                    self.progress.emit("🔐  Calculando SHA-256 de los resultantes…")
                    resultados = []
                    for n_res, r in enumerate(generados, start=1):
                        self.pct.emit(int(n_res * 100 / len(generados)))
                        r_hash = sha256_file(r)
                        resultados.append({
                            "filename": os.path.basename(r),
                            "sha256":   r_hash,
                        })
                        self.progress.emit(
                            f"   {os.path.basename(r)}: {r_hash[:16]}…{r_hash[-8:]}"
                        )
                    todos_resultados.extend(resultados)

                    # Carpeta propia de este video, para no mezclar las partes
                    # de varios videos en la misma tanda.
                    carpeta = carpeta_de_archivo(destino, src)

                    # Informe técnico de este archivo, dentro de su carpeta
                    self.progress.emit("📝  Redactando informe técnico…")
                    ruta_informe = write_informe(
                        carpeta, stem, [orig_info], resultados, is_split=is_split
                    )
                    self.progress.emit(f"✅  {os.path.basename(ruta_informe)}")

                    # Tandas de 5 (muchos portales limitan cuántos archivos se suben por vez)
                    finales = repartir_en_tandas(
                        generados, carpeta, progreso=self.progress.emit
                    )
                    final_paths.extend(finales)
                    tandas = cantidad_de_tandas(len(finales))
                    self.progress.emit(
                        f"✅  {len(finales)} archivo(s) en {tandas} tanda(s)  →  "
                        f"{os.path.basename(carpeta)}"
                    )

                    if len(self.files) == 1:
                        informe_path = ruta_informe
                        informe_dir  = carpeta

                # Con varios videos, además un informe general en la raíz
                if len(self.files) > 1:
                    self.progress.emit("\n📝  Redactando informe general…")
                    informe_path = write_informe(
                        destino, "General", todos_originales, todos_resultados,
                        is_split=is_split,
                    )
                    informe_dir = destino
                    self.progress.emit(f"✅  {os.path.basename(informe_path)}")

                try:
                    with open(informe_path, "r", encoding="utf-8") as _fh:
                        informe_texto = _fh.read()
                    self.informe_ready.emit(informe_texto, informe_dir)
                except Exception:
                    pass

            finally:
                shutil.rmtree(tmp_session, ignore_errors=True)

            self.finished.emit(informe_path, final_paths)

        except Exception as exc:
            import traceback
            self.error.emit(f"{exc}\n\n{traceback.format_exc()[-800:]}")


# ── Panel ─────────────────────────────────────────────────────────────────

class VideoCompressPanel(QWidget):
    """Panel para ajustar videos a un tamaño máximo."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(420)
        self._files: list      = []
        self._info: dict       = {}    # path → {"duration": float, "size_mb": float}
        self._worker           = None
        self._last_op_dir: str = ""
        self._out_dir: str     = ""   # "" = carpeta por defecto junto a los originales
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # ── Header ────────────────────────────────────────────────────
        hdr = QLabel("📦  Ajustar tamaño")
        hdr.setStyleSheet("font-size: 16px; font-weight: 800;")
        layout.addWidget(hdr)

        sub = QLabel(
            "Comprimí o cortá videos para que entren en el límite de un correo, un formulario o un portal.\n"
            "Genera tandas de hasta 5 archivos y un informe técnico con el hash de cada uno."
        )
        sub.setStyleSheet("font-size: 11px; color: #64748b;")
        sub.setWordWrap(True)
        layout.addWidget(sub)

        # ── Verificar FFmpeg ──────────────────────────────────────────
        try:
            from motors.motor_video_compress import is_available
            if not is_available():
                warn = QLabel(
                    "⚠️  Esta herramienta necesita FFmpeg y FFprobe.\n"
                    "Colocá ffmpeg.exe y ffprobe.exe en la carpeta bin/ del programa\n"
                    "o asegurate de que estén instalados en el PATH del sistema."
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

        # ── Card: Archivos ────────────────────────────────────────────
        card1 = QFrame()
        card1.setObjectName("card")
        c1 = QVBoxLayout(card1)
        c1.setContentsMargins(12, 10, 12, 10)
        c1.setSpacing(6)

        hdr_row = QHBoxLayout()
        hdr_row.addWidget(QLabel("📂  Videos a procesar:"))
        hdr_row.addStretch()
        btn_clear = QPushButton("🗑 Limpiar")
        btn_clear.setObjectName("ghostBtn")
        btn_clear.setFixedWidth(78)
        btn_clear.clicked.connect(self._clear_files)
        hdr_row.addWidget(btn_clear)
        c1.addLayout(hdr_row)

        self.file_list = QListWidget()
        self.file_list.setMaximumHeight(130)
        self.file_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        c1.addWidget(self.file_list)

        btn_row = QHBoxLayout()
        for label, slot in [
            ("📄 Archivos", self._pick_files),
            ("📁 Carpeta",  self._pick_folder),
            ("✕ Quitar",    self._remove_selected),
        ]:
            b = QPushButton(label)
            b.setObjectName("ghostBtn")
            b.clicked.connect(slot)
            btn_row.addWidget(b)
        c1.addLayout(btn_row)

        self.lbl_total = QLabel("Ningún video seleccionado.")
        self.lbl_total.setStyleSheet(
            "font-size: 11px; color: #475569; font-style: italic;"
        )
        c1.addWidget(self.lbl_total)
        layout.addWidget(card1)

        # ── Card: Carpeta de destino ──────────────────────────────────
        card_out = QFrame()
        card_out.setObjectName("card")
        co = QVBoxLayout(card_out)
        co.setContentsMargins(12, 10, 12, 10)
        co.setSpacing(4)
        co.addWidget(QLabel("📁  Carpeta de destino:"))

        out_row = QHBoxLayout()
        self.lbl_out = QLabel(etiqueta_destino(""))
        self.lbl_out.setStyleSheet("font-size: 11px; color: #64748b;")
        self.lbl_out.setWordWrap(True)
        out_row.addWidget(self.lbl_out, stretch=1)
        btn_out = QPushButton("Cambiar")
        btn_out.setObjectName("ghostBtn")
        btn_out.clicked.connect(self._pick_out_dir)
        out_row.addWidget(btn_out)
        self.btn_out_reset = QPushButton("Por defecto")
        self.btn_out_reset.setObjectName("ghostBtn")
        self.btn_out_reset.setVisible(False)
        self.btn_out_reset.clicked.connect(self._reset_out_dir)
        out_row.addWidget(self.btn_out_reset)
        co.addLayout(out_row)

        nota = QLabel(
            "Se arma una carpeta por cada video, y adentro las tandas de 5 "
            "archivos con el informe."
        )
        nota.setStyleSheet("font-size: 10px; color: #94a3b8;")
        nota.setWordWrap(True)
        co.addWidget(nota)
        layout.addWidget(card_out)

        # ── Card: Operación ───────────────────────────────────────────
        card2 = QFrame()
        card2.setObjectName("card")
        c2 = QVBoxLayout(card2)
        c2.setContentsMargins(12, 10, 12, 10)
        c2.setSpacing(4)
        c2.addWidget(QLabel("⚙️  Operación:"))

        self._btn_group = QButtonGroup(self)

        def _radio(mode: str, text: str) -> tuple:
            rb = QRadioButton(text)
            rb.setProperty("compress_mode", mode)
            self._btn_group.addButton(rb)
            c2.addWidget(rb)
            lbl = QLabel("")
            lbl.setStyleSheet(
                "font-size: 10px; color: #64748b; padding-left: 20px;"
            )
            lbl.setWordWrap(True)
            c2.addWidget(lbl)
            return rb, lbl

        self._rb_half,  self._lbl_half  = _radio("half",  "Reducir a 1/2 del tamaño")
        self._rb_third, self._lbl_third = _radio("third", "Reducir a 1/3 del tamaño")
        self._rb_target,  self._lbl_target  = _radio("target", f"Forzar {TARGET_MAX_MB:g} MB")

        # Personalizado: radio + spinbox en la misma fila
        crow = QHBoxLayout()
        self._rb_custom = QRadioButton("Personalizado: ")
        self._rb_custom.setProperty("compress_mode", "custom")
        self._btn_group.addButton(self._rb_custom)
        crow.addWidget(self._rb_custom)
        self._spin_custom = QDoubleSpinBox()
        self._spin_custom.setRange(1.0, 2048.0)
        self._spin_custom.setValue(50.0)
        self._spin_custom.setSuffix(" MB")
        self._spin_custom.setFixedWidth(100)
        self._spin_custom.valueChanged.connect(self._update_labels)
        crow.addWidget(self._spin_custom)
        crow.addStretch()
        c2.addLayout(crow)
        self._lbl_custom = QLabel("")
        self._lbl_custom.setStyleSheet(
            "font-size: 10px; color: #64748b; padding-left: 20px;"
        )
        self._lbl_custom.setWordWrap(True)
        c2.addWidget(self._lbl_custom)

        self._rb_split, self._lbl_split = _radio(
            "split", f"Cortar en partes de {TARGET_MAX_MB:g} MB (sin pérdida de calidad)"
        )

        self._rb_target.setChecked(True)
        self._btn_group.buttonClicked.connect(lambda _: self._update_labels())

        layout.addWidget(card2)

        # ── Progreso ──────────────────────────────────────────────────
        self.pbar = QProgressBar()
        self.pbar.setRange(0, 0)
        self.pbar.setVisible(False)
        layout.addWidget(self.pbar)

        self.log_area = QPlainTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setMaximumHeight(160)
        self.log_area.setPlaceholderText("El log de procesamiento aparecerá aquí…")
        self.log_area.setStyleSheet(
            "font-family: 'Cascadia Code', 'Fira Code', Consolas, monospace;"
            "font-size: 10px;"
        )
        self.log_area.setVisible(False)
        layout.addWidget(self.log_area)

        # ── Botones de acción ─────────────────────────────────────────
        action_row = QHBoxLayout()

        self.btn_open = QPushButton("📂 Abrir carpeta")
        self.btn_open.setObjectName("ghostBtn")
        self.btn_open.setVisible(False)
        self.btn_open.clicked.connect(self._open_result_folder)
        action_row.addWidget(self.btn_open)

        self.btn_process = QPushButton("⚖️  PROCESAR VIDEOS")
        self.btn_process.setObjectName("convertBtn")
        self.btn_process.setEnabled(False)
        self.btn_process.clicked.connect(self._start_processing)
        action_row.addWidget(self.btn_process, stretch=1)

        layout.addLayout(action_row)

        # ── Informe técnico ───────────────────────────────────────────
        self.informe_section = InformeSection()
        layout.addWidget(self.informe_section)

        layout.addStretch()

    # ── Gestión de archivos ───────────────────────────────────────────

    def _pick_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Seleccionar videos", "",
            "Videos (*.mp4 *.mkv *.avi *.mov *.webm *.flv *.wmv "
            "*.m4v *.3gp *.ts *.mpg *.mpeg *.ogv *.vob)"
        )
        self._add_paths(paths)

    def _pick_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta de videos")
        if not folder:
            return
        paths = sorted(
            os.path.join(folder, f)
            for f in os.listdir(folder)
            if os.path.splitext(f)[1].lower() in VIDEO_EXTS
            and os.path.isfile(os.path.join(folder, f))
        )
        self._add_paths(paths)

    def _add_paths(self, paths: list):
        for p in paths:
            if p in self._files:
                continue
            self._files.append(p)
            size_mb = os.path.getsize(p) / (1024 * 1024)
            self.file_list.addItem(f"  {os.path.basename(p)}  ({size_mb:.1f} MB)")
            # Cache info via ffprobe (lightweight header read)
            try:
                from motors.motor_video_compress import get_video_info
                self._info[p] = get_video_info(p)
            except Exception:
                self._info[p] = {"duration": 0, "size_mb": size_mb}
        self._refresh_state()

    def _remove_selected(self):
        rows = sorted(
            {self.file_list.row(item) for item in self.file_list.selectedItems()},
            reverse=True,
        )
        for row in rows:
            if 0 <= row < len(self._files):
                p = self._files.pop(row)
                self._info.pop(p, None)
                self.file_list.takeItem(row)
        self._refresh_state()

    def _clear_files(self):
        if self._worker and self._worker.isRunning():
            return
        self._files.clear()
        self._info.clear()
        self.file_list.clear()
        self._refresh_state()
        self.btn_open.setVisible(False)
        self.informe_section.setVisible(False)

    def _pick_out_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Carpeta de destino")
        if d:
            self._out_dir = d
            self.btn_out_reset.setVisible(True)
            self._refresh_out_label()

    def _reset_out_dir(self):
        self._out_dir = ""
        self.btn_out_reset.setVisible(False)
        self._refresh_out_label()

    def _refresh_out_label(self):
        self.lbl_out.setText(etiqueta_destino(self._files, self._out_dir))

    def _refresh_state(self):
        has = bool(self._files)
        self.btn_process.setEnabled(has)
        if has:
            n        = len(self._files)
            total_mb = sum(self._info.get(p, {}).get("size_mb", 0) for p in self._files)
            self.lbl_total.setText(
                f"{n} video{'s' if n != 1 else ''}  |  Total: {total_mb:.1f} MB"
            )
        else:
            self.lbl_total.setText("Ningún video seleccionado.")
        self._refresh_out_label()
        self._update_labels()

    # ── Etiquetas dinámicas por modo ──────────────────────────────────

    def _update_labels(self):
        if not self._files:
            for lbl in [
                self._lbl_half, self._lbl_third,
                self._lbl_target, self._lbl_custom, self._lbl_split,
            ]:
                lbl.setText("")
            return

        from motors.motor_video_compress import estimate_target_quality, estimate_split_parts

        total_mb     = sum(self._info.get(p, {}).get("size_mb", 0) for p in self._files)
        max_duration = max(
            (self._info.get(p, {}).get("duration", 0) for p in self._files),
            default=0,
        )

        self._lbl_half.setText(
            f"Pasará de {total_mb:.1f} MB a ~{total_mb/2:.1f} MB  |  "
            "Calidad Buena / Similar al original. Pérdida casi imperceptible."
        )
        self._lbl_third.setText(
            f"Pasará de {total_mb:.1f} MB a ~{total_mb/3:.1f} MB  |  "
            "Calidad Aceptable. Se puede notar algo de compresión en escenas rápidas."
        )

        if max_duration > 0:
            bps, msg = estimate_target_quality(max_duration, TARGET_MAX_MB)
            self._lbl_target.setText(
                f"Pasará de {total_mb:.1f} MB a {TARGET_MAX_MB:g} MB  |  "
                f"Bitrate estimado: {bps:.0f} kbps  |  {msg}"
            )
        else:
            self._lbl_target.setText(
                f"Pasará de {total_mb:.1f} MB a {TARGET_MAX_MB:g} MB fijo."
            )

        custom_mb = self._spin_custom.value()
        self._lbl_custom.setText(
            f"Pasará de {total_mb:.1f} MB a ~{custom_mb:.1f} MB por archivo."
        )

        total_parts = sum(
            estimate_split_parts(self._info.get(p, {}).get("size_mb", 0))
            for p in self._files
        )
        self._lbl_split.setText(
            f"~{total_parts} parte(s) totales de ≤{TARGET_MAX_MB:g} MB  |  "
            "Corte instantáneo sin pérdida de calidad."
        )

    # ── Procesamiento ─────────────────────────────────────────────────

    def _get_mode(self) -> str:
        btn = self._btn_group.checkedButton()
        return btn.property("compress_mode") if btn else "target"

    def _start_processing(self):
        if not self._files:
            return
        mode      = self._get_mode()
        custom_mb = self._spin_custom.value()

        self.btn_process.setEnabled(False)
        self.btn_open.setVisible(False)
        self.informe_section.setVisible(False)
        self.log_area.clear()
        self.log_area.setVisible(True)
        self.pbar.setRange(0, 0)        # "trabajando" hasta el primer aviso
        self.pbar.setVisible(True)

        self._worker = _CompressWorker(
            list(self._files), mode, custom_mb, self._out_dir
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.pct.connect(self._on_pct)
        self._worker.finished.connect(self._on_done)
        self._worker.informe_ready.connect(self.informe_section.set_informe)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_pct(self, valor: int):
        if self.pbar.maximum() == 0:
            self.pbar.setRange(0, 100)
            self.pbar.setFormat("%p%")
            self.pbar.setTextVisible(True)
        self.pbar.setValue(valor)

    def _on_progress(self, msg: str):
        self.log_area.appendPlainText(msg)
        sb = self.log_area.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _on_done(self, informe_path: str, final_paths: list):
        self.pbar.setVisible(False)
        self.btn_process.setEnabled(True)
        self._last_op_dir = os.path.dirname(informe_path) if informe_path else ""
        n = len(final_paths)
        self.log_area.appendPlainText(
            f"\n✅  Proceso completado.\n"
            f"   {n} archivo(s) generado(s).\n"
            f"   Carpeta: {self._last_op_dir}"
        )
        self.btn_open.setVisible(True)

    def _on_error(self, msg: str):
        self.pbar.setVisible(False)
        self.btn_process.setEnabled(True)
        self.log_area.appendPlainText(f"\n❌  ERROR:\n{msg}")

    def _open_result_folder(self):
        folder = self._last_op_dir
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
