"""
motors/motor_video_splitter.py — Partidor de video sin re-encodeo.
"""
import json
import os
import shutil
import subprocess
from typing import Callable, List, Optional

from core.paths import BIN_DIR, TEMP_DIR


def _find_ffmpeg():
    for name in ["ffmpeg.exe", "ffmpeg"]:
        local = os.path.join(BIN_DIR, name)
        if os.path.isfile(local):
            return local
    return shutil.which("ffmpeg")


def _find_ffprobe():
    for name in ["ffprobe.exe", "ffprobe"]:
        local = os.path.join(BIN_DIR, name)
        if os.path.isfile(local):
            return local
    return shutil.which("ffprobe")


FFMPEG  = _find_ffmpeg()
FFPROBE = _find_ffprobe()


def is_available() -> bool:
    return FFMPEG is not None and FFPROBE is not None


def get_video_info(src_path: str) -> dict:
    """Retorna duración en segundos y bitrate del video."""
    if not FFPROBE:
        raise RuntimeError("FFprobe no disponible.")
    cmd = [
        FFPROBE, "-v", "quiet",
        "-print_format", "json",
        "-show_format", "-show_streams",
        src_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    data = json.loads(result.stdout)
    fmt = data.get("format", {})
    duration = float(fmt.get("duration", 0))
    bit_rate = int(fmt.get("bit_rate", 0))
    return {"duration": duration, "bit_rate": bit_rate}


def estimate_parts(src_path: str, max_size_mb: float, info: dict = None) -> int:
    """Estima cuántas partes se generarán.

    Si ya se tiene la ficha del video (`info`, de get_video_info) se usa esa
    y no se vuelve a leer el archivo.
    """
    try:
        info = info or get_video_info(src_path)
        if info["bit_rate"] <= 0:
            return 0
        secs_per_part = (max_size_mb * 8 * 1024 * 1024) / info["bit_rate"]
        parts = max(1, int(info["duration"] / secs_per_part) + 1)
        return parts
    except Exception:
        return 0


def split_video(
    src_path: str,
    output_dir: str,
    max_size_mb: float,
    progress_cb: Optional[Callable[[str], None]] = None,
    pct_cb: Optional[Callable[[int], None]] = None,
) -> List[str]:
    """
    Divide el video en partes de máximo max_size_mb MB sin re-encodear.
    Devuelve la lista de rutas de los archivos generados.
    """
    if not is_available():
        raise RuntimeError(
            "El partidor de video necesita FFmpeg.\n"
            "Colocá ffmpeg.exe y ffprobe.exe en la carpeta bin/ del programa."
        )

    info = get_video_info(src_path)
    duration = info["duration"]
    bit_rate = info["bit_rate"]

    if bit_rate <= 0:
        raise RuntimeError(
            "No se pudo determinar el bitrate del video.\n"
            "El archivo puede estar dañado o en un formato no compatible."
        )

    secs_per_part = (max_size_mb * 8 * 1024 * 1024) / bit_rate
    secs_per_part = max(secs_per_part, 1.0)

    ext = os.path.splitext(src_path)[1]
    stem = os.path.splitext(os.path.basename(src_path))[0]
    out_subdir = output_dir
    os.makedirs(out_subdir, exist_ok=True)

    parts = []
    part_num = 1
    start = 0.0

    while start < duration:
        part_name = f"{stem}_parte{part_num:02d}{ext}"
        part_path = os.path.join(out_subdir, part_name)

        if progress_cb:
            progress_cb(f"✂️  Generando parte {part_num} ({start:.0f}s - {min(start+secs_per_part, duration):.0f}s)...")

        cmd = [
            FFMPEG, "-y",
            "-ss", str(start),
            "-i", src_path,
            "-t", str(secs_per_part),
            "-c", "copy",
            "-avoid_negative_ts", "make_zero",
            part_path
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=300)
        if result.returncode != 0:
            raise RuntimeError(
                f"Error al generar la parte {part_num}.\n"
                "Verificá que el archivo no esté dañado."
            )

        if os.path.exists(part_path) and os.path.getsize(part_path) > 0:
            parts.append(part_path)

        start += secs_per_part
        part_num += 1
        if pct_cb:
            pct_cb(int(min(start, duration) * 100 / duration))

    if progress_cb:
        progress_cb(f"✅ Video dividido en {len(parts)} partes.")
    return parts
