# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════╗
║   MÓDULO 0  —  Preparador Universal de Datos  —  v2.5               ║
║   Parte de Navaja — licencia GPL-3.0 (ver LICENSE)                  ║
╠══════════════════════════════════════════════════════════════════════╣
║  PUERTA DE ENTRADA PRINCIPAL PARA TODOS LOS TIPOS DE ARCHIVO        ║
║  FORMATOS SOPORTADOS: PDF · Excel (.xlsx/.xls) · CSV · ODS          ║
╠══════════════════════════════════════════════════════════════════════╣
║  FUNCIONES                                                           ║
║  • Router automático según extensión del archivo cargado            ║
║  • PDF: miniaturas, selección de páginas, canvas visual, grupos     ║
║  • Excel/CSV/ODS: carga directa en editor tabular (sin canvas)      ║
║  • Miniatura de todas las páginas del PDF (carga lazy)              ║
║  • Selección de páginas por rango o click individual                ║
║  • Vista previa ampliada con zoom (rueda del mouse)                 ║
║  • Por grupo de páginas: marcar inicio Y y fin Y de tabla           ║
║  • Separadores de columna visuales por grupo                        ║
║  • Hasta 5 grupos con configuración independiente                   ║
║  • 9 cortes en cadena para columnas complejas (absorbido de M1)     ║
║  • Doble clic en tabla para dividir columna (absorbido de M1)       ║
║  • Sincronización scroll PDF ↔ tabla preview (absorbido de M1)      ║
║  • Exportar Excel / CSV directo desde aquí                          ║
║  • Guardar / cargar receta (.json)                                  ║
║  • Botón ↩ Volver (Undo) con historial de hasta 20 estados          ║
║  • Botón 🔄 Resetear con confirmación                               ║
║  • Panel 📊 Editor tabular para Excel/CSV/ODS                       ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import sys, os, io, json, math, csv, re, threading

# ── Dentro de Navaja ────────────────────────────────────────
# Este archivo es el «MODULO 0 PREPARADOR PDF.py» del programa PDF a Excel,
# copiado tal cual. Lo que se adaptó para que conviva con el resto está
# marcado con «Dentro de Navaja»: dónde se anota un cierre
# inesperado, de dónde sale Tesseract, el botón «Limpiar» y el nombre que se
# propone para guardar.

# ── Diagnóstico de crashes nativos (segfault) ─────────────────────────────
# faulthandler escribe el stack de Python en el instante del crash nativo,
# que sys.excepthook NO puede capturar. Se mantiene el archivo abierto toda
# la sesión. Revisar fault_log.txt si la app se cierra sin cartel.
# Dentro de Navaja: el registro va a la carpeta de logs del
# programa, y si no se puede abrir se sigue sin él (con pythonw no hay
# consola a la que escribir).
import faulthandler
try:
    from core.paths import LOGS_DIR as _LOGS_DIR
    _FAULT_LOG = open(
        os.path.join(_LOGS_DIR, "fault_log_pdf_excel.txt"),
        "a", encoding="utf-8", buffering=1)
    _FAULT_LOG.write("\n==== sesión iniciada ====\n"); _FAULT_LOG.flush()
    faulthandler.enable(file=_FAULT_LOG, all_threads=True)
except Exception:
    pass
import pdfplumber, openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from PIL import Image as PILImage

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QLineEdit, QFileDialog,
    QScrollArea, QSplitter, QFrame, QSpinBox,
    QCheckBox, QComboBox, QTabWidget, QProgressBar,
    QMessageBox, QTextEdit, QSizePolicy, QApplication,
    QMainWindow, QStatusBar, QDialog, QDialogButtonBox,
    QListWidget, QListWidgetItem, QAbstractItemView,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QInputDialog, QScrollBar, QFormLayout,
)
from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, QTimer, QSize, QPoint, QRect,
)
from PyQt6.QtGui import (
    QFont, QColor, QPixmap, QPainter, QPen, QBrush,
    QImage, QCursor, QPolygon, QIcon,
)

# ══════════════════════════════════════════════════════════════════════
#  TEMAS  (idénticos al M1 para coherencia visual)
# ══════════════════════════════════════════════════════════════════════
DARK = dict(
    bg="#16202E", panel="#1E2C3D", card="#243040", border="#2E4060",
    text="#E2EAF4", muted="#8BA0B8", accent="#3B82F6", accent2="#10B981",
    red="#EF4444", row_alt="#1A2535", hdr_tbl="#1E2C3D",
    canvas_bg="#0F1620", line_col="#FF3C3C", hover_col="#FF8C00",
    wm="#1C2E42",
)
LIGHT = dict(
    bg="#F0F4F8", panel="#FFFFFF", card="#F8FAFC", border="#CBD5E0",
    text="#1A202C", muted="#718096", accent="#2563EB", accent2="#059669",
    red="#DC2626", row_alt="#EBF4FF", hdr_tbl="#EDF2F7",
    canvas_bg="#DDE3EA", line_col="#DC2626", hover_col="#D97706",
    wm="#CDD5E0",
)
_T = DARK
def T(k): return _T[k]

SNAP = 10
MAX_GROUPS = 5
THUMB_W    = 130
THUMB_H    = 180

# ══════════════════════════════════════════════════════════════════════
#  UTILIDADES PDF
# ══════════════════════════════════════════════════════════════════════
import sys as _sys
# En modo frozen (EXE) el módulo vive en _MEIPASS (carpeta temporal), pero tesseract
# va distribuido al lado del EXE real → usamos sys.executable para localizarlo.
_EXE_DIR = (os.path.dirname(os.path.abspath(_sys.executable))
            if getattr(_sys, 'frozen', False)
            else os.path.dirname(os.path.abspath(__file__)))
_TESSERACT_PATHS = [
    os.path.join(_EXE_DIR, "tesseract", "tesseract.exe"),            # junto al EXE / módulo
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "tesseract", "tesseract.exe"),
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    r"C:\Users\Public\Tesseract-OCR\tesseract.exe",
]

# ── Serialización de código nativo NO thread-safe ─────────────────────────
# PDFium (motor de render de pdfplumber) y Tesseract/PIL no son seguros con
# hilos concurrentes: dos renders u OCR a la vez producen access violation
# (ver fault_log.txt). TODO acceso pasa por estos locks.
_PDF_RENDER_LOCK = threading.Lock()   # page.to_image()
_OCR_LOCK        = threading.Lock()   # pytesseract / config global

def _render_page_image(page, resolution):
    """Renderiza una página a imagen PIL de forma thread-safe (PDFium no es reentrante)."""
    with _PDF_RENDER_LOCK:
        return page.to_image(resolution=resolution).original

_TESS_READY = False
def _configurar_tesseract(pytesseract):
    """Localiza tesseract.exe UNA sola vez (thread-safe). Evita mutar os.environ
    en cada llamada desde varios hilos."""
    global _TESS_READY
    if _TESS_READY:
        return
    with _OCR_LOCK:
        if _TESS_READY:
            return
        # Dentro de Navaja: se usa el mismo Tesseract que el
        # resto del programa (el de bin/, con sus idiomas).
        try:
            from motors.motor_ocr import TESSERACT_PATH
        except Exception:
            TESSERACT_PATH = None
        if TESSERACT_PATH:
            pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
            _TESS_READY = True
            return
        import shutil
        if not shutil.which("tesseract"):
            for candidate in _TESSERACT_PATHS:
                if os.path.isfile(candidate):
                    pytesseract.pytesseract.tesseract_cmd = candidate
                    local_tessdata = os.path.join(os.path.dirname(candidate), "tessdata")
                    if os.path.isdir(local_tessdata):
                        os.environ["TESSDATA_PREFIX"] = local_tessdata
                    break
        _TESS_READY = True

def _mejorar_imagen(img, modo="media"):
    """Preprocesa la imagen del escaneo antes del OCR.
    modo dict: {"fondo": 0-10, "texto": 0-10, "puntitos": bool, "bn": bool}
      fondo    = % de grises claros llevados a blanco puro (quita base gris)
      texto    = % de grises oscuros llevados a negro puro (remarca letras)
      puntitos = filtro de mediana 3x3 (borra motas/puntos del escáner)
      bn       = binarización con umbral Otsu (blanco y negro puro)
    Acepta también presets legacy: "suave" / "media" / "fuerte".
    """
    from PIL import ImageFilter
    if isinstance(modo, str):
        modo = {"suave":  {"fondo": 2, "texto": 1},
                "media":  {"fondo": 3, "texto": 2, "puntitos": True},
                "fuerte": {"fondo": 4, "texto": 3, "puntitos": True, "bn": True}}.get(modo, {})
    g = img.convert("L")
    fondo, texto = modo.get("fondo", 0), modo.get("texto", 0)
    if fondo or texto:
        # Estira el histograma recortando texto% de los píxeles más oscuros
        # (→ negro puro) y fondo% de los más claros (→ blanco puro).
        hist = g.histogram()
        cum, s = [], 0
        for h in hist: s += h; cum.append(s)
        total = s
        obj_lo = total * texto / 100.0
        obj_hi = total * (100.0 - fondo) / 100.0
        lo = next((i for i in range(256) if cum[i] >= obj_lo), 0)
        hi = next((i for i in range(256) if cum[i] >= obj_hi), 255)
        lo = min(lo, 254)
        if hi <= lo: hi = lo + 1
        escala = 255.0 / (hi - lo)
        tabla = [0 if v <= lo else 255 if v >= hi else int((v - lo) * escala)
                 for v in range(256)]
        g = g.point(tabla)
    if modo.get("puntitos"):
        g = g.filter(ImageFilter.MedianFilter(3))
    if modo.get("bn"):
        h = g.histogram()
        total = sum(h); s_all = sum(i * h[i] for i in range(256))
        s_b = 0.0; w_b = 0; var_max = -1.0; thr = 127
        for i in range(256):
            w_b += h[i]
            if w_b == 0: continue
            w_f = total - w_b
            if w_f == 0: break
            s_b += i * h[i]
            m_b = s_b / w_b; m_f = (s_all - s_b) / w_f
            var = w_b * w_f * (m_b - m_f) ** 2
            if var > var_max: var_max, thr = var, i
        g = g.point(lambda v, t=thr: 255 if v > t else 0)
    return g


def _ocr_page(page, lang="spa+eng", dpi=300, ocr_rotation=0, ocr_enhance="",
              ocr_min_conf=30, log_fn=None):
    """OCR posicional sobre página imagen. Retorna words en mismo formato que _extract_palabras.
    ocr_rotation: grados CW a rotar la IMAGEN antes de OCR (0/90/180/270).
    ocr_enhance: "" / "suave" / "media" / "fuerte" — limpieza previa de la imagen.
    ocr_min_conf: confianza mínima (0-100) para aceptar una palabra.
    Con rotación, las coordenadas quedan en el ESPACIO DE LECTURA (la vista
    rotada): el mismo espacio donde el visor dibuja las marcas de inicio/fin
    y columnas, así extracción y marcado son consistentes.
    """
    try:
        import pytesseract
    except ImportError:
        if log_fn: log_fn("  ⚠ pytesseract no instalado. Ejecutá: pip install pytesseract")
        return []
    _configurar_tesseract(pytesseract)
    try:
        img = _render_page_image(page, dpi)

        if ocr_rotation != 0:
            if log_fn: log_fn(f"  ↻ Pre-rotando imagen {ocr_rotation}° para OCR...")
            # PIL rotate es CCW → para CW usamos ángulo negativo
            img = img.rotate(-ocr_rotation, expand=True)

        if ocr_enhance:
            if log_fn: log_fn("  🧹 Limpiando imagen para OCR...")
            img = _mejorar_imagen(img, ocr_enhance)

        # Tesseract serializado: nunca dos OCR en paralelo (segfault)
        with _OCR_LOCK:
            data = pytesseract.image_to_data(
                img, lang=lang, output_type=pytesseract.Output.DICT,
                config="--psm 6 --oem 3")
    except Exception as e:
        if log_fn: log_fn(f"  ⚠ OCR falló: {e}")
        return []

    # Dimensiones en pts del espacio de lectura (90/270 intercambian ancho/alto)
    if ocr_rotation in (90, 270):
        eff_w, eff_h = page.height, page.width
    else:
        eff_w, eff_h = page.width, page.height
    sx = eff_w / max(img.width, 1)
    sy = eff_h / max(img.height, 1)

    words = []
    for i in range(len(data["text"])):
        txt  = (data["text"][i] or "").strip()
        conf_raw = str(data["conf"][i])
        conf = int(conf_raw) if conf_raw.lstrip("-").isdigit() else -1
        if not txt or conf < ocr_min_conf:
            continue
        x = data["left"][i]; y = data["top"][i]
        w = data["width"][i]; h = data["height"][i]

        # Coordenadas directas en el espacio de lectura (imagen ya rotada)
        words.append({
            "text":   txt,
            "x0":     x * sx,
            "x1":     (x + w) * sx,
            "top":    y * sy,
            "bottom": (y + h) * sy,
        })

    # Normalizar Y: palabras de la misma línea visual comparten el mismo top.
    # OCR introduce variación de ±2pt entre palabras del mismo renglón,
    # lo que confunde el agrupador de filas (y_tol=3). Snap a línea promedio.
    if words:
        words.sort(key=lambda w: w["top"])
        snapped, i = [], 0
        while i < len(words):
            line_top = words[i]["top"]
            j = i
            while j < len(words) and words[j]["top"] - line_top < 8:
                j += 1
            avg_top = sum(words[k]["top"] for k in range(i, j)) / (j - i)
            for k in range(i, j):
                ww = dict(words[k]); ww["top"] = avg_top; snapped.append(ww)
            i = j
        words = snapped
    return words


def _rotar_words(words, rot, pdf_w, pdf_h):
    """Lleva words/chars (x0, x1, top, bottom) del espacio original del PDF
    al espacio de lectura de la vista rotada `rot` grados CW."""
    if rot not in (90, 180, 270) or not words:
        return list(words)
    out = []
    for w in words:
        ww = dict(w)
        if rot == 90:      # (x,y) → (H−y, x)
            ww["x0"], ww["x1"] = pdf_h - w["bottom"], pdf_h - w["top"]
            ww["top"], ww["bottom"] = w["x0"], w["x1"]
        elif rot == 180:   # (x,y) → (W−x, H−y)
            ww["x0"], ww["x1"] = pdf_w - w["x1"], pdf_w - w["x0"]
            ww["top"], ww["bottom"] = pdf_h - w["bottom"], pdf_h - w["top"]
        else:              # 270: (x,y) → (y, W−x)
            ww["x0"], ww["x1"] = w["top"], w["bottom"]
            ww["top"], ww["bottom"] = pdf_w - w["x1"], pdf_w - w["x0"]
        out.append(ww)
    return out


def _extract_palabras(page, y_tol=3, word_gap=1.3, x_min=0,
                       ocr_enabled=False, ocr_lang="spa+eng",
                       ocr_rotation=0, ocr_enhance="", ocr_min_conf=30, log_fn=None):
    """Extrae palabras usando chars individuales para detectar espacios implícitos."""
    try:
        chars = page.chars
    except Exception:
        return _rotar_words(page.extract_words(x_tolerance=2, y_tolerance=y_tol,
                                               keep_blank_chars=False, use_text_flow=False),
                            ocr_rotation, page.width, page.height)
    is_image_page = (len(chars) == 0)
    chars = [c for c in chars if c.get('text', '').strip() and c.get('x1', 0) > c.get('x0', 0)]
    if ocr_rotation and chars:
        # Texto embebido en PDF girado → mismo espacio de lectura que visor y OCR
        chars = _rotar_words(chars, ocr_rotation, page.width, page.height)
    chars = [c for c in chars if c.get('x0', 0) >= x_min]
    if not chars:
        if is_image_page and ocr_enabled:
            if log_fn: log_fn(f"  🔍 Página imagen → OCR ({ocr_lang}, rot={ocr_rotation}°)...")
            ocr_words = _ocr_page(page, lang=ocr_lang, ocr_rotation=ocr_rotation,
                                  ocr_enhance=ocr_enhance, ocr_min_conf=ocr_min_conf,
                                  log_fn=log_fn)
            if x_min:
                ocr_words = [w for w in ocr_words if w["x0"] >= x_min]
            return ocr_words
        return []
    lines = {}
    for c in chars:
        y_key = round(c['top'] / y_tol) * y_tol
        lines.setdefault(y_key, []).append(c)
    words = []
    for y_key in sorted(lines):
        line_chars = sorted(lines[y_key], key=lambda c: c['x0'])
        current = [line_chars[0]]
        for c in line_chars[1:]:
            gap = c['x0'] - current[-1]['x1']
            if gap >= word_gap:
                txt = ''.join(ch['text'] for ch in current)
                if txt.strip():
                    words.append({'text': txt, 'x0': current[0]['x0'],
                        'x1': current[-1]['x1'], 'top': y_key,
                        'bottom': max(ch.get('bottom', y_key) for ch in current)})
                current = [c]
            else:
                current.append(c)
        txt = ''.join(ch['text'] for ch in current)
        if txt.strip():
            words.append({'text': txt, 'x0': current[0]['x0'],
                'x1': current[-1]['x1'], 'top': y_key,
                'bottom': max(ch.get('bottom', y_key) for ch in current)})
    return words


def auto_seps(page, y_tol=3, min_gap=8, word_gap=3.0, ocr_enabled=False, ocr_lang="spa+eng",
              ocr_rotation=0, ocr_enhance="", ocr_min_conf=30):
    words = _extract_palabras(page, y_tol, word_gap, ocr_enabled=ocr_enabled, ocr_lang=ocr_lang,
                              ocr_rotation=ocr_rotation, ocr_enhance=ocr_enhance,
                              ocr_min_conf=ocr_min_conf)
    if not words: return [], words
    # Ancho del espacio de lectura (90/270 intercambian ancho/alto)
    eff_w = page.height if ocr_rotation in (90, 270) else page.width
    occ = set()
    for w in words:
        for x in range(int(w["x0"]), int(w["x1"]) + 1): occ.add(x)
    gaps, in_g, gs = [], False, 0
    for x in range(int(eff_w) + 1):
        if x not in occ:
            if not in_g: in_g, gs = True, x
        else:
            if in_g:
                if x - gs >= min_gap: gaps.append((gs, x))
                in_g = False
    if in_g: gaps.append((gs, int(eff_w)))
    return [int((a + b) / 2) for a, b in gaps], words

def rows_from(words, seps, y_tol=3, start_y=0.0, end_y=0.0):
    if not words: return []
    seps = sorted(seps); nc = len(seps) + 1; lines = {}
    for w in words:
        if w["top"] < start_y: continue
        if end_y > 0 and w["top"] > end_y: continue
        k = round(w["top"] / y_tol) * y_tol
        lines.setdefault(k, []).append(w)
    def col_of(x0):
        c = 0
        for s in seps:
            if x0 > s: c += 1
            else: break
        return min(c, nc - 1)
    rows = []
    for y in sorted(lines):
        lw = sorted(lines[y], key=lambda w: w["x0"])
        row = [""] * nc
        for w in lw:
            c = col_of(w["x0"]); row[c] = (row[c] + " " + w["text"]).strip()
        if any(v.strip() for v in row): rows.append(row)
    return rows

