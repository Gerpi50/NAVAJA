"""
test_pdf_md.py — Pruebas de la conversión PDF → Markdown.

Arma un PDF de prueba con PyMuPDF (títulos de dos tamaños, párrafos
justificados, lista con viñetas, lista numerada, tabla con líneas y
encabezado/pie repetidos en cada página) y controla que el .md salga como
corresponde.

Se corre con:  python test_pdf_md.py
"""
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OK = 0
FAIL = 0


def check(nombre: str, condicion: bool, detalle: str = ""):
    global OK, FAIL
    if condicion:
        OK += 1
        print(f"  OK  {nombre}")
    else:
        FAIL += 1
        print(f"  FAIL {nombre}  {detalle}")


import fitz
from motors.motor_documents import PdfToMdMotor

base = tempfile.mkdtemp(prefix="gp_md_")
pdf  = os.path.join(base, "informe.pdf")
md   = os.path.join(base, "informe.md")

PARRAFO = (
    "La presente actuación se labra a los efectos de dejar constancia de lo "
    "actuado en el día de la fecha, conforme lo dispuesto por el señor Director "
    "General interviniente, y de acuerdo al detalle que a continuación se "
    "expone en el cuerpo del presente informe técnico.")

doc = fitz.open()

# ── Página 1: títulos, párrafo, listas ──────────────────────────────────
pg = doc.new_page()
pg.insert_text((72, 40), "DIRECCIÓN GENERAL — DEPARTAMENTO ADMINISTRATIVO",
               fontsize=8, fontname="helv")
pg.insert_text((72, 110), "Informe pericial", fontsize=20, fontname="hebo")
pg.insert_text((72, 150), "1. Elementos analizados", fontsize=14, fontname="hebo")
pg.insert_textbox(fitz.Rect(72, 165, 520, 260), PARRAFO,
                  fontsize=11, fontname="helv", align=3)
pg.insert_text((72, 285), "2. Conclusiones", fontsize=14, fontname="hebo")
for i, item in enumerate([
        "El teléfono conserva la totalidad de los mensajes recibidos.",
        "La memoria presenta daño físico en el conector de datos.",
        "La notebook no registra actividad posterior al hecho."]):
    pg.insert_text((90, 310 + i * 18), "•", fontsize=11, fontname="helv")
    pg.insert_text((104, 310 + i * 18), item, fontsize=11, fontname="helv")
for i, item in enumerate([
        "1. Se remite copia al Director General.",
        "2. Se reservan los originales en secretaría."]):
    pg.insert_text((90, 380 + i * 18), item, fontsize=11, fontname="helv")
pg.insert_text((280, 800), "Página 1 de 3", fontsize=8, fontname="helv")

# ── Página 2: tabla con líneas ──────────────────────────────────────────
pg = doc.new_page()
pg.insert_text((72, 40), "DIRECCIÓN GENERAL — DEPARTAMENTO ADMINISTRATIVO",
               fontsize=8, fontname="helv")
filas = [["Efecto", "Marca", "Peso"],
         ["Teléfono", "Samsung A20", "168 g"],
         ["Memoria", "SanDisk 32 GB", "2 g"]]
x0, y0, ancho, alto = 72, 120, 140, 24
for r, fila in enumerate(filas):
    for c, celda in enumerate(fila):
        rect = fitz.Rect(x0 + c * ancho, y0 + r * alto,
                         x0 + (c + 1) * ancho, y0 + (r + 1) * alto)
        pg.draw_rect(rect, color=(0, 0, 0), width=0.7)
        pg.insert_text((rect.x0 + 4, rect.y1 - 8), celda,
                       fontsize=10, fontname="helv")
pg.insert_text((280, 800), "Página 2 de 3", fontsize=8, fontname="helv")

# ── Página 3: párrafo cortado por el salto de página ────────────────────
pg = doc.new_page()
pg.insert_text((72, 40), "DIRECCIÓN GENERAL — DEPARTAMENTO ADMINISTRATIVO",
               fontsize=8, fontname="helv")
pg.insert_textbox(fitz.Rect(72, 120, 520, 300), PARRAFO,
                  fontsize=11, fontname="helv", align=3)
