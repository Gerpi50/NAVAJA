<p align="center">
  <img src="assets/icono.png" width="120" alt="Navaja">
</p>

<h1 align="center">Navaja</h1>
<p align="center"><strong>Editor universal de archivos para Windows: convertir, partir, unir, firmar, transcribir y verificar, todo sin internet.</strong></p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/licencia-GPL--3.0-blue" alt="Licencia GPL-3.0"></a>
  <img src="https://img.shields.io/badge/python-3.10%2B-3776AB" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/interfaz-PyQt6-41CD52" alt="PyQt6">
  <img src="https://img.shields.io/badge/funciona-sin%20internet-success" alt="Sin internet">
</p>

<p align="center">
  <img src="docs/captura-inicio.png" width="900" alt="Pantalla de inicio de Navaja">
</p>

Navaja junta en un solo programa las herramientas que se usan todos los días con
archivos: pasar un Word a PDF, partir un PDF que pesa demasiado, sacarle el texto a un
escaneo, transcribir un audio, achicar un video para mandarlo por correo o comprobar con
un hash que un archivo no fue modificado.

Está pensado para quien **no sabe de informática**: la pantalla de inicio pregunta
*«¿qué necesitás hacer?»* y lleva directo a la herramienta correcta. Todo funciona
**sin conexión**: ningún archivo sale de la computadora.

> 🇬🇧 **English:** Navaja is an offline, all-in-one file toolkit for Windows (PyQt6).
> It converts between 100+ formats with automatic multi-step routing, and includes PDF
> tools (merge, split, OCR, digital signing with PFX or USB tokens, PDF→Excel tables),
> audio/video tools (split, merge, compress to a size limit, frame capture, noise
> reduction, Whisper transcription) and SHA-256/SHA-512 integrity checks. The UI is in
> Spanish. Licensed under GPL-3.0.

---

## ✨ Qué hace

| Módulo | Herramientas |
|---|---|
| 🔄 **Convertir** | Más de 100 formatos de entrada (imágenes, audio, video, documentos, datos, correos, e-books, fuentes, subtítulos, comprimidos). Si no hay conversión directa, encuentra sola la cadena más corta: `HEIC → PNG → SVG`. Solo muestra los formatos a los que se puede llegar. |
| 📄 **PDF** | Unir · Partir por tamaño o por páginas · Ajustar una carpeta a un límite de tamaño (en tandas) · Separar hojas escaneadas de a dos · Reordenar, rotar y sacar páginas · **Firma digital PAdES** con certificado `.pfx`/`.p12` o **token USB** (PKCS#11, detecta la marca) · OCR · Pasar a Excel la tabla de un PDF · Comprimir, proteger y reparar |
| 🎵 **Audio** | Cortar · Unir · Mejorar un audio que se oye mal (ruido, voz baja) · **Transcribir** con Whisper, tramo por tramo y con quién habla |
| 🎬 **Video** | Partir sin pérdida · Ajustar a un tamaño máximo · Mapa del video (toda la grabación en una imagen) · Capturar el fotograma exacto · Mejorar el audio · Transcribir |
| 📊 **Tablas / Excel** | Unir varias planillas y partir el resultado |
| ✍️ **Escribir** | Redactar un texto y guardarlo como Word, PDF, ODT, HTML, EPUB, TXT o Markdown |
| 🔢 **Extraer hash** | SHA-256 y SHA-512 de cualquier archivo, y verificación de una huella recibida |

Cada operación deja un **informe técnico** con el hash de los originales y de los
resultados, listo para copiar y pegar. Los originales nunca se modifican.

<p align="center">
  <img src="docs/captura-pdf.png" width="800" alt="Módulo PDF">
</p>

## 🚀 Instalación desde el código

Requiere **Python 3.10 o superior** en Windows.

```bash
git clone https://github.com/<tu-usuario>/navaja.git
cd navaja
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Si falta alguna dependencia básica, el programa la instala sola al arrancar.

### Herramientas externas (opcionales)

Amplían lo que se puede hacer. Navaja las busca primero en una carpeta `bin/` al lado de
`main.py` (o del `.exe`) y después en el `PATH`.

| Herramienta | Qué habilita | Dónde va |
|---|---|---|
| [FFmpeg](https://ffmpeg.org) | Todo lo de audio y video | `bin/ffmpeg.exe`, `bin/ffprobe.exe` |
| [Pandoc](https://pandoc.org) | Markdown, RST, EPUB, LaTeX, ODT | `bin/pandoc.exe` |
| [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) | Reconocer el texto de un escaneo | `bin/tesseract/` (con `tessdata/`) |
| [LibreOffice](https://www.libreoffice.org) | Word, Excel, PowerPoint, Pages, Keynote | Instalado en el sistema |
| Microsoft Office | Alternativa a LibreOffice para formatos de Office | Instalado en el sistema |

### Transcripción (opcional)

La transcripción usa [Whisper](https://github.com/openai/whisper) y, para reconocer
quién habla, [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx). Son paquetes
pesados, por eso no vienen en `requirements.txt`:

```bash
pip install openai-whisper sherpa-onnx
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

Los modelos de Whisper (`base.pt`, `medium.pt`…) van en `models/whisper/`. Navaja no los
descarga solo, para respetar el funcionamiento sin internet.

## 📦 Armar el ejecutable

```bash
pip install pyinstaller
pyinstaller navaja.spec
```

Queda en `dist/Navaja/Navaja.exe`. Si existen las carpetas `bin/` y `models/`, se
incluyen en el paquete, y la carpeta entera se puede llevar en un pendrive.

## 🧪 Pruebas

```bash
python tests/test_imports.py
python tests/test_qa.py
python tests/test_compat.py
python tests/test_pdf_md.py
python tests/test_frames.py
python tests/test_gui_start.py
```

## 🗂️ Estructura

```
main.py              ← punto de entrada
core/                ← grafo de conversiones (BFS), rutas, configuración, hashes, informes
motors/              ← un motor por familia de formatos (imágenes, audio, video, PDF, OCR…)
ui/                  ← ventana principal y paneles PyQt6
pdf_excel/           ← preparador visual para pasar tablas de PDF a Excel
transcripcion/       ← Whisper, reproductor y escritor ODT
assets/              ← ícono y logo
tests/               ← pruebas
navaja.spec          ← empaquetado con PyInstaller
```

## 🔌 Agregar un motor de conversión

```python
# motors/mi_motor.py
from core.graph import BaseMotor

class MiMotor(BaseMotor):
    NAME = "MiMotor"
    CONVERSIONS = [("abc", "xyz"), ("xyz", "abc")]

    @classmethod
    def is_available(cls) -> bool:
        import shutil
        return shutil.which("mi-herramienta") is not None

    def convert(self, src_path, dst_path, src_ext, dst_ext, **kwargs):
        ...
```

Después se registra en `main.py` con `graph.register(MiMotor)`. El grafo lo suma a las
rutas posibles y la interfaz muestra los formatos nuevos sin tocar nada más.

## 📄 Licencia

Navaja se distribuye bajo la licencia **GNU GPL-3.0**: ver [LICENSE](LICENSE).

Usa, entre otros, PyQt6 (GPL-3.0), PyMuPDF (AGPL-3.0), pyHanko (MIT) y Whisper (MIT).
Las herramientas externas (FFmpeg, Pandoc, Tesseract, LibreOffice) tienen sus propias
licencias y no se incluyen en este repositorio.
