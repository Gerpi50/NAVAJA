"""
motors/motor_excel_merger.py — Une múltiples XLS/XLSX y parte por tamaño.
Modos:
  "sheets"  — cada archivo de entrada queda en una hoja separada
  "stacked" — todas las filas apiladas verticalmente en una sola hoja
"""
import os
from typing import Callable, List, Optional


EXCEL_EXTS = {".xlsx", ".xls"}


def is_available() -> bool:
    try:
        import pandas  # noqa: F401
        import openpyxl  # noqa: F401
        return True
    except ImportError:
        return False


def collect_excel_files(folder: str) -> List[str]:
    files = sorted([
        os.path.join(folder, f)
        for f in os.listdir(folder)
        if os.path.splitext(f)[1].lower() in EXCEL_EXTS
    ])
    return files


def leer_excel(pd, fpath: str, **kwargs):
    """pd.read_excel tolerante con los .xls que exportan algunos sistemas.

    Los .xls de las compañías telefónicas (p. ej. los de Telecom) traen
    registros repetidos y xlrd los rechaza con "Workbook corruption:
    seen[2] == 4", aunque Excel los abre sin quejarse. Se le pide a xlrd
    que no los descarte: los datos salen completos igual.
    """
    if fpath.lower().endswith(".xls"):
        kwargs["engine_kwargs"] = {"ignore_workbook_corruption": True}
    return pd.read_excel(fpath, **kwargs)


def _nombre_de_hoja(name: str, usados: set) -> str:
    """Recorta a 31 caracteres (límite de Excel) sin pisar una hoja ya usada."""
    base = name[:31]
    safe, n = base, 2
    while safe.lower() in usados:
        sufijo = f"~{n}"
        safe = base[:31 - len(sufijo)] + sufijo
        n += 1
    usados.add(safe.lower())
    return safe


def _file_size_mb(path: str) -> float:
    return os.path.getsize(path) / (1024 * 1024)


def merge_excel(
    files: List[str],
    output_dir: str,
    mode: str,
    max_mb: float,
    progress_cb: Optional[Callable[[str], None]] = None,
) -> List[str]:
    """
    Une archivos Excel y parte el resultado en chunks de max_mb MB.
    mode: "sheets" | "stacked"
    Devuelve lista de rutas generadas.
    """
    import pandas as pd

    if not files:
        raise ValueError("No se encontraron archivos Excel.")

    os.makedirs(output_dir, exist_ok=True)

    if mode == "sheets":
        return _merge_by_sheets(files, output_dir, max_mb, progress_cb)
    else:
        return _merge_stacked(files, output_dir, max_mb, progress_cb, pd)


# ─── Modo: cada archivo = una hoja ──────────────────────────────────────────

def _merge_by_sheets(files, output_dir, max_mb, progress_cb):
    import pandas as pd

    out_paths = []
    part_num  = 1
    batch     = []   # list of (sheet_name, DataFrame)

    def save_batch(sheets):
        nonlocal part_num
        out_path = os.path.join(output_dir, f"unido_parte{part_num:02d}.xlsx")
        usados = set()
        with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
            for name, df in sheets:
                safe_name = _nombre_de_hoja(name, usados)
                df.to_excel(writer, sheet_name=safe_name, index=False)
        size = _file_size_mb(out_path)
        if progress_cb:
            progress_cb(f"  ✅ unido_parte{part_num:02d}.xlsx  ({size:.1f} MB, {len(sheets)} hoja{'s' if len(sheets)!=1 else ''})")
        out_paths.append(out_path)
        part_num += 1

    for i, fpath in enumerate(files):
        stem = os.path.splitext(os.path.basename(fpath))[0]
        if progress_cb:
            progress_cb(f"Leyendo: {os.path.basename(fpath)}")
        try:
            df = leer_excel(pd, fpath, sheet_name=None)  # dict sheet→df
        except Exception as e:
            if progress_cb:
                progress_cb(f"  ⚠ Error: {e}")
            continue

        for sheet_name, sheet_df in df.items():
            display = f"{stem}__{sheet_name}" if len(df) > 1 else stem
            batch.append((display, sheet_df))

            # Guardar batch de prueba para estimar tamaño
            if len(batch) >= 1:
                test_path = os.path.join(output_dir, "_test_size.xlsx")
                try:
                    usados = set()
                    with pd.ExcelWriter(test_path, engine="openpyxl") as w:
                        for n, d in batch:
                            d.to_excel(w, sheet_name=_nombre_de_hoja(n, usados), index=False)
                    size = _file_size_mb(test_path)
                    os.unlink(test_path)
                    if size >= max_mb and len(batch) > 1:
                        save_batch(batch[:-1])
                        batch = [batch[-1]]
                except Exception:
                    try:
                        os.unlink(test_path)
                    except Exception:
                        pass

    if batch:
        save_batch(batch)

    if progress_cb:
        progress_cb(f"✅ {len(out_paths)} archivo{'s' if len(out_paths)!=1 else ''} generado{'s' if len(out_paths)!=1 else ''}.")
    return out_paths


# ─── Modo: filas apiladas ───────────────────────────────────────────────────

def _merge_stacked(files, output_dir, max_mb, progress_cb, pd):
    out_paths  = []
    part_num   = 1
    rows_batch = []   # list of DataFrames

    def save_batch(dfs):
        nonlocal part_num
        combined  = pd.concat(dfs, ignore_index=True)
        out_path  = os.path.join(output_dir, f"unido_parte{part_num:02d}.xlsx")
        combined.to_excel(out_path, index=False, engine="openpyxl")
        size = _file_size_mb(out_path)
        if progress_cb:
            progress_cb(f"  ✅ unido_parte{part_num:02d}.xlsx  ({size:.1f} MB, {len(combined):,} filas)")
        out_paths.append(out_path)
        part_num += 1

    for fpath in files:
        if progress_cb:
            progress_cb(f"Leyendo: {os.path.basename(fpath)}")
        try:
            xls = leer_excel(pd, fpath, sheet_name=None)
            for sheet_df in xls.values():
                rows_batch.append(sheet_df)

            # Estimar tamaño acumulado
            test_path = os.path.join(output_dir, "_test_size.xlsx")
            try:
                combined_test = pd.concat(rows_batch, ignore_index=True)
                combined_test.to_excel(test_path, index=False, engine="openpyxl")
                size = _file_size_mb(test_path)
                os.unlink(test_path)
                if size >= max_mb and len(rows_batch) > 1:
                    save_batch(rows_batch[:-1])
                    rows_batch = [rows_batch[-1]]
            except Exception:
                try:
                    os.unlink(test_path)
                except Exception:
                    pass
        except Exception as e:
            if progress_cb:
                progress_cb(f"  ⚠ Error leyendo {os.path.basename(fpath)}: {e}")

    if rows_batch:
        save_batch(rows_batch)

    if progress_cb:
        progress_cb(f"✅ {len(out_paths)} archivo{'s' if len(out_paths)!=1 else ''} generado{'s' if len(out_paths)!=1 else ''}.")
    return out_paths
