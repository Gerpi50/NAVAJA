"""test_qa.py — QA completo del Convertidor Universal."""
import sys, os, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# La consola de Windows (cp1252) no puede imprimir '→'; forzar UTF-8.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from PyQt6.QtWidgets import QApplication
app = QApplication.instance() or QApplication(sys.argv)

passed = []
failed = []

def ok(label): passed.append(label); print(f"  OK  {label}")
def fail(label, e): failed.append(label); print(f"  FAIL {label}: {e}")

print("=== 1. GRAPH EDGES ===")
from core.graph import graph
from motors.motor_images    import PillowMotor, CairoSVGMotor, PotraceMotor
from motors.motor_audio     import FFmpegAudioMotor
from motors.motor_video     import FFmpegVideoMotor
from motors.motor_documents import LibreOfficeDocMotor, PandocMotor, TxtToPdfMotor, EmailMotor, HtmlToPdfMotor, PdfExtractMotor
from motors.motor_data      import DataMotor
from motors.motor_ocr       import OcrMotor

for motor in [PillowMotor, CairoSVGMotor, PotraceMotor, FFmpegAudioMotor, FFmpegVideoMotor,
              LibreOfficeDocMotor, TxtToPdfMotor, PandocMotor, EmailMotor, HtmlToPdfMotor,
              PdfExtractMotor, DataMotor, OcrMotor]:
    graph.register(motor)

total_edges = len(graph._edges)
print(f"  Edges registered: {total_edges}")
if total_edges >= 50:
    ok(f"Graph has {total_edges} edges (>=50)")
else:
    fail(f"Graph edges", f"Only {total_edges} edges, need >=50")

print("\n=== 2. BFS PATH FINDING ===")
paths_to_check = [
    ("jpg", "png"), ("png", "pdf"), ("mp3", "wav"), ("mp4", "mp3"),
    ("docx", "pdf"), ("json", "csv"), ("txt", "pdf"),
]
for src, dst in paths_to_check:
    try:
        path = graph.find_path(src, dst)
        if path:
            ok(f"  {src}→{dst}: {' → '.join(path)}")
        else:
            fail(f"  {src}→{dst}", "No path found")
    except Exception as e:
        fail(f"  {src}→{dst}", e)

print("\n=== 3. HASHER ===")
try:
    from core.hasher import sha256, md5, file_info, build_certificate
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
        f.write(b"Hello, Universal Converter!")
        tpath = f.name
    h256 = sha256(tpath)
    hmd5 = md5(tpath)
    info = file_info(tpath)
    cert = build_certificate(info, info, "2026-03-27T00:00:00", True)
    assert len(h256) == 64, "sha256 length wrong"
    assert len(hmd5) == 32, "md5 length wrong"
    assert "sha256" in info
    assert "CONSTANCIA" in cert or "Constancia" in cert or "constancia" in cert.lower() or "Archivo" in cert
    ok("sha256 / md5 / file_info / build_certificate")
    os.unlink(tpath)
except Exception as e:
    fail("hasher", e)

print("\n=== 4. CONFIG MANAGER ===")
try:
    from core.config_manager import config
    config.load()
    old_theme = config.get("theme", "light")
    config.set("theme", "dark")
    assert config.get("theme") == "dark"
    config.set("theme", old_theme)
    ok("config get/set")
except Exception as e:
    fail("config_manager", e)

print("\n=== 5. LOGGER ===")
try:
    from core.logger import ConversionLogger
    logger = ConversionLogger()
    logger.start_session()
    from core.hasher import file_info as fi
    dummy = {"path": "test.jpg", "filename": "test.jpg", "size_bytes": 0,
             "size_human": "0 B", "sha256": "abc", "md5": "def", "modified": ""}
    logger.log_entry(
        status="ok",
        input_info=dummy,
        output_info=dummy,
        duration_seconds=0.1
    )
    cert = logger.get_certificate(0)
    assert cert is not None
    logger.finish_session()
    ok("ConversionLogger start/log/cert/finish")
except Exception as e:
    fail("logger", e)

print("\n=== 6. REAL IMAGE CONVERSION (JPG→PNG) ===")
try:
    from PIL import Image
    import io
    # Create a tiny test image
    img = Image.new("RGB", (10, 10), color=(255, 0, 0))
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as f:
        img.save(f, "JPEG")
        src = f.name
    dst = src.replace(".jpg", ".png")
    from core.runner import run_conversion
    run_conversion(src, dst, "png")
    assert os.path.isfile(dst) and os.path.getsize(dst) > 0
    ok("JPG → PNG conversion")
    os.unlink(src); os.unlink(dst)
