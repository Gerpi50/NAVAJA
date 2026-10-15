"""
motors/motor_subtitles.py — Generación de subtítulos automáticos con Whisper.

Transcribe el audio de un video/audio y produce un archivo .srt. Opcionalmente
el video se puede recodificar quemando los subtítulos (burn-in), lo cual lo
maneja FFmpegVideoMotor con el filtro `subtitles`.

Todo el módulo es defensivo: si Whisper o su modelo no están disponibles,
`is_available()` devuelve False y `generate_srt()` lanza una excepción clara
que el worker captura sin romper la aplicación.
"""
import os
from typing import Callable, Optional


def is_available() -> bool:
    """True si la librería whisper se puede importar."""
    try:
        import whisper  # noqa: F401
        return True
    except Exception:
        return False


_MODEL_CACHE = {}


def _model_roots() -> list:
    """
    Carpetas candidatas donde buscar el modelo Whisper, en orden:
    1) models/whisper junto al exe (escribible, permite descargas/actualizar)
    2) models/whisper empaquetado dentro de _internal (_MEIPASS)
    """
    roots = []
    try:
        from core.paths import MODELS_DIR, resource
        roots.append(os.path.join(MODELS_DIR, "whisper"))
        try:
            roots.append(resource(os.path.join("models", "whisper")))
        except Exception:
            pass
    except Exception:
        roots.append(os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "models", "whisper"))
    return roots


def _load_model(size: str = "base"):
    """
    Carga (y cachea) el modelo Whisper. Busca primero la copia local junto al
    exe (carpeta models/whisper) y la empaquetada; si no hay ninguna, la
    descarga en la carpeta escribible la primera vez.
    """
    if size in _MODEL_CACHE:
        return _MODEL_CACHE[size]
    import whisper

    roots = _model_roots()
    # Si alguna carpeta ya tiene el modelo, usarla como download_root (solo lee).
    for r in roots:
        if os.path.isfile(os.path.join(r, f"{size}.pt")):
            model = whisper.load_model(size, download_root=r)
            _MODEL_CACHE[size] = model
            return model

    # No está: descargar en la primera carpeta (escribible).
    target = roots[0] if roots else None
    try:
        if target:
            os.makedirs(target, exist_ok=True)
            model = whisper.load_model(size, download_root=target)
        else:
            model = whisper.load_model(size)
    except Exception:
        model = whisper.load_model(size)  # caché por defecto (~/.cache/whisper)
    _MODEL_CACHE[size] = model
    return model


def _fmt_ts(seconds: float) -> str:
    """Convierte segundos a timestamp SRT: HH:MM:SS,mmm."""
    if seconds < 0:
        seconds = 0
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3600 * 1000)
    m, ms = divmod(ms, 60 * 1000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _segments_to_srt(segments) -> str:
    lines = []
    for i, seg in enumerate(segments, start=1):
        start = _fmt_ts(float(seg.get("start", 0.0)))
        end = _fmt_ts(float(seg.get("end", 0.0)))
        text = (seg.get("text") or "").strip()
        lines.append(f"{i}\n{start} --> {end}\n{text}\n")
    return "\n".join(lines)


def generate_srt(
    media_path: str,
    srt_path: str,
    language: Optional[str] = None,
    model_size: str = "base",
    progress_cb: Optional[Callable[[str], None]] = None,
) -> str:
    """
    Transcribe `media_path` y escribe los subtítulos en `srt_path`.

    language: código ISO ("es", "en", ...) o None para autodetección.
    Devuelve la ruta del .srt generado. Lanza RuntimeError si no es posible.
    """
    if not is_available():
        raise RuntimeError(
            "La generación de subtítulos necesita el paquete 'whisper'.\n"
            "Instalalo con: pip install openai-whisper"
        )

    def log(msg: str):
        if progress_cb:
            progress_cb(msg)

    log("💬  Cargando modelo de transcripción (puede tardar la 1ª vez)…")
    model = _load_model(model_size)

    log("💬  Transcribiendo audio… (esto puede demorar)")
    options = {"task": "transcribe", "verbose": False}
    if language:
        options["language"] = language
    result = model.transcribe(media_path, **options)

    srt_text = _segments_to_srt(result.get("segments", []))
    os.makedirs(os.path.dirname(srt_path) or ".", exist_ok=True)
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write(srt_text)
    log(f"💬  Subtítulos generados: {os.path.basename(srt_path)}")
    return srt_path
