"""
ui/pdf_merger_splitter_panel.py — Panel para unir PDFs y partir por tamaño.
"""
import io
import os
import platform
import subprocess

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QDoubleSpinBox, QProgressBar, QTextEdit, QFrame, QFileDialog,
    QSizePolicy, QCheckBox,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

from ui.informe_widget import InformeSection
from core.salidas import carpeta_destino, etiqueta_destino


class _MergerWorker(QThread):
    log_msg        = pyqtSignal(str)
    progress_files = pyqtSignal(int, int)
    progress_pages = pyqtSignal(int, int)
    finished       = pyqtSignal(int, int, int, str)
    informe_ready  = pyqtSignal(str)
    error          = pyqtSignal(str)

    CHECK_THRESHOLD = 0.85

    def __init__(self, folder: str, max_mb: float, no_limit: bool = False,
                 out_dir: str = ""):
        super().__init__()
        self.folder = folder
        self.max_mb = max_mb
        self.no_limit = no_limit
        self.out_dir = out_dir   # "" = carpeta por defecto junto a los originales

    def run(self):
        try:
            from pypdf import PdfReader, PdfWriter
        except ImportError:
            self.error.emit("pypdf no está instalado. Ejecutá: pip install pypdf")
            return

        folder = self.folder
        max_bytes = int(self.max_mb * 1024 * 1024)

        pdf_files = sorted([
            os.path.join(folder, f)
            for f in os.listdir(folder)
            if f.lower().endswith(".pdf")
        ])

        if not pdf_files:
            self.error.emit("No se encontraron archivos PDF en la carpeta seleccionada.")
            return

        from core.salidas import preparar_destino
        output_folder = preparar_destino(folder, self.out_dir)

        total_files = len(pdf_files)
        self.log_msg.emit(f"Archivos detectados: {total_files}")
        if self.no_limit:
            self.log_msg.emit("Sin límite de tamaño: se generará un solo archivo")
        else:
            self.log_msg.emit(f"Tamaño máximo: {self.max_mb} MB")

        total_pages_est = 0
        for f in pdf_files:
            try:
                total_pages_est += len(PdfReader(f).pages)
            except Exception:
                pass
        self.progress_files.emit(0, total_files)
        self.progress_pages.emit(0, max(1, total_pages_est))

        pending_pages = []
        pending_approx = 0
        total_pages = 0
        output_count = 1

        def save_batch(pages):
            nonlocal output_count
            w = PdfWriter()
            for p in pages:
                w.add_page(p)
            name = "unido.pdf" if self.no_limit else f"salida_{output_count}.pdf"
            out_path = os.path.join(output_folder, name)
            w.write(out_path)
            size_kb = os.path.getsize(out_path) / 1024
            self.log_msg.emit(f"  ✅ Guardado: {name}  ({size_kb:.0f} KB)")
            output_count += 1

        def real_size_of(pages) -> int:
            buf = io.BytesIO()
            w = PdfWriter()
            for p in pages:
                w.add_page(p)
            w.write(buf)
            size = buf.tell()
            del buf
            return size

        for i, pdf_path in enumerate(pdf_files):
            self.log_msg.emit(f"Procesando: {os.path.basename(pdf_path)}")
            try:
                reader = PdfReader(pdf_path)
            except Exception as e:
                self.log_msg.emit(f"  ⚠ Error leyendo archivo: {e}")
                self.progress_files.emit(i + 1, total_files)
                continue

            try:
                file_bytes = os.path.getsize(pdf_path)
                page_count = len(reader.pages)
                bytes_per_page = file_bytes / max(1, page_count)
            except Exception:
                bytes_per_page = 200_000

            for page in reader.pages:
                total_pages += 1
                self.progress_pages.emit(total_pages, max(1, total_pages_est))

                pending_pages.append(page)
                pending_approx += bytes_per_page

                if not self.no_limit and pending_approx > max_bytes * self.CHECK_THRESHOLD:
                    real = real_size_of(pending_pages)
                    if real > max_bytes:
                        if len(pending_pages) > 1:
                            save_batch(pending_pages[:-1])
                            last = pending_pages[-1]
                            pending_pages = [last]
                            pending_approx = bytes_per_page
                        else:
                            self.log_msg.emit("  ⚠ Página supera el límite, guardando de todas formas")
                            save_batch(pending_pages)
                            pending_pages = []
                            pending_approx = 0
                    else:
                        pending_approx = real

            self.progress_files.emit(i + 1, total_files)

        if pending_pages:
            save_batch(pending_pages)

        # Build informe
        try:
            from core.informe import build_informe, file_info
            originals = [file_info(f) for f in pdf_files]
            out_files = sorted([
                os.path.join(output_folder, f)
                for f in os.listdir(output_folder)
                if f.lower().endswith(".pdf")
            ])
            results = [file_info(p) for p in out_files]
            accion = (
                "unir en un solo archivo"
                if self.no_limit
                else "unir y partir en partes"
            )
            parametros = (
                "sin límite de tamaño"
                if self.no_limit
                else f"máximo {self.max_mb} MB por parte"
            )
            texto = build_informe(
                accion=accion,
                originals=originals,
                results=results,
                extra_lines=f"Total páginas procesadas: {total_pages}",
                objeto="documento PDF",
                parametros=parametros,
            )
            self.informe_ready.emit(texto)
        except Exception:
            pass

        self.finished.emit(total_files, total_pages, output_count, output_folder)


