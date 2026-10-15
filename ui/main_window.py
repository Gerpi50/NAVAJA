"""
ui/main_window.py — Ventana principal de Navaja.
"""
import os
import platform
import shutil
import subprocess

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QProgressBar, QFileDialog,
    QMessageBox, QFrame, QScrollArea,
    QSizePolicy, QApplication, QListWidget, QListWidgetItem,
    QSplitter, QTextBrowser, QStatusBar,
)
from PyQt6.QtCore import Qt, QSize, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QIcon, QDragEnterEvent, QDropEvent, QColor
from ui.format_grid import FormatGrid

from core.graph import graph
from ui.worker import ConversionWorker, ConversionJob
from ui.informe_widget import InformeSection
from core.salidas import carpeta_destino, etiqueta_destino
from ui.widgets import (
    DropZone, FileCard, AppStatusBar, ThemeToggle, PanicButton,
    CategoryTabBar,
    AudioFilterOption, SubtitleOption, OcrOption,
    WatermarkOption, FooterLegendOption, PageNumberOption, MetadataOption, PageMarkerOption,
    # backward compat names still importable
    AudioFilterPanel, SubtitlePanel, OcrPanel,
    WatermarkPanel, LegendPanel, PageNumberPanel, MetadataPanel,
    get_file_category, FORMAT_CATEGORIES,
)


