"""
ui/theme.py — Sistema de temas de Navaja.
Diseño inspirado en Windows 11 Fluent / Arc Browser / Linear.
"""

LIGHT = {
    "background":     "#F4F6F8",
    "surface":        "#FFFFFF",
    "surface_alt":    "#F1F5F9",
    "border":         "#E8ECF2",
    "border_focus":   "#4F46E5",
    "text_primary":   "#0F172A",
    "text_secondary": "#64748B",
    "text_disabled":  "#CBD5E1",
    "accent":         "#4F46E5",
    "accent_hover":   "#4338CA",
    "accent_pressed": "#3730A3",
    "success":        "#059669",
    "success_bg":     "#ECFDF5",
    "warning":        "#D97706",
    "warning_bg":     "#FFFBEB",
    "danger":         "#DC2626",
    "danger_bg":      "#FEF2F2",
    "overlay":        "rgba(0,0,0,0.4)",
    "shadow":         "rgba(15,23,42,0.07)",
}

DARK = {
    "background":     "#0f172a",
    "surface":        "#1e293b",
    "surface_alt":    "#162032",
    "border":         "#334155",
    "border_focus":   "#818CF8",
    "text_primary":   "#f1f5f9",
    "text_secondary": "#94a3b8",
    "text_disabled":  "#475569",
    "accent":         "#818CF8",
    "accent_hover":   "#6366F1",
    "accent_pressed": "#4F46E5",
    "success":        "#22c55e",
    "success_bg":     "#052e16",
    "warning":        "#f59e0b",
    "warning_bg":     "#1c1100",
    "danger":         "#f87171",
    "danger_bg":      "#1a0000",
    "overlay":        "rgba(0,0,0,0.6)",
    "shadow":         "rgba(0,0,0,0.3)",
}


