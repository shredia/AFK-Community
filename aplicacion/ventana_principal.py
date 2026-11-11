# aplicacion/ventana_principal.py
import importlib
import sys
import time
import tkinter as tk
import traceback
from pathlib import Path
from tkinter import ttk, messagebox

import aplicacion.ventana_cuenta
import aplicacion.ventana_NC
import aplicacion.ventana_optimizador
import aplicacion.ventana_cuenta_actual
import aplicacion.ventana_guias
import aplicacion.ventana_fractura
from aplicacion import tema
from idiomas import tr, N_, idiomas_disponibles, idioma_actual, cambiar_idioma

# Módulos que se recargan en caliente, en orden de dependencias (primero los de abajo).
# Esta ventana principal NO se recarga: si la cambias, reinicia la app.
MODULOS_RECARGABLES = [
    "idiomas",
    "navegador.utils",
    "navegador.rutas",
    "navegador.visuales",
    "navegador.parser",
    "navegador.scraper",
    "navegador.optimizador",
    "navegador.cuenta",
    "navegador.reconocer",
    "navegador.guias",
    "navegador.guias_perfiles",
    "navegador.guias_datos",
    "aplicacion.tema",
    "aplicacion.imagenes",
    "aplicacion.ventana_progreso",
    "aplicacion.ventana_cuenta",
    "aplicacion.ventana_NC",
    "aplicacion.ventana_optimizador",
    "aplicacion.ventana_cuenta_actual",
    "aplicacion.ventana_perfil_guia",
    "aplicacion.ventana_guias",
    "navegador.actualizador",
    "aplicacion.ventana_actualizacion",
    "navegador.cdn",
    "navegador.fractura",
    "aplicacion.tienda_fractura",
    "aplicacion.vistas_fractura",
    "aplicacion.ventana_fractura",
]


# Tarjetas del menú, en el orden de uso recomendado
TARJETAS = [
    ("abrir_configuracion", N_("Acceso al sitio"),
     N_("Guarda tu correo y contraseña e inicia sesión en Esperian Archive."), "/game-ui/icon_hero_god.png"),
    ("abrir_cuenta_actual", N_("Mi cuenta"),
     N_("Fetch en el sitio y tus recursos, héroes, colecciones, equipo y mascotas."), "/game-ui/hero-screen/collection-3.webp"),
    ("accion_cargar_pagina", N_("Runs de NC"),
     N_("Descarga tus runs de Nightmare Corridor, sus detalles y las imágenes."), "/game-ui/hero-screen/boss-74.webp"),
    ("abrir_optimizador", N_("Optimizador NC"),
     N_("El mejor equipo por jefe sin repetir héroes, con builds y alternativas."), "/game-ui/hero-screen/boss-77.webp"),
    ("abrir_guias", N_("Guías"),
     N_("Planillas de la comunidad, con tus héroes marcados en cada sección."), "/game-ui/hero-screen/collection-10.webp"),
    ("abrir_fractura", N_("Fractura temporal"),
     N_("Planifica recompensas por piso, cofres de elección y tiendas de medallas."), "/game-ui/hero-screen/collection-1.webp"),
]


