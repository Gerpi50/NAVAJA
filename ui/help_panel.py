"""
ui/help_panel.py — Panel de Ayuda con búsqueda integrada (Ctrl+F).

Muestra el manual (HTML) en un QTextBrowser y le agrega una barra de búsqueda
con resaltado y navegación entre coincidencias (siguiente/anterior), además de
un botón para abrir el manual en el navegador (donde Ctrl+F funciona nativo).
"""
import os
import tempfile

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QShortcut, QKeySequence, QTextDocument, QTextCursor, QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QLabel, QTextBrowser,
)


class HelpPanel(QWidget):
    """Manual integrado con buscador estilo Ctrl+F."""

    def __init__(self, parent=None):
        super().__init__(parent)
        from ui.manual import MANUAL_HTML
        self._html = MANUAL_HTML

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Barra de búsqueda ────────────────────────────────────────────
        bar = QWidget()
        bar.setObjectName("helpSearchBar")
        bar.setStyleSheet(
            "#helpSearchBar { background:#f8fafc; border-bottom:1px solid #e2e8f0; }"
        )
        hb = QHBoxLayout(bar)
        hb.setContentsMargins(12, 8, 12, 8)
        hb.setSpacing(8)

        self.search = QLineEdit()
        self.search.setPlaceholderText("🔍  Buscar en el manual…  (Ctrl+F)")
        self.search.setClearButtonEnabled(True)
        self.search.returnPressed.connect(self._find_next)
        self.search.textChanged.connect(self._on_text_changed)
        hb.addWidget(self.search, 1)

        self.btn_prev = QPushButton("◀ Anterior")
        self.btn_next = QPushButton("Siguiente ▶")
        self.btn_prev.clicked.connect(self._find_prev)
        self.btn_next.clicked.connect(self._find_next)
        hb.addWidget(self.btn_prev)
        hb.addWidget(self.btn_next)

        self.status = QLabel("")
        self.status.setStyleSheet("color:#64748b;")
        hb.addWidget(self.status)

        hb.addStretch(0)

        self.btn_browser = QPushButton("🌐 Abrir en navegador")
        self.btn_browser.setToolTip(
            "Abre el manual en tu navegador, donde Ctrl+F funciona de forma nativa."
        )
        self.btn_browser.clicked.connect(self._open_in_browser)
        hb.addWidget(self.btn_browser)

        root.addWidget(bar)

        # ── Visor del manual ─────────────────────────────────────────────
        self.browser = QTextBrowser()
        self.browser.setHtml(self._html)
        self.browser.setOpenExternalLinks(True)
        root.addWidget(self.browser, 1)

        # ── Atajos de teclado ────────────────────────────────────────────
        QShortcut(QKeySequence.StandardKey.Find, self,
                  activated=self._focus_search)            # Ctrl+F
        QShortcut(QKeySequence.StandardKey.FindNext, self,
                  activated=self._find_next)               # F3
        QShortcut(QKeySequence.StandardKey.FindPrevious, self,
                  activated=self._find_prev)               # Shift+F3
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self.search,
                  activated=self._clear_search)

    # ----------------------------------------------------------------------
    def _focus_search(self):
        self.search.setFocus()
        self.search.selectAll()

    def _clear_search(self):
        self.search.clear()
        self.browser.setFocus()

    def _on_text_changed(self, _text):
        # Al cambiar el texto, reposicionar el cursor al inicio y buscar.
        cursor = self.browser.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        self.browser.setTextCursor(cursor)
        self._find(forward=True, from_start=True)

    # ----------------------------------------------------------------------
    def _find_next(self):
        self._find(forward=True)

    def _find_prev(self):
        self._find(forward=False)

    def _find(self, forward: bool = True, from_start: bool = False):
        text = self.search.text().strip()
        if not text:
            self.status.setText("")
            return

        flags = QTextDocument.FindFlag(0)
        if not forward:
            flags |= QTextDocument.FindFlag.FindBackward

        found = self.browser.find(text, flags)
        if not found:
            # Reiniciar desde el extremo correspondiente y reintentar (búsqueda circular)
            cursor = self.browser.textCursor()
            cursor.movePosition(
                QTextCursor.MoveOperation.Start if forward
                else QTextCursor.MoveOperation.End
            )
            self.browser.setTextCursor(cursor)
            found = self.browser.find(text, flags)

        if found:
            self.status.setText("✓ encontrado")
            self.status.setStyleSheet("color:#16a34a;")
        else:
            self.status.setText("✗ sin coincidencias")
            self.status.setStyleSheet("color:#dc2626;")

    # ----------------------------------------------------------------------
    def _open_in_browser(self):
        """Vuelca el manual a un .html temporal y lo abre en el navegador."""
        try:
            import webbrowser
            tmp_dir = tempfile.gettempdir()
            path = os.path.join(tmp_dir, "manual_universal_converter.html")
            with open(path, "w", encoding="utf-8") as f:
                f.write(self._html)
            webbrowser.open(f"file:///{path.replace(os.sep, '/')}")
        except Exception as e:
            self.status.setText(f"No se pudo abrir: {e}")
            self.status.setStyleSheet("color:#dc2626;")
