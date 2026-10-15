"""
motors/motor_voces.py — Reconocer quién habla en una grabación.

Whisper escribe lo que se dice, pero no sabe quién lo dice. Esto escucha las
voces, las agrupa por parecido y devuelve los turnos: «de 0:11 a 0:14 habla
la persona 2». Con eso cada tramo de la transcripción queda con su hablante.

No identifica a nadie por su nombre: sólo separa voces distintas
(«Interlocutor 1», «Interlocutor 2»…), y los nombres los pone el usuario. Se equivoca más cuando
las voces se parecen, cuando hablan a la vez o cuando el audio es malo, así
que el resultado se puede corregir tramo por tramo.

Funciona sin internet y sólo con el procesador (biblioteca sherpa-onnx). Sus
dos modelos, de unos 30 MB en total, viajan en la carpeta models/voces.
"""
import os
import wave
from typing import Callable, List, Optional

MODELO_TURNOS = "segmentacion.onnx"     # encuentra dónde empieza y termina cada voz
MODELO_VOCES = "voces_resnet34.onnx"    # saca la "huella" de cada voz
FRECUENCIA = 16000

# Qué tan distintas tienen que ser dos voces para contarlas como dos personas
# cuando no se dice cuántas hay. Con 0,5 (el valor de fábrica) a una misma
# persona la partía en dos; 0,6 anduvo bien en las pruebas.
UMBRAL = 0.6
CANTIDAD_POR_DEFECTO = 2    # lo más común: quien pregunta y quien contesta

# Cuántas personas se pueden pedir. 0 = que lo descubra solo.
CANTIDADES = [(0, "Que lo descubra solo"), (2, "2 personas"), (3, "3 personas"),
              (4, "4 personas"), (5, "5 personas"), (6, "6 personas")]


def _carpetas() -> List[str]:
    from core.paths import MODELS_DIR, resource
    return [os.path.join(str(MODELS_DIR), "voces"),
            resource(os.path.join("models", "voces"))]


def _modelo(nombre: str) -> str:
    for carpeta in _carpetas():
        ruta = os.path.join(carpeta, nombre)
        if os.path.isfile(ruta):
            return ruta
    return ""


def motivo_no_disponible() -> str:
    """"" si se puede usar; si no, la explicación para el usuario."""
    import importlib.util
    try:
        falta = importlib.util.find_spec("sherpa_onnx") is None
    except Exception:
        falta = True
    if falta:
        return ("En esta instalación falta el reconocedor de voces "
                "(sherpa-onnx).")
    if not _modelo(MODELO_TURNOS) or not _modelo(MODELO_VOCES):
        return ("Faltan los modelos del reconocedor de voces: tendrían que "
                "estar en la carpeta models\\voces del programa.")
    return ""


def _leer_wav(ruta: str):
    """El audio como números entre -1 y 1, mono, a 16 kHz."""
    import numpy as np
    with wave.open(ruta) as w:
        frecuencia, canales = w.getframerate(), w.getnchannels()
        crudo = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    audio = crudo.reshape(-1, canales).mean(axis=1).astype(np.float32) / 32768
    if frecuencia == FRECUENCIA * 2:
        # El WAV de la transcripción es de 32 kHz: mitad exacta.
        audio = audio[: len(audio) // 2 * 2].reshape(-1, 2).mean(axis=1)
    elif frecuencia != FRECUENCIA:
        n = int(len(audio) * FRECUENCIA / frecuencia)
        audio = np.interp(np.linspace(0, len(audio) - 1, n),
                          np.arange(len(audio)), audio)
    return np.ascontiguousarray(audio, dtype=np.float32)


def reconocer(
    wav: str,
    cantidad: int = 0,
    progreso_cb: Optional[Callable[[float], None]] = None,
) -> List[dict]:
    """Devuelve los turnos: [{"inicio": s, "fin": s, "persona": 0, 1, …}].

    cantidad — cuántas personas hablan; 0 para que lo descubra solo. Si se
    sabe, conviene decirlo: acierta más.
    """
    motivo = motivo_no_disponible()
    if motivo:
        raise RuntimeError(motivo)
    import sherpa_onnx

    hilos = max(1, min(8, (os.cpu_count() or 4) - 1))
    config = sherpa_onnx.OfflineSpeakerDiarizationConfig(
        segmentation=sherpa_onnx.OfflineSpeakerSegmentationModelConfig(
            pyannote=sherpa_onnx.OfflineSpeakerSegmentationPyannoteModelConfig(
                model=_modelo(MODELO_TURNOS)),
            num_threads=hilos),
        embedding=sherpa_onnx.SpeakerEmbeddingExtractorConfig(
            model=_modelo(MODELO_VOCES), num_threads=hilos),
        clustering=sherpa_onnx.FastClusteringConfig(
            num_clusters=cantidad if cantidad and cantidad > 0 else -1,
            threshold=UMBRAL),
        min_duration_on=0.3, min_duration_off=0.5)
    if not config.validate():
        raise RuntimeError("No se pudo preparar el reconocedor de voces.")
    motor = sherpa_onnx.OfflineSpeakerDiarization(config)

    def avance(hechos, total):
        if progreso_cb and total:
            progreso_cb(max(0.0, min(1.0, hechos / total)))
        return 0

    resultado = motor.process(_leer_wav(wav), callback=avance)
    turnos = [{"inicio": float(t.start), "fin": float(t.end),
               "persona": int(t.speaker)}
              for t in resultado.sort_by_start_time()]

    # Se numeran por orden de aparición: la persona 1 es la primera que habla.
    orden = {}
    for t in turnos:
        orden.setdefault(t["persona"], len(orden))
        t["persona"] = orden[t["persona"]]
    return turnos


def asignar(tramos: List[dict], turnos: List[dict]) -> int:
    """Le pone a cada tramo la persona que más habla en ese rato.

    Escribe tramo["persona"] (0, 1, …, o None si ahí no detectó ninguna voz)
    y devuelve cuántas personas distintas hay.
    """
    for tramo in tramos:
        segundos = {}
        for turno in turnos:
            comun = (min(tramo["fin"], turno["fin"])
                     - max(tramo["inicio"], turno["inicio"]))
            if comun > 0:
                segundos[turno["persona"]] = (
                    segundos.get(turno["persona"], 0.0) + comun)
        tramo["persona"] = (max(segundos, key=segundos.get)
                            if segundos else None)
    return len({t["persona"] for t in tramos if t.get("persona") is not None})


def nombres_por_defecto(cantidad: int) -> List[str]:
    return [nombre_por_defecto(i) for i in range(cantidad)]


def nombre_por_defecto(indice: int) -> str:
    return f"Interlocutor {indice + 1}"
