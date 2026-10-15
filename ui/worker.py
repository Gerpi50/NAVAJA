"""
ui/worker.py — QThread que ejecuta conversiones en segundo plano.

Procesa una cola de ConversionJob, opcionalmente en paralelo (respetando
max_parallel). Cada job puede aplicar: filtro de audio, eliminación de
metadatos, subtítulos automáticos (Whisper) y sellos de PDF.
"""
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal


@dataclass
class ConversionJob:
    """Representa un archivo a convertir con toda su configuración."""
    src_path:       str
    dst_path:       str
    dst_ext:        str
    audio_filter:   Optional[dict] = None   # {mode, intensity}
    subtitle:       Optional[dict] = None   # {language, burn_in}
    watermark:      Optional[dict] = None   # {text, font_size, color, opacity, angle}
    footer:         Optional[dict] = None   # {text, font_size, color, opacity}
    page_numbers:   Optional[dict] = None   # {position, format, start_from, font_size, color}
    strip_metadata: bool = True
    marcar_paginas: bool = True   # intercalar --- [PÁGINA n] --- al pasar a texto
    use_ocr:        bool = False
    ocr_language:   str  = "Español"
    ocr_grayscale:  bool = True             # PDF buscable en escala de grises (más liviano)
    priority:       bool = False            # True si < priority_threshold_mb


# Extensiones de video (para decidir burn-in de subtítulos)
_VIDEO_EXTS = {
    "mp4", "mkv", "avi", "mov", "webm", "flv", "wmv",
    "m4v", "3gp", "ts", "mpg", "mpeg", "ogv", "vob", "f4v",
}


