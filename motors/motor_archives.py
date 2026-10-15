"""
motor_archives.py — Conversión entre formatos de archivo comprimido.
Motores: zipfile/tarfile/gzip (stdlib), py7zr (7z), rarfile+UnRAR (rar).
Soporta: ZIP, TAR, GZ, 7Z, RAR(solo lectura)
"""
import gzip
import os
import shutil
import tarfile
import tempfile
import zipfile

from core.graph import BaseMotor
from core.paths import BIN_DIR, TEMP_DIR


def _find_unrar():
    """UnRAR.exe: en bin/ del programa, en PATH o junto a WinRAR."""
    candidates = [
        os.path.join(BIN_DIR, "UnRAR.exe"),
        shutil.which("unrar"),
        r"C:\Program Files\WinRAR\UnRAR.exe",
        r"C:\Program Files (x86)\WinRAR\UnRAR.exe",
    ]
    for c in candidates:
        if c and os.path.isfile(c):
            return c
    return None


def _safe_members(names, dest):
    """Evita path traversal (zip-slip): solo rutas relativas dentro de dest."""
    dest = os.path.abspath(dest)
    for name in names:
        target = os.path.abspath(os.path.join(dest, name))
        if not target.startswith(dest + os.sep) and target != dest:
            raise RuntimeError(f"Ruta insegura dentro del archivo: {name}")


def _extract_zip(src, dest):
    with zipfile.ZipFile(src) as zf:
        _safe_members(zf.namelist(), dest)
        zf.extractall(dest)


def _extract_tar(src, dest):
    with tarfile.open(src) as tf:
        _safe_members([m.name for m in tf.getmembers()], dest)
        tf.extractall(dest)


def _extract_7z(src, dest):
    import py7zr
    with py7zr.SevenZipFile(src) as zf:
        _safe_members(zf.getnames(), dest)
        zf.extractall(dest)


def _extract_rar(src, dest):
    import rarfile
    unrar = _find_unrar()
    if unrar:
        rarfile.UNRAR_TOOL = unrar
    with rarfile.RarFile(src) as rf:
        _safe_members(rf.namelist(), dest)
        rf.extractall(dest)


def _pack_zip(src_dir, dst):
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, files in os.walk(src_dir):
            for f in files:
                full = os.path.join(root, f)
                zf.write(full, os.path.relpath(full, src_dir))


def _pack_tar(src_dir, dst):
    with tarfile.open(dst, "w") as tf:
        for entry in sorted(os.listdir(src_dir)):
            tf.add(os.path.join(src_dir, entry), arcname=entry)


def _pack_7z(src_dir, dst):
    import py7zr
    with py7zr.SevenZipFile(dst, "w") as zf:
        for entry in sorted(os.listdir(src_dir)):
            zf.writeall(os.path.join(src_dir, entry), arcname=entry)


class ArchiveMotor(BaseMotor):
    """Convierte re-empaquetando: extrae a un temporal y comprime al destino.
    tar→gz y gz→tar son especiales (gzip envuelve un único archivo)."""
    NAME = "Archivos (zip/tar/7z/rar)"
    CONVERSIONS = [
        ("zip", "tar"), ("zip", "7z"),
        ("tar", "zip"), ("tar", "gz"),
        ("gz",  "tar"),
        ("7z",  "zip"),
        ("rar", "zip"),
    ]

    @classmethod
    def is_available(cls) -> bool:
        return True  # stdlib siempre; py7zr/rarfile se validan por conversión

    # ------------------------------------------------------------------
    def convert(self, src_path, dst_path, src_ext, dst_ext,
                progress_cb=None, **kwargs):
        def log(msg):
            if progress_cb:
                progress_cb(msg)

        # Casos directos gzip (sin re-empaquetar contenido)
        if src_ext == "tar" and dst_ext == "gz":
            log("📦 Comprimiendo tar con gzip...")
            with open(src_path, "rb") as fin, gzip.open(dst_path, "wb") as fout:
                shutil.copyfileobj(fin, fout)
            return
        if src_ext == "gz" and dst_ext == "tar":
            log("📦 Descomprimiendo gzip...")
            with gzip.open(src_path, "rb") as fin, open(dst_path, "wb") as fout:
                shutil.copyfileobj(fin, fout)
            if not tarfile.is_tarfile(dst_path):
                os.unlink(dst_path)
                raise RuntimeError(
                    "El .gz no contiene un tar (era un archivo suelto comprimido)."
                )
            return

        # Validar dependencias antes de trabajar
        if src_ext == "7z" or dst_ext == "7z":
            try:
                import py7zr  # noqa: F401
            except ImportError:
                raise RuntimeError("Falta el paquete 'py7zr' (pip install py7zr).")
        if src_ext == "rar":
            try:
                import rarfile  # noqa: F401
            except ImportError:
                raise RuntimeError("Falta el paquete 'rarfile' (pip install rarfile).")
            if _find_unrar() is None:
                raise RuntimeError(
                    "Para leer RAR se necesita UnRAR.exe (instalá WinRAR o "
                    "copiá UnRAR.exe a la carpeta bin/ del programa)."
                )

        extractors = {"zip": _extract_zip, "tar": _extract_tar,
                      "7z": _extract_7z, "rar": _extract_rar}
        packers = {"zip": _pack_zip, "tar": _pack_tar, "7z": _pack_7z}

        tmp = tempfile.mkdtemp(dir=TEMP_DIR)
        try:
            log(f"📦 Extrayendo {src_ext.upper()}...")
            extractors[src_ext](src_path, tmp)
            log(f"📦 Empaquetando {dst_ext.upper()}...")
            packers[dst_ext](tmp, dst_path)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
