"""
motors/motor_video_frames.py — Captura de fotogramas de video, con el tiempo
exacto del fotograma capturado.

Pensado para trabajo pericial: el investigador mira la grabación de una cámara,
encuentra el momento del hecho y se lleva esa imagen con el minuto y segundo
precisos, más una constancia con los hashes para que la prueba sea verificable.

Tres reglas que ordenan todo lo de acá abajo:

  1. **Nunca se estampa el tiempo pedido, sino el del fotograma entregado.**
     Si se pide el segundo 17.320 y el fotograma más cercano está en 17.280,
     la constancia dice 17.280. FFmpeg, al hacer `-ss t`, devuelve el primer
     fotograma cuyo tiempo sea >= t; después se le pregunta a FFprobe cuál
     fue ese tiempo de verdad.

  2. **La imagen no se retoca.** PNG (sin pérdida), resolución nativa, sin
     escalar, sin desentrelazar y sin filtros. El JPG inventa manchas en los
     bordes y eso es veneno si después hay que ampliar una patente o una cara.

  3. **Lo que se ve es lo que se guarda.** El panel muestra el PNG que sacó
     FFmpeg; al capturar se copia ese mismo archivo, no se vuelve a generar.
"""
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timedelta
from typing import List, Optional

from core.paths import BIN_DIR, TEMP_DIR


# ── Herramientas externas ────────────────────────────────────────────────────

def _buscar(nombres: List[str]) -> Optional[str]:
    for nombre in nombres:
        local = os.path.join(BIN_DIR, nombre)
        if os.path.isfile(local):
            return local
    return shutil.which(nombres[0].replace(".exe", ""))


FFMPEG = _buscar(["ffmpeg.exe", "ffmpeg"])
FFPROBE = _buscar(["ffprobe.exe", "ffprobe"])

# En Windows, subprocess abre una ventana de consola negra por cada llamada.
# Como acá se llama a FFmpeg en cada paso del navegador, se esconde.
_SIN_VENTANA = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def is_available() -> bool:
    return FFMPEG is not None and FFPROBE is not None


def _correr(cmd: List[str], timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True,
                          timeout=timeout, creationflags=_SIN_VENTANA)


# ── Formato de tiempo ────────────────────────────────────────────────────────

