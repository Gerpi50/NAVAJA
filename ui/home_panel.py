"""
ui/home_panel.py — Dashboard de inicio con diseño Bento Grid premium.
"""
import json
import os
from datetime import datetime
from typing import Callable, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QSizePolicy, QLineEdit, QApplication,
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import QGraphicsDropShadowEffect


# ── Módulos disponibles ───────────────────────────────────────────────────

def _desc_convertir() -> str:
    """Cuántos formatos convierte REALMENTE esta instalación.

    Decía "100+ formatos", que se lee como "convierte a más de 100", y no es
    así: lee muchos más de los que escribe, y el número depende de lo que
    haya instalado (LibreOffice, ffmpeg, Pandoc…). Se cuenta contra el grafo
    ya armado, así que el cartel nunca promete de más.
    """
    try:
        from core.graph import graph, COMPAT_MATRIX
        entradas, salidas = set(), set()
        for src in COMPAT_MATRIX:
            destinos = graph.all_targets(src)
            if destinos:
                entradas.add(src)
                salidas.update(destinos)
        if entradas and salidas:
            return (f"{len(entradas)} formatos de entrada · "
                    f"{len(salidas)} de salida\n"
                    "imagen · audio · video · documentos · datos")
    except Exception:
        pass
    return "imagen · audio · video · documentos · datos"


MODULES = [
    {
        "name": "Convertir",
        "icon": "🔄",
        "desc": "",   # se completa al construir la tarjeta: ver _desc_convertir()
        "c1": "#3B82F6", "c2": "#6366F1",
        "page": 0,
    },
    {
        "name": "PDF",
        "icon": "📄",
        "desc": "Unir · Partir por tamaño · Ajustar a un límite\n"
                "Organizar páginas · Firmar · Pasar una tabla a Excel\n"
                "Comprimir y proteger",
        "c1": "#10B981", "c2": "#059669",
        "page": 12,   # PAGE_PDF_TOOLS
    },
    {
        "name": "Audio",
        "icon": "🎵",
        "desc": "Cortar · Unir · Mejorar un audio que se oye mal\n"
                "Transcribir lo que se dice",
        "c1": "#EC4899", "c2": "#F43F5E",
        "page": 10,   # PAGE_AUDIO_MODULE
    },
    {
        "name": "Video",
        "icon": "🎬",
        "desc": "Partir sin pérdida · Ajustar tamaño\n"
                "Mapa · Capturar fotograma · Transcribir",
        "c1": "#8B5CF6", "c2": "#A855F7",
        "page": 11,   # PAGE_VIDEO_MODULE
    },
    {
        "name": "Tablas / Excel",
        "icon": "📊",
        "desc": "Unir múltiples XLS/XLSX\ny partir el resultado por tamaño",
        "c1": "#F59E0B", "c2": "#EF4444",
        "page": 4,
    },
    {
        "name": "Escribir",
        "icon": "✍️",
        "desc": "Escribí un texto acá mismo\ny guardalo como MD · TXT · PDF · Word · ODT",
        "c1": "#0EA5E9", "c2": "#6366F1",
        "page": 14,   # PAGE_EDITOR
    },
    {
        "name": "Extraer hash",
        "icon": "🔢",
        "desc": "Huella digital de cualquier archivo\nSHA-256 + SHA-512 · verificar integridad",
        "c1": "#14B8A6", "c2": "#0891B2",
        "page": 13,   # PAGE_HASH
    },
]

