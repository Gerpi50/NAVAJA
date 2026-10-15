"""
exportar_manual.py — Saca el manual del programa a un .html para compartir.

    python exportar_manual.py [destino.html]

El texto es el mismo que muestra el programa en «Ayuda» (ui/manual.py), sin
tocar una palabra. Sólo se le suma lo que hace falta para leerlo cómodo en un
navegador o imprimirlo: título, índice con enlaces y un ancho de lectura.
El archivo no depende de nada más: se manda solo.
"""
import os
import re
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

DESTINO = os.path.join(AQUI, "Manual de Navaja.html")

ESTILO = """
  /* Para leerlo en el navegador y para imprimirlo */
  html { background: #f1f5f9; }
  body { font-size: 15px; max-width: 900px; margin: 24px auto; padding: 32px 44px;
         box-shadow: 0 1px 6px rgba(15, 23, 42, .12); border-radius: 8px; }
  h1 { font-size: 26px; }
  h2 { font-size: 19px; margin-top: 30px; }
  h3 { font-size: 15.5px; }
  h4 { font-size: 15px; }
  code { font-size: 13.5px; }
  .version { color: #64748b; margin-top: -4px; }
  .indice { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px;
            padding: 12px 20px; margin: 16px 0 8px; }
  .indice strong { display: block; margin-bottom: 4px; }
  .indice ul { list-style: none; padding-left: 0; columns: 2; column-gap: 32px; }
  .indice li { margin: 3px 0; break-inside: avoid; }
  .indice a { color: #1d4ed8; text-decoration: none; }
  .indice a:hover { text-decoration: underline; }
  @media (max-width: 700px) {
    body { margin: 0; padding: 16px; border-radius: 0; }
    .indice ul { columns: 1; }
    table { display: block; overflow-x: auto; }
  }
  @media print {
    html { background: #fff; }
    body { box-shadow: none; max-width: none; margin: 0; padding: 0; font-size: 11.5pt; }
    h2 { break-after: avoid; }
    .tip, .warn, tr { break-inside: avoid; }
    .indice a { color: #000; }
  }
"""


def exportar(destino: str = DESTINO) -> str:
    from core.paths import APP_VERSION
    from ui.manual import MANUAL_HTML

    indice = []

    def con_ancla(m):
        ancla = f"s{len(indice) + 1}"
        indice.append((ancla, re.sub(r"<[^>]+>", "", m.group(1)).strip()))
        return f'<h2 id="{ancla}">{m.group(1)}</h2>'

    html = re.sub(r"<h2>(.*?)</h2>", con_ancla, MANUAL_HTML, flags=re.S)
    lista = "\n".join(f'    <li><a href="#{a}">{t}</a></li>' for a, t in indice)
    cabecera = (
        f'<p class="version">Navaja · versión {APP_VERSION}</p>\n'
        '<div class="indice">\n  <strong>Índice</strong>\n  <ul>\n'
        f"{lista}\n  </ul>\n</div>\n")

    html = html.replace(
        '<meta charset="UTF-8">',
        '<meta charset="UTF-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>Manual de Navaja</title>", 1)
    html = html.replace("</style>", ESTILO + "</style>", 1)
    html = re.sub(r"(<h1>.*?</h1>)", lambda m: m.group(1) + "\n" + cabecera,
                  html, count=1, flags=re.S)

    with open(destino, "w", encoding="utf-8") as f:
        f.write(html)
    return destino


if __name__ == "__main__":
    ruta = exportar(sys.argv[1] if len(sys.argv) > 1 else DESTINO)
    print(f"Manual guardado en:\n{ruta}\n({os.path.getsize(ruta) / 1024:.0f} KB)")
