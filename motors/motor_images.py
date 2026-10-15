"""
motor_images.py — Conversión entre formatos de imagen.
Motores: Pillow, CairoSVG.
Soporta: JPG, PNG, WEBP, BMP, TIFF, GIF, ICO, ICNS, HEIC, AVIF, TGA, PDF→img, SVG
"""
import os
import shutil
from core.graph import BaseMotor


# ---------------------------------------------------------------------------
# Motor Pillow — imágenes raster
# ---------------------------------------------------------------------------

# Antes las conversiones de Pillow se escribían par por par y la lista
# quedaba coja (GIF salía a JPG pero no a TIFF, WEBP no salía a ICO…).
# Ahora se declara qué sabe LEER y qué sabe ESCRIBIR, y el producto sale
# solo: cualquier imagen va a cualquier otra en un solo paso.
PIL_READ_FMTS = [
    "png", "jpg", "jpeg", "webp", "bmp", "tiff", "tif", "gif",
    "ico", "icns", "tga", "jfif", "psd", "heic", "heif", "avif",
]
# PSD y los RAW no figuran acá: Pillow los abre pero no los escribe.
# HEIC, HEIF y AVIF salen por pillow-heif, que viene empaquetado.
PIL_WRITE_FMTS = [
    "png", "jpg", "jpeg", "webp", "bmp", "tiff", "tif", "gif",
    "ico", "icns", "tga", "jfif", "heic", "heif", "avif", "pdf",
]
PIL_CONVERSIONS = [
    (s_, d_) for s_ in PIL_READ_FMTS for d_ in PIL_WRITE_FMTS if s_ != d_
]


class PillowMotor(BaseMotor):
    NAME = "Pillow"
    CONVERSIONS = PIL_CONVERSIONS

    @classmethod
    def is_available(cls) -> bool:
        try:
            import PIL
            return True
        except ImportError:
            return False

    def convert(self, src_path, dst_path, src_ext, dst_ext, **kwargs):
        from PIL import Image

        # Intentar registrar HEIC si está disponible
        try:
            import pillow_heif
            pillow_heif.register_heif_opener()
        except ImportError:
            pass

        img = Image.open(src_path)

        # Manejar transparencia al convertir a JPG
        # JFIF es un JPEG con otro nombre: sin esto, una imagen con
        # transparencia reventaba con "cannot write mode RGBA as JPEG".
        if dst_ext in ("jpg", "jpeg", "jfif") and img.mode in ("RGBA", "LA", "P"):
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            background.paste(img, mask=img.split()[-1] if "A" in img.mode else None)
            img = background
        elif dst_ext not in ("jpg", "jpeg", "jfif", "bmp", "gif", "ico", "tga"):
            if img.mode not in ("RGB", "RGBA", "L", "LA"):
                img = img.convert("RGBA")

        save_kwargs = {}
        if dst_ext in ("jpg", "jpeg", "jfif"):
            save_kwargs["quality"] = kwargs.get("quality", 92)
            save_kwargs["optimize"] = True
        elif dst_ext == "webp":
            save_kwargs["quality"] = kwargs.get("quality", 85)
        elif dst_ext == "png":
            save_kwargs["optimize"] = True
        elif dst_ext == "pdf":
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.save(dst_path, "PDF", **save_kwargs)
            return
        elif dst_ext == "ico":
            img.save(dst_path, sizes=[(256,256),(128,128),(64,64),(32,32),(16,16)])
            return
        elif dst_ext == "icns":
            img.save(dst_path)
            return

        img.save(dst_path, **save_kwargs)


# ---------------------------------------------------------------------------
# Motor CairoSVG — SVG ↔ raster
# ---------------------------------------------------------------------------