def same_hdr(row, ref):
    if not ref or len(row) != len(ref): return False
    m = sum(1 for a, b in zip(row, ref) if a.strip().upper() == b.strip().upper())
    return m >= max(2, len(ref) // 2)

_IC_RE = re.compile(r'[\x00-\x08\x0B-\x0C\x0E-\x1F]')
def _xclean(v):
    """Elimina caracteres ilegales para Excel/XML 1.0 (ej: separadores del PDF)
    y neutraliza inyección de fórmulas: un valor que empieza con '=' sería
    interpretado por openpyxl/Excel como fórmula viva."""
    if not v: return v
    s = _IC_RE.sub('', str(v))
    if s.startswith("="):
        s = "'" + s
    return s

_SPLIT_SEP = "\x00"   # separador interno entre renglones (null char, no aparece en PDF)

def merge_rows(rows, anchor_col=0, split_sep=" "):
    """
    Fusiona filas de continuación con la fila anterior.
    Una fila es "continuación" si su columna ancla está vacía.
    split_sep: separador entre partes al concatenar (usa _SPLIT_SEP cuando se va a dividir luego)
    """
    if not rows:
        return rows
    nc = len(rows[0]) if rows else 1
    if anchor_col >= nc:
        anchor_col = 0
    merged = [list(rows[0])]
    for row in rows[1:]:
        row = (list(row) + [""] * nc)[:nc]
        if not row[anchor_col].strip():
            prev = merged[-1]
            for c in range(nc):
                if row[c].strip():
                    sep = split_sep if prev[c] else ""
                    prev[c] = prev[c] + sep + row[c]
        else:
            merged.append(list(row))
    return merged

def split_column(rows, col, n_parts):
    """
    Expande la columna `col` en `n_parts` columnas usando _SPLIT_SEP como delimitador.
    El resultado tiene (len(row) - 1 + n_parts) elementos por fila.
    """
    result = []
    for row in rows:
        val = row[col] if col < len(row) else ""
        parts = val.split(_SPLIT_SEP, n_parts - 1)
        parts = (parts + [""] * n_parts)[:n_parts]
        new_row = list(row[:col]) + parts + list(row[col + 1:])
        result.append(new_row)
    return result

def split_by_keywords(rows, col_idx, keywords):
    """
    Divide la columna col_idx al encontrar una palabra clave.
    El texto hasta la keyword (inclusive) queda en col_idx.
    El texto posterior pasa a col_idx+1 (nueva columna insertada).
    Las keywords más largas tienen prioridad (se prueban primero).
    Si ninguna keyword aparece en la celda, col_idx+1 queda vacía.
    """
    if not keywords or not rows:
        return rows
    kws = sorted([k.strip().upper() for k in keywords if k.strip()],
                 key=len, reverse=True)   # más largas primero
    result = []
    for row in rows:
        val = row[col_idx] if col_idx < len(row) else ""
        val_upper = val.upper()
        cut = -1
        for kw in kws:
            pos = val_upper.find(kw)
            if pos >= 0:
                cut = pos + len(kw)   # índice justo después de la keyword
                break
        if cut >= 0:
            before = val[:cut].strip()
            after  = val[cut:].strip()
        else:
            before = val
            after  = ""
        new_row = list(row[:col_idx]) + [before, after] + list(row[col_idx + 1:])
        result.append(new_row)
    return result


def is_num(t):
    try:
        float(str(t).replace(",",".").replace("%","").replace("$","").replace(" ","").strip())
        return True
    except: return False

# ══════════════════════════════════════════════════════════════════════
#  WORKER: carga miniaturas en background
# ══════════════════════════════════════════════════════════════════════
class ThumbLoader(QThread):
    # ⚠ Se emite QImage (seguro entre hilos). QPixmap SOLO puede crearse en el
    # hilo de la GUI; crearlo acá producía crashes nativos intermitentes.
    thumb_ready = pyqtSignal(int, QImage)    # (page_index, image)
    done        = pyqtSignal(int)            # total pages

    def __init__(self, path, dpi=40):
        super().__init__()
        self.path = path
        self.dpi  = dpi
        self._stop = False

    def stop(self): self._stop = True

    def run(self):
        try:
            with pdfplumber.open(self.path) as pdf:
                total = len(pdf.pages)
                self.done.emit(total)
                for i, pg in enumerate(pdf.pages):
                    if self._stop: break
                    try:
                        img = _render_page_image(pg, self.dpi)
                        buf = io.BytesIO(); img.save(buf, "PNG")
                        qimg = QImage.fromData(buf.getvalue())
                        self.thumb_ready.emit(i, qimg)
                    except: pass
        except Exception as e:
            print(f"[ThumbLoader] {e}")


def pdf_de_la_tabla(salida, origen):
    """Dentro de Navaja: nombre del PDF de «También PDF».

    Lleva el nombre de la planilla; pero si la planilla se guarda al lado del
    PDF original y con su mismo nombre, ese PDF sería el original y lo
    pisaría. En ese caso se llama «…_tabla.pdf».
    """
    base = os.path.splitext(salida)[0]
    ruta = base + ".pdf"
    if origen and os.path.normcase(os.path.abspath(ruta)) == \
            os.path.normcase(os.path.abspath(origen)):
        ruta = base + "_tabla.pdf"
    return ruta


class PageConverter(QThread):
    """Convierte páginas seleccionadas a Excel/CSV usando grupos de configuración."""
    progress = pyqtSignal(int)
    log      = pyqtSignal(str)
    done     = pyqtSignal(bool, str)   # no usar 'finished': enmascara QThread.finished

    def __init__(self, path, out, groups, opts, overrides=None, selected_pages=None):
        super().__init__()
        self.path           = path
        self.out            = out
        self.groups         = groups    # lista de dicts con config por grupo
        self.opts           = opts
        self.overrides      = overrides or {}   # {pn(1-based): {"start_y":, "end_y":}}
        self.selected_pages = selected_pages    # set de pn(1-based) a incluir; None = todas

    def run(self):
        try:
            if self.out.lower().endswith(".csv"): self._csv()
            else: self._xlsx()
        except PermissionError:
            msg = f"Sin permiso para guardar:\n{self.out}\n\nCerrá el archivo si está abierto en Excel."
            self.log.emit(f"❌ {msg}")
            self.done.emit(False, msg)
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            self.log.emit(f"❌ ERROR:\n{tb}")
            self.done.emit(False, f"{type(e).__name__}: {e}")

    def _extract(self):
        opts         = self.opts
        all_rows     = []
        hdr          = None
        ocr_enabled  = opts.get("ocr_enabled",  False)
        ocr_lang     = opts.get("ocr_lang",     "spa+eng")
        ocr_rotation = opts.get("ocr_rotation", 0)
        ocr_enhance  = opts.get("ocr_enhance",  "")
        ocr_min_conf = opts.get("ocr_min_conf", 30)

        with pdfplumber.open(self.path) as pdf:
            total = len(pdf.pages)
            self.log.emit(f"📑 {total} páginas en PDF")

            for pn_0 in range(total):
                if self.isInterruptionRequested():
                    raise RuntimeError("Conversión cancelada")
                pn = pn_0 + 1
                # Buscar grupo que contiene esta página
                # Filtrar por selección de miniaturas
                if self.selected_pages is not None and pn not in self.selected_pages:
                    continue
                grp = None
                for g in self.groups:
                    if g["active"] and g["p_from"] <= pn <= g["p_to"]:
                        grp = g; break
                if grp is None: continue   # página no incluida en ningún grupo

                self.progress.emit(int(pn / total * 85))

                # Override individual de Y para esta página
                ov       = self.overrides.get(pn, {})
                start_y  = ov.get("start_y", grp["start_y"])
                end_y    = ov.get("end_y",   grp["end_y"])
                ov_tag   = "  [ov-Y]" if ov else ""
                self.log.emit(f"  → Página {pn}/{total}  [Grupo: {grp['name']}]{ov_tag}")

                pg   = pdf.pages[pn_0]
                wds  = _extract_palabras(pg, opts["y_tol"], opts.get("word_gap", 1.3),
                                          opts.get("x_min", 0),
                                          ocr_enabled=ocr_enabled, ocr_lang=ocr_lang,
                                          ocr_rotation=ocr_rotation,
                                          ocr_enhance=ocr_enhance,
                                          ocr_min_conf=ocr_min_conf,
                                          log_fn=self.log.emit)
                do_merge = grp.get("merge_rows", False)
                do_split = grp.get("split_col", False)
                split_idx   = grp.get("split_col_idx", 1)
                split_n     = grp.get("split_n_parts", 2)
                do_kw    = grp.get("kw_split", False)
                kw_col   = grp.get("kw_col", 1)
                keywords = grp.get("keywords", [])
                merge_sep = _SPLIT_SEP if (do_merge and do_split) else " "

                rows = rows_from(wds, grp["seps"], opts["y_tol"], start_y, end_y)
                if do_merge and rows:
                    rows = merge_rows(rows, anchor_col=grp.get("anchor_col", 0),
                                      split_sep=merge_sep)
                if do_split and rows:
                    rows = split_column(rows, col=split_idx, n_parts=split_n)
                if do_kw and rows and keywords:
                    rows = split_by_keywords(rows, kw_col, keywords)
                if not rows: continue

                nc = len(grp["seps"]) + 1
                if do_split:
                    nc = nc + split_n - 1
                if do_kw and keywords:
                    nc = nc + 1   # columna extra por keyword split

                if hdr is None:
                    hi  = next((i for i, r in enumerate(rows)
                                if sum(1 for c in r if c.strip()) >= 1), 0)
                    hdr = list(rows[hi])
                    # Nombrar sub-columnas automáticamente
                    if do_split and split_idx < len(hdr):
                        base = hdr[split_idx].strip() or f"Col{split_idx + 1}"
                        for k in range(split_n):
                            ci = split_idx + k
                            if ci < len(hdr):
                                hdr[ci] = f"{base} {k + 1}"
                    if do_kw and kw_col < len(hdr):
                        base = hdr[kw_col].strip() or f"Col{kw_col + 1}"
                        hdr.insert(kw_col + 1, f"{base} (resto)")
                    all_rows.append(("header", hdr))
                    data = rows[hi + 1:]
                else:
                    data = rows
                    if data and same_hdr(data[0], hdr): data = data[1:]
                    if opts.get("page_sep") and data:
                        all_rows.append(("sep", [f"── Pág {pn} [{grp['name']}] ──"]))

                for row in data:
                    row = (list(row) + [""] * nc)[:nc]
                    if any(c.strip() for c in row):
                        all_rows.append(("data", row))

        return all_rows, len(hdr) if hdr else 1

    def _xlsx(self):
        opts = self.opts
        all_rows, nc = self._extract()
        if not all_rows:
            self.done.emit(False, "No se extrajeron datos. Revisá la configuración de grupos.")
            return

        wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Datos"
        hf  = Font(name="Calibri", bold=True, size=9, color="FFFFFF")
        hfi = PatternFill("solid", start_color="1A3A5C")
        af  = PatternFill("solid", start_color="EDF3FB")
        nf  = Font(name="Calibri", size=9)
        sf  = Font(name="Calibri", italic=True, size=8, color="888888")
        sfi = PatternFill("solid", start_color="DDE6EF")
        cc  = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cl  = Alignment(horizontal="left",   vertical="center", wrap_text=True)
        th  = Side(style="thin", color="C0CDD8")
        bd  = Border(left=th, right=th, top=th, bottom=th)

        cur = 1; di = 0
        for kind, row in all_rows:
            if kind == "header":
                for ci, v in enumerate(row, 1):
                    c = ws.cell(row=cur, column=ci, value=_xclean(v.strip()) or None)
                    c.font = hf; c.fill = hfi; c.alignment = cc
                    if opts.get("borders"): c.border = bd
                ws.row_dimensions[cur].height = 22
            elif kind == "sep":
                ws.merge_cells(start_row=cur, start_column=1,
                               end_row=cur, end_column=max(nc, 1))
                c = ws.cell(row=cur, column=1, value=_xclean(str(row[0])))
                c.font = sf; c.fill = sfi; c.alignment = cc
            else:
                alt = (di % 2 == 1) and opts.get("alt_rows", True)
                for ci, v in enumerate(row, 1):
                    c = ws.cell(row=cur, column=ci, value=_xclean(v.strip()) or None)
                    c.font = nf
                    c.fill = af if alt else PatternFill()
                    c.alignment = cc if is_num(v) else cl
                    if opts.get("borders"): c.border = bd
                ws.row_dimensions[cur].height = 15; di += 1
            cur += 1

        self.log.emit("📐 Ajustando columnas..."); self.progress.emit(92)
        for col in ws.columns:
            lt = get_column_letter(col[0].column)
            mx = max((len(str(c.value)) for c in col if c.value), default=0)
            ws.column_dimensions[lt].width = min(max(mx + 2, 8), 42)
        if opts.get("freeze"): ws.freeze_panes = "A2"
        ws.sheet_view.zoomScale = 90
        self.log.emit("💾 Guardando Excel..."); self.progress.emit(97)
        wb.save(self.out); self.progress.emit(100)

        if opts.get("export_pdf", False):
            pdf_path = pdf_de_la_tabla(self.out, self.path)
            try:
                self.log.emit("📄 Generando PDF...")
                self._gen_pdf(all_rows, nc, pdf_path)
                self.log.emit(f"📄 PDF guardado: {pdf_path}")
            except Exception as e:
                self.log.emit(f"⚠ PDF no generado: {e}")

        self.done.emit(True, self.out)

    def _gen_pdf(self, all_rows, nc, path):
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
        from reportlab.lib import colors
        from reportlab.lib.units import cm

        doc = SimpleDocTemplate(path, pagesize=landscape(A4),
                                leftMargin=1*cm, rightMargin=1*cm,
                                topMargin=1.5*cm, bottomMargin=1.5*cm)
        table_data = []
        row_styles = []

        for i, (kind, row) in enumerate(all_rows):
            r = (list(row) + [""] * nc)[:nc]
            table_data.append([str(v) if v else "" for v in r])
            if kind == "header":
                row_styles += [
                    ("BACKGROUND",  (0, i), (-1, i), colors.HexColor("#1A3A5C")),
                    ("TEXTCOLOR",   (0, i), (-1, i), colors.white),
                    ("FONTNAME",    (0, i), (-1, i), "Helvetica-Bold"),
                    ("FONTSIZE",    (0, i), (-1, i), 8),
                ]
            elif kind == "sep":
                row_styles += [
                    ("BACKGROUND",  (0, i), (-1, i), colors.HexColor("#DDE6EF")),
                    ("FONTNAME",    (0, i), (-1, i), "Helvetica-Oblique"),
                    ("FONTSIZE",    (0, i), (-1, i), 7),
                    ("SPAN",        (0, i), (-1, i)),
                ]
            else:
                bg = colors.HexColor("#EDF3FB") if i % 2 == 0 else colors.white
                row_styles += [
                    ("BACKGROUND",  (0, i), (-1, i), bg),
                    ("FONTSIZE",    (0, i), (-1, i), 7),
                ]

        if not table_data:
            return

        page_w = landscape(A4)[0] - 2 * cm
        col_w  = page_w / max(nc, 1)
        t = Table(table_data, colWidths=[col_w] * nc, repeatRows=1)
        t.setStyle(TableStyle(row_styles + [
            ("FONTNAME",      (0, 1), (-1, -1), "Helvetica"),
            ("GRID",          (0, 0), (-1, -1), 0.3, colors.HexColor("#C0CDD8")),
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING",   (0, 0), (-1, -1), 3),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 3),
            ("TOPPADDING",    (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("WORDWRAP",      (0, 0), (-1, -1), "LTR"),
        ]))
        doc.build([t])

    def _csv(self):
        all_rows, _ = self._extract()
        if not all_rows:
            self.done.emit(False, "No se extrajeron datos. Revisá la configuración de grupos.")
            return
        self.log.emit("💾 Guardando CSV..."); self.progress.emit(95)
        with open(self.out, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            for kind, row in all_rows:
                if kind != "sep": w.writerow(row)
        self.progress.emit(100); self.done.emit(True, self.out)


# ══════════════════════════════════════════════════════════════════════
#  WORKER DE PREVISUALIZACIÓN
# ══════════════════════════════════════════════════════════════════════
class PreviewWorker(QThread):
    """Extrae las primeras N páginas activas y emite las filas para previsualizar."""
    ready = pyqtSignal(list, list)   # (headers, rows)
    error = pyqtSignal(str)
    log   = pyqtSignal(str)

    def __init__(self, path, groups, overrides, n_pages=3, y_tol=3, selected_pages=None,
                 word_gap=1.3, x_min=0, ocr_enabled=False, ocr_lang="spa+eng", ocr_rotation=0,
                 ocr_enhance="", ocr_min_conf=30):
        super().__init__()
        self.path           = path
        self.groups         = groups
        self.overrides      = overrides
        self.n_pages        = n_pages
        self.y_tol          = y_tol
        self.word_gap       = word_gap
        self.x_min          = x_min
        self.ocr_enabled    = ocr_enabled
        self.ocr_lang       = ocr_lang
        self.ocr_rotation   = ocr_rotation
        self.ocr_enhance    = ocr_enhance
        self.ocr_min_conf   = ocr_min_conf
        self.selected_pages = selected_pages   # set de pn(1-based); None = todas

    def run(self):
        try:
            headers = None
            all_rows = []
            pages_done = 0
            with pdfplumber.open(self.path) as pdf:
                total = len(pdf.pages)
                for pn_0 in range(total):
                    if self.isInterruptionRequested():
                        return   # cancelación cooperativa (sin terminate())
                    if pages_done >= self.n_pages:
                        break
                    pn = pn_0 + 1
                    # Filtrar por selección de miniaturas
                    if self.selected_pages is not None and pn not in self.selected_pages:
                        continue
                    grp = None
                    for g in self.groups:
                        if g["active"] and g["p_from"] <= pn <= g["p_to"]:
                            grp = g; break
                    if grp is None:
                        continue
                    ov      = self.overrides.get(pn, {})
                    start_y = ov.get("start_y", grp["start_y"])
                    end_y   = ov.get("end_y",   grp["end_y"])
                    pg      = pdf.pages[pn_0]
                    wds     = _extract_palabras(pg, self.y_tol, self.word_gap, self.x_min,
                                                ocr_enabled=self.ocr_enabled, ocr_lang=self.ocr_lang,
                                                ocr_rotation=self.ocr_rotation,
                                                ocr_enhance=self.ocr_enhance,
                                                ocr_min_conf=self.ocr_min_conf,
                                                log_fn=self.log.emit)
                    do_merge  = grp.get("merge_rows", False)
                    do_split  = grp.get("split_col", False)
                    split_idx = grp.get("split_col_idx", 1)
                    split_n   = grp.get("split_n_parts", 2)
                    do_kw     = grp.get("kw_split", False)
                    kw_col    = grp.get("kw_col", 1)
                    keywords  = grp.get("keywords", [])
                    merge_sep = _SPLIT_SEP if (do_merge and do_split) else " "

                    page_rows = rows_from(wds, grp["seps"], self.y_tol, start_y, end_y)
                    if do_merge and page_rows:
                        page_rows = merge_rows(page_rows,
                                               anchor_col=grp.get("anchor_col", 0),
                                               split_sep=merge_sep)
                    if do_split and page_rows:
                        page_rows = split_column(page_rows, col=split_idx, n_parts=split_n)
                    if do_kw and page_rows and keywords:
                        page_rows = split_by_keywords(page_rows, kw_col, keywords)
                    if not page_rows:
                        pages_done += 1; continue
                    if headers is None:
                        headers = list(page_rows[0])
                        if do_split and split_idx < len(headers):
                            base = headers[split_idx].strip() or f"Col{split_idx + 1}"
                            for k in range(split_n):
                                ci = split_idx + k
                                if ci < len(headers):
                                    headers[ci] = f"{base} {k + 1}"
                        if do_kw and kw_col < len(headers):
                            base = headers[kw_col].strip() or f"Col{kw_col + 1}"
                            headers.insert(kw_col + 1, f"{base} (resto)")
                        data = page_rows[1:]
                    else:
                        data = page_rows
                        if data and same_hdr(data[0], headers):
                            data = data[1:]
                    all_rows.extend(data)
                    pages_done += 1
            self.ready.emit(headers or [], all_rows[:300])
        except Exception:
            import traceback
            self.error.emit(traceback.format_exc())


# ══════════════════════════════════════════════════════════════════════
#  WORKER: rotación de páginas PDF
# ══════════════════════════════════════════════════════════════════════
class PDFRotator(QThread):
    progress = pyqtSignal(int)
    log      = pyqtSignal(str)
    done     = pyqtSignal(bool, str)   # no usar 'finished': enmascara QThread.finished

    def __init__(self, path, out, pages_to_rotate, angle):
        super().__init__()
        self.path            = path
        self.out             = out
        self.pages_to_rotate = pages_to_rotate  # set de pn 1-based, o None = todas
        self.angle           = angle             # 90, 180, 270

    def run(self):
        try:
            from pypdf import PdfReader, PdfWriter
        except ImportError:
            self.log.emit("⚠ pypdf no instalado. Ejecutá:  pip install pypdf")
            self.done.emit(False, "pypdf no disponible")
            return
        try:
            reader = PdfReader(self.path)
            writer = PdfWriter()
            total  = len(reader.pages)
            n_rot  = 0
            for i, page in enumerate(reader.pages):
                pn = i + 1
                if self.pages_to_rotate is None or pn in self.pages_to_rotate:
                    page.rotate(self.angle)
                    n_rot += 1
                writer.add_page(page)
                self.progress.emit(int((i + 1) / total * 95))
            with open(self.out, "wb") as f:
                writer.write(f)
            self.progress.emit(100)
            self.log.emit(f"✅ {n_rot} página(s) rotadas {self.angle}°  →  {self.out}")
            self.done.emit(True, self.out)
        except PermissionError:
            msg = f"Sin permiso para guardar:\n{self.out}\nCerrá el archivo si está abierto."
            self.log.emit(f"❌ {msg}"); self.done.emit(False, msg)
        except Exception as e:
            import traceback
            self.log.emit(f"❌ {traceback.format_exc()}")
            self.done.emit(False, str(e))


# ══════════════════════════════════════════════════════════════════════
#  WORKER: auto-detección de separadores (antes corría en el hilo GUI,
#  bloqueando la interfaz y compitiendo con el OCR del preview → crash)
# ══════════════════════════════════════════════════════════════════════
class AutoSepsWorker(QThread):
    result = pyqtSignal(int, list)   # (group_idx, seps)
    error  = pyqtSignal(str)

    def __init__(self, path, page_idx, grp_idx, params):
        super().__init__()
        self.path     = path
        self.page_idx = page_idx
        self.grp_idx  = grp_idx
        self.params   = params

    def run(self):
        try:
            with pdfplumber.open(self.path) as pdf:
                if self.page_idx >= len(pdf.pages):
                    self.error.emit(f"La página {self.page_idx + 1} no existe en el PDF")
                    return
                seps, _ = auto_seps(pdf.pages[self.page_idx], **self.params)
            self.result.emit(self.grp_idx, seps)
        except Exception as e:
            self.error.emit(str(e))


# ══════════════════════════════════════════════════════════════════════
#  SCROLL AREA CON SEGUIMIENTO DE POSICIÓN (para sync scroll)
# ══════════════════════════════════════════════════════════════════════
class TrackedScrollArea(QScrollArea):
    scroll_pct = pyqtSignal(float)
    def _emit(self):
        vsb = self.verticalScrollBar()
        if vsb.maximum() > 0:
            self.scroll_pct.emit(vsb.value() / vsb.maximum())
    def wheelEvent(self, ev):
        super().wheelEvent(ev); self._emit()
    def scrollContentsBy(self, dx, dy):
        super().scrollContentsBy(dx, dy); self._emit()


# ══════════════════════════════════════════════════════════════════════
#  DIÁLOGO DE DIVISIÓN VISUAL (absorbido del M1)
# ══════════════════════════════════════════════════════════════════════
class DialogoDividirVisual(QDialog):
    def __init__(self, text, col_name, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Dividir Columna Visualmente")
        self.setMinimumWidth(450)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(
            f"Columna objetivo: <b>{col_name}</b><br><br>"
            "Seleccioná (pintá) en el recuadro el texto o espacio de corte y apretá el botón."))

        self.e_sample = QLineEdit(text)
        self.e_sample.setReadOnly(True)
        self.e_sample.setStyleSheet("font-size: 14px; padding: 6px; letter-spacing: 1px;")
        lay.addWidget(self.e_sample)

        btn_grab = QPushButton("Usar selección como separador")
        btn_grab.setStyleSheet("font-weight: bold; padding: 6px;")
        btn_grab.clicked.connect(
            lambda: self.e_sep.setText(self.e_sample.selectedText())
            if self.e_sample.selectedText() else None)
        lay.addWidget(btn_grab)

        form = QFormLayout()
        self.e_sep = QLineEdit(" ")
        self.cmb_keep = QComboBox()
        self.cmb_keep.addItems(["Eliminar sep.", "Unir a Izq.", "Unir a Der."])
        self.e_left  = QLineEdit("COL_IZQ")
        self.e_right = QLineEdit("COL_DER")
        form.addRow("Separador:",                self.e_sep)
        form.addRow("Accion del separador?:",    self.cmb_keep)
        form.addRow("Nombre Izquierda:",         self.e_left)
        form.addRow("Nombre Derecha:",           self.e_right)
        lay.addLayout(form)

        bbox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bbox.accepted.connect(self.accept)
        bbox.rejected.connect(self.reject)
        lay.addWidget(bbox)
        if parent:
            self.setStyleSheet(parent.styleSheet())

    def get_data(self):
        return self.e_sep.text(), self.e_left.text(), self.e_right.text(), self.cmb_keep.currentText()


# ══════════════════════════════════════════════════════════════════════
#  MINIATURA INTERACTIVA
# ══════════════════════════════════════════════════════════════════════
class ThumbWidget(QWidget):
    clicked     = pyqtSignal(int, int)  # idx, modifiers → toggle selección
    dbl_clicked = pyqtSignal(int)       # idx → ver en visor canvas

    def __init__(self, idx, parent=None):
        super().__init__(parent)
        self.idx           = idx
        self._pix          = None
        self._sel          = False
        self._grp_col      = None   # color del grupo asignado
        self._has_override = False  # override Y individual
        self.setFixedSize(THUMB_W + 10, THUMB_H + 36)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setToolTip(
            f"Página {idx + 1}\n"
            "• Clic = marcar/desmarcar\n"
            "• Shift+clic = marcar rango\n"
            "• Doble clic = ver en visor"
        )

    def set_pixmap(self, pix): self._pix = pix; self.update()
    def set_selected(self, v): self._sel = v; self.update()
    def set_group_color(self, col): self._grp_col = col; self.update()
    def set_override(self, v): self._has_override = v; self.update()

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            mods = ev.modifiers()
            # Codificar modificadores como int simple (evita problemas con enums PyQt6)
            mod_int = 0
            if mods & Qt.KeyboardModifier.ShiftModifier:   mod_int |= 1
            if mods & Qt.KeyboardModifier.ControlModifier: mod_int |= 2
            self.clicked.emit(self.idx, mod_int)

    def mouseDoubleClickEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self.dbl_clicked.emit(self.idx)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRect(5, 5, THUMB_W, THUMB_H)

        # Fondo
        bg = QColor(T("card"))
        p.fillRect(r, bg)

        # Imagen o placeholder
        if self._pix:
            p.drawPixmap(r, self._pix.scaled(r.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))
        else:
            p.setPen(QColor(T("muted")))
            p.setFont(QFont("Arial", 8))
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, "...")

        # Borde grupo
        if self._grp_col:
            pen = QPen(QColor(self._grp_col), 4)
            p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(r.adjusted(1,1,-1,-1))

        # Borde selección
        if self._sel:
            pen = QPen(QColor(T("accent")), 3)
            p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(r.adjusted(1,1,-1,-1))
            # Check
            p.setBrush(QBrush(QColor(T("accent"))))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(r.right() - 16, r.top(), 16, 16)
            p.setPen(QPen(QColor("white"), 2))
            p.drawText(r.right() - 16, r.top(), 16, 16,
                       Qt.AlignmentFlag.AlignCenter, "✓")

        # Badge override (esquina inferior izquierda)
        if self._has_override:
            OV_COL = QColor("#F59E0B")
            p.setBrush(QBrush(OV_COL)); p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(r.left(), r.bottom() - 14, 14, 14)
            p.setPen(QPen(QColor("white"), 1))
            p.setFont(QFont("Arial", 6, QFont.Weight.Bold))
            p.drawText(r.left(), r.bottom() - 14, 14, 14,
                       Qt.AlignmentFlag.AlignCenter, "Y")

        # Número de página
        lbl = str(self.idx + 1)
        p.setFont(QFont("Arial", 8, QFont.Weight.Bold))
        p.setPen(QColor(T("text")))
        p.drawText(QRect(5, THUMB_H + 8, THUMB_W, 20),
                   Qt.AlignmentFlag.AlignCenter, lbl)
        p.end()


# ══════════════════════════════════════════════════════════════════════
#  PANEL DE CONFIGURACIÓN DE UN GRUPO
# ══════════════════════════════════════════════════════════════════════
GRP_COLORS = ["#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6"]

class GroupPanel(QWidget):
    """Panel de configuración de un grupo de páginas."""
    changed = pyqtSignal()

    MAX_HISTORY = 20

    def __init__(self, idx, parent=None):
        super().__init__(parent)
        self.idx    = idx
        self._color = GRP_COLORS[idx % len(GRP_COLORS)]
        self._history = []        # pila de estados para undo
        self._suppress_history = False   # evita guardar durante restore
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(4)

        # Nombre + activo
        h0 = QHBoxLayout()
        dot = QLabel("●"); dot.setStyleSheet(f"color:{self._color};font-size:14px;")
        h0.addWidget(dot)
        self.ck_active = QCheckBox(f"Grupo {self.idx + 1}")
        self.ck_active.setChecked(self.idx == 0)
        self.ck_active.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        self.ck_active.stateChanged.connect(self._save_and_changed)
        h0.addWidget(self.ck_active, 1)
        lay.addLayout(h0)

        # Rango de páginas
        h1 = QHBoxLayout(); h1.setSpacing(4)
        h1.addWidget(QLabel("Págs:"))
        self.sp_from = QSpinBox(); self.sp_from.setRange(1, 9999)
        self.sp_from.setValue(1); self.sp_from.setFixedWidth(58)
        self.sp_from.valueChanged.connect(self._save_and_changed)
        h1.addWidget(self.sp_from)
        h1.addWidget(QLabel("a"))
        self.sp_to = QSpinBox(); self.sp_to.setRange(1, 9999)
        self.sp_to.setValue(9999); self.sp_to.setFixedWidth(58)
        self.sp_to.valueChanged.connect(self._save_and_changed)
        h1.addWidget(self.sp_to)
        lay.addLayout(h1)

        # Inicio Y / Fin Y
        h2 = QHBoxLayout(); h2.setSpacing(4)
        h2.addWidget(QLabel("Inicio Y:"))
        self.sp_start_y = QSpinBox(); self.sp_start_y.setRange(0, 9999)
        self.sp_start_y.setValue(0); self.sp_start_y.setSuffix("pt")
        self.sp_start_y.setFixedWidth(68); self.sp_start_y.setToolTip("0 = desde arriba")
        self.sp_start_y.valueChanged.connect(self._save_and_changed)
        h2.addWidget(self.sp_start_y)
        h2.addWidget(QLabel("Fin Y:"))
        self.sp_end_y = QSpinBox(); self.sp_end_y.setRange(0, 9999)
        self.sp_end_y.setValue(0); self.sp_end_y.setSuffix("pt")
        self.sp_end_y.setFixedWidth(68); self.sp_end_y.setToolTip("0 = hasta abajo")
        self.sp_end_y.valueChanged.connect(self._save_and_changed)
        h2.addWidget(self.sp_end_y)
        lay.addLayout(h2)

        # Columnas (separadores en texto)
        h3 = QHBoxLayout(); h3.setSpacing(4)
        h3.addWidget(QLabel("Columnas (px separados por comas):"))
        lay.addLayout(h3)
        self.e_seps = QLineEdit()
        self.e_seps.setPlaceholderText("ej: 45 120 200 310  (vacío = auto)")
        self.e_seps.setToolTip("Posiciones X de los separadores en puntos PDF.\n"
                               "Usá 'Tomar del M1' para copiar las líneas actuales.")
        # textChanged NO guarda historial (cada tecla creaba un snapshot y
        # vaciaba la pila de undo); el snapshot se toma al terminar de editar.
        self.e_seps.textChanged.connect(lambda *_: self.changed.emit())
        self.e_seps.editingFinished.connect(self.save_to_history)
        lay.addWidget(self.e_seps)

        # Botones
        h4 = QHBoxLayout(); h4.setSpacing(3)
        self.btn_auto = QPushButton("🔄 Auto")
        self.btn_auto.setToolTip("Auto-detectar columnas en la primera página del rango")
        self.btn_auto.setFixedHeight(24)
        h4.addWidget(self.btn_auto)
        self.btn_from_m1 = QPushButton("📐 Tomar del visor")
        self.btn_from_m1.setToolTip("Copiar separadores desde el visor de la derecha")
        self.btn_from_m1.setFixedHeight(24)
        h4.addWidget(self.btn_from_m1)
        self.btn_undo = QPushButton("↩ Volver")
        self.btn_undo.setToolTip("Deshacer el último cambio")
        self.btn_undo.setFixedHeight(24)
        self.btn_undo.setObjectName("btnUndo")
        self.btn_undo.setEnabled(False)
        self.btn_undo.clicked.connect(self._undo)
        h4.addWidget(self.btn_undo)
        lay.addLayout(h4)

        # Y rápido desde visor
        h5 = QHBoxLayout(); h5.setSpacing(3)
        self.btn_set_start = QPushButton("🔵 Tomar Inicio Y del visor")
        self.btn_set_start.setFixedHeight(22)
        self.btn_set_end   = QPushButton("🟢 Tomar Fin Y del visor")
        self.btn_set_end.setFixedHeight(22)
        h5.addWidget(self.btn_set_start); h5.addWidget(self.btn_set_end)
        lay.addLayout(h5)

        # ── Fusión de renglones de continuación ───────────────────────
        sep_merge = QFrame(); sep_merge.setFrameShape(QFrame.Shape.HLine)
        sep_merge.setStyleSheet("color:#2E4060;"); lay.addWidget(sep_merge)

        lbl_merge_sec = QLabel("UNIR RENGLONES DE CONTINUACIÓN")
        lbl_merge_sec.setStyleSheet("font-size:8px;font-weight:bold;letter-spacing:1px;color:#8BA0B8;padding-top:2px;")
        lay.addWidget(lbl_merge_sec)

        h6 = QHBoxLayout(); h6.setSpacing(4)
        self.ck_merge = QCheckBox("Activar fusión de filas")
        self.ck_merge.setToolTip(
            "¿CUÁNDO USARLO?\n"
            "Cuando el PDF tiene celdas con texto largo que se parte en\n"
            "varias líneas. Cada línea aparece como fila separada, y esta\n"
            "opción las vuelve a unir en una sola fila.\n\n"
            "¿CÓMO FUNCIONA?\n"
            "El programa mira la columna ancla (ej: Fecha). Si esa columna\n"
            "tiene dato → nueva fila. Si está VACÍA → continuación de la\n"
            "fila anterior (se fusiona).\n\n"
            "¿QUÉ PONER EN 'COL. ANCLA'?\n"
            "La columna que SIEMPRE tiene dato en filas nuevas y está VACÍA\n"
            "en las líneas de continuación. Para extractos bancarios suele\n"
            "ser col. 0 (Fecha).\n\n"
            "⚠ Si activas esto y el resultado empeora, probá cambiar el\n"
            "   número de columna ancla."
        )
        self.ck_merge.stateChanged.connect(self._save_and_changed)
        h6.addWidget(self.ck_merge)
        lbl_anc = QLabel("Col. ancla:")
        lbl_anc.setToolTip("Número de columna que identifica el inicio de una fila nueva\n"
                           "(0 = primera columna, que suele ser la Fecha)")
        h6.addWidget(lbl_anc)
        self.sp_anchor = QSpinBox()
        self.sp_anchor.setRange(0, 20)
        self.sp_anchor.setValue(0)
        self.sp_anchor.setFixedWidth(48)
        self.sp_anchor.setToolTip("0 = primera col. (ej: Fecha)\n"
                                  "Esa col. debe estar vacía en las filas de continuación\n"
                                  "y con dato en las filas nuevas.")
        self.sp_anchor.valueChanged.connect(self._save_and_changed)
        h6.addWidget(self.sp_anchor)
        h6.addStretch()
        lay.addLayout(h6)

        lbl_merge_hint = QLabel("💡 La col. ancla es la que nunca está vacía en filas nuevas (ej: Fecha=col 0)")
        lbl_merge_hint.setWordWrap(True)
        lbl_merge_hint.setStyleSheet("color:#8BA0B8;font-size:8px;padding-left:2px;")
        lay.addWidget(lbl_merge_hint)

        # ── Dividir columna en sub-columnas ────────────────────────────
        sep_split = QFrame(); sep_split.setFrameShape(QFrame.Shape.HLine)
        sep_split.setStyleSheet("color:#2E4060;"); lay.addWidget(sep_split)

        lbl_split_sec = QLabel("DIVIDIR COLUMNA EN SUB-COLUMNAS")
        lbl_split_sec.setStyleSheet("font-size:8px;font-weight:bold;letter-spacing:1px;color:#8BA0B8;padding-top:2px;")
        lay.addWidget(lbl_split_sec)

        h7 = QHBoxLayout(); h7.setSpacing(4)
        self.ck_split = QCheckBox("Activar división")
        self.ck_split.setToolTip(
            "Divide una columna fusionada en sub-columnas.\n"
            "Funciona junto con 'Activar fusión': primero se fusionan las\n"
            "líneas de continuación (separadas por \\x00 internamente),\n"
            "luego se separan en columnas distintas.\n\n"
            "Ejemplo: Descripción con 2 líneas → Descripción 1 + Descripción 2")
        self.ck_split.stateChanged.connect(self._save_and_changed)
        h7.addWidget(self.ck_split)
        h7.addWidget(QLabel("Col:"))
        self.sp_split_col = QSpinBox()
        self.sp_split_col.setRange(0, 20)
        self.sp_split_col.setValue(1)
        self.sp_split_col.setFixedWidth(48)
        self.sp_split_col.setToolTip("Índice de columna a dividir (0 = primera)\nSuele ser la col. de Descripción")
        self.sp_split_col.valueChanged.connect(self._save_and_changed)
        h7.addWidget(self.sp_split_col)
        h7.addWidget(QLabel("en"))
        self.sp_split_parts = QSpinBox()
        self.sp_split_parts.setRange(2, 6)
        self.sp_split_parts.setValue(2)
        self.sp_split_parts.setFixedWidth(42)
        self.sp_split_parts.setToolTip("Cantidad de sub-columnas resultado\n(= número máximo de líneas por celda en el PDF)")
        self.sp_split_parts.valueChanged.connect(self._save_and_changed)
        h7.addWidget(self.sp_split_parts)
        h7.addWidget(QLabel("partes"))
        h7.addStretch()
        lay.addLayout(h7)

        # ── Corte por palabras clave ───────────────────────────────
        sep_kw = QFrame(); sep_kw.setFrameShape(QFrame.Shape.HLine)
        sep_kw.setStyleSheet("color:#2E4060;"); lay.addWidget(sep_kw)

        h8 = QHBoxLayout(); h8.setSpacing(4)
        self.ck_kw = QCheckBox("Corte por palabras clave")
        self.ck_kw.setToolTip(
            "Divide una columna cuando el texto contiene una de las palabras clave.\n"
            "El texto hasta la keyword queda en la columna original.\n"
            "El texto después de la keyword pasa a la columna siguiente (nueva).")
        self.ck_kw.stateChanged.connect(self._save_and_changed)
        h8.addWidget(self.ck_kw)
        h8.addWidget(QLabel("en col:"))
        self.sp_kw_col = QSpinBox(); self.sp_kw_col.setRange(0, 20)
        self.sp_kw_col.setValue(1); self.sp_kw_col.setFixedWidth(46)
        self.sp_kw_col.setToolTip("Columna donde buscar las keywords (0=primera)")
        self.sp_kw_col.valueChanged.connect(self._save_and_changed)
        h8.addWidget(self.sp_kw_col); h8.addStretch()
        lay.addLayout(h8)

        # Lista de keywords
        self.lw_kw = QListWidget(); self.lw_kw.setFixedHeight(72)
        self.lw_kw.setToolTip("Keywords activas. El texto se corta justo después de la keyword encontrada.")
        lay.addWidget(self.lw_kw)

        h9 = QHBoxLayout(); h9.setSpacing(3)
        self.le_kw = QLineEdit(); self.le_kw.setPlaceholderText("Escribí una keyword y presioná Agregar")
        self.le_kw.returnPressed.connect(self._add_kw)
        btn_kw_add = QPushButton("Agregar"); btn_kw_add.setFixedHeight(24)
        btn_kw_add.setFixedWidth(68); btn_kw_add.clicked.connect(self._add_kw)
        btn_kw_del = QPushButton("Quitar sel."); btn_kw_del.setFixedHeight(24)
        btn_kw_del.setFixedWidth(72); btn_kw_del.clicked.connect(self._del_kw)
        h9.addWidget(self.le_kw, 1); h9.addWidget(btn_kw_add); h9.addWidget(btn_kw_del)
        lay.addLayout(h9)

        lbl_kw_hint = QLabel("💡 Tip: las keywords más largas tienen prioridad. "
                             "Agregá primero 'TRANSFERENCIA DE TERCEROS' y luego 'TRANSFERENCIA'.")
        lbl_kw_hint.setWordWrap(True)
        lbl_kw_hint.setStyleSheet("color:#8BA0B8;font-size:8px;")
        lay.addWidget(lbl_kw_hint)
        # Guardar estado inicial en historial (permite deshacer el primer cambio)
        QTimer.singleShot(0, self.save_to_history)

    # ── Historial (Undo) ──────────────────────────────────────────────
    def _snapshot(self):
        """Guarda el estado actual en la pila de historial (máx 20)."""
        if self._suppress_history:
            return
        cfg = self.get_config()
        if self._history and self._history[-1] == cfg:
            return   # no duplicar si no cambió nada
        self._history.append(cfg)
        if len(self._history) > self.MAX_HISTORY:
            self._history.pop(0)
        self.btn_undo.setEnabled(True)

    def _save_and_changed(self, *_):
        """Guarda snapshot ANTES del cambio y luego emite changed."""
        if not self._suppress_history:
            # Tomamos snapshot del estado ANTERIOR (antes del cambio actual)
            # Para eso necesitamos guardar antes de que el widget se actualice
            # Como ya se actualizó, guardamos el estado post-cambio para que
            # el próximo _save_and_changed lo tome como estado anterior.
            # El truco: guardamos antes de que changed llegue al parent.
            if not self._history or self._history[-1] != self.get_config():
                self._history.append(self.get_config())
                if len(self._history) > self.MAX_HISTORY:
                    self._history.pop(0)
                self.btn_undo.setEnabled(len(self._history) > 1)
        self.changed.emit()

    def save_to_history(self):
        """Guarda el estado actual explícitamente (llamado externamente antes de cambios masivos)."""
        cfg = self.get_config()
        if not self._history or self._history[-1] != cfg:
            self._history.append(cfg)
            if len(self._history) > self.MAX_HISTORY:
                self._history.pop(0)
            self.btn_undo.setEnabled(True)

    def _undo(self):
        """Restaura el último estado guardado en la pila."""
        if len(self._history) < 2:
            return
        self._history.pop()   # quitar el estado actual
        prev = self._history[-1]
        self._suppress_history = True
        try:
            self.set_config(prev)
        finally:
            self._suppress_history = False
        self.btn_undo.setEnabled(len(self._history) > 1)
        self.changed.emit()

    def _add_kw(self):
        txt = self.le_kw.text().strip().upper()
        if not txt: return
        # No duplicar
        for i in range(self.lw_kw.count()):
            if self.lw_kw.item(i).text() == txt: return
        self.save_to_history()
        self.lw_kw.addItem(txt)
        self.le_kw.clear()
        self.changed.emit()

    def _del_kw(self):
        self.save_to_history()
        for item in self.lw_kw.selectedItems():
            self.lw_kw.takeItem(self.lw_kw.row(item))
        self.changed.emit()

    def get_config(self):
        seps_txt = self.e_seps.text().strip()
        seps = []
        if seps_txt:
            try:
                seps = [float(x) for x in seps_txt.replace(",", " ").split() if x]
            except: seps = []
        keywords = [self.lw_kw.item(i).text() for i in range(self.lw_kw.count())]
        return {
            "name":         f"Grupo {self.idx + 1}",
            "active":       self.ck_active.isChecked(),
            "p_from":       self.sp_from.value(),
            "p_to":         self.sp_to.value(),
            "start_y":      float(self.sp_start_y.value()),
            "end_y":        float(self.sp_end_y.value()),
            "seps":         seps,
            "merge_rows":   self.ck_merge.isChecked(),
            "anchor_col":   self.sp_anchor.value(),
            "split_col":    self.ck_split.isChecked(),
            "split_col_idx": self.sp_split_col.value(),
            "split_n_parts": self.sp_split_parts.value(),
            "kw_split":     self.ck_kw.isChecked(),
            "kw_col":       self.sp_kw_col.value(),
            "keywords":     keywords,
        }

    def set_config(self, cfg):
        self.ck_active.setChecked(cfg.get("active", True))
        self.sp_from.setValue(cfg.get("p_from", 1))
        self.sp_to.setValue(cfg.get("p_to", 9999))
        self.sp_start_y.setValue(int(cfg.get("start_y", 0)))
        self.sp_end_y.setValue(int(cfg.get("end_y", 0)))
        seps = cfg.get("seps", [])
        self.e_seps.setText(" ".join(str(int(s)) for s in seps))
        self.ck_merge.setChecked(cfg.get("merge_rows", False))
        self.sp_anchor.setValue(cfg.get("anchor_col", 0))
        self.ck_split.setChecked(cfg.get("split_col", False))
        self.sp_split_col.setValue(cfg.get("split_col_idx", 1))
        self.sp_split_parts.setValue(cfg.get("split_n_parts", 2))
        self.ck_kw.setChecked(cfg.get("kw_split", False))
        self.sp_kw_col.setValue(cfg.get("kw_col", 1))
        self.lw_kw.clear()
        for kw in cfg.get("keywords", []):
            self.lw_kw.addItem(kw.upper())

    def set_seps(self, seps):
        self.e_seps.setText(" ".join(str(int(s)) for s in sorted(seps)))
        self.save_to_history()   # cambios programáticos (visor/auto) sí van al undo

    def set_start_y(self, y):
        self.sp_start_y.setValue(int(y))

    def set_end_y(self, y):
        self.sp_end_y.setValue(int(y))


# ══════════════════════════════════════════════════════════════════════
#  MINI CANVAS — vista ampliada con líneas de inicio/fin y columnas
# ══════════════════════════════════════════════════════════════════════
class MiniCanvas(QWidget):
    """Vista ampliada de una página con líneas de inicio, fin y columnas."""
    seps_changed    = pyqtSignal(list)
    start_y_changed = pyqtSignal(float)
    end_y_changed   = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setCursor(QCursor(Qt.CursorShape.CrossCursor))
        self._pix      = None
        self._pix_orig = None   # pixmap sin rotar (para re-aplicar rotación)
        self._pdf_w    = 1.0; self._pdf_h = 1.0
        self._zoom     = 1.0
        self._fit_mode = True
        self._seps     = []
        self._start_y  = 0.0; self._end_y = 0.0
        self._drag     = None
        self._hover    = None
        self._display_rotation = 0   # 0 / 90 / 180 / 270 grados CW
        self._enhance_mode = ""      # vista previa de limpieza OCR ("", suave, media, fuerte)

    def set_ocr_enhance(self, modo):
        """El canvas mostrará la imagen como la verá el OCR ('' = original).
        Requiere recargar la página (load_page) para que tome efecto."""
        self._enhance_mode = modo

    def set_display_rotation(self, angle):
        """Rota la VISTA del canvas (no el PDF). angle en grados CW."""
        self._display_rotation = angle % 360
        if self._pix_orig:
            self._apply_display_rotation()
            self._fit_mode = True
            self.setMinimumSize(0, 0)
            self._fit()
        self.update()

    def _apply_display_rotation(self):
        """Aplica la rotación visual al pixmap original."""
        if not self._pix_orig:
            self._pix = None; return
        if self._display_rotation == 0:
            self._pix = self._pix_orig
        else:
            from PyQt6.QtGui import QTransform
            t = QTransform(); t.rotate(self._display_rotation)
            self._pix = self._pix_orig.transformed(t)

    # ── Coord helpers ──────────────────────────────────────────────────
    # El canvas trabaja SIEMPRE en "espacio de lectura": el de la vista
    # rotada que se muestra en pantalla. La extracción (OCR y texto
    # embebido) entrega coordenadas en ese mismo espacio, así que las
    # transformaciones son directas para cualquier rotación.
    def _iw(self): return int(self._pix.width()  * self._zoom) if self._pix else 300
    def _ih(self): return int(self._pix.height() * self._zoom) if self._pix else 400
    def _ox(self): return max((self.width()  - self._iw()) // 2, 0)
    def _oy(self): return max((self.height() - self._ih()) // 2, 0)

    def _eff_pdf_w(self):
        return self._pdf_h if self._display_rotation in (90, 270) else self._pdf_w
    def _eff_pdf_h(self):
        return self._pdf_w if self._display_rotation in (90, 270) else self._pdf_h

    def wx2pdf(self, wx):
        if not self._pix: return wx
        return (wx - self._ox()) / self._zoom * self._eff_pdf_w() / self._pix.width()

    def wy2pdf(self, wy):
        if not self._pix: return wy
        return (wy - self._oy()) / self._zoom * self._eff_pdf_h() / self._pix.height()

    def pdf2wx(self, px):
        if not self._pix: return px
        return px * self._pix.width() / self._eff_pdf_w() * self._zoom + self._ox()

    def pdf2wy(self, py):
        if not self._pix: return py
        return py * self._pix.height() / self._eff_pdf_h() * self._zoom + self._oy()

    def load_page(self, path, page_idx, dpi=150):
        try:
            with pdfplumber.open(path) as pdf:
                if page_idx >= len(pdf.pages): return
                pg = pdf.pages[page_idx]
                self._pdf_w, self._pdf_h = pg.width, pg.height
                img = _render_page_image(pg, dpi)
                if self._enhance_mode:
                    img = _mejorar_imagen(img, self._enhance_mode)
                buf = io.BytesIO(); img.save(buf, "PNG")
                self._pix_orig = QPixmap.fromImage(QImage.fromData(buf.getvalue()))
                self._apply_display_rotation()
        except Exception as e:
            self._pix = None; self._pix_orig = None; print(f"[MiniCanvas] {e}")
        # Al cargar nueva página resetear zoom automático
        self._fit_mode = True
        self.setMinimumSize(0, 0)
        self._fit(); self.update()

    def _fit(self):
        if not self._pix: return
        self._zoom = min(self.width() / max(self._pix.width(), 1),
                         self.height() / max(self._pix.height(), 1)) * 0.96

    def resizeEvent(self, ev):
        if self._fit_mode:
            self._fit()
        self.update()

    def wheelEvent(self, ev):
        """Ctrl+rueda = zoom; sin Ctrl = scroll normal."""
        if ev.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = ev.angleDelta().y()
            factor = 1.18 if delta > 0 else 1 / 1.18
            self._zoom = max(0.15, min(10.0, self._zoom * factor))
            self._fit_mode = False
            # Agrandar el widget para que el QScrollArea muestre scrollbars
            if self._pix:
                iw = int(self._pix.width()  * self._zoom) + 30
                ih = int(self._pix.height() * self._zoom) + 30
                self.setMinimumSize(iw, ih)
            self.update()
            ev.accept()
        else:
            super().wheelEvent(ev)

    def zoom_reset(self):
        """Doble click en canvas → vuelve a auto-fit."""
        self._fit_mode = True
        self.setMinimumSize(0, 0)
        self._fit(); self.update()

    def mouseDoubleClickEvent(self, ev):
        # Doble click SIN que haya sep cerca → reset zoom
        if not self._near_sep(ev.position().x()):
            self.zoom_reset()

    def set_seps(self, seps):    self._seps    = sorted(float(s) for s in seps); self.update()
    def get_seps(self):          return sorted(self._seps)
    def set_start_y(self, y):    self._start_y = float(y); self.update()
    def set_end_y(self, y):      self._end_y   = float(y); self.update()

    def _near_sep(self, wx):
        best, bd = None, SNAP * 2 + 1
        for i, s in enumerate(self._seps):
            d = abs(self.pdf2wx(s) - wx)
            if d < bd: bd, best = d, i
        return best if bd <= SNAP * 2 else None

    def _near_hline(self, wy, y_pdf):
        return y_pdf > 0 and abs(self.pdf2wy(y_pdf) - wy) <= SNAP * 2

    def mousePressEvent(self, ev):
        if not self._pix: return
        wx, wy = ev.position().x(), ev.position().y()
        idx = self._near_sep(wx)

        if ev.button() == Qt.MouseButton.RightButton:
            if idx is not None:
                self._seps.pop(idx); self.update()
                self.seps_changed.emit(self.get_seps())
            elif self._near_hline(wy, self._start_y):
                self._start_y = 0.0; self.update()
                self.start_y_changed.emit(0.0)
            elif self._near_hline(wy, self._end_y):
                self._end_y = 0.0; self.update()
                self.end_y_changed.emit(0.0)
            return

        if ev.button() == Qt.MouseButton.LeftButton:
            if self._near_hline(wy, self._start_y) and idx is None:
                self._drag = "start"; return
            if self._near_hline(wy, self._end_y) and idx is None:
                self._drag = "end"; return
            if idx is not None:
                self._drag = idx; return
            px = self.wx2pdf(wx)
            if 0 < px < self._eff_pdf_w():
                self._seps.append(px); self._seps.sort()
                self._drag = next(i for i, s in enumerate(self._seps) if abs(s - px) < 1)
                self.update(); self.seps_changed.emit(self.get_seps())

    def mouseMoveEvent(self, ev):
        if not self._pix: return
        wx, wy = ev.position().x(), ev.position().y()

        if self._drag == "start" and ev.buttons() & Qt.MouseButton.LeftButton:
            self._start_y = max(0.0, min(self._eff_pdf_h(), self.wy2pdf(wy)))
            self.update(); self.start_y_changed.emit(self._start_y); return

        if self._drag == "end" and ev.buttons() & Qt.MouseButton.LeftButton:
            self._end_y = max(0.0, min(self._eff_pdf_h(), self.wy2pdf(wy)))
            self.update(); self.end_y_changed.emit(self._end_y); return

        if isinstance(self._drag, int) and ev.buttons() & Qt.MouseButton.LeftButton:
            px = max(2.0, min(float(self._eff_pdf_w()) - 2, self.wx2pdf(wx)))
            self._seps[self._drag] = px; self._seps.sort()
            self._drag = min(range(len(self._seps)), key=lambda i: abs(self._seps[i] - px))
            self.update(); self.seps_changed.emit(self.get_seps()); return

        # Cursor hover
        self._hover = self._near_sep(wx)
        if self._hover is not None: self.setCursor(QCursor(Qt.CursorShape.SizeHorCursor))
        elif (self._near_hline(wy, self._start_y) or
              self._near_hline(wy, self._end_y)):
            self.setCursor(QCursor(Qt.CursorShape.SizeVerCursor))
        else: self.setCursor(QCursor(Qt.CursorShape.CrossCursor))

    def mouseReleaseEvent(self, ev):
        self._drag = None
        self.setCursor(QCursor(Qt.CursorShape.CrossCursor))

    def add_start_line(self):
        self._start_y = self._eff_pdf_h() * 0.12
        self.update(); self.start_y_changed.emit(self._start_y)

    def add_end_line(self):
        self._end_y = self._eff_pdf_h() * 0.88
        self.update(); self.end_y_changed.emit(self._end_y)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(T("canvas_bg")))

        if not self._pix:
            p.setPen(QColor(T("muted"))); p.setFont(QFont("Arial", 11))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                       "Hacé click en una miniatura\npara ver la página aquí")
            p.end(); return

        iw, ih = self._iw(), self._ih()
        ox, oy = self._ox(), self._oy()
        p.drawPixmap(ox, oy, iw, ih, self._pix)

        # ── Zona ignorada arriba (inicio) ────────────────────────────
        if self._start_y > 0:
            sy_w = int(self.pdf2wy(self._start_y))
            p.fillRect(ox, oy, iw, sy_w - oy, QColor(0, 0, 0, 70))
            p.setPen(QPen(QColor("#3B82F6"), 2.5))
            p.drawLine(ox, sy_w, ox + iw, sy_w)
            self._draw_hline_label(p, ox, sy_w, iw, "▶ Inicio tabla", "#3B82F6", above=False)

        # ── Zona ignorada abajo (fin) ─────────────────────────────────
        if self._end_y > 0:
            ey_w = int(self.pdf2wy(self._end_y))
            p.fillRect(ox, ey_w, iw, (oy + ih) - ey_w, QColor(0, 0, 0, 70))
            p.setPen(QPen(QColor("#10B981"), 2.5))
            p.drawLine(ox, ey_w, ox + iw, ey_w)
            self._draw_hline_label(p, ox, ey_w, iw, "◀ Fin tabla", "#10B981", above=True)

        # ── Separadores de columna ────────────────────────────────────
        for i, sp in enumerate(self._seps):
            wx_s = int(self.pdf2wx(sp))
            col  = QColor(T("hover_col")) if i == self._hover else QColor(T("line_col"))
            p.setPen(QPen(col, 2)); p.drawLine(wx_s, oy, wx_s, oy + ih)
            lbl = f"{i+1}|{i+2}"
            p.setFont(QFont("Arial", 7, QFont.Weight.Bold)); fm = p.fontMetrics()
            lw2, lh2 = fm.horizontalAdvance(lbl) + 8, fm.height() + 4
            lx2, ly2 = wx_s - lw2 // 2, oy + 14
            p.setBrush(QBrush(QColor(col.red(), col.green(), col.blue(), 200)))
            p.setPen(Qt.PenStyle.NoPen); p.drawRoundedRect(lx2, ly2, lw2, lh2, 3, 3)
            p.setPen(QColor("white")); p.drawText(lx2 + 4, ly2 + lh2 - 4, lbl)

        # ── Leyenda inferior ─────────────────────────────────────────
        p.fillRect(ox, oy + ih - 20, iw, 20, QColor(0,0,0,130))
        p.setPen(QColor(255,255,255,180)); p.setFont(QFont("Arial",7))
        p.drawText(ox+4, oy+ih-5,
                   "🔴 Click=col  ❌ Der=borrar  🔵 Drag azul=inicio  🟢 Drag verde=fin")
        p.end()

    def _draw_hline_label(self, p, ox, wy, iw, lbl, color, above):
        p.setFont(QFont("Arial", 7, QFont.Weight.Bold)); fm = p.fontMetrics()
        lw2, lh2 = fm.horizontalAdvance(lbl) + 10, fm.height() + 4
        lx2 = ox + iw // 2 - lw2 // 2
        ly2 = wy - lh2 - 3 if above else wy + 3
        c = QColor(color)
        p.setBrush(QBrush(QColor(c.red(), c.green(), c.blue(), 210)))
        p.setPen(Qt.PenStyle.NoPen); p.drawRoundedRect(lx2, ly2, lw2, lh2, 3, 3)
        p.setPen(QColor("white")); p.drawText(lx2 + 5, ly2 + lh2 - 4, lbl)


# ══════════════════════════════════════════════════════════════════════
#  WIDGET PRINCIPAL DEL MÓDULO 0
# ══════════════════════════════════════════════════════════════════════
class PreparadorWidget(QWidget):
    """Widget principal del Módulo 0 — embebible en QTabWidget."""

    receta_lista   = pyqtSignal(list)   # emite grupos cuando el usuario confirma
    excel_generado = pyqtSignal(str)    # ruta del archivo generado (para autocarga en M-I/M-III)
    limpiado       = pyqtSignal()       # Dentro de Navaja: se tocó «Limpiar»

    def __init__(self, dark=True, parent=None):
        super().__init__(parent)
        self._dark            = dark
        self._pdf_path        = ""
        self._total_pgs       = 0
        self._thumbs          = {}   # idx -> ThumbWidget
        self._loader          = None
        self._converter       = None
        self._preview_worker  = None
        self._preview_pending = False   # hay un preview encolado esperando que termine el actual
        self._current_page    = 0
        self._last_clicked    = 0
        self._canvas_page     = None
        self._page_overrides  = {}   # {page_num (1-based): {"start_y": float, "end_y": float}}
        # Cortes en cadena (absorbidos del M1)
        self.split_widgets    = []   # lista de dicts con widgets de cada corte
        self._sync_scroll_on  = True
        self._autoseps_worker = None
        # Excel/CSV editor
        self._csv_path        = ""
        self._csv_data        = []   # lista de listas (filas)
        self._csv_delim       = ";"  # delimitador detectado al abrir el CSV
        # Timer para debounce del preview (evita relanzar en cada drag de sep)
        self._preview_timer   = QTimer()
        self._preview_timer.setSingleShot(True)
        self._preview_timer.timeout.connect(self._update_preview)
        self._build()
        self._style()

    # ── Construcción UI ───────────────────────────────────────────────
    def _build(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0,0,0,0); root.setSpacing(0)

        hs = QSplitter(Qt.Orientation.Horizontal); hs.setHandleWidth(4)
        root.addWidget(hs)

        # ═══ PANEL IZQUIERDO (scroll + action bar fija) ══════════════
        left_outer = QWidget(); left_outer.setObjectName("leftPanel")
        left_outer.setMinimumWidth(330); left_outer.setMaximumWidth(420)
        lo_lay = QVBoxLayout(left_outer); lo_lay.setContentsMargins(0,0,0,0); lo_lay.setSpacing(0)
        hs.addWidget(left_outer)

        # Zona scrollable con tarjetas
        left_scroll = QScrollArea(); left_scroll.setObjectName("leftScroll")
        left_scroll.setWidgetResizable(True)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        left_content = QWidget(); left_content.setObjectName("leftContent")
        ll = QVBoxLayout(left_content); ll.setContentsMargins(10,10,10,10); ll.setSpacing(10)
        left_scroll.setWidget(left_content)
        lo_lay.addWidget(left_scroll, 1)

        # Barra de acción fija en la parte inferior
        conv_bar = QWidget(); conv_bar.setObjectName("convBar")
        cv = QVBoxLayout(conv_bar); cv.setContentsMargins(10,8,10,8); cv.setSpacing(5)
        self.btn_conv = QPushButton("⚡  PREPARAR → EXCEL / CSV")
        self.btn_conv.setObjectName("btnConv"); self.btn_conv.setMinimumHeight(42)
        self.btn_conv.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        self.btn_conv.clicked.connect(self._convert); cv.addWidget(self.btn_conv)
        self.pbar = QProgressBar(); self.pbar.setFixedHeight(4)
        self.pbar.setTextVisible(False); cv.addWidget(self.pbar)
        self.logbox = QTextEdit(); self.logbox.setReadOnly(True)
        self.logbox.setFont(QFont("Courier New", 8)); self.logbox.setMaximumHeight(50); cv.addWidget(self.logbox)
        dest_row = QHBoxLayout(); dest_row.setSpacing(4)
        self.e_out = QLineEdit(); self.e_out.setPlaceholderText("Destino .xlsx o .csv...")
        self.e_out.setReadOnly(True)
        bo = QPushButton("💾"); bo.setFixedSize(24,24); bo.clicked.connect(self._pick_out)
        dest_row.addWidget(self.e_out, 1); dest_row.addWidget(bo); cv.addLayout(dest_row)
        self.btn_open = QPushButton("Abrir resultado")
        self.btn_open.setObjectName("btnOpen"); self.btn_open.setEnabled(False)
        self.btn_open.clicked.connect(self._open_result); cv.addWidget(self.btn_open)
        lo_lay.addWidget(conv_bar)

        # Tarjeta: Panel de Conexión de Datos
        c1 = self._card("PANEL DE CONEXIÓN DE DATOS"); cl1 = c1.layout()
        fr = QHBoxLayout(); fr.setSpacing(6)
        self.btn_pdf = QPushButton("📂 Cargar Fuente de Datos")
        self.btn_pdf.setObjectName("btnFileOpen2")
        self.btn_pdf.setFixedHeight(32)
        self.btn_pdf.setToolTip("Abrir archivo: PDF, Excel (.xlsx/.xls), CSV o ODS")
        self.btn_pdf.clicked.connect(self._open_file)
        # Dentro de Navaja: se llama «Limpiar», como en las
        # demás solapas (en el programa original es «🔄 Resetear»).
        self.btn_reset = QPushButton("🗑 Limpiar")
        self.btn_reset.setObjectName("btnReset")
        self.btn_reset.setFixedHeight(32)
        self.btn_reset.setToolTip(
            "Deja la solapa como recién abierta, para empezar con otro "
            "archivo.\nNo borra nada del disco.")
        self.btn_reset.clicked.connect(self._reset_all)
        fr.addWidget(self.btn_pdf, 1); fr.addWidget(self.btn_reset); cl1.addLayout(fr)
        self.lbl_pdf = QLabel("Sin archivo"); self.lbl_pdf.setObjectName("muted"); self.lbl_pdf.setWordWrap(True)
        cl1.addWidget(self.lbl_pdf)
        self.lbl_total = QLabel(""); self.lbl_total.setObjectName("muted"); cl1.addWidget(self.lbl_total)
        lbl_fmts = QLabel("Soporta: PDF · Excel (.xlsx) · CSV · ODS")
        lbl_fmts.setObjectName("muted"); lbl_fmts.setWordWrap(True); cl1.addWidget(lbl_fmts)
        ll.addWidget(c1)

        # Tarjeta: Selección de páginas + miniaturas
        c2 = self._card("SELECCIÓN DE PÁGINAS"); cl2 = c2.layout()
        sr = QHBoxLayout(); sr.setSpacing(4)
        sr.addWidget(QLabel("De:"))
        self.sp_sel_from = QSpinBox(); self.sp_sel_from.setRange(1,9999)
        self.sp_sel_from.setValue(1); self.sp_sel_from.setFixedWidth(58); sr.addWidget(self.sp_sel_from)
        sr.addWidget(QLabel("a:"))
        self.sp_sel_to = QSpinBox(); self.sp_sel_to.setRange(1,9999)
        self.sp_sel_to.setValue(9999); self.sp_sel_to.setFixedWidth(58); sr.addWidget(self.sp_sel_to)
        btn_sel = QPushButton("Aplicar rango"); btn_sel.clicked.connect(self._select_range)
        sr.addWidget(btn_sel, 1); cl2.addLayout(sr)
        sr2 = QHBoxLayout(); sr2.setSpacing(4)
        btn_all = QPushButton("Todas"); btn_all.clicked.connect(self._select_all)
        btn_none = QPushButton("Ninguna"); btn_none.clicked.connect(self._select_none)
        sr2.addWidget(btn_all); sr2.addWidget(btn_none); sr2.addStretch(); cl2.addLayout(sr2)
        th_row = QHBoxLayout()
        lbl_pags = QLabel("Miniaturas"); lbl_pags.setObjectName("muted")
        lbl_pags.setToolTip("• Clic = marcar/desmarcar\n• Shift+clic = rango\n• Doble clic = ver en visor")
        self.lbl_sel_count = QLabel("0 sel."); self.lbl_sel_count.setObjectName("muted")
        self.btn_show_all = QPushButton("Ver todas"); self.btn_show_all.setFixedHeight(18)
        self.btn_show_all.setVisible(False); self.btn_show_all.clicked.connect(self._show_all_thumbs)
        th_row.addWidget(lbl_pags); th_row.addStretch()
        th_row.addWidget(self.lbl_sel_count); th_row.addWidget(self.btn_show_all); cl2.addLayout(th_row)
        self.thumb_scroll = QScrollArea(); self.thumb_scroll.setWidgetResizable(True); self.thumb_scroll.setFixedHeight(200)
        self.thumb_container = QWidget(); self.thumb_grid = QGridLayout(self.thumb_container)
        self.thumb_grid.setContentsMargins(4,4,4,4); self.thumb_grid.setSpacing(6)
        self.thumb_scroll.setWidget(self.thumb_container); cl2.addWidget(self.thumb_scroll)
        ll.addWidget(c2)

        # Tarjeta: Configuración de grupos
        c3 = self._card(f"CONFIGURACIÓN DE GRUPOS  (máx {MAX_GROUPS})"); cl3 = c3.layout()
        self.tabs_grp = QTabWidget(); self.group_panels = []
        for i in range(MAX_GROUPS):
            gp = GroupPanel(i)
            gp.btn_auto.clicked.connect(lambda _, idx=i: self._auto_seps_group(idx))
            gp.btn_from_m1.clicked.connect(lambda _, idx=i: self._take_seps_from_canvas(idx))
            gp.btn_set_start.clicked.connect(lambda _, idx=i: self._take_start_from_canvas(idx))
            gp.btn_set_end.clicked.connect(lambda _, idx=i: self._take_end_from_canvas(idx))
            gp.changed.connect(self._on_group_changed)
            self.tabs_grp.addTab(gp, f"G{i+1}")
            self.group_panels.append(gp)
        for i in range(MAX_GROUPS):
            self.tabs_grp.tabBar().setTabTextColor(i, QColor(GRP_COLORS[i]))
        cl3.addWidget(self.tabs_grp); ll.addWidget(c3)

        # Tarjeta: Formato Excel
        c4 = self._card("FORMATO EXCEL"); cl4 = c4.layout()
        grid_xl = QHBoxLayout(); col1, col2 = QVBoxLayout(), QVBoxLayout()
        self.ck_alt = QCheckBox("Filas alternas"); self.ck_alt.setChecked(True)
        self.ck_brd = QCheckBox("Bordes");          self.ck_brd.setChecked(True)
        self.ck_frz = QCheckBox("Congelar fila 1"); self.ck_frz.setChecked(True)
        self.ck_sep = QCheckBox("Sep. páginas");    self.ck_sep.setChecked(False)
        self.ck_pdf = QCheckBox("También PDF");     self.ck_pdf.setChecked(False)
        self.ck_pdf.setToolTip("Genera también un archivo .pdf con la tabla procesada")
        col1.addWidget(self.ck_alt); col1.addWidget(self.ck_frz); col1.addWidget(self.ck_pdf)
        col2.addWidget(self.ck_brd); col2.addWidget(self.ck_sep)
        grid_xl.addLayout(col1); grid_xl.addLayout(col2); cl4.addLayout(grid_xl)
        wgap_row = QHBoxLayout()
        wgap_row.addWidget(QLabel("Esp. palabras:"))
        self.sp_wgap = QSpinBox(); self.sp_wgap.setRange(5, 50); self.sp_wgap.setValue(13); self.sp_wgap.setSuffix("×0.1pt")
        self.sp_wgap.setToolTip("Gap mínimo entre chars para detectar espacio (×0.1pt). Default 13=1.3pt. Sube si hay sobre-separación")
        self.sp_wgap.setFixedWidth(74); wgap_row.addWidget(self.sp_wgap); wgap_row.addStretch()
        cl4.addLayout(wgap_row)
        xmin_row = QHBoxLayout()
        self.ck_xmin = QCheckBox("Ignorar margen izq."); self.ck_xmin.setChecked(False)
        self.ck_xmin.setToolTip("Excluye texto que aparece antes de X pt (útil para números de página en el margen)")
        self.sp_xmin = QSpinBox(); self.sp_xmin.setRange(10, 200); self.sp_xmin.setValue(60); self.sp_xmin.setSuffix("pt")
        self.sp_xmin.setFixedWidth(58); self.sp_xmin.setToolTip("Todo texto con X < este valor se ignora")
        xmin_row.addWidget(self.ck_xmin); xmin_row.addWidget(self.sp_xmin); xmin_row.addStretch()
        cl4.addLayout(xmin_row)

        # ── OCR para páginas imagen ───────────────────────────────────
        sep_ocr = QFrame(); sep_ocr.setFrameShape(QFrame.Shape.HLine)
        sep_ocr.setStyleSheet("color:#2E4060;"); cl4.addWidget(sep_ocr)
        lbl_ocr_sec = QLabel("OCR PARA PÁGINAS IMAGEN (PDF escaneo)")
        lbl_ocr_sec.setStyleSheet("font-size:8px;font-weight:bold;letter-spacing:1px;color:#8BA0B8;padding-top:2px;")
        cl4.addWidget(lbl_ocr_sec)
        h_ocr = QHBoxLayout(); h_ocr.setSpacing(4)
        self.ck_ocr = QCheckBox("Activar OCR si no hay texto")
        self.ck_ocr.setToolTip(
            "¿CUÁNDO USARLO?\n"
            "Cuando el PDF es una foto/escaneo y el programa no\n"
            "encuentra caracteres. El OCR lee las posiciones X/Y\n"
            "de cada palabra para preservar las columnas.\n\n"
            "El lector (Tesseract) viene con el programa:\n"
            "no hay que instalar nada.\n\n"
            "⚠ Más lento que extracción normal (~3-10 s/página).")
        h_ocr.addWidget(self.ck_ocr, 1)
        h_ocr.addWidget(QLabel("Idioma:"))
        self.cmb_ocr_lang = QComboBox()
        self.cmb_ocr_lang.addItems(["spa+eng", "spa", "eng"])
        self.cmb_ocr_lang.setFixedWidth(76)
        self.cmb_ocr_lang.setToolTip("Idioma del OCR\nspa=español · eng=inglés · spa+eng=ambos")
        self.cmb_ocr_lang.currentIndexChanged.connect(lambda: self._preview_timer.start(800))
        h_ocr.addWidget(self.cmb_ocr_lang)
        # Activar/desactivar OCR también dispara preview
        self.ck_ocr.stateChanged.connect(lambda: self._preview_timer.start(800))
        cl4.addLayout(h_ocr)

        # ── Pre-rotación de imagen antes de OCR ───────────────────────
        h_ocr_rot = QHBoxLayout(); h_ocr_rot.setSpacing(4)
        lbl_rot_ocr = QLabel("Pre-rotar para OCR:")
        lbl_rot_ocr.setToolTip(
            "Rota la imagen ANTES de enviarla a Tesseract y también\n"
            "la vista del visor. Las líneas de inicio/fin y los separadores\n"
            "de columna se marcan directamente sobre la vista rotada.\n\n"
            "Usá '180°' si el PDF está 'de cabeza'.\n"
            "Usá '90°' o '270°' si está de costado.\n"
            "⚠ NO modifica el archivo PDF original.")
        h_ocr_rot.addWidget(lbl_rot_ocr)
        self.cmb_ocr_rotation = QComboBox()
        self.cmb_ocr_rotation.addItems(["Sin rotar (0°)", "90° horario", "180°", "270° antihorario"])
        self.cmb_ocr_rotation.setFixedWidth(138)
        self.cmb_ocr_rotation.setToolTip(lbl_rot_ocr.toolTip())
        self.cmb_ocr_rotation.currentIndexChanged.connect(self._on_ocr_rotation_changed)
        h_ocr_rot.addWidget(self.cmb_ocr_rotation)
        h_ocr_rot.addStretch()
        cl4.addLayout(h_ocr_rot)

        # ── Limpieza de imagen antes de OCR ────────────────────────────
        lbl_enh_sec = QLabel("🧹 LIMPIEZA DEL ESCANEO (el visor muestra el resultado)")
        lbl_enh_sec.setStyleSheet("font-size:8px;font-weight:bold;letter-spacing:1px;color:#8BA0B8;padding-top:2px;")
        lbl_enh_sec.setToolTip(
            "Mejora el escaneo ANTES de enviarlo al OCR.\n"
            "⚠ NO modifica el PDF original.\n"
            "Al ajustar cualquier control, el visor muestra la imagen\n"
            "procesada: lo que ves es exactamente lo que leerá el OCR.")
        cl4.addWidget(lbl_enh_sec)

        h_enh1 = QHBoxLayout(); h_enh1.setSpacing(4)
        lbl_fondo = QLabel("☀ Fondo blanco:")
        lbl_fondo.setToolTip(
            "Aclara el fondo con los botones +/− (0 = sin cambio, 10 = máximo).\n"
            "Subilo si la hoja tiene base gris: los grises claros se vuelven\n"
            "blanco puro y el OCR deja de confundirlos con texto.")
        h_enh1.addWidget(lbl_fondo)
        self.sp_enh_fondo = QSpinBox(); self.sp_enh_fondo.setRange(0, 10)
        self.sp_enh_fondo.setFixedWidth(46)
        self.sp_enh_fondo.setToolTip(lbl_fondo.toolTip())
        self.sp_enh_fondo.valueChanged.connect(self._on_ocr_enhance_changed)
        h_enh1.addWidget(self.sp_enh_fondo)
        h_enh1.addSpacing(8)
        lbl_texto = QLabel("🖋 Texto oscuro:")
        lbl_texto.setToolTip(
            "Remarca el texto con los botones +/− (0 = sin cambio, 10 = máximo).\n"
            "Subilo si las letras se ven lavadas o finas: los grises oscuros\n"
            "se vuelven negro puro y el OCR las distingue mejor.")
        h_enh1.addWidget(lbl_texto)
        self.sp_enh_texto = QSpinBox(); self.sp_enh_texto.setRange(0, 10)
        self.sp_enh_texto.setFixedWidth(46)
        self.sp_enh_texto.setToolTip(lbl_texto.toolTip())
        self.sp_enh_texto.valueChanged.connect(self._on_ocr_enhance_changed)
        h_enh1.addWidget(self.sp_enh_texto)
        h_enh1.addStretch()
        cl4.addLayout(h_enh1)

        h_enh2 = QHBoxLayout(); h_enh2.setSpacing(4)
        self.ck_enh_puntitos = QCheckBox("Quitar puntitos")
        self.ck_enh_puntitos.setToolTip(
            "Borra motas y puntos sueltos del escáner (vidrio sucio/rayado)\n"
            "con un filtro de mediana, antes del OCR.")
        self.ck_enh_puntitos.stateChanged.connect(self._on_ocr_enhance_changed)
        h_enh2.addWidget(self.ck_enh_puntitos)
        self.ck_enh_bn = QCheckBox("B/N puro")
        self.ck_enh_bn.setToolTip(
            "Convierte todo a blanco y negro puro con umbral automático (Otsu).\n"
            "Máximo contraste: ideal para escaneos oscuros o muy sucios.")
        self.ck_enh_bn.stateChanged.connect(self._on_ocr_enhance_changed)
        h_enh2.addWidget(self.ck_enh_bn)
        h_enh2.addSpacing(8)
        lbl_conf = QLabel("Conf:")
        lbl_conf.setToolTip(
            "Confianza mínima del OCR (10-90).\n"
            "Las palabras con confianza menor se descartan.\n\n"
            "⬇ Bajala (20-25) si el OCR 'lee poco' / faltan palabras.\n"
            "⬆ Subila (40-50) si aparecen letras sueltas de basura\n"
            "   (puntitos del escáner leídos como texto).")
        h_enh2.addWidget(lbl_conf)
        self.sp_ocr_conf = QSpinBox()
        self.sp_ocr_conf.setRange(10, 90); self.sp_ocr_conf.setValue(30)
        self.sp_ocr_conf.setFixedWidth(46)
        self.sp_ocr_conf.setToolTip(lbl_conf.toolTip())
        self.sp_ocr_conf.valueChanged.connect(lambda: self._preview_timer.start(800))
        h_enh2.addWidget(self.sp_ocr_conf)
        h_enh2.addStretch()
        cl4.addLayout(h_enh2)

        lbl_ocr_hint = QLabel("💡 OCR preserva columnas. Solo activa en páginas sin texto extraíble.")
        lbl_ocr_hint.setWordWrap(True)
        lbl_ocr_hint.setStyleSheet("color:#8BA0B8;font-size:8px;")
        cl4.addWidget(lbl_ocr_hint)
        ll.addWidget(c4)

        # Tarjeta: 9 Cortes en Cadena (absorbidos del M1)
        c_cuts = self._card("CORTES DE COLUMNA EN CADENA (hasta 9)"); cl_cuts = c_cuts.layout()
        cl_cuts.setSpacing(4)
        self.tabs_split = QTabWidget(); self.tabs_split.setDocumentMode(True)

        def _create_split_tab():
            w = QWidget(); l = QVBoxLayout(w); l.setContentsMargins(4, 4, 4, 4); l.setSpacing(3)
            cmb_col = QComboBox(); cmb_col.addItem("(ninguna)"); l.addWidget(cmb_col)
            h_a = QHBoxLayout()
            h_a.addWidget(QLabel("Sep:")); e_sep = QLineEdit(" - "); e_sep.setFixedWidth(60); h_a.addWidget(e_sep)
            ck_act = QCheckBox("Activar"); h_a.addWidget(ck_act); l.addLayout(h_a)
            h_keep = QHBoxLayout()
            cmb_keep = QComboBox(); cmb_keep.addItems(["Eliminar sep.", "Unir a Izq.", "Unir a Der."])
            cmb_keep.setToolTip(
                "Eliminar sep. → el separador desaparece del resultado\n"
                "Unir a Izq. → el separador queda pegado al texto izquierdo\n"
                "Unir a Der. → el separador queda pegado al texto derecho")
            cmb_pos = QComboBox(); cmb_pos.addItems(["Reemplazar", "Al final"])
            cmb_pos.setToolTip(
                "Reemplazar → las 2 columnas nuevas reemplazan la original\n"
                "Al final → la columna original queda y las 2 nuevas se agregan al final")
            h_keep.addWidget(cmb_keep); h_keep.addWidget(cmb_pos); l.addLayout(h_keep)
            h_names = QHBoxLayout()
            e_left = QLineEdit("IZQ"); e_right = QLineEdit("DER")
            h_names.addWidget(QLabel("Izq:")); h_names.addWidget(e_left)
            h_names.addWidget(QLabel("Der:")); h_names.addWidget(e_right)
            l.addLayout(h_names)
            for widget in [ck_act, cmb_col, cmb_pos, cmb_keep, e_sep, e_left, e_right]:
                if isinstance(widget, QCheckBox): widget.stateChanged.connect(lambda _: self._preview_timer.start(600))
                elif isinstance(widget, QComboBox): widget.currentIndexChanged.connect(lambda _: self._preview_timer.start(600))
                elif isinstance(widget, QLineEdit): widget.textChanged.connect(lambda _: self._preview_timer.start(600))
            return w, cmb_col, e_sep, ck_act, cmb_keep, cmb_pos, e_left, e_right

        self.split_widgets = []
        for i in range(1, 10):
            w, cmb_col, e_sep, ck_act, cmb_keep, cmb_pos, e_left, e_right = _create_split_tab()
            self.tabs_split.addTab(w, str(i))
            self.split_widgets.append({
                "cmb_col": cmb_col, "e_sep": e_sep, "ck_act": ck_act,
                "cmb_keep": cmb_keep, "cmb_pos": cmb_pos,
                "e_left": e_left, "e_right": e_right
            })
        cl_cuts.addWidget(self.tabs_split)
        ll.addWidget(c_cuts)

        # Tarjeta: Receta
        c5 = self._card("RECETA"); cl5 = c5.layout()
        rr = QHBoxLayout(); rr.setSpacing(6)
        btn_save_r = QPushButton("Guardar receta"); btn_save_r.clicked.connect(self._save_recipe)
        btn_load_r = QPushButton("Cargar receta"); btn_load_r.clicked.connect(self._load_recipe)
        rr.addWidget(btn_save_r, 1); rr.addWidget(btn_load_r, 1); cl5.addLayout(rr)
        ll.addWidget(c5)

        # Tarjeta: Rotar páginas
        c_rot = self._card("ROTAR PÁGINAS PDF"); cl_rot = c_rot.layout()
        h_rot1 = QHBoxLayout(); h_rot1.setSpacing(4)
        h_rot1.addWidget(QLabel("Aplicar a:"))
        self.cmb_rot_scope = QComboBox()
        self.cmb_rot_scope.addItems(["Todas las páginas", "Solo seleccionadas"])
        self.cmb_rot_scope.setToolTip("'Solo seleccionadas' usa las miniaturas marcadas en azul")
        h_rot1.addWidget(self.cmb_rot_scope, 1); cl_rot.addLayout(h_rot1)
        h_rot2 = QHBoxLayout(); h_rot2.setSpacing(4)
        h_rot2.addWidget(QLabel("Girar:"))
        self.cmb_rot_angle = QComboBox()
        self.cmb_rot_angle.addItems(["90° (horario)", "180°", "270° (antihorario)"])
        h_rot2.addWidget(self.cmb_rot_angle, 1); cl_rot.addLayout(h_rot2)
        self.btn_rotate = QPushButton("↻  Rotar y guardar como...")
        self.btn_rotate.setFixedHeight(28); self.btn_rotate.setObjectName("btnStart")
        self.btn_rotate.setToolTip("Guarda un PDF nuevo rotado. El original NO se modifica.")
        self.btn_rotate.clicked.connect(self._rotate_pdf); cl_rot.addWidget(self.btn_rotate)
        lbl_rot_hint = QLabel("💡 El original no se modifica. Podés recargar el rotado.")
        lbl_rot_hint.setWordWrap(True)
        lbl_rot_hint.setStyleSheet("color:#8BA0B8;font-size:8px;")
        cl_rot.addWidget(lbl_rot_hint)
        ll.addWidget(c_rot)
        ll.addStretch()

        # ═══ PANEL DERECHO — visor + preview ═════════════════════════
        rp = QWidget(); rp.setObjectName("rightPanel")
        rl = QVBoxLayout(rp); rl.setContentsMargins(0,0,0,0); rl.setSpacing(0)

        rh = QWidget(); rh.setObjectName("panelHdr"); rh.setFixedHeight(72)
        rh_lay = QVBoxLayout(rh); rh_lay.setContentsMargins(10,4,10,4); rh_lay.setSpacing(2)
        rhl = QHBoxLayout(); rhl.setSpacing(6)
        self.lbl_page_info = QLabel("  Seleccioná una página")
        rhl.addWidget(self.lbl_page_info); rhl.addStretch()
        self.btn_add_start = QPushButton("+ Inicio tabla"); self.btn_add_start.setFixedHeight(24)
        self.btn_add_start.setObjectName("btnStart")
        self.btn_add_start.setToolTip("Agregar línea de inicio de tabla (afecta al GRUPO)")
        self.btn_add_start.clicked.connect(self._canvas_add_start)
        self.btn_add_end = QPushButton("+ Fin tabla"); self.btn_add_end.setFixedHeight(24)
        self.btn_add_end.setObjectName("btnEnd")
        self.btn_add_end.setToolTip("Agregar línea de fin de tabla (afecta al GRUPO)")
        self.btn_add_end.clicked.connect(self._canvas_add_end)
        rhl.addWidget(self.btn_add_start); rhl.addWidget(self.btn_add_end)
        rh_lay.addLayout(rhl)
        lbl_hint = QLabel("  🖱 Click izq en el visor = nueva columna  ·  Arrastrar = mover  ·  Click der = borrar  ·  Ctrl+rueda = zoom")
        lbl_hint.setObjectName("canvasHint")
        rhl2 = QHBoxLayout(); rhl2.setSpacing(4)
        lbl_ov = QLabel("Solo esta página:"); lbl_ov.setObjectName("muted"); rhl2.addWidget(lbl_ov)
        self.btn_ov_start = QPushButton("📌 Inicio Y"); self.btn_ov_start.setFixedHeight(20)
        self.btn_ov_start.setToolTip("Override inicio SOLO esta página"); self.btn_ov_start.clicked.connect(self._set_ov_start)
        self.btn_ov_end = QPushButton("📌 Fin Y"); self.btn_ov_end.setFixedHeight(20)
        self.btn_ov_end.setToolTip("Override fin SOLO esta página"); self.btn_ov_end.clicked.connect(self._set_ov_end)
        self.btn_ov_clear = QPushButton("Quitar"); self.btn_ov_clear.setFixedHeight(20)
        self.btn_ov_clear.setToolTip("Quitar override → usa Y del grupo"); self.btn_ov_clear.clicked.connect(self._clear_ov)
        rhl2.addWidget(self.btn_ov_start); rhl2.addWidget(self.btn_ov_end)
        rhl2.addWidget(self.btn_ov_clear); rhl2.addStretch()
        rh_lay.addLayout(rhl2)
        rh_lay.addWidget(lbl_hint)
        rl.addWidget(rh)

        self.canvas_scroll = QScrollArea(); self.canvas_scroll.setObjectName("canvasScroll")
        self.canvas_scroll.setWidgetResizable(True)
        self.canvas = MiniCanvas()
        self.canvas.seps_changed.connect(self._on_canvas_seps_changed)
        self.canvas.start_y_changed.connect(self._on_canvas_start_changed)
        self.canvas.end_y_changed.connect(self._on_canvas_end_changed)
        self.canvas_scroll.setWidget(self.canvas)
        # Sync scroll canvas → preview (absorbido del M1)
        self.canvas_scroll.verticalScrollBar().valueChanged.connect(
            lambda v: self._sync_scroll_canvas(
                v / max(self.canvas_scroll.verticalScrollBar().maximum(), 1)))

        prev_wrap = QWidget()
        prev_wrap_lay = QVBoxLayout(prev_wrap)
        prev_wrap_lay.setContentsMargins(0,0,0,0); prev_wrap_lay.setSpacing(0)
        prev_hdr = QWidget(); prev_hdr.setObjectName("panelHdr"); prev_hdr.setFixedHeight(28)
        prev_hdr_lay = QHBoxLayout(prev_hdr)
        prev_hdr_lay.setContentsMargins(10,0,6,0); prev_hdr_lay.setSpacing(4)
        self.lbl_preview = QLabel("Previsualización"); self.lbl_preview.setObjectName("muted")
        prev_hdr_lay.addWidget(self.lbl_preview); prev_hdr_lay.addStretch()
        self.ck_sync = QCheckBox("Sync scroll")
        self.ck_sync.setChecked(True)
        self.ck_sync.setToolTip("Sincronizar scroll del visor PDF con la tabla de preview")
        self.ck_sync.stateChanged.connect(lambda v: setattr(self, '_sync_scroll_on', bool(v)))
        prev_hdr_lay.addWidget(self.ck_sync)
        prev_hdr_lay.addWidget(QLabel("Págs:"))
        self.sp_prev_n = QSpinBox(); self.sp_prev_n.setRange(1,20); self.sp_prev_n.setValue(3)
        self.sp_prev_n.setFixedWidth(42); self.sp_prev_n.setToolTip("Páginas a previsualizar")
        prev_hdr_lay.addWidget(self.sp_prev_n)
        btn_prev = QPushButton("↺"); btn_prev.setFixedSize(22,22)
        btn_prev.setToolTip("Actualizar previsualización"); btn_prev.clicked.connect(self._update_preview)
        prev_hdr_lay.addWidget(btn_prev)
        btn_adj_prev = QPushButton("↔"); btn_adj_prev.setFixedSize(22,22)
        btn_adj_prev.setToolTip("Ajustar ancho de columnas automáticamente\n(podés arrastrar los bordes del encabezado para ajustar manualmente)")
        btn_adj_prev.clicked.connect(self._auto_resize_preview)
        prev_hdr_lay.addWidget(btn_adj_prev)
        prev_wrap_lay.addWidget(prev_hdr)
        self.preview_table = QTableWidget(); self.preview_table.setObjectName("previewTable")
        self.preview_table.setAlternatingRowColors(True)
        self.preview_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.preview_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.preview_table.horizontalHeader().setStretchLastSection(False)
        self.preview_table.verticalHeader().setDefaultSectionSize(18)
        self.preview_table.setMinimumHeight(100)
        # Doble clic en celda → dividir columna (absorbido del M1)
        self.preview_table.cellDoubleClicked.connect(self._on_preview_dbl_click)
        prev_wrap_lay.addWidget(self.preview_table, 1)

        # Panel Editor Excel/CSV (tab oculto, se activa con el botón)
        self._csv_editor_widget = self._build_csv_editor()

        right_vs = QSplitter(Qt.Orientation.Vertical)
        right_vs.addWidget(self.canvas_scroll); right_vs.addWidget(prev_wrap); right_vs.setSizes([420,200])
        rl.addWidget(right_vs, 1)

        # Tabs del panel derecho: Visor PDF | Editor Excel/CSV
        self._right_tabs = QTabWidget()
        self._right_tabs.setDocumentMode(True)
        self._right_tabs.addTab(rp, "Visor PDF")
        self._right_tabs.addTab(self._csv_editor_widget, "Editor Excel/CSV")
        hs.addWidget(self._right_tabs)
        hs.setSizes([410, 900])

    def _card(self, title):
        """Crea un QFrame tipo tarjeta con título y VBoxLayout."""
        w = QFrame(); w.setObjectName("card")
        l = QVBoxLayout(w); l.setContentsMargins(10,8,10,8); l.setSpacing(5)
        lbl = QLabel(title); lbl.setObjectName("cardTitle"); l.addWidget(lbl)
        return w

    def _sec(self, lay, txt):
        l = QLabel(txt); l.setObjectName("sec"); lay.addWidget(l)

    def _hr(self):
        f = QFrame(); f.setFrameShape(QFrame.Shape.HLine); f.setObjectName("hr"); return f

    # ── Editor Excel/CSV (TAREA 5) ────────────────────────────────────
    def _build_csv_editor(self):
        """Construye el widget del editor de Excel/CSV."""
        w = QWidget(); w.setObjectName("csvEditor")
        lay = QVBoxLayout(w); lay.setContentsMargins(8, 8, 8, 8); lay.setSpacing(6)

        # Toolbar
        tb = QHBoxLayout(); tb.setSpacing(6)
        btn_open = QPushButton("📂 Abrir archivo")
        btn_open.setObjectName("btnFileOpen2"); btn_open.setFixedHeight(28)
        btn_open.clicked.connect(self._open_excel_csv)
        tb.addWidget(btn_open)
        self.lbl_csv_path = QLabel("Sin archivo"); self.lbl_csv_path.setObjectName("muted")
        tb.addWidget(self.lbl_csv_path, 1)
        self.btn_csv_save = QPushButton("💾 Guardar cambios")
        self.btn_csv_save.setObjectName("btnStart"); self.btn_csv_save.setFixedHeight(28)
        self.btn_csv_save.setEnabled(False)
        self.btn_csv_save.clicked.connect(self._save_csv_changes)
        tb.addWidget(self.btn_csv_save)
        self.btn_csv_export = QPushButton("📥 Exportar como xlsx")
        self.btn_csv_export.setObjectName("btnEnd"); self.btn_csv_export.setFixedHeight(28)
        self.btn_csv_export.setEnabled(False)
        self.btn_csv_export.setToolTip("Disponible solo para archivos CSV u ODS: exporta como .xlsx")
        self.btn_csv_export.clicked.connect(self._export_csv_as_xlsx)
        tb.addWidget(self.btn_csv_export)
        lay.addLayout(tb)

        # Tabla editable
        self.csv_table = QTableWidget()
        self.csv_table.setObjectName("previewTable")
        self.csv_table.setAlternatingRowColors(True)
        self.csv_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.csv_table.horizontalHeader().setStretchLastSection(False)
        self.csv_table.verticalHeader().setDefaultSectionSize(18)
        lay.addWidget(self.csv_table, 1)

        lbl_hint = QLabel("  Hacé doble clic en una celda para editarla. Los cambios se guardan con '💾 Guardar cambios'.")
        lbl_hint.setObjectName("muted")
        lay.addWidget(lbl_hint)
        return w

    def _open_excel_csv(self):
        """Abre un archivo Excel/CSV y lo carga en la tabla editable."""
        p, _ = QFileDialog.getOpenFileName(
            self, "Abrir Excel / CSV",  "",
            "Todos los soportados (*.xlsx *.csv *.ods);;"
            "Excel (*.xlsx);;CSV (*.csv);;ODS (*.ods)")
        if not p:
            return
        self._open_excel_csv_path(p)
        if self._csv_path == p:   # cargó bien → mostrar el editor
            self._right_tabs.setCurrentIndex(1)

    def _open_excel_csv_path(self, p: str):
        """
        Carga un archivo Excel/CSV/ODS dado su path directamente.
        Llamado por _route_file cuando el archivo no es PDF.
        Muestra un mensaje de estado al finalizar.
        """
        ext = os.path.splitext(p)[1].lower()
        try:
            if ext == ".csv":
                # Detectar delimitador por conteo en una muestra (antes una fila
                # en blanco TRUNCABA el archivo y las comas no se detectaban).
                with open(p, "r", encoding="utf-8-sig", errors="replace", newline="") as f:
                    muestra = f.read(4096); f.seek(0)
                    delim = ";" if muestra.count(";") >= muestra.count(",") else ","
                    rows = [list(r) for r in csv.reader(f, delimiter=delim)]
                self._csv_data = rows
                self._csv_delim = delim
                self._csv_orig_ext = ".csv"
            elif ext == ".xlsx":
                wb = openpyxl.load_workbook(p, data_only=True)
                ws = wb.active
                self._csv_data = [
                    [str(c.value) if c.value is not None else "" for c in row]
                    for row in ws.iter_rows()
                ]
                self._csv_orig_ext = ext
            elif ext == ".xls":
                QMessageBox.warning(
                    self, "Formato .xls no soportado",
                    "El formato Excel antiguo (.xls) no es compatible.\n\n"
                    "Abrí el archivo en Excel/LibreOffice y guardalo como .xlsx,\n"
                    "después cargalo de nuevo acá.")
                return
            elif ext == ".ods":
                try:
                    wb = openpyxl.load_workbook(p, data_only=True)
                    ws = wb.active
                    self._csv_data = [
                        [str(c.value) if c.value is not None else "" for c in row]
                        for row in ws.iter_rows()
                    ]
                    self._csv_orig_ext = ".ods"
                except Exception:
                    QMessageBox.warning(
                        self, "ODS no soportado",
                        "No se pudo abrir el archivo ODS.\n\n"
                        "Abrilo en LibreOffice y guardalo como .xlsx o .csv,\n"
                        "después cargalo de nuevo acá.")
                    return
            else:
                QMessageBox.warning(self, "Formato no soportado",
                    f"Extensión '{ext}' no reconocida.")
                return

            self._csv_path = p
            self.lbl_csv_path.setText(os.path.basename(p))
            self._fill_csv_table()
            self.btn_csv_save.setEnabled(True)
            self.btn_csv_export.setEnabled(ext in (".csv", ".ods"))
            self.lbl_total.setText(
                f"Archivo de datos cargado — editando directamente  "
                f"({self.csv_table.rowCount()} filas · {self.csv_table.columnCount()} cols)"
            )
        except Exception as e:
            QMessageBox.critical(self, "Error al abrir", str(e))

    def _fill_csv_table(self):
        """Rellena csv_table con los datos de self._csv_data."""
        data = self._csv_data
        if not data:
            self.csv_table.setRowCount(0); self.csv_table.setColumnCount(0); return
        nc = max(len(r) for r in data)
        self.csv_table.setColumnCount(nc)
        self.csv_table.setRowCount(len(data))
        for ri, row in enumerate(data):
            for ci in range(nc):
                val = row[ci] if ci < len(row) else ""
                item = QTableWidgetItem(str(val))
                self.csv_table.setItem(ri, ci, item)
        self.csv_table.resizeColumnsToContents()

    def _save_csv_changes(self):
        """Guarda los cambios de la tabla al archivo original."""
        if not self._csv_path:
            return
        # Recoger datos de la tabla
        rows = []
        for ri in range(self.csv_table.rowCount()):
            row = []
            for ci in range(self.csv_table.columnCount()):
                item = self.csv_table.item(ri, ci)
                row.append(item.text() if item else "")
            rows.append(row)
        ext = os.path.splitext(self._csv_path)[1].lower()
        try:
            if ext == ".csv":
                save_path = self._csv_path
                with open(save_path, "w", newline="", encoding="utf-8-sig") as f:
                    w = csv.writer(f, delimiter=self._csv_delim)
                    for row in rows:
                        w.writerow(row)
            else:   # .xlsx / .ods → se guarda siempre como .xlsx
                wb = openpyxl.Workbook(); ws = wb.active
                for row in rows:
                    ws.append([_xclean(v) for v in row])
                save_path = (self._csv_path if ext == ".xlsx"
                             else os.path.splitext(self._csv_path)[0] + ".xlsx")
                wb.save(save_path)
            extra = ""
            if save_path != self._csv_path:
                extra = "\n\n⚠ El original no era .xlsx: se guardó una copia en ese formato."
            QMessageBox.information(self, "Guardado", f"Archivo guardado:\n{save_path}{extra}")
            self._csv_data = rows
        except PermissionError:
            QMessageBox.critical(self, "Error de permisos",
                "No se pudo guardar el archivo.\nVerificá que no esté abierto en Excel.")
        except Exception as e:
            QMessageBox.critical(self, "Error al guardar", str(e))

    def _export_csv_as_xlsx(self):
        """Exporta el archivo CSV/ODS como .xlsx."""
        if not self._csv_path:
            return
        base = os.path.splitext(self._csv_path)[0]
        out, _ = QFileDialog.getSaveFileName(
            self, "Exportar como xlsx", base + ".xlsx", "Excel (*.xlsx)")
        if not out:
            return
        if not out.endswith(".xlsx"):
            out += ".xlsx"
        # Recoger datos de la tabla
        rows = []
        for ri in range(self.csv_table.rowCount()):
            row = []
            for ci in range(self.csv_table.columnCount()):
                item = self.csv_table.item(ri, ci)
                row.append(item.text() if item else "")
            rows.append(row)
        try:
            wb = openpyxl.Workbook()
            ws = wb.active
            hf = Font(name="Calibri", bold=True, size=9, color="FFFFFF")
            hfi = PatternFill("solid", start_color="1A3A5C")
            nf  = Font(name="Calibri", size=9)
            for ri, row in enumerate(rows):
                ws.append([_xclean(v) for v in row])
                if ri == 0:
                    for cell in ws[1]:
                        cell.font = hf; cell.fill = hfi
                else:
                    for cell in ws[ri + 1]:
                        cell.font = nf
            for col in ws.columns:
                lt = get_column_letter(col[0].column)
                mx = max((len(str(c.value)) for c in col if c.value), default=0)
                ws.column_dimensions[lt].width = min(max(mx + 2, 8), 42)
            ws.freeze_panes = "A2"
            wb.save(out)
            QMessageBox.information(self, "Exportado", f"Archivo exportado:\n{out}")
        except Exception as e:
            QMessageBox.critical(self, "Error al exportar", str(e))

    # ── Estilo ────────────────────────────────────────────────────────
    def _style(self):
        global _T; _T = DARK if self._dark else LIGHT; t = _T; d = self._dark
        cg1 = "#1D4ED8" if d else "#2563EB"; cg2 = "#2563EB" if d else "#3B82F6"
        og1 = "#065F46" if d else "#059669"; og2 = "#047857" if d else "#10B981"
        self.setStyleSheet(f"""
        QWidget{{background:{t['bg']};color:{t['text']};font-family:Arial;font-size:10px;}}
        #leftPanel{{background:{t['panel']};border-right:1px solid {t['border']};}}
        #leftScroll{{border:none;background:transparent;}}
        #leftContent{{background:transparent;}}
        #convBar{{background:{t['panel']};border-top:2px solid {t['border']};}}
        #rightPanel{{background:{t['bg']};}}
        /* Tarjetas */
        #card{{background:{t['panel']};border:1px solid {t['border']};border-radius:8px;}}
        #cardTitle{{color:{t['accent']};font-size:8px;font-weight:bold;letter-spacing:2px;
                   padding-bottom:4px;border-bottom:1px solid {t['border']};margin-bottom:2px;}}
        /* Botón abrir archivo */
        #btnFileOpen2{{background:{t['accent']};color:white;border:none;border-radius:5px;
                      padding:4px 12px;font-weight:bold;font-size:10px;}}
        #btnFileOpen2:hover{{background:{cg1};}}
        /* Botones de inicio/fin tabla */
        #btnStart{{background:{"#0F2E50" if d else "#DBEAFE"};color:{"#60A5FA" if d else "#1D4ED8"};
                  border:1px solid {"#1D4ED8" if d else "#93C5FD"};font-weight:bold;}}
        #btnStart:hover{{background:#1D4ED8;color:white;}}
        #btnEnd{{background:{"#0F3020" if d else "#DCFCE7"};color:{"#6EE7B7" if d else "#065F46"};
                border:1px solid {"#065F46" if d else "#86EFAC"};font-weight:bold;}}
        #btnEnd:hover{{background:#065F46;color:white;}}
        #panelHdr{{background:{t['card']};color:{t['muted']};border-bottom:1px solid {t['border']};
                   padding-left:6px;font-size:9px;font-weight:bold;letter-spacing:1px;}}
        #canvasHint{{color:{t['muted']};font-size:8px;padding:0px 4px;background:{t['card']};}}
        #sec{{color:{t['accent']};font-size:8px;font-weight:bold;
              letter-spacing:1.5px;padding-top:2px;}}
        #hr{{border:none;border-top:1px solid {t['border']};margin:1px 0;}}
        #muted{{color:{t['muted']};font-size:9px;}}
        QLineEdit,QSpinBox,QComboBox{{background:{t['card']};border:1px solid {t['border']};
            border-radius:4px;padding:3px 6px;color:{t['text']};}}
        QPushButton{{background:{t['card']};color:{t['text']};border:1px solid {t['border']};
            border-radius:4px;padding:4px 8px;}}
        QPushButton:hover{{background:{t['panel']};border-color:{t['accent']};}}
        QPushButton:disabled{{color:{t['muted']};}}
        #btnConv{{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
            stop:0 {cg1},stop:1 {cg2});color:white;border:none;
            border-radius:5px;font-weight:bold;font-size:11px;}}
        #btnOpen{{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
            stop:0 {og1},stop:1 {og2});color:white;border:none;}}
        QProgressBar{{background:{t['card']};border:none;border-radius:3px;}}
        QProgressBar::chunk{{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
            stop:0 {t['accent']},stop:1 {t['accent2']});border-radius:3px;}}
        QTextEdit{{background:{t['bg']};border:1px solid {t['border']};
            color:{"#8FBCBB" if d else "#2D3748"};}}
        QCheckBox::indicator{{width:13px;height:13px;border:1px solid {t['border']};
            border-radius:3px;background:{t['card']};}}
        QCheckBox::indicator:checked{{background:{t['accent']};border-color:{t['accent']};}}
        QScrollArea{{border:none;background:{t['bg']};}}
        #canvasScroll{{border:none;background:{t['canvas_bg']};}}
        QTabWidget::pane{{border:1px solid {t['border']};background:{t['card']};}}
        QTabBar::tab{{background:{t['panel']};color:{t['muted']};padding:4px 10px;
            border:1px solid {t['border']};}}
        QTabBar::tab:selected{{background:{t['card']};color:{t['accent']};font-weight:bold;}}
        QSplitter::handle{{background:{t['border']};}}
        #previewTable{{background:{t['card']};alternate-background-color:{t['row_alt']};
            color:{t['text']};gridline-color:{t['border']};font-size:9px;}}
        #previewTable QHeaderView::section{{background:{t['hdr_tbl']};color:{t['accent']};
            border:1px solid {t['border']};padding:3px;font-weight:bold;font-size:9px;}}
        /* Botón Reset */
        #btnReset{{ background:{"#3A1A0A" if d else "#FEF3C7"};
                   color:{"#FBBF24" if d else "#92400E"};
                   border:1px solid {"#92400E" if d else "#FCD34D"};
                   border-radius:4px;font-weight:bold; }}
        #btnReset:hover{{ background:#92400E;color:white; }}
        /* Botón abrir CSV */
        #btnOpenCsv{{ background:{"#0F2E1A" if d else "#DCFCE7"};
                     color:{"#6EE7B7" if d else "#065F46"};
                     border:1px solid {"#065F46" if d else "#86EFAC"};
                     border-radius:4px;font-weight:bold; }}
        #btnOpenCsv:hover{{ background:#065F46;color:white; }}
        /* Botón Undo */
        #btnUndo{{ background:{t['card']};color:{t['muted']};
                  border:1px solid {t['border']};border-radius:4px; }}
        #btnUndo:enabled{{ color:{t['accent']};border-color:{t['accent']}; }}
        #btnUndo:hover{{ background:{t['accent']};color:white; }}
        """)

    def set_dark(self, dark):
        if self._dark != dark: self._dark = dark; self._style()

    def _ocr_rot_value(self):
        """Devuelve los grados de pre-rotación CW seleccionados para OCR."""
        return [0, 90, 180, 270][self.cmb_ocr_rotation.currentIndex()]

    def _ocr_enhance_value(self):
        """Config de limpieza pre-OCR. '' (falsy) = sin limpieza."""
        f  = self.sp_enh_fondo.value()
        t  = self.sp_enh_texto.value()
        p  = self.ck_enh_puntitos.isChecked()
        bn = self.ck_enh_bn.isChecked()
        if not (f or t or p or bn): return ""
        return {"fondo": f, "texto": t, "puntitos": p, "bn": bn}

    def _on_ocr_enhance_changed(self, *_):
        """Cambió la limpieza: el visor muestra la imagen tal como la verá el OCR."""
        modo = self._ocr_enhance_value()
        self.canvas.set_ocr_enhance(modo)
        if self._pdf_path:
            self._load_canvas_page(getattr(self, "_current_page", 0))
        if modo:
            partes = []
            if modo["fondo"]:    partes.append(f"fondo blanco +{modo['fondo']}")
            if modo["texto"]:    partes.append(f"texto oscuro +{modo['texto']}")
            if modo["puntitos"]: partes.append("sin puntitos")
            if modo["bn"]:       partes.append("B/N puro")
            self._log(f"🧹 Limpieza OCR: {' · '.join(partes)} — el visor muestra la imagen procesada.")
        else:
            self._log("🧹 Limpieza OCR desactivada — el visor muestra el original.")
        self._preview_timer.start(800)

    def _on_ocr_rotation_changed(self):
        """Cuando el usuario cambia la rotación OCR: actualiza canvas + preview."""
        rot = self._ocr_rot_value()
        # Rotar la vista del canvas y miniaturas
        self.canvas.set_display_rotation(rot)
        self._reload_thumbs_rotated(rot)
        self._log(f"↻ Vista/OCR rotados a {rot}°. Las líneas de inicio/fin y columnas "
                  "se marcan sobre la vista rotada — si ya habías marcado, revisá su posición.")
        # Disparar preview siempre (el worker usará OCR si está activo)
        self._preview_timer.start(800)

    def _reload_thumbs_rotated(self, rot):
        """Re-aplica rotación visual a todas las miniaturas ya cargadas."""
        from PyQt6.QtGui import QTransform
        for idx, tw in self._thumbs.items():
            pix = getattr(tw, '_pix_orig_thumb', tw._pix)
            if pix is None:
                continue
            if not hasattr(tw, '_pix_orig_thumb'):
                tw._pix_orig_thumb = pix   # guardar original la primera vez
            if rot == 0:
                tw.set_pixmap(tw._pix_orig_thumb)
            else:
                t = QTransform(); t.rotate(rot)
                tw.set_pixmap(tw._pix_orig_thumb.transformed(t))

    # ── Resetear ──────────────────────────────────────────────────────
    def _reset_all(self):
        """Limpia todo y deja el módulo en estado inicial."""
        hay_datos = (
            bool(self._pdf_path)
            or bool(getattr(self, '_csv_path', ''))
            or any(tw._sel for tw in self._thumbs.values())
        )
        if hay_datos:
            resp = QMessageBox.question(
                self, "Limpiar",
                "¿Limpiar todo para empezar con otro archivo?\n"
                "Se pierden las columnas y los grupos que marcaste "
                "(guardá la receta si los querés conservar).\n"
                "No se borra nada del disco.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if resp != QMessageBox.StandardButton.Yes:
                return

        # Detener workers en curso — SIEMPRE cancelación cooperativa.
        # ⚠ Nunca terminate(): matar el hilo en medio de OCR/PIL produce
        # segfault y cierra toda la aplicación sin aviso.
        if self._loader:
            self._loader.stop(); self._loader.wait()
        if self._converter and self._converter.isRunning():
            for sig in (self._converter.progress, self._converter.log,
                        self._converter.done):
                try: sig.disconnect()
                except TypeError: pass
            self._converter.requestInterruption()
            self._converter.wait()   # esperar de verdad: si sigue vivo junto a un
                                     # worker nuevo → OCR concurrente → crash
        if self._preview_worker and self._preview_worker.isRunning():
            for sig in (self._preview_worker.ready, self._preview_worker.log,
                        self._preview_worker.error):
                try: sig.disconnect()
                except TypeError: pass
            self._preview_worker.requestInterruption()
            self._preview_worker.wait()
        if self._autoseps_worker and self._autoseps_worker.isRunning():
            self._autoseps_worker.wait()
        self._preview_pending = False
        self._preview_timer.stop()

        # Limpiar miniaturas
        for i in reversed(range(self.thumb_grid.count())):
            w = self.thumb_grid.itemAt(i).widget()
            if w: w.deleteLater()
        self._thumbs.clear()

        # Limpiar canvas
        self.canvas._pix = None; self.canvas._seps = []
        self.canvas._start_y = 0.0; self.canvas._end_y = 0.0; self.canvas.update()

        # Limpiar preview table
        self.preview_table.setRowCount(0); self.preview_table.setColumnCount(0)
        self.lbl_preview.setText("Previsualización")

        # Limpiar grupos y su historial
        for gp in self.group_panels:
            gp._history.clear()
            gp._suppress_history = True
            gp.ck_active.setChecked(gp.idx == 0)
            gp.sp_from.setValue(1); gp.sp_to.setValue(9999)
            gp.sp_start_y.setValue(0); gp.sp_end_y.setValue(0)
            gp.e_seps.clear()
            gp.ck_merge.setChecked(False); gp.sp_anchor.setValue(0)
            gp.ck_split.setChecked(False); gp.sp_split_col.setValue(1); gp.sp_split_parts.setValue(2)
            gp.ck_kw.setChecked(False); gp.sp_kw_col.setValue(0); gp.lw_kw.clear()
            gp._suppress_history = False
            gp.btn_undo.setEnabled(False)

        # Resetear cortes en cadena
        for sw in self.split_widgets:
            sw["ck_act"].setChecked(False)
            sw["cmb_col"].setCurrentIndex(0)
            sw["e_sep"].setText(" - ")
            sw["e_left"].setText("IZQ"); sw["e_right"].setText("DER")
            sw["cmb_keep"].setCurrentIndex(0); sw["cmb_pos"].setCurrentIndex(0)

        # Limpiar overrides y estado general
        self._page_overrides.clear()
        self._pdf_path = ""; self._total_pgs = 0; self._current_page = 0
        self._last_clicked = 0; self._canvas_page = None
        self.lbl_pdf.setText("Sin archivo"); self.lbl_total.setText("")
        self.lbl_page_info.setText("  Seleccioná una página")
        self.e_out.setText(""); self.pbar.setValue(0)
        self.logbox.clear(); self.btn_open.setEnabled(False)
        if hasattr(self, '_result'): del self._result

        # Limpiar editor Excel/CSV
        self._csv_path = ""; self._csv_data = []
        if hasattr(self, 'csv_table'):
            self.csv_table.setRowCount(0); self.csv_table.setColumnCount(0)
        if hasattr(self, 'lbl_csv_path'):
            self.lbl_csv_path.setText("Sin archivo")
        if hasattr(self, 'btn_csv_save'):
            self.btn_csv_save.setEnabled(False)
        if hasattr(self, 'btn_csv_export'):
            self.btn_csv_export.setEnabled(False)
        # Volver a pestaña del visor PDF
        if hasattr(self, '_right_tabs'):
            self._right_tabs.setCurrentIndex(0)

        # Re-habilitar todos los controles (por si estaban deshabilitados por un no-PDF)
        self._enable_pdf_controls(True)

        self._log("🗑 Listo. Cargá un nuevo archivo.")
        self.limpiado.emit()

    # ── Doble clic en preview → dividir columna (absorbido de M1) ─────
    def _on_preview_dbl_click(self, row, col):
        """Doble clic en la tabla de preview → abre diálogo para dividir columna."""
        header_item = self.preview_table.horizontalHeaderItem(col)
        header_text = header_item.text() if header_item else f"Col {col+1}"
        item = self.preview_table.item(row, col)
        text = item.text() if item else ""
        dlg = DialogoDividirVisual(text, header_text, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            sep, left, right, keep = dlg.get_data()
            if sep:
                # Encontrar el primer tab de corte libre
                active_idx = self.tabs_split.currentIndex()
                if self.split_widgets[active_idx]["ck_act"].isChecked():
                    for next_i in range(active_idx + 1, 9):
                        if not self.split_widgets[next_i]["ck_act"].isChecked():
                            active_idx = next_i
                            self.tabs_split.setCurrentIndex(active_idx)
                            break
                sw = self.split_widgets[active_idx]
                sw["cmb_col"].setCurrentText(header_text)
                sw["e_sep"].setText(sep)
                sw["e_left"].setText(left); sw["e_right"].setText(right)
                sw["cmb_keep"].setCurrentText(keep)
                sw["ck_act"].setChecked(True)
                self._preview_timer.start(200)

    def _apply_split_to_preview(self, rows, split_idx):
        """Aplica un corte de columna a las filas del preview."""
        sw = self.split_widgets[split_idx]
        if not sw["ck_act"].isChecked():
            return rows
        sep       = sw["e_sep"].text()
        col_name  = sw["cmb_col"].currentText()
        name_left = sw["e_left"].text().strip() or "IZQ"
        name_right= sw["e_right"].text().strip() or "DER"
        modo      = sw["cmb_pos"].currentText()
        keep      = sw["cmb_keep"].currentText()

        col_idx = None
        if sep and col_name != "(ninguna)" and rows:
            for i, v in enumerate(rows[0]):
                if v.strip() == col_name or f"Col {i+1}" == col_name:
                    col_idx = i; break
        if col_idx is None:
            return rows

        new_rows = []
        for ri, row in enumerate(rows):
            row = list(row)
            if ri == 0:
                if modo == "Reemplazar":
                    row = row[:col_idx] + [name_left, name_right] + row[col_idx+1:]
                else:
                    row = row + [name_left, name_right]
            else:
                val = row[col_idx] if col_idx < len(row) else ""
                if sep in val:
                    parts = val.split(sep, 1)
                    rl, rr = parts[0], parts[1]
                    if keep == "Unir a Izq.":   left, right = (rl + sep).strip(), rr.strip()
                    elif keep == "Unir a Der.": left, right = rl.strip(), (sep + rr).strip()
                    else:                       left, right = rl.strip(), rr.strip()
                else:
                    left, right = val.strip(), ""
                if modo == "Reemplazar":
                    row = row[:col_idx] + [left, right] + row[col_idx+1:]
                else:
                    row = row + [left, right]
            new_rows.append(row)
        return new_rows

    def _sync_scroll_canvas(self, pct):
        """Sincroniza el scroll del preview con el porcentaje dado."""
        if not self._sync_scroll_on:
            return
        vsb = self.preview_table.verticalScrollBar()
        if vsb.maximum() > 0:
            vsb.setValue(int(pct * vsb.maximum()))

    # ── Apertura universal de archivos ────────────────────────────────
    def _open_file(self):
        """Abre el diálogo multiformato y enruta al método correcto."""
        p, _ = QFileDialog.getOpenFileName(
            self, "Cargar Fuente de Datos", "",
            "Todos los formatos soportados (*.pdf *.xlsx *.csv *.ods);;"
            "Documentos PDF (*.pdf);;"
            "Hojas de cálculo Excel (*.xlsx);;"
            "Archivos CSV (*.csv);;"
            "Hojas LibreOffice/ODS (*.ods)"
        )
        if not p:
            return
        ext = os.path.splitext(p)[1].lower()
        tipo = {
            ".pdf": "PDF",
            ".xlsx": "Excel",
            ".csv": "CSV",
            ".ods": "ODS",
        }.get(ext, ext.upper())
        self.lbl_pdf.setText(f"{os.path.basename(p)}  [{tipo}]")
        self._route_file(p)

    def _route_file(self, path):
        """
        Router: detecta la extensión y toma la ruta correcta.
        - .pdf  → flujo completo de miniaturas + canvas visual
        - .xlsx/.xls/.csv/.ods → carga directa en editor tabular
        """
        ext = os.path.splitext(path)[1].lower()

        if ext == ".pdf":
            # Flujo PDF: habilitar/mostrar todos los controles PDF
            self._pdf_path = path
            self._enable_pdf_controls(True)
            self._load_thumbs()
            self.lbl_total.setText("Cargando páginas...")
        elif ext == ".xls":
            QMessageBox.warning(self, "Formato .xls no soportado",
                "El formato Excel antiguo (.xls) no es compatible.\n\n"
                "Abrí el archivo en Excel/LibreOffice y guardalo como .xlsx,\n"
                "después cargalo de nuevo acá.")
        elif ext in (".xlsx", ".csv", ".ods"):
            # Flujo datos: deshabilitar controles exclusivos de PDF
            self._enable_pdf_controls(False)
            self._pdf_path = ""
            self.lbl_total.setText("Archivo de datos — editando directamente")
            # Cargar en el editor tabular
            self._open_excel_csv_path(path)
            # Cambiar a la pestaña del editor
            self._right_tabs.setCurrentIndex(1)
        else:
            QMessageBox.warning(self, "Formato no soportado",
                f"La extensión '{ext}' no está soportada.\n"
                "Formatos válidos: PDF, xlsx, csv, ods")

    def _enable_pdf_controls(self, enabled: bool):
        """
        Habilita o deshabilita los controles exclusivos del flujo PDF.
        Cuando enabled=False (archivo de datos), estos controles se ocultan/deshabilitan.
        """
        # Panel de miniaturas de páginas
        if hasattr(self, 'thumb_scroll'):
            self.thumb_scroll.setEnabled(enabled)
            self.thumb_scroll.setVisible(enabled)
        # Selección de rango de páginas
        if hasattr(self, 'sp_sel_from'):
            self.sp_sel_from.setEnabled(enabled)
            self.sp_sel_to.setEnabled(enabled)
        # Separadores de columna y marcadores Y viven en el canvas
        if hasattr(self, 'canvas_scroll'):
            self.canvas_scroll.setEnabled(enabled)
            self.canvas_scroll.setVisible(enabled)
        # Botones del visor (inicio/fin tabla, override Y)
        for attr in ('btn_add_start', 'btn_add_end', 'btn_ov_start', 'btn_ov_end', 'btn_ov_clear'):
            if hasattr(self, attr):
                getattr(self, attr).setEnabled(enabled)
                getattr(self, attr).setVisible(enabled)
        # Grupos de páginas y cortes en cadena
        if hasattr(self, 'tabs_grp'):
            self.tabs_grp.setEnabled(enabled)
            self.tabs_grp.setVisible(enabled)
        if hasattr(self, 'tabs_split'):
            self.tabs_split.setEnabled(enabled)
            self.tabs_split.setVisible(enabled)
        # Botón de conversión a Excel/CSV desde PDF
        if hasattr(self, 'btn_conv'):
            self.btn_conv.setEnabled(enabled)
            self.btn_conv.setVisible(enabled)

    # ── PDF ───────────────────────────────────────────────────────────
    def _pick_pdf(self):
        """Mantiene compatibilidad interna — usa _open_file para nuevo flujo."""
        p, _ = QFileDialog.getOpenFileName(self, "Abrir PDF", "", "PDF (*.pdf)")
        if not p: return
        self._pdf_path = p
        self.lbl_pdf.setText(os.path.basename(p))
        self._load_thumbs()

    def _load_thumbs(self):
        # Limpiar grid
        for i in reversed(range(self.thumb_grid.count())):
            w = self.thumb_grid.itemAt(i).widget()
            if w: w.deleteLater()
        self._thumbs.clear()

        if self._loader:
            self._loader.stop(); self._loader.wait()

        self.lbl_total.setText("Cargando páginas...")
        self._loader = ThumbLoader(self._pdf_path, dpi=40)
        self._loader.done.connect(self._on_total_known)
        self._loader.thumb_ready.connect(self._on_thumb_ready)
        self._loader.start()

    def _on_total_known(self, total):
        self._total_pgs = total
        self._last_clicked = 0
        self.lbl_total.setText(f"{total} páginas")
        self.sp_sel_to.setValue(total)
        # Crear placeholders
        cols = 2
        for i in range(total):
            tw = ThumbWidget(i)
            tw.clicked.connect(self._on_thumb_clicked)
            tw.dbl_clicked.connect(self._on_thumb_preview)
            tw.set_selected(True)
            r, c = divmod(i, cols)
            self.thumb_grid.addWidget(tw, r, c)
            self._thumbs[i] = tw
        self._update_sel_count()
        # Actualizar sp_to de grupos
        for gp in self.group_panels:
            gp.sp_to.setValue(total)
        # Lanzar preview inicial (1.5 s de delay para que carguen las miniaturas)
        self._preview_timer.start(1500)

    def _on_thumb_ready(self, idx, qimg):
        if idx in self._thumbs:
            tw = self._thumbs[idx]
            pix = QPixmap.fromImage(qimg)   # conversión a QPixmap EN el hilo GUI
            tw._pix_orig_thumb = pix   # guardar original para re-rotar si cambia rotación
            rot = self._ocr_rot_value()
            if rot != 0:
                from PyQt6.QtGui import QTransform
                t = QTransform(); t.rotate(rot)
                tw.set_pixmap(pix.transformed(t))
            else:
                tw.set_pixmap(pix)

    def _on_thumb_clicked(self, idx, modifiers=0):
        """Click simple → solo alterna selección (rápido, sin bloquear UI)."""
        # mod_int: bit 0 = Shift, bit 1 = Ctrl  (codificado en mousePressEvent)
        shift = bool(modifiers & 1)
        tw = self._thumbs.get(idx)
        if not tw:
            return

        if shift and self._last_clicked != idx:
            # Marcar rango desde el último click hasta acá
            start, end = sorted([self._last_clicked, idx])
            for i, tw2 in self._thumbs.items():
                if start <= i <= end:
                    tw2.set_selected(True)
        else:
            # Toggle individual (con o sin Ctrl)
            tw.set_selected(not tw._sel)

        self._last_clicked = idx
        self._update_sel_count()

    def _on_thumb_preview(self, idx):
        """Doble click → ver/ajustar página en el visor canvas."""
        self._current_page = idx
        self._last_clicked = idx
        self._refresh_page_label(idx)
        self._load_canvas_page(idx)

    def _refresh_page_label(self, idx):
        pn = idx + 1
        ov = self._page_overrides.get(pn)
        if ov:
            parts = []
            if "start_y" in ov: parts.append(f"InicioY={int(ov['start_y'])}")
            if "end_y"   in ov: parts.append(f"FinY={int(ov['end_y'])}")
            self.lbl_page_info.setText(f"  📄  Página {pn}  ⚡ override: {', '.join(parts)}")
        else:
            self.lbl_page_info.setText(f"  📄  Página {pn}  (Y del grupo)")

    def _set_ov_start(self):
        pn = self._current_page + 1
        ov = self._page_overrides.setdefault(pn, {})
        ov["start_y"] = self.canvas._start_y
        self._apply_override_thumb(pn)
        self._refresh_page_label(self._current_page)
        self._log(f"📌 Pág {pn}: override Inicio Y={int(self.canvas._start_y)}")

    def _set_ov_end(self):
        pn = self._current_page + 1
        ov = self._page_overrides.setdefault(pn, {})
        ov["end_y"] = self.canvas._end_y
        self._apply_override_thumb(pn)
        self._refresh_page_label(self._current_page)
        self._log(f"📌 Pág {pn}: override Fin Y={int(self.canvas._end_y)}")

    def _clear_ov(self):
        pn = self._current_page + 1
        if pn in self._page_overrides:
            del self._page_overrides[pn]
        self._apply_override_thumb(pn)
        self._refresh_page_label(self._current_page)
        # Recargar canvas con valores del grupo
        grp = self._get_group_for_page(pn)
        if grp:
            self._sync_canvas_from_group(grp, pn)
        self._log(f"🗑 Pág {pn}: override eliminado → usa Y del grupo")

    def _apply_override_thumb(self, pn):
        tw = self._thumbs.get(pn - 1)
        if tw:
            tw.set_override(pn in self._page_overrides)

    def _load_canvas_page(self, idx):
        if not self._pdf_path: return
        grp = self._get_group_for_page(idx + 1)
        rot = self._ocr_rot_value()
        def _load():
            self.canvas.load_page(self._pdf_path, idx, dpi=120)
            self.canvas.set_display_rotation(rot)
        QTimer.singleShot(10, _load)
        if grp:
            QTimer.singleShot(250, lambda: self._sync_canvas_from_group(grp, idx + 1))

    def _sync_canvas_from_group(self, grp, pn):
        cfg = grp.get_config()
        self.canvas.set_seps(cfg["seps"])
        ov = self._page_overrides.get(pn, {})
        self.canvas.set_start_y(ov.get("start_y", cfg["start_y"]))
        self.canvas.set_end_y(ov.get("end_y", cfg["end_y"]))

    def _get_group_for_page(self, pn):
        for gp in self.group_panels:
            cfg = gp.get_config()
            if cfg["active"] and cfg["p_from"] <= pn <= cfg["p_to"]:
                return gp
        return self.group_panels[self.tabs_grp.currentIndex()]

    def _update_sel_count(self):
        n_sel     = sum(1 for tw in self._thumbs.values() if tw._sel)
        n_visible = sum(1 for tw in self._thumbs.values() if tw.isVisible())
        n_total   = len(self._thumbs)
        hay_ocultas = n_visible < n_total
        if hay_ocultas:
            self.lbl_sel_count.setText(f"{n_sel} sel.  · {n_visible}/{n_total} visibles")
        else:
            self.lbl_sel_count.setText(f"{n_sel} sel.")
        self.btn_show_all.setVisible(hay_ocultas)
        # Colorear según grupo + marcar overrides
        for idx, tw in self._thumbs.items():
            pn = idx + 1
            col = None
            for i, gp in enumerate(self.group_panels):
                cfg = gp.get_config()
                if cfg["active"] and cfg["p_from"] <= pn <= cfg["p_to"]:
                    col = GRP_COLORS[i]; break
            tw.set_group_color(col)
            tw.set_override(pn in self._page_overrides)

    # ── Selección ─────────────────────────────────────────────────────
    def _select_range(self):
        f, t = self.sp_sel_from.value() - 1, self.sp_sel_to.value() - 1
        for idx, tw in self._thumbs.items():
            tw.set_selected(f <= idx <= t)
        # Ocultar las que quedan fuera del rango
        self._filter_thumbs(f, t)
        self._update_sel_count()
        self._preview_timer.start(600)

    def _select_all(self):
        for tw in self._thumbs.values(): tw.set_selected(True)
        self._filter_thumbs(None, None)   # mostrar todas
        self._update_sel_count()
        self._preview_timer.start(600)

    def _select_none(self):
        for tw in self._thumbs.values(): tw.set_selected(False)
        self._filter_thumbs(None, None)   # mostrar todas (sin marcar)
        self._update_sel_count()
        self._preview_timer.start(600)

    def _filter_thumbs(self, from_idx, to_idx):
        """
        Reconstruye el grid mostrando solo los thumbs del rango [from_idx, to_idx].
        Si from_idx/to_idx son None → muestra todos.
        """
        # Quitar todos los widgets del layout sin destruirlos
        for i in reversed(range(self.thumb_grid.count())):
            item = self.thumb_grid.itemAt(i)
            if item and item.widget():
                self.thumb_grid.removeWidget(item.widget())

        cols = 2
        pos  = 0
        for idx in sorted(self._thumbs.keys()):
            tw      = self._thumbs[idx]
            visible = (from_idx is None) or (from_idx <= idx <= to_idx)
            if visible:
                r, c = divmod(pos, cols)
                self.thumb_grid.addWidget(tw, r, c)
                tw.show()
                pos += 1
            else:
                tw.hide()

        self.thumb_container.adjustSize()

    def _show_all_thumbs(self):
        """Restaura visibilidad de todas las páginas sin cambiar la selección."""
        self._filter_thumbs(None, None)
        self._update_sel_count()
        self._preview_timer.start(600)

    # ── Canvas callbacks ──────────────────────────────────────────────
    def _canvas_add_start(self): self.canvas.add_start_line()
    def _canvas_add_end(self):   self.canvas.add_end_line()

    def _on_canvas_seps_changed(self, seps):
        grp = self._get_group_for_page(self._current_page + 1)
        if grp: grp.set_seps(seps)
        self._preview_timer.start(900)   # debounce: actualizar preview 900 ms después

    def _on_canvas_start_changed(self, y):
        grp = self._get_group_for_page(self._current_page + 1)
        if grp: grp.set_start_y(y)
        self._preview_timer.start(900)

    def _on_canvas_end_changed(self, y):
        grp = self._get_group_for_page(self._current_page + 1)
        if grp: grp.set_end_y(y)
        self._preview_timer.start(900)

    def _on_group_changed(self):
        self._update_sel_count()
        self._preview_timer.start(1200)

    # ── Preview de datos ─────────────────────────────────────────────
    def _update_preview(self):
        if not self._pdf_path:
            return
        # Mientras la conversión está corriendo NO se lanza preview: dos hilos
        # con OCR/render en paralelo producen access violation. Queda diferido.
        if self._converter and self._converter.isRunning():
            self._preview_pending = True
            return
        groups = [gp.get_config() for gp in self.group_panels]
        active = [g for g in groups if g["active"]]
        if not active:
            self.lbl_preview.setText("  📊  Activá al menos un grupo")
            return
        n = self.sp_prev_n.value()
        self.lbl_preview.setText(f"  📊  Cargando {n} pág(s)...")
        # SERIALIZADO: un solo worker a la vez. Nunca terminate() (mata el hilo en
        # medio de OCR → segfault) ni dos workers OCR en paralelo (tesseract/PIL no
        # son seguros concurrentes). Si hay uno corriendo, le pido parar y difiero
        # el relanzamiento hasta que termine.
        if self._preview_worker and self._preview_worker.isRunning():
            self._preview_pending = True
            self._preview_worker.requestInterruption()
            return
        self._preview_pending = False
        sel_pages = {idx + 1 for idx, tw in self._thumbs.items() if tw._sel} or None
        self._preview_worker = PreviewWorker(
            self._pdf_path, active, self._page_overrides,
            n_pages=n, selected_pages=sel_pages,
            word_gap=self.sp_wgap.value() / 10.0,
            x_min=self.sp_xmin.value() if self.ck_xmin.isChecked() else 0,
            ocr_enabled=self.ck_ocr.isChecked(),
            ocr_lang=self.cmb_ocr_lang.currentText(),
            ocr_rotation=self._ocr_rot_value(),
            ocr_enhance=self._ocr_enhance_value(),
            ocr_min_conf=self.sp_ocr_conf.value())
        self._preview_worker.ready.connect(self._on_preview_ready)
        self._preview_worker.log.connect(self._log)
        self._preview_worker.error.connect(
            lambda e: (self.lbl_preview.setText("  ⚠ Error al previsualizar"), self._log(f"⚠ Preview: {e}")))
        self._preview_worker.finished.connect(self._on_preview_finished)
        self._preview_worker.start()

    def _on_preview_finished(self):
        """Cuando un worker termina, relanza el preview si quedó pendiente."""
        if getattr(self, "_preview_pending", False):
            self._preview_pending = False
            self._preview_timer.start(100)

    def _on_preview_ready(self, headers, rows):
        t = self.preview_table
        prev_nc = t.columnCount()
        t.blockSignals(True)
        t.clearContents()
        if not headers and not rows:
            self.lbl_preview.setText("📊 Sin datos — revisá seps y Y del grupo")
            t.setRowCount(0); t.setColumnCount(0)
            t.blockSignals(False)
            return

        # Combinar headers + rows en una sola lista para aplicar cortes
        all_rows = [headers] + list(rows) if headers else list(rows)

        # Actualizar combos de cortes con las columnas actuales y aplicar cortes activos
        current_headers = list(all_rows[0]) if all_rows else []
        for si, sw in enumerate(self.split_widgets):
            sw["cmb_col"].blockSignals(True)
            prev = sw["cmb_col"].currentText()
            sw["cmb_col"].clear(); sw["cmb_col"].addItem("(ninguna)")
            for j, h in enumerate(current_headers):
                sw["cmb_col"].addItem(h.strip() or f"Col {j+1}")
            idx = sw["cmb_col"].findText(prev)
            sw["cmb_col"].setCurrentIndex(max(0, idx))
            sw["cmb_col"].blockSignals(False)
            if sw["ck_act"].isChecked():
                all_rows = self._apply_split_to_preview(all_rows, si)
                if all_rows:
                    current_headers = list(all_rows[0])

        if not all_rows:
            t.setRowCount(0); t.setColumnCount(0); t.blockSignals(False); return

        headers_final = all_rows[0]
        rows_final    = all_rows[1:]
        nc = max(len(r) for r in all_rows) if all_rows else 1

        t.setColumnCount(nc)
        t.setHorizontalHeaderLabels([str(h).strip() or f"Col {i+1}" for i, h in enumerate(headers_final)])
        t.setRowCount(len(rows_final))
        for r, row in enumerate(rows_final):
            for c in range(nc):
                val = row[c] if c < len(row) else ""
                t.setItem(r, c, QTableWidgetItem(str(val)))
        t.blockSignals(False)
        # Auto-resize solo si cambiaron las columnas (nuevo PDF o nueva config)
        if nc != prev_nc:
            t.resizeColumnsToContents()
        n = self.sp_prev_n.value()
        grp_activo = self.tabs_grp.currentIndex()
        gp = self.group_panels[grp_activo]
        merge_info = " · 🔗 fusión ON" if gp.ck_merge.isChecked() else ""
        n_cuts = sum(1 for sw in self.split_widgets if sw["ck_act"].isChecked())
        cuts_info = f" · {n_cuts} corte(s)" if n_cuts else ""
        self.lbl_preview.setText(
            f"📊 {len(rows_final)} filas · {nc} cols · {n} pág(s){merge_info}{cuts_info}  —  dblClick=dividir col")

    def _auto_resize_preview(self):
        """Ajusta ancho de columnas del preview automáticamente."""
        self.preview_table.resizeColumnsToContents()

    # ── Auto-detectar seps ────────────────────────────────────────────
    # Corre en un worker: antes se ejecutaba en el hilo GUI (congelaba la
    # interfaz 3-10 s con OCR) y podía correr en paralelo con el preview.
    def _auto_seps_group(self, idx):
        if not self._pdf_path: return
        if self._autoseps_worker and self._autoseps_worker.isRunning():
            self._log("⏳ Ya hay una auto-detección en curso, esperá que termine.")
            return
        gp  = self.group_panels[idx]
        cfg = gp.get_config()
        params = dict(y_tol=3, min_gap=8,
                      word_gap=self.sp_wgap.value() / 10.0,
                      ocr_enabled=self.ck_ocr.isChecked(),
                      ocr_lang=self.cmb_ocr_lang.currentText(),
                      ocr_rotation=self._ocr_rot_value(),
                      ocr_enhance=self._ocr_enhance_value(),
                      ocr_min_conf=self.sp_ocr_conf.value())
        gp.btn_auto.setEnabled(False)
        self._log(f"🔄 Grupo {idx+1}: detectando columnas (pág {cfg['p_from']})...")
        self._autoseps_worker = AutoSepsWorker(self._pdf_path, cfg["p_from"] - 1, idx, params)
        self._autoseps_worker.result.connect(self._on_autoseps_done)
        self._autoseps_worker.error.connect(self._on_autoseps_error)
        self._autoseps_worker.start()

    def _on_autoseps_done(self, idx, seps):
        gp = self.group_panels[idx]
        gp.btn_auto.setEnabled(True)
        gp.set_seps(seps)
        self._log(f"🔄 Grupo {idx+1}: {len(seps)+1} columnas auto-detectadas")

    def _on_autoseps_error(self, msg):
        for gp in self.group_panels:
            gp.btn_auto.setEnabled(True)
        self._log(f"❌ Error auto-detect: {msg}")

    def _take_seps_from_canvas(self, idx):
        seps = self.canvas.get_seps()
        self.group_panels[idx].set_seps(seps)
        self._log(f"📐 Grupo {idx+1}: {len(seps)} separadores tomados del visor")

    def _take_start_from_canvas(self, idx):
        y = self.canvas._start_y
        self.group_panels[idx].set_start_y(y)
        self._log(f"🔵 Grupo {idx+1}: Inicio Y={int(y)}pt")

    def _take_end_from_canvas(self, idx):
        y = self.canvas._end_y
        self.group_panels[idx].set_end_y(y)
        self._log(f"🟢 Grupo {idx+1}: Fin Y={int(y)}pt")

    # ── Receta ────────────────────────────────────────────────────────
    def _save_recipe(self):
        p, _ = QFileDialog.getSaveFileName(self, "Guardar receta", "", "JSON (*.json)")
        if not p: return
        # Serializar overrides con claves string para JSON
        ov_serial = {str(k): v for k, v in self._page_overrides.items()}
        recipe = {"pdf":       self._pdf_path,
                  "groups":    [gp.get_config() for gp in self.group_panels],
                  "overrides": ov_serial}
        with open(p if p.endswith(".json") else p+".json", "w", encoding="utf-8") as f:
            json.dump(recipe, f, indent=2)
        n_ov = len(self._page_overrides)
        self._log(f"💾 Receta guardada: {os.path.basename(p)}"
                  + (f"  ({n_ov} override(s) Y)" if n_ov else ""))

    def _load_recipe(self):
        p, _ = QFileDialog.getOpenFileName(self, "Cargar receta", "", "JSON (*.json)")
        if not p: return
        try:
            with open(p, "r", encoding="utf-8") as f: data = json.load(f)
            if data.get("pdf") and os.path.exists(data["pdf"]):
                self._pdf_path = data["pdf"]
                self.lbl_pdf.setText(os.path.basename(self._pdf_path))
                self._load_thumbs()
            for i, cfg in enumerate(data.get("groups", [])):
                if i < len(self.group_panels):
                    self.group_panels[i].set_config(cfg)
            # Cargar overrides
            self._page_overrides = {int(k): v for k, v in data.get("overrides", {}).items()}
            self._update_sel_count()   # refresca badges de override en thumbs
            n_ov = len(self._page_overrides)
            self._log(f"📂 Receta cargada: {os.path.basename(p)}"
                      + (f"  ({n_ov} override(s) Y)" if n_ov else ""))
        except Exception as e:
            QMessageBox.warning(self, "Error", f"No se pudo cargar la receta:\n{e}")

    # ── Conversión ────────────────────────────────────────────────────
    def _destino_sugerido(self):
        """Dentro de Navaja: se propone guardar al lado del
        PDF, con su mismo nombre."""
        if not self._pdf_path:
            return ""
        return os.path.splitext(self._pdf_path)[0] + ".xlsx"

    def _pick_out(self):
        p, _ = QFileDialog.getSaveFileName(self, "Guardar como",
                                           self._destino_sugerido(),
                                           "Excel (*.xlsx);;CSV (*.csv)")
        if p: self.e_out.setText(p)

    def _convert(self):
        if not self._pdf_path:
            QMessageBox.warning(self, "Aviso", "Cargá un PDF primero."); return
        out = self.e_out.text().strip()
        if not out:
            # Auto-abrir diálogo de destino
            out, _ = QFileDialog.getSaveFileName(
                self, "Guardar Excel / CSV", self._destino_sugerido(),
                "Excel (*.xlsx);;CSV (*.csv)")
            if not out:
                return
            self.e_out.setText(out)

        groups = [gp.get_config() for gp in self.group_panels]
        active = [g for g in groups if g["active"]]
        if not active:
            QMessageBox.warning(self, "Aviso", "Activá al menos un grupo."); return

        opts = {
            "y_tol":        3,
            "word_gap":     self.sp_wgap.value() / 10.0,
            "x_min":        self.sp_xmin.value() if self.ck_xmin.isChecked() else 0,
            "alt_rows":     self.ck_alt.isChecked(),
            "borders":      self.ck_brd.isChecked(),
            "freeze":       self.ck_frz.isChecked(),
            "page_sep":     self.ck_sep.isChecked(),
            "export_pdf":   self.ck_pdf.isChecked(),
            "ocr_enabled":  self.ck_ocr.isChecked(),
            "ocr_lang":     self.cmb_ocr_lang.currentText(),
            "ocr_rotation": self._ocr_rot_value(),
            "ocr_enhance":  self._ocr_enhance_value(),
            "ocr_min_conf": self.sp_ocr_conf.value(),
        }

        # Frenar el preview ANTES de convertir: OCR/render concurrentes = crash
        self._preview_timer.stop()
        self._preview_pending = False
        if self._preview_worker and self._preview_worker.isRunning():
            self._preview_worker.requestInterruption()
            self._preview_worker.wait()

        self.btn_conv.setEnabled(False); self.btn_open.setEnabled(False)
        self.pbar.setValue(0); self.logbox.clear()
        self._log(f"🚀 Convirtiendo {self._pdf_path}...")
        for g in active:
            self._log(f"  📌 {g['name']}: págs {g['p_from']}-{g['p_to']} | "
                      f"Y {int(g['start_y'])}-{int(g['end_y']) or 'fin'} | "
                      f"{len(g['seps'])+1} cols")

        if self._page_overrides:
            self._log(f"  📌 {len(self._page_overrides)} página(s) con override Y individual")
        sel_pages = {idx + 1 for idx, tw in self._thumbs.items() if tw._sel} or None
        n_sel = len(sel_pages) if sel_pages else self._total_pgs
        self._log(f"  📄 {n_sel} página(s) seleccionadas para exportar")
        self._converter = PageConverter(
            self._pdf_path, out, active, opts,
            overrides=self._page_overrides, selected_pages=sel_pages)
        self._converter.progress.connect(self.pbar.setValue)
        self._converter.log.connect(self._log)
        self._converter.done.connect(self._on_done)
        self._converter.start()

    def _on_done(self, ok, info):
        self.btn_conv.setEnabled(True)
        # Si quedó un preview diferido mientras se convertía, relanzarlo ahora
        if getattr(self, "_preview_pending", False):
            self._preview_pending = False
            self._preview_timer.start(300)
        if ok:
            self._result = info; self.btn_open.setEnabled(True)
            self._log(f"\n✅ Guardado: {info}")
            self.receta_lista.emit([gp.get_config() for gp in self.group_panels])
            self.excel_generado.emit(info)
            QMessageBox.information(self, "Listo", f"Archivo generado:\n{info}")
        else:
            self._log(f"\n❌ Error: {info}")
            QMessageBox.critical(self, "Error", info)

    def _open_result(self):
        if hasattr(self, "_result") and os.path.exists(self._result):
            import subprocess, platform
            s = platform.system()
            if s == "Windows":   os.startfile(self._result)
            elif s == "Darwin":  subprocess.Popen(["open", self._result])
            else:                subprocess.Popen(["xdg-open", self._result])

    # ── Rotación de páginas ───────────────────────────────────────────
    def _rotate_pdf(self):
        if not self._pdf_path:
            QMessageBox.warning(self, "Aviso", "Cargá un PDF primero."); return

        # Scope
        if self.cmb_rot_scope.currentIndex() == 0:
            pages_to_rotate = None   # todas
            n_desc = "todas las páginas"
        else:
            pages_to_rotate = {idx + 1 for idx, tw in self._thumbs.items() if tw._sel}
            if not pages_to_rotate:
                QMessageBox.warning(self, "Aviso",
                    "No hay páginas seleccionadas.\n"
                    "Marcá al menos una miniatura (clic en azul) o elegí 'Todas'.")
                return
            n_desc = f"{len(pages_to_rotate)} página(s) seleccionada(s)"

        angle_map = {0: 90, 1: 180, 2: 270}
        angle = angle_map[self.cmb_rot_angle.currentIndex()]

        base = os.path.splitext(self._pdf_path)[0]
        out, _ = QFileDialog.getSaveFileName(
            self, "Guardar PDF rotado",
            f"{base}_rot{angle}.pdf", "PDF (*.pdf)")
        if not out: return
        if not out.lower().endswith(".pdf"): out += ".pdf"

        self.btn_rotate.setEnabled(False)
        self.pbar.setValue(0); self.logbox.clear()
        self._log(f"↻ Rotando {n_desc}  {angle}°...")
        self._rotator = PDFRotator(self._pdf_path, out, pages_to_rotate, angle)
        self._rotator.progress.connect(self.pbar.setValue)
        self._rotator.log.connect(self._log)
        self._rotator.done.connect(self._on_rotate_done)
        self._rotator.start()

    def _on_rotate_done(self, ok, info):
        self.btn_rotate.setEnabled(True)
        if ok:
            resp = QMessageBox.question(
                self, "PDF rotado — ¿Cargar?",
                f"Guardado:\n{info}\n\n¿Cargar el PDF rotado en el programa?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if resp == QMessageBox.StandardButton.Yes:
                self._pdf_path = info
                self.lbl_pdf.setText(os.path.basename(info))
                self._load_thumbs()
        else:
            QMessageBox.critical(self, "Error al rotar", info)

    def _log(self, msg):
        self.logbox.append(msg)
        self.logbox.verticalScrollBar().setValue(
            self.logbox.verticalScrollBar().maximum())

    def get_groups(self):
        return [gp.get_config() for gp in self.group_panels]


# ══════════════════════════════════════════════════════════════════════
#  STANDALONE
# ══════════════════════════════════════════════════════════════════════
def _install_excepthook():
    """Captura excepciones no manejadas: las loguea a crash_log.txt y las muestra,
    en vez de dejar que PyQt cierre la app de golpe."""
    import traceback as _tb
    log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "crash_log.txt")
    def _hook(etype, evalue, etb):
        msg = "".join(_tb.format_exception(etype, evalue, etb))
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(msg + "\n" + "=" * 70 + "\n")
        except Exception:
            pass
        sys.stderr.write(msg)
        try:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(None, "Error capturado",
                                 f"{etype.__name__}: {evalue}\n\n"
                                 f"Detalle guardado en:\n{log_path}")
        except Exception:
            pass
    sys.excepthook = _hook


if __name__ == "__main__":
    _install_excepthook()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = QMainWindow()
    win.setWindowTitle("Preparador Universal de Datos — v2.5")
    win.setMinimumSize(1200, 750)
    w = PreparadorWidget(dark=True)
    win.setCentralWidget(w)
    win.show()
    sys.exit(app.exec())
