"""
graph.py — Grafo de conversiones.
Registra motores y resuelve rutas automáticamente (incluso indirectas).
Solo se aceptan conversiones que estén en la matriz de compatibilidad.
"""
from collections import deque
from typing import Optional, List, Tuple, Dict, Type

# ── Matriz universal de conversiones permitidas ───────────────────────────────
# Define qué destinos son técnicamente válidos para cada origen.
# Los motores solo se registran si la conversión aparece aquí.
COMPAT_MATRIX: Dict[str, List[str]] = {
    # Documentos
    "doc":   ["docx", "odt", "pdf", "txt", "html", "rtf"],
    "docx":  ["doc", "odt", "pdf", "txt", "html", "rtf", "md"],
    "odt":   ["doc", "docx", "pdf", "txt", "html", "md"],
    "rtf":   ["doc", "docx", "pdf", "txt"],
    "txt":   ["pdf", "html", "md", "docx"],
    "html":  ["pdf", "docx", "txt", "md"],
    "htm":   ["pdf", "docx", "txt", "md"],
    # Pandoc escribe estos directo desde Markdown, sin encadenar nada.
    "md":    ["html", "pdf", "docx", "odt", "epub", "txt"],
    "rst":   ["html", "pdf", "docx"],
    "tex":   ["pdf", "html"],
    "pdf":   ["docx", "txt", "md", "html", "png", "jpg", "epub", "svg"],
    "pages": ["pdf", "docx"],
    "key":   ["pdf", "pptx"],
    "wps":   ["docx", "pdf", "txt"],
    "ipynb": ["html", "pdf"],
    # Hojas de cálculo
    "xls":   ["xlsx", "ods", "csv", "pdf", "html"],
    "xlsx":  ["xls", "ods", "csv", "tsv", "pdf", "html", "png"],
    "ods":   ["xls", "xlsx", "csv", "pdf", "html"],
    "csv":   ["xlsx", "xls", "ods", "tsv", "pdf"],
    "tsv":   ["csv", "xlsx"],
    "numbers": ["xlsx", "csv", "pdf"],
    # Presentaciones
    "ppt":   ["pptx", "pdf", "png", "jpg"],
    "pptx":  ["ppt", "pdf", "png", "jpg"],
    "odp":   ["pptx", "pdf", "png", "jpg"],
    # Imágenes raster
    # Una imagen solo puede ir a otra imagen o a PDF (la foto dentro de un PDF).
    # "txt" aparece únicamente cuando hay OCR disponible (ver OCR_ONLY abajo).
    "png":   ["jpg", "webp", "bmp", "tiff", "ico", "pdf", "svg", "txt"],
    "jpg":   ["png", "webp", "bmp", "tiff", "svg", "pdf", "txt"],
    "jpeg":  ["png", "webp", "bmp", "tiff", "pdf", "txt"],
    "webp":  ["png", "jpg", "pdf", "txt"],
    "bmp":   ["png", "jpg", "svg", "pdf", "txt"],
    "tiff":  ["png", "jpg", "pdf", "txt"],
    "tif":   ["png", "jpg", "pdf", "txt"],
    "gif":   ["png", "webp", "pdf"],
    "ico":   ["png"],
    "icns":  ["png"],
    "avif":  ["png", "jpg", "webp", "pdf"],
    "heic":  ["png", "jpg", "pdf"],
    "heif":  ["png", "jpg", "pdf"],
    "tga":   ["png", "jpg", "pdf"],
    "jfif":  ["png", "jpg", "pdf"],
    "psd":   ["png", "jpg", "pdf"],
    "dng":   ["jpg", "png", "pdf"],
    # Vectorial
    "svg":   ["png", "jpg", "pdf", "eps"],
    "eps":   ["pdf", "png"],
    "ai":    ["pdf", "png"],
    # Audio
    "mp3":   ["wav", "flac", "aac", "ogg", "m4a"],
    "wav":   ["mp3", "flac", "aac"],
    "flac":  ["mp3", "wav"],
    "aac":   ["mp3", "wav"],
    "ogg":   ["mp3", "wav"],
    "m4a":   ["mp3", "wav"],
    "m4b":   ["mp3", "wav"],
    "m4r":   ["mp3", "wav"],
    "wma":   ["mp3", "wav"],
    "aiff":  ["mp3", "wav"],
    "au":    ["mp3", "wav"],
    "amr":   ["mp3", "wav"],
    "ac3":   ["mp3", "wav"],
    "ape":   ["mp3", "wav", "flac"],
    "mka":   ["mp3", "wav"],
    "caf":   ["mp3", "wav"],
    "ra":    ["mp3", "wav"],
    "opus":  ["mp3", "wav"],
    # Video
    "mp4":   ["mkv", "avi", "mov", "webm", "mp3", "wav", "flac", "aac", "ogg", "m4a", "opus"],
    "mkv":   ["mp4", "avi", "mp3", "wav", "flac", "aac", "ogg", "m4a", "opus"],
    "avi":   ["mp4", "mkv", "mp3", "wav", "aac"],
    "mov":   ["mp4", "mkv", "mp3", "wav", "aac", "m4a"],
    "webm":  ["mp4", "mp3", "wav", "ogg", "opus"],
    "flv":   ["mp4", "mp3", "wav"],
    "wmv":   ["mp4", "mp3", "wav"],
    "m4v":   ["mp4", "mp3", "wav", "aac", "m4a"],
    "3gp":   ["mp4", "mp3", "wav"],
    "ts":    ["mp4", "mp3", "wav"],
    "mpg":   ["mp4", "mp3", "wav"],
    "mpeg":  ["mp4", "mp3", "wav"],
    "ogv":   ["mp4", "mp3", "wav", "ogg"],
    "vob":   ["mp4", "mp3", "wav"],
    "f4v":   ["mp4", "mp3", "wav"],
    # Subtítulos
    "srt":   ["vtt", "ass"],
    "ass":   ["srt"],
    "vtt":   ["srt"],
    "sub":   ["srt"],
    # Ebooks
    "epub":  ["mobi", "azw3", "pdf", "txt"],
    "mobi":  ["epub"],
    "azw3":  ["epub"],
    # Datos estructurados
    "json":  ["xml", "yaml", "toml", "csv"],
    "xml":   ["json", "csv"],
    "yaml":  ["json"],
    "yml":   ["json"],
    "toml":  ["json"],
    "parquet": ["csv", "json"],
    "hdf5":  ["csv", "json"],
    # Fuentes
    "ttf":   ["otf", "woff", "woff2"],
    "otf":   ["ttf", "woff"],
    "woff":  ["ttf"],
    "woff2": ["ttf"],
    # Archivos comprimidos
    "zip":   ["tar", "7z"],
    "rar":   ["zip"],
    "7z":    ["zip"],
    "tar":   ["gz", "zip"],
    "gz":    ["tar"],
    # Email → documentos
    "msg":   ["pdf", "txt", "html", "eml"],
    "eml":   ["pdf", "txt", "html"],
    "emlx":  ["pdf", "txt", "html", "eml"],
}


