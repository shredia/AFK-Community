# aplicacion/ventana_progreso.py
"""Ventana que muestra qué está haciendo una tarea larga (log + barra + cancelar)."""
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk
from aplicacion import tema
from idiomas import tr


class VentanaProgreso:
    """
    Uso:
        prog = VentanaProgreso(parent, "Descargando...")
        # Desde cualquier hilo:
        prog.log("mensaje")
        prog.avance(hechas, total)
        if prog.cancelar.is_set(): ...
        # Al terminar (desde cualquier hilo):
        prog.terminar("Listo", ok=True)
    """

    INTERVALO_MS = 100

    def __init__(self, parent, titulo, cancelable=True):
        self.cancelar = threading.Event()
        self._cola = queue.Queue()
        self._inicio = time.monotonic()
        self._terminado = False

        self.top = tk.Toplevel(parent)
        self.top.title(tr(titulo))
        self.top.geometry("560x380")
        self.top.minsize(420, 300)
        self.top.transient(parent)
        self.top.protocol("WM_DELETE_WINDOW", self._al_cerrar)

        self.lbl_estado = tk.Label(self.top, text=tr("Iniciando..."), font=("Arial", 10, "bold"), anchor="w")
        self.lbl_estado.pack(fill="x", padx=12, pady=(12, 4))

        self.barra = ttk.Progressbar(self.top, mode="indeterminate")
        self.barra.pack(fill="x", padx=12)
        self.barra.start(12)

        self.lbl_detalle = tk.Label(self.top, text="", fg=tema.MUTED, anchor="w")
        self.lbl_detalle.pack(fill="x", padx=12, pady=(2, 6))

        marco = ttk.Frame(self.top)
        marco.pack(fill="both", expand=True, padx=12)
        self.txt_log = tk.Text(marco, height=12, state="disabled", wrap="word", font=("Consolas", 9))
        scroll = ttk.Scrollbar(marco, command=self.txt_log.yview)
        self.txt_log.configure(yscrollcommand=scroll.set)
        self.txt_log.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        self.btn = ttk.Button(
            self.top,
            text=tr("Cancelar") if cancelable else tr("Cerrar"),
            command=self._al_boton,
            state="normal" if cancelable else "disabled",
        )
        self.btn.pack(pady=10)

        # Tomar el foco modal (si el padre lo tenía, se le devuelve al cerrar)
        self._parent = parent
        self._parent_tenia_grab = parent.grab_current() is parent
        self.top.grab_set()

        self.top.after(self.INTERVALO_MS, self._procesar_cola)

    def _destruir(self):
        self.top.grab_release()
        self.top.destroy()
        if self._parent_tenia_grab:
            try:
                self._parent.grab_set()
            except tk.TclError:
                pass

    # ---------- API segura para llamar desde cualquier hilo ----------

    def log(self, mensaje):
        try:
            print(mensaje)
        except (UnicodeEncodeError, OSError):
            pass  # la consola no soporta el carácter; la ventana sí lo muestra
        self._cola.put(("log", mensaje))

    def avance(self, hechas, total):
        self._cola.put(("avance", (hechas, total)))

    def terminar(self, mensaje, ok=True):
        self._cola.put(("fin", (mensaje, ok)))

    # ---------- Interno (hilo de Tk) ----------

    def _procesar_cola(self):
        try:
            while True:
                tipo, dato = self._cola.get_nowait()
                if tipo == "log":
                    self._agregar_log(dato)
                    self.lbl_estado.config(text=dato.strip())
                elif tipo == "avance":
                    self._actualizar_barra(*dato)
                elif tipo == "fin":
                    self._finalizar(*dato)
        except queue.Empty:
            pass
        except tk.TclError:
            return  # la ventana ya se cerró

        if not self._terminado or not self._cola.empty():
            self.top.after(self.INTERVALO_MS, self._procesar_cola)

    def _agregar_log(self, mensaje):
        segundos = int(time.monotonic() - self._inicio)
        linea = f"[{segundos // 60:02d}:{segundos % 60:02d}] {mensaje}\n"
        self.txt_log.configure(state="normal")
        self.txt_log.insert("end", linea)
        self.txt_log.see("end")
        self.txt_log.configure(state="disabled")

    def _actualizar_barra(self, hechas, total):
        if total <= 0:
            return
        if str(self.barra.cget("mode")) != "determinate":
            self.barra.stop()
            self.barra.configure(mode="determinate", maximum=total)
        self.barra.configure(value=hechas)

        transcurrido = time.monotonic() - self._inicio
        texto = f"{hechas} de {total} ({hechas * 100 // total}%)"
        if hechas:
            restante = int(transcurrido / hechas * (total - hechas))
            texto += f" — quedan ~{restante // 60} min {restante % 60} s"
        self.lbl_detalle.config(text=tr(texto))

    def _finalizar(self, mensaje, ok):
        self._terminado = True
        self.barra.stop()
        if str(self.barra.cget("mode")) != "determinate":
            self.barra.configure(mode="determinate", maximum=1, value=1 if ok else 0)
        self._agregar_log(mensaje)
        self.lbl_estado.config(text=tr(mensaje), fg=tema.OK if ok else tema.ERR)
        self.btn.config(text=tr("Cerrar"), state="normal")

    def _al_boton(self):
        if self._terminado:
            self._destruir()
        else:
            self.cancelar.set()
            self.btn.config(state="disabled", text=tr("Cancelando..."))
            self.log("Cancelando... se detendrá al terminar la run actual.")

    def _al_cerrar(self):
        if self._terminado:
            self._destruir()
        else:
            self._al_boton()