def hms(segundos: float) -> str:
    """0:04:17.32 → "00:04:17.320" (con milésimas, que es lo que se firma)."""
    if segundos is None or segundos < 0:
        segundos = 0.0
    total_ms = int(round(segundos * 1000))
    h, resto = divmod(total_ms, 3600000)
    m, resto = divmod(resto, 60000)
    s, ms = divmod(resto, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def segundos(texto: str) -> Optional[float]:
    """Lee "00:04:17.320", "4:17.32" o "257.32". None si no se entiende."""
    texto = (texto or "").strip().replace(",", ".")
    if not texto:
        return None
    partes = texto.split(":")
    try:
        valores = [float(p) for p in partes]
    except ValueError:
        return None
    total = 0.0
    for v in valores:
        total = total * 60 + v
    return total if total >= 0 else None


def _nombre_de_tiempo(t: float) -> str:
    """Tiempo apto para nombre de archivo: 00-04-17.320"""
    return hms(t).replace(":", "-")


# ── Ficha del video ──────────────────────────────────────────────────────────

def _fraccion(texto: str) -> float:
    """"30000/1001" → 29.97"""
    try:
        if "/" in str(texto):
            num, den = str(texto).split("/")
            den = float(den)
            return float(num) / den if den else 0.0
        return float(texto)
    except (ValueError, TypeError):
        return 0.0


# ── El cero del video no siempre es el cero del archivo ──────────────────────
#
# Muchos MP4 (cámaras, celulares, exportaciones de DVR) declaran que el flujo
# de video empieza en 0,041667 —un fotograma— y no en cero. FFmpeg cuenta ese
# desfasaje en las marcas de tiempo absolutas, así que el fotograma que
# cualquier reproductor muestra en el minuto 1:20 figura como 1:20.042.
#
# Acá todos los tiempos son **relativos al comienzo del video**, que es como
# los cuenta el usuario y como los muestra un reproductor: al leer una marca de
# tiempo se le resta este desfasaje, y al pedir un momento se le suma.

_INICIOS = {}


def _inicio_del_video(stream: dict) -> float:
    try:
        return max(0.0, float(stream.get("start_time") or 0.0))
    except (TypeError, ValueError):
        return 0.0


def _desfasaje(src_path: str) -> float:
    """Segundos entre el cero del archivo y el primer fotograma."""
    try:
        clave = (os.path.abspath(src_path), os.path.getmtime(src_path),
                 os.path.getsize(src_path))
    except OSError:
        return 0.0
    if clave in _INICIOS:
        return _INICIOS[clave]

    valor = 0.0
    if is_available():
        r = _correr([FFPROBE, "-v", "error", "-select_streams", "v:0",
                     "-show_entries", "stream=start_time",
                     "-print_format", "json", src_path], timeout=30)
        if r.returncode == 0:
            try:
                streams = json.loads(r.stdout or "{}").get("streams", [])
                if streams:
                    valor = _inicio_del_video(streams[0])
            except ValueError:
                valor = 0.0
    if len(_INICIOS) > 32:
        _INICIOS.clear()
    _INICIOS[clave] = valor
    return valor


def info_video(src_path: str) -> dict:
    """Ficha técnica del video: duración, medidas, códec, cadencia y hora de inicio."""
    if not is_available():
        raise RuntimeError(
            "La captura de fotogramas necesita FFmpeg.\n"
            "Colocá ffmpeg.exe y ffprobe.exe en la carpeta bin/ del programa."
        )
    r = _correr([FFPROBE, "-v", "error", "-print_format", "json",
                 "-show_format", "-show_streams", src_path], timeout=60)
    if r.returncode != 0:
        raise RuntimeError(f"No se pudo leer el video:\n{r.stderr[-300:]}")

    datos = json.loads(r.stdout or "{}")
    fmt = datos.get("format", {})
    video = next((s for s in datos.get("streams", [])
                  if s.get("codec_type") == "video"), {})

    fps_prom = _fraccion(video.get("avg_frame_rate", 0))
    fps_base = _fraccion(video.get("r_frame_rate", 0))
    duracion = float(fmt.get("duration") or video.get("duration") or 0.0)

    # Cadencia variable: la cámara graba más cuadros cuando hay movimiento.
    # Con VFR, "un segundo" no son N fotogramas fijos, así que no se puede
    # calcular el número de fotograma por multiplicación: hay que leerlo.
    vfr = bool(fps_prom and fps_base and abs(fps_prom - fps_base) > 0.01)

    # Hora de inicio de la grabación. Muchos DVR no la escriben, o la escriben
    # con la hora del equipo mal puesta: por eso se informa de dónde salió.
    inicio = (fmt.get("tags", {}) or {}).get("creation_time") \
        or (video.get("tags", {}) or {}).get("creation_time") or ""
    inicio_dt = None
    if inicio:
        try:
            inicio_dt = datetime.fromisoformat(inicio.replace("Z", "+00:00"))
        except ValueError:
            inicio_dt = None

    return {
        "path": src_path,
        "duracion": duracion,
        "duracion_hms": hms(duracion),
        "ancho": int(video.get("width") or 0),
        "alto": int(video.get("height") or 0),
        "codec": video.get("codec_name", "?"),
        "codec_largo": video.get("codec_long_name", ""),
        "fps": fps_prom or fps_base,
        "fps_base": fps_base,
        "vfr": vfr,
        "entrelazado": video.get("field_order", "progressive") not in
                       ("progressive", "unknown", "", None),
        "nb_frames": int(video.get("nb_frames") or 0),
        "inicio_grabacion": inicio,
        "inicio_dt": inicio_dt,
        "bit_rate": int(fmt.get("bit_rate") or 0),
        "inicio": _inicio_del_video(video),
    }


# ── Fotogramas: dónde están y cuál es cuál ───────────────────────────────────

def lista_fotogramas(src_path: str, desde: float, ventana: float = 2.0) -> List[dict]:
    """Fotogramas que hay entre `desde` y `desde + ventana`, con su tiempo real.

    Sirve para dos cosas: saber qué tiempo tiene realmente el fotograma que se
    está mirando, y moverse de a uno sin inventar cuentas (que es lo único
    que funciona cuando el video es de cadencia variable).
    """
    if not is_available():
        return []
    desde = max(0.0, desde)
    hasta = desde + ventana
    # FFprobe habla en tiempos absolutos: se le pregunta sumando el desfasaje
    # y se le resta al contestar, para que afuera todo sea relativo al
    # comienzo del video.
    inicio = _desfasaje(src_path)
    desde += inicio
    hasta += inicio
    # El intervalo se pide con el final ABSOLUTO ("5.32%6.32") y no relativo
    # ("5.32%+1"): FFprobe, para posicionarse, retrocede al cuadro clave
    # anterior, y con la forma relativa cuenta la duración desde ahí. En una
    # grabación con cuadros clave cada varios segundos —lo normal en un DVR—
    # la lista terminaba antes de llegar al momento pedido y volvía vacía.
    r = _correr([
        FFPROBE, "-v", "error", "-select_streams", "v:0",
        "-show_frames",
        "-read_intervals", f"{desde}%{hasta}",
        "-show_entries", "frame=best_effort_timestamp_time,pict_type,key_frame",
        "-print_format", "json", src_path,
    ], timeout=60)
    if r.returncode != 0:
        return []

    salida = []
    for f in json.loads(r.stdout or "{}").get("frames", []):
        ts = f.get("best_effort_timestamp_time")
        if ts is None:
            continue
        try:
            ts = float(ts)
        except (TypeError, ValueError):
            continue
        salida.append({
            "t": ts - inicio,
            "tipo": f.get("pict_type", "?"),
            "clave": bool(int(f.get("key_frame", 0) or 0)),
        })
    # Por lo anterior vienen también los fotogramas previos al momento
    # pedido: se recortan para que la función devuelva lo que promete.
    salida = [f for f in salida
              if desde - inicio - 0.0005 <= f["t"] <= hasta - inicio + 0.0005]
    salida.sort(key=lambda x: x["t"])
    return salida


def _fotograma_entregado(src_path: str, t: float) -> dict:
    """Datos del fotograma que FFmpeg devuelve al pedirle el tiempo `t`.

    FFmpeg entrega el primero cuyo tiempo sea >= t; se busca ese mismo.
    """
    for ventana in (1.0, 4.0, 15.0):
        for f in lista_fotogramas(src_path, t, ventana):
            if f["t"] >= t - 0.0005:
                return f
    return {"t": t, "tipo": "?", "clave": False}


def fotograma_vecino(src_path: str, t: float, direccion: int) -> float:
    """Tiempo del fotograma anterior (-1) o siguiente (+1) al del tiempo `t`.

    Se lee la lista real de fotogramas en vez de sumar 1/fps: con cadencia
    variable esa cuenta no cierra y el paso se queda clavado en el mismo
    fotograma. Si no hay vecino (principio o final del video), devuelve `t`.
    """
    if direccion > 0:
        for ventana in (2.0, 8.0, 30.0):
            for f in lista_fotogramas(src_path, t, ventana):
                if f["t"] > t + 0.0005:
                    return f["t"]
        return t

    for ventana in (2.0, 8.0, 30.0):
        desde = max(0.0, t - ventana)
        previos = [f["t"] for f in lista_fotogramas(src_path, desde, ventana + 0.5)
                   if f["t"] < t - 0.0005]
        if previos:
            return previos[-1]
        if desde <= 0.0:
            break
    return 0.0 if t > 0 else t


def numero_de_fotograma(ficha: dict, t: float) -> Optional[int]:
    """Número de fotograma contando desde 1. None si el video es de cadencia
    variable: ahí el número no se puede calcular, habría que contarlos todos."""
    if ficha.get("vfr") or not ficha.get("fps"):
        return None
    return int(round(t * ficha["fps"])) + 1


def hora_real(ficha: dict, t: float) -> Optional[datetime]:
    """Hora del hecho = inicio de la grabación + tiempo transcurrido.
    None si el archivo no trae la hora de inicio (pasa seguido en los DVR)."""
    if not ficha.get("inicio_dt"):
        return None
    return ficha["inicio_dt"] + timedelta(seconds=t)


# ── Extracción ───────────────────────────────────────────────────────────────

def extraer_fotograma(src_path: str, t: float, dst_png: str,
                      desentrelazar: bool = False) -> dict:
    """Saca el fotograma del tiempo `t` a un PNG y devuelve sus datos reales.

    Devuelve {"archivo", "t", "t_hms", "tipo", "clave", "pedido"}.
    """
    if not is_available():
        raise RuntimeError("FFmpeg no está disponible.")

    os.makedirs(os.path.dirname(os.path.abspath(dst_png)) or ".", exist_ok=True)

    cmd = [FFMPEG, "-y", "-ss", f"{max(0.0, t):.6f}", "-i", src_path]
    if desentrelazar:
        # Desentrelazar CAMBIA los píxeles: solo si el usuario lo pide, y
        # queda anotado en la constancia.
        cmd += ["-vf", "yadif=deint=interlaced"]
    cmd += ["-frames:v", "1", "-update", "1", dst_png]

    r = _correr(cmd, timeout=120)
    if r.returncode != 0 or not os.path.exists(dst_png) or os.path.getsize(dst_png) == 0:
        raise RuntimeError(
            "No se pudo extraer el fotograma.\n" + (r.stderr or "")[-300:]
        )

    real = _fotograma_entregado(src_path, t)
    return {
        "archivo": dst_png,
        "t": real["t"],
        "t_hms": hms(real["t"]),
        "tipo": real["tipo"],
        "clave": real["clave"],
        "pedido": t,
        "desentrelazado": desentrelazar,
    }


def _miniatura(src_path: str, t: float, dst_png: str, ancho: int) -> float:
    """Saca una miniatura del tiempo `t` y devuelve el tiempo REAL que salió.

    Acá el tiempo se lee del propio FFmpeg (`-copyts` + filtro `showinfo`), en
    la misma llamada que hace la imagen: para un mapa de sesenta miniaturas,
    preguntar aparte con FFprobe duplicaría la espera.
    """
    r = _correr([
        FFMPEG, "-y", "-copyts", "-ss", f"{max(0.0, t):.6f}", "-i", src_path,
        "-vf", f"showinfo,scale={ancho}:-2", "-frames:v", "1", "-update", "1",
        dst_png,
    ], timeout=120)
    if r.returncode != 0 or not os.path.exists(dst_png):
        raise RuntimeError("No se pudo extraer la miniatura.\n" + (r.stderr or "")[-300:])

    marca = re.search(r"pts_time:([0-9.]+)", r.stderr or "")
    if not marca:
        return t
    # -copyts devuelve la marca absoluta del archivo: se le saca el desfasaje.
    return max(0.0, float(marca.group(1)) - _desfasaje(src_path))


def _intervalo_redondo(duracion: float, maximo: int) -> float:
    """Cada cuántos segundos conviene sacar una miniatura.

    Se elige un intervalo "de reloj" (5 s, 30 s, 2 min…) en vez del número
    exacto que daría la división: leer un mapa con miniaturas cada 47 segundos
    es incómodo, y ubicarse cada 1 minuto es inmediato.
    """
    if duracion <= 0 or maximo <= 0:
        return 1.0
    crudo = duracion / maximo
    for paso in (1, 2, 5, 10, 15, 20, 30, 60, 120, 300, 600, 900, 1800, 3600):
        if crudo <= paso:
            return float(paso)
    return float(int(crudo / 3600 + 1) * 3600)


def mapa_del_video(src_path: str, dst_png: str, cada: float = None,
                   columnas: int = 5, ancho_celda: int = 320,
                   maximo: int = 60, progress_cb=None) -> dict:
    """Arma una sola imagen con miniaturas de todo el video, cada una con su
    minuto y segundo.

    Sirve para ubicarse: en vez de arrastrar la barra a ciegas por una
    grabación de tres horas, se ve la película entera de un vistazo y se salta
    directo al momento que interesa.

    Devuelve, además del archivo, la posición exacta de cada miniatura dentro
    de la imagen: con eso el panel sabe a qué momento corresponde el lugar
    donde el usuario hizo clic.
    """
    from PIL import Image, ImageDraw, ImageFont

    if not is_available():
        raise RuntimeError("FFmpeg no está disponible.")

    ficha = info_video(src_path)
    if ficha["duracion"] <= 0:
        raise RuntimeError(
            "El archivo no declara cuánto dura, así que no se puede repartir "
            "las miniaturas a lo largo del video.")

    cada = float(cada) if cada else _intervalo_redondo(ficha["duracion"], maximo)
    columnas = max(1, int(columnas))

    tiempos = []
    t = 0.0
    while t < ficha["duracion"] - 0.001 and len(tiempos) < 400:
        tiempos.append(t)
        t += cada

    # ── Miniaturas ───────────────────────────────────────────────────────
    temporal = os.path.join(TEMP_DIR, "mapa_video")
    shutil.rmtree(temporal, ignore_errors=True)
    os.makedirs(temporal, exist_ok=True)

    celdas = []
    try:
        for i, pedido in enumerate(tiempos):
            if progress_cb and (i % 5 == 0 or i == len(tiempos) - 1):
                progress_cb(f"🗺️  Miniatura {i + 1} de {len(tiempos)}…")
            archivo = os.path.join(temporal, f"m{i:04d}.png")
            try:
                real = _miniatura(src_path, pedido, archivo, ancho_celda)
            except RuntimeError:
                continue          # un tramo dañado no tiene que voltear el mapa
            celdas.append({"archivo": archivo, "t": real, "t_hms": hms(real)})

        if not celdas:
            raise RuntimeError(
                "No se pudo extraer ninguna miniatura: el video puede estar dañado.")

        with Image.open(celdas[0]["archivo"]) as primera:
            ancho_mini, alto_mini = primera.size

        # ── Composición ──────────────────────────────────────────────────
        margen, hueco, alto_pie = 14, 8, 20
        filas = (len(celdas) + columnas - 1) // columnas
        alto_celda = alto_mini + alto_pie
        alto_encabezado = 58
        ancho_total = margen * 2 + columnas * ancho_mini + (columnas - 1) * hueco
        alto_total = (alto_encabezado + margen + filas * alto_celda
                      + (filas - 1) * hueco + margen)

        hoja = Image.new("RGB", (ancho_total, alto_total), (17, 24, 39))
        lapiz = ImageDraw.Draw(hoja)

        def fuente(nombre, tam):
            try:
                return ImageFont.truetype(nombre, tam)
            except OSError:
                return ImageFont.load_default()

        titulo_f = fuente("arialbd.ttf", 17)
        datos_f = fuente("arial.ttf", 12)
        reloj_f = fuente("arialbd.ttf", 13)

        lapiz.text((margen, 12), os.path.basename(src_path),
                   font=titulo_f, fill=(248, 250, 252))
        detalle = (f"Duración {ficha['duracion_hms']}   ·   "
                   f"{ficha['ancho']}x{ficha['alto']} px   ·   "
                   f"{len(celdas)} miniaturas, una cada {hms(cada)}")
        if ficha["inicio_grabacion"]:
            detalle += (f"   ·   inicio de la grabación "
                        f"{ficha['inicio_grabacion'][:19].replace('T', ' ')}")
        lapiz.text((margen, 34), detalle, font=datos_f, fill=(148, 163, 184))

        for i, celda in enumerate(celdas):
            col, fila = i % columnas, i // columnas
            x = margen + col * (ancho_mini + hueco)
            y = alto_encabezado + margen + fila * (alto_celda + hueco)
            with Image.open(celda["archivo"]) as mini:
                hoja.paste(mini.convert("RGB"), (x, y))
            # El reloj va debajo de la miniatura y no encima: tapar la imagen
            # sería tapar justo lo que se está buscando.
            lapiz.rectangle([x, y + alto_mini, x + ancho_mini,
                             y + alto_mini + alto_pie], fill=(30, 41, 59))
            lapiz.text((x + 6, y + alto_mini + 3), celda["t_hms"],
                       font=reloj_f, fill=(226, 232, 240))
            celda.update({"x": x, "y": y, "w": ancho_mini,
                          "h": alto_mini + alto_pie})
            celda.pop("archivo", None)

        os.makedirs(os.path.dirname(os.path.abspath(dst_png)) or ".", exist_ok=True)
        hoja.save(dst_png)
    finally:
        shutil.rmtree(temporal, ignore_errors=True)

    if progress_cb:
        progress_cb(f"✅ Mapa armado con {len(celdas)} miniaturas.")

    return {
        "archivo": dst_png,
        "cada": cada,
        "columnas": columnas,
        "filas": filas,
        "ancho": ancho_total,
        "alto": alto_total,
        "celdas": celdas,
        "ficha": ficha,
    }


def constancia_mapa(ficha: dict, archivo: str, cada: float,
                    cantidad: int, herramienta: str = "") -> str:
    """Constancia del mapa: de qué video salió y cómo se armó."""
    from core.hasher import file_info

    sep = "─" * 62
    origen = file_info(ficha["path"])
    mapa = file_info(archivo)
    return "\n".join([
        sep,
        "CONSTANCIA DE MAPA DE VIDEO",
        sep,
        "Se armó una vista general del archivo de video:",
        f"  «{origen['filename']}»",
        f"  SHA-256: {origen['sha256']}",
        f"  MD5:     {origen['md5']}",
        f"  Tamaño:  {origen['size_human']}",
        f"  Duración: {ficha['duracion_hms']}",
        "",
        "Cómo se armó:",
        f"  {cantidad} miniaturas, una cada {hms(cada)} de grabación,",
        "  con el tiempo de cada fotograma leído del propio video.",
        "",
        "Imagen resultante:",
        f"  «{mapa['filename']}»",
        f"  SHA-256: {mapa['sha256']}",
        f"  MD5:     {mapa['md5']}",
        f"  Tamaño:  {mapa['size_human']}",
        "",
        "Las miniaturas están reducidas de tamaño: sirven para ubicarse en la",
        "grabación, no para observar detalles. Para eso se captura el",
        "fotograma, que sale en la resolución original.",
        "",
        f"Fecha y hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
    ] + ([f"Herramienta: {herramienta}"] if herramienta else []) + [sep, ""])


def rafaga(src_path: str, desde: float, hasta: float, out_dir: str,
           desentrelazar: bool = False, progress_cb=None) -> List[dict]:
    """Todos los fotogramas entre `desde` y `hasta`, numerados y con su tiempo.

    El disparo, el choque o la cara no siempre están en el fotograma que uno
    eligió primero: con la ráfaga se lleva la secuencia entera del momento.
    """
    if not is_available():
        raise RuntimeError("FFmpeg no está disponible.")

    desde = max(0.0, desde)
    dur = max(0.04, hasta - desde)
    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(src_path))[0]

    if progress_cb:
        progress_cb(f"🎞️  Extrayendo fotogramas entre {hms(desde)} y {hms(hasta)}…")

    patron = os.path.join(out_dir, f"{stem}_rafaga_%05d.png")
    cmd = [FFMPEG, "-y", "-ss", f"{desde:.6f}", "-i", src_path, "-t", f"{dur:.6f}"]
    if desentrelazar:
        cmd += ["-vf", "yadif=deint=interlaced"]
    # fps_mode passthrough: ni repite ni descarta cuadros, salen los que hay.
    cmd += ["-fps_mode", "passthrough", patron]

    r = _correr(cmd, timeout=600)
    if r.returncode != 0:
        raise RuntimeError("No se pudo extraer la ráfaga.\n" + (r.stderr or "")[-300:])

    archivos = sorted(
        os.path.join(out_dir, f) for f in os.listdir(out_dir)
        if f.startswith(f"{stem}_rafaga_") and f.endswith(".png")
    )
    tiempos = [f for f in lista_fotogramas(src_path, desde, dur + 0.5)
               if f["t"] >= desde - 0.0005][:len(archivos)]

    # Se renombra cada uno con su tiempo real, que es el dato que importa.
    resultado = []
    for i, archivo in enumerate(archivos):
        datos = tiempos[i] if i < len(tiempos) else {"t": desde, "tipo": "?", "clave": False}
        final = os.path.join(
            out_dir, f"{stem}_{_nombre_de_tiempo(datos['t'])}.png")
        if os.path.abspath(final) != os.path.abspath(archivo):
            if os.path.exists(final):
                os.unlink(final)
            os.rename(archivo, final)
        resultado.append({
            "archivo": final, "t": datos["t"], "t_hms": hms(datos["t"]),
            "tipo": datos["tipo"], "clave": datos["clave"],
        })

    if progress_cb:
        progress_cb(f"✅ {len(resultado)} fotogramas extraídos.")
    return resultado


