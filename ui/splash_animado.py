"""
splash_animado.py — Pantalla de inicio animada de Navaja.

Se dibuja cuadro a cuadro con QPainter (no hace falta ningún video ni GIF):

  * la tarjeta aparece con un fundido y un leve acercamiento;
  * el logo sube a su lugar y se enfoca;
  * un brillo cruza el logo en diagonal (sólo sobre el dibujo, no sobre el
    fondo) y vuelve a pasar cada tanto mientras carga;
  * detrás del logo late un halo celeste y gira un arco fino;
  * abajo, el nombre, la versión, el mensaje de carga y una barra que avanza
    con cada etapa real del arranque.

Todo se calcula con el reloj, no contando cuadros: si el arranque bloquea el
hilo un momento (armar la ventana principal tarda), al volver la animación
sigue en el punto que corresponde en vez de atrasarse.

Si en Windows están desactivadas las animaciones (Accesibilidad → Efectos de
animación), la pantalla se muestra quieta, ya en su estado final.
"""

import math
import time

from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF, QEventLoop
from PyQt6.QtGui import (
    QPainter, QPixmap, QColor, QLinearGradient, QRadialGradient, QFont,
    QPen, QPainterPath, QGuiApplication,
)
from PyQt6.QtWidgets import QWidget, QApplication


# ── Paleta (la del logo) ───────────────────────────────────────────
_FONDO_ARRIBA = QColor("#151b40")
_FONDO_ABAJO  = QColor("#0a0d22")
_CELESTE      = QColor("#22d3ee")
_AZUL         = QColor("#3b82f6")
_TEXTO        = QColor("#f1f5f9")
_TEXTO_SUAVE  = QColor("#93a4c8")

# ── Medidas ───────────────────────────────────────────────────────────
_ANCHO, _ALTO = 440, 520
_LOGO_ALTO    = 300
_RADIO        = 20

# ── Tiempos (ms) ──────────────────────────────────────────────────────
_T_TARJETA = 380          # fundido de la tarjeta
_T_LOGO_0  = 120          # el logo empieza a subir
_T_LOGO    = 650          # duración de la subida
_T_BRILLO  = 850          # primer brillo
_DUR_BRILLO = 900
_CADA_BRILLO = 3200       # se repite mientras siga cargando
_T_SALIDA  = 260          # fundido de salida


def _animaciones_activas() -> bool:
    """Respeta 'Efectos de animación' de Windows (SPI_GETCLIENTAREAANIMATION)."""
    try:
        import ctypes
        valor = ctypes.c_bool(True)
        if ctypes.windll.user32.SystemParametersInfoW(0x1042, 0,
                                                     ctypes.byref(valor), 0):
            return bool(valor.value)
    except Exception:
        pass
    return True


def _sube(x: float) -> float:
    """Ease-out cúbico: arranca rápido y se asienta suave."""
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def _rebote(x: float) -> float:
    """Ease-out con un pasito de más (back), para el acercamiento del logo."""
    x = max(0.0, min(1.0, x))
    c = 1.4
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