# ── ¿Qué necesitás hacer? ─────────────────────────────────────────────────
#
# El menú lateral nombra HERRAMIENTAS ("PDF", "Video", "Extraer hash") y eso
# obliga al usuario a saber de antemano qué herramienta resuelve su problema.
# Cuando no lo sabe —que es casi siempre la primera vez— se queda mirando la
# pantalla sin saber dónde tocar. Esta lista está escrita al revés: cada
# renglón es el problema tal como lo cuenta el usuario, y el programa
# contesta a qué botón ir.
#
# Cada entrada: (problema, a dónde hay que ir, página, solapa de adentro).
# La solapa se busca por una palabra de su nombre, así que se la puede
# renombrar sin romper esto mientras esa palabra siga estando.
TAREAS = [
    ("Tengo un archivo y lo necesito en otro formato "
     "(Word a PDF, foto a PDF, video a MP3…)",
     "🔄 Convertir", 0, None),

    ("Tengo varios PDF sueltos y quiero uno solo",
     "📄 PDF · Unir archivos", 12, "Unir"),

    ("Un PDF pesa demasiado y no me deja subirlo",
     "📄 PDF · Partir", 12, "Partir"),

    ("Tengo que subir varios PDF a un portal con límite de tamaño",
     "📄 PDF · Ajustar tamaño", 12, "Ajustar"),

    ("El PDF es un escaneo y necesito copiar el texto",
     "📄 PDF · Reconocer texto", 12, "Reconocer"),

    ("Tengo un PDF con una tabla (un resumen bancario, un listado) "
     "y la necesito en Excel",
     "📄 PDF · Pasar a Excel", 12, "Excel"),

    ("Tengo que firmar un PDF digitalmente (certificado o token)",
     "📄 PDF · Firmar", 12, "Firmar"),

    ("Quiero sacar, rotar o reordenar páginas de un PDF",
     "📄 PDF · Organizar páginas", 12, "Organizar"),

    ("Necesito la foto del momento exacto de un video de cámara",
     "🎬 Video · Capturar fotograma", 11, "Capturar"),

    ("El video es largo y no sé en qué momento pasa lo que busco",
     "🎬 Video · Mapa del video", 11, "Mapa"),

    ("Un video pesa demasiado para mandarlo o subirlo",
     "🎬 Video · Ajustar tamaño", 11, "Ajustar"),

    ("Necesito cortar un video en partes",
     "🎬 Video · Partir", 11, "Partir"),

    ("Necesito cortar un audio largo, o juntar varios en uno",
     "🎵 Audio", 10, None),

    ("Necesito pasar a texto lo que se dice en un audio",
     "🎵 Audio · Transcribir", 10, "Transcribir"),

    ("Necesito pasar a texto lo que se dice en un video",
     "🎬 Video · Transcribir", 11, "Transcribir"),

    ("Un audio o un video se escucha mal: ruido, voz muy baja",
     "🎵 Audio · Mejorar audio", 10, "Mejorar"),

    ("Tengo varios Excel y quiero juntarlos en un archivo",
     "📊 Tablas / Excel", 4, None),

    ("Quiero escribir un texto y guardarlo en Word o PDF",
     "✍️ Escribir", 14, None),

    ("Necesito probar que un archivo no fue modificado",
     "🔢 Extraer hash", 13, None),

    ("No encuentro lo que busco / quiero leer las instrucciones",
     "❓ Ayuda", 7, None),
]

NEWS_TIPS = [
    ("🔐 Hash automático",
     "Todos los módulos generan un informe técnico con SHA-256 para auditoría digital."),
    ("📦 Ajustar tamaño",
     "Comprimí o cortá videos para que entren en el límite de un correo o un portal, con informe incluido."),
    ("📋 Informe copiable",
     "Tras cada proceso encontrás el informe listo para copiar y pegar donde lo necesites."),
    ("✍️ Escribir sin salir",
     "Redactá un texto o un prompt y guardalo en el formato que quieras, "
     "o copialo y listo."),
    ("📦 PDF con límite de tamaño",
     "Elegí una carpeta con 30 PDF y el programa arma las tandas de 5, "
     "partiendo los que pasan de 10 MB."),
    ("📊 De un PDF a Excel",
     "Un resumen bancario o un listado en PDF pasa a una planilla: marcás "
     "las columnas sobre la hoja y ves cómo queda antes de guardar."),
    ("📸 El fotograma exacto",
     "De un video de cámara podés sacar la foto del momento justo, con el minuto "
     "y segundo y una constancia con los hashes."),
    ("🗺️ Mapa del video",
     "¿No sabés en qué momento pasa lo que buscás? Armá el mapa, tocá la "
     "miniatura y el programa te lleva a ese fotograma."),
]


