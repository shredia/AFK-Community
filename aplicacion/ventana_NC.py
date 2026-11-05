# aplicacion/ventana_NC.py
import tkinter as tk
from tkinter import ttk, messagebox
import asyncio
import threading
from navegador.scraper import descargar_runs
from navegador.parser import flatten
import pandas as pd
from pathlib import Path
from navegador.scraper import obtener_sources_iniciales
import json
from datetime import datetime

class Ventana_NC:
    def __init__(self, parent, perfil_path):
        self.parent = parent
        self.perfil_path = perfil_path
        
        self.top = tk.Toplevel(parent)
        self.top.title("Cargar Página y Datos NC")
        self.top.geometry("450x360")  # Aumentamos un poco la altura para que todo quepa bien
        self.top.resizable(False, False)
        self.top.grab_set()

        # Llamamos a la creación de la interfaz directamente
        self.crear_interfaz()

        self.verificar_y_cargar_cache()  # Verificamos si hay un archivo guardado y lo cargamos
    def crear_interfaz(self):
        # 1. Título principal
        tk.Label(self.top, text="Panel de Extracción de Datos NC", font=("Arial", 12, "bold")).pack(pady=10)

        # 2. Estado del proceso
        self.lbl_estado_nc = tk.Label(self.top, text="Listo para iniciar la descarga", fg="gray", font=("Arial", 10))
        self.lbl_estado_nc.pack(pady=5)

        # 3. Botón para actualizar la lista
        self.btn_ejecutar = ttk.Button(self.top, text="Actualizar lista de runs", command=self.ejecutar_proceso)
        self.btn_ejecutar.pack(pady=10)

        # 4. Etiqueta y Combobox (Desplegable)
        tk.Label(self.top, text="Runs filtradas (Mine = true):", font=("Arial", 9, "bold")).pack(anchor="w", padx=25, pady=(10, 2))
        
        self.variable_seleccionada = tk.StringVar()
        self.combo_runs = ttk.Combobox(
            self.top, 
            textvariable=self.variable_seleccionada, 
            state="disabled",  # Empieza deshabilitado hasta que haya datos
            width=50
        )
        self.combo_runs.set("Primero haz clic en actualizar...")
        self.combo_runs.pack(pady=5)

        # Vinculamos la selección
        self.combo_runs.bind("<<ComboboxSelected>>", self.al_seleccionar_run)


    def verificar_y_cargar_cache(self):
            """Busca si hay un archivo guardado localmente y lo carga en el desplegable"""
            ruta_archivo = Path("sources_guardados.json")  # O el nombre de tu archivo guardado
            
            if ruta_archivo.exists():
                try:
                    import json
                    with open(ruta_archivo, "r", encoding="utf-8") as f:
                        datos_brutos = json.load(f)
    
                    # Filtramos y procesamos (igual que cuando los descargas de la red)
                    runs_filtradas = [r for r in datos_brutos if r.get("mine") is True]
                    if runs_filtradas:
                        from navegador.parser import procesar_y_ordenar_runs  # Asegúrate de importar tu función
                        self.runs_guardadas = procesar_y_ordenar_runs(runs_filtradas)
    
                        opciones_visibles = [
                            f"📅 {r['fecha']} | 👾 Bosses: {r['bossesKilled']} | ⏱️ {r['tiempo']}" 
                            for r in self.runs_guardadas
                        ]
    
                        # Actualizamos el combobox
                        self.combo_runs['values'] = opciones_visibles
                        self.combo_runs.config(state="readonly")
                        self.combo_runs.set("Selecciona una run (Cargado local)...")
                        self.lbl_estado_nc.config(text=f"Datos locales cargados ({len(self.runs_guardadas)} runs)", fg="green")
                except Exception as e:
                    print(f"No se pudo cargar el archivo local: {e}")

    def al_seleccionar_run(self, event):
        """Método que se ejecuta automáticamente al elegir una opción del desplegable"""
        try:
            # 1. Obtenemos el índice numérico seleccionado en el Combobox
            indice = self.combo_runs.current()
            
            # 2. Verificamos de forma segura que la lista exista y tenga elementos
            if hasattr(self, 'runs_guardadas') and self.runs_guardadas and indice >= 0:
                if indice < len(self.runs_guardadas):
                    run_elegida = self.runs_guardadas[indice]
                    
                    # 3. Aquí puedes manejar la run seleccionada
                    print(f"Run seleccionada ID: {run_elegida.get('id')}")
                    print(f"Detalles: {run_elegida}")
                    
                    # Opcional: Mostrar un mensaje o actualizar alguna etiqueta en tu ventana
                    # self.lbl_estado_nc.config(text=f"Seleccionada: {run_elegida.get('fecha')}", fg="blue")
                    
        except Exception as e:
            print(f"Error al procesar la selección del Combobox: {e}")

    def ejecutar_proceso(self):
        self.btn_ejecutar.config(state="disabled")
        self.lbl_estado_nc.config(text="Procesando... Conectando al simulador...", fg="blue")

        def tarea_hilo():
            try:
                # Llamamos a tu función independiente usando asyncio.run
                sources = asyncio.run(obtener_sources_iniciales(perfil_path=self.perfil_path))

                if not sources:
                    self.top.after(0, lambda: self.lbl_estado_nc.config(text="No se obtuvieron sources.", fg="orange"))
                    self.top.after(0, lambda: self.btn_ejecutar.config(state="normal"))
                    return
                sources = asyncio.run(obtener_sources_iniciales(perfil_path=self.perfil_path))
                if sources:
                    # Guardamos inmediatamente en un archivo JSON
                    archivo_salida = Path("sources_guardados.json")
                    with open(archivo_salida, "w", encoding="utf-8") as f:
                        json.dump(sources, f, indent=4, ensure_ascii=False)
    
                    print(f"Guardado exitosamente en: {archivo_salida.resolve()}")

                # Actualizamos el estado con éxito en la interfaz
                self.top.after(0, lambda: self.lbl_estado_nc.config(text=f"¡Éxito! Se obtuvieron {len(sources)} elementos.", fg="green"))
                self.top.after(0, lambda: messagebox.showinfo("Éxito", f"Se cargaron {len(sources)} registros correctamente.", parent=self.top))
                self.top.after(0, lambda: self.btn_ejecutar.config(state="normal"))


            except Exception as e:
                # Si ocurre algún fallo (por sesión vencida, red, etc.)
                self.top.after(0, lambda: self.lbl_estado_nc.config(text="Error durante la carga", fg="red"))
                self.top.after(0, lambda: messagebox.showerror("Error crítico", str(e), parent=self.top))
                self.top.after(0, lambda: self.btn_ejecutar.config(state="normal"))

        # Lanzamos el hilo para evitar que la ventana se congele
        threading.Thread(target=tarea_hilo, daemon=True).start()