except Exception as e:
    fail("JPG→PNG", e)

print("\n=== 7. REAL TEXT→PDF CONVERSION ===")
try:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="w") as f:
        f.write("Hola mundo desde el test de QA.")
        src = f.name
    dst = src.replace(".txt", ".pdf")
    from core.runner import run_conversion
    run_conversion(src, dst, "pdf")
    assert os.path.isfile(dst) and os.path.getsize(dst) > 0
    ok("TXT → PDF conversion")
    os.unlink(src); os.unlink(dst)
except Exception as e:
    fail("TXT→PDF", e)

print("\n=== 8. PDF STAMP ===")
try:
    from motors.motor_pdf_stamp import stamp_pdf_footer, stamp_pdf_watermark, stamp_pdf_page_numbers, apply_all_stamps
    ok("motor_pdf_stamp imports (footer, watermark, page_numbers, apply_all_stamps)")
except Exception as e:
    fail("motor_pdf_stamp", e)

print("\n=== 9. UI WIDGETS ===")
try:
    from ui.widgets import DropZone, FileCard, ThemeToggle, PanicButton, AppStatusBar
    from ui.widgets import AudioFilterPanel, SubtitlePanel, OcrPanel, WatermarkPanel, LegendPanel, PageNumberPanel, MetadataPanel
    ok("All UI widgets importable")
except Exception as e:
    fail("ui.widgets", e)

print("\n=== 10. MAIN WINDOW ===")
try:
    from ui.main_window import MainWindow
    w = MainWindow()
    assert w is not None
    ok("MainWindow instantiates")
    w.close()
except Exception as e:
    fail("MainWindow", e)

print("\n=== 11. THEME ===")
try:
    from ui.theme import ThemeManager, LIGHT, DARK
    ThemeManager.apply(app, "dark")
    ThemeManager.apply(app, "light")
    ok("ThemeManager light/dark")
except Exception as e:
    fail("theme", e)

print("\n=== 12. VIDEO SPLITTER MOTOR ===")
try:
    from motors.motor_video_splitter import split_video, estimate_parts, get_video_info
    ok("motor_video_splitter imports")
except Exception as e:
    fail("motor_video_splitter", e)

print("\n=== 13. OCR MOTOR ===")
try:
    from motors.motor_ocr import OcrMotor
    avail = OcrMotor.is_available()
    ok(f"OcrMotor.is_available() = {avail}")
except Exception as e:
    fail("motor_ocr", e)

print("\n=== 14. SELECTOR DE FORMATO (desplegable + escritura) ===")
try:
    from ui.format_grid import FormatGrid
    g = FormatGrid()
    elegidos = []
    g.format_selected.connect(elegidos.append)
    g.update_formats(["docx"], ["pdf", "txt", "md", "html"])

    assert g.search.count() == 4, f"el desplegable tiene {g.search.count()} items"
    ok(f"el desplegable lista los {g.search.count()} formatos disponibles")

    idx = [i for i in range(g.search.count()) if g.search.itemData(i) == "pdf"][0]
    g.search.activated.emit(idx)
    assert g.get_selected() == "pdf" and elegidos == ["pdf"]
    ok("elegir del desplegable selecciona el formato")

    g.search.lineEdit().setText("md")
    g.search.lineEdit().returnPressed.emit()
    assert g.get_selected() == "md"
    ok("escribir el formato y dar Enter también selecciona")

    g.search.lineEdit().textEdited.emit("pd")
    visibles = [f for f, b in g._buttons.items() if not b.isHidden()]
    assert visibles == ["pdf"], visibles
    ok("escribir filtra la grilla de botones")

    g._buttons["txt"].click()
    assert g.get_selected() == "txt" and "TXT" in g.search.currentText()
    ok("tocar un botón deja el formato escrito en el desplegable")

    g.clear_selection()
    assert g.get_selected() == "" and g.search.currentText() == ""
    ok("limpiar la selección vacía el desplegable")

    g.search.lineEdit().setText("mp3")
    g.search.lineEdit().returnPressed.emit()
    assert g.get_selected() == "", "no debe aceptar un formato no disponible"
    ok("un formato que no aplica a los archivos no se puede elegir")
