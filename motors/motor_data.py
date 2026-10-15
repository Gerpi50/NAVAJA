"""
motor_data.py — Conversión entre formatos de datos estructurados.
Soporta: JSON, XML, YAML, TOML, CSV, TSV, XLSX, SQL, Parquet, HDF5
"""
import os
from core.graph import BaseMotor


def _hay(modulo: str) -> bool:
    """True si la librería opcional está instalada en este equipo."""
    try:
        __import__(modulo)
        return True
    except Exception:
        return False


# Pandas necesita una librería distinta para cada formato binario, y no todas
# vienen empaquetadas. Antes se declaraban todos igual y la conversión
# reventaba recién al ejecutarse ("Missing optional dependency 'pytables'").
# Ahora se declara solo lo que este equipo puede hacer de verdad; lo demás
# lo resuelve el grafo por cadena (XLS → XLSX → JSON con LibreOffice).
_TEXTO_FMTS = ["json", "xml", "yaml", "yml", "toml", "csv", "tsv"]

DATA_READ_FMTS = list(_TEXTO_FMTS) + ["xlsx"]
DATA_WRITE_FMTS = list(_TEXTO_FMTS) + ["xlsx"]
if _hay("xlrd"):
    DATA_READ_FMTS.append("xls")
if _hay("xlwt"):
    DATA_WRITE_FMTS.append("xls")
if _hay("pyarrow") or _hay("fastparquet"):
    DATA_READ_FMTS.append("parquet")
    DATA_WRITE_FMTS.append("parquet")
if _hay("tables"):
    DATA_READ_FMTS += ["hdf5", "h5"]
    DATA_WRITE_FMTS += ["hdf5", "h5"]

# Se mantiene el nombre viejo: lo usan el motor y las pruebas.
DATA_FMTS = sorted(set(DATA_READ_FMTS) | set(DATA_WRITE_FMTS))

DATA_CONVERSIONS = [
    (s, d) for s in DATA_READ_FMTS for d in DATA_WRITE_FMTS if s != d
]


class DataMotor(BaseMotor):
    NAME = "Data"
    CONVERSIONS = DATA_CONVERSIONS

    @classmethod
    def is_available(cls) -> bool:
        try:
            import pandas
            return True
        except ImportError:
            return False

    def convert(self, src_path, dst_path, src_ext, dst_ext, **kwargs):
        import pandas as pd

        # --- LECTURA ---
        df = self._read(src_path, src_ext)

        # --- ESCRITURA ---
        self._write(df, dst_path, dst_ext)

    def _read(self, path, ext):
        import pandas as pd

        ext = ext.lower()
        if ext == "json":
            try:
                return pd.read_json(path)
            except ValueError:
                import json
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    return pd.DataFrame(data)
                elif isinstance(data, dict):
                    return pd.DataFrame([data])
                return pd.DataFrame()

        elif ext == "xml":
            return pd.read_xml(path)

        elif ext in ("yaml", "yml"):
            import yaml
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if isinstance(data, list):
                return pd.DataFrame(data)
            elif isinstance(data, dict):
                return pd.DataFrame([data])
            return pd.DataFrame()

        elif ext == "toml":
            try:
                import tomllib
            except ImportError:
                import tomli as tomllib
            with open(path, "rb") as f:
                data = tomllib.load(f)
            if isinstance(data, dict):
                # Aplanar primer nivel
                flat = {}
                for k, v in data.items():
                    if isinstance(v, dict):
                        for k2, v2 in v.items():
                            flat[f"{k}.{k2}"] = v2
                    else:
                        flat[k] = v
                return pd.DataFrame([flat])
            return pd.DataFrame()

        elif ext == "csv":
            return pd.read_csv(path, encoding_errors="replace")

        elif ext == "tsv":
            return pd.read_csv(path, sep="\t", encoding_errors="replace")

        elif ext in ("xlsx", "xls"):
            from motors.motor_excel_merger import leer_excel
            return leer_excel(pd, path)

        elif ext == "parquet":
            return pd.read_parquet(path)

        elif ext in ("hdf5", "h5"):
            store = pd.HDFStore(path, mode="r")
            keys = store.keys()
            store.close()
            return pd.read_hdf(path, key=keys[0] if keys else "/data")

        else:
            raise ValueError(f"Formato de lectura no soportado: {ext}")

    def _write(self, df, path, ext):
        import pandas as pd
        import json

        ext = ext.lower()
        if ext == "json":
            df.to_json(path, orient="records", indent=2, force_ascii=False)

        elif ext == "xml":
            df.to_xml(path, index=False)

        elif ext in ("yaml", "yml"):
            import yaml
            records = df.to_dict(orient="records")
            with open(path, "w", encoding="utf-8") as f:
                yaml.dump(records, f, allow_unicode=True, default_flow_style=False)

        elif ext == "toml":
            try:
                import tomli_w as tomllib_w
            except ImportError:
                raise RuntimeError("Instala tomli-w para exportar a TOML.")
            records = df.to_dict(orient="records")
            with open(path, "wb") as f:
                tomllib_w.dump({"data": records}, f)

        elif ext == "csv":
            df.to_csv(path, index=False, encoding="utf-8")

        elif ext == "tsv":
            df.to_csv(path, index=False, sep="\t", encoding="utf-8")

        elif ext in ("xlsx", "xls"):
            df.to_excel(path, index=False)

        elif ext == "parquet":
            df.to_parquet(path, index=False)

        elif ext in ("hdf5", "h5"):
            df.to_hdf(path, key="data", mode="w")

        else:
            raise ValueError(f"Formato de escritura no soportado: {ext}")
