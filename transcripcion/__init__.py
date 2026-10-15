"""
transcripcion — Transcripción de audio y video con Whisper, sin internet.

  transcriber.py  → carga del modelo, elección CPU/GPU y transcripción
  entorno.py      → deja el ffmpeg propio en el PATH (Whisper lo llama así)
  odt_writer.py   → escritor de documentos .odt usado por el informe
"""


def human_size(num: int) -> str:
    """Tamaño legible: 1,2 MB."""
    for unit in ("bytes", "KB", "MB", "GB"):
        if num < 1024 or unit == "GB":
            if unit == "bytes":
                return f"{num} {unit}"
            return f"{num:.1f}".replace(".", ",") + f" {unit}"
        num /= 1024.0
    return f"{num} GB"