# ── Cierre por familias ───────────────────────────────────────────────
# La matriz de arriba se escribió a mano, fila por fila, y por eso quedaba
# coja: cada vez que un motor ganaba un destino había que acordarse de
# agregarlo también acá, y si uno se olvidaba la capacidad quedaba muerta
# (ODT→MD y DOCX→EPUB existían en Pandoc pero la matriz los tapaba).
#
# La regla ahora se declara una sola vez por familia: TODO formato de una
# familia puede ir a CUALQUIER otro de su familia, más los destinos "puente"
# que se listan al lado. Lo que no tenga motor no se ofrece igual, porque
# all_targets() solo muestra los destinos que find_path() sabe resolver: la
# matriz dice "esto tiene sentido", el grafo dice "esto además se puede".

def _allow(sources: List[str], targets: List[str]) -> None:
    """Habilita sources × targets en la matriz (sin duplicados ni auto-pares)."""
    for _s in sources:
        _row = COMPAT_MATRIX.setdefault(_s, [])
        for _d in targets:
            if _d != _s and _d not in _row:
                _row.append(_d)


# Texto: documentos de oficina, markup y ebooks. Cualquier texto sale a
# cualquier otro texto; si no hay motor directo el grafo arma la cadena
# (RTF → DOCX → MD, MOBI → EPUB → PDF, DOC → DOCX → MD).
TEXT_FMTS = [
    "doc", "docx", "odt", "rtf", "txt", "md", "html", "htm", "rst", "tex",
    "pdf", "epub", "mobi", "azw3", "wps", "abw", "pages", "ipynb",
]
# Única excepción al "texto solo va a texto": un documento también puede
# salir como imágenes, una por página (va por PDF). Al revés no: una foto
# solo se vuelve texto con OCR, y eso se controla en OCR_ONLY.
TEXT_TO_IMG = ["png", "jpg", "svg"]
_allow(TEXT_FMTS, TEXT_FMTS + TEXT_TO_IMG)

