"""test_compat.py — Verifica la matriz de compatibilidad."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from core.graph import graph, COMPAT_MATRIX, is_compat
from motors.motor_images    import PillowMotor, CairoSVGMotor
from motors.motor_audio     import FFmpegAudioMotor
from motors.motor_documents import TxtToPdfMotor, PdfExtractMotor
from motors.motor_data      import DataMotor

for m in [PillowMotor, CairoSVGMotor, TxtToPdfMotor, PdfExtractMotor, DataMotor]:
    graph.register(m)

print("=== CONVERSIONES PROHIBIDAS (deben ser False) ===")
tests_prohibited = [
    ("xlsx", "midi"),
    ("xlsx", "mp3"),
    ("png",  "docx"),
    ("mp3",  "xlsx"),
    ("jpg",  "wav"),
    ("csv",  "mp4"),
]
all_ok = True
for src, dst in tests_prohibited:
    in_matrix = is_compat(src, dst)
    in_graph  = graph.direct_motor(src, dst) is not None
    status = "OK" if not in_matrix and not in_graph else "FAIL"
    if status == "FAIL":
        all_ok = False
    print(f"  {status}  {src.upper()}→{dst.upper()}: matrix={in_matrix}, graph={in_graph}")

print()
print("=== RUTAS DE CADENA ===")
chains = [
    ("xlsx", "png"),   # via pdf
    ("txt",  "pdf"),   # directo
    ("jpg",  "pdf"),   # directo (png->pdf in compat)
]
for src, dst in chains:
    path = graph.find_path(src, dst)
    print(f"  {src.upper()}→{dst.upper()}: {' → '.join(p.upper() for p in path) if path else 'SIN RUTA'}")

print()
print(f"Total edges en grafo: {len(graph._edges)}")
print(f"Total entradas en COMPAT_MATRIX: {sum(len(v) for v in COMPAT_MATRIX.values())}")
print()
print("RESULTADO:", "PASS" if all_ok else "HAY CONVERSIONES PROHIBIDAS EN EL GRAFO")
