"""test_frames.py — Pruebas de la captura de fotogramas (motor + panel).

Se arma solo los videos de prueba con FFmpeg, así que no depende de tener
ningún archivo a mano. Se corre igual que los demás:

    venv_build\\Scripts\\python.exe test_frames.py
"""
import hashlib
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from core.paths import TEMP_DIR
from motors import motor_video_frames as mvf

BANCO = os.path.join(TEMP_DIR, "pruebas_fotogramas")
CAMARA = os.path.join(BANCO, "camara.mp4")          # cuadro clave cada 2 s
DVR = os.path.join(BANCO, "dvr_gop_largo.mp4")      # cuadro clave cada 10 s
DESFASADO = os.path.join(BANCO, "desfasado.mp4")    # el video arranca en 0,5 s
SALIDA = os.path.join(BANCO, "salida")

pasaron = []
fallaron = []


def probar(etiqueta, condicion, detalle=""):
    if condicion:
        pasaron.append(etiqueta)
        print(f"  OK   {etiqueta}" + (f"   {detalle}" if detalle else ""))
    else:
        fallaron.append(etiqueta)
        print(f"  FALLA {etiqueta}   {detalle}")


def sha(ruta):
    with open(ruta, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def preparar_banco():
    """Genera los videos de prueba: uno normal, uno tipo DVR y uno desfasado."""
    shutil.rmtree(BANCO, ignore_errors=True)
    os.makedirs(SALIDA, exist_ok=True)
    sin_ventana = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    for destino, duracion, gop in ((CAMARA, 10, 50), (DVR, 30, 250)):
        subprocess.run([
            mvf.FFMPEG, "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i",
            f"testsrc=size=640x480:rate=25:duration={duracion}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-g", str(gop),
            "-y", destino,
        ], check=True, creationflags=sin_ventana)
    # Muchas cámaras y celulares declaran que el video empieza medio segundo
    # después del cero del archivo. Antes eso se colaba en los tiempos que se
    # informaban (el fotograma del minuto 1:20 figuraba como 1:20.042).
    subprocess.run([
        mvf.FFMPEG, "-hide_banner", "-loglevel", "error", "-i", CAMARA,
        "-c", "copy", "-output_ts_offset", "0.5", "-y", DESFASADO,
    ], check=True, creationflags=sin_ventana)


# ═══════════════════════════════════════════════════════════════════════
print("=== 0. PREPARACIÓN ===")
if not mvf.is_available():
    print("  FFmpeg no está disponible: no se puede correr esta prueba.")
    sys.exit(1)
preparar_banco()
probar("videos de prueba generados",
       os.path.exists(CAMARA) and os.path.exists(DVR))

print("\n=== 1. FICHA DEL VIDEO ===")
ficha = mvf.info_video(CAMARA)
probar("duración", abs(ficha["duracion"] - 10) < 0.1, ficha["duracion_hms"])
probar("medidas", (ficha["ancho"], ficha["alto"]) == (640, 480))
probar("cadencia", abs(ficha["fps"] - 25) < 0.01, f"{ficha['fps']}")
probar("detecta cadencia fija", not ficha["vfr"])

print("\n=== 2. FORMATO DE TIEMPO ===")
probar("hms(257.32)", mvf.hms(257.32) == "00:04:17.320")
probar("lee 00:04:17.320", abs(mvf.segundos("00:04:17.320") - 257.32) < 1e-6)
probar("lee 4:17.32", abs(mvf.segundos("4:17.32") - 257.32) < 1e-6)
probar("lee 257,32 con coma", abs(mvf.segundos("257,32") - 257.32) < 1e-6)
probar("rechaza lo que no entiende", mvf.segundos("hola") is None)

print("\n=== 3. SE INFORMA EL TIEMPO DEL FOTOGRAMA, NO EL PEDIDO ===")
# A 25 cuadros/s los fotogramas caen en 0.00, 0.04, 0.08… Pidiendo 1.234
# el que corresponde es el de 1.24.
c = mvf.extraer_fotograma(CAMARA, 1.234, os.path.join(SALIDA, "a.png"))
probar("pedido 1.234 → informa 1.240", abs(c["t"] - 1.24) < 0.001, c["t_hms"])
probar("no repite el tiempo pedido", abs(c["t"] - c["pedido"]) > 0.001)
c2 = mvf.extraer_fotograma(CAMARA, 1.24, os.path.join(SALIDA, "b.png"))
probar("1.234 y 1.240 dan el mismo fotograma", sha(c["archivo"]) == sha(c2["archivo"]))
c3 = mvf.extraer_fotograma(CAMARA, 1.234, os.path.join(SALIDA, "c.png"))
probar("repetir la extracción da bytes idénticos", sha(c["archivo"]) == sha(c3["archivo"]))
c4 = mvf.extraer_fotograma(CAMARA, 1.28, os.path.join(SALIDA, "d.png"))
probar("el fotograma siguiente es otra imagen", sha(c["archivo"]) != sha(c4["archivo"]))

print("\n=== 4. MOVERSE DE A UN FOTOGRAMA ===")
lista = mvf.lista_fotogramas(CAMARA, 1.0, 1.0)
probar("lista los fotogramas de un segundo", 24 <= len(lista) <= 27, str(len(lista)))
probar("vienen ordenados",
       all(lista[i]["t"] <= lista[i + 1]["t"] for i in range(len(lista) - 1)))
probar("un fotograma adelante",
       abs(mvf.fotograma_vecino(CAMARA, 1.24, 1) - 1.28) < 0.001)
probar("un fotograma atrás",
       abs(mvf.fotograma_vecino(CAMARA, 1.24, -1) - 1.20) < 0.001)
probar("en el arranque no se va antes de cero",
       mvf.fotograma_vecino(CAMARA, 0.0, -1) == 0.0)

print("\n=== 5. NÚMERO DE FOTOGRAMA Y HORA DEL HECHO ===")
probar("número de fotograma", mvf.numero_de_fotograma(ficha, 1.24) == 32)
probar("con cadencia variable no inventa número",
       mvf.numero_de_fotograma({"vfr": True, "fps": 25}, 1.24) is None)
probar("sin hora de inicio no inventa hora",
       mvf.hora_real({"inicio_dt": None}, 5) is None)

print("\n=== 6. GRABACIÓN CON CUADROS CLAVE MUY SEPARADOS (como un DVR) ===")
# Acá se caía antes: FFprobe medía la ventana desde el cuadro clave anterior
# y la lista terminaba antes de llegar al momento pedido.
lejos = 17.32
lista_dvr = mvf.lista_fotogramas(DVR, lejos, 0.4)
probar("lista fotogramas lejos del cuadro clave", len(lista_dvr) >= 9,
       f"{len(lista_dvr)} fotogramas")
probar("el primero es el del momento pedido",
       bool(lista_dvr) and abs(lista_dvr[0]["t"] - lejos) < 0.041)
c_dvr = mvf.extraer_fotograma(DVR, lejos, os.path.join(SALIDA, "dvr.png"))
probar("extrae con el tiempo correcto", abs(c_dvr["t"] - lejos) < 0.041, c_dvr["t_hms"])
probar("paso adelante lejos del cuadro clave",
       abs(mvf.fotograma_vecino(DVR, c_dvr["t"], 1) - c_dvr["t"] - 0.04) < 0.005)
probar("paso atrás lejos del cuadro clave",
       abs(c_dvr["t"] - mvf.fotograma_vecino(DVR, c_dvr["t"], -1) - 0.04) < 0.005)

print("\n=== 7. RÁFAGA ===")
for nombre, video, arranque in (("normal", CAMARA, 5.32), ("DVR", DVR, lejos)):
    carpeta = os.path.join(SALIDA, f"rafaga_{nombre}")
    frames = mvf.rafaga(video, arranque, arranque + 0.4, carpeta)
    en_disco = len([f for f in os.listdir(carpeta) if f.endswith(".png")])
    probar(f"ráfaga {nombre}: un archivo por fotograma",
           en_disco == len(frames) and en_disco >= 9,
           f"informa {len(frames)}, en disco {en_disco}")
    probar(f"ráfaga {nombre}: ningún fotograma se pisa",
           len({f["t_hms"] for f in frames}) == len(frames))
    probar(f"ráfaga {nombre}: los tiempos avanzan",
           all(frames[i]["t"] < frames[i + 1]["t"] for i in range(len(frames) - 1)))

print("\n=== 8. RECORTE SIN RECODIFICAR ===")
seg = mvf.recortar_original(CAMARA, 3.0, 6.0, os.path.join(SALIDA, "segmento.mp4"))
info_seg = mvf.info_video(seg)
probar("el segmento existe", os.path.getsize(seg) > 1000)
probar("mantiene el códec", info_seg["codec"] == ficha["codec"])
probar("mantiene las medidas",
       (info_seg["ancho"], info_seg["alto"]) == (ficha["ancho"], ficha["alto"]))

print("\n=== 9. CONSTANCIA ===")
texto = mvf.constancia(ficha, c, [c["archivo"]], herramienta="Navaja (prueba)")
for dato in ["CONSTANCIA DE CAPTURA DE FOTOGRAMA", "00:00:01.240",
             "Fotograma n.º:     32", "640x480", "sin recortes"]:
    probar(f"la constancia dice «{dato[:36]}»", dato in texto)
probar("trae los hashes del video y de la imagen", texto.count("SHA-256") == 2)
probar("no inventa la hora si no la sabe", "no se puede determinar" in texto)

print("\n=== 10. ERRORES CLAROS ===")
try:
    mvf.info_video(os.path.join(BANCO, "no_existe.mp4"))
    probar("avisa si el archivo no existe", False)
except RuntimeError as e:
    probar("avisa si el archivo no existe", "No se pudo leer" in str(e))

print("\n=== 11. EL PANEL ===")
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QCoreApplication, QDeadlineTimer

app = QApplication.instance() or QApplication(sys.argv)
from ui.frame_capture_panel import FrameCapturePanel


def esperar(condicion, segundos=30):
    limite = QDeadlineTimer(int(segundos * 1000))
    while not limite.hasExpired():
        QCoreApplication.processEvents()
        if condicion():
            return True
        app.thread().msleep(30)
    return condicion()


panel = FrameCapturePanel()
probar("el panel se construye", panel is not None)
probar("arranca con los botones apagados",
       not panel.btn_capturar.isEnabled()
       and all(not b.isEnabled() for b in panel._botones_paso))

salida_panel = os.path.join(SALIDA, "panel")
os.makedirs(salida_panel, exist_ok=True)
panel._out_dir = salida_panel
panel._src_path = CAMARA
panel._ficha = mvf.info_video(CAMARA)
panel.slider.setRange(0, int(panel._ficha["duracion"] * 1000))
for b in panel._botones_paso:
    b.setEnabled(True)
panel._arrancar_navegador()
panel._navegar("salto", 0.0, desde=1.234)

llego = esperar(lambda: panel._captura is not None)
probar("llega el primer fotograma", llego)

if llego:
    probar("muestra el tiempo del fotograma entregado",
           "00:00:01.240" in panel.lbl_momento.text(), panel.lbl_momento.text())
    probar("muestra el número de fotograma",
           "fotograma n.º 32" in panel.lbl_momento.text())
    probar("hay imagen en pantalla",
           panel.vista.pixmap() is not None and not panel.vista.pixmap().isNull())
    probar("el slider sigue al fotograma", abs(panel.slider.value() - 1240) <= 1)

    antes = panel._captura["t"]
    panel._navegar("paso", 1)
    esperar(lambda: panel._captura["t"] > antes + 0.001)
    probar("botón de un fotograma adelante", abs(panel._captura["t"] - 1.28) < 0.001,
           panel._captura["t_hms"])

    panel.txt_tiempo.setText("00:00:05.500")
    panel._ir_a_tiempo()
    esperar(lambda: abs(panel._captura["t"] - 5.52) < 0.001)
    probar("va al tiempo escrito", abs(panel._captura["t"] - 5.52) < 0.001,
           panel._captura["t_hms"])
    panel.txt_tiempo.setText("cualquier cosa")
    panel._ir_a_tiempo()
    probar("avisa si el tiempo está mal escrito", "No entendí" in panel.lbl_estado.text())

    t_capturado = panel._captura["t"]
    panel._capturar()
    esperar(lambda: panel._tarea is not None and not panel._tarea.isRunning(), 45)
    esperar(lambda: "✅" in panel.lbl_estado.text() or "❌" in panel.lbl_estado.text())
    probar("captura y avisa", "✅" in panel.lbl_estado.text(), panel.lbl_estado.text())

    pngs = [f for f in os.listdir(salida_panel) if f.endswith(".png")]
    actas = [f for f in os.listdir(salida_panel) if f.endswith("_constancia.txt")]
    probar("guardó la imagen", len(pngs) == 1, str(pngs))
    probar("el nombre lleva el tiempo",
           bool(pngs) and mvf._nombre_de_tiempo(t_capturado) in pngs[0])
    probar("guardó la constancia", len(actas) == 1)

    if pngs:
        guardado = os.path.join(salida_panel, pngs[0])
        aparte = os.path.join(SALIDA, "verificacion.png")
        mvf.extraer_fotograma(CAMARA, t_capturado, aparte)
        probar("lo que se ve es lo que se guarda", sha(guardado) == sha(aparte))
        from PIL import Image
        with Image.open(guardado) as im:
            probar("PNG en la resolución original",
                   im.format == "PNG" and im.size == (640, 480), str(im.size))

    panel._nav.detener()
    probar("el hilo del navegador termina bien", not panel._nav.isRunning())

print("\n=== 11b. VIDEOS QUE NO ARRANCAN EN CERO ===")
# El archivo declara que el video empieza en 0,5 s. Los tiempos que se
# informan tienen que ser los que ve el usuario en un reproductor (contados
# desde el comienzo del video), no las marcas absolutas del contenedor: si no,
# el fotograma del minuto 1:20 figura como 1:20.042.
desf = mvf.info_video(DESFASADO)
probar("la ficha detecta el desfasaje", abs(desf["inicio"] - 0.5) < 0.01,
       f"{desf['inicio']} s")

c_desf = mvf.extraer_fotograma(DESFASADO, 5.0, os.path.join(SALIDA, "desf.png"))
probar("el tiempo informado se cuenta desde el comienzo del video",
       abs(c_desf["t"] - 5.0) < 0.041, c_desf["t_hms"])
probar("y no arrastra el desfasaje del archivo",
       abs(c_desf["t"] - 5.5) > 0.4, c_desf["t_hms"])
probar("el primer fotograma es el segundo cero",
       abs(mvf.lista_fotogramas(DESFASADO, 0, 0.2)[0]["t"]) < 0.001)
probar("el paso de a un fotograma sigue andando",
       abs(mvf.fotograma_vecino(DESFASADO, c_desf["t"], 1)
           - c_desf["t"] - 0.04) < 0.005)

# Lo importante: la imagen es la misma que la del mismo momento del original.
# Se corrigió el número, no lo que se muestra.
igual = os.path.join(SALIDA, "sin_desf.png")
mvf.extraer_fotograma(CAMARA, 5.0, igual)
probar("muestra el mismo fotograma que el video sin desfasar",
       sha(c_desf["archivo"]) == sha(igual))

mapa_desf = mvf.mapa_del_video(DESFASADO, os.path.join(SALIDA, "mapa_desf.png"),
                               cada=2.0, columnas=3, ancho_celda=160)
probar("el mapa también informa tiempos desde el comienzo",
       [c["t"] for c in mapa_desf["celdas"]] == [0.0, 2.0, 4.0, 6.0, 8.0],
       str([c["t_hms"] for c in mapa_desf["celdas"]]))

print("\n=== 12. MAPA DEL VIDEO (motor) ===")
probar("intervalo redondo para 30 s", mvf._intervalo_redondo(30, 60) == 1.0)
probar("intervalo redondo para 2 horas", mvf._intervalo_redondo(7200, 60) == 120.0)
probar("intervalo redondo para 10 minutos", mvf._intervalo_redondo(600, 60) == 10.0)

mapa_png = os.path.join(SALIDA, "mapa.png")
mapa = mvf.mapa_del_video(CAMARA, mapa_png, cada=2.0, columnas=4, ancho_celda=240)
probar("el mapa existe", os.path.getsize(mapa_png) > 5000)
probar("una miniatura cada 2 s en un video de 10 s", len(mapa["celdas"]) == 5,
       str(len(mapa["celdas"])))
probar("los tiempos son los esperados",
       [c["t"] for c in mapa["celdas"]] == [0.0, 2.0, 4.0, 6.0, 8.0],
       str([c["t_hms"] for c in mapa["celdas"]]))
probar("la grilla respeta las columnas pedidas", mapa["columnas"] == 4
       and mapa["filas"] == 2)
probar("cada celda cae dentro de la imagen",
       all(c["x"] >= 0 and c["y"] >= 0
           and c["x"] + c["w"] <= mapa["ancho"]
           and c["y"] + c["h"] <= mapa["alto"] for c in mapa["celdas"]))
probar("ninguna celda se superpone con otra",
       len({(c["x"], c["y"]) for c in mapa["celdas"]}) == len(mapa["celdas"]))

# El mapa no puede mentir: el pedazo de imagen que está en una celda tiene que
# ser el mismo fotograma que devuelve el video en ese tiempo.
from PIL import Image

celda = mapa["celdas"][3]                      # la del segundo 6
suelta = os.path.join(SALIDA, "suelta.png")
mvf._miniatura(CAMARA, celda["t"], suelta, 240)
with Image.open(mapa_png) as hoja, Image.open(suelta) as mini:
    recorte = hoja.crop((celda["x"], celda["y"],
                         celda["x"] + mini.width, celda["y"] + mini.height))
    probar("la miniatura del mapa es el fotograma de ese tiempo",
           list(recorte.getdata()) == list(mini.convert("RGB").getdata()))

acta_mapa = mvf.constancia_mapa(mapa["ficha"], mapa_png, mapa["cada"],
                                len(mapa["celdas"]), "Navaja (prueba)")
probar("la constancia del mapa trae los dos hashes",
       acta_mapa.count("SHA-256") == 2)
probar("la constancia del mapa aclara que son miniaturas",
       "no para observar detalles" in acta_mapa)

print("\n=== 13. MAPA DEL VIDEO (panel) ===")
from ui.video_map_panel import VideoMapPanel

salida_mapa = os.path.join(SALIDA, "panel_mapa")
os.makedirs(salida_mapa, exist_ok=True)
pm = VideoMapPanel()
probar("el panel del mapa se construye", pm is not None)
probar("arranca sin poder armar nada", not pm.btn_armar.isEnabled())

pm._out_dir = salida_mapa
pm.cargar_video(CAMARA)
probar("con el video cargado ya se puede armar", pm.btn_armar.isEnabled())
probar("calcula solo cada cuánto sacar una miniatura",
       pm.spin_cada.value() == 1.0, f"{pm.spin_cada.value()} s")
probar("avisa cuántas miniaturas van a salir",
       "miniaturas" in pm.lbl_estimado.text(), pm.lbl_estimado.text())

pm.chk_auto.setChecked(False)
pm.spin_cada.setValue(2.0)
pm.spin_col.setValue(4)
pm._armar()
esperar(lambda: pm._worker is not None and not pm._worker.isRunning(), 60)
esperar(lambda: pm._datos is not None or "❌" in pm.lbl_estado.text())
probar("arma el mapa y avisa", pm._datos is not None
       and "✅" in pm.lbl_estado.text(), pm.lbl_estado.text())
probar("guardó el archivo del mapa",
       len([f for f in os.listdir(salida_mapa) if f.endswith("_mapa.png")]) == 1)
probar("guardó la constancia del mapa",
       len([f for f in os.listdir(salida_mapa)
            if f.endswith("_mapa_constancia.txt")]) == 1)

if pm._datos:
    objetivo = pm._datos["celdas"][2]           # la del segundo 4
    pm._clic_en_mapa(objetivo["x"] + 5, objetivo["y"] + 5)
    probar("un clic sobre una miniatura reconoce el momento",
           pm._momento == objetivo["t"], mvf.hms(pm._momento or -1))
    probar("y habilita el salto a la captura", pm.btn_ir.isEnabled())
    probar("el cartel dice de qué momento es",
           objetivo["t_hms"] in pm.lbl_momento.text(), pm.lbl_momento.text())

    pm._clic_en_mapa(pm._datos["ancho"] - 2, pm._datos["alto"] - 2)
    probar("un clic en el borde vacío no inventa un momento",
           "no hay ninguna miniatura" in pm.lbl_momento.text())

print("\n=== 14. EL MAPA Y LA CAPTURA TRABAJAN JUNTAS ===")
from ui.video_module_panel import VideoModulePanel

modulo = VideoModulePanel()
solapas = [modulo.tabs.tabText(i) for i in range(modulo.tabs.count())]
probar("el módulo Video tiene sus seis solapas", len(solapas) == 6, str(solapas))
probar("ninguna solapa quedó rota",
       not any("No disponible" in modulo.tabs.widget(i).__class__.__name__
               for i in range(modulo.tabs.count()))
       and modulo.mapa is not None and modulo.captura is not None)

if modulo.mapa is not None and modulo.captura is not None:
    modulo.tabs.setCurrentIndex(0)
    modulo.mapa.momento_elegido.emit(CAMARA, 4.0)
    llego = esperar(lambda: modulo.captura._captura is not None, 30)
    probar("al elegir un momento salta a la solapa de captura",
           modulo.tabs.tabText(modulo.tabs.currentIndex()).strip().startswith("📸"),
           modulo.tabs.tabText(modulo.tabs.currentIndex()))
    probar("la captura abrió el mismo video",
           os.path.abspath(modulo.captura._src_path) == os.path.abspath(CAMARA))
    probar("y quedó parada en ese fotograma",
           llego and abs(modulo.captura._captura["t"] - 4.0) < 0.041,
           modulo.captura._captura["t_hms"] if llego else "no llegó")
    if modulo.captura._nav:
        modulo.captura._nav.detener()

print("\n" + "=" * 54)
print(f"TOTAL: {len(pasaron) + len(fallaron)} pruebas   "
      f"PASARON: {len(pasaron)}   FALLARON: {len(fallaron)}")
if fallaron:
    for f in fallaron:
        print(f"  · {f}")
sys.exit(1 if fallaron else 0)
