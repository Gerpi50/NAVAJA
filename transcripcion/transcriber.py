# -*- coding: utf-8 -*-
"""
Transcripcion de audios y videos con Whisper, totalmente offline.

Los modelos se buscan primero en la carpeta «modelos» que acompana al
ejecutable y despues en la cache del usuario (~/.cache/whisper). Si el modelo
pedido no esta se avisa en lugar de intentar bajarlo, para no romper el
requisito de funcionar sin internet.

El idioma se fuerza a espanol: dejar que Whisper lo detecte solo produce, en
audios cortos o con ruido, transcripciones en portugues o italiano.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass

# Nombre del modelo -> (etiqueta para la interfaz, tamano aproximado en disco)
MODELS = {
    "tiny":     ("Tiny - el más rápido, precisión baja", 75),
    "base":     ("Base - rápido, precisión media", 145),
    "small":    ("Small - buen equilibrio", 484),
    "medium":   ("Medium - recomendado, muy buena precisión", 1528),
    "large-v3": ("Large v3 - máxima precisión, el más lento", 3087),
    "large-v3-turbo": ("Turbo - casi la precisión de Large, mucho más rápido", 1544),
}

DEFAULT_MODEL = "medium"

# Sesga la puntuacion y el vocabulario hacia el espanol rioplatense.
#
# IMPORTANTE: este texto va CON tildes a proposito. Whisper imita el estilo
# ortografico del prompt, de modo que uno escrito sin acentos produce
# transcripciones sin acentos ("habilitacion" en lugar de "habilitación").
INITIAL_PROMPT = (
    "Transcripción literal en español de una grabación de voz. "
    "Se usa voseo rioplatense, con tildes, signos de interrogación y "
    "puntuación normal. Por ejemplo: ¿Cómo estás? Sí, mañana te llevo la "
    "documentación de la habilitación municipal."
)

NO_SPEECH_TEXT = "(el audio no contiene voz audible)"


CARPETA_MODELOS = "modelos"


def _app_dir() -> str:
    """Carpeta de la aplicacion: la del .exe si esta empaquetada, o el proyecto."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def cache_dir() -> str:
    """Carpeta donde Whisper guarda los modelos .pt en el perfil del usuario."""
    root = os.getenv("XDG_CACHE_HOME") or os.path.join(
        os.path.expanduser("~"), ".cache"
    )
    return os.path.join(root, "whisper")


def model_dirs() -> list[str]:
    """Carpetas donde se buscan los modelos, en orden de prioridad.

    La carpeta «modelos» junto al ejecutable va primero: asi la version
    portable lleva los modelos al lado del .exe, sin depender del perfil del
    usuario ni de que haya internet.
    """
    dirs: list[str] = []
    propia = os.getenv("NAVAJA_MODELOS")
    if propia:
        dirs.append(propia)
    dirs.append(os.path.join(_app_dir(), CARPETA_MODELOS))
    # Dentro de Navaja: su carpeta models/whisper.
    try:
        from core.paths import MODELS_DIR

        dirs.append(os.path.join(str(MODELS_DIR), "whisper"))
    except Exception:
        pass
    dirs.append(cache_dir())

    vistos, unicas = set(), []
    for d in dirs:
        clave = os.path.normcase(os.path.abspath(d))
        if clave not in vistos:
            vistos.add(clave)
            unicas.append(d)
    return unicas


def model_path(name: str) -> str:
    """Ruta del .pt del modelo si esta presente; si no, la ruta preferida."""
    for d in model_dirs():
        ruta = os.path.join(d, f"{name}.pt")
        if os.path.isfile(ruta):
            return ruta
    return os.path.join(model_dirs()[0], f"{name}.pt")


def model_root(name: str) -> str:
    """Carpeta que contiene el modelo (lo que Whisper espera como raiz)."""
    return os.path.dirname(model_path(name))


def available_models() -> dict[str, bool]:
    """Devuelve, para cada modelo conocido, si esta disponible localmente."""
    return {name: os.path.isfile(model_path(name)) for name in MODELS}


# Preferencia de dispositivo elegible por el usuario.
DISPOSITIVOS = ("auto", "cpu", "cuda")