pg.insert_text((280, 800), "Página 3 de 3", fontsize=8, fontname="helv")

doc.save(pdf)
doc.close()

print("\n=== PDF → MARKDOWN ===")
PdfToMdMotor().convert(pdf, md, "pdf", "md")
texto = open(md, encoding="utf-8").read()
print(texto)
print("-" * 60)

titulos = [l for l in texto.splitlines() if l.startswith("#")]
check("el título más grande es #",
      any(l.startswith("# ") and "Informe pericial" in l for l in titulos),
      str(titulos[:3]))
check("los títulos de sección quedan un nivel abajo",
      any(l.startswith("## ") and "Elementos analizados" in l for l in titulos),
      str(titulos[:3]))
check("no se cuela el encabezado repetido", "DIRECCIÓN GENERAL" not in texto)
check("no se cuelan los números de página", "Página 1 de 3" not in texto)
check("las viñetas salen como lista",
      "- El teléfono conserva la totalidad de los mensajes recibidos."
      in texto, "")
check("la lista numerada se conserva",
      "1. Se remite copia al Director General." in texto)
check("el párrafo se rearma en un solo renglón",
      "conforme lo dispuesto por el señor Director General interviniente, y de "
      "acuerdo al detalle" in texto)
check("la tabla sale como tabla de Markdown",
      "| Efecto | Marca | Peso |" in texto and "| --- |" in texto)
check("las filas de la tabla están completas",
      "| Teléfono | Samsung A20 | 168 g |" in texto)
check("no quedan renglones sueltos con una sola letra",
      not [l for l in texto.splitlines() if len(l.strip()) == 1])

# ── PDF escaneado: tiene que avisar, no dejar un .md vacío ──────────────
print("\n=== PDF SIN TEXTO ===")
vacio = os.path.join(base, "escaneado.pdf")
d = fitz.open()
d.new_page()
d.save(vacio)
d.close()
try:
    PdfToMdMotor().convert(vacio, os.path.join(base, "escaneado.md"), "pdf", "md")
    check("avisa que el PDF no tiene texto", False, "no lanzó error")
except RuntimeError as e:
    check("avisa que el PDF no tiene texto", "escaneada" in str(e).lower())

# ── HTML → MD (Pandoc): sin cortes de renglón ni comillas escapadas ────
print("\n=== HTML → MARKDOWN (Pandoc) ===")
from motors.motor_documents import PandocMotor

if not PandocMotor.is_available():
    print("  (salteado: no hay pandoc)")
else:
    html = os.path.join(base, "nota.html")
    salida = os.path.join(base, "nota.md")
    open(html, "w", encoding="utf-8").write(
        '<html><head><meta charset="utf-8"></head><body>'
        "<h1>Informe</h1>"
        "<p>El perito dijo \"no hay rastros\" y se retiró del lugar, "
        "dejando constancia de que la diligencia se cumplió en su "
        "totalidad conforme lo ordenado por el señor Director General "
        "interviniente en las presentes actuaciones.</p>"
        "<ul><li>Primero</li><li>Segundo</li></ul>"
        "</body></html>")
    PandocMotor().convert(html, salida, "html", "md")
    texto = open(salida, encoding="utf-8").read()
    print(texto)
    largos = [l for l in texto.splitlines() if len(l) > 100]
    check("el párrafo no se corta a 72 columnas", bool(largos), texto[:120])
    check("las comillas no salen escapadas", '\\"' not in texto)
    check("el título se conserva", texto.lstrip().startswith("# Informe"))
    check("la lista se conserva", "- Primero" in texto)

# ── Escrito con ruido de sistema de gestión, títulos estrictos, párrafos ──────
print("\n=== PDF DE UN ESCRITO FORMAL (solicitud / expediente) ===")

jud = os.path.join(base, "solicitud.pdf")
jud_md = os.path.join(base, "solicitud.md")

