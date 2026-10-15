"""
core/paths.py — Gestión centralizada de rutas del sistema.
"""
import os
import sys

# Versión del programa. Se identifica por la fecha de la compilación y no por
# un número: no hay entregas anteriores en uso contra las cuales numerar.
APP_VERSION = "15/10/2026"

# Nombre del programa: es lo único que hay que tocar para renombrarlo.
APP_NAME     = "Navaja"
APP_TAGLINE  = "Editor universal de archivos"
APP_TITLE    = f"{APP_NAME} · {APP_TAGLINE}"
APP_ID       = "Navaja.EditorUniversal"      # AppUserModelID de Windows


def get_base_dir() -> str:
    """
    Determina la carpeta base donde el programa puede escribir.
    Primero intenta la carpeta del ejecutable; si no hay permisos,
    usa %APPDATA%\<APP_NAME>\
    """
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
    else:
        exe_dir = os.path.dirname(os.path.abspath(__file__))
        exe_dir = os.path.dirname(exe_dir)  # subir un nivel desde core/

    test_file = os.path.join(exe_dir, ".write_test")
    try:
        with open(test_file, "w") as f:
            f.write("test")
        os.unlink(test_file)
        return exe_dir
    except (PermissionError, OSError):
        appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
        base = os.path.join(appdata, APP_NAME)
        os.makedirs(base, exist_ok=True)
        return base


def _resource_path(relative: str) -> str:
    """Resuelve rutas de recursos tanto en desarrollo como en el exe compilado."""
    if getattr(sys, '_MEIPASS', None):
        return os.path.join(sys._MEIPASS, relative)
    base = os.path.dirname(os.path.abspath(__file__))
    base = os.path.dirname(base)  # subir desde core/
    return os.path.join(base, relative)


BASE_DIR    = get_base_dir()
LOGS_DIR    = os.path.join(BASE_DIR, "logs")
TEMP_DIR    = os.path.join(BASE_DIR, "temp")
MODELS_DIR  = os.path.join(BASE_DIR, "models")
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

# BIN_DIR: junto al ejecutable (permite reemplazar ffmpeg sin recompilar).
# Si ahí no existe, se usa la copia empaquetada dentro de _internal (_MEIPASS).
if getattr(sys, 'frozen', False):
    _exe_dir = os.path.dirname(sys.executable)
else:
    _exe_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_bin_candidates = [os.path.join(_exe_dir, "bin")]
_meipass = getattr(sys, "_MEIPASS", None)
if _meipass:
    _bin_candidates.append(os.path.join(_meipass, "bin"))
BIN_DIR = next((c for c in _bin_candidates if os.path.isdir(c)), _bin_candidates[0])

# Crear carpetas escribibles necesarias al importar este módulo
for _d in [LOGS_DIR, TEMP_DIR, MODELS_DIR]:
    os.makedirs(_d, exist_ok=True)
os.makedirs(BIN_DIR, exist_ok=True)


def resource(relative: str) -> str:
    """Acceso a recursos del programa (assets, splash, icon, etc.)."""
    return _resource_path(relative)
