"""
motor_subtitles_conv.py — Conversión entre formatos de subtítulos.
Puro Python, sin dependencias externas.
Soporta: SRT ↔ VTT, SRT → ASS, ASS → SRT, SUB (MicroDVD/SubViewer) → SRT

(motor_subtitles.py es otra cosa: GENERA subtítulos con Whisper.)
"""
import re

from core.graph import BaseMotor


# ── Modelo interno: lista de (start_seg, end_seg, texto) en segundos ─────────

def _ts_srt(seconds: float) -> str:
    ms = round(seconds * 1000)
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _ts_vtt(seconds: float) -> str:
    return _ts_srt(seconds).replace(",", ".")


def _ts_ass(seconds: float) -> str:
    cs = round(seconds * 100)
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"


def _parse_ts(ts: str) -> float:
    """'HH:MM:SS,mmm' | 'HH:MM:SS.mmm' | 'H:MM:SS.cc' → segundos."""
    ts = ts.strip().replace(",", ".")
    parts = ts.split(":")
    parts = [float(p) for p in parts]
    while len(parts) < 3:
        parts.insert(0, 0.0)
    h, m, s = parts
    return h * 3600 + m * 60 + s


def _read_text(path: str) -> str:
    with open(path, "rb") as f:
        raw = f.read()
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


# ── Parsers ──────────────────────────────────────────────────────────────────

_SRT_TIME = re.compile(
    r"(\d{1,2}:\d{2}:\d{2}[.,]\d{1,3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[.,]\d{1,3})"
)


def _parse_srt_vtt(text: str):
    """Sirve para SRT y VTT (misma estructura de bloques con '-->')."""
    cues = []
    for block in re.split(r"\n\s*\n", text.replace("\r\n", "\n")):
        m = _SRT_TIME.search(block)
        if not m:
            continue
        start, end = _parse_ts(m.group(1)), _parse_ts(m.group(2))
        lines = block[m.end():].strip().split("\n")
        payload = "\n".join(l.strip() for l in lines if l.strip())
        # VTT permite tags <c>...</c>; limpiarlos para formatos que no
        payload = re.sub(r"</?c[^>]*>", "", payload)
        if payload:
            cues.append((start, end, payload))
    return cues


_ASS_DIALOGUE = re.compile(r"^Dialogue:\s*[^,]*,([^,]*),([^,]*),", re.M)


def _parse_ass(text: str):
    cues = []
    fmt_fields = None
    for line in text.replace("\r\n", "\n").split("\n"):
        if line.startswith("Format:") and "Start" in line:
            fmt_fields = [f.strip() for f in line[len("Format:"):].split(",")]
        elif line.startswith("Dialogue:"):
            fields = line[len("Dialogue:"):].split(",")
            names = fmt_fields or ["Layer", "Start", "End", "Style", "Name",
                                   "MarginL", "MarginR", "MarginV", "Effect", "Text"]
            n_before_text = len(names) - 1
            if len(fields) <= n_before_text:
                continue
            row = dict(zip(names[:n_before_text], fields[:n_before_text]))
            text_part = ",".join(fields[n_before_text:])
            # limpiar tags de estilo {\...} y saltos \N
            text_part = re.sub(r"\{[^}]*\}", "", text_part)
            text_part = text_part.replace("\\N", "\n").replace("\\n", "\n").strip()
            try:
                start = _parse_ts(row["Start"])
                end = _parse_ts(row["End"])
            except (KeyError, ValueError):
                continue
            if text_part:
                cues.append((start, end, text_part))
    cues.sort(key=lambda c: c[0])
    return cues


_MICRODVD = re.compile(r"^\{(\d+)\}\{(\d+)\}(.*)$")
_SUBVIEWER_TIME = re.compile(
    r"^(\d{2}:\d{2}:\d{2}\.\d{2}),(\d{2}:\d{2}:\d{2}\.\d{2})"
)


def _parse_sub(text: str, fps: float = 23.976):
    """SUB en variante MicroDVD ({inicio}{fin}texto) o SubViewer."""
    cues = []
    lines = text.replace("\r\n", "\n").split("\n")
    for i, line in enumerate(lines):
        m = _MICRODVD.match(line.strip())
        if m:
            start = int(m.group(1)) / fps
            end = int(m.group(2)) / fps
            payload = m.group(3).replace("|", "\n").strip()
            payload = re.sub(r"\{[^}]*\}", "", payload)
            if payload:
                cues.append((start, end, payload))
            continue
        m = _SUBVIEWER_TIME.match(line.strip())
        if m and i + 1 < len(lines):
            start, end = _parse_ts(m.group(1)), _parse_ts(m.group(2))
            payload = lines[i + 1].replace("[br]", "\n").strip()
            if payload:
                cues.append((start, end, payload))
    return cues


# ── Writers ──────────────────────────────────────────────────────────────────

def _write_srt(cues, path):
    out = []
    for i, (start, end, text) in enumerate(cues, 1):
        out.append(f"{i}\n{_ts_srt(start)} --> {_ts_srt(end)}\n{text}\n")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


def _write_vtt(cues, path):
    out = ["WEBVTT\n"]
    for start, end, text in cues:
        out.append(f"{_ts_vtt(start)} --> {_ts_vtt(end)}\n{text}\n")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


_ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 384
PlayResY: 288

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,16,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,1,0,2,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _write_ass(cues, path):
    lines = [_ASS_HEADER]
    for start, end, text in cues:
        payload = text.replace("\n", "\\N")
        lines.append(
            f"Dialogue: 0,{_ts_ass(start)},{_ts_ass(end)},Default,,0,0,0,,{payload}"
        )
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def _write_txt(cues, path):
    """Transcripción plana: solo el texto, sin tiempos ni numeración.

    Un subtítulo también es texto: quien quiere el guión de un video no
    necesita los códigos de tiempo. Desde acá el grafo encadena a MD, PDF
    o DOCX sin motores nuevos.
    """
    lineas = []
    for _start, _end, text in cues:
        t = " ".join(text.split())
        if t:
            lineas.append(t)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lineas) + "\n")


# ── Motor ────────────────────────────────────────────────────────────────────

class SubtitleConvertMotor(BaseMotor):
    NAME = "Subtítulos"
    CONVERSIONS = [
        ("srt", "vtt"), ("srt", "ass"), ("srt", "txt"),
        ("vtt", "srt"), ("vtt", "ass"), ("vtt", "txt"),
        ("ass", "srt"), ("ass", "vtt"), ("ass", "txt"),
        ("sub", "srt"), ("sub", "vtt"), ("sub", "ass"), ("sub", "txt"),
    ]

    def convert(self, src_path, dst_path, src_ext, dst_ext, **kwargs):
        text = _read_text(src_path)
        if src_ext in ("srt", "vtt"):
            cues = _parse_srt_vtt(text)
        elif src_ext == "ass":
            cues = _parse_ass(text)
        elif src_ext == "sub":
            cues = _parse_sub(text)
        else:
            raise RuntimeError(f"Origen de subtítulo no soportado: {src_ext}")

        if not cues:
            raise RuntimeError(
                "No se encontraron subtítulos en el archivo "
                "(¿formato dañado o variante no soportada?)."
            )

        writers = {"srt": _write_srt, "vtt": _write_vtt,
                   "ass": _write_ass, "txt": _write_txt}
        writers[dst_ext](cues, dst_path)
