# -*- coding: utf-8 -*-
"""
Reproductor de audio para revisar una transcripción tramo por tramo.

Convierte a WAV con ffmpeg para no depender de los códecs de Windows, que no
siempre soportan Opus, y permite cambiar la velocidad de reproducción.
"""

from __future__ import annotations

import os
import subprocess
import tempfile

from PyQt6.QtCore import QObject, QUrl, pyqtSignal



class Reproductor(QObject):
    """Reproduce audios con control de posicion y de velocidad. Convierte a
    WAV con ffmpeg para no depender de los codecs de Windows, que no siempre
    soportan Opus."""

    posicion = pyqtSignal(int)      # milisegundos
    duracion = pyqtSignal(int)      # milisegundos
    sonando = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self._player = None
        self._salida = None
        self._cache: dict[str, str] = {}
        self._temp = ""
        self._origen = ""           # ruta original cargada en el reproductor
        self._velocidad = 1.0
        self._pendiente = -1        # posicion a aplicar cuando termine de cargar
        try:
            from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer

            self._player = QMediaPlayer()
            self._salida = QAudioOutput()
            self._player.setAudioOutput(self._salida)
            self._salida.setVolume(1.0)
            self._player.positionChanged.connect(self._cambio_posicion)
            self._player.durationChanged.connect(self._cambio_duracion)
            self._player.playbackStateChanged.connect(self._cambio_estado)
            self._player.mediaStatusChanged.connect(self._cambio_media)
            self.disponible = True
        except Exception:
            self.disponible = False

    # --------------------------------------------------------------- internos

    def _cambio_posicion(self, ms) -> None:
        self.posicion.emit(int(ms))

    def _cambio_duracion(self, ms) -> None:
        self.duracion.emit(int(ms))

    def _cambio_estado(self, estado) -> None:
        self.sonando.emit(
            estado == self._player.PlaybackState.PlayingState
        )

    def _cambio_media(self, estado) -> None:
        """Cuando el archivo termina de cargar aplica la velocidad elegida y
        la posicion que el usuario haya pedido antes de que estuviera listo."""
        listos = (self._player.MediaStatus.LoadedMedia,
                  self._player.MediaStatus.BufferedMedia)
        if estado not in listos:
            return
        self._player.setPlaybackRate(self._velocidad)
        if self._pendiente >= 0:
            self._player.setPosition(self._pendiente)
            self._pendiente = -1

    def _wav(self, path: str) -> str:
        """Devuelve la ruta a un WAV reproducible, convirtiendo si hace falta."""
        if path in self._cache and os.path.exists(self._cache[path]):
            return self._cache[path]
        if not self._temp:
            self._temp = tempfile.mkdtemp(prefix="wa_play_")
        destino = os.path.join(
            self._temp, f"audio{len(self._cache):03d}.wav"
        )
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", path,
               "-ac", "2", "-ar", "44100", destino]
        try:
            proc = subprocess.run(
                cmd, capture_output=True, timeout=300,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if proc.returncode == 0 and os.path.getsize(destino):
                self._cache[path] = destino
                return destino
        except Exception:
            pass
        return path

    # ----------------------------------------------------------------- publico

    def cargar(self, path: str) -> bool:
        """Deja el audio listo (en pausa) para escuchar o para buscar dentro.

        La conversion a WAV puede tardar la primera vez; despues queda en
        cache y el mismo audio se abre al instante."""
        if not self._player:
            return False
        if self._origen == path and self._player.source().isValid():
            return True
        destino = self._wav(path)
        self._player.stop()
        self._player.setSource(QUrl.fromLocalFile(destino))
        self._player.setPlaybackRate(self._velocidad)
        self._origen = path
        self._pendiente = -1
        return True

    def alternar(self, path: str) -> bool:
        """Reproduce o pausa. Devuelve False si no se pudo abrir el audio."""
        if not self._player:
            try:
                os.startfile(self._wav(path))  # noqa: S606 - reproductor del sistema
                return True
            except Exception:
                return False
        if not self.cargar(path):
            return False
        if self._player.playbackState() == self._player.PlaybackState.PlayingState:
            self._player.pause()
        else:
            total = self._player.duration()
            if total and self._player.position() >= total - 50:
                self._player.setPosition(0)
            self._player.play()
        return True

    def buscar(self, ms: int) -> None:
        """Salta a un punto exacto del audio."""
        if not self._player:
            return
        ms = max(0, int(ms))
        if self._player.isSeekable():
            self._player.setPosition(ms)
        else:
            self._pendiente = ms

    def saltar(self, delta_ms: int) -> None:
        """Retrocede (delta negativo) o adelanta unos segundos."""
        if not self._player:
            return
        destino = self._player.position() + delta_ms
        limite = self._player.duration()
        if limite:
            destino = min(destino, max(0, limite - 200))
        self.buscar(destino)

    def poner_velocidad(self, factor: float) -> None:
        self._velocidad = float(factor)
        if self._player:
            self._player.setPlaybackRate(self._velocidad)

    def duracion_actual(self) -> int:
        return self._player.duration() if self._player else 0

    def reproducir(self, path: str) -> bool:
        """Compatibilidad: arranca el audio desde donde este."""
        if not self._player:
            return self.alternar(path)
        if not self.cargar(path):
            return False
        self._player.play()
        return True

    def detener(self) -> None:
        if self._player:
            self._player.stop()
            self._player.setPosition(0)

    def limpiar(self) -> None:
        self.detener()
        if self._player:
            self._player.setSource(QUrl())
        self._origen = ""
        if self._temp and os.path.isdir(self._temp):
            import shutil

            shutil.rmtree(self._temp, ignore_errors=True)
            self._temp = ""
            self._cache.clear()