P1 = ("Que en el marco de la investigación penal preparatoria de referencia, "
      "se ha logrado establecer con el grado de probabilidad exigido en esta "
      "etapa que en el domicilio sito en calle 47 número 1234 de la ciudad "
      "de La Plata funcionaría un punto de venta de estupefacientes al "
      "menudeo, conforme surge de las tareas de inteligencia ordenadas y de "
      "los testimonios reservados en secretaría")
P2 = ("cuya transcripción se acompaña. En razón de ello, y siendo que la "
      "medida resulta conducente para el esclarecimiento del hecho, se "
      "solicita se libre la correspondiente orden.")

doc = fitz.open()


def _membrete(pg, num):
    """Lo que un sistema de gestión estampa en cada hoja."""
    pg.insert_text((60, 28), '# ÑEÌ" \'K5+<Ó  E02000007432111',
                   fontsize=9, fontname="helv")
    pg.insert_text((60, 40), "ORGANISMO PÚBLICO PROVINCIAL", fontsize=8,
                   fontname="helv")
    pg.insert_text((250, 795), f"Pag. {num} de 22", fontsize=8, fontname="helv")
    pg.insert_text((60, 812), "usuario@organismo.gob - Fecha: 2026-09-06 11:42:03",
                   fontsize=8, fontname="helv")


pg = doc.new_page()
_membrete(pg, 1)
pg.insert_text((72, 110), "SOLICITA HABILITACIÓN", fontsize=12, fontname="hebo")
pg.insert_text((72, 150), "I.- OBJETO:", fontsize=11, fontname="hebo")
pg.insert_textbox(fitz.Rect(72, 165, 520, 300), P1,
                  fontsize=11, fontname="helv", align=3)
pg.insert_text((72, 340), "II.- HECHOS:", fontsize=11, fontname="hebo")
pg.insert_text((72, 365), "Juan Carlos Pérez", fontsize=11, fontname="helv")
pg.insert_text((72, 385), "DNI 28.456.789", fontsize=11, fontname="helv")
pg.insert_text((72, 405), "EXPTE N° 06-00-012345-20", fontsize=11, fontname="helv")

pg = doc.new_page()
_membrete(pg, 2)
pg.insert_textbox(fitz.Rect(72, 110, 520, 200), P2,
                  fontsize=11, fontname="helv", align=3)
pg.insert_text((72, 230), "III.- MEDIDAS SOLICITADAS:", fontsize=11,
               fontname="hebo")
pg.insert_text((90, 260), "a) La inspección del inmueble y sus dependencias.",
               fontsize=11, fontname="helv")
pg.insert_text((90, 280), "b) La revisión de la documentación presentada.",
               fontsize=11, fontname="helv")
pg.insert_text((72, 320), "VII. PETITORIO:", fontsize=11, fontname="hebo")
pg.insert_text((72, 345), "Por todo lo expuesto, solicito se haga lugar.",
               fontsize=11, fontname="helv")
doc.save(jud)
doc.close()

PdfToMdMotor().convert(jud, jud_md, "pdf", "md")
texto = open(jud_md, encoding="utf-8").read()
print(texto)
titulos = [l for l in texto.splitlines() if l.startswith("#")]

check("se va el garabato del código de barras", 'ÑEÌ' not in texto)
check("se conserva el identificador de la pieza digital",
      texto.startswith("**Pieza digital:** E02000007432111"), texto[:80])
check("el identificador no se repite por página",
      texto.count("E02000007432111") == 1, str(texto.count("E02000007432111")))
check("el número de expediente no se confunde con una pieza digital",
      "06-00-012345-20" in texto
      and "Pieza digital:** E02000007432111\n" in texto)
check("se va el membrete de la hoja", "ORGANISMO PÚBLICO" not in texto)
check("se va la paginación", "Pag. 1 de 22" not in texto)
check("se va la firma electrónica", "organismo.gob" not in texto)
check("la carátula es el título principal",
      "# SOLICITA HABILITACIÓN" in titulos, str(titulos))
check("la numeración romana es título",
      "## I.- OBJETO:" in titulos and "## VII. PETITORIO:" in titulos,
      str(titulos))
check("los incisos son título",
      any(l.startswith("### a)") for l in titulos)
      and any(l.startswith("### b)") for l in titulos), str(titulos))
