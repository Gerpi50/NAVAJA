"""
ui/format_grid.py — Widget de selección de formato de salida.
Grilla de botones agrupados por categoría con filtro de búsqueda.
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QScrollArea, QPushButton, QComboBox,
    QFrame, QButtonGroup, QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QColor

# ── Configuración de categorías ───────────────────────────────────────────────

CAT_CONFIG = {
    # key: (icon, label, bg_light, border_light, fg_light,
    #                    bg_dark,  border_dark,  fg_dark)
    "image":    ("🖼️",  "Imagen",    "#fef3c7", "#f59e0b", "#92400e",
                                    "#78350f", "#d97706", "#fde68a"),
    "audio":    ("🎵",  "Audio",     "#ede9fe", "#8b5cf6", "#4c1d95",
                                    "#4c1d95", "#a78bfa", "#ede9fe"),
    "video":    ("🎬",  "Video",     "#fee2e2", "#ef4444", "#991b1b",
                                    "#7f1d1d", "#f87171", "#fee2e2"),
    "document": ("📄",  "Documento", "#dbeafe", "#3b82f6", "#1e3a8a",
                                    "#1e3a8a", "#60a5fa", "#dbeafe"),
    "data":     ("📊",  "Datos",     "#d1fae5", "#10b981", "#064e3b",
                                    "#064e3b", "#34d399", "#d1fae5"),
    "email":    ("📧",  "Email",     "#fce7f3", "#ec4899", "#831843",
                                    "#831843", "#f472b6", "#fce7f3"),
    "web":      ("🌐",  "Web",       "#cffafe", "#06b6d4", "#164e63",
                                    "#164e63", "#22d3ee", "#cffafe"),
    "other":    ("📎",  "Otros",     "#f1f5f9", "#94a3b8", "#334155",
                                    "#334155", "#94a3b8", "#f1f5f9"),
}

CAT_ORDER = ["image", "audio", "video", "document", "data", "email", "web", "other"]

FORMAT_TOOLTIPS = {
    "pdf":     "Documento portable. Ideal para compartir e imprimir.",
    "mp3":     "Audio comprimido. Compatible con todos los reproductores.",
    "webp":    "Imagen web moderna. Más liviana que JPG con igual calidad.",
    "xlsx":    "Planilla de Excel.",
    "xls":     "Planilla de Excel (formato antiguo).",
    "ods":     "Planilla OpenDocument.",
    "epub":    "Libro digital para e-readers.",
    "json":    "Formato de datos para sistemas y programas.",
    "csv":     "Tabla de datos en texto plano. Abrila con Excel.",
    "tsv":     "Tabla separada por tabulaciones.",
    "gif":     "Imagen animada.",
    "opus":    "Audio moderno y comprimido. Ideal para voz.",
    "txt":     "Texto plano. Se abre con cualquier programa.",
    "docx":    "Documento Word editable.",
    "doc":     "Documento Word (formato antiguo).",
    "odt":     "Documento OpenDocument.",
    "rtf":     "Texto enriquecido portable.",
    "mp4":     "Video estándar. Compatible con todos los reproductores.",
    "jpg":     "Foto comprimida. Ideal para compartir.",
    "jpeg":    "Foto comprimida (igual que JPG).",
    "png":     "Imagen con fondo transparente. Alta calidad.",
    "wav":     "Audio sin comprimir. Alta calidad, archivo grande.",
    "flac":    "Audio sin pérdida de calidad y con compresión.",
    "ogg":     "Formato de audio libre y abierto.",
    "mkv":     "Video de alta calidad con múltiples pistas.",
    "avi":     "Video clásico de Windows.",
    "svg":     "Gráfico vectorial. No pierde calidad al agrandar.",
    "html":    "Página web. Se abre en cualquier navegador.",
    "xml":     "Formato de datos estructurados.",
    "yaml":    "Configuración en formato legible.",
    "toml":    "Configuración TOML.",
    "ico":     "Ícono de programa para Windows.",
    "icns":    "Ícono para macOS.",
    "mov":     "Video QuickTime.",
    "webm":    "Video web moderno.",
    "flv":     "Video Flash.",
    "wmv":     "Video Windows Media.",
    "3gp":     "Video para móviles.",
    "m4a":     "Audio AAC en contenedor MP4.",
    "m4b":     "Audiolibro en contenedor MP4.",
    "aac":     "Audio comprimido moderno.",
    "wma":     "Audio Windows Media.",
    "aiff":    "Audio sin comprimir (Mac/iOS).",
    "bmp":     "Imagen sin comprimir.",
    "tiff":    "Imagen de alta calidad para impresión.",
    "heic":    "Foto iPhone (alta eficiencia).",
    "avif":    "Imagen moderna de alta compresión.",
    "tga":     "Imagen Targa para diseño y juegos.",
    "pptx":    "Presentación PowerPoint.",
    "md":      "Texto Markdown.",
    "rst":     "ReStructuredText.",
    "tex":     "Documento LaTeX.",
    "parquet": "Datos en columnas (Big Data).",
    "hdf5":    "Datos científicos jerárquicos.",
    "msg":     "Correo Outlook.",
    "eml":     "Correo en formato estándar.",
    "mhtml":   "Página web completa en un archivo.",
    "htm":     "Página web (igual que HTML).",
    "psd":     "Archivo Photoshop.",
    "eps":     "Gráfico PostScript.",
    "dng":     "RAW digital negativo.",
    "ipynb":   "Jupyter Notebook.",
    "pages":   "Documento Pages (Mac).",
    "key":     "Presentación Keynote (Mac).",
    "numbers": "Planilla Numbers (Mac).",
    "wps":     "Documento WPS Office.",
    "au":      "Audio Sun/NeXT.",
    "amr":     "Audio para telefonía móvil.",
    "ac3":     "Audio Dolby Digital.",
    "ape":     "Audio Monkey's (sin pérdida).",
    "mka":     "Audio Matroska.",
    "caf":     "Audio Core Audio (Mac).",
    "ra":      "Audio RealAudio.",
    "dts":     "Audio DTS Surround.",
    "midi":    "Música MIDI (instrucciones musicales).",
    "m4v":     "Video iTunes.",
    "ts":      "Flujo de transporte MPEG.",
    "mpg":     "Video MPEG estándar.",
    "mpeg":    "Video MPEG (igual que MPG).",
    "ogv":     "Video Ogg.",
    "vob":     "Video DVD.",
}


class _FormatButton(QPushButton):
    """Botón de formato con indicador de conversión en cadena."""

    def __init__(self, fmt: str, is_chain: bool, cat_key: str, dark: bool = False):
        label = fmt.upper() + (" 🔗" if is_chain else "")
        super().__init__(label)
        self.fmt      = fmt
        self.cat_key  = cat_key
        self.is_chain = is_chain
        self.setCheckable(True)
        self.setFixedSize(80, 38)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        tip = FORMAT_TOOLTIPS.get(fmt, fmt.upper())
        if is_chain:
            tip += "\n🔗 Conversión en dos pasos (indirecta)"
        self.setToolTip(tip)

        self._dark = dark
        self._apply_style(False)

    def set_dark(self, dark: bool):
        self._dark = dark
        self._apply_style(self.isChecked())

    def _apply_style(self, checked: bool):
        cfg = CAT_CONFIG.get(self.cat_key, CAT_CONFIG["other"])
        if self._dark:
            bg, border, fg = cfg[5], cfg[6], cfg[7]
            bg_sel = _darken(bg, 0.7)
        else:
            bg, border, fg = cfg[2], cfg[3], cfg[4]
            bg_sel = _lighten_or_darken(bg)

        if checked:
            style = (
                f"QPushButton {{"
                f"  background:{bg_sel}; border:2px solid {border};"
                f"  color:{fg}; border-radius:6px;"
                f"  font-weight:700; font-size:11px;"
                f"}}"
            )
        else:
            style = (
                f"QPushButton {{"
                f"  background:{bg}; border:1px solid {border};"
                f"  color:{fg}; border-radius:6px;"
                f"  font-weight:600; font-size:11px;"
                f"}}"
                f"QPushButton:hover {{"
                f"  background:{bg_sel}; border:2px solid {border};"
                f"}}"
            )
        self.setStyleSheet(style)

    def nextCheckState(self):
        # Interceptar para actualizar estilo manualmente
        pass


def _lighten_or_darken(hex_color: str, factor: float = 0.85) -> str:
    """Oscurece ligeramente un color hex para el estado seleccionado."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    r = max(0, int(r * factor))
    g = max(0, int(g * factor))
    b = max(0, int(b * factor))
    return f"#{r:02x}{g:02x}{b:02x}"