class VentanaPrincipal:
    def __init__(self, root):
        self.root = root
        tema.aplicar(root)
        self.root.title(tr("Esperian NC"))
        self.root.geometry("980x760")
        self.root.minsize(860, 600)
        # Ruta absoluta: funciona aunque se ejecute desde otra carpeta
        self.perfil_path = Path(__file__).resolve().parent.parent / "perfil_esperian"
        self.base_dir = self.perfil_path.parent
        self._fechas_modulos = self._leer_fechas_modulos()
        from aplicacion.imagenes import CacheImagenes
        self.imagenes = CacheImagenes()

        self._info_actualizacion = None
        self.crear_interfaz()
        self.actualizar_resumen()
        self.root.after(2000, self._revisar_actualizaciones)

    def crear_interfaz(self):
        cabecera = ttk.Frame(self.root)
        cabecera.pack(fill="x", padx=28, pady=(22, 6))
        ttk.Label(cabecera, text=tr("Esperian NC"), style="Titulo.TLabel").pack(anchor="w")
        ttk.Label(cabecera, text=tr("Tus runs de Nightmare Corridor, tu cuenta y las guías de la comunidad, en un solo lugar."),
                  style="Muted.TLabel", font=tema.FUENTE_SUBTITULO).pack(anchor="w", pady=(2, 0))

        rejilla = ttk.Frame(self.root)
        rejilla.pack(fill="both", expand=True, padx=22, pady=10)
        for i, (metodo, titulo, texto, imagen) in enumerate(TARJETAS):
            self._tarjeta(rejilla, i, metodo, titulo, texto, imagen).grid(
                row=i // 3, column=i % 3, sticky="nsew", padx=8, pady=8)
        for c in range(3):
            rejilla.columnconfigure(c, weight=1, uniform="tarjetas")

        flujo = ttk.Frame(rejilla, style="Tarjeta.TFrame", padding=14)
        n = len(TARJETAS)
        flujo.grid(row=n // 3, column=n % 3, sticky="nsew", padx=8, pady=8)
        ttk.Label(flujo, text=tr("Cómo empezar"), style="TarjetaTitulo.TLabel").pack(anchor="w")
        ttk.Label(flujo, style="TarjetaTexto.TLabel", justify="left", wraplength=250,
                  text=tr("1. Acceso al sitio: inicia sesión una vez.\n"
                       "2. Mi cuenta: haz fetch para traer tus datos.\n"
                       "3. Runs de NC: descarga lista y detalles.\n"
                       "4. Optimizador NC: arma tu mejor rotación.\n"
                       "5. Guías: compara con las recomendaciones.\n"
                       "6. Fractura temporal: planifica pisos y medallas.")).pack(anchor="w", pady=(6, 0))

        pie = ttk.Frame(self.root, style="Panel.TFrame", padding=(16, 8))
        pie.pack(fill="x", side="bottom")
        # aviso de versión nueva (se muestra solo si hay una)
        self.banner_act = ttk.Frame(self.root, style="Panel.TFrame", padding=(16, 6))
        self.lbl_banner_act = ttk.Label(self.banner_act, text="", style="Panel.TLabel", foreground=tema.DORADO)
        self.lbl_banner_act.pack(side="left")
        ttk.Button(self.banner_act, text=tr("Actualizar ahora"), style="Acento.TButton",
                   command=self._instalar_actualizacion).pack(side="right")
        if self._info_actualizacion:
            self._mostrar_banner(self._info_actualizacion)
        self.lbl_resumen = ttk.Label(pie, text="", style="Panel.TLabel")
        self.lbl_resumen.pack(side="left")
        ttk.Button(pie, text=tr("Salir"), command=self.root.quit).pack(side="right")
        from navegador.actualizador import version_local
        ttk.Button(pie, text=tr("⟳ v{0}", version_local()), command=self.abrir_actualizaciones).pack(
            side="right", padx=(0, 10))
        self._idiomas = idiomas_disponibles()
        self.combo_idioma = ttk.Combobox(pie, state="readonly", width=12,
                                         values=[nombre for _, nombre in self._idiomas])
        actual = next((i for i, (c, _) in enumerate(self._idiomas) if c == idioma_actual()), 0)
        if self._idiomas:
            self.combo_idioma.current(actual)
        self.combo_idioma.pack(side="right", padx=(0, 10))
        self.combo_idioma.bind("<<ComboboxSelected>>", lambda e: self._cambiar_idioma())
        ttk.Label(pie, text="🌐", style="Panel.TLabel").pack(side="right", padx=(10, 4))
        self.lbl_estado = ttk.Label(pie, text=tr("Los cambios de código se aplican al abrir una ventana."),
                                    style="Panel.TLabel", foreground=tema.MUTED)
        self.lbl_estado.pack(side="right", padx=14)

    def _tarjeta(self, padre, i, metodo, titulo, texto, imagen):
        marco = ttk.Frame(padre, style="Tarjeta.TFrame", padding=14)
        fila = ttk.Frame(marco, style="Panel.TFrame")
        fila.pack(fill="x")
        foto = self.imagenes.obtener(imagen, 56)
        ttk.Label(fila, image=foto, style="Tarjeta.TLabel").pack(side="left")
        textos = ttk.Frame(fila, style="Panel.TFrame")
        textos.pack(side="left", padx=12, fill="x", expand=True)
        ttk.Label(textos, text=f"{i + 1}", style="TarjetaPaso.TLabel", background=tema.DORADO,
                  padding=(7, 1)).pack(anchor="w")
        ttk.Label(textos, text=tr(titulo), style="TarjetaTitulo.TLabel").pack(anchor="w", pady=(4, 0))
        ttk.Label(marco, text=tr(texto), style="TarjetaTexto.TLabel", wraplength=250, justify="left").pack(
            anchor="w", pady=(10, 12))
        ttk.Button(marco, text=tr("Abrir  →"), style="Acento.TButton", command=getattr(self, metodo)).pack(anchor="w")
        # Toda la tarjeta es clicable
        for w in (marco, fila, textos):
            w.bind("<Button-1>", lambda e, m=metodo: getattr(self, m)())
        return marco

    def actualizar_resumen(self):
        """Pie: estado rápido de tus datos (sin conectarse)."""
        import json
        from navegador.cuenta import hace_cuanto
        partes = []
        cuentas = sorted((self.base_dir / "cuentas").glob("*/*/cuenta_actual.json"),
                         key=lambda p: p.stat().st_mtime, reverse=True)
        if cuentas:
            try:
                e = json.loads(cuentas[0].read_text(encoding="utf-8"))
                partes.append(tr("Cuenta: captura {0}", hace_cuanto(e.get('capturedAt'))))
            except (OSError, json.JSONDecodeError):
                pass
        else:
            partes.append(tr("Cuenta: sin sincronizar"))
        detalles = sum(1 for _ in (self.base_dir / "cuentas").glob("*/*/detalles/*.json"))
        partes.append(tr("Runs de NC con detalle: {0}", detalles))
        guias = sum(1 for _ in (self.base_dir / "guias").glob("*/guia.json"))
        partes.append(tr("Guías descargadas: {0}", guias))
        self.lbl_resumen.configure(text="   ·   ".join(partes))
        if getattr(self, "_tarea_resumen", None):
            try:
                self.root.after_cancel(self._tarea_resumen)
            except tk.TclError:
                pass
        self._tarea_resumen = self.root.after(60_000, self.actualizar_resumen)

    # ============================================
    # ACTUALIZACIONES (GitHub)
    # ============================================

    def _revisar_actualizaciones(self):
        """Al abrir: revisa en segundo plano (como mucho cada 12 h) si hay versión nueva publicada."""
        import threading
        from navegador import actualizador as act
        if not act.leer_token() or act.es_copia_desarrollo():
            return

        def trabajo():
            try:
                info = act.revisar(self.base_dir)
            except Exception:   # sin conexión, token vencido…: no molestar al abrir
                return
            if info:
                self.root.after(0, lambda: self._mostrar_banner(info))
        threading.Thread(target=trabajo, daemon=True).start()

    def _mostrar_banner(self, info):
        self._info_actualizacion = info
        try:
            self.lbl_banner_act.configure(text=tr("⬆ Hay una versión nueva disponible: {0}", info["version"]))
            self.banner_act.pack(fill="x", side="bottom")
        except tk.TclError:
            pass

    def _instalar_actualizacion(self):
        from aplicacion.ventana_actualizacion import instalar
        if self._info_actualizacion:
            instalar(self.root, self._info_actualizacion)

    def abrir_actualizaciones(self):
        from aplicacion.ventana_actualizacion import VentanaActualizacion
        VentanaActualizacion(self.root, self.base_dir)

    def _cambiar_idioma(self):
        i = self.combo_idioma.current()
        if i < 0:
            return
        cambiar_idioma(self._idiomas[i][0])
        # Redibujar el menú con el idioma nuevo (las demás ventanas lo toman al abrirse)
        for hijo in self.root.winfo_children():
            if not isinstance(hijo, tk.Toplevel):
                hijo.destroy()
        self.crear_interfaz()
        self.actualizar_resumen()

    # ============================================
    # RECARGA DE CÓDIGO EN CALIENTE
    # ============================================

    @staticmethod
    def _leer_fechas_modulos():
        fechas = {}
        for nombre in MODULOS_RECARGABLES:
            modulo = sys.modules.get(nombre)
            archivo = getattr(modulo, "__file__", None)
            if archivo:
                try:
                    fechas[nombre] = Path(archivo).stat().st_mtime
                except OSError:
                    pass
        return fechas

    def recargar_codigo_si_cambio(self):
        """
        Si algún archivo .py cambió desde la última vez, recarga los módulos.
        Si el código nuevo tiene un error, avisa y sigue usando la versión anterior.
        """
        actuales = self._leer_fechas_modulos()
        cambiados = [n for n in MODULOS_RECARGABLES if actuales.get(n) != self._fechas_modulos.get(n)]
        if not cambiados:
            return True

        try:
            # Se recargan todos en orden para que los dependientes tomen las versiones nuevas
            for nombre in MODULOS_RECARGABLES:
                if nombre in sys.modules:
                    importlib.reload(sys.modules[nombre])
                else:
                    importlib.import_module(nombre)
        except Exception:
            detalle = traceback.format_exc(limit=3)
            print(detalle)
            self.lbl_estado.config(text=tr("✗ El código modificado tiene un error (ver consola)."), foreground=tema.ERR)
            messagebox.showerror(
                tr("Error en el código"),
                "No se pudo recargar el código modificado. Corrige el error y vuelve a intentarlo.\n\n" + detalle,
                parent=self.root,
            )
            return False

        self._fechas_modulos = self._leer_fechas_modulos()
        archivos = ", ".join(n.split(".")[-1] + ".py" for n in cambiados)
        self.lbl_estado.config(text=tr('↻ Código recargado {0}: {1}', time.strftime('%H:%M:%S'), archivos), foreground=tema.INFO)
        print(f"Código recargado: {archivos}")
        return True

    # ============================================
    # ACCIONES
    # ============================================

    def abrir_configuracion(self):
        if self.recargar_codigo_si_cambio():
            aplicacion.ventana_cuenta.VentanaCuenta(self.root, self.perfil_path)

    def accion_cargar_pagina(self):
        if self.recargar_codigo_si_cambio():
            aplicacion.ventana_NC.Ventana_NC(self.root, self.perfil_path)

    def abrir_optimizador(self, carpeta=None, enfoque=None):
        if self.recargar_codigo_si_cambio():
            aplicacion.ventana_optimizador.VentanaOptimizador(self.root, self.perfil_path,
                                                              carpeta_inicial=carpeta, enfoque=enfoque)

    def abrir_guias(self):
        if self.recargar_codigo_si_cambio():
            aplicacion.ventana_guias.VentanaGuias(self.root, self.perfil_path,
                                                  abrir_optimizador=self.abrir_optimizador)

    def abrir_fractura(self):
        if self.recargar_codigo_si_cambio():
            aplicacion.ventana_fractura.VentanaFractura(self.root, self.perfil_path)

    def abrir_cuenta_actual(self):
        if self.recargar_codigo_si_cambio():
            aplicacion.ventana_cuenta_actual.VentanaCuentaActual(self.root, self.perfil_path,
                                                                 abrir_optimizador=self.abrir_optimizador)


def iniciar_aplicacion():
    root = tk.Tk()
    app = VentanaPrincipal(root)
    root.mainloop()
