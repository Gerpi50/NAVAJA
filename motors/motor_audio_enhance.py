"""
motors/motor_audio_enhance.py — Mejorar el audio de una grabación.

Pensado para grabaciones donde la voz se escucha mal: un micrófono de
ambiente, ruido de fondo, alguien que habla bajito lejos del micrófono (por
ejemplo una cámara Gesell). Trabaja sobre archivos de audio y sobre el audio
de un video.

No hay una receta que sirva para todas las grabaciones, así que los ajustes
se eligen a oído: `muestra()` saca unos segundos del archivo real, con o sin
los ajustes, para escucharlos antes de procesar todo.

El original nunca se toca: `mejorar()` escribe siempre un archivo nuevo. En
un video la imagen se copia tal cual (sin recodificar) y sólo cambia el audio.
"""
import json
import os
import subprocess
from typing import Callable, Dict, List, Optional

from motors.motor_video_compress import FFMPEG, FFPROBE, _ffmpeg_con_avance


# ── Las perillas ─────────────────────────────────────────────────────────
# (clave, nombre, mínimo, máximo, ayuda). Todas arrancan en 0 = sin tocar.
PERILLAS = [
    ("ruido",   "Ruido de fondo", 0, 10,
     "Baja el soplido parejo de fondo: aire acondicionado, ventilador, "
     "el siseo del micrófono.\nSi te pasás, la voz suena metálica o «bajo "
     "el agua»."),
    ("graves",  "Zumbido y golpes", 0, 10,
     "Saca los sonidos muy graves: zumbido eléctrico, golpes en la mesa, "
     "pasos, motores.\nSi te pasás, la voz queda finita."),
    ("agudos",  "Siseo agudo", 0, 10,
     "Saca los sonidos muy agudos: siseo, chirridos.\nSi te pasás, la voz "
     "queda apagada y se pierden las eses."),
    ("voz",     "Realzar la voz", 0, 10,
     "Levanta la zona donde están las consonantes, que es lo que hace que "
     "se entiendan las palabras."),
    ("parejo",  "Emparejar volumen", 0, 10,
     "Sube las partes donde se habla bajito y deja como están las fuertes: "
     "sirve cuando uno habla cerca del micrófono y el otro lejos.\nTambién "
     "sube el ruido en los silencios: combinalo con «Ruido de fondo»."),
    ("volumen", "Volumen", -10, 20,
     "Sube o baja todo el audio por igual (en decibeles)."),
]

AJUSTES_EN_CERO: Dict[str, int] = {clave: 0 for clave, *_ in PERILLAS}

# Puntos de partida. No están medidos contra una grabación en particular:
# son para empezar y corregir a oído con la prueba.
PREAJUSTES = [
    ("Suave",         dict(ruido=3, graves=2, agudos=0, voz=2, parejo=3, volumen=0)),
    ("Medio",         dict(ruido=5, graves=3, agudos=2, voz=4, parejo=5, volumen=0)),
    ("Fuerte",        dict(ruido=8, graves=4, agudos=4, voz=6, parejo=7, volumen=0)),
    ("Cámara Gesell", dict(ruido=6, graves=4, agudos=2, voz=6, parejo=8, volumen=3)),
]

EXT_VIDEO = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".wmv", ".m4v",
             ".3gp", ".ts", ".mpg", ".mpeg", ".ogv", ".vob", ".mts", ".m2ts"}
EXT_AUDIO = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".opus", ".flac", ".wma",
             ".amr", ".aiff", ".aif", ".ac3", ".mka", ".3ga"}

# Con qué se guarda el audio según la extensión de salida.
_CODEC_AUDIO = {
    ".mp3":  ["-c:a", "libmp3lame", "-b:a", "192k"],
    ".m4a":  ["-c:a", "aac", "-b:a", "192k"],
    ".aac":  ["-c:a", "aac", "-b:a", "192k"],
    ".wav":  ["-c:a", "pcm_s16le"],
    ".flac": ["-c:a", "flac"],
    ".ogg":  ["-c:a", "libvorbis", "-q:a", "5"],
    ".opus": ["-c:a", "libopus", "-b:a", "128k"],
}
# Contenedores de video que aceptan audio AAC con la imagen copiada tal cual.
_VIDEO_CON_AAC = {".mp4", ".mkv", ".mov", ".m4v"}


def is_available() -> bool:
    return FFMPEG is not None and FFPROBE is not None