class AnimatedSplash(QWidget):
    """Pantalla de inicio animada.

    Uso:
        splash = AnimatedSplash(logo_path, "Navaja", version)
        splash.start()
        splash.step("Cargando motores…", 0.3)
        ...
        splash.finish(window)
    """

    def __init__(self, logo_path: str = "", titulo: str = "",
                 version: str = ""):
        super().__init__(None, Qt.WindowType.SplashScreen
                         | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setFixedSize(_ANCHO, _ALTO)

        self._titulo   = titulo
        self._version  = version
        self._mensaje  = ""
        self._meta     = 0.0      # progreso pedido (0–1)
        self._barra    = 0.0      # progreso dibujado (persigue a la meta)
        self._t0       = time.monotonic()
        self._ultimo   = self._t0
        self._salida_t = None     # cuándo empezó el fundido de salida
        self._animar   = _animaciones_activas()

        self._logo = self._cargar_logo(logo_path)

        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._tic)

        # Centrada en la pantalla donde está el mouse.
        pantalla = QGuiApplication.screenAt(self.cursor().pos()) \
            or QGuiApplication.primaryScreen()
        if pantalla:
            g = pantalla.availableGeometry()
            self.move(g.center().x() - _ANCHO // 2,
                      g.center().y() - _ALTO // 2)

    # ── API ──────────────────────────────────────────────────────────
    def start(self):
        self._t0 = self._ultimo = time.monotonic()
        self.show()
        self.raise_()
        if self._animar:
            self._timer.start(16)
        self.pump()

    def step(self, mensaje: str, progreso: float):
        """Cambia el mensaje y la meta de la barra, y repinta."""
        self._mensaje = mensaje
        self._meta = max(self._meta, min(1.0, progreso))
        if not self._animar:
            self._barra = self._meta
        self.pump()

    def pump(self):
        """Deja que Qt pinte el cuadro que toca (llamar entre tareas largas)."""
        self.update()
        QApplication.processEvents()

    def elapsed_ms(self) -> int:
        return int((time.monotonic() - self._t0) * 1000)

    def wait(self, ms: int):
        """Espera animando (el event loop sigue vivo)."""
        if ms <= 0:
            return
        bucle = QEventLoop()
        QTimer.singleShot(int(ms), bucle.quit)
        bucle.exec()

    def wait_until(self, ms_total: int):
        """Espera hasta que la pantalla lleve ms_total en pantalla."""
        self.wait(ms_total - self.elapsed_ms())

    def finish(self, ventana=None):
        """Completa la barra, muestra la ventana y se desvanece encima."""
        self._meta = 1.0
        if self._animar:
            # Que la barra llegue al final antes de irse.
            limite = time.monotonic() + 0.35
            while self._barra < 0.995 and time.monotonic() < limite:
                self.wait(16)
        if ventana is not None:
            ventana.showMaximized()
            self.raise_()
        if not self._animar:
            self.close()
            return
        self._salida_t = time.monotonic()
        self.wait(_T_SALIDA + 30)
        self._timer.stop()
        self.close()

    # ── Interno ──────────────────────────────────────────────────────
    def _cargar_logo(self, ruta: str):
        if not ruta:
            return None
        px = QPixmap(ruta)
        if px.isNull():
            return None
        dpr = self.devicePixelRatioF() or 1.0
        px = px.scaledToHeight(int(_LOGO_ALTO * dpr),
                               Qt.TransformationMode.SmoothTransformation)
        px.setDevicePixelRatio(dpr)
        return px

    def _tic(self):
        ahora = time.monotonic()
        dt = ahora - self._ultimo
        self._ultimo = ahora
        # La barra persigue a la meta con un resorte suave (independiente
        # de los cuadros por segundo).
        self._barra += (self._meta - self._barra) * (1 - math.exp(-dt * 7.0))
        if self._salida_t is not None:
            op = 1 - _sube((ahora - self._salida_t) * 1000 / _T_SALIDA)
            self.setWindowOpacity(max(0.0, op))
        self.update()

    def _t(self) -> float:
        """Milisegundos de animación (en reposo si están desactivadas)."""
        if not self._animar:
            return 10_000.0
        return (time.monotonic() - self._t0) * 1000

    # ── Dibujo ───────────────────────────────────────────────────────
    def paintEvent(self, _ev):
        t = self._t()
        p = QPainter(self)
        p.setRenderHints(QPainter.RenderHint.Antialiasing
                         | QPainter.RenderHint.SmoothPixmapTransform
                         | QPainter.RenderHint.TextAntialiasing)

        # Tarjeta: fundido + acercamiento leve.
        a = _sube(t / _T_TARJETA)
        esc = 0.965 + 0.035 * a
        p.setOpacity(a)
        p.translate(_ANCHO / 2, _ALTO / 2)
        p.scale(esc, esc)
        p.translate(-_ANCHO / 2, -_ALTO / 2)

        self._dibujar_tarjeta(p)

        centro = QPointF(_ANCHO / 2, 40 + _LOGO_ALTO / 2)
        self._dibujar_halo(p, t, centro)
        self._dibujar_logo(p, t, centro)
        self._dibujar_textos(p, t)
        self._dibujar_barra(p, t)
        p.end()

    def _dibujar_tarjeta(self, p: QPainter):
        r = QRectF(1, 1, _ANCHO - 2, _ALTO - 2)
        camino = QPainterPath()
        camino.addRoundedRect(r, _RADIO, _RADIO)
        fondo = QLinearGradient(0, 0, 0, _ALTO)
        fondo.setColorAt(0, _FONDO_ARRIBA)
        fondo.setColorAt(1, _FONDO_ABAJO)
        p.fillPath(camino, fondo)
        borde = QColor(_CELESTE)
        borde.setAlpha(55)
        p.setPen(QPen(borde, 1.2))
        p.drawPath(camino)
        p.setClipPath(camino)

    def _dibujar_halo(self, p: QPainter, t: float, c: QPointF):
        aparece = _sube((t - 250) / 700)
        if aparece <= 0:
            return
        late = 0.5 + 0.5 * math.sin(t / 650)
        radio = _LOGO_ALTO * (0.52 + 0.04 * late)
        g = QRadialGradient(c, radio)
        col = QColor(_CELESTE)
        col.setAlpha(int((38 + 34 * late) * aparece))
        g.setColorAt(0, col)
        col2 = QColor(_AZUL)
        col2.setAlpha(int(18 * aparece))
        g.setColorAt(0.55, col2)
        g.setColorAt(1, QColor(0, 0, 0, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(g)
        p.drawEllipse(c, radio, radio)

        # Arco fino que gira alrededor del logo.
        r = _LOGO_ALTO * 0.56
        caja = QRectF(c.x() - r, c.y() - r, 2 * r, 2 * r)
        ang = int(-(t / 2400) * 360 * 16) % (360 * 16)
        for desfase, alfa in ((0, 150), (180 * 16, 70)):
            col = QColor(_CELESTE)
            col.setAlpha(int(alfa * aparece))
            pen = QPen(col, 2.0)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawArc(caja, ang + desfase, 70 * 16)

    def _dibujar_logo(self, p: QPainter, t: float, c: QPointF):
        if self._logo is None:
            return
        x = (t - _T_LOGO_0) / _T_LOGO
        if x <= 0:
            return
        op = _sube(x)
        esc = 0.9 + 0.1 * _rebote(x)
        dy = 18 * (1 - _sube(x))

        logo = self._con_brillo(t)
        w = logo.width() / logo.devicePixelRatio()
        h = logo.height() / logo.devicePixelRatio()

        p.save()
        p.setOpacity(p.opacity() * op)
        p.translate(c.x(), c.y() + dy)
        p.scale(esc, esc)
        p.drawPixmap(QRectF(-w / 2, -h / 2, w, h), logo,
                     QRectF(0, 0, logo.width(), logo.height()))
        p.restore()

    def _con_brillo(self, t: float) -> QPixmap:
        """El logo con la franja de luz encima, recortada al dibujo."""
        if t < _T_BRILLO:
            return self._logo
        fase = ((t - _T_BRILLO) % _CADA_BRILLO) / _DUR_BRILLO
        if fase >= 1:
            return self._logo

        px = QPixmap(self._logo)
        dpr = px.devicePixelRatio()
        w = px.width() / dpr
        h = px.height() / dpr
        q = QPainter(px)
        q.setRenderHint(QPainter.RenderHint.Antialiasing)
        # SourceAtop: la luz sólo queda donde el logo tiene dibujo.
        q.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceAtop)
        recorrido = w + h
        x = -h + recorrido * _sube(fase) if fase < 1 else w
        g = QLinearGradient(x, 0, x + h * 0.55, h * 0.55)
        g.setColorAt(0.0, QColor(255, 255, 255, 0))
        g.setColorAt(0.5, QColor(255, 255, 255, 120))
        g.setColorAt(1.0, QColor(255, 255, 255, 0))
        q.fillRect(QRectF(0, 0, w, h), g)
        q.end()
        return px

    def _dibujar_textos(self, p: QPainter, t: float):
        y0 = 40 + _LOGO_ALTO + 26
        op = _sube((t - 450) / 500)
        if op <= 0:
            return
        p.save()
        p.setOpacity(p.opacity() * op)
        dy = 8 * (1 - op)

        f = QFont("Segoe UI", 15)
        f.setWeight(QFont.Weight.DemiBold)
        f.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 101)
        p.setFont(f)
        p.setPen(_TEXTO)
        p.drawText(QRectF(0, y0 + dy, _ANCHO, 28),
                   Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                   self._titulo)

        if self._version:
            f2 = QFont("Segoe UI", 9)
            p.setFont(f2)
            p.setPen(_TEXTO_SUAVE)
            p.drawText(QRectF(0, y0 + 28 + dy, _ANCHO, 18),
                       Qt.AlignmentFlag.AlignHCenter, f"Versión {self._version}")

        if self._mensaje:
            f3 = QFont("Segoe UI", 9)
            p.setFont(f3)
            col = QColor(_CELESTE)
            col.setAlpha(220)
            p.setPen(col)
            p.drawText(QRectF(24, _ALTO - 62, _ANCHO - 48, 18),
                       Qt.AlignmentFlag.AlignHCenter, self._mensaje)
        p.restore()

    def _dibujar_barra(self, p: QPainter, t: float):
        op = _sube((t - 450) / 500)
        if op <= 0:
            return
        p.save()
        p.setOpacity(p.opacity() * op)
        ancho = 220
        caja = QRectF((_ANCHO - ancho) / 2, _ALTO - 36, ancho, 4)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 22))
        p.drawRoundedRect(caja, 2, 2)

        lleno = QRectF(caja.x(), caja.y(), max(4.0, ancho * self._barra), 4)
        g = QLinearGradient(caja.x(), 0, caja.x() + ancho, 0)
        g.setColorAt(0, _AZUL)
        g.setColorAt(1, _CELESTE)
        p.setBrush(g)
        p.drawRoundedRect(lleno, 2, 2)

        # Reflejo que recorre la parte llena: indica que sigue trabajando.
        if self._animar and lleno.width() > 12:
            fase = (t % 1400) / 1400
            cx = lleno.x() + lleno.width() * fase
            r = QLinearGradient(cx - 24, 0, cx + 24, 0)
            r.setColorAt(0, QColor(255, 255, 255, 0))
            r.setColorAt(0.5, QColor(255, 255, 255, 150))
            r.setColorAt(1, QColor(255, 255, 255, 0))
            p.setClipRect(lleno)
            p.setBrush(r)
            p.drawRoundedRect(lleno, 2, 2)
        p.restore()
