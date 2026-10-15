"""
ui/hash_panel.py — Extraer el hash (huella digital) de uno o varios archivos.

El hash es la huella de un archivo: si cambia un solo byte, cambia por
completo. Sirve para probar que un archivo no fue modificado.

Se calculan dos algoritmos fuertes por defecto y en una sola lectura, para
que sacarle el hash a un video de varios GB no lo lea dos veces.
"""
import os

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget,
    QFileDialog, QMessageBox, QGroupBox, QCheckBox, QProgressBar,
    QPlainTextEdit, QLineEdit, QAbstractItemView, QApplication,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont

from core.hasher import HASH_ALGOS, HASH_DEFAULT, hash_file, hash_label


class _HashWorker(QThread):
    """Calcula los hashes en segundo plano: un archivo grande tarda."""
    progreso = pyqtSignal(str, int)          # (nombre, % del archivo actual)
    avance = pyqtSignal(int, int)            # (archivo actual, total)
    listo = pyqtSignal(list)                 # [{"path","filename","size_mb","hashes"}]
    error = pyqtSignal(str)

    def __init__(self, paths, algos):
        super().__init__()
        self._paths = list(paths)
        self._algos = tuple(algos)

    def run(self):
        try:
            resultados = []
            total = len(self._paths)
            for i, path in enumerate(self._paths, start=1):
                nombre = os.path.basename(path)
                self.avance.emit(i, total)
                self.progreso.emit(nombre, 0)
                hashes = hash_file(
                    path, self._algos,
                    progress_cb=lambda pct, n=nombre: self.progreso.emit(n, pct))
                try:
                    size_mb = os.path.getsize(path) / (1024 * 1024)
                except OSError:
                    size_mb = 0.0
                resultados.append({
                    "path": path, "filename": nombre,
                    "size_mb": size_mb, "hashes": hashes,
                })
            self.listo.emit(resultados)
        except Exception as e:
            self.error.emit(str(e))