except Exception as e:
    fail("selector de formato", e)

print("\n=== 15. CARTEL DE FORMATOS DE LA PANTALLA DE INICIO ===")
try:
    from ui.home_panel import _desc_convertir
    desc = _desc_convertir()
    assert "100+" not in desc, "sigue prometiendo 100+ formatos"
    ok(f"el cartel dice lo que hay: {desc.splitlines()[0]}")
except Exception as e:
    fail("cartel de formatos", e)

print("\n=== 16. ESCRIBIR (editor con vista previa y guardado) ===")
try:
    import tempfile
    from ui.editor_panel import (EditorPanel, _GuardarWorker,
                                 formatos_disponibles)

    carpeta = tempfile.mkdtemp(prefix="qa_escribir_")
    TEXTO = ("# Prompt de prueba\n\nActuá como un **ingeniero**. Necesito:\n\n"
             "- una cosa\n- otra cosa\n")

    panel = EditorPanel()
    panel.BORRADOR = os.path.join(carpeta, "borrador.md")
    panel.editor.setPlainText(TEXTO)
    panel._refrescar_preview()
    panel._actualizar_conteo()

    assert "Prompt de prueba" in panel.preview.toPlainText()
    ok("la vista previa muestra el Markdown con formato")

    assert "caracteres" in panel.lbl_conteo.text() and \
           "tokens" in panel.lbl_conteo.text()
    ok(f"contador de texto: {panel.lbl_conteo.text()}")

    panel._copiar()
    assert app.clipboard().text() == TEXTO
    ok("copiar al portapapeles deja el texto tal cual")

    disponibles = [e for e, _f, _n in formatos_disponibles()]
    assert "md" in disponibles and "txt" in disponibles
    ok(f"formatos ofrecidos en este equipo: {', '.join(disponibles)}")

    for ext in ("md", "txt"):
        destino = os.path.join(carpeta, f"prompt.{ext}")
        w = _GuardarWorker(TEXTO, destino)
        errores = []
        w.error.connect(errores.append)
        w.run()
        assert not errores, errores
        assert open(destino, encoding="utf-8").read() == TEXTO
    ok("guardar como .md y .txt escribe el texto tal cual")

    if "pdf" in disponibles:
        destino = os.path.join(carpeta, "prompt.pdf")
        w = _GuardarWorker(TEXTO, destino)
        errores = []
        w.error.connect(errores.append)
        w.run()
        assert not errores, errores
        assert os.path.getsize(destino) > 500
        ok("guardar como PDF genera el archivo")
    else:
        ok("PDF no disponible en este equipo (se saltea)")

    panel._guardar_borrador()
    otro = EditorPanel()
    otro.BORRADOR = panel.BORRADOR
    otro._cargar_borrador()
    assert "Prompt de prueba" in otro.editor.toPlainText()
    ok("el borrador se recupera al volver a abrir")

    from ui.main_window import MainWindow
    assert MainWindow.PAGE_EDITOR == 14
    ok("la página 'Escribir' está registrada en la ventana principal")
except Exception as e:
    fail("escribir", e)

