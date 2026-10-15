"""
motors/motor_ocr.py — Reconocimiento óptico de caracteres (OCR).
"""
import os
import shutil
import tempfile
from typing import Callable, Optional

from core.paths import BIN_DIR, TEMP_DIR


def _find_tesseract() -> Optional[str]:
    """Busca tesseract en BIN_DIR, luego en PATH, luego en rutas estándar."""
    # 1) Junto al programa (build portable): bin/tesseract/ es el layout que
    #    arma el empaquetado (el exe viene con sus DLLs y su tessdata al lado);
    #    bin/tesseract.exe se acepta por compatibilidad con copias sueltas.
    for local in (os.path.join(BIN_DIR, "tesseract", "tesseract.exe"),
                  os.path.join(BIN_DIR, "tesseract.exe")):
        if os.path.isfile(local):
            # Fijar los idiomas propios: si la PC de destino tiene un
            # TESSDATA_PREFIX apuntando a otra instalación (o a una ruta que
            # ya no existe), tesseract no encontraría spa/eng y fallaría.
            tessdata = os.path.join(os.path.dirname(local), "tessdata")
            if os.path.isdir(tessdata):
                os.environ["TESSDATA_PREFIX"] = tessdata
            return local
    # 2) En el PATH del sistema
    found = shutil.which("tesseract")
    if found:
        return found
    # 3) Ubicaciones de instalación habituales en Windows (el instalador
    #    oficial NO agrega Tesseract al PATH por defecto).
    candidates = [
        os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"),
                     "Tesseract-OCR", "tesseract.exe"),
        os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                     "Tesseract-OCR", "tesseract.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""),
                     "Programs", "Tesseract-OCR", "tesseract.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""),
                     "Tesseract-OCR", "tesseract.exe"),
        r"C:\Tesseract-OCR\tesseract.exe",
    ]
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    return None


TESSERACT_PATH = _find_tesseract()


def is_available() -> bool:
    return TESSERACT_PATH is not None


def is_scanned_pdf(filepath: str) -> bool:
    """Detecta si un PDF es principalmente imágenes (escaneado)."""
    try:
        from pypdf import PdfReader
        with open(filepath, "rb") as f:
            reader = PdfReader(f)
            text = ""
            for page in reader.pages[:5]:  # revisar primeras 5 páginas
                text += (page.extract_text() or "")
        return len(text.strip()) < 50
    except Exception:
        return False


def _get_tesseract_lang(lang: str) -> str:
    """Mapea idioma legible a código tesseract."""
    mapping = {
        "Español":    "spa",
        "Inglés":     "eng",
        "Portugués":  "por",
        "Francés":    "fra",
        "Alemán":     "deu",
        "Italiano":   "ita",
    }
    return mapping.get(lang, "spa")


# Por debajo de este promedio de palabras por renglón, la lectura automática
# se considera "desarmada en columnas" y se relee la página como bloque único.
_MIN_WORDS_PER_LINE = 4
_MIN_LINES_TO_JUDGE = 8


def _words_per_line(text: str) -> tuple:
    lines = [l for l in text.splitlines() if l.strip()]
    if not lines:
        return 0.0, 0
    return sum(len(l.split()) for l in lines) / len(lines), len(lines)


def _ocr_pil_lang(img, lang_code: str) -> str:
    """OCR de la página en modo automático, con relectura si sale en pedazos.

    El modo automático de Tesseract (psm 3) busca columnas. Con texto
    justificado muy estirado, tipografía de máquina de escribir o formularios,
    los espacios anchos entre palabras le parecen separaciones de columna y lee
    la hoja "de arriba abajo" por tiras: el TXT sale con una a tres palabras por
    renglón. Si pasa eso, se relee como un único bloque (psm 6), que respeta el
    renglón completo. No se usa psm 6 siempre porque en un documento que de
    verdad tiene dos columnas mezclaría los renglones de ambas."""
    import pytesseract
    if TESSERACT_PATH:
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
    text = pytesseract.image_to_string(img, lang=lang_code)
    wpl, n = _words_per_line(text)
    if n >= _MIN_LINES_TO_JUDGE and wpl < _MIN_WORDS_PER_LINE:
        bloque = pytesseract.image_to_string(img, lang=lang_code, config="--psm 6")
        wpl_b, _ = _words_per_line(bloque)
        if wpl_b > wpl * 1.5:
            return bloque
    return text


