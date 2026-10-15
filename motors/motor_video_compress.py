"""
motors/motor_video_compress.py — Ajustar un video a un tamaño máximo:
comprimirlo o cortarlo en partes, con informe técnico y hash de cada archivo.
"""
import hashlib
import json
import math
import os
import shutil
import subprocess
import time
from datetime import datetime
from typing import Callable, List, Optional, Tuple

from core.paths import BIN_DIR, TEMP_DIR


# ── Tamaño objetivo por defecto ──────────────────────────────────────────
# Muchos portales, formularios y correos aceptan hasta 10 MB por archivo.
TARGET_MAX_MB  = 10.0
# Margen de seguridad para el corte sin re-encodeo (el tamaño real de cada
# parte puede desviarse unos décimos por los keyframes).
TARGET_SAFE_MB = 9.5


# ── Binarios ──────────────────────────────────────────────────────────────

def _find_bin(name: str) -> Optional[str]:
    for candidate in [f"{name}.exe", name]:
        local = os.path.join(str(BIN_DIR), candidate)
        if os.path.isfile(local):
            return local
    return shutil.which(name)


FFMPEG  = _find_bin("ffmpeg")
FFPROBE = _find_bin("ffprobe")


def is_available() -> bool:
    return FFMPEG is not None and FFPROBE is not None


# ── Hash SHA-256 en bloques de 1 MB ─────────────────────────────────────

def sha256_file(path: str, pct_cb: Optional[Callable[[int], None]] = None) -> str:
    """pct_cb(0–100) avisa el avance (un video de varios GB tarda)."""
    h = hashlib.sha256()
    total = os.path.getsize(path) or 1
    leido = 0
    ultimo = -1
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1048576), b""):
            h.update(chunk)
            if pct_cb:
                leido += len(chunk)
                pct = int(leido * 100 / total)
                if pct != ultimo:
                    ultimo = pct
                    pct_cb(pct)
    return h.hexdigest()


# ── FFmpeg con avance ────────────────────────────────────────────────────

def _ffmpeg_con_avance(cmd: List[str], duracion: float,
                       pct_cb: Optional[Callable[[int], None]],
                       desde: float = 0.0, hasta: float = 100.0) -> None:
    """Corre FFmpeg y va avisando el porcentaje, entre `desde` y `hasta`.

    FFmpeg informa por dónde va (-progress); con eso y la duración del video
    sale el porcentaje. No tiene tiempo límite: recodificar una hora de
    video puede tardar mucho más que los 10 minutos que había antes, y se
    cortaba a mitad de camino. Lanza RuntimeError con el final del error.
    """
    import tempfile
    cmd = [cmd[0], "-progress", "pipe:1", "-nostats"] + cmd[1:]
    with tempfile.TemporaryFile() as errores:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=errores,
            stdin=subprocess.DEVNULL, text=True, encoding="utf-8",
            errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        ultimo = -1
        for linea in proc.stdout:
            if not pct_cb or duracion <= 0:
                continue
            clave, _, valor = linea.strip().partition("=")
            if clave not in ("out_time_us", "out_time_ms"):
                continue
            try:
                hecho = int(valor) / 1_000_000 / duracion
            except ValueError:
                continue
            pct = int(desde + (hasta - desde) * max(0.0, min(1.0, hecho)))
            if pct != ultimo:
                ultimo = pct
                pct_cb(pct)
        proc.wait()
        if proc.returncode != 0:
            errores.seek(0)
            raise RuntimeError(
                errores.read().decode(errors="replace")[-500:])
    if pct_cb:
        pct_cb(int(hasta))


# ── Información de video via FFprobe ────────────────────────────────────

