# -*- coding: utf-8 -*-
"""
Escritor de documentos ODT (OpenDocument Text) generados a mano.

Se construye el paquete ODF directamente (zip + XML) en lugar de usar una
libreria de alto nivel para tener control absoluto sobre:

  * la fuente (Arial 12) y el interlineado (doble por defecto),
  * el idioma del texto (es-AR) fijado en el estilo predeterminado y en cada
    estilo derivado, de modo que LibreOffice/Word no marquen todo el informe
    como "para corregir" con un diccionario equivocado,
  * la insercion de imagenes con tamano exacto en centimetros.
"""

from __future__ import annotations

import os
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from xml.sax.saxutils import escape

try:
    from PIL import Image
except ImportError:  # pragma: no cover - Pillow viene instalado
    Image = None


CM_PER_INCH = 2.54

NAMESPACES = (
    'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
    'xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0" '
    'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
    'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" '
    'xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0" '
    'xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0" '
    'xmlns:xlink="http://www.w3.org/1999/xlink" '
    'xmlns:dc="http://purl.org/dc/elements/1.1/" '
    'xmlns:meta="urn:oasis:names:tc:opendocument:xmlns:meta:1.0" '
    'xmlns:number="urn:oasis:names:tc:opendocument:xmlns:datastyle:1.0" '
    'xmlns:svg="urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0" '
    'xmlns:chart="urn:oasis:names:tc:opendocument:xmlns:chart:1.0" '
    'xmlns:dr3d="urn:oasis:names:tc:opendocument:xmlns:dr3d:1.0" '
    'xmlns:math="http://www.w3.org/1998/Math/MathML" '
    'xmlns:form="urn:oasis:names:tc:opendocument:xmlns:form:1.0" '
    'xmlns:script="urn:oasis:names:tc:opendocument:xmlns:script:1.0" '
    'xmlns:ooo="http://openoffice.org/2004/office" '
    'xmlns:loext="urn:org:documentfoundation:names:experimental:office:xmlns:loext:1.0"'
)

# Atributos de idioma. Se declaran tambien para asiatico y complejo como
# "sin idioma" (zxx/none) para que el corrector no intente revisar con otro
# diccionario y deje el documento lleno de subrayados rojos.
LANG_ATTRS = (
    'fo:language="es" fo:country="AR" '
    'style:language-asian="zxx" style:country-asian="none" '
    'style:language-complex="zxx" style:country-complex="none"'
)


def _fmt_pt(size_pt: float) -> str:
    """Formatea el cuerpo de letra sin decimales innecesarios: 12pt, no 12.0pt."""
    if float(size_pt).is_integer():
        return f"{int(size_pt)}"
    return f"{size_pt:g}"


def _text_props(font: str, size_pt: float, bold: bool = False,
                italic: bool = False) -> str:
    """Propiedades de texto con fuente, cuerpo e idioma en las tres escrituras."""
    size_pt = _fmt_pt(size_pt)
    parts = [
        f'style:font-name="{escape(font)}"',
        f'style:font-name-asian="{escape(font)}"',
        f'style:font-name-complex="{escape(font)}"',
        f'fo:font-size="{size_pt}pt"',
        f'style:font-size-asian="{size_pt}pt"',
        f'style:font-size-complex="{size_pt}pt"',
        LANG_ATTRS,
    ]
    if bold:
        parts += ['fo:font-weight="bold"', 'style:font-weight-asian="bold"',
                  'style:font-weight-complex="bold"']
    if italic:
        parts += ['fo:font-style="italic"', 'style:font-style-asian="italic"',
                  'style:font-style-complex="italic"']
    return "<style:text-properties " + " ".join(parts) + "/>"


