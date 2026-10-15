"""
motor_pdf_tools.py — Herramientas de edición de PDF (estilo iLovePDF, offline).

Funciones:
  - apply_page_ops : reordenar / eliminar / rotar páginas
  - compress_pdf   : comprimir (3 niveles, recomprime imágenes embebidas)
  - protect_pdf    : proteger con contraseña (AES-256)
  - unlock_pdf     : quitar la contraseña (conociéndola)
  - repair_pdf     : reparar PDF dañado (reescritura limpia)
  - render_thumbnails : miniaturas de páginas para la UI
  - merge_files    : unir varios PDF en uno solo, en el orden dado
  - find_duplicate_pages : detectar páginas con el mismo contenido (texto/OCR)
  - desdoblar_hojas_dobles : separar hojas apaisadas de dos carillas en A4
"""
import io
import os
import re
from itertools import combinations
from typing import Callable, Dict, List, Optional, Tuple



# ─────────────────────────────────────────────────────────────────────────────
# Guardado seguro
#
# Dos problemas reales, medidos el 1-sep-2026 con un documento escaneado de 43 MB / 133
# páginas guardado en un pendrive Kingston de 2 GB formateado en FAT:
#
# 1. MuPDF escribiendo directo sobre la unidad extraíble tardó 297,7 s (5 min).
#    El MISMO guardado en el disco interno tarda 0,1 s, y copiar el resultado
#    ya terminado al pendrive, 7,7 s. MuPDF escribe con muchos saltos y
#    reescrituras, y eso en FAT sobre USB es carísimo. Total: 5 min → 8 s.
# 2. Como se escribía directo sobre el nombre definitivo, durante todo ese rato
#    quedaba un PDF a medio escribir con el nombre final. Al abrirlo, no abría
#    ("no se puede abrir el archivo"), y no había forma de saber si ya estaba.
#
# Por eso: se arma en el disco local, se copia informando el avance y recién al
# final el archivo aparece con su nombre definitivo (os.replace es atómico).
# ─────────────────────────────────────────────────────────────────────────────

_COPY_CHUNK = 4 * 1024 * 1024   # 4 MB por bloque al copiar al destino

# ── Límites por defecto al partir PDF ────────────────────────────────────────────
PDF_MAX_MB_DEFECTO = 10.0    # límite habitual de correos y portales
POR_TANDA_DEFECTO  = 5       # archivos que muchos portales dejan subir por vez


def _drive_of(path: str) -> str:
    return os.path.splitdrive(os.path.abspath(path))[0].lower()


def _staging_dir_for(dst_path: str) -> Optional[str]:
    """Carpeta de trabajo en OTRA unidad que la del destino, o None si no hay.

    Devolver None significa "el destino ya está en un disco rápido (o no hay
    alternativa)": ahí se escribe en el mismo directorio con nombre temporal.
    """
    import tempfile
    dst_drive = _drive_of(dst_path)
    candidates = []
    try:
        from core.paths import TEMP_DIR
        candidates.append(TEMP_DIR)
    except Exception:
        pass
    candidates.append(tempfile.gettempdir())
    for cand in candidates:
        if not cand:
            continue
        try:
            if _drive_of(cand) != dst_drive:
                os.makedirs(cand, exist_ok=True)
                return cand
        except Exception:
            continue
    return None


def _copy_with_progress(src: str, dst: str,
                        progress_cb: Optional[Callable] = None,
                        pct_cb: Optional[Callable] = None) -> None:
    """Copia mostrando el avance (el destino puede ser lento: USB, red)."""
    import time
    total = os.path.getsize(src)
    done = 0
    last = 0.0
    with open(src, "rb") as fi, open(dst, "wb") as fo:
        while True:
            chunk = fi.read(_COPY_CHUNK)
            if not chunk:
                break
            fo.write(chunk)
            done += len(chunk)
            pct = int(done * 100 / total) if total else 100
            if pct_cb:
                pct_cb(pct)
            now = time.time()
            if progress_cb and (now - last > 0.5 or done >= total):
                last = now
                progress_cb(f"💾 Guardando en el destino... {pct}% "
                            f"({done / 1e6:.0f} de {total / 1e6:.0f} MB)")
        fo.flush()
        os.fsync(fo.fileno())


def write_file_safely(dst_path: str, write_fn: Callable[[str], None],
                      progress_cb: Optional[Callable] = None,
                      pct_cb: Optional[Callable] = None) -> None:
    """Escribe un archivo con `write_fn(ruta)` sin dejar nunca a la vista uno a
    medio escribir, y sin escribir directo sobre una unidad lenta.

    `write_fn` recibe la ruta donde debe generar el archivo."""
    dst_path = os.path.abspath(dst_path)
    dst_dir = os.path.dirname(dst_path) or "."
    os.makedirs(dst_dir, exist_ok=True)

    staging = _staging_dir_for(dst_path)
    part = dst_path + ".part"
    staged = None
    try:
        if staging:
            import tempfile
            fd, staged = tempfile.mkstemp(suffix=".pdf", dir=staging)
            os.close(fd)
            if progress_cb:
                progress_cb("💾 Armando el archivo...")
            write_fn(staged)
            _copy_with_progress(staged, part, progress_cb, pct_cb)
        else:
            if progress_cb:
                progress_cb("💾 Guardando el archivo...")
            write_fn(part)
            if pct_cb:
                pct_cb(100)
        os.replace(part, dst_path)     # atómico: recién acá aparece el nombre final
    except BaseException:
        for leftover in (part,):
            try:
                if os.path.exists(leftover):
                    os.remove(leftover)
            except Exception:
                pass
        raise
    finally:
        if staged:
            try:
                os.remove(staged)
            except Exception:
                pass


def save_doc_safely(doc, dst_path: str,
                    progress_cb: Optional[Callable] = None,
                    pct_cb: Optional[Callable] = None,
                    **save_kw) -> None:
    """Guarda un documento MuPDF con las mismas garantías que
    `write_file_safely` (nada de archivos a medio escribir con el nombre
    final, y nada de hacer que MuPDF escriba directo sobre un pendrive)."""
    write_file_safely(dst_path, lambda ruta: doc.save(ruta, **save_kw),
                      progress_cb, pct_cb)


# ─────────────────────────────────────────────────────────────────────────────
# Organizar páginas
# ─────────────────────────────────────────────────────────────────────────────

def apply_page_ops(src_path: str, dst_path: str,
                   order: List[int],
                   rotations: Optional[Dict[int, int]] = None,
                   progress_cb: Optional[Callable] = None,
                   pct_cb: Optional[Callable] = None) -> None:
    """Reescribe el PDF con las páginas en `order` (índices originales, base 0;
    las páginas que no aparecen quedan eliminadas) y aplica `rotations`
    (grados extra por índice original: 90/180/270)."""
    import fitz
    if not order:
        raise RuntimeError("No quedaron páginas: no se puede guardar un PDF vacío.")

    doc = fitz.open(src_path)
    try:
        n = doc.page_count
        bad = [i for i in order if i < 0 or i >= n]
        if bad:
            raise RuntimeError(f"Índices de página inválidos: {bad}")

        # Rotar primero (sobre índices originales), luego seleccionar/ordenar
        for idx, extra in (rotations or {}).items():
            if 0 <= idx < n and extra % 360:
                page = doc[idx]
                page.set_rotation((page.rotation + extra) % 360)

        if progress_cb:
            progress_cb(f"📄 Reordenando {len(order)} de {n} páginas...")
        doc.select(order)
        save_doc_safely(doc, dst_path, progress_cb, pct_cb,
                        garbage=3, deflate=True)
    finally:
        doc.close()


# ─────────────────────────────────────────────────────────────────────────────
# Comprimir
# ─────────────────────────────────────────────────────────────────────────────

# nivel → (lado máx de imagen en px, calidad JPEG)
_COMPRESS_LEVELS = {
    "light":  (2400, 80),
    "medium": (1600, 65),
    "strong": (1100, 45),
}


def compress_pdf(src_path: str, dst_path: str, level: str = "medium",
                 progress_cb: Optional[Callable] = None,
                 pct_cb: Optional[Callable] = None) -> dict:
    """Comprime un PDF recomprimiendo las imágenes embebidas (JPEG) y
    reescribiendo el archivo con limpieza estructural.

    Devuelve {"before": bytes, "after": bytes, "images": n_recomprimidas}.
    """
    import fitz
    from PIL import Image

    max_edge, quality = _COMPRESS_LEVELS.get(level, _COMPRESS_LEVELS["medium"])
    before = os.path.getsize(src_path)

    doc = fitz.open(src_path)
    n_images = 0
    try:
        seen_xrefs = set()
        total = doc.page_count
        for pno, page in enumerate(doc):
            if progress_cb and pno % 10 == 0:
                progress_cb(f"🗜 Comprimiendo página {pno+1}/{total}...")
            for img_info in page.get_images(full=True):
                xref = img_info[0]
                if xref in seen_xrefs:
                    continue
                seen_xrefs.add(xref)
                try:
                    extracted = doc.extract_image(xref)
                    raw = extracted["image"]
                    if len(raw) < 30_000:      # imágenes chicas: no vale la pena
                        continue
                    img = Image.open(io.BytesIO(raw))
                    if img.mode in ("RGBA", "LA", "P"):
                        img = img.convert("RGB")
                    elif img.mode not in ("RGB", "L"):
                        img = img.convert("RGB")
                    # Reducir tamaño si supera el tope del nivel
                    w, h = img.size
                    scale = max_edge / max(w, h)
                    if scale < 1.0:
                        img = img.resize((max(1, round(w*scale)),
                                          max(1, round(h*scale))),
                                         Image.LANCZOS)
                    buf = io.BytesIO()
                    img.save(buf, format="JPEG", quality=quality, optimize=True)
                    new_bytes = buf.getvalue()
                    if len(new_bytes) < len(raw) * 0.9:   # solo si achica >10%
                        page.replace_image(xref, stream=new_bytes)
                        n_images += 1
                except Exception:
                    continue  # una imagen problemática no aborta el resto

        if progress_cb:
            progress_cb("🗜 Reescribiendo estructura del PDF...")
        save_doc_safely(doc, dst_path, progress_cb, pct_cb,
                        garbage=4, deflate=True, clean=True)
    finally:
        doc.close()

    after = os.path.getsize(dst_path)
    # Si "comprimido" quedó más grande (PDF ya óptimo), copiar el original
    if after >= before:
        import shutil
        shutil.copyfile(src_path, dst_path)
        after = before
    return {"before": before, "after": after, "images": n_images}


# ─────────────────────────────────────────────────────────────────────────────
# Proteger / desbloquear
# ─────────────────────────────────────────────────────────────────────────────

def protect_pdf(src_path: str, dst_path: str, password: str,
                progress_cb: Optional[Callable] = None) -> None:
    """Protege el PDF con contraseña (AES-256 si pypdf lo soporta)."""
    from pypdf import PdfReader, PdfWriter
    if not password:
        raise RuntimeError("La contraseña no puede estar vacía.")
    if progress_cb:
        progress_cb("🔒 Cifrando PDF...")
    reader = PdfReader(src_path)
    writer = PdfWriter()
    writer.append(reader)
    try:
        writer.encrypt(user_password=password, algorithm="AES-256")
    except Exception:
        writer.encrypt(user_password=password)   # fallback RC4/AES-128
    with open(dst_path, "wb") as f:
        writer.write(f)


def unlock_pdf(src_path: str, dst_path: str, password: str,
               progress_cb: Optional[Callable] = None) -> None:
    """Quita la contraseña de un PDF (hay que conocerla)."""
    from pypdf import PdfReader, PdfWriter
    reader = PdfReader(src_path)
    if reader.is_encrypted:
        result = reader.decrypt(password or "")
        if not result:
            raise RuntimeError("Contraseña incorrecta.")
    if progress_cb:
        progress_cb("🔓 Quitando cifrado...")
    writer = PdfWriter()
    writer.append(reader)
    with open(dst_path, "wb") as f:
        writer.write(f)


# ─────────────────────────────────────────────────────────────────────────────
# Reparar
# ─────────────────────────────────────────────────────────────────────────────

def repair_pdf(src_path: str, dst_path: str,
               progress_cb: Optional[Callable] = None,
               pct_cb: Optional[Callable] = None) -> int:
    """Intenta reparar un PDF dañado reescribiéndolo limpio con MuPDF
    (que tolera estructuras rotas). Devuelve la cantidad de páginas
    recuperadas."""
    import fitz
    if progress_cb:
        progress_cb("🩹 Analizando y reescribiendo el PDF...")
    try:
        doc = fitz.open(src_path)
    except Exception as e:
        raise RuntimeError(
            f"El archivo está demasiado dañado para recuperarlo: {e}"
        ) from e
    try:
        n = doc.page_count
        if n == 0:
            raise RuntimeError("No se pudo recuperar ninguna página.")
        save_doc_safely(doc, dst_path, progress_cb, pct_cb,
                        garbage=4, deflate=True, clean=True)
        return n
    finally:
        doc.close()


# ─────────────────────────────────────────────────────────────────────────────
# Miniaturas para la UI
# ─────────────────────────────────────────────────────────────────────────────

def render_thumbnails(src_path: str, max_edge: int = 220):
    """Generador: rinde (índice, ancho, alto, bytes PNG) por página.
    Pensado para poblar la grilla de miniaturas sin cargar todo en RAM."""
    import fitz
    doc = fitz.open(src_path)
    try:
        for i, page in enumerate(doc):
            rect = page.rect
            scale = max_edge / max(rect.width, rect.height, 1)
            pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale))
            yield i, pix.width, pix.height, pix.tobytes("png")
            del pix
    finally:
        doc.close()