def _ocr_pil(img, lang_code: str) -> str:
    """Extrae texto de una imagen PIL ya abierta con pytesseract."""
    try:
        return _ocr_pil_lang(img, lang_code)
    except Exception as e:
        # Intentar sin idioma específico
        try:
            return _ocr_pil_lang(img, "eng")
        except Exception:
            raise RuntimeError(f"Error en OCR: {e}")


def _ocr_image(image_path: str, lang_code: str) -> str:
    """Extrae texto de una imagen (por ruta) con pytesseract."""
    from PIL import Image
    with Image.open(image_path) as img:
        return _ocr_pil(img, lang_code)


def convert_image_to_text(src_path: str, dst_path: str, lang: str = "Español",
                           progress_cb: Optional[Callable] = None) -> None:
    """Convierte imagen directamente a texto mediante OCR."""
    if not is_available():
        raise RuntimeError(
            "Reconocimiento de texto no disponible.\n"
            "Colocá tesseract.exe en la carpeta bin/ del programa."
        )
    lang_code = _get_tesseract_lang(lang)
    if progress_cb:
        progress_cb(f"🔍 OCR: extrayendo texto de imagen...")
    text = _ocr_image(src_path, lang_code)
    with open(dst_path, "w", encoding="utf-8") as f:
        f.write(text)


def convert_pdf_to_text(src_path: str, dst_path: str, lang: str = "Español",
                         progress_cb: Optional[Callable] = None,
                         page_cb: Optional[Callable] = None) -> None:
    """Convierte un PDF a texto, con OCR en las páginas escaneadas.

    Renderiza con PyMuPDF (igual que el PDF buscable): antes usaba pdf2image,
    que necesita **poppler** instalado y en el PATH. En el .exe portable poppler
    no viaja, así que todo PDF → TXT con OCR moría con
    "PDFInfoNotInstalledError: Unable to get page count" y el fallback por
    ImportError no se disparaba (pdf2image sí estaba, lo que faltaba era el
    binario). PyMuPDF ya es dependencia del programa y no necesita nada externo.

    Las páginas digitales se leen directo del PDF (más fiel y muchísimo más
    rápido), armadas por renglón como se ven en la hoja; las escaneadas pasan
    por OCR, así un documento mixto no se degrada ni tarda de más.

    Qué es escaneada se decide por la imagen que tapa la hoja, no por cuánto
    texto trae: algunos sistemas le estampan a cada hoja escaneada "COPIA / Usuario: ...
    fecha" como texto (57 letras), eso pasaba el mínimo, no se hacía OCR y del
    escrito salía sólo el sello. Una capa de texto invisible que haya puesto
    el escáner tampoco se usa: se relee con OCR, como pide quien activa OCR.

    `page_cb(actual, total)` mueve la barra de avance dentro del archivo: en un
    documento de cientos de páginas el OCR tarda minutos y sin esto no se ve
    ningún progreso."""
    if not is_available():
        raise RuntimeError(
            "Reconocimiento de texto no disponible.\n"
            "Colocá tesseract.exe en la carpeta bin/ del programa."
        )

    import fitz  # PyMuPDF
    from motors.motor_pdf_tools import renglones_de_pagina

    lang_code = _get_tesseract_lang(lang)
    all_text = []

    doc = fitz.open(src_path)
    try:
        total = doc.page_count
        for i, page in enumerate(doc):
            # 1) Página digital: su propio texto, por renglones
            texto = ""
            if not _page_is_scan(page, _TXT_SCAN_IMG_RATIO):
                texto = "\n".join(renglones_de_pagina(page)).strip()
            if len(texto) >= _MIN_TEXT_PER_PAGE:
                if progress_cb:
                    progress_cb(f"📄 Página {i+1}/{total}: texto del PDF (sin OCR)")
            else:
                # 2) Página escaneada: renderizar y pasar por Tesseract
                if progress_cb:
                    progress_cb(f"🔍 OCR página {i+1}/{total}...")
                img = _render_page(page)
                try:
                    texto = (_ocr_pil(img, lang_code) or "").strip()
                finally:
                    img.close()

            all_text.append(f"--- Página {i+1} ---\n{texto}")
            if page_cb:
                page_cb(i + 1, total)
    finally:
        doc.close()

    with open(dst_path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(all_text))