def _encode_inline(text: str) -> str:
    """Convierte texto plano a XML ODF preservando saltos, tabulaciones y espacios.

    ODF colapsa los espacios consecutivos, por lo que hay que codificarlos con
    <text:s>. Los saltos de linea internos de un mensaje se representan con
    <text:line-break/> para que el mensaje siga siendo un unico parrafo.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    out = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "\n":
            out.append("<text:line-break/>")
            i += 1
        elif ch == "\t":
            out.append("<text:tab/>")
            i += 1
        elif ch == " ":
            j = i
            while j < n and text[j] == " ":
                j += 1
            run = j - i
            if run == 1:
                out.append(" ")
            else:
                # el primer espacio va literal, el resto codificado
                out.append(" ")
                out.append(f'<text:s text:c="{run - 1}"/>')
            i = j
        else:
            j = i
            while j < n and text[j] not in "\n\t ":
                j += 1
            out.append(escape(text[i:j]))
            i = j
    return "".join(out)


@dataclass
class _Picture:
    """Imagen ya embebida en el paquete."""
    zip_path: str
    data: bytes
    media_type: str


@dataclass
class OdtReport:
    """Acumula parrafos e imagenes y finalmente escribe el archivo .odt."""

    font: str = "Arial"
    font_size_pt: float = 12.0
    line_height: str = "200%"

    _body: list[str] = field(default_factory=list)
    _pictures: list[_Picture] = field(default_factory=list)
    _pic_seq: int = 0
    _frame_seq: int = 0

    # ------------------------------------------------------------------ texto

    def add_paragraph(self, text: str = "", style: str = "Cuerpo") -> None:
        """Agrega un parrafo. Sin texto genera un parrafo vacio (linea en blanco)."""
        if text:
            self._body.append(
                f'<text:p text:style-name="{style}">{_encode_inline(text)}</text:p>'
            )
        else:
            self._body.append(f'<text:p text:style-name="{style}"/>')

    def add_empty(self, count: int = 1, style: str = "Cuerpo") -> None:
        for _ in range(count):
            self.add_paragraph("", style)

    def add_rich_paragraph(self, runs, style: str = "Cuerpo") -> None:
        """Parrafo con tramos de distinto formato.

        `runs` es una secuencia de tuplas (texto, estilo_de_texto) donde el
        estilo puede ser None (formato del parrafo), "Negrita" o "Cursiva".
        """
        chunks = []
        for text, run_style in runs:
            if not text:
                continue
            encoded = _encode_inline(text)
            if run_style:
                chunks.append(
                    f'<text:span text:style-name="{run_style}">{encoded}</text:span>'
                )
            else:
                chunks.append(encoded)
        inner = "".join(chunks)
        if inner:
            self._body.append(
                f'<text:p text:style-name="{style}">{inner}</text:p>'
            )
        else:
            self.add_paragraph("", style)

    def add_page_break(self) -> None:
        """Salto de pagina mediante un parrafo con quiebre previo."""
        self._body.append('<text:p text:style-name="SaltoPagina"/>')

    # ---------------------------------------------------------------- imagenes

    def add_image(self, path: str, max_width_cm: float = 8.0,
                  max_height_cm: float = 16.0,
                  style: str = "Centrado") -> bool:
        """Inserta una imagen centrada, escalada dentro del recuadro indicado.

        Devuelve False si el archivo no se pudo leer o convertir. Los formatos
        que algunos visores ODF no soportan (webp, gif animado, bmp, tiff) se
        convierten a PNG; de los animados se toma el primer fotograma.
        """
        try:
            data, media_type, ext, px_w, px_h = self._prepare_image(path)
        except Exception:
            return False

        if not data or not px_w or not px_h:
            return False

        w_cm, h_cm = _fit_box(px_w, px_h, max_width_cm, max_height_cm)

        self._pic_seq += 1
        zip_path = f"Pictures/imagen{self._pic_seq:04d}{ext}"
        self._pictures.append(_Picture(zip_path, data, media_type))

        self._frame_seq += 1
        name = escape(os.path.basename(path))
        self._body.append(
            f'<text:p text:style-name="{style}">'
            f'<draw:frame draw:style-name="MarcoImagen" draw:name="Imagen{self._frame_seq}" '
            f'text:anchor-type="as-char" svg:width="{w_cm:.3f}cm" svg:height="{h_cm:.3f}cm" '
            f'draw:z-index="{self._frame_seq}">'
            f'<draw:image xlink:href="{zip_path}" xlink:type="simple" '
            f'xlink:show="embed" xlink:actuate="onLoad"/>'
            f'<svg:title>{name}</svg:title>'
            f"</draw:frame></text:p>"
        )
        return True

    @staticmethod
    def _prepare_image(path: str):
        """Devuelve (bytes, media_type, extension, ancho_px, alto_px)."""
        ext = os.path.splitext(path)[1].lower()
        passthrough = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
        }

        if Image is None:
            # Sin Pillow solo se pueden embeber formatos nativos, y sin conocer
            # sus dimensiones se asume un cuadrado.
            if ext in passthrough:
                with open(path, "rb") as fh:
                    return fh.read(), passthrough[ext], ext, 1000, 1000
            raise RuntimeError("Pillow no disponible para convertir la imagen")

        with Image.open(path) as img:
            img.load()
            px_w, px_h = img.size
            if ext in passthrough and getattr(img, "n_frames", 1) == 1:
                with open(path, "rb") as fh:
                    return fh.read(), passthrough[ext], ext, px_w, px_h

            # Conversion a PNG (webp, gif, bmp, tiff, o jpg/png animado)
            frame = img
            if getattr(img, "n_frames", 1) > 1:
                img.seek(0)
                frame = img.copy()
            if frame.mode not in ("RGB", "RGBA", "L"):
                frame = frame.convert("RGBA")

            import io

            buf = io.BytesIO()
            frame.save(buf, format="PNG")
            return buf.getvalue(), "image/png", ".png", px_w, px_h

    # ------------------------------------------------------------------ salida

    def save(self, path: str) -> str:
        """Escribe el .odt. Devuelve la ruta final."""
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)

        # mimetype debe ser la primera entrada y sin comprimir (spec ODF)
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            info = zipfile.ZipInfo("mimetype")
            info.compress_type = zipfile.ZIP_STORED
            zf.writestr(info, b"application/vnd.oasis.opendocument.text")

            zf.writestr("META-INF/manifest.xml", self._manifest_xml())
            zf.writestr("meta.xml", self._meta_xml())
            zf.writestr("styles.xml", self._styles_xml())
            zf.writestr("content.xml", self._content_xml())
            zf.writestr("settings.xml", self._settings_xml())

            for pic in self._pictures:
                zf.writestr(pic.zip_path, pic.data)

        return path

    # --------------------------------------------------------------- XML parts

    def _font_decls(self) -> str:
        return (
            "<office:font-face-decls>"
            f'<style:font-face style:name="{escape(self.font)}" '
            f'svg:font-family="{escape(self.font)}" '
            'style:font-family-generic="swiss" style:font-pitch="variable"/>'
            "</office:font-face-decls>"
        )

    def _styles_xml(self) -> str:
        base_text = _text_props(self.font, self.font_size_pt)
        bold_text = _text_props(self.font, self.font_size_pt, bold=True)
        italic_text = _text_props(self.font, self.font_size_pt, italic=True)

        para_props = (
            "<style:paragraph-properties "
            f'fo:line-height="{self.line_height}" '
            'fo:margin-top="0cm" fo:margin-bottom="0cm" '
            'fo:text-align="start" style:justify-single-word="false" '
            'fo:orphans="2" fo:widows="2"/>'
        )

        return f"""<?xml version="1.0" encoding="UTF-8"?>