def recortar_original(src_path: str, desde: float, hasta: float,
                      dst_path: str) -> str:
    """Guarda un pedazo del video **sin recodificar** (`-c copy`).

    Los bits son los del original, así que sirve para adjuntar junto a la
    foto. Ojo: el corte se pega al fotograma clave anterior, así que el
    pedacito puede arrancar hasta unos segundos antes de lo pedido. Es el
    precio de no tocar la imagen.
    """
    if not is_available():
        raise RuntimeError("FFmpeg no está disponible.")
    desde = max(0.0, desde)
    dur = max(0.1, hasta - desde)
    os.makedirs(os.path.dirname(os.path.abspath(dst_path)) or ".", exist_ok=True)
    r = _correr([
        FFMPEG, "-y", "-ss", f"{desde:.6f}", "-i", src_path,
        "-t", f"{dur:.6f}", "-c", "copy",
        "-avoid_negative_ts", "make_zero", dst_path,
    ], timeout=300)
    if r.returncode != 0 or not os.path.exists(dst_path):
        raise RuntimeError("No se pudo recortar el video.\n" + (r.stderr or "")[-300:])
    return dst_path


# ── Constancia ───────────────────────────────────────────────────────────────

def constancia(ficha: dict, captura: dict, imagenes: List[str],
               herramienta: str = "") -> str:
    """Texto de la constancia de captura, con los datos que la hacen verificable.

    Con los hashes del video de origen y de la imagen, cualquiera puede
    comprobar después que la foto salió de ese video y que nadie la tocó.
    """
    from core.hasher import file_info

    sep = "─" * 62
    origen = file_info(ficha["path"])
    n = numero_de_fotograma(ficha, captura["t"])
    hora = hora_real(ficha, captura["t"])

    lineas = [
        sep,
        "CONSTANCIA DE CAPTURA DE FOTOGRAMA",
        sep,
        "Se extrajo un fotograma del archivo de video:",
        f"  «{origen['filename']}»",
        f"  SHA-256: {origen['sha256']}",
        f"  MD5:     {origen['md5']}",
        f"  Tamaño:  {origen['size_human']}",
        "",
        "Datos técnicos del video:",
        f"  Duración:   {ficha['duracion_hms']}",
        f"  Imagen:     {ficha['ancho']}x{ficha['alto']} px",
        f"  Códec:      {ficha['codec']}",
        f"  Cadencia:   {ficha['fps']:.3f} cuadros/s"
        + ("  (VARIABLE)" if ficha["vfr"] else "  (fija)"),
    ]
    if ficha.get("entrelazado"):
        lineas.append("  Entrelazado: sí")

    lineas += [
        "",
        "Momento capturado:",
        f"  Tiempo del video:  {captura['t_hms']}",
    ]
    if n is not None:
        lineas.append(f"  Fotograma n.º:     {n}")
    else:
        lineas.append("  Fotograma n.º:     no aplica (el video es de cadencia variable)")
    lineas.append(f"  Tipo de cuadro:    {captura.get('tipo', '?')}"
                  + ("  (cuadro clave)" if captura.get("clave") else ""))

    if hora:
        lineas += [
            f"  Hora estimada:     {hora.strftime('%Y-%m-%d %H:%M:%S')}",
            f"     └─ calculada sobre la hora de inicio declarada por el archivo",
            f"        ({ficha['inicio_grabacion']}). Si la cámara imprime la hora",
            "        sobre la imagen, esa es la que debe tomarse como válida.",
        ]
    else:
        lineas += [
            "  Hora estimada:     no se puede determinar",
            "     └─ el archivo no declara la hora de inicio de la grabación.",
            "        Si la cámara imprime la hora sobre la imagen, esa es la",
            "        que debe tomarse como válida.",
        ]

    lineas += ["", "Imagen resultante:"]
    for img in imagenes:
        datos = file_info(img)
        lineas += [
            f"  «{datos['filename']}»",
            f"  SHA-256: {datos['sha256']}",
            f"  MD5:     {datos['md5']}",
            f"  Tamaño:  {datos['size_human']}",
        ]

    tratamiento = ("desentrelazado (yadif)" if captura.get("desentrelazado")
                   else "ninguno")
    lineas += [
        "",
        "Tratamiento de la imagen:",
        f"  {tratamiento}",
        "  Formato PNG sin pérdida, en la resolución original del video,",
        "  sin recortes, sin escalado y sin ajustes de color.",
        "",
        f"Fecha y hora de la extracción: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
    ]
    if herramienta:
        lineas.append(f"Herramienta: {herramienta}")
    lineas.append(sep)
    return "\n".join(lineas) + "\n"
