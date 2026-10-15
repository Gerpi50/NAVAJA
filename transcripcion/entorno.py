# -*- coding: utf-8 -*-
"""
Preparacion del entorno de ejecucion.

En la version portable, ffmpeg viaja dentro de la propia carpeta del programa
en `recursos/ffmpeg`. Como Whisper invoca `ffmpeg` como si estuviera en el
PATH, hay que agregar esa carpeta al PATH del proceso antes de transcribir.
"""

from __future__ import annotations

import os
import shutil
import sys

SUBCARPETA_FFMPEG = os.path.join("recursos", "ffmpeg")


def empaquetado() -> bool:
    """True si el programa corre desde el ejecutable armado con PyInstaller."""
    return bool(getattr(sys, "frozen", False))


def app_dir() -> str:
    """Carpeta del programa: la del .exe, o la raiz del proyecto en codigo."""
    if empaquetado():
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def carpetas_ffmpeg() -> list[str]:
    """Carpetas propias donde puede estar el ffmpeg que acompana al programa."""
    candidatas = [
        os.path.join(app_dir(), SUBCARPETA_FFMPEG),
        os.path.join(app_dir(), "ffmpeg"),
    ]
    # Dentro de Navaja: el ffmpeg es el de su carpeta bin/.
    try:
        from core.paths import BIN_DIR

        candidatas.insert(0, str(BIN_DIR))
    except Exception:
        pass
    interno = getattr(sys, "_MEIPASS", "")
    if interno:
        candidatas.append(os.path.join(interno, SUBCARPETA_FFMPEG))
    return [c for c in candidatas if os.path.isdir(c)]


def preparar_entorno() -> None:
    """Agrega el ffmpeg propio al PATH, delante del que pueda haber instalado."""
    propias = carpetas_ffmpeg()
    if not propias:
        return
    actual = os.environ.get("PATH", "")
    partes = [p for p in propias if p not in actual.split(os.pathsep)]
    if partes:
        os.environ["PATH"] = os.pathsep.join(partes + [actual])


def ffmpeg_disponible() -> bool:
    """True si se puede ejecutar ffmpeg (propio o instalado en el sistema)."""
    preparar_entorno()
    return shutil.which("ffmpeg") is not None


def ruta_ffmpeg() -> str:
    """Ruta del ffmpeg que se va a usar, para mostrarla en diagnosticos."""
    preparar_entorno()
    return shutil.which("ffmpeg") or ""


# ------------------------------------------------------- recursos que viajan


def ruta_recurso(nombre: str) -> str:
    """Busca un archivo que acompana al programa (manual, SVG, etc.).

    Se mira primero al lado del ejecutable -que es donde queda en la version
    portable-, despues adentro del paquete de PyInstaller y por ultimo en la
    carpeta del proyecto, que es el caso de cuando se corre desde el codigo.
    """
    # Dentro de Navaja los recursos viajan en la carpeta del propio
    # paquete (transcripcion/), no al lado del ejecutable.
    candidatas = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), nombre),
        os.path.join(app_dir(), nombre),
    ]
    interno = getattr(sys, "_MEIPASS", "")
    if interno:
        candidatas.append(os.path.join(interno, nombre))
    candidatas.append(
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     nombre)
    )
    for ruta in candidatas:
        if os.path.isfile(ruta):
            return ruta
    return ""


# --------------------------------------------------------- consola de Windows


def ocultar_consola() -> bool:
    """Esconde la ventana negra de consola si es exclusivamente nuestra.

    Al abrir el programa con `python.exe` (o con un `pythonw` que en realidad
    es un .bat, como los de pyenv) Windows deja una terminal abierta delante
    de la ventana. Aca se la oculta.

    No se toca nada si la consola esta compartida con otros procesos: eso
    significa que alguien la abrio antes -una terminal del usuario- y
    esconderla seria esconderle su propia ventana.
    """
    if sys.platform != "win32":
        return False
    try:
        import ctypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        ventana = kernel32.GetConsoleWindow()
        if not ventana:
            return False            # ya se abrio sin consola (pythonw.exe)

        # Si el unico proceso enganchado a la consola somos nosotros, la
        # consola nacio con el programa y se puede ocultar sin molestar.
        lista = (ctypes.c_uint32 * 8)()
        cuantos = kernel32.GetConsoleProcessList(lista, 8)
        if cuantos != 1:
            return False

        ctypes.WinDLL("user32").ShowWindow(ventana, 0)   # SW_HIDE
        return True
    except Exception:
        return False