<office:document-styles {NAMESPACES} office:version="1.3">
{self._font_decls()}
<office:styles>
<style:default-style style:family="paragraph">
{para_props}
{base_text}
</style:default-style>
<style:style style:name="Standard" style:family="paragraph" style:class="text">
{para_props}
{base_text}
</style:style>
<style:style style:name="Textosinformato" style:display-name="Texto sin formato" style:family="paragraph" style:parent-style-name="Standard" style:class="text">
{para_props}
{base_text}
</style:style>
<style:style style:name="Cuerpo" style:display-name="Cuerpo del informe" style:family="paragraph" style:parent-style-name="Textosinformato">
{para_props}
{base_text}
</style:style>
<style:style style:name="Centrado" style:family="paragraph" style:parent-style-name="Textosinformato">
<style:paragraph-properties fo:line-height="{self.line_height}" fo:margin-top="0cm" fo:margin-bottom="0cm" fo:text-align="center" style:justify-single-word="false"/>
{base_text}
</style:style>
<style:style style:name="SaltoPagina" style:family="paragraph" style:parent-style-name="Textosinformato">
<style:paragraph-properties fo:line-height="{self.line_height}" fo:margin-top="0cm" fo:margin-bottom="0cm" fo:break-before="page"/>
{base_text}
</style:style>
<style:style style:name="TituloSeccion" style:display-name="Titulo de seccion" style:family="paragraph" style:parent-style-name="Textosinformato" style:next-style-name="Cuerpo">
<style:paragraph-properties fo:line-height="{self.line_height}" fo:margin-top="0cm" fo:margin-bottom="0cm" fo:keep-with-next="always"/>
{bold_text}
</style:style>
<style:style style:name="TituloSeccionHoja" style:display-name="Titulo de seccion en hoja nueva" style:family="paragraph" style:parent-style-name="TituloSeccion" style:next-style-name="Cuerpo">
<style:paragraph-properties fo:line-height="{self.line_height}" fo:margin-top="0cm" fo:margin-bottom="0cm" fo:break-before="page" fo:keep-with-next="always"/>
{bold_text}
</style:style>
<style:style style:name="Negrita" style:family="text">
{bold_text}
</style:style>
<style:style style:name="Cursiva" style:family="text">
{italic_text}
</style:style>
<style:style style:name="MarcoImagen" style:display-name="Marco de imagen" style:family="graphic">
<style:graphic-properties text:anchor-type="as-char" style:vertical-pos="top" style:vertical-rel="baseline" style:horizontal-pos="center" style:horizontal-rel="paragraph" fo:border="none" fo:padding="0cm" fo:margin-top="0.1cm" fo:margin-bottom="0.1cm" draw:fill="none" draw:stroke="none" style:wrap="none"/>
</style:style>
</office:styles>
<office:automatic-styles>
<style:page-layout style:name="PL1">
<style:page-layout-properties fo:page-width="21.001cm" fo:page-height="29.7cm" style:print-orientation="portrait" fo:margin-top="2.5cm" fo:margin-bottom="2.5cm" fo:margin-left="2.5cm" fo:margin-right="2.5cm" style:num-format="1" style:writing-mode="lr-tb" style:footnote-max-height="0cm">
<style:footnote-sep style:width="0.018cm" style:distance-before-sep="0.101cm" style:distance-after-sep="0.101cm" style:line-style="solid" style:adjustment="left" style:rel-width="25%" style:color="#000000"/>
</style:page-layout-properties>
</style:page-layout>
</office:automatic-styles>
<office:master-styles>
<style:master-page style:name="Standard" style:page-layout-name="PL1"/>
</office:master-styles>
</office:document-styles>"""

    def _content_xml(self) -> str:
        body = "\n".join(self._body) if self._body else '<text:p text:style-name="Cuerpo"/>'
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<office:document-content {NAMESPACES} office:version="1.3">
{self._font_decls()}
<office:automatic-styles/>
<office:body>
<office:text text:use-soft-page-breaks="true">
{body}
</office:text>
</office:body>
</office:document-content>"""

    def _meta_xml(self) -> str:
        """Metadatos del documento.

        A proposito no se escriben ni el titulo, ni el asunto, ni el nombre del
        programa que lo genero: el informe no debe decir nada que no sea el
        contenido del chat. Solo queda la fecha y el idioma, que es lo que
        necesita el corrector ortografico.
        """
        now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<office:document-meta {NAMESPACES} office:version="1.3">
