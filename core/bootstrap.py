"""
bootstrap.py — Auto-instala dependencias Python necesarias antes de importar nada.
"""
import sys
import subprocess


# Dependencias obligatorias: se instalan si no están presentes
REQUIRED = {
    "PyQt6":       "PyQt6.QtWidgets",
    "Pillow":      "PIL",
    "reportlab":   "reportlab.pdfgen",
    "pypdf":       "pypdf",
    "python-docx": "docx",
    "openpyxl":    "openpyxl",
    "python-pptx": "pptx",
    "extract-msg": "extract_msg",
    "markdown":    "markdown",
    "chardet":     "chardet",
    "pandas":      "pandas",
    "PyYAML":      "yaml",
}

# Dependencias opcionales: se verifican pero NO se instalan si el import falla
# por razones nativas (cairosvg necesita libcairo-2.dll que no siempre está en Windows)
OPTIONAL = {
    "cairosvg": "cairosvg",
}


def bootstrap():
    # En el exe congelado (PyInstaller) no hay pip y sys.executable es el
    # propio exe: intentar "pip install" relanzaría la GUI en bucle. Las
    # dependencias ya vienen empaquetadas; si falta alguna es un error de
    # build que debe verse como ImportError claro, no como procesos zombis.
    if getattr(sys, "frozen", False):
        return

    for pkg, module in REQUIRED.items():
        try:
            __import__(module)
        except ImportError:
            print(f"[bootstrap] Instalando {pkg}...")
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", pkg, "--quiet"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

    # Opcionales: solo verificar, nunca abortar si fallan
    for pkg, module in OPTIONAL.items():
        try:
            __import__(module)
        except Exception:
            pass  # No disponible en este sistema — el motor lo manejará

    # Windows only
    import platform
    if platform.system() == "Windows":
        try:
            __import__("comtypes")
        except ImportError:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "comtypes", "--quiet"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