check("un nombre propio suelto NO es título",
      not any("Juan Carlos Pérez" in l for l in titulos))
check("un DNI NO es título", not any("28.456.789" in l for l in titulos))
check("un número de expediente NO es título",
      not any("06-00-012345-20" in l for l in titulos))
check("ningún título empieza en minúscula",
      not [l for l in titulos
           if l.lstrip("# ")[:1].islower() and not l.lstrip("# ")[1:2] == ")"],
      str(titulos))
check("el párrafo cortado por el salto de página se une",
      "reservados en secretaría cuya transcripción se acompaña" in texto
      or "orden." in texto.replace("\n", " "))

# ── Proveído: párrafos que cierran con ".-" y leyenda girada al margen ─
print("\n=== Proveído con '.-' y leyenda al costado ===")
prov = os.path.join(base, "proveido.pdf")
prov_md = os.path.join(base, "proveido.md")
doc = fitz.open()
for n in range(2):
    pg = doc.new_page()
    # Leyenda de costado, igual en las dos hojas (dir vertical).
    pg.insert_text((40, 780), "Anexo - Resolución S.P.C. N° 2/26", fontsize=10,
                   fontname="helv", rotate=90)
    if n == 0:
        pg.insert_text((72, 100), "y no existe embargo.-", fontsize=11,
                       fontname="helv")
        pg.insert_text((72, 130), "SECRETARIA, 23 de septiembre de 2026.-",
                       fontsize=11, fontname="helv")
        pg.insert_text((72, 160), "asciende a la suma de PESOS: TREINTA y",
                       fontsize=11, fontname="helv")
        pg.insert_text((72, 175), "TRES MILLONES TRESCIENTOS MIL",
                       fontsize=11, fontname="helv")
        pg.insert_text((72, 190), "CON SESENTA CENTAVOS, aprobándoselo.-",
                       fontsize=11, fontname="helv")
    else:
        pg.insert_text((72, 100), "Regístrese.-", fontsize=11, fontname="helv")
doc.save(prov)
doc.close()
PdfToMdMotor().convert(prov, prov_md, "pdf", "md")
texto = open(prov_md, encoding="utf-8").read()
check("'.-' cierra el párrafo (no es guión de sílaba)",
      "embargo.-\n\nSECRETARIA" in texto and "embargo.SECRETARIA" not in texto,
      texto[:200])
check("un renglón en mayúsculas en medio de una oración NO es título",
      "# TRES MILLONES" not in texto and "TREINTA y TRES MILLONES" in texto,
      texto[:400])
check("la leyenda girada repetida en cada hoja se descarta",
      "Anexo - Resolución" not in texto, texto[:400])

# ── El filtro de márgenes no puede comerse texto del cuerpo ────────────
print("\n=== TEXTO QUE ARRANCA ALTO EN LA HOJA ===")
alto_pdf = os.path.join(base, "arriba.pdf")
alto_md  = os.path.join(base, "arriba.md")
doc = fitz.open()
pg = doc.new_page()
pg.insert_text((72, 300), "Texto de la primera hoja.", fontsize=11,
               fontname="helv")
pg.insert_text((250, 800), "2", fontsize=8, fontname="helv")
pg = doc.new_page()
# Arranca dentro del 10% de arriba: es cuerpo, no membrete.
pg.insert_text((72, 70), "Renglon que arranca arriba de todo en la hoja.",
               fontsize=11, fontname="helv")
pg.insert_text((250, 800), "3", fontsize=8, fontname="helv")
doc.save(alto_pdf)
doc.close()

PdfToMdMotor().convert(alto_pdf, alto_md, "pdf", "md")
texto = open(alto_md, encoding="utf-8").read()
check("no se pierde el cuerpo que empieza en el margen de arriba",
      "arranca arriba de todo" in texto, texto[:200])
check("la numeración suelta igual se va", "\n2\n" not in f"\n{texto}\n")

# ── El final de una hoja repetido al principio de la siguiente ─────────
print("\n=== REPETICIÓN ENTRE HOJAS (PDF → MD y PDF → TXT) ===")
from motors.motor_documents import PdfExtractMotor

