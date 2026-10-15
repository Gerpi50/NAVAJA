"""
ui/informe_widget.py — Widget reutilizable para mostrar el informe técnico en todos los paneles.
"""
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QPlainTextEdit, QFileDialog, QApplication,
)
from PyQt6.QtCore import QTimer
import os


class InformeSection(QFrame):
    """
    Sección colapsada/expandible que muestra el informe técnico
    listo para copiar o guardar. Insertar en cualquier panel después del resultado.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setVisible(False)
        self._texto   = ""
        self._out_dir = ""
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        # Header row
        hdr = QHBoxLayout()
        lbl = QLabel("📋  Informe técnico generado")
        lbl.setStyleSheet("font-size: 12px; font-weight: 700;")
        hdr.addWidget(lbl, stretch=1)

        self.btn_copy = QPushButton("📋 Copiar")
        self.btn_copy.setObjectName("ghostBtn")
        self.btn_copy.setFixedWidth(82)
        self.btn_copy.setToolTip("Copiar el informe al portapapeles")
        self.btn_copy.clicked.connect(self._copy)
        hdr.addWidget(self.btn_copy)

        self.btn_save = QPushButton("💾 Guardar")
        self.btn_save.setObjectName("ghostBtn")
        self.btn_save.setFixedWidth(82)
        self.btn_save.setToolTip("Guardar el informe como archivo .txt")
        self.btn_save.clicked.connect(self._save)
        hdr.addWidget(self.btn_save)

        layout.addLayout(hdr)

        # Text area
        self.text_area = QPlainTextEdit()
        self.text_area.setReadOnly(True)
        self.text_area.setMinimumHeight(190)
        self.text_area.setMaximumHeight(300)
        layout.addWidget(self.text_area)

        # Status
        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("font-size: 10px; color: #16a34a;")
        layout.addWidget(self.lbl_status)

    def set_informe(self, texto: str, out_dir: str = ""):
        """Muestra el informe. Llamar desde el panel cuando el procesamiento termina."""
        self._texto   = texto
        self._out_dir = out_dir
        self.text_area.setPlainText(texto)
        self.lbl_status.setText("")
        self.setVisible(True)

    def _copy(self):
        if not self._texto:
            return
        QApplication.clipboard().setText(self._texto)
        self.lbl_status.setText("✅  Copiado al portapapeles.")
        QTimer.singleShot(2500, lambda: self.lbl_status.setText(""))

    def _save(self):
        if not self._texto:
            return
        from datetime import datetime
        default = os.path.join(
            self._out_dir or "",
            f"Informe_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
        )
        path, _ = QFileDialog.getSaveFileName(
            self, "Guardar informe", default, "Texto (*.txt)"
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self._texto)
            self.lbl_status.setText(f"✅  Guardado: {os.path.basename(path)}")
            QTimer.singleShot(3000, lambda: self.lbl_status.setText(""))