print("\n=== 17. ESCRIBIR EN TEXTO COMÚN (sin saber Markdown) ===")
try:
    from core.texto_natural import a_markdown
    from ui.editor_panel import EditorPanel, MODO_COMUN, MODO_MARKDOWN

    NATURAL = ("SOLICITA ALLANAMIENTO\n\n"
               "I.- OBJETO:\n\n"
               "Que se ha establecido que en el domicilio de calle 47\n"
               "funcionaría un punto de venta.\n"
               "Se acompañan las tareas realizadas.\n\n"
               "a) El registro del inmueble.\n"
               "b) El secuestro de los elementos.\n\n"
               "- teléfonos celulares\n"
               "- documentación\n")

    md = a_markdown(NATURAL)
    assert md.startswith("# SOLICITA ALLANAMIENTO")
    ok("un renglón en MAYÚSCULAS se convierte en título")
    assert "## I.- OBJETO:" in md
    ok("la numeración romana queda como sección")
    assert "### a) El registro del inmueble." in md
    ok("los incisos a) b) quedan destacados")
    assert "- teléfonos celulares" in md
    ok("los guiones arman una lista")
    assert "calle 47 funcionaría un punto de venta." in md
    ok("el renglón cortado sin punto se une con el que sigue")
    assert "Se acompañan las tareas" in md
    ok("después del punto, arranca renglón nuevo")

    panel = EditorPanel()
    panel.BORRADOR = os.path.join(tempfile.mkdtemp(), "b.md")
    panel.editor.setPlainText(NATURAL)
    assert panel.combo_modo.currentData() == MODO_COMUN
    ok("el panel arranca en modo texto común")
    assert panel._markdown_actual().startswith("# SOLICITA")
    panel.combo_modo.setCurrentIndex(1)
    assert panel.combo_modo.currentData() == MODO_MARKDOWN
    assert panel._markdown_actual() == NATURAL
    ok("en modo Markdown el texto va tal cual, sin interpretar")

    panel.combo_modo.setCurrentIndex(0)
    panel._refrescar_preview()
    vista = panel.preview.toPlainText()
    assert "SOLICITA ALLANAMIENTO" in vista and "##" not in vista
    ok("la vista previa muestra el formato, no los signos")

    panel._actualizar_leyenda()
    assert "MAYÚSCULAS" in panel.lbl_leyenda.text()
    ok("la leyenda explica las reglas de escritura")

    # Escribir normal, ver el Markdown, copiarlo y no guardar nada
    from ui.editor_panel import VISTA_MARKDOWN
    panel.combo_vista.setCurrentIndex(1)
    assert panel.combo_vista.currentData() == VISTA_MARKDOWN
    en_pantalla = panel.preview.toPlainText()
    assert en_pantalla.startswith("# SOLICITA ALLANAMIENTO")
    ok("la vista «Markdown» muestra el código que armó el programa")

    panel._copiar_markdown()
    assert app.clipboard().text() == en_pantalla == panel._markdown_actual()
    ok("«Copiar en Markdown» deja el Markdown en el portapapeles")

    panel._copiar()
    assert app.clipboard().text() == NATURAL
    ok("«Copiar texto» sigue copiando lo escrito tal cual")
except Exception as e:
    fail("texto común", e)

print("\n=== 18. TODOS LOS MÓDULOS COMPILAN Y LAS PANTALLAS ABREN ===")
# Un error de tipeo en un panel no rompe el arranque: la ventana principal lo
# atrapa y muestra "no disponible" en esa sección. Cómodo para el usuario,
# pero significa que un archivo roto se puede empaquetar sin que nadie lo
# note. Esto lo caza antes.
try:
    import ast
    import io as _io
    import pathlib

    rotos = []
    for carpeta in ("core", "motors", "ui"):
        for archivo in sorted(pathlib.Path(carpeta).glob("*.py")):
            try:
                ast.parse(_io.open(archivo, encoding="utf-8").read())
            except SyntaxError as e:
                rotos.append(f"{archivo}:{e.lineno} {e.msg}")
    assert not rotos, "archivos con error de sintaxis: " + "; ".join(rotos)
    ok("todos los módulos de core/, motors/ y ui/ compilan")
except Exception as e:
    fail("compilación de los módulos", e)

try:
    from ui.video_module_panel import VideoModulePanel
    from ui.audio_module_panel import AudioModulePanel

    modulo_video = VideoModulePanel()
    solapas = [modulo_video.tabs.tabText(i)
               for i in range(modulo_video.tabs.count())]
    assert len(solapas) == 6, f"solapas del módulo Video: {solapas}"
    for esperada in ("Mejorar audio", "Transcribir"):
        assert any(esperada in s for s in solapas), \
            f"falta la solapa {esperada}: {solapas}"
    assert modulo_video.mapa is not None and modulo_video.captura is not None, \
        "el mapa o la captura no cargaron"
    ok(f"el módulo Video abre sus {len(solapas)} solapas")

    AudioModulePanel()
    ok("el módulo Audio abre")
except Exception as e:
    fail("apertura de los módulos", e)