def _darken(hex_color: str, factor: float = 0.6) -> str:
    return _lighten_or_darken(hex_color, factor)


# ── Widget principal ──────────────────────────────────────────────────────────

class FormatGrid(QWidget):
    """
    Selector de formato de salida con botones agrupados por categoría.
    Radio behavior: solo un formato seleccionado a la vez.
    """

    format_selected = pyqtSignal(str)   # extensión elegida, ej. "mp4"
    format_cleared  = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._src_exts:   list  = []
        self._all_fmts:   dict  = {}
        self._buttons:    dict  = {}
        self._btn_group           = QButtonGroup(self)
        self._btn_group.setExclusive(True)
        self._dark = False
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._build_skeleton()

    # ── Construcción de la estructura fija ───────────────────────────────────

    def _build_skeleton(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Selector de formato: se puede desplegar la lista o escribir.
        # Antes era sólo una caja de texto para filtrar, y el que no se sabía
        # de memoria la extensión tenía que ir a buscarla entre los botones.
        self.search = QComboBox()
        self.search.setEditable(True)
        self.search.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.search.setMaxVisibleItems(18)
        self.search.lineEdit().setPlaceholderText(
            "Elegí el formato de la lista o escribilo (ej: mp3, pdf)")
        self.search.setToolTip(
            "Desplegá la lista para ver todos los formatos disponibles, "
            "o escribí para filtrarlos.")
        # textEdited y no textChanged: así el filtro sólo corre cuando escribe
        # el usuario, y no cuando el programa cambia el texto solo.
        self.search.lineEdit().textEdited.connect(self._apply_filter)
        self.search.lineEdit().returnPressed.connect(self._elegir_escrito)
        self.search.activated.connect(self._elegir_del_desplegable)
        layout.addWidget(self.search)

        # Área de scroll con los grupos — sin altura fija, crece con el contenedor
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        layout.addWidget(self.scroll, stretch=1)

        # Contenedor interior (se reconstruye en _rebuild)
        self._content = QWidget()
        self.scroll.setWidget(self._content)
        self._show_empty()

    def _show_empty(self):
        """Muestra el estado vacío sin archivos."""
        self._clear_content()
        vbox = QVBoxLayout(self._content)
        vbox.setContentsMargins(8, 20, 8, 20)
        lbl = QLabel("Arrastrá archivos para ver\nlos formatos disponibles")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("color:#94a3b8; font-size:12px;")
        vbox.addWidget(lbl)

    def _clear_content(self):
        """Destruye todos los widgets dentro del contenedor de scroll."""
        old = self._content.layout()
        if old:
            while old.count():
                item = old.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            QWidget().setLayout(old)   # transfiere el layout viejo para destruirlo
        # Limpiar grupos de botones
        for b in list(self._buttons.values()):
            self._btn_group.removeButton(b)
        self._buttons.clear()

    # ── API pública ───────────────────────────────────────────────────────────

    def update_formats(self, src_exts: list, targets: list):
        """
        Reconstruye la grilla con los formatos de destino alcanzables.
        src_exts: extensiones de los archivos fuente (para detectar cadenas).
        targets:  formatos de destino posibles.
        """
        self._src_exts = src_exts

        if not targets:
            self._all_fmts = {}
            self._show_empty()
            return

        # Agrupar targets por categoría de destino
        from ui.widgets import get_file_category
        grouped: dict = {k: [] for k in CAT_ORDER}
        for fmt in targets:
            cat = get_file_category(fmt)
            bucket = cat if cat in grouped else "other"
            grouped[bucket].append(fmt)

        # Conservar solo categorías con al menos un formato
        self._all_fmts = {k: sorted(v) for k, v in grouped.items() if v}

        # Recordar selección actual si sigue siendo válida
        prev = self.get_selected()
        self._rebuild(prev)

    def get_selected(self) -> str:
        """Devuelve la extensión seleccionada, o '' si nada está seleccionado."""
        btn = self._btn_group.checkedButton()
        if btn:
            return btn.fmt
        return ""

    def _limpiar_desplegable(self):
        combo = self.search
        combo.blockSignals(True)
        combo.setCurrentIndex(-1)
        combo.lineEdit().clear()
        combo.blockSignals(False)

    def clear_selection(self):
        self._limpiar_desplegable()
        checked = self._btn_group.checkedButton()
        if checked:
            self._btn_group.setExclusive(False)
            checked.setChecked(False)
            self._btn_group.setExclusive(True)
            checked._apply_style(False)
        self.format_cleared.emit()

    def set_dark(self, dark: bool):
        self._dark = dark
        for btn in self._buttons.values():
            btn.set_dark(dark)
            btn._apply_style(btn.isChecked())

    # ── Construcción de la grilla ─────────────────────────────────────────────

    def _rebuild(self, reselect: str = ""):
        self._clear_content()

        cats = [k for k in CAT_ORDER if k in self._all_fmts]
        n_cats = len(cats)

        outer = QVBoxLayout(self._content)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(8)

        if n_cats == 0:
            lbl = QLabel("Sin formatos disponibles para estos archivos.")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("color:#94a3b8; font-size:11px;")
            outer.addWidget(lbl)
            return

        # Todos los grupos apilados verticalmente (full width), separados por línea
        for idx, cat in enumerate(cats):
            if idx > 0:
                line = QFrame()
                line.setFrameShape(QFrame.Shape.HLine)
                line.setStyleSheet("color:#e2e8f0;")
                outer.addWidget(line)
            group_w = self._make_group(cat, self._all_fmts[cat])
            outer.addWidget(group_w)

        outer.addStretch()

        # Re-seleccionar si el formato previo sigue disponible
        if reselect and reselect in self._buttons:
            btn = self._buttons[reselect]
            self._btn_group.setExclusive(False)
            btn.setChecked(True)
            self._btn_group.setExclusive(True)
            btn._apply_style(True)

        # La lista del desplegable se rehace junto con la grilla
        self._llenar_desplegable()
        self._apply_filter(self.search.currentText()
                           if self.search.count() == 0 else "")

    def _make_group(self, cat_key: str, fmts: list) -> QFrame:
        """Crea un frame con encabezado + grilla de botones para una categoría."""
        cfg = CAT_CONFIG.get(cat_key, CAT_CONFIG["other"])
        icon, label = cfg[0], cfg[1]
        border_color = cfg[6] if self._dark else cfg[3]

        frame = QFrame()
        frame.setObjectName(f"fmtGroup_{cat_key}")
        frame.setStyleSheet(
            f"QFrame#{frame.objectName()} {{"
            f"  border:1px solid {border_color}; border-radius:8px;"
            f"  padding:4px;"
            f"}}"
        )

        vbox = QVBoxLayout(frame)
        vbox.setContentsMargins(8, 6, 8, 8)
        vbox.setSpacing(6)

        # Encabezado
        hdr = QLabel(f"{icon}  {label}")
        font = QFont()
        font.setBold(True)
        font.setPointSize(9)
        hdr.setFont(font)
        fg = cfg[7] if self._dark else cfg[4]
        hdr.setStyleSheet(f"color:{fg}; border:none;")
        vbox.addWidget(hdr)

        # Grilla de botones (3 columnas)
        grid = QGridLayout()
        grid.setSpacing(4)
        grid.setContentsMargins(0, 0, 0, 0)

        for idx, fmt in enumerate(fmts):
            is_chain = self._is_chain(fmt)
            btn = _FormatButton(fmt, is_chain, cat_key, self._dark)
            btn.clicked.connect(self._on_button_clicked)
            self._btn_group.addButton(btn)
            self._buttons[fmt] = btn
            row, col = divmod(idx, 5)
            grid.addWidget(btn, row, col)

        vbox.addLayout(grid)
        return frame

    def _llenar_desplegable(self):
        """Carga la lista del desplegable con los formatos disponibles."""
        from ui.widgets import get_file_category
        combo = self.search
        combo.blockSignals(True)
        texto_previo = combo.lineEdit().text()
        combo.clear()
        for cat in CAT_ORDER:
            fmts = self._all_fmts.get(cat) or []
            if not fmts:
                continue
            icono, etiqueta = CAT_CONFIG.get(cat, CAT_CONFIG["other"])[:2]
            for fmt in fmts:
                nombre = f"{icono}  {fmt.upper()}"
                ayuda = FORMAT_TOOLTIPS.get(fmt, "")
                if ayuda:
                    nombre += f"  —  {ayuda}"
                combo.addItem(nombre, fmt)
        combo.setCurrentIndex(-1)
        combo.lineEdit().setText(texto_previo)
        combo.blockSignals(False)

    def _elegir_del_desplegable(self, indice: int):
        """El usuario eligió un formato de la lista."""
        fmt = self.search.itemData(indice)
        if fmt:
            self.select_format(fmt)

    def _elegir_escrito(self):
        """Enter en la caja: si lo escrito es un formato, se selecciona."""
        texto = self.search.currentText().strip().lstrip(".").lower()
        if texto in self._buttons:
            self.select_format(texto)

    def select_format(self, fmt: str) -> bool:
        """Selecciona un formato por su extensión (como si se tocara el botón).

        Devuelve False si ese formato no está disponible para los archivos
        que hay en la cola.
        """
        btn = self._buttons.get(fmt)
        if btn is None:
            return False
        for b in self._buttons.values():
            if b.isChecked() and b is not btn:
                self._btn_group.setExclusive(False)
                b.setChecked(False)
                self._btn_group.setExclusive(True)
                b._apply_style(False)
        self._btn_group.setExclusive(False)
        btn.setChecked(True)
        self._btn_group.setExclusive(True)
        btn._apply_style(True)
        self._mostrar_en_desplegable(fmt)
        self._apply_filter("")
        self.format_selected.emit(fmt)
        return True

    def _mostrar_en_desplegable(self, fmt: str):
        """Deja escrito en la caja el formato elegido, sin disparar el filtro."""
        combo = self.search
        combo.blockSignals(True)
        for i in range(combo.count()):
            if combo.itemData(i) == fmt:
                combo.setCurrentIndex(i)
                break
        # En la caja queda sólo la extensión: el renglón completo del
        # desplegable, con el ícono y la explicación, no entra y se lee mal.
        combo.lineEdit().setText(fmt.upper())
        combo.blockSignals(False)

    def _is_chain(self, dst_fmt: str) -> bool:
        """True si alguna fuente necesita conversión en cadena para llegar a dst_fmt."""
        if not self._src_exts:
            return False
        try:
            from core.graph import graph
            for src in self._src_exts:
                path = graph.find_path(src, dst_fmt)
                if path and len(path) > 2:
                    return True
        except Exception:
            pass
        return False

    # ── Eventos ───────────────────────────────────────────────────────────────

    def _on_button_clicked(self):
        btn = self.sender()
        if not isinstance(btn, _FormatButton):
            return

        was_checked = btn.isChecked()

        # Desmarcar todos visualmente
        for b in self._buttons.values():
            if b.isChecked() and b is not btn:
                self._btn_group.setExclusive(False)
                b.setChecked(False)
                self._btn_group.setExclusive(True)
                b._apply_style(False)

        if was_checked:
            # Era el botón activo → se estaba "deseleccionando" (toggle off)
            self._btn_group.setExclusive(False)
            btn.setChecked(False)
            self._btn_group.setExclusive(True)
            btn._apply_style(False)
            self._limpiar_desplegable()
            self.format_cleared.emit()
        else:
            btn.setChecked(True)
            btn._apply_style(True)
            self._mostrar_en_desplegable(btn.fmt)
            self.format_selected.emit(btn.fmt)

    def _apply_filter(self, text: str):
        """Muestra/oculta botones y grupos según el texto de búsqueda."""
        q = text.strip().lower()
        for fmt, btn in self._buttons.items():
            btn.setVisible(not q or q in fmt.lower())

        # Ocultar grupos donde todos los botones están ocultos
        for frame in self._content.findChildren(QFrame):
            name = frame.objectName()
            if not name.startswith("fmtGroup_"):
                continue
            btns_in_group = [
                b for f, b in self._buttons.items()
                if b.parent() is not None and self._cat_of(f) == name[9:]
            ]
            frame.setVisible(bool(not q) or any(b.isVisible() for b in btns_in_group))

    def _cat_of(self, fmt: str) -> str:
        from ui.widgets import get_file_category
        return get_file_category(fmt)