# Umbrales para decidir si conviene usar la placa de video.
#
# No toda GPU le gana al procesador: medido en esta computadora, el modelo
# "medium" tarda 21 s en una NVIDIA T600 (4 GB, 10 multiprocesadores) y 9 s en
# un procesador de 14 hilos. Las placas de entrada pierden contra un CPU
# moderno, asi que solo se usa la GPU cuando tiene tamano suficiente.
GPU_VRAM_MINIMA_GB = 6.0
GPU_SM_MINIMOS = 16


def gpu_info() -> dict | None:
    """Datos de la placa de video, o None si no hay CUDA disponible."""
    try:
        import torch

        if not torch.cuda.is_available():
            return None
        props = torch.cuda.get_device_properties(0)
        return {
            "nombre": props.name,
            "vram_gb": props.total_memory / (1024 ** 3),
            "sm": getattr(props, "multi_processor_count", 0),
        }
    except Exception:
        return None


def _gb(valor: float) -> str:
    """Formato de memoria en castellano: 4,0 GB."""
    return f"{valor:.1f}".replace(".", ",") + " GB"


def pick_device(preferencia: str = "auto") -> tuple[str, str]:
    """Elige el dispositivo y explica por que, para mostrarlo en la interfaz.

    Devuelve ("cpu" | "cuda", motivo). Los textos van con tildes porque se
    muestran tal cual en la ventana.
    """
    hilos = os.cpu_count() or 4
    info = gpu_info()

    if preferencia == "cpu":
        return "cpu", "elegido a mano"

    if preferencia == "cuda":
        if info is None:
            return "cpu", (
                "se pidió la placa de video, pero esta computadora no tiene "
                "una compatible"
            )
        return "cuda", "elegida a mano"

    # Automatico
    if info is None:
        return "cpu", "no se detectó una placa de video compatible"

    if info["vram_gb"] >= GPU_VRAM_MINIMA_GB and info["sm"] >= GPU_SM_MINIMOS:
        return "cuda", (
            f"la placa {info['nombre']} ({_gb(info['vram_gb'])}) es más "
            f"rápida que el procesador"
        )

    return "cpu", (
        f"sus {hilos} hilos son más rápidos que la placa {info['nombre']} "
        f"({_gb(info['vram_gb'])}), que es de gama de entrada"
    )


def describe_device(preferencia: str = "auto") -> str:
    """Texto para la interfaz: con que se va a transcribir."""
    try:
        import torch  # noqa: F401
    except ImportError:
        return "PyTorch no está instalado"

    device, _motivo = pick_device(preferencia)
    if device == "cuda":
        info = gpu_info() or {}
        nombre = info.get("nombre", "placa de video")
        return f"Transcripción con la placa {nombre}"
    return f"Transcripción con el procesador ({os.cpu_count() or 4} hilos)"


@dataclass
class TranscriptionResult:
    text: str = ""
    error: str = ""
    language: str = ""
    duration: float | None = None