class CairoSVGMotor(BaseMotor):
    NAME = "CairoSVG"
    CONVERSIONS = [
        ("svg", "png"), ("svg", "pdf"), ("svg", "jpg"),
        ("svg", "webp"),
    ]

    @classmethod
    def is_available(cls) -> bool:
        try:
            import cairosvg
            return True
        except Exception:
            return False

    def convert(self, src_path, dst_path, src_ext, dst_ext, **kwargs):
        try:
            import cairosvg
        except (ImportError, OSError) as e:
            raise RuntimeError(f"CairoSVG no disponible: {e}") from e
        with open(src_path, "rb") as f:
            svg_data = f.read()

        if dst_ext == "png":
            cairosvg.svg2png(bytestring=svg_data, write_to=dst_path,
                             dpi=kwargs.get("dpi", 150))
        elif dst_ext == "pdf":
            cairosvg.svg2pdf(bytestring=svg_data, write_to=dst_path)
        elif dst_ext in ("jpg", "jpeg", "webp"):
            # SVG→PNG→JPG/WEBP via Pillow
            import tempfile
            from PIL import Image
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp_path = tmp.name
            try:
                cairosvg.svg2png(bytestring=svg_data, write_to=tmp_path,
                                 dpi=kwargs.get("dpi", 150))
                img = Image.open(tmp_path).convert("RGB")
                img.save(dst_path)
            finally:
                os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# Motor SVG vía PyMuPDF — no requiere libcairo ni herramientas externas
# ---------------------------------------------------------------------------

class FitzSvgMotor(BaseMotor):
    """Renderiza SVG con MuPDF (fitz). Reemplaza a CairoSVG cuando falta
    libcairo (caso típico en Windows). También exporta EPS rasterizado
    vía Pillow (que puede ESCRIBIR EPS sin Ghostscript)."""
    NAME = "MuPDF-SVG"
    CONVERSIONS = [
        ("svg", "png"), ("svg", "jpg"), ("svg", "pdf"), ("svg", "eps"),
    ]

    @classmethod
    def is_available(cls) -> bool:
        try:
            import fitz  # noqa: F401
            return True
        except ImportError:
            return False

    def _render_pixmap(self, src_path, dpi=150):
        import fitz
        doc = fitz.open(src_path)
        try:
            page = doc[0]
            zoom = dpi / 72.0
            return page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=True)
        finally:
            doc.close()

    def convert(self, src_path, dst_path, src_ext, dst_ext, **kwargs):
        import fitz
        if dst_ext == "pdf":
            doc = fitz.open(src_path)
            try:
                pdf_bytes = doc.convert_to_pdf()
            finally:
                doc.close()
            with open(dst_path, "wb") as f:
                f.write(pdf_bytes)
            return

        pix = self._render_pixmap(src_path, dpi=kwargs.get("dpi", 150))
        if dst_ext == "png":
            pix.save(dst_path)
            return
        # jpg / eps: pasar por Pillow (sin canal alfa, fondo blanco)
        from PIL import Image
        img = Image.frombytes("RGBA", (pix.width, pix.height), pix.samples)
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[-1])
        if dst_ext == "eps":
            bg.save(dst_path, "EPS")
        else:
            bg.save(dst_path, quality=kwargs.get("quality", 92))


# ---------------------------------------------------------------------------
# Motor raster→SVG por incrustación (fallback sin potrace)
# ---------------------------------------------------------------------------