def renglones_de_pagina(page) -> List[str]:
    """Texto de una página de PyMuPDF armado por renglones como se ven en la
    hoja: junta en un mismo renglón todo lo que está a la misma altura, de
    izquierda a derecha, y deja una línea en blanco entre párrafos.

    `get_text("text")` sigue el orden interno del PDF, no lo que se ve: los
    PDF de muchos generadores escriben cada palabra como un objeto
    suelto, y el .txt salía con una palabra por renglón (7 letras de promedio
    en un despacho de 3 hojas). El texto dibujado fuera de la hoja se descarta
    (ver «repetición entre hojas»); el que va en vertical (sellos del margen)
    se agrega al final de la página, en renglones propios."""
    hoja = page.rect
    trozos = []          # (x0, y0, x1, y1, texto) de cada tramo horizontal
    verticales = []
    for bloque in page.get_text("dict").get("blocks", []):
        if bloque.get("type") != 0:
            continue
        for linea in bloque.get("lines", []):
            x0, y0, x1, y1 = linea.get("bbox") or (0, 0, 0, 0)
            if y0 >= hoja.y1 or y1 <= hoja.y0 or x0 >= hoja.x1 or x1 <= hoja.x0:
                continue
            dx, dy = linea.get("dir") or (1, 0)
            if abs(dy) > 0.2 or dx < 0:
                txt = "".join(s.get("text", "") for s in linea.get("spans", []))
                txt = re.sub(r"\s+", " ", txt).strip()
                if txt:
                    verticales.append(txt)
                continue
            for span in linea.get("spans", []):
                txt = span.get("text", "")
                if txt.strip():
                    trozos.append((*span["bbox"], txt))
    if not trozos:
        return verticales

    # Agrupar por altura: un tramo va al renglón cuyo centro vertical cae
    # dentro de la mitad de su alto.
    trozos.sort(key=lambda t: ((t[1] + t[3]) / 2, t[0]))
    renglones = []       # [centro_y, alto, [trozos]]
    for t in trozos:
        cy, alto = (t[1] + t[3]) / 2, max(t[3] - t[1], 1.0)
        if renglones:
            r = renglones[-1]
            if abs(cy - r[0]) <= min(alto, r[1]) * 0.5:
                r[2].append(t)
                continue
        renglones.append([cy, alto, [t]])

    # Interlineado típico de la página (los escritos suelen ir a doble
    # espacio): un párrafo nuevo es un salto bastante mayor que ése.
    saltos = sorted(b[0] - a[0] for a, b in zip(renglones, renglones[1:]))
    interlineado = saltos[len(saltos) // 2] if saltos else 0.0
    salida: List[str] = []
    previo = None
    for cy, alto, ts in renglones:
        ts.sort(key=lambda t: t[0])
        texto = ""
        fin = None
        for x0, _, x1, _, txt in ts:
            if texto and not texto.endswith(" ") and not txt.startswith(" ") \
                    and x0 - fin > alto * 0.15:
                texto += " "
            texto += txt
            fin = x1
        texto = re.sub(r"[ \t]+", " ", texto).strip()
        if not texto:
            continue
        # Hueco vertical grande = cambio de párrafo
        if previo is not None and interlineado and cy - previo > interlineado * 1.6:
            salida.append("")
        salida.append(texto)
        previo = cy
    return salida + verticales


def render_page(src_path: str, page: int = 0, max_edge: int = 420):
    """PNG de UNA página: (bytes, ancho_px, alto_px, ancho_pt, alto_pt).

    `render_thumbnails` recorre todo el documento; para la vista previa de la
    firma sólo hace falta una página, y el PDF puede tener cientos.
    """
    import fitz
    doc = fitz.open(src_path)
    try:
        page = max(0, min(page, doc.page_count - 1))
        pagina = doc[page]
        rect = pagina.rect
        escala = max_edge / max(rect.width, rect.height, 1)
        pix = pagina.get_pixmap(matrix=fitz.Matrix(escala, escala))
        return (pix.tobytes("png"), pix.width, pix.height,
                rect.width, rect.height)
    finally:
        doc.close()


def page_count(src_path: str) -> int:
    import fitz
    doc = fitz.open(src_path)
    try:
        return doc.page_count
    finally:
        doc.close()


# ─────────────────────────────────────────────────────────────────────────────
# Páginas duplicadas
# ─────────────────────────────────────────────────────────────────────────────

def _normalize_words(text: str) -> set:
    return set(re.findall(r"\w+", text.lower()))


# Huella visual: diferencia de brillo entre vecinos en una grilla de 33×32.
# Dos páginas distintas de un mismo libro se parecen mucho vistas en chico
# (mismos márgenes, renglones parejos): por eso el tope es estricto.
_HUELLA_COLS, _HUELLA_FILAS = 33, 32
_HUELLA_MAX_DIF = 0.05     # fracción de bits distintos para darlas por iguales


def _huella_visual(page) -> Optional[int]:
    """Entero de 1024 bits que resume cómo se ve la página (dHash)."""
    import fitz
    from PIL import Image
    try:
        pix = page.get_pixmap(dpi=24, colorspace=fitz.csGRAY)
        im = Image.frombytes("L", (pix.width, pix.height), pix.samples)
        im = im.resize((_HUELLA_COLS, _HUELLA_FILAS), Image.BILINEAR)
        px = list(im.getdata())
    except Exception:
        return None
    bits = 0
    for f in range(_HUELLA_FILAS):
        fila = px[f * _HUELLA_COLS:(f + 1) * _HUELLA_COLS]
        for c in range(_HUELLA_COLS - 1):
            bits = (bits << 1) | (fila[c] > fila[c + 1])
    return bits


def _firma_imagenes(doc, page) -> Optional[tuple]:
    """Qué imágenes muestra la página y dónde: dos páginas con la misma firma
    se ven exactamente iguales.

    No alcanza con que usen la misma imagen: una hoja doble escaneada se
    puede partir mostrando la misma foto corrida (la página 49 de un libro
    real era la mitad izquierda y la 50 la derecha, de una misma imagen).
    Por eso cuenta también la ubicación de la imagen en la hoja y el giro."""
    firmas = []
    for info in page.get_image_info(hashes=True):
        digest = info.get("digest")
        if not digest:
            continue
        caja = tuple(round(v / 2) for v in info.get("bbox", ()))
        firmas.append((bytes(digest).hex(), caja))
    if not firmas:
        return None
    return (page.rotation, tuple(sorted(firmas)))


def find_duplicate_pages(src_path: str, threshold: float = 0.8,
                         progress_cb: Optional[Callable] = None,
                         pct_cb: Optional[Callable] = None,
                         ) -> List[Tuple[int, int, float, str]]:
    """Busca páginas repetidas. Devuelve (pág_a, pág_b, similitud 0-1,
    motivo), índices base 0. Tres formas de darse cuenta, de más a menos
    segura:

    - "misma imagen": las dos muestran exactamente la misma foto (un PDF
      armado repitiendo la hoja escaneada). Similitud 1.
    - "texto": mismo texto (hoja fotografiada dos veces, distinto encuadre).
    - "imagen parecida": páginas sin texto (escaneos) que se ven iguales.

    Antes sólo se miraba el texto: en un libro escaneado (fotos sin capa de
    texto) ninguna página era comparable y decía que no había duplicados,
    aunque todas estuvieran repetidas."""
    import fitz
    doc = fitz.open(src_path)
    try:
        n = doc.page_count
        word_sets, firmas, huellas = [], [], []
        for i in range(n):
            if progress_cb and (i % 5 == 0 or i == n - 1):
                progress_cb(f"🔍 Revisando página {i + 1}/{n}...")
            page = doc[i]
            word_sets.append(_normalize_words(page.get_text()))
            firmas.append(_firma_imagenes(doc, page))
            # La huella visual sólo hace falta en páginas sin texto
            huellas.append(_huella_visual(page)
                           if len(word_sets[-1]) < 5 else None)
            if pct_cb:
                pct_cb(int((i + 1) * 100 / n))

        bits = (_HUELLA_COLS - 1) * _HUELLA_FILAS
        pairs = []
        for i, j in combinations(range(n), 2):
            if firmas[i] and firmas[i] == firmas[j]:
                pairs.append((i, j, 1.0, "misma imagen"))
                continue
            a, b = word_sets[i], word_sets[j]
            if len(a) >= 5 and len(b) >= 5:
                sim = len(a & b) / len(a | b)
                if sim >= threshold:
                    pairs.append((i, j, sim, "texto"))
                continue
            if huellas[i] is not None and huellas[j] is not None:
                dif = bin(huellas[i] ^ huellas[j]).count("1") / bits
                if dif <= _HUELLA_MAX_DIF:
                    pairs.append((i, j, 1 - dif, "imagen parecida"))
        return pairs
    finally:
        doc.close()


def find_duplicate_files(paths: List[str], threshold: float = 0.8,
                         progress_cb: Optional[Callable] = None,
                         ) -> List[Tuple[int, int, float]]:
    """Como find_duplicate_pages pero comparando archivos completos entre sí
    (todas sus páginas juntas). Pensado para la lista de "Unir archivos":
    detecta si dos PDF de la lista son la misma hoja fotografiada dos veces.
    Devuelve ternas (índice_a, índice_b, similitud), índices sobre `paths`."""
    import fitz
    word_sets = []
    for i, path in enumerate(paths):
        if progress_cb:
            progress_cb(f"🔍 Leyendo texto de {i + 1}/{len(paths)}: "
                       f"{os.path.basename(path)}...")
        try:
            with fitz.open(path) as doc:
                text = "\n".join(page.get_text() for page in doc)
        except Exception:
            text = ""
        word_sets.append(_normalize_words(text))

    pairs = []
    for i, j in combinations(range(len(paths)), 2):
        a, b = word_sets[i], word_sets[j]
        if len(a) < 5 or len(b) < 5:
            continue
        union = len(a | b)
        if union == 0:
            continue
        sim = len(a & b) / union
        if sim >= threshold:
            pairs.append((i, j, sim))
    return pairs


# ─────────────────────────────────────────────────────────────────────────────
# Unir archivos
# ─────────────────────────────────────────────────────────────────────────────

def merge_files(src_paths: List[str], dst_path: str,
                progress_cb: Optional[Callable] = None,
                pct_cb: Optional[Callable] = None) -> dict:
    """Une varios PDF (en el orden dado) en un solo archivo `dst_path`.
    Devuelve {"pages": total_páginas}."""
    import fitz
    if not src_paths:
        raise RuntimeError("No hay archivos para unir.")

    out = fitz.open()
    try:
        for i, path in enumerate(src_paths, start=1):
            if progress_cb:
                progress_cb(f"📄 Agregando {i}/{len(src_paths)}: "
                           f"{os.path.basename(path)}")
            with fitz.open(path) as doc:
                out.insert_pdf(doc)
        if progress_cb:
            progress_cb(f"💾 Guardando {out.page_count} páginas...")
        save_doc_safely(out, dst_path, progress_cb, pct_cb,
                        garbage=3, deflate=True)
        return {"pages": out.page_count}
    finally:
        out.close()


# ─────────────────────────────────────────────────────────────────────────────
# Partir un PDF
#
# Hasta ahora partir sólo existía pegado a "unir una carpeta", metido dentro
# del panel. Acá vive como operación propia y reutilizable: sirve para un PDF
# suelto y no depende de la interfaz.
# ─────────────────────────────────────────────────────────────────────────────

# Cuando la estimación llega a este % del límite, se mide el tamaño real.
# Medir es caro (hay que escribir el PDF en memoria), estimar es gratis pero
# impreciso: el umbral es el punto medio.
_SPLIT_CHECK_THRESHOLD = 0.85


def _split_out_dir(src_path: str, out_dir: str = "") -> str:
    if not out_dir:
        base = os.path.splitext(os.path.basename(src_path))[0]
        out_dir = os.path.join(os.path.dirname(src_path), f"{base}_partido")
    os.makedirs(out_dir, exist_ok=True)
    return out_dir


def split_pdf_by_size(src_path: str, out_dir: str = "", max_mb: float = PDF_MAX_MB_DEFECTO,
                      prefix: str = "parte",
                      progress_cb: Optional[Callable] = None) -> Dict:
    """Parte un PDF en archivos que no superen `max_mb` megabytes.

    Va acumulando páginas y, cuando la estimación se acerca al límite, mide
    el tamaño real. Si una sola página ya excede el límite, la guarda igual
    y avisa: es preferible a quedarse en un bucle infinito.
    """
    from pypdf import PdfReader, PdfWriter

    out_dir = _split_out_dir(src_path, out_dir)
    max_bytes = int(max_mb * 1024 * 1024)
    if max_bytes <= 0:
        raise RuntimeError("El tamaño máximo por parte tiene que ser mayor a 0.")

    lector = PdfReader(src_path)
    total_paginas = len(lector.pages)
    if total_paginas == 0:
        raise RuntimeError("El PDF no tiene páginas.")

    try:
        bytes_por_pagina = os.path.getsize(src_path) / total_paginas
    except OSError:
        bytes_por_pagina = 200_000

    generados: List[str] = []
    avisos: List[str] = []

    def guardar(paginas) -> None:
        escritor = PdfWriter()
        for p in paginas:
            escritor.add_page(p)
        nombre = f"{prefix}_{len(generados) + 1}.pdf"
        destino = os.path.join(out_dir, nombre)
        escritor.write(destino)
        generados.append(destino)
        if progress_cb:
            mb = os.path.getsize(destino) / 1048576
            progress_cb(f"✂️ Guardado {nombre} ({mb:.1f} MB)")

    def tamano_real(paginas) -> int:
        buf = io.BytesIO()
        escritor = PdfWriter()
        for p in paginas:
            escritor.add_page(p)
        escritor.write(buf)
        return buf.tell()

    pendientes = []
    estimado = 0.0
    for i, pagina in enumerate(lector.pages, start=1):
        if progress_cb and i % 10 == 0:
            progress_cb(f"✂️ Analizando página {i}/{total_paginas}...")
        pendientes.append(pagina)
        estimado += bytes_por_pagina

        if estimado > max_bytes * _SPLIT_CHECK_THRESHOLD:
            real = tamano_real(pendientes)
            if real > max_bytes:
                if len(pendientes) > 1:
                    guardar(pendientes[:-1])
                    pendientes = [pendientes[-1]]
                    estimado = bytes_por_pagina
                else:
                    avisos.append(
                        f"La página {i} sola ya supera {max_mb} MB; se guardó "
                        "igual en su propia parte.")
                    guardar(pendientes)
                    pendientes = []
                    estimado = 0.0
            else:
                estimado = real

    if pendientes:
        guardar(pendientes)

    return {"split": True, "archivos": generados, "partes": len(generados),
            "paginas": total_paginas, "carpeta": out_dir, "avisos": avisos}


# ─────────────────────────────────────────────────────────────────────────────
# Preparar una carpeta de PDFs para subir a un portal con límite de tamaño
#
# El caso real: 30 PDF sueltos que hay que subir de a 5, y ninguno puede pasar
# de 10 MB. Hacerlo a mano es tedioso y es fácil copiar uno de más o saltearse
# otro. Acá se elige la carpeta y el programa deja todo listo: parte los que se
# pasan del límite y arma las tandas de 5.
# ─────────────────────────────────────────────────────────────────────────────

def preparar_pdfs_por_tamano(archivos: List[str], destino: str = "",
                            max_mb: float = PDF_MAX_MB_DEFECTO,
                            por_tanda: int = POR_TANDA_DEFECTO,
                            progress_cb: Optional[Callable] = None) -> Dict:
    """Deja una lista de PDF lista para cargar a un portal con límite de tamaño.

    Cada archivo que supera `max_mb` se parte en partes que sí entran; los que
    ya entran se copian tal cual. Después se reparte todo en tandas de
    `por_tanda` archivos.

    Los originales no se tocan: se trabaja sobre copias.
    """
    import shutil
    import tempfile
    from core.paths import TEMP_DIR
    from core.salidas import (preparar_destino, repartir_en_tandas,
                              cantidad_de_tandas)

    pdfs = [a for a in (archivos or [])
            if a and os.path.isfile(a) and a.lower().endswith(".pdf")]
    if not pdfs:
        raise RuntimeError("No hay archivos PDF para preparar.")
    if max_mb <= 0:
        raise RuntimeError("El tamaño máximo por archivo tiene que ser mayor a 0.")

    destino = preparar_destino(pdfs, destino)
    limite_bytes = int(max_mb * 1024 * 1024)

    os.makedirs(str(TEMP_DIR), exist_ok=True)
    staging = tempfile.mkdtemp(prefix="limite_pdf_", dir=str(TEMP_DIR))

    generados: List[str] = []
    avisos:    List[str] = []
    # Qué se hizo con cada archivo, para que el informe lo pueda contar uno
    # por uno en vez de listar entradas y salidas por separado.
    detalle:   List[Dict] = []
    partidos = copiados = 0

    try:
        for i, src in enumerate(pdfs, start=1):
            nombre = os.path.basename(src)
            stem   = os.path.splitext(nombre)[0]
            tam    = os.path.getsize(src)
            mb     = tam / 1048576

            if progress_cb:
                progress_cb(f"📄 {i}/{len(pdfs)} · {nombre} ({mb:.1f} MB)")

            if tam <= limite_bytes:
                dst = os.path.join(staging, nombre)
                shutil.copy2(src, dst)
                detalle.append({"origen": src, "accion": "copiado",
                                "size_mb": mb, "desde": len(generados),
                                "hasta": len(generados) + 1})
                generados.append(dst)
                copiados += 1
                continue

            sub = os.path.join(staging, f"_p{i}")
            os.makedirs(sub, exist_ok=True)
            if progress_cb:
                progress_cb(
                    f"✂️ {nombre} pesa {mb:.1f} MB: se parte en partes "
                    f"de hasta {max_mb:g} MB…")
            r = split_pdf_by_size(src, sub, max_mb=max_mb,
                                  prefix=f"{stem}_Parte",
                                  progress_cb=progress_cb)
            partes = r.get("archivos") or []
            avisos.extend(r.get("avisos") or [])
            desde = len(generados)
            for parte in partes:
                dst = os.path.join(staging, os.path.basename(parte))
                shutil.move(parte, dst)
                generados.append(dst)
            detalle.append({"origen": src, "accion": "partido",
                            "size_mb": mb, "desde": desde,
                            "hasta": len(generados)})
            partidos += 1

        # Control final: ningún archivo puede pasar del límite elegido
        for g in generados:
            if os.path.getsize(g) > limite_bytes:
                avisos.append(
                    f"«{os.path.basename(g)}» quedó en "
                    f"{os.path.getsize(g) / 1048576:.1f} MB y no entra en "
                    f"{max_mb:g} MB: una sola página ya pesa más que el límite.")

        if progress_cb:
            progress_cb(f"📦 Armando tandas de {por_tanda}…")
        finales = repartir_en_tandas(generados, destino, por_tanda,
                                     progreso=progress_cb)
        # Las tandas mueven los archivos: se guarda dónde quedó cada uno.
        for d in detalle:
            d["resultados"] = finales[d.pop("desde"):d.pop("hasta")]
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    return {
        "limite":     True,
        "archivos": finales,
        "origenes": pdfs,
        "copiados": copiados,
        "partidos": partidos,
        "detalle":  detalle,
        "tandas":   cantidad_de_tandas(len(finales), por_tanda),
        "carpeta":  destino,
        "max_mb":   max_mb,
        "avisos":   avisos,
    }

def split_pdf_by_pages(src_path: str, out_dir: str = "",
                       pages_per_file: int = 10, prefix: str = "parte",
                       progress_cb: Optional[Callable] = None) -> Dict:
    """Parte un PDF en archivos de `pages_per_file` páginas cada uno."""
    from pypdf import PdfReader, PdfWriter

    if pages_per_file < 1:
        raise RuntimeError("Cada parte tiene que tener al menos 1 página.")

    out_dir = _split_out_dir(src_path, out_dir)
    lector = PdfReader(src_path)
    total = len(lector.pages)
    if total == 0:
        raise RuntimeError("El PDF no tiene páginas.")

    generados: List[str] = []
    for inicio in range(0, total, pages_per_file):
        escritor = PdfWriter()
        for p in lector.pages[inicio:inicio + pages_per_file]:
            escritor.add_page(p)
        nombre = f"{prefix}_{len(generados) + 1}.pdf"
        destino = os.path.join(out_dir, nombre)
        escritor.write(destino)
        generados.append(destino)
        if progress_cb:
            fin = min(inicio + pages_per_file, total)
            progress_cb(f"✂️ {nombre}: páginas {inicio + 1} a {fin}")

    return {"split": True, "archivos": generados, "partes": len(generados),
            "paginas": total, "carpeta": out_dir, "avisos": []}


def extract_pdf_range(src_path: str, dst_path: str, first_page: int = 1,
                      last_page: Optional[int] = None,
                      progress_cb: Optional[Callable] = None) -> Dict:
    """Guarda en `dst_path` sólo las páginas de `first_page` a `last_page`.

    Los números son los que ve el usuario: la primera página es la 1.
    """
    from pypdf import PdfReader, PdfWriter

    lector = PdfReader(src_path)
    total = len(lector.pages)
    if total == 0:
        raise RuntimeError("El PDF no tiene páginas.")

    if last_page is None:
        last_page = total
    primera = max(1, min(int(first_page), total))
    ultima = max(1, min(int(last_page), total))
    if primera > ultima:
        raise RuntimeError(
            f"La página inicial ({primera}) no puede ser mayor que la "
            f"final ({ultima}).")

    if progress_cb:
        progress_cb(f"✂️ Extrayendo páginas {primera} a {ultima} de {total}...")

    escritor = PdfWriter()
    for p in lector.pages[primera - 1:ultima]:
        escritor.add_page(p)
    escritor.write(dst_path)

    return {"split": True, "archivos": [dst_path], "partes": 1,
            "paginas": ultima - primera + 1, "carpeta":
            os.path.dirname(dst_path), "avisos": []}


# ─────────────────────────────────────────────────────────────────────────────
# Desdoblar hojas dobles
#
# Documentos escaneados de a dos carillas: una hoja oficio apaisada con la
# página 1 a la izquierda y la 2 a la derecha. Cada mitad sale como una hoja
# A4 vertical propia. Se hace con show_pdf_page (no se re-renderiza): si el
# original tiene texto o vectores, se conservan tal cual, y un escaneo no
# pierde resolución.
#
# Leerlas por OCR sin separarlas antes da renglones mezclados: Tesseract junta
# en una misma línea el renglón de la página izquierda con el de la derecha.
# ─────────────────────────────────────────────────────────────────────────────

A4_PT = (595.28, 841.89)          # ancho y alto de una hoja A4 en puntos
_DOBLE_PROPORCION = 1.15          # ancho/alto desde el cual la hoja es "doble"
_CENTRO_BANDA = (0.38, 0.62)      # dónde se busca el pliegue (fracción del ancho)


def es_hoja_doble(ancho: float, alto: float) -> bool:
    """Una hoja apaisada (bastante más ancha que alta) se toma como doble."""
    return alto > 0 and ancho / alto >= _DOBLE_PROPORCION


EXT_FOTOS = (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp")


def _abrir_hojas(fuentes):
    """Abre un PDF, o arma uno en memoria con varios PDF y/o fotos, en el
    orden dado (cada foto es una hoja). `fuentes` es una ruta o una lista.

    Las fotos de celular suelen venir guardadas de costado con una marca EXIF
    que dice cómo girarlas; el visor de Windows la respeta pero MuPDF no, y
    una hoja doble fotografiada quedaría parada. Se gira con Pillow antes."""
    import fitz
    if isinstance(fuentes, str):
        fuentes = [fuentes]
    if len(fuentes) == 1 and fuentes[0].lower().endswith(".pdf"):
        return fitz.open(fuentes[0])

    from PIL import Image, ImageOps
    doc = fitz.open()
    for ruta in fuentes:
        if ruta.lower().endswith(".pdf"):
            with fitz.open(ruta) as pdf:
                doc.insert_pdf(pdf)
            continue
        if not ruta.lower().endswith(EXT_FOTOS):
            doc.close()
            raise RuntimeError(
                f"«{os.path.basename(ruta)}» no es una foto ni un PDF.")
        with Image.open(ruta) as im:
            im = ImageOps.exif_transpose(im)
            if im.mode not in ("RGB", "L"):
                im = im.convert("RGB")
            buf = io.BytesIO()
            im.save(buf, format="JPEG", quality=90)
            # Tamaño de hoja proporcional a la foto (150 px por pulgada):
            # lo que importa es la proporción, que decide si es doble.
            w, h = im.size
        hoja = doc.new_page(width=w * 72 / 150, height=h * 72 / 150)
        hoja.insert_image(hoja.rect, stream=buf.getvalue())
    return doc


def contar_hojas_dobles(src_path) -> Tuple[int, int]:
    """(hojas apaisadas, total de hojas), para avisar en pantalla.
    `src_path` es un PDF o una lista de fotos."""
    doc = _abrir_hojas(src_path)
    try:
        dobles = sum(1 for p in doc if es_hoja_doble(p.rect.width, p.rect.height))
        return dobles, doc.page_count
    finally:
        doc.close()


def _x_del_pliegue(page) -> float:
    """Busca la columna más limpia cerca del centro de la hoja: ahí está la
    separación entre las dos carillas.

    Un escaneo rara vez queda centrado justo; cortar en la mitad exacta puede
    llevarse el final de los renglones de una página a la otra. Si la franja
    central no tiene un hueco claro, se corta en la mitad."""
    import fitz
    ancho = page.rect.width
    mitad = ancho / 2
    try:
        pix = page.get_pixmap(dpi=40, colorspace=fitz.csGRAY)
        w, h, datos = pix.width, pix.height, pix.samples
        x0, x1 = int(w * _CENTRO_BANDA[0]), int(w * _CENTRO_BANDA[1])
        if x1 - x0 < 5 or h < 5:
            return mitad
        # Tinta por columna (0 = blanco). Se ignora un 3 % arriba y abajo,
        # donde suelen quedar bordes negros del escáner.
        y0, y1 = int(h * 0.03), int(h * 0.97)
        tinta = [sum(255 - datos[y * w + x] for y in range(y0, y1))
                 for x in range(x0, x1)]
        r = max(1, (x1 - x0) // 40)       # suavizado: un hueco, no una columna suelta
        suave = [sum(tinta[max(0, i - r):i + r + 1]) / len(tinta[max(0, i - r):i + r + 1])
                 for i in range(len(tinta))]
        minimo = min(suave)
        promedio = sum(suave) / len(suave)
        if promedio <= 0 or minimo > promedio * 0.6:
            return mitad                  # sin hueco claro: mitad exacta
        # Entre las columnas igual de limpias, la más cercana al centro
        centro = (x1 - x0) / 2
        tope = minimo + (promedio - minimo) * 0.05
        mejor = min((i for i, v in enumerate(suave) if v <= tope),
                    key=lambda i: abs(i - centro))
        return (x0 + mejor + 0.5) * ancho / w
    except Exception:
        return mitad


def _poner_en_a4(salida, src_doc, pno: int, clip) -> None:
    """Agrega a `salida` una hoja A4 con el recorte `clip` de la página `pno`,
    agrandado o achicado para que entre entero y centrado. Si el recorte es
    apaisado, la hoja A4 también."""
    w, h = A4_PT
    if clip.width > clip.height:
        w, h = h, w
    hoja = salida.new_page(width=w, height=h)
    hoja.show_pdf_page(hoja.rect, src_doc, pno, clip=clip, keep_proportion=True)


def desdoblar_hojas_dobles(src_path, dst_path: str,
                           derecha_primero: bool = False,
                           ocr: str = "", lang: str = "Español",
                           grayscale: bool = False,
                           exigir_dobles: bool = True,
                           progress_cb: Optional[Callable] = None,
                           page_cb: Optional[Callable] = None) -> Dict:
    """Separa cada hoja doble (apaisada) en dos hojas A4, en orden de lectura:
    primero la mitad izquierda y después la derecha (al revés con
    `derecha_primero`). Las hojas que ya son simples pasan a A4 sin cortar.

    `src_path` es un PDF, o una lista de fotos (cada foto es una hoja).
    `ocr`: "" deja sólo el PDF desdoblado; "pdf" lo deja además con el texto
    buscable; "txt" guarda en `dst_path` el texto reconocido, página por página.
    """
    import fitz
    import tempfile

    if ocr not in ("", "pdf", "txt"):
        raise RuntimeError(f"Salida de reconocimiento desconocida: {ocr}")
    if ocr:
        from motors.motor_ocr import is_available
        if not is_available():
            raise RuntimeError(
                "Reconocimiento de texto no disponible.\n"
                "Colocá tesseract.exe en la carpeta bin/ del programa.")

    origen = _abrir_hojas(src_path)
    salida = fitz.open()
    try:
        total = origen.page_count
        if total == 0:
            raise RuntimeError("El PDF no tiene páginas.")
        # Hojas guardadas giradas (/Rotate): se "hornea" el giro para que
        # izquierda y derecha sean las que se ven en pantalla.
        for pagina in origen:
            if pagina.rotation:
                pagina.remove_rotation()

        dobles = 0
        for i, pagina in enumerate(origen):
            r = pagina.rect
            if es_hoja_doble(r.width, r.height):
                dobles += 1
                if progress_cb:
                    progress_cb(f"📖 Desdoblando hoja {i + 1}/{total}...")
                x = r.x0 + _x_del_pliegue(pagina)
                mitades = [fitz.Rect(r.x0, r.y0, x, r.y1),
                           fitz.Rect(x, r.y0, r.x1, r.y1)]
                if derecha_primero:
                    mitades.reverse()
                for clip in mitades:
                    _poner_en_a4(salida, origen, i, clip)
            else:
                if progress_cb:
                    progress_cb(f"📄 Hoja {i + 1}/{total}: simple, pasa a A4")
                _poner_en_a4(salida, origen, i, r)
            if page_cb:
                page_cb(i + 1, total)

        if dobles == 0 and exigir_dobles:
            raise RuntimeError(
                "Ninguna hoja de este PDF es apaisada: no hay hojas dobles "
                "para separar.")
        paginas = salida.page_count

        if not ocr:
            save_doc_safely(salida, dst_path, progress_cb,
                            garbage=3, deflate=True)
        else:
            # El OCR trabaja sobre el PDF ya desdoblado, armado aparte
            fd, temporal = tempfile.mkstemp(suffix=".pdf")
            os.close(fd)
            try:
                salida.save(temporal, garbage=3, deflate=True)
                if ocr == "pdf":
                    from motors.motor_ocr import convert_pdf_to_searchable_pdf
                    convert_pdf_to_searchable_pdf(
                        temporal, dst_path, lang, progress_cb=progress_cb,
                        page_cb=page_cb, grayscale=grayscale)
                else:
                    from motors.motor_ocr import convert_pdf_to_text
                    convert_pdf_to_text(temporal, dst_path, lang,
                                        progress_cb=progress_cb,
                                        page_cb=page_cb)
            finally:
                try:
                    os.remove(temporal)
                except Exception:
                    pass
    finally:
        salida.close()
        origen.close()

    return {"desdoblar": True, "hojas": total, "dobles": dobles,
            "paginas": paginas, "ocr": ocr, "archivos": [dst_path]}


def desdoblar_varios(fuentes: List[str], carpeta: str, sufijo: str,
                     derecha_primero: bool = False,
                     ocr: str = "", lang: str = "Español",
                     grayscale: bool = False,
                     progress_cb: Optional[Callable] = None,
                     page_cb: Optional[Callable] = None) -> Dict:
    """Un resultado por cada archivo de `fuentes` (PDF o foto), en `carpeta`,
    con el nombre del original + `sufijo` (p. ej. "_A4.pdf").

    Un archivo sin hojas dobles no corta la tanda: igual sale en A4 (y con
    OCR, si se pidió) y se avisa. Si uno falla, se sigue con los demás."""
    os.makedirs(carpeta, exist_ok=True)
    archivos, avisos = [], []
    hojas = dobles = paginas = 0
    n = len(fuentes)
    for k, fuente in enumerate(fuentes, 1):
        nombre = os.path.basename(fuente)
        destino = os.path.join(carpeta, os.path.splitext(nombre)[0] + sufijo)
        if progress_cb:
            progress_cb(f"📖 Archivo {k}/{n}: {nombre}")

        def _avance(cur, tot, _k=k):
            if page_cb and tot:
                page_cb((_k - 1) * tot + cur, n * tot)

        try:
            r = desdoblar_hojas_dobles(
                fuente, destino, derecha_primero=derecha_primero, ocr=ocr,
                lang=lang, grayscale=grayscale, exigir_dobles=False,
                progress_cb=progress_cb, page_cb=_avance)
        except Exception as e:
            avisos.append(f"«{nombre}»: {e}")
            continue
        archivos.append(destino)
        hojas += r["hojas"]
        dobles += r["dobles"]
        paginas += r["paginas"]
        if not r["dobles"]:
            avisos.append(f"«{nombre}» no tenía hojas dobles: salió en A4 sin cortar.")
    if not archivos:
        raise RuntimeError("No se pudo procesar ningún archivo:\n"
                           + "\n".join(avisos))
    return {"desdoblar": True, "hojas": hojas, "dobles": dobles,
            "paginas": paginas, "ocr": ocr, "archivos": archivos,
            "carpeta": carpeta, "avisos": avisos}


# ─────────────────────────────────────────────────────────────────────────────
# Firma digital (PAdES) — certificado .pfx/.p12 o token USB (PKCS#11)
# ─────────────────────────────────────────────────────────────────────────────

# DLLs PKCS#11 típicas de tokens de firma digital en Windows.
# Es sólo la vía rápida: `find_pkcs11_modules()` además rastrea el disco, así
# que un token de otra marca igual se detecta aunque no figure acá.
_PKCS11_CANDIDATES = [
    r"C:\Windows\System32\eTPKCS11.dll",          # SafeNet / Aladdin eToken
    r"C:\Windows\System32\eps2003csp11.dll",      # ePass 2003 (Feitian)
    r"C:\Windows\System32\asepkcs.dll",           # Athena IDProtect
    r"C:\Windows\System32\akbypkcs11.dll",        # Akby
    r"C:\Windows\System32\bit4xpki.dll",          # Bit4id
    r"C:\Windows\System32\bit4ipki.dll",          # Bit4id (variante)
    r"C:\Windows\System32\cmP11.dll",             # CardOS / Atos
    r"C:\Windows\System32\aetpkss1.dll",          # Athena ASECard
    r"C:\Windows\System32\gclib.dll",             # Gemalto Classic Client
    r"C:\Windows\System32\idprimepkcs11.dll",     # Gemalto/Thales IDPrime
    r"C:\Windows\System32\WDPKCS.dll",            # Watchdata WatchKey
    r"C:\Windows\System32\SetTokI.dll",           # Siemens / Setec
    r"C:\Windows\System32\pteidpkcs11.dll",       # Cartão de Cidadão (PT)
    r"C:\Windows\System32\FTPKCS11.dll",          # Feitian genérico
    r"C:\Windows\System32\ShuttleCsp11_3003.dll",  # Longmai mToken (viejo)
    r"C:\Windows\System32\lm_cryptoide_pkcs11.dll",  # Longmai mToken CryptoID FIPS 140-3
    r"C:\Program Files\OpenSC Project\OpenSC\pkcs11\opensc-pkcs11.dll",
    r"C:\Program Files (x86)\OpenSC Project\OpenSC\pkcs11\opensc-pkcs11.dll",
]

# Nombre de archivo (en minúsculas) → marca del token, para mostrar en la UI.
_PKCS11_BRANDS = {
    "etpkcs11.dll": "SafeNet / Aladdin eToken",
    "eps2003csp11.dll": "ePass 2003 (Feitian)",
    "ftpkcs11.dll": "Feitian",
    "asepkcs.dll": "Athena IDProtect",
    "aetpkss1.dll": "Athena ASECard",
    "akbypkcs11.dll": "Akby",
    "bit4xpki.dll": "Bit4id",
    "bit4ipki.dll": "Bit4id",
    "cmp11.dll": "CardOS / Atos",
    "gclib.dll": "Gemalto Classic Client",
    "idprimepkcs11.dll": "Gemalto / Thales IDPrime",
    "wdpkcs.dll": "Watchdata WatchKey",
    "settoki.dll": "Setec",
    "pteidpkcs11.dll": "Cartão de Cidadão (PT)",
    "shuttlecsp11_3003.dll": "mToken CryptoID (Longmai)",
    "lm_cryptoide_pkcs11.dll": "mToken CryptoID (Longmai)",
    "opensc-pkcs11.dll": "OpenSC (genérico)",
}

# Nombres de archivo que delatan un módulo PKCS#11 de cualquier fabricante.
_PKCS11_NAME_RE = re.compile(
    r"(pkcs.?11|cryptoki|csp11|mtoken|p11\.dll$|pki\.dll$|pkcs\.dll$)",
    re.IGNORECASE)

# Carpetas donde los middlewares suelen instalar su módulo PKCS#11.
_PKCS11_SCAN_DIRS = [
    os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32"),
    os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "SysWOW64"),
]
_PKCS11_SCAN_ROOTS = [
    os.environ.get("ProgramFiles", r"C:\Program Files"),
    os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
]


def _is_pkcs11_module(path: str) -> bool:
    """True si la DLL exporta `C_GetFunctionList`, o sea, es PKCS#11 de verdad.

    Es la prueba definitiva y no depende del fabricante: descarta los falsos
    positivos por nombre (p. ej. msvcp110_win.dll) sin listas negras.
    """
    try:
        import ctypes
        lib = ctypes.WinDLL(path)
    except Exception:
        return False
    try:
        getattr(lib, "C_GetFunctionList")
        return True
    except Exception:
        return False


def _scan_dir_for_pkcs11(directory: str, encontrados: List[str],
                         profundidad: int = 0, max_prof: int = 3) -> None:
    """Agrega a `encontrados` las DLLs con pinta de PKCS#11 bajo `directory`."""
    try:
        with os.scandir(directory) as it:
            entradas = list(it)
    except (OSError, PermissionError):
        return
    for e in entradas:
        try:
            if e.is_file() and e.name.lower().endswith(".dll") \
                    and _PKCS11_NAME_RE.search(e.name):
                encontrados.append(e.path)
            elif e.is_dir() and profundidad < max_prof:
                _scan_dir_for_pkcs11(e.path, encontrados,
                                     profundidad + 1, max_prof)
        except (OSError, PermissionError):
            continue


def find_pkcs11_modules(deep: bool = True) -> List[str]:
    """Devuelve las DLLs PKCS#11 de tokens presentes en este equipo.

    Combina tres fuentes para soportar cualquier marca de token:
      1. La lista curada `_PKCS11_CANDIDATES` (vía rápida, marcas conocidas).
      2. Un rastreo de System32/SysWOW64 y Program Files buscando nombres con
         pinta de módulo PKCS#11 (`deep=True`).
      3. Validación real: se conserva sólo lo que exporta `C_GetFunctionList`.
    """
    candidatos: List[str] = [p for p in _PKCS11_CANDIDATES if os.path.isfile(p)]

    if deep:
        crudos: List[str] = []
        for d in _PKCS11_SCAN_DIRS:
            _scan_dir_for_pkcs11(d, crudos, max_prof=0)
        for raiz in _PKCS11_SCAN_ROOTS:
            _scan_dir_for_pkcs11(raiz, crudos, max_prof=3)
        candidatos.extend(crudos)

    # Deduplicar respetando el orden (la lista curada va primero)
    vistos = set()
    unicos: List[str] = []
    for p in candidatos:
        clave = os.path.normcase(os.path.abspath(p))
        if clave not in vistos:
            vistos.add(clave)
            unicos.append(p)

    return [p for p in unicos if _is_pkcs11_module(p)]


def describe_pkcs11_module(path: str) -> str:
    """Etiqueta amigable para el combo de la UI: 'eTPKCS11.dll — SafeNet'."""
    nombre = os.path.basename(path)
    marca = _PKCS11_BRANDS.get(nombre.lower())
    return f"{nombre} — {marca}" if marca else nombre


# ─────────────────────────────────────────────────────────────────────────────
# Detección del token físico (para guiar al usuario que no sabe de informática)
# ─────────────────────────────────────────────────────────────────────────────

# Palabra clave que aparece en el nombre del dispositivo → (marca, middleware).
_TOKEN_MIDDLEWARE = [
    ("SAFENET",    "SafeNet / Aladdin eToken", "SafeNet Authentication Client"),
    ("ETOKEN",     "SafeNet / Aladdin eToken", "SafeNet Authentication Client"),
    ("ALADDIN",    "SafeNet / Aladdin eToken", "SafeNet Authentication Client"),
    ("IDPRIME",    "Gemalto / Thales IDPrime", "SafeNet Authentication Client"),
    ("GEMALTO",    "Gemalto",                  "Gemalto Classic Client"),
    ("EPASS",      "ePass 2003 (Feitian)",     "ePass2003 (middleware de Feitian)"),
    ("FEITIAN",    "Feitian",                  "ePass2003 (middleware de Feitian)"),
    ("BIT4ID",     "Bit4id",                   "Bit4id middleware"),
    ("IDPROTECT",  "Athena IDProtect",         "IDProtect Client"),
    ("ATHENA",     "Athena",                   "IDProtect Client"),
    ("ASECARD",    "Athena ASECard",           "IDProtect Client"),
    ("WATCHDATA",  "Watchdata WatchKey",       "WatchKey middleware"),
    ("WATCHKEY",   "Watchdata WatchKey",       "WatchKey middleware"),
    ("LONGMAI",    "mToken CryptoID (Longmai)", "mToken middleware"),
    ("MTOKEN",     "mToken CryptoID (Longmai)", "mToken middleware"),
    ("CRYPTOID",   "mToken CryptoID (Longmai)", "mToken middleware"),
    ("YUBIKEY",    "YubiKey",                  "YubiKey Minidriver u OpenSC"),
    ("CARDOS",     "CardOS / Atos",            "CardOS API"),
    ("TOKENME",    "TokenMe (Macroseguridad)", "Macroseguridad TokenMe"),
]

# ─────────────────────────────────────────────────────────────────────────────
# Guía de descarga por middleware: de dónde bajarlo y qué hacer con el archivo.
#
# Los links de fabricante se pudren seguido, así que cada entrada tiene:
#   url    → página verificada a mano (4-ago-2026); si el fabricante no publica
#            una descarga abierta, se usa una búsqueda armada, que nunca muere.
#   pasos  → instrucciones para alguien que no sabe nada de computación.
# ─────────────────────────────────────────────────────────────────────────────

def _busqueda(texto: str) -> str:
    """URL de búsqueda como último recurso (no depende de ningún fabricante)."""
    from urllib.parse import quote_plus
    return "https://www.google.com/search?q=" + quote_plus(texto)


# Pasos finales, iguales para todos los middlewares.
_PASOS_COMUNES = [
    "Cuando termine de instalar, reiniciá la computadora.",
    "Enchufá el token en un puerto USB y volvé a abrir el Conversor.",
    'En esta misma pantalla tocá "🔄 Buscar el token de nuevo": el cartel '
    "tiene que ponerse verde y decir «Token detectado».",
]

_MIDDLEWARE_INFO: Dict[str, Dict] = {
    "SafeNet Authentication Client": {
        "url": "https://knowledge.digicert.com/general-information/"
               "how-to-download-safenet-authentication-client",
        "sitio": "DigiCert (descarga abierta, sin usuario ni contraseña)",
        "pasos": [
            "Abrí la página y buscá el renglón que dice «SafeNet "
            "Authentication Client 10.9 R1 GA for Windows».",
            "Hacé clic para descargarlo. Es un archivo .zip grande; guardalo "
            "en el Escritorio para encontrarlo fácil.",
            "Cuando termine, hacé clic derecho sobre el .zip → «Extraer "
            "todo...» → «Extraer». Se arma una carpeta con el mismo nombre.",
            "Entrá a esa carpeta y abrí la subcarpeta que diga «64-bit» "
            "(o «x64»).",
            "Hacé clic derecho sobre el archivo que termina en .msi → "
            "«Ejecutar como administrador». Si Windows pregunta si permitís "
            "los cambios, decí que sí.",
            "Seguí el instalador: Siguiente → aceptar los términos → "
            "Siguiente → Instalar. Dejá el idioma y la carpeta como vienen.",
        ] + _PASOS_COMUNES,
    },
    "Gemalto Classic Client": {
        "url": _busqueda("Gemalto Classic Client download Windows middleware"),
        "sitio": "búsqueda (Gemalto no publica una descarga abierta)",
        "pasos": [
            "Gemalto no ofrece descarga libre: el programa te lo tiene que "
            "dar quien te vendió o entregó el token.",
            "Si igual querés buscarlo, abrí el link y descargá el instalador "
            "para Windows de un sitio oficial o de tu autoridad certificante.",
            "Hacé clic derecho sobre el instalador → «Ejecutar como "
            "administrador» y seguí los pasos.",
        ] + _PASOS_COMUNES,
    },
    "ePass2003 (middleware de Feitian)": {
        "url": "https://www.ftsafe.com/Support/Resources",
        "sitio": "Feitian (fabricante del token)",
        "pasos": [
            "Abrí la página de soporte de Feitian y buscá la descarga que "
            "diga «ePass2003» para Windows.",
            "Descargá el archivo y guardalo en el Escritorio.",
            "Si es un .zip, hacé clic derecho → «Extraer todo...» → "
            "«Extraer».",
            "Hacé clic derecho sobre «ePass2003 Setup.exe» → «Ejecutar como "
            "administrador» y seguí los pasos con Siguiente.",
        ] + _PASOS_COMUNES,
    },
    "Bit4id middleware": {
        "url": _busqueda("Bit4id middleware descargar Windows token"),
        "sitio": "búsqueda (el sitio de Bit4id bloquea la descarga directa)",
        "pasos": [
            "Abrí el link y entrá al sitio oficial de Bit4id, sección "
            "«Download» o «Descargas».",
            "Descargá el middleware para Windows y guardalo en el Escritorio.",
            "Hacé clic derecho sobre el instalador → «Ejecutar como "
            "administrador» y seguí los pasos.",
        ] + _PASOS_COMUNES,
    },
    "IDProtect Client": {
        "url": _busqueda("Athena IDProtect Client download Windows"),
        "sitio": "búsqueda (Athena fue comprada por NXP; lo distribuyen "
                 "los revendedores)",
        "pasos": [
            "Este programa lo entrega normalmente quien te vendió el token. "
            "Pediselo a ellos primero.",
            "Si preferís buscarlo, abrí el link y descargá «IDProtect "
            "Client» para Windows de un sitio oficial.",
            "Hacé clic derecho sobre el instalador → «Ejecutar como "
            "administrador» y seguí los pasos.",
        ] + _PASOS_COMUNES,
    },
    "Macroseguridad TokenMe": {
        "url": "https://www.macroseguridad.net/",
        "sitio": "Macroseguridad (empresa argentina, habilitada por ARCA/AFIP)",
        "pasos": [
            "Abrí el sitio y entrá a la sección «Soporte» → «Descargas».",
            "Descargá el programa que corresponda a tu modelo de token, para "
            "Windows.",
            "Hacé clic derecho sobre el instalador → «Ejecutar como "
            "administrador» y seguí los pasos.",
        ] + _PASOS_COMUNES,
    },
    "YubiKey Minidriver u OpenSC": {
        "url": "https://www.yubico.com/support/download/"
               "smart-card-drivers-tools/",
        "sitio": "Yubico (fabricante, descarga abierta)",
        "pasos": [
            "Abrí la página y descargá «YubiKey Smart Card Minidriver» para "
            "Windows, versión x64 (la de 64 bits).",
            "Hacé clic derecho sobre el archivo descargado → «Ejecutar como "
            "administrador» y seguí los pasos.",
        ] + _PASOS_COMUNES,
    },
    "WatchKey middleware": {
        "url": _busqueda("Watchdata WatchKey middleware download Windows"),
        "sitio": "búsqueda (Watchdata distribuye por revendedor)",
        "pasos": [
            "Pediselo primero a quien te entregó el token: es lo más seguro.",
            "Si no, abrí el link y descargá el middleware «WatchKey» para "
            "Windows de un sitio oficial.",
            "Hacé clic derecho sobre el instalador → «Ejecutar como "
            "administrador» y seguí los pasos.",
        ] + _PASOS_COMUNES,
    },
    # Longmai no publica descarga abierta: en Argentina estos tokens
    # (mToken CryptoID / CryptoFIPS) los distribuye Macroseguridad, que manda
    # el middleware por mail después de un formulario con el número de serie.
    # Verificado el 26-ago-2026: cryptoid.com.ar vive, el formulario también,
    # y no hay ningún link de descarga directo en ninguno de los dos.
    "mToken middleware": {
        "url": "https://www.cryptoid.com.ar/",
        "sitio": "Macroseguridad / CryptoID (distribuidor en Argentina)",
        "pasos": [
            "Pediselo primero a quien te entregó el token (el organismo, "
            "colegio o empresa): ellos tienen el instalador y es el camino "
            "más rápido y seguro.",
            "Si no lo conseguís, abrí el link: es la página del token "
            "«mToken CryptoID FIPS» en Argentina.",
            "Ahí, en la parte de soporte, hay un formulario que pide el "
            "NÚMERO DE SERIE del token (está impreso en el cuerpo del "
            "token, en letra chica) más tu nombre y tu correo.",
            "Completalo y te mandan por correo la guía y el middleware. No "
            "hay descarga directa: el fabricante no lo publica abierto.",
            "Cuando lo tengas, si viene en .zip hacé clic derecho → "
            "«Extraer todo...» → «Extraer».",
            "Hacé clic derecho sobre el instalador → «Ejecutar como "
            "administrador» y seguí los pasos.",
        ] + _PASOS_COMUNES,
    },
    "CardOS API": {
        "url": _busqueda("Atos CardOS API download Windows middleware"),
        "sitio": "búsqueda (Atos/Eviden lo entrega a sus clientes)",
        "pasos": [
            "Pediselo primero a quien te entregó el token: Atos no publica "
            "una descarga abierta.",
            "Si no, abrí el link y descargá «CardOS API» para Windows de un "
            "sitio oficial.",
            "Hacé clic derecho sobre el instalador → «Ejecutar como "
            "administrador» y seguí los pasos.",
        ] + _PASOS_COMUNES,
    },
    # Comodín: sirve con muchísimos tokens cuando no se identifica la marca.
    "OpenSC (genérico)": {
        "url": "https://github.com/OpenSC/OpenSC/releases",
        "sitio": "OpenSC (programa libre que funciona con muchas marcas)",
        "pasos": [
            "Esto es un comodín: funciona con muchos tokens, pero si sabés la "
            "marca del tuyo conviene el programa del fabricante.",
            "Abrí la página, buscá la versión más nueva y descargá el archivo "
            "que termine en «_x64.msi» (el de 64 bits).",
            "Hacé clic derecho sobre el .msi → «Ejecutar como administrador» "
            "y seguí los pasos.",
        ] + _PASOS_COMUNES,
    },
}

# Consejo que vale para cualquier marca, sobre todo en Argentina.
_NOTA_ORGANISMO = (
    "Consejo: si el token te lo dio un organismo (una dependencia pública, el ente de impuestos, "
    "un colegio profesional o una autoridad certificante), lo más rápido es "
    "pedirles a ellos el instalador o el instructivo. Es el mismo programa, "
    "pero te aseguran la versión exacta que usan."
)


# Instaladores que viajan con el programa (carpeta instaladores_token): para
# estas marcas no hay que descargar nada, se instala desde el propio Conversor.
# Son los binarios del fabricante, con su firma digital; antes de abrirlos se
# comprueba que la firma siga siendo válida y de quién corresponde.
_INSTALADORES_INCLUIDOS: Dict[str, Tuple[str, str]] = {
    # programa: (archivo, parte del nombre de quien lo firma)
    "SafeNet Authentication Client":
        ("SafeNetAuthenticationClient-x64.msi", "Thales"),
    "mToken middleware":
        ("LMCryptoIDE_Setup.exe", "Longmai"),
}

_PASOS_INSTALADOR_INCLUIDO = [
    "Desenchufá el token: el instalador lo pide.",
    'Tocá "▶ Instalar ahora". Si Windows pregunta si permitís los cambios, '
    "decí que sí.",
    "Seguí el instalador: Siguiente → aceptar los términos → Instalar. "
    "Dejá el idioma y la carpeta como vienen.",
]


def instalador_incluido(middleware: str) -> str:
    """Ruta del instalador que viaja con el programa, o "" si no hay."""
    dato = _INSTALADORES_INCLUIDOS.get(middleware)
    if not dato:
        return ""
    try:
        from core.paths import resource
        ruta = resource(os.path.join("instaladores_token", dato[0]))
    except Exception:
        return ""
    return ruta if os.path.isfile(ruta) else ""


def verificar_instalador_incluido(middleware: str) -> Tuple[bool, str]:
    """(True, firmante) si el instalador incluido conserva la firma digital
    válida de su fabricante; (False, motivo) si no."""
    ruta = instalador_incluido(middleware)
    if not ruta:
        return False, "El instalador no está en la carpeta del programa."
    estado, firmante = _firmas_authenticode([ruta]).get(ruta, ("", ""))
    esperado = _INSTALADORES_INCLUIDOS[middleware][1]
    if estado != "Valid":
        return False, ("El instalador no tiene una firma digital válida "
                       f"(estado: {estado or 'no se pudo comprobar'}).")
    if esperado.lower() not in firmante.lower():
        return False, f"El instalador está firmado por «{firmante}», no por {esperado}."
    return True, firmante


def download_guide(middleware: str = "") -> Dict:
    """De dónde bajar el programa del token y qué hacer con el archivo.

    Si no se identificó la marca, devuelve la guía genérica de OpenSC. Si el
    instalador de esa marca viaja con el programa, la guía es la corta: se
    instala desde acá, sin descargar nada (clave `instalador`).
    """
    info = _MIDDLEWARE_INFO.get(middleware)
    generico = not info
    if generico:
        info = _MIDDLEWARE_INFO["OpenSC (genérico)"]
        middleware = "OpenSC (genérico)"
    guia = {
        "programa": middleware,
        "url": info["url"],
        "sitio": info["sitio"],
        "pasos": list(info["pasos"]),
        "nota": _NOTA_ORGANISMO,
        "generico": generico,
        "instalador": "",
    }
    incluido = instalador_incluido(middleware)
    if incluido:
        guia["instalador"] = incluido
        guia["sitio"] = "viene con el programa: no hay que descargar nada"
        guia["pasos"] = _PASOS_INSTALADOR_INCLUIDO + _PASOS_COMUNES
        guia["nota"] = ""       # el consejo de pedírselo al organismo sobra
    return guia


def format_download_guide(guia: Dict) -> str:
    """Guía de instalación en texto plano, lista para mostrar en un diálogo."""
    lineas = [
        f"CÓMO INSTALAR: {guia['programa']}",
        "=" * 60,
        "",
    ]
    if guia.get("instalador"):
        lineas += ["El instalador viene con el programa: no hay que "
                   "descargar nada."]
    else:
        lineas += [f"Dónde bajarlo: {guia['sitio']}",
                   f"Link: {guia['url']}"]
    lineas += [
        "",
        "PASOS:",
    ]
    for i, paso in enumerate(guia["pasos"], 1):
        lineas.append(f"  {i}. {paso}")
    lineas += ["", guia["nota"]]
    return "\n".join(lineas)


# ─────────────────────────────────────────────────────────────────────────────
# "Ya lo descargué, ¿cuál abro?" — encontrar el instalador en la carpeta bajada
#
# No se puede hardcodear la ruta por marca: cada fabricante arma el paquete a
# su manera (SafeNet usa Msi\x64\..., otros dejan un único .exe en la raíz).
# Así que se busca por características, no por nombre conocido.
# ─────────────────────────────────────────────────────────────────────────────

# Partes del nombre/ruta que delatan que NO es el instalador principal.
_INSTALADOR_DESCARTES = [
    "customization", "admx", "documentation", "manual", "sample", "ejemplo",
    "uninstall", "desinstal", "readme", "sdk", "debug", "symbol", "language",
    "languagepack", "hotfix", "patch",
]

# Arquitecturas: (palabras en el nombre, puntaje si la máquina es x64).
_ARCH_HINTS = [
    (("arm64", "aarch64"), -100),          # otra arquitectura: nunca sirve
    (("x64", "amd64", "64-bit", "64bit", "win64"), 40),
    (("x32", "x86", "32-bit", "32bit", "win32", "i386"), -40),
]


def _maquina_es_64() -> bool:
    import platform
    return platform.machine().upper() in ("AMD64", "X86_64", "IA64")


def _puntaje_instalador(path: str, tam: int) -> Tuple[int, str]:
    """Qué tan probable es que `path` sea EL instalador a ejecutar."""
    nombre = os.path.basename(path).lower()
    ruta = path.lower()
    puntaje = 0
    motivos = []

    if nombre.endswith(".msi"):
        puntaje += 30
    elif nombre.endswith(".exe"):
        puntaje += 20

    if _maquina_es_64():
        for palabras, valor in _ARCH_HINTS:
            if any(p in ruta for p in palabras):
                puntaje += valor
                if valor > 0:
                    motivos.append("es la versión de 64 bits, la que "
                                   "corresponde a esta computadora")
                elif valor <= -100:
                    motivos.append("es para otro tipo de procesador (ARM)")
                else:
                    motivos.append("es la versión de 32 bits")
                break

    for palabra in _INSTALADOR_DESCARTES:
        if palabra in ruta:
            puntaje -= 60
            motivos.append(f"la ruta dice «{palabra}»: no es el instalador "
                           "principal")
            break

    # Palabras que suelen estar en el instalador de verdad
    if any(p in nombre for p in ("setup", "install", "client", "driver",
                                 "middleware", "token")):
        puntaje += 15

    # Los instaladores reales pesan; los desinstaladores y utilitarios, no
    mb = tam / (1024 * 1024)
    if mb >= 5:
        puntaje += 10
    elif mb < 1:
        puntaje -= 20
        motivos.append("es muy chico para ser un instalador")

    return puntaje, "; ".join(motivos)


def _firmas_authenticode(paths: List[str]) -> Dict[str, Tuple[str, str]]:
    """{path: (estado, firmante)} usando PowerShell, en una sola llamada."""
    if not paths:
        return {}
    import subprocess, json as _json

    lista = "@(" + ",".join(f"'{p}'" for p in
                            (x.replace("'", "''") for x in paths)) + ")"
    cmd = (f"$r = foreach ($f in {lista}) {{ "
           "$s = Get-AuthenticodeSignature -LiteralPath $f; "
           "[pscustomobject]@{ Path = $f; Status = [string]$s.Status; "
           "Signer = if ($s.SignerCertificate) "
           "{ ($s.SignerCertificate.Subject -split ',')[0] } else { '' } } }; "
           "$r | ConvertTo-Json -Compress")
    try:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        salida = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
            capture_output=True, text=True, timeout=60,
            creationflags=flags).stdout.strip()
        datos = _json.loads(salida) if salida else []
    except Exception:
        return {}

    if isinstance(datos, dict):
        datos = [datos]
    fuera = {}
    for d in datos:
        firmante = (d.get("Signer") or "").replace("CN=", "").strip(' "')
        fuera[d.get("Path", "")] = (d.get("Status", ""), firmante)
    return fuera


def find_downloaded_installer(carpeta: str, max_resultados: int = 6) -> List[Dict]:
    """Busca el instalador del driver dentro de la carpeta que bajó el usuario.

    Funciona con cualquier marca: no busca nombres conocidos sino las
    características de un instalador (extensión, arquitectura, tamaño, firma
    digital). Devuelve los candidatos ordenados, el mejor primero.
    """
    candidatos: List[Dict] = []
    for raiz, _dirs, archivos in os.walk(carpeta):
        for nombre in archivos:
            if not nombre.lower().endswith((".msi", ".exe")):
                continue
            path = os.path.join(raiz, nombre)
            try:
                tam = os.path.getsize(path)
            except OSError:
                continue
            puntaje, motivo = _puntaje_instalador(path, tam)
            candidatos.append({
                "path": path, "nombre": nombre, "mb": round(tam / 1048576, 1),
                "puntaje": puntaje, "motivo": motivo,
                "firmado": False, "firmante": "", "estado_firma": "",
            })

    candidatos.sort(key=lambda c: -c["puntaje"])
    candidatos = candidatos[:max_resultados]

    # La firma sólo se consulta para los pocos finalistas (es lo más lento)
    firmas = _firmas_authenticode([c["path"] for c in candidatos])
    for c in candidatos:
        estado, firmante = firmas.get(c["path"], ("", ""))
        c["estado_firma"] = estado
        c["firmante"] = firmante
        c["firmado"] = (estado == "Valid")
        if c["firmado"]:
            c["puntaje"] += 25

    candidatos.sort(key=lambda c: -c["puntaje"])
    return candidatos


def format_installer_choice(candidatos: List[Dict]) -> str:
    """Explica en castellano cuál abrir y por qué, para mostrar en la UI."""
    if not candidatos:
        return ("No encontré ningún instalador (.msi o .exe) en esa carpeta.\n\n"
                "Fijate que sea la carpeta donde extrajiste lo que "
                "descargaste. Si bajaste un .zip y todavía no lo abriste, "
                "hacé clic derecho sobre él → «Extraer todo...» primero.")

    mejor = candidatos[0]
    lineas = [
        "ESTE ES EL ARCHIVO QUE TENÉS QUE ABRIR:",
        "=" * 60,
        "",
        f"  {mejor['nombre']}",
        f"  ({mejor['mb']} MB)",
        "",
        f"Carpeta: {os.path.dirname(mejor['path'])}",
        "",
    ]
    if mejor["firmado"]:
        lineas.append(f"✔ Tiene firma digital válida de: {mejor['firmante']}")
        lineas.append("  Eso confirma que el archivo es auténtico del "
                      "fabricante y que nadie lo modificó.")
    elif mejor["estado_firma"]:
        lineas.append(f"⚠ Firma digital: {mejor['estado_firma']}. Si no lo "
                      "bajaste del sitio oficial, no lo instales.")
    if mejor["motivo"]:
        lineas.append(f"• Lo elegí porque {mejor['motivo']}.")

    lineas += [
        "",
        "QUÉ HACER:",
        "  1. Tocá «📂 Mostrarme el archivo»: se abre la carpeta con ese "
        "archivo ya seleccionado.",
        "  2. Hacé clic derecho sobre él → «Instalar» (o «Ejecutar como "
        "administrador»).",
        "  3. Seguí el instalador con Siguiente hasta el final.",
        "  4. Reiniciá la computadora y volvé a abrir el Conversor.",
    ]

    otros = [c for c in candidatos[1:] if c["puntaje"] > 0]
    if otros:
        lineas += ["", "-" * 60, "Otros archivos que encontré (NO son el que "
                   "necesitás, los dejo por las dudas):"]
        for c in otros:
            detalle = f" — {c['motivo']}" if c["motivo"] else ""
            lineas.append(f"  · {c['nombre']} ({c['mb']} MB){detalle}")

    return "\n".join(lineas)


def _list_smartcard_readers() -> List[str]:
    """Lectores de tarjeta/token conectados AHORA (vía winscard de Windows)."""
    if os.name != "nt":
        return []
    try:
        import ctypes
        from ctypes import wintypes
        winscard = ctypes.WinDLL("winscard.dll")
        ctx = ctypes.c_void_p()
        # SCARD_SCOPE_USER = 0
        if winscard.SCardEstablishContext(0, None, None,
                                          ctypes.byref(ctx)) != 0:
            return []
        try:
            largo = wintypes.DWORD(0)
            if winscard.SCardListReadersW(ctx, None, None,
                                          ctypes.byref(largo)) != 0:
                return []
            buf = ctypes.create_unicode_buffer(largo.value)
            if winscard.SCardListReadersW(ctx, None, buf,
                                          ctypes.byref(largo)) != 0:
                return []
            # Cadena multi-string terminada en doble NUL
            crudo = buf[:largo.value]
            return [r for r in "".join(crudo).split("\0") if r.strip()]
        finally:
            winscard.SCardReleaseContext(ctx)
    except Exception:
        return []


def _registry_smartcard_names() -> List[str]:
    """Nombres de tokens/tarjetas que Windows conoce, leídos del registro."""
    if os.name != "nt":
        return []
    nombres: List[str] = []
    try:
        import winreg
    except ImportError:
        return []

    # 1) Definiciones de tarjetas instaladas por los middlewares
    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography\Calais\SmartCards",
        ) as k:
            i = 0
            while True:
                try:
                    nombres.append(winreg.EnumKey(k, i))
                    i += 1
                except OSError:
                    break
    except OSError:
        pass

    # 2) Dispositivos de tarjeta inteligente enumerados por el filtro SCFILTER
    #    (los IDs suelen incluir la marca, p. ej. ..._SAFENET_TOKEN_JC_0_...)
    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Enum\SCFILTER",
        ) as k:
            i = 0
            while True:
                try:
                    sub = winreg.EnumKey(k, i)
                    i += 1
                except OSError:
                    break
                try:
                    with winreg.OpenKey(k, sub) as k2:
                        j = 0
                        while True:
                            try:
                                inst = winreg.EnumKey(k2, j)
                                j += 1
                            except OSError:
                                break
                            nombres.append(inst)
                            try:
                                with winreg.OpenKey(k2, inst) as k3:
                                    for valor in ("FriendlyName", "DeviceDesc"):
                                        try:
                                            v, _ = winreg.QueryValueEx(k3, valor)
                                            if v:
                                                nombres.append(str(v))
                                        except OSError:
                                            pass
                            except OSError:
                                pass
                except OSError:
                    continue
    except OSError:
        pass

    return nombres


