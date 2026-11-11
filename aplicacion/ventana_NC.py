# aplicacion/ventana_NC.py
import tkinter as tk
from tkinter import ttk, messagebox
import asyncio
import json
import threading
from collections import defaultdict
from pathlib import Path

from navegador.parser import procesar_y_ordenar_runs
from navegador.rutas import cargar_mapa_personajes, carpeta_personaje, ruta_detalle
from navegador.scraper import (
    obtener_sources_iniciales,
    descargar_detalles_faltantes,
    detalles_pendientes,
    descargar_assets,
    assets_pendientes,
)
from aplicacion.ventana_progreso import VentanaProgreso
from aplicacion import tema
from idiomas import tr


def _solo_propias(runs):
    return [run for run in runs if isinstance(run, dict) and run.get("mine") is True]


class Ventana_NC:
    def __init__(self, parent, perfil_path):
        self.parent = parent
        self.perfil_path = Path(perfil_path)
        self.base_dir = self.perfil_path.parent
        self.archivo_cache = self.base_dir / "sources_guardados.json"   # lista resumida (solo mine)

        self.sources = []          # runs propias (mine: true)
        self.runs_guardadas = []   # runs procesadas para el combobox

        self.top = tk.Toplevel(parent)
        self.top.title(tr("Runs de NC"))
        self.top.geometry("500x520")
        self.top.resizable(False, False)
        self.top.grab_set()

        self.crear_interfaz()
        self.verificar_y_cargar_cache()

    # ============================================
    # INTERFAZ
    # ============================================

    def crear_interfaz(self):
        tk.Label(self.top, text=tr("Runs de Nightmare Corridor"), font=("Arial", 12, "bold")).pack(pady=10)
        self.lbl_estado_nc = tk.Label(self.top, text=tr("Listo para iniciar la descarga"), fg=tema.MUTED, font=("Arial", 10))
        self.lbl_estado_nc.pack(pady=5)

        # 1. Lista resumida
        frame_lista = ttk.LabelFrame(self.top, text=tr(" 1. Lista de tus runs (resumen) "))
        frame_lista.pack(fill="x", padx=20, pady=5)
        self.btn_ejecutar = ttk.Button(frame_lista, text=tr("Actualizar lista de runs"), command=self.ejecutar_proceso)
        self.btn_ejecutar.pack(pady=8)

        # 2. Detalles completos
        frame_det = ttk.LabelFrame(self.top, text=tr(" 2. Detalles completos (equipos, héroes, etc.) "))
        frame_det.pack(fill="x", padx=20, pady=5)
        self.lbl_detalles = tk.Label(frame_det, text="", font=("Arial", 9))
        self.lbl_detalles.pack(pady=(6, 2))
        self.btn_detalles = ttk.Button(frame_det, text=tr("Descargar detalles faltantes"),
                                       command=self.descargar_detalles, state="disabled")
        self.btn_detalles.pack(pady=(2, 8))

        # 3. Assets
        frame_assets = ttk.LabelFrame(self.top, text=tr(" 3. Imágenes (héroes, mascotas, etc.) "))
        frame_assets.pack(fill="x", padx=20, pady=5)
        self.lbl_assets = tk.Label(frame_assets, text="", font=("Arial", 9))
        self.lbl_assets.pack(pady=(6, 2))
        self.btn_assets = ttk.Button(frame_assets, text=tr("Descargar imágenes faltantes"),
                                     command=self.descargar_imagenes, state="disabled")
        self.btn_assets.pack(pady=(2, 8))

        tk.Label(self.top, text=tr("Tus runs:"), font=("Arial", 9, "bold")).pack(anchor="w", padx=25, pady=(10, 2))
        self.variable_seleccionada = tk.StringVar()
        self.combo_runs = ttk.Combobox(self.top, textvariable=self.variable_seleccionada, state="disabled", width=60)
        self.combo_runs.set("Primero haz clic en actualizar...")
        self.combo_runs.pack(pady=5)
        self.combo_runs.bind("<<ComboboxSelected>>", self.al_seleccionar_run)

    # ============================================
    # DATOS LOCALES
    # ============================================

    def verificar_y_cargar_cache(self):
        """Carga el cache local (solo runs propias) y actualiza la ventana."""
        if not self.archivo_cache.exists():
            self._actualizar_contadores()
            return

        try:
            with self.archivo_cache.open("r", encoding="utf-8") as archivo:
                datos = json.load(archivo)
            self.sources = _solo_propias(datos)

            # Limpieza: versiones anteriores guardaban también runs ajenas
            if len(self.sources) != len(datos):
                self._guardar_cache(self.sources)
                print(f"Cache limpiado: se eliminaron {len(datos) - len(self.sources)} runs ajenas.")

            self._mostrar_runs("Datos locales cargados")
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
            print(f"No se pudo cargar el archivo local: {error}")
            self._actualizar_contadores()

    def _guardar_cache(self, sources):
        """Guarda la lista global y una copia por cuenta/servidor (cuentas/<cuenta>/<servidor>/runs.json)."""
        with self.archivo_cache.open("w", encoding="utf-8") as archivo:
            json.dump(sources, archivo, indent=4, ensure_ascii=False)

        mapa = cargar_mapa_personajes(self.base_dir)
        por_carpeta = defaultdict(list)
        for run in sources:
            por_carpeta[carpeta_personaje(self.base_dir, mapa, run.get("character"))].append(run)
        for carpeta, runs in por_carpeta.items():
            carpeta.mkdir(parents=True, exist_ok=True)
            with (carpeta / "runs.json").open("w", encoding="utf-8") as archivo:
                json.dump(runs, archivo, indent=4, ensure_ascii=False)

    def _actualizar_contadores(self):
        # Detalles
        if not self.sources:
            self.lbl_detalles.config(text=tr("Primero actualiza la lista de runs."), fg=tema.MUTED)
            self.btn_detalles.config(state="disabled")
        else:
            pendientes, ya = detalles_pendientes(self.base_dir, self.sources)
            if not pendientes:
                self.lbl_detalles.config(text=tr('✓ Tienes los {0} detalles de tus runs.', ya), fg=tema.OK)
                self.btn_detalles.config(state="disabled")
            else:
                self.lbl_detalles.config(
                    text=tr('Descargados: {0} de {1}  —  faltan {2}', ya, ya + len(pendientes), len(pendientes)), fg=tema.TEXTO)
                self.btn_detalles.config(state="normal")

        # Assets
        pendientes_a, total_a = assets_pendientes(self.base_dir)
        if total_a == 0:
            self.lbl_assets.config(text=tr("Primero descarga algunos detalles."), fg=tema.MUTED)
            self.btn_assets.config(state="disabled")
        elif not pendientes_a:
            self.lbl_assets.config(text=tr('✓ Tienes las {0} imágenes (en NC/assets).', total_a), fg=tema.OK)
            self.btn_assets.config(state="disabled")
        else:
            self.lbl_assets.config(
                text=tr('Descargadas: {0} de {1}  —  faltan {2}', total_a - len(pendientes_a), total_a, len(pendientes_a)),
                fg=tema.TEXTO)
            self.btn_assets.config(state="normal")

    def _mostrar_runs(self, mensaje):
        self.runs_guardadas = procesar_y_ordenar_runs(self.sources)
        opciones = [
            f"📅 {run['fecha']} | 👾 Bosses: {run['bossesKilled']} | ⏱️ {run['tiempo']}"
            for run in self.runs_guardadas
        ]
        self.combo_runs["values"] = opciones
        self.combo_runs.config(state="readonly")
        self.combo_runs.set("Selecciona una run...")
        self.lbl_estado_nc.config(text=tr('{0} ({1} runs)', mensaje, len(self.runs_guardadas)), fg=tema.OK)
        self._actualizar_contadores()

    def al_seleccionar_run(self, event):
        """Método que se ejecuta automáticamente al elegir una opción del desplegable"""
        indice = self.combo_runs.current()
        if 0 <= indice < len(self.runs_guardadas):
            run_elegida = self.runs_guardadas[indice]
            mapa = cargar_mapa_personajes(self.base_dir)
            ruta = ruta_detalle(self.base_dir, mapa, run_elegida)
            print(f"Run seleccionada ID: {run_elegida.get('id')}")
            print(f"Detalle: {ruta if ruta.exists() else 'no descargado'}")
            print(f"Resumen: {run_elegida}")

    def _bloquear_botones(self, bloquear):
        self.btn_ejecutar.config(state="disabled" if bloquear else "normal")
        if bloquear:
            self.btn_detalles.config(state="disabled")
            self.btn_assets.config(state="disabled")
        else:
            self._actualizar_contadores()

    # ============================================
    # 1. DESCARGAR LISTA (poca información)
    # ============================================

    def ejecutar_proceso(self):
        self._bloquear_botones(True)
        self.lbl_estado_nc.config(text=tr("Descargando lista de runs..."), fg=tema.INFO)
        prog = VentanaProgreso(self.top, "Actualizando lista de runs", cancelable=False)

        def tarea_hilo():
            try:
                sources = asyncio.run(obtener_sources_iniciales(self.perfil_path, progreso=prog.log))
                sources = _solo_propias(sources)
                if not sources:
                    raise RuntimeError(tr("La API no devolvió runs tuyas."))
                prog.log(tr("Guardando lista (global y por cuenta/servidor)..."))
                self._guardar_cache(sources)
            except Exception as error:
                prog.terminar(f"✗ {error}", ok=False)
                self.top.after(0, lambda: self._fin_tarea(False, "Error durante la carga"))
                return

            prog.terminar(tr('✓ Lista actualizada: {0} runs tuyas.', len(sources)), ok=True)
            self.top.after(0, lambda: self._fin_lista(sources))

        threading.Thread(target=tarea_hilo, daemon=True).start()

    def _fin_lista(self, sources):
        self.sources = sources
        self._mostrar_runs("Datos actualizados")
        self._bloquear_botones(False)

    def _fin_tarea(self, ok, mensaje):
        self.lbl_estado_nc.config(text=tr(mensaje), fg=tema.OK if ok else tema.ERR)
        self._bloquear_botones(False)

    # ============================================
    # 2. DESCARGAR DETALLES (harta información)
    # ============================================

    def descargar_detalles(self):
        if not self.sources:
            messagebox.showinfo(tr("Sin runs"), tr("Primero actualiza la lista de runs."), parent=self.top)
            return

        self._bloquear_botones(True)
        self.lbl_estado_nc.config(text=tr("Descargando detalles..."), fg=tema.INFO)
        prog = VentanaProgreso(self.top, "Descargando detalles de runs", cancelable=True)
        sources = list(self.sources)

        def tarea_hilo():
            try:
                descargadas, errores = asyncio.run(descargar_detalles_faltantes(
                    self.perfil_path, sources, self.base_dir,
                    progreso=prog.log, avance=prog.avance, cancelar=prog.cancelar,
                ))
            except Exception as error:
                prog.terminar(f"✗ {error}", ok=False)
                self.top.after(0, lambda: self._fin_tarea(False, "Error al descargar detalles"))
                return

            self._informar_fin(prog, descargadas, errores, "detalles nuevos")
            self.top.after(0, lambda: self._fin_tarea(True, "Detalles actualizados"))

        threading.Thread(target=tarea_hilo, daemon=True).start()

    # ============================================
    # 3. DESCARGAR IMÁGENES
    # ============================================

    def descargar_imagenes(self):
        self._bloquear_botones(True)
        self.lbl_estado_nc.config(text=tr("Descargando imágenes..."), fg=tema.INFO)
        prog = VentanaProgreso(self.top, "Descargando imágenes", cancelable=True)

        def tarea_hilo():
            try:
                descargadas, errores = asyncio.run(descargar_assets(
                    self.perfil_path, self.base_dir,
                    progreso=prog.log, avance=prog.avance, cancelar=prog.cancelar,
                ))
            except Exception as error:
                prog.terminar(f"✗ {error}", ok=False)
                self.top.after(0, lambda: self._fin_tarea(False, "Error al descargar imágenes"))
                return

            self._informar_fin(prog, descargadas, errores, "imágenes nuevas")
            self.top.after(0, lambda: self._fin_tarea(True, "Imágenes actualizadas"))

        threading.Thread(target=tarea_hilo, daemon=True).start()

    @staticmethod
    def _informar_fin(prog, descargadas, errores, que):
        # que: "detalles nuevos" / "imágenes nuevas"
        if errores:
            prog.terminar(tr('Terminado: {0} {1} y {2} errores (puedes reintentar).', descargadas, que, len(errores)), ok=False)
        elif prog.cancelar.is_set():
            prog.terminar(tr('Cancelado. Se alcanzaron a descargar {0} {1}.', descargadas, que), ok=False)
        else:
            prog.terminar(tr('✓ Listo: {0} {1}.', descargadas, que), ok=True)
