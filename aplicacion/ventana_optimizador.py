# aplicacion/ventana_optimizador.py
"""Ventana del optimizador Nightmare Corridor: mejor equipo por jefe sin repetir héroes."""
import json
import unicodedata
from collections import Counter
import queue
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import ttk
from tkinter import font as tkfont

from navegador.optimizador import (
    Opciones,
    cargar_indice,
    construir_composiciones,
    rotacion_mas_reciente,
    catalogo,
    cargar_baneos,
    guardar_baneos,
    candidatos_por_jefe,
    optimizar,
    PROPIO,
    NOMBRES_ORIGEN,
    COPIA_TODAS,
    COPIA_NO_PROPIA,
    NOMBRES_COPIA,
)
from navegador.visuales import Visuales
from navegador.cuenta import cargar_cuenta_actual
from aplicacion.imagenes import CacheImagenes
from aplicacion import tema
from idiomas import tr, N_

TAM_HEROE = 50
TAM_DETALLE = 96
TAM_JEFE = 50
TAM_EQUIPO = 40
TAM_ICONO = 18
TAM_RETRATO = 56          # ancho del retrato compuesto (alto ≈ 1,33×)
TAM_RETRATO_DETALLE = 120
# Tamaño de íconos de las tarjetas: (ancho del retrato, tarjetas por fila)
TAMANOS = {"Pequeño": (56, 2), "Mediano": (84, 1), "Grande": (108, 1), "Muy grande": (136, 1)}
ARCHIVO_PREFERENCIAS = "preferencias.json"


def cargar_preferencia(base_dir, clave, defecto=None):
    try:
        return json.loads((Path(base_dir) / ARCHIVO_PREFERENCIAS).read_text(encoding="utf-8")).get(clave, defecto)
    except (OSError, json.JSONDecodeError, AttributeError):
        return defecto


def guardar_preferencia(base_dir, clave, valor):
    archivo = Path(base_dir) / ARCHIVO_PREFERENCIAS
    try:
        datos = json.loads(archivo.read_text(encoding="utf-8")) if archivo.exists() else {}
    except (OSError, json.JSONDecodeError):
        datos = {}
    datos[clave] = valor
    try:
        archivo.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


# ============================================================
# UTILIDADES
# ============================================================

def fecha_local(iso):
    if not iso:
        return "—"
    try:
        return datetime.fromisoformat(str(iso).replace("Z", "+00:00")).astimezone().strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return str(iso)


def _oscurecer(hex_color, factor=1.0):
    """Los colores de calidad del sitio son claros (fondo oscuro); se oscurecen para fondo blanco."""
    try:
        h = hex_color.lstrip("#")
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
        return "#%02x%02x%02x" % (int(r * factor), int(g * factor), int(b * factor))
    except (ValueError, AttributeError):
        return tema.TEXTO


def _nombre_con_origen(h):
    origen = h.get("origen") or PROPIO
    if origen == PROPIO:
        return h.get("name", "?")
    corto = {"prestado": "prestado", "prueba": "prueba", "temporal": "prestado/prueba",
             "fuera_roster": "ya no lo tienes"}.get(origen, origen)
    return f"{h.get('name', '?')} ({corto})"


def formato_tiempo(segundos):
    """23.391 -> '23.391 s' · 132.393 -> '2m 12.393 s' (se mantienen los milisegundos)."""
    if segundos is None:
        return "—"
    minutos, resto = divmod(round(float(segundos), 3), 60)
    if minutos < 1:
        return f"{resto:.3f} s"
    return f"{int(minutos)}m {resto:06.3f} s"


def _normalizar_texto(texto):
    texto = unicodedata.normalize("NFD", str(texto).lower())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def orden_boss(boss):
    return (0, int(boss)) if str(boss).isdigit() else (1, str(boss))


def listar_servidores(base_dir):
    """[(etiqueta, carpeta_servidor)] de los servidores que tienen detalles descargados."""
    resultado = []
    for carpeta_detalles in sorted((Path(base_dir) / "cuentas").glob("*/*/detalles")):
        carpeta = carpeta_detalles.parent
        n = sum(1 for _ in carpeta_detalles.glob("*.json"))
        if not n:
            continue
        nombre = carpeta.name
        archivo = carpeta / f"{carpeta.name}.json"
        if archivo.exists():
            try:
                nombre = json.loads(archivo.read_text(encoding="utf-8")).get("name") or nombre
            except (OSError, json.JSONDecodeError):
                pass
        resultado.append((f"{nombre} · Servidor {carpeta.name} ({n} runs)", carpeta))
    return resultado


class MarcoDesplazable(ttk.Frame):
    """Frame con barra de desplazamiento vertical."""

    def __init__(self, parent):
        super().__init__(parent)
        self.canvas = tk.Canvas(self, highlightthickness=0)
        barra = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.interior = ttk.Frame(self.canvas)
        self.interior.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self._ventana = self.canvas.create_window((0, 0), window=self.interior, anchor="nw")
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._ventana, width=e.width))
        self.canvas.configure(yscrollcommand=barra.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")
        self.interior.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", self._rueda))
        self.interior.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))

    def _rueda(self, evento):
        self.canvas.yview_scroll(int(-evento.delta / 120), "units")


