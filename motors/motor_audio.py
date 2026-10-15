"""
motor_audio.py — Conversión entre formatos de audio.
Motor: FFmpeg (externo).
Soporta: MP3, WAV, FLAC, AAC, OGG, OPUS, M4A, M4B, M4R, WMA, AIFF, AU,
         AMR, AC3, APE, MKA, CAF, MID, RA, DTS
"""
import os
import shutil
import subprocess
from core.graph import BaseMotor


AUDIO_FMTS = [
    "mp3", "wav", "flac", "aac", "ogg", "opus",
    "m4a", "m4b", "m4r", "wma", "aiff", "aif",
    "au", "amr", "ac3", "ape", "mka", "caf", "ra",
    "dts", "mid", "midi",
]

# Producto cartesiano completo (todos → todos, excepto mismo formato)
AUDIO_CONVERSIONS = [
    (src, dst)
    for src in AUDIO_FMTS
    for dst in AUDIO_FMTS
    if src != dst
]

# Mapeo de extensión → codec FFmpeg
CODEC_MAP = {
    "mp3":  ["-codec:a", "libmp3lame",  "-q:a", "2"],
    "wav":  ["-codec:a", "pcm_s16le"],
    "flac": ["-codec:a", "flac"],
    "aac":  ["-codec:a", "aac",         "-b:a", "192k"],
    "ogg":  ["-codec:a", "libvorbis",   "-q:a", "5"],
    "opus": ["-codec:a", "libopus",     "-b:a", "128k"],
    "m4a":  ["-codec:a", "aac",         "-b:a", "192k"],
    "m4b":  ["-codec:a", "aac",         "-b:a", "128k"],
    "m4r":  ["-codec:a", "aac",         "-b:a", "128k"],
    "wma":  ["-codec:a", "wmav2"],
    "aiff": ["-codec:a", "pcm_s16be"],
    "aif":  ["-codec:a", "pcm_s16be"],
    "au":   ["-codec:a", "pcm_s16be"],
    "amr":  ["-codec:a", "libopencore_amrnb", "-ar", "8000", "-ac", "1"],
    "ac3":  ["-codec:a", "ac3"],
    "ape":  ["-codec:a", "ape"],
    "mka":  ["-codec:a", "copy"],
    "caf":  ["-codec:a", "pcm_s16le"],
    "ra":   ["-codec:a", "real_144"],
    # El encoder DCA de FFmpeg está marcado como experimental: sin
    # "-strict -2" se niega a arrancar.
    "dts":  ["-codec:a", "dca", "-strict", "-2", "-b:a", "1536k"],
    "mid":  [],   # MIDI: limitado en FFmpeg
    "midi": [],
}

# Contenedor por extensión
CONTAINER_MAP = {
    "mp3":  "mp3",
    "wav":  "wav",
    "flac": "flac",
    "aac":  "adts",
    "ogg":  "ogg",
    "opus": "opus",
    "m4a":  "ipod",
    "m4b":  "ipod",
    "m4r":  "ipod",
    "wma":  "asf",
    "aiff": "aiff",
    "aif":  "aiff",
    "au":   "au",
    "amr":  "amr",
    "ac3":  "ac3",
    "ape":  "ape",
    "mka":  "matroska",
    "caf":  "caf",
    "ra":   "rm",
    "dts":  "dts",
    "mid":  "midi",
    "midi": "midi",
}


def build_af_filter(cfg) -> str:
    """
    Traduce la configuración del filtro de audio (de la UI) a una cadena
    -af de FFmpeg. Devuelve "" si no hay filtro.

    cfg = {"mode": "voz"|"agudos"|"graves"|"limpieza", "intensity": 0-100}
    """
    if not cfg:
        return ""
    mode = cfg.get("mode", "limpieza")
    try:
        intensity = max(0, min(100, int(cfg.get("intensity", 50))))
    except (TypeError, ValueError):
        intensity = 50
    f = intensity / 100.0

    if mode == "voz":
        # Banda de voz humana + reducción de ruido proporcional a la intensidad
        nr = round(6 + f * 24, 1)            # 6..30 dB
        return f"highpass=f=100,lowpass=f=8000,afftdn=nr={nr}"
    if mode == "agudos":
        g = round(f * 15, 1)                 # 0..15 dB de realce
        return f"treble=g={g}"
    if mode == "graves":
        g = round(f * 15, 1)
        return f"bass=g={g}"
    # "limpieza" (por defecto): solo reducción de ruido
    nr = round(6 + f * 30, 1)                # 6..36 dB
    return f"afftdn=nr={nr}"


class FFmpegAudioMotor(BaseMotor):
    NAME = "FFmpeg-Audio"
    CONVERSIONS = AUDIO_CONVERSIONS

    @classmethod
    def is_available(cls) -> bool:
        return shutil.which("ffmpeg") is not None

    def convert(self, src_path, dst_path, src_ext, dst_ext, **kwargs):
        codec_args = list(CODEC_MAP.get(dst_ext, []))
        fmt = CONTAINER_MAP.get(dst_ext, dst_ext)

        af = build_af_filter(kwargs.get("audio_filter"))
        # Un filtro de audio obliga a recodificar: "copy" deja de ser válido.
        if af and "copy" in codec_args:
            codec_args = ["-codec:a", "libmp3lame", "-q:a", "2"] \
                if dst_ext in ("mp3",) else []

        cmd = ["ffmpeg", "-y", "-i", src_path]
        if af:
            cmd += ["-af", af]
        cmd += codec_args
        if kwargs.get("strip_metadata"):
            cmd += ["-map_metadata", "-1"]
        cmd += ["-f", fmt, dst_path]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"FFmpeg error:\n{result.stderr[-800:]}"
            )