<office:meta>
<meta:creation-date>{now}</meta:creation-date>
<dc:date>{now}</dc:date>
<dc:language>es-AR</dc:language>
</office:meta>
</office:document-meta>"""

    def _settings_xml(self) -> str:
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<office:document-settings {NAMESPACES} office:version="1.3">
<office:settings>
<config:config-item-set xmlns:config="urn:oasis:names:tc:opendocument:xmlns:config:1.0" config:name="ooo:configuration-settings">
<config:config-item xmlns:config="urn:oasis:names:tc:opendocument:xmlns:config:1.0" config:name="AddParaTableSpacing" config:type="boolean">true</config:config-item>
</config:config-item-set>
</office:settings>
</office:document-settings>"""

    def _manifest_xml(self) -> str:
        entries = [
            '<manifest:file-entry manifest:full-path="/" '
            'manifest:version="1.3" '
            'manifest:media-type="application/vnd.oasis.opendocument.text"/>',
            '<manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>',
            '<manifest:file-entry manifest:full-path="styles.xml" manifest:media-type="text/xml"/>',
            '<manifest:file-entry manifest:full-path="meta.xml" manifest:media-type="text/xml"/>',
            '<manifest:file-entry manifest:full-path="settings.xml" manifest:media-type="text/xml"/>',
        ]
        for pic in self._pictures:
            entries.append(
                f'<manifest:file-entry manifest:full-path="{pic.zip_path}" '
                f'manifest:media-type="{pic.media_type}"/>'
            )
        joined = "\n".join(entries)
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.3">
{joined}
</manifest:manifest>"""


def _fit_box(px_w: int, px_h: int, max_w_cm: float, max_h_cm: float):
    """Escala (px_w, px_h) para que entre en el recuadro sin deformarse."""
    if px_w <= 0 or px_h <= 0:
        return max_w_cm, max_w_cm
    ratio = px_h / px_w
    w = max_w_cm
    h = w * ratio
    if h > max_h_cm:
        h = max_h_cm
        w = h / ratio
    return w, h
