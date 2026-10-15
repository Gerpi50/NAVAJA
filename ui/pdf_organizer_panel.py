"""
ui/pdf_organizer_panel.py — Editor visual de PDF (estilo iLovePDF, 100% offline).

Pestaña "Organizar páginas": miniaturas arrastrables para reordenar,
eliminar y rotar páginas, y guardar el resultado como un PDF nuevo.

Pestaña "Herramientas": comprimir, proteger con contraseña, quitar
contraseña y reparar PDF dañado.
"""
import os

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QFileDialog, QMessageBox,
    QTabWidget, QProgressBar, QLineEdit, QRadioButton,
    QButtonGroup, QGroupBox, QAbstractItemView, QFrame, QSpinBox,
    QComboBox, QCheckBox, QScrollArea, QDialog, QDoubleSpinBox, QMenu,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import (
    QPixmap, QIcon, QImage, QTransform, QKeySequence, QShortcut,
    QColor, QBrush,
)


# ═════════════════════════════════════════════════════════════════════════════
# Workers
# ═════════════════════════════════════════════════════════════════════════════

class _ThumbWorker(QThread):
    """Renderiza miniaturas en segundo plano (una señal por página)."""
    thumb_ready = pyqtSignal(int, bytes)       # índice, PNG bytes
    finished_ok = pyqtSignal(int)              # total de páginas
    error       = pyqtSignal(str)

    def __init__(self, pdf_path: str):
        super().__init__()
        self.pdf_path = pdf_path
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            from motors.motor_pdf_tools import render_thumbnails
            total = 0
            for idx, _w, _h, png in render_thumbnails(self.pdf_path):
                if self._cancel:
                    return
                self.thumb_ready.emit(idx, png)
                total += 1
            self.finished_ok.emit(total)
        except Exception as e:
            self.error.emit(str(e))


class _DupWorker(QThread):
    """Busca páginas duplicadas (misma imagen, texto o aspecto) en segundo plano."""
    log_msg     = pyqtSignal(str)
    finished_ok = pyqtSignal(list)             # [(pág_a, pág_b, similitud, motivo), ...]
    error       = pyqtSignal(str)

    def __init__(self, pdf_path: str):
        super().__init__()
        self.pdf_path = pdf_path

    def run(self):
        try:
            from motors.motor_pdf_tools import find_duplicate_pages
            pairs = find_duplicate_pages(self.pdf_path,
                                         progress_cb=self.log_msg.emit)
            self.finished_ok.emit(pairs)
        except Exception as e:
            self.error.emit(str(e))


class _DupFilesWorker(QThread):
    """Busca archivos duplicados (mismo texto/OCR) entre varios PDF completos."""
    log_msg     = pyqtSignal(str)
    finished_ok = pyqtSignal(list)             # [(idx_a, idx_b, similitud), ...]
    error       = pyqtSignal(str)

    def __init__(self, paths: list):
        super().__init__()
        self.paths = paths

    def run(self):
        try:
            from motors.motor_pdf_tools import find_duplicate_files
            pairs = find_duplicate_files(self.paths, progress_cb=self.log_msg.emit)
            self.finished_ok.emit(pairs)
        except Exception as e:
            self.error.emit(str(e))


class _MergeRunWorker(QThread):
    """Normaliza (opcional, y opcionalmente solo un rango) cada PDF y
    después los une en uno solo."""
    log_msg     = pyqtSignal(str)
    progress    = pyqtSignal(int, int)   # (paso actual, total de pasos)
    finished_ok = pyqtSignal(str)
    error       = pyqtSignal(str)

    def __init__(self, paths: list, dst: str, normalize_indices, lang: str):
        """`normalize_indices`: None = no normalizar nada; un set de índices
        (base 0, sobre `paths`) = normalizar solo esos archivos antes de unir."""
        super().__init__()
        self.paths = paths
        self.dst = dst
        self.normalize_indices = normalize_indices
        self.lang = lang

    def run(self):
        import shutil
        import tempfile
        from motors.motor_pdf_tools import merge_files
        tmp_dir = None
        indices = self.normalize_indices or set()
        # Pasos totales: uno por archivo a normalizar + uno final por unir.
        total_steps = len(indices) + 1
        step = 0
        self.progress.emit(0, total_steps)
        try:
            paths = list(self.paths)
            if indices:
                from motors.motor_ocr import normalize_pdf_pages
                tmp_dir = tempfile.mkdtemp(prefix="normalizado_")
                ordered = sorted(indices)
                for n, i in enumerate(ordered, start=1):
                    path = paths[i]
                    self.log_msg.emit(
                        f"📐 Normalizando archivo #{i + 1} ({n}/{len(ordered)}): "
                        f"{os.path.basename(path)}...")
                    dst_tmp = os.path.join(
                        tmp_dir, f"{i:03d}_{os.path.basename(path)}")

                    # Prefijo con el nº de archivo de la lista: los mensajes
                    # internos de normalize_pdf_pages dicen "página 1/1" (una
                    # sola página, la de este archivo) y sin el prefijo se
                    # puede confundir con "archivo 1/1" de toda la lista.
                    def _cb(msg, _file_num=i + 1):
                        self.log_msg.emit(f"[Archivo #{_file_num}] {msg}")

                    normalize_pdf_pages(path, dst_tmp, self.lang,
                                       progress_cb=_cb)
                    paths[i] = dst_tmp
                    step += 1
                    self.progress.emit(step, total_steps)

            result = merge_files(paths, self.dst, progress_cb=self.log_msg.emit)
            step += 1
            self.progress.emit(step, total_steps)
            msg = (f"Guardado: {os.path.basename(self.dst)} — "
                  f"{result['pages']} página(s) unidas")
            if indices:
                total = len(paths)
                if len(indices) == total:
                    msg += " (hoja y letra normalizadas en todos)."
                else:
                    lo, hi = min(indices) + 1, max(indices) + 1
                    msg += f" (hoja y letra normalizadas del #{lo} al #{hi})."
            else:
                msg += "."
            self.finished_ok.emit(msg)
        except Exception as e:
            self.error.emit(str(e))
        finally:
            if tmp_dir:
                shutil.rmtree(tmp_dir, ignore_errors=True)


class _OpWorker(QThread):
    """Ejecuta una operación de motor_pdf_tools en segundo plano."""
    log_msg     = pyqtSignal(str)
    pct         = pyqtSignal(int)              # avance 0-100 (si el motor lo informa)
    finished_ok = pyqtSignal(str)              # mensaje de éxito
    result_obj  = pyqtSignal(object)           # resultado crudo (para el informe)
    error       = pyqtSignal(str)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs

    def _params(self) -> set:
        """Parámetros que acepta la función del motor.

        Se consulta la firma en vez de pasarle un kwarg de avance a ciegas,
        que en las funciones que no lo tienen sería un TypeError."""
        try:
            import inspect
            return set(inspect.signature(self._fn).parameters)
        except Exception:
            return set()

    def run(self):
        try:
            params = self._params()
            if "pct_cb" in params:
                self._kwargs["pct_cb"] = self.pct.emit
            elif "page_cb" in params:
                # OCR y compañía informan (página actual, total): se traduce
                # a porcentaje para que la barra avance dentro del archivo.
                self._kwargs["page_cb"] = lambda cur, tot: self.pct.emit(
                    int(cur * 100 / tot) if tot else 0)
            result = self._fn(*self._args, progress_cb=self.log_msg.emit,
                              **self._kwargs)
            self.result_obj.emit(result)
            self.finished_ok.emit(self._format_result(result))
        except Exception as e:
            self.error.emit(str(e))

    @staticmethod
    def _format_result(result) -> str:
        if isinstance(result, dict) and result.get("limite"):
            texto = (
                f"{len(result['archivos'])} archivo(s) listos en "
                f"{result['tandas']} tanda(s) de hasta "
                f"{result['max_mb']:g} MB, en la carpeta "
                f"«{os.path.basename(result['carpeta'])}»"
                f"  ({result['copiados']} sin cambios, "
                f"{result['partidos']} partido(s)).")
            if result.get("avisos"):
                texto += "\n⚠ " + result["avisos"][0]
                if len(result["avisos"]) > 1:
                    texto += f" (y {len(result['avisos']) - 1} caso(s) más)"
            return texto
        if isinstance(result, dict) and result.get("split"):
            partes = result["partes"]
            texto = (f"{partes} archivo(s) generado(s) con "
                     f"{result['paginas']} página(s) en total, en la carpeta "
                     f"«{os.path.basename(result['carpeta'])}».")
            if result.get("avisos"):
                texto += "\n⚠ " + result["avisos"][0]
                if len(result["avisos"]) > 1:
                    texto += f" (y {len(result['avisos']) - 1} caso(s) más)"
            return texto
        if isinstance(result, dict) and result.get("desdoblar"):
            simples = result["hojas"] - result["dobles"]
            texto = (f"{result['dobles']} hoja(s) doble(s) separada(s): "
                     f"quedaron {result['paginas']} página(s) A4")
            if simples:
                texto += f" ({simples} hoja(s) simple(s) pasada(s) a A4 sin cortar)"
            texto += "."
            if result.get("carpeta"):
                texto += (f" {len(result['archivos'])} archivo(s) en la carpeta "
                          f"«{os.path.basename(result['carpeta'])}».")
            if result.get("avisos"):
                texto += "\n⚠ " + result["avisos"][0]
                if len(result["avisos"]) > 1:
                    texto += f" (y {len(result['avisos']) - 1} caso(s) más)"
            return texto
        if isinstance(result, dict) and result.get("token_probe"):
            from motors.motor_pdf_tools import format_token_probe
            return format_token_probe(result)
        if isinstance(result, dict) and "before" in result:
            before = result["before"] / (1024 * 1024)
            after = result["after"] / (1024 * 1024)
            saved = (1 - result["after"] / max(result["before"], 1)) * 100
            return (f"Tamaño original: {before:.2f} MB → nuevo: {after:.2f} MB "
                    f"(ahorro {saved:.0f}%, {result['images']} imágenes recomprimidas)")
        if isinstance(result, dict) and "text_height_px" in result:
            if result["text_height_px"] is None:
                return (f"{result['pages']} página(s) llevadas a hoja A4 "
                        f"(no había páginas escaneadas para calibrar letra: "
                        f"el texto digital se dejó intacto).")
            return (f"{result['pages']} página(s) llevadas a hoja A4 con "
                    f"letra pareja en las páginas escaneadas (altura de "
                    f"referencia: {result['text_height_px']} px).")
        if isinstance(result, dict) and "pages" in result:
            return f"Total de páginas: {result['pages']}"
        if isinstance(result, int):
            return f"Páginas recuperadas: {result}"
        return "Operación completada."


# ═════════════════════════════════════════════════════════════════════════════
# Diálogo de revisión de duplicados (lado a lado)
# ═════════════════════════════════════════════════════════════════════════════

def _render_first_page(path: str, max_edge: int = 420):
    """PNG bytes de la primera página de un PDF, para vistas previas."""
    try:
        from motors.motor_pdf_tools import render_thumbnails
        for _idx, _w, _h, png in render_thumbnails(path, max_edge=max_edge):
            return png
    except Exception:
        pass
    return None


class _InformeWorker(QThread):
    """Arma el informe técnico en segundo plano.

    Hashear no es gratis: un PDF de cientos de MB tarda, y hacerlo en el hilo
    de la interfaz congelaría la ventana justo al terminar la operación.
    """
    listo = pyqtSignal(str)

    def __init__(self, frase: str, origenes, resultados):
        super().__init__()
        self._frase = frase
        self._origenes = [p for p in origenes if p and os.path.isfile(p)]
        self._resultados = [p for p in resultados if p and os.path.isfile(p)]

    def run(self):
        try:
            from core.informe import info_completa, build_informe_detallado
            # Una operación = un punto del informe, aunque entren varios
            # archivos: al unir, los orígenes van todos juntos con su hash y
            # el resultante al final. Nada de hashear "el proceso" paso a paso.
            operaciones = [{
                "frase": self._frase,
                "originales": [info_completa(p) for p in self._origenes],
                "resultados": [info_completa(p) for p in self._resultados],
            }]
            self.listo.emit(build_informe_detallado(operaciones))
        except Exception as e:
            self.listo.emit(f"No se pudo generar el informe: {e}")


def _cant_pdf(n: int) -> str:
    """"1 archivo PDF" / "5 archivos PDF", para que el informe concuerde."""
    return f"{n} archivo PDF" if n == 1 else f"{n} archivos PDF"