class PdfMergerSplitterPanel(QWidget):
    """Panel lateral para unir PDFs de una carpeta y partirlos por tamaño."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(380)
        self._folder  = ""
        self._out_dir = ""
        self._worker  = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        hdr = QLabel("🔗  Unir y cortar PDFs")
        hdr.setStyleSheet("font-size: 16px; font-weight: 800;")
        layout.addWidget(hdr)

        sub = QLabel(
            "Une todos los PDFs de una carpeta en un solo documento\n"
            "y lo parte en archivos del tamaño que necesitás."
        )
        sub.setStyleSheet("font-size: 11px; color: #64748b;")
        sub.setWordWrap(True)
        layout.addWidget(sub)

        try:
            import pypdf  # noqa: F401
        except ImportError:
            warn = QLabel(
                "⚠️  Esta herramienta necesita el paquete <b>pypdf</b>.\n"
                "Instalalo con:  <code>pip install pypdf</code>"
            )
            warn.setStyleSheet(
                "background: #fffbeb; border: 1px solid #f59e0b; "
                "border-radius: 6px; padding: 10px; color: #92400e;"
            )
            warn.setWordWrap(True)
            warn.setTextFormat(Qt.TextFormat.RichText)
            layout.addWidget(warn)
            layout.addStretch()
            return

        # ── Tarjeta: carpeta de entrada ──────────────────────────────
        card1 = QFrame()
        card1.setObjectName("card")
        c1 = QVBoxLayout(card1)
        c1.setContentsMargins(12, 10, 12, 10)
        c1.setSpacing(8)

        c1.addWidget(QLabel("Carpeta con los PDFs:"))
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

        c1.addWidget(QLabel("Carpeta de destino:"))
        row_out = QHBoxLayout()
        self.lbl_out = QLabel(etiqueta_destino(""))
        self.lbl_out.setStyleSheet("font-size: 11px; color: #64748b;")
        self.lbl_out.setWordWrap(True)
        row_out.addWidget(self.lbl_out, stretch=1)
        btn_out = QPushButton("Cambiar")
        btn_out.setObjectName("ghostBtn")
        btn_out.clicked.connect(self._pick_out_dir)
        row_out.addWidget(btn_out)
        c1.addLayout(row_out)
        layout.addWidget(card1)

        # ── Tarjeta: tamaño máximo ───────────────────────────────────
        card2 = QFrame()
        card2.setObjectName("card")
        c2 = QVBoxLayout(card2)
        c2.setContentsMargins(12, 10, 12, 10)
        c2.setSpacing(8)

        self.chk_no_limit = QCheckBox("Sin límite — unir todo en un solo archivo")
        self.chk_no_limit.setToolTip(
            "Une todos los PDFs en un único documento sin partirlo por tamaño."
        )
        self.chk_no_limit.toggled.connect(self._on_no_limit_toggled)
        c2.addWidget(self.chk_no_limit)

        self.lbl_size = QLabel("Tamaño máximo de cada parte:")
        c2.addWidget(self.lbl_size)

        size_row = QHBoxLayout()
        self.spin_size = QDoubleSpinBox()
        self.spin_size.setRange(1, 100)
        self.spin_size.setValue(9.5)
        self.spin_size.setDecimals(1)
        self.spin_size.setSuffix(" MB")
        size_row.addWidget(self.spin_size)
        size_row.addStretch()
        c2.addLayout(size_row)

        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel("Presets:"))
        self._preset_btns = []
        for mb, tip in [(5.0, "Email estándar"), (10.0, "Email extendido"), (15.0, "WhatsApp"), (20.0, "Uso general")]:
            btn = QPushButton(f"{mb:g} MB")
            btn.setObjectName("presetBtn")
            btn.setMinimumWidth(58)
            btn.setToolTip(tip)
            btn.clicked.connect(lambda checked, v=mb: self.spin_size.setValue(v))
            preset_row.addWidget(btn)
            self._preset_btns.append(btn)
        c2.addLayout(preset_row)
        layout.addWidget(card2)

        # ── Progreso ─────────────────────────────────────────────────
        self.pbar_files = QProgressBar()
        self.pbar_files.setFormat("Archivos: %v / %m")
        self.pbar_files.setVisible(False)
        layout.addWidget(self.pbar_files)

        self.pbar_pages = QProgressBar()
        self.pbar_pages.setFormat("Páginas: %v / %m")
        self.pbar_pages.setVisible(False)
        layout.addWidget(self.pbar_pages)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setStyleSheet(
            "background: #111111; color: #00ff41; "
            "font-family: Consolas, monospace; font-size: 11px; "
            "border-radius: 6px;"
        )
        self.log.setMinimumHeight(120)
        self.log.setMaximumHeight(200)
        self.log.setVisible(False)
        layout.addWidget(self.log)

        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("font-size: 11px; color: #475569;")
        self.lbl_status.setWordWrap(True)
        layout.addWidget(self.lbl_status)

        self.btn_run = QPushButton("🔗  Unir y cortar PDFs")
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

    # ── Handlers ──────────────────────────────────────────────────────

    def _on_no_limit_toggled(self, checked: bool):
        self.spin_size.setEnabled(not checked)
        self.lbl_size.setEnabled(not checked)
        for btn in self._preset_btns:
            btn.setEnabled(not checked)

    def _pick_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta con PDFs")
        if not folder:
            return
        self._folder = folder
        self.lbl_out.setText(carpeta_destino(folder, self._out_dir))
        self.lbl_folder.setText(os.path.basename(folder) or folder)
        self.lbl_folder.setToolTip(folder)

        pdfs = [f for f in os.listdir(folder) if f.lower().endswith(".pdf")]
        if pdfs:
            self.lbl_folder_info.setText(f"{len(pdfs)} archivo{'s' if len(pdfs) != 1 else ''} PDF encontrado{'s' if len(pdfs) != 1 else ''}")
            self.btn_run.setEnabled(True)
        else:
            self.lbl_folder_info.setText("⚠  No hay archivos PDF en esta carpeta.")
            self.btn_run.setEnabled(False)

    def _limpiar(self):
        if self._worker and self._worker.isRunning():
            return
        self._folder = ""
        self._out_dir = ""
        self._last_out = ""
        self.lbl_folder.setText("Ninguna carpeta seleccionada")
        self.lbl_folder.setToolTip("")
        self.lbl_folder_info.setText("")
        self.lbl_out.setText(etiqueta_destino(""))
        self.btn_run.setEnabled(False)
        self.log.clear()
        self.log.setVisible(False)
        self.lbl_status.setText("")
        self.btn_open.setVisible(False)
        self.informe_section.setVisible(False)

    def _pick_out_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Carpeta de destino")
        if d:
            self._out_dir = d
            self.lbl_out.setText(d)

    def _start(self):
        if not self._folder:
            return
        out_dir = carpeta_destino(self._folder, self._out_dir)
        self._last_out = out_dir

        self.btn_run.setEnabled(False)
        self.btn_open.setVisible(False)
        self.informe_section.setVisible(False)
        self.log.clear()
        self.log.setVisible(True)
        self.pbar_files.setVisible(True)
        self.pbar_pages.setVisible(True)
        self.pbar_files.setValue(0)
        self.pbar_pages.setValue(0)
        self.lbl_status.setText("Procesando…")

        self._worker = _MergerWorker(
            self._folder, self.spin_size.value(),
            no_limit=self.chk_no_limit.isChecked(),
            out_dir=self._out_dir,
        )
        self._worker.log_msg.connect(self._append_log)
        self._worker.progress_files.connect(
            lambda cur, tot: (self.pbar_files.setMaximum(tot), self.pbar_files.setValue(cur))
        )
        self._worker.progress_pages.connect(
            lambda cur, tot: (self.pbar_pages.setMaximum(tot), self.pbar_pages.setValue(cur))
        )
        self._worker.finished.connect(self._on_done)
        self._worker.informe_ready.connect(
            lambda txt: self.informe_section.set_informe(txt, out_dir)
        )
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _append_log(self, text: str):
        self.log.append(text)
        self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())

    def _on_done(self, files_in: int, pages: int, files_out: int, out_folder: str):
        self._out_dir = out_folder
        self.pbar_files.setVisible(False)
        self.pbar_pages.setVisible(False)
        self.btn_run.setEnabled(True)
        self.lbl_status.setText(
            f"✅  {files_in} PDF{'s' if files_in != 1 else ''} unidos  |  "
            f"{pages} página{'s' if pages != 1 else ''}  |  "
            f"{files_out} archivo{'s' if files_out != 1 else ''} generado{'s' if files_out != 1 else ''}"
        )
        self.btn_open.setVisible(True)

    def _on_error(self, msg: str):
        self.pbar_files.setVisible(False)
        self.pbar_pages.setVisible(False)
        self.btn_run.setEnabled(True)
        self.lbl_status.setText(f"❌  {msg}")

    def _open_output(self):
        folder = self._out_dir
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
