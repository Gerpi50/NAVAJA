"""
core/logger.py — Sistema de log JSON de sesiones de conversión.
"""
import json
import os
import uuid
from datetime import datetime
from typing import Optional


class ConversionLogger:
    """Registra sesiones de conversión en archivos JSON en LOGS_DIR."""

    def __init__(self):
        self._session_id: Optional[str] = None
        self._started_at: Optional[str] = None
        self._entries: list = []
        self._filepath: Optional[str] = None

    def _get_logs_dir(self):
        from core.paths import LOGS_DIR
        return LOGS_DIR

    def start_session(self) -> None:
        """Inicia una nueva sesión de logging."""
        self._session_id = str(uuid.uuid4())[:8]
        self._started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._entries = []
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._filepath = os.path.join(self._get_logs_dir(), f"conversion_{ts}.json")

    def log_entry(self, status: str, input_info: dict, output_info: dict,
                  duration_seconds: float, error_message: str = "") -> dict:
        """Agrega una entrada a la sesión actual y la devuelve."""
        from core.hasher import build_certificate
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        success = (status == "ok")
        certificate_text = build_certificate(
            input_info, output_info, timestamp, success
        )
        entry = {
            "index":            len(self._entries),
            "timestamp":        timestamp,
            "status":           status,
            "input":            input_info,
            "output":           output_info,
            "duration_seconds": round(duration_seconds, 2),
            "error_message":    error_message,
            "certificate_text": certificate_text,
        }
        self._entries.append(entry)
        self._flush()
        return entry

    def finish_session(self) -> None:
        """Cierra la sesión y escribe el JSON final."""
        if not self._session_id:
            return
        successful = sum(1 for e in self._entries if e["status"] == "ok")
        failed = len(self._entries) - successful
        data = {
            "session_id":    self._session_id,
            "started_at":    self._started_at,
            "finished_at":   datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_files":   len(self._entries),
            "successful":    successful,
            "failed":        failed,
            "entries":       self._entries,
        }
        if self._filepath:
            try:
                with open(self._filepath, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
            except Exception:
                pass

    def _flush(self) -> None:
        """Escribe el estado actual al disco."""
        self.finish_session()

    def get_certificate(self, index: int) -> str:
        if 0 <= index < len(self._entries):
            return self._entries[index].get("certificate_text", "")
        return ""

    def get_all_certificates(self) -> str:
        return "\n".join(
            e.get("certificate_text", "") for e in self._entries
        )

    def list_sessions(self) -> list:
        try:
            logs_dir = self._get_logs_dir()
            files = sorted(
                [f for f in os.listdir(logs_dir) if f.endswith(".json")],
                reverse=True
            )
            return [os.path.join(logs_dir, f) for f in files]
        except Exception:
            return []

    def load_session(self, filepath: str) -> Optional[dict]:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None


logger = ConversionLogger()