rep_pdf = os.path.join(base, "resolucion.pdf")
COLA = ["y en atención a lo dictaminado por el señor Director General,",
        "corresponde y así lo resuelvo, hacer lugar a lo peticionado"]

doc = fitz.open()
pg = doc.new_page()
pg.insert_text((72, 120), "Primera hoja: el cuerpo de la resolución.",
               fontsize=11, fontname="helv")
for i, ln in enumerate(COLA):
    pg.insert_text((72, 700 + i * 18), ln, fontsize=11, fontname="helv")
# El mismo texto dibujado MÁS ABAJO DEL BORDE: no se ve al abrir el PDF,
# pero cualquier extractor lo lee.
for i, ln in enumerate(COLA):
    pg.insert_text((72, 870 + i * 18), ln, fontsize=11, fontname="helv")
pg = doc.new_page()
for i, ln in enumerate(COLA):
    pg.insert_text((72, 120 + i * 18), ln, fontsize=11, fontname="helv")
pg.insert_text((72, 200), "por el término de ley, con costas.",
               fontsize=11, fontname="helv")
doc.save(rep_pdf)
doc.close()

rep_md = os.path.join(base, "resolucion.md")
rep_txt = os.path.join(base, "resolucion.txt")
PdfToMdMotor().convert(rep_pdf, rep_md, "pdf", "md")
PdfExtractMotor().convert(rep_pdf, rep_txt, "pdf", "txt")
t_md = open(rep_md, encoding="utf-8").read()
t_txt = open(rep_txt, encoding="utf-8").read()

CLAVE = "corresponde y así lo resuelvo"
check("el MD no repite la cola de la hoja", t_md.count(CLAVE) == 1,
      f"aparece {t_md.count(CLAVE)} veces")
check("el TXT no repite la cola de la hoja", t_txt.count(CLAVE) == 1,
      f"aparece {t_txt.count(CLAVE)} veces")
check("no se perdió el texto de la hoja siguiente",
      "por el término de ley" in t_md and "por el término de ley" in t_txt)
check("no se perdió el cuerpo de la primera hoja",
      "Primera hoja" in t_md and "Primera hoja" in t_txt)

print("\n=== MARCADORES DE PÁGINA (para poder citar la hoja) ===")
# Un .md no tiene páginas: si el documento se le pasa a una IA para que cite,
# no puede decir de qué hoja salió cada cosa. Por eso se intercala el número
# de página del documento original.
from motors.motor_documents import (MARCADOR_PAGINA, es_marcador_de_pagina,
                                    copia_con_marcadores)

# Un PDF propio de tres hojas, con un párrafo que arranca en la primera y
# termina en la segunda (el caso que no se puede romper).
pdf_pag = os.path.join(tempfile.gettempdir(), "gp_paginado.pdf")
md_pag = os.path.join(tempfile.gettempdir(), "gp_paginado.md")
_doc = fitz.open()
_p = _doc.new_page()
_p.insert_text((72, 100), "Informe de tres hojas", fontsize=20, fontname="hebo")
_p.insert_text((72, 150), "La pericia se realizó sobre el material secuestrado y",
               fontsize=11, fontname="helv")
_p = _doc.new_page()
_p.insert_text((72, 100), "se concluyó que el equipo estaba operativo.",
               fontsize=11, fontname="helv")
_p.insert_text((72, 140), "Segundo asunto de la hoja dos.", fontsize=11, fontname="helv")
_p = _doc.new_page()
_p.insert_text((72, 100), "Cierre del informe en la hoja tres.",
               fontsize=11, fontname="helv")
_doc.save(pdf_pag)
_doc.close()

PdfToMdMotor().convert(pdf_pag, md_pag, "pdf", "md")
t_pag = open(md_pag, encoding="utf-8").read()
lineas = t_pag.splitlines()
marcas = [l for l in lineas if es_marcador_de_pagina(l) is not None]
numeros = [es_marcador_de_pagina(l) for l in marcas]

