"""
motors/motor_audio_merger.py — Une múltiples archivos de audio con FFmpeg.
Concatena sin re-encodeo cuando todos tienen el mismo formato/codec.
"""
import json
import os
import shutil
import tempfile
from typing import Callable, List, Optional


AUDIO_EXTS = {
    ".mp3", ".wav", ".flac", ".aac", ".ogg", ".opus",
    ".m4a", ".m4b", ".wma", ".aiff", ".aif", ".au",
    ".ac3", ".ape", ".mka", ".caf", ".ra", ".dts",
}


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
    return FFMPEG is not None


def collect_audio_files(folder: str) -> List[str]:
    return sorted([
        os.path.join(folder, f)
        for f in os.listdir(folder)
        if os.path.splitext(f)[1].lower() in AUDIO_EXTS
    ])


def get_duration(path: str) -> float:
    if not FFPROBE:
        return 0.0
    cmd = [FFPROBE, "-v", "quiet", "-print_format", "json", "-show_format", path]
    import subprocess
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    try:
        return float(json.loads(result.stdout).get("format", {}).get("duration", 0))
    except Exception:
        return 0.0


def merge_audio(
    files: List[str],
    output_dir: str,
    max_mb: float,
    progress_cb: Optional[Callable[[str], None]] = None,
) -> List[str]:
    """
    Concatena archivos de audio y parte el resultado en chunks de max_mb MB.
    Todos los archivos de entrada deben tener la misma extensión.
    Devuelve lista de rutas generadas.
    """
    import subprocess

    if not files:
        raise ValueError("No se encontraron archivos de audio.")
    if not FFMPEG:
        raise RuntimeError("FFmpeg no disponible.")

    os.makedirs(output_dir, exist_ok=True)

    # Agrupar por extensión y procesar cada grupo
    from collections import defaultdict
    groups = defaultdict(list)
    for f in files:
        ext = os.path.splitext(f)[1].lower()
        groups[ext].append(f)

    out_paths = []
    for ext, group_files in sorted(groups.items()):
        if progress_cb:
            progress_cb(f"Procesando {len(group_files)} archivo{'s' if len(group_files)!=1 else ''} {ext.upper()}...")

        group_out = _merge_group(group_files, output_dir, ext, max_mb, progress_cb, subprocess)
        out_paths.extend(group_out)

    if progress_cb:
        progress_cb(f"✅ {len(out_paths)} archivo{'s' if len(out_paths)!=1 else ''} generado{'s' if len(out_paths)!=1 else ''}.")
    return out_paths


def _merge_group(files, output_dir, ext, max_mb, progress_cb, subprocess_mod):
    """Une un grupo de archivos con la misma extensión."""
    max_bytes = max_mb * 1024 * 1024

    # Crear archivo de lista para FFmpeg concat demuxer
    tmp_list = tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    )
    for f in files:
        tmp_list.write(f"file '{f.replace(chr(39), chr(39)+chr(92)+chr(39)+chr(39))}'\n")
    tmp_list.close()

    # Archivo temporal con todo concatenado
    tmp_merged = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
    tmp_merged.close()

    try:
        if progress_cb:
            progress_cb(f"  Concatenando {len(files)} archivos...")

        cmd = [
            FFMPEG, "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", tmp_list.name,
            "-c", "copy",
            tmp_merged.name,
        ]
        result = subprocess_mod.run(cmd, capture_output=True, timeout=600)
        if result.returncode != 0:
            # Fallback: re-encode a mp3 si el concat directo falla
            if progress_cb:
                progress_cb("  ⚠ Concat directo falló, re-encodeando a MP3...")
            tmp_merged2 = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            tmp_merged2.close()
            cmd2 = [
                FFMPEG, "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", tmp_list.name,
                "-codec:a", "libmp3lame", "-q:a", "2",
                tmp_merged2.name,
            ]
            result2 = subprocess_mod.run(cmd2, capture_output=True, timeout=600)
            if result2.returncode != 0:
                raise RuntimeError(
                    f"Error al concatenar archivos {ext}.\n"
                    f"{result2.stderr.decode(errors='replace')[-400:]}"
                )
            os.unlink(tmp_merged.name)
            tmp_merged_path = tmp_merged2.name
            ext = ".mp3"
        else:
            tmp_merged_path = tmp_merged.name

        # Partir el resultado en chunks por tamaño
        out_paths = _split_by_size(tmp_merged_path, output_dir, ext, max_bytes, progress_cb, subprocess_mod)

    finally:
        os.unlink(tmp_list.name)
        for p in [tmp_merged.name]:
            try:
                os.unlink(p)
            except Exception:
                pass

    return out_paths


def _split_by_size(merged_path, output_dir, ext, max_bytes, progress_cb, subprocess_mod):
    """Parte merged_path en archivos de máx max_bytes bytes."""
    total_size = os.path.getsize(merged_path)

    if total_size <= max_bytes:
        # No hace falta partir
        out_name = f"unido_completo{ext}"
        out_path = os.path.join(output_dir, out_name)
        import shutil as _sh
        _sh.copy2(merged_path, out_path)
        size_mb = total_size / (1024 * 1024)
        if progress_cb:
            progress_cb(f"  ✅ {out_name}  ({size_mb:.1f} MB)")
        return [out_path]

    # Obtener duración total para estimar segundos por chunk
    duration = get_duration(merged_path)
    if duration <= 0:
        raise RuntimeError("No se pudo determinar la duración del archivo combinado.")

    bitrate = (total_size * 8) / duration  # bits por segundo
    secs_per_chunk = (max_bytes * 8) / bitrate
    secs_per_chunk = max(secs_per_chunk, 1.0)

    out_paths = []
    part_num  = 1
    start     = 0.0

    while start < duration:
        out_name = f"unido_parte{part_num:02d}{ext}"
        out_path = os.path.join(output_dir, out_name)
        end = min(start + secs_per_chunk, duration)

        if progress_cb:
            progress_cb(
                f"  Parte {part_num}: {int(start//60)}:{int(start%60):02d} → "
                f"{int(end//60)}:{int(end%60):02d}..."
            )

        cmd = [
            FFMPEG, "-y",
            "-ss", str(start),
            "-i", merged_path,
            "-t", str(secs_per_chunk),
            "-c", "copy",
            out_path,
        ]
        result = subprocess_mod.run(cmd, capture_output=True, timeout=300)
        if result.returncode != 0:
            raise RuntimeError(f"Error generando parte {part_num}.")

        if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            size_mb = os.path.getsize(out_path) / (1024 * 1024)
            if progress_cb:
                progress_cb(f"  ✅ {out_name}  ({size_mb:.1f} MB)")
            out_paths.append(out_path)

        start    += secs_per_chunk
        part_num += 1

    return out_paths
