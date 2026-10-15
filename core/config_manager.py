"""
core/config_manager.py — Lectura y escritura de config.json.
"""
import json
import os

DEFAULTS = {
    "theme": "light",
    "last_output_folder": "",
    "max_parallel_conversions": 2,
    "file_size_limits_mb": {
        "image": 150,
        "audio": 500,
        "video": 2048,
        "document": 200,
        "data": 100
    },
    "audio_filter": {
        "enabled": False,
        "mode": "limpieza",
        "intensity": 50
    },
    "pdf_options": {
        "watermark_enabled": False,
        "footer_enabled": False,
        "page_numbers_enabled": False
    },
    "strip_metadata": True,
    # Intercalar "--- [PÁGINA n] ---" al convertir un documento a texto,
    # para que después se pueda citar de qué hoja salió cada cosa.
    "page_markers": True,
    "duplicate_file_action": "ask",
    "multi_sheet_action": "ask",
    "whisper_model_path": "",
    "priority_threshold_mb": 5,
    "ocr_enabled": True
}


class _ConfigManager:
    """Singleton de gestión de configuración."""

    def __init__(self):
        self._data: dict = {}
        self._restored = False
        self._config_file = None

    def _get_config_file(self):
        if self._config_file is None:
            from core.paths import CONFIG_FILE
            self._config_file = CONFIG_FILE
        return self._config_file

    def load(self) -> None:
        """Carga config.json. Si no existe o está corrupto, crea defaults."""
        cfg = self._get_config_file()
        if os.path.exists(cfg):
            try:
                with open(cfg, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                self._data = {**DEFAULTS, **loaded}
                # Merge profundo para dicts anidados
                for key, val in DEFAULTS.items():
                    if isinstance(val, dict) and key in loaded:
                        self._data[key] = {**val, **loaded[key]}
            except Exception:
                self._data = dict(DEFAULTS)
                self._restored = True
                self.save()
        else:
            self._data = dict(DEFAULTS)
            self.save()

    def save(self) -> None:
        """Guarda config.json inmediatamente."""
        cfg = self._get_config_file()
        try:
            os.makedirs(os.path.dirname(cfg), exist_ok=True)
            with open(cfg, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def get(self, key: str, default=None):
        """Accede a un valor por clave."""
        return self._data.get(key, default)

    def set(self, key: str, value) -> None:
        """Actualiza un valor y guarda inmediatamente."""
        self._data[key] = value
        self.save()

    @property
    def was_restored(self) -> bool:
        return self._restored


config = _ConfigManager()
