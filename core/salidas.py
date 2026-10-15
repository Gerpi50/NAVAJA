"""
core/salidas.py — Carpetas de salida unificadas para todos los módulos.

Regla única, igual en todo el programa:

  1. Si el usuario eligió una carpeta de destino, se usa esa.
  2. Si no eligió, se guarda en "PROCESADO CON NAVAJA" dentro de la
     carpeta donde están los originales.
  3. Si esa carpeta no se puede escribir (un CD, un pendrive protegido, una
     carpeta de red sin permiso), se cae al Escritorio para no perder el
     trabajo, y el módulo avisa a dónde fue.

Además concentra las dos formas de ordenar los resultados:

  * una carpeta por cada archivo original (para no mezclar las partes de
    cinco videos distintos), y
  * tandas de 5, que es lo que muchos portales permiten subir de una vez.
"""
import os
import shutil
import tempfile
from typing import Callable, List, Optional

# Nombre de la carpeta que se crea al lado de los originales.
from core.paths import APP_NAME

CARPETA_SALIDA = f"PROCESADO CON {APP_NAME.upper()}"

# Cuántos archivos entran en cada tanda: es el máximo que muchos portales aceptan
# cargar de una sola vez.
POR_TANDA = 5


# ── Dónde se puede escribir ──────────────────────────────────────────────

def es_escribible(directorio: str) -> bool:
    """True si se puede crear un archivo dentro de `directorio`."""
    if not directorio or not os.path.isdir(directorio):
        return False
    try:
        with tempfile.NamedTemporaryFile(dir=directorio, prefix=".gp_", suffix=".tmp"):
            pass
        return True
    except Exception:
        return False


def _escritorio() -> str:
    """Escritorio del usuario; si no existe, la carpeta personal."""
    home = os.path.expanduser("~")
    for nombre in ("Desktop", "Escritorio"):
        ruta = os.path.join(home, nombre)
        if os.path.isdir(ruta):
            return ruta
    return home


def carpeta_de(origen: str) -> str:
    """Carpeta que contiene `origen` (o el mismo `origen` si ya es carpeta)."""
    if not origen:
        return ""
    return origen if os.path.isdir(origen) else os.path.dirname(origen)


# ── Carpeta de destino ───────────────────────────────────────────────────

def carpeta_destino(origen, elegida: str = "",
                    nombre: str = CARPETA_SALIDA) -> str:
    """Devuelve la carpeta donde guardar (sin crearla).

    origen  — un archivo, una carpeta, o una lista de archivos (se usa el
              primero: si vinieran de carpetas distintas manda ese).
    elegida — carpeta que eligió el usuario; si viene, se respeta tal cual.
    """
    if elegida:
        return elegida

    if isinstance(origen, (list, tuple)):
        origen = origen[0] if origen else ""
    base = carpeta_de(origen)

    if base and es_escribible(base):
        return os.path.join(base, nombre)
    return os.path.join(_escritorio(), nombre)


def preparar_destino(origen, elegida: str = "",
                     nombre: str = CARPETA_SALIDA) -> str:
    """carpeta_destino() + la crea. Devuelve la ruta lista para escribir."""
    destino = carpeta_destino(origen, elegida, nombre)
    os.makedirs(destino, exist_ok=True)
    return destino


def etiqueta_destino(origen, elegida: str = "") -> str:
    """Texto corto para mostrar en la GUI antes de procesar."""
    if elegida:
        return elegida
    if not origen or (isinstance(origen, (list, tuple)) and not origen):
        return f"(carpeta de los originales)/{CARPETA_SALIDA}/"
    return carpeta_destino(origen, elegida)


# ── Ordenar los resultados ───────────────────────────────────────────────

def carpeta_de_archivo(destino: str, archivo: str, crear: bool = True) -> str:
    """Subcarpeta con el nombre del archivo original, sin la extensión.

    Con cinco videos procesados de una vez, cada uno deja sus partes en su
    propia carpeta en lugar de mezclarse todas.
    """
    stem = os.path.splitext(os.path.basename(archivo))[0]
    ruta = os.path.join(destino, stem)
    if crear:
        os.makedirs(ruta, exist_ok=True)
    return ruta


def repartir_en_tandas(archivos: List[str], destino: str,
                       por_tanda: int = POR_TANDA,
                       progreso: Optional[Callable[[str], None]] = None
                       ) -> List[str]:
    """Mueve `archivos` a Tanda_1, Tanda_2… dentro de `destino`.

    Si entran todos en una sola tanda no arma ninguna carpeta: sería un clic
    de más para nada. Devuelve las rutas finales, en orden.
    """
    archivos = [a for a in archivos if a and os.path.exists(a)]
    if not archivos:
        return []

    if len(archivos) <= por_tanda:
        finales = []
        for src in archivos:
            dst = os.path.join(destino, os.path.basename(src))
            if os.path.abspath(src) != os.path.abspath(dst):
                os.makedirs(destino, exist_ok=True)
                shutil.move(src, dst)
            finales.append(dst)
        return finales

    finales = []
    for i, src in enumerate(archivos):
        tanda = (i // por_tanda) + 1
        carpeta = os.path.join(destino, f"Tanda_{tanda}")
        os.makedirs(carpeta, exist_ok=True)
        dst = os.path.join(carpeta, os.path.basename(src))
        if os.path.abspath(src) != os.path.abspath(dst):
            shutil.move(src, dst)
        finales.append(dst)
        if progreso and (i + 1) % por_tanda == 0:
            progreso(f"📦  Tanda {tanda} completa ({por_tanda} archivos).")
    return finales


def cantidad_de_tandas(cantidad: int, por_tanda: int = POR_TANDA) -> int:
    """Cuántas tandas hacen falta para `cantidad` archivos."""
    if cantidad <= 0:
        return 0
    return -(-cantidad // por_tanda)   # ceil sin importar math