def _brand_from_names(nombres: List[str]) -> Tuple[str, str]:
    """(marca, middleware) deducidos de nombres de lector o de dispositivo."""
    texto = " ".join(nombres).upper()
    for clave, m, mw in _TOKEN_MIDDLEWARE:
        if clave in texto:
            return m, mw
    return "", ""


def detect_smartcard_hardware() -> Dict:
    """Averigua si hay un token conectado y de qué marca es.

    Devuelve: `lectores` (conectados ahora), `marca` y `middleware` sugerido
    (o cadena vacía si no se pudo identificar).

    OJO: la marca se deduce SÓLO de los lectores conectados en este momento.
    El registro de Windows lista además todas las tarjetas que conoce cada
    middleware instalado (SafeNet solo agrega ~30 nombres «eToken*»), así que
    mirarlo daba «SafeNet» aunque el token puesto fuera de otra marca. El
    registro se usa nada más cuando no hay ningún lector conectado, para poder
    sugerir algo.
    """
    lectores = _list_smartcard_readers()
    nombres_registro = _registry_smartcard_names()

    marca, middleware = _brand_from_names(lectores)
    if not lectores:
        marca, middleware = _brand_from_names(nombres_registro)

    return {
        "lectores": lectores,
        "conectado": bool(lectores),
        "marca": marca,
        "middleware": middleware,
        "nombres": lectores + nombres_registro,
    }