class TarjetaEquipo(ttk.LabelFrame):
    """Muestra un equipo (5 héroes + mascota) contra un jefe."""

    def __init__(self, parent, imagenes, al_elegir, al_alternativas=None, vis=None, tam=TAM_RETRATO):
        super().__init__(parent, text=" — ")
        self.tam = tam                              # ancho del retrato
        self.tam_jefe = max(TAM_JEFE, int(tam * 0.9))
        self.con_equipo = tam >= 80                 # fila de equipo bajo el retrato si hay espacio
        self.imagenes = imagenes
        self.al_elegir = al_elegir
        self.vis = vis
        self.comp = None

        fila = ttk.Frame(self)
        fila.pack(fill="x", padx=6, pady=4)
        # Jefe (imagen + nombre)
        jefe = ttk.Frame(fila)
        jefe.pack(side="left", padx=(0, 8))
        self.lbl_jefe_img = ttk.Label(jefe, image=self.imagenes.obtener(None, self.tam_jefe))
        self.lbl_jefe_img.pack()
        self.lbl_jefe_nombre = ttk.Label(jefe, text="", font=("Arial", 9 if tam >= 80 else 8, "bold"), wraplength=self.tam_jefe + 10,
                                         justify="center")
        self.lbl_jefe_nombre.pack()
        ttk.Separator(fila, orient="vertical").pack(side="left", fill="y", padx=(0, 8))
        fila = ttk.Frame(fila)
        fila.pack(side="left")
        self.botones_heroe = []
        for i in range(5):
            b = ttk.Button(fila, compound="top", command=lambda i=i: self._click_heroe(i))
            b.grid(row=0, column=i, padx=1)
            self.botones_heroe.append(b)
        ttk.Separator(fila, orient="vertical").grid(row=0, column=5, sticky="ns", padx=4)
        self.boton_mascota = ttk.Button(fila, compound="top", command=self._click_mascota)
        self.boton_mascota.grid(row=0, column=6, padx=1)

        pie = ttk.Frame(self)
        pie.pack(fill="x", padx=6, pady=(0, 4))
        self.lbl_pie = ttk.Label(pie, text="", foreground=tema.MUTED)
        self.lbl_pie.pack(side="left")
        if al_alternativas:
            ttk.Button(pie, text=tr("Ver alternativas"), command=lambda: al_alternativas(self.comp)).pack(side="right")

    def mostrar(self, comp, titulo, boss_id=None):
        self.comp = comp
        self.configure(text=f" {titulo} ")
        boss_id = comp.boss_id if comp else boss_id
        if self.vis and boss_id:
            nombre, url = self.vis.jefe(boss_id)
            self.lbl_jefe_img.configure(image=self.imagenes.obtener(url, self.tam_jefe))
            self.lbl_jefe_nombre.configure(text=tr(nombre))
        else:
            self.lbl_jefe_img.configure(image=self.imagenes.obtener(None, self.tam_jefe))
            self.lbl_jefe_nombre.configure(text="")
        for i, boton in enumerate(self.botones_heroe):
            if comp and i < len(comp.heroes):
                h = comp.heroes[i]
                nombre = h.get("name", "?")
                corto = nombre.split(" - ")[0]
                imagen = (self.imagenes.retrato(h, self.vis, comp.golden, self.tam, con_equipo=self.con_equipo)
                          if self.vis and self.vis.disponible else self.imagenes.obtener(h.get("imageUrl"), self.tam))
                boton.configure(image=imagen, text=tr(corto[:max(9, self.tam // 7)]), state="normal")
            else:
                boton.configure(image=self.imagenes.obtener(None, self.tam), text="", state="disabled")
        if comp and comp.mascota:
            self.boton_mascota.configure(image=self.imagenes.obtener(comp.mascota.get("imageUrl"), self.tam),
                                         text=tr(str(comp.mascota.get("name", "?"))[:max(9, self.tam // 7)]),
                                         state="normal")
        else:
            self.boton_mascota.configure(image=self.imagenes.obtener(None, self.tam), text="", state="disabled")
        if comp:
            self.lbl_pie.configure(text=f"{fecha_local(comp.fecha)} · rotación {comp.rotacion} · "
                                        f"usado {comp.veces} {'vez' if comp.veces == 1 else 'veces'}"
                                        + (f" · ⚠ {len(comp.no_propios)} héroe(s) no propio(s)"
                                           if comp.no_propios else ""))
        else:
            self.lbl_pie.configure(text="")

    def _click_heroe(self, i):
        if self.comp and i < len(self.comp.heroes):
            self.al_elegir(self.comp, self.comp.heroes[i], "HEROE")

    def _click_mascota(self):
        if self.comp and self.comp.mascota:
            self.al_elegir(self.comp, self.comp.mascota, "MASCOTA")


# ============================================================
# VENTANA PRINCIPAL DEL OPTIMIZADOR
# ============================================================

class VentanaOptimizador:
    def __init__(self, parent, perfil_path, carpeta_inicial=None, enfoque=None):
        """enfoque: {'texto': 'Thalassa', 'boss': '76'} -> abre Explorar filtrado (desde Cuenta actual)."""
        self.parent = parent
        self._enfoque_pendiente = enfoque
        self.base_dir = Path(perfil_path).parent
        self.imagenes = CacheImagenes()
        self.vis = Visuales(self.base_dir)
        self._tamano = cargar_preferencia(self.base_dir, "tamano_iconos", "Grande")
        if self._tamano not in TAMANOS:
            self._tamano = "Grande"
        self.servidores = listar_servidores(self.base_dir)
        self.carpeta = None
        self.runs, self.comps, self.refs = [], [], {}
        self.baneos = []
        self.resultado = None
        self.explorar_lista = []
        self.seleccion = None   # (comp, objeto, tipo) mostrado en el panel de detalle
        self._cola = queue.Queue()
        self._ocupado = False

        self.top = tk.Toplevel(parent)
        self.top.title(tr("Optimizador NC"))
        self.top.geometry("1600x960")
        self.top.minsize(1100, 700)

        self.crear_interfaz()
        self.top.after(100, self._procesar_cola)

        if not self.servidores:
            self.lbl_estado.configure(
                text=tr("No hay detalles descargados. Usa 'Runs de NC' → 'Descargar detalles faltantes'."),
                foreground=tema.ERR)
        else:
            indice = 0
            if carpeta_inicial is not None:
                for i, (_, carpeta) in enumerate(self.servidores):
                    if Path(carpeta) == Path(carpeta_inicial):
                        indice = i
            self.combo_servidor.current(indice)
            self.cargar_servidor()

    # ---------------- comunicación con hilos ----------------

    def _en_ui(self, funcion):
        self._cola.put(funcion)

    def _procesar_cola(self):
        try:
            while True:
                self._cola.get_nowait()()
        except queue.Empty:
            pass
        try:
            self.top.after(100, self._procesar_cola)
        except tk.TclError:
            pass

    def _estado(self, texto, color=tema.TEXTO):
        self.lbl_estado.configure(text=tr(texto), foreground=color)

    # ---------------- interfaz ----------------

    def crear_interfaz(self):
        cfg = ttk.LabelFrame(self.top, text=tr(" Configuración "))
        cfg.pack(fill="x", padx=10, pady=(10, 4))

        # Fila 1: servidor y rotación
        f1 = ttk.Frame(cfg)
        f1.pack(fill="x", padx=8, pady=4)
        ttk.Label(f1, text=tr("Servidor:")).pack(side="left")
        self.combo_servidor = ttk.Combobox(f1, state="readonly", width=42,
                                           values=[etq for etq, _ in self.servidores])
        self.combo_servidor.pack(side="left", padx=(4, 16))
        self.combo_servidor.bind("<<ComboboxSelected>>", lambda e: self.cargar_servidor())

        ttk.Label(f1, text=tr("Rotación (Boss ID):")).pack(side="left")
        self.combos_rotacion = []
        for i in range(6):
            c = ttk.Combobox(f1, width=5)
            c.pack(side="left", padx=2)
            c.bind("<<ComboboxSelected>>", lambda e: self._actualizar_nombres_rotacion())
            c.bind("<KeyRelease>", lambda e: self._actualizar_nombres_rotacion())
            self.combos_rotacion.append(c)
        ttk.Button(f1, text=tr("Más reciente"), command=self.usar_rotacion_reciente).pack(side="left", padx=6)
        self.lbl_nombres_rotacion = ttk.Label(cfg, text="", foreground=tema.MUTED)
        self.lbl_nombres_rotacion.pack(anchor="w", padx=8)
        if not self.vis.disponible:
            ttk.Label(cfg, foreground=tema.WARN,
                      text=tr("Sin tablas del sitio: en 'Runs de NC' pulsa 'Descargar imágenes faltantes' "
                           "para ver jefes, equipo y afijos con nombre e imagen.")).pack(anchor="w", padx=8)

        # Fila 2: opciones y acciones
        f2 = ttk.Frame(cfg)
        f2.pack(fill="x", padx=8, pady=(0, 6))
        self.var_completas = tk.BooleanVar(value=True)
        self.var_mascota = tk.BooleanVar(value=True)
        self.var_limite = tk.IntVar(value=0)
        self.var_tiempo = tk.IntVar(value=60)
        ttk.Checkbutton(f2, text=tr("Solo runs completas"), variable=self.var_completas).pack(side="left")
        ttk.Checkbutton(f2, text=tr("Prohibir repetir mascotas"), variable=self.var_mascota).pack(side="left", padx=12)
        f3 = ttk.Frame(cfg)
        f3.pack(fill="x", padx=8, pady=(0, 6))
        self.var_excluir_temp = tk.BooleanVar(value=cargar_preferencia(self.base_dir, "excluir_temporales", False))
        self.var_excluir_fuera = tk.BooleanVar(value=cargar_preferencia(self.base_dir, "excluir_fuera_roster", False))
        ttk.Checkbutton(f3, text=tr("Excluir equipos con héroes prestados / de prueba"), variable=self.var_excluir_temp,
                        command=self._al_cambiar_filtros).pack(side="left")
        ttk.Checkbutton(f3, text=tr("Excluir equipos con héroes que ya no están en tu roster"),
                        variable=self.var_excluir_fuera, command=self._al_cambiar_filtros).pack(side="left", padx=12)
        self.lbl_no_propios = ttk.Label(f3, text="", foreground=tema.MUTED)
        self.lbl_no_propios.pack(side="left", padx=8)
        ttk.Label(f2, text=tr("Límite por jefe (0 = todas):")).pack(side="left")
        ttk.Spinbox(f2, from_=0, to=9999, width=6, textvariable=self.var_limite).pack(side="left", padx=(2, 12))
        ttk.Label(f2, text=tr("Tiempo máx. búsqueda (s):")).pack(side="left")
        ttk.Spinbox(f2, from_=1, to=3600, width=6, textvariable=self.var_tiempo).pack(side="left", padx=(2, 12))
        self.btn_baneos = ttk.Button(f2, text=tr("Baneos (0)"), command=self.abrir_baneos)
        self.btn_baneos.pack(side="left", padx=4)
        self.btn_optimizar = ttk.Button(f2, text=tr("▶ Optimizar"), command=self.ejecutar_optimizacion)
        self.btn_optimizar.pack(side="left", padx=4)

        self.lbl_estado = ttk.Label(self.top, text="", font=("Arial", 10, "bold"))
        self.lbl_estado.pack(fill="x", padx=12, pady=2)

        # Cuerpo: pestañas a la izquierda, detalle a la derecha
        cuerpo = ttk.PanedWindow(self.top, orient="horizontal")
        cuerpo.pack(fill="both", expand=True, padx=10, pady=(4, 10))

        self.notebook = ttk.Notebook(cuerpo)
        cuerpo.add(self.notebook, weight=3)
        self._crear_tab_optimo()
        self._crear_tab_explorar()
        self._crear_tab_builds()

        self._crear_panel_detalle(cuerpo)

    def _crear_tab_optimo(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=tr("  Óptimo (6 jefes)  "))
        arriba = ttk.Frame(tab)
        arriba.pack(fill="x", padx=8, pady=6)
        self.lbl_resumen = ttk.Label(arriba, text=tr("Pulsa ▶ Optimizar."), font=("Arial", 10))
        self.lbl_resumen.pack(side="left")
        self.combo_tamano = ttk.Combobox(arriba, state="readonly", width=11, values=list(TAMANOS))
        self.combo_tamano.set(self._tamano)
        self.combo_tamano.pack(side="right")
        self.combo_tamano.bind("<<ComboboxSelected>>", lambda e: self.cambiar_tamano(self.combo_tamano.get()))
        ttk.Label(arriba, text=tr("Tamaño de íconos:")).pack(side="right", padx=4)

        self.marco_optimo = MarcoDesplazable(tab)
        self.marco_optimo.pack(fill="both", expand=True)
        self.tarjetas = []
        self._contenido_tarjetas = [(None, f"Jefe {i + 1}", None) for i in range(6)]
        self._construir_tarjetas()

    def _construir_tarjetas(self):
        """(Re)crea las 6 tarjetas con el tamaño elegido: 1 por fila si son grandes, 2 si son pequeñas."""
        for t in self.tarjetas:
            t.destroy()
        tam, columnas = TAMANOS[self._tamano]
        interior = self.marco_optimo.interior
        for c in range(2):
            interior.columnconfigure(c, weight=1 if c < columnas else 0)
        self.tarjetas = []
        for i in range(6):
            t = TarjetaEquipo(interior, self.imagenes, self.mostrar_detalle, self.ver_alternativas, self.vis, tam=tam)
            t.grid(row=i // columnas, column=i % columnas, sticky="nsew", padx=6, pady=6)
            comp, titulo, boss = self._contenido_tarjetas[i]
            t.mostrar(comp, titulo, boss_id=boss)
            self.tarjetas.append(t)

    def cambiar_tamano(self, tamano):
        if tamano not in TAMANOS or tamano == self._tamano:
            return
        self._tamano = tamano
        guardar_preferencia(self.base_dir, "tamano_iconos", tamano)
        self._construir_tarjetas()
        if hasattr(self, "tarjeta_explorar"):
            comp_actual = self.tarjeta_explorar.comp
            titulo = self.tarjeta_explorar.cget("text").strip()
            self.tarjeta_explorar.destroy()
            self.tarjeta_explorar = TarjetaEquipo(self.tab_explorar, self.imagenes, self.mostrar_detalle,
                                                  vis=self.vis, tam=TAMANOS[tamano][0])
            self.tarjeta_explorar.pack(fill="x", padx=8, pady=8)
            self.tarjeta_explorar.mostrar(comp_actual, titulo or "—")

    def _crear_tab_explorar(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=tr("  Explorar por jefe  "))
        self.tab_explorar = tab

        arriba = ttk.Frame(tab)
        arriba.pack(fill="x", padx=8, pady=6)
        ttk.Label(arriba, text=tr("Jefe:")).pack(side="left")
        self.combo_jefe = ttk.Combobox(arriba, state="readonly", width=34)
        self.combo_jefe.pack(side="left", padx=4)
        self.combo_jefe.bind("<<ComboboxSelected>>", lambda e: self.actualizar_explorar())
        ttk.Label(arriba, text=tr("Héroe o colección:")).pack(side="left", padx=(12, 2))
        self.var_filtro_explorar = tk.StringVar()
        filtro = ttk.Entry(arriba, textvariable=self.var_filtro_explorar, width=22)
        filtro.pack(side="left")
        self.var_filtro_explorar.trace_add("write", lambda *a: self.actualizar_explorar())
        ttk.Button(arriba, text="✕", width=3, command=lambda: self.var_filtro_explorar.set("")).pack(side="left")
        self.lbl_explorar = ttk.Label(arriba, text="", foreground=tema.MUTED)
        self.lbl_explorar.pack(side="left", padx=10)
        ttk.Label(arriba, text=tr("(usa los mismos filtros y baneos de arriba)"), foreground=tema.MUTED).pack(side="right")

        columnas = ("n", "tiempo", "heroes", "mascota", "veces", "fecha", "rotacion")
        self.tabla_explorar = ttk.Treeview(tab, columns=columnas, show="headings", height=9)
        for col, titulo, ancho, anchor in (
            ("n", N_("#"), 40, "center"), ("tiempo", N_("Tiempo"), 95, "center"),
            ("heroes", N_("Héroes"), 430, "w"), ("mascota", N_("Mascota"), 130, "w"),
            ("veces", N_("Usos"), 50, "center"), ("fecha", N_("Mejor run"), 120, "center"),
            ("rotacion", N_("Rotación"), 130, "center"),
        ):
            self.tabla_explorar.heading(col, text=tr(titulo))
            self.tabla_explorar.column(col, width=ancho, anchor=anchor, stretch=(col == "heroes"))
        self.tabla_explorar.pack(fill="both", expand=True, padx=8)
        self.tabla_explorar.bind("<<TreeviewSelect>>", self._al_elegir_explorar)

        self.tarjeta_explorar = TarjetaEquipo(tab, self.imagenes, self.mostrar_detalle, vis=self.vis,
                                              tam=TAMANOS[self._tamano][0])
        self.tarjeta_explorar.pack(fill="x", padx=8, pady=8)

    def _crear_tab_builds(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=tr("  Colecciones, equipo y muebles  "))
        ttk.Label(tab, text=tr("Builds de los 30 héroes de la solución óptima. Equipo: W/H/B/F = arma/casco/"
                            "cuerpo/botas · M/T1..T5 = tier · ★ = estrellas · SP = usa su Special Power. "
                            "Clic en una fila para ver el detalle."),
                  foreground=tema.MUTED).pack(anchor="w", padx=8, pady=6)
        columnas = ("jefe", "heroe", "sp", "si", "grabado", "muebles", "coleccion", "col_nivel", "equipo")
        self.tabla_builds = ttk.Treeview(tab, columns=columnas, show="headings")
        for col, titulo, ancho in (
            ("jefe", N_("Jefe"), 140), ("heroe", N_("Héroe"), 180), ("sp", N_("SP"), 45), ("si", N_("SI"), 35),
            ("grabado", N_("Grabado"), 55), ("muebles", N_("Muebles"), 75), ("coleccion", N_("Colección"), 190),
            ("col_nivel", N_("★ · Míticos"), 75), ("equipo", N_("Equipo"), 230),
        ):
            self.tabla_builds.heading(col, text=tr(titulo))
            self.tabla_builds.column(col, width=ancho, anchor="w" if col in ("heroe", "coleccion", "equipo") else "center")
        barra = ttk.Scrollbar(tab, orient="vertical", command=self.tabla_builds.yview)
        self.tabla_builds.configure(yscrollcommand=barra.set)
        self.tabla_builds.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=(0, 8))
        barra.pack(side="right", fill="y", pady=(0, 8))
        self.tabla_builds.bind("<<TreeviewSelect>>", self._al_elegir_build)
        self._builds_items = {}

    def _crear_panel_detalle(self, cuerpo):
        panel = ttk.LabelFrame(cuerpo, text=tr(" Detalle "))
        cuerpo.add(panel, weight=2)

        cabecera = ttk.Frame(panel)
        cabecera.pack(fill="x", padx=8, pady=8)
        self.lbl_img_detalle = ttk.Label(cabecera, image=self.imagenes.obtener(None, TAM_DETALLE))
        self.lbl_img_detalle.pack(side="left")
        self.lbl_nombre_detalle = ttk.Label(cabecera, text=tr("Haz clic en un héroe o mascota"),
                                            font=("Arial", 13, "bold"), wraplength=320)
        self.lbl_nombre_detalle.pack(side="left", padx=10)

        botones = ttk.Frame(panel)
        botones.pack(fill="x", padx=8)
        self.btn_ban_todos = ttk.Button(botones, text=tr("Banear en todos los jefes"),
                                        command=lambda: self.banear_seleccion(todos=True), state="disabled")
        self.btn_ban_todos.pack(side="left")
        self.btn_ban_jefe = ttk.Button(botones, text=tr("Banear solo en este jefe"),
                                       command=lambda: self.banear_seleccion(todos=False), state="disabled")
        self.btn_ban_jefe.pack(side="left", padx=6)
        self.btn_ban_copia = ttk.Button(botones, text=tr("Banear solo la copia prestada/prueba"),
                                        command=lambda: self.banear_seleccion(todos=True, solo_copia=True),
                                        state="disabled")
        self.btn_ban_copia.pack(side="left")

        marco = ttk.Frame(panel)
        marco.pack(fill="both", expand=True, padx=8, pady=8)
        self.txt_detalle = tk.Text(marco, wrap="word", font=("Consolas", 10), state="disabled", width=52)
        barra = ttk.Scrollbar(marco, command=self.txt_detalle.yview)
        self.txt_detalle.configure(yscrollcommand=barra.set)
        self.txt_detalle.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")
        self.txt_detalle.tag_configure("titulo", font=("Arial", 10, "bold"), spacing1=8)
        self.txt_detalle.tag_configure("gris", foreground=tema.MUTED)
        self.txt_detalle.tag_configure("negrita", font=("Arial", 9, "bold"))
        self.txt_detalle.tag_configure("grande", font=("Arial", 11, "bold"))
        self.txt_detalle.tag_configure("tier", foreground=tema.DORADO, font=("Arial", 9, "bold"))
        self.txt_detalle.tag_configure("sp_si", foreground=tema.DORADO, font=("Arial", 9, "bold"))
        self.txt_detalle.tag_configure("sp_no", foreground=tema.ERR)
        # Sangría colgante: las líneas largas continúan alineadas con el valor, no bajo la etiqueta
        ancho_etiqueta = tkfont.Font(font=("Consolas", 10)).measure(" " * 16)
        self.txt_detalle.tag_configure("fila", lmargin2=ancho_etiqueta)
        self.txt_detalle.tag_configure("parrafo", lmargin2=tkfont.Font(font=("Consolas", 10)).measure("    "),
                                       spacing3=4)

    # ---------------- carga de datos ----------------

    def cargar_servidor(self):
        indice = self.combo_servidor.current()
        if indice < 0 or self._ocupado:
            return
        self.carpeta = self.servidores[indice][1]
        self._ocupado = True
        self.btn_optimizar.configure(state="disabled")
        self._estado(tr("Cargando runs del servidor..."), tema.INFO)
        carpeta = self.carpeta

        def tarea():
            try:
                datos = cargar_indice(carpeta, progreso=lambda m: self._en_ui(lambda: self._estado(m, tema.INFO)))
                actual = cargar_cuenta_actual(carpeta) or {}
                comps = construir_composiciones(datos["runs"], actual.get("heroes_temporales") or ())
            except Exception as error:
                mensaje = str(error)
                self._en_ui(lambda: self._fin_carga(None, None, mensaje))
                return
            self._en_ui(lambda: self._fin_carga(datos, comps, None))

        threading.Thread(target=tarea, daemon=True).start()

    def _fin_carga(self, datos, comps, error):
        self._ocupado = False
        self.btn_optimizar.configure(state="normal")
        if error:
            self._estado(tr('Error al cargar: {0}', error), tema.ERR)
            return
        self.runs, self.refs, self.comps = datos["runs"], datos["refs"], comps
        self.baneos = cargar_baneos(self.carpeta)
        self._actualizar_boton_baneos()

        bosses = sorted({c.boss_id for c in comps}, key=orden_boss)
        for combo in self.combos_rotacion:
            combo.configure(values=bosses)
        self.combo_jefe.configure(values=[self._etiqueta_jefe(b) for b in bosses])
        self._actualizar_conteo_no_propios()
        self.usar_rotacion_reciente()
        if bosses:
            self.combo_jefe.set(self._etiqueta_jefe(bosses[0]))
        completas = sum(1 for r in self.runs
                        if (r.get("result") or {}).get("bossesKilled") == 6)
        self._estado(tr('✓ {0} runs cargadas ({1} completas), {2} composiciones, {3} jefes distintos.', len(self.runs), completas, len(comps), len(bosses)), tema.OK)
        self.actualizar_explorar()
        if self._enfoque_pendiente:
            enfoque, self._enfoque_pendiente = self._enfoque_pendiente, None
            self.enfocar(enfoque.get("texto", ""), enfoque.get("boss"))

    def enfocar(self, texto, boss=None):
        """Abre 'Explorar por jefe' filtrado por un héroe/colección (y un jefe, si se indica)."""
        if boss:
            self.combo_jefe.set(self._etiqueta_jefe(boss))
        self.var_filtro_explorar.set(texto)
        self.actualizar_explorar()
        self.notebook.select(self.tab_explorar)

    def _al_cambiar_filtros(self):
        guardar_preferencia(self.base_dir, "excluir_temporales", self.var_excluir_temp.get())
        guardar_preferencia(self.base_dir, "excluir_fuera_roster", self.var_excluir_fuera.get())
        self.actualizar_explorar()
        self._estado(tr("Filtros cambiados. Pulsa ▶ Optimizar para recalcular."), tema.WARN)

    def _actualizar_conteo_no_propios(self):
        conteo = Counter()
        for c in self.comps:
            for h, o in c.no_propios:
                conteo[(h.get("name", "?").split(" - ")[0], o)] += 1
        if not conteo:
            self.lbl_no_propios.configure(text=tr("(tus runs usan solo héroes propios)"))
            return
        partes = [f"{n} {NOMBRES_ORIGEN.get(o, o).split(' (')[0].lower()} ×{v}" for (n, o), v in conteo.most_common(6)]
        self.lbl_no_propios.configure(text="En tus runs: " + ", ".join(partes))

    def usar_rotacion_reciente(self):
        rot = rotacion_mas_reciente(self.runs)
        for combo, boss in zip(self.combos_rotacion, rot + [""] * 6):
            combo.set(boss)
        self._actualizar_nombres_rotacion()

    def _etiqueta_jefe(self, boss_id):
        return f"{boss_id} · {self.vis.jefe(boss_id)[0]}" if self.vis.disponible else str(boss_id)

    @staticmethod
    def _id_de_etiqueta(etiqueta):
        return str(etiqueta).split(" · ", 1)[0].strip()

    def _actualizar_nombres_rotacion(self):
        if not self.vis.disponible:
            return
        nombres = [f"{i}. {self.vis.jefe(c.get().strip())[0]}" if c.get().strip() else f"{i}. —"
                   for i, c in enumerate(self.combos_rotacion, 1)]
        self.lbl_nombres_rotacion.configure(text="   ".join(nombres))

    def _opciones(self):
        try:
            limite = max(0, int(self.var_limite.get()))
        except (tk.TclError, ValueError):
            limite = 0
        try:
            tiempo = max(1, int(self.var_tiempo.get()))
        except (tk.TclError, ValueError):
            tiempo = 60
        return Opciones(
            solo_completas=self.var_completas.get(),
            prohibir_repetir_mascota=self.var_mascota.get(),
            excluir_temporales=self.var_excluir_temp.get(),
            excluir_fuera_roster=self.var_excluir_fuera.get(),
            limite_por_jefe=limite,
            tiempo_maximo=tiempo,
        )

    # ---------------- optimización ----------------

    def ejecutar_optimizacion(self):
        if self._ocupado or not self.comps:
            return
        rotacion = [c.get().strip() for c in self.combos_rotacion]
        opciones = self._opciones()
        baneos = list(self.baneos)
        comps = self.comps
        self._ocupado = True
        self.btn_optimizar.configure(state="disabled")
        self._estado(tr('Optimizando rotación {0}...', '-'.join(rotacion)), tema.INFO)

        def tarea():
            try:
                res = optimizar(comps, rotacion, opciones, baneos)
            except Exception as error:
                mensaje = str(error)
                self._en_ui(lambda: self._fin_optimizacion(None, mensaje, rotacion))
                return
            self._en_ui(lambda: self._fin_optimizacion(res, None, rotacion))

        threading.Thread(target=tarea, daemon=True).start()

    def _fin_optimizacion(self, res, error, rotacion):
        self._ocupado = False
        self.btn_optimizar.configure(state="normal")
        if error:
            self._estado(tr('Error: {0}', error), tema.ERR)
            return
        self.resultado = res
        ok = bool(res.elegidas)
        color = tema.OK if res.estado == "Óptimo global" else (tema.WARN if ok else tema.ERR)
        self._estado(f"{res.estado} — {res.detalle}", color)

        if ok:
            self.lbl_resumen.configure(
                text=tr('Tiempo total: {0}   ·   Composiciones consideradas: {1}   ·   Búsqueda: {2:.2f} s   ·   Rotación: {3}', formato_tiempo(res.total), res.consideradas, res.duracion, '-'.join(rotacion)))
        else:
            pista = ("  Prueba desmarcando 'Solo runs completas' o revisa los baneos."
                     if self.var_completas.get() else "  Revisa los baneos o la rotación.")
            self.lbl_resumen.configure(text=res.detalle + pista)

        for i, tarjeta in enumerate(self.tarjetas):
            boss = rotacion[i] if i < len(rotacion) else "?"
            comp = res.elegidas[i] if ok else None
            n_cand = len(res.candidatos.get(i + 1, [])) if res.candidatos else 0
            titulo = f"Jefe {i + 1} · {self._etiqueta_jefe(boss)}"
            if comp:
                mejor_solo = res.candidatos[i + 1][0].tiempo
                extra = "" if abs(comp.tiempo - mejor_solo) < 1e-9 else f"  (mejor individual {formato_tiempo(mejor_solo)})"
                titulo += f" · {formato_tiempo(comp.tiempo)}{extra} · {n_cand} equipos posibles"
            else:
                titulo += f" · {n_cand} equipos posibles"
            self._contenido_tarjetas[i] = (comp, titulo, boss)
            tarjeta.mostrar(comp, titulo, boss_id=boss)
        self.notebook.select(0)
        self._llenar_builds()

    # ---------------- explorar por jefe ----------------

    def ver_alternativas(self, comp):
        if comp is None:
            return
        self.combo_jefe.set(self._etiqueta_jefe(comp.boss_id))
        self.actualizar_explorar(seleccionar=comp)
        self.notebook.select(self.tab_explorar)

    def actualizar_explorar(self, seleccionar=None):
        boss = self._id_de_etiqueta(self.combo_jefe.get())
        self.tabla_explorar.delete(*self.tabla_explorar.get_children())
        self.explorar_lista = []
        if not boss or not self.comps:
            return
        # Si el jefe está en la rotación actual se usa su posición real (afecta baneos por posición)
        rotacion = [c.get().strip() for c in self.combos_rotacion]
        if boss in rotacion:
            posicion = rotacion.index(boss) + 1
        else:
            rotacion, posicion = [boss, "", "", "", "", ""], 1
        candidatos, consideradas = candidatos_por_jefe(self.comps, rotacion, self._opciones(), self.baneos)
        self.explorar_lista = candidatos[posicion]
        texto = _normalizar_texto(self.var_filtro_explorar.get().strip()) if hasattr(self, "var_filtro_explorar") else ""
        if texto:
            self.explorar_lista = [
                c for c in self.explorar_lista
                if any(texto in _normalizar_texto(h.get("name", "")) or
                       texto in _normalizar_texto((h.get("collection") or {}).get("name", "")) for h in c.heroes)
                or texto in _normalizar_texto(c.mascota.get("name", ""))
            ]
        for i, c in enumerate(self.explorar_lista, 1):
            self.tabla_explorar.insert("", "end", iid=str(i - 1), values=(
                i, formato_tiempo(c.tiempo), ", ".join(_nombre_con_origen(h) for h in c.heroes),
                c.mascota.get("name", ""), c.veces, fecha_local(c.fecha), c.rotacion,
            ))
        self.lbl_explorar.configure(text=tr('{0} equipos distintos de {1} usos', len(self.explorar_lista), consideradas))
        indice = 0
        if seleccionar is not None:
            for i, c in enumerate(self.explorar_lista):
                if c.firma == seleccionar.firma:
                    indice = i
                    break
        if self.explorar_lista:
            self.tabla_explorar.selection_set(str(indice))
            self.tabla_explorar.see(str(indice))
        else:
            self.tarjeta_explorar.mostrar(None, f"{self._etiqueta_jefe(boss)}: sin equipos con estos filtros",
                                          boss_id=boss)

    def _al_elegir_explorar(self, _evento=None):
        sel = self.tabla_explorar.selection()
        if not sel:
            return
        i = int(sel[0])
        c = self.explorar_lista[i]
        self.tarjeta_explorar.mostrar(c, f"{self._etiqueta_jefe(c.boss_id)} · #{i + 1} · {formato_tiempo(c.tiempo)}")

    # ---------------- builds ----------------

    def _resumen_equipo(self, gear):
        if not gear:
            return "—"
        nombres = self._nombres_calidad_gear()
        partes = []
        for g in sorted(gear, key=lambda g: g.get("slot", 0)):
            tier = self.vis.tier_equipo(g)
            if not tier:  # piezas sin tier (Legendary, Elite...): abreviar la calidad
                tier = (nombres.get(g.get("quality"), f"Q{g.get('quality')}")
                        .replace("Legendary", "L").replace("Elite", "E").replace(" ", ""))
            estrellas = f"★{g.get('stars')}" if g.get("stars") else ""
            partes.append(f"{g.get('part', '?')[:1]}:{tier}{estrellas}")
        return "  ".join(partes)

    def _llenar_builds(self):
        self.tabla_builds.delete(*self.tabla_builds.get_children())
        self._builds_items = {}
        if not self.resultado or not self.resultado.elegidas:
            return
        tags = self.refs.get("collectionTags") or {}
        for pos, comp in enumerate(self.resultado.elegidas, 1):
            for h in comp.heroes:
                col = h.get("collection") or {}
                mueble = h.get("furniture") or {}
                col_txt = col.get("name", "—")
                if col.get("tag") is not None and str(col.get("tag")) in tags:
                    col_txt += f" ({tags[str(col.get('tag'))]})"
                afijos = col.get("affixes") or []
                miticos = sum(1 for a in afijos if int(a.get("quality") or 0) >= 5)
                estrellas_col = self.vis.estrellas_coleccion(col) if col else None
                sp = self.vis.usa_sp(h, comp.golden)
                iid = self.tabla_builds.insert("", "end", values=(
                    f"{pos} · {self.vis.jefe(comp.boss_id)[0]}", _nombre_con_origen(h),
                    "" if sp is None else ("✦ Sí" if sp else "No"),
                    "—" if h.get("sig") is None else h.get("sig"),
                    "—" if h.get("engraving") is None else h.get("engraving"),
                    f"{mueble.get('pieces', 0)}/9 · nv {mueble.get('level', 0)}",
                    col_txt,
                    f"{'★' * (estrellas_col or 0) or '—'} · {miticos}" if col else "—",
                    self._resumen_equipo(h.get("gear")),
                ))
                self._builds_items[iid] = (comp, h)

    def _al_elegir_build(self, _evento=None):
        sel = self.tabla_builds.selection()
        if sel and sel[0] in self._builds_items:
            comp, h = self._builds_items[sel[0]]
            self.mostrar_detalle(comp, h, "HEROE")

    # ---------------- panel de detalle ----------------

    def _nombres_calidad_gear(self):
        go = self.refs.get("gearOptions") or {}
        return {q.get("quality"): q.get("name") for q in go.get("qualities") or []}

    def _nombres_faccion_gear(self):
        go = self.refs.get("gearOptions") or {}
        return {f.get("tag"): f.get("name") for f in go.get("factions") or []}

    def mostrar_detalle(self, comp, obj, tipo):
        self.seleccion = (comp, obj, tipo)
        if tipo == "HEROE" and self.vis.disponible:
            cabecera = self.imagenes.retrato(obj, self.vis, comp.golden, TAM_RETRATO_DETALLE, con_equipo=True)
        else:
            cabecera = self.imagenes.obtener(obj.get("imageUrl"), TAM_DETALLE)
        self.lbl_img_detalle.configure(image=cabecera)
        self.lbl_nombre_detalle.configure(text=obj.get("name", "?"))
        self.btn_ban_todos.configure(state="normal")
        self.btn_ban_jefe.configure(state="normal")
        no_propio = tipo == "HEROE" and (obj.get("origen") or PROPIO) != PROPIO
        self.btn_ban_copia.configure(state="normal" if no_propio else "disabled")

        t = self.txt_detalle
        t.configure(state="normal")
        t.delete("1.0", "end")
        vis = self.vis

        def titulo(texto):
            t.insert("end", texto + "\n", "titulo")

        def linea(etiqueta, valor):
            t.insert("end", f"  {etiqueta:<14}", ("gris", "fila"))
            t.insert("end", f"{valor}\n", "fila")

        def imagen(url, tam=TAM_ICONO):
            if url:
                t.image_create("end", image=self.imagenes.obtener(url, tam), padx=1, align="center")

        titulo(tr("Run"))
        nombre_jefe, url_jefe = vis.jefe(comp.boss_id)
        t.insert("end", "  ")
        imagen(url_jefe, 64)
        t.insert("end", f"  {nombre_jefe}\n", "grande")
        linea(tr("Jefe"), tr('posición {0} · Boss {1}', comp.posicion, comp.boss_id))
        linea(tr("Tiempo"), formato_tiempo(comp.tiempo))
        linea(tr("Fecha"), fecha_local(comp.fecha))
        linea(tr("Rotación"), comp.rotacion)
        linea(tr("Run ID"), comp.run_id)

        if tipo == "MASCOTA":
            titulo(tr("Mascota"))
            linea(tr("Nivel"), obj.get("level", "—"))
            linea(tr("Trabajos"), " / ".join(str(j) for j in obj.get("jobs") or []) or "—")
            linea(tr("Trabajo máx."), obj.get("maxJob", "—"))
            linea(tr("ID"), obj.get("tid", "—"))
        else:
            self._detalle_heroe(comp, obj, titulo, linea, imagen)

        t.configure(state="disabled")
        t.see("1.0")

    def _detalle_heroe(self, comp, h, titulo, linea, imagen):
        t = self.txt_detalle
        vis = self.vis

        titulo(tr("Héroe"))
        t.insert("end", "  ")
        imagen(vis.faccion(h.get("faction")), 28)
        t.insert("end", f" {h.get('faction', '—')} · {h.get('job', '—')}\n")
        t.insert("end", f"  {'Estrellas':<14}", ("gris", "fila"))
        n = vis.numero_estrellas(h.get("quality"))
        for _ in range(n):
            imagen(vis.estrella(h.get("engraving")), 22)
        t.insert("end", f" {vis.nombre_calidad(h.get('quality'))}\n" if n else
                 f"{vis.nombre_calidad(h.get('quality'))}\n", "fila")
        t.insert("end", f"  {'SI (firma)':<14}", ("gris", "fila"))
        imagen(vis.icono_si(h.get("tid"), h.get("sig")), 40)
        t.insert("end", f" +{h.get('sig', '—')}\n", "fila")

        sp = vis.usa_sp(h, comp.golden)
        if sp is not None:
            t.insert("end", f"  {'Special Power':<14}", ("gris", "fila"))
            if sp:
                t.insert("end", tr("✦ SP usado en este jefe\n"), ("sp_si", "fila"))
            else:
                otro = next((x.get("name") for x in comp.heroes
                             if comp.golden is not None and str(x.get("slot")) == str(comp.golden)), None)
                texto = f"No usa SP (lo usa {otro})" if otro else "No usa SP (nadie lo usa en este jefe)"
                t.insert("end", texto + "\n", ("sp_no", "fila"))
        origen = h.get("origen") or PROPIO
        t.insert("end", f"  {'Copia':<14}", ("gris", "fila"))
        t.insert("end", NOMBRES_ORIGEN.get(origen, origen) + "\n",
                 ("fila",) if origen == PROPIO else ("sp_no", "fila"))
        linea(tr("ID"), tr('{0} (instancia {1})', h.get('tid', '—'), h.get('id', '—')))

        titulo(tr("Grabado"))
        t.insert("end", f"  {'Total':<14}", ("gris", "fila"))
        imagen(vis.estrella(h.get("engraving")), 22)
        t.insert("end", tr(' {0}  (color de estrella: blanco <30, naranja ≥30, rojo ≥60, diamante ≥80)\n', h.get('engraving', 0)), "fila")
        for nodo in h.get("engravingNodes") or []:
            stats = ", ".join(nodo.get("stats") or []) or nodo.get("key")
            linea("", f"{stats}: {nodo.get('level', 0)}/{nodo.get('max', '?')}")

        titulo(tr("Muebles"))
        mueble = h.get("furniture") or {}
        piezas = int(mueble.get("pieces") or 0)
        insignia, corona = vis.insignia_muebles(h)
        t.insert("end", "  ")
        imagen(insignia, 32)
        imagen(corona, 20)
        for _ in range(piezas):
            imagen(vis.icono_mueble(9), 22)
        t.insert("end", tr('  {0}/9 piezas\n', piezas))
        linea(tr("Nivel"), mueble.get("level", 0))
        slots = h.get("furnitureSlots")
        if slots:
            linea(tr("Por pieza"), " ".join(str(s) for s in slots))

        titulo(tr("Equipo"))
        gear = sorted(h.get("gear") or [], key=lambda g: g.get("slot", 0))
        if not gear:
            linea("", tr("Sin datos de equipo"))
        calidades = self._nombres_calidad_gear()
        for g in gear:
            calidad = calidades.get(g.get("quality"), f"Q{g.get('quality')}")
            t.insert("end", "  ")
            t.image_create("end", image=self.imagenes.equipo(g, vis, 64), padx=1, align="center")
            tier = vis.tier_equipo(g) or "—"
            t.insert("end", f" {g.get('name', '?')}  ", "negrita")
            t.insert("end", f"{tier} · ★{g.get('stars', 0)}\n", "tier")
            t.insert("end", f"  {g.get('part', '?'):<14}", ("gris", "fila"))
            t.insert("end", calidad, "fila")
            nombre_faccion, icono_faccion = vis.faccion_equipo(g.get("faction"))
            if nombre_faccion:
                t.insert("end", " · ", "fila")
                imagen(icono_faccion, 22)
                t.insert("end", f" {nombre_faccion}", "fila")
            if g.get("attuned"):
                t.insert("end", tr(" · sintonizado"), "fila")
            t.insert("end", "\n")

        titulo(tr("Colección"))
        col = h.get("collection") or {}
        if not col:
            linea("", tr("Sin colección"))
        else:
            tags = self.refs.get("collectionTags") or {}
            estrellas_col = vis.estrellas_coleccion(col)
            t.insert("end", "  ")
            imagen(vis.imagen_coleccion(col.get("tid")), 72)
            t.insert("end", f"  {col.get('name', '—')}  ", "negrita")
            for _ in range(estrellas_col or 0):
                imagen("/game-ui/img_star_light.png", 22)
            t.insert("end", "\n")
            linea(tr("Tipo"), tags.get(str(col.get("tag")), col.get("tag", "—")))
            linea(tr("Nivel"), col.get("level", "—"))
            afijos = col.get("affixes") or []
            linea(tr("Míticos"), sum(1 for a in afijos if int(a.get("quality") or 0) >= 5))
            for a in sorted(afijos, key=lambda a: -int(a.get("quality") or 0)):
                nombre_afijo, icono_afijo = vis.afijo(a.get("nature"), a.get("quality"))
                valor = vis.valor_afijo(col.get("tid"), a.get("nature"), a.get("quality"))
                color = vis.color_calidad_afijo(a.get("quality"))
                etiqueta = f"afijo_{a.get('quality')}"
                if color:
                    t.tag_configure(etiqueta, foreground=_oscurecer(color))
                t.insert("end", "    ")
                imagen(icono_afijo, 30)
                t.insert("end", f" {nombre_afijo}{(' ' + valor) if valor else ''}  ", (etiqueta, "fila"))
                t.insert("end", tr('(calidad {0})\n', a.get('quality')), ("gris", "fila"))
            habilidades = vis.habilidades_coleccion(col.get("tid"))
            if habilidades:
                activas = estrellas_col if estrellas_col is not None else len(habilidades)
                t.insert("end", tr('  Habilidades ({0}/{1} activas)\n', min(activas, len(habilidades)), len(habilidades)),
                         "negrita")
                for i, hab in enumerate(habilidades):
                    activa = i < activas
                    t.insert("end", f"  {'•' if activa else '○'} {hab.get('name', '')}: ",
                             ("negrita", "parrafo") if activa else ("gris", "parrafo"))
                    t.insert("end", f"{hab.get('description', '')}\n", "parrafo" if activa else ("gris", "parrafo"))

        # Guía de colecciones: ¿la colección de esta run cumplía la recomendación para NC?
        recs = vis.recomendaciones_heroe(h.get("tid"), "NC")
        titulo(tr("Guía de colecciones (NC)"))
        if not vis.recomendaciones:
            linea("", tr("Sin datos de la guía (sincroniza en 'Mi cuenta')."))
        elif not recs:
            linea("", tr("La guía no tiene recomendación de NC para este héroe."))
        else:
            for f in recs:
                cumple, _, detalle = vis.evaluar_recomendacion(col, f) if col else (False, 0, "sin colección")
                icono = vis.imagen_coleccion(f.get("collectionTid"))
                t.insert("end", "  ")
                imagen(icono, 26)
                t.insert("end", f" {vis.nombre_coleccion(f.get('collectionTid'))} +{f.get('skillBonus', 0)} · "
                                f"{f.get('primary') or '—'}\n", ("negrita", "parrafo"))
                if cumple:
                    t.insert("end", tr("      ✓ La colección de esta run cumple\n"), ("tier", "parrafo"))
                else:
                    t.insert("end", f"      ✗ {detalle}\n", ("sp_no", "parrafo"))
                if f.get("notes"):
                    t.insert("end", f"      {f['notes']}\n", ("gris", "parrafo"))

    # ---------------- baneos ----------------

    def _actualizar_boton_baneos(self):
        activos = sum(1 for b in self.baneos if b.get("activo", True))
        self.btn_baneos.configure(text=tr('Baneos ({0})', activos))

    def banear_seleccion(self, todos, solo_copia=False):
        if not self.seleccion or not self.carpeta:
            return
        comp, obj, tipo = self.seleccion
        nuevo = {
            "tipo": tipo,
            "nombre": obj.get("name", ""),
            "id": str(obj.get("tid") or ""),
            "jefe": "TODOS" if todos else comp.boss_id,
            "copia": COPIA_NO_PROPIA if solo_copia else COPIA_TODAS,
            "activo": True,
        }
        clave = (nuevo["tipo"], nuevo["nombre"], nuevo["jefe"], nuevo["copia"])
        if any((b.get("tipo"), b.get("nombre"), b.get("jefe"), b.get("copia") or COPIA_TODAS) == clave
               for b in self.baneos):
            self._estado(tr('{0} ya estaba baneado ({1}).', nuevo['nombre'], nuevo['jefe']), tema.WARN)
            return
        self.baneos.append(nuevo)
        guardar_baneos(self.carpeta, self.baneos)
        self._actualizar_boton_baneos()
        self.actualizar_explorar()
        self._estado(tr('Baneado {0}{1} ({2}). Pulsa ▶ Optimizar para recalcular.', nuevo['nombre'], ' (solo copia prestada/prueba)' if solo_copia else '', 'todos los jefes' if todos else 'Boss ' + comp.boss_id), tema.WARN)

    def abrir_baneos(self):
        if not self.carpeta:
            return
        VentanaBaneos(self.top, self.baneos, catalogo(self.comps),
                      sorted({c.boss_id for c in self.comps}, key=orden_boss), self._guardar_baneos)

    def _guardar_baneos(self, baneos):
        self.baneos = baneos
        guardar_baneos(self.carpeta, baneos)
        self._actualizar_boton_baneos()
        self.actualizar_explorar()
        self._estado(tr("Baneos guardados. Pulsa ▶ Optimizar para recalcular."), tema.WARN)


# ============================================================
# EDITOR DE BANEOS
# ============================================================

class VentanaBaneos:
    def __init__(self, parent, baneos, cat, bosses, al_guardar):
        self.baneos = [dict(b) for b in baneos]
        self.cat = cat
        self.al_guardar = al_guardar

        self.top = tk.Toplevel(parent)
        self.top.title(tr("Baneos"))
        self.top.geometry("900x640")
        self.top.transient(parent)
        self.top.grab_set()

        ttk.Label(self.top, text=tr("Jefe = TODOS, posición (1-6) o Boss ID. Copia 'Solo prestada/prueba' quita "
                                 "solo las copias que no son tuyas. Doble clic para activar/desactivar."),
                  foreground=tema.MUTED).pack(anchor="w", padx=10, pady=(10, 4))

        self.tabla = ttk.Treeview(self.top, columns=("tipo", "nombre", "jefe", "copia", "activo"), show="headings")
        for col, titulo, ancho in (("tipo", N_("Tipo"), 90), ("nombre", N_("Nombre"), 280), ("jefe", N_("Jefe"), 90),
                                   ("copia", N_("Copia"), 150), ("activo", N_("Activo"), 70)):
            self.tabla.heading(col, text=tr(titulo))
            self.tabla.column(col, width=ancho, anchor="w" if col == "nombre" else "center")
        self.tabla.pack(fill="both", expand=True, padx=10)
        self.tabla.bind("<Double-1>", self._alternar)

        # --- Agregar baneo: búsqueda en vivo ---
        marco_nuevo = ttk.LabelFrame(self.top, text=tr(" Agregar baneo "))
        marco_nuevo.pack(fill="x", padx=10, pady=8)

        f = ttk.Frame(marco_nuevo)
        f.pack(fill="x", padx=8, pady=(6, 2))
        ttk.Label(f, text=tr("Tipo:")).pack(side="left")
        self.var_tipo = tk.StringVar(value="HEROE")
        combo_tipo = ttk.Combobox(f, textvariable=self.var_tipo, values=["HEROE", "MASCOTA"], state="readonly", width=9)
        combo_tipo.pack(side="left", padx=(2, 10))
        combo_tipo.bind("<<ComboboxSelected>>", lambda e: self._filtrar())
        ttk.Label(f, text=tr("Buscar:")).pack(side="left")
        self.var_busqueda = tk.StringVar()
        self.entrada = ttk.Entry(f, textvariable=self.var_busqueda, width=34)
        self.entrada.pack(side="left", padx=(2, 10))
        self.var_busqueda.trace_add("write", lambda *a: self._filtrar())
        self.entrada.bind("<Down>", self._bajar_a_lista)
        self.entrada.bind("<Return>", lambda e: self._agregar())
        ttk.Label(f, text=tr("Jefe:")).pack(side="left")
        self.combo_jefe = ttk.Combobox(f, values=["TODOS"] + [str(i) for i in range(1, 7)] + list(bosses), width=8)
        self.combo_jefe.set("TODOS")
        self.combo_jefe.pack(side="left", padx=(2, 10))
        ttk.Label(f, text=tr("Copia:")).pack(side="left")
        self.combo_copia = ttk.Combobox(f, state="readonly", width=20, values=list(NOMBRES_COPIA.values()))
        self.combo_copia.set(NOMBRES_COPIA[COPIA_TODAS])
        self.combo_copia.pack(side="left", padx=2)

        lista = ttk.Frame(marco_nuevo)
        lista.pack(fill="x", padx=8, pady=(2, 4))
        self.lista = tk.Listbox(lista, height=7, activestyle="dotbox", exportselection=False)
        barra = ttk.Scrollbar(lista, orient="vertical", command=self.lista.yview)
        self.lista.configure(yscrollcommand=barra.set)
        self.lista.pack(side="left", fill="x", expand=True)
        barra.pack(side="left", fill="y")
        self.lista.bind("<Double-1>", lambda e: self._agregar())
        self.lista.bind("<Return>", lambda e: self._agregar())

        pie = ttk.Frame(marco_nuevo)
        pie.pack(fill="x", padx=8, pady=(0, 6))
        self.lbl_coincidencias = ttk.Label(pie, text="", foreground=tema.MUTED)
        self.lbl_coincidencias.pack(side="left")
        ttk.Button(pie, text=tr("Agregar"), command=self._agregar).pack(side="right")
        ttk.Label(pie, text=tr("Escribe para filtrar · ↓ para ir a la lista · doble clic o Enter para agregar"),
                  foreground=tema.MUTED).pack(side="right", padx=10)

        g = ttk.Frame(self.top)
        g.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Button(g, text=tr("Quitar seleccionados"), command=self._quitar).pack(side="left")
        ttk.Button(g, text=tr("Guardar y cerrar"), command=self._guardar).pack(side="right")
        ttk.Button(g, text=tr("Cancelar"), command=self._cerrar).pack(side="right", padx=6)

        self._filtrar()
        self._refrescar()
        self.entrada.focus_set()

    @staticmethod
    def _normalizar(texto):
        """Minúsculas y sin tildes, para buscar 'eluard' o 'pippa' sin importar cómo se escriba."""
        texto = unicodedata.normalize("NFD", str(texto).lower())
        return "".join(c for c in texto if unicodedata.category(c) != "Mn")

    def _filtrar(self):
        consulta = self._normalizar(self.var_busqueda.get().strip())
        nombres = sorted(self.cat.get(self.var_tipo.get(), {}), key=self._normalizar)
        if consulta:
            # primero los que empiezan con lo escrito, luego los que lo contienen
            empiezan = [n for n in nombres if self._normalizar(n).startswith(consulta)]
            contienen = [n for n in nombres if consulta in self._normalizar(n) and n not in empiezan]
            nombres = empiezan + contienen
        self._resultados = nombres
        self.lista.delete(0, "end")
        for n in nombres:
            self.lista.insert("end", n)
        if nombres:
            self.lista.selection_set(0)
            self.lista.activate(0)
        total = len(self.cat.get(self.var_tipo.get(), {}))
        self.lbl_coincidencias.configure(
            text=tr('{0} de {1}', len(nombres), total) if consulta else tr('{0} disponibles', total))

    def _bajar_a_lista(self, _evento=None):
        if self._resultados:
            self.lista.focus_set()
            self.lista.selection_clear(0, "end")
            self.lista.selection_set(0)
            self.lista.activate(0)
        return "break"

    def _actualizar_nombres(self):
        self.var_busqueda.set("")
        self._filtrar()

    def _refrescar(self):
        self.tabla.delete(*self.tabla.get_children())
        for i, b in enumerate(self.baneos):
            self.tabla.insert("", "end", iid=str(i), values=(
                b.get("tipo"), b.get("nombre"), b.get("jefe", "TODOS"),
                NOMBRES_COPIA.get(b.get("copia") or COPIA_TODAS, b.get("copia")) if b.get("tipo") == "HEROE" else "—",
                "Sí" if b.get("activo", True) else "No"))

    def _agregar(self):
        sel = self.lista.curselection()
        if sel:
            nombre = self.lista.get(sel[0])
        elif len(self._resultados) == 1:
            nombre = self._resultados[0]
        else:
            self.lbl_coincidencias.configure(text=tr("Elige un nombre de la lista"))
            return
        tipo = self.var_tipo.get()
        jefe = self.combo_jefe.get().strip() or "TODOS"
        copia = next((k for k, v in NOMBRES_COPIA.items() if v == self.combo_copia.get()), COPIA_TODAS)
        if tipo != "HEROE":
            copia = COPIA_TODAS
        if any((b.get("tipo"), b.get("nombre"), b.get("jefe", "TODOS"), b.get("copia") or COPIA_TODAS)
               == (tipo, nombre, jefe, copia) for b in self.baneos):
            self.lbl_coincidencias.configure(text=tr('{0} ya está en la lista', nombre))
            return
        self.baneos.append({
            "tipo": tipo, "nombre": nombre, "id": self.cat.get(tipo, {}).get(nombre, ""),
            "jefe": jefe, "copia": copia, "activo": True,
        })
        self._refrescar()
        self.tabla.see(str(len(self.baneos) - 1))
        self.lbl_coincidencias.configure(text=tr('✓ Agregado: {0}', nombre))
        self.var_busqueda.set("")
        self.entrada.focus_set()

    def _quitar(self):
        for iid in sorted(self.tabla.selection(), key=int, reverse=True):
            del self.baneos[int(iid)]
        self._refrescar()

    def _alternar(self, _evento=None):
        for iid in self.tabla.selection():
            b = self.baneos[int(iid)]
            b["activo"] = not b.get("activo", True)
        self._refrescar()

    def _guardar(self):
        self.al_guardar(self.baneos)
        self._cerrar()

    def _cerrar(self):
        self.top.grab_release()
        self.top.destroy()
