"""
ui/video_module_panel.py — Módulo Video: Partir, Ajustar tamaño, Mapa, Capturar fotograma
Mejorar audio y Transcribir.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTabWidget, QScrollArea, QFrame, QLabel,
)


def _en_scroll(widget) -> QScrollArea:
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setWidget(widget)
    return scroll


def _no_disponible(error) -> QLabel:
    lbl = QLabel(f"No disponible:\n{error}")
    lbl.setStyleSheet("color:#94a3b8; padding:24px;")
    return lbl


class VideoModulePanel(QWidget):
    """Módulo Video con sus herramientas en pestañas."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        tabs = QTabWidget()
        tabs.setDocumentMode(True)

        # ── Pestaña 1: Partir Video ──────────────────────────────────
        try:
            from ui.video_splitter_panel import VideoSplitterPanel
            tabs.addTab(_en_scroll(VideoSplitterPanel()), "✂️  Partir Video")
        except Exception as e:
            tabs.addTab(_no_disponible(e), "✂️  Partir Video")

        # ── Pestaña 2: Ajustar tamaño ────────────────────────────────────
        try:
            from ui.video_compress_panel import VideoCompressPanel
            tabs.addTab(_en_scroll(VideoCompressPanel()), "📦  Ajustar tamaño")
        except Exception as e:
            tabs.addTab(_no_disponible(e), "📦  Ajustar tamaño")

        # ── Pestañas 3 y 4: el mapa y la captura trabajan juntas ─────
        # El mapa sirve para encontrar el momento y la captura para sacarlo en
        # tamaño real: al tocar una miniatura del mapa, el programa salta solo
        # a la otra solapa, ya parado en ese fotograma.
        self.mapa = None
        self.captura = None
        try:
            from ui.video_map_panel import VideoMapPanel
            self.mapa = VideoMapPanel()
            tabs.addTab(_en_scroll(self.mapa), "🗺️  Mapa del video")
        except Exception as e:
            tabs.addTab(_no_disponible(e), "🗺️  Mapa del video")

        try:
            from ui.frame_capture_panel import FrameCapturePanel
            self.captura = FrameCapturePanel()
            indice_captura = tabs.addTab(_en_scroll(self.captura),
                                         "📸  Capturar fotograma")
        except Exception as e:
            indice_captura = tabs.addTab(_no_disponible(e),
                                         "📸  Capturar fotograma")

        if self.mapa is not None and self.captura is not None:
            self.mapa.momento_elegido.connect(
                lambda ruta, t: (self.captura.ir_a_momento(ruta, t),
                                 tabs.setCurrentIndex(indice_captura)))

        # ── Pestaña 5: Mejorar el audio del video ────────────────────
        # Es el mismo panel del módulo Audio: acepta audios y videos.
        try:
            from ui.audio_enhance_panel import AudioEnhancePanel
            tabs.addTab(_en_scroll(AudioEnhancePanel()), "🎚  Mejorar audio")
        except Exception as e:
            tabs.addTab(_no_disponible(e), "🎚  Mejorar audio")

        # ── Pestaña 6: Transcribir lo que se dice en el video ────────
        self.transcribir = None
        try:
            from ui.transcribe_panel import TranscribePanel
            self.transcribir = TranscribePanel()
            tabs.addTab(_en_scroll(self.transcribir), "🎙  Transcribir")
        except Exception as e:
            tabs.addTab(_no_disponible(e), "🎙  Transcribir")

        self.tabs = tabs
        layout.addWidget(tabs)