def diagnose_token() -> Dict:
    """Diagnóstico completo en castellano llano para el usuario final.

    Estados posibles: `listo`, `sin_driver`, `sin_token`, `sin_pyhanko`.
    """
    if not is_signing_available():
        return {
            "estado": "sin_pyhanko",
            "titulo": "Falta un componente de la app",
            "mensaje": "No está instalado el paquete 'pyhanko', que es el que "
                       "firma los PDF. Reinstalá la aplicación.",
            "modulos": [], "hardware": {},
        }

    hw = detect_smartcard_hardware()
    modulos = find_pkcs11_modules()

    if modulos and hw["conectado"]:
        # Tener una DLL instalada no alcanza: la de una marca no ve el token
        # de otra. Sin esta comprobación, cambiar de token dejaba el cartel en
        # «todo listo» y después no aparecía ningún certificado.
        dll_ok, slots = find_token_module(modulos)
        if not dll_ok:
            return _diag_driver_ajeno(modulos, hw)

        marca = f" ({hw['marca']})" if hw["marca"] else ""
        etiqueta = (slots[0].get("etiqueta") or "").strip() if slots else ""
        return {
            "estado": "listo",
            "dll": dll_ok,
            "slots": slots,
            "token": etiqueta,
            "titulo": "Token detectado",
            "mensaje": f"Tu token está conectado{marca} y el programa del "
                       "fabricante está instalado."
                       + (f"\nEl token se llama «{etiqueta}»." if etiqueta else "")
                       + "\n\n"
                       "Falta un paso que la app no puede hacer sola: probar "
                       "el PIN. Escribilo y tocá «🔍 Probar token» — si el "
                       "PIN es correcto vas a ver tu certificado, y recién "
                       "ahí está todo confirmado.\n\n"
                       "Ojo: cada PIN equivocado gasta un reintento y "
                       "agotarlos bloquea el token.",
            "modulos": modulos, "hardware": hw,
        }

    if modulos and not hw["conectado"]:
        return {
            "estado": "sin_token",
            "titulo": "No encuentro el token",
            "mensaje": "El driver está instalado, pero no hay ningún token "
                       "enchufado. Conectá el token al puerto USB y volvé a "
                       "probar. Si ya está puesto, sacalo y volvé a ponerlo.",
            "modulos": modulos, "hardware": hw,
        }

    # Sin módulo PKCS#11: falta el middleware del fabricante
    if hw["middleware"]:
        detalle = (f"Tu token es un {hw['marca']}. Instalá el programa "
                   f"«{hw['middleware']}» del fabricante y volvé a abrir "
                   "esta aplicación.")
    elif hw["conectado"]:
        detalle = ("Hay un token conectado, pero no pude identificar la marca. "
                   "Instalá el programa que vino con el token (el CD o la "
                   "descarga del fabricante) y volvé a abrir esta aplicación.")
    else:
        detalle = ("No hay ningún token conectado y tampoco está instalado el "
                   "programa del fabricante. Conectá el token e instalá su "
                   "programa; después volvé a abrir esta aplicación.")

    return {
        "estado": "sin_driver",
        "titulo": "Falta el programa del token",
        "mensaje": detalle + "\n\nEse programa es el que le permite a "
                   "cualquier aplicación usar tu token para firmar; sin él, "
                   "Windows ve el token pero no puede usar el certificado."
                   '\n\nTocá "⬇ Cómo instalarlo" y te llevo a la página de '
                   "descarga con el paso a paso.",
        "modulos": modulos, "hardware": hw,
        "descarga": download_guide(hw["middleware"]),
    }


