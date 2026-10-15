"""test_imports.py — Quick import test for all modules."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

results = []

def test(label, fn):
    try:
        fn()
        results.append(f"OK  {label}")
    except Exception as e:
        results.append(f"FAIL {label}: {e}")

test("core.paths", lambda: __import__("core.paths", fromlist=["BASE_DIR"]))
test("core.bootstrap", lambda: __import__("core.bootstrap", fromlist=["bootstrap"]))
test("core.config_manager", lambda: __import__("core.config_manager", fromlist=["config"]))
test("core.graph", lambda: __import__("core.graph", fromlist=["graph"]))
test("core.hasher", lambda: __import__("core.hasher", fromlist=["sha256"]))
test("core.logger", lambda: __import__("core.logger", fromlist=["ConversionLogger"]))
test("core.runner", lambda: __import__("core.runner", fromlist=["run_conversion"]))
test("motors.motor_images", lambda: __import__("motors.motor_images", fromlist=["PillowMotor"]))
test("motors.motor_audio", lambda: __import__("motors.motor_audio", fromlist=["FFmpegAudioMotor"]))
test("motors.motor_video", lambda: __import__("motors.motor_video", fromlist=["FFmpegVideoMotor"]))
test("motors.motor_documents", lambda: __import__("motors.motor_documents", fromlist=["TxtToPdfMotor"]))
test("motors.motor_data", lambda: __import__("motors.motor_data", fromlist=["DataMotor"]))
test("motors.motor_ocr", lambda: __import__("motors.motor_ocr", fromlist=["OcrMotor"]))
test("motors.motor_pdf_stamp", lambda: __import__("motors.motor_pdf_stamp", fromlist=["stamp_pdf_footer"]))
test("motors.motor_video_splitter", lambda: __import__("motors.motor_video_splitter", fromlist=["split_video"]))

# Qt imports
try:
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    test("ui.theme", lambda: __import__("ui.theme", fromlist=["ThemeManager"]))
    test("ui.widgets", lambda: __import__("ui.widgets", fromlist=["DropZone"]))
    test("ui.manual", lambda: __import__("ui.manual", fromlist=["MANUAL_HTML"]))
    test("ui.log_viewer", lambda: __import__("ui.log_viewer", fromlist=["LogViewerPanel"]))
    test("ui.video_splitter_panel", lambda: __import__("ui.video_splitter_panel", fromlist=["VideoSplitterPanel"]))
    test("ui.worker", lambda: __import__("ui.worker", fromlist=["ConversionWorker"]))
    test("ui.main_window", lambda: __import__("ui.main_window", fromlist=["MainWindow"]))
except Exception as e:
    results.append(f"FAIL Qt setup: {e}")

print("\n".join(results))
fails = [r for r in results if r.startswith("FAIL")]
print(f"\n{'='*40}")
print(f"Total: {len(results)} | OK: {len(results)-len(fails)} | FAIL: {len(fails)}")