class HashPanel(QWidget):
    """Herramienta de integridad: saca el hash de cualquier archivo."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker = None
        self._resultados = []
        self._build()

    # ── Construcción ──────────────────────────────────────────────────
    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        hdr = QLabel("🔢  Extraer hash")
        hdr.setObjectName("panelHeader")
        lay.addWidget(hdr)

        intro = QLabel(
            "El <b>hash</b> es la huella digital de un archivo: un código que "
            "cambia por completo si se modifica aunque sea un byte. Sirve "
            "para demostrar que un archivo es idéntico al original.")
        intro.setWordWrap(True)
        intro.setStyleSheet("color:#64748b;")
        lay.addWidget(intro)

        # ── 1. Archivos ──────────────────────────────────────────────
        grp1 = QGroupBox("1️⃣  Elegí los archivos")
        g1 = QVBoxLayout(grp1)
        fila = QHBoxLayout()
        btn_files = QPushButton("➕ Agregar archivos...")
        btn_files.clicked.connect(self._add_files)
        fila.addWidget(btn_files)
        btn_folder = QPushButton("📁 Agregar carpeta...")
        btn_folder.clicked.connect(self._add_folder)
        fila.addWidget(btn_folder)
        btn_clear = QPushButton("🗑 Limpiar")
        btn_clear.clicked.connect(self._clear)
        fila.addWidget(btn_clear)
        fila.addStretch()
        g1.addLayout(fila)

        self.lista = QListWidget()
        self.lista.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection)
        self.lista.setMinimumHeight(120)
        g1.addWidget(self.lista)
        lay.addWidget(grp1)

        # ── 2. Algoritmos ────────────────────────────────────────────
        grp2 = QGroupBox("2️⃣  Con qué algoritmos")
        g2 = QVBoxLayout(grp2)
        self._checks = {}
        for clave, (nombre, confiable, ayuda) in HASH_ALGOS.items():
            chk = QCheckBox(nombre if confiable else f"{nombre}  ⚠ obsoleto")
            chk.setChecked(clave in HASH_DEFAULT)
            chk.setToolTip(ayuda)
            if not confiable:
                chk.setStyleSheet("color:#b45309;")
            self._checks[clave] = chk
            g2.addWidget(chk)

        nota = QLabel(
            "Vienen marcados <b>SHA-256</b> y <b>SHA-512</b>: dos algoritmos "
            "fuertes. SHA-1 y MD5 están rotos (se pueden fabricar dos "
            "archivos distintos con el mismo código), así que marcalos sólo "
            "si un sistema viejo te los exige.")
        nota.setWordWrap(True)
        nota.setStyleSheet("color:#64748b; font-size:11px;")
        g2.addWidget(nota)
        lay.addWidget(grp2)

        self.btn_run = QPushButton("🔢 Calcular los hashes")
        self.btn_run.setObjectName("primaryBtn")
        self.btn_run.clicked.connect(self._run)
        lay.addWidget(self.btn_run)

        # ── Verificar contra un hash conocido ────────────────────────
        # Va acá, siempre a la vista: si a alguien le pasaron un hash y
        # quiere comprobar un archivo, es lo primero que busca. Antes
        # estaba escondido dentro del resultado y no aparecía hasta
        # después de calcular.
        grp_ver = QGroupBox("🔎  ¿Te pasaron un hash? Verificá el archivo")
        gv = QVBoxLayout(grp_ver)
        gv.addWidget(QLabel(
            "Pegá el código que te dieron y te digo si el archivo de arriba "
            "es exactamente ese. No hace falta que sepas de qué tipo es: "
            "lo reconozco por su longitud."))
        fila_cmp = QHBoxLayout()
        self.txt_cmp = QLineEdit()
        self.txt_cmp.setPlaceholderText("pegá acá el hash que te pasaron")
        self.txt_cmp.returnPressed.connect(self._verify)
        fila_cmp.addWidget(self.txt_cmp, stretch=1)
        self.btn_cmp = QPushButton("🔎 Verificar")
        self.btn_cmp.clicked.connect(self._verify)
        fila_cmp.addWidget(self.btn_cmp)
        gv.addLayout(fila_cmp)

        self.lbl_cmp = QLabel("")
        self.lbl_cmp.setWordWrap(True)
        self.lbl_cmp.setVisible(False)
        gv.addWidget(self.lbl_cmp)
        lay.addWidget(grp_ver)

        self.pbar = QProgressBar()
        self.pbar.setVisible(False)
        lay.addWidget(self.pbar)
        self.lbl_status = QLabel("")
        self.lbl_status.setWordWrap(True)
        lay.addWidget(self.lbl_status)

        # ── 3. Resultado ─────────────────────────────────────────────
        self.grp_out = QGroupBox("3️⃣  Resultado")
        g3 = QVBoxLayout(self.grp_out)
        self.salida = QPlainTextEdit()
        self.salida.setReadOnly(True)
        self.salida.setFont(QFont("Consolas", 9))
        self.salida.setMinimumHeight(160)
        g3.addWidget(self.salida)

        fila_out = QHBoxLayout()
        btn_copy = QPushButton("📋 Copiar")
        btn_copy.clicked.connect(self._copy)
        fila_out.addWidget(btn_copy)
        btn_save = QPushButton("💾 Guardar como informe...")
        btn_save.clicked.connect(self._save)
        fila_out.addWidget(btn_save)
        fila_out.addStretch()
        g3.addLayout(fila_out)

        self.grp_out.setVisible(False)
        lay.addWidget(self.grp_out)
        lay.addStretch()

    # ── Archivos ──────────────────────────────────────────────────────
    def _add_paths(self, paths):
        existentes = {self.lista.item(i).data(Qt.ItemDataRole.UserRole)
                      for i in range(self.lista.count())}
        nuevos = 0
        for p in paths:
            if p in existentes or not os.path.isfile(p):
                continue
            from PyQt6.QtWidgets import QListWidgetItem
            item = QListWidgetItem(os.path.basename(p))
            item.setData(Qt.ItemDataRole.UserRole, p)
            item.setToolTip(p)
            self.lista.addItem(item)
            nuevos += 1
        if nuevos:
            self.lbl_status.setText(f"{nuevos} archivo(s) agregado(s).")

    def _add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Elegí los archivos", "", "Todos los archivos (*.*)")
        self._add_paths(paths)

    def _add_folder(self):
        carpeta = QFileDialog.getExistingDirectory(self, "Elegí la carpeta")
        if not carpeta:
            return
        archivos = sorted(
            os.path.join(carpeta, f) for f in os.listdir(carpeta)
            if os.path.isfile(os.path.join(carpeta, f)))
        if not archivos:
            QMessageBox.information(self, "Extraer hash",
                                    "Esa carpeta no tiene archivos.")
            return
        self._add_paths(archivos)

    def _clear(self):
        self.lista.clear()
        self.salida.setPlainText("")
        self.grp_out.setVisible(False)
        self._resultados = []
        self.lbl_status.setText("")

    # ── Cálculo ───────────────────────────────────────────────────────
    def _algos_elegidos(self):
        return tuple(c for c, chk in self._checks.items() if chk.isChecked())

    def _run(self):
        paths = [self.lista.item(i).data(Qt.ItemDataRole.UserRole)
                 for i in range(self.lista.count())]
        if not paths:
            QMessageBox.warning(self, "Extraer hash",
                                "Primero agregá al menos un archivo.")
            return
        algos = self._algos_elegidos()
        if not algos:
            QMessageBox.warning(self, "Extraer hash",
                                "Marcá al menos un algoritmo.")
            return
        if self._worker and self._worker.isRunning():
            QMessageBox.information(self, "Extraer hash",
                                    "Esperá a que termine el cálculo en curso.")
            return

        self.btn_run.setEnabled(False)
        self.pbar.setVisible(True)
        self.pbar.setRange(0, 100)
        self.pbar.setValue(0)

        self._worker = _HashWorker(paths, algos)
        self._worker.progreso.connect(self._on_progress)
        self._worker.avance.connect(self._on_step)
        self._worker.listo.connect(self._on_done)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_progress(self, nombre: str, pct: int):
        self.pbar.setValue(pct)
        self.lbl_status.setText(f"Calculando: {nombre} ({pct}%)")

    def _on_step(self, actual: int, total: int):
        self.pbar.setFormat(f"Archivo {actual} de {total} — %p%")

    def _on_done(self, resultados: list):
        self.btn_run.setEnabled(True)
        self.pbar.setVisible(False)
        self._resultados = resultados
        self.salida.setPlainText(self._texto_resultado(resultados))
        self.grp_out.setVisible(True)
        self.lbl_status.setText(
            f"✅ Listo: {len(resultados)} archivo(s) procesado(s).")

    def _on_error(self, msg: str):
        self.btn_run.setEnabled(True)
        self.pbar.setVisible(False)
        self.lbl_status.setText("")
        QMessageBox.warning(self, "Extraer hash", f"Error:\n{msg}")

    @staticmethod
    def _texto_resultado(resultados: list) -> str:
        from core.informe import fecha_formal
        lineas = [
            "CÓDIGOS DE VERIFICACIÓN (HASH)",
            "─" * 68,
            f"Fecha: {fecha_formal()}",
            "",
        ]
        for i, r in enumerate(resultados, start=1):
            lineas.append(f"{i}) {r['filename']}  ({r['size_mb']:.2f} MB)")
            lineas.append(f"   Ruta: {r['path']}")
            for algo, valor in r["hashes"].items():
                lineas.append(f"   {hash_label(algo):9}: {valor}")
            lineas.append("")
        lineas.append("─" * 68)
        return "\n".join(lineas)

    # ── Salida ────────────────────────────────────────────────────────
    def _copy(self):
        QApplication.clipboard().setText(self.salida.toPlainText())
        self.lbl_status.setText("📋 Copiado al portapapeles.")

    def _save(self):
        if not self._resultados:
            return
        from core.informe import build_informe_detallado
        sugerido = os.path.join(
            os.path.dirname(self._resultados[0]["path"]), "hashes.txt")
        dst, _ = QFileDialog.getSaveFileName(
            self, "Guardar informe de hashes", sugerido, "Texto (*.txt)")
        if not dst:
            return
        operaciones = [{
            "frase": f"extraer los códigos de verificación (hash) del "
                     f"archivo «{r['filename']}»",
            "original": r,
            "resultados": [],
        } for r in self._resultados]
        try:
            with open(dst, "w", encoding="utf-8") as f:
                f.write(build_informe_detallado(operaciones))
            self.lbl_status.setText(f"💾 Informe guardado en {dst}")
        except Exception as e:
            QMessageBox.warning(self, "Extraer hash",
                                f"No pude guardar el informe:\n{e}")

    # ── Verificación contra un hash conocido ──────────────────────────
    def _aviso_cmp(self, texto: str, tipo: str = "info"):
        colores = {
            "ok":    ("#dcfce7", "#166534"),
            "mal":   ("#fee2e2", "#991b1b"),
            "info":  ("#e0f2fe", "#075985"),
        }
        fondo, color = colores.get(tipo, colores["info"])
        self.lbl_cmp.setText(texto)
        self.lbl_cmp.setStyleSheet(
            f"background:{fondo}; color:{color}; padding:8px; "
            "border-radius:4px;")
        self.lbl_cmp.setVisible(True)

    def _verify(self):
        """Compara el hash pegado contra los archivos de la lista.

        Reconoce el algoritmo por la longitud del hash y, si hace falta, lo
        calcula en el momento: el usuario no tiene por qué saber si le
        pasaron un SHA-256 o un SHA-1.
        """
        from core.hasher import algos_por_longitud, normalizar_hash

        esperado = normalizar_hash(self.txt_cmp.text())
        if not esperado:
            return

        candidatos = algos_por_longitud(esperado)
        if not candidatos:
            self._aviso_cmp(
                "Eso no parece un hash. Un hash son sólo números y letras "
                "de la A a la F, sin espacios (por ejemplo, 64 caracteres "
                "para un SHA-256). Fijate de haberlo copiado completo.",
                "mal")
            return

        nombres = " o ".join(hash_label(a) for a in candidatos)
        paths = [self.lista.item(i).data(Qt.ItemDataRole.UserRole)
                 for i in range(self.lista.count())]
        if not paths:
            self._aviso_cmp(
                f"Ese hash parece un {nombres}. Agregá arriba el archivo que "
                "querés verificar y volvé a tocar «Verificar».", "info")
            return

        # ¿Ya lo tenemos calculado?
        if self._buscar_coincidencia(esperado, candidatos, nombres):
            return

        # Si no, se calcula justo el algoritmo que corresponde
        if self._worker and self._worker.isRunning():
            QMessageBox.information(self, "Extraer hash",
                                    "Esperá a que termine el cálculo en curso.")
            return

        self._aviso_cmp(
            f"Ese hash parece un {nombres}. Calculándolo para comparar...",
            "info")
        self._pendiente_cmp = (esperado, candidatos, nombres)
        self.btn_run.setEnabled(False)
        self.btn_cmp.setEnabled(False)
        self.pbar.setVisible(True)
        self._worker = _HashWorker(paths, candidatos)
        self._worker.progreso.connect(self._on_progress)
        self._worker.avance.connect(self._on_step)
        self._worker.listo.connect(self._on_verify_done)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_verify_done(self, resultados: list):
        self.btn_run.setEnabled(True)
        self.btn_cmp.setEnabled(True)
        self.pbar.setVisible(False)
        self.lbl_status.setText("")

        # Se suman a lo ya calculado, sin pisar lo anterior
        por_path = {r["path"]: r for r in self._resultados}
        for r in resultados:
            if r["path"] in por_path:
                por_path[r["path"]]["hashes"].update(r["hashes"])
            else:
                self._resultados.append(r)
        if self._resultados:
            self.salida.setPlainText(self._texto_resultado(self._resultados))
            self.grp_out.setVisible(True)

        esperado, candidatos, nombres = getattr(
            self, "_pendiente_cmp", ("", [], ""))
        if esperado and not self._buscar_coincidencia(
                esperado, candidatos, nombres):
            pass
        self._pendiente_cmp = None

    def _buscar_coincidencia(self, esperado: str, candidatos: list,
                             nombres: str) -> bool:
        """Busca el hash entre lo calculado. Devuelve True si ya hubo veredicto."""
        calculado_alguno = False
        for r in self._resultados:
            for algo in candidatos:
                valor = r["hashes"].get(algo)
                if not valor or valor.startswith("ERROR"):
                    continue
                calculado_alguno = True
                if valor.lower() == esperado:
                    self._aviso_cmp(
                        f"✅ COINCIDE. El archivo «{r['filename']}» tiene "
                        f"exactamente ese {hash_label(algo)}: es idéntico al "
                        "original, no fue modificado.", "ok")
                    return True

        if calculado_alguno:
            if len(self._resultados) == 1:
                sujeto = (f"El archivo «{self._resultados[0]['filename']}» no "
                          f"tiene ese {nombres}")
            else:
                sujeto = (f"Ninguno de los {len(self._resultados)} archivos "
                          f"de la lista tiene ese {nombres}")
            self._aviso_cmp(
                f"❌ NO COINCIDE. {sujeto}. No es el mismo archivo que generó "
                "ese código, o fue modificado.", "mal")
            return True
        return False