class _ZoomImageDialog(QDialog):
    """Ventana simple con la vista previa a mayor tamaño, con scroll."""

    def __init__(self, title: str, thumb: bytes, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(800, 900)
        lay = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        lbl = QLabel()
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if thumb:
            img = QImage.fromData(thumb, "PNG")
            lbl.setPixmap(QPixmap.fromImage(img))
        else:
            lbl.setText("(no se pudo generar la vista previa)")
        scroll.setWidget(lbl)
        lay.addWidget(scroll)
        btn_close = QPushButton("Cerrar")
        btn_close.clicked.connect(self.accept)
        lay.addWidget(btn_close)


class _DuplicatePairDialog(QDialog):
    """Muestra el contenido de dos archivos lado a lado (el nº a la
    izquierda, el nº b a la derecha) para elegir cuál eliminar."""

    THUMB_EDGE = 420
    ZOOM_EDGE = 1400

    def __init__(self, num_a: int, name_a: str, path_a: str,
                num_b: int, name_b: str, path_b: str,
                similarity: float, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Posible duplicado")
        self.choice = None   # "a", "b" o None (mantener ambos)

        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(
            f"Los archivos #{num_a} y #{num_b} parecen ser la misma hoja "
            f"({similarity * 100:.0f}% de coincidencia de texto). "
            f"Elegí cuál eliminar:"))

        row = QHBoxLayout()
        row.addLayout(self._build_side(num_a, name_a, path_a, "a"))
        row.addLayout(self._build_side(num_b, name_b, path_b, "b"))
        lay.addLayout(row)

        btn_keep = QPushButton("Mantener ambos (no es duplicado)")
        btn_keep.clicked.connect(self._keep_both)
        lay.addWidget(btn_keep)

    def _build_side(self, num: int, name: str, path: str, side: str) -> QVBoxLayout:
        col = QVBoxLayout()
        lbl_title = QLabel(f"#{num}  {name}")
        lbl_title.setWordWrap(True)
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        col.addWidget(lbl_title)

        thumb = _render_first_page(path, max_edge=self.THUMB_EDGE)
        lbl_img = QLabel()
        lbl_img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_img.setMinimumSize(self.THUMB_EDGE, self.THUMB_EDGE)
        if thumb:
            img = QImage.fromData(thumb, "PNG")
            lbl_img.setPixmap(QPixmap.fromImage(img))
        else:
            lbl_img.setText("(no se pudo generar la vista previa)")
        col.addWidget(lbl_img)

        btn_zoom = QPushButton("🔍 Ver más grande")
        btn_zoom.clicked.connect(lambda: self._zoom(num, name, path))
        col.addWidget(btn_zoom)

        btn = QPushButton(f"🗑 Eliminar #{num}")
        btn.clicked.connect(lambda: self._choose(side))
        col.addWidget(btn)
        return col

    def _zoom(self, num: int, name: str, path: str):
        big = _render_first_page(path, max_edge=self.ZOOM_EDGE)
        dlg = _ZoomImageDialog(f"#{num}  {name}", big, parent=self)
        dlg.exec()

    def _choose(self, side: str):
        self.choice = side
        self.accept()

    def _keep_both(self):
        self.choice = None
        self.accept()


# ═════════════════════════════════════════════════════════════════════════════
# Panel principal
# ═════════════════════════════════════════════════════════════════════════════

class _LimitePrepInformeWorker(QThread):
    """Informe técnico de la preparación de PDF con límite de tamaño.

    Cuenta archivo por archivo qué se hizo con cada uno —si se copió tal cual
    o en cuántas partes se partió— y en qué tanda quedó cada resultado, con
    los hashes de antes y después. Listar entradas y salidas por separado no
    sirve de constancia: con 30 PDF no se sabe cuál salió de cuál.
    """
    listo = pyqtSignal(str)

    def __init__(self, detalle, max_mb, por_tanda, carpeta, total_tandas=0):
        super().__init__()
        self._detalle      = list(detalle or [])
        self._max_mb       = max_mb
        self._por_tanda    = por_tanda
        self._carpeta      = carpeta
        self._total_tandas = total_tandas

    def _ubicacion(self, ruta: str) -> str:
        """Nombre del archivo con su tanda, tal como quedó en la carpeta."""
        try:
            rel = os.path.relpath(ruta, self._carpeta)
        except Exception:
            rel = os.path.basename(ruta)
        return rel

    def run(self):
        try:
            from core.informe import (build_informe_detallado, info_completa,
                                      save_informe, fecha_formal,
                                      tamano_legible)

            operaciones = []
            for d in self._detalle:
                origen  = d["origen"]
                nombre  = os.path.basename(origen)
                mb      = d.get("size_mb", 0.0)
                salidas = d.get("resultados") or []
                tam = tamano_legible(mb)
                if d.get("accion") == "partido":
                    frase = (f"partir el archivo «{nombre}» ({tam}) en "
                             f"{len(salidas)} parte(s) de hasta "
                             f"{self._max_mb:g} MB, por superar el máximo "
                             f"elegido")
                else:
                    frase = (f"incorporar el archivo «{nombre}» ({tam}) "
                             f"sin modificarlo, por no superar el máximo de "
                             f"{self._max_mb:g} MB elegido")

                resultados = []
                for r in salidas:
                    info = info_completa(r)
                    info["filename"] = self._ubicacion(r)
                    resultados.append(info)

                operaciones.append({
                    "frase": frase,
                    "original": info_completa(origen),
                    "resultados": resultados,
                })

            total = sum(len(o["resultados"]) for o in operaciones)
            encabezado = (
                f"El día de la fecha ({fecha_formal()}) se "
                f"prepararon para su carga "
                f"{len(operaciones)} archivo(s), de los que resultaron {total} "
                f"archivo(s) de hasta {self._max_mb:g} MB, ordenados en "
                f"{self._total_tandas} tanda(s) de {self._por_tanda}. Se deja "
                f"constancia de los códigos de verificación (hash) de cada "
                f"archivo antes y después del proceso. Los originales no "
                f"fueron modificados.")

            texto = build_informe_detallado(operaciones, encabezado=encabezado)

            if self._carpeta:
                try:
                    ruta = save_informe(texto, self._carpeta,
                                        prefix="Informe_PDF_por_tamano")
                    texto += f"\n[Informe guardado en: {ruta}]\n"
                except Exception:
                    pass
            self.listo.emit(texto)
        except Exception as e:
            self.listo.emit(f"No se pudo generar el informe: {e}")


class PdfOrganizerPanel(QWidget):
    """Editor visual de PDF: organizar páginas + herramientas."""

    THUMB_EDGE = 160    # lado máximo de miniatura en pantalla

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pdf_path: str = ""
        self._thumb_worker = None
        self._op_worker = None
        self._dup_worker = None
        self._merge_dup_worker = None
        self._merge_worker = None
        self._setup_ui()

    # ──────────────────────────────────────────────────────────────────
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        header = QLabel("📄  PDF")
        header.setObjectName("panelHeader")
        layout.addWidget(header)

        # Solapas nombradas por lo que hacen (verbo), no por el objeto.
        # El orden sigue lo que más se usa.
        tabs = QTabWidget()
        tabs.addTab(self._wrap_scroll(self._build_merge_tab()),
                   "🔗  Unir archivos")
        tabs.addTab(self._wrap_scroll(self._build_split_tab()),
                   "✂️  Partir")
        tabs.addTab(self._wrap_scroll(self._build_double_tab()),
                   "📖  Hojas dobles")
        tabs.addTab(self._wrap_scroll(self._build_limite_tab()),
                   "📦  Ajustar tamaño")
        tabs.addTab(self._wrap_scroll(self._build_organizer_tab()),
                   "📑  Organizar páginas")
        tabs.addTab(self._wrap_scroll(self._build_sign_tab()),
                   "🖋  Firmar")
        tabs.addTab(self._wrap_scroll(self._build_ocr_tab()),
                   "🔍  Reconocer texto")
        # Sin scroll alrededor: trae su visor y su tabla, que se acomodan
        # solos al alto de la ventana.
        tabs.addTab(self._build_excel_tab(),
                   "📊  Pasar a Excel")
        tabs.addTab(self._wrap_scroll(self._build_tools_tab()),
                   "🛠  Herramientas")
        layout.addWidget(tabs, stretch=1)

        # Barra de avance común a todas las operaciones del módulo. Sin esto
        # no había forma de saber si una operación seguía trabajando o ya
        # había terminado: guardar un PDF grande en un pendrive puede tardar
        # varios minutos con la ventana aparentemente quieta.
        self.op_progress = QProgressBar()
        self.op_progress.setTextVisible(True)
        self.op_progress.setVisible(False)
        layout.addWidget(self.op_progress)

        # Informe técnico con hashes, compartido por todas las operaciones
        # del módulo (unir, partir, firmar, OCR). Aparece recién cuando hay
        # algo que informar.
        try:
            from ui.informe_widget import InformeSection
            self.informe_section = InformeSection()
            self.informe_section.setVisible(False)
            layout.addWidget(self.informe_section)
        except Exception:
            self.informe_section = None

    # ──────────────────────────────────────────────────────────────────
    # TAB: Pasar a Excel
    #
    # La tabla de un PDF (un resumen bancario, un listado) a una planilla.
    # Es el preparador visual de tablas: ver ui/pdf_excel_panel.
    # ──────────────────────────────────────────────────────────────────

    def _build_excel_tab(self) -> QWidget:
        from ui.pdf_excel_panel import PdfExcelPanel
        self.excel_panel = PdfExcelPanel()
        self.excel_panel.generado.connect(self._on_excel_generado)
        self.excel_panel.empezo.connect(self._esconder_informe)
        self.excel_panel.limpiado.connect(self._esconder_informe)
        return self.excel_panel

    def _esconder_informe(self):
        if getattr(self, "informe_section", None):
            self.informe_section.setVisible(False)

    def _on_excel_generado(self, origen: str, archivos: list):
        nombre = os.path.basename(origen)
        planilla = archivos[0] if archivos else ""
        formato = ("un archivo de texto separado por punto y coma (CSV)"
                   if planilla.lower().endswith(".csv")
                   else "una planilla de cálculo (XLSX)")
        frase = (f"extraer las tablas del archivo «{nombre}» y volcarlas en "
                 f"{formato}")
        if len(archivos) > 1:
            frase += ", generando además un PDF con la tabla resultante"
        self._generar_informe(frase, [origen], archivos)

    # ──────────────────────────────────────────────────────────────────
    # TAB: Partir un PDF
    #
    # Faltaba: hasta ahora sólo se podía partir como efecto secundario de
    # unir una carpeta. Acá se parte un PDF que ya tenés.
    # ──────────────────────────────────────────────────────────────────

    def _build_split_tab(self) -> QWidget:
        from motors.motor_pdf_tools import PDF_MAX_MB_DEFECTO
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(10)

        self._split_src = ""
        self._split_pages = 0

        # ── 1. Elegir el PDF ─────────────────────────────────────────
        grp1 = QGroupBox("1️⃣  Elegí el PDF que querés partir")
        g1 = QHBoxLayout(grp1)
        btn_pick = QPushButton("📄 Elegir PDF...")
        btn_pick.clicked.connect(self._pick_split_src)
        g1.addWidget(btn_pick)
        self.lbl_split_src = QLabel("(ninguno elegido)")
        self.lbl_split_src.setStyleSheet("color:#64748b;")
        self.lbl_split_src.setWordWrap(True)
        g1.addWidget(self.lbl_split_src, stretch=1)
        g1.addWidget(self._boton_limpiar(self._split_clear))
        lay.addWidget(grp1)

        # ── 2. Cómo partirlo ─────────────────────────────────────────
        grp2 = QGroupBox("2️⃣  Cómo querés partirlo")
        g2 = QVBoxLayout(grp2)
        self._split_mode_group = QButtonGroup(self)

        # Por tamaño
        self.rad_split_size = QRadioButton(
            "En partes que no superen un tamaño")
        self.rad_split_size.setChecked(True)
        self._split_mode_group.addButton(self.rad_split_size)
        g2.addWidget(self.rad_split_size)

        row_size = QHBoxLayout()
        row_size.addSpacing(22)
        row_size.addWidget(QLabel("Máximo por parte:"))
        self.spin_split_mb = QDoubleSpinBox()
        self.spin_split_mb.setRange(0.1, 2000.0)
        self.spin_split_mb.setValue(PDF_MAX_MB_DEFECTO)
        self.spin_split_mb.setSuffix(" MB")
        self.spin_split_mb.setDecimals(1)
        row_size.addWidget(self.spin_split_mb)
        btn_limite = QPushButton(f"{PDF_MAX_MB_DEFECTO:g} MB")
        btn_limite.setObjectName("ghostBtn")
        btn_limite.setToolTip("Límite habitual de correos, formularios y portales.")
        btn_limite.clicked.connect(
            lambda: self.spin_split_mb.setValue(PDF_MAX_MB_DEFECTO))
        row_size.addWidget(btn_limite)
        row_size.addStretch()
        g2.addLayout(row_size)

        # Por cantidad de páginas
        self.rad_split_pages = QRadioButton("En partes de X páginas cada una")
        self._split_mode_group.addButton(self.rad_split_pages)
        g2.addWidget(self.rad_split_pages)

        row_pages = QHBoxLayout()
        row_pages.addSpacing(22)
        row_pages.addWidget(QLabel("Páginas por parte:"))
        self.spin_split_pages = QSpinBox()
        self.spin_split_pages.setRange(1, 10000)
        self.spin_split_pages.setValue(10)
        row_pages.addWidget(self.spin_split_pages)
        row_pages.addStretch()
        g2.addLayout(row_pages)

        # Extraer un rango
        self.rad_split_range = QRadioButton(
            "Quedarme sólo con un tramo de páginas")
        self._split_mode_group.addButton(self.rad_split_range)
        g2.addWidget(self.rad_split_range)

        row_range = QHBoxLayout()
        row_range.addSpacing(22)
        row_range.addWidget(QLabel("Desde la página"))
        self.spin_range_from = QSpinBox()
        self.spin_range_from.setRange(1, 10000)
        row_range.addWidget(self.spin_range_from)
        row_range.addWidget(QLabel("hasta la"))
        self.spin_range_to = QSpinBox()
        self.spin_range_to.setRange(1, 10000)
        row_range.addWidget(self.spin_range_to)
        row_range.addStretch()
        g2.addLayout(row_range)

        # Habilitar sólo los controles del modo elegido
        for rad, controles in (
            (self.rad_split_size, [self.spin_split_mb, btn_limite]),
            (self.rad_split_pages, [self.spin_split_pages]),
            (self.rad_split_range, [self.spin_range_from, self.spin_range_to]),
        ):
            rad.toggled.connect(
                lambda on, cs=controles: [c.setEnabled(on) for c in cs])
        for c in (self.spin_split_pages, self.spin_range_from,
                  self.spin_range_to):
            c.setEnabled(False)

        lay.addWidget(grp2)

        btn_split = QPushButton("✂️ Partir el PDF")
        btn_split.clicked.connect(self._do_split)
        lay.addWidget(btn_split)

        self.lbl_split_status = QLabel("")
        self.lbl_split_status.setWordWrap(True)
        lay.addWidget(self.lbl_split_status)

        lay.addStretch()
        return tab

    def _pick_split_src(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Elegí el PDF a partir", "", "Archivos PDF (*.pdf)")
        if not path:
            return
        from motors.motor_pdf_tools import page_count
        try:
            total = page_count(path)
        except Exception as e:
            QMessageBox.warning(self, "Partir PDF",
                                f"No pude abrir ese PDF:\n{e}")
            return

        self._split_src = path
        self._split_pages = total
        mb = os.path.getsize(path) / 1048576
        self.lbl_split_src.setText(
            f"<b>{os.path.basename(path)}</b><br>"
            f"{total} página(s) · {mb:.1f} MB")
        for spin in (self.spin_range_from, self.spin_range_to):
            spin.setMaximum(max(total, 1))
        self.spin_range_from.setValue(1)
        self.spin_range_to.setValue(total)
        self.spin_split_pages.setMaximum(max(total, 1))

    def _split_clear(self):
        self._split_src = ""
        self._split_pages = 0
        self.lbl_split_src.setText("(ninguno elegido)")
        self.lbl_split_status.setText("")

    def _do_split(self):
        if not self._split_src:
            QMessageBox.warning(self, "Partir PDF",
                                "Primero elegí el PDF que querés partir.")
            return
        if not os.path.isfile(self._split_src):
            QMessageBox.warning(
                self, "Partir PDF",
                "El PDF que habías elegido ya no está en esa carpeta. "
                "Volvé a elegirlo.")
            return

        if self.rad_split_range.isChecked():
            # Un solo archivo de salida: se pregunta dónde guardarlo
            destino = (os.path.splitext(self._split_src)[0]
                       + f"_paginas_{self.spin_range_from.value()}"
                         f"-{self.spin_range_to.value()}.pdf")
            dst, _ = QFileDialog.getSaveFileName(
                self, "Guardar como", destino, "Archivos PDF (*.pdf)")
            if not dst:
                return
            from motors.motor_pdf_tools import extract_pdf_range
            origen = self._split_src
            desde, hasta = (self.spin_range_from.value(),
                            self.spin_range_to.value())
            frase = (f"extraer las páginas {desde} a {hasta} del archivo "
                     f"«{os.path.basename(origen)}»")
            self._run_op(extract_pdf_range, origen, dst, desde, hasta,
                         status_label=self.lbl_split_status,
                         success_prefix="✅ Listo. ",
                         on_result=lambda r: self._generar_informe(
                             frase, [origen], self._archivos_de(r, [dst])))
            return

        # Varios archivos: se pregunta la carpeta destino
        carpeta = QFileDialog.getExistingDirectory(
            self, "¿En qué carpeta dejo las partes?",
            os.path.dirname(self._split_src))
        if not carpeta:
            return

        origen = self._split_src
        nombre = os.path.basename(origen)
        if self.rad_split_size.isChecked():
            from motors.motor_pdf_tools import split_pdf_by_size
            limite = self.spin_split_mb.value()
            frase = (f"partir el archivo «{nombre}» en partes de hasta "
                     f"{limite:.1f} MB cada una")
            self._run_op(split_pdf_by_size, origen, carpeta, limite,
                         status_label=self.lbl_split_status,
                         success_prefix="✅ PDF partido. ",
                         on_result=lambda r: self._generar_informe(
                             frase, [origen], self._archivos_de(r)))
        else:
            from motors.motor_pdf_tools import split_pdf_by_pages
            cuantas = self.spin_split_pages.value()
            frase = (f"partir el archivo «{nombre}» en partes de {cuantas} "
                     f"página(s) cada una")
            self._run_op(split_pdf_by_pages, origen, carpeta, cuantas,
                         status_label=self.lbl_split_status,
                         success_prefix="✅ PDF partido. ",
                         on_result=lambda r: self._generar_informe(
                             frase, [origen], self._archivos_de(r)))

    # ──────────────────────────────────────────────────────────────────
    # TAB: Hojas dobles
    #
    # Fojas escaneadas de a dos: una hoja oficio apaisada con una página a
    # cada lado. Se separan en hojas A4 sueltas y, si se pide, se reconoce
    # el texto ya separado (leídas juntas, el OCR mezcla los renglones de
    # las dos páginas).
    # ──────────────────────────────────────────────────────────────────

    def _build_double_tab(self) -> QWidget:
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(10)


        intro = QLabel(
            "Para documentos escaneados <b>de a dos páginas por hoja</b>: "
            "una hoja oficio apaisada con la página 1 a la izquierda y la 2 "
            "a la derecha. Cada página sale como una <b>hoja A4</b> propia, "
            "en orden. El corte se hace en el pliegue que se ve en el "
            "escaneo, aunque no esté justo en la mitad. Sirve con un PDF "
            "o directamente con <b>fotos</b> (JPG, PNG...): cada foto es "
            "una hoja.")
        intro.setWordWrap(True)
        lay.addWidget(intro)

        # ── 1. Elegir PDF y/o fotos ──────────────────────────────────
        grp1 = QGroupBox("1️⃣  Elegí los PDF o las fotos")
        g1 = QVBoxLayout(grp1)
        row_add = QHBoxLayout()
        btn_add = QPushButton("➕ Agregar archivos...")
        btn_add.clicked.connect(self._double_add_files)
        row_add.addWidget(btn_add)
        btn_folder = QPushButton("📁 Agregar carpeta...")
        btn_folder.clicked.connect(self._double_add_folder)
        row_add.addWidget(btn_folder)
        btn_remove = QPushButton("🗑 Quitar seleccionados")
        btn_remove.clicked.connect(self._double_remove)
        row_add.addWidget(btn_remove)
        row_add.addWidget(self._boton_limpiar(self._double_clear))
        row_add.addStretch()
        g1.addLayout(row_add)

        ayuda = QLabel(
            "Podés mezclar PDF y fotos. Se procesan en el orden de la lista: "
            "arrastrá para cambiarlo. Al agregar, quedan ordenados por nombre "
            "(IMG_0001, IMG_0002...).")
        ayuda.setWordWrap(True)
        ayuda.setStyleSheet("color:#64748b; font-size:11px;")
        g1.addWidget(ayuda)

        self.double_list = QListWidget()
        self.double_list.setDragDropMode(
            QAbstractItemView.DragDropMode.InternalMove)
        self.double_list.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection)
        self.double_list.setMinimumHeight(130)
        self.double_list.model().rowsMoved.connect(
            lambda *_: self._double_refresh())
        g1.addWidget(self.double_list)

        self.lbl_double_src = QLabel("(la lista está vacía)")
        self.lbl_double_src.setStyleSheet("color:#64748b;")
        self.lbl_double_src.setWordWrap(True)
        g1.addWidget(self.lbl_double_src)

        self.rad_double_join = QRadioButton(
            "Todo junto en un solo resultado, en el orden de la lista")
        self.rad_double_each = QRadioButton(
            "Un resultado por cada archivo (en la carpeta que elijas)")
        self.rad_double_join.setChecked(True)
        self._double_join_group = QButtonGroup(self)
        for r in (self.rad_double_join, self.rad_double_each):
            self._double_join_group.addButton(r)
            g1.addWidget(r)
        lay.addWidget(grp1)

        # ── 2. Orden de las dos mitades ──────────────────────────────
        grp2 = QGroupBox("2️⃣  Qué página va primero")
        g2 = QVBoxLayout(grp2)
        self.rad_double_left = QRadioButton(
            "La de la izquierda (lo normal: izquierda = 1, derecha = 2)")
        self.rad_double_left.setChecked(True)
        self.rad_double_right = QRadioButton("La de la derecha")
        self._double_order_group = QButtonGroup(self)
        for r in (self.rad_double_left, self.rad_double_right):
            self._double_order_group.addButton(r)
            g2.addWidget(r)
        lay.addWidget(grp2)

        # ── 3. Qué querés obtener ────────────────────────────────────
        grp3 = QGroupBox("3️⃣  Qué querés obtener")
        g3 = QVBoxLayout(grp3)
        self.rad_double_pdf = QRadioButton(
            "Un PDF con cada página en su hoja A4")
        self.rad_double_ocr = QRadioButton(
            "Un PDF con cada página en su hoja A4 y el texto buscable (OCR)")
        self.rad_double_txt = QRadioButton(
            "Un archivo de texto (.txt) con lo que dice cada página (OCR)")
        self.rad_double_ocr.setChecked(True)
        self._double_out_group = QButtonGroup(self)
        for r in (self.rad_double_pdf, self.rad_double_ocr,
                  self.rad_double_txt):
            self._double_out_group.addButton(r)
            g3.addWidget(r)

        row_op = QHBoxLayout()
        row_op.addSpacing(22)
        row_op.addWidget(QLabel("Idioma del documento:"))
        self.cmb_double_lang = QComboBox()
        self.cmb_double_lang.addItems(
            ["Español", "Inglés", "Portugués", "Francés", "Alemán", "Italiano"])
        row_op.addWidget(self.cmb_double_lang)
        self.chk_double_gray = QCheckBox("Blanco y negro (archivo más liviano)")
        row_op.addWidget(self.chk_double_gray)
        row_op.addStretch()
        g3.addLayout(row_op)

        try:
            from motors.motor_ocr import is_available
            hay_ocr = is_available()
        except Exception:
            hay_ocr = False
        if hay_ocr:
            def _sync_ocr_controls():
                ocr = not self.rad_double_pdf.isChecked()
                self.cmb_double_lang.setEnabled(ocr)
                self.chk_double_gray.setEnabled(self.rad_double_ocr.isChecked())
            for r in (self.rad_double_pdf, self.rad_double_ocr,
                      self.rad_double_txt):
                r.toggled.connect(_sync_ocr_controls)
            _sync_ocr_controls()
        else:
            self.rad_double_pdf.setChecked(True)
            for c in (self.rad_double_ocr, self.rad_double_txt,
                      self.cmb_double_lang, self.chk_double_gray):
                c.setEnabled(False)
            falta = QLabel(
                "El reconocimiento de texto no está disponible: falta "
                "tesseract.exe en la carpeta bin/.")
            falta.setWordWrap(True)
            falta.setStyleSheet("color:#92400e; font-size:11px;")
            g3.addWidget(falta)
        lay.addWidget(grp3)

        btn_run = QPushButton("📖 Separar las hojas")
        btn_run.clicked.connect(self._do_double)
        lay.addWidget(btn_run)

        self.lbl_double_status = QLabel("")
        self.lbl_double_status.setWordWrap(True)
        lay.addWidget(self.lbl_double_status)

        # Dónde quedó lo último que se hizo, y un botón para abrirlo
        self._double_last_dir = ""
        self.lbl_double_where = QLabel("")
        self.lbl_double_where.setWordWrap(True)
        self.lbl_double_where.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        self.lbl_double_where.setVisible(False)
        lay.addWidget(self.lbl_double_where)
        self.btn_double_open = QPushButton("📂 Abrir carpeta de resultados")
        self.btn_double_open.setObjectName("ghostBtn")
        self.btn_double_open.setVisible(False)
        self.btn_double_open.clicked.connect(
            lambda: self._open_folder(self._double_last_dir))
        lay.addWidget(self.btn_double_open)

        lay.addStretch()
        return tab

    def _double_paths(self) -> list:
        return [self.double_list.item(i).data(Qt.ItemDataRole.UserRole)
                for i in range(self.double_list.count())]

    def _double_add_files(self):
        from motors.motor_pdf_tools import EXT_FOTOS
        fotos = " ".join("*" + e for e in EXT_FOTOS)
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Elegí los PDF o las fotos con hojas dobles", "",
            f"PDF o fotos (*.pdf {fotos});;Archivos PDF (*.pdf);;"
            f"Fotos ({fotos})")
        if paths:
            self._double_add_paths(paths)

    def _double_add_folder(self):
        from motors.motor_pdf_tools import EXT_FOTOS
        folder = QFileDialog.getExistingDirectory(
            self, "Elegí la carpeta con los PDF o las fotos")
        if not folder:
            return
        paths = [os.path.join(folder, f) for f in os.listdir(folder)
                 if f.lower().endswith((".pdf",) + EXT_FOTOS)]
        if not paths:
            QMessageBox.information(
                self, "Hojas dobles",
                "Esa carpeta no tiene PDF ni fotos.")
            return
        self._double_add_paths(paths)

    def _double_add_paths(self, paths):
        # Ordenados por nombre: es como numera la cámara o el celular
        paths = sorted(paths, key=lambda p: os.path.basename(p).lower())
        existentes = {os.path.normcase(os.path.abspath(p))
                      for p in self._double_paths()}
        for path in paths:
            clave = os.path.normcase(os.path.abspath(path))
            if clave in existentes:
                continue
            item = QListWidgetItem(os.path.basename(path))
            item.setData(Qt.ItemDataRole.UserRole, path)
            item.setToolTip(path)
            self.double_list.addItem(item)
            existentes.add(clave)
        self._double_refresh()

    def _double_remove(self):
        for item in self.double_list.selectedItems():
            self.double_list.takeItem(self.double_list.row(item))
        self._double_refresh()

    def _double_clear(self):
        self.double_list.clear()
        self._double_refresh()
        self.lbl_double_status.setText("")
        self.lbl_double_where.setVisible(False)
        self.btn_double_open.setVisible(False)

    def _double_refresh(self):
        """Numera la lista y cuenta cuántas hojas dobles hay en total."""
        paths = self._double_paths()
        for i, path in enumerate(paths):
            self.double_list.item(i).setText(
                f"{i + 1}.  {os.path.basename(path)}")
        if not paths:
            self.lbl_double_src.setText("(la lista está vacía)")
            return
        from motors.motor_pdf_tools import contar_hojas_dobles
        dobles = total = 0
        malos = []
        for p in paths:
            try:
                d, t = contar_hojas_dobles(p)
                dobles += d
                total += t
            except Exception:
                malos.append(os.path.basename(p))
        if dobles == 0:
            detalle = "⚠ Ninguna hoja es apaisada: no parece haber hojas dobles."
        elif dobles == total:
            detalle = (f"Las {total} hoja(s) son dobles: van a quedar "
                       f"{total * 2} página(s) A4.")
        else:
            detalle = (f"{dobles} de {total} hoja(s) son dobles; las otras "
                       f"{total - dobles} se pasan a A4 sin cortar.")
        texto = f"<b>{len(paths)} archivo(s)</b> · {detalle}"
        if malos:
            texto += ("<br>⚠ No pude abrir: " + ", ".join(malos[:3])
                      + (" y otros" if len(malos) > 3 else ""))
        self.lbl_double_src.setText(texto)

    def _do_double(self):
        origenes = self._double_paths()
        if not origenes:
            QMessageBox.warning(self, "Hojas dobles",
                                "Primero agregá los PDF o las fotos.")
            return
        faltan = [p for p in origenes if not os.path.isfile(p)]
        if faltan:
            QMessageBox.warning(
                self, "Hojas dobles",
                f"«{os.path.basename(faltan[0])}» ya no está en esa carpeta. "
                "Quitalo de la lista o volvé a agregarlo.")
            return

        if self.rad_double_txt.isChecked():
            ocr, sufijo, filtro = "txt", "_A4.txt", "Texto (*.txt)"
        elif self.rad_double_ocr.isChecked():
            ocr, sufijo, filtro = "pdf", "_A4_buscable.pdf", "Archivos PDF (*.pdf)"
        else:
            ocr, sufijo, filtro = "", "_A4.pdf", "Archivos PDF (*.pdf)"

        def _clave(ruta):
            return os.path.normcase(os.path.abspath(ruta))

        separado = self.rad_double_each.isChecked() and len(origenes) > 1
        if separado:
            dst = QFileDialog.getExistingDirectory(
                self, "¿En qué carpeta dejo los resultados?",
                os.path.dirname(origenes[0]))
            if not dst:
                return
            salidas = {_clave(os.path.join(
                dst, os.path.splitext(os.path.basename(p))[0] + sufijo))
                for p in origenes}
            if salidas & {_clave(p) for p in origenes}:
                QMessageBox.warning(self, "Hojas dobles",
                                    "Elegí otra carpeta: se pisaría un original.")
                return
        else:
            destino = os.path.splitext(origenes[0])[0] + sufijo
            dst, _ = QFileDialog.getSaveFileName(
                self, "Guardar como", destino, filtro)
            if not dst:
                return
            if _clave(dst) in {_clave(p) for p in origenes}:
                QMessageBox.warning(self, "Hojas dobles",
                                    "Elegí un nombre distinto al original.")
                return

        if len(origenes) == 1:
            objeto = f"del archivo «{os.path.basename(origenes[0])}»"
        else:
            objeto = (f"de los {len(origenes)} archivos "
                      + ", ".join(f"«{os.path.basename(p)}»" for p in origenes)
                      + (" (cada uno por separado)" if separado
                         else " (en ese orden, en un solo resultado)"))
        lang = self.cmb_double_lang.currentText()
        derecha = self.rad_double_right.isChecked()
        frase = (f"separar las hojas dobles {objeto} en "
                 f"páginas individuales de tamaño A4, "
                 f"{'derecha' if derecha else 'izquierda'} primero")
        if ocr == "pdf":
            frase += (f", y aplicar reconocimiento óptico de caracteres (OCR) "
                      f"en idioma {lang.lower()} para dejar el texto buscable")
        elif ocr == "txt":
            frase += (f", y extraer su texto mediante reconocimiento óptico "
                      f"de caracteres (OCR) en idioma {lang.lower()}")

        self.lbl_double_where.setVisible(False)
        self.btn_double_open.setVisible(False)

        opciones = dict(derecha_primero=derecha, ocr=ocr, lang=lang,
                        grayscale=(ocr == "pdf"
                                   and self.chk_double_gray.isChecked()))
        from motors.motor_pdf_tools import (desdoblar_hojas_dobles,
                                            desdoblar_varios)
        if separado:
            self._run_op(desdoblar_varios, origenes, dst, sufijo,
                         status_label=self.lbl_double_status,
                         success_prefix="✅ Listo. ",
                         on_result=lambda r: self._double_listo(
                             r, frase, origenes, dst, carpeta=True),
                         **opciones)
        else:
            self._run_op(desdoblar_hojas_dobles,
                         origenes if len(origenes) > 1 else origenes[0], dst,
                         status_label=self.lbl_double_status,
                         success_prefix="✅ Listo. ",
                         on_result=lambda r: self._double_listo(
                             r, frase, origenes, dst, carpeta=False),
                         **opciones)

    def _double_listo(self, resultado, frase, origenes, dst, carpeta: bool):
        """Muestra dónde quedó el resultado y habilita abrir la carpeta."""
        if carpeta:
            self._double_last_dir = dst
            texto = f"📁 Guardado en la carpeta:<br><b>{dst}</b>"
        else:
            self._double_last_dir = os.path.dirname(dst)
            texto = f"📁 Guardado en:<br><b>{dst}</b>"
        self.lbl_double_where.setText(texto)
        self.lbl_double_where.setVisible(True)
        self.btn_double_open.setVisible(True)
        self._generar_informe(frase, origenes,
                              self._archivos_de(resultado, [dst]))

    @staticmethod
    def _open_folder(carpeta: str):
        if not carpeta or not os.path.isdir(carpeta):
            return
        import platform
        import subprocess
        try:
            if platform.system() == "Windows":
                os.startfile(carpeta)
            elif platform.system() == "Darwin":
                subprocess.run(["open", carpeta])
            else:
                subprocess.run(["xdg-open", carpeta])
        except Exception:
            pass

    # ──────────────────────────────────────────────────────────────────
    # TAB: Ajustar tamaño (PDF con límite por archivo)
    #
    # Con 30 PDF sueltos, subirlos de a 5 controlando que ninguno pase de
    # 10 MB es tedioso y es fácil equivocarse (copiar uno de más, saltear
    # otro). Acá se elige la carpeta y el programa deja las tandas armadas.
    # ──────────────────────────────────────────────────────────────────

    def _build_limite_tab(self) -> QWidget:
        from motors.motor_pdf_tools import PDF_MAX_MB_DEFECTO, POR_TANDA_DEFECTO
        from core.salidas import etiqueta_destino

        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(10)

        self._limite_files: list   = []
        self._limite_out: str      = ""
        self._limite_last_dir: str = ""

        intro = QLabel(
            "Deja una carpeta de PDF lista para subir a un portal con límite de "
            "tamaño: parte los que "
            "pasan del límite y arma las tandas de 5 archivos.")
        intro.setWordWrap(True)
        intro.setStyleSheet("color:#64748b;")
        lay.addWidget(intro)

        # ── 1. Elegir los PDF ────────────────────────────────────────
        grp1 = QGroupBox("1️⃣  Elegí los PDF")
        g1 = QVBoxLayout(grp1)
        row1 = QHBoxLayout()
        btn_folder = QPushButton("📁 Elegir carpeta...")
        btn_folder.clicked.connect(self._pick_limite_folder)
        row1.addWidget(btn_folder)
        btn_files = QPushButton("📄 Elegir archivos...")
        btn_files.clicked.connect(self._pick_limite_files)
        row1.addWidget(btn_files)
        row1.addWidget(self._boton_limpiar(self._clear_limite_files))
        row1.addStretch()
        g1.addLayout(row1)

        self.lbl_limite_files = QLabel("(ninguno elegido)")
        self.lbl_limite_files.setStyleSheet("color:#64748b;")
        self.lbl_limite_files.setWordWrap(True)
        g1.addWidget(self.lbl_limite_files)
        lay.addWidget(grp1)

        # ── 2. Cómo se preparan ──────────────────────────────────────
        grp2 = QGroupBox("2️⃣  Cómo se preparan")
        g2 = QVBoxLayout(grp2)

        row_mb = QHBoxLayout()
        row_mb.addWidget(QLabel("Máximo por archivo:"))
        self.spin_limite_mb = QDoubleSpinBox()
        self.spin_limite_mb.setRange(0.1, 2000.0)
        self.spin_limite_mb.setValue(PDF_MAX_MB_DEFECTO)
        self.spin_limite_mb.setSuffix(" MB")
        self.spin_limite_mb.setDecimals(1)
        self.spin_limite_mb.valueChanged.connect(
            lambda _v: self._refresh_limite_files())
        row_mb.addWidget(self.spin_limite_mb)
        btn_limite_mb = QPushButton(f"{PDF_MAX_MB_DEFECTO:g} MB")
        btn_limite_mb.setObjectName("ghostBtn")
        btn_limite_mb.setToolTip("Límite habitual de correos, formularios y portales.")
        btn_limite_mb.clicked.connect(
            lambda: self.spin_limite_mb.setValue(PDF_MAX_MB_DEFECTO))
        row_mb.addWidget(btn_limite_mb)
        row_mb.addStretch()
        g2.addLayout(row_mb)

        row_tanda = QHBoxLayout()
        row_tanda.addWidget(QLabel("Archivos por tanda:"))
        self.spin_limite_tanda = QSpinBox()
        self.spin_limite_tanda.setRange(1, 100)
        self.spin_limite_tanda.setValue(POR_TANDA_DEFECTO)
        self.spin_limite_tanda.setToolTip(
            "Muchos portales sólo dejan subir unos pocos archivos por vez.")
        row_tanda.addWidget(self.spin_limite_tanda)
        row_tanda.addStretch()
        g2.addLayout(row_tanda)

        row_out = QHBoxLayout()
        row_out.addWidget(QLabel("Carpeta de destino:"))
        self.lbl_limite_out = QLabel(etiqueta_destino(""))
        self.lbl_limite_out.setStyleSheet("color:#64748b;")
        self.lbl_limite_out.setWordWrap(True)
        row_out.addWidget(self.lbl_limite_out, stretch=1)
        btn_out = QPushButton("Cambiar")
        btn_out.setObjectName("ghostBtn")
        btn_out.clicked.connect(self._pick_limite_out)
        row_out.addWidget(btn_out)
        g2.addLayout(row_out)
        lay.addWidget(grp2)

        # ── 3. Preparar ──────────────────────────────────────────────
        btn_run = QPushButton("📦 Preparar la carpeta")
        btn_run.clicked.connect(self._do_limite_prep)
        lay.addWidget(btn_run)

        self.lbl_limite_status = QLabel("")
        self.lbl_limite_status.setWordWrap(True)
        lay.addWidget(self.lbl_limite_status)

        self.btn_limite_open = QPushButton("📂 Abrir carpeta de resultados")
        self.btn_limite_open.setObjectName("ghostBtn")
        self.btn_limite_open.setVisible(False)
        self.btn_limite_open.clicked.connect(self._open_limite_folder)
        lay.addWidget(self.btn_limite_open)

        lay.addStretch()
        return tab

    # ── Elegir archivos ───────────────────────────────────────────────

    def _pick_limite_folder(self):
        carpeta = QFileDialog.getExistingDirectory(
            self, "Elegí la carpeta con los PDF")
        if not carpeta:
            return
        pdfs = sorted(
            os.path.join(carpeta, f)
            for f in os.listdir(carpeta)
            if f.lower().endswith(".pdf")
            and os.path.isfile(os.path.join(carpeta, f))
        )
        if not pdfs:
            QMessageBox.warning(self, "Ajustar tamaño",
                                "No hay archivos PDF en esa carpeta.")
            return
        self._limite_files = pdfs
        self._refresh_limite_files()

    def _pick_limite_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Elegí los PDF", "", "Archivos PDF (*.pdf)")
        if not paths:
            return
        for p in paths:
            if p not in self._limite_files:
                self._limite_files.append(p)
        self._refresh_limite_files()

    def _clear_limite_files(self):
        self._limite_files = []
        self._refresh_limite_files()
        self.lbl_limite_status.setText("")
        self.btn_limite_open.setVisible(False)

    def _refresh_limite_files(self):
        from core.salidas import etiqueta_destino
        if not self._limite_files:
            self.lbl_limite_files.setText("(ninguno elegido)")
        else:
            n  = len(self._limite_files)
            mb = sum(os.path.getsize(p) for p in self._limite_files
                     if os.path.isfile(p)) / 1048576
            limite = self.spin_limite_mb.value() * 1048576
            grandes = sum(1 for p in self._limite_files
                          if os.path.isfile(p) and os.path.getsize(p) > limite)
            texto = f"<b>{n}</b> PDF · {mb:.1f} MB en total"
            if grandes:
                plural = "n" if grandes > 1 else ""
                texto += (f" · {grandes} pasa{plural} del límite y "
                          f"se parte{plural}")
            self.lbl_limite_files.setText(texto)
        self.lbl_limite_out.setText(
            etiqueta_destino(self._limite_files, self._limite_out))

    def _pick_limite_out(self):
        d = QFileDialog.getExistingDirectory(self, "Carpeta de destino")
        if d:
            self._limite_out = d
            self._refresh_limite_files()

    # ── Preparar ──────────────────────────────────────────────────────

    def _do_limite_prep(self):
        if not self._limite_files:
            QMessageBox.warning(
                self, "Ajustar tamaño",
                "Primero elegí la carpeta (o los archivos) que querés preparar.")
            return
        faltan = [p for p in self._limite_files if not os.path.isfile(p)]
        if faltan:
            QMessageBox.warning(
                self, "Ajustar tamaño",
                f"{len(faltan)} archivo(s) ya no están en su carpeta. "
                "Volvé a elegirlos.")
            return

        from motors.motor_pdf_tools import preparar_pdfs_por_tamano
        origenes  = list(self._limite_files)
        max_mb    = self.spin_limite_mb.value()
        por_tanda = self.spin_limite_tanda.value()

        self._run_op(preparar_pdfs_por_tamano, origenes, self._limite_out,
                     max_mb, por_tanda,
                     status_label=self.lbl_limite_status,
                     success_prefix="✅ Listo. ",
                     on_result=lambda r: self._limite_prep_listo(
                         r, max_mb, por_tanda))

    def _limite_prep_listo(self, resultado, max_mb, por_tanda):
        if not isinstance(resultado, dict):
            return
        self._limite_last_dir = resultado.get("carpeta", "")
        self.btn_limite_open.setVisible(bool(self._limite_last_dir))
        self._informe_limite_worker = _LimitePrepInformeWorker(
            resultado.get("detalle") or [], max_mb, por_tanda,
            self._limite_last_dir, resultado.get("tandas", 0))
        self._informe_limite_worker.listo.connect(self._mostrar_informe)
        self._informe_limite_worker.start()

    def _open_limite_folder(self):
        carpeta = self._limite_last_dir
        if not carpeta or not os.path.isdir(carpeta):
            return
        import platform
        import subprocess
        try:
            if platform.system() == "Windows":
                os.startfile(carpeta)
            elif platform.system() == "Darwin":
                subprocess.run(["open", carpeta])
            else:
                subprocess.run(["xdg-open", carpeta])
        except Exception:
            pass

    # ──────────────────────────────────────────────────────────────────
    # TAB: Reconocer texto (OCR)
    #
    # El OCR ya existía, pero sólo se llegaba desde "Convertir", como una
    # casilla dentro de una conversión. Reconocer el texto de un PDF es una
    # tarea de PDF y merece estar acá, al lado de unir, partir y firmar.
    # ──────────────────────────────────────────────────────────────────

    def _build_ocr_tab(self) -> QWidget:
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(10)

        self._ocr_src = ""

        intro = QLabel(
            "Cuando un PDF viene de un escáner, las páginas son "
            "<b>fotos</b>: no se puede buscar ni copiar el texto. "
            "El reconocimiento de texto (OCR) lee esas imágenes y escribe "
            "el texto que encuentra.")
        intro.setWordWrap(True)
        lay.addWidget(intro)

        try:
            from motors.motor_ocr import is_available
            hay_ocr = is_available()
        except Exception:
            hay_ocr = False

        if not hay_ocr:
            falta = QLabel(
                "⚠️  Falta el programa que hace el reconocimiento "
                "(<b>tesseract.exe</b> en la carpeta <code>bin/</code>). "
                "Sin él esta función no se puede usar.")
            falta.setWordWrap(True)
            falta.setStyleSheet(
                "background:#fffbeb; border:1px solid #f59e0b; "
                "border-radius:6px; padding:10px; color:#92400e;")
            lay.addWidget(falta)
            lay.addStretch()
            return tab

        # ── 1. Elegir el PDF ─────────────────────────────────────────
        grp1 = QGroupBox("1️⃣  Elegí el PDF")
        g1 = QHBoxLayout(grp1)
        btn_pick = QPushButton("📄 Elegir PDF...")
        btn_pick.clicked.connect(self._pick_ocr_src)
        g1.addWidget(btn_pick)
        self.lbl_ocr_src = QLabel("(ninguno elegido)")
        self.lbl_ocr_src.setStyleSheet("color:#64748b;")
        self.lbl_ocr_src.setWordWrap(True)
        g1.addWidget(self.lbl_ocr_src, stretch=1)
        g1.addWidget(self._boton_limpiar(self._ocr_clear))
        lay.addWidget(grp1)

        # Aviso de si hace falta OCR o no, para no procesar al pedo
        self.lbl_ocr_diag = QLabel("")
        self.lbl_ocr_diag.setWordWrap(True)
        self.lbl_ocr_diag.setVisible(False)
        lay.addWidget(self.lbl_ocr_diag)

        # ── 2. Qué querés obtener ────────────────────────────────────
        grp2 = QGroupBox("2️⃣  Qué querés obtener")
        g2 = QVBoxLayout(grp2)

        self.rad_ocr_pdf = QRadioButton(
            "Un PDF igual al original, pero con el texto buscable")
        self.rad_ocr_pdf.setChecked(True)
        self.rad_ocr_txt = QRadioButton(
            "Un archivo de texto (.txt) con lo que diga el documento")
        self._ocr_out_group = QButtonGroup(self)
        for r in (self.rad_ocr_pdf, self.rad_ocr_txt):
            self._ocr_out_group.addButton(r)
            g2.addWidget(r)

        detalle = QLabel(
            "La primera opción es la recomendada: el documento se ve "
            "<b>idéntico</b> y además se puede buscar con Ctrl+F y copiar. "
            "La segunda descarta el diseño y deja sólo las palabras.")
        detalle.setWordWrap(True)
        detalle.setStyleSheet("color:#64748b; font-size:11px;")
        g2.addWidget(detalle)

        row_op = QHBoxLayout()
        row_op.addWidget(QLabel("Idioma del documento:"))
        self.cmb_ocr_lang = QComboBox()
        self.cmb_ocr_lang.addItems(
            ["Español", "Inglés", "Portugués", "Francés", "Alemán", "Italiano"])
        row_op.addWidget(self.cmb_ocr_lang)
        self.chk_ocr_gray = QCheckBox("Blanco y negro (archivo más liviano)")
        self.chk_ocr_gray.setToolTip(
            "Guarda las páginas en escala de grises: el PDF pesa bastante "
            "menos, pero se pierde el color del original.")
        row_op.addWidget(self.chk_ocr_gray)
        row_op.addStretch()
        g2.addLayout(row_op)

        # Leídas juntas, las dos páginas de una hoja doble salen con los
        # renglones mezclados: se separan antes de reconocer.
        self.chk_ocr_double = QCheckBox(
            "Las hojas son dobles (dos páginas por hoja): separarlas en A4 "
            "antes de reconocer")
        self.chk_ocr_double.setEnabled(False)
        self.chk_ocr_double.setToolTip(
            "Se activa sola cuando el PDF tiene hojas apaisadas. "
            "La página de la izquierda queda primero.")
        g2.addWidget(self.chk_ocr_double)
        lay.addWidget(grp2)

        btn_ocr = QPushButton("🔍 Reconocer el texto")
        btn_ocr.clicked.connect(self._do_ocr)
        lay.addWidget(btn_ocr)

        self.lbl_ocr_status = QLabel("")
        self.lbl_ocr_status.setWordWrap(True)
        lay.addWidget(self.lbl_ocr_status)

        lay.addStretch()
        return tab

    def _pick_ocr_src(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Elegí el PDF", "", "Archivos PDF (*.pdf)")
        if not path:
            return
        self._ocr_src = path
        from motors.motor_pdf_tools import page_count
        try:
            total = page_count(path)
        except Exception:
            total = 0
        self.lbl_ocr_src.setText(
            f"<b>{os.path.basename(path)}</b>"
            + (f"<br>{total} página(s)" if total else ""))

        # ¿Este PDF necesita OCR, o ya tiene texto?
        try:
            from motors.motor_ocr import is_scanned_pdf
            escaneado = is_scanned_pdf(path)
        except Exception:
            escaneado = True

        if escaneado:
            self.lbl_ocr_diag.setText(
                "✅ Este PDF parece escaneado (sus páginas son imágenes): "
                "el reconocimiento de texto le sirve.")
            self.lbl_ocr_diag.setStyleSheet(
                "background:#dcfce7; color:#166534; padding:8px; "
                "border-radius:4px;")
        else:
            self.lbl_ocr_diag.setText(
                "ℹ️ Este PDF <b>ya tiene texto</b> buscable: probablemente no "
                "necesites reconocerlo. Podés hacerlo igual, pero va a tardar "
                "y el resultado no va a mejorar.")
            self.lbl_ocr_diag.setStyleSheet(
                "background:#e0f2fe; color:#075985; padding:8px; "
                "border-radius:4px;")

        try:
            from motors.motor_pdf_tools import contar_hojas_dobles
            dobles, _ = contar_hojas_dobles(path)
        except Exception:
            dobles = 0
        self.chk_ocr_double.setEnabled(dobles > 0)
        self.chk_ocr_double.setChecked(dobles > 0)
        if dobles:
            self.lbl_ocr_diag.setText(
                self.lbl_ocr_diag.text()
                + f"<br>📖 {dobles} hoja(s) son apaisadas (dos páginas por "
                  f"hoja): se van a separar en A4 antes de reconocer.")
        self.lbl_ocr_diag.setVisible(True)

    def _ocr_clear(self):
        self._ocr_src = ""
        self.lbl_ocr_src.setText("(ninguno elegido)")
        self.lbl_ocr_diag.setVisible(False)
        self.chk_ocr_double.setChecked(False)
        self.chk_ocr_double.setEnabled(False)
        self.lbl_ocr_status.setText("")

    def _do_ocr(self):
        if not self._ocr_src:
            QMessageBox.warning(self, "Reconocer texto",
                                "Primero elegí el PDF.")
            return
        if not os.path.isfile(self._ocr_src):
            QMessageBox.warning(
                self, "Reconocer texto",
                "El PDF que habías elegido ya no está en esa carpeta. "
                "Volvé a elegirlo.")
            return

        a_pdf = self.rad_ocr_pdf.isChecked()
        sufijo = "_buscable.pdf" if a_pdf else ".txt"
        filtro = "Archivos PDF (*.pdf)" if a_pdf else "Texto (*.txt)"
        destino = os.path.splitext(self._ocr_src)[0] + sufijo
        dst, _ = QFileDialog.getSaveFileName(
            self, "Guardar como", destino, filtro)
        if not dst:
            return

        lang = self.cmb_ocr_lang.currentText()
        origen = self._ocr_src
        nombre = os.path.basename(origen)
        if self.chk_ocr_double.isEnabled() and self.chk_ocr_double.isChecked():
            from motors.motor_pdf_tools import desdoblar_hojas_dobles
            frase = (f"separar las hojas dobles del archivo «{nombre}» en "
                     f"páginas individuales de tamaño A4 y "
                     + (f"aplicar reconocimiento óptico de caracteres (OCR) "
                        f"en idioma {lang.lower()}, generando un PDF con "
                        f"texto buscable" if a_pdf else
                        f"extraer su texto mediante reconocimiento óptico de "
                        f"caracteres (OCR) en idioma {lang.lower()}"))
            self._run_op(desdoblar_hojas_dobles, origen, dst,
                         status_label=self.lbl_ocr_status,
                         success_prefix="✅ Texto reconocido. ",
                         on_result=lambda r: self._generar_informe(
                             frase, [origen], [dst]),
                         ocr="pdf" if a_pdf else "txt", lang=lang,
                         grayscale=a_pdf and self.chk_ocr_gray.isChecked())
            return
        if a_pdf:
            from motors.motor_ocr import convert_pdf_to_searchable_pdf
            frase = (f"aplicar reconocimiento óptico de caracteres (OCR) en "
                     f"idioma {lang.lower()} sobre el archivo «{nombre}», "
                     f"generando un PDF que conserva la imagen original y "
                     f"suma una capa de texto buscable")
            self._run_op(convert_pdf_to_searchable_pdf, origen, dst, lang,
                         status_label=self.lbl_ocr_status,
                         success_prefix="✅ Listo: el PDF ahora se puede "
                                        "buscar con Ctrl+F. ",
                         on_result=lambda r: self._generar_informe(
                             frase, [origen], [dst]),
                         grayscale=self.chk_ocr_gray.isChecked())
        else:
            from motors.motor_ocr import convert_pdf_to_text
            frase = (f"extraer el texto del archivo «{nombre}» mediante "
                     f"reconocimiento óptico de caracteres (OCR) en idioma "
                     f"{lang.lower()}")
            self._run_op(convert_pdf_to_text, origen, dst, lang,
                         status_label=self.lbl_ocr_status,
                         success_prefix="✅ Texto reconocido. ",
                         on_result=lambda r: self._generar_informe(
                             frase, [origen], [dst]))

    def _build_folder_merge_tab(self) -> QWidget:
        """Embebe el panel de 'unir una carpeta entera y partir por tamaño'.

        Antes era un módulo aparte del menú lateral llamado 'Texto / PDF',
        que no decía nada de lo que hace. Es el mismo patrón que usa el
        módulo de Audio para embeber sus paneles.
        """
        try:
            from ui.pdf_merger_splitter_panel import PdfMergerSplitterPanel
            scroll = QScrollArea()
            scroll.setWidget(PdfMergerSplitterPanel())
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            return scroll
        except Exception as e:
            aviso = QLabel(f"No disponible:\n{e}")
            aviso.setStyleSheet("color:#94a3b8; padding:24px;")
            aviso.setWordWrap(True)
            return aviso

    @staticmethod
    def _wrap_scroll(widget: QWidget) -> QScrollArea:
        """Envuelve una pestaña en un scroll vertical: si la ventana queda
        baja, se puede desplazar para ver los controles de más abajo en vez
        de que queden tapados/invisibles."""
        scroll = QScrollArea()
        scroll.setWidget(widget)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        return scroll

    # ──────────────────────────────────────────────────────────────────
    # TAB 1: Organizar páginas
    # ──────────────────────────────────────────────────────────────────

    def _build_organizer_tab(self) -> QWidget:
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(8)

        # Fila superior: elegir archivo
        top = QHBoxLayout()
        self.btn_open = QPushButton("📂 Elegir PDF...")
        self.btn_open.clicked.connect(self._open_pdf)
        top.addWidget(self.btn_open)
        self.lbl_file = QLabel("Ningún archivo cargado.")
        self.lbl_file.setStyleSheet("color: #64748b;")
        top.addWidget(self.lbl_file, stretch=1)
        top.addWidget(self._boton_limpiar(self._org_clear))
        lay.addLayout(top)

        hint = QLabel(
            "Arrastrá las miniaturas para cambiar el orden. "
            "Seleccioná una o varias (Ctrl+clic) y usá los botones para rotar o eliminar. "
            "\"🔍 Buscar duplicados\" resalta páginas con el mismo texto "
            "(por ejemplo, la misma hoja fotografiada dos veces). "
            "Nada se guarda hasta que toques \"Guardar como...\"."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #64748b; font-size: 11px;")
        lay.addWidget(hint)

        # Grilla de miniaturas
        self.thumb_list = QListWidget()
        self.thumb_list.setViewMode(QListWidget.ViewMode.IconMode)
        self.thumb_list.setIconSize(QSize(self.THUMB_EDGE, self.THUMB_EDGE))
        self.thumb_list.setGridSize(QSize(self.THUMB_EDGE + 24, self.THUMB_EDGE + 42))
        self.thumb_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.thumb_list.setMovement(QListWidget.Movement.Snap)
        self.thumb_list.setDragDropMode(
            QAbstractItemView.DragDropMode.InternalMove)
        self.thumb_list.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection)
        self.thumb_list.setSpacing(6)
        self.thumb_list.setMinimumHeight(220)
        lay.addWidget(self.thumb_list, stretch=1)

        # Supr elimina las páginas seleccionadas
        QShortcut(QKeySequence(Qt.Key.Key_Delete), self.thumb_list,
                  activated=self._delete_selected)

        self.thumb_progress = QProgressBar()
        self.thumb_progress.setVisible(False)
        lay.addWidget(self.thumb_progress)

        # Botonera (dos filas para que no se corte en ventanas angostas)
        btns_row1 = QHBoxLayout()
        self.btn_rot_left = QPushButton("↺ Rotar izquierda")
        self.btn_rot_left.clicked.connect(lambda: self._rotate_selected(-90))
        self.btn_rot_right = QPushButton("↻ Rotar derecha")
        self.btn_rot_right.clicked.connect(lambda: self._rotate_selected(90))
        self.btn_delete = QPushButton("🗑 Eliminar seleccionadas")
        self.btn_delete.clicked.connect(self._delete_selected)
        self.btn_find_dups = QPushButton("🔍 Buscar duplicados")
        self.btn_find_dups.clicked.connect(self._find_duplicates)
        # Escaneos en los que salió una hoja bien y la siguiente de cabeza:
        # se dan vuelta todas juntas, sin ir una por una.
        self.btn_flip_alt = QPushButton("🙃 Voltear una por medio")
        self.btn_flip_alt.setToolTip(
            "Para cuando quedó una hoja bien y la siguiente de cabeza.\n"
            "Gira 180° todas las pares o todas las impares de una vez.")
        menu_flip = QMenu(self.btn_flip_alt)
        menu_flip.addAction(
            "Las hojas pares (2, 4, 6…)", lambda: self._flip_alternate(1))
        menu_flip.addAction(
            "Las hojas impares (1, 3, 5…)", lambda: self._flip_alternate(0))
        self.btn_flip_alt.setMenu(menu_flip)
        for b in (self.btn_rot_left, self.btn_rot_right, self.btn_flip_alt,
                  self.btn_delete, self.btn_find_dups):
            b.setEnabled(False)
            btns_row1.addWidget(b)
        btns_row1.addStretch()
        lay.addLayout(btns_row1)

        btns_row2 = QHBoxLayout()
        self.btn_reset = QPushButton("↩ Deshacer todo")
        self.btn_reset.clicked.connect(self._reload_thumbs)
        self.btn_reset.setEnabled(False)
        btns_row2.addWidget(self.btn_reset)
        self.btn_save = QPushButton("💾 Guardar como...")
        self.btn_save.setObjectName("primaryBtn")
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(self._save_organized)
        btns_row2.addWidget(self.btn_save)
        btns_row2.addStretch()
        lay.addLayout(btns_row2)

        self.lbl_org_status = QLabel("")
        self.lbl_org_status.setWordWrap(True)
        lay.addWidget(self.lbl_org_status)
        return tab

    # ──────────────────────────────────────────────────────────────────
    def _open_pdf(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Elegir PDF", "", "Archivos PDF (*.pdf)")
        if not path:
            return
        self._pdf_path = path
        self.lbl_file.setText(os.path.basename(path))
        self._reload_thumbs()

    def _org_clear(self):
        if self._thumb_worker and self._thumb_worker.isRunning():
            self._thumb_worker.cancel()
            self._thumb_worker.wait(2000)
        self._pdf_path = ""
        self.thumb_list.clear()
        self.thumb_progress.setVisible(False)
        self.lbl_file.setText("Ningún archivo cargado.")
        self.lbl_org_status.setText("")
        self._set_org_buttons(False)

    def _reload_thumbs(self):
        if not self._pdf_path:
            return
        if self._thumb_worker and self._thumb_worker.isRunning():
            self._thumb_worker.cancel()
            self._thumb_worker.wait(2000)

        self.thumb_list.clear()
        self.lbl_org_status.setText("")
        try:
            from motors.motor_pdf_tools import page_count
            total = page_count(self._pdf_path)
        except Exception as e:
            QMessageBox.warning(self, "Editar PDF",
                                f"No se pudo abrir el PDF:\n{e}")
            return
        self.thumb_progress.setVisible(True)
        self.thumb_progress.setRange(0, total)
        self.thumb_progress.setValue(0)
        self._set_org_buttons(False)

        self._thumb_worker = _ThumbWorker(self._pdf_path)
        self._thumb_worker.thumb_ready.connect(self._add_thumb)
        self._thumb_worker.finished_ok.connect(self._thumbs_done)
        self._thumb_worker.error.connect(self._thumbs_error)
        self._thumb_worker.start()

    def _add_thumb(self, idx: int, png: bytes):
        img = QImage.fromData(png, "PNG")
        item = QListWidgetItem(QIcon(QPixmap.fromImage(img)),
                               f"Pág. {idx + 1}")
        item.setData(Qt.ItemDataRole.UserRole, idx)      # índice original
        item.setData(Qt.ItemDataRole.UserRole + 1, 0)    # rotación acumulada
        item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.thumb_list.addItem(item)
        self.thumb_progress.setValue(self.thumb_list.count())

    def _thumbs_done(self, total: int):
        self.thumb_progress.setVisible(False)
        self._set_org_buttons(True)
        self.lbl_org_status.setText(f"{total} páginas cargadas.")

    def _thumbs_error(self, msg: str):
        self.thumb_progress.setVisible(False)
        # Sin esto los botones quedaban apagados para siempre
        if self.thumb_list.count():
            self._set_org_buttons(True)
        QMessageBox.warning(self, "Editar PDF",
                            f"Error generando miniaturas:\n{msg}")

    def _set_org_buttons(self, on: bool):
        for b in (self.btn_rot_left, self.btn_rot_right, self.btn_flip_alt,
                  self.btn_delete, self.btn_reset, self.btn_save,
                  self.btn_find_dups):
            b.setEnabled(on)

    # ──────────────────────────────────────────────────────────────────
    def _rotate_selected(self, degrees: int):
        items = self.thumb_list.selectedItems()
        if not items:
            self.lbl_org_status.setText(
                "Seleccioná al menos una página para rotar.")
            return
        self._rotate_items(items, degrees)
        self.lbl_org_status.setText(
            f"{len(items)} página(s) rotada(s) {degrees:+d}°. "
            "Recordá guardar para aplicar.")

    def _rotate_items(self, items, degrees: int):
        for item in items:
            rot = (item.data(Qt.ItemDataRole.UserRole + 1) + degrees) % 360
            item.setData(Qt.ItemDataRole.UserRole + 1, rot)
            # Rotar la miniatura en pantalla
            icon = item.icon()
            pix = icon.pixmap(QSize(self.THUMB_EDGE, self.THUMB_EDGE))
            pix = pix.transformed(QTransform().rotate(degrees),
                                  Qt.TransformationMode.SmoothTransformation)
            item.setIcon(QIcon(pix))

    def _flip_alternate(self, resto: int):
        """Gira 180° una hoja por medio, según el orden que se ve en pantalla.

        resto=1 → las pares (2, 4, 6…); resto=0 → las impares (1, 3, 5…).
        """
        items = [self.thumb_list.item(i)
                 for i in range(resto, self.thumb_list.count(), 2)]
        if not items:
            return
        self._rotate_items(items, 180)
        cuales = "pares" if resto else "impares"
        self.lbl_org_status.setText(
            f"{len(items)} hoja(s) {cuales} giradas 180°. Mirá las miniaturas "
            "y, si quedó bien, tocá \"Guardar como...\". Si eran las otras, "
            "volvé a tocar el mismo botón para deshacerlo.")

    def _delete_selected(self):
        items = self.thumb_list.selectedItems()
        if not items:
            self.lbl_org_status.setText(
                "Seleccioná al menos una página para eliminar.")
            return
        if len(items) >= self.thumb_list.count():
            QMessageBox.warning(self, "Editar PDF",
                                "No podés eliminar todas las páginas.")
            return
        for item in items:
            self.thumb_list.takeItem(self.thumb_list.row(item))
        self.lbl_org_status.setText(
            f"{len(items)} página(s) quitada(s) de la vista. "
            "El archivo original no cambia hasta guardar.")

    def _find_duplicates(self):
        if not self._pdf_path or self.thumb_list.count() == 0:
            return
        if self._dup_worker and self._dup_worker.isRunning():
            return
        # Limpia resaltados de una búsqueda anterior
        for i in range(self.thumb_list.count()):
            self.thumb_list.item(i).setBackground(QBrush())
        self.lbl_org_status.setText("🔍 Buscando páginas duplicadas...")
        self.btn_find_dups.setEnabled(False)

        self._dup_worker = _DupWorker(self._pdf_path)
        self._dup_worker.log_msg.connect(self.lbl_org_status.setText)
        self._dup_worker.finished_ok.connect(self._dup_done)
        self._dup_worker.error.connect(self._dup_error)
        self._dup_worker.start()

    def _dup_done(self, pairs):
        self.btn_find_dups.setEnabled(True)
        if not pairs:
            self.lbl_org_status.setText(
                "No se encontraron páginas duplicadas.")
            return

        # Mapea índice original de página -> item actualmente en la lista
        by_orig = {}
        for i in range(self.thumb_list.count()):
            item = self.thumb_list.item(i)
            by_orig[item.data(Qt.ItemDataRole.UserRole)] = item

        highlight = QBrush(QColor("#fde68a"))   # amarillo suave
        explica = {"misma imagen": "es exactamente la misma imagen",
                   "texto": "de coincidencia de texto",
                   "imagen parecida": "de parecido visual"}
        seguros = []
        for a, b, sim, motivo in pairs:
            item_a, item_b = by_orig.get(a), by_orig.get(b)
            for item in (item_a, item_b):
                if item:
                    item.setBackground(highlight)
            if item_a and item_b:
                detalle = (explica[motivo] if motivo == "misma imagen"
                           else f"{sim * 100:.0f}% {explica[motivo]}")
                item_a.setToolTip(f"Repetida con la página {b + 1}: {detalle}")
                item_b.setToolTip(f"Repetida con la página {a + 1}: {detalle}")
            if motivo == "misma imagen":
                seguros.append((a, b))

        # Grupos de páginas idénticas (una hoja puede estar 3 o 4 veces):
        # se conserva la primera de cada grupo y sobran las demás.
        grupo = {}

        def raiz(x):
            while grupo.get(x, x) != x:
                x = grupo[x]
            return x
        for a, b in seguros:
            ra, rb = raiz(a), raiz(b)
            if ra != rb:
                grupo[max(ra, rb)] = min(ra, rb)
        sobran = [x for x in {v for par in seguros for v in par}
                  if raiz(x) != x and x in by_orig]

        dudosos = len(pairs) - len(seguros)
        texto = (f"⚠ {len(pairs)} par(es) de páginas repetidas, resaltadas en "
                 f"amarillo (pasá el mouse para ver con cuál).")
        if dudosos:
            texto += (f" {dudosos} par(es) son «posibles» (por texto o "
                      f"parecido): revisalos vos.")
        self.lbl_org_status.setText(texto)

        if not sobran:
            return
        resp = QMessageBox.question(
            self, "Buscar duplicados",
            f"Hay {len(sobran)} página(s) que son copia exacta de otra "
            f"(misma imagen, en el mismo lugar).\n\n"
            f"¿Las dejo seleccionadas para que las revises? Se conserva la "
            f"primera de cada grupo. No se borra nada hasta que toques "
            f"«🗑 Eliminar seleccionadas», y el archivo original no cambia "
            f"hasta guardar.")
        if resp != QMessageBox.StandardButton.Yes:
            return
        self.thumb_list.clearSelection()
        for x in sorted(sobran):
            by_orig[x].setSelected(True)
        self.thumb_list.scrollToItem(by_orig[min(sobran)])
        self.lbl_org_status.setText(
            texto + f"\n✔ {len(sobran)} copia(s) seleccionada(s): revisalas y "
            f"tocá «🗑 Eliminar seleccionadas».")

    def _dup_error(self, msg: str):
        self.btn_find_dups.setEnabled(True)
        QMessageBox.warning(self, "Buscar duplicados",
                            f"No se pudo analizar el PDF:\n{msg}")

    def _save_organized(self):
        if self.thumb_list.count() == 0:
            return
        default = os.path.splitext(self._pdf_path)[0] + "_editado.pdf"
        dst, _ = QFileDialog.getSaveFileName(
            self, "Guardar PDF editado", default, "Archivos PDF (*.pdf)")
        if not dst:
            return
        if os.path.abspath(dst) == os.path.abspath(self._pdf_path):
            QMessageBox.warning(
                self, "Editar PDF",
                "Elegí un nombre distinto al original "
                "(no se sobreescribe el archivo fuente).")
            return

        order, rotations = [], {}
        for i in range(self.thumb_list.count()):
            item = self.thumb_list.item(i)
            orig = item.data(Qt.ItemDataRole.UserRole)
            rot = item.data(Qt.ItemDataRole.UserRole + 1)
            order.append(orig)
            if rot % 360:
                rotations[orig] = rot

        from motors.motor_pdf_tools import apply_page_ops
        self._run_op(apply_page_ops, self._pdf_path, dst, order, rotations,
                     status_label=self.lbl_org_status,
                     success_prefix=f"✅ Guardado: {os.path.basename(dst)} — ")

    # ──────────────────────────────────────────────────────────────────
    # TAB 2: Unir archivos (varios PDF → uno solo)
    # ──────────────────────────────────────────────────────────────────

    def _build_merge_tab(self) -> QWidget:
        from motors.motor_pdf_tools import PDF_MAX_MB_DEFECTO
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(8)

        hint = QLabel(
            "Agregá los PDF que quieras unir, archivo por archivo o carpeta "
            "completa (podés repetir para ir sumando de varios lugares). "
            "El número de cada fila es el orden en que se van a unir. "
            "Arrastrá para cambiar el orden, usá \"↑ Subir\" / \"↓ Bajar\", "
            "o seleccioná un archivo y escribí a qué número lo querés mover. "
            "Se unen en el orden en que aparecen en la lista."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #64748b; font-size: 11px;")
        lay.addWidget(hint)

        top = QHBoxLayout()
        btn_add = QPushButton("➕ Agregar PDFs...")
        btn_add.clicked.connect(self._merge_add_files)
        top.addWidget(btn_add)
        btn_add_folder = QPushButton("📁 Agregar carpeta...")
        btn_add_folder.clicked.connect(self._merge_add_folder)
        top.addWidget(btn_add_folder)
        top.addStretch()
        lay.addLayout(top)

        list_row = QHBoxLayout()

        self.merge_list = QListWidget()
        self.merge_list.setDragDropMode(
            QAbstractItemView.DragDropMode.InternalMove)
        self.merge_list.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection)
        # Arrastrar para reordenar también debe renumerar la lista
        self.merge_list.model().rowsMoved.connect(
            lambda *a: self._merge_renumber())
        self.merge_list.setMinimumHeight(160)
        self.merge_list.itemSelectionChanged.connect(self._merge_update_preview)
        list_row.addWidget(self.merge_list, stretch=2)

        # Vista previa del archivo seleccionado, para identificarlo antes
        # de reordenarlo o eliminarlo.
        preview_col = QVBoxLayout()
        preview_col.addWidget(QLabel("Vista previa:"))
        self.lbl_merge_preview = QLabel("Seleccioná un archivo\nde la lista.")
        self.lbl_merge_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_merge_preview.setWordWrap(True)
        self.lbl_merge_preview.setStyleSheet(
            "color: #64748b; border: 1px solid #cbd5e1; border-radius: 6px;")
        self.lbl_merge_preview.setMinimumSize(200, 260)
        preview_col.addWidget(self.lbl_merge_preview, stretch=1)
        self.lbl_merge_preview_name = QLabel("")
        self.lbl_merge_preview_name.setWordWrap(True)
        self.lbl_merge_preview_name.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.lbl_merge_preview_name.setStyleSheet("font-size: 11px; color: #475569;")
        preview_col.addWidget(self.lbl_merge_preview_name)
        list_row.addLayout(preview_col, stretch=1)

        lay.addLayout(list_row, stretch=1)

        QShortcut(QKeySequence(Qt.Key.Key_Delete), self.merge_list,
                  activated=self._merge_remove_selected)

        btns_row1 = QHBoxLayout()
        self.btn_merge_up = QPushButton("↑ Subir")
        self.btn_merge_up.clicked.connect(lambda: self._merge_move(-1))
        self.btn_merge_down = QPushButton("↓ Bajar")
        self.btn_merge_down.clicked.connect(lambda: self._merge_move(1))
        self.btn_merge_remove = QPushButton("🗑 Quitar seleccionados")
        self.btn_merge_remove.clicked.connect(self._merge_remove_selected)
        self.btn_merge_clear = self._boton_limpiar(self._merge_clear_all)
        for b in (self.btn_merge_up, self.btn_merge_down,
                  self.btn_merge_remove, self.btn_merge_clear):
            btns_row1.addWidget(b)
        btns_row1.addStretch()
        lay.addLayout(btns_row1)

        # Cambiar orden a un número puntual (además de subir/bajar)
        row_pos = QHBoxLayout()
        row_pos.addWidget(QLabel("Mover el seleccionado a la posición:"))
        self.spin_merge_pos = QSpinBox()
        self.spin_merge_pos.setMinimum(1)
        self.spin_merge_pos.setMaximum(1)
        row_pos.addWidget(self.spin_merge_pos)
        btn_move_to = QPushButton("Mover")
        btn_move_to.clicked.connect(self._merge_move_to)
        row_pos.addWidget(btn_move_to)
        row_pos.addStretch()
        lay.addLayout(row_pos)

        # ── Ajustes antes de unir: duplicados + normalizar ────────────
        row_dup = QHBoxLayout()
        self.btn_merge_find_dups = QPushButton("🔍 Buscar duplicados")
        self.btn_merge_find_dups.setToolTip(
            "Compara el texto de cada archivo contra los demás para "
            "detectar la misma hoja fotografiada dos veces.")
        self.btn_merge_find_dups.clicked.connect(self._merge_find_duplicates)
        row_dup.addWidget(self.btn_merge_find_dups)
        row_dup.addStretch()
        lay.addLayout(row_dup)

        try:
            from motors.motor_ocr import is_available as _ocr_available
            ocr_ok = _ocr_available()
        except Exception:
            ocr_ok = False

        row_norm = QHBoxLayout()
        self.chk_merge_normalize = QCheckBox(
            "📐 Igualar tamaño de hoja y de letra antes de unir")
        self.chk_merge_normalize.setToolTip(
            "Útil si algunas fotos se sacaron más cerca o más lejos: antes "
            "de unir, reescribe cada PDF en hoja A4 con la letra pareja "
            "(usa OCR para medir el tamaño de letra)."
            if ocr_ok else
            "No disponible: falta tesseract.exe en la carpeta bin/.")
        self.chk_merge_normalize.setEnabled(ocr_ok)
        row_norm.addWidget(self.chk_merge_normalize)
        self.cmb_merge_norm_lang = QComboBox()
        self.cmb_merge_norm_lang.addItems(
            ["Español", "Inglés", "Portugués", "Francés", "Alemán", "Italiano"])
        self.cmb_merge_norm_lang.setEnabled(ocr_ok)
        row_norm.addWidget(self.cmb_merge_norm_lang)
        row_norm.addStretch()
        lay.addLayout(row_norm)

        # Rango: normalizar la lista completa o solo del archivo # al #
        row_norm_range = QHBoxLayout()
        row_norm_range.addWidget(QLabel("Aplicar a:"))
        self.rad_norm_all = QRadioButton("Todos")
        self.rad_norm_all.setChecked(True)
        self.rad_norm_range = QRadioButton("Del archivo")
        self._norm_range_group = QButtonGroup(self)
        self._norm_range_group.addButton(self.rad_norm_all)
        self._norm_range_group.addButton(self.rad_norm_range)
        row_norm_range.addWidget(self.rad_norm_all)
        row_norm_range.addWidget(self.rad_norm_range)
        self.spin_norm_from = QSpinBox()
        self.spin_norm_from.setMinimum(1)
        self.spin_norm_from.setMaximum(1)
        row_norm_range.addWidget(self.spin_norm_from)
        row_norm_range.addWidget(QLabel("al"))
        self.spin_norm_to = QSpinBox()
        self.spin_norm_to.setMinimum(1)
        self.spin_norm_to.setMaximum(1)
        row_norm_range.addWidget(self.spin_norm_to)
        row_norm_range.addStretch()
        lay.addLayout(row_norm_range)

        def _sync_norm_range_enabled():
            on = ocr_ok and self.chk_merge_normalize.isChecked()
            for w in (self.rad_norm_all, self.rad_norm_range):
                w.setEnabled(on)
            range_on = on and self.rad_norm_range.isChecked()
            self.spin_norm_from.setEnabled(range_on)
            self.spin_norm_to.setEnabled(range_on)

        def _on_range_checked(checked: bool):
            _sync_norm_range_enabled()
            if checked:
                # Punto de partida cómodo: todo el rango actual, a achicar
                # si se quiere normalizar solo una parte.
                self.spin_norm_to.setValue(self.merge_list.count() or 1)

        self.chk_merge_normalize.toggled.connect(lambda _: _sync_norm_range_enabled())
        self.rad_norm_all.toggled.connect(lambda _: _sync_norm_range_enabled())
        self.rad_norm_range.toggled.connect(_on_range_checked)
        _sync_norm_range_enabled()

        # ── ¿Partir el resultado? ────────────────────────────────────
        # Antes esto era un módulo aparte ("Texto / PDF"), donde unir y
        # partir venían pegados en un solo botón y no se entendía que
        # partir fuera opcional.
        grp_split = QGroupBox("¿Partir el resultado en varios archivos?")
        gsp = QVBoxLayout(grp_split)
        self._merge_split_group = QButtonGroup(self)
        self.rad_merge_nosplit = QRadioButton(
            "No: dejar un solo archivo con todo")
        self.rad_merge_nosplit.setChecked(True)
        self.rad_merge_split = QRadioButton(
            "Sí: partirlo en partes que no superen un tamaño")
        for r in (self.rad_merge_nosplit, self.rad_merge_split):
            self._merge_split_group.addButton(r)
            gsp.addWidget(r)

        row_sp = QHBoxLayout()
        row_sp.addSpacing(22)
        row_sp.addWidget(QLabel("Máximo por parte:"))
        self.spin_merge_mb = QDoubleSpinBox()
        self.spin_merge_mb.setRange(0.1, 2000.0)
        self.spin_merge_mb.setValue(PDF_MAX_MB_DEFECTO)
        self.spin_merge_mb.setSuffix(" MB")
        self.spin_merge_mb.setDecimals(1)
        self.spin_merge_mb.setEnabled(False)
        row_sp.addWidget(self.spin_merge_mb)
        btn_limite_merge = QPushButton(f"{PDF_MAX_MB_DEFECTO:g} MB")
        btn_limite_merge.setObjectName("ghostBtn")
        btn_limite_merge.setEnabled(False)
        btn_limite_merge.clicked.connect(
            lambda: self.spin_merge_mb.setValue(PDF_MAX_MB_DEFECTO))
        row_sp.addWidget(btn_limite_merge)
        row_sp.addStretch()
        gsp.addLayout(row_sp)
        self.rad_merge_split.toggled.connect(self.spin_merge_mb.setEnabled)
        self.rad_merge_split.toggled.connect(btn_limite_merge.setEnabled)
        lay.addWidget(grp_split)

        btns_row2 = QHBoxLayout()
        self.btn_merge_run = QPushButton("🔗 Unir y guardar...")
        self.btn_merge_run.setObjectName("primaryBtn")
        self.btn_merge_run.clicked.connect(self._merge_run)
        btns_row2.addWidget(self.btn_merge_run)
        btns_row2.addStretch()
        lay.addLayout(btns_row2)

        self.pbar_merge = QProgressBar()
        self.pbar_merge.setVisible(False)
        lay.addWidget(self.pbar_merge)

        self.lbl_merge_status = QLabel("")
        self.lbl_merge_status.setWordWrap(True)
        lay.addWidget(self.lbl_merge_status)
        return tab

    # ──────────────────────────────────────────────────────────────────
    def _merge_add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Elegir PDFs para unir", "", "Archivos PDF (*.pdf)")
        if not paths:
            return
        self._merge_add_paths(paths)

    def _merge_add_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Elegir carpeta con PDFs")
        if not folder:
            return
        paths = sorted(
            os.path.join(folder, f) for f in os.listdir(folder)
            if f.lower().endswith(".pdf")
        )
        if not paths:
            QMessageBox.information(
                self, "Agregar carpeta",
                "Esa carpeta no tiene archivos PDF.")
            return
        self._merge_add_paths(paths)

    def _merge_add_paths(self, paths):
        existing = {
            os.path.normcase(os.path.abspath(
                self.merge_list.item(i).data(Qt.ItemDataRole.UserRole)))
            for i in range(self.merge_list.count())
        }
        added = 0
        for path in paths:
            key = os.path.normcase(os.path.abspath(path))
            if key in existing:
                continue
            item = QListWidgetItem(os.path.basename(path))
            item.setData(Qt.ItemDataRole.UserRole, path)
            item.setToolTip(path)
            self.merge_list.addItem(item)
            existing.add(key)
            added += 1
        skipped = len(paths) - added
        msg = f"{self.merge_list.count()} archivo(s) en la lista."
        if skipped:
            msg += f" ({skipped} ya estaba(n) agregado(s), se omitieron)."
        self.lbl_merge_status.setText(msg)
        self._merge_after_change()

    def _merge_move(self, step: int):
        rows = sorted(r.row() for r in self.merge_list.selectedIndexes())
        if not rows:
            return
        for row in (rows if step < 0 else list(reversed(rows))):
            target = row + step
            if target < 0 or target >= self.merge_list.count():
                continue
            item = self.merge_list.takeItem(row)
            self.merge_list.insertItem(target, item)
            item.setSelected(True)
        self._merge_after_change()

    def _merge_move_to(self):
        items = self.merge_list.selectedItems()
        if len(items) != 1:
            QMessageBox.information(
                self, "Cambiar orden",
                "Seleccioná exactamente un archivo para moverlo "
                "a una posición puntual.")
            return
        item = items[0]
        row = self.merge_list.row(item)
        target = self.spin_merge_pos.value() - 1
        target = max(0, min(target, self.merge_list.count() - 1))
        if target == row:
            return
        self.merge_list.takeItem(row)
        self.merge_list.insertItem(target, item)
        item.setSelected(True)
        self._merge_after_change()

    def _merge_remove_selected(self):
        items = self.merge_list.selectedItems()
        if not items:
            self.lbl_merge_status.setText(
                "Seleccioná al menos un archivo para quitar.")
            return
        for item in items:
            self.merge_list.takeItem(self.merge_list.row(item))
        self.lbl_merge_status.setText(
            f"{len(items)} archivo(s) quitado(s) de la lista.")
        self._merge_after_change()

    def _merge_clear_all(self):
        self.merge_list.clear()
        self._merge_after_change()
        self.pbar_merge.setVisible(False)
        self.lbl_merge_status.setText("")

    def _merge_renumber(self):
        for i in range(self.merge_list.count()):
            item = self.merge_list.item(i)
            path = item.data(Qt.ItemDataRole.UserRole)
            item.setText(f"{i + 1}. {os.path.basename(path)}")

    def _merge_after_change(self):
        self._merge_renumber()
        count = max(1, self.merge_list.count())
        self.spin_merge_pos.setMaximum(count)
        self.spin_norm_from.setMaximum(count)
        self.spin_norm_to.setMaximum(count)
        # La lista cambió: cualquier resaltado de duplicados previo ya no vale
        for i in range(self.merge_list.count()):
            self.merge_list.item(i).setBackground(QBrush())
        self._merge_update_preview()

    def _merge_update_preview(self):
        items = self.merge_list.selectedItems()
        if len(items) != 1:
            self.lbl_merge_preview.setPixmap(QPixmap())
            self.lbl_merge_preview.setText(
                "Seleccioná un archivo\nde la lista."
                if not items else
                f"{len(items)} archivos seleccionados.")
            self.lbl_merge_preview_name.setText("")
            return

        item = items[0]
        path = item.data(Qt.ItemDataRole.UserRole)
        thumb = _render_first_page(path, max_edge=220)
        if thumb:
            img = QImage.fromData(thumb, "PNG")
            self.lbl_merge_preview.setText("")
            self.lbl_merge_preview.setPixmap(QPixmap.fromImage(img))
        else:
            self.lbl_merge_preview.setPixmap(QPixmap())
            self.lbl_merge_preview.setText("(no se pudo generar\nla vista previa)")
        self.lbl_merge_preview_name.setText(item.text())

    # ── Buscar duplicados (archivos completos) ──────────────────────────
    def _merge_find_duplicates(self):
        total = self.merge_list.count()
        if total < 2:
            self.lbl_merge_status.setText(
                "Agregá al menos dos archivos para poder compararlos.")
            return
        if self._merge_dup_worker and self._merge_dup_worker.isRunning():
            return
        for i in range(total):
            self.merge_list.item(i).setBackground(QBrush())
        self.lbl_merge_status.setText("🔍 Buscando archivos duplicados...")
        self.btn_merge_find_dups.setEnabled(False)

        paths = [self.merge_list.item(i).data(Qt.ItemDataRole.UserRole)
                 for i in range(total)]
        self._merge_dup_worker = _DupFilesWorker(paths)
        self._merge_dup_worker.finished_ok.connect(self._merge_dup_done)
        self._merge_dup_worker.error.connect(self._merge_dup_error)
        self._merge_dup_worker.start()

    def _merge_dup_done(self, pairs):
        self.btn_merge_find_dups.setEnabled(True)
        if not pairs:
            self.lbl_merge_status.setText(
                "No se encontraron archivos duplicados.")
            return

        removed = set()
        for a, b, sim in pairs:
            if a in removed or b in removed:
                continue
            item_a = self.merge_list.item(a)
            item_b = self.merge_list.item(b)
            if not item_a or not item_b:
                continue
            path_a = item_a.data(Qt.ItemDataRole.UserRole)
            path_b = item_b.data(Qt.ItemDataRole.UserRole)
            dlg = _DuplicatePairDialog(
                a + 1, os.path.basename(path_a), path_a,
                b + 1, os.path.basename(path_b), path_b,
                sim, parent=self)
            dlg.exec()
            if dlg.choice == "a":
                removed.add(a)
            elif dlg.choice == "b":
                removed.add(b)

        if removed:
            for idx in sorted(removed, reverse=True):
                self.merge_list.takeItem(idx)
            self._merge_after_change()
            self.lbl_merge_status.setText(
                f"Se quitaron {len(removed)} archivo(s) duplicado(s). "
                f"La lista quedó renumerada.")
        else:
            self.lbl_merge_status.setText(
                "Revisaste los posibles duplicados: no se quitó ninguno.")

    def _merge_dup_error(self, msg: str):
        self.btn_merge_find_dups.setEnabled(True)
        QMessageBox.warning(self, "Buscar duplicados",
                            f"No se pudo analizar los archivos:\n{msg}")

    # ── Unir (con normalización opcional antes de unir) ─────────────────
    def _merge_run(self):
        total = self.merge_list.count()
        if total < 2:
            QMessageBox.warning(self, "Unir archivos",
                                "Agregá al menos dos PDF para unir.")
            return
        if self._merge_worker and self._merge_worker.isRunning():
            QMessageBox.information(
                self, "Unir archivos",
                "Esperá a que termine la operación en curso.")
            return
        paths = [self.merge_list.item(i).data(Qt.ItemDataRole.UserRole)
                 for i in range(total)]
        default = os.path.join(os.path.dirname(paths[0]), "unido.pdf")
        dst, _ = QFileDialog.getSaveFileName(
            self, "Guardar PDF unido", default, "Archivos PDF (*.pdf)")
        if not dst:
            return
        if os.path.abspath(dst) in (os.path.abspath(p) for p in paths):
            QMessageBox.warning(
                self, "Unir archivos",
                "Elegí un nombre distinto a los archivos de origen.")
            return

        normalize = (self.chk_merge_normalize.isEnabled() and
                    self.chk_merge_normalize.isChecked())
        lang = self.cmb_merge_norm_lang.currentText()

        normalize_indices = None
        if normalize:
            if self.rad_norm_range.isChecked():
                start = self.spin_norm_from.value() - 1
                end = self.spin_norm_to.value() - 1
                if start > end:
                    start, end = end, start
                start = max(0, min(start, total - 1))
                end = max(0, min(end, total - 1))
                normalize_indices = set(range(start, end + 1))
            else:
                normalize_indices = set(range(total))

        # Los usa _merge_run_done para el informe y para partir
        self._merge_dst = dst
        self._merge_srcs = list(paths)
        self.btn_merge_run.setEnabled(False)
        self.pbar_merge.setVisible(True)
        self.pbar_merge.setRange(0, 1)
        self.pbar_merge.setValue(0)
        self._merge_worker = _MergeRunWorker(paths, dst, normalize_indices, lang)
        self._merge_worker.log_msg.connect(self.lbl_merge_status.setText)
        self._merge_worker.progress.connect(self._merge_run_progress)
        self._merge_worker.finished_ok.connect(self._merge_run_done)
        self._merge_worker.error.connect(self._merge_run_error)
        self._merge_worker.start()

    def _merge_run_progress(self, current: int, total: int):
        self.pbar_merge.setRange(0, total)
        self.pbar_merge.setValue(current)
        self.pbar_merge.setFormat(f"%v / %m")

    def _merge_run_done(self, msg: str):
        self.btn_merge_run.setEnabled(True)
        self.pbar_merge.setVisible(False)
        self.lbl_merge_status.setText(f"✅ {msg}")

        unido = getattr(self, "_merge_dst", "")
        origenes = list(getattr(self, "_merge_srcs", []))

        # Si no pidió partir, el informe se arma con el archivo unido
        if not self.rad_merge_split.isChecked():
            if unido and os.path.isfile(unido):
                self._generar_informe(
                    f"unir en un solo documento "
                    f"«{os.path.basename(unido)}» "
                    f"{_cant_pdf(len(origenes))} que se "
                    f"detallan a continuación, respetando el orden de la "
                    f"lista", origenes, [unido])
            return

        if not unido or not os.path.isfile(unido):
            return
        from motors.motor_pdf_tools import split_pdf_by_size
        limite = self.spin_merge_mb.value()
        frase = (f"unir {_cant_pdf(len(origenes))} que se detallan a "
                 f"continuación y partir el resultado en partes de hasta "
                 f"{limite:.1f} MB cada una")
        self._run_op(split_pdf_by_size, unido,
                     os.path.join(os.path.dirname(unido), "partes"),
                     limite,
                     status_label=self.lbl_merge_status,
                     success_prefix="✅ Unido y partido. ",
                     on_result=lambda r: self._generar_informe(
                         frase, origenes, self._archivos_de(r)))

    def _merge_run_error(self, msg: str):
        self.btn_merge_run.setEnabled(True)
        self.pbar_merge.setVisible(False)
        self.lbl_merge_status.setText("")
        QMessageBox.warning(self, "Unir archivos", f"Error:\n{msg}")

    # ──────────────────────────────────────────────────────────────────
    # TAB 3: Herramientas (comprimir / proteger / desbloquear / reparar)
    # ──────────────────────────────────────────────────────────────────

    def _build_tools_tab(self) -> QWidget:
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(10)

        # ── Comprimir ────────────────────────────────────────────────
        grp_c = QGroupBox("🗜  Comprimir PDF")
        gc = QVBoxLayout(grp_c)
        lbl_compress = QLabel(
            "Reduce el tamaño recomprimiendo las imágenes del PDF. "
            "El texto no pierde calidad.")
        lbl_compress.setWordWrap(True)
        gc.addWidget(lbl_compress)
        radios = QHBoxLayout()
        self.rad_light = QRadioButton("Suave (mejor calidad)")
        self.rad_medium = QRadioButton("Media (recomendado)")
        self.rad_strong = QRadioButton("Fuerte (mínimo peso)")
        self.rad_medium.setChecked(True)
        self._level_group = QButtonGroup(self)
        for r in (self.rad_light, self.rad_medium, self.rad_strong):
            self._level_group.addButton(r)
            radios.addWidget(r)
        radios.addStretch()
        gc.addLayout(radios)
        btn_compress = QPushButton("🗜 Elegir PDF y comprimir...")
        btn_compress.clicked.connect(self._do_compress)
        gc.addWidget(btn_compress)
        lay.addWidget(grp_c)

        # ── Normalizar hoja y letra ──────────────────────────────────
        lay.addWidget(self._build_normalize_group())

        # ── Proteger ─────────────────────────────────────────────────
        grp_p = QGroupBox("🔒  Proteger con contraseña")
        gp = QVBoxLayout(grp_p)
        row_p = QHBoxLayout()
        row_p.addWidget(QLabel("Contraseña:"))
        self.txt_pass_set = QLineEdit()
        self.txt_pass_set.setEchoMode(QLineEdit.EchoMode.Password)
        row_p.addWidget(self.txt_pass_set)
        row_p.addWidget(QLabel("Repetir:"))
        self.txt_pass_set2 = QLineEdit()
        self.txt_pass_set2.setEchoMode(QLineEdit.EchoMode.Password)
        row_p.addWidget(self.txt_pass_set2)
        gp.addLayout(row_p)
        btn_protect = QPushButton("🔒 Elegir PDF y proteger...")
        btn_protect.clicked.connect(self._do_protect)
        gp.addWidget(btn_protect)
        lay.addWidget(grp_p)

        # ── Desbloquear ──────────────────────────────────────────────
        grp_u = QGroupBox("🔓  Quitar contraseña (conociéndola)")
        gu = QVBoxLayout(grp_u)
        row_u = QHBoxLayout()
        row_u.addWidget(QLabel("Contraseña actual:"))
        self.txt_pass_unlock = QLineEdit()
        self.txt_pass_unlock.setEchoMode(QLineEdit.EchoMode.Password)
        row_u.addWidget(self.txt_pass_unlock)
        gu.addLayout(row_u)
        btn_unlock = QPushButton("🔓 Elegir PDF y quitar contraseña...")
        btn_unlock.clicked.connect(self._do_unlock)
        gu.addWidget(btn_unlock)
        lay.addWidget(grp_u)

        # La firma vive en su propia solapa "🖋 Firmar": necesita espacio
        # para la vista previa y no es una herramienta más.

        # ── Reparar ──────────────────────────────────────────────────
        grp_r = QGroupBox("🩹  Reparar PDF dañado")
        gr = QVBoxLayout(grp_r)
        lbl_repair = QLabel(
            "Intenta recuperar un PDF que no abre o muestra errores, "
            "reescribiendo su estructura interna.")
        lbl_repair.setWordWrap(True)
        gr.addWidget(lbl_repair)
        btn_repair = QPushButton("🩹 Elegir PDF y reparar...")
        btn_repair.clicked.connect(self._do_repair)
        gr.addWidget(btn_repair)
        lay.addWidget(grp_r)

        self.lbl_tools_status = QLabel("")
        self.lbl_tools_status.setWordWrap(True)
        lay.addWidget(self.lbl_tools_status)

        row_limpiar = QHBoxLayout()
        row_limpiar.addWidget(self._boton_limpiar(self._tools_clear))
        row_limpiar.addStretch()
        lay.addLayout(row_limpiar)
        lay.addStretch()
        return tab

    def _tools_clear(self):
        for campo in (self.txt_pass_set, self.txt_pass_set2,
                      self.txt_pass_unlock):
            campo.clear()
        self.lbl_tools_status.setText("")

    # ──────────────────────────────────────────────────────────────────
    # TAB 4: Firmar (elegir PDF, página y posición del sello)
    # ──────────────────────────────────────────────────────────────────

    def _build_sign_tab(self) -> QWidget:
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(10)

        self._sign_src = ""
        self._sign_pages = 0
        self._sign_position = "abajo-derecha"

        # ── 1. Elegir el PDF ─────────────────────────────────────────
        grp_pdf = QGroupBox("1️⃣  Elegí el PDF que querés firmar")
        gp = QHBoxLayout(grp_pdf)
        btn_pick = QPushButton("📄 Elegir PDF...")
        btn_pick.clicked.connect(self._pick_sign_src)
        gp.addWidget(btn_pick)
        self.lbl_sign_src = QLabel("(ninguno elegido)")
        self.lbl_sign_src.setStyleSheet("color:#64748b;")
        self.lbl_sign_src.setWordWrap(True)
        gp.addWidget(self.lbl_sign_src, stretch=1)
        gp.addWidget(self._boton_limpiar(self._sign_clear))
        lay.addWidget(grp_pdf)

        # ── 2. Dónde va el sello ─────────────────────────────────────
        grp_pos = QGroupBox("2️⃣  Dónde querés que se vea la firma")
        gpos = QHBoxLayout(grp_pos)

        # Izquierda: vista previa
        col_prev = QVBoxLayout()
        self.lbl_sign_preview = QLabel("Elegí un PDF para ver la vista previa")
        self.lbl_sign_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_sign_preview.setMinimumSize(300, 380)
        self.lbl_sign_preview.setStyleSheet(
            "border:1px solid #cbd5e1; border-radius:6px; "
            "background:#f8fafc; color:#94a3b8;")
        col_prev.addWidget(self.lbl_sign_preview)
        gpos.addLayout(col_prev)

        # Derecha: página + grilla de posiciones
        col_ctl = QVBoxLayout()

        col_ctl.addWidget(QLabel("<b>Página donde se ve el sello</b>"))
        self.rad_page_first = QRadioButton("La primera página")
        self.rad_page_last = QRadioButton("La última página")
        self.rad_page_num = QRadioButton("Una página en particular:")
        self.rad_page_first.setChecked(True)
        self._page_group = QButtonGroup(self)
        for r in (self.rad_page_first, self.rad_page_last, self.rad_page_num):
            self._page_group.addButton(r)
            col_ctl.addWidget(r)
            r.toggled.connect(self._update_sign_preview)

        row_num = QHBoxLayout()
        row_num.addSpacing(20)
        self.spin_sign_page = QSpinBox()
        self.spin_sign_page.setMinimum(1)
        self.spin_sign_page.setMaximum(1)
        self.spin_sign_page.setEnabled(False)
        self.spin_sign_page.valueChanged.connect(self._update_sign_preview)
        self.rad_page_num.toggled.connect(self.spin_sign_page.setEnabled)
        row_num.addWidget(self.spin_sign_page)
        row_num.addStretch()
        col_ctl.addLayout(row_num)

        aclara = QLabel(
            "La firma protege <b>todo</b> el documento; el sello se ve en "
            "una hoja, como en los firmadores oficiales.")
        aclara.setWordWrap(True)
        aclara.setStyleSheet("color:#64748b; font-size:11px;")
        col_ctl.addWidget(aclara)

        col_ctl.addSpacing(8)
        col_ctl.addWidget(QLabel("<b>Posición en la hoja</b>"))
        col_ctl.addLayout(self._build_position_grid())

        self.chk_sign_visible = QCheckBox("Mostrar el sello en el PDF")
        self.chk_sign_visible.setChecked(True)
        self.chk_sign_visible.setToolTip(
            "Si lo desmarcás, la firma es igual de válida pero no se ve "
            "ningún recuadro en el documento.")
        self.chk_sign_visible.toggled.connect(self._update_sign_preview)
        col_ctl.addSpacing(8)
        col_ctl.addWidget(self.chk_sign_visible)

        # ── La leyenda: cargo y dependencia, debajo del nombre ───────
        # El nombre sale del certificado y no se puede tocar; esto es lo que
        # cada uno le suma. Queda guardado para la próxima firma.
        from PyQt6.QtWidgets import QPlainTextEdit
        from PyQt6.QtCore import QTimer
        from PyQt6.QtGui import QFont
        col_ctl.addSpacing(8)
        col_ctl.addWidget(QLabel("<b>Leyenda debajo de tu nombre</b> (opcional)"))
        self.txt_sign_leyenda = QPlainTextEdit()
        self.txt_sign_leyenda.setPlaceholderText(
            "Tu cargo y dependencia, un renglón por línea. Por ejemplo:\n"
            "Cargo\n"
            "Área o dependencia\n"
            "Ciudad")
        self.txt_sign_leyenda.setFixedHeight(84)
        self.txt_sign_leyenda.setToolTip(
            "Lo que escribas acá sale en el sello, debajo de tu nombre, con "
            "los mismos renglones.\nQueda guardado: la próxima vez ya está "
            "puesto. Si lo dejás vacío, el sello lleva sólo nombre y fecha.")
        try:
            from core.config_manager import config
            self.txt_sign_leyenda.setPlainText(
                str(config.get("sign_leyenda", "") or ""))
        except Exception:
            pass
        col_ctl.addWidget(self.txt_sign_leyenda)

        col_ctl.addWidget(QLabel("Así va a decir el sello:"))
        self.lbl_sign_texto = QLabel("")
        self.lbl_sign_texto.setFont(QFont("Courier New", 8))
        self.lbl_sign_texto.setTextFormat(Qt.TextFormat.PlainText)
        self.lbl_sign_texto.setStyleSheet(
            "background:#ffffff; color:#0f172a; border:1.5px solid #0f172a; "
            "padding:8px;")
        col_ctl.addWidget(self.lbl_sign_texto)

        # Se guarda sola un momento después de dejar de escribir.
        self._leyenda_timer = QTimer(self)
        self._leyenda_timer.setSingleShot(True)
        self._leyenda_timer.timeout.connect(self._guardar_leyenda)
        self.txt_sign_leyenda.textChanged.connect(self._on_leyenda_cambiada)
        self.chk_sign_visible.toggled.connect(
            lambda on: (self.txt_sign_leyenda.setEnabled(on),
                        self.lbl_sign_texto.setEnabled(on)))
        self._mostrar_texto_del_sello()

        col_ctl.addStretch()
        gpos.addLayout(col_ctl, stretch=1)
        lay.addWidget(grp_pos)

        # ── 3. Con qué firmar ────────────────────────────────────────
        lay.addWidget(self._build_sign_group())

        self.lbl_sign_status = QLabel("")
        self.lbl_sign_status.setWordWrap(True)
        lay.addWidget(self.lbl_sign_status)

        lay.addStretch()
        return tab

    def _build_position_grid(self):
        """Grilla 3×3 con las posiciones del sello, como en una hoja."""
        from PyQt6.QtWidgets import QGridLayout
        from motors.motor_pdf_tools import SIGN_POSITIONS

        grid = QGridLayout()
        grid.setSpacing(4)
        self._pos_group = QButtonGroup(self)
        self._pos_buttons = {}

        for i, (clave, etiqueta) in enumerate(SIGN_POSITIONS):
            btn = QPushButton(etiqueta)
            btn.setCheckable(True)
            btn.setMinimumWidth(104)
            btn.setToolTip(f"Poner el sello: {etiqueta.lower()}")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            if clave == self._sign_position:
                btn.setChecked(True)
            btn.clicked.connect(
                lambda _checked, c=clave: self._set_sign_position(c))
            self._pos_group.addButton(btn)
            self._pos_buttons[clave] = btn
            grid.addWidget(btn, i // 3, i % 3)

        return grid

    def _set_sign_position(self, clave: str):
        self._sign_position = clave
        self._update_sign_preview()

    def _pick_sign_src(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Elegí el PDF a firmar", "", "Archivos PDF (*.pdf)")
        if not path:
            return
        from motors.motor_pdf_tools import page_count
        try:
            total = page_count(path)
        except Exception as e:
            QMessageBox.warning(self, "Firmar PDF",
                                f"No pude abrir ese PDF:\n{e}")
            return

        self._sign_src = path
        self._sign_pages = total
        self.lbl_sign_src.setText(
            f"<b>{os.path.basename(path)}</b><br>{total} página(s)")
        self.spin_sign_page.setMaximum(max(total, 1))
        self.spin_sign_page.setValue(1)
        self._update_sign_preview()

    def _sign_clear(self):
        """Saca el PDF elegido; el certificado o el token quedan como están."""
        self._sign_src = ""
        self._sign_pages = 0
        self.lbl_sign_src.setText("(ninguno elegido)")
        self.spin_sign_page.setValue(1)
        self.spin_sign_page.setMaximum(1)
        self.lbl_sign_preview.setText("Elegí un PDF para ver la vista previa")
        self.lbl_sign_status.setText("")

    def _sign_page_index(self) -> int:
        """Índice (base 0) de la página donde va el sello."""
        if self.rad_page_last.isChecked():
            return max(self._sign_pages - 1, 0)
        if self.rad_page_num.isChecked():
            return max(0, min(self.spin_sign_page.value() - 1,
                              max(self._sign_pages - 1, 0)))
        return 0

    # ── Leyenda del sello ─────────────────────────────────────────────

    def _sign_leyenda(self) -> str:
        return self.txt_sign_leyenda.toPlainText().strip()

    def _mostrar_texto_del_sello(self):
        """El texto del sello tal como va a salir, con un nombre de ejemplo."""
        from datetime import datetime
        from motors.motor_pdf_tools import texto_del_sello
        self.lbl_sign_texto.setText(texto_del_sello(
            self._sign_leyenda(), "(tu nombre, como figura en el certificado)",
            datetime.now().strftime("%Y-%m-%d %H:%M:%S") + " -03"))

    def _on_leyenda_cambiada(self):
        self._mostrar_texto_del_sello()
        self._leyenda_timer.start(600)      # al dejar de escribir: ver abajo

    def _guardar_leyenda(self):
        """Guarda la leyenda y acomoda el recuadro de la vista previa, que
        crece con los renglones."""
        try:
            from core.config_manager import config
            if config.get("sign_leyenda", "") != self._sign_leyenda():
                config.set("sign_leyenda", self._sign_leyenda())
        except Exception:
            pass
        self._update_sign_preview()

    def _update_sign_preview(self, *_):
        """Dibuja la página elegida con el recuadro del sello encima."""
        if not self._sign_src:
            return
        from PyQt6.QtGui import QPixmap, QPainter, QColor, QPen
        from motors.motor_pdf_tools import render_page, stamp_preview_rect

        pagina = self._sign_page_index()
        try:
            png, img_w, img_h, pt_w, pt_h = render_page(
                self._sign_src, pagina, max_edge=380)
        except Exception as e:
            self.lbl_sign_preview.setText(f"No pude previsualizar:\n{e}")
            return

        pix = QPixmap()
        pix.loadFromData(png)

        if self.chk_sign_visible.isChecked():
            x, y, w, h = stamp_preview_rect(pt_w, pt_h, img_w, img_h,
                                            self._sign_position,
                                            self._sign_leyenda())
            pintor = QPainter(pix)
            pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
            pintor.setBrush(QColor(79, 70, 229, 60))       # índigo translúcido
            pintor.setPen(QPen(QColor(79, 70, 229), 2))
            pintor.drawRect(x, y, w, h)
            pintor.setPen(QPen(QColor(49, 46, 129)))
            fuente = pintor.font()
            fuente.setPointSize(7)
            fuente.setBold(True)
            pintor.setFont(fuente)
            pintor.drawText(x, y, w, h,
                            int(Qt.AlignmentFlag.AlignCenter), "FIRMA")
            pintor.end()

        self.lbl_sign_preview.setPixmap(pix)
        self.lbl_sign_preview.setText("")

    # ──────────────────────────────────────────────────────────────────
    def _build_sign_group(self) -> QGroupBox:
        """Grupo 'Firmar digitalmente': certificado .pfx o token USB."""
        grp = QGroupBox("🖋  Firmar digitalmente (PAdES)")
        gs = QVBoxLayout(grp)

        try:
            from motors.motor_pdf_tools import is_signing_available
            available = is_signing_available()
        except Exception:
            available = False
        if not available:
            gs.addWidget(QLabel(
                "No disponible: falta el paquete 'pyhanko'."))
            return grp

        # Modo: archivo o token
        mode_row = QHBoxLayout()
        self.rad_sign_pfx = QRadioButton("Certificado en archivo (.pfx / .p12)")
        self.rad_sign_token = QRadioButton("Token USB (PKCS#11)")
        self.rad_sign_pfx.setChecked(True)
        self._sign_mode_group = QButtonGroup(self)
        for r in (self.rad_sign_pfx, self.rad_sign_token):
            self._sign_mode_group.addButton(r)
            mode_row.addWidget(r)
        mode_row.addStretch()
        gs.addLayout(mode_row)

        # ── Sub-panel PFX ────────────────────────────────────────────
        self._sign_pfx_widget = QWidget()
        pf = QHBoxLayout(self._sign_pfx_widget)
        pf.setContentsMargins(0, 0, 0, 0)
        self.btn_pick_pfx = QPushButton("📄 Elegir certificado...")
        self.btn_pick_pfx.clicked.connect(self._pick_pfx)
        pf.addWidget(self.btn_pick_pfx)
        self.lbl_pfx = QLabel("(ninguno)")
        self.lbl_pfx.setStyleSheet("color: #64748b;")
        pf.addWidget(self.lbl_pfx, stretch=1)
        pf.addWidget(QLabel("Contraseña:"))
        self.txt_pfx_pass = QLineEdit()
        self.txt_pfx_pass.setEchoMode(QLineEdit.EchoMode.Password)
        pf.addWidget(self.txt_pfx_pass)
        gs.addWidget(self._sign_pfx_widget)

        # ── Sub-panel Token ──────────────────────────────────────────
        # El usuario final sólo enchufa el token y escribe el PIN: la app
        # detecta sola el driver. Lo técnico vive en "Opciones avanzadas".
        self._sign_token_widget = QWidget()
        tk = QVBoxLayout(self._sign_token_widget)
        tk.setContentsMargins(0, 0, 0, 0)

        # Estado del token, en castellano llano
        self.lbl_token_status = QLabel("Buscando el token...")
        self.lbl_token_status.setWordWrap(True)
        self.lbl_token_status.setStyleSheet(
            "padding: 6px; border-radius: 4px; background: #f1f5f9;")
        tk.addWidget(self.lbl_token_status)

        row_btns = QHBoxLayout()
        btn_redetect = QPushButton("🔄 Buscar el token de nuevo")
        btn_redetect.clicked.connect(self._refresh_token_status)
        row_btns.addWidget(btn_redetect)
        self.btn_probe_token = QPushButton("🔍 Probar token")
        self.btn_probe_token.setToolTip(
            "Se conecta al token y muestra tus certificados, sin firmar nada.")
        self.btn_probe_token.clicked.connect(self._probe_token)
        row_btns.addWidget(self.btn_probe_token)
        # Sólo aparece cuando falta el programa del fabricante.
        self.btn_token_download = QPushButton("⬇ Cómo instalarlo")
        self.btn_token_download.setToolTip(
            "Te abre la página de descarga y te muestra el paso a paso.")
        self.btn_token_download.clicked.connect(self._show_download_guide)
        self.btn_token_download.setVisible(False)
        row_btns.addWidget(self.btn_token_download)
        row_btns.addStretch()
        tk.addLayout(row_btns)

        row_pin = QHBoxLayout()
        row_pin.addWidget(QLabel("PIN del token:"))
        self.txt_token_pin = QLineEdit()
        self.txt_token_pin.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_token_pin.setPlaceholderText(
            "el mismo PIN que te dieron con el token")
        row_pin.addWidget(self.txt_token_pin, stretch=1)
        tk.addLayout(row_pin)

        # ── Opciones avanzadas (ocultas por defecto) ─────────────────
        from PyQt6.QtWidgets import QCheckBox as _QCheckBox, QComboBox
        self.chk_token_adv = _QCheckBox("Opciones avanzadas")
        tk.addWidget(self.chk_token_adv)

        self._token_adv_widget = QWidget()
        adv = QVBoxLayout(self._token_adv_widget)
        adv.setContentsMargins(16, 0, 0, 0)
        row_dll = QHBoxLayout()
        row_dll.addWidget(QLabel("Driver del token (DLL):"))
        self.cmb_token_dll = QComboBox()
        self.cmb_token_dll.setEditable(True)
        self.cmb_token_dll.lineEdit().setPlaceholderText(
            "vacío = detectar automáticamente")
        row_dll.addWidget(self.cmb_token_dll, stretch=1)
        btn_dll = QPushButton("...")
        btn_dll.setMaximumWidth(32)
        btn_dll.clicked.connect(self._pick_token_dll)
        row_dll.addWidget(btn_dll)
        adv.addLayout(row_dll)
        row_lbl = QHBoxLayout()
        row_lbl.addWidget(QLabel("Certificado (opcional):"))
        self.txt_token_label = QLineEdit()
        self.txt_token_label.setPlaceholderText("vacío = usar el primero")
        row_lbl.addWidget(self.txt_token_label, stretch=1)
        adv.addLayout(row_lbl)
        self._token_adv_widget.setVisible(False)
        self.chk_token_adv.toggled.connect(self._token_adv_widget.setVisible)
        tk.addWidget(self._token_adv_widget)

        self._sign_token_widget.setVisible(False)
        gs.addWidget(self._sign_token_widget)

        self.rad_sign_pfx.toggled.connect(
            lambda on: (self._sign_pfx_widget.setVisible(on),
                        self._sign_token_widget.setVisible(not on),
                        None if on else self._refresh_token_status()))

        # ── Opciones comunes ─────────────────────────────────────────
        # El sello visible y la página se eligen arriba, sobre la vista
        # previa: acá queda sólo lo propio del certificado.
        row_opts = QHBoxLayout()
        row_opts.addWidget(QLabel("Motivo (opcional):"))
        self.txt_sign_reason = QLineEdit()
        self.txt_sign_reason.setPlaceholderText("p. ej.: Conformidad")
        row_opts.addWidget(self.txt_sign_reason)
        gs.addLayout(row_opts)

        btn_sign = QPushButton("🖋 Firmar el PDF")
        btn_sign.clicked.connect(self._do_sign)
        gs.addWidget(btn_sign)

        self._pfx_path = ""
        return grp

    def _pick_pfx(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Elegir certificado", "",
            "Certificados (*.pfx *.p12);;Todos (*.*)")
        if path:
            self._pfx_path = path
            self.lbl_pfx.setText(os.path.basename(path))

    def _pick_token_dll(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Elegir DLL PKCS#11 del token",
            r"C:\Windows\System32", "DLL (*.dll)")
        if path:
            self.cmb_token_dll.setEditText(path)

    # ── Token: detección y prueba ─────────────────────────────────────
    _TOKEN_STATUS_STYLE = {
        "listo":       ("#166534", "#dcfce7"),   # verde
        "sin_token":   ("#9a3412", "#ffedd5"),   # naranja
        "sin_driver":  ("#9a3412", "#ffedd5"),
        "driver_otra_marca": ("#9a3412", "#ffedd5"),
        "sin_pyhanko": ("#991b1b", "#fee2e2"),   # rojo
    }

    def _refresh_token_status(self):
        """Detecta el token y muestra en castellano qué falta, si falta algo."""
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QCursor
        from PyQt6.QtWidgets import QApplication

        QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
        try:
            from motors.motor_pdf_tools import diagnose_token
            diag = diagnose_token()
        except Exception as e:
            diag = {"estado": "sin_pyhanko", "titulo": "Error al detectar",
                    "mensaje": str(e), "modulos": []}
        finally:
            QApplication.restoreOverrideCursor()

        icono = "✅" if diag["estado"] == "listo" else "⚠"
        color, fondo = self._TOKEN_STATUS_STYLE.get(
            diag["estado"], ("#334155", "#f1f5f9"))
        self.lbl_token_status.setText(
            f"{icono}  <b>{diag['titulo']}</b><br>"
            + diag["mensaje"].replace("\n\n", "<br>").replace("\n", " "))
        self.lbl_token_status.setStyleSheet(
            f"padding: 6px; border-radius: 4px; "
            f"color: {color}; background: {fondo};")

        # Cargar los drivers detectados en el combo avanzado
        try:
            from motors.motor_pdf_tools import describe_pkcs11_module
            actual = self.cmb_token_dll.currentText().strip()
            self.cmb_token_dll.clear()
            for dll in diag.get("modulos", []):
                self.cmb_token_dll.addItem(describe_pkcs11_module(dll), dll)
            self.cmb_token_dll.setEditText(actual)
        except Exception:
            pass

        self.btn_probe_token.setEnabled(diag["estado"] != "sin_pyhanko")

        # Guía de descarga: sólo tiene sentido si falta el programa del token
        self._token_download = diag.get("descarga")
        self.btn_token_download.setVisible(bool(self._token_download))
        # Si el instalador de esa marca viaja con el programa, el botón lo
        # dice: no hay nada que ir a buscar.
        if self._token_download and self._token_download.get("instalador"):
            self.btn_token_download.setText("⬇ Instalarlo (viene con el programa)")
            self.btn_token_download.setToolTip(
                "El instalador de tu token viene con el programa:\n"
                "te muestra los pasos y lo abre desde acá.")
        else:
            self.btn_token_download.setText("⬇ Cómo instalarlo")
            self.btn_token_download.setToolTip(
                "Te abre la página de descarga y te muestra el paso a paso.")
        return diag

    def _show_download_guide(self):
        """Muestra el paso a paso y ofrece abrir la página de descarga."""
        guia = getattr(self, "_token_download", None)
        if not guia:
            return

        from motors.motor_pdf_tools import format_download_guide
        from PyQt6.QtWidgets import QDialog, QPlainTextEdit, QDialogButtonBox
        from PyQt6.QtGui import QFont

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Cómo instalar {guia['programa']}")
        dlg.resize(660, 480)
        lay = QVBoxLayout(dlg)

        incluido = guia.get("instalador", "")
        cabecera = QLabel(
            f"Para firmar con tu token hace falta instalar "
            f"<b>{guia['programa']}</b>.<br>"
            + ("<b>Viene con el programa</b>: no hay que descargar nada."
               if incluido else f"Se descarga de: {guia['sitio']}"))
        cabecera.setWordWrap(True)
        lay.addWidget(cabecera)

        vista = QPlainTextEdit(format_download_guide(guia))
        vista.setReadOnly(True)
        vista.setFont(QFont("Segoe UI", 10))
        vista.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        lay.addWidget(vista)

        botones = QDialogButtonBox()
        if incluido:
            btn_instalar = botones.addButton(
                "▶ Instalar ahora", QDialogButtonBox.ButtonRole.ActionRole)
            btn_instalar.setObjectName("primaryBtn")
            btn_instalar.setToolTip(
                "Abre el instalador que viene con el programa.")
            btn_instalar.clicked.connect(
                lambda: self._instalar_programa_del_token(guia, dlg))
        btn_abrir = botones.addButton(
            "🌐 Abrir la página de descarga",
            QDialogButtonBox.ButtonRole.ActionRole)
        btn_buscar = botones.addButton(
            "📁 Ya lo descargué: ¿cuál abro?",
            QDialogButtonBox.ButtonRole.ActionRole)
        btn_buscar.setToolTip(
            "Elegís la carpeta que descargaste y te digo exactamente qué "
            "archivo tenés que abrir, sea la marca que sea.")
        btn_copiar = botones.addButton(
            "📋 Copiar el link", QDialogButtonBox.ButtonRole.ActionRole)
        botones.addButton(QDialogButtonBox.StandardButton.Close)
        botones.rejected.connect(dlg.reject)

        def _abrir():
            from PyQt6.QtGui import QDesktopServices
            from PyQt6.QtCore import QUrl
            QDesktopServices.openUrl(QUrl(guia["url"]))

        def _copiar():
            from PyQt6.QtWidgets import QApplication
            QApplication.clipboard().setText(guia["url"])
            btn_copiar.setText("📋 ¡Link copiado!")

        btn_abrir.clicked.connect(_abrir)
        btn_copiar.clicked.connect(_copiar)
        btn_buscar.clicked.connect(lambda: self._find_installer(dlg))
        # Con el instalador a mano, lo de descargar sobra: se esconde para
        # que quede un solo botón que tocar.
        for btn in (btn_abrir, btn_buscar, btn_copiar):
            btn.setVisible(not incluido)
        lay.addWidget(botones)
        dlg.exec()

    def _instalar_programa_del_token(self, guia, padre=None):
        """Abre el instalador del token que viaja con el programa."""
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QCursor
        from PyQt6.QtWidgets import QApplication
        from motors.motor_pdf_tools import verificar_instalador_incluido

        padre = padre or self
        # Es un programa que se va a ejecutar como administrador: antes se
        # comprueba que siga teniendo la firma digital de su fabricante.
        QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
        try:
            bien, detalle = verificar_instalador_incluido(guia["programa"])
        finally:
            QApplication.restoreOverrideCursor()
        if not bien:
            QMessageBox.warning(
                padre, "Instalar el programa del token",
                "No se abrió el instalador porque no pasó el control de "
                f"autenticidad.\n\n{detalle}\n\n"
                "Pedile el instalador a quien te entregó el token.")
            return
        try:
            os.startfile(guia["instalador"])
        except Exception as e:
            QMessageBox.warning(
                padre, "Instalar el programa del token",
                f"No se pudo abrir el instalador.\n\n{e}")
            return
        QMessageBox.information(
            padre, "Instalar el programa del token",
            "Se abrió el instalador (puede tardar unos segundos en aparecer, "
            "y Windows te va a preguntar si permitís los cambios: decí que sí).\n\n"
            "Cuando termine:\n"
            "  1. Reiniciá la computadora.\n"
            "  2. Enchufá el token y volvé a abrir el Conversor.\n"
            '  3. En 📄 PDF → 🖋 Firmar, tocá "🔄 Buscar el token de nuevo".')

    def _find_installer(self, padre=None):
        """Busca el instalador en la carpeta descargada y dice cuál abrir.

        No depende de la marca: reconoce al instalador por sus características
        (extensión, arquitectura, tamaño y firma digital).
        """
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QCursor
        from PyQt6.QtWidgets import (QApplication, QDialog, QPlainTextEdit,
                                     QDialogButtonBox)
        from PyQt6.QtGui import QFont

        carpeta = QFileDialog.getExistingDirectory(
            padre or self,
            "Elegí la carpeta que descargaste (la del programa del token)")
        if not carpeta:
            return

        QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
        try:
            from motors.motor_pdf_tools import (find_downloaded_installer,
                                                format_installer_choice)
            candidatos = find_downloaded_installer(carpeta)
            texto = format_installer_choice(candidatos)
        except Exception as e:
            candidatos, texto = [], f"No pude revisar esa carpeta: {e}"
        finally:
            QApplication.restoreOverrideCursor()

        dlg = QDialog(padre or self)
        dlg.setWindowTitle("Cuál archivo abrir")
        dlg.resize(680, 480)
        lay = QVBoxLayout(dlg)
        vista = QPlainTextEdit(texto)
        vista.setReadOnly(True)
        vista.setFont(QFont("Segoe UI", 10))
        lay.addWidget(vista)

        botones = QDialogButtonBox()
        if candidatos:
            btn_mostrar = botones.addButton(
                "📂 Mostrarme el archivo",
                QDialogButtonBox.ButtonRole.ActionRole)
            btn_mostrar.clicked.connect(
                lambda: self._reveal_in_explorer(candidatos[0]["path"]))
        botones.addButton(QDialogButtonBox.StandardButton.Close)
        botones.rejected.connect(dlg.reject)
        lay.addWidget(botones)
        dlg.exec()

    @staticmethod
    def _reveal_in_explorer(path: str):
        """Abre el Explorador con ese archivo ya seleccionado."""
        import subprocess
        try:
            subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
        except Exception:
            from PyQt6.QtGui import QDesktopServices
            from PyQt6.QtCore import QUrl
            QDesktopServices.openUrl(
                QUrl.fromLocalFile(os.path.dirname(path)))

    def _token_dll(self) -> str:
        """DLL elegida a mano en avanzadas, o '' para detección automática."""
        texto = self.cmb_token_dll.currentText().strip()
        if not texto:
            return ""
        # Si eligió un ítem de la lista, el path real va en userData
        idx = self.cmb_token_dll.currentIndex()
        if idx >= 0 and self.cmb_token_dll.itemText(idx) == texto:
            datos = self.cmb_token_dll.itemData(idx)
            if datos:
                return str(datos)
        return texto

    def _token_pin(self) -> str:
        """PIN escrito, sin espacios sobrantes.

        Un espacio pegado al copiar hace que el token rechace el PIN y gaste
        un reintento, sin que el usuario tenga forma de darse cuenta.
        """
        return self.txt_token_pin.text().strip()

    def _probe_token(self):
        """Abre el token y muestra sus certificados, sin firmar nada."""
        pin = self._token_pin()
        if not pin:
            resp = QMessageBox.question(
                self, "Probar token",
                "No escribiste el PIN.\n\n"
                "Puedo probar igual, pero muchos tokens no muestran el "
                "certificado hasta que se escribe el PIN.\n\n"
                "¿Probar sin PIN?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if resp != QMessageBox.StandardButton.Yes:
                return
        from motors.motor_pdf_tools import probe_token
        self._run_op(probe_token, self._token_dll(), pin,
                     status_label=self.lbl_sign_status,
                     dialog_title="Resultado de la prueba del token")

    def _do_sign(self):
        use_pfx = self.rad_sign_pfx.isChecked()
        if use_pfx and not self._pfx_path:
            QMessageBox.warning(self, "Firmar PDF",
                                "Primero elegí el archivo del certificado.")
            return
        if not use_pfx:
            # Sin driver detectado no tiene sentido pedirle el PDF al usuario:
            # se le explica primero qué falta.
            if not self._token_dll():
                from motors.motor_pdf_tools import find_pkcs11_modules
                if not find_pkcs11_modules():
                    diag = self._refresh_token_status()
                    QMessageBox.warning(
                        self, "Firmar PDF",
                        f"{diag['titulo']}\n\n{diag['mensaje']}")
                    return
            if not self._token_pin():
                QMessageBox.warning(
                    self, "Firmar PDF",
                    "Escribí el PIN de tu token para poder firmar.")
                return
        if not self._sign_src:
            QMessageBox.warning(
                self, "Firmar PDF",
                "Primero elegí el PDF que querés firmar, arriba de todo.")
            return
        if not os.path.isfile(self._sign_src):
            QMessageBox.warning(
                self, "Firmar PDF",
                "El PDF que habías elegido ya no está en esa carpeta. "
                "Volvé a elegirlo.")
            return

        destino = os.path.splitext(self._sign_src)[0] + "_firmado.pdf"
        dst, _ = QFileDialog.getSaveFileName(
            self, "Guardar el PDF firmado como", destino,
            "Archivos PDF (*.pdf)")
        if not dst:
            return

        reason = self.txt_sign_reason.text().strip()
        visible = self.chk_sign_visible.isChecked()
        pagina = self._sign_page_index()
        posicion = self._sign_position
        leyenda = self._sign_leyenda()
        self._guardar_leyenda()

        origen = self._sign_src
        medio = ("un certificado en archivo (.pfx/.p12)" if use_pfx
                 else "el token USB de firma digital")
        frase = (f"firmar digitalmente el archivo «{os.path.basename(origen)}» "
                 f"con {medio}, en formato PAdES, dejando el sello visible en "
                 f"la página {pagina + 1}" if visible else
                 f"firmar digitalmente el archivo «{os.path.basename(origen)}» "
                 f"con {medio}, en formato PAdES, sin sello visible")

        def informe(_res):
            self._generar_informe(frase, [origen], [dst])

        if use_pfx:
            from motors.motor_pdf_tools import sign_pdf_pfx
            self._run_op(sign_pdf_pfx, origen, dst,
                         self._pfx_path, self.txt_pfx_pass.text(),
                         reason, "", visible, pagina,
                         status_label=self.lbl_sign_status,
                         success_prefix="✅ PDF firmado digitalmente. ",
                         on_result=informe,
                         position=posicion, leyenda=leyenda)
        else:
            from motors.motor_pdf_tools import sign_pdf_token
            self._run_op(sign_pdf_token, origen, dst,
                         self._token_dll(),
                         self._token_pin(),
                         self.txt_token_label.text().strip(),
                         reason, "", visible, pagina,
                         status_label=self.lbl_sign_status,
                         success_prefix="✅ PDF firmado con el token. ",
                         on_result=informe,
                         position=posicion, leyenda=leyenda)

    # ──────────────────────────────────────────────────────────────────
    def _pick_src_dst(self, title: str, suffix: str):
        """Diálogo origen + destino sugerido. Devuelve (src, dst) o None."""
        src, _ = QFileDialog.getOpenFileName(
            self, title, "", "Archivos PDF (*.pdf)")
        if not src:
            return None
        default = os.path.splitext(src)[0] + suffix
        dst, _ = QFileDialog.getSaveFileName(
            self, "Guardar como", default, "Archivos PDF (*.pdf)")
        if not dst:
            return None
        if os.path.abspath(dst) == os.path.abspath(src):
            QMessageBox.warning(self, title,
                                "Elegí un nombre distinto al original.")
            return None
        return src, dst

    def _build_normalize_group(self) -> QGroupBox:
        """Grupo 'Normalizar hoja y letra': para fotos sacadas a distinta
        distancia (letra más chica o más grande según la foto)."""
        grp = QGroupBox("📐  Normalizar tamaño de hoja y de letra")
        g = QVBoxLayout(grp)
        lbl_norm = QLabel(
            "Para PDF armados con fotos de apuntes: si algunas fotos se "
            "sacaron más cerca o más lejos, la letra queda de distinto "
            "tamaño entre páginas. Esto detecta el tamaño de letra típico "
            "(por OCR) y reescribe todas las páginas en hoja A4 con el "
            "mismo zoom, para que se vea parejo.")
        lbl_norm.setWordWrap(True)
        g.addWidget(lbl_norm)

        try:
            from motors.motor_ocr import is_available
            available = is_available()
        except Exception:
            available = False
        if not available:
            g.addWidget(QLabel(
                "No disponible: falta tesseract.exe en la carpeta bin/."))
            return grp

        row = QHBoxLayout()
        row.addWidget(QLabel("Idioma del texto:"))
        from PyQt6.QtWidgets import QComboBox
        self.cmb_normalize_lang = QComboBox()
        self.cmb_normalize_lang.addItems(
            ["Español", "Inglés", "Portugués", "Francés", "Alemán", "Italiano"])
        row.addWidget(self.cmb_normalize_lang)
        row.addStretch()
        g.addLayout(row)

        btn_normalize = QPushButton("📐 Elegir PDF y normalizar...")
        btn_normalize.clicked.connect(self._do_normalize)
        g.addWidget(btn_normalize)
        return grp

    def _do_normalize(self):
        pair = self._pick_src_dst("Normalizar hoja y letra", "_normalizado.pdf")
        if not pair:
            return
        lang = self.cmb_normalize_lang.currentText()
        from motors.motor_ocr import normalize_pdf_pages
        self._run_op(normalize_pdf_pages, pair[0], pair[1], lang,
                     status_label=self.lbl_tools_status,
                     success_prefix="✅ Páginas normalizadas. ")

    def _do_compress(self):
        pair = self._pick_src_dst("Comprimir PDF", "_comprimido.pdf")
        if not pair:
            return
        level = ("light" if self.rad_light.isChecked() else
                 "strong" if self.rad_strong.isChecked() else "medium")
        from motors.motor_pdf_tools import compress_pdf
        self._run_op(compress_pdf, pair[0], pair[1], level,
                     status_label=self.lbl_tools_status,
                     success_prefix="✅ Comprimido. ")

    def _do_protect(self):
        pw1 = self.txt_pass_set.text()
        pw2 = self.txt_pass_set2.text()
        if not pw1:
            QMessageBox.warning(self, "Proteger PDF",
                                "Escribí una contraseña primero.")
            return
        if pw1 != pw2:
            QMessageBox.warning(self, "Proteger PDF",
                                "Las contraseñas no coinciden.")
            return
        pair = self._pick_src_dst("Proteger PDF", "_protegido.pdf")
        if not pair:
            return
        from motors.motor_pdf_tools import protect_pdf
        self._run_op(protect_pdf, pair[0], pair[1], pw1,
                     status_label=self.lbl_tools_status,
                     success_prefix="✅ PDF protegido. "
                     "Guardá la contraseña: sin ella no se puede abrir. ")

    def _do_unlock(self):
        pair = self._pick_src_dst("Quitar contraseña", "_desbloqueado.pdf")
        if not pair:
            return
        from motors.motor_pdf_tools import unlock_pdf
        self._run_op(unlock_pdf, pair[0], pair[1],
                     self.txt_pass_unlock.text(),
                     status_label=self.lbl_tools_status,
                     success_prefix="✅ Contraseña quitada. ")

    def _do_repair(self):
        pair = self._pick_src_dst("Reparar PDF", "_reparado.pdf")
        if not pair:
            return
        from motors.motor_pdf_tools import repair_pdf
        self._run_op(repair_pdf, pair[0], pair[1],
                     status_label=self.lbl_tools_status,
                     success_prefix="✅ PDF reparado. ")

    # ──────────────────────────────────────────────────────────────────
    def _run_op(self, fn, *args, status_label=None, success_prefix="",
                dialog_title="", on_result=None, **kwargs):
        """Corre una operación en un hilo, mostrando avance en el label.

        Si se pasa `dialog_title`, además muestra el resultado en un diálogo
        (útil para diagnósticos, donde el texto no entra en una línea).
        Los kwargs sobrantes van tal cual a la función del motor.
        """
        if self._op_worker and self._op_worker.isRunning():
            QMessageBox.information(
                self, "Editar PDF",
                "Esperá a que termine la operación en curso.")
            return
        label = status_label or self.lbl_tools_status

        # Arranca en modo "ocupado" (barra animada sin porcentaje): ya con eso
        # se ve que el programa está trabajando. Si el motor sabe informar
        # avance real, la barra pasa a porcentaje en cuanto llega el primero.
        self._op_busy_start()

        self._op_worker = _OpWorker(fn, *args, **kwargs)
        self._op_worker.log_msg.connect(label.setText)
        self._op_worker.pct.connect(self._op_pct)
        if on_result:
            self._op_worker.result_obj.connect(on_result)
        if dialog_title:
            self._op_worker.finished_ok.connect(
                lambda msg: (self._op_busy_stop(), label.setText(""),
                             self._show_report(dialog_title, msg)))
        else:
            self._op_worker.finished_ok.connect(
                lambda msg: (self._op_busy_stop(),
                             label.setText(success_prefix + msg)))
        self._op_worker.error.connect(
            lambda msg: (self._op_busy_stop(), label.setText(""),
                         QMessageBox.warning(self, "Editar PDF",
                                             f"Error:\n{msg}")))
        self._op_worker.start()

    # ── Limpiar ───────────────────────────────────────────────────────

    def _boton_limpiar(self, vaciar_solapa) -> QPushButton:
        """Botón «Limpiar», el mismo en todas las solapas del módulo."""
        btn = QPushButton("🗑 Limpiar")
        btn.setObjectName("ghostBtn")
        btn.setToolTip(
            "Deja la solapa como recién abierta, para empezar con otro "
            "archivo.\nNo borra nada del disco.")
        btn.clicked.connect(lambda: self._limpiar(vaciar_solapa))
        return btn

    def _limpiar(self, vaciar_solapa):
        """Vacía una solapa y esconde el informe de la operación anterior."""
        trabajando = (self._op_worker, self._merge_worker,
                      self._dup_worker, self._merge_dup_worker)
        if any(w is not None and w.isRunning() for w in trabajando):
            QMessageBox.information(
                self, "Limpiar",
                "Esperá a que termine la operación en curso.")
            return
        vaciar_solapa()
        if getattr(self, "informe_section", None):
            self.informe_section.setVisible(False)

    def _op_busy_start(self):
        self.op_progress.setRange(0, 0)          # animación de "trabajando"
        self.op_progress.setFormat("Trabajando...")
        self.op_progress.setVisible(True)

    def _op_pct(self, value: int):
        if self.op_progress.maximum() == 0:
            self.op_progress.setRange(0, 100)
            self.op_progress.setFormat("%p%")
        self.op_progress.setValue(value)

    def _op_busy_stop(self):
        self.op_progress.setVisible(False)
        self.op_progress.setRange(0, 0)
        self.op_progress.reset()

    def _generar_informe(self, frase: str, origenes, resultados):
        """Dispara el armado del informe técnico de la operación recién hecha."""
        if not getattr(self, "informe_section", None):
            return
        self._informe_worker = _InformeWorker(frase, origenes, resultados)
        self._informe_worker.listo.connect(self._mostrar_informe)
        self._informe_worker.start()

    def _mostrar_informe(self, texto: str):
        if not getattr(self, "informe_section", None):
            return
        try:
            self.informe_section.set_informe(texto)
        except TypeError:
            # Algunas versiones esperan (texto, carpeta)
            self.informe_section.set_informe(texto, "")
        self.informe_section.setVisible(True)

    @staticmethod
    def _archivos_de(resultado, por_defecto=None):
        """Saca la lista de archivos generados del resultado del motor."""
        if isinstance(resultado, dict) and resultado.get("archivos"):
            return list(resultado["archivos"])
        return [p for p in (por_defecto or []) if p]

    def _show_report(self, titulo: str, texto: str):
        """Muestra un informe largo en un diálogo con fuente monoespaciada."""
        from PyQt6.QtWidgets import QDialog, QPlainTextEdit, QDialogButtonBox
        from PyQt6.QtGui import QFont

        dlg = QDialog(self)
        dlg.setWindowTitle(titulo)
        dlg.resize(620, 420)
        lay = QVBoxLayout(dlg)
        vista = QPlainTextEdit(texto)
        vista.setReadOnly(True)
        vista.setFont(QFont("Consolas", 9))
        lay.addWidget(vista)
        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        botones.accepted.connect(dlg.accept)
        lay.addWidget(botones)
        dlg.exec()