# Hojas de cálculo: entre ellas, a documento y a los formatos de datos.
SHEET_FMTS = ["xls", "xlsx", "ods", "csv", "tsv", "numbers"]
_allow(SHEET_FMTS, SHEET_FMTS + ["pdf", "html", "md", "txt", "png",
                                 "json", "xml", "yaml", "yml", "toml"])

# Presentaciones: entre ellas, a PDF, a imágenes (una por diapositiva) y al
# texto que llevan adentro.
PRES_FMTS = ["ppt", "pptx", "odp", "key"]
_allow(PRES_FMTS, PRES_FMTS + ["pdf", "png", "jpg", "md", "txt", "html", "docx"])

# Correo: el cuerpo del mail es texto, así que va a donde va el texto.
MAIL_FMTS = ["msg", "eml", "emlx"]
_allow(MAIL_FMTS, MAIL_FMTS + ["pdf", "txt", "html", "md", "docx", "odt", "rtf"])

# Datos estructurados: todos contra todos (DataMotor los lee y escribe todos).
DATA_FMTS = ["json", "xml", "yaml", "yml", "toml", "csv", "tsv", "xlsx",
             "xls", "parquet", "hdf5", "h5"]
_allow(DATA_FMTS, DATA_FMTS)

# Imágenes: todas contra todas, más PDF y SVG. Las que Pillow no sabe
# guardar (HEIC, PSD, DNG…) quedan afuera solas: entran como origen y el
# grafo no encuentra ruta para ofrecerlas como destino.
IMG_FMTS = [
    "png", "jpg", "jpeg", "webp", "bmp", "tiff", "tif", "gif", "ico", "icns",
    "avif", "heic", "heif", "tga", "jfif", "psd", "dng",
]
_allow(IMG_FMTS, IMG_FMTS + ["pdf", "svg"])
_allow(["svg", "eps", "ai"], ["png", "jpg", "webp", "bmp", "tiff", "pdf", "eps"])

# Audio: todos contra todos, salvo los tres que FFmpeg sabe leer pero no
# escribir. Ofrecerlos como destino era prometer una conversión que
# terminaba en error del encoder.
AUDIO_FMTS = [
    "mp3", "wav", "flac", "aac", "ogg", "opus", "m4a", "m4b", "m4r", "wma",
    "aiff", "aif", "au", "amr", "ac3", "ape", "mka", "caf", "ra", "dts",
]
# APE se lee pero no se escribe (FFmpeg no trae encoder de Monkey's Audio).
# MIDI no figura en ninguna de las dos listas: este FFmpeg tampoco lo lee,
# hace falta un sintetizador con soundfont.
AUDIO_NO_ENCODE = {"ape"}
_allow(AUDIO_FMTS, [_d for _d in AUDIO_FMTS if _d not in AUDIO_NO_ENCODE])

