"""
core/informe.py — Generador de informes técnicos de procesamiento digital.
Usado por todos los módulos de procesamiento para producir constancias con hash.
"""
import hashlib
import os
from datetime import datetime
from typing import List, Optional


_MESES = [
    "", "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def fecha_formal() -> str:
    hoy = datetime.now()
    return f"{hoy.day:02d} de {_MESES[hoy.month]} de {hoy.year}"


# ── Concordancia singular / plural ──────────────────────────────────────
# Los informes son formales: si se procesó un solo archivo tienen que decir
# "el original", no "los originales".

def plural(sustantivo: str) -> str:
    """Pluraliza el núcleo de la frase: "archivo de audio" → "archivos de audio"."""
    nucleo, sep, resto = sustantivo.partition(" ")
    sufijo = "s" if nucleo[-1:].lower() in "aeiouáéíóú" else "es"
    return f"{nucleo}{sufijo}{sep}{resto}"


def tamano_legible(mb: float) -> str:
    """Tamaño en la unidad que se entiende: MB, KB o bytes."""
    if mb is None:
        return ""
    if mb >= 1:
        return f"{mb:.2f} MB"
    kb = mb * 1024
    if kb >= 1:
        return f"{kb:.0f} KB"
    return f"{int(round(kb * 1024))} bytes"


def ref_objeto(n: int, objeto: str = "archivo") -> str:
    """"el archivo de audio" (n == 1) / "los archivos de audio" (n > 1)."""
    return f"el {objeto}" if n == 1 else f"los {plural(objeto)}"


def sha256_file(path: str, pct_cb=None) -> str:
    """SHA-256 en bloques de 1 MB. Lanza excepción si el archivo no existe.

    pct_cb(0–100) avisa el avance: con un video de varios GB el cálculo
    tarda, y sin avisar parece que el programa se quedó.
    """
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


def file_info(path: str, pct_cb=None) -> dict:
    """
    Devuelve dict con filename, sha256, size_mb.
    No lanza excepción: registra el error en sha256 si algo falla.
    """
    try:
        size_mb = os.path.getsize(path) / (1024 * 1024)
        h256    = sha256_file(path, pct_cb)
    except Exception as e:
        size_mb = 0.0
        h256    = f"ERROR: {e}"
    return {
        "filename": os.path.basename(path),
        "sha256":   h256,
        "size_mb":  size_mb,
    }


def build_informe(
    accion: str,
    originals: List[dict],   # [{"filename": str, "sha256": str, "size_mb": float}, ...]
    results: List[dict],     # idem
    extra_lines: Optional[str] = None,   # texto adicional antes de los resultantes
    objeto: str = "archivo",             # sustantivo SINGULAR: "archivo de audio"
    parametros: Optional[str] = None,    # parámetros del proceso, entre paréntesis
) -> str:
    """
    Construye el texto del informe técnico estándar.

    accion     — verbo en infinitivo SIN el objeto, ej: "dividir en partes",
                 "unir", "convertir al formato PDF". El objeto lo pone la
                 función, para que concuerde en número con `originals`.
    originals  — lista de archivos de entrada con sus metadatos.
    results    — lista de archivos resultantes con sus metadatos.
    extra_lines— texto adicional (opcional) insertado antes del detalle de resultantes.
    objeto     — sustantivo en singular que describe la entrada; se pluraliza
                 solo si hay más de un original.
    parametros — detalle del proceso ("máximo 10 MB por parte"); va entre
                 paréntesis al final de la frase.
    """
    fecha = fecha_formal()
    n     = len(originals)
    m     = len(results)
    ref_obj    = ref_objeto(n, objeto)
    ref_mismos = "del mismo"   if n == 1 else "de los mismos"
    params     = f" ({parametros})" if parametros else ""

    orig_lines = ""
    for o in originals:
        size_str = f"  Tamaño: {o['size_mb']:.2f} MB\n" if o.get("size_mb") else ""
        orig_lines += (
            f"\n- Archivo: {o['filename']}\n"
            f"  SHA-256: {o['sha256']}\n"
            f"{size_str}"
        )

    result_lines = ""
    for r in results:
        size_str = f" ({r['size_mb']:.2f} MB)" if r.get("size_mb") else ""
        result_lines += f"- {r['filename']}{size_str}  |  SHA-256: {r['sha256']}\n"

    extra = f"\n{extra_lines}\n" if extra_lines else ""

    texto = (
        f"INFORME TÉCNICO DE PROCESAMIENTO DIGITAL\n"
        f"{'─' * 55}\n"
        f"\n"
        f"El día de la fecha ({fecha}) se procedió a {accion} {ref_obj} "
        f"que se detalla{'n' if n > 1 else ''} "
        f"a continuación{params}:\n"
        f"{orig_lines}\n"
        f"Terminado el proceso, se adjunta{'n' if m > 1 else ''} el resultado, "
        f"que puede haber reducido la calidad {ref_mismos}. "
        f"{'El original no se modificó' if n == 1 else 'Los originales no se modificaron'}.\n"
        f"{extra}\n"
        f"{'Detalle del archivo resultante' if m == 1 else 'Detalle de los archivos resultantes'}:\n"
        f"{'─' * 55}\n"
        f"{result_lines}"
        f"{'─' * 55}\n"
        f"Fecha de generación: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    )
    return texto


# ─────────────────────────────────────────────────────────────────────────────
# Informe detallado: narra qué se hizo con CADA archivo
#
# El informe de arriba lista entradas y salidas por separado, así que con
# varios archivos no se sabe cuál salió de cuál. Este los vincula uno a uno.
# ─────────────────────────────────────────────────────────────────────────────

def info_completa(path: str, algos=None) -> dict:
    """file_info con varios hashes: {filename, size_mb, hashes: {algo: hex}}."""
    from core.hasher import hash_file, HASH_DEFAULT
    algos = algos or HASH_DEFAULT
    try:
        size_mb = os.path.getsize(path) / (1024 * 1024)
    except Exception:
        size_mb = 0.0
    return {
        "filename": os.path.basename(path),
        "path": path,
        "size_mb": size_mb,
        "hashes": hash_file(path, algos),
    }


def _bloque_hashes(info: dict, sangria: str = "     ") -> str:
    from core.hasher import hash_label
    lineas = []
    for algo, valor in (info.get("hashes") or {}).items():
        lineas.append(f"{sangria}{hash_label(algo)}: {valor}")
    if not lineas and info.get("sha256"):
        lineas.append(f"{sangria}SHA-256: {info['sha256']}")
    return "\n".join(lineas)


def build_informe_detallado(operaciones: List[dict],
                            encabezado: Optional[str] = None) -> str:
    """Informe que describe archivo por archivo qué se hizo.

    `operaciones` es una lista de:
        {"frase": "convertir el archivo «a.docx» al formato «.pdf»",
         "original": info_completa(...),         # o None
         "resultados": [info_completa(...), ...]}

    Cuando la operación toma VARIAS entradas a la vez (unir, por ejemplo) se
    usa "originales": [info_completa(...), ...] en lugar de "original". Todas
    quedan dentro del mismo punto, con su hash, porque son una sola operación:
    partirlas en puntos separados haría parecer que hubo varios procesos.

    La `frase` la arma cada módulo, porque sólo él sabe qué hizo. Se inserta
    después de "Se procedió a", así que va en infinitivo.
    """
    fecha = fecha_formal()

    # "del archivo" sólo si de verdad hubo uno: una sola operación puede tomar
    # varios de entrada (unir), y ahí corresponde "de cada archivo".
    n_archivos = sum(
        len([o for o in (op.get("originales") or
                         ([op["original"]] if op.get("original") else []))
             if o]) + len(op.get("resultados") or [])
        for op in operaciones)

    if len(operaciones) == 1:
        cabecera = (
            f"Informo que, el día de la fecha ({fecha}), se realizó la "
            "operación que se detalla a continuación, dejándose constancia "
            "de los códigos de verificación (hash) "
            f"{'del archivo' if n_archivos <= 2 else 'de cada archivo'} "
            "antes y después del proceso.")
    else:
        cabecera = (
            f"Informo que, el día de la fecha ({fecha}), se realizaron las "
            "operaciones que se detallan a continuación, dejándose constancia "
            "de los códigos de verificación (hash) de cada archivo antes y "
            "después del proceso.")

    partes = [
        "INFORME TÉCNICO DE PROCESAMIENTO DIGITAL",
        "─" * 68,
        "",
        encabezado or cabecera,
        "",
    ]

    for i, op in enumerate(operaciones, start=1):
        partes.append("─" * 68)
        partes.append(f"{i}) Se procedió a {op['frase']}.")
        partes.append("")

        origenes = op.get("originales")
        if origenes is None:
            uno = op.get("original")
            origenes = [uno] if uno else []
        origenes = [o for o in origenes if o]

        if len(origenes) == 1:
            origen = origenes[0]
            tam = (f" ({tamano_legible(origen['size_mb'])})"
                   if origen.get("size_mb") else "")
            partes.append(f"   Archivo original: {origen['filename']}{tam}")
            partes.append(_bloque_hashes(origen))
            partes.append("")
        elif len(origenes) > 1:
            partes.append(f"   Archivos originales ({len(origenes)}):")
            for j, o in enumerate(origenes, start=1):
                tam = (f" ({tamano_legible(o['size_mb'])})"
                       if o.get("size_mb") else "")
                partes.append(f"     {j}. {o['filename']}{tam}")
                partes.append(_bloque_hashes(o, sangria="        "))
            partes.append("")

        resultados = op.get("resultados") or []
        if len(resultados) == 1:
            r = resultados[0]
            tam = f" ({tamano_legible(r['size_mb'])})" if r.get("size_mb") else ""
            partes.append(f"   Archivo resultante: {r['filename']}{tam}")
            partes.append(_bloque_hashes(r))
        elif len(resultados) > 1:
            partes.append(f"   Archivos resultantes ({len(resultados)}):")
            for j, r in enumerate(resultados, start=1):
                tam = f" ({tamano_legible(r['size_mb'])})" if r.get("size_mb") else ""
                partes.append(f"     {j}. {r['filename']}{tam}")
                partes.append(_bloque_hashes(r, sangria="        "))
        else:
            partes.append("   Sin archivos resultantes.")
        partes.append("")

    partes.append("─" * 68)
    partes.append(
        f"Fecha de generación: "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    return "\n".join(partes)


def save_informe(texto: str, directory: str, prefix: str = "Informe") -> str:
    """
    Guarda el informe en directory/prefix_YYYYMMDD_HHMMSS.txt.
    Devuelve la ruta del archivo creado.
    """
    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{prefix}_{ts}.txt"
    out_path = os.path.join(directory, filename)
    os.makedirs(directory, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(texto)
    return out_path