def _diag_driver_ajeno(modulos: List[str], hw: Dict) -> Dict:
    """Hay token puesto y hay drivers, pero ninguno de esos drivers lo ve.

    Es lo que pasa al cambiar de token y quedarse con el middleware del
    anterior: Windows muestra el lector, la app encuentra una DLL PKCS#11, y
    sin embargo no hay ningún certificado porque esa DLL es de otra marca.
    """
    lector = hw["lectores"][0] if hw["lectores"] else "el token"
    instalados = ", ".join(describe_pkcs11_module(m) for m in modulos)

    if hw["marca"]:
        quien = f"Tu token es un {hw['marca']} (el lector dice «{lector}»)."
        falta = (f"Lo que falta es instalar «{hw['middleware']}», que es el "
                 "programa de esa marca.")
    else:
        quien = (f"Hay un token conectado (el lector dice «{lector}»), pero no "
                 "pude identificar la marca.")
        falta = ("Hay que instalar el programa que corresponde a ESE token: "
                 "el que vino con él, o el que indique el organismo que te lo "
                 "entregó.")

    return {
        "estado": "driver_otra_marca",
        "titulo": "El programa instalado es de otro token",
        "mensaje": (
            f"{quien}\n\nEn esta computadora está instalado el programa de "
            f"OTRA marca ({instalados}), y ese no sabe leer tu token: por eso "
            "el token figura conectado pero no aparece ningún certificado."
            f"\n\n{falta}\n\nEl programa viejo podés dejarlo instalado, no "
            'molesta.\n\nTocá "⬇ Cómo instalarlo" y te llevo a la página de '
            "descarga con el paso a paso."),
        "modulos": modulos, "hardware": hw,
        "descarga": download_guide(hw["middleware"]),
    }


