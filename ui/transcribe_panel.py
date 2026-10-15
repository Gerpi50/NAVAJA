"""
ui/transcribe_panel.py — Panel «Transcribir»: pasa a texto lo que se dice en
un audio o en un video, y permite revisarlo escuchando.

Es la misma forma de trabajar que la de un editor de subtítulos
(y el mismo motor, Whisper): se transcribe, y después se escucha y se corrige
tramo por tramo, con la velocidad que haga falta, marcando lo ya revisado.
La diferencia es que acá una grabación puede ser larga: la lista de la
izquierda no son audios sino los tramos de la grabación, cada uno con su
minuto y segundo, y el que está sonando queda resaltado.

El reproductor está a la vista desde que se elige el archivo: se puede
escuchar antes de transcribir y mientras se transcribe, y lo que ya salió se
corrige sin esperar a que termine el resto de la tanda.

Está en los módulos Audio y Video. El trabajo se guarda solo: si se cierra el
programa, al volver a elegir el mismo archivo se sigue donde se dejó.
"""
import os
import platform
import re
import subprocess

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSlider,
    QComboBox, QProgressBar, QFileDialog, QFrame, QMessageBox, QListWidget,
    QListWidgetItem, QPlainTextEdit, QCheckBox, QSplitter, QDialog,
    QDialogButtonBox, QFormLayout, QLineEdit,
)
from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QKeySequence, QShortcut

from ui.informe_widget import InformeSection
from core.salidas import carpeta_destino
from core.paths import TEMP_DIR
from motors import motor_transcribe as mt
from motors import motor_voces as mv
from motors.motor_audio_enhance import EXT_AUDIO, EXT_VIDEO

VELOCIDADES = (
    ("0,5×", 0.5), ("0,75×", 0.75), ("Normal", 1.0),
    ("1,25×", 1.25), ("1,5×", 1.5), ("1,75×", 1.75), ("2×", 2.0),
)
SALTO_MS = 10_000

_COLOR_SONANDO = QColor("#fde68a")      # el tramo que se está escuchando


def _filtro_archivos() -> str:
    audio = " ".join(f"*{e}" for e in sorted(EXT_AUDIO))
    video = " ".join(f"*{e}" for e in sorted(EXT_VIDEO))
    return (f"Audio y video ({audio} {video});;Audio ({audio});;"
            f"Video ({video});;Todos los archivos (*.*)")


def _orden_natural(ruta: str) -> list:
    """Para ordenar «audio 2» antes que «audio 10»."""
    return [int(parte) if parte.isdigit() else parte
            for parte in re.split(r"(\d+)", os.path.basename(ruta).lower())]


# ── Workers ───────────────────────────────────────────────────────────────

class _TandaWorker(QThread):
    """Transcribe uno o varios archivos, con el modelo cargado una sola vez."""
    empieza   = pyqtSignal(int)         # arranca el archivo de ese índice
    progreso  = pyqtSignal(float)       # de 0 a 1, del archivo en curso
    aviso     = pyqtSignal(str)
    tramos    = pyqtSignal(int, list)   # lo que va entendiendo
    hecho     = pyqtSignal(int, dict)
    fallo     = pyqtSignal(int, str)    # ese archivo no se pudo; sigue
    terminado = pyqtSignal()
    cancelado = pyqtSignal()
    error     = pyqtSignal(str)         # no se pudo ni empezar

    def __init__(self, pendientes, modelo, dispositivo, personas=None):
        super().__init__()
        self.pendientes = pendientes    # [(índice, origen, wav)]
        self.modelo, self.dispositivo = modelo, dispositivo
        self.personas = personas    # None = no reconocer; 0 = que descubra
        self._cortar = False

    def cancelar(self):
        self._cortar = True

    def _uno(self, sesion, indice, src, wav) -> dict:
        from core.informe import sha256_file
        if not os.path.isfile(wav):
            self.aviso.emit("Leyendo el audio del archivo…")
            mt.extraer_audio(src, wav)
        self.aviso.emit("Calculando el hash del archivo…")
        huella, peso = sha256_file(src), os.path.getsize(src)
        if self._cortar:
            raise mt.Cancelado()
        self.aviso.emit("Transcribiendo…")
        resultado = sesion.transcribir(
            wav, progreso_cb=self.progreso.emit,
            cancel_cb=lambda: self._cortar,
            tramos_cb=lambda nuevos: self.tramos.emit(indice, nuevos))
        resultado.update(sha256=huella, tamano=peso)
        if self.personas is not None and resultado["tramos"]:
            # Si esto falla, la transcripción igual sirve.
            try:
                self.aviso.emit("Reconociendo quién habla…")
                self.progreso.emit(0.0)
                turnos = mv.reconocer(wav, self.personas,
                                      progreso_cb=self.progreso.emit)
                resultado["personas"] = mv.asignar(resultado["tramos"], turnos)
            except Exception as e:
                resultado["aviso_voces"] = str(e)
        return resultado

    def run(self):
        sesion = None
        try:
            sesion = mt.Sesion(self.modelo, self.dispositivo, self.aviso.emit)
            for indice, src, wav in self.pendientes:
                if self._cortar:
                    raise mt.Cancelado()
                self.empieza.emit(indice)
                try:
                    resultado = self._uno(sesion, indice, src, wav)
                except mt.Cancelado:
                    raise
                except Exception as e:
                    self.fallo.emit(indice, str(e))
                    continue
                self.hecho.emit(indice, resultado)
            self.terminado.emit()
        except mt.Cancelado:
            self.cancelado.emit()
        except Exception as e:
            self.error.emit(str(e))
        finally:
            if sesion is not None:
                try:
                    sesion.cerrar()
                except Exception:
                    pass


class _VocesWorker(QThread):
    """Reconoce quién habla en una transcripción que ya está hecha."""
    progreso = pyqtSignal(float)
    listo    = pyqtSignal(list)
    error    = pyqtSignal(str)

    def __init__(self, wav, personas):
        super().__init__()
        self.wav, self.personas = wav, personas

    def run(self):
        try:
            self.listo.emit(mv.reconocer(self.wav, self.personas,
                                         progreso_cb=self.progreso.emit))
        except Exception as e:
            self.error.emit(str(e))


class _NombresDialog(QDialog):
    """Para ponerle nombre a cada participante."""

    def __init__(self, nombres: list, ejemplos: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nombres de los participantes")
        self.setMinimumWidth(520)
        lay = QVBoxLayout(self)
        ayuda = QLabel(
            "Poné el nombre o el rol de cada uno (por ejemplo «Entrevistadora» "
            "y «Niña»). Así sale escrito en la transcripción.")
        ayuda.setWordWrap(True)
        lay.addWidget(ayuda)
        form = QFormLayout()
        self._campos = []
        for nombre, ejemplo in zip(nombres, ejemplos):
            campo = QLineEdit(nombre)
            campo.selectAll()
            pista = QLabel(f"Dice, por ejemplo: «{ejemplo}»" if ejemplo
                           else "No tiene ningún tramo asignado.")
            pista.setWordWrap(True)
            pista.setStyleSheet("font-size: 11px; color: #64748b;")
            caja = QVBoxLayout()
            caja.addWidget(campo)
            caja.addWidget(pista)
            form.addRow(f"{nombre}:", caja)
            self._campos.append(campo)
        lay.addLayout(form)
        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                   | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        lay.addWidget(botones)

    def nombres(self) -> list:
        return [c.text().strip() for c in self._campos]


class _AudioWorker(QThread):
    """Prepara el audio para escuchar (al retomar un trabajo guardado)."""
    listo = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, src, wav):
        super().__init__()
        self.src, self.wav = src, wav

    def run(self):
        try:
            self.listo.emit(mt.extraer_audio(self.src, self.wav))
        except Exception as e:
            self.error.emit(str(e))


class _GuardarWorker(QThread):
    """Escribe el informe (o los subtítulos) y arma la constancia técnica.

    Va aparte porque hace falta el hash de cada archivo, y con un video de
    varios GB calcularlo lleva su tiempo.
    """
    aviso = pyqtSignal(str)
    listo = pyqtSignal(list, str)       # archivos escritos, constancia
    error = pyqtSignal(str)

    def __init__(self, registros, ruta, con_tiempos, carpeta, parametros):
        super().__init__()
        self.registros, self.ruta = registros, ruta
        self.con_tiempos, self.carpeta = con_tiempos, carpeta
        self.parametros = parametros

    def run(self):
        from core.informe import build_informe, file_info, sha256_file
        try:
            for r in self.registros:
                if not r.get("sha256"):
                    self.aviso.emit("Calculando el hash de "
                                    f"«{os.path.basename(r['src'])}»…")
                    r["sha256"] = sha256_file(r["src"])
                    r["tamano"] = os.path.getsize(r["src"])
            self.aviso.emit("Escribiendo…")
            escritos = []
            if self.ruta.lower().endswith(".srt"):
                # Los subtítulos van de a uno por grabación.
                carpeta = os.path.dirname(self.ruta)
                for r in self.registros:
                    destino = self.ruta if len(self.registros) == 1 else \
                        os.path.join(carpeta, os.path.splitext(
                            os.path.basename(r["src"]))[0] + ".srt")
                    escritos.append(mt.guardar(
                        r["tramos"], destino, True, nombres=r["nombres"]))
            else:
                escritos.append(mt.guardar_informe(
                    [dict(r, nombre=os.path.basename(r["src"]))
                     for r in self.registros],
                    self.ruta, self.con_tiempos, self.carpeta))
        except Exception as e:
            self.error.emit(str(e))
            return
        constancia = ""
        try:
            hay_video = any(r["es_video"] for r in self.registros)
            hay_audio = any(not r["es_video"] for r in self.registros)
            constancia = build_informe(
                accion="transcribir lo que se dice en",
                originals=[{"filename": os.path.basename(r["src"]),
                            "sha256": r["sha256"],
                            "size_mb": r["tamano"] / (1024 * 1024)}
                           for r in self.registros],
                results=[file_info(p) for p in escritos],
                objeto=("archivo de audio o video" if hay_video and hay_audio
                        else "archivo de video" if hay_video
                        else "archivo de audio"),
                parametros=self.parametros,
                extra_lines=(
                    "La transcripción fue hecha por reconocimiento automático "
                    "de voz y revisada escuchando la grabación. Los archivos "
                    "originales no fueron modificados."),
            )
        except Exception:
            pass
        self.listo.emit(escritos, constancia)