class ClickableRow(QFrame):
    """Fila con varios widgets adentro que se comporta como un botón.

    No se usa un QPushButton porque Qt no calcula el alto de un botón a
    partir de un layout hijo: el botón queda colapsado y sus etiquetas se
    dibujan encima de lo que tiene arriba.
    """

    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mouseReleaseEvent(self, event):
        if (event.button() == Qt.MouseButton.LeftButton
                and self.rect().contains(event.position().toPoint())):
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class MainWindow(QMainWindow):
    """Ventana principal de Navaja."""

    PAGE_CONVERTER   = 0
    PAGE_VIDEO_SPLIT = 1
    PAGE_AUDIO_SPLIT = 2
    PAGE_PDF_MERGE   = 3
    PAGE_EXCEL_MERGE = 4
    PAGE_AUDIO_MERGE = 5
    PAGE_LOG         = 6
    PAGE_HELP        = 7
    PAGE_VIDEO_COMPRESS = 8
    PAGE_HOME          = 9
    PAGE_AUDIO_MODULE  = 10   # Cortar Audio + Unir Audio
    PAGE_VIDEO_MODULE  = 11   # Partir Video + Ajustar tamaño
    PAGE_PDF_TOOLS     = 12   # Módulo PDF: unir, partir, firmar, OCR…
    PAGE_HASH          = 13   # Extraer hash (integridad de cualquier archivo)
    PAGE_EDITOR        = 14   # Escribir un texto y guardarlo en cualquier formato

    def __init__(self, progreso=None):
        """progreso(hechas, total): se llama al terminar de armar cada página;
        la pantalla de inicio lo usa para avanzar la barra y repintarse."""
        super().__init__()
        self._progreso              = progreso
        self.selected_files: list   = []
        self.output_dir: str        = ""
        self.worker                 = None
        self._file_cards: dict      = {}   # src_path (ruta completa) → (FileCard, QListWidgetItem)
        self._converting            = False
        self._last_result_msg       = ""
        self._log_panel             = None
        self._nav_buttons: list     = []   # list of (page_idx, QPushButton)
        self.setAcceptDrops(True)
        self._init_ui()
        self._init_icon()
        self._refresh_formats()

    def _init_icon(self):
        """Establece el ícono de la ventana (y taskbar en Windows)."""
        try:
            from core.paths import resource
            ico_path = resource(os.path.join("assets", "icono.ico"))
            if os.path.isfile(ico_path):
                icon = QIcon(ico_path)
                self.setWindowIcon(icon)
                QApplication.instance().setWindowIcon(icon)
        except Exception:
            pass

        # Taskbar en Windows: asignar AppUserModelID para agrupación correcta
        try:
            import ctypes
            from core.paths import APP_ID
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
        except Exception:
            pass

    # ──────────────────────────────────────────────────────────────────
    # Construcción de la UI
    # ──────────────────────────────────────────────────────────────────

    def _init_ui(self):
        from core.paths import APP_TITLE
        self.setWindowTitle(APP_TITLE)
        self.setMinimumSize(960, 680)
        self.resize(1200, 800)

        # Root widget: sidebar izq + área principal der
        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ── Sidebar ──────────────────────────────────────────────────
        sidebar = self._build_sidebar()
        root_layout.addWidget(sidebar)

        # ── Área principal: stack + status bar ───────────────────────
        main_area = QWidget()
        main_area.setObjectName("mainArea")
        main_layout = QVBoxLayout(main_area)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Aviso de restauración de config
        try:
            from core.config_manager import config
            if config.was_restored:
                warn_cfg = QLabel("ℹ️  Se restableció la configuración por defecto.")
                warn_cfg.setStyleSheet(
                    "background:#eff6ff; color:#1d4ed8; padding: 6px 16px; font-size:11px;"
                )
                main_layout.addWidget(warn_cfg)
                QTimer.singleShot(5000, warn_cfg.deleteLater)
        except Exception:
            pass

        # Stack de páginas
        from PyQt6.QtWidgets import QStackedWidget
        self._stack = QStackedWidget()
        self._stack.setObjectName("mainStack")

        # Páginas, en el orden de los índices PAGE_* de arriba.
        paginas = [
            self._build_converter_page,                        # 0
            lambda: self._build_tool_page("video_split"),      # 1
            lambda: self._build_tool_page("audio_split"),      # 2
            lambda: self._build_tool_page("pdf_merge"),        # 3
            lambda: self._build_tool_page("excel_merge"),      # 4
            lambda: self._build_tool_page("audio_merge"),      # 5
            lambda: self._build_tool_page("log"),              # 6
            lambda: self._build_tool_page("help"),             # 7
            lambda: self._build_tool_page("video_compress"),   # 8
            self._build_home_page,                             # 9
            lambda: self._build_tool_page("audio_module"),     # 10
            lambda: self._build_tool_page("video_module"),     # 11
            lambda: self._build_tool_page("pdf_tools"),        # 12
            lambda: self._build_tool_page("hash"),             # 13
            lambda: self._build_tool_page("editor"),           # 14
        ]
        for i, armar in enumerate(paginas, start=1):
            self._stack.addWidget(armar())
            if self._progreso:
                try:
                    self._progreso(i, len(paginas))
                except Exception:
                    pass

        main_layout.addWidget(self._stack, stretch=1)

        # Status bar
        self.status_bar = AppStatusBar()
        main_layout.addWidget(self.status_bar)

        root_layout.addWidget(main_area, stretch=1)
        self.setCentralWidget(root)

        # Activar Home como página inicial
        self._set_active_nav(self.PAGE_HOME)
        self._stack.setCurrentIndex(self.PAGE_HOME)

    # ──────────────────────────────────────────────────────────────────
    # Sidebar
    # ──────────────────────────────────────────────────────────────────

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("sideBar")
        sidebar.setFixedWidth(224)
        sidebar.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

        # El contenido va dentro de un QScrollArea: si la pantalla es baja,
        # aparece la barra y se puede llegar a "Salir" en vez de que los
        # últimos ítems queden cortados contra el borde de la ventana.
        marco = QVBoxLayout(sidebar)
        marco.setContentsMargins(0, 0, 0, 0)
        marco.setSpacing(0)

        scroll = QScrollArea()
        scroll.setObjectName("sideBarScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        marco.addWidget(scroll)

        contenido = QWidget()
        contenido.setObjectName("sideBarContent")
        scroll.setWidget(contenido)

        layout = QVBoxLayout(contenido)
        layout.setContentsMargins(12, 20, 12, 10)
        layout.setSpacing(4)

        # ── Logo ──────────────────────────────────────────────────────
        logo_widget = QWidget()
        logo_widget.setObjectName("sideBarLogo")
        logo_layout = QVBoxLayout(logo_widget)
        logo_layout.setContentsMargins(10, 8, 10, 12)
        logo_layout.setSpacing(2)

        from core.paths import APP_NAME, APP_TAGLINE
        lbl_title = QLabel(APP_NAME)
        lbl_title.setObjectName("sideBarTitle")
        logo_layout.addWidget(lbl_title)

        lbl_subtitle = QLabel(APP_TAGLINE.upper())
        lbl_subtitle.setObjectName("sideBarSubtitle")
        logo_layout.addWidget(lbl_subtitle)

        layout.addWidget(logo_widget)

        sep_top = QFrame()
        sep_top.setObjectName("sideBarSep")
        layout.addWidget(sep_top)
        layout.addSpacing(6)

        # ── Inicio ────────────────────────────────────────────────────
        # El tooltip dice para qué sirve volver acá, no cómo se llama la
        # pantalla: "Inicio" ya está escrito al lado del ícono.
        layout.addWidget(self._make_nav_btn(
            self.PAGE_HOME, "🏠", "Inicio",
            "¿No sabés qué botón tocar?\n"
            "Acá está la lista de «qué necesito hacer» y el programa\n"
            "te lleva directo a la pantalla que lo resuelve."
        ))

        layout.addSpacing(4)

        # ── Módulos, agrupados por lo que se hace ─────────────────────
        #
        # Antes estaban todos al mismo nivel y el menú mezclaba dos cosas
        # distintas: un verbo ("Convertir") con tipos de archivo ("PDF",
        # "Audio"). Ahora son tres caminos: cambiar el formato, trabajar
        # sobre el archivo del mismo tipo, y verificar la integridad. Los
        # cuatro tipos siguen a un solo clic: agrupar no puede costar
        # clics de más.
        # Los títulos de sección y los tooltips están escritos como preguntas
        # del usuario, no como categorías del programa: "¿lo necesito en otro
        # formato?" en vez de "CONVERTIR". El que sabe lo que busca lee el
        # nombre del botón y listo; el que no, lee el tooltip y se ubica.
        secciones = [
            ("¿LO NECESITÁS EN OTRO FORMATO?", [
                (self.PAGE_CONVERTER, "🔄", "Convertir",
                 "Cambiarle el formato a un archivo, sin tocar su contenido.\n"
                 "Word a PDF · foto a PDF · video a MP3 · Excel a CSV…\n\n"
                 "Cargás el archivo y el programa te muestra a qué formatos\n"
                 "se puede pasar. Los que no se pueden, no aparecen."),
            ]),
            ("¿TRABAJAR SOBRE EL ARCHIVO?", [
                # Un solo módulo para PDF: antes estaba partido en "Texto /
                # PDF" y "Editar PDF", dos nombres que no decían qué hacía
                # cada uno y que además repetían la función de unir.
                (self.PAGE_PDF_TOOLS, "📄", "PDF",
                 "Todo lo que se hace SOBRE un PDF, sin cambiarle el formato:\n"
                 "· Unir varios en uno · Partir uno que pesa demasiado\n"
                 "· Ajustarlo a un tamaño máximo · Reordenar, rotar o sacar páginas\n"
                 "· Firmarlo digitalmente · Reconocer el texto de un escaneo\n"
                 "· Pasar a Excel la tabla de un resumen o un listado\n"
                 "· Comprimir, proteger y reparar"),
                (self.PAGE_AUDIO_MODULE, "🎵", "Audio",
                 "· Cortar un audio largo en partes\n"
                 "· Unir varios audios en un solo archivo\n"
                 "· Mejorar un audio que se escucha mal\n"
                 "· Transcribir: pasar a texto lo que se dice"),
                (self.PAGE_VIDEO_MODULE, "🎬", "Video",
                 "· Partir un video en partes, sin perder calidad\n"
                 "· Ajustarlo a un tamaño máximo (con informe)\n"
                 "· Mapa del video: toda la grabación en una imagen\n"
                 "· Capturar el fotograma exacto de un momento\n"
                 "· Mejorar el audio · Transcribir lo que se dice"),
                (self.PAGE_EXCEL_MERGE, "📊", "Tablas / Excel",
                 "Unir varios Excel en uno solo\n"
                 "y partir el resultado si queda muy pesado"),
            ]),
            ("¿ESCRIBIR ALGO?", [
                (self.PAGE_EDITOR, "✍️", "Escribir",
                 "Escribir un texto acá mismo y guardarlo directamente\n"
                 "como Word, PDF, OpenDocument, HTML, EPUB, TXT o MD.\n"
                 "No hace falta saber Markdown: escribís normal."),
            ]),
            ("¿COMPROBAR QUE NO SE TOCÓ?", [
                (self.PAGE_HASH, "🔢", "Extraer hash",
                 "La huella digital de un archivo (SHA-256).\n"
                 "Sirve para probar que un archivo es idéntico al original,\n"
                 "y para verificar una huella que te pasaron."),
            ]),
        ]
        for titulo, entradas in secciones:
            layout.addWidget(self._section_label(titulo))
            for page_idx, emoji, label, tooltip in entradas:
                layout.addWidget(
                    self._make_nav_btn(page_idx, emoji, label, tooltip))
            layout.addSpacing(2)

        # Stretch
        layout.addStretch()

        sep_bot = QFrame()
        sep_bot.setObjectName("sideBarSep")
        layout.addWidget(sep_bot)
        layout.addSpacing(4)

        # Log y Ayuda al fondo
        for page_idx, emoji, label, tooltip in [
            (self.PAGE_LOG, "📋", "Log",
             "Qué hizo el programa: la lista de todo lo procesado,\n"
             "con las constancias para copiar y pegar donde haga falta."),
            (self.PAGE_HELP, "❓", "Ayuda",
             "El manual, con el paso a paso de cada herramienta\n"
             "y ejemplos de para qué sirve cada una."),
        ]:
            layout.addWidget(self._make_nav_btn(page_idx, emoji, label, tooltip))

        layout.addSpacing(4)

        # Toggle de tema
        self.theme_btn = ThemeToggle()
        self.theme_btn.clicked.connect(self._toggle_theme)
        layout.addWidget(self.theme_btn)

        # Botón de salir (visible desde cualquier módulo)
        layout.addSpacing(4)
        layout.addWidget(self._build_exit_button())

        return sidebar

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("sideBarSection")
        # Los títulos ahora son preguntas y no entran en los 224 px de la
        # barra: sin esto, "¿LO NECESITÁS EN OTRO FORMATO?" quedaba cortado.
        lbl.setWordWrap(True)
        return lbl

    def _build_exit_button(self) -> QWidget:
        """Botón de salida al pie del sidebar.

        Vive en el sidebar, así que está visible desde cualquier módulo sin
        importar en qué solapa esté el usuario.
        """
        from core.paths import APP_NAME
        btn = ClickableRow()
        btn.setObjectName("sideBarExit")
        btn.setToolTip(f"Cerrar {APP_NAME}")

        row = QHBoxLayout(btn)
        row.setContentsMargins(8, 6, 10, 6)
        row.setSpacing(10)

        avatar = QLabel(APP_NAME[:1])
        avatar.setObjectName("profileAvatar")
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(avatar)

        name_lbl = QLabel(APP_NAME)
        name_lbl.setObjectName("profileName")
        row.addWidget(name_lbl, stretch=1)

        salir_lbl = QLabel("⏻")
        salir_lbl.setObjectName("exitIcon")
        row.addWidget(salir_lbl)

        # Sin esto, los QLabel se comen el clic y la fila nunca se dispara
        for hijo in (avatar, name_lbl, salir_lbl):
            hijo.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        btn.clicked.connect(self._confirm_exit)
        self.exit_btn = btn
        return btn

    def _confirm_exit(self):
        """Pide confirmación antes de cerrar, para no perder trabajo a medias."""
        resp = QMessageBox.question(
            self, "Cerrar",
            "¿Querés cerrar la aplicación?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if resp == QMessageBox.StandardButton.Yes:
            self.close()

    def _make_nav_btn(self, page_idx: int, emoji: str, label: str, tooltip: str) -> QPushButton:
        btn = QPushButton(f"{emoji}  {label}")
        btn.setObjectName("navBtn")
        btn.setCheckable(True)
        btn.setToolTip(tooltip)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda checked, idx=page_idx: self._nav_to(idx))
        self._nav_buttons.append((page_idx, btn))
        return btn

    def _nav_to(self, page_idx: int, solapa: str = None):
        """Va a una página y, si se pide, abre una solapa de adentro.

        Los módulos grandes (PDF, Video, Audio) tienen varias solapas, y
        llegar al módulo no es llegar a la herramienta: el usuario todavía
        tiene que adivinar cuál de las siete solapas del PDF le sirve. Con
        `solapa`, la pantalla de inicio lo deja parado en la correcta.

        La solapa se busca por una palabra de su nombre y no por su número:
        reordenarlas o cambiarles el ícono no rompe nada.
        """
        self._stack.setCurrentIndex(page_idx)
        self._set_active_nav(page_idx)
        if solapa:
            self._abrir_solapa(self._stack.widget(page_idx), solapa)

    @staticmethod
    def _abrir_solapa(pagina, palabra: str) -> bool:
        from PyQt6.QtWidgets import QTabWidget

        if pagina is None:
            return False
        tabs = (pagina if isinstance(pagina, QTabWidget)
                else pagina.findChild(QTabWidget))
        if tabs is None:
            return False
        palabra = palabra.lower()
        for i in range(tabs.count()):
            if palabra in tabs.tabText(i).lower():
                tabs.setCurrentIndex(i)
                return True
        return False

    def _set_active_nav(self, active_idx: int):
        for idx, btn in self._nav_buttons:
            btn.setChecked(idx == active_idx)

    # ──────────────────────────────────────────────────────────────────
    # Páginas del stack
    # ──────────────────────────────────────────────────────────────────

    def _build_tool_page(self, tool_name: str) -> QWidget:
        """Crea una página con el panel de herramienta correspondiente."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        if tool_name == "video_split":
            try:
                from ui.video_splitter_panel import VideoSplitterPanel
                panel = VideoSplitterPanel()
            except Exception as e:
                panel = self._error_placeholder(f"Panel 'Partir Video' no disponible.\n{e}")

        elif tool_name == "audio_split":
            try:
                from ui.audio_splitter_panel import AudioSplitterPanel
                panel = AudioSplitterPanel()
            except Exception as e:
                panel = self._error_placeholder(f"Panel 'Cortar Audio' no disponible.\n{e}")

        elif tool_name == "pdf_merge":
            try:
                from ui.pdf_merger_splitter_panel import PdfMergerSplitterPanel
                panel = PdfMergerSplitterPanel()
            except Exception as e:
                panel = self._error_placeholder(f"Panel 'Unir PDFs' no disponible.\n{e}")

        elif tool_name == "excel_merge":
            try:
                from ui.excel_merger_panel import ExcelMergerPanel
                panel = ExcelMergerPanel()
            except Exception as e:
                panel = self._error_placeholder(f"Panel 'Unir Excel' no disponible.\n{e}")

        elif tool_name == "audio_merge":
            try:
                from ui.audio_merger_panel import AudioMergerPanel
                panel = AudioMergerPanel()
            except Exception as e:
                panel = self._error_placeholder(f"Panel 'Unir Audio' no disponible.\n{e}")

        elif tool_name == "video_compress":
            try:
                from ui.video_compress_panel import VideoCompressPanel
                panel = VideoCompressPanel()
            except Exception as e:
                panel = self._error_placeholder(f"Panel 'Ajustar tamaño' no disponible.\n{e}")

        elif tool_name == "audio_module":
            try:
                from ui.audio_module_panel import AudioModulePanel
                return AudioModulePanel()
            except Exception as e:
                panel = self._error_placeholder(f"Módulo 'Audio' no disponible.\n{e}")

        elif tool_name == "video_module":
            try:
                from ui.video_module_panel import VideoModulePanel
                return VideoModulePanel()
            except Exception as e:
                panel = self._error_placeholder(f"Módulo 'Video' no disponible.\n{e}")

        elif tool_name == "editor":
            try:
                from ui.editor_panel import EditorPanel
                panel = EditorPanel()
            except Exception as e:
                panel = self._error_placeholder(
                    f"Panel 'Escribir' no disponible.\n{e}")

        elif tool_name == "hash":
            try:
                from ui.hash_panel import HashPanel
                panel = HashPanel()
            except Exception as e:
                panel = self._error_placeholder(
                    f"Panel 'Extraer hash' no disponible.\n{e}")

        elif tool_name == "pdf_tools":
            try:
                from ui.pdf_organizer_panel import PdfOrganizerPanel
                panel = PdfOrganizerPanel()
            except Exception as e:
                panel = self._error_placeholder(f"Panel 'Editar PDF' no disponible.\n{e}")

        elif tool_name == "log":
            try:
                from ui.log_viewer import LogViewerPanel
                panel = LogViewerPanel()
                self._log_panel = panel
            except Exception as e:
                panel = self._error_placeholder(f"Panel 'Log' no disponible.\n{e}")

        elif tool_name == "help":
            try:
                from ui.help_panel import HelpPanel
                panel = HelpPanel()
            except Exception as e:
                # Respaldo: visor simple si el panel con buscador falla
                try:
                    from ui.manual import MANUAL_HTML
                    browser = QTextBrowser()
                    browser.setHtml(MANUAL_HTML)
                    browser.setOpenExternalLinks(True)
                    panel = browser
                except Exception as e2:
                    panel = self._error_placeholder(f"Panel 'Ayuda' no disponible.\n{e2}")

        else:
            panel = self._error_placeholder(f"Panel '{tool_name}' desconocido.")

        scroll.setWidget(panel)
        return scroll

    def _build_home_page(self) -> QWidget:
        """Crea el dashboard de inicio con Bento Grid."""
        try:
            from ui.home_panel import HomePanel
            return HomePanel(navigate_to=self._nav_to)
        except Exception as e:
            return self._error_placeholder(f"Panel 'Inicio' no disponible.\n{e}")

    def _paneles_con_trabajo(self) -> list:
        """Los paneles que tienen algo para guardar o cortar al salir."""
        paneles = []
        try:
            from ui.transcribe_panel import TranscribePanel
            paneles.extend(self.findChildren(TranscribePanel))
        except Exception:
            pass
        return paneles

    def _error_placeholder(self, msg: str) -> QWidget:
        """Widget de error para cuando un panel no puede cargarse."""
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl = QLabel(msg)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setWordWrap(True)
        lbl.setStyleSheet("color: #94a3b8; font-size: 13px; padding: 40px;")
        lay.addWidget(lbl)
        return w

    # ──────────────────────────────────────────────────────────────────
    # Página 0: Conversor
    # ──────────────────────────────────────────────────────────────────

    def _build_converter_page(self) -> QWidget:
        """Panel de conversión: splitter horizontal file_panel | format_panel."""
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        splitter.addWidget(self._build_file_panel())
        splitter.addWidget(self._build_format_panel())
        splitter.setSizes([380, 620])
        return splitter

    def _build_file_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("filePanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # Header
        lbl = QLabel("📂  Cola de archivos")
        lbl.setObjectName("panelHeader")
        layout.addWidget(lbl)

        # Zona drag & drop
        self.drop_zone = DropZone()
        self.drop_zone.files_dropped.connect(self._add_files_list)
        layout.addWidget(self.drop_zone)

        # Aviso archivos mixtos
        self.warn_mixed = QLabel(
            "⚠️  Hay archivos de distintos tipos en la cola.\n"
            "El formato elegido se aplicará solo a los compatibles.\n"
            "Los incompatibles se marcarán con ⛔ y se saltearán."
        )
        self.warn_mixed.setObjectName("warnMixed")
        self.warn_mixed.setWordWrap(True)
        self.warn_mixed.setVisible(False)
        layout.addWidget(self.warn_mixed)

        # CategoryTabBar
        self.category_tab_bar = CategoryTabBar()
        self.category_tab_bar.category_changed.connect(self._on_category_filter)
        layout.addWidget(self.category_tab_bar)

        # Lista de archivos
        self.file_list = QListWidget()
        self.file_list.setSpacing(2)
        self.file_list.setMinimumHeight(200)
        layout.addWidget(self.file_list, stretch=1)

        # Botones Archivos + Carpeta
        btn_row = QHBoxLayout()
        btn_files = QPushButton("📄 Archivos")
        btn_folder = QPushButton("📁 Carpeta")
        btn_files.clicked.connect(self._add_files_dialog)
        btn_folder.clicked.connect(self._add_folder_dialog)
        btn_row.addWidget(btn_files)
        btn_row.addWidget(btn_folder)
        layout.addLayout(btn_row)

        # Panic button
        self.panic_btn = PanicButton()
        self.panic_btn.panic_confirmed.connect(self._do_panic)
        layout.addWidget(self.panic_btn)

        return panel

    def _build_format_panel(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # ── Formato de salida ────────────────────────────────────────
        fmt_card = QFrame()
        fmt_card.setObjectName("card")
        fmt_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        fc = QVBoxLayout(fmt_card)
        fc.setContentsMargins(12, 10, 12, 10)
        fc.setSpacing(6)

        lbl_fmt = QLabel("Formato de salida")
        lbl_fmt.setObjectName("cardHeader")
        fc.addWidget(lbl_fmt)

        # Grilla de formatos
        self.format_grid = FormatGrid()
        self.format_grid.format_selected.connect(self._on_format_selected)
        self.format_grid.format_cleared.connect(self._on_format_cleared)
        fc.addWidget(self.format_grid)

        self.lbl_route = QLabel("")
        self.lbl_route.setStyleSheet("font-size:11px; padding-top:2px;")
        self.lbl_route.setWordWrap(True)
        fc.addWidget(self.lbl_route)

        # Carpeta de salida
        sep = QFrame()
        sep.setObjectName("sep")
        fc.addWidget(sep)

        lbl_out = QLabel("Carpeta de destino")
        lbl_out.setObjectName("cardHeader")
        fc.addWidget(lbl_out)

        out_row = QHBoxLayout()
        self.lbl_out_path = QLabel(etiqueta_destino(""))
        self.lbl_out_path.setStyleSheet("font-size:11px; color:#64748b;")
        self.lbl_out_path.setWordWrap(True)
        btn_change_out = QPushButton("Cambiar")
        btn_change_out.setObjectName("ghostBtn")
        btn_change_out.setFixedWidth(80)
        btn_change_out.clicked.connect(self._set_output_dir)
        out_row.addWidget(self.lbl_out_path, stretch=1)
        out_row.addWidget(btn_change_out)
        fc.addLayout(out_row)

        layout.addWidget(fmt_card, stretch=3)

        # ── Opciones ─────────────────────────────────────────────────
        # Con poco alto asignado, las opciones (marca de agua, leyenda,
        # numeración, OCR…) quedaban recortadas y no se leían. Ahora tienen
        # un mínimo propio, crecen igual que la grilla de formatos y la
        # barra de scroll se ve.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setMinimumHeight(190)
        scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        opts_container = QWidget()
        opts_layout = QVBoxLayout(opts_container)
        opts_layout.setContentsMargins(0, 0, 0, 0)
        opts_layout.setSpacing(6)

        self.opt_metadata = MetadataOption()
        self.metadata_panel = self.opt_metadata
        opts_layout.addWidget(self.opt_metadata)

        # Los números de página van arriba de todo porque es la opción que
        # cambia el contenido del texto: conviene que se vea, no que se
        # descubra.
        self.opt_paginas = PageMarkerOption()
        opts_layout.addWidget(self.opt_paginas)

        self.opt_watermark = WatermarkOption()
        self.watermark_panel = self.opt_watermark
        opts_layout.addWidget(self.opt_watermark)

        self.opt_footer = FooterLegendOption()
        self.legend_panel = self.opt_footer
        opts_layout.addWidget(self.opt_footer)

        self.opt_pagenums = PageNumberOption()
        self.page_num_panel = self.opt_pagenums
        opts_layout.addWidget(self.opt_pagenums)

        self.opt_audio = AudioFilterOption()
        self.audio_panel = self.opt_audio
        self.opt_audio.setVisible(False)
        opts_layout.addWidget(self.opt_audio)

        self.opt_subtitle = SubtitleOption()
        self.subtitle_panel = self.opt_subtitle
        self.opt_subtitle.setVisible(False)
        opts_layout.addWidget(self.opt_subtitle)

        self.opt_ocr = OcrOption()
        self.ocr_panel = self.opt_ocr
        self.opt_ocr.setVisible(False)
        opts_layout.addWidget(self.opt_ocr)

        opts_layout.addStretch()
        scroll.setWidget(opts_container)
        layout.addWidget(scroll, stretch=2)

        # ── Resultado inline ─────────────────────────────────────────
        self.lbl_result = QLabel("")
        self.lbl_result.setStyleSheet("font-size:12px; font-weight:600; padding:4px;")
        self.lbl_result.setWordWrap(True)
        self.lbl_result.setVisible(False)
        layout.addWidget(self.lbl_result)

        # ── Barra de progreso ─────────────────────────────────────────
        self.pbar = QProgressBar()
        self.pbar.setValue(0)
        self.pbar.setVisible(False)
        layout.addWidget(self.pbar)

        # ── Botones de acción ─────────────────────────────────────────
        btn_row2 = QHBoxLayout()
        self.btn_open_output = QPushButton("📂 Abrir carpeta")
        self.btn_open_output.setObjectName("ghostBtn")
        self.btn_open_output.setVisible(False)
        self.btn_open_output.clicked.connect(self._open_output_folder)
        btn_row2.addWidget(self.btn_open_output)

        self.btn_convert = QPushButton("🚀  CONVERTIR")
        self.btn_convert.setObjectName("convertBtn")
        self.btn_convert.setEnabled(False)
        self.btn_convert.clicked.connect(self._start_conversion)
        btn_row2.addWidget(self.btn_convert, stretch=1)
        layout.addLayout(btn_row2)

        # ── Informe técnico (constancia con SHA-256) ─────────────────
        self.informe_section = InformeSection()
        layout.addWidget(self.informe_section)

        return widget

    # ──────────────────────────────────────────────────────────────────
    # Drag & Drop
    # ──────────────────────────────────────────────────────────────────

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        files = []
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if os.path.isfile(path):
                files.append(path)
            elif os.path.isdir(path):
                for root, _, fnames in os.walk(path):
                    for fname in fnames:
                        files.append(os.path.join(root, fname))
        self._add_files_list(files)

    # ──────────────────────────────────────────────────────────────────
    # Gestión de archivos
    # ──────────────────────────────────────────────────────────────────

    def _add_files_dialog(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Seleccionar archivos", "", "Todos los archivos (*.*)"
        )
        self._add_files_list(files)

    def _add_folder_dialog(self):
        folder = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta")
        if folder:
            files = []
            for f in os.listdir(folder):
                fp = os.path.join(folder, f)
                if os.path.isfile(fp):
                    files.append(fp)
            self._add_files_list(files)

    def _add_files_list(self, paths: list):
        try:
            from core.config_manager import config
            priority_mb = config.get("priority_threshold_mb", 5)
        except Exception:
            priority_mb = 5

        for path in paths:
            if path in self.selected_files:
                continue
            if not os.path.isfile(path):
                continue

            self.selected_files.append(path)

            size_mb = os.path.getsize(path) / (1024 * 1024) if os.path.exists(path) else 0
            is_priority = size_mb < priority_mb

            card = FileCard(path)
            card.remove_requested.connect(self._remove_file)
            item = QListWidgetItem(self.file_list)
            item.setSizeHint(QSize(0, 40))
            self.file_list.addItem(item)
            self.file_list.setItemWidget(item, card)
            self._file_cards[path] = (card, item)

            if is_priority and size_mb > 0:
                card.set_status("priority", "⚡ Este archivo es pequeño y se procesará primero.")

            if not self.output_dir:
                self.lbl_out_path.setText(carpeta_destino(path))

        self._cerrar_informe_anterior()
        self._check_mixed_types()
        self._refresh_formats()
        self._update_convert_btn()
        self.status_bar.update_files(len(self.selected_files))

    def _cerrar_informe_anterior(self):
        """Guarda el informe de la tanda anterior mientras se arma la que sigue.

        Habla de archivos que ya no están en la cola, y encima es un cuadro
        alto que deja la grilla de formatos en una ranura de tres renglones.
        No se pierde: queda guardado en la carpeta de salida y en la solapa
        de constancias del panel de log.
        """
        if self.informe_section.isVisible():
            self.informe_section.setVisible(False)
            self.lbl_result.setVisible(False)

    def _remove_file(self, src_path: str):
        """Elimina un archivo de la cola."""
        if src_path in self.selected_files:
            self.selected_files.remove(src_path)
        if src_path in self._file_cards:
            card, item = self._file_cards.pop(src_path)
            row = self.file_list.row(item)
            self.file_list.takeItem(row)
        # El destino que se muestra sale de los archivos de la cola: si el
        # que se sacó era el único, no puede seguir diciendo su carpeta.
        if not self.output_dir:
            self.lbl_out_path.setText(
                carpeta_destino(self.selected_files[0])
                if self.selected_files else etiqueta_destino(""))
        self._cerrar_informe_anterior()
        self._check_mixed_types()
        self._refresh_formats()
        self._update_convert_btn()
        self.status_bar.update_files(len(self.selected_files))

    def _check_mixed_types(self):
        """Muestra aviso y CategoryTabBar si hay archivos de categorías distintas."""
        if not self.selected_files:
            self.warn_mixed.setVisible(False)
            self.category_tab_bar.setVisible(False)
            return

        cats: dict = {}
        for f in self.selected_files:
            ext = os.path.splitext(f)[1].lstrip(".").lower()
            cat = get_file_category(ext)
            cats[cat] = cats.get(cat, 0) + 1

        mixed = len(cats) > 1
        self.warn_mixed.setVisible(mixed)
        self.category_tab_bar.set_categories(cats if mixed else {})
        if not mixed:
            # Sin categorías mixtas: asegurar que todos los ítems estén visibles
            for i in range(self.file_list.count()):
                self.file_list.item(i).setHidden(False)

    def _on_category_filter(self, cat: str):
        """Muestra solo las tarjetas de la categoría elegida (archivos mixtos)."""
        for src_path, (card, item) in self._file_cards.items():
            ext = os.path.splitext(src_path)[1].lstrip(".").lower()
            item.setHidden(get_file_category(ext) != cat)

    def _refresh_incompat_marks(self):
        """Marca con ⛔ los archivos que no pueden llegar al formato elegido."""
        fmt = self.format_grid.get_selected()
        for src_path, (card, _item) in self._file_cards.items():
            ext = os.path.splitext(src_path)[1].lstrip(".").lower()
            if not fmt:
                if card.status == "excluded":
                    card.set_status("pending")
                    card.name_lbl.setStyleSheet("font-size:12px;")
                continue
            if graph.find_path(ext, fmt):
                if card.status == "excluded":
                    card.set_status("pending")
                    card.name_lbl.setStyleSheet("font-size:12px;")
            else:
                card.mark_excluded("Este archivo no se puede convertir al formato elegido.")

    def _do_panic(self):
        """Para todo y limpia la cola."""
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(3000)
        self.selected_files.clear()
        self.file_list.clear()
        self._file_cards.clear()
        self.output_dir = ""
        self.lbl_out_path.setText(etiqueta_destino(""))
        self.pbar.setValue(0)
        self.pbar.setVisible(False)
        self.lbl_result.setVisible(False)
        self.btn_convert.setEnabled(False)
        self.btn_open_output.setVisible(False)
        self.warn_mixed.setVisible(False)
        self.category_tab_bar.setVisible(False)
        self.status_bar.update_files(0)
        # El informe de la tanda anterior también se va. Es un cuadro de texto
        # alto (190 px de mínimo) y, si queda prendido, le come el lugar a la
        # grilla de formatos: al vaciar la cola para empezar de nuevo, elegir
        # el formato pasaba a ser una ranura de tres renglones. Además ya está
        # guardado en la carpeta de salida y en la solapa de constancias.
        self.informe_section.setVisible(False)
        self.lbl_route.setText("")

        # Limpiar TEMP_DIR
        try:
            from core.paths import TEMP_DIR
            for f in os.listdir(TEMP_DIR):
                fp = os.path.join(TEMP_DIR, f)
                try:
                    if os.path.isfile(fp):
                        os.unlink(fp)
                    elif os.path.isdir(fp):
                        shutil.rmtree(fp)
                except Exception:
                    pass
        except Exception:
            pass

        self._refresh_formats()

    def _set_output_dir(self):
        default = self.output_dir or os.path.expanduser("~")
        d = QFileDialog.getExistingDirectory(self, "Carpeta de destino", default)
        if d:
            self.output_dir = d
            self.lbl_out_path.setText(d)

    # ──────────────────────────────────────────────────────────────────
    # Gestión de formatos
    # ──────────────────────────────────────────────────────────────────

    def _refresh_formats(self):
        """Actualiza el FormatGrid según los archivos cargados."""
        if not self.selected_files:
            src_exts = []
            all_targets = []
        else:
            src_exts = list({
                os.path.splitext(f)[1].lstrip(".").lower()
                for f in self.selected_files
            })
            sets = [set(graph.all_targets(e)) for e in src_exts]
            all_targets = sorted(set.union(*sets)) if sets else []

            # OCR → PDF buscable: si hay Tesseract y el origen es PDF o imagen,
            # ofrecer "pdf" como destino aunque el grafo no tenga una arista
            # directa (p. ej. pdf→pdf, que el OCR resuelve conservando formato).
            try:
                from motors.motor_ocr import OcrMotor
                _ocr_srcs = {"pdf", "png", "jpg", "jpeg", "tiff", "tif", "bmp", "webp"}
                if (OcrMotor.is_available()
                        and any(e in _ocr_srcs for e in src_exts)
                        and "pdf" not in all_targets):
                    all_targets = sorted(all_targets + ["pdf"])
            except Exception:
                pass

        self.format_grid.update_formats(src_exts, all_targets)
        fmt = self.format_grid.get_selected()
        self._show_route_for(fmt)
        self._update_option_panels(fmt)
        self._refresh_incompat_marks()
        self._update_convert_btn()

    def _on_format_selected(self, fmt: str):
        """Disparado cuando el usuario elige un botón en FormatGrid."""
        self.status_bar.update_format(fmt)
        self._show_route_for(fmt)
        self._update_option_panels(fmt)
        self._refresh_incompat_marks()
        self._update_convert_btn()

    def _on_format_cleared(self):
        self.lbl_route.setText("")
        self.status_bar.update_format("")
        self._refresh_incompat_marks()
        self._update_convert_btn()

    def _show_route_for(self, fmt: str):
        """Muestra la ruta de conversión para el formato seleccionado."""
        if not fmt or not self.selected_files:
            self.lbl_route.setText("")
            return
        src_ext = os.path.splitext(self.selected_files[0])[1].lstrip(".").lower()
        if src_ext == fmt == "pdf":
            self.lbl_route.setText(
                "<span style='color:#10b981'>✓ OCR → PDF buscable</span> "
                "<span style='color:#94a3b8'>(conserva el formato)</span>"
            )
            return
        path = graph.find_path(src_ext, fmt)
        if path:
            direct = len(path) == 2
            route_str = " → ".join(p.upper() for p in path)
            tag = "directo" if direct else "en cadena"
            self.lbl_route.setText(
                f"<span style='color:#10b981'>✓ {route_str}</span> "
                f"<span style='color:#94a3b8'>({tag})</span>"
            )
        else:
            self.lbl_route.setText(
                "<span style='color:#ef4444'>✗ Sin ruta disponible</span>"
            )

    def _update_option_panels(self, fmt: str):
        """Muestra/oculta opciones según el tipo de archivo y formato."""
        if not self.selected_files:
            self.opt_audio.setVisible(False)
            self.opt_subtitle.setVisible(False)
            self.opt_ocr.setVisible(False)
            return

        cats = set()
        for f in self.selected_files:
            ext = os.path.splitext(f)[1].lstrip(".").lower()
            cats.add(get_file_category(ext))

        is_pdf_out = fmt == "pdf"
        self.opt_footer.set_pdf_only(is_pdf_out)
        self.opt_pagenums.set_pdf_only(is_pdf_out)

        self.opt_audio.setVisible("audio" in cats)
        self.opt_subtitle.setVisible("video" in cats)
        # El OCR solo sabe producir texto plano (TXT) o PDF buscable. Con DOCX
        # o HTML escribía el texto crudo dentro de un archivo con esa extensión,
        # es decir, un archivo roto.
        self.opt_ocr.setVisible(
            fmt in ("txt", "pdf") and
            any(c in cats for c in ("document", "image"))
        )

    def _update_convert_btn(self):
        has_files = bool(self.selected_files)
        fmt       = self.format_grid.get_selected()
        self.btn_convert.setEnabled(has_files and bool(fmt) and not self._converting)
        count = len(self.selected_files)
        if count > 0 and fmt:
            self.btn_convert.setText(
                f"Convertir {count} archivo{'s' if count != 1 else ''} → {fmt.upper()}"
            )
        else:
            self.btn_convert.setText("CONVERTIR")

    # ──────────────────────────────────────────────────────────────────
    # Conversión
    # ──────────────────────────────────────────────────────────────────

    def _start_conversion(self):
        if not self.selected_files:
            return

        dst_ext = self.format_grid.get_selected()
        if not dst_ext:
            return
        selected_fmts = [dst_ext]

        try:
            from core.config_manager import config
            strip_meta   = config.get("strip_metadata", True)
            marcar_pags  = config.get("page_markers", True)
            priority_mb  = config.get("priority_threshold_mb", 5)
            max_parallel = config.get("max_parallel_conversions", 2)
        except Exception:
            strip_meta   = True
            marcar_pags  = True
            priority_mb  = 5
            max_parallel = 2

        out_base = self.output_dir or ""
        ocr_cfg  = self.opt_ocr.get_config() if self.opt_ocr.isVisible() else None
        use_ocr  = ocr_cfg is not None
        jobs = []
        skipped = 0
        for src in self.selected_files:
            # Saltear archivos incompatibles con el formato elegido (ya marcados ⛔)
            src_ext = os.path.splitext(src)[1].lstrip(".").lower()
            # OCR → PDF buscable resuelve pdf→pdf (mismo origen y destino), que
            # el grafo no contempla; sin OCR ese caso no tiene sentido.
            ocr_pdf = use_ocr and dst_ext == "pdf"
            if not graph.find_path(src_ext, dst_ext) and not ocr_pdf:
                skipped += 1
                continue
            if src_ext == dst_ext and not ocr_pdf:
                skipped += 1
                continue
            stem    = os.path.splitext(os.path.basename(src))[0]
            out_dir = out_base if out_base else carpeta_destino(src)
            size_mb = os.path.getsize(src) / (1024 * 1024) if os.path.exists(src) else 0

            for dst_ext in selected_fmts:
                dst = os.path.join(out_dir, f"{stem}.{dst_ext}")
                jobs.append(ConversionJob(
                    src_path       = src,
                    dst_path       = dst,
                    dst_ext        = dst_ext,
                    audio_filter   = self.opt_audio.get_config(),
                    subtitle       = self.opt_subtitle.get_config(),
                    watermark      = self.opt_watermark.get_config(),
                    footer         = self.opt_footer.get_config(),
                    page_numbers   = self.opt_pagenums.get_config(),
                    strip_metadata = strip_meta and self.opt_metadata.is_enabled(),
                    marcar_paginas = marcar_pags and self.opt_paginas.is_enabled(),
                    use_ocr        = use_ocr,
                    ocr_language   = (ocr_cfg or {}).get("language", "Español"),
                    ocr_grayscale  = (ocr_cfg or {}).get("grayscale", True),
                    priority       = size_mb < priority_mb,
                ))

        if not jobs:
            QMessageBox.information(
                self, "Nada para convertir",
                "Ninguno de los archivos seleccionados se puede convertir "
                f"al formato {dst_ext.upper()}."
            )
            return

        self._skipped_count = skipped
        self._last_dst_ext  = dst_ext
        self._informe_rows  = []   # [(input_info, output_info), ...] de jobs OK
        self._converting = True
        self.btn_convert.setEnabled(False)
        self.pbar.setValue(0)
        self.pbar.setVisible(True)
        self.lbl_result.setVisible(False)
        self.btn_open_output.setVisible(False)
        self.informe_section.setVisible(False)

        # Resetear estados de cards (sin tocar los marcados ⛔ incompatibles)
        for _path, (card, _) in self._file_cards.items():
            if card.status != "excluded":
                card.set_status("pending")

        # Crear directorio de salida
        if jobs:
            first_out_dir = os.path.dirname(jobs[0].dst_path)
            os.makedirs(first_out_dir, exist_ok=True)

        # Inicializar log viewer si está disponible
        try:
            if self._log_panel:
                self._log_panel.clear_entries()
        except Exception:
            pass

        self.worker = ConversionWorker(jobs, max_parallel)
        self.worker.progress.connect(self._on_progress)
        self.worker.progress_value.connect(self.pbar.setValue)
        self.worker.job_started.connect(self._on_job_started)
        self.worker.job_done.connect(self._on_job_done)
        self.worker.finished.connect(self._on_finished)
        self.worker.fatal_error.connect(self._on_fatal_error)
        self.worker.start()

    def _on_progress(self, msg: str):
        try:
            if self._log_panel:
                self._log_panel.append_log(msg)
        except Exception:
            pass

    def _on_job_started(self, src_path: str):
        if src_path in self._file_cards:
            self._file_cards[src_path][0].set_status("running")

    def _on_job_done(self, src_path: str, ok: bool, log_entry: dict):
        if src_path in self._file_cards:
            self._file_cards[src_path][0].set_status("ok" if ok else "error")
        try:
            if self._log_panel and log_entry:
                self._log_panel.add_entry(log_entry)
        except Exception:
            pass
        # Acumular para el informe técnico (solo conversiones exitosas)
        if ok and log_entry and log_entry.get("input") and log_entry.get("output"):
            if not hasattr(self, "_informe_rows"):
                self._informe_rows = []
            self._informe_rows.append((log_entry["input"], log_entry["output"]))

    def _on_finished(self, success: int, errors: int):
        self._converting = False
        self.pbar.setValue(100)
        self._update_convert_btn()

        out_folder = self.output_dir
        if not out_folder and self.selected_files:
            out_folder = carpeta_destino(self.selected_files[0])

        msg = f"✅ {success} convertido{'s' if success != 1 else ''}"
        if errors:
            msg += f"  |  ❌ {errors} error{'es' if errors != 1 else ''}"
        skipped = getattr(self, "_skipped_count", 0)
        if skipped:
            msg += f"  |  ⛔ {skipped} incompatible{'s' if skipped != 1 else ''}"
        if out_folder:
            msg += f"  |  📁 {out_folder}"
        self.lbl_result.setText(msg)
        self.lbl_result.setVisible(True)
        self.btn_open_output.setVisible(bool(out_folder and os.path.isdir(out_folder)))
        self._last_out_folder = out_folder

        # ── Informe técnico: generar, mostrar y auto-guardar ──────────
        self._build_and_show_informe(out_folder)

        # ── Avisos de los motores ────────────────────────────────────
        self._mostrar_avisos()

    def _mostrar_avisos(self):
        """Cartel con lo que el motor decidió omitir o cambiar.

        Un archivo que salió "Exitoso" igual pudo perder algo por el camino
        (el texto vertical del margen que pdf2docx no sabe girar). Eso no
        puede quedar solo en el log técnico, que está en el panel lateral y
        se llena de renglones de avance: va en un cartel, una vez, al final.
        """
        avisos = list(getattr(self.worker, "_avisos", []))
        if not avisos:
            return
        self.lbl_result.setText(
            self.lbl_result.text()
            + f"  |  ⚠ {len(avisos)} aviso{'s' if len(avisos) != 1 else ''}"
        )
        cuerpo = "\n\n".join(f"• {a}" for a in avisos[:12])
        if len(avisos) > 12:
            cuerpo += f"\n\n(y {len(avisos) - 12} más, en el log técnico)"
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Avisos de la conversión")
        box.setText("La conversión terminó, pero hay algo para tener en cuenta:")
        box.setInformativeText(cuerpo)
        box.exec()

    def _build_and_show_informe(self, out_folder: str):
        """Construye el informe técnico de la sesión, lo muestra y lo guarda .txt."""
        rows = getattr(self, "_informe_rows", [])
        if not rows:
            return
        try:
            from core.informe import build_informe, save_informe

            def _to_info(d: dict) -> dict:
                return {
                    "filename": d.get("filename", ""),
                    "sha256":   d.get("sha256", ""),
                    "size_mb":  (d.get("size_bytes", 0) or 0) / (1024 * 1024),
                }

            originals = [_to_info(i) for i, _o in rows]
            results   = [_to_info(o) for _i, o in rows]
            fmt = getattr(self, "_last_dst_ext", "") or ""
            texto = build_informe(
                accion=f"convertir al formato {fmt.upper()}" if fmt else "convertir",
                originals=originals,
                results=results,
            )

            saved_path = ""
            if out_folder:
                try:
                    saved_path = save_informe(texto, out_folder, prefix="Informe_conversion")
                except Exception:
                    saved_path = ""

            if saved_path:
                texto += f"\n[Informe guardado automáticamente en: {saved_path}]\n"

            self.informe_section.set_informe(texto, out_folder)
            if saved_path:
                self.lbl_result.setText(
                    self.lbl_result.text() + f"  |  📋 Informe: {os.path.basename(saved_path)}"
                )
        except Exception:
            pass

    def _on_fatal_error(self, msg: str):
        self._converting = False
        self._update_convert_btn()
        self.pbar.setVisible(False)
        try:
            if self._log_panel:
                self._log_panel.append_log(f"❌ ERROR FATAL: {msg}")
        except Exception:
            pass

    def _open_output_folder(self):
        folder = getattr(self, '_last_out_folder', self.output_dir)
        if folder and os.path.isdir(folder):
            try:
                if platform.system() == "Windows":
                    os.startfile(folder)
                elif platform.system() == "Darwin":
                    subprocess.run(["open", folder])
                else:
                    subprocess.run(["xdg-open", folder])
            except Exception:
                pass

    # ──────────────────────────────────────────────────────────────────
    # Tema
    # ──────────────────────────────────────────────────────────────────

    def _toggle_theme(self):
        app = QApplication.instance()
        from ui.theme import ThemeManager
        new_mode = ThemeManager.toggle(app)
        self.theme_btn.set_mode(new_mode)
        self.status_bar.update_theme(new_mode)
        self.format_grid.set_dark(new_mode == "dark")

    # ──────────────────────────────────────────────────────────────────
    # Cierre
    # ──────────────────────────────────────────────────────────────────

    def closeEvent(self, event):
        # Los módulos con trabajo a medio hacer (una transcripción) preguntan antes y pueden frenar la salida.
        for panel in self._paneles_con_trabajo():
            try:
                if not panel.puede_cerrar():
                    event.ignore()
                    return
            except Exception:
                pass

        if self._converting and self.worker and self.worker.isRunning():
            reply = QMessageBox.question(
                self, "¿Salir?",
                "Hay una conversión en curso.\n¿Querés salir de todas formas?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                event.ignore()
                return

        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(3000)

        # Limpiar temporales
        try:
            from core.paths import TEMP_DIR
            shutil.rmtree(TEMP_DIR, ignore_errors=True)
            os.makedirs(TEMP_DIR, exist_ok=True)
        except Exception:
            pass

        # Guardar config
        try:
            from core.config_manager import config
            config.save()
        except Exception:
            pass

        # Finalizar logger
        try:
            from core.logger import logger
            logger.finish_session()
        except Exception:
            pass

        event.accept()
