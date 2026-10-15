"""
core/hasher.py — Cálculo de hashes SHA-256 y MD5 de archivos.
"""
import hashlib
import os
from datetime import datetime


def sha256(filepath: str) -> str:
    """Calcula el SHA-256 de un archivo. Devuelve 'ERROR: motivo' si falla."""
    try:
        h = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception as e:
        return f"ERROR: {e}"


def md5(filepath: str) -> str:
    """Calcula el MD5 de un archivo. Devuelve 'ERROR: motivo' si falla."""
    try:
        h = hashlib.md5()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception as e:
        return f"ERROR: {e}"


# ─────────────────────────────────────────────────────────────────────────────
# Hash múltiple
#
# Se calculan varios algoritmos en UNA sola lectura del archivo: leer un video
# de 2 GB cuatro veces sería absurdo.
# ─────────────────────────────────────────────────────────────────────────────

# clave → (nombre para mostrar, es_confiable, para qué sirve)
HASH_ALGOS = {
    "sha256": ("SHA-256", True,
               "El estándar actual. Es el que más se usa para verificar integridad."),
    "sha512": ("SHA-512", True,
               "Más largo que SHA-256 y de la misma familia. Sirve como "
               "segundo hash independiente."),
    "sha3_256": ("SHA3-256", True,
                 "Familia distinta a SHA-2: si algún día se encontrara una "
                 "debilidad en SHA-2, este no se vería afectado."),
    "blake2b": ("BLAKE2b", True,
                "Tan seguro como SHA-3 y bastante más rápido."),
    "sha1": ("SHA-1", False,
             "OBSOLETO: se demostró que se pueden fabricar dos archivos "
             "distintos con el mismo SHA-1. Usalo sólo si un sistema viejo "
             "te lo exige, nunca como única garantía."),
    "md5": ("MD5", False,
            "OBSOLETO: roto desde hace años. Sirve para detectar una copia "
            "corrupta, no para probar que nadie modificó el archivo."),
}

# Por defecto se usan dos algoritmos fuertes y de familias distintas.
HASH_DEFAULT = ("sha256", "sha512")


def hash_file(filepath: str, algos=HASH_DEFAULT, progress_cb=None) -> dict:
    """Calcula varios hashes leyendo el archivo UNA sola vez.

    Devuelve {clave: hexdigest}. Nunca lanza: si algo falla, el valor es
    'ERROR: motivo'.
    """
    algos = tuple(a for a in algos if a in HASH_ALGOS)
    if not algos:
        algos = HASH_DEFAULT

    try:
        hs = {a: hashlib.new(a.replace("sha3_256", "sha3_256")) for a in algos}
    except Exception as e:
        return {a: f"ERROR: {e}" for a in algos}

    try:
        total = os.path.getsize(filepath)
        leido = 0
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                for h in hs.values():
                    h.update(chunk)
                leido += len(chunk)
                if progress_cb and total:
                    progress_cb(int(leido * 100 / total))
        return {a: h.hexdigest() for a, h in hs.items()}
    except Exception as e:
        return {a: f"ERROR: {e}" for a in algos}


# Cuántos caracteres hexadecimales produce cada algoritmo. Sirve para
# adivinar de cuál es un hash que le pasaron al usuario, que casi nunca
# viene acompañado del nombre del algoritmo.
_LARGO_A_ALGOS = {
    32:  ["md5"],
    40:  ["sha1"],
    64:  ["sha256", "sha3_256"],   # mismo largo, familias distintas
    128: ["sha512", "blake2b"],
}


def algos_por_longitud(hash_hex: str) -> list:
    """Algoritmos que pueden haber producido ese hash, según su longitud.

    Devuelve [] si no parece un hash (largo raro o caracteres no hex).
    """
    limpio = (hash_hex or "").strip().replace(" ", "").replace(":", "").lower()
    if not limpio or any(c not in "0123456789abcdef" for c in limpio):
        return []
    return list(_LARGO_A_ALGOS.get(len(limpio), []))


def normalizar_hash(hash_hex: str) -> str:
    """Deja el hash comparable: sin espacios ni separadores, en minúsculas."""
    return (hash_hex or "").strip().replace(" ", "").replace(":", "").lower()


def hash_label(algo: str) -> str:
    """Nombre para mostrar de un algoritmo ('sha256' → 'SHA-256')."""
    return HASH_ALGOS.get(algo, (algo.upper(), True, ""))[0]


def _human_size(nbytes: int) -> str:
    """Convierte bytes a formato legible."""
    for unit in ["B", "KB", "MB", "GB"]:
        if nbytes < 1024:
            return f"{nbytes:.1f} {unit}"
        nbytes /= 1024
    return f"{nbytes:.1f} TB"


def file_info(filepath: str) -> dict:
    """
    Devuelve un dict con información del archivo incluyendo hashes.
    Nunca lanza excepción.
    """
    try:
        stat = os.stat(filepath)
        size = stat.st_size
        modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        return {
            "path":        filepath,
            "filename":    os.path.basename(filepath),
            "size_bytes":  size,
            "size_human":  _human_size(size),
            "sha256":      sha256(filepath),
            "md5":         md5(filepath),
            "modified":    modified,
        }
    except Exception as e:
        return {
            "path":        filepath,
            "filename":    os.path.basename(filepath),
            "size_bytes":  0,
            "size_human":  "0 B",
            "sha256":      f"ERROR: {e}",
            "md5":         f"ERROR: {e}",
            "modified":    "ERROR",
        }


def build_certificate(input_info: dict, output_info: dict,
                       timestamp: str, success: bool) -> str:
    """
    Genera el texto de la constancia de conversión.
    Formato exacto según especificación.
    """
    sep = "─" * 57
    result_str = "Exitoso" if success else "Fallido"
    return (
        f"{sep}\n"
        f"CONSTANCIA DE CONVERSIÓN\n"
        f"{sep}\n"
        f"Se procedió a convertir el archivo:\n"
        f"  «{input_info['filename']}»\n"
        f"  SHA-256: {input_info['sha256']}\n"
        f"  MD5:     {input_info['md5']}\n"
        f"  Tamaño:  {input_info['size_human']}\n"
        f"\n"
        f"Al formato:\n"
        f"  «{output_info['filename']}»\n"
        f"  SHA-256: {output_info['sha256']}\n"
        f"  MD5:     {output_info['md5']}\n"
        f"  Tamaño:  {output_info['size_human']}\n"
        f"\n"
        f"Fecha y hora: {timestamp}\n"
        f"Resultado:    {result_str}\n"
        f"{sep}\n"
    )