# ─────────────────────────────────────────────────────────────────────────────
# PDF BUSCABLE (searchable PDF) — conserva la página original y le agrega
# una capa de texto invisible, seleccionable y buscable (Ctrl+F).
# ─────────────────────────────────────────────────────────────────────────────

_OCR_DPI = 300        # resolución ideal de render para PDF buscable
_OCR_MAX_EDGE = 4000  # px máximos en el lado más largo de una página renderizada
_OCR_MAX_MP = 12.0    # megapíxeles máximos por página renderizada

# Mínimo de caracteres que debe tener la capa de texto de una página para
# darla por buena y saltear el OCR. Un escaneo suele traer 0; algunos traen
# basura de unos pocos caracteres (números de sello, marcas del escáner).
_MIN_TEXT_PER_PAGE = 20

# Para PDF → TXT: una imagen que tapa esto o más de la hoja la hace escaneada.
# Medido en escritos reales: los escaneos tapan del 84 al 100 % (el sistema les
# deja margen para el sello); en las páginas digitales, el logo, un 4 %.
_TXT_SCAN_IMG_RATIO = 0.60


def _pick_dpi(page, base_dpi: int = _OCR_DPI) -> float:
    """Elige un DPI de render seguro para OCR.

    Algunos PDF declaran un tamaño de página enorme (p. ej. 35×50 pulgadas) aun
    cuando la imagen escaneada real es chica. Renderizar esos a 300 DPI genera
    imágenes de cientos de megapíxeles (cientos de MB cada una) que agotan la RAM
    y encima son un sobre-escalado inútil. Acotamos el render por lado máximo y
    por megapíxeles totales, sin superar nunca el DPI ideal.
    """
    w_in = page.rect.width / 72.0
    h_in = page.rect.height / 72.0
    long_in = max(w_in, h_in, 1e-6)
    dpi = float(base_dpi)
    dpi = min(dpi, _OCR_MAX_EDGE / long_in)         # tope por lado más largo
    mp = (w_in * dpi) * (h_in * dpi) / 1_000_000.0
    if mp > _OCR_MAX_MP:                              # tope por megapíxeles
        dpi *= (_OCR_MAX_MP / mp) ** 0.5
    return max(72.0, dpi)


def _count_pdf_pages(src_path: str) -> int:
    """Cantidad de páginas del PDF (sin renderizar nada)."""
    import fitz  # PyMuPDF
    doc = fitz.open(src_path)
    try:
        return doc.page_count
    finally:
        doc.close()


def pdf_sin_terminar(src_path: str) -> bool:
    """¿Al PDF le falta el cierre? Es lo que pasa mientras otro programa lo
    está guardando («Microsoft Print to PDF» tarda minutos en un archivo
    grande) o cuando la descarga se cortó: se abre, pero sin páginas o con
    menos de las que tiene. Sólo se usa para explicar un error que ya ocurrió."""
    try:
        with open(src_path, "rb") as f:
            f.seek(0, os.SEEK_END)
            f.seek(max(0, f.tell() - 2048))
            return b"%%EOF" not in f.read()
    except OSError:
        return False


PDF_SIN_TERMINAR_MSG = (
    "El PDF está incompleto: todavía se está guardando o la descarga se "
    "cortó.\nEsperá a que termine de guardarse (que el tamaño deje de "
    "crecer) y volvé a convertir."
)


def _render_page(page, dpi: int = _OCR_DPI):
    """Renderiza una página de PyMuPDF a imagen PIL, con DPI acotado."""
    import fitz  # PyMuPDF
    from PIL import Image
    eff_dpi = _pick_dpi(page, base_dpi=dpi)
    zoom = eff_dpi / 72.0
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    mode = "RGBA" if pix.alpha else "RGB"
    img = Image.frombytes(mode, (pix.width, pix.height), pix.samples)
    img = img.convert("RGB")
    del pix  # liberar el buffer del render cuanto antes
    return img


