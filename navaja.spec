# navaja.spec — PyInstaller spec para Navaja (onedir)
#
# Genera:  dist/Navaja/Navaja.exe      ← el ejecutable
#          dist/Navaja/_internal/...   ← el resto, en carpeta
#
# Uso (desde un venv con requirements.txt instalado):
#   pip install pyinstaller
#   pyinstaller navaja.spec
#
# Las herramientas externas (ffmpeg, ffprobe, pandoc, tesseract) se buscan en
# la carpeta bin/ junto al exe. No están en el repositorio: ver README.

import importlib.util
import os

from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

block_cipher = None


def _instalado(modulo: str) -> bool:
    return importlib.util.find_spec(modulo) is not None


datos_extra, binarios_extra, modulos_extra = [], [], []

# Transcripción (Whisper), opcional: sus tablas de tokens y el banco de
# filtros mel son archivos de datos; sin ellos arranca pero falla al
# transcribir.
if _instalado('whisper'):
    datos_extra += collect_data_files('whisper', includes=['assets/*'])
    modulos_extra += collect_submodules('whisper')
    modulos_extra += ['tiktoken_ext', 'tiktoken_ext.openai_public']

# Reconocer quién habla (sherpa-onnx), opcional: trae sus propias DLL.
if _instalado('sherpa_onnx'):
    d, b, m = collect_all('sherpa_onnx')
    datos_extra += d
    binarios_extra += b
    modulos_extra += m

datas = [('assets', 'assets')]
if os.path.isdir('bin'):
    datas.append(('bin', 'bin'))      # ffmpeg, ffprobe, pandoc, tesseract
if os.path.isdir('models'):
    datas.append(('models', 'models'))  # modelos de Whisper y de voces

a = Analysis(
    ['main.py'],
    pathex=[os.path.abspath('.')],
    binaries=binarios_extra,
    datas=datas + datos_extra,
    hiddenimports=modulos_extra + [
        'PyQt6.QtMultimedia',   # escuchar los audios al revisar
        'PyQt6.QtSvg',
        'comtypes.stream',
        'PIL._imaging',
        'fitz',
        'pdfplumber', 'pdfminer', 'pypdfium2',
        'openpyxl', 'xlrd', 'docx', 'pptx', 'extract_msg',
        'markdown', 'markdownify', 'docutils', 'chardet',
        'yaml', 'toml', 'pandas', 'pyarrow', 'lxml',
        'qtawesome', 'pdf2docx', 'py7zr', 'rarfile', 'rawpy',
        'brotli', 'mobi', 'fontTools',
        'pyhanko', 'pyhanko_certvalidator', 'pkcs11', 'asn1crypto',
        'pytesseract',
    ] + collect_submodules('core')
      + collect_submodules('motors')
      + collect_submodules('ui')
      + collect_submodules('pdf_excel')
      + collect_submodules('transcripcion'),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Red de seguridad por si se compila desde un entorno con más paquetes:
    # nada de esto es necesario para la app.
    excludes=[
        'tensorflow', 'keras', 'sklearn', 'scipy', 'matplotlib',
        'cv2', 'selenium', 'playwright', 'notebook', 'jupyter', 'IPython',
        'flask', 'librosa',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,      # onedir: el exe va separado del resto
    name='Navaja',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,              # sin consola (windowed)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icono.ico',
    version_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='Navaja',
)
