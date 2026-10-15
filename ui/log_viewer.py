"""
ui/log_viewer.py — Panel lateral de logs y constancias.
"""
import os
import platform
import subprocess
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QTextEdit, QTabWidget,
    QApplication, QFileDialog, QSizePolicy, QMessageBox,
    QAbstractItemView,
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont


class LogViewerPanel(QWidget):
    """Panel lateral con log técnico, constancias e historial."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(360)
        self._entries: list = []  # dicts de log_entry
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Encabezado
        hdr = QWidget()
        hdr.setStyleSheet("background: #1e293b; padding: 10px;")
        hdr_layout = QHBoxLayout(hdr)
        hdr_layout.setContentsMargins(12, 8, 12, 8)
        title = QLabel("📋  Log y constancias")
        title.setStyleSheet("color: white; font-weight: 700; font-size: 13px;")
        hdr_layout.addWidget(title)
        hdr_layout.addStretch()
        layout.addWidget(hdr)

        tabs = QTabWidget()
        layout.addWidget(tabs, stretch=1)

        # ─── Tab: Log técnico ───────────────────────────────────────
        tab_log = QWidget()
        tl = QVBoxLayout(tab_log)
        tl.setContentsMargins(6, 6, 6, 6)
        tl.setSpacing(6)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setPlaceholderText("El log técnico aparecerá aquí durante la conversión...")
        tl.addWidget(self.log_text, stretch=1)

        btn_row = QHBoxLayout()
        btn_clear = QPushButton("🗑 Limpiar log")
        btn_clear.setObjectName("ghostBtn")
        btn_clear.clicked.connect(self.log_text.clear)
        btn_export = QPushButton("💾 Exportar .txt")
        btn_export.setObjectName("ghostBtn")
        btn_export.clicked.connect(self._export_log)
        btn_row.addWidget(btn_clear)
        btn_row.addWidget(btn_export)
        tl.addLayout(btn_row)
        tabs.addTab(tab_log, "📟  Log técnico")

        # ─── Tab: Constancias ───────────────────────────────────────
        tab_cert = QWidget()
        tc = QVBoxLayout(tab_cert)
        tc.setContentsMargins(6, 6, 6, 6)
        tc.setSpacing(6)

        tc.addWidget(QLabel("Seleccioná una conversión:"))
        self.entry_list = QListWidget()
        self.entry_list.setMaximumHeight(140)
        self.entry_list.currentRowChanged.connect(self._on_entry_selected)
        tc.addWidget(self.entry_list)

        self.cert_text = QTextEdit()
        self.cert_text.setReadOnly(True)
        self.cert_text.setPlaceholderText("La constancia aparecerá aquí...")
        self.cert_text.setStyleSheet(
            "background: #f8fafc; color: #1e293b; border: 1px solid #e2e8f0;"
            "border-radius: 6px; font-family: monospace; font-size: 11px;"
        )
        tc.addWidget(self.cert_text, stretch=1)

        btn_row2 = QHBoxLayout()
        btn_copy = QPushButton("📋 Copiar constancia")
        btn_copy.setObjectName("ghostBtn")
        btn_copy.clicked.connect(self._copy_certificate)
        btn_copy_all = QPushButton("📋 Copiar todas")
        btn_copy_all.setObjectName("ghostBtn")
        btn_copy_all.clicked.connect(self._copy_all_certificates)
        btn_row2.addWidget(btn_copy)
        btn_row2.addWidget(btn_copy_all)
        tc.addLayout(btn_row2)
        tabs.addTab(tab_cert, "🛡️  Constancias")

        # ─── Tab: Historial ─────────────────────────────────────────
        tab_hist = QWidget()
        th = QVBoxLayout(tab_hist)
        th.setContentsMargins(6, 6, 6, 6)
        th.setSpacing(6)

        self.hist_list = QListWidget()
        self.hist_list.setAlternatingRowColors(True)
        # Selección múltiple: Ctrl+clic / Shift+clic para elegir varias sesiones
        self.hist_list.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        th.addWidget(self.hist_list, stretch=1)

        btn_row3 = QHBoxLayout()
        btn_open_session = QPushButton("📂 Abrir sesión")
        btn_open_session.setObjectName("ghostBtn")
        btn_open_session.clicked.connect(self._open_session)
        btn_open_folder = QPushButton("📁 Carpeta de logs")
        btn_open_folder.setObjectName("ghostBtn")
        btn_open_folder.clicked.connect(self._open_logs_folder)
        btn_row3.addWidget(btn_open_session)
        btn_row3.addWidget(btn_open_folder)
        th.addLayout(btn_row3)

        btn_row4 = QHBoxLayout()
        btn_del_sel = QPushButton("🗑 Eliminar seleccionados")
        btn_del_sel.setObjectName("ghostBtn")
        btn_del_sel.clicked.connect(self._delete_selected_sessions)
        btn_del_all = QPushButton("🗑 Eliminar todos")
        btn_del_all.setObjectName("ghostBtn")
        btn_del_all.clicked.connect(self._delete_all_sessions)
        btn_row4.addWidget(btn_del_sel)
        btn_row4.addWidget(btn_del_all)
        th.addLayout(btn_row4)
        tabs.addTab(tab_hist, "📁  Historial")

        self._load_history()

    # ── API pública ──────────────────────────────────────────────────

    def append_log(self, msg: str):
        """Agrega un mensaje al log técnico (con auto-scroll)."""
        self.log_text.append(msg)
        sb = self.log_text.verticalScrollBar()
        sb.setValue(sb.maximum())

    def add_entry(self, entry: dict):
        """Agrega una entrada de conversión a la lista de constancias."""
        self._entries.append(entry)
        status = "✅" if entry.get("status") == "ok" else "❌"
        name = entry.get("input", {}).get("filename", "?")
        dur = entry.get("duration_seconds", 0)
        label = f"{status}  {name}  ({dur:.1f}s)"
        self.entry_list.addItem(label)

    def clear_entries(self):
        """Limpia la lista de constancias (nueva sesión)."""
        self._entries.clear()
        self.entry_list.clear()
        self.cert_text.clear()

    # ── Handlers internos ────────────────────────────────────────────

    def _on_entry_selected(self, row: int):
        if 0 <= row < len(self._entries):
            cert = self._entries[row].get("certificate_text", "")
            self.cert_text.setPlainText(cert)

    def _copy_certificate(self):
        row = self.entry_list.currentRow()
        if 0 <= row < len(self._entries):
            cert = self._entries[row].get("certificate_text", "")
            QApplication.clipboard().setText(cert)

    def _copy_all_certificates(self):
        all_certs = "\n".join(
            e.get("certificate_text", "") for e in self._entries
        )
        QApplication.clipboard().setText(all_certs)

    def _export_log(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar log", "log_conversor.txt",
            "Archivo de texto (*.txt)"
        )
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(self.log_text.toPlainText())
            except Exception:
                pass

    def _load_history(self):
        self.hist_list.clear()
        try:
            from core.logger import logger
            sessions = logger.list_sessions()
            for fp in sessions[:50]:
                data = logger.load_session(fp)
                if data:
                    started = data.get("started_at", "?")
                    total   = data.get("total_files", 0)
                    ok      = data.get("successful", 0)
                    fail    = data.get("failed", 0)
                    name    = os.path.basename(fp)
                    label   = f"{started}  |  {total} archivos  ✅{ok} ❌{fail}"
                    item = QListWidgetItem(label)
                    item.setData(Qt.ItemDataRole.UserRole, fp)
                    self.hist_list.addItem(item)
        except Exception:
            pass

    def _open_session(self):
        item = self.hist_list.currentItem()
        if item:
            fp = item.data(Qt.ItemDataRole.UserRole)
            if fp and os.path.exists(fp):
                try:
                    from core.logger import logger
                    data = logger.load_session(fp)
                    if data:
                        entries = data.get("entries", [])
                        self._entries = entries
                        self.entry_list.clear()
                        for e in entries:
                            status = "✅" if e.get("status") == "ok" else "❌"
                            name = e.get("input", {}).get("filename", "?")
                            label = f"{status}  {name}"
                            self.entry_list.addItem(label)
                except Exception:
                    pass

    def _delete_selected_sessions(self):
        """Elimina las sesiones seleccionadas (Ctrl/Shift+clic para varias)."""
        items = self.hist_list.selectedItems()
        if not items:
            QMessageBox.information(
                self, "Eliminar sesiones",
                "Primero seleccioná una o más sesiones de la lista.\n"
                "(Ctrl+clic para elegir varias.)"
            )
            return
        n = len(items)
        resp = QMessageBox.question(
            self, "Eliminar sesiones",
            f"¿Eliminar {n} sesión{'es' if n != 1 else ''} del historial?\n"
            "Los archivos convertidos NO se tocan; solo se borra el registro.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if resp != QMessageBox.StandardButton.Yes:
            return
        errors = 0
        for item in items:
            fp = item.data(Qt.ItemDataRole.UserRole)
            try:
                if fp and os.path.exists(fp):
                    os.remove(fp)
            except Exception:
                errors += 1
        self._load_history()
        if errors:
            QMessageBox.warning(
                self, "Eliminar sesiones",
                f"No se pudieron eliminar {errors} archivo(s) "
                "(puede que estén en uso)."
            )

    def _delete_all_sessions(self):
        """Elimina todo el historial de sesiones, con confirmación."""
        total = self.hist_list.count()
        if total == 0:
            QMessageBox.information(
                self, "Eliminar historial", "No hay sesiones para eliminar."
            )
            return
        resp = QMessageBox.question(
            self, "Eliminar TODO el historial",
            f"¿Eliminar las {total} sesiones del historial?\n\n"
            "Esta acción no se puede deshacer.\n"
            "Los archivos convertidos NO se tocan; solo se borran los registros.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if resp != QMessageBox.StandardButton.Yes:
            return
        errors = 0
        for i in range(total):
            fp = self.hist_list.item(i).data(Qt.ItemDataRole.UserRole)
            try:
                if fp and os.path.exists(fp):
                    os.remove(fp)
            except Exception:
                errors += 1
        self._load_history()
        if errors:
            QMessageBox.warning(
                self, "Eliminar historial",
                f"No se pudieron eliminar {errors} archivo(s) "
                "(puede que estén en uso)."
            )

    def _open_logs_folder(self):
        try:
            from core.paths import LOGS_DIR
            if platform.system() == "Windows":
                os.startfile(LOGS_DIR)
            elif platform.system() == "Darwin":
                subprocess.run(["open", LOGS_DIR])
            else:
                subprocess.run(["xdg-open", LOGS_DIR])
        except Exception:
            pass
