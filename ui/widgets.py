"""
ui/widgets.py — Widgets reutilizables para la interfaz.
"""
import os
from typing import List

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QCheckBox, QRadioButton, QButtonGroup, QLineEdit,
    QSpinBox, QDoubleSpinBox, QComboBox, QColorDialog, QFrame,
    QSizePolicy, QApplication, QMessageBox,
)
from PyQt6.QtCore import (
    Qt, pyqtSignal, QSize, QMimeData, QTimer,
    QPropertyAnimation, QEasingCurve,
)
from PyQt6.QtGui import QFont, QColor, QDragEnterEvent, QDropEvent, QPixmap

try:
    import qtawesome as qta
    _QTA = True
except ImportError:
    _QTA = False


def _icon(name: str, color: str = "#64748b", size: int = 16):
    if _QTA:
        try:
            return qta.icon(name, color=color)
        except Exception:
            pass
    from PyQt6.QtGui import QIcon
    return QIcon()


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

CATEGORY_COLORS = {
    "image":    "#f59e0b", "document": "#3b82f6",
    "audio":    "#8b5cf6", "video":    "#ef4444",
    "data":     "#10b981", "email":    "#ec4899",
    "web":      "#06b6d4", "other":    "#94a3b8",
}

FORMAT_CATEGORIES = {
    "jpg":"image","jpeg":"image","png":"image","webp":"image","bmp":"image",
    "tiff":"image","tif":"image","gif":"image","svg":"image","heic":"image",
    "heif":"image","avif":"image","ico":"image","icns":"image","tga":"image",
    "jfif":"image","psd":"image","eps":"image","dng":"image",
    "pdf":"document","docx":"document","doc":"document","odt":"document",
    "rtf":"document","txt":"document","pages":"document","wps":"document",
    "epub":"document","md":"document","rst":"document","tex":"document",
    "mp3":"audio","wav":"audio","flac":"audio","aac":"audio","ogg":"audio",
    "opus":"audio","m4a":"audio","wma":"audio","aiff":"audio","au":"audio",
    "mp4":"video","mkv":"video","avi":"video","mov":"video","webm":"video",
    "flv":"video","wmv":"video","m4v":"video","3gp":"video","ts":"video",
    "mpg":"video","mpeg":"video","ogv":"video",
    "json":"data","xml":"data","yaml":"data","yml":"data","csv":"data",
    "tsv":"data","xlsx":"data","xls":"data","ods":"data","parquet":"data",
    # Audio y video que faltaban: sin esto caían en "Otros" (gris) aunque
    # la app ya los convierte.
    "m4b":"audio","m4r":"audio","amr":"audio","ac3":"audio","ape":"audio",
    "mka":"audio","caf":"audio","ra":"audio","dts":"audio","aif":"audio",
    "vob":"video","f4v":"video",
    # Presentaciones y ebooks: van con los documentos.
    "ppt":"document","pptx":"document","odp":"document","key":"document",
    "mobi":"document","azw3":"document","abw":"document","ipynb":"document",
    "hdf5":"data","h5":"data","toml":"data","numbers":"data",
    "msg":"email","eml":"email","emlx":"email",
    "html":"web","htm":"web","xhtml":"web","mhtml":"web","css":"web",
}

STATUS_ICONS = {
    "pending":    "⏳",
    "running":    "⚙️",
    "ok":         "✅",
    "error":      "❌",
    "excluded":   "⛔",
    "priority":   "⚡",
}


def cat_color(ext: str) -> str:
    cat = FORMAT_CATEGORIES.get(ext.lower(), "other")
    return CATEGORY_COLORS.get(cat, "#94a3b8")


def get_file_category(ext: str) -> str:
    return FORMAT_CATEGORIES.get(ext.lower(), "other")


# ─────────────────────────────────────────────────────────────────────────────
# DropZone
# ─────────────────────────────────────────────────────────────────────────────

