"""
core/texto_natural.py — De un texto escrito normal a Markdown.

La idea: que el usuario escriba como escribe siempre —como en un Word— sin
tener que aprender a poner `##` ni `**`. El programa deduce la estructura de
la forma en que uno ya escribe:

  * un renglón corto TODO EN MAYÚSCULAS es un título;
  * la numeración romana ("I.- OBJETO:") también;
  * los incisos "a)", "b)" quedan destacados;
  * un guión al principio del renglón arma una viñeta;
  * un renglón en blanco separa párrafos;
  * y el punto manda: si un renglón no cierra con punto y el siguiente
    empieza en minúscula, es la misma oración partida en dos, y se une.

Son las mismas reglas con las que se lee un PDF escaneado (ver
`motors/motor_documents.py`, PdfToMdMotor), pero al revés: acá se escribe.
"""
import re

# Un título es corto: más largo que esto es un párrafo en mayúsculas.
MAX_TITULO = 80

FIN_DE_FRASE = (".", ":", ";", "!", "?", "…")

_ROMANO   = r"^\(?[IVXLCDM]{1,7}\)?\s*[.\-–—)]+\s+\S"
_INCISO   = r"^\(?[a-zA-Z]\)\s+\S"
_NUMERADO = r"^\(?\d{1,3}[.)]\s+\S"
_VINETA   = r"^[-*•▪◦‣]\s+\S"


# Lo que se le muestra al usuario en el panel de escritura.
REGLAS = [
    ("🔠", "MAYÚSCULAS", "Un renglón corto todo en mayúsculas se convierte "
                         "en título.", "SOLICITA ALLANAMIENTO"),
    ("🔢", "Números romanos", "Sirven para las secciones.", "I.- OBJETO:"),
    ("🔡", "Incisos", "Las letras con paréntesis quedan destacadas.",
     "a) El registro del inmueble."),
    ("▪", "Viñetas", "Un guión al principio del renglón arma una lista.",
     "- Primer punto"),
    ("⏎", "Renglón en blanco", "Separa un párrafo del siguiente.", ""),
    ("⏺", "El punto", "Si un renglón no termina con punto y el que sigue "
                      "empieza en minúscula, se unen en la misma oración.", ""),
]


def _es_titulo_mayusculas(texto: str) -> bool:
    letras = [c for c in texto if c.isalpha()]
    return bool(letras) and all(c.isupper() for c in letras) \
        and len(texto) <= MAX_TITULO


def _tipo_de(linea: str, primera: bool) -> tuple:
    """Qué es este renglón: (tipo, texto limpio)."""
    t = linea.strip()
    if not t:
        return ("blanco", "")
    if re.match(_VINETA, t):
        return ("vineta", t[1:].strip())
    if re.match(_INCISO, t):
        return ("inciso", t)
    if re.match(_NUMERADO, t):
        return ("numero", t)
    if re.match(_ROMANO, t):
        return ("titulo2", t)
    if _es_titulo_mayusculas(t):
        return ("titulo1" if primera else "titulo2", t)
    return ("texto", t)


def _escapar(texto: str) -> str:
    """Lo que Markdown leería como sintaxis y acá es texto común."""
    return re.sub(r"^([#>|])", r"\\\1", texto)


def a_markdown(texto: str) -> str:
    """Convierte un texto escrito normal en Markdown con estructura."""
    if not texto or not texto.strip():
        return ""

    lineas = texto.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    piezas = []      # [(tipo, texto)] listos para escribir
    parrafo = []     # renglones del párrafo en curso
    hubo_titulo = False

    def cerrar_parrafo():
        if parrafo:
            piezas.append(("parrafo", "  \n".join(parrafo)))
            parrafo.clear()

    primera_util = True
    for linea in lineas:
        tipo, limpio = _tipo_de(linea, primera_util and not hubo_titulo)

        if tipo == "blanco":
            cerrar_parrafo()
            continue

        primera_util = False

        if tipo in ("titulo1", "titulo2"):
            cerrar_parrafo()
            hubo_titulo = True
            piezas.append((tipo, limpio))
            continue

        if tipo == "inciso":
            cerrar_parrafo()
            piezas.append(("inciso", limpio))
            continue

        if tipo in ("vineta", "numero"):
            cerrar_parrafo()
            piezas.append((tipo, limpio))
            continue

        # Texto común: ¿sigue la oración anterior o es un renglón nuevo?
        if parrafo and not parrafo[-1].rstrip().endswith(FIN_DE_FRASE) \
                and limpio[:1].islower():
            parrafo[-1] = parrafo[-1].rstrip() + " " + limpio
        else:
            parrafo.append(_escapar(limpio))

    cerrar_parrafo()

    # ── Armado final ──────────────────────────────────────────────────
    salida = []
    previo = None
    for tipo, contenido in piezas:
        if tipo == "titulo1":
            bloque = "# " + contenido
        elif tipo == "titulo2":
            bloque = "## " + contenido
        elif tipo == "inciso":
            bloque = "### " + contenido
        elif tipo == "vineta":
            bloque = "- " + contenido
        elif tipo == "numero":
            bloque = contenido
        else:
            bloque = contenido

        if not salida:
            salida.append(bloque)
        elif tipo in ("vineta", "numero") and previo == tipo:
            salida.append("\n" + bloque)      # ítems de la misma lista, juntos
        else:
            salida.append("\n\n" + bloque)
        previo = tipo

    return "".join(salida).strip() + "\n"