# ── Panel ─────────────────────────────────────────────────────────────────

class TranscribePanel(QWidget):
    """Transcribir un audio o un video y revisarlo escuchando."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(620)
        # Los archivos elegidos (uno, varios o una carpeta). Cada uno:
        # {"src","es_video","duracion","wav","estado","error","tramos",
        #  "nombres","modelo","sha256","tamano","fila"}; los tramos son
        # {"inicio","fin","texto","original","revisado","persona"}.
        self._archivos = []
        self._actual = -1           # el que se está revisando
        self._carpeta = ""          # nombre de la carpeta, si se eligió una
        self._voces_worker = None
        self._worker = None
        self._audio_worker = None
        self._guardar_worker = None
        self._en_curso = -1         # el que se está transcribiendo
        self._tanda = []            # los que entran en la transcripción
        self._tanda_listos = set()  # de ésos, los que ya salieron
        self._resumen = ""
        self._fila = -1             # tramo que se está corrigiendo
        self._sonando = -1          # tramo que está sonando
        self._arrastrando = False
        self._cargando_texto = False
        self._reproductor = None
        self._dispositivo_visto = False
        self._last_out = ""
        self._setup_ui()

    # ── El archivo que se está revisando ─────────────────────────────────
    # El resto del panel trabaja sobre «el archivo actual» con estos nombres.
    def _reg(self):
        if 0 <= self._actual < len(self._archivos):
            return self._archivos[self._actual]
        return None

    @property
    def _src_path(self) -> str:
        r = self._reg()
        return r["src"] if r else ""

    @property
    def _wav(self) -> str:
        r = self._reg()
        return r["wav"] if r else ""

    @property
    def _es_video(self) -> bool:
        r = self._reg()
        return bool(r and r["es_video"])

    @property
    def _tramos(self) -> list:
        r = self._reg()
        return r["tramos"] if r else []

    @_tramos.setter
    def _tramos(self, valor):
        r = self._reg()
        if r is not None:
            r["tramos"] = valor

    @property
    def _nombres(self) -> list:
        r = self._reg()
        return r["nombres"] if r else []

    @_nombres.setter
    def _nombres(self, valor):
        r = self._reg()
        if r is not None:
            r["nombres"] = valor

    def _hechos(self) -> list:
        return [r for r in self._archivos if r["estado"] == "hecho"]

    # ── Construcción ─────────────────────────────────────────────────────
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        hdr = QLabel("🎙  Transcribir")
        hdr.setStyleSheet("font-size: 16px; font-weight: 800;")
        layout.addWidget(hdr)

        sub = QLabel(
            "Pasa a texto lo que se dice en un audio o en un video. Después "
            "podés escucharlo tramo por tramo, a la velocidad que quieras, y "
            "corregir lo que haya entendido mal. Funciona sin internet y el "
            "archivo original no se toca.")
        sub.setStyleSheet("font-size: 11px; color: #64748b;")
        sub.setWordWrap(True)
        layout.addWidget(sub)

        motivo = mt.motivo_no_disponible()
        if motivo:
            warn = QLabel("⚠️  " + motivo)
            warn.setStyleSheet(
                "background: #fffbeb; border: 1px solid #f59e0b; "
                "border-radius: 6px; padding: 10px; color: #92400e;")
            warn.setWordWrap(True)
            layout.addWidget(warn)
            layout.addStretch()
            self._sin_motor = True
            return
        self._sin_motor = False

        # ── Archivo y opciones ───────────────────────────────────────────
        card1 = QFrame()
        card1.setObjectName("card")
        c1 = QVBoxLayout(card1)
        c1.setContentsMargins(12, 10, 12, 10)
        c1.setSpacing(8)

        fila = QHBoxLayout()
        self.lbl_file = QLabel("No se eligió ningún archivo")
        self.lbl_file.setStyleSheet("font-size: 11px; color: #64748b;")
        self.lbl_file.setWordWrap(True)
        fila.addWidget(self.lbl_file, stretch=1)
        btn_pick = QPushButton("📁 Elegir archivos")
        btn_pick.setObjectName("ghostBtn")
        btn_pick.setToolTip(
            "Un audio o un video, o varios a la vez (con Ctrl o Shift).")
        btn_pick.clicked.connect(self._elegir)
        fila.addWidget(btn_pick)
        btn_carpeta = QPushButton("📂 Elegir carpeta")
        btn_carpeta.setObjectName("ghostBtn")
        btn_carpeta.setToolTip(
            "Todos los audios y videos que haya en una carpeta, por ejemplo "
            "las notas de voz de un chat.")
        btn_carpeta.clicked.connect(self._elegir_carpeta)
        fila.addWidget(btn_carpeta)
        btn_limpiar = QPushButton("🗑 Limpiar")
        btn_limpiar.setObjectName("ghostBtn")
        btn_limpiar.setToolTip(
            "Deja la solapa como recién abierta, para empezar con otros "
            "archivos.\nNo borra nada del disco: lo corregido queda guardado "
            "y vuelve al elegir el mismo archivo.")
        btn_limpiar.clicked.connect(self._limpiar)
        fila.addWidget(btn_limpiar)
        c1.addLayout(fila)

        op = QHBoxLayout()
        op.addWidget(QLabel("Modelo:"))
        self.combo_modelo = QComboBox()
        self.combo_modelo.setToolTip(
            "«Medio» es el recomendado. «Turbo» tarda bastante menos con casi "
            "la misma precisión: conviene en grabaciones largas.")
        for nombre, etiqueta, esta in mt.modelos_disponibles():
            self.combo_modelo.addItem(
                etiqueta if esta else f"{etiqueta}  (no está en este equipo)",
                nombre)
            if not esta:
                indice = self.combo_modelo.count() - 1
                self.combo_modelo.model().item(indice).setEnabled(False)
        # Viene elegido el que le conviene a esta PC (Chico si tiene poca
        # memoria), siempre que esté en el equipo.
        for candidato in (mt.modelo_sugerido(), mt.MODELO_POR_DEFECTO, "small"):
            idx = self.combo_modelo.findData(candidato)
            if idx >= 0 and self.combo_modelo.model().item(idx).isEnabled():
                self.combo_modelo.setCurrentIndex(idx)
                break
        self.combo_modelo.currentIndexChanged.connect(self._ver_dispositivo)
        op.addWidget(self.combo_modelo, stretch=1)
        op.addSpacing(10)
        op.addWidget(QLabel("Transcribir con:"))
        self.combo_disp = QComboBox()
        for clave, etiqueta in mt.DISPOSITIVOS:
            self.combo_disp.addItem(etiqueta, clave)
        self.combo_disp.currentIndexChanged.connect(self._ver_dispositivo)
        op.addWidget(self.combo_disp)
        c1.addLayout(op)

        self.lbl_disp = QLabel("")
        self.lbl_disp.setStyleSheet("font-size: 11px; color: #64748b;")
        self.lbl_disp.setWordWrap(True)
        c1.addWidget(self.lbl_disp)

        quien = QHBoxLayout()
        self.chk_voces = QCheckBox("Reconocer quién habla")
        self.chk_voces.setToolTip(
            "Separa las voces y le pone a cada tramo quién lo dice "
            "(«Interlocutor 1», «Interlocutor 2»…); después podés ponerles "
            "el nombre.\n"
            "No reconoce a nadie por su identidad: sólo distingue voces. "
            "Se puede equivocar si las voces se parecen o si hablan a la vez, "
            "y se corrige tramo por tramo.")
        quien.addWidget(self.chk_voces)
        quien.addSpacing(10)
        quien.addWidget(QLabel("¿Cuántos hablan?"))
        self.combo_personas = QComboBox()
        for cantidad, etiqueta in mv.CANTIDADES:
            self.combo_personas.addItem(etiqueta, cantidad)
        self.combo_personas.setCurrentIndex(
            max(0, self.combo_personas.findData(mv.CANTIDAD_POR_DEFECTO)))
        self.combo_personas.setToolTip(
            "Si sabés cuántas personas hablan, decilo: acierta bastante más "
            "que dejando que lo descubra solo.")
        quien.addWidget(self.combo_personas)
        quien.addStretch()
        c1.addLayout(quien)
        self._sin_voces = mv.motivo_no_disponible()
        if self._sin_voces:
            self.chk_voces.setEnabled(False)
            self.combo_personas.setEnabled(False)
            self.chk_voces.setToolTip(self._sin_voces)
            # A la vista: una casilla gris sin explicación parece una falla.
            falta = QLabel("⚠️  No se puede reconocer quién habla: "
                           + self._sin_voces)
            falta.setStyleSheet("font-size: 11px; color: #b45309;")
            falta.setWordWrap(True)
            c1.addWidget(falta)
        layout.addWidget(card1)

        accion = QHBoxLayout()
        self.btn_transcribir = QPushButton("🎙  Transcribir")
        self.btn_transcribir.setObjectName("convertBtn")
        self.btn_transcribir.clicked.connect(self._transcribir)
        accion.addWidget(self.btn_transcribir, stretch=1)
        self.btn_cancelar = QPushButton("Cancelar")
        self.btn_cancelar.setObjectName("ghostBtn")
        self.btn_cancelar.setVisible(False)
        self.btn_cancelar.clicked.connect(self._cancelar)
        accion.addWidget(self.btn_cancelar)
        layout.addLayout(accion)

        self.pbar = QProgressBar()
        self.pbar.setVisible(False)
        layout.addWidget(self.pbar)

        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("font-size: 11px; color: #475569;")
        self.lbl_status.setWordWrap(True)
        layout.addWidget(self.lbl_status)

        # ── Lo que va transcribiendo ─────────────────────────────────────
        self.caja_vivo = QFrame()
        self.caja_vivo.setObjectName("card")
        cv = QVBoxLayout(self.caja_vivo)
        cv.setContentsMargins(12, 10, 12, 10)
        cv.setSpacing(6)
        cv.addWidget(QLabel("Lo que va transcribiendo"))
        self.vivo = QPlainTextEdit()
        self.vivo.setReadOnly(True)
        self.vivo.setStyleSheet(
            "QPlainTextEdit { background: #ffffff; color: #0f172a; "
            "border: 1px solid #cbd5e1; border-radius: 8px; padding: 10px; "
            "font-family: 'Segoe UI', Arial, sans-serif; font-size: 11pt; }")
        self.vivo.setMinimumHeight(80)
        self.vivo.setMaximumHeight(120)
        cv.addWidget(self.vivo)
        nota = QLabel("Es lo que entiende a medida que avanza. Abajo podés ir "
                      "escuchando la grabación, y corrigiendo lo que ya salió.")
        nota.setStyleSheet("font-size: 11px; color: #64748b;")
        cv.addWidget(nota)
        self.caja_vivo.setVisible(False)
        layout.addWidget(self.caja_vivo)

        # ── Revisión ─────────────────────────────────────────────────────
        self.zona = QFrame()
        self.zona.setObjectName("card")
        z = QVBoxLayout(self.zona)
        z.setContentsMargins(12, 10, 12, 10)
        z.setSpacing(8)

        self.fila_archivo = QWidget()
        fa = QHBoxLayout(self.fila_archivo)
        fa.setContentsMargins(0, 0, 0, 0)
        fa.addWidget(QLabel("Archivo:"))
        self.combo_archivo = QComboBox()
        self.combo_archivo.setToolTip(
            "Qué grabación estás escuchando. Mientras se transcribe, las "
            "que todavía no salieron aparecen apagadas.")
        self.combo_archivo.activated.connect(self._cambiar_archivo)
        fa.addWidget(self.combo_archivo, stretch=1)
        self.fila_archivo.setVisible(False)
        z.addWidget(self.fila_archivo)

        self.split = QSplitter(Qt.Orientation.Horizontal)

        izquierda = QWidget()
        il = QVBoxLayout(izquierda)
        il.setContentsMargins(0, 0, 0, 0)
        il.setSpacing(6)
        il.addWidget(QLabel("Tramos de la grabación"))
        self.lista = QListWidget()
        self.lista.setWordWrap(True)
        self.lista.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.lista.setToolTip(
            "Tocá un tramo para ir a ese momento de la grabación.\n"
            "El que está sonando queda resaltado.")
        self.lista.currentRowChanged.connect(self._cambiar_tramo)
        self.lista.itemClicked.connect(self._tramo_tocado)
        il.addWidget(self.lista, stretch=1)
        self.chk_seguir = QCheckBox("La lista sigue al audio mientras suena")
        self.chk_seguir.setChecked(True)
        self.chk_seguir.setToolTip(
            "Mientras escuchás, va pasando sola al tramo que suena.\n"
            "Se frena mientras estás escribiendo una corrección.")
        il.addWidget(self.chk_seguir)
        self.split.addWidget(izquierda)

        derecha = QWidget()
        dl = QVBoxLayout(derecha)
        dl.setContentsMargins(0, 0, 0, 0)
        dl.setSpacing(8)

        cabecera = QHBoxLayout()
        self.lbl_tramo = QLabel("")
        self.lbl_tramo.setStyleSheet("font-size: 13px; font-weight: 700;")
        cabecera.addWidget(self.lbl_tramo)
        cabecera.addStretch()
        self.lbl_habla = QLabel("Habla:")
        cabecera.addWidget(self.lbl_habla)
        self.combo_habla = QComboBox()
        self.combo_habla.setMinimumWidth(170)
        self.combo_habla.setToolTip(
            "Quién dice este tramo. Cambialo si el programa se equivocó.")
        self.combo_habla.currentIndexChanged.connect(self._cambiar_persona)
        cabecera.addWidget(self.combo_habla)
        self.btn_nombres = QPushButton("✏️ Nombres…")
        self.btn_nombres.setObjectName("ghostBtn")
        self.btn_nombres.setToolTip(
            "Ponerle nombre a cada participante (Entrevistadora, Niña…)")
        self.btn_nombres.clicked.connect(self._editar_nombres)
        cabecera.addWidget(self.btn_nombres)
        self.btn_voces = QPushButton("👥 Reconocer quién habla")
        self.btn_voces.setObjectName("ghostBtn")
        self.btn_voces.setToolTip(
            "Separa las voces de esta transcripción, sin transcribir de "
            "nuevo. Usa la cantidad de personas elegida arriba.\n"
            "Si ya estaba hecho, lo hace otra vez y pisa lo corregido a mano.")
        self.btn_voces.clicked.connect(self._reconocer_voces)
        cabecera.addWidget(self.btn_voces)
        dl.addLayout(cabecera)

        controles = QHBoxLayout()
        controles.setSpacing(6)
        self.btn_atras = QPushButton("◀◀  10 s")
        self.btn_atras.setToolTip("Retroceder 10 segundos (Ctrl + ←)")
        self.btn_atras.clicked.connect(lambda: self._saltar(-SALTO_MS))
        controles.addWidget(self.btn_atras)
        self.btn_play = QPushButton("▶  Escuchar")
        self.btn_play.setObjectName("primaryBtn")
        self.btn_play.setToolTip("Reproducir o pausar (Ctrl + Espacio)")
        self.btn_play.clicked.connect(self._alternar)
        controles.addWidget(self.btn_play)
        self.btn_adelante = QPushButton("10 s  ▶▶")
        self.btn_adelante.setToolTip("Adelantar 10 segundos (Ctrl + →)")
        self.btn_adelante.clicked.connect(lambda: self._saltar(SALTO_MS))
        controles.addWidget(self.btn_adelante)
        self.btn_repetir = QPushButton("↺  Repetir el tramo")
        self.btn_repetir.setToolTip(
            "Vuelve al principio del tramo que estás corrigiendo y lo "
            "reproduce (Ctrl + R)")
        self.btn_repetir.clicked.connect(self._repetir_tramo)
        controles.addWidget(self.btn_repetir)
        controles.addSpacing(8)
        controles.addWidget(QLabel("Velocidad"))
        self.combo_vel = QComboBox()
        for texto, factor in VELOCIDADES:
            self.combo_vel.addItem(texto, factor)
        self.combo_vel.setCurrentIndex([f for _, f in VELOCIDADES].index(1.0))
        self.combo_vel.setToolTip(
            "Más lento para entender a alguien que habla apurado o bajito;\n"
            "más rápido para repasar una grabación larga.\n"
            "(Ctrl + Shift + ← / →)")
        self.combo_vel.currentIndexChanged.connect(self._cambiar_velocidad)
        controles.addWidget(self.combo_vel)
        controles.addStretch()
        dl.addLayout(controles)

        barra = QHBoxLayout()
        self.lbl_pos = QLabel("00:00")
        self.lbl_pos.setMinimumWidth(56)
        barra.addWidget(self.lbl_pos)
        self.barra_audio = QSlider(Qt.Orientation.Horizontal)
        self.barra_audio.setRange(0, 0)
        self.barra_audio.setPageStep(10000)
        self.barra_audio.setSingleStep(2000)
        self.barra_audio.setToolTip(
            "Arrastrá para ir a cualquier parte de la grabación")
        self.barra_audio.sliderPressed.connect(
            lambda: setattr(self, "_arrastrando", True))
        self.barra_audio.sliderReleased.connect(self._soltar_barra)
        self.barra_audio.sliderMoved.connect(
            lambda v: self.lbl_pos.setText(mt.marca(v / 1000)))
        self.barra_audio.actionTriggered.connect(self._clic_en_barra)
        barra.addWidget(self.barra_audio, stretch=1)
        self.lbl_dur = QLabel("00:00")
        self.lbl_dur.setMinimumWidth(56)
        self.lbl_dur.setAlignment(Qt.AlignmentFlag.AlignRight
                                  | Qt.AlignmentFlag.AlignVCenter)
        barra.addWidget(self.lbl_dur)
        dl.addLayout(barra)

        self.edit = QPlainTextEdit()
        self.edit.setPlaceholderText(
            "Acá aparece el texto del tramo elegido. Lo que corrijas acá es "
            "lo que se guarda.")
        # Hoja clara y letra de lectura: el tema del programa pinta estos
        # cuadros como una consola (fondo oscuro, letra chica).
        self.edit.setStyleSheet(
            "QPlainTextEdit { background: #ffffff; color: #0f172a; "
            "border: 1px solid #cbd5e1; border-radius: 8px; padding: 10px; "
            "font-family: 'Segoe UI', Arial, sans-serif; font-size: 12pt; }"
            "QPlainTextEdit:focus { border: 2px solid #6366f1; }")
        self.edit.setMinimumHeight(120)
        self.edit.textChanged.connect(self._texto_cambiado)
        dl.addWidget(self.edit, stretch=1)

        pie = QHBoxLayout()
        self.chk_revisado = QCheckBox("Ya revisé este tramo")
        self.chk_revisado.setToolTip(
            "Le pone un tilde en la lista, para saber por dónde ibas")
        self.chk_revisado.stateChanged.connect(self._alternar_revisado)
        pie.addWidget(self.chk_revisado)
        self.btn_hasta_aca = QPushButton("✓  Revisado hasta acá")
        self.btn_hasta_aca.setObjectName("ghostBtn")
        self.btn_hasta_aca.setToolTip(
            "Marca como revisados todos los tramos desde el principio hasta "
            "éste:\nasí queda a la vista hasta dónde corregiste.")
        self.btn_hasta_aca.clicked.connect(self._revisado_hasta_aca)
        pie.addWidget(self.btn_hasta_aca)
        self.btn_siguiente = QPushButton("Siguiente sin revisar  →")
        self.btn_siguiente.setObjectName("ghostBtn")
        self.btn_siguiente.clicked.connect(self._siguiente_sin_revisar)
        pie.addWidget(self.btn_siguiente)
        self.btn_restaurar = QPushButton("Restaurar el texto original")
        self.btn_restaurar.setObjectName("ghostBtn")
        self.btn_restaurar.setToolTip(
            "Vuelve este tramo a lo que había entendido el programa")
        self.btn_restaurar.clicked.connect(self._restaurar)
        pie.addWidget(self.btn_restaurar)
        pie.addStretch()
        self.lbl_avance = QLabel("")
        self.lbl_avance.setStyleSheet("font-size: 11px; color: #475569;")
        pie.addWidget(self.lbl_avance)
        dl.addLayout(pie)
        self.split.addWidget(derecha)
        self.split.setStretchFactor(0, 2)
        self.split.setStretchFactor(1, 3)
        z.addWidget(self.split, stretch=1)

        guardar = QHBoxLayout()
        self.chk_tiempos = QCheckBox("Con el minuto y segundo de cada tramo")
        self.chk_tiempos.setChecked(True)
        guardar.addWidget(self.chk_tiempos)
        guardar.addStretch()
        self.btn_copiar = QPushButton("📋 Copiar todo")
        self.btn_copiar.setObjectName("ghostBtn")
        self.btn_copiar.clicked.connect(self._copiar)
        guardar.addWidget(self.btn_copiar)
        self.btn_guardar = QPushButton("💾  Generar el informe…")
        self.btn_guardar.setObjectName("primaryBtn")
        self.btn_guardar.setToolTip(
            "La transcripción de todo lo que elegiste, con el hash SHA-256 "
            "de cada archivo.\nComo documento (.odt o .docx), texto (.txt) o "
            "subtítulos (.srt).")
        self.btn_guardar.clicked.connect(self._guardar)
        guardar.addWidget(self.btn_guardar)
        z.addLayout(guardar)

        self.zona.setVisible(False)
        layout.addWidget(self.zona, stretch=1)

        self.btn_open = QPushButton("📂 Abrir carpeta de resultados")
        self.btn_open.setObjectName("ghostBtn")
        self.btn_open.setVisible(False)
        self.btn_open.clicked.connect(self._abrir_carpeta)
        layout.addWidget(self.btn_open)

        self.informe_section = InformeSection()
        layout.addWidget(self.informe_section)
        layout.addStretch()

        # Atajos, los mismos del generador de informes. Valen sólo acá.
        for secuencia, accion in (
            ("Ctrl+Space", self._alternar),
            ("Ctrl+Left", lambda: self._saltar(-SALTO_MS)),
            ("Ctrl+Right", lambda: self._saltar(SALTO_MS)),
            ("Ctrl+Shift+Left", lambda: self._velocidad_relativa(-1)),
            ("Ctrl+Shift+Right", lambda: self._velocidad_relativa(1)),
            ("Ctrl+R", self._repetir_tramo),
        ):
            atajo = QShortcut(QKeySequence(secuencia), self)
            atajo.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            atajo.activated.connect(accion)

        # Guarda solo un momento después de la última corrección.
        self._guardado = QTimer(self)
        self._guardado.setSingleShot(True)
        self._guardado.setInterval(1500)
        self._guardado.timeout.connect(self._guardar_trabajo)

        self._habilitar()

    # ── Reproductor ──────────────────────────────────────────────────────
    def _player(self):
        """El reproductor de audio, creado al necesitarlo."""
        if self._reproductor is None:
            from transcripcion.reproductor import Reproductor
            self._reproductor = Reproductor()
            self._reproductor.posicion.connect(self._posicion)
            self._reproductor.duracion.connect(self._duracion)
            self._reproductor.sonando.connect(self._estado)
            self._reproductor.poner_velocidad(self.combo_vel.currentData())
        return self._reproductor

    def _cargar_audio(self) -> bool:
        if not self._wav or not os.path.isfile(self._wav):
            return False
        rep = self._player()
        # El WAV ya está hecho: se le avisa para que no lo convierta de nuevo.
        rep._cache[self._wav] = self._wav
        return rep.cargar(self._wav)

    def _alternar(self):
        if self._cargar_audio():
            self._player().alternar(self._wav)

    def _saltar(self, delta_ms: int):
        if self._cargar_audio():
            self._player().saltar(delta_ms)

    def _ir_a(self, segundos: float, reproducir: bool = False):
        if not self._cargar_audio():
            return
        rep = self._player()
        rep.buscar(int(segundos * 1000))
        self._posicion(int(segundos * 1000))
        if reproducir:
            rep.reproducir(self._wav)

    def _repetir_tramo(self):
        if 0 <= self._fila < len(self._tramos):
            self._ir_a(self._tramos[self._fila]["inicio"], reproducir=True)

    def _cambiar_velocidad(self):
        if self._reproductor is not None:
            self._reproductor.poner_velocidad(self.combo_vel.currentData())

    def _velocidad_relativa(self, pasos: int):
        i = self.combo_vel.currentIndex() + pasos
        self.combo_vel.setCurrentIndex(
            max(0, min(self.combo_vel.count() - 1, i)))

    def _soltar_barra(self):
        self._arrastrando = False
        self._ir_a(self.barra_audio.value() / 1000)

    def _clic_en_barra(self, _accion):
        # Un clic sobre la barra (no sobre el punto) también lleva ahí.
        if not self._arrastrando:
            QTimer.singleShot(
                0, lambda: self._ir_a(self.barra_audio.sliderPosition() / 1000))

    def _duracion(self, ms: int):
        self.barra_audio.setRange(0, max(0, ms))
        self.lbl_dur.setText(mt.marca(ms / 1000))

    def _estado(self, sonando: bool):
        self.btn_play.setText("⏸  Pausar" if sonando else "▶  Escuchar")

    def _posicion(self, ms: int):
        if not self._arrastrando:
            self.barra_audio.blockSignals(True)
            self.barra_audio.setValue(ms)
            self.barra_audio.blockSignals(False)
            self.lbl_pos.setText(mt.marca(ms / 1000))
        self._marcar_sonando(self._tramo_en(ms / 1000))

    def _tramo_en(self, segundos: float) -> int:
        """El tramo que corresponde a ese momento (-1 si no hay ninguno)."""
        ultimo = -1
        for i, t in enumerate(self._tramos):
            if t["inicio"] <= segundos + 0.05:
                ultimo = i
            else:
                break
        return ultimo

    def _marcar_sonando(self, fila: int):
        """Resalta en la lista el tramo que está sonando."""
        if fila == self._sonando:
            return
        anterior, self._sonando = self._sonando, fila
        for f, encendido in ((anterior, False), (fila, True)):
            item = self.lista.item(f) if f >= 0 else None
            if item is None:
                continue
            # Parlante adelante y negrita: se ve con cualquier tema (el
            # color de fondo de un renglón lo pisa la hoja de estilos).
            item.setText(self._rotulo(f))
            letra = item.font()
            letra.setBold(encendido)
            item.setFont(letra)
            item.setBackground(QBrush(_COLOR_SONANDO) if encendido else QBrush())
        if fila < 0:
            return
        self.lista.scrollToItem(self.lista.item(fila))
        # La lista sigue al audio, salvo que se esté escribiendo.
        if (self.chk_seguir.isChecked() and not self.edit.hasFocus()
                and fila != self._fila):
            self._siguiendo = True
            self.lista.setCurrentRow(fila)
            self._siguiendo = False

    # ── Archivo ──────────────────────────────────────────────────────────
    def showEvent(self, event):
        super().showEvent(event)
        if not self._sin_motor and not self._dispositivo_visto:
            self._dispositivo_visto = True
            QTimer.singleShot(200, self._ver_dispositivo)

    def _ver_dispositivo(self):
        try:
            texto = mt.describir_dispositivo(self.combo_disp.currentData())
        except Exception:
            texto = ""
        aviso = mt.aviso_memoria(self.combo_modelo.currentData())
        if aviso:
            texto = f"⚠️  {aviso}" + (f"\n{texto}" if texto else "")
        self.lbl_disp.setText(texto)
        self.lbl_disp.setStyleSheet(
            "font-size: 11px; color: " + ("#b45309;" if aviso else "#64748b;"))

    def _elegir(self):
        rutas, _ = QFileDialog.getOpenFileNames(
            self, "Elegir audios o videos", "", _filtro_archivos())
        if rutas:
            self.cargar_varios(rutas)

    def _elegir_carpeta(self):
        carpeta = QFileDialog.getExistingDirectory(
            self, "Elegir la carpeta con los audios o videos")
        if not carpeta:
            return
        validas = set(EXT_AUDIO) | set(EXT_VIDEO)
        try:
            rutas = sorted(
                (os.path.join(carpeta, n) for n in os.listdir(carpeta)
                 if os.path.splitext(n)[1].lower() in validas
                 and os.path.isfile(os.path.join(carpeta, n))),
                key=_orden_natural)
        except OSError as e:
            QMessageBox.warning(self, "Transcribir",
                                f"No pude leer esa carpeta:\n{e}")
            return
        if not rutas:
            QMessageBox.information(
                self, "Transcribir",
                "En esa carpeta no hay audios ni videos.\n"
                "(No se miran las carpetas que tenga adentro.)")
            return
        self.cargar_varios(rutas, os.path.basename(os.path.normpath(carpeta)))

    def cargar(self, ruta: str):
        self.cargar_varios([ruta])

    def cargar_varios(self, rutas: list, carpeta: str = ""):
        """Deja elegidos esos archivos (los que tengan audio)."""
        if self._ocupado():
            return
        from motors.motor_audio_enhance import info
        from PyQt6.QtWidgets import QApplication
        nuevos, descartados = [], []
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            for n, ruta in enumerate(rutas):
                try:
                    ficha = info(ruta)
                    sirve = bool(ficha["tiene_audio"])
                except Exception:
                    sirve = False
                if not sirve:
                    descartados.append(os.path.basename(ruta))
                    continue
                nuevos.append({
                    "src": ruta, "es_video": bool(ficha["tiene_video"]),
                    "duracion": float(ficha["duracion"] or 0),
                    "wav": os.path.join(
                        str(TEMP_DIR), f"transcribir_{os.getpid()}_{id(self)}_"
                        f"{n}_{abs(hash(ruta)) % 10**8}.wav"),
                    "estado": "pendiente", "error": "", "tramos": [],
                    "nombres": [], "modelo": "", "sha256": "", "tamano": 0,
                    "fila": 0})
        finally:
            QApplication.restoreOverrideCursor()
        if not nuevos:
            QMessageBox.warning(
                self, "Transcribir",
                "No pude leer ese archivo, o no tiene audio." if len(rutas) == 1
                else "Ninguno de esos archivos tiene audio que se pueda leer.")
            return

        self._vaciar()
        self._archivos = nuevos
        self._carpeta = carpeta

        guardados = []
        for r in nuevos:
            g = mt.cargar_trabajo(r["src"])
            if g:
                guardados.append((r, g))
        if guardados:
            if len(nuevos) == 1:
                g = guardados[0][1]
                hechos = sum(1 for t in g["tramos"] if t.get("revisado"))
                pregunta = (
                    f"Este archivo ya lo transcribiste ({g.get('guardado', '')}).\n"
                    f"Tiene {len(g['tramos'])} tramos y revisaste {hechos}.\n\n"
                    "¿Seguimos con ese trabajo?\n\n"
                    "«No» lo deja de lado para transcribir de nuevo.")
            else:
                pregunta = (
                    f"{len(guardados)} de estos {len(nuevos)} archivos ya los "
                    "transcribiste antes.\n\n¿Seguimos con ese trabajo? Se "
                    "transcribe sólo lo que falta.\n\n"
                    "«No» lo deja de lado para transcribir todo de nuevo.")
            respuesta = QMessageBox.question(
                self, "Hay un trabajo guardado", pregunta,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes)
            if respuesta == QMessageBox.StandardButton.Yes:
                for r, g in guardados:
                    r.update(estado="hecho", tramos=g["tramos"],
                             nombres=list(g.get("nombres") or []),
                             modelo=g.get("modelo", ""),
                             fila=int(g.get("fila", 0) or 0))

        self._mostrar_archivos()
        aviso = ""
        if descartados:
            aviso = (f"⚠️  Dejé afuera {len(descartados)} "
                     f"{'archivo' if len(descartados) == 1 else 'archivos'} "
                     "sin audio o que no pude leer: "
                     + ", ".join(descartados[:4])
                     + ("…" if len(descartados) > 4 else "") + ".\n")
        primero = next((i for i, r in enumerate(self._archivos)
                        if r["estado"] == "hecho"), -1)
        if primero >= 0:
            self._resumen = aviso
        else:
            primero = 0
            self._resumen = (
                aviso + "Elegí el modelo y tocá «Transcribir». Con el "
                "procesador lleva más o menos lo que dura la grabación; en "
                "una computadora vieja, bastante más.")
        self._cambiar_archivo(primero)

    def _rotulo_archivo(self, r: dict) -> str:
        nombre = os.path.basename(r["src"])
        if r["estado"] == "hecho":
            return f"✓  {nombre}   ({mt.marca(r['duracion'])})"
        if r["estado"] == "error":
            return f"✗  {nombre}   — no se pudo transcribir"
        return f"·  {nombre}   — sin transcribir"

    def _mostrar_archivos(self):
        """Arriba, qué se eligió; en la revisión, el desplegable de archivos."""
        n = len(self._archivos)
        if n == 0:
            self.lbl_file.setText("No se eligió ningún archivo")
        elif n == 1:
            r = self._archivos[0]
            self.lbl_file.setText(
                f"{os.path.basename(r['src'])}   ·   "
                f"{'Video' if r['es_video'] else 'Audio'} de "
                f"{mt.marca(r['duracion'])}")
        else:
            hechos = len(self._hechos())
            self.lbl_file.setText(
                f"{n} archivos"
                + (f" de la carpeta «{self._carpeta}»" if self._carpeta else "")
                + f"   ·   {mt.marca(sum(r['duracion'] for r in self._archivos))}"
                " en total"
                + (f"   ·   {hechos} ya transcriptos" if hechos else ""))
        self.combo_archivo.blockSignals(True)
        self.combo_archivo.clear()
        for i, r in enumerate(self._archivos):
            self.combo_archivo.addItem(self._rotulo_archivo(r))
            self.combo_archivo.model().item(i).setEnabled(
                self._se_puede_ver(i))
        if self._actual >= 0:
            self.combo_archivo.setCurrentIndex(self._actual)
        self.combo_archivo.blockSignals(False)
        self.fila_archivo.setVisible(n > 1)

    def _se_puede_ver(self, indice: int) -> bool:
        """Si se puede pasar a ese archivo ahora.

        Mientras se transcribe, a los que faltan no: su audio lo está
        preparando la transcripción y no hay que pisarse.
        """
        if not self._transcribiendo() or indice == self._actual:
            return True
        return (self._archivos[indice]["estado"] == "hecho"
                and (indice not in self._tanda
                     or indice in self._tanda_listos))

    def _cambiar_archivo(self, indice: int):
        """Pasa a escuchar y revisar otro de los archivos."""
        valido = (0 <= indice < len(self._archivos)
                  and self._se_puede_ver(indice))
        if self._trabajo_suelto() or not valido:
            self.combo_archivo.setCurrentIndex(self._actual)
            return
        anterior = self._reg()
        if anterior is not None and indice != self._actual:
            self._guardado.stop()
            self._guardar_trabajo()
            anterior["fila"] = max(0, self._fila)
        if self._reproductor is not None:
            self._reproductor.detener()
        self._actual = indice
        self.combo_archivo.setCurrentIndex(indice)
        r = self._archivos[indice]
        if os.path.isfile(r["wav"]):
            self._mostrar_revision(r.get("fila", 0))
            return
        self.zona.setVisible(False)
        if not self._transcribiendo():
            self.lbl_status.setText("Preparando el audio para escuchar…")
            self.pbar.setRange(0, 0)
            self.pbar.setVisible(True)
        self._audio_worker = _AudioWorker(r["src"], r["wav"])
        self._audio_worker.listo.connect(
            lambda _w: self._mostrar_revision(r.get("fila", 0)))
        self._audio_worker.error.connect(self._sin_audio)
        self._audio_worker.finished.connect(self._habilitar)
        self._audio_worker.start()
        self._habilitar()

    def _sin_audio(self, msg: str):
        """No se pudo preparar el audio: se corrige igual, sin escuchar."""
        self._resumen = ((self._resumen + " " if self._resumen else "")
                         + f"⚠️  No pude preparar el audio para escuchar ({msg}).")
        r = self._reg()
        self._mostrar_revision(r.get("fila", 0) if r else 0)

    def _vaciar(self):
        """Saca lo elegido de la pantalla (lo guardado no se borra)."""
        self._guardado.stop()
        self._guardar_trabajo()
        if self._reproductor is not None:
            self._reproductor.detener()
            self._reproductor.limpiar()
        for r in self._archivos:
            if os.path.isfile(r["wav"]):
                try:
                    os.remove(r["wav"])
                except OSError:
                    pass
        self._archivos = []
        self._actual = -1
        self._en_curso = -1
        self._tanda = []
        self._tanda_listos = set()
        self._carpeta = ""
        self._resumen = ""
        self._fila = -1
        self._sonando = -1
        self._cargando_texto = True
        self.lista.clear()
        self.edit.clear()
        self.combo_habla.clear()
        self.combo_archivo.clear()
        self.vivo.clear()
        self._cargando_texto = False
        self.lbl_file.setText("No se eligió ningún archivo")
        self.lbl_tramo.setText("")
        self.lbl_status.setText("")
        self.lbl_pos.setText("00:00")
        self.lbl_dur.setText("00:00")
        self.barra_audio.setRange(0, 0)
        self.pbar.setVisible(False)
        self.caja_vivo.setVisible(False)
        self.fila_archivo.setVisible(False)
        self.zona.setVisible(False)
        self.btn_open.setVisible(False)
        self.informe_section.setVisible(False)

    def _limpiar(self):
        if self._ocupado():
            return
        self._vaciar()
        self._habilitar()

    def _transcribiendo(self) -> bool:
        return bool(self._worker and self._worker.isRunning())

    def _trabajo_suelto(self) -> bool:
        """Preparando un audio, reconociendo voces o escribiendo el informe."""
        return any(w is not None and w.isRunning() for w in (
            self._audio_worker, self._voces_worker, self._guardar_worker))

    def _ocupado(self) -> bool:
        return self._transcribiendo() or self._trabajo_suelto()

    def _habilitar(self):
        if self._sin_motor:
            return
        ocupado = self._ocupado()
        hay = bool(self._archivos)
        falta = any(r["estado"] != "hecho" for r in self._archivos)
        self.btn_transcribir.setEnabled(hay and not ocupado)
        self.btn_transcribir.setText(
            "🎙  Transcribir" if falta or not hay
            else "🎙  Transcribir de nuevo")
        self.btn_cancelar.setVisible(self._transcribiendo())
        self.combo_modelo.setEnabled(not ocupado)
        self.combo_disp.setEnabled(not ocupado)
        self.combo_archivo.setEnabled(not self._trabajo_suelto())
        hay_hechos = bool(self._hechos())
        self.btn_guardar.setEnabled(hay_hechos and not ocupado)
        self.btn_copiar.setEnabled(hay_hechos)
        # Escuchar se puede con sólo tener el audio; corregir, con el texto.
        hay_audio = bool(self._wav) and os.path.isfile(self._wav)
        for w in (self.btn_atras, self.btn_play, self.btn_adelante,
                  self.barra_audio, self.combo_vel):
            w.setEnabled(hay_audio)
        hay_tramos = bool(self._tramos)
        for w in (self.lista, self.edit, self.chk_revisado,
                  self.btn_hasta_aca, self.btn_siguiente):
            w.setEnabled(hay_tramos)
        self.btn_repetir.setEnabled(hay_tramos and hay_audio)
        if not hay_tramos:
            self.btn_restaurar.setEnabled(False)
        hay_voces = not self._sin_voces
        self.chk_voces.setEnabled(hay_voces and not ocupado)
        self.combo_personas.setEnabled(hay_voces and not ocupado)
        self.btn_voces.setEnabled(hay_voces and not ocupado
                                  and bool(self._tramos))
        self.btn_voces.setToolTip(
            self._sin_voces or self.btn_voces.toolTip())
        hay_personas = bool(self._nombres)
        for w in (self.lbl_habla, self.combo_habla, self.btn_nombres):
            w.setVisible(hay_personas)

    # ── Transcribir ──────────────────────────────────────────────────────
    def _transcribir(self):
        if not self._archivos or self._ocupado():
            return
        if any(not os.path.isfile(r["src"]) for r in self._archivos):
            QMessageBox.warning(
                self, "Transcribir",
                "Alguno de los archivos que habías elegido ya no está en su "
                "carpeta. Volvé a elegirlos.")
            return
        aviso = mt.aviso_memoria(self.combo_modelo.currentData())
        if aviso:
            respuesta = QMessageBox.question(
                self, "Poca memoria para este modelo",
                aviso + "\n\n¿Querés transcribir igual con este modelo?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if respuesta != QMessageBox.StandardButton.Yes:
                return
        tanda = [i for i, r in enumerate(self._archivos)
                 if r["estado"] != "hecho"]
        if not tanda:
            respuesta = QMessageBox.question(
                self, "Transcribir de nuevo",
                "Ya está todo transcripto. Si transcribís de nuevo se pierden "
                "las correcciones que hiciste.\n\n¿Seguimos?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if respuesta != QMessageBox.StandardButton.Yes:
                return
            tanda = list(range(len(self._archivos)))
        self._guardado.stop()
        self._guardar_trabajo()
        # Lo que se transcribe de nuevo se saca de la vista; si se corta
        # antes de que salga, vuelve lo que había.
        for i in tanda:
            r = self._archivos[i]
            if r["estado"] == "hecho":
                r["previo"] = {"tramos": r["tramos"], "nombres": r["nombres"],
                               "modelo": r["modelo"]}
                r.update(estado="pendiente", tramos=[], nombres=[])
        self._tanda = tanda
        self._tanda_listos = set()
        if self._actual in tanda:
            self._mostrar_revision()
        self.btn_open.setVisible(False)
        self.informe_section.setVisible(False)
        self.vivo.clear()
        self.caja_vivo.setVisible(True)
        self.pbar.setRange(0, 0)
        self.pbar.setVisible(True)
        self.lbl_status.setText("Preparando…")

        self._tanda_total = sum(
            self._archivos[i]["duracion"] for i in tanda) or 1.0
        self._tanda_hecha = 0.0
        self._tanda_segundos = 0.0
        self._tanda_con = ""
        self._tanda_aviso_voces = ""
        self._tanda_fin = ("error", "La transcripción se cortó sin avisar.")
        self._worker = _TandaWorker(
            [(i, self._archivos[i]["src"], self._archivos[i]["wav"])
             for i in tanda],
            self.combo_modelo.currentData(), self.combo_disp.currentData(),
            personas=(self.combo_personas.currentData()
                      if self.chk_voces.isChecked() and not self._sin_voces
                      else None))
        self._worker.empieza.connect(self._archivo_empieza)
        self._worker.progreso.connect(self._avance_tanda)
        self._worker.aviso.connect(self.lbl_status.setText)
        self._worker.tramos.connect(self._tramos_en_vivo)
        self._worker.hecho.connect(self._archivo_hecho)
        self._worker.fallo.connect(self._archivo_fallo)
        self._worker.terminado.connect(
            lambda: setattr(self, "_tanda_fin", ("bien", "")))
        self._worker.cancelado.connect(
            lambda: setattr(self, "_tanda_fin", ("cancelado", "")))
        self._worker.error.connect(
            lambda msg: setattr(self, "_tanda_fin", ("error", msg)))
        # Se cierra recién cuando el hilo terminó del todo: antes, el panel
        # todavía se ve a sí mismo como ocupado.
        self._worker.finished.connect(self._tanda_terminada)
        self._worker.start()
        self._mostrar_archivos()
        self._habilitar()

    def _puesto(self, indice: int) -> str:
        """« (2 de 5)» si se están transcribiendo varios; si no, nada."""
        if len(self._tanda) < 2 or indice not in self._tanda:
            return ""
        return f" ({self._tanda.index(indice) + 1} de {len(self._tanda)})"

    def _archivo_empieza(self, indice: int):
        self._en_curso = indice
        if indice == self._actual and not self._tramos:
            self.lbl_tramo.setText(self._rotulo_sin_tramos())
        if len(self._tanda) > 1:
            nombre = os.path.basename(self._archivos[indice]["src"])
            self._escribir_en_vivo(
                ("" if self.vivo.document().isEmpty() else "\n")
                + f"── {nombre}{self._puesto(indice)} ──")

    def _escribir_en_vivo(self, texto: str):
        self.vivo.appendPlainText(texto)
        barra = self.vivo.verticalScrollBar()
        barra.setValue(barra.maximum())

    def _tramos_en_vivo(self, _indice: int, nuevos: list):
        for t in nuevos:
            self._escribir_en_vivo(f"[{mt.marca(t['inicio'])}]  {t['texto']}")

    def _avance_tanda(self, fraccion: float):
        if not (0 <= self._en_curso < len(self._archivos)):
            return
        r = self._archivos[self._en_curso]
        voces = self.lbl_status.text().startswith("Reconociendo")
        if self.pbar.maximum() == 0:
            self.pbar.setRange(0, 1000)
            self.pbar.setFormat("%p%")
            self.pbar.setTextVisible(True)
        hecho = self._tanda_hecha + r["duracion"] * (1.0 if voces else fraccion)
        self.pbar.setValue(int(1000 * min(1.0, hecho / self._tanda_total)))
        if not voces:
            self.lbl_status.setText(
                f"Transcribiendo «{os.path.basename(r['src'])}»"
                f"{self._puesto(self._en_curso)}: va por el minuto "
                f"{mt.marca(fraccion * r['duracion'])} de "
                f"{mt.marca(r['duracion'])}.")

    def _avance(self, fraccion: float):
        """Avance de un trabajo suelto (reconocer quién habla)."""
        if self.pbar.maximum() == 0:
            self.pbar.setRange(0, 1000)
            self.pbar.setFormat("%p%")
            self.pbar.setTextVisible(True)
        self.pbar.setValue(int(fraccion * 1000))

    def _archivo_hecho(self, indice: int, resultado: dict):
        r = self._archivos[indice]
        r.update(
            estado="hecho", error="", fila=0,
            tramos=[dict(t, original=t["texto"], revisado=False)
                    for t in resultado["tramos"]],
            nombres=mv.nombres_por_defecto(resultado.get("personas", 0)),
            modelo=resultado["modelo"], sha256=resultado["sha256"],
            tamano=resultado["tamano"])
        r.pop("previo", None)
        self._tanda_listos.add(indice)
        self._tanda_hecha += r["duracion"]
        self._tanda_segundos += resultado["segundos"]
        self._tanda_con = ("la placa de video"
                           if resultado["dispositivo"] == "cuda"
                           else "el procesador")
        if resultado.get("aviso_voces"):
            self._tanda_aviso_voces = resultado["aviso_voces"]
        if not r["tramos"]:
            self._escribir_en_vivo("(no se encontró voz en esta grabación)")
        self._guardar_trabajo_de(r)
        self._mostrar_archivos()
        if indice == self._actual:
            # Es el que está escuchando: ya lo puede corregir.
            self._mostrar_revision()

    def _archivo_fallo(self, indice: int, msg: str):
        r = self._archivos[indice]
        r.update(estado="error", error=msg)
        self._tanda_hecha += r["duracion"]
        self._escribir_en_vivo(f"❌  No se pudo transcribir: {msg}")
        self._mostrar_archivos()
        if indice == self._actual:
            self.lbl_tramo.setText(self._rotulo_sin_tramos())

    def _cancelar(self):
        if self._worker and self._worker.isRunning():
            self._worker.cancelar()
            self.lbl_status.setText("Cortando la transcripción…")
            self.btn_cancelar.setEnabled(False)

    def _tanda_terminada(self):
        """El hilo terminó: bien, cancelado o con error."""
        como, msg = self._tanda_fin
        self.pbar.setVisible(False)
        self.caja_vivo.setVisible(False)
        self.btn_cancelar.setEnabled(True)
        self._en_curso = -1
        salieron = [i for i in self._tanda
                    if self._archivos[i]["estado"] == "hecho"]
        fallaron = [i for i in self._tanda
                    if self._archivos[i]["estado"] == "error"]
        # Lo que se iba a transcribir de nuevo y no llegó a salir, vuelve.
        repuesto = False
        for i in self._tanda:
            r = self._archivos[i]
            previo = r.pop("previo", None)
            if previo and r["estado"] != "hecho":
                r.update(estado="hecho", error="", **previo)
                repuesto = repuesto or i == self._actual
        self._mostrar_archivos()

        if como == "error":
            texto = f"❌  {msg}"
        elif como == "cancelado":
            texto = "Transcripción cancelada."
            if salieron:
                texto += (f" Quedaron transcriptos {len(salieron)} de "
                          f"{len(self._tanda)}.")
        else:
            texto = ""
            if salieron:
                texto = (f"Transcripto en {mt.marca(self._tanda_segundos)} "
                         f"con {self._tanda_con}.")
                if len(self._tanda) > 1:
                    texto = (f"{len(salieron)} archivos transcriptos en "
                             f"{mt.marca(self._tanda_segundos)} con "
                             f"{self._tanda_con}.")
                elif self._archivos[salieron[0]]["nombres"]:
                    voces = len(self._archivos[salieron[0]]["nombres"])
                    texto += (f" Reconocí {voces} "
                              f"{'voz' if voces == 1 else 'voces'} distintas.")
                if self._tanda_aviso_voces:
                    texto += (" No pude reconocer quién habla: "
                              f"{self._tanda_aviso_voces}")
            if fallaron:
                primero = self._archivos[fallaron[0]]
                texto += (f" ❌ No se pudo con {len(fallaron)}: "
                          f"«{os.path.basename(primero['src'])}» "
                          f"({primero['error']}).")

        texto = texto.strip()
        actual = self._reg()
        if actual is not None and actual["estado"] == "hecho" and not repuesto:
            # Ya lo está revisando: no se le mueve nada de lugar.
            self.lbl_status.setText(
                (texto + " " if texto else "") + "Escuchá y corregí lo que "
                "haga falta: se guarda solo.")
            self._habilitar()
            return
        self._resumen = texto
        destino = self._actual
        if not repuesto:
            destino = next(iter(salieron), next(
                (i for i, r in enumerate(self._archivos)
                 if r["estado"] == "hecho"), self._actual))
        if destino == self._actual:
            self._mostrar_revision(actual.get("fila", 0) if actual else 0)
        else:
            self._cambiar_archivo(destino)

    def _error(self, msg: str):
        self.pbar.setVisible(False)
        self.caja_vivo.setVisible(False)
        self.btn_cancelar.setEnabled(True)
        self.lbl_status.setText(f"❌  {msg}")
        self._habilitar()

    # ── Revisión ─────────────────────────────────────────────────────────
    def _rotulo_sin_tramos(self) -> str:
        """Lo que va en el lugar del tramo cuando todavía no hay texto."""
        r = self._reg()
        if r is None:
            return ""
        if r["estado"] == "error":
            return "No se pudo transcribir"
        if r["estado"] == "hecho":
            return "No se encontró voz"
        if self._actual == self._en_curso:
            return "Se está transcribiendo…"
        return "Todavía sin transcribir"

    def _mostrar_revision(self, fila: int = 0):
        """Muestra el archivo actual: para escuchar y, si hay texto, corregir."""
        en_tanda = self._transcribiendo()
        if not en_tanda:
            self.pbar.setVisible(False)
        self._sonando = -1
        self._fila = -1
        self.lista.blockSignals(True)
        self.lista.clear()
        for i, _t in enumerate(self._tramos):
            self.lista.addItem(QListWidgetItem(self._rotulo(i)))
        self.lista.blockSignals(False)
        self._llenar_personas()
        r = self._reg()
        self.zona.setVisible(r is not None)
        hay_audio = self._cargar_audio()
        resumen, self._resumen = self._resumen, ""
        if self._tramos:
            self.lista.setCurrentRow(max(0, min(fila, len(self._tramos) - 1)))
            cola = "Escuchá y corregí lo que haga falta: se guarda solo."
        else:
            self._cargando_texto = True
            self.edit.clear()
            self.chk_revisado.setChecked(False)
            self._cargando_texto = False
            self.lbl_tramo.setText(self._rotulo_sin_tramos())
            if r is None:
                cola = ""
            elif r["estado"] == "hecho":
                cola = ("No se encontró voz en esta grabación. Si se escucha "
                        "bajito, probá primero con «Mejorar audio».")
            elif r["estado"] == "error":
                cola = (f"Este archivo no se pudo transcribir ({r['error']})."
                        + (" Igual lo podés escuchar." if hay_audio else ""))
            elif hay_audio:
                cola = ("Ya podés escuchar la grabación; el texto para "
                        "corregir aparece al transcribirla.")
            else:
                cola = ""
        if not en_tanda:
            self.lbl_status.setText(
                (resumen + " " if resumen and cola else resumen) + cola)
        self._actualizar_avance()
        self._habilitar()

    def _rotulo(self, i: int) -> str:
        t = self._tramos[i]
        texto = t["texto"].replace("\n", " ")
        if len(texto) > 90:
            texto = texto[:88].rstrip() + "…"
        nombre = mt.quien(t, self._nombres)
        return (f"{'🔊 ' if i == self._sonando else ''}"
                f"{'✓ ' if t.get('revisado') else ''}"
                f"[{mt.marca(t['inicio'])}]  "
                f"{nombre + ': ' if nombre else ''}{texto}")

    def _tramo_tocado(self, item):
        # Un toque del usuario lleva el audio al principio de ese tramo.
        fila = self.lista.row(item)
        if 0 <= fila < len(self._tramos):
            self._ir_a(self._tramos[fila]["inicio"])

    def _cambiar_tramo(self, fila: int):
        self._fila = fila
        if not (0 <= fila < len(self._tramos)):
            return
        t = self._tramos[fila]
        self.lbl_tramo.setText(
            f"Tramo {fila + 1} de {len(self._tramos)}   ·   "
            f"de {mt.marca(t['inicio'])} a {mt.marca(t['fin'])}")
        self._cargando_texto = True
        self.edit.setPlainText(t["texto"])
        self.chk_revisado.setChecked(bool(t.get("revisado")))
        persona = t.get("persona")
        self.combo_habla.setCurrentIndex(
            persona + 1 if persona is not None
            and 0 <= persona < len(self._nombres) else 0)
        self._cargando_texto = False
        self.btn_restaurar.setEnabled(t["texto"] != t.get("original", t["texto"]))

    def _texto_cambiado(self):
        if self._cargando_texto or not (0 <= self._fila < len(self._tramos)):
            return
        t = self._tramos[self._fila]
        t["texto"] = self.edit.toPlainText().strip()
        self.lista.item(self._fila).setText(self._rotulo(self._fila))
        self.btn_restaurar.setEnabled(t["texto"] != t.get("original", ""))
        self._guardado.start()

    def _restaurar(self):
        if 0 <= self._fila < len(self._tramos):
            self.edit.setPlainText(self._tramos[self._fila].get("original", ""))

    def _alternar_revisado(self, _estado):
        if self._cargando_texto or not (0 <= self._fila < len(self._tramos)):
            return
        self._tramos[self._fila]["revisado"] = self.chk_revisado.isChecked()
        self.lista.item(self._fila).setText(self._rotulo(self._fila))
        self._actualizar_avance()
        self._guardar_trabajo()

    def _siguiente_sin_revisar(self):
        n = len(self._tramos)
        for paso in range(1, n + 1):
            i = (self._fila + paso) % n
            if not self._tramos[i].get("revisado"):
                self.lista.setCurrentRow(i)
                self._ir_a(self._tramos[i]["inicio"])
                return
        self.lbl_status.setText("✅  Ya revisaste todos los tramos.")

    def _revisado_hasta_aca(self):
        """Da por revisado todo, desde el principio hasta este tramo."""
        if not (0 <= self._fila < len(self._tramos)):
            return
        for i in range(self._fila + 1):
            self._tramos[i]["revisado"] = True
            self.lista.item(i).setText(self._rotulo(i))
        self._cargando_texto = True
        self.chk_revisado.setChecked(True)
        self._cargando_texto = False
        self._actualizar_avance()
        self._guardar_trabajo()

    def _actualizar_avance(self):
        if not self._tramos:
            self.lbl_avance.setText("")
            return
        hechos = sum(1 for t in self._tramos if t.get("revisado"))
        texto = f"Revisados {hechos} de {len(self._tramos)}"
        # Hasta dónde llega lo corregido sin saltear ninguno.
        seguidos = next((i for i, t in enumerate(self._tramos)
                         if not t.get("revisado")), len(self._tramos))
        if 0 < seguidos < len(self._tramos):
            texto += ("   ·   corregido hasta el minuto "
                      + mt.marca(self._tramos[seguidos - 1]["fin"]))
        self.lbl_avance.setText(texto)

    def _guardar_trabajo_de(self, r: dict, fila: int = 0):
        if r and r["tramos"]:
            try:
                mt.guardar_trabajo(r["src"], {
                    "tramos": r["tramos"], "modelo": r["modelo"],
                    "nombres": r["nombres"], "fila": max(0, fila)})
            except OSError:
                pass

    def _guardar_trabajo(self):
        self._guardar_trabajo_de(self._reg(), self._fila)

    # ── Quién habla ──────────────────────────────────────────────────────
    def _llenar_personas(self):
        """El desplegable «Habla:», con los participantes de ahora."""
        self._cargando_texto = True
        self.combo_habla.clear()
        self.combo_habla.addItem("(sin asignar)")
        for nombre in self._nombres:
            self.combo_habla.addItem(nombre)
        self.combo_habla.addItem("➕ Otro interlocutor…")
        self._cargando_texto = False

    def _refrescar_rotulos(self):
        for i in range(self.lista.count()):
            self.lista.item(i).setText(self._rotulo(i))

    def _cambiar_persona(self, indice: int):
        """El usuario corrige quién dice el tramo que está mirando."""
        if self._cargando_texto or not (0 <= self._fila < len(self._tramos)):
            return
        if indice == self.combo_habla.count() - 1:      # «Otro interlocutor…»
            self._nombres.append(mv.nombre_por_defecto(len(self._nombres)))
            nueva = len(self._nombres) - 1
            self._llenar_personas()
            self._tramos[self._fila]["persona"] = nueva
            self._cargando_texto = True
            self.combo_habla.setCurrentIndex(nueva + 1)
            self._cargando_texto = False
        else:
            self._tramos[self._fila]["persona"] = (
                indice - 1 if indice > 0 else None)
        self.lista.item(self._fila).setText(self._rotulo(self._fila))
        self._guardar_trabajo()

    def _editar_nombres(self):
        if not self._nombres:
            return
        ejemplos = []
        for persona in range(len(self._nombres)):
            frase = next((t["texto"] for t in self._tramos
                          if t.get("persona") == persona
                          and t["texto"] != mt.SIN_VOZ
                          and len(t["texto"]) > 12), "")
            ejemplos.append(frase[:70] + ("…" if len(frase) > 70 else ""))
        dialogo = _NombresDialog(self._nombres, ejemplos, self)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return
        self._nombres = [nuevo or viejo for nuevo, viejo
                         in zip(dialogo.nombres(), self._nombres)]
        fila = self._fila
        self._llenar_personas()
        self._refrescar_rotulos()
        self._cambiar_tramo(fila)
        self._guardar_trabajo()

    def _reconocer_voces(self):
        """Separa las voces de una transcripción ya hecha."""
        if not self._tramos or self._ocupado() or self._sin_voces:
            return
        if not self._wav or not os.path.isfile(self._wav):
            return
        if self._nombres:
            respuesta = QMessageBox.question(
                self, "Reconocer quién habla",
                "Ya está reconocido quién habla. Si lo hago de nuevo se "
                "pierden los cambios que hiciste a mano en «Habla:» (los "
                "textos corregidos no se tocan).\n\n¿Seguimos?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if respuesta != QMessageBox.StandardButton.Yes:
                return
        if self._reproductor is not None and self._reproductor._player:
            self._reproductor._player.pause()
        self.pbar.setRange(0, 0)
        self.pbar.setVisible(True)
        self.lbl_status.setText("Reconociendo quién habla…")
        self._voces_worker = _VocesWorker(
            self._wav, self.combo_personas.currentData())
        self._voces_worker.progreso.connect(self._avance)
        self._voces_worker.listo.connect(self._voces_listas)
        self._voces_worker.error.connect(self._error)
        self._voces_worker.finished.connect(self._habilitar)
        self._voces_worker.start()
        self._habilitar()

    def _voces_listas(self, turnos: list):
        self.pbar.setVisible(False)
        viejos = self._nombres
        cantidad = mv.asignar(self._tramos, turnos)
        # Si ya les había puesto nombre y siguen siendo los mismos, quedan.
        self._nombres = (viejos if len(viejos) == cantidad
                         else mv.nombres_por_defecto(cantidad))
        fila = max(0, self._fila)
        self._llenar_personas()
        self._refrescar_rotulos()
        self._cambiar_tramo(fila)
        self._guardar_trabajo()
        if cantidad:
            self.lbl_status.setText(
                f"✅  Reconocí {cantidad} "
                f"{'voz' if cantidad == 1 else 'voces'} distintas. Poneles "
                "nombre con «Nombres…» y corregí con «Habla:» si en algún "
                "tramo me equivoqué.")
        else:
            self.lbl_status.setText(
                "No pude distinguir ninguna voz en la grabación.")
        self._habilitar()

    # ── Guardar el resultado ─────────────────────────────────────────────
    def _copiar(self):
        from PyQt6.QtWidgets import QApplication
        hechos = self._hechos()
        con_tiempos = self.chk_tiempos.isChecked()
        if len(hechos) == 1:
            texto = mt.texto_completo(hechos[0]["tramos"], con_tiempos,
                                      hechos[0]["nombres"])
        else:
            texto = "\n\n".join(
                f"── {os.path.basename(r['src'])} ──\n"
                + mt.texto_completo(r["tramos"], con_tiempos, r["nombres"])
                for r in hechos)
        QApplication.clipboard().setText(texto)
        self.lbl_status.setText("✅  Transcripción copiada al portapapeles.")

    def _guardar(self):
        hechos = self._hechos()
        if not hechos or self._ocupado():
            return
        self._guardado.stop()
        self._guardar_trabajo()
        carpeta = carpeta_destino([r["src"] for r in hechos], "")
        os.makedirs(carpeta, exist_ok=True)
        if len(hechos) == 1:
            base = (os.path.splitext(os.path.basename(hechos[0]["src"]))[0]
                    + " - transcripción")
        else:
            base = "Transcripciones - " + (
                self._carpeta or f"{len(hechos)} archivos")
        ruta, _ = QFileDialog.getSaveFileName(
            self, "Generar el informe", os.path.join(carpeta, base + ".odt"),
            "Informe para LibreOffice o Word (*.odt);;Word (*.docx);;"
            "Texto (*.txt);;Subtítulos (*.srt)")
        if not ruta:
            return

        tramos = sum(len(r["tramos"]) for r in hechos)
        revisados = sum(1 for r in hechos for t in r["tramos"]
                        if t.get("revisado"))
        modelos = sorted({
            dict(mt.MODELOS).get(r["modelo"], r["modelo"]).split(" — ")[0]
            for r in hechos if r["modelo"]})
        parametros = (
            (f"modelo Whisper «{'», «'.join(modelos)}», " if modelos else "")
            + f"{tramos} tramos, {revisados} revisados a oído")
        if any(mt.nombres_utiles(r["tramos"], r["nombres"]) for r in hechos):
            parametros += ("; interlocutores distinguidos por su voz en forma "
                           "automática y controlados a oído")
        self._sin_transcribir = len(self._archivos) - len(hechos)
        self.pbar.setRange(0, 0)
        self.pbar.setVisible(True)
        self._guardar_worker = _GuardarWorker(
            hechos, ruta, self.chk_tiempos.isChecked(),
            self._carpeta if len(hechos) == len(self._archivos) else "",
            parametros)
        self._guardar_worker.aviso.connect(self.lbl_status.setText)
        self._guardar_worker.listo.connect(self._informe_guardado)
        self._guardar_worker.error.connect(self._no_se_guardo)
        self._guardar_worker.finished.connect(self._habilitar)
        self._guardar_worker.start()
        self._habilitar()

    def _informe_guardado(self, escritos: list, constancia: str):
        self.pbar.setVisible(False)
        self._last_out = os.path.dirname(escritos[0])
        texto = (f"✅  Guardado: {os.path.basename(escritos[0])}"
                 if len(escritos) == 1
                 else f"✅  Guardados {len(escritos)} archivos de subtítulos.")
        if self._sin_transcribir:
            texto += (f"  Quedan {self._sin_transcribir} sin transcribir, "
                      "que no van en el informe.")
        self.lbl_status.setText(texto)
        self.btn_open.setVisible(True)
        if constancia:
            self.informe_section.set_informe(constancia, self._last_out)

    def _no_se_guardo(self, msg: str):
        self.pbar.setVisible(False)
        QMessageBox.warning(self, "Transcribir", f"No se pudo guardar:\n{msg}")

    def _abrir_carpeta(self):
        if not self._last_out or not os.path.isdir(self._last_out):
            return
        try:
            if platform.system() == "Windows":
                os.startfile(self._last_out)
            elif platform.system() == "Darwin":
                subprocess.run(["open", self._last_out])
            else:
                subprocess.run(["xdg-open", self._last_out])
        except Exception:
            pass

    # ── Ciclo de vida ────────────────────────────────────────────────────
    def hideEvent(self, event):
        # Al cambiar de solapa o de módulo, deja de sonar.
        if self._reproductor is not None and self._reproductor._player:
            self._reproductor._player.pause()
        super().hideEvent(event)

    def puede_cerrar(self) -> bool:
        """Lo llama el Conversor al salir: guarda y corta lo que esté corriendo."""
        if self._sin_motor:
            return True
        if self._worker and self._worker.isRunning():
            respuesta = QMessageBox.question(
                self, "Hay una transcripción en curso",
                "Se está transcribiendo una grabación. Si salís ahora se "
                "pierde lo que va.\n\n¿Querés salir de todos modos?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if respuesta != QMessageBox.StandardButton.Yes:
                return False
            self._worker.cancelar()
            self._worker.wait(5000)
        self._vaciar()
        return True