def _iter_pdf_pages(src_path: str, dpi: int = _OCR_DPI):
    """Renderiza las páginas de un PDF de a una (generador) usando PyMuPDF.

    Importante: rinde una imagen PIL por vez en lugar de acumularlas todas en
    una lista. Esto mantiene el uso de memoria acotado a una sola página, lo que
    permite procesar libros enteros (cientos de páginas a 300 DPI) sin agotar la
    RAM (antes esto provocaba MemoryError en PDF grandes).
    """
    import fitz  # PyMuPDF
    doc = fitz.open(src_path)
    try:
        for page in doc:
            yield _render_page(page, dpi)
    finally:
        doc.close()


_OCR_JPEG_QUALITY = 70  # calidad del JPEG embebido en el PDF buscable


def _compress_for_embed(img, grayscale: bool = False):
    """Recomprime la imagen a JPEG en memoria antes de embeberla.

    pytesseract embebe la imagen tal cual en el PDF: una página RGB sin comprimir
    pesa varios MB, y un libro entero acumularía varios GB en RAM (riesgo de
    MemoryError) y en disco. Pasar un JPEG reduce ~6× el peso sin afectar el OCR.
    Si `grayscale=True`, además convierte a blanco y negro: el PDF buscable pesa
    aún menos (útil para libros y documentos escaneados sin color relevante).
    """
    import io
    from PIL import Image
    if grayscale:
        img = img.convert("L")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=_OCR_JPEG_QUALITY)
    buf.seek(0)
    return Image.open(buf)


def _image_to_searchable_pdf_bytes(img, lang_code: str, grayscale: bool = False) -> bytes:
    """Devuelve un PDF de una página (imagen + capa OCR invisible) en bytes."""
    import pytesseract
    if TESSERACT_PATH:
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
    try:
        img = _compress_for_embed(img, grayscale=grayscale)
    except Exception:
        pass  # si falla la compresión, se embebe la imagen original
    try:
        return pytesseract.image_to_pdf_or_hocr(img, lang=lang_code, extension="pdf")
    except Exception:
        # Reintento con inglés si el paquete de idioma no está instalado
        return pytesseract.image_to_pdf_or_hocr(img, lang="eng", extension="pdf")


def convert_image_to_searchable_pdf(src_path: str, dst_path: str,
                                    lang: str = "Español",
                                    progress_cb: Optional[Callable] = None,
                                    grayscale: bool = False) -> None:
    """Convierte una imagen a un PDF buscable (imagen original + texto OCR oculto)."""
    if not is_available():
        raise RuntimeError(
            "Reconocimiento de texto no disponible.\n"
            "Colocá tesseract.exe en la carpeta bin/ del programa."
        )
    lang_code = _get_tesseract_lang(lang)
    from PIL import Image
    if progress_cb:
        progress_cb("🔍 OCR: generando PDF buscable...")

    pages = []
    with Image.open(src_path) as im:
        # Soporta imágenes multipágina (p. ej. TIFF de varios cuadros)
        n_frames = getattr(im, "n_frames", 1)
        for frame in range(n_frames):
            try:
                im.seek(frame)
            except Exception:
                pass
            pages.append(im.convert("RGB").copy())

    from motors.motor_pdf_tools import write_file_safely

    if len(pages) == 1:
        pdf_bytes = _image_to_searchable_pdf_bytes(pages[0], lang_code, grayscale=grayscale)

        def _escribir(ruta):
            with open(ruta, "wb") as f:
                f.write(pdf_bytes)

        write_file_safely(dst_path, _escribir, progress_cb)
        return

    # Varias páginas → unir con pypdf
    import io
    from pypdf import PdfWriter, PdfReader
    writer = PdfWriter()
    total = len(pages)
    for i, img in enumerate(pages):
        if progress_cb:
            progress_cb(f"🔍 OCR página {i+1}/{total} (PDF buscable)...")
        pdf_bytes = _image_to_searchable_pdf_bytes(img, lang_code, grayscale=grayscale)
        for page in PdfReader(io.BytesIO(pdf_bytes)).pages:
            writer.add_page(page)

    def _escribir_varias(ruta):
        with open(ruta, "wb") as f:
            writer.write(f)

    write_file_safely(dst_path, _escribir_varias, progress_cb)