def get_video_info(path: str) -> dict:
    """duration (seg), bit_rate (bps), size_bytes, size_mb."""
    if not FFPROBE:
        raise RuntimeError("FFprobe no disponible.")
    cmd = [
        FFPROBE, "-v", "quiet",
        "-print_format", "json",
        "-show_format", "-show_streams",
        path,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    data = json.loads(r.stdout or "{}")
    fmt       = data.get("format", {})
    duration  = float(fmt.get("duration", 0))
    bit_rate  = int(fmt.get("bit_rate", 0))
    size_bytes = os.path.getsize(path)
    size_mb    = size_bytes / (1024 * 1024)
    return {
        "duration":   duration,
        "bit_rate":   bit_rate,
        "size_bytes": size_bytes,
        "size_mb":    size_mb,
    }


# ── Helpers de estimación para la GUI ───────────────────────────────────

def estimate_target_quality(duration_secs: float, target_mb: float = TARGET_MAX_MB) -> Tuple[float, str]:
    """Retorna (bitrate_kbps, mensaje_calidad) para llegar al tamaño objetivo."""
    if duration_secs <= 0:
        return 0.0, ""
    bitrate_kbps = (target_mb * 8192) / duration_secs
    if bitrate_kbps < 800:
        msg = (f"⚠️  Calidad Mala / Controlar. El video es muy largo para "
               f"entrar en {target_mb:g} MB.")
    else:
        msg = "✅  Calidad Buena/Aceptable para visualización móvil."
    return bitrate_kbps, msg


def estimate_split_parts(size_mb: float, safe_mb: float = TARGET_SAFE_MB) -> int:
    """Partes = ceil(size_mb / TARGET_SAFE_MB)."""
    return max(1, math.ceil(size_mb / safe_mb))


# ── Cálculo de bitrates para dos pasadas ────────────────────────────────

def _calc_bitrates(duration_secs: float, target_mb: float) -> Tuple[int, int]:
    """Devuelve (video_kbps, audio_kbps) para alcanzar target_mb."""
    total_kbps = int((target_mb * 8 * 1024) / duration_secs)
    if total_kbps < 300:
        audio_kbps = 64
    elif total_kbps < 500:
        audio_kbps = 96
    else:
        audio_kbps = 128
    video_kbps = max(total_kbps - audio_kbps, 100)
    return video_kbps, audio_kbps


# ── Compresión con dos pasadas ───────────────────────────────────────────

def compress_video(
    src: str,
    dst: str,
    target_mb: float,
    progress_cb: Optional[Callable[[str], None]] = None,
    pct_cb: Optional[Callable[[int], None]] = None,
) -> None:
    """Comprime src → dst apuntando a target_mb con two-pass libx264/AAC."""
    if not is_available():
        raise RuntimeError("FFmpeg/FFprobe no disponibles.")

    info     = get_video_info(src)
    duration = info["duration"]
    if duration <= 0:
        raise RuntimeError("No se pudo determinar la duración del video.")

    v_kbps, a_kbps = _calc_bitrates(duration, target_mb)

    if progress_cb:
        progress_cb(
            f"⚙️  Objetivo {target_mb:.1f} MB  "
            f"(video {v_kbps} kbps · audio {a_kbps} kbps)…"
        )

    tmp_dir = os.path.join(
        str(TEMP_DIR), f"compress_pass_{os.getpid()}_{int(time.time()*1000)}"
    )
    os.makedirs(tmp_dir, exist_ok=True)
    passlog  = os.path.join(tmp_dir, "pass")
    null_out = "NUL" if os.name == "nt" else "/dev/null"

    try:
        if progress_cb:
            progress_cb("⚙️  Pasada 1/2 (análisis)…")
        cmd1 = [
            FFMPEG, "-y", "-i", src,
            "-c:v", "libx264", "-b:v", f"{v_kbps}k",
            "-pass", "1", "-passlogfile", passlog,
            "-an", "-f", "null", null_out,
        ]
        try:
            _ffmpeg_con_avance(cmd1, duration, pct_cb, 0, 45)
        except RuntimeError as e:
            raise RuntimeError(f"Pasada 1 falló:\n{e}")

        if progress_cb:
            progress_cb("⚙️  Pasada 2/2 (codificación)…")
        dst_dir = os.path.dirname(dst)
        if dst_dir:
            os.makedirs(dst_dir, exist_ok=True)
        cmd2 = [
            FFMPEG, "-y", "-i", src,
            "-c:v", "libx264", "-b:v", f"{v_kbps}k",
            "-pass", "2", "-passlogfile", passlog,
            "-c:a", "aac", "-b:a", f"{a_kbps}k",
            dst,
        ]
        try:
            _ffmpeg_con_avance(cmd2, duration, pct_cb, 45, 100)
        except RuntimeError as e:
            raise RuntimeError(f"Pasada 2 falló:\n{e}")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    if not os.path.exists(dst) or os.path.getsize(dst) == 0:
        raise RuntimeError("El archivo comprimido no fue generado correctamente.")

    if progress_cb:
        actual_mb = os.path.getsize(dst) / (1024 * 1024)
        progress_cb(f"✅  Compresión completa → {actual_mb:.1f} MB reales")


# ── Corte en partes sin re-encodeo ──────────────────────────────────────

def split_video_by_size(
    src: str,
    output_dir: str,
    progress_cb: Optional[Callable[[str], None]] = None,
    pct_cb: Optional[Callable[[int], None]] = None,
) -> List[str]:
    """Divide src en partes ≤TARGET_SAFE_MB con -c copy (corte sin pérdida)."""
    if not is_available():
        raise RuntimeError("FFmpeg/FFprobe no disponibles.")

    info      = get_video_info(src)
    duration  = info["duration"]
    size_mb   = info["size_mb"]
    if duration <= 0:
        raise RuntimeError("No se pudo determinar la duración del video.")

    num_parts     = estimate_split_parts(size_mb)
    secs_per_part = duration / num_parts
    stem          = os.path.splitext(os.path.basename(src))[0]
    ext           = os.path.splitext(src)[1]
    os.makedirs(output_dir, exist_ok=True)

    parts = []
    for i in range(num_parts):
        start    = i * secs_per_part
        out_name = f"{stem}_Parte_{i+1}de{num_parts}{ext}"
        out_path = os.path.join(output_dir, out_name)

        if progress_cb:
            end = min(start + secs_per_part, duration)
            progress_cb(f"✂️  Parte {i+1}/{num_parts}  ({start:.0f}s → {end:.0f}s)…")

        cmd = [
            FFMPEG, "-y",
            "-ss", str(start),
            "-i", src,
            "-t", str(secs_per_part),
            "-c", "copy",
            "-avoid_negative_ts", "make_zero",
            out_path,
        ]
        r = subprocess.run(cmd, capture_output=True, timeout=300)
        if r.returncode != 0:
            raise RuntimeError(
                f"Error en parte {i+1}:\n"
                f"{r.stderr.decode(errors='replace')[-400:]}"
            )
        if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            parts.append(out_path)
        if pct_cb:
            pct_cb(int((i + 1) * 100 / num_parts))

    if progress_cb:
        progress_cb(f"✅  Video cortado en {len(parts)} partes.")
    return parts


# ── Organización en Tandas ───────────────────────────────────────────────

def organize_in_tandas(files: List[str], operation_dir: str) -> List[str]:
    """Mueve files a Tanda_1, Tanda_2… (5 por tanda) dentro de operation_dir."""
    MAX_PER_TANDA = 5
    final = []
    for i, src in enumerate(files):
        tanda_num = (i // MAX_PER_TANDA) + 1
        tanda_dir = os.path.join(operation_dir, f"Tanda_{tanda_num}")
        os.makedirs(tanda_dir, exist_ok=True)
        dst = os.path.join(tanda_dir, os.path.basename(src))
        shutil.move(src, dst)
        final.append(dst)
    return final


# ── Informe técnico ─────────────────────────────────────────────────────

_MESES = [
    "", "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def _fecha_formal() -> str:
    hoy = datetime.now()
    return f"{hoy.day:02d} de {_MESES[hoy.month]} de {hoy.year}"


def write_informe(
    operation_dir: str,
    operation_name: str,
    originals: List[dict],   # [{"filename": ..., "sha256": ...}, ...]
    results: List[dict],     # [{"filename": ..., "sha256": ...}, ...]
    is_split: bool = False,
) -> str:
    """Genera el informe técnico. Devuelve ruta del .txt creado."""
    from core.informe import ref_objeto

    fecha = _fecha_formal()
    n     = len(originals)
    m     = len(results)

    ref_obj    = ref_objeto(n)                                  # el/los archivo(s)
    ref_de     = "del archivo" if n == 1 else "de los archivos"
    ref_mismos = "del mismo"   if n == 1 else "de los mismos"

    accion = (
        f"segmentar en fragmentos menores a {TARGET_MAX_MB:g} Megabytes {ref_obj}"
        if is_split
        else f"comprimir el tamaño de almacenamiento {ref_de}"
    )

    orig_lines = ""
    for o in originals:
        orig_lines += f"\n- Archivo: {o['filename']}\n  SHA-256: {o['sha256']}\n"

    result_lines = ""
    for r in results:
        result_lines += f"- {r['filename']} (SHA-256: {r['sha256']})\n"

    texto = (
        "INFORME TÉCNICO DE PROCESAMIENTO DIGITAL\n"
        "\n"
        f"El día de la fecha ({fecha}) se procedió a {accion} que se "
        f"detalla{'n' if n > 1 else ''} a continuación:\n"
        f"{orig_lines}\n"
        f"El proceso puede haber reducido la calidad {ref_mismos}. "
        f"{'El original no se modificó' if n == 1 else 'Los originales no se modificaron'}.\n"
        "\n"
        f"{'Detalle del archivo resultante' if m == 1 else 'Detalle de los archivos resultantes'}:\n"
        f"{result_lines}"
    )

    os.makedirs(operation_dir, exist_ok=True)
    out_path = os.path.join(operation_dir, f"Informe_{operation_name}.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(texto)
    return out_path