class RasterEmbedSvgMotor(BaseMotor):
    """Genera un SVG válido incrustando la imagen en base64. No vectoriza
    (para trazado real instalar potrace, que tiene prioridad al registrarse
    antes), pero produce un .svg utilizable en navegadores y editores."""
    NAME = "SVG-Embed"
    CONVERSIONS = [
        ("png", "svg"), ("jpg", "svg"), ("bmp", "svg"),
    ]

    def convert(self, src_path, dst_path, src_ext, dst_ext, **kwargs):
        import base64
        from PIL import Image
        with Image.open(src_path) as im:
            w, h = im.size
        mime = "image/png" if src_ext == "png" else \
               "image/jpeg" if src_ext in ("jpg", "jpeg") else "image/bmp"
        with open(src_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        svg = (
            f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'xmlns:xlink="http://www.w3.org/1999/xlink" '
            f'width="{w}" height="{h}" viewBox="0 0 {w} {h}">\n'
            f'  <image width="{w}" height="{h}" '
            f'xlink:href="data:{mime};base64,{b64}"/>\n'
            f'</svg>\n'
        )
        with open(dst_path, "w", encoding="utf-8") as f:
            f.write(svg)


# ---------------------------------------------------------------------------
# Motor RAW (DNG) — rawpy/libraw
# ---------------------------------------------------------------------------

class RawMotor(BaseMotor):
    NAME = "RAW (rawpy)"
    CONVERSIONS = [
        ("dng", "jpg"), ("dng", "png"),
    ]

    @classmethod
    def is_available(cls) -> bool:
        try:
            import rawpy  # noqa: F401
            return True
        except ImportError:
            return False

    def convert(self, src_path, dst_path, src_ext, dst_ext, **kwargs):
        import rawpy
        from PIL import Image
        with rawpy.imread(src_path) as raw:
            rgb = raw.postprocess()  # demosaico con parámetros por defecto
        img = Image.fromarray(rgb)
        if dst_ext == "jpg":
            img.save(dst_path, quality=kwargs.get("quality", 92))
        else:
            img.save(dst_path)


# ---------------------------------------------------------------------------
# Motor AI (Adobe Illustrator) — la gran mayoría de los .ai modernos son
# PDF-compatibles, así que MuPDF los abre directamente.
# ---------------------------------------------------------------------------

class AiFitzMotor(BaseMotor):
    NAME = "MuPDF-AI"
    CONVERSIONS = [
        ("ai", "pdf"), ("ai", "png"),
    ]

    @classmethod
    def is_available(cls) -> bool:
        try:
            import fitz  # noqa: F401
            return True
        except ImportError:
            return False

    def convert(self, src_path, dst_path, src_ext, dst_ext, **kwargs):
        import fitz
        try:
            doc = fitz.open(src_path, filetype="pdf")
        except Exception as e:
            raise RuntimeError(
                "Este .ai no es PDF-compatible (guardado sin la opción "
                "'Create PDF Compatible File' de Illustrator). "
                f"Detalle: {e}"
            ) from e
        try:
            if dst_ext == "pdf":
                doc.save(dst_path)
            else:
                zoom = kwargs.get("dpi", 150) / 72.0
                pix = doc[0].get_pixmap(matrix=fitz.Matrix(zoom, zoom))
                pix.save(dst_path)
        finally:
            doc.close()


# ---------------------------------------------------------------------------
# Motor Ghostscript — EPS (PostScript real necesita gs)
# ---------------------------------------------------------------------------

def _ghostscript_path():
    for name in ("gswin64c", "gswin32c", "gs"):
        found = shutil.which(name)
        if found:
            return found
    import glob
    for pat in (r"C:\Program Files\gs\gs*\bin\gswin64c.exe",
                r"C:\Program Files (x86)\gs\gs*\bin\gswin32c.exe"):
        hits = sorted(glob.glob(pat))
        if hits:
            return hits[-1]
    return None


class GhostscriptEpsMotor(BaseMotor):
    NAME = "Ghostscript-EPS"
    CONVERSIONS = [
        ("eps", "pdf"), ("eps", "png"),
    ]

    @classmethod
    def is_available(cls) -> bool:
        return _ghostscript_path() is not None

    def convert(self, src_path, dst_path, src_ext, dst_ext, **kwargs):
        import subprocess
        gs = _ghostscript_path()
        device = "pdfwrite" if dst_ext == "pdf" else "png16m"
        cmd = [gs, "-dSAFER", "-dBATCH", "-dNOPAUSE", "-dEPSCrop",
               f"-sDEVICE={device}"]
        if dst_ext == "png":
            cmd.append(f"-r{kwargs.get('dpi', 150)}")
        cmd += [f"-sOutputFile={dst_path}", src_path]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(f"Ghostscript error: {result.stderr[-400:]}")


# ---------------------------------------------------------------------------
# Motor PNG→SVG (potrace)
# ---------------------------------------------------------------------------

class PotraceMotor(BaseMotor):
    NAME = "Potrace"
    CONVERSIONS = [
        ("png", "svg"), ("jpg", "svg"), ("bmp", "svg"),
    ]

    @classmethod
    def is_available(cls) -> bool:
        return shutil.which("potrace") is not None

    def convert(self, src_path, dst_path, src_ext, dst_ext, **kwargs):
        import subprocess, tempfile
        from PIL import Image
        # Convertir a BMP primero (potrace trabaja con BMP)
        with tempfile.NamedTemporaryFile(suffix=".bmp", delete=False) as tmp:
            tmp_bmp = tmp.name
        try:
            img = Image.open(src_path).convert("L")
            img.save(tmp_bmp)
            subprocess.run(
                ["potrace", "--svg", "-o", dst_path, tmp_bmp],
                check=True, capture_output=True
            )
        finally:
            os.unlink(tmp_bmp)
