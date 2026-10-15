"""test_gui_start.py — Verifica que la GUI arranca sin errores y cierra sola."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("PYTHONUTF8", "1")

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

errors = []

app = QApplication(sys.argv)
app.setStyle("Fusion")

try:
    from core.paths import BASE_DIR, TEMP_DIR, LOGS_DIR, MODELS_DIR, resource
    from core.config_manager import config
    config.load()
    from ui.theme import ThemeManager
    ThemeManager.apply(app, config.get("theme", "light"))

    from core.graph import graph
    from motors.motor_images    import PillowMotor, CairoSVGMotor, PotraceMotor
    from motors.motor_audio     import FFmpegAudioMotor
    from motors.motor_video     import FFmpegVideoMotor
    from motors.motor_documents import (LibreOfficeDocMotor, PandocMotor, TxtToPdfMotor,
                                         EmailMotor, HtmlToPdfMotor, PdfExtractMotor)
    from motors.motor_data      import DataMotor
    from motors.motor_ocr       import OcrMotor
    for motor in [PillowMotor, CairoSVGMotor, PotraceMotor, FFmpegAudioMotor, FFmpegVideoMotor,
                  LibreOfficeDocMotor, TxtToPdfMotor, PandocMotor, EmailMotor, HtmlToPdfMotor,
                  PdfExtractMotor, DataMotor, OcrMotor]:
        graph.register(motor)

    from ui.main_window import MainWindow
    window = MainWindow()
    window.show()
    print("GUI arranco correctamente.")

    # Cierra automaticamente despues de 2 segundos
    QTimer.singleShot(2000, app.quit)
    app.exec()
    print("GUI cerro correctamente.")
    sys.exit(0)

except Exception as e:
    import traceback
    print(f"ERROR: {e}")
    traceback.print_exc()
    sys.exit(1)