# Video: todos contra todos, y además la pista de audio suelta. El GIF entra
# como video (GIF → MP4 y MP4 → GIF valen) pero no como origen de audio,
# porque un GIF no tiene pista de sonido.
VIDEO_FMTS = [
    "mp4", "mkv", "avi", "mov", "webm", "flv", "wmv", "m4v", "3gp", "ts",
    "mpg", "mpeg", "ogv", "gif", "vob", "f4v",
]
AUDIO_OUT_FMTS = ["mp3", "wav", "flac", "opus", "aac", "m4a", "ogg"]
_allow(VIDEO_FMTS, VIDEO_FMTS)
_allow([_v for _v in VIDEO_FMTS if _v != "gif"], AUDIO_OUT_FMTS)

# Subtítulos, fuentes y comprimidos: cada familia, todos contra todos.
_allow(["srt", "vtt", "ass", "sub"],
       ["srt", "vtt", "ass", "txt", "md", "pdf", "docx", "html"])
_allow(["ttf", "otf", "woff", "woff2"], ["ttf", "otf", "woff", "woff2"])
_allow(["zip", "tar", "7z", "rar", "gz"], ["zip", "tar", "7z", "gz"])


# ── Pares que solo valen por vía directa ──────────────────────────────────────
# Imagen → TXT solo tiene sentido con OCR (Tesseract). Si el OCR no está
# instalado su arista no se registra y el destino desaparece de la grilla; sin
# esta restricción el BFS lo alcanzaría por una cadena inútil
# (jpg → pdf → txt, que devuelve un archivo vacío porque la foto no lleva texto).
OCR_ONLY = {(_s, "txt") for _s in ("jpg", "jpeg", "png", "tiff", "tif", "bmp", "webp")}

# Máximo de saltos permitidos en una cadena. Con 2 alcanzan todas las rutas
# legítimas (p. ej. ODS → XLSX → CSV); más saltos solo producen cadenas
# absurdas que cruzan de categoría (JPG → PDF → DOCX → ODT).
MAX_CHAIN_STEPS = 2

# Cuando hay varias cadenas del mismo largo, el paso intermedio decide la
# calidad del resultado: ODS → HTML → MD conserva la tabla, ODS → PDF → MD
# devuelve un renglón suelto, porque del PDF hay que adivinar de nuevo dónde
# empieza cada cosa. Cuanto más bajo el número, antes se prueba ese formato
# como puente. El PDF va último a propósito.
PESO_INTERMEDIO: Dict[str, int] = {
    "docx": 0, "html": 1, "md": 2, "odt": 3, "epub": 4,
    "xlsx": 5, "csv": 6, "txt": 7,
    "pdf": 20,
    # Las imágenes van últimas: pasar por PNG obliga a leer el texto con OCR
    # (PPTX → PNG → TXT devolvía una sola diapositiva, adivinada de una foto).
    "png": 30, "jpg": 31,
}
_PESO_POR_DEFECTO = 10


def _peso_intermedio(ext: str) -> int:
    return PESO_INTERMEDIO.get(ext, _PESO_POR_DEFECTO)


def compat_targets(src_ext: str) -> List[str]:
    """Devuelve los destinos válidos según la matriz para un origen dado."""
    return list(COMPAT_MATRIX.get(src_ext.lower(), []))


def is_compat(src_ext: str, dst_ext: str) -> bool:
    """True si la conversión directa src→dst está en la matriz de compatibilidad."""
    return dst_ext.lower() in COMPAT_MATRIX.get(src_ext.lower(), [])


class BaseMotor:
    """Clase base para todos los motores de conversión."""
    NAME: str = "base"
    CONVERSIONS: List[Tuple[str, str]] = []   # [("jpg","png"), ...]

    @classmethod
    def can_convert(cls, src_ext: str, dst_ext: str) -> bool:
        return (src_ext.lower(), dst_ext.lower()) in cls.CONVERSIONS

    @classmethod
    def is_available(cls) -> bool:
        """Devuelve True si el motor puede ejecutarse en este sistema."""
        return True

    def convert(self, src_path: str, dst_path: str,
                src_ext: str, dst_ext: str, **kwargs) -> None:
        raise NotImplementedError


# ---------------------------------------------------------------------------

