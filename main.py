"""
main.py — Punto de entrada de Navaja, editor universal de archivos.

Uso:
    python main.py

Requisitos externos (opcionales, amplían capacidades):
    - FFmpeg          → audio y video
    - LibreOffice     → documentos de oficina, Pages, Keynote, Numbers
    - Pandoc          → markdown, rst, epub, latex
    - wkhtmltopdf     → HTML → PDF alternativo
    - potrace         → imágenes raster → SVG
    - Tesseract       → OCR

Python packages (se instalan automáticamente):
    PyQt6, qtawesome, Pillow, reportlab, pypdf, cairosvg,
    python-docx, openpyxl, python-pptx, extract-msg,
    markdown, chardet
"""

import sys
import os

# ── 1. Asegurar path del proyecto ────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── 2. Paths y carpetas base (primero de todo) ───────────────────────
from core.paths import (BASE_DIR, TEMP_DIR, LOGS_DIR, MODELS_DIR, resource,
                        APP_VERSION, APP_NAME, APP_TITLE, APP_ID)

# ── 2b. Autoprueba de la transcripción (para verificar el paquete) ───
#   Navaja.exe --probar-transcripcion <audio> <informe.txt> [modelo]
# El exe no tiene consola: el resultado queda escrito en <informe.txt>.
if "--probar-transcripcion" in sys.argv:
    from motors.motor_transcribe import autoprueba
    sys.exit(autoprueba(sys.argv[sys.argv.index("--probar-transcripcion") + 1:]))

# ── 3. Bootstrap: instalar dependencias Python que falten ────────────
from core.bootstrap import bootstrap
bootstrap()

# ── 4. Imports Qt (después del bootstrap) ────────────────────────────
from PyQt6.QtWidgets import QApplication, QStyleFactory
from PyQt6.QtGui import QIcon

# ── 5. ConfigManager ─────────────────────────────────────────────────
from core.config_manager import config
config.load()


def _resource(name: str) -> str:
    """Resuelve la ruta de un recurso (funciona en dev y en el exe)."""
    return resource(name)


def main():
    # ── QApplication ──────────────────────────────────────────────────
    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create("Fusion"))
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName(APP_NAME)

    # ── Ícono de la aplicación (taskbar + exe) ────────────────────────
    # assets/icono.ico se genera desde assets/navaja.png con
    # assets/generar_icono.py.
    ico_path = _resource(os.path.join("assets", "icono.ico"))
    if os.path.isfile(ico_path):
        app_icon = QIcon(ico_path)
        app.setWindowIcon(app_icon)

    # Windows: forzar agrupación en taskbar con ícono correcto
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            APP_ID
        )
    except Exception:
        pass

    MIN_SPLASH_MS = 2200  # que la presentación se vea completa
    splash = None
    try:
        from ui.splash_animado import AnimatedSplash
        logo_path = _resource(os.path.join("assets", "icono.png"))
        splash = AnimatedSplash(
            logo_path if os.path.isfile(logo_path) else "",
            APP_TITLE, APP_VERSION,
        )
        splash.start()
        # Unos cuadros libres para que la entrada del logo se vea
        # fluida antes de que la carga empiece a ocupar el hilo.
        splash.wait(450)
    except Exception:
        splash = None

    def _splash_msg(msg: str, progreso: float = 0.0):
        if splash:
            splash.step(msg, progreso)

    _splash_msg("Iniciando…", 0.05)

    # ── Tema ──────────────────────────────────────────────────────────
    from ui.theme import ThemeManager
    ThemeManager.apply(app, config.get("theme", "light"))

    # ── Registrar motores en el grafo ─────────────────────────────────
    _splash_msg("Cargando motores de conversión…", 0.15)
    from core.graph import graph

    from motors.motor_images    import (
        PillowMotor, CairoSVGMotor, PotraceMotor,
        FitzSvgMotor, RasterEmbedSvgMotor, RawMotor,
        AiFitzMotor, GhostscriptEpsMotor,
    )
    from motors.motor_audio     import FFmpegAudioMotor
    from motors.motor_video     import FFmpegVideoMotor
    from motors.motor_documents import (
        LibreOfficeDocMotor, PandocMotor, TxtToPdfMotor,
        EmailMotor, HtmlToPdfMotor, PdfExtractMotor,
        PdfToDocxMotor, PdfToMdMotor, HtmlToMdMotor, TxtToMdMotor,
        DocutilsMotor, IpynbMotor,
    )
    from motors.motor_data      import DataMotor
    from motors.motor_ocr       import OcrMotor
    from motors.motor_msoffice  import MSWordMotor, MSExcelMotor, MSPowerPointMotor
    from motors.motor_fonts     import FontMotor
    from motors.motor_archives  import ArchiveMotor
    from motors.motor_subtitles_conv import SubtitleConvertMotor
    from motors.motor_ebooks    import CalibreMotor, MobiUnpackMotor, PdfToEpubMotor

    for motor in [
        PillowMotor,
        # SVG: CairoSVG si hay libcairo; MuPDF como alternativa integrada.
        # Potrace (vectorización real) antes que el fallback por incrustación.
        CairoSVGMotor, FitzSvgMotor, PotraceMotor, RasterEmbedSvgMotor,
        RawMotor, AiFitzMotor, GhostscriptEpsMotor,
        FFmpegAudioMotor, FFmpegVideoMotor,
        # PDF→DOCX y PDF→MD directos, antes que cualquier cadena indirecta
        PdfToDocxMotor, PdfToMdMotor,
        # Microsoft Office (si está instalado, tiene prioridad sobre LibreOffice
        # para formatos nativos de Office)
        MSWordMotor, MSExcelMotor, MSPowerPointMotor,
        # LibreOffice como fallback
        LibreOfficeDocMotor, TxtToPdfMotor, PandocMotor,
        HtmlToMdMotor, TxtToMdMotor, DocutilsMotor, IpynbMotor,
        EmailMotor, HtmlToPdfMotor, PdfExtractMotor,
        DataMotor, OcrMotor,
        FontMotor, ArchiveMotor, SubtitleConvertMotor,
        # Ebooks: Calibre (si está) gana; luego los puro-Python
        CalibreMotor, MobiUnpackMotor, PdfToEpubMotor,
    ]:
        graph.register(motor)
        if splash:
            splash.pump()

    _splash_msg("Armando la interfaz…", 0.30)

    # ── Ventana principal ─────────────────────────────────────────────
    from ui.main_window import MainWindow
    def _pagina_lista(hechas: int, total: int):
        # De 30% a 95% de la barra mientras se arman las páginas.
        _splash_msg("Armando la interfaz…", 0.30 + 0.65 * hechas / total)

    window = MainWindow(progreso=_pagina_lista)

    # Aplicar ícono también a la ventana principal
    if os.path.isfile(ico_path):
        window.setWindowIcon(QIcon(ico_path))

    # ── Cerrar la pantalla de inicio y mostrar la ventana ────────────
    # La ventana abre siempre maximizada.
    if splash:
        _splash_msg("Listo", 1.0)
        splash.wait_until(MIN_SPLASH_MS)
        splash.finish(window)   # muestra la ventana y se desvanece encima
    else:
        window.showMaximized()

    # ── Actualizar status bar con motores disponibles ─────────────────
    try:
        import shutil
        from core.paths import BIN_DIR
        has_ffmpeg = bool(
            os.path.isfile(os.path.join(BIN_DIR, "ffmpeg.exe")) or
            shutil.which("ffmpeg")
        )
        has_lo = bool(shutil.which("soffice") or
            any(os.path.isdir(p) for p in [
                "C:/Program Files/LibreOffice",
                "C:/Program Files (x86)/LibreOffice",
            ])
        )
        window.status_bar.update_motors(has_ffmpeg, has_lo)
        window.status_bar.update_theme(config.get("theme", "light"))
    except Exception:
        pass

    # ── Detectar capacidades del sistema y guardar runtime_caps.json ──
    try:
        _detect_runtime_caps()
    except Exception:
        pass

    # ── Mostrar aviso si config fue restaurada ────────────────────────
    if config.was_restored:
        try:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(
                window, "Configuración restaurada",
                "ℹ️  Se restableció la configuración por defecto.\n"
                "Esto pasa cuando el archivo de configuración estaba dañado."
            )
        except Exception:
            pass

    ret = app.exec()
    sys.exit(ret)