class ConversionWorker(QThread):
    """QThread que procesa una cola de ConversionJob (en paralelo si se pide)."""

    progress        = pyqtSignal(str)              # mensaje log técnico
    progress_value  = pyqtSignal(int)              # 0-100
    job_started     = pyqtSignal(str)              # src_path (identificador)
    job_done        = pyqtSignal(str, bool, dict)  # src_path, success, log_entry
    finished        = pyqtSignal(int, int)         # exitosos, fallidos
    fatal_error     = pyqtSignal(str)              # error irrecuperable

    def __init__(self, jobs: list, max_parallel: int = 2):
        super().__init__()
        # Ordenar: primero los prioritarios
        self.jobs = sorted(jobs, key=lambda j: (0 if j.priority else 1))
        self.max_parallel = max(1, min(max_parallel, 4))
        self._running = True
        self._lock = threading.Lock()
        self._completed = 0
        self._success = 0
        self._errors = 0
        # Avisos de los motores (los que empiezan con ⚠). Van al log técnico
        # igual que todo, pero ahí se pierden entre los renglones de avance:
        # se guardan aparte para poder mostrarlos al terminar.
        self._avisos: list = []

    def stop(self):
        self._running = False

    # ------------------------------------------------------------------
    def run(self):
        from core.logger import logger
        logger.start_session()

        total = len(self.jobs)
        if total == 0:
            logger.finish_session()
            self.finished.emit(0, 0)
            return

        try:
            workers = self.max_parallel
            if workers <= 1:
                for job in self.jobs:
                    if not self._running:
                        break
                    self._process_job(job, total)
            else:
                with ThreadPoolExecutor(max_workers=workers) as pool:
                    for job in self.jobs:
                        pool.submit(self._process_job, job, total)
        except Exception as e:
            self.fatal_error.emit(str(e))

        self.progress_value.emit(100)
        logger.finish_session()
        self.finished.emit(self._success, self._errors)

    # ------------------------------------------------------------------
    def _process_job(self, job: "ConversionJob", total: int):
        """Procesa un único job. Seguro para ejecutarse en varios hilos."""
        if not self._running:
            return

        from core.runner import run_conversion, ConversionError
        from core.hasher import file_info
        from core.logger import logger

        name = os.path.basename(job.src_path)
        self.job_started.emit(job.src_path)
        self.progress.emit(f"⚙️  {name}")

        def log(msg: str):
            self.progress.emit(f"   {msg}")
            if msg.lstrip().startswith("⚠"):
                aviso = f"{name}: {msg.lstrip().lstrip('⚠ ')}"
                with self._lock:
                    if aviso not in self._avisos:
                        self._avisos.append(aviso)

        def page_progress(current: int, total_pages: int):
            """Mueve la barra dentro de un mismo archivo (p. ej. OCR por página).

            El avance de cada página se reparte en la fracción que le toca a este
            job sobre el total de la cola, para que la barra progrese aunque haya
            un único archivo grande (un libro completo en OCR)."""
            if not total_pages:
                return
            with self._lock:
                base = self._completed
            frac = (base + current / total_pages) / total
            self.progress_value.emit(min(int(frac * 100), 99))

        start_time = time.time()
        log_entry = {}
        ok = False

        try:
            dst_dir = os.path.dirname(job.dst_path)
            if dst_dir:
                os.makedirs(dst_dir, exist_ok=True)

            in_info = file_info(job.src_path)

            # ── Subtítulos automáticos (antes de convertir, por si hay burn-in) ──
            burn_subtitle_path = None
            if job.subtitle is not None:
                burn_subtitle_path = self._maybe_generate_subtitles(job, log)

            # ── Conversión principal ────────────────────────────────────
            if job.use_ocr:
                from motors.motor_ocr import (
                    convert_image_to_text, convert_pdf_to_text,
                    convert_image_to_searchable_pdf, convert_pdf_to_searchable_pdf,
                )
                src_ext = os.path.splitext(job.src_path)[1].lstrip(".").lower()
                if job.dst_ext == "pdf":
                    # PDF buscable: conserva el formato y agrega capa de texto OCR
                    if src_ext == "pdf":
                        convert_pdf_to_searchable_pdf(job.src_path, job.dst_path,
                                                      lang=job.ocr_language, progress_cb=log,
                                                      page_cb=page_progress,
                                                      grayscale=job.ocr_grayscale)
                    else:
                        convert_image_to_searchable_pdf(job.src_path, job.dst_path,
                                                        lang=job.ocr_language, progress_cb=log,
                                                        grayscale=job.ocr_grayscale)
                elif job.dst_ext != "txt":
                    # El OCR solo produce TXT o PDF buscable. Cualquier otro
                    # destino terminaría escribiendo texto plano dentro de un
                    # archivo con extensión ajena (un DOCX/HTML roto).
                    raise ValueError(
                        f"El OCR no puede generar {job.dst_ext.upper()}: "
                        "elegí TXT (texto plano) o PDF (PDF buscable)."
                    )
                elif src_ext == "pdf":
                    convert_pdf_to_text(job.src_path, job.dst_path,
                                        lang=job.ocr_language, progress_cb=log,
                                        page_cb=page_progress)
                else:
                    convert_image_to_text(job.src_path, job.dst_path,
                                          lang=job.ocr_language, progress_cb=log)
            else:
                run_conversion(
                    src_path           = job.src_path,
                    dst_path           = job.dst_path,
                    dst_ext            = job.dst_ext,
                    progress_cb        = log,
                    strip_metadata     = job.strip_metadata,
                    marcar_paginas     = job.marcar_paginas,
                    audio_filter       = job.audio_filter,
                    burn_subtitle_path = burn_subtitle_path,
                )

            # ── Salida de texto vacía = conversión fallida ───────────────
            # Un PDF escaneado sin OCR devolvía un .txt con solo saltos de
            # línea; se informaba "Exitoso" y hasta se emitía la constancia
            # con su hash. Un archivo de texto sin texto no es un éxito.
            self._check_text_output(job)

            # ── Post-proceso PDF: sellos y limpieza de metadatos ─────────
            if os.path.exists(job.dst_path) and job.dst_ext == "pdf":
                self._postprocess_pdf(job)

            # ── Info de salida ──────────────────────────────────────────
            out_info = file_info(job.dst_path) if os.path.exists(job.dst_path) else {
                "filename": os.path.basename(job.dst_path),
                "size_bytes": 0, "size_human": "0 B",
                "sha256": "ERROR: archivo no creado",
                "md5":    "ERROR: archivo no creado",
                "path":   job.dst_path, "modified": "",
            }

            duration = time.time() - start_time
            ok = os.path.exists(job.dst_path)
            with self._lock:
                if ok:
                    self._success += 1
                else:
                    self._errors += 1
                log_entry = logger.log_entry(
                    "ok" if ok else "error", in_info, out_info, duration
                )

        except ConversionError as e:
            # "Sin ruta" es cuando el formato no se puede alcanzar. Si la ruta
            # existía pero fallaron todos los motores, el cartel tenía que
            # decir otra cosa: el usuario veía "sin ruta" para algo que la app
            # sí ofrecía y no entendía nada.
            etiqueta = ("❌ Sin ruta de conversión"
                        if "No hay ruta" in str(e) else "❌ No se pudo convertir")
            log_entry = self._log_failure(job, name, str(e), start_time, etiqueta)
        except Exception as e:
            log_entry = self._log_failure(
                job, name, f"{type(e).__name__}: {e}",
                start_time, "❌ Error"
            )

        # Progreso por cantidad completada
        with self._lock:
            self._completed += 1
            pct = int(self._completed / total * 100)
        self.progress_value.emit(min(pct, 99))
        self.job_done.emit(job.src_path, ok, log_entry)

    # ------------------------------------------------------------------
    def _maybe_generate_subtitles(self, job, log) -> Optional[str]:
        """
        Genera un .srt junto al archivo de salida. Devuelve la ruta del .srt
        si se debe quemar en el video (burn-in), o None. Nunca propaga errores:
        si Whisper no está disponible, avisa y sigue sin subtítulos.
        """
        try:
            from motors.motor_subtitles import generate_srt, is_available
            if not is_available():
                self.progress.emit(
                    "   ⚠ Subtítulos omitidos: falta el paquete 'whisper'."
                )
                return None
            language = job.subtitle.get("language")
            srt_dst = os.path.splitext(job.dst_path)[0] + ".srt"
            generate_srt(job.src_path, srt_dst, language=language, progress_cb=log)

            dst_ext = job.dst_ext.lower()
            if job.subtitle.get("burn_in") and dst_ext in _VIDEO_EXTS:
                return srt_dst
            return None
        except Exception as e:
            self.progress.emit(f"   ⚠ No se pudieron generar subtítulos: {e}")
            return None

    # ------------------------------------------------------------------
    # Formatos cuyo contenido es texto legible: si salen sin una sola letra,
    # la conversión no sirvió (típico: PDF escaneado convertido sin OCR).
    _TEXT_EXTS = ("txt", "md", "html", "htm", "csv", "rst")

    def _check_text_output(self, job):
        """Falla si el archivo de texto generado no tiene texto."""
        if job.dst_ext not in self._TEXT_EXTS:
            return
        if not os.path.exists(job.dst_path):
            return
        try:
            with open(job.dst_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read(200_000)
        except Exception:
            return
        # Los marcadores que agrega el propio OCR ("--- Página 3 ---") y el
        # armazón HTML no cuentan como contenido.
        import re as _re
        limpio = _re.sub(r"---\s*P[áa]gina\s*\d+\s*---", " ", content)
        limpio = _re.sub(r"<[^>]+>", " ", limpio)
        if limpio.strip():
            return
        try:
            os.remove(job.dst_path)   # no dejar el archivo vacío dando vueltas
        except Exception:
            pass
        src_ext = os.path.splitext(job.src_path)[1].lstrip(".").lower()
        extra = ""
        if src_ext == "pdf" and not job.use_ocr:
            extra = ("\nEs un PDF escaneado (imágenes): activá "
                     "«🔍 Reconocer texto (OCR)» y volvé a convertir.")
        elif job.use_ocr:
            extra = ("\nEl OCR no reconoció ninguna letra: revisá el idioma "
                     "elegido y que las páginas no estén en blanco.")
        raise RuntimeError(
            f"No se extrajo ningún texto: el {job.dst_ext.upper()} habría "
            f"quedado vacío.{extra}"
        )

    # ------------------------------------------------------------------
    def _postprocess_pdf(self, job):
        """Aplica sellos al PDF y, si corresponde, limpia metadatos."""
        needs_stamp = (
            (job.watermark and job.watermark.get("text")) or
            (job.footer and job.footer.get("text")) or
            (job.page_numbers)
        )
        if needs_stamp:
            self.progress.emit("   🖊️  Aplicando sellos al PDF...")
            from motors.motor_pdf_stamp import apply_all_stamps
            import tempfile
            # El temporal va en la MISMA carpeta de salida: os.replace es atómico
            # solo dentro del mismo volumen (entre discos distintos fallaría).
            out_dir = os.path.dirname(job.dst_path) or "."
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False, dir=out_dir) as tmp:
                tmp_path = tmp.name
            try:
                apply_all_stamps(job.dst_path, tmp_path, options={
                    "watermark":    job.watermark    or {},
                    "footer":       job.footer       or {},
                    "page_numbers": job.page_numbers or {},
                })
                os.replace(tmp_path, job.dst_path)
            finally:
                if os.path.exists(tmp_path):
                    try:
                        os.unlink(tmp_path)
                    except Exception:
                        pass

        if job.strip_metadata:
            self._strip_pdf_metadata(job.dst_path)

    @staticmethod
    def _strip_pdf_metadata(pdf_path: str):
        """Elimina el diccionario /Info (autor, software, fechas) del PDF."""
        try:
            from pypdf import PdfReader, PdfWriter
            reader = PdfReader(pdf_path)
            writer = PdfWriter()
            for page in reader.pages:
                writer.add_page(page)
            # No copiamos reader.metadata → el PDF sale sin metadatos.
            import tempfile
            out_dir = os.path.dirname(pdf_path) or "."
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False, dir=out_dir) as tmp:
                tmp_path = tmp.name
            with open(tmp_path, "wb") as f:
                writer.write(f)
            os.replace(tmp_path, pdf_path)
        except Exception:
            pass  # Si falla, el PDF queda con sus metadatos originales.

    # ------------------------------------------------------------------
    def _log_failure(self, job, name, error_msg, start_time, header) -> dict:
        from core.hasher import file_info
        from core.logger import logger
        duration = time.time() - start_time
        self.progress.emit(f"{header}: {name}")
        self.progress.emit(f"   {error_msg}")
        dummy_out = {
            "filename": os.path.basename(job.dst_path),
            "size_bytes": 0, "size_human": "0 B",
            "sha256": "N/A", "md5": "N/A",
            "path": job.dst_path, "modified": "",
        }
        with self._lock:
            self._errors += 1
            return logger.log_entry("error", file_info(job.src_path),
                                    dummy_out, duration, error_msg)
