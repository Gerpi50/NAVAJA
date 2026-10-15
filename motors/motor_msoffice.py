"""
motors/motor_msoffice.py — Conversión usando Microsoft Office via COM automation.
Usa Word, Excel y PowerPoint instalados en Windows (si están disponibles).
Requiere: pip install pywin32
"""
import os
import tempfile
from core.graph import BaseMotor


# ── Detección de aplicaciones Office disponibles ──────────────────────
# Antes esto abría Word/Excel/PowerPoint por COM y les daba Quit() para ver si
# estaban instalados. El problema: Dispatch() se engancha a la copia que YA
# esté abierta, así que arrancar el conversor podía cerrarle el Word al
# usuario con el documento a medio escribir. Ahora se mira el registro de
# Windows, que dice lo mismo sin tocar nada.

def _com_registrado(prog_id: str) -> bool:
    """True si el ProgID (p. ej. "Word.Application") figura en el registro."""
    try:
        import winreg
    except ImportError:
        return False
    try:
        import win32com.client  # noqa: F401  (pywin32 hace falta para usarlo)
    except ImportError:
        return False
    for vista in (getattr(winreg, "KEY_WOW64_64KEY", 0),
                  getattr(winreg, "KEY_WOW64_32KEY", 0)):
        try:
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT,
                                prog_id + r"\CLSID", 0,
                                winreg.KEY_READ | vista):
                return True
        except OSError:
            continue
    return False


def _check_com(prog_id: str) -> bool:
    """Compatibilidad: nombre viejo de _com_registrado()."""
    return _com_registrado(prog_id)


def _word_available() -> bool:
    return _com_registrado("Word.Application")


def _excel_available() -> bool:
    return _com_registrado("Excel.Application")


def _powerpoint_available() -> bool:
    return _com_registrado("PowerPoint.Application")


# Caché para no repetir la consulta en cada chequeo
_word_ok = None
_excel_ok = None
_ppt_ok = None


def _has_word() -> bool:
    global _word_ok
    if _word_ok is None:
        _word_ok = _word_available()
    return _word_ok


def _has_excel() -> bool:
    global _excel_ok
    if _excel_ok is None:
        _excel_ok = _excel_available()
    return _excel_ok


def _has_powerpoint() -> bool:
    global _ppt_ok
    if _ppt_ok is None:
        _ppt_ok = _powerpoint_available()
    return _ppt_ok


# ── Constantes WdSaveFormat (Word) ───────────────────────────────────────────
WD_FORMAT = {
    "pdf":  17,   # wdFormatPDF
    "docx": 12,   # wdFormatXMLDocument
    "doc":  0,    # wdFormatDocument
    "odt":  23,   # wdFormatOpenDocumentText
    "rtf":  6,    # wdFormatRTF
    "txt":  2,    # wdFormatText
    "html": 8,    # wdFormatHTML
}

# ── Constantes XlFileFormat (Excel) ──────────────────────────────────────────
XL_FORMAT = {
    "xlsx": 51,    # xlOpenXMLWorkbook
    "xls":  -4143, # xlWorkbookNormal
    "csv":  6,     # xlCSV
    "ods":  60,    # xlOpenDocumentSpreadsheet
    "html": 44,    # xlHtml
    "pdf":  0,     # xlTypePDF (usado con ExportAsFixedFormat)
}

# ── Constantes PpSaveAsFileType (PowerPoint) ─────────────────────────────────
PP_FORMAT = {
    "pptx": 24,    # ppSaveAsOpenXMLPresentation
    "ppt":  1,     # ppSaveAsPresentation
    "odp":  35,    # ppSaveAsOpenDocumentPresentation
    "pdf":  32,    # ppSaveAsPDF
    "png":  19,    # ppSaveAsPNG
    "jpg":  17,    # ppSaveAsJPEG
}


# ── Motor Word ────────────────────────────────────────────────────────────────

class MSWordMotor(BaseMotor):
    NAME = "Microsoft Word"
    CONVERSIONS = [
        # → PDF
        ("docx","pdf"), ("doc","pdf"), ("odt","pdf"), ("rtf","pdf"),
        ("txt","pdf"),  ("html","pdf"),
        # → DOCX
        ("doc","docx"), ("odt","docx"), ("rtf","docx"), ("txt","docx"),
        ("html","docx"),
        # → ODT
        ("docx","odt"), ("doc","odt"),  ("rtf","odt"),
        # → RTF
        ("docx","rtf"), ("doc","rtf"),
        # → TXT
        ("docx","txt"), ("doc","txt"),  ("odt","txt"), ("rtf","txt"),
        # → HTML
        ("docx","html"),("doc","html"), ("odt","html"),
    ]

    @classmethod
    def is_available(cls) -> bool:
        try:
            import win32com.client  # noqa
            return _has_word()
        except ImportError:
            return False

    def convert(self, src_path, dst_path, src_ext, dst_ext, **kwargs):
        import win32com.client
        import pythoncom
        pythoncom.CoInitialize()

        src_abs = os.path.abspath(src_path)
        dst_abs = os.path.abspath(dst_path)

        # DispatchEx abre una copia propia y aparte: si el usuario tiene
        # Word abierto no se lo tocamos, y no falla al pedirle que se
        # esconda ("Property Word.Application.Visible can not be set").
        word = win32com.client.DispatchEx("Word.Application")
        try:
            word.Visible = False
        except Exception:
            pass
        doc = None
        try:
            doc = word.Documents.Open(src_abs, ReadOnly=True)
            if dst_ext == "pdf":
                doc.ExportAsFixedFormat(
                    OutputFileName=dst_abs,
                    ExportFormat=17,   # wdExportFormatPDF
                    OpenAfterExport=False,
                )
            else:
                fmt = WD_FORMAT.get(dst_ext)
                if fmt is None:
                    raise RuntimeError(f"Formato destino no soportado por Word: {dst_ext}")
                doc.SaveAs2(dst_abs, FileFormat=fmt)
        finally:
            if doc:
                doc.Close(SaveChanges=False)
            word.Quit()


