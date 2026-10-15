"""
ui/audio_module_panel.py — Módulo Audio: Cortar, Unir, Mejorar y Transcribir.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTabWidget, QScrollArea, QFrame,
)


class AudioModulePanel(QWidget):
    """Módulo Audio con sus herramientas en pestañas."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        tabs = QTabWidget()
        tabs.setDocumentMode(True)

        # ── Pestaña 1: Cortar Audio ──────────────────────────────────
        try:
            from ui.audio_splitter_panel import AudioSplitterPanel
            splitter_scroll = QScrollArea()
            splitter_scroll.setWidgetResizable(True)
            splitter_scroll.setFrameShape(QFrame.Shape.NoFrame)
            splitter_scroll.setWidget(AudioSplitterPanel())
            tabs.addTab(splitter_scroll, "✂️  Cortar Audio")
        except Exception as e:
            from PyQt6.QtWidgets import QLabel
            lbl = QLabel(f"No disponible:\n{e}")
            lbl.setStyleSheet("color:#94a3b8; padding:24px;")
            tabs.addTab(lbl, "✂️  Cortar Audio")

        # ── Pestaña 2: Unir Audio ────────────────────────────────────
        try:
            from ui.audio_merger_panel import AudioMergerPanel
            merger_scroll = QScrollArea()
            merger_scroll.setWidgetResizable(True)
            merger_scroll.setFrameShape(QFrame.Shape.NoFrame)
            merger_scroll.setWidget(AudioMergerPanel())
            tabs.addTab(merger_scroll, "🎵  Unir Audio")
        except Exception as e:
            from PyQt6.QtWidgets import QLabel
            lbl = QLabel(f"No disponible:\n{e}")
            lbl.setStyleSheet("color:#94a3b8; padding:24px;")
            tabs.addTab(lbl, "🎵  Unir Audio")

        # ── Pestaña 3: Mejorar audio ─────────────────────────────────
        try:
            from ui.audio_enhance_panel import AudioEnhancePanel
            mejorar_scroll = QScrollArea()
            mejorar_scroll.setWidgetResizable(True)
            mejorar_scroll.setFrameShape(QFrame.Shape.NoFrame)
            mejorar_scroll.setWidget(AudioEnhancePanel())
            tabs.addTab(mejorar_scroll, "🎚  Mejorar audio")
        except Exception as e:
            from PyQt6.QtWidgets import QLabel
            lbl = QLabel(f"No disponible:\n{e}")
            lbl.setStyleSheet("color:#94a3b8; padding:24px;")
            tabs.addTab(lbl, "🎚  Mejorar audio")

        # ── Pestaña 4: Transcribir ───────────────────────────────────
        # Es el mismo panel del módulo Video: acepta audios y videos.
        self.transcribir = None
        try:
            from ui.transcribe_panel import TranscribePanel
            self.transcribir = TranscribePanel()
            transcribir_scroll = QScrollArea()
            transcribir_scroll.setWidgetResizable(True)
            transcribir_scroll.setFrameShape(QFrame.Shape.NoFrame)
            transcribir_scroll.setWidget(self.transcribir)
            tabs.addTab(transcribir_scroll, "🎙  Transcribir")
        except Exception as e:
            from PyQt6.QtWidgets import QLabel
            lbl = QLabel(f"No disponible:\n{e}")
            lbl.setStyleSheet("color:#94a3b8; padding:24px;")
            tabs.addTab(lbl, "🎙  Transcribir")

        self.tabs = tabs
        layout.addWidget(tabs)