# ── Tarjeta de módulo ─────────────────────────────────────────────────────

class _ModuleCard(QFrame):
    """Tarjeta clickeable con fondo degradado para el Bento Grid."""

    def __init__(self, module: dict, navigate_to: Callable, parent=None):
        super().__init__(parent)
        self._navigate_to = navigate_to
        self._page        = module["page"]
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(230)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setObjectName("homeModuleCard")

        # Gradiente via stylesheet
        c1, c2 = module["c1"], module["c2"]
        self.setStyleSheet(f"""
            QFrame#homeModuleCard {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {c1}, stop:1 {c2});
                border-radius: 22px;
                border: none;
            }}
        """)

        # Sombra
        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(22)
        self._shadow.setOffset(0, 6)
        self._shadow.setColor(QColor(0, 0, 0, 40))
        self.setGraphicsEffect(self._shadow)

        # Contenido
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 22, 22, 18)
        lay.setSpacing(6)

        icon_lbl = QLabel(module["icon"])
        icon_lbl.setStyleSheet(
            "font-size: 38px; background: transparent; color: white;"
        )
        lay.addWidget(icon_lbl)

        lay.addStretch()

        name_lbl = QLabel(module["name"])
        name_lbl.setStyleSheet(
            "font-size: 17px; font-weight: 800; color: white; background: transparent;"
        )
        lay.addWidget(name_lbl)

        desc_lbl = QLabel(module["desc"])
        desc_lbl.setStyleSheet(
            "font-size: 10px; color: rgba(255,255,255,0.80); background: transparent;"
        )
        desc_lbl.setWordWrap(True)
        lay.addWidget(desc_lbl)

        arrow_row = QHBoxLayout()
        arrow_row.addStretch()
        arrow_lbl = QLabel("→")
        arrow_lbl.setStyleSheet(
            "font-size: 18px; color: rgba(255,255,255,0.90); "
            "background: transparent; font-weight: 700;"
        )
        arrow_row.addWidget(arrow_lbl)
        lay.addLayout(arrow_row)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._navigate_to(self._page)

    def enterEvent(self, event):
        self._shadow.setBlurRadius(34)
        self._shadow.setColor(QColor(0, 0, 0, 60))
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._shadow.setBlurRadius(22)
        self._shadow.setColor(QColor(0, 0, 0, 40))
        super().leaveEvent(event)


# ── Renglón de "¿Qué necesitás hacer?" ────────────────────────────────────

class _TareaRow(QFrame):
    """Un problema del usuario y el botón que lo resuelve, en un renglón."""

    def __init__(self, problema: str, destino: str, page: int,
                 solapa, navegar: Callable, impar: bool = False, parent=None):
        super().__init__(parent)
        self._page = page
        self._solapa = solapa
        self._navegar = navegar
        self.problema = problema
        self.destino = destino

        self.setObjectName("tareaRow")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        # Renglones alternados: entre el problema (izquierda) y el botón al
        # que hay que ir (derecha) hay mucho espacio en blanco, y sin una
        # guía el ojo se pasa de renglón y termina yendo a la pantalla
        # equivocada.
        fondo = "rgba(15,23,42,0.035)" if impar else "transparent"
        self.setStyleSheet(
            f"QFrame#tareaRow {{ background: {fondo}; border: none; "
            "border-radius: 8px; }"
            "QFrame#tareaRow:hover { background: rgba(99,102,241,0.13); }"
        )
        self.setToolTip(f"Te lleva a: {destino}")

        fila = QHBoxLayout(self)
        fila.setContentsMargins(10, 7, 10, 7)
        fila.setSpacing(10)

        lbl_problema = QLabel(problema)
        lbl_problema.setStyleSheet(
            "font-size: 12px; color: #334155; background: transparent;")
        lbl_problema.setWordWrap(True)
        fila.addWidget(lbl_problema, stretch=1)

        # La flecha y el destino van juntos: se lee "esto → andá acá".
        lbl_destino = QLabel(f"→   {destino}")
        lbl_destino.setStyleSheet(
            "font-size: 12px; font-weight: 700; color: #4F46E5; "
            "background: transparent;")
        fila.addWidget(lbl_destino)

    def coincide(self, texto: str) -> bool:
        """True si lo que se escribió en el buscador aparece en el renglón."""
        texto = (texto or "").strip().lower()
        if not texto:
            return True
        return any(palabra in (self.problema + " " + self.destino).lower()
                   for palabra in texto.split())

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            try:
                self._navegar(self._page, self._solapa)
            except TypeError:      # una navegación vieja, sin solapas
                self._navegar(self._page)


