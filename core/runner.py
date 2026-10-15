"""
runner.py — Ejecuta una conversión (directa o en cadena).
Resuelve la ruta en el grafo y aplica cada motor intermedio.
"""
import os
import tempfile
from typing import Callable, Optional
from .graph import graph

try:
    from .paths import TEMP_DIR as _TEMP_DIR
except Exception:
    _TEMP_DIR = None


class ConversionError(Exception):
    pass


def run_conversion(
    src_path: str,
    dst_path: str,
    dst_ext: str,
    progress_cb: Optional[Callable[[str], None]] = None,
    **kwargs,
) -> None:
    """
    Convierte src_path → dst_path con extensión dst_ext.
    Resuelve rutas indirectas automáticamente.

    Raises ConversionError si no hay ruta disponible.
    """
    src_ext = os.path.splitext(src_path)[1].lstrip(".").lower()
    dst_ext = dst_ext.lower()

    def log(msg):
        if progress_cb:
            progress_cb(msg)

    path = graph.find_path(src_ext, dst_ext)
    if not path:
        raise ConversionError(
            f"No hay ruta de conversión disponible: {src_ext} → {dst_ext}\n"
            "Verifica que los motores necesarios estén instalados."
        )

    if len(path) == 2:
        # Conversión directa
        _convertir_paso(src_path, dst_path, src_ext, dst_ext, log, **kwargs)

    else:
        # Conversión en cadena: usar archivos temporales intermedios
        log(f"🔗  Ruta: {' → '.join(p.upper() for p in path)}")
        temp_files = []
        current_src = src_path

        try:
            for i in range(len(path) - 1):
                step_src_ext = path[i]
                step_dst_ext = path[i + 1]
                is_last = (i == len(path) - 2)
                if is_last:
                    step_dst = dst_path
                else:
                    kw = {"suffix": f".{step_dst_ext}", "delete": False}
                    if _TEMP_DIR:
                        kw["dir"] = _TEMP_DIR
                    tmp = tempfile.NamedTemporaryFile(**kw)
                    tmp.close()
                    step_dst = tmp.name
                    temp_files.append(step_dst)

                _convertir_paso(current_src, step_dst, step_src_ext,
                                step_dst_ext, log, sangria="   ↳ ", **kwargs)
                current_src = step_dst

        finally:
            for f in temp_files:
                try:
                    os.unlink(f)
                except Exception:
                    pass


def _convertir_paso(src, dst, src_ext, dst_ext, log, sangria="⚙️  ", **kwargs):
    """Hace un paso de la conversión probando los motores en orden.

    Puede haber más de un motor para el mismo par (Word y LibreOffice hacen
    los dos DOCX → PDF). Antes se usaba solo el primero y, si ese fallaba
    —Word ocupado, un COM que no responde— la conversión se daba por
    perdida aunque el otro motor estuviera ahí al lado. Ahora se prueban
    todos y solo se avisa el error si fallan todos.
    """
    motores = graph.direct_motors(src_ext, dst_ext)
    if not motores:
        raise ConversionError(
            f"No hay motor para {src_ext.upper()} → {dst_ext.upper()}")

    # Los motores reciben el mismo canal de avance que el runner: varios
    # tienen algo para contar mientras trabajan (qué layout están rehaciendo,
    # qué decidieron omitir) y sin esto esos avisos no llegaban a ningún lado,
    # porque progress_cb era un parámetro con nombre de run_conversion y nunca
    # entraba en los kwargs que se le pasan al motor.
    kwargs.setdefault("progress_cb", log)

    errores = []
    for i, motor_cls in enumerate(motores):
        if i:
            log(f"   ↺ Reintentando con {motor_cls.NAME}…")
        else:
            log(f"{sangria}{src_ext.upper()} → {dst_ext.upper()} [{motor_cls.NAME}]")
        try:
            motor_cls().convert(src, dst, src_ext, dst_ext, **kwargs)
            if os.path.exists(dst) and os.path.getsize(dst) > 0:
                return
            raise ConversionError("el motor no generó ningún archivo")
        except Exception as e:
            errores.append(f"{motor_cls.NAME}: {e}")
            # Un archivo a medio escribir confunde al paso siguiente.
            if os.path.exists(dst):
                try:
                    os.unlink(dst)
                except OSError:
                    pass

    raise ConversionError(
        f"No se pudo convertir {src_ext.upper()} → {dst_ext.upper()}.\n"
        + "\n".join(errores[-3:])
    )
