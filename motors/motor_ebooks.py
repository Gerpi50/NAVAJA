"""
motor_ebooks.py — Conversión de libros electrónicos.
Motores:
  - Calibre (ebook-convert.exe) si está instalado: epub↔mobi/azw3 con máxima calidad.
  - 'mobi' (KindleUnpack, puro Python): mobi/azw3 → epub sin Calibre.
  - Writer EPUB propio (puro Python): pdf → epub.
"""
import os
import shutil
import subprocess

from core.graph import BaseMotor
from core.paths import BIN_DIR


def _calibre_path():
    candidates = [
        os.path.join(BIN_DIR, "ebook-convert.exe"),
        shutil.which("ebook-convert"),
        r"C:\Program Files\Calibre2\ebook-convert.exe",
        r"C:\Program Files (x86)\Calibre2\ebook-convert.exe",
    ]
    for c in candidates:
        if c and os.path.isfile(c):
            return c
    return None


# ---------------------------------------------------------------------------
# Calibre — el mejor conversor de ebooks (si está instalado)
# ---------------------------------------------------------------------------

class CalibreMotor(BaseMotor):
    NAME = "Calibre"
    CONVERSIONS = [
        ("epub", "mobi"), ("epub", "azw3"), ("epub", "pdf"), ("epub", "txt"),
        ("mobi", "epub"), ("azw3", "epub"),
        ("pdf", "epub"),
    ]

    @classmethod
    def is_available(cls) -> bool:
        return _calibre_path() is not None

    def convert(self, src_path, dst_path, src_ext, dst_ext,
                progress_cb=None, **kwargs):
        if progress_cb:
            progress_cb("📚 Convirtiendo con Calibre...")
        result = subprocess.run(
            [_calibre_path(), src_path, dst_path],
            capture_output=True, text=True, timeout=600,
        )
        if result.returncode != 0 or not os.path.exists(dst_path):
            raise RuntimeError(f"Calibre error: {result.stderr[-400:]}")


# ---------------------------------------------------------------------------
# mobi/azw3 → epub sin Calibre (paquete 'mobi' = KindleUnpack)
# ---------------------------------------------------------------------------

class MobiUnpackMotor(BaseMotor):
    NAME = "MobiUnpack"
    CONVERSIONS = [
        ("mobi", "epub"), ("azw3", "epub"),
    ]

    @classmethod
    def is_available(cls) -> bool:
        try:
            import mobi  # noqa: F401
            return True
        except ImportError:
            return False

    def convert(self, src_path, dst_path, src_ext, dst_ext,
                progress_cb=None, **kwargs):
        import glob
        import mobi
        if progress_cb:
            progress_cb("📚 Desempaquetando Kindle → EPUB...")
        tempdir, extracted = mobi.extract(src_path)
        try:
            if extracted and extracted.lower().endswith(".epub"):
                shutil.copyfile(extracted, dst_path)
                return
            # buscar el epub generado dentro del tempdir
            hits = glob.glob(os.path.join(tempdir, "**", "*.epub"), recursive=True)
            if hits:
                shutil.copyfile(hits[0], dst_path)
                return
            raise RuntimeError(
                "No se pudo generar EPUB desde este archivo Kindle "
                "(posiblemente tiene DRM o es un formato antiguo). "
                "Con Calibre instalado la conversión mejora."
            )
        finally:
            shutil.rmtree(tempdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# pdf → epub puro Python (texto extraído con PyMuPDF, EPUB armado a mano)
# ---------------------------------------------------------------------------

_CONTAINER_XML = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>"""


def _xhtml_page(title: str, body_html: str) -> str:
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<!DOCTYPE html>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml">\n'
        f"<head><title>{title}</title></head>\n"
        f"<body>{body_html}</body>\n</html>"
    )


class PdfToEpubMotor(BaseMotor):
    """Extrae el texto del PDF (una sección por página) y arma un EPUB 3
    mínimo válido. Para PDFs escaneados sin texto usar antes OCR."""
    NAME = "PDF→EPUB"
    CONVERSIONS = [
        ("pdf", "epub"),
    ]

    @classmethod
    def is_available(cls) -> bool:
        try:
            import fitz  # noqa: F401
            return True
        except ImportError:
            return False

    def convert(self, src_path, dst_path, src_ext, dst_ext,
                progress_cb=None, **kwargs):
        import html as html_mod
        import uuid
        import zipfile

        import fitz

        title = os.path.splitext(os.path.basename(src_path))[0]
        book_id = f"urn:uuid:{uuid.uuid4()}"

        doc = fitz.open(src_path)
        try:
            pages = []
            total = doc.page_count
            for i, page in enumerate(doc):
                if progress_cb and (i % 20 == 0):
                    progress_cb(f"📚 EPUB: página {i+1}/{total}...")
                text = page.get_text("text").strip()
                paras = [
                    f"<p>{html_mod.escape(p)}</p>"
                    for p in text.split("\n\n") if p.strip()
                ] or ["<p></p>"]
                pages.append("\n".join(paras))
        finally:
            doc.close()

        if not any(p != "<p></p>" for p in pages):
            raise RuntimeError(
                "El PDF no tiene texto extraíble (¿escaneado?). "
                "Usá primero OCR → PDF buscable y convertí ese resultado."
            )

        manifest, spine = [], []
        for i in range(len(pages)):
            manifest.append(
                f'<item id="p{i}" href="page{i:04d}.xhtml" '
                'media-type="application/xhtml+xml"/>'
            )
            spine.append(f'<itemref idref="p{i}"/>')

        opf = (
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" '
            'unique-identifier="bookid">\n'
            '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">\n'
            f'<dc:identifier id="bookid">{book_id}</dc:identifier>\n'
            f"<dc:title>{html_mod.escape(title)}</dc:title>\n"
            "<dc:language>es</dc:language>\n"
            '<meta property="dcterms:modified">2026-01-01T00:00:00Z</meta>\n'
            "</metadata>\n"
            f'<manifest>{"".join(manifest)}'
            '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" '
            'properties="nav"/></manifest>\n'
            f'<spine>{"".join(spine)}</spine>\n'
            "</package>"
        )

        nav = _xhtml_page(
            title,
            '<nav epub:type="toc" xmlns:epub="http://www.idpf.org/2007/ops">'
            f'<ol><li><a href="page0000.xhtml">{html_mod.escape(title)}</a></li></ol></nav>',
        )

        with zipfile.ZipFile(dst_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # mimetype debe ir primero y SIN comprimir (spec EPUB)
            zf.writestr("mimetype", "application/epub+zip",
                        compress_type=zipfile.ZIP_STORED)
            zf.writestr("META-INF/container.xml", _CONTAINER_XML)
            zf.writestr("OEBPS/content.opf", opf)
            zf.writestr("OEBPS/nav.xhtml", nav)
            for i, body in enumerate(pages):
                zf.writestr(f"OEBPS/page{i:04d}.xhtml",
                            _xhtml_page(f"Página {i+1}", body))