class Transcriber:
    """Envoltorio de Whisper que carga el modelo una sola vez."""

    def __init__(self, model_name: str = DEFAULT_MODEL, log_cb=None,
                 device_pref: str = "auto"):
        self.model_name = model_name
        self.log_cb = log_cb
        self.device_pref = device_pref if device_pref in DISPOSITIVOS else "auto"
        self._model = None
        self._device = "cpu"

    # ------------------------------------------------------------------ logica

    def _log(self, msg: str) -> None:
        if self.log_cb:
            self.log_cb(msg)

    @property
    def device(self) -> str:
        return self._device

    def ensure_model(self) -> None:
        """Carga el modelo en memoria, en el dispositivo que corresponda."""
        if self._model is not None:
            return

        path = model_path(self.model_name)
        if not os.path.isfile(path):
            buscado = "\n".join(
                f"   {os.path.join(d, self.model_name + '.pt')}"
                for d in model_dirs()
            )
            raise RuntimeError(
                f"No se encontro el modelo «{self.model_name}».\n\n"
                f"Se busco en:\n{buscado}\n\n"
                "Elegi otro modelo de la lista, o copia el archivo "
                f"{self.model_name}.pt en la carpeta «modelos»."
            )

        import whisper

        device, motivo = pick_device(self.device_pref)
        self._log(f"Dispositivo elegido: {motivo}.")
        self._log(f"Cargando el modelo «{self.model_name}» en {device.upper()}…")
        try:
            self._model = whisper.load_model(
                self.model_name, device=device, download_root=model_root(self.model_name)
            )
            self._device = device
        except Exception as exc:
            if device == "cuda":
                self._log(
                    f"No se pudo usar la placa de video "
                    f"({type(exc).__name__}). Se continúa con el "
                    "procesador; va a tardar más."
                )
                _empty_cuda_cache()
                self._model = whisper.load_model(
                    self.model_name, device="cpu", download_root=model_root(self.model_name)
                )
                self._device = "cpu"
            else:
                raise
        self._log(f"Modelo listo en {self._device.upper()}.")

    def transcribe(self, path: str, kind: str = "audio") -> TranscriptionResult:
        """Transcribe un archivo de audio o video. Nunca lanza excepcion."""
        try:
            self.ensure_model()
        except Exception as exc:
            return TranscriptionResult(error=str(exc))

        target = path
        temp_wav = ""
        try:
            if kind == "video":
                temp_wav = _extract_audio(path)
                if temp_wav:
                    target = temp_wav

            result = self._run(target)
            segments = result.get("segments") or []
            text = (result.get("text") or "").strip()

            # Whisper a veces "alucina" frases sobre silencio. Si todos los
            # segmentos tienen alta probabilidad de no contener voz, se
            # descarta el texto en lugar de inventar contenido en el informe.
            if segments:
                no_speech = [
                    s for s in segments if s.get("no_speech_prob", 0) > 0.85
                ]
                if len(no_speech) == len(segments):
                    text = ""

            if not text:
                return TranscriptionResult(text=NO_SPEECH_TEXT,
                                           language=result.get("language", ""))
            return TranscriptionResult(
                text=_tidy(text), language=result.get("language", "")
            )
        except Exception as exc:
            return TranscriptionResult(
                error=f"{type(exc).__name__}: {exc}"
            )
        finally:
            if temp_wav and os.path.exists(temp_wav):
                try:
                    os.remove(temp_wav)
                except OSError:
                    pass

    def _run(self, target: str) -> dict:
        """Ejecuta Whisper, repitiendo en CPU si la GPU se queda sin memoria."""
        options = dict(
            language="es",
            task="transcribe",
            fp16=(self._device == "cuda"),
            initial_prompt=INITIAL_PROMPT,
            condition_on_previous_text=False,
            no_speech_threshold=0.6,
            verbose=None,
        )
        try:
            return self._model.transcribe(target, **options)
        except Exception as exc:
            if self._device == "cuda" and _is_oom(exc):
                self._log(
                    "La placa de video se quedó sin memoria. Se recarga el "
                    "modelo en el procesador y se reintenta."
                )
                _empty_cuda_cache()
                import whisper

                self._model = whisper.load_model(
                    self.model_name, device="cpu", download_root=model_root(self.model_name)
                )
                self._device = "cpu"
                options["fp16"] = False
                return self._model.transcribe(target, **options)
            raise

    def release(self) -> None:
        """Libera el modelo y la memoria de la GPU."""
        self._model = None
        _empty_cuda_cache()


# ---------------------------------------------------------------- utilidades


def _is_oom(exc: Exception) -> bool:
    name = type(exc).__name__.lower()
    text = str(exc).lower()
    return "outofmemory" in name or "out of memory" in text


def _empty_cuda_cache() -> None:
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass


def _extract_audio(path: str) -> str:
    """Extrae la pista de audio de un video a un WAV temporal de 16 kHz mono."""
    fd, out = tempfile.mkstemp(suffix=".wav", prefix="wa_audio_")
    os.close(fd)
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error", "-i", path,
        "-vn", "-ac", "1", "-ar", "16000", "-f", "wav", out,
    ]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=900,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if proc.returncode != 0 or not os.path.getsize(out):
            os.remove(out)
            return ""
        return out
    except Exception:
        if os.path.exists(out):
            os.remove(out)
        return ""


def _tidy(text: str) -> str:
    """Limpieza minima: espacios repetidos y mayuscula inicial."""
    text = " ".join(text.split())
    if text and text[0].islower():
        text = text[0].upper() + text[1:]
    return text