class ConversionGraph:
    """
    Grafo dirigido de conversiones.
    - Registra motores con sus aristas (src_ext → dst_ext).
    - Resuelve rutas cortas automáticamente (BFS).
    - Devuelve el motor correcto para cada arista.
    """

    def __init__(self):
        # { (src, dst) : [MotorClass, ...] } — en orden de preferencia.
        # Se guardan todos los que saben hacer esa conversión, no solo el
        # primero: si el de arriba falla (Word ocupado, LibreOffice a medio
        # instalar), el runner prueba el siguiente en vez de darse por vencido.
        self._edges: Dict[Tuple[str, str], List[Type[BaseMotor]]] = {}
        self._motors: List[Type[BaseMotor]] = []

    # ------------------------------------------------------------------
    def register(self, motor_class: Type[BaseMotor]) -> None:
        if not motor_class.is_available():
            return
        self._motors.append(motor_class)
        # Defensivo: un motor podría no declarar CONVERSIONS (p. ej. si solo se
        # usa por una vía directa). En ese caso no aporta aristas al grafo.
        for src, dst in getattr(motor_class, "CONVERSIONS", []):
            s, d = src.lower(), dst.lower()
            # Solo registrar si la conversión está en la matriz de compatibilidad
            if d not in COMPAT_MATRIX.get(s, []):
                continue
            key = (s, d)
            # El primero registrado manda; los demás quedan de respaldo.
            self._edges.setdefault(key, []).append(motor_class)

    # ------------------------------------------------------------------
    def direct_motor(self, src: str, dst: str) -> Optional[Type[BaseMotor]]:
        """El motor preferido para esa conversión directa (o None)."""
        motores = self._edges.get((src.lower(), dst.lower()))
        return motores[0] if motores else None

    # ------------------------------------------------------------------
    def direct_motors(self, src: str, dst: str) -> List[Type[BaseMotor]]:
        """Todos los motores que saben hacer src → dst, en orden de preferencia."""
        return list(self._edges.get((src.lower(), dst.lower()), []))

    # ------------------------------------------------------------------
    def find_path(self, src: str, dst: str) -> Optional[List[str]]:
        """
        BFS: devuelve lista de extensiones [src, mid1, ..., dst] o None.

        La matriz de compatibilidad manda sobre el par (origen, destino final):
        encadenar aristas válidas no convierte en válida una conversión que la
        matriz no declara (JPG → ODT y compañía).
        """
        src, dst = src.lower(), dst.lower()
        if src == dst:
            return [src]
        if not is_compat(src, dst):
            return None
        if (src, dst) in self._edges:
            return [src, dst]
        if (src, dst) in OCR_ONLY:
            return None

        visited = {src}
        queue = deque([[src]])

        while queue:
            path = queue.popleft()
            if len(path) > MAX_CHAIN_STEPS:      # ya no caben más saltos
                continue
            current = path[-1]
            # vecinos = todos los destinos alcanzables desde current, en orden
            # de preferencia (ver PESO_INTERMEDIO): con dos rutas del mismo
            # largo gana la que pasa por el formato que menos texto pierde.
            vecinos = sorted(
                {d for (s, d) in self._edges if s == current and d not in visited},
                key=lambda e: (_peso_intermedio(e), e),
            )
            for d in vecinos:
                new_path = path + [d]
                if d == dst:
                    return new_path
                visited.add(d)
                queue.append(new_path)
        return None

    # ------------------------------------------------------------------
    def all_targets(self, src: str) -> List[str]:
        """
        Destinos ofrecibles para src: los que la matriz declara y además tienen
        una ruta real (directa o en cadena corta) con los motores instalados.
        """
        src = src.lower()
        return sorted(d for d in COMPAT_MATRIX.get(src, [])
                      if self.find_path(src, d))

    # ------------------------------------------------------------------
    def supported_sources(self) -> List[str]:
        return sorted({s for (s, _) in self._edges})

    # ------------------------------------------------------------------
    def is_direct(self, src: str, dst: str) -> bool:
        return (src.lower(), dst.lower()) in self._edges

    # ------------------------------------------------------------------
    def is_indirect(self, src: str, dst: str) -> bool:
        if self.is_direct(src, dst):
            return False
        return self.find_path(src, dst) is not None


# Instancia global
graph = ConversionGraph()