def _detect_runtime_caps():
    """Detecta herramientas externas y escribe runtime_caps.json."""
    import json
    import shutil
    from core.paths import BASE_DIR, BIN_DIR, MODELS_DIR

    def _find(names: list) -> str:
        for n in names:
            local = os.path.join(BIN_DIR, n)
            if os.path.isfile(local):
                return local
        for n in names:
            found = shutil.which(n)
            if found:
                return found
        return ""

    def _find_libreoffice() -> str:
        paths = [
            "C:/Program Files/LibreOffice/program/soffice.exe",
            "C:/Program Files (x86)/LibreOffice/program/soffice.exe",
        ]
        for p in paths:
            if os.path.isfile(p):
                return p
        return shutil.which("soffice") or ""

    ffmpeg_path    = _find(["ffmpeg.exe", "ffmpeg"])
    ffprobe_path   = _find(["ffprobe.exe", "ffprobe"])
    libreoffice    = _find_libreoffice()
    pandoc_path    = _find(["pandoc.exe", "pandoc"])
    potrace_path   = _find(["potrace.exe", "potrace"])
    # El OCR se empaqueta en bin/tesseract/ (exe + DLLs + tessdata juntos),
    # así que ese layout se prueba primero — ver motor_ocr._find_tesseract().
    tesseract_path = _find([os.path.join("tesseract", "tesseract.exe"),
                            "tesseract.exe", "tesseract"])

    whisper_dir    = os.path.join(MODELS_DIR, "whisper-base")
    whisper_ok     = os.path.isdir(whisper_dir) and bool(os.listdir(whisper_dir))

    caps = {
        "ffmpeg":                bool(ffmpeg_path),
        "ffmpeg_path":           ffmpeg_path,
        "ffprobe":               bool(ffprobe_path),
        "ffprobe_path":          ffprobe_path,
        "libreoffice":           bool(libreoffice),
        "libreoffice_path":      libreoffice,
        "pandoc":                bool(pandoc_path),
        "pandoc_path":           pandoc_path,
        "potrace":               bool(potrace_path),
        "potrace_path":          potrace_path,
        "tesseract":             bool(tesseract_path),
        "tesseract_path":        tesseract_path,
        "whisper_model_downloaded": whisper_ok,
        "whisper_model_path":    whisper_dir if whisper_ok else "",
    }

    caps_file = os.path.join(BASE_DIR, "runtime_caps.json")
    with open(caps_file, "w", encoding="utf-8") as f:
        json.dump(caps, f, indent=2)


if __name__ == "__main__":
    main()
