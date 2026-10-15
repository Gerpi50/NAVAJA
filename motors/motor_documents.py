"""
motor_documents.py — Conversión de documentos de texto y office.
Motores: LibreOffice, python-docx, pypdf, reportlab, Pandoc, extract-msg.
Soporta: DOCX, DOC, ODT, RTF, TXT, PDF, EPUB, HTML, MD, RST,
         PAGES, WPS, ABW, LATEX, MSG, EML, EMLX, MBOX
"""
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from typing import List, Optional, Tuple
from core.graph import BaseMotor


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _libreoffice_path():
    lo = shutil.which("soffice") or shutil.which("soffice.exe")
    if lo:
        return lo
    candidates = [
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        "/usr/bin/soffice",
        "/usr/local/bin/soffice",
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None

def _pandoc_path():
    # Primero pandoc.exe en bin/ (build portable), luego el PATH
    from core.paths import BIN_DIR
    local = os.path.join(BIN_DIR, "pandoc.exe")
    if os.path.isfile(local):
        return local
    return shutil.which("pandoc")


# ---------------------------------------------------------------------------
# Motor LibreOffice — documentos de oficina
# ---------------------------------------------------------------------------

# LibreOffice son tres programas en uno y cada uno abre y guarda lo suyo.
# La lista de pares se escribía a mano y quedaba despareja: CSV → HTML no
# estaba, así que el grafo lo mandaba por PDF y devolvía un HTML vacío.
# Ahora se declara qué abre y qué guarda cada programa, y el producto sale
# solo.
LO_WRITER_READ = ["doc", "docx", "odt", "rtf", "txt", "html", "htm",
                  "wps", "abw", "pages"]
LO_WRITER_WRITE = ["pdf", "docx", "doc", "odt", "rtf", "txt", "html", "htm"]

LO_CALC_READ = ["xls", "xlsx", "ods", "csv", "numbers"]
LO_CALC_WRITE = ["pdf", "xlsx", "xls", "ods", "csv", "html", "htm"]

LO_IMPRESS_READ = ["ppt", "pptx", "odp", "key"]
LO_IMPRESS_WRITE = ["pdf", "pptx", "ppt", "odp"]

# EPUB no figura: LibreOffice lo exporta pero no lo importa. Estaba declarado
# como epub→pdf y devolvía un archivo vacío; ahora ese trabajo lo hace
# Pandoc (epub → HTML → PDF), que sí sabe leerlo.
LO_CONVERSIONS = [
    (s_, d_)
    for _lee, _guarda in ((LO_WRITER_READ, LO_WRITER_WRITE),
                          (LO_CALC_READ, LO_CALC_WRITE),
                          (LO_IMPRESS_READ, LO_IMPRESS_WRITE))
    for s_ in _lee for d_ in _guarda if s_ != d_
]


class LibreOfficeDocMotor(BaseMotor):
    NAME = "LibreOffice-Doc"
    CONVERSIONS = LO_CONVERSIONS

    @classmethod
    def is_available(cls) -> bool:
        return _libreoffice_path() is not None

    def convert(self, src_path, dst_path, src_ext, dst_ext, **kwargs):
        lo = _libreoffice_path()
        out_dir = os.path.dirname(dst_path) or "."
        stem = os.path.splitext(os.path.basename(src_path))[0]
        expected = os.path.join(out_dir, f"{stem}.{dst_ext}")

        # Mapeo de extensión a filtro LibreOffice
        filter_map = {
            "pdf":  "writer_pdf_Export",
            "doc":  "MS Word 97",
            "xls":  "MS Excel 97",
            "docx": "MS Word 2007 XML",
            "odt":  "writer8",
            "rtf":  "Rich Text Format",
            "txt":  "Text",
            "html": "HTML (StarWriter)",
            "htm":  "HTML (StarWriter)",
            "ods":  "calc8",
            "xlsx": "Calc MS Excel 2007 XML",
            "csv":  "Text - txt - csv (StarCalc)",
            "odp":  "impress8",
            "pptx": "Impress MS PowerPoint 2007 XML",
        }

        # El filtro HTML depende de la app de origen (Writer vs Calc)
        if dst_ext in ("html", "htm") and src_ext in (
                "xlsx", "xls", "ods", "csv", "numbers"):
            filter_map["html"] = "HTML (StarCalc)"
            filter_map["htm"]  = "HTML (StarCalc)"

        cmd = [lo, "--headless", "--convert-to", dst_ext,
               "--outdir", out_dir, src_path]

        if dst_ext in filter_map:
            cmd = [lo, "--headless",
                   "--infilter=" + (filter_map.get(src_ext, "")),
                   "--convert-to", f"{dst_ext}:{filter_map[dst_ext]}",
                   "--outdir", out_dir, src_path]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if result.returncode != 0:
            raise RuntimeError(f"LibreOffice error: {result.stderr[-600:]}")

        # Renombrar al destino correcto si difiere
        if os.path.abspath(expected) != os.path.abspath(dst_path):
            if os.path.exists(expected):
                shutil.move(expected, dst_path)


# ---------------------------------------------------------------------------
# Marcadores de página
# ---------------------------------------------------------------------------
#
# Un .md es un chorro de texto sin páginas. Cuando el documento se le da a una
# IA para que cite ("¿de dónde sacaste esto?"), la respuesta no puede incluir
# la página porque en el archivo no existe. Por eso, al convertir a Markdown se
# intercala un renglón así donde el documento original cambiaba de hoja:
#
#     --- [PÁGINA 7] ---
#
# Queda solo, con un renglón en blanco antes y después, para que ningún lector
# lo pegue al párrafo de al lado.
#
# Dónde cae el marcador: **antes del párrafo con el que empieza la página**. Si
# un párrafo viene cortado entre dos hojas, se lo cuenta en la hoja donde
# empezó, que es como se cita.

MARCADOR_PAGINA = "--- [PÁGINA {}] ---"

# Pandoc escapa los corchetes al escribir Markdown ("\[PÁGINA 3\]") y algunos
# conversores cambian los tres guiones por una raya. Se reconoce cualquiera de
# esas formas para devolver el marcador a su forma canónica.
_MD_MARCA_PAGINA = re.compile(
    r"^[ \t]*\\?[-—–]{1,3}[ \t]*\\?\[[ \t]*P[ÁA]GINA[ \t]+(\d+)[ \t]*\\?\][ \t]*"
    r"\\?[-—–]{1,3}[ \t]*$",
    re.IGNORECASE,
)


def es_marcador_de_pagina(linea: str) -> Optional[int]:
    """Número de página si el renglón es un marcador; None si no lo es."""
    m = _MD_MARCA_PAGINA.match(linea)
    return int(m.group(1)) if m else None


# Cada formato guarda el salto de página de su manera. LibreOffice escribe
# <text:soft-page-break/> cada vez que pagina el documento; Word escribe
# <w:lastRenderedPageBreak/>. Los dos son "dónde cortó la última vez que se
# mostró el documento", así que el número de página es el que vería quien
# abriera el archivo, no una cuenta inventada por nosotros.
_FORMATOS_PAGINADOS = {
    "odt": {
        "xml": "content.xml",
        # La etiqueta exacta, no el texto suelto: el propio tag que abre el
        # cuerpo dice text:use-soft-page-breaks="true" y contarlo como salto
        # corría todo el documento una página.
        "salto": re.compile(r"<text:soft-page-break\s*/?>"),
        "bloque": re.compile(r"<text:(p|h)[\s/>]"),
        "abre": re.compile(r"<(table:table|draw:frame|text:list|"
                           r"office:annotation|text:note)[\s>]"),
        "cierra": re.compile(r"</(table:table|draw:frame|text:list|"
                             r"office:annotation|text:note)>"),
        "cuerpo": "<office:text",
        "parrafo": "<text:p>{}</text:p>",
    },
    "docx": {
        "xml": "word/document.xml",
        "salto": re.compile(r"<w:lastRenderedPageBreak\s*/?>"),
        "bloque": re.compile(r"<w:p[\s/>]"),
        "abre": re.compile(r"<(w:tbl|w:txbxContent)[\s>]"),
        "cierra": re.compile(r"</(w:tbl|w:txbxContent)>"),
        "cuerpo": "<w:body",
        "parrafo": '<w:p><w:r><w:t xml:space="preserve">{}</w:t></w:r></w:p>',
    },
}


def _inyectar_marcadores_xml(xml: str, reglas: dict) -> Tuple[str, int]:
    """Mete un párrafo con el marcador donde el documento cambia de página."""
    inicio = xml.find(reglas["cuerpo"])
    if inicio < 0:
        return xml, 0

    salida = [xml[:inicio]]
    resto = xml[inicio:]
    pagina, pendiente, profundidad, puestos, pos = 1, True, 0, 0, 0

    for tag in re.finditer(r"<[^>]*>", resto):
        etiqueta = tag.group(0)

        # Adentro de una tabla o de un cuadro de texto no se puede meter un
        # párrafo suelto sin romper el XML: el marcador espera a que el
        # documento vuelva al nivel de arriba.
        if reglas["abre"].match(etiqueta):
            profundidad += 1
        elif reglas["cierra"].match(etiqueta):
            profundidad = max(0, profundidad - 1)

        if reglas["salto"].match(etiqueta):
            pagina += 1
            pendiente = True
            continue

        if pendiente and profundidad == 0 and reglas["bloque"].match(etiqueta):
            salida.append(resto[pos:tag.start()])
            salida.append(reglas["parrafo"].format(MARCADOR_PAGINA.format(pagina)))
            pos = tag.start()
            pendiente = False
            puestos += 1

    salida.append(resto[pos:])
    return "".join(salida), puestos


def copia_con_marcadores(src_path: str, src_ext: str, destino_dir: str) -> Optional[str]:
    """Copia del documento con los marcadores de página puestos.

    Devuelve la ruta de la copia, o None si el documento no trae información
    de páginas (pasa con archivos generados por programa, que nunca fueron
    paginados por un procesador de texto). En ese caso se convierte el
    original tal cual: es preferible un Markdown sin marcadores a uno con
    números de página inventados.
    """
    reglas = _FORMATOS_PAGINADOS.get(src_ext)
    if not reglas:
        return None

    try:
        with zipfile.ZipFile(src_path) as z:
            nombres = z.namelist()
            if reglas["xml"] not in nombres:
                return None
            contenido = {n: z.read(n) for n in nombres}

        xml = contenido[reglas["xml"]].decode("utf-8")
        if not reglas["salto"].search(xml):
            return None

        nuevo, puestos = _inyectar_marcadores_xml(xml, reglas)
        if not puestos:
            return None
        contenido[reglas["xml"]] = nuevo.encode("utf-8")

        os.makedirs(destino_dir, exist_ok=True)
        copia = os.path.join(destino_dir, os.path.basename(src_path))
        with zipfile.ZipFile(copia, "w", zipfile.ZIP_DEFLATED) as z:
            # El "mimetype" de un ODF tiene que ir primero y sin comprimir.
            if "mimetype" in contenido:
                z.writestr(zipfile.ZipInfo("mimetype"), contenido["mimetype"],
                           compress_type=zipfile.ZIP_STORED)
            for n in nombres:
                if n != "mimetype":
                    z.writestr(n, contenido[n])
        return copia
    except (OSError, KeyError, zipfile.BadZipFile, UnicodeDecodeError):
        return None


# ---------------------------------------------------------------------------
# Pulido del Markdown que sale de un documento de oficina
# ---------------------------------------------------------------------------

# Un Word o un ODT arrastran restos de cómo fue escrito: pedazos de negrita
# sin texto adentro (queda "n****o" en el medio de una palabra), párrafos
# vacíos con estilo de título (queda un "##" solo) y listas pegadas al
# párrafo anterior. Nada de eso es texto: es basura de formato que el
# conversor venía copiando tal cual.
#
# Regla que se respeta acá: **no se inventa ni se corrige contenido.** Si el
# documento original dice "distintoya" sin espacio, el Markdown va a decir
# "distintoya": eso lo escribió el autor y no es asunto del conversor. Sólo
# se saca lo que no tiene texto adentro.

# Cuatro asteriscos seguidos son una negrita que quedó sin nada adentro. Se
# exige que sean EXACTAMENTE cuatro (ni tres, que es negrita+cursiva, ni
# cinco) y no se toca "**a** **b**": ahí los asteriscos del medio cierran una
# negrita y abren otra, y borrarlos fusionaría las dos.
_MD_NEGRITA_VACIA = re.compile(r"(?<!\*)\*{4}(?!\*)")
_MD_TITULO_VACIO = re.compile(r"^#{1,6}[ \t]*$")
_MD_ITEM = re.compile(r"^[ \t]*([-*+]|\d+[.)])[ \t]+\S")
_MD_CERCA = re.compile(r"^[ \t]*(```|~~~)")


def limpiar_markdown(texto: str) -> str:
    """Saca del Markdown las marcas de formato que quedaron sin contenido.

    Lo que está adentro de un bloque de código (``` … ```) no se toca: ahí
    un "##" o un "-" son parte del código y no formato del documento.
    """
    salida = []
    en_codigo = False

    for linea in texto.split("\n"):
        if _MD_CERCA.match(linea):
            en_codigo = not en_codigo
            salida.append(linea)
            continue

        if en_codigo:
            salida.append(linea)
            continue

        # El marcador de página se devuelve a su forma exacta: Pandoc escapa
        # los corchetes al escribirlo y así "\[PÁGINA 3\]" no lo reconocería
        # ni un buscador ni la IA que después tiene que citar la hoja.
        n = es_marcador_de_pagina(linea)
        if n is not None:
            if salida and salida[-1].strip():
                salida.append("")
            salida.append(MARCADOR_PAGINA.format(n))
            salida.append("")
            continue

        linea = _MD_NEGRITA_VACIA.sub("", linea)

        # Un título sin texto no dice nada y, peor, parte el documento en una
        # sección que no existe.
        if _MD_TITULO_VACIO.match(linea):
            continue

        # Una lista pegada al párrafo anterior: hay programas que la muestran
        # como un renglón más y se pierden las viñetas.
        if (_MD_ITEM.match(linea) and salida and salida[-1].strip()
                and not _MD_ITEM.match(salida[-1])):
            salida.append("")
        # Y al revés: el párrafo que arranca pegado al final de una lista.
        elif (salida and _MD_ITEM.match(salida[-1]) and linea.strip()
                and not _MD_ITEM.match(linea)
                and not linea.startswith((" ", "\t", ">", "|"))):
            salida.append("")

        salida.append(linea)

    texto = "\n".join(salida)
    # Los agujeros que deja lo anterior: nunca más de un renglón en blanco.
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto.rstrip() + "\n"


def pulir_markdown(ruta: str) -> bool:
    """Aplica limpiar_markdown() sobre un archivo ya escrito. True si cambió.

    Se respeta el final de renglón que ya traía el archivo (en Windows,
    CRLF): si no, el archivo entero figura como modificado aunque sólo se
    hayan sacado dos marcas de formato, y comparar versiones se vuelve
    imposible.
    """
    try:
        with open(ruta, "r", encoding="utf-8", newline="") as f:
            crudo = f.read()
    except (OSError, UnicodeDecodeError):
        return False

    salto = "\r\n" if "\r\n" in crudo else "\n"
    original = crudo.replace("\r\n", "\n")
    limpio = limpiar_markdown(original)
    if limpio == original:
        return False

    with open(ruta, "w", encoding="utf-8", newline="") as f:
        f.write(limpio.replace("\n", salto))
    return True


# ---------------------------------------------------------------------------
# Motor Pandoc — documentos de texto/markup
# ---------------------------------------------------------------------------

class PandocMotor(BaseMotor):
    NAME = "Pandoc"
    CONVERSIONS = [
        ("md","pdf"),   ("md","html"),  ("md","docx"),  ("md","odt"),
        ("md","epub"),  ("md","rst"),   ("md","txt"),   ("md","tex"),
        ("rst","pdf"),  ("rst","html"), ("rst","docx"),  ("rst","md"),
        ("html","md"),  ("html","rst"), ("html","epub"), ("html","pdf"),
        ("htm","md"),   ("htm","pdf"),
        ("docx","md"),  ("docx","epub"),("docx","rst"),
        ("odt","md"),   ("odt","epub"),
        ("epub","md"),  ("epub","html"),("epub","pdf"),  ("epub","docx"),
        ("tex","pdf"),  ("tex","html"), ("tex","docx"),
        ("txt","md"),   ("txt","html"), ("txt","rst"),
        ("ipynb","html"),("ipynb","pdf"),("ipynb","md"), ("ipynb","docx"),
    ]

    @classmethod
    def is_available(cls) -> bool:
        return _pandoc_path() is not None

    def convert(self, src_path, dst_path, src_ext, dst_ext, **kwargs):
        pandoc = _pandoc_path()
        cmd = [pandoc, src_path, "-o", dst_path]

        # Markdown: el formato que sale por defecto es el "markdown" de
        # Pandoc, que corta los renglones a 72 columnas, escapa las comillas
        # (\") y agrega atributos suyos ({width="11.6in"}) que ningún otro
        # programa entiende. Con GFM y sin corte de línea, el .md queda
        # legible y se puede pegar en cualquier lado.
        if dst_ext == "md":
            # Los números de página del documento original se intercalan como
            # renglones aparte, para que después se pueda citar "página 7".
            # Se trabaja sobre una copia: el archivo del usuario no se toca.
            entrada = os.path.abspath(src_path)
            temporal = None
            if kwargs.get("marcar_paginas", True):
                temporal = tempfile.mkdtemp(prefix="gp_paginas_")
                copia = copia_con_marcadores(entrada, src_ext, temporal)
                if copia:
                    entrada = copia
                else:
                    shutil.rmtree(temporal, ignore_errors=True)
                    temporal = None

            try:
                # gfm-raw_html: las imágenes salen como ![](ruta) y no como un
                # <img style="width:11.6in"> que sólo entiende un navegador.
                cmd = [pandoc, entrada,
                       "-t", "gfm-raw_html", "--wrap=none",
                       "-o", os.path.basename(dst_path)]
                # Las imágenes del documento se extraen al lado del .md: si no,
                # el Markdown queda con enlaces a archivos que no existen. Se
                # corre desde la carpeta de destino para que la ruta que escribe
                # Pandoc quede relativa y el .md se pueda mover de lugar.
                if src_ext in ("docx", "odt", "epub", "ipynb"):
                    media = os.path.splitext(os.path.basename(dst_path))[0] + "_imagenes"
                    cmd += [f"--extract-media={media}"]
                destino = os.path.dirname(os.path.abspath(dst_path)) or "."
                os.makedirs(destino, exist_ok=True)
                r = subprocess.run(cmd, capture_output=True, text=True,
                                   timeout=180, cwd=destino)
                if r.returncode != 0:
                    raise RuntimeError(f"Pandoc error: {r.stderr[-600:]}")
            finally:
                if temporal:
                    shutil.rmtree(temporal, ignore_errors=True)
            pulir_markdown(dst_path)
            return

        # PDF requiere un engine LaTeX o weasyprint
        if dst_ext == "pdf":
            engine = None
            if shutil.which("wkhtmltopdf"):
                engine = "wkhtmltopdf"
            elif shutil.which("xelatex"):
                engine = "xelatex"
            elif shutil.which("pdflatex"):
                engine = "pdflatex"
            if engine:
                cmd += [f"--pdf-engine={engine}"]
            elif _libreoffice_path():
                # Sin engine LaTeX: pandoc → HTML y LibreOffice → PDF
                self._pdf_via_html(pandoc, src_path, dst_path)
                return
            # sin engine ni LibreOffice: dejar que pandoc falle con su mensaje

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(f"Pandoc error: {result.stderr[-600:]}")

    @staticmethod
    def _pdf_via_html(pandoc, src_path, dst_path):
        """pandoc → HTML intermedio → PDF con LibreOffice."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_html = os.path.join(tmp, "pandoc_out.html")
            result = subprocess.run(
                [pandoc, "--standalone", src_path, "-o", tmp_html],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode != 0:
                raise RuntimeError(f"Pandoc error: {result.stderr[-600:]}")
            LibreOfficeDocMotor().convert(tmp_html, dst_path, "html", "pdf")


# ---------------------------------------------------------------------------
# Motor TXT → PDF puro (reportlab, sin dependencias externas)
# ---------------------------------------------------------------------------

class TxtToPdfMotor(BaseMotor):
    NAME = "TXT→PDF"
    CONVERSIONS = [
        ("txt", "pdf"),
        ("md",  "pdf"),
        ("csv", "pdf"),
    ]

    @classmethod
    def is_available(cls) -> bool:
        try:
            import reportlab
            return True
        except ImportError:
            return False

    def convert(self, src_path, dst_path, src_ext, dst_ext, **kwargs):
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        from reportlab.lib.units import mm

        with open(src_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        page_w, page_h = A4
        margin = 20 * mm
        font_size = 9
        line_h = font_size * 1.4
        max_lines = int((page_h - 2 * margin) / line_h)

        c = canvas.Canvas(dst_path, pagesize=A4)
        c.setFont("Courier", font_size)

        y = page_h - margin
        for line in lines:
            line = line.rstrip("\n\r")
            # Truncar líneas muy largas
            max_chars = int((page_w - 2 * margin) / (font_size * 0.6))
            if len(line) > max_chars:
                line = line[:max_chars - 1] + "…"
            c.drawString(margin, y, line)
            y -= line_h
            if y < margin:
                c.showPage()
                c.setFont("Courier", font_size)
                y = page_h - margin

        c.save()


# ---------------------------------------------------------------------------
# Motor MSG / EML — correos electrónicos
# ---------------------------------------------------------------------------

class EmailMotor(BaseMotor):
    NAME = "Email"
    CONVERSIONS = [
        ("msg",  "pdf"), ("msg",  "txt"), ("msg",  "html"), ("msg",  "eml"),
        ("eml",  "pdf"), ("eml",  "txt"), ("eml",  "html"),
        ("emlx", "pdf"), ("emlx", "txt"), ("emlx", "html"), ("emlx", "eml"),
    ]

    @classmethod
    def is_available(cls) -> bool:
        try:
            import extract_msg
            return True
        except ImportError:
            return False

    def convert(self, src_path, dst_path, src_ext, dst_ext, **kwargs):
        if src_ext == "msg":
            self._from_msg(src_path, dst_path, dst_ext)
        elif src_ext in ("eml", "emlx"):
            self._from_eml(src_path, dst_path, dst_ext)

    def _from_msg(self, src_path, dst_path, dst_ext):
        import extract_msg
        msg = extract_msg.openMsg(src_path)
        subject = msg.subject or "(Sin asunto)"
        sender  = msg.sender or ""
        date    = str(msg.date) if msg.date else ""
        body    = msg.body or ""

        content = f"De: {sender}\nFecha: {date}\nAsunto: {subject}\n\n{body}"

        if dst_ext == "txt":
            with open(dst_path, "w", encoding="utf-8") as f:
                f.write(content)
        elif dst_ext == "html":
            html = f"<html><body><pre>{content}</pre></body></html>"
            with open(dst_path, "w", encoding="utf-8") as f:
                f.write(html)
        elif dst_ext == "eml":
            # Exportar como EML estándar
            eml = msg.getEmailObj()
            with open(dst_path, "wb") as f:
                from email import generator
                gen = generator.BytesGenerator(f)
                gen.flatten(eml)
        elif dst_ext == "pdf":
            with tempfile.NamedTemporaryFile(suffix=".txt", delete=False,
                                             mode="w", encoding="utf-8") as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            try:
                TxtToPdfMotor().convert(tmp_path, dst_path, "txt", "pdf")
            finally:
                os.unlink(tmp_path)

    def _from_eml(self, src_path, dst_path, dst_ext):
        import email
        with open(src_path, "rb") as f:
            msg = email.message_from_bytes(f.read())

        subject = msg.get("Subject", "(Sin asunto)")
        sender  = msg.get("From", "")
        date    = msg.get("Date", "")
        body    = ""

        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    body = part.get_payload(decode=True).decode("utf-8", errors="replace")
                    break
        else:
            body = msg.get_payload(decode=True).decode("utf-8", errors="replace")

        content = f"De: {sender}\nFecha: {date}\nAsunto: {subject}\n\n{body}"

        if dst_ext == "txt":
            with open(dst_path, "w", encoding="utf-8") as f:
                f.write(content)
        elif dst_ext == "html":
            with open(dst_path, "w", encoding="utf-8") as f:
                f.write(f"<html><body><pre>{content}</pre></body></html>")
        elif dst_ext == "pdf":
            with tempfile.NamedTemporaryFile(suffix=".txt", delete=False,
                                             mode="w", encoding="utf-8") as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            try:
                TxtToPdfMotor().convert(tmp_path, dst_path, "txt", "pdf")
            finally:
                os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# Motor HTML → PDF (WeasyPrint o wkhtmltopdf)
# ---------------------------------------------------------------------------

class HtmlToPdfMotor(BaseMotor):
    NAME = "HTML→PDF"
    CONVERSIONS = [
        ("html", "pdf"), ("htm", "pdf"),
        ("mhtml", "pdf"), ("mht", "pdf"),
    ]

    @classmethod
    def is_available(cls) -> bool:
        try:
            import weasyprint
            return True
        except ImportError:
            return shutil.which("wkhtmltopdf") is not None

    def convert(self, src_path, dst_path, src_ext, dst_ext, **kwargs):
        try:
            from weasyprint import HTML
            HTML(filename=src_path).write_pdf(dst_path)
        except ImportError:
            subprocess.run(
                ["wkhtmltopdf", src_path, dst_path],
                check=True, capture_output=True, timeout=120
            )


# ---------------------------------------------------------------------------
# Motor PDF → imágenes / texto
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# El final de una hoja repetido al principio de la siguiente
#
# Reportado el 6-sep-2026: al pasar un PDF a TXT o a MD, los últimos renglones
# de cada hoja aparecían otra vez arriba de la hoja siguiente, aunque abriendo
# el PDF no se ven repetidos. Pasa cuando el generador del documento dibuja el
# texto que "desborda" la caja de la página —queda tapado por el borde de la
# hoja, invisible al leerlo, pero ahí está— y lo vuelve a dibujar completo en
# la página que sigue. Cualquier extractor de texto lo lee dos veces.
#
# Se compara el final de una hoja con el principio de la siguiente y se saca
# lo que coincide. Para no borrar de más hace falta que sean dos renglones
# repetidos, o uno solo pero largo.
# ---------------------------------------------------------------------------

_MAX_RENGLONES_REPETIDOS = 15
_MIN_LARGO_REPETIDO      = 30


def _clave_renglon(texto: str) -> str:
    """Texto normalizado para comparar renglones entre páginas."""
    return re.sub(r"\s+", " ", (texto or "")).strip().lower()


def quitar_repeticion_entre_paginas(paginas: List[List[str]]) -> List[List[str]]:
    """Saca de cada página el arranque que repite el final de la anterior.

    `paginas` es una lista de páginas, y cada página una lista de renglones.
    Devuelve la misma estructura, sin las repeticiones.
    """
    limpias = []
    anterior_util = []
    for pagina in paginas:
        indices = [i for i, ln in enumerate(pagina) if _clave_renglon(ln)]
        actual_util = [_clave_renglon(pagina[i]) for i in indices]

        cortar = 0
        tope = min(len(anterior_util), len(actual_util), _MAX_RENGLONES_REPETIDOS)
        for k in range(tope, 0, -1):
            if anterior_util[-k:] == actual_util[:k]:
                largo = sum(len(t) for t in actual_util[:k])
                if k >= 2 or largo >= _MIN_LARGO_REPETIDO:
                    cortar = k
                    break

        if cortar:
            sobran = set(indices[:cortar])
            pagina = [ln for i, ln in enumerate(pagina) if i not in sobran]
            actual_util = actual_util[cortar:]

        limpias.append(pagina)
        if actual_util:
            anterior_util = actual_util
    return limpias


class PdfExtractMotor(BaseMotor):
    NAME = "PDF-Extract"
    CONVERSIONS = [
        ("pdf", "txt"),  ("pdf", "html"),
        ("pdf", "png"),  ("pdf", "jpg"),
        ("pdf", "svg"),
    ]

    @classmethod
    def is_available(cls) -> bool:
        try:
            import pypdf
            return True
        except ImportError:
            return False

    @staticmethod
    def _texto_por_pagina(src_path, reader) -> List[List[str]]:
        """Renglones de cada página, sin lo que está dibujado fuera de la hoja.

        Se lee con PyMuPDF, que da las coordenadas de cada renglón: así se
        puede descartar el texto que el generador dibujó más abajo del borde
        de la página —invisible al abrir el PDF, pero que el extractor lee y
        aparece duplicado en el .txt. Si PyMuPDF no está, se cae a pypdf.
        """
        try:
            import fitz
        except ImportError:
            return [(page.extract_text() or "").splitlines()
                    for page in reader.pages]

        # Los renglones se arman por posición: muchos PDF (los de sistemas de gestión, por
        # ejemplo) escriben cada palabra suelta y salía una por renglón.
        #
        # Las hojas escaneadas de algunos sistemas traen como texto sólo el sello
        # ("COPIA / Usuario: ..."): salía el sello y nada del escrito, dado
        # por exitoso. Si todas son escaneos se corta pidiendo OCR; si son
        # algunas, la página lo dice en el .txt en vez de quedar muda.
        from motors.motor_pdf_tools import renglones_de_pagina
        from motors.motor_ocr import _page_is_scan, _TXT_SCAN_IMG_RATIO
        paginas, escaneadas = [], 0
        doc = fitz.open(src_path)
        try:
            for page in doc:
                renglones = renglones_de_pagina(page)
                if _page_is_scan(page, _TXT_SCAN_IMG_RATIO):
                    escaneadas += 1
                    renglones = renglones + [
                        "", "[Página escaneada: su texto es una imagen. "
                            "Para leerlo, convertí con «🔍 Reconocer texto (OCR)».]"]
                paginas.append(renglones)
            total = doc.page_count
        finally:
            doc.close()
        if total and escaneadas == total:
            raise RuntimeError(
                f"El PDF no tiene texto que extraer: sus {total} página(s) "
                "son imágenes escaneadas (lo único escrito es el sello).\n"
                "Activá la opción «🔍 Reconocer texto (OCR)» antes de "
                "convertir, o generá primero un PDF buscable (OCR con "
                "destino PDF) y convertí ese.")
        return paginas

    def convert(self, src_path, dst_path, src_ext, dst_ext, **kwargs):
        from pypdf import PdfReader

        try:
            reader = PdfReader(src_path)
        except Exception:
            # Un PDF que todavía se está guardando no se deja leer y salía
            # "Stream has ended unexpectedly", que no le dice nada a nadie.
            from motors.motor_ocr import pdf_sin_terminar, PDF_SIN_TERMINAR_MSG
            if pdf_sin_terminar(src_path):
                raise RuntimeError(PDF_SIN_TERMINAR_MSG)
            raise

        if dst_ext in ("txt", "html"):
            paginas = self._texto_por_pagina(src_path, reader)
            paginas = quitar_repeticion_entre_paginas(paginas)
            text = "\n\n".join("\n".join(p) for p in paginas)
            # Un PDF escaneado (puras imágenes) no tiene capa de texto que
            # extraer: acá salía un archivo con SOLO saltos de línea, dado por
            # exitoso y con constancia y todo. Cortar diciendo qué hacer.
            if not text.strip():
                from motors.motor_ocr import (pdf_sin_terminar,
                                              PDF_SIN_TERMINAR_MSG)
                if pdf_sin_terminar(src_path):
                    raise RuntimeError(PDF_SIN_TERMINAR_MSG)
                raise RuntimeError(
                    "El PDF no tiene texto que extraer: sus "
                    f"{len(reader.pages)} página(s) son imágenes escaneadas "
                    "o letras dibujadas (pasa al guardar con «Microsoft "
                    "Print to PDF»).\n"
                    "Activá la opción «🔍 Reconocer texto (OCR)» antes de "
                    "convertir, o generá primero un PDF buscable (OCR con "
                    "destino PDF) y convertí ese."
                )
            if dst_ext == "html":
                text = f"<html><body><pre>{text}</pre></body></html>"
            with open(dst_path, "w", encoding="utf-8") as f:
                f.write(text)

        elif dst_ext in ("png", "jpg"):
            # PyMuPDF renderiza sin depender de poppler
            import fitz
            doc = fitz.open(src_path)
            try:
                zoom = 150 / 72.0
                mat = fitz.Matrix(zoom, zoom)
                base, ext = os.path.splitext(dst_path)
                for i, page in enumerate(doc):
                    pix = page.get_pixmap(matrix=mat)
                    # La primera página va a dst_path (para que el archivo de
                    # salida esperado siempre exista); el resto, numeradas.
                    out = dst_path if i == 0 else f"{base}_p{i+1}{ext}"
                    pix.save(out)
            finally:
                doc.close()

        elif dst_ext == "svg":
            # SVG vectorial real por página (texto y curvas del PDF)
            import fitz
            doc = fitz.open(src_path)
            try:
                base, ext = os.path.splitext(dst_path)
                for i, page in enumerate(doc):
                    svg = page.get_svg_image()
                    out = dst_path if i == 0 else f"{base}_p{i+1}{ext}"
                    with open(out, "w", encoding="utf-8") as f:
                        f.write(svg)
            finally:
                doc.close()


# ---------------------------------------------------------------------------
# Motor PDF → Markdown
# ---------------------------------------------------------------------------

class PdfToMdMotor(BaseMotor):
    """PDF → Markdown directo, con PyMuPDF.

    Encadenar pdf→docx→md (pdf2docx + Pandoc) tarda muchísimo y se rompe en
    PDF complejos, así que se lee el PDF una sola vez y se arma el Markdown
    a mano.

    Cómo se decide cada cosa (reescrito el 6-sep-2026, porque la primera
    versión pegaba el título con el párrafo que le seguía y perdía las
    listas):

      * El **bloque** del PDF marca dónde termina un párrafo —PyMuPDF ya los
        agrupa bien—, pero adentro se mira **renglón por renglón**: si los
        primeros renglones tienen letra más grande, ese pedazo es un título
        y el resto sigue siendo el párrafo.
      * Un título tiene que parecerlo: letra más grande y texto corto. Tres
        renglones largos con letra apenas más grande son un párrafo, no un
        `###`.
      * Las viñetas de Word viajan como una letra suelta en Wingdings o
        Symbol ("", "o"), muchas veces en un renglón aparte. Se detectan por
        la tipografía, se sacan del texto y el renglón que les corresponde
        pasa a ítem de lista, con la sangría que tenía en el PDF.
      * Se descartan encabezados y pies repetidos y los números de página.
      * Las tablas salen como tablas de Markdown.
      * Un párrafo cortado por el salto de página se vuelve a unir.
    """
    NAME = "PDF→Markdown"
    CONVERSIONS = [
        ("pdf", "md"),
    ]

    # Umbrales sobre el tamaño de letra del cuerpo para decidir el nivel de
    # título. Debajo de 1.12 no se distingue de un párrafo en negrita.
    _H1 = 1.45
    _H2 = 1.22
    _H3 = 1.12

    # Un título es corto. Con más que esto, por grande que sea la letra, es
    # un párrafo de apertura, no un encabezado.
    _MAX_RENGLONES_TITULO = 2
    _MAX_LARGO_TITULO     = 150

    # Franja de cada página que se considera margen (encabezado y pie).
    # Los documentos de sistemas de gestión —resoluciones, expedientes—
    # llevan ahí el código de barras del sistema, la paginación y la firma
    # electrónica, que en un RAG son ruido puro.
    _MARGEN_RUIDO = 0.10

    # Dentro de esa franja, ¿se borra TODO o sólo lo que parece membrete?
    # Queda en False a propósito: con el borrado a ciegas, un documento cuyo
    # texto arranca alto en la página pierde renglones enteros (probado: se
    # comía el primer ítem de una lista al pie de una hoja y arriba de la
    # siguiente). Con False se borra lo que está en la franja Y ADEMÁS es
    # letra más chica que el cuerpo, se repite entre páginas, es paginación o
    # coincide con los patrones de un sistema de gestión: en esos escritos
    # eso es exactamente el membrete, el código del sistema y la firma.
    _MARGEN_ABSOLUTO = False

    # Metadatos de sistemas de gestión documental, que aparecen en cualquier
    # parte de la hoja y no aportan nada al texto.
    _RUIDO_SISTEMA = (
        # Paginación: "Pag. 1 de 22", "Página 3/22", "- 4 -"
        r"^[\s\-–—]*p[áa]g(?:ina)?\.?\s*\d{1,4}\s*(?:de|/)\s*\d{1,4}[\s\-–—.]*$",
        # Firma electrónica: "usuario@organismo.gob - Fecha: 12/03/2026"
        r"[\w.+-]+@[\w-]+\.[\w.]+\s*[-–—|]\s*fecha\s*:",
        r"^\s*(?:documento|expediente)?\s*firmad[oa]\s+(?:digital|electr[óo]nica)mente",
        r"^\s*firma\s+(?:digital|electr[óo]nica)\b",
        # Sellos de validación del sistema
        r"^\s*(?:este|el presente)\s+documento\s+.*firma\s+(?:digital|electr[óo]nica)",
        r"\bhash\s+de\s+validaci[óo]n\b",
    )

    # Códigos de sistema / barras: "# ÑEÌ" 'K5+<Ó E02000007432111"
    _CODIGO_BARRAS = r"[A-Z]{0,2}\d{9,}"

    # El identificador de la PIEZA DIGITAL (ej. E02000007432111) NO es
    # ruido: dice de qué pieza es este documento y en un RAG hace falta
    # para poder citar la fuente. Se rescata del garabato del código de
    # barras y se pone una sola vez arriba, en vez de repetirlo por hoja.
    _PIEZA_DIGITAL = r"\b(?:[A-Z]{1,3}\d{9,}|\d{12,})\b"

    # Tipografías donde una letra suelta es en realidad una viñeta.
    _FUENTES_SIMBOLO = ("wingding", "symbol", "zapfdingbat", "dingbat")
    _VINETAS = "•▪◦‣⁃∙·○●■□"
    # Un paréntesis o una comilla NO cierran el párrafo: "…tarjetas (cards)"
    # sigue en el renglón de abajo. En los escritos formales el párrafo
    # cierra con ".-" ("…no existe embargo.-"): ese guión no es de sílaba.
    _FIN_DE_FRASE = ('.', ':', ';', '!', '?', '…', '.-', ':-', ';-', '.—')

    @classmethod
    def is_available(cls) -> bool:
        try:
            import fitz  # noqa: F401
            return True
        except ImportError:
            return False

    # ══════════════════════════════════════════════════════════════════
    def convert(self, src_path, dst_path, src_ext, dst_ext, **kwargs):
        import fitz

        doc = fitz.open(src_path)
        try:
            paginas   = doc.page_count
            elementos = []
            for page in doc:
                elementos.extend(self._leer_pagina(page))
        finally:
            doc.close()

        renglones = [e for e in elementos if e["tipo"] == "linea"]
        if not renglones and not any(e["tipo"] == "tabla" for e in elementos):
            # Un PDF que todavía se está guardando se abre sin páginas o con
            # hojas vacías: no es que le falte texto, es que no terminó.
            from motors.motor_ocr import pdf_sin_terminar, PDF_SIN_TERMINAR_MSG
            if pdf_sin_terminar(src_path):
                raise RuntimeError(PDF_SIN_TERMINAR_MSG)
            # Un PDF escaneado no tiene capa de texto y el .md saldría vacío.
            # Lo mismo el que se guardó con «Microsoft Print to PDF» desde el
            # navegador: las letras van como dibujos, sin tipografía ni texto.
            raise RuntimeError(
                "El PDF no tiene texto que extraer: sus páginas son "
                "imágenes escaneadas o letras dibujadas (pasa al guardar "
                "con «Microsoft Print to PDF»).\n"
                "Generá primero un PDF buscable (OCR con destino PDF) y "
                "convertí ese a Markdown."
            )

        # El final de una hoja repetido al principio de la siguiente.
        self._quitar_repeticion(elementos)
        renglones = [e for e in renglones if not e.get("descartar")]

        # El identificador de la pieza se lee ANTES de tirar el ruido: viaja
        # justamente adentro del renglón del código de barras.
        piezas = self._codigos_de_pieza(renglones)

        cuerpo = self._tamano_cuerpo(renglones)
        self._marcar_repetidos(renglones, paginas, cuerpo)
        elementos = [e for e in elementos if not e.get("descartar")]
        renglones = [e for e in elementos if e["tipo"] == "linea"]

        izq    = self._margen_de_listas(renglones, cuerpo)

        niveles = self._niveles_de_titulo(renglones, cuerpo)
        texto = self._armar_markdown(
            elementos, cuerpo, izq, niveles,
            marcar_paginas=kwargs.get("marcar_paginas", True))

        if piezas:
            texto = ("**Pieza digital:** " + " · ".join(piezas)
                     + "\n\n" + texto)

        with open(dst_path, "w", encoding="utf-8") as f:
            f.write(texto.strip() + "\n")

    # ══════════════════════════════════════════════════════════════════
    # Lectura del PDF
    # ══════════════════════════════════════════════════════════════════

    @classmethod
    def _leer_pagina(cls, page) -> list:
        """Renglones y tablas de una página, en orden de lectura."""
        elementos = []

        # ── Tablas ────────────────────────────────────────────────────
        tablas = []
        try:
            for t in page.find_tables().tables:
                filas = t.extract()
                if filas and len(filas) > 1:
                    tablas.append((t.bbox, filas))
        except Exception:
            pass   # find_tables no está en todas las versiones de PyMuPDF

        for bbox, filas in tablas:
            elementos.append({
                "tipo": "tabla", "filas": filas,
                # page.number viene en base cero; se guarda la hoja tal como
                # la cuenta una persona, que es la que después se cita.
                "y": bbox[1], "pagina": page.number + 1, "bloque": -1,
            })

        def dentro_de_tabla(bbox) -> bool:
            cx, cy = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
            for (tx0, ty0, tx1, ty1), _f in tablas:
                if tx0 <= cx <= tx1 and ty0 <= cy <= ty1:
                    return True
            return False

        # ── Renglones ─────────────────────────────────────────────────
        alto  = page.rect.height or 1
        datos = page.get_text("dict")
        for nb, block in enumerate(datos.get("blocks", [])):
            if block.get("type") != 0:          # 0 = texto, 1 = imagen
                continue
            for line in block.get("lines", []):
                spans = [sp for sp in line.get("spans", [])
                         if sp.get("text", "").strip()]
                if not spans:
                    continue
                bbox = line.get("bbox") or block.get("bbox") or (0, 0, 0, 0)
                if dentro_de_tabla(bbox):
                    continue
                # Texto dibujado fuera de la caja de la página: al mirar el
                # PDF no se ve (queda tapado por el borde), pero el extractor
                # lo lee igual y es una de las formas en que el final de una
                # hoja reaparece al principio de la siguiente.
                if bbox[1] >= page.rect.height or bbox[3] <= 0 \
                        or bbox[0] >= page.rect.width or bbox[2] <= 0:
                    continue

                texto = re.sub(r"[ \t]+", " ",
                               "".join(sp.get("text", "") for sp in spans)).strip()
                if not texto:
                    continue
                # "1.Arquitectura" → "1. Arquitectura": en el PDF el número y
                # el texto van separados por una tabulación que se pierde.
                texto = re.sub(r"^(\(?\d{1,3}[.)])(?=\S)", r"\1 ", texto)

                # Tamaño y negrita del renglón: manda lo que más caracteres
                # ocupa, así una nota chiquita no decide por todo el renglón.
                pesos, negrita, total = {}, 0, 0
                for sp in spans:
                    n = len(sp.get("text", ""))
                    clave = round(sp.get("size", 0), 1)
                    pesos[clave] = pesos.get(clave, 0) + n
                    if sp.get("flags", 0) & 16:
                        negrita += n
                    total += n

                elementos.append({
                    "tipo":     "linea",
                    "texto":    texto,
                    "spans":    spans,
                    "size":     max(pesos, key=pesos.get) if pesos else 0.0,
                    "negrita":  bool(total) and negrita >= total * 0.9,
                    "marcador": cls._es_marcador(spans, texto),
                    "vineta":   False,
                    "x0":       bbox[0],
                    "x1":       bbox[2],
                    "y":        bbox[1],
                    "alto":     max(bbox[3] - bbox[1], 1.0),
                    "rel_y":    bbox[1] / alto,
                    "pagina":   page.number + 1,
                    "bloque":   nb,
                    # Texto girado (leyenda en el margen lateral).
                    "vertical": abs((line.get("dir") or (1, 0))[0]) < 0.5,
                })

        elementos.sort(key=lambda e: (e["pagina"], round(e["y"], 1), e.get("x0", 0)))
        cls._resolver_vinetas(elementos)
        return elementos

    # ------------------------------------------------------------------
    @classmethod
    def _es_marcador(cls, spans, texto: str) -> bool:
        """¿El renglón es sólo la viñeta?

        Puede ser una letra en Wingdings/Symbol, un signo de viñeta, o —el
        caso más molesto— la letra "o" en Courier, que es lo que Word usa
        para el segundo nivel de las listas. Un renglón de una sola letra
        nunca es texto: si además hay texto a su derecha, es una viñeta.
        """
        if len(texto) > 2:
            return False
        if texto in cls._VINETAS or texto in "-–—*§":
            return True
        fuente = (spans[0].get("font") or "").lower()
        if any(f in fuente for f in cls._FUENTES_SIMBOLO):
            return True
        return len(texto) == 1 and texto.isalpha()

    # ------------------------------------------------------------------
    @classmethod
    def _resolver_vinetas(cls, elementos) -> None:
        """Convierte los marcadores sueltos en viñetas del renglón que sigue.

        En los PDF de Word la viñeta suele venir como un renglón aparte, a la
        izquierda del texto y a la misma altura. Si se deja, el .md queda con
        una "o" suelta en el medio del texto.
        """
        lineas = [e for e in elementos if e["tipo"] == "linea"]
        for i, e in enumerate(lineas):
            if not e.get("marcador"):
                continue
            # El texto del ítem: el renglón más cercano en altura, a la
            # derecha del marcador.
            candidatos = [
                o for o in lineas
                if not o.get("marcador") and not o.get("descartar")
                and o["pagina"] == e["pagina"]
                and abs(o["y"] - e["y"]) <= e["alto"] * 0.8
                and o["x0"] >= e["x0"]
            ]
            if candidatos:
                destino = min(candidatos, key=lambda o: (abs(o["y"] - e["y"]),
                                                         o["x0"]))
            elif len(e["texto"]) == 1 and e["texto"].isalpha():
                continue      # una letra suelta sin texto al lado: no es viñeta
            elif i + 1 < len(lineas):
                destino = lineas[i + 1]
            else:
                continue
            e["descartar"] = True
            destino["vineta"] = True
            destino["x0"] = min(destino["x0"], e["x0"])

        # Una viñeta que quedó escrita dentro del texto (PDF sin fuente de
        # símbolos) también vale.
        for e in lineas:
            if e.get("descartar") or e["vineta"]:
                continue
            if e["texto"][:1] in cls._VINETAS and len(e["texto"]) > 2:
                e["texto"] = e["texto"][1:].lstrip()
                e["vineta"] = True

    # ══════════════════════════════════════════════════════════════════
    # Limpieza: encabezados, pies y números de página
    # ══════════════════════════════════════════════════════════════════

    @staticmethod
    def _es_numero_de_pagina(texto: str) -> bool:
        t = texto.strip(" .-–—|")
        if t.isdigit() and len(t) <= 4:
            return True
        return bool(re.match(
            r"^(p[áa]g(ina)?\.?\s*)?\d{1,4}\s*(de|/)\s*\d{1,4}$", t, re.I))

    @classmethod
    def _quitar_repeticion(cls, elementos: list) -> None:
        """Marca el arranque de cada hoja que repite el final de la anterior.

        Mismo criterio que en PDF→TXT: dos renglones repetidos, o uno solo
        pero largo. Ver `quitar_repeticion_entre_paginas`.
        """
        por_pagina = {}
        orden = []
        for e in elementos:
            if e["tipo"] != "linea":
                continue
            if e["pagina"] not in por_pagina:
                por_pagina[e["pagina"]] = []
                orden.append(e["pagina"])
            por_pagina[e["pagina"]].append(e)

        anterior = []
        for pagina in orden:
            lineas = por_pagina[pagina]
            actual = [_clave_renglon(l["texto"]) for l in lineas]

            cortar = 0
            tope = min(len(anterior), len(actual), _MAX_RENGLONES_REPETIDOS)
            for k in range(tope, 0, -1):
                if anterior[-k:] == actual[:k]:
                    largo = sum(len(t) for t in actual[:k])
                    if k >= 2 or largo >= _MIN_LARGO_REPETIDO:
                        cortar = k
                        break

            for l in lineas[:cortar]:
                l["descartar"] = True
            if actual[cortar:]:
                anterior = actual[cortar:]

    @classmethod
    def _codigos_de_pieza(cls, renglones: list) -> list:
        """Identificadores de pieza digital del documento, sin repetir."""
        vistos = []
        for r in renglones:
            for codigo in re.findall(cls._PIEZA_DIGITAL, r["texto"]):
                if codigo not in vistos:
                    vistos.append(codigo)
        return vistos

    @classmethod
    def _es_ruido_de_sistema(cls, texto: str) -> bool:
        """Metadatos del sistema de gestión que no son parte del documento.

        Paginación, firmas electrónicas con fecha, sellos de validación y los
        códigos de barra de sistemas de gestión, que se leen como una sopa de símbolos
        (`# ÑEÌ" 'K5+<Ó E02000007432111`).
        """
        t = texto.strip()
        if not t:
            return True

        bajo = t.lower()
        for patron in cls._RUIDO_SISTEMA:
            if re.search(patron, bajo, re.I):
                return True

        # Código de barras: una tira larga de dígitos, sola o rodeada
        # de símbolos que no forman palabras.
        if re.search(cls._CODIGO_BARRAS, t):
            letras = sum(c.isalpha() for c in t)
            palabras = [w for w in re.split(r"\s+", t) if len(w) > 3 and w.isalpha()]
            if len(palabras) <= 1 or letras < len(t) * 0.35:
                return True

        # Renglón sin una sola palabra de verdad: puro símbolo o número.
        sin_espacios = re.sub(r"\s", "", t)
        if len(sin_espacios) >= 6:
            raros = sum(1 for c in sin_espacios
                        if not (c.isalnum() or c in ".,;:()/-–—°ºªNn"))
            if raros >= len(sin_espacios) * 0.30:
                return True

        return False

    @classmethod
    def _marcar_repetidos(cls, renglones: list, paginas: int,
                          cuerpo: float = 0.0) -> None:
        """Descarta el ruido: márgenes, metadatos del sistema y repetidos.

        Se borra todo lo que caiga en el 10% de arriba o de abajo de la hoja
        —ahí viven el código del sistema, la paginación y la firma electrónica—,
        salvo que la letra sea más grande que la del cuerpo: un título de
        capítulo arranca alto en la página y no hay que comérselo.
        """
        def en_el_margen(r) -> bool:
            if cuerpo and r["size"] > cuerpo * 1.15:
                return False               # un título grande no es membrete
            return (r["rel_y"] < cls._MARGEN_RUIDO
                    or r["rel_y"] > 1 - cls._MARGEN_RUIDO)

        def es_membrete(r) -> bool:
            """Letra más chica que el cuerpo: sello, código o pie de página."""
            return bool(cuerpo) and r["size"] < cuerpo * 0.95

        for r in renglones:
            if cls._es_ruido_de_sistema(r["texto"]):
                r["descartar"] = True      # el ruido del sistema va en
                continue                   # cualquier parte de la hoja
            if en_el_margen(r) and (cls._MARGEN_ABSOLUTO or es_membrete(r)
                                    or cls._es_numero_de_pagina(r["texto"])):
                r["descartar"] = True

        from collections import defaultdict

        # Leyenda girada en el margen lateral que se repite en varias hojas
        # ("Anexo - Resolución S.P.C. N° 2/26 …"): es un pie de página puesto
        # de costado. No cae en la franja de arriba/abajo, por eso va aparte.
        girados = defaultdict(set)
        for r in renglones:
            if r.get("vertical"):
                girados[re.sub(r"\d+", "#", r["texto"].strip().lower())] \
                    .add(r["pagina"])
        for r in renglones:
            if r.get("vertical") and len(girados[re.sub(
                    r"\d+", "#", r["texto"].strip().lower())]) >= 2:
                r["descartar"] = True

        if paginas < 3:
            return

        vistos = defaultdict(set)
        for r in renglones:
            if en_el_margen(r):
                clave = re.sub(r"\d+", "#", r["texto"].strip().lower())
                if len(clave) > 3:
                    vistos[clave].add(r["pagina"])

        repetidos = {c for c, pgs in vistos.items()
                     if len(pgs) >= max(3, paginas * 0.6)}
        for r in renglones:
            if en_el_margen(r):
                clave = re.sub(r"\d+", "#", r["texto"].strip().lower())
                if clave in repetidos:
                    r["descartar"] = True

    # ══════════════════════════════════════════════════════════════════
    # Medidas del documento
    # ══════════════════════════════════════════════════════════════════

    @classmethod
    def _niveles_de_titulo(cls, renglones: list, cuerpo: float) -> dict:
        """Qué nivel (#, ##, ###) le toca a cada tamaño de letra.

        El más grande del documento es el #, el que sigue el ##, y así. Con
        umbrales fijos, un h1 y un h2 de Word caían los dos en "#".
        """
        tamanos = sorted({round(r["size"], 1) for r in renglones
                          if (cuerpo and r["size"] / cuerpo >= cls._H3)
                          or cls._titulo_de_escrito(r["texto"])},
                         reverse=True)
        return {t: min(i + 1, 3) for i, t in enumerate(tamanos)}

    @staticmethod
    def _tamano_cuerpo(renglones: list) -> float:
        """Tamaño de letra del cuerpo: el que más caracteres acumula."""
        from collections import Counter
        c = Counter()
        for r in renglones:
            c[round(r["size"], 1)] += len(r["texto"])
        return c.most_common(1)[0][0] if c else 12.0

    @classmethod
    def _margen_de_listas(cls, renglones: list, cuerpo: float) -> float:
        """Desde dónde arranca el primer nivel de las listas.

        Se mide contra los propios ítems y no contra el margen del cuerpo:
        una lista entera corrida a la derecha es de primer nivel igual, y no
        tiene por qué salir anidada en el Markdown.
        """
        # Los títulos numerados ("1. Antecedentes") no cuentan: no son ítems
        # de lista y correrían el margen hacia la izquierda.
        items = [r["x0"] for r in renglones
                 if (r.get("vineta") or cls._empieza_numerado(r["texto"]))
                 and (not cuerpo or r["size"] <= cuerpo * 1.05)]
        if items:
            return min(items)
        from collections import Counter
        c = Counter(round(r["x0"]) for r in renglones
                    if abs(r["size"] - cuerpo) < 0.6)
        return float(c.most_common(1)[0][0]) if c else 0.0

    # ══════════════════════════════════════════════════════════════════
    # Armado del Markdown
    # ══════════════════════════════════════════════════════════════════

    @classmethod
    def _armar_markdown(cls, elementos, cuerpo, izq, niveles=None,
                        marcar_paginas: bool = True) -> str:
        salida = []

        # Los renglones se agrupan por bloque del PDF: el bloque es el
        # párrafo. Las tablas se intercalan donde corresponde.
        grupos = []
        for e in elementos:
            if e["tipo"] == "tabla":
                grupos.append(("tabla", e, e.get("pagina", 0)))
                continue
            clave = (e["pagina"], e["bloque"])
            if grupos and grupos[-1][0] == "bloque" and grupos[-1][1] == clave:
                grupos[-1][2].append(e)
            else:
                grupos.append(("bloque", clave, [e]))

        pagina_actual = None
        for grupo in grupos:
            # El número de hoja se intercala como un renglón aparte, para
            # poder citar después de dónde salió cada cosa.
            if marcar_paginas:
                pagina = grupo[2] if grupo[0] == "tabla" else grupo[1][0]
                if pagina and pagina != pagina_actual:
                    salida.append(("pagina", MARCADOR_PAGINA.format(pagina)))
                    pagina_actual = pagina

            if grupo[0] == "tabla":
                salida.append(("tabla", cls._tabla_markdown(grupo[1]["filas"])))
                continue
            for pieza in cls._piezas_del_bloque(grupo[2], cuerpo, izq, niveles):
                salida.append(pieza)

        return cls._unir(cls._pegar_cortes(salida))

    # ------------------------------------------------------------------
    @classmethod
    def _piezas_del_bloque(cls, lineas, cuerpo, izq, niveles=None) -> list:
        """Parte un bloque del PDF en títulos, ítems de lista y párrafos."""
        # Un renglón corto en negrita es un subtítulo sólo si está solo:
        # varios renglones seguidos en negrita son un párrafo destacado, no
        # una fila de títulos.
        solos = set()
        for i, ln in enumerate(lineas):
            if not ln["negrita"]:
                continue
            antes   = i > 0 and lineas[i - 1]["negrita"]
            despues = i + 1 < len(lineas) and lineas[i + 1]["negrita"]
            if not antes and not despues:
                solos.add(id(ln))

        piezas = []
        actual = []          # renglones que se están juntando
        modo   = None        # ("titulo", nivel) | ("vineta", nivel) | ("p", 0)

        def cerrar():
            if not actual:
                return
            texto = cls._juntar([cls._inline(l) for l in actual])
            tipo, nivel = modo
            if tipo == "titulo":
                piezas.append(("titulo", "#" * nivel + " " + cls._plano(texto)))
            elif tipo == "vineta":
                piezas.append(("lista:v", "  " * nivel + "- " + texto))
            elif tipo == "numero":
                piezas.append(("lista:n", "  " * nivel + texto))
            else:
                piezas.append(("parrafo", cls._escapar(texto)))
            actual.clear()

        for ln in lineas:
            nuevo = cls._modo_de(ln, lineas, cuerpo, izq, id(ln) in solos,
                                 niveles)
            if modo is None or nuevo != modo or nuevo[0] in ("vineta", "numero"):
                # Los ítems de lista empiezan siempre pieza nueva; los
                # renglones que continúan un ítem no traen marcador y caen
                # en el "continuar" de más abajo.
                if nuevo[0] in ("vineta", "numero") and not (
                        ln["vineta"] or cls._empieza_numerado(ln["texto"])):
                    actual.append(ln)
                    continue
                cerrar()
                modo = nuevo
            actual.append(ln)
        cerrar()
        return piezas

    # ------------------------------------------------------------------
    # ── Títulos: criterio estricto ────────────────────────────────────
    #
    # En un escrito formal hay nombres propios, DNI y números de causa sueltos en
    # su propio renglón. Si cualquiera de esos se convierte en "##", el
    # chunking del RAG parte el texto por la mitad y mete basura en el índice.
    # Por eso un renglón es título sólo si se gana el lugar.

    _ROMANO  = r"^\(?[IVXLCDM]{1,7}\)?\s*[.\-–—)]+\s+\S"
    _INCISO  = r"^\(?[a-zA-Z]\)\s+\S"
    _DNI     = r"\b\d{1,3}\.?\d{3}\.?\d{3}\b|\b\d{7,9}\b"
    _CAUSA   = r"\b(?:CAUSA|EXPTE?|LEGAJO)\b|\bN[°ºo]\.?\s*\d{2,}"

    @classmethod
    def _titulo_prohibido(cls, texto: str) -> bool:
        """Lo que NUNCA puede ser un título, por más grande que sea la letra."""
        t = texto.strip()
        if not t:
            return True
        # Empieza en minúscula: es la continuación de un párrafo. La única
        # excepción son los incisos de un escrito formal: a), b), c).
        if t[0].islower() and not re.match(cls._INCISO, t):
            return True
        if len(t) > 90:
            return True
        if re.search(cls._DNI, t) or re.search(cls._CAUSA, t, re.I):
            return True
        digitos = sum(c.isdigit() for c in t)
        if digitos > len(t) * 0.40:
            return True
        if t.endswith((",", ";", "y", "e", "o", "u")):
            return True
        # Nombre propio suelto ("Juan Carlos Pérez"): pocas palabras, todas
        # con mayúscula inicial y sin dos puntos al final.
        palabras = t.split()
        if (not t.isupper() and len(palabras) <= 4 and not t.endswith(":")
                and all(w[:1].isupper() for w in palabras if w[:1].isalpha())):
            return True
        return False

    @classmethod
    def _titulo_de_escrito(cls, texto: str):
        """Nivel de título por la forma del renglón, o None si no lo es.

        Vale por sí solo, sin mirar el tamaño de letra:
          * TODO EN MAYÚSCULAS y corto  → "SOLICITA ALLANAMIENTO"
          * numeración romana           → "I.- OBJETO:", "VII. PETITORIO:"
          * inciso                      → "a) …", "b) …"
        """
        t = texto.strip()
        if re.match(cls._ROMANO, t):
            return 2
        if re.match(cls._INCISO, t):
            return 3
        letras = [c for c in t if c.isalpha()]
        if letras and all(c.isupper() for c in letras) and len(t) <= 80:
            return 2
        return None

    @classmethod
    def _modo_de(cls, linea, lineas, cuerpo, izq, negrita_sola=False,
                 niveles=None):
        """Qué es este renglón dentro de su bloque.

        El tamaño de letra se mira primero: un título numerado ("1.
        Antecedentes", habitual en informes y expedientes) sigue siendo un
        título, no el primer ítem de una lista.
        """
        texto = linea["texto"]
        ratio = linea["size"] / cuerpo if cuerpo else 1.0

        # Nada que empiece en minúscula, ni un DNI, ni un número de causa, ni
        # un nombre suelto pueden ser título, aunque estén en negrita o con
        # letra más grande.
        if cls._titulo_prohibido(texto):
            if linea["vineta"]:
                return ("vineta", cls._sangria(linea, izq))
            if cls._empieza_numerado(texto):
                return ("numero", cls._sangria(linea, izq))
            return ("p", 0)

        # Renglón que sigue a una oración sin cerrar del cuerpo ("…la suma
        # de PESOS: TREINTA y" / "TRES MILLONES…"): es la misma oración,
        # aunque venga en mayúsculas. Se mira la oración abierta hacia arriba
        # (renglones seguidos sin puntuación final): si en algún renglón hay
        # minúsculas es texto del cuerpo; si todos están en mayúsculas son
        # dos renglones de un mismo título.
        i = next((k for k, l in enumerate(lineas) if l is linea), 0)
        abierta = False
        for k in range(i - 1, -1, -1):
            previo = lineas[k]["texto"].strip()
            if not previo or previo.endswith(cls._FIN_DE_FRASE):
                break
            if any(c.islower() for c in previo):
                abierta = True
                break
        if abierta:
            if not re.match(cls._ROMANO, texto.strip()) \
                    and not re.match(cls._INCISO, texto.strip()) \
                    and not linea["vineta"] \
                    and not cls._empieza_numerado(texto):
                return ("p", 0)

        # Forma de título del escrito: manda sobre el tamaño.
        de_escrito = cls._titulo_de_escrito(texto)
        if de_escrito:
            if de_escrito == 2 and texto.strip().isupper():
                # Entre los títulos en mayúsculas, el de letra más grande es
                # la carátula del escrito ("SOLICITA ALLANAMIENTO").
                de_escrito = (niveles or {}).get(round(linea["size"], 1), 2)
            return ("titulo", de_escrito)

        nivel = 0
        if ratio >= cls._H3:
            nivel = (niveles or {}).get(round(linea["size"], 1))
            if not nivel:
                nivel = 1 if ratio >= cls._H1 else (2 if ratio >= cls._H2 else 3)
        elif negrita_sola and len(texto) <= 90 \
                and not texto.endswith((".", ";", ",")):
            # Renglón corto y todo en negrita: subtítulo del mismo cuerpo.
            # Acá no corresponde el control de "hermanos" de abajo: la letra
            # es la del cuerpo, así que todos los renglones del bloque serían
            # hermanos y nunca sería título.
            return ("titulo", 3)

        if nivel:
            # Un título tiene que parecerlo: los renglones seguidos con esa
            # misma letra tienen que ser pocos y cortos. Si no, es un párrafo
            # de apertura con letra un poco más grande.
            hermanos = [l for l in lineas if abs(l["size"] - linea["size"]) < 0.3]
            largo    = sum(len(l["texto"]) for l in hermanos)
            if len(hermanos) <= cls._MAX_RENGLONES_TITULO and \
                    largo <= cls._MAX_LARGO_TITULO:
                return ("titulo", nivel)

        if linea["vineta"]:
            return ("vineta", cls._sangria(linea, izq))
        if cls._empieza_numerado(linea["texto"]):
            return ("numero", cls._sangria(linea, izq))
        return ("p", 0)

    # ------------------------------------------------------------------
    @staticmethod
    def _sangria(linea, izq_lista) -> int:
        """Nivel de anidado del ítem, por lo que está corrido en la hoja."""
        return min(3, max(0, int(round((linea["x0"] - izq_lista) / 18.0))))

    # ------------------------------------------------------------------
    @staticmethod
    def _empieza_numerado(texto: str) -> bool:
        return bool(re.match(r"^\(?\d{1,3}[.)]\s*\S", texto))

    # ------------------------------------------------------------------
    @staticmethod
    def _juntar(textos) -> str:
        """Une los renglones de un párrafo respetando el guión de sílaba."""
        texto = textos[0] if textos else ""
        for ln in textos[1:]:
            # Guión de sílaba sólo si lo precede una letra: ".-" y " -" no lo son.
            if texto.endswith("-") and len(texto) > 1 and texto[-2].isalpha():
                texto = texto[:-1] + ln
            else:
                texto += " " + ln
        return re.sub(r"\s+", " ", texto).strip()

    # ------------------------------------------------------------------
    @classmethod
    def _pegar_cortes(cls, piezas) -> list:
        """Vuelve a unir el párrafo que quedó cortado por el salto de página."""
        salida = []
        for tipo, texto in piezas:
            # El marcador de página se intercala en el medio pero no corta el
            # párrafo: se mira la pieza de texto anterior salteándolo, y la
            # continuación se pega arriba del marcador. Así el párrafo que
            # empieza en una hoja y termina en la otra queda entero y contado
            # en la hoja donde empezó, que es como se cita.
            i = len(salida) - 1
            while i >= 0 and salida[i][0] == "pagina":
                i -= 1
            if i >= 0 and tipo == "parrafo" \
                    and (salida[i][0] == "parrafo"
                         or salida[i][0].startswith("lista")):
                previo = salida[i][1].rstrip()
                # Si el renglón anterior no cerró la oración, esto es la
                # continuación del mismo párrafo (o del mismo ítem) partida
                # por un salto de página o de bloque. El caso obligatorio es
                # "termina sin puntuación final y sigue en minúscula": ahí el
                # salto de línea del PDF rompe la oración al medio.
                if previo and not previo.endswith(cls._FIN_DE_FRASE):
                    salida[i] = (salida[i][0], cls._juntar([previo, texto]))
                    continue
            salida.append((tipo, texto))
        return salida

    # ------------------------------------------------------------------
    @staticmethod
    def _unir(piezas) -> str:
        """Un renglón en blanco entre piezas; los ítems de una lista, pegados."""
        texto, previo = "", None
        for tipo, bloque in piezas:
            if not texto:
                texto = bloque
            elif tipo.startswith("lista") and tipo == previo:
                texto += "\n" + bloque
            else:
                texto += "\n\n" + bloque
            previo = tipo
        return texto

    # ------------------------------------------------------------------
    @classmethod
    def _inline(cls, linea) -> str:
        """Marca en **negrita** los tramos en negrita dentro del renglón.

        Si el renglón entero está en negrita no se marca nada: sería ruido, y
        ese caso ya se resolvió antes como subtítulo.
        """
        spans = linea.get("spans") or []
        texto = linea["texto"]
        if linea.get("negrita") or len(spans) < 2:
            return texto

        partes = []
        for sp in spans:
            t = sp.get("text", "")
            nucleo = t.strip()
            if not nucleo:
                partes.append(t)
                continue
            izq = " " if t[:1] == " " else ""
            der = " " if t[-1:] == " " else ""
            if sp.get("flags", 0) & 16:
                partes.append(f"{izq}**{nucleo}**{der}")
            else:
                partes.append(t)
        armado = re.sub(r"[ \t]+", " ", "".join(partes)).strip()
        armado = re.sub(r"\*\*\s*\*\*", " ", armado)        # negritas vacías
        # "1.**Arquitectura**" → "1. **Arquitectura**": el número y el
        # texto vienen en spans distintos y el espacio se pierde.
        armado = re.sub(r"^(\(?\d{1,3}[.)])(?=\S)", r"\1 ", armado)
        if armado.count("**") % 2:
            return texto
        # Si al sacar las marcas no queda el mismo texto, algo salió mal.
        limpio = armado.replace("**", "")
        if re.sub(r"\s", "", limpio) != re.sub(r"\s", "", texto):
            return texto
        return armado

    # ------------------------------------------------------------------
    @staticmethod
    def _plano(texto: str) -> str:
        """Un título no necesita negritas adentro."""
        return texto.replace("**", "")

    # ------------------------------------------------------------------
    @staticmethod
    def _escapar(texto: str) -> str:
        """Neutraliza lo que Markdown interpretaría como sintaxis.

        Un "#" de número de expediente al principio del renglón convertiría
        el párrafo entero en un título.
        """
        return re.sub(r"^([#>|])", r"\\\1", texto)

    # ------------------------------------------------------------------
    @staticmethod
    def _tabla_markdown(filas) -> str:
        limpias = []
        for fila in filas:
            limpias.append([
                re.sub(r"\s+", " ", (c or "")).strip().replace("|", "\\|")
                for c in fila
            ])
        ancho = max(len(f) for f in limpias)
        for f in limpias:
            f.extend([""] * (ancho - len(f)))

        encabezado = limpias[0]
        if any(encabezado):
            cuerpo = limpias[1:]
        else:
            encabezado = [f"Columna {i + 1}" for i in range(ancho)]
            cuerpo = limpias

        lineas = ["| " + " | ".join(encabezado) + " |",
                  "|" + "|".join([" --- "] * ancho) + "|"]
        for f in cuerpo:
            lineas.append("| " + " | ".join(f) + " |")
        return "\n".join(lineas)


# ---------------------------------------------------------------------------
# Motor pdf2docx — PDF → DOCX conservando layout (tablas, columnas, imágenes)
# ---------------------------------------------------------------------------

class PdfToDocxMotor(BaseMotor):
    NAME = "pdf2docx"
    CONVERSIONS = [
        ("pdf", "docx"),
    ]

    # Un renglón se considera rotado cuando su vector de dirección se aparta
    # de la horizontal (1, 0). El margen tolera el redondeo del propio PDF.
    _TOLERANCIA_DIR = 0.01

    @classmethod
    def is_available(cls) -> bool:
        try:
            import pdf2docx  # noqa: F401
            return True
        except ImportError:
            return False

    @staticmethod
    def _es_rotado(direccion) -> bool:
        dx, dy = direccion
        return abs(dy) > PdfToDocxMotor._TOLERANCIA_DIR or dx < 1 - PdfToDocxMotor._TOLERANCIA_DIR

    @classmethod
    def _sin_texto_rotado(cls, src_path, progress_cb=None):
        """Copia el PDF sin los renglones girados. Devuelve (ruta, es_temporal).

        Los sellos que corren verticales por el margen —el "Anexo - Resolución
        S.P.C. N° …" de algunos anexos— pdf2docx no los sabe girar: los
        acuesta en una columna angosta a la izquierda, partidos en varios
        renglones, y esa columna le corre el ancho al resto de la hoja. Sale
        mejor sacarlos antes de reconstruir el layout y avisar que se omitieron,
        que dejarlos deformando la página.

        Se borra solo el texto: las imágenes y las líneas quedan intactas, así
        que la raya vertical del margen sigue estando donde estaba.
        """
        try:
            import fitz
        except ImportError:
            return src_path, False

        doc = fitz.open(src_path)
        try:
            omitidos = []
            for pagina in doc:
                marcas = 0
                for bloque in pagina.get_text("dict")["blocks"]:
                    if bloque.get("type") != 0:      # 0 = texto; 1 = imagen
                        continue
                    for renglon in bloque["lines"]:
                        if not cls._es_rotado(renglon.get("dir", (1, 0))):
                            continue
                        texto = "".join(s["text"] for s in renglon["spans"]).strip()
                        if texto:
                            omitidos.append(texto)
                        pagina.add_redact_annot(fitz.Rect(renglon["bbox"]), fill=None)
                        marcas += 1
                if marcas:
                    pagina.apply_redactions(
                        images=fitz.PDF_REDACT_IMAGE_NONE,
                        graphics=fitz.PDF_REDACT_LINE_ART_NONE,
                        text=fitz.PDF_REDACT_TEXT_REMOVE,
                    )

            if not omitidos:
                return src_path, False

            if progress_cb:
                distintos = list(dict.fromkeys(omitidos))
                muestra = "; ".join(t[:60] for t in distintos[:3])
                if len(distintos) > 3:
                    muestra += "; …"
                cuantos = ("un renglón" if len(omitidos) == 1
                           else f"{len(omitidos)} renglones")
                progress_cb(
                    f"⚠ Se omitió texto vertical del margen ({cuantos}): {muestra}"
                )
                progress_cb(
                    "⚠ El resto de la hoja se respeta; ese texto solo figura "
                    "en el PDF original."
                )

            from core.paths import TEMP_DIR
            kw = {"suffix": ".pdf", "delete": False}
            if TEMP_DIR:
                kw["dir"] = TEMP_DIR
            tmp = tempfile.NamedTemporaryFile(**kw)
            tmp.close()
            doc.save(tmp.name, garbage=3, deflate=True)
            return tmp.name, True
        finally:
            doc.close()

    def convert(self, src_path, dst_path, src_ext, dst_ext,
                progress_cb=None, **kwargs):
        from pdf2docx import Converter
        if progress_cb:
            progress_cb("📄 Reconstruyendo layout PDF → DOCX...")

        origen, es_temporal = self._sin_texto_rotado(src_path, progress_cb)
        try:
            cv = Converter(origen)
            try:
                cv.convert(dst_path)
            finally:
                cv.close()
        finally:
            if es_temporal:
                try:
                    os.unlink(origen)
                except OSError:
                    pass


# ---------------------------------------------------------------------------
# Motores de markup puro Python (sin Pandoc): HTML→MD, TXT→MD, RST, IPYNB
# ---------------------------------------------------------------------------

class HtmlToMdMotor(BaseMotor):
    NAME = "html→markdown"
    CONVERSIONS = [
        ("html", "md"), ("htm", "md"),
    ]

    @classmethod
    def is_available(cls) -> bool:
        try:
            import markdownify  # noqa: F401
            return True
        except ImportError:
            return False

    def convert(self, src_path, dst_path, src_ext, dst_ext, **kwargs):
        import chardet
        from markdownify import markdownify as md
        with open(src_path, "rb") as f:
            raw = f.read()
        enc = (chardet.detect(raw).get("encoding") or "utf-8")
        text = md(raw.decode(enc, errors="replace"), heading_style="ATX")
        with open(dst_path, "w", encoding="utf-8") as f:
            f.write(text)


class TxtToMdMotor(BaseMotor):
    """El texto plano ya es Markdown válido: se copia normalizando encoding."""
    NAME = "txt→markdown"
    CONVERSIONS = [
        ("txt", "md"),
    ]

    def convert(self, src_path, dst_path, src_ext, dst_ext, **kwargs):
        import chardet
        with open(src_path, "rb") as f:
            raw = f.read()
        enc = (chardet.detect(raw).get("encoding") or "utf-8")
        with open(dst_path, "w", encoding="utf-8") as f:
            f.write(raw.decode(enc, errors="replace"))


class DocutilsMotor(BaseMotor):
    """reStructuredText → HTML con docutils (puro Python).
    rst→pdf y rst→docx se resuelven por cadena (rst→html→pdf/docx)."""
    NAME = "docutils"
    CONVERSIONS = [
        ("rst", "html"),
    ]

    @classmethod
    def is_available(cls) -> bool:
        try:
            import docutils  # noqa: F401
            return True
        except ImportError:
            return False

    def convert(self, src_path, dst_path, src_ext, dst_ext, **kwargs):
        from docutils.core import publish_file
        publish_file(source_path=src_path, destination_path=dst_path,
                     writer_name="html5")


class IpynbMotor(BaseMotor):
    """Jupyter Notebook → HTML sin nbconvert: parsea el JSON del notebook,
    renderiza celdas markdown (paquete 'markdown') y código en <pre>.
    ipynb→pdf se resuelve por cadena (ipynb→html→pdf)."""
    NAME = "ipynb→html"
    CONVERSIONS = [
        ("ipynb", "html"),
    ]

    def convert(self, src_path, dst_path, src_ext, dst_ext, **kwargs):
        import html as html_mod
        import json

        import markdown as md_mod

        with open(src_path, "r", encoding="utf-8") as f:
            nb = json.load(f)

        parts = [
            "<html><head><meta charset='utf-8'><style>",
            "body{font-family:sans-serif;max-width:900px;margin:2em auto;padding:0 1em}",
            "pre{background:#f4f4f4;padding:.8em;border-radius:6px;overflow-x:auto}",
            ".out{background:#fffbe6;border-left:3px solid #e0c000;padding:.5em .8em}",
            "img{max-width:100%}",
            "</style></head><body>",
        ]
        for cell in nb.get("cells", []):
            src = "".join(cell.get("source", []))
            ctype = cell.get("cell_type")
            if ctype == "markdown":
                parts.append(md_mod.markdown(src, extensions=["tables", "fenced_code"]))
            elif ctype == "code":
                parts.append(f"<pre><code>{html_mod.escape(src)}</code></pre>")
                for out in cell.get("outputs", []):
                    data = out.get("data", {})
                    if "image/png" in data:
                        b64 = "".join(data["image/png"]).replace("\n", "")
                        parts.append(f'<img src="data:image/png;base64,{b64}"/>')
                    elif "text/html" in data:
                        parts.append("".join(data["text/html"]))
                    elif "text/plain" in data:
                        txt = html_mod.escape("".join(data["text/plain"]))
                        parts.append(f'<div class="out"><pre>{txt}</pre></div>')
                    elif out.get("output_type") == "stream":
                        txt = html_mod.escape("".join(out.get("text", [])))
                        parts.append(f'<div class="out"><pre>{txt}</pre></div>')
        parts.append("</body></html>")

        with open(dst_path, "w", encoding="utf-8") as f:
            f.write("\n".join(parts))