print("\n=== 19. EL MENÚ LLEVA A DONDE DICE ===")
# La lista "¿Qué necesitás hacer?" promete llevar a la pantalla exacta. Si
# alguien renombra una solapa, la promesa se rompe en silencio: el usuario
# toca y aterriza en otro lado. Esto lo verifica renglón por renglón.
try:
    from PyQt6.QtWidgets import QTabWidget
    from ui.main_window import MainWindow
    from ui.home_panel import TAREAS, HomePanel

    ventana = MainWindow()
    problemas = []
    for _problema, destino, page, solapa in TAREAS:
        if not (0 <= page < ventana._stack.count()):
            problemas.append(f"{destino}: la página {page} no existe")
            continue
        ventana._nav_to(page, solapa)
        if ventana._stack.currentIndex() != page:
            problemas.append(f"{destino}: no llegó a la página {page}")
        elif solapa:
            pagina = ventana._stack.widget(page)
            tabs = (pagina if isinstance(pagina, QTabWidget)
                    else pagina.findChild(QTabWidget))
            if tabs is None:
                problemas.append(f"{destino}: esa pantalla no tiene solapas")
            elif solapa.lower() not in tabs.tabText(tabs.currentIndex()).lower():
                problemas.append(
                    f"{destino}: abrió «{tabs.tabText(tabs.currentIndex()).strip()}»")
    assert not problemas, "; ".join(problemas)
    ok(f"los {len(TAREAS)} renglones de «¿Qué necesitás hacer?» abren la solapa correcta")

    inicio = ventana._stack.widget(ventana.PAGE_HOME)
    home = inicio if hasattr(inicio, "_tarea_rows") else inicio.findChild(HomePanel)
    filas = home._tarea_rows
    assert len(filas) == len(TAREAS)

    home._filtrar_tareas("firmar")
    assert sum(1 for f in filas if f.isVisibleTo(home)) == 1
    home._filtrar_tareas("qwerty")
    assert sum(1 for f in filas if f.isVisibleTo(home)) == 0
    assert home._sin_resultados.isVisibleTo(home), \
        "sin resultados no avisa nada"
    home._filtrar_tareas("")
    assert sum(1 for f in filas if f.isVisibleTo(home)) == len(TAREAS)
    ok("el buscador de inicio filtra la lista y avisa cuando no encuentra nada")

    sin_ayuda = [b.text() for _, b in ventana._nav_buttons
                 if len(b.toolTip().strip()) < 25]
    assert not sin_ayuda, f"botones sin explicación: {sin_ayuda}"
    ok("todos los botones del menú explican para qué sirven")
except Exception as e:
    fail("el menú lleva a donde dice", e)

print("\n=== 20. TEXTO VERTICAL AL PASAR PDF A DOCX/ODT ===")
try:
    import fitz
    from motors.motor_documents import PdfToDocxMotor

    SELLO = "Anexo - Resolución S.P.C. N° 2/26"
    doc = fitz.open()
    pagina = doc.new_page()
    pagina.insert_text((60, 120), "Texto normal de la hoja", fontsize=11)
    # rotate=90: el sello que corre por el margen, como en algunos anexos escaneados
    pagina.insert_textbox(fitz.Rect(20, 60, 40, 700), SELLO,
                          fontsize=9, rotate=90)
    tmp_pdf = os.path.join(tempfile.gettempdir(), "qa_vertical.pdf")
    doc.save(tmp_pdf)
    doc.close()

    def rotados(ruta):
        d = fitz.open(ruta)
        try:
            return [
                "".join(s["text"] for s in ln["spans"]).strip()
                for pg in d
                for blk in pg.get_text("dict")["blocks"] if blk.get("type") == 0
                for ln in blk["lines"] if PdfToDocxMotor._es_rotado(ln.get("dir", (1, 0)))
            ]
        finally:
            d.close()

    assert rotados(tmp_pdf), "el PDF de prueba no quedó con texto rotado"
    ok("se detecta el texto vertical del margen")

    avisos = []
    limpio, es_temporal = PdfToDocxMotor._sin_texto_rotado(
        tmp_pdf, progress_cb=avisos.append)
    try:
        assert es_temporal and limpio != tmp_pdf, "no se armó una copia aparte"
        assert not rotados(limpio), "el texto vertical siguió estando"
        ok("el texto vertical se omite y el original no se toca")

        d = fitz.open(limpio)
        plano = "".join(pg.get_text() for pg in d)
        d.close()
        assert "Texto normal de la hoja" in plano, "se llevó puesto el texto derecho"
        ok("el resto de la hoja queda intacto")
    finally:
        if es_temporal:
            os.unlink(limpio)

    assert avisos and any(a.startswith("⚠") for a in avisos), "no avisó nada"
    assert any(SELLO[:20] in a for a in avisos), \
        f"el aviso no dice qué se omitió: {avisos}"
    ok("avisa qué texto omitió")

    sin_rotar = os.path.join(tempfile.gettempdir(), "qa_sin_vertical.pdf")
    d = fitz.open()
    d.new_page().insert_text((60, 120), "Todo derecho", fontsize=11)
    d.save(sin_rotar)
    d.close()
    callados = []
    ruta, temporal = PdfToDocxMotor._sin_texto_rotado(
        sin_rotar, progress_cb=callados.append)
    assert ruta == sin_rotar and not temporal, "copió un PDF que no hacía falta copiar"
    assert not callados, f"avisó de más: {callados}"
    ok("si no hay texto vertical no avisa ni copia nada")
    os.unlink(sin_rotar)
    os.unlink(tmp_pdf)