# ── Motor Excel ───────────────────────────────────────────────────────────────

class MSExcelMotor(BaseMotor):
    NAME = "Microsoft Excel"
    CONVERSIONS = [
        ("xlsx","pdf"), ("xls","pdf"),  ("ods","pdf"),  ("csv","pdf"),
        ("xlsx","xls"), ("xls","xlsx"),
        ("xlsx","ods"), ("xls","ods"),  ("ods","xlsx"),
        ("xlsx","csv"), ("xls","csv"),  ("ods","csv"),
        ("csv","xlsx"), ("csv","xls"),
        # XLSX/XLS → HTML lo hace LibreOffice: Excel exporta un HTML con
        # marcos (<frame>) y una carpeta de archivos al lado, así que al
        # pasarlo a MD quedaba una sola línea: "Esta página utiliza marcos
        # que su explorador no admite".
    ]

    @classmethod
    def is_available(cls) -> bool:
        try:
            import win32com.client  # noqa
            return _has_excel()
        except ImportError:
            return False

    def convert(self, src_path, dst_path, src_ext, dst_ext, **kwargs):
        import win32com.client
        import pythoncom
        pythoncom.CoInitialize()

        src_abs = os.path.abspath(src_path)
        dst_abs = os.path.abspath(dst_path)

        excel = win32com.client.DispatchEx("Excel.Application")
        try:
            excel.Visible = False
            excel.DisplayAlerts = False
        except Exception:
            pass
        wb = None
        try:
            wb = excel.Workbooks.Open(src_abs, ReadOnly=True)
            if dst_ext == "pdf":
                wb.ExportAsFixedFormat(
                    Type=0,              # xlTypePDF
                    Filename=dst_abs,
                    Quality=0,           # xlQualityStandard
                    IncludeDocProperties=True,
                    IgnorePrintAreas=False,
                    OpenAfterPublish=False,
                )
            else:
                fmt = XL_FORMAT.get(dst_ext)
                if fmt is None:
                    raise RuntimeError(f"Formato destino no soportado por Excel: {dst_ext}")
                wb.SaveAs(dst_abs, FileFormat=fmt)
        finally:
            if wb:
                wb.Close(SaveChanges=False)
            excel.Quit()


# ── Motor PowerPoint ──────────────────────────────────────────────────────────

class MSPowerPointMotor(BaseMotor):
    NAME = "Microsoft PowerPoint"
    CONVERSIONS = [
        ("pptx","pdf"), ("ppt","pdf"),  ("odp","pdf"),
        ("pptx","ppt"), ("ppt","pptx"),
        ("pptx","odp"), ("ppt","odp"),
        ("pptx","png"), ("ppt","png"),
        ("pptx","jpg"), ("ppt","jpg"),
    ]

    @classmethod
    def is_available(cls) -> bool:
        try:
            import win32com.client  # noqa
            return _has_powerpoint()
        except ImportError:
            return False

    def convert(self, src_path, dst_path, src_ext, dst_ext, **kwargs):
        import win32com.client
        import pythoncom
        pythoncom.CoInitialize()

        src_abs = os.path.abspath(src_path)
        dst_abs = os.path.abspath(dst_path)

        ppt = win32com.client.DispatchEx("PowerPoint.Application")
        prs = None
        try:
            # WithWindow=False requiere que la app no sea visible
            prs = ppt.Presentations.Open(src_abs, WithWindow=False)

            if dst_ext in ("png", "jpg"):
                # Exportar cada diapositiva como imagen
                # PowerPoint exporta a una carpeta; manejar resultado
                out_dir  = os.path.dirname(dst_abs)
                stem     = os.path.splitext(os.path.basename(dst_abs))[0]
                img_type = "PNG" if dst_ext == "png" else "JPG"
                prs.Export(dst_abs, img_type)
                # Si generó múltiples archivos en carpeta, renombrar el primero
                candidate_dir = os.path.join(out_dir, stem)
                if os.path.isdir(candidate_dir):
                    imgs = sorted(os.listdir(candidate_dir))
                    if imgs:
                        first = os.path.join(candidate_dir, imgs[0])
                        import shutil
                        shutil.move(first, dst_abs)
            else:
                fmt = PP_FORMAT.get(dst_ext)
                if fmt is None:
                    raise RuntimeError(f"Formato destino no soportado por PowerPoint: {dst_ext}")
                prs.SaveAs(dst_abs, fmt)
        finally:
            if prs:
                prs.Close()
            ppt.Quit()