def is_signing_available() -> bool:
    try:
        import pyhanko  # noqa: F401
        return True
    except ImportError:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Ubicación del sello de firma
#
# Un PDF admite UNA firma con UN sello visible: la firma protege todo el
# documento aunque el sello se vea en una sola hoja. Por eso se elige página
# y posición, no "todas las páginas".
# ─────────────────────────────────────────────────────────────────────────────

# clave interna → texto para la UI. El orden es el de la grilla de 3×3.
SIGN_POSITIONS = [
    ("arriba-izquierda", "Arriba izquierda"),
    ("arriba-centro",    "Arriba centro"),
    ("arriba-derecha",   "Arriba derecha"),
    ("medio-izquierda",  "Medio izquierda"),
    ("medio-centro",     "Centro"),
    ("medio-derecha",    "Medio derecha"),
    ("abajo-izquierda",  "Abajo izquierda"),
    ("abajo-centro",     "Abajo centro"),
    ("abajo-derecha",    "Abajo derecha"),
]
SIGN_POSITION_DEFAULT = "abajo-derecha"

# Medidas del sello en puntos PDF (1 punto = 1/72 pulgada)
STAMP_W, STAMP_H, STAMP_MARGIN = 222.0, 64.0, 28.0

# ── La leyenda del sello ────────────────────────────────────────────────────
# El sello dice quién firmó (el nombre sale del certificado) y cuándo. Debajo
# del nombre el usuario puede sumar su leyenda: cargo y dependencia, en los
# renglones que quiera («Cargo» / «Área o dependencia» / «Ciudad»).
LEYENDA_MAX_RENGLONES = 6
LEYENDA_MAX_CARACTERES = 60     # más largo que esto, el renglón se parte solo
STAMP_ALTO_RENGLON = 11.0       # lo que crece el sello por cada renglón sumado