def convert_pdf_to_searchable_pdf(src_path: str, dst_path: str,
                                  lang: str = "Español",
                                  progress_cb: Optional[Callable] = None,
                                  page_cb: Optional[Callable] = None,
                                  grayscale: bool = False) -> None:
    """Convierte un PDF escaneado a un PDF buscable conservando cada página.

    Cada página se renderiza tal cual y se le añade por debajo una capa de
    texto OCR invisible. El resultado se ve idéntico al original pero el texto
    es seleccionable y buscable (Ctrl+F).

    El procesamiento es en streaming (una página a la vez) para mantener el uso
    de memoria acotado y poder convertir libros completos sin MemoryError.
    `page_cb(actual, total)` se invoca por página para mover una barra numérica.
    """
    if not is_available():
        raise RuntimeError(
            "Reconocimiento de texto no disponible.\n"
            "Colocá tesseract.exe en la carpeta bin/ del programa."
        )
    lang_code = _get_tesseract_lang(lang)
    import gc
    import io
    from pypdf import PdfWriter, PdfReader

    total = _count_pdf_pages(src_path)
    if total == 0:
        if pdf_sin_terminar(src_path):
            raise RuntimeError(PDF_SIN_TERMINAR_MSG)
        raise RuntimeError("El PDF no tiene páginas que procesar.")

    writer = PdfWriter()
    for i, img in enumerate(_iter_pdf_pages(src_path)):
        if progress_cb:
            progress_cb(f"🔍 OCR página {i+1}/{total} (PDF buscable)...")
        try:
            pdf_bytes = _image_to_searchable_pdf_bytes(img, lang_code, grayscale=grayscale)
        finally:
            img.close()      # libera la imagen renderizada de inmediato
            del img
        for page in PdfReader(io.BytesIO(pdf_bytes)).pages:
            writer.add_page(page)
        del pdf_bytes
        if (i + 1) % 25 == 0:
            gc.collect()
        if page_cb:
            page_cb(i + 1, total)

    # El guardado va por write_file_safely: en un pendrive, escribir directo
    # sobre el nombre final dejaba un PDF a medio hacer que no abría.
    from motors.motor_pdf_tools import write_file_safely

    def _escribir(ruta):
        with open(ruta, "wb") as f:
            writer.write(f)

    if progress_cb:
        progress_cb("💾 Guardando el PDF buscable...")
    write_file_safely(dst_path, _escribir, progress_cb)


# ─────────────────────────────────────────────────────────────────────────────
# NORMALIZAR PÁGINAS — mismo tamaño de hoja y mismo tamaño de letra.
#
# Pensado para apuntes fotografiados: si algunas fotos se sacaron más cerca
# (letra grande) y otras más lejos (letra chica), esto detecta la altura
# típica de línea de texto de cada página por OCR, calcula una escala común
# (la mediana de todo el documento) y reconstruye cada página sobre una hoja
# A4 con ese mismo zoom. De paso, vuelve a incrustar la capa OCR para que el
# resultado siga siendo buscable.
# ─────────────────────────────────────────────────────────────────────────────

_NORM_RENDER_DPI = 200
_NORM_MIN_CONF = 40    # confianza mínima de Tesseract (0-100) para contar una palabra
_NORM_SCALE_MIN = 0.2
_NORM_SCALE_MAX = 5.0
_NORM_MARGIN_MM = 5.0  # margen en blanco que se deja de cada lado en la hoja A4
# Banda alrededor de la referencia "de cuerpo" global para decidir qué
# palabras de una página cuentan como texto de cuerpo (y no un título/negrita
# mucho más grande) al calibrar la escala de esa página en particular.
_NORM_BODY_BAND = (0.55, 1.8)