def _build_stylesheet(t: dict) -> str:
    is_light = t is LIGHT

    # Sidebar siempre con diseño limpio (light/white en modo claro)
    if is_light:
        sidebar_bg      = "#FFFFFF"
        sidebar_sep     = "#E8ECF2"
        nav_text        = "#64748B"
        nav_hover_bg    = "#F1F5F9"
        nav_hover_text  = "#0F172A"
        nav_active_bg   = "#EEF2FF"
        nav_active_text = "#4F46E5"
        nav_active_border = "#4F46E5"
        logo_title_color = "#0F172A"
        logo_sub_color   = "#4F46E5"
        section_color    = "#94A3B8"
    else:
        sidebar_bg      = "#0D1117"
        sidebar_sep     = "#1e293b"
        nav_text        = "#94a3b8"
        nav_hover_bg    = "#1e293b"
        nav_hover_text  = "#f1f5f9"
        nav_active_bg   = "#1e3a5f"
        nav_active_text = "#818CF8"
        nav_active_border = "#818CF8"
        logo_title_color = "#FFFFFF"
        logo_sub_color   = "#818CF8"
        section_color    = "#475569"

    list_sel_bg = "#EEF2FF" if is_light else "#1e3a5f"

    return f"""
/* ── Base ─────────────────────────────────────────────────────────── */
QMainWindow, QWidget, QDialog {{
    background-color: {t['background']};
    font-family: 'Segoe UI', 'SF Pro Display', 'Ubuntu', sans-serif;
    font-size: 13px;
    color: {t['text_primary']};
}}
QLabel {{
    color: {t['text_primary']};
    background: transparent;
}}
QLabel#appTitle {{
    font-size: 22px; font-weight: 800;
    color: {t['text_primary']}; letter-spacing: -0.5px;
}}
QLabel#appSubtitle {{
    font-size: 12px; color: {t['text_secondary']};
}}

/* ── Sidebar ─────────────────────────────────────────────────────── */
QFrame#sideBar {{
    background: {sidebar_bg};
    border-radius: 0;
    border: none;
    border-right: 1px solid {sidebar_sep};
}}
QWidget#sideBarLogo {{
    background: transparent;
    padding: 8px 0px;
}}
QLabel#sideBarTitle {{
    font-size: 18px;
    font-weight: 800;
    color: {logo_title_color};
    letter-spacing: -0.5px;
    background: transparent;
}}
QLabel#sideBarSubtitle {{
    font-size: 10px;
    color: {logo_sub_color};
    font-weight: 700;
    letter-spacing: 1px;
    background: transparent;
}}
QFrame#sideBarSep {{
    background: {sidebar_sep};
    min-height: 1px;
    max-height: 1px;
    border: none;
}}
QLabel#sideBarSection {{
    font-size: 9px;
    font-weight: 700;
    color: {section_color};
    letter-spacing: 1.5px;
    padding: 10px 14px 2px 14px;
    background: transparent;
}}
QPushButton#navBtn {{
    background: transparent;
    color: {nav_text};
    text-align: left;
    padding: 9px 14px;
    border-radius: 10px;
    border: none;
    font-size: 13px;
    font-weight: 500;
}}
QPushButton#navBtn:hover {{
    background: {nav_hover_bg};
    color: {nav_hover_text};
}}
QPushButton#navBtn:checked {{
    background: {nav_active_bg};
    color: {nav_active_text};
    font-weight: 700;
    border-left: 3px solid {nav_active_border};
    padding-left: 11px;
}}
/* Contenedor con scroll del sidebar (para pantallas bajas) */
QScrollArea#sideBarScroll {{
    background: transparent;
    border: none;
}}
QScrollArea#sideBarScroll > QWidget > QWidget {{
    background: transparent;
}}
QWidget#sideBarContent {{
    background: transparent;
}}

/* Botón de salir al pie del sidebar */
QFrame#sideBarExit {{
    background: {t['surface_alt']};
    border: 1px solid transparent;
    border-radius: 12px;
}}
QFrame#sideBarExit:hover {{
    background: #fee2e2;
    border: 1px solid #fca5a5;
}}
QLabel#exitIcon {{
    font-size: 15px;
    font-weight: 700;
    color: {t['text_secondary']};
    background: transparent;
}}
QFrame#sideBarExit:hover QLabel#exitIcon {{
    color: #b91c1c;
}}
QLabel#profileAvatar {{
    background: {t['accent']};
    color: white;
    border-radius: 16px;
    font-weight: 800;
    font-size: 13px;
    min-width: 32px;
    max-width: 32px;
    min-height: 32px;
    max-height: 32px;
}}
QLabel#profileName {{
    font-size: 12px;
    font-weight: 700;
    color: {t['text_primary']};
    background: transparent;
}}

/* ── Panels ──────────────────────────────────────────────────────── */
QFrame#filePanel {{
    background: {t['surface']};
    border-radius: 0;
    border: none;
    border-right: 1px solid {t['border']};
}}
QLabel#panelHeader {{
    font-size: 14px;
    font-weight: 700;
    color: {t['text_primary']};
    background: transparent;
}}
QLabel#cardHeader {{
    font-size: 13px;
    font-weight: 700;
    color: {t['text_secondary']};
    background: transparent;
}}
QLabel#warnMixed {{
    background: {t['warning_bg']};
    border: 1px solid {t['warning']};
    border-radius: 10px;
    padding: 8px;
    font-size: 11px;
    color: {t['text_primary']};
}}

/* ── Cards ───────────────────────────────────────────────────────── */
QFrame#card {{
    background: {t['surface']};
    border-radius: 16px;
    border: 1px solid {t['border']};
}}
QFrame#sep {{
    background: {t['border']};
    min-height: 1px; max-height: 1px;
}}

/* ── Buttons ─────────────────────────────────────────────────────── */
QPushButton {{
    background: {t['accent']}; color: white;
    border-radius: 10px; padding: 9px 16px;
    font-weight: 600; font-size: 12px; border: none;
}}
QPushButton:hover   {{ background: {t['accent_hover']}; }}
QPushButton:pressed {{ background: {t['accent_pressed']}; }}
QPushButton:disabled{{ background: {t['text_disabled']}; color: {t['border']}; }}
QPushButton#dangerBtn {{
    background: {t['danger']};
}}
QPushButton#dangerBtn:hover {{ background: #b91c1c; }}
QPushButton#convertBtn {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #4F46E5, stop:1 #7C3AED);
    color: white;
    font-size: 15px;
    font-weight: 700;
    padding: 14px 28px;
    border-radius: 14px;
    border: none;
}}
QPushButton#convertBtn:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #4338CA, stop:1 #6D28D9);
}}
QPushButton#convertBtn:disabled {{
    background: {t['text_disabled']};
    color: {t['border']};
}}
QPushButton#ghostBtn {{
    background: {t['surface_alt']}; color: {t['text_secondary']};
    border: 1.5px solid {t['border']};
    border-radius: 10px;
}}
QPushButton#ghostBtn:hover {{ background: {t['border']}; color: {t['text_primary']}; }}
/* Botones de preset compactos (5 MB, 16 MB, ...): padding chico para que el
   texto no se recorte en anchos reducidos. */
QPushButton#presetBtn {{
    background: {t['surface_alt']}; color: {t['text_secondary']};
    border: 1.5px solid {t['border']};
    border-radius: 8px;
    padding: 5px 4px; font-size: 11px; font-weight: 700;
    min-width: 0px;
}}
QPushButton#presetBtn:hover {{ background: {t['border']}; color: {t['text_primary']}; }}
QPushButton#warningBtn {{
    background: {t['warning']}; color: white; border-radius: 10px;
}}
QPushButton#warningBtn:hover {{ background: #b45309; }}

/* Botones de acción rápida (pills) en Home */
QPushButton#quickActionBtn {{
    background: {t['surface']};
    color: {t['text_primary']};
    border-radius: 20px;
    border: 1.5px solid {t['border']};
    padding: 8px 18px;
    font-size: 12px;
    font-weight: 600;
}}
QPushButton#quickActionBtn:hover {{
    background: {t['surface_alt']};
    border-color: {t['accent']};
    color: {t['accent']};
}}

/* ── Stack ───────────────────────────────────────────────────────── */
QStackedWidget {{
    background: transparent;
}}

/* ── Form controls ───────────────────────────────────────────────── */
QComboBox {{
    background: {t['surface']}; border: 1.5px solid {t['border']};
    border-radius: 9px; padding: 7px 12px;
    font-size: 13px; color: {t['text_primary']}; min-width: 120px;
}}
QComboBox:focus {{ border-color: {t['border_focus']}; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox QAbstractItemView {{
    background: {t['surface']}; color: {t['text_primary']};
    border: 1px solid {t['border']}; selection-background-color: {t['accent']};
}}
QProgressBar {{
    border: 2px solid {t['border']}; border-radius: 9px;
    text-align: center; font-weight: 700;
    color: {t['text_primary']}; background: {t['surface']}; min-height: 24px;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 {t['accent']}, stop:1 #7C3AED);
    border-radius: 7px;
}}
QCheckBox {{
    font-size: 12px; color: {t['text_primary']};
    font-weight: 600; spacing: 7px;
}}
QCheckBox::indicator {{
    width:17px; height:17px; border-radius:5px;
    border: 2px solid {t['text_disabled']}; background: {t['surface']};
}}
QCheckBox::indicator:checked {{
    background: {t['accent']}; border-color: {t['accent']};
}}
QRadioButton {{
    font-size: 12px; color: {t['text_primary']}; spacing: 6px;
}}
QRadioButton::indicator {{
    width: 15px; height: 15px; border-radius: 8px;
    border: 2px solid {t['text_disabled']}; background: {t['surface']};
}}
QRadioButton::indicator:checked {{
    background: {t['accent']}; border-color: {t['accent']};
}}
QLineEdit {{
    background: {t['surface']}; border: 1.5px solid {t['border']};
    border-radius: 9px; padding: 8px 12px;
    font-size: 12px; color: {t['text_primary']};
}}
QLineEdit:focus {{ border-color: {t['border_focus']}; }}
QSpinBox, QDoubleSpinBox {{
    background: {t['surface']}; border: 1.5px solid {t['border']};
    border-radius: 9px; padding: 6px 8px;
    font-size: 12px; color: {t['text_primary']}; min-width: 64px;
}}
QSpinBox:focus, QDoubleSpinBox:focus {{ border-color: {t['border_focus']}; }}
QSlider::groove:horizontal {{
    height: 6px; background: {t['border']}; border-radius: 3px;
}}
QSlider::handle:horizontal {{
    background: {t['accent']}; border: 2px solid {t['accent_hover']};
    width: 16px; height: 16px; border-radius: 8px; margin: -5px 0;
}}
QSlider::sub-page:horizontal {{
    background: {t['accent']}; border-radius: 3px;
}}
QListWidget {{
    background: {t['surface']}; border: none;
    border-radius: 12px; outline: none;
    color: {t['text_primary']};
}}
QListWidget::item {{ border-radius: 8px; color: {t['text_primary']}; padding: 2px; }}
QListWidget::item:selected {{
    background: {list_sel_bg};
    color: {t['text_primary']};
}}
QTextEdit, QPlainTextEdit {{
    background: #0f172a; color: #94a3b8;
    border: none; border-radius: 12px;
    font-family: 'Cascadia Code','Fira Code','Consolas',monospace;
    font-size: 11px; padding: 8px;
}}
/* El panel de Escribir no es un log: se escribe un documento, así que va
   con fondo de hoja y letra legible, no la consola oscura de arriba. */
QPlainTextEdit#docEditor, QTextBrowser#docPreview {{
    background: {t['surface']};
    color: {t['text_primary']};
    border: 1px solid {t['border']};
    border-radius: 10px;
    padding: 10px;
    font-size: 13px;
    selection-background-color: {t['accent']};
    selection-color: #ffffff;
}}
QTextBrowser#docPreview {{
    font-family: 'Segoe UI','Inter',system-ui,sans-serif;
}}
QTabWidget::pane {{
    border: 1px solid {t['border']}; border-radius: 12px;
    background: {t['surface']};
}}
QTabBar::tab {{
    background: {t['surface_alt']}; color: {t['text_secondary']};
    padding: 8px 18px; border-radius: 8px 8px 0 0;
    font-weight: 600; font-size: 12px;
}}
QTabBar::tab:selected {{ background: {t['surface']}; color: {t['text_primary']}; }}
/* Barras de scroll: antes eran de 6 px y del color del borde, así que
   sobre el fondo claro no se veían y no había forma de darse cuenta de que
   la lista seguía más abajo. Ahora tienen carril propio y un tirador con
   contraste. */
QScrollBar:vertical {{
    background: {t['surface_alt']}; width: 12px; border-radius: 6px; margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {t['text_disabled']}; border-radius: 5px; min-height: 32px;
    border: 1px solid {t['surface_alt']};
}}
QScrollBar::handle:vertical:hover {{ background: {t['text_secondary']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: transparent;
}}
QScrollBar:horizontal {{
    background: {t['surface_alt']}; height: 12px; border-radius: 6px; margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: {t['text_disabled']}; border-radius: 5px; min-width: 32px;
    border: 1px solid {t['surface_alt']};
}}
QScrollBar::handle:horizontal:hover {{ background: {t['text_secondary']}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    background: transparent;
}}
QSplitter::handle {{
    background: {t['border']};
}}
QToolTip {{
    background: #1e293b; color: #f1f5f9;
    border: 1px solid #334155; border-radius: 8px;
    padding: 6px 10px; font-size: 11px;
}}
QMessageBox {{
    background: {t['surface']};
}}
QStatusBar {{
    background: {t['surface']}; color: {t['text_secondary']};
    border-top: 1px solid {t['border']};
    font-size: 11px;
}}
QScrollArea {{
    border: none;
    background: transparent;
}}
"""


class ThemeManager:
    _mode = "light"

    @classmethod
    def apply(cls, app, mode: str = "light") -> None:
        cls._mode = mode
        palette = LIGHT if mode == "light" else DARK
        app.setStyleSheet(_build_stylesheet(palette))

    @classmethod
    def toggle(cls, app) -> str:
        new_mode = "dark" if cls._mode == "light" else "light"
        cls.apply(app, new_mode)
        try:
            from core.config_manager import config
            config.set("theme", new_mode)
        except Exception:
            pass
        return new_mode

    @classmethod
    def current_mode(cls) -> str:
        return cls._mode

    @classmethod
    def current_colors(cls) -> dict:
        return LIGHT if cls._mode == "light" else DARK