except Exception as e:
    fail("texto vertical al pasar PDF a DOCX/ODT", e)

print("\n=== 21. VOLVER A ELEGIR FORMATO DESPUÉS DE CONVERTIR ===")
try:
    import fitz
    from ui.main_window import MainWindow

    pdf_a = os.path.join(tempfile.gettempdir(), "qa_cola_a.pdf")
    pdf_b = os.path.join(tempfile.gettempdir(), "qa_cola_b.pdf")
    for _p in (pdf_a, pdf_b):
        _d = fitz.open()
        _d.new_page().insert_text((60, 100), "hoja de prueba")
        _d.save(_p)
        _d.close()

    def _ventana():
        v = MainWindow()
        v.resize(1200, 800)
        v.show()
        v._stack.setCurrentIndex(v.PAGE_CONVERTER)
        for _ in range(5):
            app.processEvents()
        return v

    def _alto(v):
        for _ in range(5):
            app.processEvents()
        return v.format_grid.height()

    def _simular_conversion(v):
        v.lbl_result.setText("✅ 1 convertido")
        v.lbl_result.setVisible(True)
        v.informe_section.set_informe("INFORME\n" + "renglón\n" * 25, "")

    ventana = _ventana()
    ventana._add_files_list([pdf_a])
    alto_limpio = _alto(ventana)
    assert alto_limpio > 200, f"la grilla arranca chica: {alto_limpio}px"
    _simular_conversion(ventana)
    assert ventana.informe_section.isVisible(), "el informe no se mostró"
    assert _alto(ventana) < alto_limpio, "el informe no estaba ocupando lugar"
    ventana.close()
    ok("al terminar, el informe se muestra y achica la grilla")

    # Las tres formas de arrancar una tanda nueva tienen que devolver el lugar.
    # Contra qué se compara depende de cómo queda la cola: la carpeta de
    # destino que se muestra arriba de la grilla ocupa dos renglones cuando
    # la ruta es larga y uno solo cuando la cola está vacía, así que con la
    # cola vacía la pantalla tiene que quedar igual que recién abierta, y
    # con un archivo, igual que antes de convertir.
    caminos = {
        "el botón «Limpiar todo»":      (lambda v: v._do_panic(), True),
        "arrastrar otro archivo":       (lambda v: v._add_files_list([pdf_b]), False),
        "sacar el archivo de la cola":  (lambda v: v._remove_file(pdf_a), True),
    }
    for nombre, (accion, queda_vacia) in caminos.items():
        v = _ventana()
        recien_abierta = _alto(v)
        v._add_files_list([pdf_a])
        con_archivo = _alto(v)
        _simular_conversion(v)
        accion(v)
        recuperado = _alto(v)
        visible = v.informe_section.isVisible()
        v.close()
        esperado = recien_abierta if queda_vacia else con_archivo
        assert not visible, f"{nombre}: el informe quedó prendido"
        assert recuperado == esperado, \
            f"{nombre}: la grilla quedó en {recuperado}px en vez de {esperado}px"
    ok(f"las {len(caminos)} formas de empezar de nuevo devuelven el alto de la grilla")

    os.unlink(pdf_a)
    os.unlink(pdf_b)
except Exception as e:
    fail("volver a elegir formato después de convertir", e)

print("\n" + "="*50)
print(f"TOTAL: {len(passed)+len(failed)} tests")
print(f"  PASSED: {len(passed)}")
print(f"  FAILED: {len(failed)}")
if failed:
    print("\nFailed tests:")
    for f in failed:
        print(f"  - {f}")
sys.exit(0 if not failed else 1)