def _text_metrics_px(img, lang_code: str):
    """Alturas (px) de todas las palabras que Tesseract reconoce con
    confianza razonable en la imagen (lista cruda, sin resumir — incluye
    títulos, negrita, etc.), y el recuadro (left, top, right, bottom) que
    envuelve a todo el texto detectado (o None si no se detectó nada).

    El recuadro es clave para no confundir "tamaño de la foto" con "tamaño
    del contenido real": una foto puede tener mucho margen en blanco
    alrededor del texto, y ese margen se puede recortar libremente sin
    perder nada — lo que nunca hay que recortar es el recuadro del texto."""
    import pytesseract
    if TESSERACT_PATH:
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
    try:
        data = pytesseract.image_to_data(img, lang=lang_code,
                                         output_type=pytesseract.Output.DICT)
    except Exception:
        try:
            data = pytesseract.image_to_data(img, lang="eng",
                                             output_type=pytesseract.Output.DICT)
        except Exception:
            return [], None

    heights = []
    left = top = None
    right = bottom = None
    for x, y, w, h, conf, txt in zip(
            data.get("left", []), data.get("top", []),
            data.get("width", []), data.get("height", []),
            data.get("conf", []), data.get("text", [])):
        if not str(txt).strip():
            continue
        try:
            conf_val = float(conf)
        except (TypeError, ValueError):
            continue
        if conf_val < _NORM_MIN_CONF:
            continue
        if not h or h <= 3:
            continue
        heights.append(h)
        left = x if left is None else min(left, x)
        top = y if top is None else min(top, y)
        right = (x + w) if right is None else max(right, x + w)
        bottom = (y + h) if bottom is None else max(bottom, y + h)

    bbox = (left, top, right, bottom) if heights else None
    return heights, bbox


_NORM_SCAN_IMG_RATIO = 0.80   # una imagen que cubre esto o más de la hoja -> es un escaneo/foto


def _page_is_scan(page, ratio: float = _NORM_SCAN_IMG_RATIO) -> bool:
    """Heurística: ¿esta página es (probablemente) una foto/escaneo, en vez
    de texto digital maquetado? Se basa en si hay una imagen que ocupa casi
    toda la hoja — eso es cierto tanto si la página nunca pasó por OCR como
    si ya tiene una capa de texto invisible incrustada encima de la foto (en
    ambos casos `page.get_text()` puede devolver texto, así que mirar solo
    la cantidad de texto no alcanza para distinguir)."""
    area = page.rect.width * page.rect.height
    if area <= 0:
        return False
    for info in page.get_image_info():
        bbox = info.get("bbox")
        if not bbox:
            continue
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        if (w * h) / area >= ratio:
            return True
    return False