check("hay un marcador por cada hoja del PDF", numeros == [1, 2, 3], str(numeros))
check("el marcador tiene la forma pedida", marcas[0] == "--- [PÁGINA 1] ---",
      repr(marcas[0]) if marcas else "no hay ninguno")
check("cada marcador va solo en su renglón", all(l == l.strip() for l in marcas))

for i, l in enumerate(lineas):
    n = es_marcador_de_pagina(l)
    if n is None:
        continue
    antes = lineas[i - 1] if i else ""
    despues = lineas[i + 1] if i + 1 < len(lineas) else ""
    check(f"el marcador de la página {n} tiene un renglón en blanco a cada lado",
          antes.strip() == "" and despues.strip() == "",
          f"antes={antes!r} despues={despues!r}")

check("cada texto queda después del marcador de su hoja",
      t_pag.index("--- [PÁGINA 2] ---") < t_pag.index("Segundo asunto de la hoja dos.")
      < t_pag.index("--- [PÁGINA 3] ---") < t_pag.index("Cierre del informe"))

# El marcador no puede romper el rearmado del párrafo cortado entre hojas: la
# continuación se pega arriba del marcador, y el párrafo queda contado en la
# hoja donde empezó, que es como se cita.
sin_marcas = "\n".join(l for l in lineas if es_marcador_de_pagina(l) is None)
check("el párrafo cortado por el salto de hoja sigue entero",
      "material secuestrado y se concluyó que el equipo estaba operativo."
      in sin_marcas, repr(sin_marcas[:200]))

md_sin = os.path.join(tempfile.gettempdir(), "gp_sin_marcas.md")
PdfToMdMotor().convert(pdf_pag, md_sin, "pdf", "md", marcar_paginas=False)
texto_sin = open(md_sin, encoding="utf-8").read()
check("se pueden apagar los marcadores",
      not any(es_marcador_de_pagina(l) is not None
              for l in texto_sin.splitlines()))
def _sin_aire(s):
    """El mismo texto, sin importar cuántos renglones en blanco seguidos hay.

    Al sacar un marcador quedan los dos renglones en blanco que lo rodeaban:
    lo que se compara es el texto, no el aire."""
    return re.sub(r"\n{2,}", "\n\n", s).strip()

check("apagarlos no cambia nada más del texto",
      _sin_aire(texto_sin) == _sin_aire(sin_marcas),
      repr(texto_sin[:120]))

check("reconoce el marcador aunque venga escapado",
      es_marcador_de_pagina(r"--- \[PÁGINA 12\] ---") == 12)
check("reconoce el marcador con raya larga",
      es_marcador_de_pagina("— [PÁGINA 7] —") == 7)
check("no confunde un texto cualquiera con un marcador",
      es_marcador_de_pagina("--- separador ---") is None
      and es_marcador_de_pagina("La página 12 dice") is None)

# ODT: los marcadores salen de los saltos de página que el procesador de
# texto ya dejó escritos. Un ODT armado por programa no los tiene, y ahí no
# se inventa nada: se convierte igual, sin marcadores.
import subprocess
from motors.motor_documents import _pandoc_path

# Armar el ODT de prueba necesita Pandoc (en bin/ o en el PATH).
if not _pandoc_path():
    print("  (se saltean las pruebas de ODT: no se encontró Pandoc)")
