"""
motors/motor_audio_splitter.py — Partidor de audio sin re-encodeo.
Modos: por segundos o por kilobytes.
"""
import json
import os
import shutil
import subprocess
from typing import Callable, List, Optional


def _find_ffmpeg():
    from core.paths import BIN_DIR
    for name in ["ffmpeg.exe", "ffmpeg"]:
        local = os.path.join(BIN_DIR, name)
        if os.path.isfile(local):
            return local
    return shutil.which("ffmpeg")


def _find_ffprobe():
    from core.paths import BIN_DIR
    for name in ["ffprobe.exe", "ffprobe"]:
        local = os.path.join(BIN_DIR, name)
        if os.path.isfile(local):
            return local
    return shutil.which("ffprobe")


FFMPEG  = _find_ffmpeg()
FFPROBE = _find_ffprobe()


def is_available() -> bool:
    return FFMPEG is not None and FFPROBE is not None


def get_audio_info(src_path: str) -> dict:
    """Retorna duración en segundos y bitrate del audio."""
    if not FFPROBE:
        raise RuntimeError("FFprobe no disponible.")
    cmd = [
        FFPROBE, "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        src_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    data = json.loads(result.stdout)
    fmt = data.get("format", {})
    duration = float(fmt.get("duration", 0))
    bit_rate  = int(fmt.get("bit_rate", 0))
    return {"duration": duration, "bit_rate": bit_rate}


def estimate_parts_by_seconds(src_path: str, secs_per_part: float) -> int:
    try:
        info = get_audio_info(src_path)
        if info["duration"] <= 0 or secs_per_part <= 0:
            return 0
        import math
        return math.ceil(info["duration"] / secs_per_part)
    except Exception:
        return 0


def estimate_parts_by_kb(src_path: str, kb_per_part: float) -> int:
    try:
        info = get_audio_info(src_path)
        if info["bit_rate"] <= 0 or kb_per_part <= 0:
            return 0
        secs = (kb_per_part * 1024 * 8) / info["bit_rate"]
        return estimate_parts_by_seconds(src_path, secs)
    except Exception:
        return 0


def split_audio_by_seconds(
    src_path: str,
    output_dir: str,
    secs_per_part: float,
    progress_cb: Optional[Callable[[str], None]] = None,
) -> List[str]:
    """Divide el audio en partes de X segundos sin re-encodear."""
    if not is_available():
        raise RuntimeError(
            "El partidor de audio necesita FFmpeg.\n"
            "Colocá ffmpeg.exe y ffprobe.exe en la carpeta bin/ del programa."
        )
    if secs_per_part <= 0:
        raise ValueError("Los segundos por parte deben ser mayores que 0.")

    info = get_audio_info(src_path)
    duration = info["duration"]
    if duration <= 0:
        raise RuntimeError("No se pudo determinar la duración del archivo.")

    return _do_split(src_path, output_dir, duration, secs_per_part, progress_cb)


def split_audio_by_kb(
    src_path: str,
    output_dir: str,
    kb_per_part: float,
    progress_cb: Optional[Callable[[str], None]] = None,
) -> List[str]:
    """Divide el audio en partes de aprox. X KB sin re-encodear."""
    if not is_available():
        raise RuntimeError(
            "El partidor de audio necesita FFmpeg.\n"
            "Colocá ffmpeg.exe y ffprobe.exe en la carpeta bin/ del programa."
        )
    if kb_per_part <= 0:
        raise ValueError("El tamaño en KB debe ser mayor que 0.")

    info = get_audio_info(src_path)
    duration = info["duration"]
    bit_rate  = info["bit_rate"]

    if duration <= 0:
        raise RuntimeError("No se pudo determinar la duración del archivo.")
    if bit_rate <= 0:
        raise RuntimeError(
            "No se pudo determinar el bitrate del archivo.\n"
            "El archivo puede estar dañado o en un formato no compatible."
        )

    secs_per_part = (kb_per_part * 1024 * 8) / bit_rate
    secs_per_part = max(secs_per_part, 1.0)

    return _do_split(src_path, output_dir, duration, secs_per_part, progress_cb)


def _do_split(
    src_path: str,
    output_dir: str,
    duration: float,
    secs_per_part: float,
    progress_cb: Optional[Callable[[str], None]],
) -> List[str]:
    ext  = os.path.splitext(src_path)[1]
    stem = os.path.splitext(os.path.basename(src_path))[0]
    out_subdir = output_dir
    os.makedirs(out_subdir, exist_ok=True)

    parts    = []
    part_num = 1
    start    = 0.0

    while start < duration:
        part_name = f"{stem}_parte{part_num:02d}{ext}"
        part_path = os.path.join(out_subdir, part_name)
        end = min(start + secs_per_part, duration)

        if progress_cb:
            progress_cb(
                f"✂️  Parte {part_num} ({int(start//60)}:{int(start%60):02d} - "
                f"{int(end//60)}:{int(end%60):02d})..."
            )

        cmd = [
            FFMPEG, "-y",
            "-ss", str(start),
            "-i", src_path,
            "-t", str(secs_per_part),
            "-c", "copy",
            part_path,
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=300)
        if result.returncode != 0:
            raise RuntimeError(
                f"Error al generar la parte {part_num}.\n"
                "Verificá que el archivo no esté dañado."
            )

        if os.path.exists(part_path) and os.path.getsize(part_path) > 0:
            parts.append(part_path)

        start    += secs_per_part
        part_num += 1

    if progress_cb:
        progress_cb(f"✅ Audio dividido en {len(parts)} partes.")
    return parts