# ── Ficha del archivo ────────────────────────────────────────────────────

def info(ruta: str) -> dict:
    """duracion (s), tiene_audio, tiene_video, y datos del audio."""
    if not FFPROBE:
        raise RuntimeError("FFprobe no disponible.")
    r = subprocess.run(
        [FFPROBE, "-v", "quiet", "-print_format", "json",
         "-show_format", "-show_streams", ruta],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=60, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    datos = json.loads(r.stdout or "{}")
    pistas = datos.get("streams", [])
    audio = next((p for p in pistas if p.get("codec_type") == "audio"), None)
    # Una carátula de MP3 figura como "video": no cuenta.
    video = next((p for p in pistas if p.get("codec_type") == "video"
                  and not p.get("disposition", {}).get("attached_pic")), None)
    try:
        duracion = float(datos.get("format", {}).get("duration", 0) or 0)
    except ValueError:
        duracion = 0.0
    return {
        "duracion":    duracion,
        "tiene_audio": audio is not None,
        "tiene_video": video is not None,
        "codec":       (audio or {}).get("codec_name", ""),
        "canales":     int((audio or {}).get("channels", 0) or 0),
        "muestreo":    int((audio or {}).get("sample_rate", 0) or 0),
    }


# ── De las perillas a los filtros de FFmpeg ──────────────────────────────

def _limpio(ajustes: Optional[dict]) -> Dict[str, int]:
    a = dict(AJUSTES_EN_CERO)
    for clave, _nombre, minimo, maximo, _ayuda in PERILLAS:
        try:
            a[clave] = max(minimo, min(maximo, int((ajustes or {}).get(clave, 0))))
        except (TypeError, ValueError):
            a[clave] = 0
    return a


def hay_cambios(ajustes: Optional[dict]) -> bool:
    return any(_limpio(ajustes).values())


def cadena_filtros(ajustes: Optional[dict]) -> str:
    """Los filtros de FFmpeg para esos ajustes ("" si está todo en cero).

    El orden importa: primero se saca lo que sobra (graves, agudos, ruido) y
    después se levanta lo que queda (voz, volumen). Al revés, se le subiría
    el volumen también al ruido antes de sacarlo.
    """
    a = _limpio(ajustes)
    filtros: List[str] = []
    if a["graves"]:
        filtros.append(f"highpass=f={40 + 26 * a['graves']}")           # 66–300 Hz
    if a["agudos"]:
        filtros.append(f"lowpass=f={16000 - 1100 * a['agudos']}")       # 14900–5000 Hz
    if a["ruido"]:
        # nr: cuánto baja el ruido (dB); nf: piso de ruido; tn: lo sigue solo
        filtros.append(f"afftdn=nr={6 + 3 * a['ruido']}"
                       f":nf={-52 + a['ruido']}:tn=1")
    if a["voz"]:
        filtros.append(f"equalizer=f=2800:t=o:w=1.6:g={1.2 * a['voz']:.1f}")
    if a["parejo"]:
        # m: cuánto puede llegar a subir las partes bajas
        filtros.append(f"dynaudnorm=f=250:g=11:p=0.9:m={1 + 2.4 * a['parejo']:.1f}")
    if a["volumen"]:
        filtros.append(f"volume={a['volumen']}dB")
    if filtros:
        filtros.append("alimiter=limit=0.95")       # que nada sature
    return ",".join(filtros)


def descripcion(ajustes: Optional[dict]) -> str:
    """Los ajustes en palabras, para el informe."""
    a = _limpio(ajustes)
    partes = []
    if a["ruido"]:
        partes.append(f"reducción de ruido de fondo {a['ruido']}/10")
    if a["graves"]:
        partes.append(f"corte de graves por debajo de {40 + 26 * a['graves']} Hz")
    if a["agudos"]:
        partes.append(f"corte de agudos por encima de {16000 - 1100 * a['agudos']} Hz")
    if a["voz"]:
        partes.append(f"realce de la voz de {1.2 * a['voz']:.1f} dB")
    if a["parejo"]:
        partes.append(f"emparejado de volumen {a['parejo']}/10")
    if a["volumen"]:
        partes.append(f"volumen {a['volumen']:+d} dB")
    return ", ".join(partes) if partes else "sin ajustes"


# ── Probar unos segundos ─────────────────────────────────────────────────

def muestra(src: str, dst_wav: str, desde: float, segundos: float,
            ajustes: Optional[dict] = None) -> str:
    """Saca `segundos` del archivo desde `desde`, a un WAV para escuchar.

    Con ajustes=None (o todo en cero) sale el sonido original.
    """
    if not is_available():
        raise RuntimeError("Hace falta FFmpeg (bin/ffmpeg.exe).")
    cmd = [FFMPEG, "-y", "-v", "error",
           "-ss", f"{max(0.0, desde):.3f}", "-t", f"{segundos:.3f}",
           "-i", src, "-vn", "-sn", "-map", "0:a:0"]
    filtros = cadena_filtros(ajustes)
    if filtros:
        cmd += ["-af", filtros]
    # WAV de 16 bits: lo que reproduce Windows sin instalar nada.
    cmd += ["-ac", "2", "-ar", "44100", "-c:a", "pcm_s16le", dst_wav]
    r = subprocess.run(cmd, capture_output=True, timeout=120,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if r.returncode != 0 or not os.path.isfile(dst_wav) \
            or os.path.getsize(dst_wav) < 1000:
        raise RuntimeError(
            "No pude sacar la muestra de audio.\n"
            + r.stderr.decode(errors="replace")[-400:])
    return dst_wav


# ── Procesar el archivo entero ───────────────────────────────────────────

def nombre_salida(src: str, carpeta: str, ficha: Optional[dict] = None) -> str:
    """Ruta del archivo nuevo: mismo nombre + «_audio_mejorado»."""
    ficha = ficha or info(src)
    base, ext = os.path.splitext(os.path.basename(src))
    ext = ext.lower()
    if ficha["tiene_video"]:
        # .avi, .wmv y otros no aceptan bien el audio nuevo: van a .mkv,
        # que guarda cualquier imagen sin recodificarla.
        ext_out = ext if ext in _VIDEO_CON_AAC else ".mkv"
    else:
        ext_out = ext if ext in _CODEC_AUDIO else ".mp3"
    ruta = os.path.join(carpeta, f"{base}_audio_mejorado{ext_out}")
    n = 2
    while os.path.exists(ruta):
        ruta = os.path.join(carpeta, f"{base}_audio_mejorado_{n}{ext_out}")
        n += 1
    return ruta


def mejorar(src: str, dst: str, ajustes: dict,
            progress_cb: Optional[Callable[[str], None]] = None,
            pct_cb: Optional[Callable[[int], None]] = None) -> str:
    """Escribe en `dst` una copia de `src` con el audio mejorado."""
    if not is_available():
        raise RuntimeError("Hace falta FFmpeg (bin/ffmpeg.exe).")
    filtros = cadena_filtros(ajustes)
    if not filtros:
        raise RuntimeError(
            "Todas las perillas están en cero: no hay nada para mejorar.")
    ficha = info(src)
    if not ficha["tiene_audio"]:
        raise RuntimeError("Ese archivo no tiene audio.")
    if os.path.abspath(src) == os.path.abspath(dst):
        raise RuntimeError("El archivo nuevo no puede pisar al original.")

    os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
    ext = os.path.splitext(dst)[1].lower()
    cmd = [FFMPEG, "-y", "-i", src]
    if ficha["tiene_video"]:
        if progress_cb:
            progress_cb("🎚  Mejorando el audio (la imagen se copia tal cual)…")
        cmd += ["-map", "0:v:0", "-map", "0:a:0", "-c:v", "copy",
                "-af", filtros, "-c:a", "aac", "-b:a", "192k"]
    else:
        if progress_cb:
            progress_cb("🎚  Mejorando el audio…")
        cmd += ["-vn", "-map", "0:a:0", "-af", filtros]
        cmd += _CODEC_AUDIO.get(ext, _CODEC_AUDIO[".mp3"])
    cmd.append(dst)

    try:
        _ffmpeg_con_avance(cmd, ficha["duracion"], pct_cb)
    except RuntimeError as e:
        if os.path.exists(dst):
            try:
                os.remove(dst)
            except OSError:
                pass
        raise RuntimeError(f"No se pudo procesar el archivo:\n{e}")
    if not os.path.isfile(dst) or os.path.getsize(dst) == 0:
        raise RuntimeError("El archivo mejorado no se generó.")
    if progress_cb:
        progress_cb("✅  Audio mejorado.")
    return dst