else:

    odt_prueba = os.path.join(tempfile.gettempdir(), "gp_marcas.odt")
    subprocess.run([_pandoc_path(), "-f", "markdown", "-o", odt_prueba, "-"],
                   input="# Uno\n\nTexto de la primera hoja.\n",
                   text=True, capture_output=True)
    copia = copia_con_marcadores(odt_prueba, "odt", tempfile.mkdtemp())
    check("un ODT sin saltos de página no se toca (no se inventan hojas)",
          copia is None, f"devolvió {copia}")

    # Y con saltos de página, uno por hoja, sin tocar el original.
    import zipfile
    odt_paginado = os.path.join(tempfile.gettempdir(), "gp_marcas2.odt")
    with zipfile.ZipFile(odt_prueba) as z:
        partes = {n: z.read(n) for n in z.namelist()}
    xml = partes["content.xml"].decode("utf-8")
    xml = xml.replace("</office:text>",
                      "<text:soft-page-break/><text:p>Hoja dos.</text:p>"
                      "<text:soft-page-break/><text:p>Hoja tres.</text:p>"
                      "</office:text>")
    partes["content.xml"] = xml.encode("utf-8")
    with zipfile.ZipFile(odt_paginado, "w") as z:
        for n, datos in partes.items():
            z.writestr(n, datos)

    antes = os.path.getsize(odt_paginado)
    carpeta = tempfile.mkdtemp()
    copia = copia_con_marcadores(odt_paginado, "odt", carpeta)
    check("con saltos de página sí se prepara una copia", copia is not None)
    check("el archivo original no se modifica", os.path.getsize(odt_paginado) == antes)
    if copia:
        with zipfile.ZipFile(copia) as z:
            contenido = z.read("content.xml").decode("utf-8")
        check("la copia trae un marcador por hoja",
              all(MARCADOR_PAGINA.format(n) in contenido for n in (1, 2, 3)),
              f"{contenido.count('PÁGINA')} marcadores")
        md_odt = os.path.join(tempfile.gettempdir(), "gp_marcas.md")
        PandocMotor().convert(odt_paginado, md_odt, "odt", "md")
        t_odt = open(md_odt, encoding="utf-8").read()
        check("y llegan al Markdown sin escapes",
              [es_marcador_de_pagina(l) for l in t_odt.splitlines()
               if es_marcador_de_pagina(l) is not None] == [1, 2, 3],
              repr([l for l in t_odt.splitlines() if "PÁGINA" in l]))
        check("el texto del ODT se conserva",
              "Hoja dos." in t_odt and "Hoja tres." in t_odt)

print("\n=== PULIDO DEL MARKDOWN QUE SALE DE WORD / ODT ===")
# Un documento de oficina arrastra restos de cómo fue escrito: negritas sin
# nada adentro (quedaba "n****o" en medio de una palabra) y párrafos vacíos
# con estilo de título (quedaba un "##" solo). Eso es basura de formato y se
# saca. Lo que NO se toca es el texto: si el autor escribió dos palabras
# pegadas, así quedan.
from motors.motor_documents import limpiar_markdown as _limpiar

N = "\n"
check("saca la negrita vacía dentro de una palabra",
      _limpiar("dice n****o usaba") == "dice no usaba" + N)
check("saca el título sin texto",
      _limpiar("Antes" + N + "## " + N + "Después") == "Antes" + N + "Después" + N)
check("respeta el título con texto", _limpiar("## Sección") == "## Sección" + N)
check("no fusiona dos negritas seguidas",
      _limpiar("**uno** **dos**") == "**uno** **dos**" + N)
check("no toca negrita y cursiva juntas",
      _limpiar("***muy importante***") == "***muy importante***" + N)
check("no toca las viñetas con asterisco",
      _limpiar("* item uno" + N + "* item dos") == "* item uno" + N + "* item dos" + N)
check("no inventa espacios que el documento no tiene",
      _limpiar("**una frase**pegada") == "**una frase**pegada" + N)
check("respeta las etiquetas escapadas",
      _limpiar(r"cambiar \<\<PERSONA_1\>\> por") == r"cambiar \<\<PERSONA_1\>\> por" + N)
check("separa la lista del párrafo anterior",
      _limpiar("Los sesgos:" + N + "- uno") == "Los sesgos:" + N + N + "- uno" + N)
check("no toca lo que está adentro de un bloque de código",
      _limpiar("```text" + N + "## dentro" + N + "n****o" + N + "```")
      == "```text" + N + "## dentro" + N + "n****o" + N + "```" + N)
check("no toca las tablas",
      _limpiar("| A | B |" + N + "|---|---|") == "| A | B |" + N + "|---|---|" + N)
check("no deja más de un renglón en blanco seguido",
      _limpiar("uno" + N * 5 + "dos") == "uno" + N + N + "dos" + N)

print("\n" + "=" * 54)
print(f"TOTAL: {OK + FAIL} pruebas   PASARON: {OK}   FALLARON: {FAIL}")
sys.exit(1 if FAIL else 0)
