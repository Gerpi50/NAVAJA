"""
motors/motor_pdf_stamp.py — Post-procesador de PDF: leyenda, marca de agua, numeración.
"""
import os
import shutil
import tempfile


def _hex_to_rgb(h: str):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) / 255 for i in (0, 2, 4))


def stamp_pdf_footer(
    src_path: str, dst_path: str,
    legend: str, font_size: int = 9,
    color_hex: str = "#888888", opacity: float = 0.7,
) -> None:
    """Leyenda centrada al pie de cada página."""
    from reportlab.pdfgen import canvas as rl_canvas
    from pypdf import PdfReader, PdfWriter

    r, g, b = _hex_to_rgb(color_hex)
    reader = PdfReader(src_path)
    writer = PdfWriter()

    for page in reader.pages:
        pw = float(page.mediabox.width)
        ph = float(page.mediabox.height)
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name
        c = rl_canvas.Canvas(tmp_path, pagesize=(pw, ph))
        c.setFillColorRGB(r, g, b, alpha=opacity)
        c.setFont("Helvetica", font_size)
        tw = c.stringWidth(legend, "Helvetica", font_size)
        c.drawString((pw - tw) / 2, 14, legend)
        c.save()
        page.merge_page(PdfReader(tmp_path).pages[0])
        writer.add_page(page)
        os.unlink(tmp_path)

    with open(dst_path, "wb") as f:
        writer.write(f)


def stamp_pdf_watermark(
    src_path: str, dst_path: str,
    text: str, font_size: int = 60,
    color_hex: str = "#cccccc", opacity: float = 0.25,
    angle: float = 45.0,
) -> None:
    """Marca de agua diagonal semitransparente."""
    from reportlab.pdfgen import canvas as rl_canvas
    from pypdf import PdfReader, PdfWriter

    r, g, b = _hex_to_rgb(color_hex)
    reader = PdfReader(src_path)
    writer = PdfWriter()

    for page in reader.pages:
        pw = float(page.mediabox.width)
        ph = float(page.mediabox.height)
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name
        c = rl_canvas.Canvas(tmp_path, pagesize=(pw, ph))
        c.setFillColorRGB(r, g, b, alpha=opacity)
        c.setFont("Helvetica-Bold", font_size)
        c.saveState()
        c.translate(pw / 2, ph / 2)
        c.rotate(angle)
        tw = c.stringWidth(text, "Helvetica-Bold", font_size)
        c.drawString(-tw / 2, 0, text)
        c.restoreState()
        c.save()
        page.merge_page(PdfReader(tmp_path).pages[0])
        writer.add_page(page)
        os.unlink(tmp_path)

    with open(dst_path, "wb") as f:
        writer.write(f)


def stamp_pdf_page_numbers(
    src_path: str, dst_path: str,
    position: str = "bottom-center",
    font_size: int = 9,
    color_hex: str = "#333333",
    format_str: str = "Página {n} de {total}",
    start_from: int = 1,
) -> None:
    """Numeración de páginas configurable."""
    from reportlab.pdfgen import canvas as rl_canvas
    from pypdf import PdfReader, PdfWriter

    r, g, b = _hex_to_rgb(color_hex)
    reader = PdfReader(src_path)
    writer = PdfWriter()
    total  = len(reader.pages)
    margin = 18

    for i, page in enumerate(reader.pages):
        pw  = float(page.mediabox.width)
        ph  = float(page.mediabox.height)
        n   = i + start_from
        text = format_str.replace("{n}", str(n)).replace("{total}", str(total))

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name

        c = rl_canvas.Canvas(tmp_path, pagesize=(pw, ph))
        c.setFillColorRGB(r, g, b)
        c.setFont("Helvetica", font_size)
        tw = c.stringWidth(text, "Helvetica", font_size)

        y = margin if "bottom" in position else (ph - margin - font_size)
        if "center" in position:
            x = (pw - tw) / 2
        elif "right" in position:
            x = pw - tw - margin
        else:
            x = margin

        c.drawString(x, y, text)
        c.save()
        page.merge_page(PdfReader(tmp_path).pages[0])
        writer.add_page(page)
        os.unlink(tmp_path)

    with open(dst_path, "wb") as f:
        writer.write(f)


def apply_all_stamps(src_path: str, dst_path: str, options: dict) -> None:
    """
    Aplica sellos en orden: marca de agua → leyenda → numeración.
    options = {
        "watermark":    {text, font_size, color, opacity, angle},
        "footer":       {text, font_size, color, opacity},
        "page_numbers": {enabled, position, font_size, color, format, start_from}
    }
    """
    try:
        from core.paths import TEMP_DIR
    except Exception:
        TEMP_DIR = None

    current = src_path
    temps   = []

    def _make_temp():
        kw = {"suffix": ".pdf", "delete": False}
        if TEMP_DIR:
            kw["dir"] = TEMP_DIR
        t = tempfile.NamedTemporaryFile(**kw)
        t.close()
        temps.append(t.name)
        return t.name

    try:
        # 1. Marca de agua
        wm = options.get("watermark", {})
        if wm.get("text"):
            nxt = _make_temp()
            stamp_pdf_watermark(current, nxt,
                text=wm["text"],
                font_size=int(wm.get("font_size", 60)),
                color_hex=wm.get("color", "#cccccc"),
                opacity=float(wm.get("opacity", 0.25)),
                angle=float(wm.get("angle", 45)),
            )
            current = nxt

        # 2. Leyenda al pie
        ft = options.get("footer", {})
        if ft.get("text"):
            nxt = _make_temp()
            stamp_pdf_footer(current, nxt,
                legend=ft["text"],
                font_size=int(ft.get("font_size", 9)),
                color_hex=ft.get("color", "#888888"),
                opacity=float(ft.get("opacity", 0.7)),
            )
            current = nxt

        # 3. Numeración de páginas
        pn = options.get("page_numbers", {})
        if pn.get("enabled") or pn.get("format"):
            nxt = _make_temp()
            stamp_pdf_page_numbers(current, nxt,
                position=pn.get("position", "bottom-center"),
                font_size=int(pn.get("font_size", 9)),
                color_hex=pn.get("color", "#333333"),
                format_str=pn.get("format", "Página {n} de {total}"),
                start_from=int(pn.get("start_from", 1)),
            )
            current = nxt

        # Copiar resultado
        if current != dst_path:
            shutil.copy2(current, dst_path)

    finally:
        for t in temps:
            if t != dst_path:
                try:
                    os.unlink(t)
                except Exception:
                    pass