# ── Proceso reciente (fila de tabla) ──────────────────────────────────────

def _load_recent(n: int = 10) -> list:
    """Lee las N conversiones más recientes del logger."""
    try:
        from core.paths import LOGS_DIR
        import glob
        log_files = sorted(
            glob.glob(os.path.join(str(LOGS_DIR), "*.json")),
            reverse=True,
        )
        entries = []
        for lf in log_files[:5]:
            try:
                with open(lf, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for e in data.get("entries", []):
                    entries.append(e)
            except Exception:
                continue
            if len(entries) >= n:
                break
        return entries[:n]
    except Exception:
        return []


# ── Panel principal ───────────────────────────────────────────────────────

class HomePanel(QWidget):
    """Dashboard de inicio con Bento Grid de módulos y procesos recientes."""

    def __init__(self, navigate_to: Callable, parent=None):
        super().__init__(parent)
        self._navigate_to = navigate_to
        self._setup_ui()

    def _setup_ui(self):
        # Envolver todo en un QScrollArea
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll)

        container = QWidget()
        scroll.setWidget(container)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(32, 28, 32, 32)
        layout.setSpacing(28)

        # ── 1. Header ────────────────────────────────────────────────
        layout.addLayout(self._build_header())

        # ── 2. ¿Qué necesitás hacer? ─────────────────────────────────
        # Va primero, antes que los módulos: es la sección que sirve cuando
        # uno no sabe qué botón apretar, que es justo el momento en que se
        # mira la pantalla de inicio.
        layout.addWidget(self._section_label("¿QUÉ NECESITÁS HACER?"))
        layout.addWidget(self._build_tareas())

        # ── 3. Módulos (Bento Grid) ──────────────────────────────────
        layout.addWidget(self._section_label("LAS HERRAMIENTAS, UNA POR UNA"))
        layout.addLayout(self._build_module_grid())

        # ── 4. Recientes + Qué podés hacer ─────────────────
        layout.addWidget(self._section_label("ACTIVIDAD"))
        layout.addLayout(self._build_bottom_section())

        layout.addStretch()

    # ── Header ───────────────────────────────────────────────────────

    def _build_header(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(16)

        # Saludo
        hour  = datetime.now().hour
        greet = "Buenos días" if hour < 12 else ("Buenas tardes" if hour < 19 else "Buenas noches")

        lbl_col = QVBoxLayout()
        lbl_col.setSpacing(2)

        greet_lbl = QLabel(f"{greet} 👋")
        greet_lbl.setStyleSheet(
            "font-size: 26px; font-weight: 800; color: #0F172A; background: transparent;"
        )
        lbl_col.addWidget(greet_lbl)

        sub_lbl = QLabel("Contá qué necesitás hacer y te digo qué botón tocar ↓")
        sub_lbl.setStyleSheet(
            "font-size: 13px; color: #64748B; background: transparent;"
        )
        lbl_col.addWidget(sub_lbl)
        row.addLayout(lbl_col)

        # La versión se identifica por fecha, no por número.
        try:
            from core.paths import APP_VERSION
        except Exception:
            APP_VERSION = ""
        if APP_VERSION:
            ver_lbl = QLabel(f"Versión {APP_VERSION}")
            ver_lbl.setStyleSheet(
                "font-size: 10px; color: #94A3B8; background: transparent;"
            )
            ver_lbl.setAlignment(Qt.AlignmentFlag.AlignBottom)
            row.addSpacing(10)
            row.addWidget(ver_lbl)

        row.addStretch()

        # El buscador era decorativo: escribir no hacía nada. Para alguien que
        # no encuentra la herramienta, un buscador que no busca es peor que no
        # tener ninguno. Ahora filtra la lista de "¿Qué necesitás hacer?".
        self.search = QLineEdit()
        self.search.setPlaceholderText("🔍  Buscar: pdf, firmar, video, pesa…")
        self.search.setFixedWidth(280)
        self.search.setFixedHeight(38)
        self.search.setToolTip(
            "Escribí una palabra de lo que necesitás hacer\n"
            "y la lista de abajo se achica a lo que coincide.")
        self.search.setStyleSheet(
            "QLineEdit { border: 1.5px solid #E8ECF2; border-radius: 20px; "
            "padding: 0 16px; font-size: 12px; color: #64748B; "
            "background: #FFFFFF; }"
            "QLineEdit:focus { border-color: #4F46E5; }"
        )
        self.search.textChanged.connect(self._filtrar_tareas)
        row.addWidget(self.search)

        return row

    # ── Bento Grid ────────────────────────────────────────────────────

    def _build_module_grid(self):
        # Las siete tarjetas estaban en una sola fila y no entraban: en una
        # pantalla normal la última quedaba cortada contra el borde y había
        # que descubrir que la pantalla se movía de costado. Ahora bajan de
        # renglón solas.
        from PyQt6.QtWidgets import QGridLayout

        grid = QGridLayout()
        grid.setSpacing(14)
        columnas = 4
        for i, mod in enumerate(MODULES):
            if mod["page"] == 0 and not mod["desc"]:
                mod = dict(mod, desc=_desc_convertir())
            grid.addWidget(_ModuleCard(mod, self._navigate_to),
                           i // columnas, i % columnas)
        return grid

    # ── ¿Qué necesitás hacer? ─────────────────────────────────────────

    def _build_tareas(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(2)

        ayuda = QLabel(
            "Buscá abajo lo que necesitás y tocá el renglón: el programa te "
            "lleva directo a la pantalla correcta. Si no aparece, escribí "
            "una palabra en el buscador de arriba."
        )
        ayuda.setStyleSheet("font-size: 11px; color: #64748B; padding: 0 10px 6px 10px;")
        ayuda.setWordWrap(True)
        lay.addWidget(ayuda)

        self._tarea_rows = []
        for i, (problema, destino, page, solapa) in enumerate(TAREAS):
            fila = _TareaRow(problema, destino, page, solapa,
                             self._navigate_to, impar=bool(i % 2))
            self._tarea_rows.append(fila)
            lay.addWidget(fila)

        self._sin_resultados = QLabel(
            "No encontré nada con esa palabra. Probá con otra "
            "(«pdf», «video», «firmar», «pesa»…) o mirá el manual en ❓ Ayuda."
        )
        self._sin_resultados.setStyleSheet(
            "font-size: 12px; color: #92400E; background: #FFFBEB; "
            "border: 1px solid #F59E0B; border-radius: 6px; padding: 10px;")
        self._sin_resultados.setWordWrap(True)
        self._sin_resultados.setVisible(False)
        lay.addWidget(self._sin_resultados)

        return card

    def _filtrar_tareas(self, texto: str):
        """El buscador achica la lista en vez de no hacer nada."""
        visibles = 0
        for fila in getattr(self, "_tarea_rows", []):
            coincide = fila.coincide(texto)
            fila.setVisible(coincide)
            visibles += int(coincide)
        if hasattr(self, "_sin_resultados"):
            self._sin_resultados.setVisible(visibles == 0)

    # ── Sección inferior ──────────────────────────────────────────────

    def _build_bottom_section(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(16)

        # Recientes (izq ~65%)
        recent_card = self._build_recent_card()
        row.addWidget(recent_card, stretch=65)

        # Qué podés hacer (der ~35%)
        news_card = self._build_news_card()
        row.addWidget(news_card, stretch=35)

        return row

    def _build_recent_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(10)

        hdr = QLabel("🕐  Conversiones recientes")
        hdr.setStyleSheet("font-size: 13px; font-weight: 700; color: #0F172A;")
        lay.addWidget(hdr)

        sep = QFrame()
        sep.setObjectName("sep")
        lay.addWidget(sep)

        entries = _load_recent(8)
        if entries:
            for e in entries:
                row = self._build_entry_row(e)
                lay.addWidget(row)
        else:
            empty = QLabel("Todavía no hay conversiones registradas.\nRealizá tu primera conversión para verla aquí.")
            empty.setStyleSheet("font-size: 11px; color: #94A3B8; padding: 16px 0;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setWordWrap(True)
            lay.addWidget(empty)

        lay.addStretch()
        return card

    def _build_entry_row(self, entry: dict) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        row = QHBoxLayout(w)
        row.setContentsMargins(0, 3, 0, 3)
        row.setSpacing(10)

        # Icono / extensión
        src_ext = entry.get("src_ext", "").upper() or "?"
        dst_ext = entry.get("dst_ext", "").upper() or "?"
        badge   = QLabel(f"{src_ext} → {dst_ext}")
        badge.setStyleSheet(
            "background: #EEF2FF; color: #4F46E5; border-radius: 8px; "
            "padding: 2px 8px; font-size: 10px; font-weight: 700;"
        )
        row.addWidget(badge)

        # Nombre
        fname = entry.get("filename", entry.get("src_file", "—"))
        fname = os.path.basename(fname)
        name_lbl = QLabel(fname)
        name_lbl.setStyleSheet("font-size: 11px; color: #334155;")
        name_lbl.setToolTip(fname)
        row.addWidget(name_lbl, stretch=1)

        # Estado
        ok = entry.get("success", True)
        status_lbl = QLabel("✅ OK" if ok else "❌ Error")
        status_lbl.setStyleSheet(
            f"font-size: 10px; color: {'#059669' if ok else '#DC2626'};"
        )
        row.addWidget(status_lbl)

        # Tiempo
        ts = entry.get("timestamp", "")
        if ts:
            try:
                dt = datetime.fromisoformat(ts)
                time_str = dt.strftime("%d/%m %H:%M")
            except Exception:
                time_str = ts[:16]
            time_lbl = QLabel(time_str)
            time_lbl.setStyleSheet("font-size: 10px; color: #94A3B8;")
            row.addWidget(time_lbl)

        return w

    def _build_news_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        card.setStyleSheet(
            "QFrame#card { "
            "background: qlineargradient(x1:0, y1:0, x2:1, y2:1, "
            "stop:0 #F8F7FF, stop:1 #EEF2FF); "
            "border-radius: 16px; border: 1.5px solid #E0E7FF; }"
        )
        lay = QVBoxLayout(card)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(12)

        hdr = QLabel("✨  Qué podés hacer")
        hdr.setStyleSheet("font-size: 13px; font-weight: 700; color: #4F46E5;")
        lay.addWidget(hdr)

        for icon_title, body in NEWS_TIPS:
            tip_card = QFrame()
            tip_card.setStyleSheet(
                "QFrame { background: white; border-radius: 10px; border: none; }"
            )
            tip_lay = QVBoxLayout(tip_card)
            tip_lay.setContentsMargins(10, 8, 10, 8)
            tip_lay.setSpacing(2)

            title_lbl = QLabel(icon_title)
            title_lbl.setStyleSheet(
                "font-size: 11px; font-weight: 700; color: #1E293B; background: transparent;"
            )
            tip_lay.addWidget(title_lbl)

            body_lbl = QLabel(body)
            body_lbl.setStyleSheet(
                "font-size: 10px; color: #64748B; background: transparent;"
            )
            body_lbl.setWordWrap(True)
            tip_lay.addWidget(body_lbl)

            lay.addWidget(tip_card)

        lay.addStretch()
        return card

    # ── Helper ────────────────────────────────────────────────────────

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "font-size: 10px; font-weight: 700; color: #94A3B8; "
            "letter-spacing: 2px; background: transparent;"
        )
        return lbl
