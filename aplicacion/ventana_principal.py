# aplicacion/ventana_principal.py
import tkinter as tk
from tkinter import ttk, messagebox
from aplicacion.ventana_cuenta import VentanaCuenta # Importamos la sub-ventana desde el otro archivo
from aplicacion.ventana_NC import Ventana_NC # Importamos la sub-ventana desde el otro archivo
from navegador.scraper import configurar_cuenta  # Importamos para configurar la cuenta
from navegador.scraper import descargar_runs  # Importamos para descargar runs

class VentanaPrincipal:
    def __init__(self, root):
        self.root = root
        self.root.title("Gestor Esperian Archive")
        self.root.geometry("500x350")
        self.root.resizable(False, False)
        self.perfil_path = "./perfil_esperian"

        self.crear_interfaz()

    def crear_interfaz(self):
        # Título principal
        titulo = tk.Label(self.root, text="Panel Principal - Esperian", font=("Arial", 14, "bold"))
        titulo.pack(pady=20)

        # Marco de acciones principales
        frame_acciones = ttk.LabelFrame(self.root, text=" Menú de Opciones ")
        frame_acciones.pack(fill="x", padx=30, pady=10)

        # Botón que abre la sub-ventana de configuración
        btn_config = ttk.Button(frame_acciones, text="1. Configurar Cuenta y Credenciales", command=self.abrir_configuracion)
        btn_config.pack(fill="x", padx=20, pady=10)

        # 2. NUEVO: Botón para cargar la página (solo creado visualmente)
        btn_cargar = ttk.Button(frame_acciones, text="2. Cargar Página", command=self.accion_cargar_pagina)
        btn_cargar.pack(fill="x", padx=20, pady=10)

        # Botón de salida
        btn_salir = ttk.Button(frame_acciones, text="Salir de la Aplicación", command=self.root.quit)
        btn_salir.pack(fill="x", padx=20, pady=10)

        # Etiqueta de estado
        self.lbl_estado = tk.Label(self.root, text="Sistema listo", fg="gray", font=("Arial", 9))
        self.lbl_estado.pack(pady=20)

    def abrir_configuracion(self):
        # Llamamos a la sub-ventana pasándole la ventana principal como referencia
        VentanaCuenta(self.root, self.perfil_path)

    def accion_cargar_pagina(self):
        # Aquí iría la lógica para cargar la página
        Ventana_NC(self.root, self.perfil_path)

def iniciar_aplicacion():
    root = tk.Tk()
    app = VentanaPrincipal(root)
    root.mainloop()