def leyenda_en_renglones(leyenda: str) -> List[str]:
    """La leyenda tal como va al sello: los renglones que escribió el usuario,
    sin vacíos, partiendo los que no entran y con un tope de cantidad."""
    import textwrap
    # La letra del sello no trae algunos signos tipográficos (la raya larga
    # salía como una comilla baja): se pasan a su equivalente simple.
    simples = str.maketrans({"—": "-", "–": "-", "“": '"', "”": '"',
                             "‘": "'", "’": "'", "…": "..."})
    renglones: List[str] = []
    for crudo in (leyenda or "").replace("\r", "").split("\n"):
        limpio = " ".join(crudo.translate(simples).split())
        if not limpio:
            continue
        renglones.extend(textwrap.wrap(limpio, LEYENDA_MAX_CARACTERES) or [limpio])
    return renglones[:LEYENDA_MAX_RENGLONES]


def texto_del_sello(leyenda: str = "", firmante: str = "%(signer)s",
                    fecha: str = "%(ts)s") -> str:
    """El texto completo del sello. Con los valores por defecto devuelve la
    plantilla que usa la firma; la pantalla le pasa un nombre y una fecha de
    ejemplo para mostrar cómo va a quedar."""
    renglones = ["Firmado digitalmente por:", firmante]
    renglones += leyenda_en_renglones(leyenda)
    renglones.append(f"Fecha: {fecha}")
    return "\n".join(renglones)


def alto_del_sello(leyenda: str = "") -> float:
    """Alto del sello: crece con los renglones de la leyenda, para que la
    letra no se achique."""
    return STAMP_H + STAMP_ALTO_RENGLON * len(leyenda_en_renglones(leyenda))


def stamp_box(page_w: float, page_h: float,
              position: str = SIGN_POSITION_DEFAULT,
              ancho: float = STAMP_W, alto: float = STAMP_H,
              margen: float = STAMP_MARGIN) -> Tuple[float, float, float, float]:
    """Recuadro del sello: (x1, y1, x2, y2) con origen ABAJO-izquierda.

    Es el mismo cálculo que usa la vista previa, así que lo que se ve es
    exactamente donde va a quedar el sello.
    """
    if position not in dict(SIGN_POSITIONS):
        position = SIGN_POSITION_DEFAULT

    # En hojas chicas el sello se achica antes que salirse
    ancho = min(ancho, max(page_w - 2 * margen, 10.0))
    alto = min(alto, max(page_h - 2 * margen, 10.0))

    vertical, _, horizontal = position.partition("-")

    if horizontal == "izquierda":
        x1 = margen
    elif horizontal == "derecha":
        x1 = page_w - margen - ancho
    else:
        x1 = (page_w - ancho) / 2

    if vertical == "abajo":
        y1 = margen
    elif vertical == "arriba":
        y1 = page_h - margen - alto
    else:
        y1 = (page_h - alto) / 2

    return (x1, y1, x1 + ancho, y1 + alto)


def stamp_preview_rect(page_w: float, page_h: float, img_w: int, img_h: int,
                       position: str = SIGN_POSITION_DEFAULT,
                       leyenda: str = "") -> Tuple[int, int, int, int]:
    """El mismo recuadro pero en píxeles de la miniatura, origen ARRIBA.

    Qt dibuja con el origen arriba-izquierda y el PDF abajo-izquierda: acá
    se hace esa conversión una sola vez, para no repetirla en la UI.
    """
    x1, y1, x2, y2 = stamp_box(page_w, page_h, position,
                               alto=alto_del_sello(leyenda))
    ex = img_w / page_w if page_w else 1.0
    ey = img_h / page_h if page_h else 1.0
    return (int(x1 * ex), int((page_h - y2) * ey),
            int((x2 - x1) * ex), int((y2 - y1) * ey))


def page_size(src_path: str, page: int = 0) -> Tuple[float, float]:
    """Ancho y alto en puntos de una página."""
    import fitz
    doc = fitz.open(src_path)
    try:
        page = max(0, min(page, doc.page_count - 1))
        rect = doc[page].rect
        return rect.width, rect.height
    finally:
        doc.close()


def resolve_sign_page(src_path: str, eleccion="primera") -> int:
    """Convierte 'primera' / 'ultima' / un número en índice de página."""
    total = page_count(src_path)
    if isinstance(eleccion, str):
        clave = eleccion.strip().lower()
        if clave in ("primera", "primer", "inicial", "first"):
            return 0
        if clave in ("ultima", "última", "final", "last"):
            return max(total - 1, 0)
        try:
            eleccion = int(clave)
        except ValueError:
            return 0
    # Número de página tal como lo ve el usuario: 1 es la primera
    return max(0, min(int(eleccion) - 1, total - 1))


def _build_pdf_signer(signer, field_name: str, reason: str, location: str,
                      visible: bool, page: int, src_path: str,
                      position: str = SIGN_POSITION_DEFAULT,
                      leyenda: str = ""):
    """Arma el PdfSigner con sello visible opcional en la posición elegida."""
    from pyhanko.sign import signers
    from pyhanko.sign.fields import SigFieldSpec
    from pyhanko import stamp
    from pyhanko.pdf_utils import text

    meta = signers.PdfSignatureMetadata(
        field_name=field_name,
        reason=reason or None,
        location=location or None,
    )
    if not visible:
        return signers.PdfSigner(meta, signer=signer)

    import fitz
    doc = fitz.open(src_path)
    try:
        page = max(0, min(page, doc.page_count - 1))
        rect = doc[page].rect
        w, h = rect.width, rect.height
    finally:
        doc.close()
    box = stamp_box(w, h, position, alto=alto_del_sello(leyenda))

    spec = SigFieldSpec(sig_field_name=field_name, on_page=page, box=box)
    # El texto es una plantilla con %(signer)s y %(ts)s: un «%» que venga en
    # la leyenda se duplica para que no se tome como parte de la plantilla.
    style = stamp.TextStampStyle(
        stamp_text=texto_del_sello((leyenda or "").replace("%", "%%")),
        text_box_style=text.TextBoxStyle(font_size=8),
    )
    return signers.PdfSigner(meta, signer=signer,
                             stamp_style=style, new_field_spec=spec)


def _do_sign(src_path: str, dst_path: str, signer, reason: str, location: str,
             visible: bool, page: int, progress_cb: Optional[Callable],
             position: str = SIGN_POSITION_DEFAULT,
             leyenda: str = "") -> None:
    import time
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter

    field_name = f"Firma-{int(time.time())}"
    pdf_signer = _build_pdf_signer(signer, field_name, reason, location,
                                   visible, page, src_path, position, leyenda)
    if progress_cb:
        progress_cb("🖋 Firmando PDF...")
    with open(src_path, "rb") as inf:
        writer = IncrementalPdfFileWriter(inf)
        with open(dst_path, "wb") as outf:
            pdf_signer.sign_pdf(writer, output=outf)


def sign_pdf_pfx(src_path: str, dst_path: str, pfx_path: str, password: str,
                 reason: str = "", location: str = "",
                 visible: bool = True, page: int = 0,
                 progress_cb: Optional[Callable] = None,
                 position: str = SIGN_POSITION_DEFAULT,
                 leyenda: str = "") -> None:
    """Firma digital PAdES con certificado en archivo .pfx / .p12."""
    if not is_signing_available():
        raise RuntimeError("Falta el paquete 'pyhanko' (pip install pyhanko).")
    from pyhanko.sign import signers

    if progress_cb:
        progress_cb("🖋 Cargando certificado...")
    try:
        signer = signers.SimpleSigner.load_pkcs12(
            pfx_file=pfx_path,
            passphrase=password.encode("utf-8") if password else None,
        )
    except Exception as e:
        raise RuntimeError(
            f"No se pudo abrir el certificado (¿contraseña incorrecta?): {e}"
        ) from e
    if signer is None:
        raise RuntimeError(
            "No se pudo cargar el certificado. Verificá el archivo y la contraseña."
        )
    _do_sign(src_path, dst_path, signer, reason, location,
             visible, page, progress_cb, position, leyenda)


def resolve_token_dll(dll_path: str = "") -> str:
    """Devuelve la DLL PKCS#11 a usar; si no se indicó ninguna, la detecta.

    Así el usuario final no tiene que saber qué es una DLL: sólo enchufa el
    token. Si no hay forma de resolverla, explica en castellano qué falta.
    """
    dll_path = (dll_path or "").strip()
    if dll_path:
        if not os.path.isfile(dll_path):
            raise RuntimeError(f"No existe la DLL del token: {dll_path}")
        return dll_path

    modulos = find_pkcs11_modules()
    if modulos:
        # La primera de la lista puede ser la de otra marca (un middleware
        # viejo que quedó instalado): hay que quedarse con la que ve el token.
        dll_ok, _ = find_token_module(modulos)
        if dll_ok:
            return dll_ok
        diag = diagnose_token()
        if diag["estado"] in ("driver_otra_marca", "sin_token"):
            raise RuntimeError(f"{diag['titulo']}.\n\n{diag['mensaje']}")
        return modulos[0]

    diag = diagnose_token()
    raise RuntimeError(f"{diag['titulo']}.\n\n{diag['mensaje']}")


def find_token_module(modulos: Optional[List[str]] = None
                      ) -> Tuple[str, List[Dict]]:
    """Devuelve (dll, slots) de la primera DLL que VE un token puesto.

    Si ninguna lo ve, devuelve ("", []). Se prueba abriendo cada módulo y
    pidiéndole los slots con token: es la única prueba que no depende de la
    marca. Con un token puesto tarda milisegundos por DLL.
    """
    if modulos is None:
        modulos = find_pkcs11_modules()
    for dll in modulos:
        try:
            slots = list_token_slots(dll)
        except Exception:
            continue  # DLL de otra marca o middleware roto: se sigue
        if slots:
            return dll, slots
    return "", []


def list_token_slots(dll_path: str) -> List[Dict]:
    """Slots del módulo PKCS#11 que tienen un token puesto.

    Casi todos los middlewares publican varios slots vacíos además del real
    (SafeNet publica 8 y sólo uno tiene el token). Devuelve sólo los que
    tienen token, con el índice que espera pyhanko.
    """
    import pkcs11 as p11

    lib = p11.lib(dll_path)
    encontrados: List[Dict] = []
    # El índice es la posición en get_slots(), que es lo que usa pyhanko
    for indice, slot in enumerate(lib.get_slots()):
        try:
            token = slot.get_token()
        except Exception:
            continue  # slot vacío: es lo normal en la mayoría
        try:
            serie = token.serial.decode("utf-8", "replace").strip()
        except Exception:
            serie = ""
        encontrados.append({
            "slot_no": indice,
            "slot_id": getattr(slot, "slot_id", indice),
            "descripcion": (slot.slot_description or "").strip(),
            "etiqueta": (token.label or "").strip(),
            "serie": serie,
        })
    return encontrados


def _resolve_token_slot(dll_path: str, etiqueta: str = "") -> Tuple[int, str]:
    """Elige el slot donde está el token. Devuelve (slot_no, etiqueta).

    Sin esto, pyhanko falla con «Module has more than 1 slot; slot index or
    token criteria must be provided» cuando el middleware publica slots de
    sobra, que es lo habitual.
    """
    try:
        slots = list_token_slots(dll_path)
    except Exception as e:
        raise RuntimeError(
            "No pude comunicarme con el programa del token.\n"
            f"Detalle: {e}") from e

    if not slots:
        raise RuntimeError(
            "No hay ningún token puesto. El programa del token está "
            "instalado, pero el token no está enchufado o no hace contacto: "
            "sacalo, volvé a ponerlo y probá de nuevo.")

    etiqueta = (etiqueta or "").strip()
    if etiqueta:
        for s in slots:
            if s["etiqueta"].lower() == etiqueta.lower():
                return s["slot_no"], s["etiqueta"]
        nombres = ", ".join(f"«{s['etiqueta']}»" for s in slots)
        raise RuntimeError(
            f"No encontré un token llamado «{etiqueta}». "
            f"Los que hay puestos son: {nombres}.")

    if len(slots) > 1:
        # Varios tokens a la vez: se usa el primero, pero conviene avisar
        nombres = ", ".join(f"«{s['etiqueta']}»" for s in slots)
        _log_multiples_tokens(nombres)

    return slots[0]["slot_no"], slots[0]["etiqueta"]


# Las excepciones de python-pkcs11 vienen SIN texto: str(e) es "". Sin este
# mapeo el usuario ve "Detalle:" vacío y no hay forma de saber qué pasó.
_ERRORES_TOKEN = {
    "PinIncorrect": (
        "El PIN es incorrecto.\n\n"
        "Cuidado: si lo errás varias veces seguidas el token se bloquea y hay "
        "que desbloquearlo con el código PUK o volver al organismo que lo "
        "emitió."),
    "PinInvalid": (
        "El PIN tiene caracteres que el token no acepta."),
    "PinLenRange": (
        "El PIN es demasiado corto o demasiado largo para este token. "
        "Fijate de haberlo escrito completo."),
    "PinLocked": (
        "El token está BLOQUEADO por haber errado el PIN demasiadas veces.\n\n"
        "Hay que desbloquearlo con el código PUK desde el programa del "
        "fabricante, o llevarlo al organismo que lo emitió."),
    "PinExpired": (
        "El PIN venció y hay que cambiarlo desde el programa del fabricante "
        "antes de poder firmar."),
    "UserPinNotInitialized": (
        "El token todavía no tiene PIN de usuario configurado. Configuralo "
        "desde el programa del fabricante."),
    "UserAlreadyLoggedIn": (
        "El token ya tiene una sesión abierta, probablemente desde otro "
        "programa. Cerrá el resto de los programas que usen el token "
        "(el del fabricante, el navegador, el firmador oficial) y probá de "
        "nuevo."),
    "SessionCount": (
        "El token no acepta más sesiones abiertas a la vez. Cerrá los otros "
        "programas que lo estén usando y probá de nuevo."),
    "TokenNotPresent": (
        "El token dejó de estar disponible. Sacalo, volvé a enchufarlo y "
        "probá de nuevo."),
    "DeviceRemoved": (
        "Se desconectó el token en el medio de la operación. Volvé a "
        "enchufarlo y probá de nuevo."),
    "DeviceError": (
        "El token devolvió un error de dispositivo. Sacalo, volvé a "
        "enchufarlo y, si sigue, probá en otro puerto USB."),
    "FunctionFailed": (
        "El programa del token rechazó la operación. Suele arreglarse "
        "sacando y volviendo a poner el token; si sigue, reiniciá la "
        "computadora."),
    "GeneralError": (
        "El programa del token devolvió un error general. Sacá el token, "
        "volvé a ponerlo y, si sigue, reiniciá la computadora."),
}


