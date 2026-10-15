"""
generar_icono.py — Convierte assets/navaja.png en assets/icono.ico (y icono.png).

Es el ícono del exe, de la ventana y de la barra de tareas. La imagen es
apaisada y un ícono es cuadrado: se recorta un cuadrado centrado en el mango
de la navaja y se le redondean las esquinas.

Uso:  python assets/generar_icono.py
"""

import os

from PIL import Image, ImageDraw

RAIZ = os.path.dirname(os.path.abspath(__file__))
ORIGEN = os.path.join(RAIZ, "navaja.png")
DESTINO_ICO = os.path.join(RAIZ, "icono.ico")
DESTINO_PNG = os.path.join(RAIZ, "icono.png")

# Centro del mango (el botón rojo), como fracción del ancho y del alto.
_CENTRO = (0.477, 0.537)
_LADO = 1024
_RADIO = 0.18            # redondeo de las esquinas, fracción del lado
_TAMANOS = [16, 20, 24, 32, 40, 48, 64, 128, 256]


def generar():
    img = Image.open(ORIGEN).convert("RGBA")
    ancho, alto = img.size
    lado = min(ancho, alto)
    x0 = min(max(0, round(ancho * _CENTRO[0] - lado / 2)), ancho - lado)
    y0 = min(max(0, round(alto * _CENTRO[1] - lado / 2)), alto - lado)
    cuadrado = img.crop((x0, y0, x0 + lado, y0 + lado)).resize(
        (_LADO, _LADO), Image.LANCZOS)

    mascara = Image.new("L", (_LADO, _LADO), 0)
    ImageDraw.Draw(mascara).rounded_rectangle(
        (0, 0, _LADO - 1, _LADO - 1), radius=round(_LADO * _RADIO), fill=255)
    cuadrado.putalpha(mascara)

    cuadrado.resize((512, 512), Image.LANCZOS).save(DESTINO_PNG)
    cuadrado.save(DESTINO_ICO, sizes=[(t, t) for t in _TAMANOS])
    print(f"{DESTINO_ICO}  ({os.path.getsize(DESTINO_ICO):,} bytes)")


if __name__ == "__main__":
    generar()