def normalize_pdf_pages(src_path: str, dst_path: str, lang: str = "Español",
                        progress_cb: Optional[Callable] = None) -> dict:
    """Empareja el tamaño de hoja (A4) entre todas las páginas de un PDF, y
    además empareja el tamaño de la letra de CUERPO solo en las páginas que
    son fotos/escaneos (p. ej. apuntes fotografiados a distinta distancia).
    Devuelve {"pages": n, "text_height_px": referencia de cuerpo usada, o
    None si no había páginas escaneadas que calibrar}.

    Las páginas de texto digital (un libro, un PDF exportado, etc.) NO se
    tocan más que para encajarlas en la hoja A4: reescalarlas por OCR no
    tiene sentido (ya tienen el tamaño de letra que su autor eligió) y,
    peor, si el algoritmo decidiera agrandarlas, el recorte para que entren
    en A4 termina cortando párrafos reales por los costados. Esas páginas se
    reincrustan tal cual, como vectores (sin rasterizar), preservando nitidez
    y el texto real/buscable original.

    Títulos, negrita, subtítulos, etc. en las páginas escaneadas: cada una se
    reescala como un todo con un único factor, así que un título que hoy es
    más grande que el cuerpo del texto sigue siéndolo después de normalizar.
    Para eso, al calibrar cada página se ignoran las palabras mucho más
    grandes que lo típico del documento (p. ej. un título ocupando casi toda
    una portada), para que esa página no la escale usando el título como si
    fuera el cuerpo.

    Nota técnica: el renderer PDF de Tesseract asume una resolución fija
    propia (no la real de la imagen que se le pasa), así que la página que
    genera NO mide físicamente lo que uno esperaría. Por eso cada página
    escaneada se arma primero como un mini-PDF de Tesseract (imagen + texto
    OCR) y después se reincrusta con `show_pdf_page` escalada a la hoja A4
    exacta: eso reescala imagen y texto invisible juntos, sin desalinearlos."""
    import statistics
    import fitz
    from PIL import Image

    if not is_available():
        raise RuntimeError(
            "Esta función necesita Tesseract OCR.\n"
            "Colocá tesseract.exe en la carpeta bin/ del programa.")

    lang_code = _get_tesseract_lang(lang)

    doc = fitz.open(src_path)
    try:
        n = doc.page_count
        if n == 0:
            raise RuntimeError("El PDF no tiene páginas.")

        images = [None] * n           # solo se llena para páginas escaneadas
        bboxes = [None] * n           # recuadro del contenido real (px)
        page_heights = [[] for _ in range(n)]
        is_scan = [False] * n

        for i, page in enumerate(doc):
            if progress_cb:
                progress_cb(f"📐 Analizando página {i + 1}/{n}...")
            if not _page_is_scan(page):
                continue   # texto digital: se deja intacta, no se mide letra
            is_scan[i] = True

            # Algunos PDF (p. ej. fotos pasadas a PDF con un conversor que
            # asigna un tamaño de hoja gigante) declaran páginas enormes
            # aunque la imagen real sea chica. Sin este límite, renderizar a
            # 200 DPI fijo puede generar una imagen de cientos de MP que deja
            # el OCR "trabado" durante varios minutos en esa sola página.
            eff_dpi = _pick_dpi(page, base_dpi=_NORM_RENDER_DPI)
            zoom = eff_dpi / 72.0
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
            mode = "RGBA" if pix.alpha else "RGB"
            img = Image.frombytes(mode, (pix.width, pix.height),
                                  pix.samples).convert("RGB")
            del pix
            images[i] = img
            page_heights[i], bboxes[i] = _text_metrics_px(img, lang_code)

        # Referencia global de "letra de cuerpo": mediana de todas las
        # palabras detectadas en las páginas ESCANEADAS (las de texto digital
        # no aportan ni consumen esta referencia). Como el cuerpo del texto
        # es mucho más abundante que los títulos, esta mediana global
        # representa bien el tamaño de cuerpo típico aunque alguna página
        # puntual sea casi todo título (p. ej. una portada fotografiada).
        pooled = [h for hs in page_heights for h in hs]
        target_height = None
        page_refs = [None] * n
        if pooled:
            global_ref = statistics.median(pooled)
            band_low, band_high = _NORM_BODY_BAND
            # Por página: calibrar con las palabras "de cuerpo" (cercanas a
            # la referencia global), ignorando títulos/negrita mucho más
            # grandes que esta página pudiera tener. Si una página escaneada
            # no tiene ninguna palabra de tamaño "de cuerpo" (p. ej. es
            # enteramente una portada con un título gigante y nada más), no
            # hay forma confiable de calibrarla — se deja sin reescalar
            # (None → escala 1.0 más abajo) en vez de achicar el título al
            # tamaño del cuerpo de las demás páginas.
            for i, hs in enumerate(page_heights):
                if not is_scan[i]:
                    continue
                body_like = [h for h in hs
                            if band_low * global_ref <= h <= band_high * global_ref]
                page_refs[i] = statistics.median(body_like) if body_like else None
            valid_refs = [r for r in page_refs if r]
            target_height = statistics.median(valid_refs) if valid_refs else None
        elif any(is_scan):
            raise RuntimeError(
                "No se detectó texto confiable en ninguna página escaneada: "
                "no se puede calcular una escala común.")

        a4_w_pt, a4_h_pt = fitz.paper_size("a4")
        target_w_px = int(a4_w_pt * _NORM_RENDER_DPI / 72.0)
        target_h_px = int(a4_h_pt * _NORM_RENDER_DPI / 72.0)
        a4_rect = fitz.Rect(0, 0, a4_w_pt, a4_h_pt)

        # Margen en blanco de cada lado: el contenido se ajusta a esta área
        # "útil" (más chica que la hoja completa), y al centrarlo en la hoja
        # el margen queda parejo en los cuatro bordes.
        margin_px = round(_NORM_MARGIN_MM / 25.4 * _NORM_RENDER_DPI)
        usable_w_px = max(1, target_w_px - 2 * margin_px)
        usable_h_px = max(1, target_h_px - 2 * margin_px)

        out_doc = fitz.open()
        for i in range(n):
            if progress_cb:
                progress_cb(f"📐 Normalizando página {i + 1}/{n}...")

            if not is_scan[i]:
                # Texto digital: se reincrusta tal cual (vector, sin
                # rasterizar) solo reencuadrado a la hoja A4.
                new_page = out_doc.new_page(width=a4_w_pt, height=a4_h_pt)
                new_page.show_pdf_page(a4_rect, doc, i)
                continue

            img = images[i]
            h = page_refs[i]
            bbox = bboxes[i]
            scale = (target_height / h) if (h and target_height) else 1.0
            scale = max(_NORM_SCALE_MIN, min(scale, _NORM_SCALE_MAX))

            # Encoger, NUNCA recortar contenido real: en vez de mirar el
            # tamaño de toda la foto (que puede tener mucho margen en blanco
            # alrededor, sobre todo si la hoja no llena el encuadre), se mira
            # el recuadro real donde está el texto. Si agrandar para igualar
            # la letra hiciera que ESE recuadro no entre en la hoja A4
            # (páginas fotografiadas con márgenes angostos, como un libro),
            # se reduce lo justo y necesario para que el texto quepa
            # completo — el margen sobrante sí se puede recortar sin perder
            # nada. Perder texto real cortándolo por los costados es mucho
            # peor que dejar la letra un poco más chica de lo ideal.
            if bbox:
                content_w = (bbox[2] - bbox[0]) or 1
                content_h = (bbox[3] - bbox[1]) or 1
            else:
                content_w, content_h = img.width, img.height
            fit_scale = min(usable_w_px / (content_w * scale),
                            usable_h_px / (content_h * scale), 1.0)
            scale *= fit_scale

            new_w = max(1, round(img.width * scale))
            new_h = max(1, round(img.height * scale))
            if (new_w, new_h) != img.size:
                img = img.resize((new_w, new_h), Image.LANCZOS)

            # Recorte/pegado centrado en el CONTENIDO (no en el centro
            # geométrico de la foto), para no cortar texto de un lado
            # mientras sobra margen del otro.
            if bbox:
                cx = (bbox[0] + bbox[2]) / 2 * scale
                cy = (bbox[1] + bbox[3]) / 2 * scale
            else:
                cx, cy = img.width / 2, img.height / 2

            crop_w = min(usable_w_px, img.width)
            crop_h = min(usable_h_px, img.height)
            crop_x = int(round(cx - crop_w / 2))
            crop_y = int(round(cy - crop_h / 2))
            crop_x = max(0, min(crop_x, img.width - crop_w))
            crop_y = max(0, min(crop_y, img.height - crop_h))
            cropped = img.crop((crop_x, crop_y, crop_x + crop_w, crop_y + crop_h))

            canvas = Image.new("RGB", (target_w_px, target_h_px), "white")
            paste_x = max(0, (target_w_px - cropped.width) // 2)
            paste_y = max(0, (target_h_px - cropped.height) // 2)
            canvas.paste(cropped, (paste_x, paste_y))

            pdf_bytes = _image_to_searchable_pdf_bytes(canvas, lang_code)
            page_doc = fitz.open("pdf", pdf_bytes)
            try:
                new_page = out_doc.new_page(width=a4_w_pt, height=a4_h_pt)
                new_page.show_pdf_page(a4_rect, page_doc, 0)
            finally:
                page_doc.close()

        out_doc.save(dst_path, garbage=3, deflate=True)
        out_doc.close()
    finally:
        doc.close()

    return {
        "pages": n,
        "text_height_px": round(target_height, 1) if target_height else None,
    }


from core.graph import BaseMotor


class OcrMotor(BaseMotor):
    NAME = "OCR (Tesseract)"
    # El OCR se invoca por la vía directa `use_ocr` del worker, no a través
    # del grafo. Estas aristas se declaran como CONVERSIONS (no EDGES) para que
    # graph.register() pueda iterarlas sin romperse cuando Tesseract está
    # instalado. La matriz de compatibilidad decide cuáles se registran.
    CONVERSIONS = [
        ("jpg",  "txt"), ("jpeg", "txt"), ("png",  "txt"),
        ("tiff", "txt"), ("tif",  "txt"), ("bmp",  "txt"),
        ("webp", "txt"),
    ]

    @classmethod
    def is_available(cls) -> bool:
        return is_available()

    def convert(self, src_path: str, dst_path: str,
                src_ext: str, dst_ext: str,
                progress_cb=None, ocr_language: str = "Español", **kwargs) -> None:
        convert_image_to_text(src_path, dst_path, ocr_language, progress_cb)
