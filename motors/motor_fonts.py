"""
motor_fonts.py — Conversión entre formatos de fuentes tipográficas.
Motor: fontTools (puro Python; woff2 requiere brotli).
Soporta: TTF, OTF, WOFF, WOFF2
"""
from core.graph import BaseMotor


def _has_brotli() -> bool:
    try:
        import brotli  # noqa: F401
        return True
    except ImportError:
        return False


class FontMotor(BaseMotor):
    NAME = "fontTools"
    CONVERSIONS = [
        ("ttf", "otf"),  ("ttf", "woff"), ("ttf", "woff2"),
        ("otf", "ttf"),  ("otf", "woff"),
        ("woff", "ttf"), ("woff2", "ttf"),
    ]

    @classmethod
    def is_available(cls) -> bool:
        try:
            import fontTools  # noqa: F401
            return True
        except ImportError:
            return False

    # ------------------------------------------------------------------
    @staticmethod
    def _otf_to_ttf(font):
        """CFF (curvas cúbicas) → glyf (cuadráticas) con cu2qu."""
        from fontTools.pens.cu2quPen import Cu2QuPen
        from fontTools.pens.ttGlyphPen import TTGlyphPen
        from fontTools.ttLib import newTable

        glyph_order = font.getGlyphOrder()
        glyf_glyphs = {}
        glyph_set = font.getGlyphSet()
        for name in glyph_order:
            pen = TTGlyphPen(glyph_set)
            cu2qu = Cu2QuPen(pen, max_err=1.0, reverse_direction=True)
            glyph_set[name].draw(cu2qu)
            glyf_glyphs[name] = pen.glyph()

        glyf = newTable("glyf")
        glyf.glyphOrder = glyph_order
        glyf.glyphs = glyf_glyphs

        loca = newTable("loca")
        font["loca"] = loca
        font["glyf"] = glyf

        maxp = font["maxp"]
        maxp.tableVersion = 0x00010000
        for attr in ("maxZones", "maxTwilightPoints", "maxStorage",
                     "maxFunctionDefs", "maxInstructionDefs",
                     "maxStackElements", "maxSizeOfInstructions",
                     "maxComponentElements"):
            setattr(maxp, attr, 0)

        post = font["post"]
        post.formatType = 2.0
        post.extraNames = []
        post.mapping = {}
        post.glyphOrder = glyph_order

        for tag in ("CFF ", "CFF2", "VORG"):
            if tag in font:
                del font[tag]
        font.sfntVersion = "\x00\x01\x00\x00"
        # recalcular bounding boxes al guardar
        font.recalcBBoxes = True
        return font

    # ------------------------------------------------------------------
    def convert(self, src_path, dst_path, src_ext, dst_ext, **kwargs):
        from fontTools.ttLib import TTFont

        if dst_ext == "woff2" and not _has_brotli():
            raise RuntimeError(
                "WOFF2 requiere el paquete 'brotli' (pip install brotli)."
            )

        font = TTFont(src_path)
        is_cff = "CFF " in font or "CFF2" in font

        if dst_ext in ("woff", "woff2"):
            # Cambio de contenedor: conserva las curvas originales
            font.flavor = dst_ext
            font.save(dst_path)
            return

        if dst_ext == "ttf":
            if is_cff:
                font = self._otf_to_ttf(font)   # conversión real de curvas
            font.flavor = None                   # quitar envoltorio woff/woff2
            font.save(dst_path)
            return

        if dst_ext == "otf":
            # Sin qu2cu estable no se convierten las curvas: se guarda el
            # contenedor sfnt con extensión .otf (válido — OpenType admite
            # contornos TrueType). La fuente funciona igual en Windows/Mac.
            font.flavor = None
            font.save(dst_path)
            return

        raise RuntimeError(f"Destino de fuente no soportado: {dst_ext}")
