"""
ui/pdf_excel_panel.py — «Pasar a Excel»: la tabla de un PDF, a una planilla.

Es el preparador visual de tablas (PDF a Excel), metido dentro del módulo PDF
como una solapa más. Su código está en el paquete `pdf_excel/` y acá sólo se
lo acomoda dentro de la solapa:

  · se arma recién la primera vez que se abre la solapa, porque trae un visor,
    cinco grupos y nueve cortes y no hace falta cargarlos si no se usa;
  · conserva su propia apariencia (su hoja de estilos se aplica sólo a él);
  · avisa al módulo PDF cuando generó la planilla, para que arme el informe
    técnico con los hashes, y cuando se tocó «Limpiar».
"""
import importlib.util
import os

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt, QTimer, pyqtSignal


def faltantes() -> list:
    """Paquetes que el preparador necesita y esta instalación no tiene."""
    faltan = []
    for modulo in ("pdfplumber", "openpyxl"):
        try:
            if importlib.util.find_spec(modulo) is None:
                faltan.append(modulo)
        except Exception:
            faltan.append(modulo)
    return faltan


class PdfExcelPanel(QWidget):
    """Solapa que aloja el preparador de PDF a Excel."""

    # PDF de origen y archivos generados (la planilla y, si se pidió, el PDF)
    generado = pyqtSignal(str, list)
    empezo = pyqtSignal()       # se tocó «Preparar → Excel / CSV»
    limpiado = pyqtSignal()     # se tocó «Limpiar»

    def __init__(self, parent=None):
        super().__init__(parent)
        self.preparador = None
        self._armando = False
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.setSpacing(0)

        self._espera = QLabel("Abriendo el conversor de PDF a Excel…")
        self._espera.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._espera.setWordWrap(True)
        self._espera.setStyleSheet(
            "color: #64748b; font-size: 13px; padding: 40px;")
        self._lay.addWidget(self._espera)

    def showEvent(self, event):
        super().showEvent(event)
        if self.preparador is None and not self._armando:
            self._armando = True
            # Un instante después, así primero se ve el cartel de espera.
            QTimer.singleShot(60, self._armar)

    def _armar(self):
        faltan = faltantes()
        if faltan:
            self._espera.setText(
                "⚠️  En esta instalación falta lo necesario para leer las "
                f"tablas de un PDF ({', '.join(faltan)}).\n\n"
                "Abrí el programa con «Abrir_App (codigo fuente).bat», que "
                "usa el Python que sí lo tiene.")
            self._armando = False
            return
        try:
            from pdf_excel.preparador import PreparadorWidget
            preparador = PreparadorWidget(dark=False)
        except Exception as e:
            self._espera.setText(
                f"No se pudo abrir el conversor de PDF a Excel.\n\n{e}")
            self._armando = False
            return

        preparador.excel_generado.connect(self._on_generado)
        preparador.limpiado.connect(self.limpiado)
        preparador.btn_conv.clicked.connect(self.empezo)

        self._espera.setVisible(False)
        self._lay.addWidget(preparador, stretch=1)
        self.preparador = preparador
        self._armando = False

    def _on_generado(self, salida: str):
        origen = self.preparador._pdf_path
        archivos = [salida]
        # Con «También PDF» queda además la tabla en un PDF, al lado.
        if (self.preparador.ck_pdf.isChecked()
                and not salida.lower().endswith(".csv")):
            from pdf_excel.preparador import pdf_de_la_tabla
            en_pdf = pdf_de_la_tabla(salida, origen)
            if os.path.isfile(en_pdf):
                archivos.append(en_pdf)
        self.generado.emit(origen, archivos)

    def ocupado(self) -> bool:
        """True mientras se está generando la planilla."""
        conv = getattr(self.preparador, "_converter", None)
        return bool(conv is not None and conv.isRunning())