def token_pin_status(dll_path: str) -> Dict:
    """Estado del PIN según las banderas del token.

    Las banderas encendidas son confiables (si dice BLOQUEADO, está
    bloqueado). Las apagadas NO prueban nada: SafeNet deja
    USER_PIN_COUNT_LOW apagado aunque haya intentos fallidos. El contador
    real sólo lo muestra la herramienta del fabricante.
    """
    estado = {"leido": False, "fallos_previos": False, "ultimo_intento": False,
              "bloqueado": False, "debe_cambiar": False}
    try:
        import pkcs11 as p11
        from pkcs11.constants import TokenFlag

        lib = p11.lib(dll_path)
        for slot in lib.get_slots():
            try:
                token = slot.get_token()
            except Exception:
                continue
            flags = int(token.flags)
            estado.update({
                "leido": True,
                "fallos_previos": bool(flags & int(TokenFlag.USER_PIN_COUNT_LOW)),
                "ultimo_intento": bool(flags & int(TokenFlag.USER_PIN_FINAL_TRY)),
                "bloqueado": bool(flags & int(TokenFlag.USER_PIN_LOCKED)),
                "debe_cambiar": bool(
                    flags & int(TokenFlag.USER_PIN_TO_BE_CHANGED)),
            })
            break
    except Exception:
        pass
    return estado


def _explicar_error_token(e: Exception, dll_path: str = "",
                          estado_previo: Optional[Dict] = None) -> str:
    """Convierte una excepción PKCS#11 muda en algo que se entienda.

    `estado_previo` es lo que decía el token ANTES del intento. Comparándolo
    con lo que dice después se sabe con certeza si el fallo consumió un
    intento de PIN, que es la única forma de distinguir "PIN equivocado" de
    "otro problema" sin quemar intentos a ciegas.
    """
    nombre = type(e).__name__
    detalle = str(e).strip()

    partes = [_ERRORES_TOKEN.get(
        nombre,
        "No se pudo completar la operación con el token.")]

    if dll_path:
        despues = token_pin_status(dll_path)
        antes = estado_previo or {}
        if despues["leido"]:
            if despues["bloqueado"]:
                partes.append(
                    "⛔ El token informa que el PIN quedó BLOQUEADO. "
                    "No sigas probando: hay que desbloquearlo con el PUK.")
            elif despues["ultimo_intento"]:
                partes.append(
                    "⚠ El token avisa que queda UN SOLO INTENTO antes de "
                    "bloquearse. No pruebes más PINes al azar: si no estás "
                    "seguro, consultá al organismo que te dio el token.")
            elif despues["fallos_previos"] and not antes.get("fallos_previos"):
                partes.append(
                    "El token registró un intento de PIN fallido recién "
                    "ahora: entonces sí, el PIN estaba equivocado.")

    # OJO: la ausencia de esas banderas NO prueba que el PIN esté bien.
    # Verificado el 4-ago-2026 con un SafeNet eToken: falló un intento, el
    # contador del fabricante bajó de 15 a 14 y USER_PIN_COUNT_LOW siguió
    # apagado. Varios middlewares no mantienen esa bandera. Por eso acá no
    # se afirma nunca "no es el PIN": se manda a mirar el contador real.
    if nombre in ("PinIncorrect", "FunctionFailed", "GeneralError"):
        partes.append(
            "IMPORTANTE: cada intento fallido gasta uno de los reintentos "
            "del token, y agotarlos lo bloquea. No pruebes PINes al azar.\n\n"
            "Para ver cuántos te quedan de verdad, abrí el programa del "
            "fabricante (para SafeNet: «SafeNet Authentication Client "
            "Tools») y mirá el número de reintentos restantes. Ese contador "
            "es el único confiable.")

    # Siempre dejar rastro técnico: sin esto el detalle queda vacío
    tecnico = f"{nombre}" + (f": {detalle}" if detalle else "")
    partes.append(f"(Código técnico: {tecnico})")
    return "\n\n".join(partes)


def _log_multiples_tokens(nombres: str) -> None:
    """Punto único para avisar que hay más de un token puesto."""
    try:
        import logging
        logging.getLogger(__name__).info(
            "Hay más de un token conectado (%s); se usa el primero.", nombres)
    except Exception:
        pass


def _build_token_signer(session, cert_label: str = "",
                        progress_cb: Optional[Callable] = None):
    """Arma el firmante emparejando certificado y clave privada por CKA_ID.

    Si a pyhanko sólo se le pasa `cert_label`, busca la clave privada con esa
    misma etiqueta. En SafeNet (y en varios otros) la clave tiene una
    etiqueta distinta de la del certificado, y falla con
    «Could not find private key with label ...».

    El vínculo correcto en PKCS#11 es el atributo CKA_ID, que el certificado
    y su clave comparten por definición. Además el CKA_ID del certificado se
    puede leer sin PIN, así que sirve aunque la clave esté oculta.
    """
    from pyhanko.sign import pkcs11 as sign_pkcs11
    import pkcs11 as p11

    buscado = (cert_label or "").strip()

    try:
        certs = list(session.get_objects({
            p11.Attribute.CLASS: p11.ObjectClass.CERTIFICATE,
        }))
    except Exception:
        certs = []

    elegido = None
    etiqueta = ""
    etiquetas = []
    for cert in certs:
        try:
            actual = cert[p11.Attribute.LABEL]
        except Exception:
            actual = ""
        etiquetas.append(actual)
        if not buscado or actual == buscado:
            elegido, etiqueta = cert, actual
            break

    if buscado and elegido is None:
        disponibles = ", ".join(f"«{e}»" for e in etiquetas if e) or "ninguno"
        raise RuntimeError(
            f"El token no tiene un certificado llamado «{buscado}».\n\n"
            f"Los que tiene son: {disponibles}.\n\n"
            "Dejá vacío el campo «Certificado» en Opciones avanzadas para "
            "que se use el primero automáticamente.")

    if elegido is None:
        raise RuntimeError(
            "El token abrió correctamente pero no tiene ningún certificado "
            "adentro. Consultá al organismo que te lo entregó.")

    if progress_cb and etiqueta:
        progress_cb(f"🖋 Certificado: {etiqueta}")

    try:
        cka_id = bytes(elegido[p11.Attribute.ID])
    except Exception:
        cka_id = b""

    if cka_id:
        # Camino normal: por CKA_ID, que es como se emparejan de verdad
        return sign_pkcs11.PKCS11Signer(session, cert_id=cka_id,
                                        key_id=cka_id)

    # Sin CKA_ID no queda otra que confiar en la etiqueta
    if progress_cb:
        progress_cb("🖋 El certificado no tiene CKA_ID: se usa la etiqueta.")
    return sign_pkcs11.PKCS11Signer(session, cert_label=etiqueta or None)


def sign_pdf_token(src_path: str, dst_path: str, dll_path: str = "", pin: str = "",
                   cert_label: str = "", reason: str = "", location: str = "",
                   visible: bool = True, page: int = 0,
                   progress_cb: Optional[Callable] = None,
                   position: str = SIGN_POSITION_DEFAULT,
                   leyenda: str = "") -> None:
    """Firma digital PAdES con token USB vía PKCS#11.

    `dll_path`: la librería PKCS#11 del fabricante del token
    (p. ej. eTPKCS11.dll para SafeNet eToken).
    `cert_label`: etiqueta del certificado dentro del token; si se omite,
    se usa el primero que haya.
    """
    if not is_signing_available():
        raise RuntimeError("Falta el paquete 'pyhanko' (pip install pyhanko).")

    dll_path = resolve_token_dll(dll_path)

    from pyhanko.sign import pkcs11 as sign_pkcs11

    if progress_cb:
        progress_cb("🖋 Conectando con el token (puede pedir unos segundos)...")
    slot_no, etiqueta_token = _resolve_token_slot(dll_path)
    if progress_cb and etiqueta_token:
        progress_cb(f"🖋 Token: {etiqueta_token}")
    estado_previo = token_pin_status(dll_path)
    try:
        session = sign_pkcs11.open_pkcs11_session(
            dll_path, slot_no=slot_no, user_pin=pin or None)
    except Exception as e:
        raise RuntimeError(
            "No se pudo abrir el token.\n\n"
            + _explicar_error_token(e, dll_path, estado_previo)) from e

    try:
        signer = _build_token_signer(session, cert_label, progress_cb)
        _do_sign(src_path, dst_path, signer, reason, location,
                 visible, page, progress_cb, position, leyenda)
    finally:
        try:
            session.close()
        except Exception:
            pass


def _describe_certificate(der: bytes) -> Dict[str, str]:
    """Extrae titular / emisor / vencimiento de un certificado DER."""
    info: Dict[str, str] = {}
    try:
        from asn1crypto import x509
        cert = x509.Certificate.load(der)
        subject = cert.subject.native or {}
        issuer = cert.issuer.native or {}
        info["titular"] = str(subject.get("common_name") or
                              subject.get("organization_name") or "?")
        info["emisor"] = str(issuer.get("common_name") or
                             issuer.get("organization_name") or "?")
        validity = cert["tbs_certificate"]["validity"]
        info["desde"] = validity["not_before"].native.strftime("%d/%m/%Y")
        info["hasta"] = validity["not_after"].native.strftime("%d/%m/%Y")
        import datetime
        ahora = datetime.datetime.now(datetime.timezone.utc)
        info["vencido"] = "sí" if validity["not_after"].native < ahora else "no"
    except Exception as e:
        info["error"] = f"no se pudo leer el certificado ({e})"
    return info


def probe_token(dll_path: str = "", pin: str = "",
                progress_cb: Optional[Callable] = None) -> Dict:
    """Abre el token y lista sus certificados SIN firmar nada.

    Sirve para verificar antes de firmar que el driver es el correcto, que el
    PIN funciona y con qué etiqueta figura el certificado dentro del token.
    Devuelve un dict con la info encontrada (clave `token_probe`).
    """
    if not is_signing_available():
        raise RuntimeError("Falta el paquete 'pyhanko' (pip install pyhanko).")

    dll_path = resolve_token_dll(dll_path)

    from pyhanko.sign import pkcs11 as sign_pkcs11

    if progress_cb:
        progress_cb("🔍 Buscando en qué slot está el token...")
    slot_no, etiqueta_token = _resolve_token_slot(dll_path)
    if progress_cb:
        progress_cb(f"🔍 Token encontrado: {etiqueta_token or '(sin nombre)'}"
                    f" — abriendo sesión...")
    estado_previo = token_pin_status(dll_path)
    try:
        session = sign_pkcs11.open_pkcs11_session(
            dll_path, slot_no=slot_no, user_pin=pin or None)
    except Exception as e:
        raise RuntimeError(
            "El token está puesto y lo encontré, pero no pude abrirlo.\n\n"
            + _explicar_error_token(e, dll_path, estado_previo)) from e

    resultado: Dict = {
        "token_probe": True,
        "dll": dll_path,
        "con_pin": bool(pin),
        "token": {},
        "certificados": [],
        "claves": [],
    }
    try:
        # Datos del token
        try:
            tok = session.token

            def _texto(valor) -> str:
                """El serial viene en bytes; sin esto se imprime b'028878d5'."""
                if isinstance(valor, (bytes, bytearray)):
                    return valor.decode("utf-8", "replace").strip()
                return str(valor or "").strip()

            resultado["token"] = {
                "etiqueta": _texto(getattr(tok, "label", "")),
                "fabricante": _texto(getattr(tok, "manufacturer_id", "")),
                "modelo": _texto(getattr(tok, "model", "")),
                "serie": _texto(getattr(tok, "serial", "")),
            }
        except Exception:
            pass

        import pkcs11 as p11

        if progress_cb:
            progress_cb("🔍 Leyendo certificados del token...")
        try:
            objetos = list(session.get_objects({
                p11.Attribute.CLASS: p11.ObjectClass.CERTIFICATE,
            }))
        except Exception as e:
            raise RuntimeError(
                f"El token abrió pero no se pudieron listar certificados: {e}"
            ) from e

        for obj in objetos:
            entrada: Dict[str, str] = {}
            try:
                entrada["etiqueta"] = str(obj[p11.Attribute.LABEL] or "")
            except Exception:
                entrada["etiqueta"] = ""
            try:
                der = obj[p11.Attribute.VALUE]
                if der:
                    entrada.update(_describe_certificate(bytes(der)))
            except Exception as e:
                entrada["error"] = f"no se pudo leer el certificado ({e})"
            resultado["certificados"].append(entrada)

        # Claves privadas (solo visibles con PIN en la mayoría de los tokens)
        try:
            for obj in session.get_objects({
                p11.Attribute.CLASS: p11.ObjectClass.PRIVATE_KEY,
            }):
                try:
                    resultado["claves"].append(str(obj[p11.Attribute.LABEL] or ""))
                except Exception:
                    resultado["claves"].append("(sin etiqueta)")
        except Exception:
            pass

        return resultado
    finally:
        try:
            session.close()
        except Exception:
            pass


def format_token_probe(info: Dict) -> str:
    """Convierte el resultado de `probe_token` en un informe legible."""
    lineas: List[str] = []
    tok = info.get("token") or {}
    datos = [f"{k.capitalize()}: {v}" for k, v in tok.items() if v]
    if datos:
        lineas.append("TOKEN\n  " + "\n  ".join(datos))

    certs = info.get("certificados") or []
    if not certs:
        lineas.append(
            "CERTIFICADOS\n  Ninguno visible."
            + ("" if info.get("con_pin") else
               "\n  Probá de nuevo escribiendo el PIN: muchos tokens ocultan\n"
               "  los certificados hasta que se inicia sesión."))
    else:
        bloques = []
        for i, c in enumerate(certs, start=1):
            etiqueta = c.get("etiqueta") or "(sin etiqueta)"
            det = [f"  {i}. Etiqueta: {etiqueta}"]
            if c.get("error"):
                det.append(f"     {c['error']}")
            else:
                det.append(f"     Titular : {c.get('titular', '?')}")
                det.append(f"     Emisor  : {c.get('emisor', '?')}")
                det.append(f"     Vigencia: {c.get('desde', '?')} → "
                           f"{c.get('hasta', '?')}"
                           + ("  ⚠ VENCIDO" if c.get("vencido") == "sí" else ""))
            bloques.append("\n".join(det))
        lineas.append(f"CERTIFICADOS ({len(certs)})\n" + "\n".join(bloques))

    claves = info.get("claves") or []
    if claves:
        lineas.append("CLAVES PRIVADAS\n  " + "\n  ".join(claves))
    elif info.get("con_pin"):
        lineas.append("CLAVES PRIVADAS\n  Ninguna visible (¿PIN sin permisos "
                      "de firma?).")

    if certs and info.get("con_pin") and claves:
        lineas.append("✅ El token está listo para firmar.")
    elif certs and not info.get("con_pin"):
        lineas.append("ℹ Se leyó el token sin PIN. Para confirmar que podés "
                      "firmar, probá otra vez con el PIN.")

    return "\n\n".join(lineas)