class DropZone(QWidget):
    """Zona de drag-and-drop de archivos y carpetas."""
    files_dropped = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumHeight(100)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setToolTip(
            "Podés arrastrar uno o varios archivos, o una carpeta entera con archivos mixtos."
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_lbl = QLabel("📂")
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet("font-size:48px; border:none; background:transparent;")
        layout.addWidget(icon_lbl)

        self.lbl = QLabel("Arrastrá archivos o carpetas aquí\no usá los botones de abajo")
        self.lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl.setStyleSheet("color:#94a3b8; font-size:12px; border:none; background:transparent;")
        layout.addWidget(self.lbl)

        self._update_style(False)

    def _update_style(self, active: bool):
        border_color = "#3b82f6" if active else "#e2e8f0"
        bg = "#eff6ff" if active else "#f8fafc"
        self.setStyleSheet(
            f"DropZone {{ border: 2px dashed {border_color}; border-radius: 10px;"
            f" background: {bg}; }}"
        )

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._update_style(True)

    def dragLeaveEvent(self, event):
        self._update_style(False)

    def dropEvent(self, event: QDropEvent):
        self._update_style(False)
        files = []
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if os.path.isfile(path):
                files.append(path)
            elif os.path.isdir(path):
                for root, _, fnames in os.walk(path):
                    for fname in fnames:
                        files.append(os.path.join(root, fname))
        if files:
            self.files_dropped.emit(files)


# ─────────────────────────────────────────────────────────────────────────────
# FileCard
# ─────────────────────────────────────────────────────────────────────────────

class FileCard(QWidget):
    """Tarjeta de archivo con estado visual."""
    remove_requested = pyqtSignal(str)

    _SPIN_FRAMES = ["⣾", "⣽", "⣻", "⢿", "⡿", "⣟", "⣯", "⣷"]

    def __init__(self, src_path: str, parent=None):
        super().__init__(parent)
        self.src_path = src_path
        self.status = "pending"
        self._spin_idx = 0
        self._spin_timer = QTimer(self)
        self._spin_timer.setInterval(120)
        self._spin_timer.timeout.connect(self._advance_spin)

        # Thumbnail hover state
        self._thumb_timer = QTimer(self)
        self._thumb_timer.setSingleShot(True)
        self._thumb_timer.setInterval(400)
        self._thumb_timer.timeout.connect(self._show_thumbnail)
        self._thumb_popup = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(8)

        ext = os.path.splitext(src_path)[1].lstrip(".").lower()
        color = cat_color(ext)

        # Badge extensión
        self.badge = QLabel(ext.upper() if ext else "?")
        self.badge.setFixedSize(42, 22)
        self.badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.badge.setStyleSheet(
            f"background:{color}; color:white; border-radius:4px; "
            f"font-size:10px; font-weight:700;"
        )
        layout.addWidget(self.badge)

        # Nombre (truncado con tooltip)
        size_mb = os.path.getsize(src_path) / (1024 * 1024) if os.path.exists(src_path) else 0
        name = os.path.basename(src_path)
        self.name_lbl = QLabel()
        self.name_lbl.setMaximumWidth(180)
        self.name_lbl.setStyleSheet("font-size:12px;")
        self.name_lbl.setToolTip(src_path)
        # Elide text
        fm = self.name_lbl.fontMetrics()
        elided = fm.elidedText(name, Qt.TextElideMode.ElideRight, 180)
        self.name_lbl.setText(elided)
        layout.addWidget(self.name_lbl, stretch=1)

        # Tamaño
        size_str = f"{size_mb:.1f} MB" if size_mb >= 1 else f"{size_mb * 1024:.0f} KB"
        size_lbl = QLabel(size_str)
        size_lbl.setStyleSheet("font-size:10px; color:#94a3b8;")
        size_lbl.setFixedWidth(58)
        layout.addWidget(size_lbl)

        # Estado
        self.status_lbl = QLabel("⏳")
        self.status_lbl.setFixedWidth(24)
        layout.addWidget(self.status_lbl)

        # Botón eliminar
        self.btn_remove = QPushButton("✕")
        self.btn_remove.setObjectName("ghostBtn")
        self.btn_remove.setFixedSize(20, 20)
        self.btn_remove.setToolTip("Quitar de la cola")
        self.btn_remove.clicked.connect(lambda: self.remove_requested.emit(self.src_path))
        layout.addWidget(self.btn_remove)

        self.setMouseTracking(True)

    def _advance_spin(self):
        self._spin_idx = (self._spin_idx + 1) % len(self._SPIN_FRAMES)
        self.status_lbl.setText(self._SPIN_FRAMES[self._spin_idx])

    def set_status(self, status: str, tooltip: str = ""):
        self.status = status
        self._spin_timer.stop()
        if status == "running":
            self._spin_idx = 0
            self.status_lbl.setText(self._SPIN_FRAMES[0])
            self._spin_timer.start()
        else:
            icon = STATUS_ICONS.get(status, "⏳")
            self.status_lbl.setText(icon)
        if tooltip:
            self.status_lbl.setToolTip(tooltip)

    def mark_excluded(self, reason: str = ""):
        self.set_status("excluded", reason)
        self.name_lbl.setStyleSheet("font-size:12px; color:#94a3b8; text-decoration:line-through;")

    def enterEvent(self, event):
        self._thumb_timer.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._thumb_timer.stop()
        self._hide_thumbnail()
        super().leaveEvent(event)

    def _show_thumbnail(self):
        ext = os.path.splitext(self.src_path)[1].lstrip(".").lower()
        cat = get_file_category(ext)
        if cat not in ("image", "video"):
            return
        if not os.path.isfile(self.src_path):
            return
        try:
            from PIL import Image
            img = Image.open(self.src_path)
            img.thumbnail((160, 120))
            import tempfile, os as _os
            tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            tmp_path = tmp.name
            tmp.close()
            img.save(tmp_path)
            pixmap = QPixmap(tmp_path)
            try:
                _os.unlink(tmp_path)
            except Exception:
                pass
            if pixmap.isNull():
                return
            popup = QLabel()
            popup.setWindowFlags(Qt.WindowType.ToolTip)
            popup.setPixmap(pixmap)
            popup.setFixedSize(pixmap.size())
            global_pos = self.mapToGlobal(self.rect().topRight())
            popup.move(global_pos.x() + 4, global_pos.y())
            popup.show()
            self._thumb_popup = popup
        except Exception:
            pass

    def _hide_thumbnail(self):
        if self._thumb_popup is not None:
            try:
                self._thumb_popup.hide()
                self._thumb_popup.deleteLater()
            except Exception:
                pass
            self._thumb_popup = None


# ─────────────────────────────────────────────────────────────────────────────
# FormatBadge
# ─────────────────────────────────────────────────────────────────────────────

class FormatBadge(QLabel):
    """Badge coloreado para un formato de archivo."""
    def __init__(self, fmt: str, parent=None):
        super().__init__(fmt.upper(), parent)
        color = cat_color(fmt)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(
            f"background:{color}; color:white; border-radius:4px; "
            f"font-size:10px; font-weight:700; padding: 2px 6px;"
        )


# ─────────────────────────────────────────────────────────────────────────────
# CategoryTabBar
# ─────────────────────────────────────────────────────────────────────────────

_CAT_ICONS = {
    "image":    "🖼️",
    "audio":    "🎵",
    "video":    "🎬",
    "document": "📄",
    "data":     "📊",
    "email":    "📧",
    "web":      "🌐",
    "other":    "📎",
}


class CategoryTabBar(QWidget):
    """Barra de pestañas de categorías — se muestra solo con categorías mixtas."""
    category_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._active_cat = ""
        self._buttons: dict = {}
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self._layout = layout
        self.setVisible(False)

    def set_categories(self, cats: dict):
        """cats = {"image": 3, "video": 2, ...}"""
        # Clear existing
        for btn in self._buttons.values():
            self._layout.removeWidget(btn)
            btn.deleteLater()
        self._buttons.clear()

        if len(cats) <= 1:
            self.setVisible(False)
            return

        first = True
        for cat_key, count in cats.items():
            icon = _CAT_ICONS.get(cat_key, "📎")
            color = CATEGORY_COLORS.get(cat_key, "#94a3b8")
            btn = QPushButton(f"{icon} {cat_key.capitalize()} ({count})")
            btn.setCheckable(True)
            btn.setProperty("cat_key", cat_key)
            btn.setProperty("cat_color", color)
            btn.clicked.connect(self._on_tab_clicked)
            self._layout.addWidget(btn)
            self._buttons[cat_key] = btn
            if first:
                self._activate(cat_key)
                first = False

        self._layout.addStretch()
        self.setVisible(True)

    def _on_tab_clicked(self):
        btn = self.sender()
        cat = btn.property("cat_key")
        self._activate(cat)
        self.category_changed.emit(cat)

    def _activate(self, cat_key: str):
        self._active_cat = cat_key
        for key, btn in self._buttons.items():
            active = key == cat_key
            color = btn.property("cat_color")
            if active:
                btn.setStyleSheet(
                    f"QPushButton {{ font-weight:700; border-bottom:2px solid {color};"
                    f" background:rgba(0,0,0,0.05); border-radius:4px; padding:4px 8px; }}"
                )
                btn.setChecked(True)
            else:
                btn.setStyleSheet(
                    "QPushButton { font-weight:400; border:none; background:transparent;"
                    " border-radius:4px; padding:4px 8px; }"
                )
                btn.setChecked(False)

    def active_category(self) -> str:
        return self._active_cat


# ─────────────────────────────────────────────────────────────────────────────
# AccordionOption — base class
# ─────────────────────────────────────────────────────────────────────────────

class AccordionOption(QFrame):
    """Panel colapsable genérico para opciones de conversión."""

    def __init__(self, title: str, icon_text: str, default_checked: bool = False, parent=None):
        super().__init__(parent)
        self.setObjectName("accordionOption")
        self._expanded = False
        self._content_height = 0
        self._icon_text = icon_text
        self._title = title

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Header ──────────────────────────────────────────────────
        self._header = QWidget()
        self._header.setObjectName("accordionHeader")
        self._header.setStyleSheet(
            "#accordionHeader { background:#f8fafc; border-radius:6px; padding:2px; }"
            "#accordionHeader:hover { background:#f1f5f9; }"
        )
        self._header.setCursor(Qt.CursorShape.PointingHandCursor)
        self._header.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        h_layout = QHBoxLayout(self._header)
        h_layout.setContentsMargins(10, 8, 10, 8)
        h_layout.setSpacing(8)

        self.checkbox = QCheckBox()
        self.checkbox.setChecked(default_checked)
        h_layout.addWidget(self.checkbox)

        icon_lbl = QLabel(icon_text)
        icon_lbl.setStyleSheet("font-size:14px;")
        h_layout.addWidget(icon_lbl)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("font-size:12px; font-weight:600;")
        h_layout.addWidget(title_lbl)

        h_layout.addStretch()

        self._arrow = QLabel("▶")
        self._arrow.setStyleSheet("font-size:10px; color:#64748b;")
        h_layout.addWidget(self._arrow)

        outer.addWidget(self._header)

        # ── Content area (animated) ──────────────────────────────────
        self._content_wrapper = QWidget()
        self._content_wrapper.setMaximumHeight(0)
        self._content_wrapper.setObjectName("accordionContent")
        self._content_wrapper.setStyleSheet(
            "#accordionContent { background:#fafafa; border-radius:0 0 6px 6px;"
            " margin-left:20px; }"
        )

        content_layout = QVBoxLayout(self._content_wrapper)
        content_layout.setContentsMargins(10, 6, 10, 8)
        content_layout.setSpacing(6)

        self._build_content(content_layout)

        outer.addWidget(self._content_wrapper)

        # ── Animation ────────────────────────────────────────────────
        self._anim = QPropertyAnimation(self._content_wrapper, b"maximumHeight")
        self._anim.setDuration(150)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

        # ── Connect signals ──────────────────────────────────────────
        self._header.mousePressEvent = self._header_clicked
        self.checkbox.toggled.connect(self._on_checkbox_toggled)

        # Initial state
        if default_checked:
            # Expand after show
            QTimer.singleShot(0, self._expand_no_anim)

    def _header_clicked(self, event):
        self._toggle_expand()

    def _on_checkbox_toggled(self, checked: bool):
        if checked and not self._expanded:
            self._toggle_expand()
        elif not checked and self._expanded:
            self._toggle_expand()

    def _toggle_expand(self):
        if self._expanded:
            self._collapse()
        else:
            self._expand()

    def _expand_no_anim(self):
        h = self._get_content_height()
        self._content_wrapper.setMaximumHeight(h)
        self._expanded = True
        self._arrow.setText("▼")

    def _expand(self):
        h = self._get_content_height()
        self._anim.stop()
        self._anim.setStartValue(self._content_wrapper.maximumHeight())
        self._anim.setEndValue(h)
        self._anim.start()
        self._expanded = True
        self._arrow.setText("▼")

    def _collapse(self):
        self._anim.stop()
        self._anim.setStartValue(self._content_wrapper.maximumHeight())
        self._anim.setEndValue(0)
        self._anim.start()
        self._expanded = False
        self._arrow.setText("▶")

    def _get_content_height(self) -> int:
        if self._content_height == 0:
            self._content_wrapper.adjustSize()
            h = self._content_wrapper.sizeHint().height()
            self._content_height = max(h, 60)
        return self._content_height

    def _build_content(self, layout: QVBoxLayout):
        """Override in subclass to populate content area."""
        pass

    def is_checked(self) -> bool:
        return self.checkbox.isChecked()


# ─────────────────────────────────────────────────────────────────────────────
# MetadataOption
# ─────────────────────────────────────────────────────────────────────────────

class MetadataOption(AccordionOption):
    """Opción para eliminar metadatos del archivo de salida."""

    def __init__(self, parent=None):
        super().__init__(
            title="Eliminar metadatos del archivo de salida",
            icon_text="🕵️",
            default_checked=True,
            parent=parent,
        )
        self.checkbox.setToolTip(
            "Cuando está activado, los archivos convertidos no contienen\n"
            "información sobre quién los creó, cuándo ni con qué\n"
            "dispositivo. Recomendado para documentos oficiales."
        )

    def _build_content(self, layout: QVBoxLayout):
        pass  # Solo importa el checkbox

    def is_enabled(self) -> bool:
        return self.checkbox.isChecked()


# ─────────────────────────────────────────────────────────────────────────────
# PageMarkerOption
# ─────────────────────────────────────────────────────────────────────────────

class PageMarkerOption(AccordionOption):
    """Marcar en el texto dónde cambiaba de página el documento original."""

    def __init__(self, parent=None):
        super().__init__(
            title="Marcar los números de página (para poder citar)",
            icon_text="📑",
            default_checked=True,
            parent=parent,
        )
        self.checkbox.setToolTip(
            "Un archivo de texto no tiene páginas. Con esto activado, al\n"
            "convertir a Markdown se intercala un renglón como\n"
            "«--- [PÁGINA 7] ---» donde el documento original cambiaba de hoja.\n\n"
            "Sirve para citar: si después le pedís a una IA que resuma o\n"
            "busque algo en el documento, puede decirte la página exacta.\n"
            "Los números son los del documento tal como se ve impreso."
        )

    def _build_content(self, layout: QVBoxLayout):
        pass  # Solo importa el checkbox

    def is_enabled(self) -> bool:
        return self.checkbox.isChecked()


# ─────────────────────────────────────────────────────────────────────────────
# WatermarkOption
# ─────────────────────────────────────────────────────────────────────────────

class WatermarkOption(AccordionOption):
    """Opción para agregar marca de agua."""

    def __init__(self, parent=None):
        self._color = "#cccccc"
        super().__init__(
            title="Agregar marca de agua",
            icon_text="💧",
            default_checked=False,
            parent=parent,
        )

    def _build_content(self, layout: QVBoxLayout):
        self.input_text = QLineEdit()
        self.input_text.setPlaceholderText("Texto de la marca de agua")
        layout.addWidget(self.input_text)

        row = QHBoxLayout()
        row.addWidget(QLabel("Opacidad:"))
        self.slider_opacity = QSlider(Qt.Orientation.Horizontal)
        self.slider_opacity.setRange(10, 90)
        self.slider_opacity.setValue(25)
        self.opacity_lbl = QLabel("25%")
        self.slider_opacity.valueChanged.connect(lambda v: self.opacity_lbl.setText(f"{v}%"))
        row.addWidget(self.slider_opacity)
        row.addWidget(self.opacity_lbl)
        layout.addLayout(row)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Tamaño:"))
        self.spin_size = QSpinBox()
        self.spin_size.setRange(20, 100)
        self.spin_size.setValue(60)
        self.spin_size.setSuffix("pt")
        row2.addWidget(self.spin_size)
        row2.addWidget(QLabel("Ángulo:"))
        self.spin_angle = QDoubleSpinBox()
        self.spin_angle.setRange(0, 360)
        self.spin_angle.setValue(45)
        self.spin_angle.setSuffix("°")
        row2.addWidget(self.spin_angle)
        layout.addLayout(row2)

        self.btn_color = QPushButton()
        self.btn_color.setObjectName("ghostBtn")
        self.btn_color.setText(f"● {self._color.upper()}")
        self.btn_color.clicked.connect(self._pick_color)
        layout.addWidget(self.btn_color)

    def _pick_color(self):
        c = QColorDialog.getColor(QColor(self._color), self)
        if c.isValid():
            self._color = c.name()
            self.btn_color.setText(f"● {self._color.upper()}")

    def get_config(self) -> dict | None:
        if not self.checkbox.isChecked():
            return None
        return {
            "text":      self.input_text.text().strip(),
            "font_size": self.spin_size.value(),
            "color":     self._color,
            "opacity":   self.slider_opacity.value() / 100.0,
            "angle":     self.spin_angle.value(),
        }


# ─────────────────────────────────────────────────────────────────────────────
# FooterLegendOption
# ─────────────────────────────────────────────────────────────────────────────

class FooterLegendOption(AccordionOption):
    """Opción para agregar leyenda al pie de página."""

    def __init__(self, parent=None):
        self._color = "#888888"
        super().__init__(
            title="Leyenda al pie de página",
            icon_text="✏️",
            default_checked=False,
            parent=parent,
        )

    def _build_content(self, layout: QVBoxLayout):
        self.input_text = QLineEdit()
        self.input_text.setPlaceholderText("Ej: CONFIDENCIAL · Empresa SA · 2025")
        layout.addWidget(self.input_text)

        row = QHBoxLayout()
        row.addWidget(QLabel("Tamaño:"))
        self.spin_size = QSpinBox()
        self.spin_size.setRange(6, 20)
        self.spin_size.setValue(9)
        self.spin_size.setSuffix("pt")
        row.addWidget(self.spin_size)

        self.btn_color = QPushButton()
        self.btn_color.setObjectName("ghostBtn")
        self.btn_color.setText(f"● {self._color.upper()}")
        self.btn_color.setFixedWidth(130)
        self.btn_color.clicked.connect(self._pick_color)
        row.addWidget(self.btn_color)
        row.addStretch()
        layout.addLayout(row)

    def _pick_color(self):
        c = QColorDialog.getColor(QColor(self._color), self)
        if c.isValid():
            self._color = c.name()
            self.btn_color.setText(f"● {self._color.upper()}")

    def get_config(self) -> dict | None:
        if not self.checkbox.isChecked():
            return None
        text = self.input_text.text().strip()
        if not text:
            return None
        return {
            "text":      text,
            "font_size": self.spin_size.value(),
            "color":     self._color,
            "opacity":   1.0,
        }

    def set_pdf_only(self, is_pdf: bool):
        if not is_pdf:
            if self.checkbox.isChecked():
                self.checkbox.setChecked(False)
            self.checkbox.setEnabled(False)
            self.setToolTip("Solo disponible cuando el formato de salida es PDF")
        else:
            self.checkbox.setEnabled(True)
            self.setToolTip("")


# ─────────────────────────────────────────────────────────────────────────────
# PageNumberOption
# ─────────────────────────────────────────────────────────────────────────────

class PageNumberOption(AccordionOption):
    """Opción para numerar páginas."""

    POSITIONS = [
        "Centro abajo", "Derecha abajo", "Izquierda abajo",
        "Centro arriba", "Derecha arriba", "Izquierda arriba",
    ]
    POS_MAP = {
        "Centro abajo":    "bottom-center",
        "Derecha abajo":   "bottom-right",
        "Izquierda abajo": "bottom-left",
        "Centro arriba":   "top-center",
        "Derecha arriba":  "top-right",
        "Izquierda arriba":"top-left",
    }

    def __init__(self, parent=None):
        self._color = "#333333"
        super().__init__(
            title="Numerar páginas",
            icon_text="🔢",
            default_checked=False,
            parent=parent,
        )

    def _build_content(self, layout: QVBoxLayout):
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Posición:"))
        self.combo_pos = QComboBox()
        self.combo_pos.addItems(self.POSITIONS)
        row1.addWidget(self.combo_pos)
        row1.addStretch()
        layout.addLayout(row1)

        self.input_fmt = QLineEdit("Página {n} de {total}")
        self.input_fmt.setToolTip(
            "Usá {n} para el número de página y {total} para el total de páginas."
        )
        layout.addWidget(self.input_fmt)

        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Inicio:"))
        self.spin_start = QSpinBox()
        self.spin_start.setRange(1, 9999)
        self.spin_start.setValue(1)
        row3.addWidget(self.spin_start)
        row3.addWidget(QLabel("Tamaño:"))
        self.spin_size = QSpinBox()
        self.spin_size.setRange(6, 16)
        self.spin_size.setValue(9)
        self.spin_size.setSuffix("pt")
        row3.addWidget(self.spin_size)
        row3.addStretch()
        layout.addLayout(row3)

    def get_config(self) -> dict | None:
        if not self.checkbox.isChecked():
            return None
        return {
            "position":   self.POS_MAP.get(self.combo_pos.currentText(), "bottom-center"),
            "format":     self.input_fmt.text() or "Página {n} de {total}",
            "start_from": self.spin_start.value(),
            "font_size":  self.spin_size.value(),
            "color":      self._color,
        }

    def set_pdf_only(self, is_pdf: bool):
        if not is_pdf:
            if self.checkbox.isChecked():
                self.checkbox.setChecked(False)
            self.checkbox.setEnabled(False)
            self.setToolTip("Solo disponible cuando el formato de salida es PDF")
        else:
            self.checkbox.setEnabled(True)
            self.setToolTip("")


# ─────────────────────────────────────────────────────────────────────────────
# AudioFilterOption
# ─────────────────────────────────────────────────────────────────────────────

class AudioFilterOption(AccordionOption):
    """Opción de filtro de audio."""

    def __init__(self, parent=None):
        super().__init__(
            title="Aplicar filtro de audio",
            icon_text="🎚️",
            default_checked=False,
            parent=parent,
        )

    def _build_content(self, layout: QVBoxLayout):
        self.btn_group = QButtonGroup(self)
        modes = [
            ("Voz humana",        "Resalta la voz humana. Ideal para grabaciones de reuniones, clases o entrevistas."),
            ("Agudos",            "Resalta los sonidos agudos: platillos, consonantes, brillo general del audio."),
            ("Graves",            "Resalta los graves: bajo, bombo, calidez y profundidad del sonido."),
            ("Solo limpieza de ruido", "Elimina el ruido de fondo (ventiladores, estática, ambiente) sin cambiar el sonido."),
        ]
        for i, (label, tip) in enumerate(modes):
            rb = QRadioButton(label)
            rb.setToolTip(tip)
            if i == 3:
                rb.setChecked(True)
            self.btn_group.addButton(rb, i)
            layout.addWidget(rb)

        intensity_row = QHBoxLayout()
        intensity_row.addWidget(QLabel("Intensidad:"))
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setValue(50)
        self.slider.setToolTip("Intensidad del filtro (0 = mínimo, 100 = máximo)")
        intensity_row.addWidget(self.slider)
        self.intensity_lbl = QLabel("50%")
        self.intensity_lbl.setFixedWidth(36)
        self.slider.valueChanged.connect(lambda v: self.intensity_lbl.setText(f"{v}%"))
        intensity_row.addWidget(self.intensity_lbl)
        layout.addLayout(intensity_row)

    def get_config(self) -> dict | None:
        if not self.checkbox.isChecked():
            return None
        modes_map = {0: "voz", 1: "agudos", 2: "graves", 3: "limpieza"}
        return {
            "mode":      modes_map.get(self.btn_group.checkedId(), "limpieza"),
            "intensity": self.slider.value(),
        }


# ─────────────────────────────────────────────────────────────────────────────
# SubtitleOption
# ─────────────────────────────────────────────────────────────────────────────

class SubtitleOption(AccordionOption):
    """Opción para generar subtítulos automáticos."""

    LANGUAGES = [
        "Detectar automáticamente", "Español", "Inglés", "Portugués", "Francés",
        "Alemán", "Italiano", "Chino", "Japonés", "Árabe",
        "Ruso", "Coreano", "Hindi", "Turco", "Holandés",
        "Polaco", "Sueco", "Noruego", "Danés", "Finlandés",
    ]

    def __init__(self, parent=None):
        self._available = False
        try:
            from motors.motor_subtitles import is_available
            self._available = is_available()
        except Exception:
            self._available = False
        super().__init__(
            title="Generar subtítulos automáticos",
            icon_text="💬",
            default_checked=False,
            parent=parent,
        )
        if not self._available:
            self.checkbox.setEnabled(False)
            self.checkbox.setToolTip(
                "Necesita el motor de transcripción (Whisper),\n"
                "que no está instalado en este equipo."
            )

    def _build_content(self, layout: QVBoxLayout):
        lang_row = QHBoxLayout()
        lang_row.addWidget(QLabel("Idioma del audio:"))
        self.combo_lang = QComboBox()
        self.combo_lang.addItems(self.LANGUAGES)
        self.combo_lang.setEnabled(self._available)
        lang_row.addWidget(self.combo_lang)
        lang_row.addStretch()
        layout.addLayout(lang_row)

        self.chk_burn = QCheckBox("Incluir subtítulos dentro del video")
        self.chk_burn.setEnabled(self._available)
        layout.addWidget(self.chk_burn)

    def get_config(self) -> dict | None:
        if not self.checkbox.isChecked() or not self._available:
            return None
        lang_map = {
            "Detectar automáticamente": None, "Español": "es", "Inglés": "en",
            "Portugués": "pt", "Francés": "fr", "Alemán": "de",
            "Italiano": "it", "Chino": "zh", "Japonés": "ja",
            "Árabe": "ar", "Ruso": "ru", "Coreano": "ko",
        }
        lang = self.combo_lang.currentText()
        return {
            "language": lang_map.get(lang, None),
            "burn_in":  self.chk_burn.isChecked(),
        }


# ─────────────────────────────────────────────────────────────────────────────
# OcrOption
# ─────────────────────────────────────────────────────────────────────────────

class OcrOption(AccordionOption):
    """Opción para reconocimiento de texto (OCR)."""

    def __init__(self, parent=None):
        self._available = False
        try:
            from motors.motor_ocr import OcrMotor
            self._available = OcrMotor.is_available()
        except Exception:
            self._available = False
        super().__init__(
            title="Reconocer texto (OCR)",
            icon_text="🔍",
            default_checked=False,
            parent=parent,
        )
        if not self._available:
            self.checkbox.setEnabled(False)
            self.checkbox.setToolTip(
                "Necesita Tesseract en bin/. Pedíselo al administrador."
            )

    def _build_content(self, layout: QVBoxLayout):
        lang_row = QHBoxLayout()
        lang_row.addWidget(QLabel("Idioma:"))
        self.combo_lang = QComboBox()
        self.combo_lang.addItems(["Español", "Inglés", "Portugués", "Francés"])
        self.combo_lang.setEnabled(self._available)
        lang_row.addWidget(self.combo_lang)
        lang_row.addStretch()
        layout.addLayout(lang_row)

        self.chk_gray = QCheckBox("Escala de grises (PDF más liviano)")
        self.chk_gray.setChecked(True)
        self.chk_gray.setEnabled(self._available)
        self.chk_gray.setToolTip(
            "Guarda el PDF buscable en blanco y negro: pesa bastante menos.\n"
            "Desactivalo solo si el documento tiene color que querés conservar."
        )
        layout.addWidget(self.chk_gray)

        hint = QLabel(
            "Con destino <b>PDF</b> se genera un <b>PDF buscable</b>: conserva la "
            "página original y agrega una capa de texto seleccionable (Ctrl+F).<br>"
            "Con destino TXT/DOCX/HTML se extrae el texto plano."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("font-size:11px; color:#64748b;")
        layout.addWidget(hint)

    def get_config(self) -> dict | None:
        if not self.checkbox.isChecked() or not self._available:
            return None
        return {
            "language":  self.combo_lang.currentText(),
            "grayscale": self.chk_gray.isChecked(),
        }


# ─────────────────────────────────────────────────────────────────────────────
# ThemeToggle
# ─────────────────────────────────────────────────────────────────────────────

class ThemeToggle(QPushButton):
    """Botón para alternar entre tema claro y oscuro."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(36, 36)
        self.setObjectName("ghostBtn")
        self.setToolTip("Cambiar entre modo claro y oscuro")
        self._mode = "light"
        self._update_icon()

    def _update_icon(self):
        self.setText("☀️" if self._mode == "light" else "🌙")

    def set_mode(self, mode: str):
        self._mode = mode
        self._update_icon()

    def toggle_theme(self) -> str:
        """Alterna tema y devuelve el nuevo modo."""
        app = QApplication.instance()
        if app:
            from ui.theme import ThemeManager
            new_mode = ThemeManager.toggle(app)
            self._mode = new_mode
            self._update_icon()
            return new_mode
        return self._mode


# ─────────────────────────────────────────────────────────────────────────────
# PanicButton
# ─────────────────────────────────────────────────────────────────────────────

class PanicButton(QPushButton):
    """Botón rojo para limpiar toda la cola y cancelar conversiones."""
    panic_confirmed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__("🗑 Limpiar todo", parent)
        self.setObjectName("dangerBtn")
        self.setToolTip(
            "Cancela todo y limpia la cola de archivos.\n"
            "Los archivos ya convertidos no se borran."
        )
        self.clicked.connect(self._confirm)

    def _confirm(self):
        reply = QMessageBox.question(
            self, "¿Limpiar todo?",
            "¿Querés vaciar la cola y cancelar todo?\n\n"
            "Esto no borra los archivos que ya se convirtieron.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.panic_confirmed.emit()


# ─────────────────────────────────────────────────────────────────────────────
# AppStatusBar
# ─────────────────────────────────────────────────────────────────────────────

class AppStatusBar(QWidget):
    """Barra de estado inferior con información de la sesión."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(14)

        self.lbl_files = QLabel("0 archivos")
        self.lbl_files.setStyleSheet("font-size:11px;")
        layout.addWidget(self.lbl_files)

        layout.addWidget(self._sep())

        self.lbl_format = QLabel("Sin formato")
        self.lbl_format.setStyleSheet("font-size:11px;")
        layout.addWidget(self.lbl_format)

        layout.addWidget(self._sep())

        self.lbl_motors = QLabel("Motores: cargando...")
        self.lbl_motors.setStyleSheet("font-size:11px;")
        layout.addWidget(self.lbl_motors)

        layout.addStretch()

        self.lbl_theme = QLabel("☀️ Claro")
        self.lbl_theme.setStyleSheet("font-size:11px;")
        layout.addWidget(self.lbl_theme)

    def _sep(self):
        sep = QLabel("|")
        sep.setStyleSheet("color:#94a3b8;")
        return sep

    def update_files(self, count: int):
        self.lbl_files.setText(f"{count} archivo{'s' if count != 1 else ''}")

    def update_format(self, fmt: str):
        self.lbl_format.setText(f"→ {fmt.upper()}" if fmt else "Sin formato")

    def update_motors(self, ffmpeg: bool, libreoffice: bool):
        parts = []
        parts.append(f"{'✅' if ffmpeg else '⚠️'} FFmpeg")
        parts.append(f"{'✅' if libreoffice else '⚠️'} LibreOffice")
        self.lbl_motors.setText("  ".join(parts))

    def update_theme(self, mode: str):
        self.lbl_theme.setText("☀️ Claro" if mode == "light" else "🌙 Oscuro")


# ─────────────────────────────────────────────────────────────────────────────
# Backward compatibility aliases
# ─────────────────────────────────────────────────────────────────────────────

AudioFilterPanel  = AudioFilterOption
SubtitlePanel     = SubtitleOption
OcrPanel          = OcrOption
WatermarkPanel    = WatermarkOption
LegendPanel       = FooterLegendOption
PageNumberPanel   = PageNumberOption
MetadataPanel     = MetadataOption
