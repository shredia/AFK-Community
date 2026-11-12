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
    arrendados_de,
    rotacion_mas_reciente,
    candidatos_por_jefe,
    quitar_baneadas,
    optimizar,
    aplicar_sp_manual,
    guardar_sp_manual,
    deducir_golden,
    PROPIO,
    NOMBRES_ORIGEN,
)
from navegador.visuales import Visuales
from navegador.cuenta import cargar_cuenta_actual
from navegador import bloqueos as blq
from navegador import roster as rst
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
TAM_JEFE_ROTACION = 52    # imagen de cada jefe en la rotación de la semana
TAM_JEFE_SEMANA = 40      # miniatura de cada jefe en la cabecera
TAM_RESUMEN = 50          # retratos de las tarjetas del Resumen
# Tamaño de íconos de las tarjetas: (ancho del retrato, tarjetas por fila)
TAMANOS = {N_("Pequeño"): (56, 2), N_("Mediano"): (84, 1), N_("Grande"): (108, 1), N_("Muy grande"): (136, 1)}
ARCHIVO_PREFERENCIAS = "preferencias.json"
ARCHIVO_LIMITES = "limites.json"
MAX_CHIPS = 7               # chips de 'Activos' antes de '+N más…'
MAX_FALTA_POR_JEFE = 8      # equipos más rápidos por jefe en 'Qué me falta'


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


def resumen_heroes(candidatos):
    """
    Héroes usados en una lista de equipos contra un jefe:
    {clave: {"nombre", "equipos", "usos", "mejor": comp más rápido con ese héroe, "heroe": su build ahí}}.
    """
    salida = {}
    for c in candidatos:
        for h in c.heroes:
            clave = str(h.get("tid") or h.get("name") or "?")
            e = salida.setdefault(clave, {"nombre": h.get("name", "?"), "equipos": 0, "usos": 0,
                                          "mejor": c, "heroe": h})
            e["equipos"] += 1
            e["usos"] += c.veces
            if c.tiempo < e["mejor"].tiempo:
                e["mejor"], e["heroe"] = c, h
    return salida


def texto_build(h):
    """'SI 30 · G 80 · Timeline Watch 3M' (lo que define la build de un héroe en una ronda)."""
    if not h:
        return ""
    partes = []
    if h.get("sig") is not None:
        partes.append(f"SI {h['sig']}")
    if h.get("engraving") is not None:
        partes.append(f"G {h['engraving']}")
    col = h.get("collection") or {}
    if col:
        partes.append(f"{col.get('name', '?')} {col.get('mythic', 0)}M")
    return " · ".join(partes)


CARPETA_AMIGOS = "_amigos"


def diferencias_equipos(a, b):
    """Héroes en ambos equipos [(de a, de b)], solo en a, solo en b, y mascota (a, b) si cambia."""
    clave = lambda h: str(h.get("tid") or h.get("name") or "?")
    en_b = {clave(h): h for h in b.heroes}
    en_a = {clave(h) for h in a.heroes}
    ambos = [(h, en_b[clave(h)]) for h in a.heroes if clave(h) in en_b]
    solo_a = [h for h in a.heroes if clave(h) not in en_b]
    solo_b = [h for h in b.heroes if clave(h) not in en_a]
    ma, mb = a.mascota.get("name", "—"), b.mascota.get("name", "—")
    return {"ambos": ambos, "solo_a": solo_a, "solo_b": solo_b, "mascota": (ma, mb) if ma != mb else None}


def diferencias_build(ha, hb):
    """['SI 30 ⟷ 20', 'Grabado 60 ⟷ 30', ...] solo de lo que cambia entre dos copias del mismo héroe."""
    partes = []
    for campo, nombre in (("quality", N_("Calidad")), ("sig", N_("SI")), ("engraving", N_("Grabado"))):
        if ha.get(campo) != hb.get(campo):
            partes.append(f"{tr(nombre)} {ha.get(campo, '—')} ⟷ {hb.get(campo, '—')}")
    ma, mb = (ha.get("furniture") or {}).get("pieces", 0), (hb.get("furniture") or {}).get("pieces", 0)
    if ma != mb:
        partes.append(f"{tr('Muebles')} {ma}/9 ⟷ {mb}/9")
    ca, cb = ha.get("collection") or {}, hb.get("collection") or {}
    texto_col = lambda c: f"{c.get('name', '?')} {c.get('mythic', 0)}M" if c else "—"
    if (ca.get("tid"), ca.get("mythic")) != (cb.get("tid"), cb.get("mythic")):
        partes.append(f"{tr('Colección')} {texto_col(ca)} ⟷ {texto_col(cb)}")
    ea = sorted((g.get("slot"), g.get("quality"), g.get("stars")) for g in ha.get("gear") or [])
    eb = sorted((g.get("slot"), g.get("quality"), g.get("stars")) for g in hb.get("gear") or [])
    if ea != eb:
        partes.append(tr("Equipo distinto"))
    return partes


def listar_servidores(base_dir):
    """[(etiqueta, carpeta_servidor)] de los servidores que tienen detalles descargados."""
    resultado = []
    for carpeta_detalles in sorted((Path(base_dir) / "cuentas").glob("*/*/detalles")):
        carpeta = carpeta_detalles.parent
        n = sum(1 for _ in carpeta_detalles.glob("*.json"))
        if not n:
            continue
        nombre, ficha = carpeta.name, {}
        archivo = carpeta / f"{carpeta.name}.json"
        if archivo.exists():
            try:
                ficha = json.loads(archivo.read_text(encoding="utf-8"))
                nombre = ficha.get("name") or nombre
            except (OSError, json.JSONDecodeError):
                pass
        if ficha.get("amigo"):   # runs importadas de un amigo (cuentas/_amigos/<nombre>/)
            servidor = f" · {tr('Servidor')} {ficha['svr_id']}" if ficha.get("svr_id") else ""
            resultado.append((tr("Amigo: {0}{1} ({2} runs)", nombre, servidor, n), carpeta))
        else:
            resultado.append((f"{nombre} · Servidor {carpeta.name} ({n} runs)", carpeta))
    # primero tus servidores, luego los amigos
    resultado.sort(key=lambda x: x[1].parent.name == "_amigos")
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
        self.lbl_jefe_nombre = ttk.Label(jefe, text="", font=("Segoe UI", 9 if tam >= 80 else 8, "bold"), wraplength=self.tam_jefe + 10,
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
            usos = tr("usado 1 vez") if comp.veces == 1 else tr("usado {0} veces", comp.veces)
            self.lbl_pie.configure(text=f"{fecha_local(comp.fecha)} · " + tr("rotación {0}", comp.rotacion)
                                        + f" · {usos}"
                                        + (" · " + tr("⚠ {0} héroe(s) no propio(s)", len(comp.no_propios))
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
        """enfoque: {'texto': 'Thalassa', 'boss': '76'} -> abre ese jefe filtrado por ese héroe (desde Mi cuenta)."""
        self.parent = parent
        self._enfoque_pendiente = enfoque
        self.base_dir = Path(perfil_path).parent
        self.imagenes = CacheImagenes()
        self.vis = Visuales(self.base_dir)
        self._tamano = cargar_preferencia(self.base_dir, "tamano_iconos", "Mediano")
        if self._tamano not in TAMANOS:
            self._tamano = "Mediano"
        self.servidores = listar_servidores(self.base_dir)
        self.carpeta = None
        self.runs, self.comps, self.refs = [], [], {}
        self.baneos = []
        self.resultado = None
        self._optimo_por_jefe = {}      # boss -> composición elegida por el optimizador
        self._rotacion_optimizada = None
        self.explorar_lista = []
        self.seleccion = None           # (comp, objeto, tipo) mostrado en el panel de detalle
        self._cola = queue.Queue()
        self._ocupado = False
        self._fuentes = {}              # str(carpeta) -> comps de otro servidor / amigo (ya cargados)
        self._esperando = {}            # str(carpeta) -> funciones a llamar cuando termine de cargar
        self._carpetas_amigos, self._nombre_carpeta = [], {}
        self.baneos_amigos = []         # baneos para equipos de amigos / otros servidores
        self.limites = []               # límites de build (colección a ★2, SI 20...) de este servidor
        self._optimo_otro = None        # {'clave', 'nombre', 'por_jefe', 'total'} del óptimo de otros
        self._total_yo = None
        self._clave_opt = None
        self._ids_otro = set()          # id() de equipos de otras carpetas: tus baneos no aplican ahí
        self._opciones_fuente = []      # [(etiqueta, carpeta)] para 'Comparar con'
        self._paginas_jefe = {}         # boss -> {"marco", "version", widgets...}
        self._version_jefes = 0
        self._rotacion_tabs = None
        self._cands_cache = None        # (version, {boss: [comps]}) de tus equipos
        self._detalle_visible = False

        self.reglas = []                # bloqueos unificados (baneos + límites) de este servidor
        self.perfil = None              # tu roster (qué tienes) para saber si puedes copiar un equipo
        self._evaluaciones = {}         # id(comp) -> (nivel, faltas) según tu roster
        self._rotacion = [""] * 6
        self._bosses = []
        self._ultimo_optimo = None      # {'clave', 'nombre', 'por_jefe', 'total'} de la última optimización
        self._pendiente_opt = None
        self._cache_otros = None

        self.top = tema.ventana(parent)
        self.top.title(tr("Optimizador NC"))
        self.top.geometry("1600x960")
        self.top.minsize(1100, 700)

        self._crear_variables()
        self.crear_interfaz()
        self.top.after(100, self._procesar_cola)

        if not self.servidores:
            self.lbl_estado.configure(
                text=tr("No hay runs. Importa afk-runs.json en Ajustes → Importar / exportar."),
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

    def _estado(self, texto, color=tema.MUTED):
        self.lbl_estado.configure(text=tr(texto), foreground=color)

    # ---------------- interfaz ----------------

    def _crear_variables(self):
        pref = lambda clave, defecto: cargar_preferencia(self.base_dir, clave, defecto)
        self.var_completas = tk.BooleanVar(value=pref("solo_completas", True))
        self.var_mascota = tk.BooleanVar(value=pref("prohibir_repetir_mascota", True))
        self.var_limite = tk.IntVar(value=pref("limite_por_jefe", 0))
        self.var_tiempo = tk.IntVar(value=pref("tiempo_busqueda", 60))
        self.var_excluir_temp = tk.BooleanVar(value=pref("excluir_temporales", False))
        self.var_excluir_fuera = tk.BooleanVar(value=pref("excluir_fuera_roster", False))
        self.var_modo_roster = tk.StringVar(value=pref("equipos_otros_roster", "todos"))
        self.var_filtro = tk.StringVar()
        self.var_filtro_explorar = self.var_filtro          # un solo filtro para pestañas de jefe y Explorar

    def guardar_opciones_busqueda(self):
        for clave, var in (("solo_completas", self.var_completas), ("prohibir_repetir_mascota", self.var_mascota),
                           ("limite_por_jefe", self.var_limite), ("tiempo_busqueda", self.var_tiempo),
                           ("excluir_temporales", self.var_excluir_temp),
                           ("excluir_fuera_roster", self.var_excluir_fuera),
                           ("equipos_otros_roster", self.var_modo_roster)):
            try:
                guardar_preferencia(self.base_dir, clave, var.get())
            except tk.TclError:
                pass
        self._al_cambiar_filtros()

    def crear_interfaz(self):
        cab = ttk.Frame(self.top, padding=(18, 14, 18, 4))
        cab.pack(fill="x")

        # Fila 1: cuenta · rotación de la semana · estado
        f1 = ttk.Frame(cab)
        f1.pack(fill="x")
        ttk.Label(f1, text=tr("CUENTA Y SERVIDOR"), style="Etiqueta.TLabel").grid(row=0, column=0, sticky="w")
        self.combo_servidor = ttk.Combobox(f1, state="readonly", width=40,
                                           values=[etq for etq, _ in self.servidores])
        self.combo_servidor.grid(row=1, column=0, sticky="w", padx=(0, 28))
        self.combo_servidor.bind("<<ComboboxSelected>>", lambda e: self.cargar_servidor())
        ttk.Label(f1, text=tr("ROTACIÓN DE LA SEMANA"), style="Etiqueta.TLabel").grid(row=0, column=1, sticky="w")
        semana = ttk.Frame(f1)
        semana.grid(row=1, column=1, sticky="w")
        self.imgs_rotacion = []
        for i in range(6):
            img = tk.Label(semana, image=self.imagenes.obtener(None, TAM_JEFE_SEMANA), bg=tema.FONDO, bd=0,
                           cursor="hand2")
            img.pack(side="left", padx=(0, 4))
            img.bind("<Button-1>", lambda e: self.editar_rotacion())
            self.imgs_rotacion.append(img)
        ttk.Button(semana, text=tr("✎ Cambiar"), style="Plano.TButton", command=self.editar_rotacion).pack(
            side="left", padx=(4, 0))
        self.lbl_estado = ttk.Label(f1, text="", style="Pequeno.TLabel", wraplength=460, justify="right", anchor="e")
        self.lbl_estado.grid(row=1, column=2, sticky="e")
        f1.columnconfigure(2, weight=1)
        if not self.vis.disponible:
            ttk.Label(cab, foreground=tema.WARN, style="Pequeno.TLabel",
                      text=tr("Faltan las tablas del sitio (nombres e imágenes de jefes, equipo y afijos). "
                              "Se podrán descargar cuando la conexión con el sitio vuelva a estar disponible.")).pack(anchor="w", pady=(4, 0))

        # Fila 2: acciones, filtro y total
        f2 = ttk.Frame(cab)
        f2.pack(fill="x", pady=(14, 0))
        self.btn_optimizar = ttk.Button(f2, text=tr("▶  Optimizar"), style="Acento.TButton",
                                        command=self.ejecutar_optimizacion)
        self.btn_optimizar.pack(side="left")
        ttk.Label(f2, text=tr("con"), style="Muted.TLabel").pack(side="left", padx=(10, 6))
        self.combo_opt_fuente = ttk.Combobox(f2, state="readonly", width=34)
        self.combo_opt_fuente.pack(side="left")
        self.btn_configurar = ttk.Button(f2, text=tr("⚙  Configurar"), command=self.abrir_configurar)
        self.btn_configurar.pack(side="left", padx=(8, 0))
        self.btn_elegir_amigos = self.btn_configurar     # nombre anterior del botón
        buscar = ttk.Frame(f2)
        buscar.pack(side="left", padx=(22, 0))
        ttk.Label(buscar, text="⌕", style="Muted.TLabel", font=(tema.FAMILIA, 13)).pack(side="left")
        self.entrada_filtro = ttk.Entry(buscar, textvariable=self.var_filtro, width=28)
        self.entrada_filtro.pack(side="left", padx=(4, 0))
        ttk.Button(buscar, text="✕", style="Plano.TButton", width=2,
                   command=lambda: self.var_filtro.set("")).pack(side="left")
        self.lbl_ayuda_filtro = ttk.Label(buscar, text=tr("héroes, colección o mascota · «Talimar, Dracula»"),
                                          style="Pequeno.TLabel")
        self.lbl_ayuda_filtro.pack(side="left", padx=(4, 0))
        self.var_filtro.trace_add("write", lambda *a: self.actualizar_explorar())
        total = ttk.Frame(f2)
        total.pack(side="right")
        self.lbl_total = ttk.Label(total, text="", style="Total.TLabel")
        self.lbl_total.pack(anchor="e")
        self.lbl_total_sub = ttk.Label(total, text="", style="Pequeno.TLabel")
        self.lbl_total_sub.pack(anchor="e")

        # Fila 3: bloqueos y opciones activas (chips)
        self.fila_chips = ttk.Frame(cab)
        self.fila_chips.pack(fill="x", pady=(10, 0))

        # Cuerpo: Resumen, una pestaña por jefe, Qué me falta y Explorar. El detalle aparece a la derecha.
        self.cuerpo = ttk.PanedWindow(self.top, orient="horizontal")
        self.cuerpo.pack(fill="both", expand=True, padx=14, pady=(8, 12))
        self.nb_jefes = ttk.Notebook(self.cuerpo)
        self.cuerpo.add(self.nb_jefes, weight=3)
        self.notebook = self.nb_jefes
        self.nb_jefes.bind("<<NotebookTabChanged>>", lambda e: self._al_cambiar_pestana())
        self._crear_tab_resumen()
        self._crear_tab_falta()
        self._crear_tab_estadisticas()
        self._crear_tab_explorar()
        self._crear_panel_detalle(self.cuerpo)
        self._actualizar_chips()

    def _al_cambiar_pestana(self):
        self._refrescar_jefe_actual()
        self._dibujar_explorar_si_visible()
        self._dibujar_resumen_si_visible()
        self._dibujar_falta_si_visible()
        self._dibujar_stats_si_visible()

    def cambiar_tamano(self, tamano):
        if tamano not in TAMANOS or tamano == self._tamano:
            return
        self._tamano = tamano
        guardar_preferencia(self.base_dir, "tamano_iconos", tamano)
        self._reconstruir_tabs_jefes()
        self._llenar_lista_explorar()

    def _tam_tarjeta_jefe(self):
        """Dos tarjetas lado a lado: como mucho el tamaño 'Mediano'."""
        return min(TAMANOS[self._tamano][0], TAMANOS["Mediano"][0])

    def _crear_tab_explorar(self):
        tab = ttk.Frame(self.nb_jefes)
        self.nb_jefes.add(tab, text=tr("⌕ Explorar"))
        tab.boss = None
        self.tab_explorar = tab

        # Modo: equipos contra un jefe, o runs completas ordenadas por tiempo total
        modos = ttk.Frame(tab)
        modos.pack(fill="x", padx=8, pady=(6, 0))
        self.var_modo_explorar = tk.StringVar(value="jefe")
        for valor, texto in (("jefe", N_("Equipos por jefe")), ("runs", N_("Runs completas (tiempo total)"))):
            ttk.Radiobutton(modos, text=tr(texto), value=valor, variable=self.var_modo_explorar, style="Toolbutton",
                            command=self._cambiar_modo_explorar).pack(side="left", padx=(0, 4))
        self.marco_explorar_jefe = ttk.Frame(tab)
        self.marco_explorar_jefe.pack(fill="both", expand=True)
        self.marco_explorar_runs = ttk.Frame(tab)
        self._crear_explorar_runs(self.marco_explorar_runs)
        tab = self.marco_explorar_jefe

        arriba = ttk.Frame(tab)
        arriba.pack(fill="x", padx=8, pady=6)
        ttk.Label(arriba, text=tr("Jefe (de cualquier semana):")).pack(side="left")
        self.combo_jefe = ttk.Combobox(arriba, state="readonly", width=34)
        self.combo_jefe.pack(side="left", padx=4)
        self.combo_jefe.bind("<<ComboboxSelected>>", lambda e: self.actualizar_explorar())
        self.lbl_explorar = ttk.Label(arriba, text="", foreground=tema.MUTED)
        self.lbl_explorar.pack(side="left", padx=10)

        # Tabla con íconos: retrato (SI, grabado, muebles) de cada héroe y la mascota con su nivel.
        # Clic en un ícono: su detalle a la derecha.
        self.lista_explorar = MarcoDesplazable(tab)
        self.lista_explorar.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self._mostrados_explorar = 0

    COLUMNAS_EXPLORAR = (N_("#"), N_("Tiempo"), N_("Héroes"), "", "", "", "", N_("Mascota"), N_("Usos"),
                         N_("Mejor run"), N_("Rotación"))
    LOTE_EXPLORAR = 30

    def _llenar_lista_explorar(self, desde=0):
        """Dibuja las filas [desde, desde+LOTE) de la lista de Explorar (con 'Mostrar más' al final)."""
        interior = self.lista_explorar.interior
        if desde == 0:
            for w in interior.winfo_children():
                w.destroy()
            for col, titulo in enumerate(self.COLUMNAS_EXPLORAR):
                ttk.Label(interior, text=tr(titulo) if titulo else "", font=("Segoe UI", 9, "bold"),
                          foreground=tema.DORADO).grid(row=0, column=col, padx=3, pady=(0, 4),
                                                       sticky="w" if col == 2 else "")
        else:
            for w in interior.grid_slaves(row=desde + 1):
                w.destroy()   # el botón 'Mostrar más' anterior
        tam = self._tam_tarjeta_jefe()
        lista = self.explorar_lista
        hasta = min(len(lista), desde + self.LOTE_EXPLORAR)
        for i in range(desde, hasta):
            c, fila = lista[i], i + 1
            ttk.Label(interior, text=str(i + 1), foreground=tema.MUTED).grid(row=fila, column=0, padx=3)
            ttk.Label(interior, text=formato_tiempo(c.tiempo), font=("Segoe UI", 10, "bold")).grid(
                row=fila, column=1, padx=(3, 8))
            for j in range(5):
                if j < len(c.heroes):
                    h = c.heroes[j]
                    imagen = (self.imagenes.retrato(h, self.vis, c.golden, tam, con_coleccion=False)
                              if self.vis.disponible else self.imagenes.obtener(h.get("imageUrl"), tam))
                    tk.Button(interior, image=imagen, relief="flat", bd=0, cursor="hand2", bg=tema.FONDO,
                              activebackground=tema.PANEL,
                              command=lambda c=c, h=h: self.mostrar_detalle(c, h, "HEROE")).grid(
                        row=fila, column=2 + j, padx=1, pady=2)
            if c.mascota:
                tk.Button(interior, image=self.imagenes.mascota(c.mascota, tam), relief="flat", bd=0,
                          cursor="hand2", bg=tema.FONDO, activebackground=tema.PANEL,
                          command=lambda c=c: self.mostrar_detalle(c, c.mascota, "MASCOTA")).grid(
                    row=fila, column=7, padx=(8, 3), pady=2)
            ttk.Label(interior, text=f"{c.veces}×").grid(row=fila, column=8, padx=6)
            ttk.Label(interior, text=fecha_local(c.fecha)).grid(row=fila, column=9, padx=6)
            ttk.Label(interior, text=c.rotacion, foreground=tema.MUTED).grid(row=fila, column=10, padx=6)
        self._mostrados_explorar = hasta
        if hasta < len(lista):
            ttk.Button(interior, text=tr("Mostrar {0} más (quedan {1})", min(self.LOTE_EXPLORAR, len(lista) - hasta),
                                         len(lista) - hasta),
                       command=lambda: self._llenar_lista_explorar(hasta)).grid(
                row=hasta + 1, column=0, columnspan=11, pady=8)

    # ---------------- explorar: runs completas ----------------

    def _cambiar_modo_explorar(self):
        if self.var_modo_explorar.get() == "runs":
            self.marco_explorar_jefe.pack_forget()
            self.marco_explorar_runs.pack(fill="both", expand=True)
            self.actualizar_runs()
        else:
            self.marco_explorar_runs.pack_forget()
            self.marco_explorar_jefe.pack(fill="both", expand=True)
            self._dibujar_explorar_si_visible()

    def _crear_explorar_runs(self, marco):
        arriba = ttk.Frame(marco)
        arriba.pack(fill="x", padx=8, pady=6)
        ttk.Label(arriba, text=tr("Runs de:")).pack(side="left")
        self.combo_runs_fuente = ttk.Combobox(arriba, state="readonly", width=34)
        self.combo_runs_fuente.pack(side="left", padx=4)
        self.combo_runs_fuente.bind("<<ComboboxSelected>>", lambda e: self.actualizar_runs())
        self.var_runs_semana = tk.BooleanVar(value=True)
        self.var_runs_completas = tk.BooleanVar(value=True)
        self.var_runs_sin_baneos = tk.BooleanVar(value=False)
        for texto, var in ((N_("Solo la rotación de la semana"), self.var_runs_semana),
                           (N_("Solo completas (6/6)"), self.var_runs_completas),
                           (N_("Ocultar runs con baneos o fuera de tus límites"), self.var_runs_sin_baneos)):
            ttk.Checkbutton(arriba, text=tr(texto), variable=var, command=self.actualizar_runs).pack(side="left", padx=6)
        self.lbl_runs = ttk.Label(arriba, text="", foreground=tema.MUTED)
        self.lbl_runs.pack(side="left", padx=8)

        columnas = ["n", "total", "jefes"] + [f"j{i}" for i in range(1, 7)] + ["fecha", "de"]
        self.tabla_runs = ttk.Treeview(marco, columns=columnas, show="headings", height=10)
        anchos = {"n": 40, "total": 105, "jefes": 50, "fecha": 120, "de": 90}
        for col in columnas:
            self.tabla_runs.column(col, width=anchos.get(col, 150), anchor="center" if col in anchos else "w",
                                   stretch=col.startswith("j") and col != "jefes")
        for col, titulo in (("n", "#"), ("total", N_("Tiempo total")), ("jefes", N_("Jefes")),
                            ("fecha", N_("Fecha")), ("de", N_("De"))):
            self.tabla_runs.heading(col, text=tr(titulo))
        self.tabla_runs.tag_configure("mejor", foreground=tema.OK)
        self.tabla_runs.tag_configure("incompleta", foreground=tema.MUTED)
        self.tabla_runs.pack(fill="both", expand=True, padx=8)
        self.tabla_runs.bind("<<TreeviewSelect>>", lambda e: self._al_elegir_run())
        ttk.Label(marco, foreground=tema.MUTED, text=tr(
            "Ordenadas por jefes derrotados y tiempo total. En verde, el jefe donde esa run fue la más rápida de la "
            "lista. Clic en una run para ver sus 6 equipos.")).pack(anchor="w", padx=8, pady=(2, 0))
        self.marco_equipos_run = MarcoDesplazable(marco)
        self.marco_equipos_run.pack(fill="both", expand=True, padx=8, pady=6)
        self.tarjetas_run = []
        self.lista_runs = []

    def _runs_de(self, clave):
        """[(run_id, [comps por posición], de_quien)] de una fuente, sin filtrar."""
        if clave == self._clave_propia():
            comps = list(self.comps)
        else:
            comps = []
            for c in self._carpetas_de(clave):
                comps.extend(self._fuentes.get(str(c)) or [])
            if self._es_mezcla(clave):
                comps = list(self.comps) + comps
        por_run = {}
        for c in comps:
            por_run.setdefault((getattr(c, "dueno", None), c.run_id), []).append(c)
        return [(rid, sorted(cs, key=lambda c: c.posicion), dueno) for (dueno, rid), cs in por_run.items()]

    def actualizar_runs(self):
        if not hasattr(self, "tabla_runs") or self.var_modo_explorar.get() != "runs" or not self.comps:
            return
        i = self.combo_runs_fuente.current()
        clave = self._opciones_fuente[i][1] if 0 <= i < len(self._opciones_fuente) else self._clave_propia()
        if self._pool(clave) is None:
            self.lbl_runs.configure(text=tr("Cargando..."))
            self._asegurar(clave, self.actualizar_runs)
            return
        semana = [b for b in self._rotacion_semanal() if b]
        rotacion6 = (self._rotacion_semanal() + [""] * 6)[:6]
        terminos = self._terminos_filtro()
        filas = []
        for rid, comps, dueno in self._runs_de(clave):
            if self.var_runs_semana.get() and semana and {c.boss_id for c in comps} != set(semana):
                continue
            derrotados = [c for c in comps if c.derrotado]
            if self.var_runs_completas.get() and len(derrotados) < 6:
                continue
            if terminos and not all(any(self._coincide(c, t) for c in comps) for t in terminos):
                continue
            if self.var_runs_sin_baneos.get():
                baneos = (self.baneos_amigos + self.limites) if (comps and id(comps[0]) in self._ids_otro) \
                    else self._baneos_yo()
                if len(quitar_baneadas(comps, rotacion6, baneos)) < len(comps):
                    continue
            filas.append((len(derrotados), sum(c.tiempo for c in derrotados), rid, comps, dueno))
        filas.sort(key=lambda f: (-f[0], f[1]))
        self.lista_runs = filas

        # columnas: los jefes de la semana (en su orden) o 'Jefe 1..6' si se mezclan semanas
        por_jefe = self.var_runs_semana.get() and len(semana) == 6
        for i in range(6):
            if por_jefe and self.vis.disponible:
                nombre, url = self.vis.jefe(semana[i])
                # imagen del jefe en el encabezado de su columna
                self.tabla_runs.heading(f"j{i + 1}", text=f" {tr(nombre)}", image=self.imagenes.obtener(url, 30))
            else:
                self.tabla_runs.heading(f"j{i + 1}", text=semana[i] if por_jefe else tr("Jefe {0}", i + 1), image="")
        mejor_por_jefe = {}
        for _, _, _, comps, _ in filas:
            for c in comps:
                if c.derrotado:
                    mejor_por_jefe[c.boss_id] = min(mejor_por_jefe.get(c.boss_id, 1e9), c.tiempo)

        self.tabla_runs.delete(*self.tabla_runs.get_children())
        for n, (jefes, total, rid, comps, dueno) in enumerate(filas, 1):
            celdas = []
            orden = ({c.boss_id: c for c in comps}.get(b) for b in semana) if por_jefe else iter(comps)
            for c in list(orden)[:6]:
                if c is None:
                    celdas.append("—")
                    continue
                texto = formato_tiempo(c.tiempo) if c.derrotado else tr("✗ no derrotado")
                if c.derrotado and abs(c.tiempo - mejor_por_jefe.get(c.boss_id, -1)) < 0.0005:
                    texto = "★ " + texto
                celdas.append(texto if por_jefe else f"{self.vis.jefe(c.boss_id)[0] if self.vis.disponible else c.boss_id}: {texto}")
            celdas += [""] * (6 - len(celdas))
            tag = ("incompleta",) if jefes < 6 else (("mejor",) if n == 1 else ())
            self.tabla_runs.insert("", "end", iid=str(n - 1), tags=tag, values=(
                n, formato_tiempo(total), f"{jefes}/6", *celdas, fecha_local(comps[0].fecha), dueno or tr("tú")))
        mejor = formato_tiempo(filas[0][1]) if filas and filas[0][0] == 6 else "—"
        self.lbl_runs.configure(text=tr("{0} runs · mejor total {1}", len(filas), mejor))
        if filas:
            self.tabla_runs.selection_set("0")

    def _al_elegir_run(self):
        sel = self.tabla_runs.selection()
        if not sel or int(sel[0]) >= len(self.lista_runs):
            return
        jefes, total, rid, comps, dueno = self.lista_runs[int(sel[0])]
        for t in self.tarjetas_run:
            t.destroy()
        self.tarjetas_run = []
        interior = self.marco_equipos_run.interior
        for c in range(2):
            interior.columnconfigure(c, weight=1)
        for i, comp in enumerate(comps):
            t = TarjetaEquipo(interior, self.imagenes, self.mostrar_detalle, vis=self.vis, tam=TAMANOS["Pequeño"][0])
            t.grid(row=i // 2, column=i % 2, sticky="nsew", padx=4, pady=4)
            estado = formato_tiempo(comp.tiempo) if comp.derrotado else tr("no derrotado")
            t.mostrar(comp, f"{comp.posicion}. {self._etiqueta_jefe(comp.boss_id)} · {estado}")
            self.tarjetas_run.append(t)

    # ---------------- bloqueos (baneos + límites) y roster ----------------

    def _baneos_yo(self):
        """Reglas que valen para tus equipos."""
        return list(self.baneos) + list(self.limites)

    def _anotar_estrellas(self, comps):
        """Guarda en cada colección su nivel de habilidad (★), para poder limitar por él."""
        if not self.vis.disponible:
            return
        for c in comps:
            for h in c.heroes:
                col = h.get("collection")
                if col and "estrellas" not in col:
                    col["estrellas"] = self.vis.estrellas_coleccion(col) or 0

    def _cargar_reglas(self):
        self.reglas = blq.cargar_bloqueos(self.carpeta, self._carpeta_baneos_amigos())
        self._aplicar_reglas()

    def _aplicar_reglas(self):
        self.baneos = blq.para(self.reglas, blq.APLICA_YO)
        self.baneos_amigos = blq.para(self.reglas, blq.APLICA_AMIGOS)
        self.limites = []

    def guardar_reglas(self, reglas, aviso=True):
        """Guarda la lista completa de bloqueos y recalcula lo que se ve."""
        if not self.carpeta:
            return
        self.reglas = blq.sin_duplicados([dict(b) for b in reglas])
        try:
            blq.guardar_bloqueos(self.carpeta, self.reglas)
        except OSError as error:
            self._estado(tr("No se pudieron guardar los bloqueos: {0}", error), tema.ERR)
        self._aplicar_reglas()
        self._actualizar_chips()
        self.actualizar_explorar()
        if aviso and (self._optimo_por_jefe or self._optimo_otro):
            self._estado(tr("Bloqueos cambiados. Pulsa ▶ Optimizar para recalcular."), tema.WARN)

    def _alternar_regla(self, regla):
        regla["activo"] = not regla.get("activo", True)
        self.guardar_reglas(self.reglas)

    def recargar_perfil(self):
        """Tu roster (inventario + correcciones a mano)."""
        self.perfil = rst.cargar_perfil(self.carpeta, self.vis) if self.carpeta else None
        self._evaluaciones = {}
        self._cache_otros = None

    def evaluar(self, comp):
        """(nivel, faltas) de un equipo según tu roster (en caché)."""
        clave = id(comp)
        if clave not in self._evaluaciones:
            nombre = self.vis.nombre_calidad if self.vis.disponible else None
            self._evaluaciones[clave] = rst.evaluar_equipo(comp, self.perfil, nombre)
        return self._evaluaciones[clave]

    def _filtro_roster(self, comps):
        """Equipos de otros que puedes armar (según 'Búsqueda → Equipos de amigos')."""
        modo = self.var_modo_roster.get()
        if modo not in ("casi", "ok") or not rst.hay_datos(self.perfil):
            return list(comps)
        permitidos = {rst.PUEDO} if modo == "ok" else {rst.PUEDO, rst.CASI}
        return [c for c in comps if self.evaluar(c)[0] in permitidos]

    def abrir_configurar(self, pestana="fuentes", objeto=None, nombre=None):
        """Ventana '⚙ Configurar': fuentes, bloqueos, mi roster, búsqueda y vista."""
        if not self.carpeta:
            return
        from aplicacion.optimizador_ajustes import VentanaConfigurar
        VentanaConfigurar(self, pestana, objeto=objeto, nombre=nombre)

    # nombres anteriores
    def abrir_fuentes(self):
        self.abrir_configurar("fuentes")

    def abrir_limites(self, objeto=None, nombre=None):
        self.abrir_configurar("bloqueos", objeto, nombre)

    def abrir_baneos(self):
        self.abrir_configurar("bloqueos")

    abrir_baneos_amigos = abrir_baneos

    def limitar_seleccion(self):
        """Desde el detalle: abre los bloqueos con el héroe ya elegido."""
        if not self.seleccion:
            return
        _, obj, tipo = self.seleccion
        if tipo == "HEROE":
            self.abrir_configurar("bloqueos", "HEROE", obj.get("name"))

    def _nombre_jefe(self, boss):
        return tr(self.vis.jefe(boss)[0]) if self.vis.disponible else tr("jefe {0}", boss)

    def _actualizar_chips(self):
        """Fila de 'Activos': cada bloqueo y opción no habitual, con ✕ para quitarlo (y '+N más…')."""
        if not hasattr(self, "fila_chips"):
            return
        for w in self.fila_chips.winfo_children():
            w.destroy()
        chips = []   # (texto, al_quitar, color)
        for b in self.reglas:
            if b.get("activo", True):
                texto = blq.describir(b, etiqueta_jefe=self._nombre_jefe)
                aplica = b.get("aplica", blq.APLICA_TODO)
                if aplica == blq.APLICA_YO:
                    texto += " · " + tr("tus equipos")
                elif aplica == blq.APLICA_AMIGOS:
                    texto += " · " + tr("amigos")
                chips.append((texto, lambda b=b: self._alternar_regla(b), tema.TEXTO))
        for activo, texto, var, defecto in (
                (not self.var_completas.get(), N_("Incluye runs incompletas"), self.var_completas, True),
                (not self.var_mascota.get(), N_("Mascotas repetibles"), self.var_mascota, True),
                (self.var_excluir_temp.get(), N_("Sin prestados / prueba"), self.var_excluir_temp, False),
                (self.var_excluir_fuera.get(), N_("Sin héroes fuera de tu roster"), self.var_excluir_fuera, False)):
            if activo:
                chips.append((tr(texto), lambda v=var, d=defecto: (v.set(d), self.guardar_opciones_busqueda()),
                              tema.INFO))
        modo = self.var_modo_roster.get()
        if modo in ("casi", "ok"):
            chips.append((tr("Amigos: solo lo que puedes armar ✅") if modo == "ok"
                          else tr("Amigos: solo lo que puedes armar ✅🟡"),
                          lambda: (self.var_modo_roster.set("todos"), self.guardar_opciones_busqueda()), tema.INFO))
        if not chips:
            ttk.Label(self.fila_chips, style="Pequeno.TLabel", text=tr(
                "Sin bloqueos. En ⚙ Configurar puedes quitar héroes, colecciones o builds que no tienes.")).pack(
                side="left")
            return
        ttk.Label(self.fila_chips, text=tr("ACTIVOS"), style="Etiqueta.TLabel").pack(side="left", padx=(0, 8))
        for texto, quitar, color in chips[:MAX_CHIPS]:
            tema.Chip(self.fila_chips, texto, al_quitar=quitar, color=color).pack(side="left", padx=(0, 6))
        if len(chips) > MAX_CHIPS:
            tema.Chip(self.fila_chips, tr("+{0} más…", len(chips) - MAX_CHIPS), color=tema.DORADO,
                      al_clic=lambda: self.abrir_configurar("bloqueos")).pack(side="left")
        else:
            ttk.Button(self.fila_chips, text=tr("Editar…"), style="Plano.TButton",
                       command=lambda: self.abrir_configurar("bloqueos")).pack(side="left")

    _actualizar_boton_baneos = _actualizar_chips

    # ---------------- rotación ----------------

    def _rotacion_semanal(self):
        """Los 6 jefes de la semana (vacíos incluidos, para conservar la posición)."""
        return list(self._rotacion)

    def rotacion_reciente(self):
        return sorted(rotacion_mas_reciente(self.runs), key=orden_boss)

    def usar_rotacion_reciente(self):
        """Rotación de tu run más reciente, ordenada por ID de jefe (los ID de jefe nuevos son siempre mayores)."""
        self.poner_rotacion(self.rotacion_reciente())

    def poner_rotacion(self, ids):
        self._rotacion = [str(b).strip() for b in (list(ids) + [""] * 6)[:6]]
        self._actualizar_nombres_rotacion()

    def editar_rotacion(self):
        if not self.comps:
            return
        from aplicacion.optimizador_ajustes import VentanaRotacion
        VentanaRotacion(self)

    def _actualizar_nombres_rotacion(self):
        """Miniaturas de la cabecera; las pestañas siguen a la rotación."""
        for boss, img in zip(self._rotacion, self.imgs_rotacion):
            url = self.vis.jefe(boss)[1] if (boss and self.vis.disponible) else None
            img.configure(image=self.imagenes.obtener(url, TAM_JEFE_SEMANA))
        # La optimización anterior ya no vale si cambió la rotación
        if (self._optimo_por_jefe or self._optimo_otro) and tuple(self._rotacion) != self._rotacion_optimizada:
            self.resultado, self._optimo_por_jefe, self._optimo_otro, self._total_yo = None, {}, None, None
            self._ultimo_optimo = None
            self.lbl_resumen.configure(text=tr("La rotación cambió: pulsa ▶ Optimizar para recalcular."))
            self.lbl_total.configure(text="")
            self.lbl_total_sub.configure(text="")
        if hasattr(self, "tab_explorar"):
            self._reconstruir_tabs_jefes(forzar=False)

    # ---------------- acciones desde otras secciones ----------------

    def ir_a_explorar(self):
        self.var_modo_explorar.set("jefe")
        self._cambiar_modo_explorar()
        self.nb_jefes.select(self.tab_explorar)

    def _ir_a_jefe(self, boss):
        pagina = self._paginas_jefe.get(str(boss))
        if pagina:
            self.nb_jefes.select(pagina["marco"])

    def abrir_en(self, carpeta=None, enfoque=None):
        """Cambia al servidor `carpeta` (si hace falta) y enfoca un héroe / jefe."""
        if carpeta is not None and (not self.carpeta or Path(carpeta) != Path(self.carpeta)):
            for i, (_, c) in enumerate(self.servidores):
                if Path(c) == Path(carpeta):
                    self._enfoque_pendiente = enfoque
                    self.combo_servidor.current(i)
                    self.cargar_servidor()
                    return
        if enfoque:
            self.enfocar(enfoque.get("texto", ""), enfoque.get("boss"))

    def optimizar_con_carpeta(self, carpeta):
        """Optimiza con las runs de una carpeta (p. ej. un amigo, desde la sección Amigos)."""
        if self._ocupado or not self.comps:
            self._pendiente_opt = carpeta
            return
        self._preparar_fuentes()
        clave = ("carpeta", str(Path(carpeta)))
        i = self._indice_fuente(clave)
        if self._opciones_fuente[i][1] != clave:
            self._estado(tr("Esa carpeta no tiene runs con detalle."), tema.WARN)
            return
        self.combo_opt_fuente.current(i)
        self.ejecutar_optimizacion()

    def recargar_fuentes(self):
        """Se importaron o borraron runs / amigos: vuelve a leer las carpetas."""
        self.servidores = listar_servidores(self.base_dir)
        self.combo_servidor.configure(values=[e for e, _ in self.servidores])
        self._fuentes.clear()
        self._ids_otro = set()
        self._evaluaciones = {}
        self._cache_otros = None
        if not self.servidores:
            return
        indice = next((i for i, (_, c) in enumerate(self.servidores)
                       if self.carpeta and Path(c) == Path(self.carpeta)), 0)
        self.combo_servidor.current(indice)
        if not self._ocupado:
            self.cargar_servidor()

    # ---------------- pestaña Resumen ----------------

    def _crear_tab_resumen(self):
        tab = ttk.Frame(self.nb_jefes)
        tab.boss = None
        self.nb_jefes.add(tab, text=tr("★ Resumen"))
        self.tab_resumen = tab
        self.lbl_resumen = ttk.Label(tab, style="Muted.TLabel", wraplength=1150, justify="left", text=tr(
            "Pulsa ▶ Optimizar para elegir el mejor equipo de cada jefe sin repetir héroes."))
        self.lbl_resumen.pack(anchor="w", padx=14, pady=(12, 4))
        self.marco_resumen = MarcoDesplazable(tab)
        self.marco_resumen.pack(fill="both", expand=True, padx=8, pady=(0, 6))
        self._resumen_pendiente = True

    def _dibujar_resumen_si_visible(self):
        try:
            visible = self.nb_jefes.select() == str(self.tab_resumen)
        except tk.TclError:
            return
        if visible and self._resumen_pendiente:
            self._resumen_pendiente = False
            self._llenar_resumen()

    def _llenar_resumen(self):
        interior = self.marco_resumen.interior
        for w in interior.winfo_children():
            w.destroy()
        if not self.comps:
            return
        optimo = self._ultimo_optimo
        mios = self._candidatos_yo()
        otros = self._candidatos_otros()
        for c in range(3):
            interior.columnconfigure(c, weight=1, uniform="resumen")
        n = 0
        for pos, boss in enumerate(self._rotacion_semanal(), 1):
            if not boss:
                continue
            lista_mios = self._filtrar(mios.get(boss) or [])
            comp = optimo["por_jefe"].get(boss) if optimo else (lista_mios[0] if lista_mios else None)
            tarjeta = self._tarjeta_resumen(interior, pos, boss, comp, lista_mios,
                                            self._filtrar((otros or {}).get(boss) or []), optimo is not None,
                                            otros is None)
            tarjeta.grid(row=n // 3, column=n % 3, sticky="nsew", padx=6, pady=6)
            n += 1
        if not n:
            ttk.Label(interior, text=tr("Elige la rotación de la semana (✎ Cambiar)."), style="Muted.TLabel").grid(
                row=0, column=0, sticky="w", padx=10, pady=10)

    def _tarjeta_resumen(self, padre, pos, boss, comp, mios, otros, optimizado, cargando):
        t = ttk.Frame(padre, style="Tarjeta.TFrame", padding=14)
        cab = ttk.Frame(t, style="Panel.TFrame")
        cab.pack(fill="x")
        nombre, url = self.vis.jefe(boss) if self.vis.disponible else (str(boss), None)
        img = tk.Label(cab, image=self.imagenes.obtener(url, 46), bg=tema.PANEL, bd=0, cursor="hand2")
        img.pack(side="left")
        img.bind("<Button-1>", lambda e: self._ir_a_jefe(boss))
        textos = ttk.Frame(cab, style="Panel.TFrame")
        textos.pack(side="left", padx=10, fill="x", expand=True)
        ttk.Label(textos, text=f"{pos}. {tr(nombre)}", style="TarjetaTitulo.TLabel").pack(anchor="w")
        ttk.Label(textos, style="TarjetaTexto.TLabel", text=tr("ID {0} · {1}", boss, tr("elegido al optimizar") if optimizado
                                                              else tr("tu mejor equipo (sin optimizar)"))).pack(anchor="w")
        ttk.Label(cab, text=formato_tiempo(comp.tiempo) if comp else "—", style="TarjetaTiempo.TLabel").pack(
            side="right", anchor="n")

        if comp is None:
            ttk.Label(t, text=tr("Sin equipos con estos filtros y bloqueos."), style="TarjetaTexto.TLabel").pack(
                anchor="w", pady=(12, 0))
        else:
            fila = ttk.Frame(t, style="Panel.TFrame")
            fila.pack(anchor="w", pady=(12, 8))
            for h in comp.heroes:
                imagen = (self.imagenes.retrato(h, self.vis, comp.golden, TAM_RESUMEN, con_coleccion=False)
                          if self.vis.disponible else self.imagenes.obtener(h.get("imageUrl"), TAM_RESUMEN))
                b = tk.Label(fila, image=imagen, bg=tema.PANEL, bd=0, cursor="hand2")
                b.pack(side="left", padx=1)
                b.bind("<Button-1>", lambda e, c=comp, h=h: self.mostrar_detalle(c, h, "HEROE"))
            if comp.mascota:
                b = tk.Label(fila, image=self.imagenes.mascota(comp.mascota, TAM_RESUMEN), bg=tema.PANEL, bd=0,
                             cursor="hand2")
                b.pack(side="left", padx=(8, 0))
                b.bind("<Button-1>", lambda e, c=comp: self.mostrar_detalle(c, c.mascota, "MASCOTA"))
            dueno = getattr(comp, "dueno", None)
            linea, color = tr("De: {0}", dueno or tr("tú")), tema.MUTED
            if dueno:
                nivel, faltas = self.evaluar(comp)
                if nivel:
                    color = {rst.PUEDO: tema.OK, rst.CASI: tema.WARN, rst.NO_PUEDO: tema.ERR}[nivel]
                    detalle = "; ".join(f["texto"] for f in faltas[:2]) + ("…" if len(faltas) > 2 else "")
                    linea += f"   {rst.ICONO_NIVEL[nivel]} " + (detalle or tr(rst.TEXTO_NIVEL[nivel]))
            ttk.Label(t, text=linea, style="TarjetaTexto.TLabel", foreground=color, wraplength=380,
                      justify="left").pack(anchor="w")
        texto, color = self._comparacion_resumen(comp, mios, otros, cargando)
        if texto:
            ttk.Label(t, text=texto, style="TarjetaTexto.TLabel", foreground=color, wraplength=380,
                      justify="left").pack(anchor="w", pady=(4, 0))
        ttk.Button(t, text=tr("Ver jefe  →"), style="Plano.TButton", command=lambda: self._ir_a_jefe(boss)).pack(
            anchor="e", pady=(8, 0))
        for w in (t, cab, textos):
            w.bind("<Double-1>", lambda e: self._ir_a_jefe(boss))
        return t

    def _comparacion_resumen(self, comp, mios, otros, cargando):
        """Una línea: cuánto más rápido lo hace otro (y si puedes copiarlo), o cómo te va con tu equipo."""
        if comp is None:
            return "", tema.MUTED
        if getattr(comp, "dueno", None):
            if mios:
                d = comp.tiempo - mios[0].tiempo
                return tr("Tu mejor equipo: {0} ({1:+.3f} s)", formato_tiempo(mios[0].tiempo), -d), tema.MUTED
            return tr("No tienes equipos tuyos contra este jefe."), tema.MUTED
        if cargando:
            return tr("Cargando equipos de amigos…"), tema.MUTED
        if not self._carpetas_de(("otros", None)):
            return "", tema.MUTED
        mas_rapido = next((c for c in otros if c.tiempo < comp.tiempo - 0.0005), None)
        if mas_rapido is None:
            return tr("✓ Nadie más lo hace más rápido."), tema.OK
        nivel, _ = self.evaluar(mas_rapido)
        icono = f" {rst.ICONO_NIVEL[nivel]}" if nivel else ""
        return (tr("Más rápido: {0} de {1} (−{2:.3f} s){3}", formato_tiempo(mas_rapido.tiempo),
                   getattr(mas_rapido, "dueno", None) or "?", comp.tiempo - mas_rapido.tiempo, icono), tema.WARN)

    def _candidatos_otros(self):
        """{boss: [equipos de las demás carpetas]} (amigos y tus otros servidores) o None si se están cargando."""
        clave = ("otros", None)
        if not self.carpeta or not self._carpetas_de(clave):
            return {}
        if self._cache_otros and self._cache_otros[0] == self._version_jefes:
            return self._cache_otros[1]
        pool = self._pool(clave, con_roster=False)
        if pool is None:
            if not getattr(self, "_cargando_otros", False):
                self._cargando_otros = True

                def listo():
                    self._cargando_otros = False
                    self._invalidar_jefes()
                self._asegurar(clave, listo)
            return None
        rotacion = (self._rotacion_semanal() + [""] * 6)[:6]
        cands, _ = candidatos_por_jefe(pool[0], rotacion, self._opciones(), pool[1])
        salida = {boss: list(cands.get(pos, [])) for pos, boss in enumerate(rotacion, 1) if boss}
        self._cache_otros = (self._version_jefes, salida)
        return salida

    # ---------------- pestaña Estadísticas ----------------

    COL_STATS = (("heroe", N_("Héroe"), 190, "w"), ("sp", N_("SP"), 44, "center"), ("dano", N_("Daño"), 90, "e"),
                 ("pct", N_("% del daño"), 70, "e"), ("barra", "", 130, "w"), ("cura", N_("Curación"), 90, "e"),
                 ("defensa", N_("Defensa"), 90, "e"), ("kills", N_("Kills"), 50, "center"),
                 ("energia", N_("Energía"), 70, "e"), ("vida", N_("Vida"), 60, "e"))

    def _crear_tab_estadisticas(self):
        tab = ttk.Frame(self.nb_jefes)
        tab.boss = None
        self.nb_jefes.add(tab, text=tr("📊 Estadísticas"))
        self.tab_stats = tab
        arriba = ttk.Frame(tab, padding=(14, 12, 14, 4))
        arriba.pack(fill="x")
        ttk.Label(arriba, text=tr("Run:")).pack(side="left")
        self.combo_stats = ttk.Combobox(arriba, state="readonly", width=72)
        self.combo_stats.pack(side="left", padx=6)
        self.combo_stats.bind("<<ComboboxSelected>>", lambda e: self._llenar_stats())
        self.var_stats_solo = tk.BooleanVar(value=True)
        ttk.Checkbutton(arriba, text=tr("Solo runs con estadísticas"), variable=self.var_stats_solo,
                        command=self._preparar_stats).pack(side="left", padx=10)
        self.var_stats_semana = tk.BooleanVar(value=False)
        ttk.Checkbutton(arriba, text=tr("Solo jefes de esta semana"), variable=self.var_stats_semana,
                        command=self._preparar_stats).pack(side="left")
        self.lbl_stats = ttk.Label(tab, text="", style="Muted.TLabel", wraplength=1150, justify="left")
        self.lbl_stats.pack(anchor="w", padx=14, pady=(2, 4))
        self.marco_stats = MarcoDesplazable(tab)
        self.marco_stats.pack(fill="both", expand=True, padx=8, pady=(0, 6))
        self._runs_stats = []
        self._stats_pendiente = True

    def _dibujar_stats_si_visible(self):
        try:
            visible = self.nb_jefes.select() == str(self.tab_stats)
        except tk.TclError:
            return
        if visible and self._stats_pendiente:
            self._stats_pendiente = False
            self._preparar_stats()

    @staticmethod
    def _tiene_stats(comps):
        return any(h.get("stats") for c in comps for h in c.heroes)

    def _preparar_stats(self):
        """Lista de runs (tuyas y de lo que esté cargado de amigos), la más reciente primero."""
        anterior = self._runs_stats[self.combo_stats.current()][0] if 0 <= self.combo_stats.current() < len(
            self._runs_stats) else None
        comps = list(self.comps)
        for cargados in self._fuentes.values():
            comps.extend(cargados)
        por_run = {}
        for c in comps:
            por_run.setdefault((getattr(c, "dueno", None), c.run_id), []).append(c)
        semana = {b for b in self._rotacion_semanal() if b}
        runs = []
        for clave, cs in por_run.items():
            cs = sorted(cs, key=lambda c: c.posicion)
            con = self._tiene_stats(cs)
            if self.var_stats_solo.get() and not con:
                continue
            if self.var_stats_semana.get() and semana and {c.boss_id for c in cs} != semana:
                continue
            runs.append((clave, cs, con))
        runs.sort(key=lambda r: str(r[1][0].fecha), reverse=True)
        self._runs_stats = runs
        valores = []
        for (dueno, _), cs, con in runs:
            hechos = [c for c in cs if c.derrotado]
            valores.append(f"{fecha_local(cs[0].fecha)} · {formato_tiempo(sum(c.tiempo for c in hechos))} · "
                           f"{len(hechos)}/{len(cs)} · {dueno or tr('tú')}" + ("" if con else "  · " + tr("sin estadísticas")))
        self.combo_stats.configure(values=valores)
        if runs:
            claves = [r[0] for r in runs]
            self.combo_stats.current(claves.index(anterior) if anterior in claves else 0)
        else:
            self.combo_stats.set("")
        self._llenar_stats()

    def ver_estadisticas(self, comp):
        """Desde el detalle: abre la pestaña con la run de ese equipo."""
        self.var_stats_solo.set(False)
        self.var_stats_semana.set(False)
        self._stats_pendiente = False
        self._preparar_stats()
        clave = (getattr(comp, "dueno", None), comp.run_id)
        for i, (k, _, _) in enumerate(self._runs_stats):
            if k == clave:
                self.combo_stats.current(i)
                break
        self._llenar_stats(enfocar=comp.posicion)
        self.nb_jefes.select(self.tab_stats)

    @staticmethod
    def _cifra(n):
        n = float(n or 0)
        for limite, sufijo in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
            if abs(n) >= limite:
                return f"{n / limite:.2f}{sufijo}"
        return f"{n:.0f}"

    def _llenar_stats(self, enfocar=None):
        interior = self.marco_stats.interior
        for w in interior.winfo_children():
            w.destroy()
        i = self.combo_stats.current()
        if not self._runs_stats or i < 0:
            self.lbl_stats.configure(text=tr(
                "No hay runs con estadísticas. Las runs descargadas del sitio no traen daño ni curación: importa "
                "afk-runs.json (Ajustes → Importar / exportar) y se les suman a las que ya tienes."))
            return
        _, comps, con = self._runs_stats[i]
        self.lbl_stats.configure(text=tr(
            "Daño, curación y defensa de cada héroe en cada jefe. Energía y vida: cómo terminó la ronda. "
            "SP: ✦ lo usó · — no lo usó · ? no se sabe (márcalo en el detalle del héroe).") if con else tr(
            "Esta run no tiene estadísticas (viene del sitio). Importa afk-runs.json para sumárselas."))
        destino = None
        for comp in comps:
            caja = self._tarjeta_stats(interior, comp)
            caja.pack(fill="x", padx=6, pady=6)
            if enfocar is not None and comp.posicion == enfocar:
                destino = caja
        if destino is not None:
            self.top.after(50, lambda: self._desplazar_a(destino))

    def _desplazar_a(self, widget):
        try:
            alto = max(1, self.marco_stats.interior.winfo_height())
            self.marco_stats.canvas.yview_moveto(widget.winfo_y() / alto)
        except tk.TclError:
            pass

    def _tarjeta_stats(self, padre, comp):
        caja = ttk.Frame(padre, style="Tarjeta.TFrame", padding=12)
        cab = ttk.Frame(caja, style="Panel.TFrame")
        cab.pack(fill="x")
        nombre, url = self.vis.jefe(comp.boss_id) if self.vis.disponible else (str(comp.boss_id), None)
        ttk.Label(cab, image=self.imagenes.obtener(url, 36), style="Tarjeta.TLabel").pack(side="left")
        ttk.Label(cab, text=f"{comp.posicion}. {tr(nombre)}", style="TarjetaTitulo.TLabel").pack(side="left", padx=10)
        ttk.Label(cab, text=formato_tiempo(comp.tiempo) if comp.derrotado else tr("✗ no derrotado"),
                  style="TarjetaTiempo.TLabel").pack(side="right")
        jefe = (comp.estadisticas or {}).get("jefe") or {}
        if jefe:
            ttk.Label(caja, style="TarjetaTexto.TLabel", text=tr(
                "Jefe: vida al final {0}% · daño que hizo {1}", f"{jefe.get('hp_pct', 0) / 100:.1f}",
                self._cifra(jefe.get("damage")))).pack(anchor="w", pady=(4, 0))
        filas = []
        mascota_stats = (comp.estadisticas or {}).get("mascota") or {}
        total = sum((h.get("stats") or {}).get("damage", 0) for h in comp.heroes) + mascota_stats.get("damage", 0)
        for h in comp.heroes:
            s = h.get("stats") or {}
            sp = self.vis.usa_sp(h, comp.golden) if self.vis.disponible else None
            marca = {True: "✦", False: "—", "?": "?"}.get(sp, "")
            pct = 100 * s.get("damage", 0) / total if total else 0
            filas.append((h.get("name", "?").split(" - ")[0], marca,
                          self._cifra(s.get("damage")) if s else "—", f"{pct:.1f}%" if s else "",
                          "█" * int(round(pct / 4)), self._cifra(s.get("heal")) if s else "—",
                          self._cifra(s.get("defend")) if s else "—", s.get("kill", "") if s else "",
                          f"{s.get('mp_pct', 0) / 100:.0f}%" if s else "", f"{s.get('hp_pct', 0) / 100:.0f}%" if s else "",
                          "sp_dudoso" if sp == "?" else ("sp" if sp is True else "")))
        if comp.mascota:
            pct = 100 * mascota_stats.get("damage", 0) / total if total and mascota_stats else 0
            filas.append((f"🐾 {comp.mascota.get('name', '?')}", "",
                          self._cifra(mascota_stats.get("damage")) if mascota_stats else "—",
                          f"{pct:.1f}%" if mascota_stats else "", "█" * int(round(pct / 4)),
                          self._cifra(mascota_stats.get("heal")) if mascota_stats else "—", "", "", "", "", "mascota"))
        tabla = ttk.Treeview(caja, columns=[c for c, *_ in self.COL_STATS], show="headings", height=len(filas))
        for col, titulo, ancho, anchor in self.COL_STATS:
            tabla.heading(col, text=tr(titulo) if titulo else "")
            tabla.column(col, width=ancho, anchor=anchor, stretch=col in ("heroe", "barra"))
        tabla.tag_configure("sp", foreground=tema.DORADO)
        tabla.tag_configure("sp_dudoso", foreground=tema.ERR)
        tabla.tag_configure("mascota", foreground=tema.MUTED)
        for k, fila in enumerate(filas):
            *valores, tag = fila
            tabla.insert("", "end", iid=str(k), values=valores, tags=(tag,) if tag else ())
        tabla.pack(fill="x", pady=(8, 0))
        tabla.bind("<<TreeviewSelect>>", lambda e, t=tabla, c=comp: self._stats_elegir(t, c))
        return caja

    def _stats_elegir(self, tabla, comp):
        sel = tabla.selection()
        if not sel:
            return
        k = int(sel[0])
        if k < len(comp.heroes):
            self.mostrar_detalle(comp, comp.heroes[k], "HEROE")
        elif comp.mascota:
            self.mostrar_detalle(comp, comp.mascota, "MASCOTA")

    # ---------------- pestaña Qué me falta ----------------

    COL_FALTA = (("jefe", N_("Jefe"), 170, "w"), ("tuyo", N_("Tu mejor"), 95, "center"),
                 ("tiempo", N_("Su tiempo"), 95, "center"), ("ganas", N_("Ganas"), 85, "center"),
                 ("de", N_("De"), 110, "w"), ("puedes", N_("¿Puedes?"), 75, "center"),
                 ("equipo", N_("Equipo"), 290, "w"), ("falta", N_("Qué te falta"), 380, "w"))

    def _crear_tab_falta(self):
        tab = ttk.Frame(self.nb_jefes)
        tab.boss = None
        self.nb_jefes.add(tab, text=tr("🎯 Qué me falta"))
        self.tab_falta = tab
        ttk.Label(tab, style="Muted.TLabel", wraplength=1150, justify="left", text=tr(
            "Equipos de tus amigos (y de tus otros servidores) más rápidos que tu mejor equipo en cada jefe de esta "
            "semana, y qué te falta para copiarlos según 'Mi roster'. Clic en uno para compararlo en su jefe.")).pack(
            anchor="w", padx=14, pady=(12, 4))
        self.lbl_falta = ttk.Label(tab, text="", style="Muted.TLabel", wraplength=1150, justify="left")
        self.lbl_falta.pack(anchor="w", padx=14)
        self.marco_mejoras = ttk.Frame(tab, style="Tarjeta.TFrame", padding=14)
        self.marco_mejoras.pack(fill="x", padx=14, pady=(8, 8))
        marco = ttk.Frame(tab)
        marco.pack(fill="both", expand=True, padx=14, pady=(0, 10))
        self.tabla_falta = ttk.Treeview(marco, columns=[c for c, *_ in self.COL_FALTA], show="headings")
        for col, titulo, ancho, anchor in self.COL_FALTA:
            self.tabla_falta.heading(col, text=tr(titulo))
            self.tabla_falta.column(col, width=ancho, anchor=anchor, stretch=col in ("equipo", "falta"))
        self.tabla_falta.tag_configure(rst.PUEDO, foreground=tema.OK)
        self.tabla_falta.tag_configure(rst.CASI, foreground=tema.WARN)
        self.tabla_falta.tag_configure(rst.NO_PUEDO, foreground=tema.ERR)
        barra = ttk.Scrollbar(marco, orient="vertical", command=self.tabla_falta.yview)
        self.tabla_falta.configure(yscrollcommand=barra.set)
        self.tabla_falta.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")
        self.tabla_falta.bind("<<TreeviewSelect>>", lambda e: self._al_elegir_falta())
        self._filas_falta = []
        self._falta_pendiente = True

    def _dibujar_falta_si_visible(self):
        try:
            visible = self.nb_jefes.select() == str(self.tab_falta)
        except tk.TclError:
            return
        if visible and self._falta_pendiente:
            self._falta_pendiente = False
            self._llenar_falta()

    def calcular_faltas(self):
        """Filas [{boss, pos, mi, comp, nivel, faltas, gana}] o None si faltan datos por cargar."""
        otros = self._candidatos_otros()
        if otros is None:
            return None
        mios = self._candidatos_yo()
        filas = []
        for pos, boss in enumerate(self._rotacion_semanal(), 1):
            if not boss:
                continue
            lista = self._filtrar(mios.get(boss) or [])
            mi = lista[0] if lista else None
            base = mi.tiempo if mi else None
            n = 0
            for c in self._filtrar(otros.get(boss) or []):
                if base is not None and c.tiempo >= base - 0.0005:
                    break
                nivel, faltas = self.evaluar(c)
                filas.append({"boss": boss, "pos": pos, "mi": mi, "comp": c, "nivel": nivel, "faltas": faltas,
                              "gana": (base - c.tiempo) if base is not None else None})
                n += 1
                if n >= MAX_FALTA_POR_JEFE:
                    break
        filas.sort(key=lambda f: -(f["gana"] if f["gana"] is not None else 1e6))
        return filas

    def _llenar_falta(self):
        tabla = self.tabla_falta
        tabla.delete(*tabla.get_children())
        for w in self.marco_mejoras.winfo_children():
            w.destroy()
        self._filas_falta = []
        if not self.comps:
            return
        if not self._carpetas_de(("otros", None)):
            self.lbl_falta.configure(text=tr("Aún no hay runs de amigos. Impórtalas en 'Amigos' para ver qué equipos "
                                             "más rápidos podrías copiar."), foreground=tema.WARN)
            ttk.Label(self.marco_mejoras, text=tr("Sin datos para comparar."), style="TarjetaTexto.TLabel").pack(anchor="w")
            return
        filas = self.calcular_faltas()
        if filas is None:
            self.lbl_falta.configure(text=tr("Cargando equipos de amigos…"), foreground=tema.INFO)
            return
        self._filas_falta = filas
        if not rst.hay_datos(self.perfil):
            self.lbl_falta.configure(foreground=tema.WARN, text=tr(
                "No sé qué tienes: sincroniza 'Mi cuenta', importa afk-inventory.json o márcalo en "
                "⚙ Configurar → Mi roster. Mientras tanto, la columna ¿Puedes? queda en '?'."))
        else:
            self.lbl_falta.configure(foreground=tema.MUTED, text=tr(
                "{0} equipos más rápidos que los tuyos · ✅ puedes armarlo · 🟡 tienes los héroes, falta mejorar "
                "algo · ❌ te falta algún héroe", len(filas)))
        for i, f in enumerate(filas):
            c = f["comp"]
            equipo = ", ".join(h.get("name", "?").split(" - ")[0] for h in c.heroes)
            if c.mascota:
                equipo += f" + {c.mascota.get('name', '?')}"
            falta = "; ".join(x["texto"] for x in f["faltas"]) or (tr("Lo tienes todo") if f["nivel"] else "—")
            tabla.insert("", "end", iid=str(i), tags=(f["nivel"],) if f["nivel"] else (), values=(
                f"{f['pos']}. {self._nombre_jefe(f['boss'])}",
                formato_tiempo(f["mi"].tiempo) if f["mi"] else "—", formato_tiempo(c.tiempo),
                f"−{f['gana']:.3f} s" if f["gana"] is not None else tr("nuevo"),
                getattr(c, "dueno", None) or "?", rst.ICONO_NIVEL.get(f["nivel"], "?"), equipo, falta))
        self._dibujar_mejoras(filas)

    def _dibujar_mejoras(self, filas):
        """Arriba de la tabla: lo que ya puedes armar y las mejoras sueltas que más tiempo te dan."""
        caja = self.marco_mejoras
        ttk.Label(caja, text=tr("LO QUE MÁS TE ACERCA"), style="PanelMuted.TLabel").pack(anchor="w", pady=(0, 6))
        if not filas:
            ttk.Label(caja, text=tr("✓ En los jefes de esta semana nadie tiene un equipo más rápido que el tuyo."),
                      style="TarjetaTexto.TLabel", foreground=tema.OK).pack(anchor="w")
            return
        ya = {}
        for f in filas:
            if f["nivel"] == rst.PUEDO and f["boss"] not in ya:
                ya[f["boss"]] = f
        for f in ya.values():
            ttk.Label(caja, style="Tarjeta.TLabel", foreground=tema.OK, text=tr(
                "✅ {0}: ya puedes armar el equipo de {1} y ganar {2}", self._nombre_jefe(f["boss"]),
                getattr(f["comp"], "dueno", None) or "?",
                f"{f['gana']:.3f} s" if f["gana"] is not None else "—")).pack(anchor="w")
        sueltas = {}
        for f in filas:
            if len(f["faltas"]) == 1 and f["gana"]:
                x = f["faltas"][0]
                if x["clave"] not in sueltas or f["gana"] > sueltas[x["clave"]][0]:
                    sueltas[x["clave"]] = (f["gana"], x["texto"], f["boss"])
        for gana, texto, boss in sorted(sueltas.values(), key=lambda s: -s[0])[:6]:
            ttk.Label(caja, style="Tarjeta.TLabel", text=tr("• {0}  →  −{1:.3f} s en {2}", texto, gana,
                                                           self._nombre_jefe(boss))).pack(anchor="w")
        repetidas = Counter(x["texto"] for f in filas for x in f["faltas"])
        if repetidas:
            texto = ", ".join(f"{t} ({n})" for t, n in repetidas.most_common(4))
            ttk.Label(caja, style="TarjetaTexto.TLabel", wraplength=1100, justify="left",
                      text=tr("Lo que más se repite en los equipos más rápidos: {0}", texto)).pack(anchor="w", pady=(6, 0))
        if not ya and not sueltas and not repetidas:
            ttk.Label(caja, style="TarjetaTexto.TLabel", text=tr(
                "Sin datos de tu roster para decir qué te falta.")).pack(anchor="w")

    def _al_elegir_falta(self):
        sel = self.tabla_falta.selection()
        if not sel or int(sel[0]) >= len(self._filas_falta):
            return
        f = self._filas_falta[int(sel[0])]
        pagina = self._paginas_jefe.get(f["boss"])
        if not pagina:
            return
        pagina["fuente_clave"] = ("otros", None)
        pagina["forzar_otro"] = f["comp"]
        pagina["version"] = -1
        self.nb_jefes.select(pagina["marco"])
        self._refrescar_jefe_actual()

    def _crear_panel_detalle(self, cuerpo):
        """Panel de la derecha. No se muestra hasta que haces clic en un héroe o mascota."""
        panel = ttk.LabelFrame(cuerpo, text=tr(" Detalle "))
        self.panel_detalle = panel

        cabecera = ttk.Frame(panel)
        cabecera.pack(fill="x", padx=8, pady=8)
        ttk.Button(cabecera, text="✕", width=3, command=self._ocultar_detalle).pack(side="right", anchor="n")
        self.lbl_img_detalle = ttk.Label(cabecera, image=self.imagenes.obtener(None, TAM_DETALLE))
        self.lbl_img_detalle.pack(side="left")
        self.lbl_nombre_detalle = ttk.Label(cabecera, text=tr("Haz clic en un héroe o mascota"),
                                            font=("Segoe UI", 13, "bold"), wraplength=320)
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
        self.btn_limitar = ttk.Button(botones, text=tr("Limitar build…"), command=self.limitar_seleccion,
                                      state="disabled")
        self.btn_limitar.pack(side="left", padx=6)
        self.btn_stats = ttk.Button(botones, text=tr("📊 Estadísticas"), state="disabled",
                                    command=lambda: self.seleccion and self.ver_estadisticas(self.seleccion[0]))
        self.btn_stats.pack(side="left")

        marco = ttk.Frame(panel)
        marco.pack(fill="both", expand=True, padx=8, pady=8)
        self.txt_detalle = tk.Text(marco, wrap="word", font=("Consolas", 10), state="disabled", width=52)
        barra = ttk.Scrollbar(marco, command=self.txt_detalle.yview)
        self.txt_detalle.configure(yscrollcommand=barra.set)
        self.txt_detalle.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")
        self.txt_detalle.tag_configure("titulo", font=("Segoe UI", 10, "bold"), spacing1=8)
        self.txt_detalle.tag_configure("gris", foreground=tema.MUTED)
        self.txt_detalle.tag_configure("negrita", font=("Segoe UI", 9, "bold"))
        self.txt_detalle.tag_configure("grande", font=("Segoe UI", 11, "bold"))
        self.txt_detalle.tag_configure("tier", foreground=tema.DORADO, font=("Segoe UI", 9, "bold"))
        self.txt_detalle.tag_configure("sp_si", foreground=tema.DORADO, font=("Segoe UI", 9, "bold"))
        self.txt_detalle.tag_configure("sp_no", foreground=tema.ERR)
        # Sangría colgante: las líneas largas continúan alineadas con el valor, no bajo la etiqueta
        ancho_etiqueta = tkfont.Font(font=("Consolas", 10)).measure(" " * 16)
        self.txt_detalle.tag_configure("fila", lmargin2=ancho_etiqueta)
        self.txt_detalle.tag_configure("parrafo", lmargin2=tkfont.Font(font=("Consolas", 10)).measure("    "),
                                       spacing3=4)

    def _mostrar_panel_detalle(self):
        if not self._detalle_visible:
            self.cuerpo.add(self.panel_detalle, weight=2)
            self._detalle_visible = True

    def _ocultar_detalle(self):
        if self._detalle_visible:
            self.cuerpo.forget(self.panel_detalle)
            self._detalle_visible = False

    # ---------------- pestañas por jefe ----------------

    COL_JEFE = (
        ("heroe", N_("Héroe"), 200, "w"),
        ("yo", N_("Tú: mejor · equipos"), 170, "center"),
        ("otro", N_("Comparado: mejor · equipos"), 190, "center"),
        ("dif", N_("¿Quién es más rápido?"), 230, "w"),
    )

    # ---- fuentes: tus runs, otro servidor, un amigo, todos los amigos o los elegidos

    def _clave_propia(self):
        return ("carpeta", str(self.carpeta))

    def _todas_las_carpetas(self):
        """Todas las carpetas con runs: tus servidores (de cualquier cuenta del sitio) y tus amigos."""
        return [Path(c) for _, c in listar_servidores(self.base_dir)]

    def _relativa(self, carpeta):
        try:
            return Path(carpeta).resolve().relative_to(self.base_dir.resolve()).as_posix()
        except ValueError:
            return Path(carpeta).as_posix()

    def _seleccion(self):
        """Carpetas de 'Tu selección' (por defecto: este servidor + todos los amigos)."""
        todas = self._todas_las_carpetas()
        guardada = cargar_preferencia(self.base_dir, "seleccion_fuentes", None)
        if guardada is None:
            return [c for c in todas if (self.carpeta and c == Path(self.carpeta)) or c.parent.name == "_amigos"]
        return [c for c in todas if self._relativa(c) in set(guardada)]

    def _seleccion_incluye_actual(self):
        return any(self.carpeta and c == Path(self.carpeta) for c in self._seleccion())

    def _preparar_fuentes(self):
        """Opciones de 'Comparar con' y de 'Optimizar con'."""
        actual = Path(self.carpeta) if self.carpeta else None
        otros = [(e, Path(c)) for e, c in listar_servidores(self.base_dir) if Path(c) != actual]
        self._carpetas_amigos = [c for _, c in otros if c.parent.name == "_amigos"]
        # amigos: solo su nombre ('Pedro'); tus otros servidores: 'MiPersonaje · Servidor 1192'
        self._nombre_carpeta = {str(c): (e.replace("Amigo: ", "").split(" · ")[0] if c.parent.name == "_amigos"
                                         else e.split(" (")[0]) for e, c in otros}
        opciones = [(tr("Tus runs (este servidor)"), self._clave_propia())]
        opciones += [(e, ("carpeta", str(c))) for e, c in otros]
        n_amigos = len(self._carpetas_amigos)
        if n_amigos > 1 and len(otros) > n_amigos:
            opciones.append((tr("Todos los amigos ({0})", n_amigos), ("amigos", None)))
        if otros:
            opciones.append((tr("Todos los demás: amigos y otros servidores ({0})", len(otros)) if len(otros) > n_amigos
                             else tr("Todos los amigos ({0})", n_amigos), ("otros", None)))
        # Mezclas: tus equipos + los de amigos (el óptimo puede tomar cada jefe de cualquiera)
        if n_amigos:
            opciones.append((tr("Tus runs + todos los amigos ({0})", n_amigos), ("yo+amigos", None)))
        # Lo que elijas en '⚙ Elegir fuentes y bloqueos' (servidores de cualquier cuenta y amigos)
        opciones.append((tr("Tu selección ({0} carpetas)", len(self._seleccion())), ("personal", None)))
        self._opciones_fuente = opciones
        anterior = self._clave_opt if getattr(self, "_clave_opt", None) else self._clave_propia()
        self.combo_opt_fuente.configure(values=[e for e, _ in opciones])
        self.combo_opt_fuente.current(self._indice_fuente(anterior))
        self.combo_runs_fuente.configure(values=[e for e, _ in opciones])
        if self.combo_runs_fuente.current() < 0:
            self.combo_runs_fuente.current(0)

    def _indice_fuente(self, clave):
        return next((i for i, (_, k) in enumerate(self._opciones_fuente) if k == clave), 0)

    def _etiqueta_fuente(self, clave):
        if clave == self._clave_propia():
            return tr("Tú")
        if clave[0] == "carpeta":
            return self._nombre_carpeta.get(clave[1], Path(clave[1]).name)
        return {"amigos": tr("Todos los amigos"), "yo+amigos": tr("Tú + todos los amigos"),
                "personal": tr("Tu selección"), "otros": tr("Todos los demás")}[clave[0]]

    def _es_mezcla(self, clave):
        """La fuente junta tus equipos de este servidor con los de otras carpetas."""
        return clave[0] == "yo+amigos" or (clave[0] == "personal" and self._seleccion_incluye_actual())

    def _carpetas_de(self, clave):
        """Carpetas (distintas del servidor abierto) que hay que cargar para una fuente."""
        if clave[0] == "carpeta":
            return [Path(clave[1])]
        if clave[0] == "personal":
            return [c for c in self._seleccion() if not (self.carpeta and c == Path(self.carpeta))]
        if clave[0] == "otros":
            return [c for c in self._todas_las_carpetas() if not (self.carpeta and c == Path(self.carpeta))]
        return list(self._carpetas_amigos)

    def _pool(self, clave, con_roster=True):
        """
        (comps, baneos) de una fuente, o None si falta cargar alguna carpeta.
        con_roster: a los equipos de otros se les aplica 'solo lo que puedes armar' (si está activo).
        """
        if clave == self._clave_propia():
            return self.comps, self._baneos_yo()
        comps = []
        for c in self._carpetas_de(clave):
            cargados = self._fuentes.get(str(c))
            if cargados is None:
                return None
            comps.extend(cargados)
        filtro = self._filtro_roster if con_roster else list
        if self._es_mezcla(clave):
            # cada equipo con las reglas de su lado: 'tus equipos' / 'amigos' (+ las de 'todos')
            rotacion = self._rotacion_semanal()
            mios = quitar_baneadas(self.comps, rotacion, self._baneos_yo())
            return mios + filtro(quitar_baneadas(comps, rotacion, self.baneos_amigos)), []
        return filtro(comps), list(self.baneos_amigos) + list(self.limites)

    def _asegurar(self, clave, al_terminar):
        """Carga lo que falte de una fuente y luego llama a al_terminar()."""
        faltan = [c for c in self._carpetas_de(clave)
                  if clave != self._clave_propia() and str(c) not in self._fuentes]
        if not faltan:
            al_terminar()
            return
        pendientes = {str(c) for c in faltan}

        def una_lista(c):
            pendientes.discard(str(c))
            if not pendientes:
                al_terminar()
        for c in faltan:
            self._cargar_fuente(c, lambda c=c: una_lista(c))

    def _cargar_fuente(self, carpeta, al_terminar):
        clave = str(carpeta)
        if clave in self._fuentes:
            al_terminar()
            return
        self._esperando.setdefault(clave, []).append(al_terminar)
        if len(self._esperando[clave]) > 1:
            return   # ya se está cargando
        self._estado(tr("Cargando runs para comparar..."), tema.INFO)
        nombre = self._nombre_carpeta.get(clave, Path(carpeta).name)

        def tarea():
            try:
                datos = cargar_indice(carpeta)
                actual = cargar_cuenta_actual(carpeta) or {}
                comps = construir_composiciones(datos["runs"], actual.get("heroes_temporales") or (), arrendados_de(actual))
                aplicar_sp_manual(comps, carpeta)
                for c in comps:
                    c.dueno = nombre   # de quién es el equipo (se muestra al juntar varios amigos)
                    c.carpeta_origen = carpeta
                self._anotar_estrellas(comps)
            except Exception as error:
                mensaje = str(error)
                self._en_ui(lambda: (self._esperando.pop(clave, None),
                                     self._estado(tr("Error al cargar: {0}", mensaje), tema.ERR)))
                return

            def listo():
                self._fuentes[clave] = comps
                self._ids_otro |= {id(c) for c in comps}
                self._estado(tr("✓ {0} equipos de {1} cargados.", len(comps), nombre), tema.OK)
                for funcion in self._esperando.pop(clave, []):
                    funcion()
            self._en_ui(listo)

        threading.Thread(target=tarea, daemon=True).start()

    # ---- pestañas

    def _reconstruir_tabs_jefes(self, forzar=True):
        """Una pestaña por jefe de la rotación de la semana, en su orden (Explorar queda al final)."""
        rotacion = tuple(self._rotacion_semanal())
        if not forzar and rotacion == self._rotacion_tabs:
            return
        self._rotacion_tabs = rotacion
        seleccionado = None
        try:
            seleccionado = self.nb_jefes.nametowidget(self.nb_jefes.select()).boss
        except (tk.TclError, AttributeError, KeyError):
            pass
        fuentes = {b: p.get("fuente_clave") for b, p in self._paginas_jefe.items()}
        for pagina in list(self._paginas_jefe.values()):
            pagina["marco"].destroy()
        self._paginas_jefe = {}
        for posicion, boss in enumerate(rotacion, 1):
            if not boss or boss in self._paginas_jefe:
                continue
            marco = ttk.Frame(self.nb_jefes)
            marco.boss = boss
            nombre, url = self.vis.jefe(boss) if self.vis.disponible else (str(boss), None)
            self.nb_jefes.insert(self.tab_falta, marco, text=f"{posicion}. {tr(nombre)}",
                                 image=self.imagenes.obtener(url, 28), compound="left")
            self._paginas_jefe[boss] = {"marco": marco, "version": -1, "posicion": posicion, "nombre": tr(nombre),
                                        "fuente_clave": fuentes.get(boss) or self._fuente_por_defecto()}
        destino = self._paginas_jefe.get(seleccionado) or next(iter(self._paginas_jefe.values()), None)
        if destino is not None:
            self.nb_jefes.select(destino["marco"])
        self._invalidar_jefes()

    def _fuente_por_defecto(self):
        """Lado derecho: el óptimo de otros si lo calculaste; si no, el primer amigo; si no, tus runs."""
        if self._optimo_otro:
            return self._optimo_otro["clave"]
        if self._carpetas_amigos:
            return ("carpeta", str(self._carpetas_amigos[0]))
        return self._clave_propia()

    def _invalidar_jefes(self):
        """Datos, filtros, baneos u optimización cambiaron: títulos al día y recalcular la pestaña visible."""
        self._version_jefes += 1
        self._cands_cache = None
        self._actualizar_titulos_tabs()
        self._refrescar_jefe_actual()
        self._resumen_pendiente = self._falta_pendiente = self._stats_pendiente = True
        self._dibujar_resumen_si_visible()
        self._dibujar_falta_si_visible()
        self._dibujar_stats_si_visible()

    def _candidatos_yo(self):
        """{boss: [tus equipos]} de toda la rotación (una sola pasada)."""
        if self._cands_cache and self._cands_cache[0] == self._version_jefes:
            return self._cands_cache[1]
        rotacion = (self._rotacion_semanal() + [""] * 6)[:6]
        salida = {}
        if self.comps:
            cands, _ = candidatos_por_jefe(self.comps, rotacion, self._opciones(), self._baneos_yo())
            for pos, boss in enumerate(rotacion, 1):
                if boss:
                    salida[boss] = list(cands.get(pos, []))
        self._cands_cache = (self._version_jefes, salida)
        return salida

    def _candidatos(self, comps, boss, baneos):
        """Equipos contra ese jefe (por ID, de cualquier rotación), con su posición de esta semana para los baneos."""
        if not comps:
            return []
        rotacion = (self._rotacion_semanal() + [""] * 6)[:6]
        if boss not in rotacion:
            rotacion = [boss, "", "", "", "", ""]
        cands, _ = candidatos_por_jefe(comps, rotacion, self._opciones(), baneos)
        return list(cands.get(rotacion.index(boss) + 1, []))

    def _actualizar_titulos_tabs(self):
        """Título: 'posición. jefe · tu tiempo' (+ '⟷ tiempo del óptimo de otros' si lo calculaste)."""
        cands = self._candidatos_yo()
        for boss, pagina in self._paginas_jefe.items():
            optimo = self._optimo_por_jefe.get(boss)
            lista = cands.get(boss) or []
            if optimo is not None:
                tiempo = f"★ {formato_tiempo(optimo.tiempo)}"
            elif lista:
                tiempo = formato_tiempo(lista[0].tiempo)
            else:
                tiempo = "—"
            otro = (self._optimo_otro or {}).get("por_jefe", {}).get(boss)
            if otro is not None:
                tiempo += f"  ⟷  {formato_tiempo(otro.tiempo)}"
            try:
                self.nb_jefes.tab(pagina["marco"], text=f"{pagina['posicion']}. {pagina['nombre']} · {tiempo}")
            except tk.TclError:
                pass

    def _refrescar_jefe_actual(self):
        try:
            marco = self.nb_jefes.nametowidget(self.nb_jefes.select())
        except (tk.TclError, KeyError):
            return
        pagina = self._paginas_jefe.get(getattr(marco, "boss", None))
        if pagina and pagina["version"] != self._version_jefes:
            pagina["version"] = self._version_jefes
            self._llenar_pagina_jefe(marco.boss, pagina)

    def _construir_pagina_jefe(self, pagina):
        marco = pagina["marco"]
        pagina["lbl"] = ttk.Label(marco, text="", font=("Segoe UI", 10, "bold"))
        pagina["lbl"].pack(anchor="w", padx=6, pady=(6, 0))
        # Barra 'tú vs. el otro' con los equipos que se están mostrando
        pagina["versus"] = tk.Label(marco, text="", font=("Segoe UI", 12, "bold"), anchor="w",
                                    bg=tema.PANEL, fg=tema.TEXTO, padx=10, pady=6)
        pagina["versus"].pack(fill="x", padx=6, pady=(4, 2))

        fila = ttk.Frame(marco)
        fila.pack(fill="x")
        tam = self._tam_tarjeta_jefe()
        for lado, columna in (("yo", 0), ("otro", 1)):
            fila.columnconfigure(columna, weight=1, uniform="lados")
            caja = ttk.LabelFrame(fila, text=tr(" Tus equipos ") if lado == "yo" else tr(" Comparar con "))
            caja.grid(row=0, column=columna, sticky="nsew", padx=4, pady=4)
            if lado == "otro":
                fuente = ttk.Combobox(caja, state="readonly", values=[e for e, _ in self._opciones_fuente])
                fuente.pack(fill="x", padx=6, pady=(4, 0))
                fuente.bind("<<ComboboxSelected>>", lambda e, p=pagina: self._cambiar_fuente(p))
                pagina["combo_fuente"] = fuente
            selector = ttk.Frame(caja)
            selector.pack(fill="x", padx=6, pady=4)
            ttk.Button(selector, text="▶", width=3,
                       command=lambda p=pagina, l=lado: self._mover_equipo(p, l, +1)).pack(side="right")
            ttk.Button(selector, text="◀", width=3,
                       command=lambda p=pagina, l=lado: self._mover_equipo(p, l, -1)).pack(side="right", padx=2)
            combo = ttk.Combobox(selector, state="readonly")
            combo.pack(side="left", fill="x", expand=True)
            combo.bind("<<ComboboxSelected>>", lambda e, p=pagina, l=lado: self._mostrar_equipo(
                p, l, p[f"combo_{l}"].current()))
            pagina[f"combo_{lado}"] = combo
            pagina[f"tarjeta_{lado}"] = TarjetaEquipo(caja, self.imagenes, self.mostrar_detalle, vis=self.vis, tam=tam)
            pagina[f"tarjeta_{lado}"].pack(fill="x", padx=4, pady=(0, 4))

        # Diferencias entre los dos equipos mostrados
        caja_dif = ttk.LabelFrame(marco, text=tr(" Diferencias entre estos dos equipos "))
        caja_dif.pack(fill="x", padx=6, pady=(2, 4))
        texto = tk.Text(caja_dif, height=6, wrap="word", font=("Segoe UI", 10), relief="flat",
                        bg=tema.PANEL, fg=tema.TEXTO, padx=8, pady=4, state="disabled")
        texto.pack(fill="x")
        texto.tag_configure("negrita", font=("Segoe UI", 10, "bold"))
        texto.tag_configure("yo", foreground=tema.OK, font=("Segoe UI", 10, "bold"))
        texto.tag_configure("otro", foreground=tema.WARN, font=("Segoe UI", 10, "bold"))
        texto.tag_configure("gris", foreground=tema.MUTED)
        pagina["dif"] = texto

        pagina["lbl_tabla"] = ttk.Label(marco, foreground=tema.MUTED, text="")
        pagina["lbl_tabla"].pack(anchor="w", padx=6)
        marco_tabla = ttk.Frame(marco)
        marco_tabla.pack(fill="both", expand=True, padx=4, pady=4)
        tabla = ttk.Treeview(marco_tabla, columns=[c for c, *_ in self.COL_JEFE], show="headings")
        for col, titulo, ancho, anchor in self.COL_JEFE:
            tabla.heading(col, text=tr(titulo))
            tabla.column(col, width=ancho, anchor=anchor, stretch=col in ("heroe", "dif"))
        tabla.tag_configure("gano_yo", foreground=tema.OK)
        tabla.tag_configure("gana_otro", foreground=tema.WARN)
        tabla.tag_configure("solo", foreground=tema.MUTED)
        barra = ttk.Scrollbar(marco_tabla, orient="vertical", command=tabla.yview)
        tabla.configure(yscrollcommand=barra.set)
        tabla.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")
        tabla.bind("<<TreeviewSelect>>", lambda e, p=pagina: self._al_elegir_heroe_jefe(p))
        pagina["tabla"] = tabla

    def _cambiar_fuente(self, pagina):
        pagina["fuente_clave"] = self._opciones_fuente[pagina["combo_fuente"].current()][1]
        pagina["version"] = -1
        self._refrescar_jefe_actual()

    def _terminos_filtro(self):
        """'Talimar, Dracula' -> ['talimar', 'dracula'] (sin tildes ni mayúsculas)."""
        return [_normalizar_texto(t.strip()) for t in self.var_filtro.get().split(",") if t.strip()]

    @staticmethod
    def _coincide(c, termino):
        """El equipo usa un héroe, colección o mascota que contiene ese texto."""
        return (any(termino in _normalizar_texto(h.get("name", "")) or
                    termino in _normalizar_texto((h.get("collection") or {}).get("name", "")) for h in c.heroes)
                or termino in _normalizar_texto(c.mascota.get("name", "")))

    def _filtrar(self, lista):
        """Solo los equipos que usan TODOS los héroes / colecciones del filtro."""
        terminos = self._terminos_filtro()
        if not terminos:
            return lista
        return [c for c in lista if all(self._coincide(c, t) for t in terminos)]

    def _llenar_pagina_jefe(self, boss, pagina):
        if "tabla" not in pagina:
            self._construir_pagina_jefe(pagina)
        clave = pagina.get("fuente_clave") or self._clave_propia()
        if self._indice_fuente(clave) == 0 and clave != self._clave_propia():
            clave = self._clave_propia()   # esa fuente ya no existe
        pagina["fuente_clave"] = clave
        pagina["combo_fuente"].configure(values=[e for e, _ in self._opciones_fuente])
        pagina["combo_fuente"].current(self._indice_fuente(clave))
        nombre_otro = self._etiqueta_fuente(clave)

        mios = self._filtrar(self._candidatos_yo().get(boss) or [])
        pool = self._pool(clave)
        if pool is None:   # falta cargar: se vuelve a llenar al terminar
            self._asegurar(clave, lambda: (pagina.update(version=-1), self._refrescar_jefe_actual()))
            otros = []
        else:
            otros = self._filtrar(self._candidatos(pool[0], boss, pool[1]))
        varios = clave[0] != "carpeta"
        res_yo, res_otro = resumen_heroes(mios), resumen_heroes(otros)
        pagina.update(boss=boss, mios=mios, otros=otros, res_yo=res_yo, res_otro=res_otro,
                      nombre_otro=nombre_otro, varios=varios)

        optimo = self._optimo_por_jefe.get(boss)
        optimo_otro = None
        if self._optimo_otro and self._optimo_otro["clave"] == clave:
            optimo_otro = self._optimo_otro["por_jefe"].get(boss)
        pagina["optimo_otro"] = optimo_otro
        partes = [f"{pagina['posicion']}. {self._etiqueta_jefe(boss)}",
                  tr("{0} equipos tuyos", len(mios)),
                  tr("{0} equipos de {1}", len(otros), nombre_otro) if clave != self._clave_propia() else ""]
        pagina["lbl"].configure(text="   ·   ".join(p for p in partes if p))

        for lado, lista, estrella in (("yo", mios, optimo), ("otro", otros, optimo_otro)):
            firma = estrella.firma if estrella is not None else None
            pagina[f"combo_{lado}"].configure(values=[
                ("★ " if c.firma == firma else "") + self._texto_equipo(i, c, varios and lado == "otro")
                for i, c in enumerate(lista, 1)])
            pagina[f"indice_{lado}"] = next((i for i, c in enumerate(lista) if c.firma == firma), 0)
        forzado = pagina.pop("forzar_otro", None)
        if forzado is not None:
            pagina["indice_otro"] = next((i for i, c in enumerate(otros) if c is forzado), pagina["indice_otro"])
        self._mostrar_equipo(pagina, "yo", pagina["indice_yo"], actualizar=False)
        self._mostrar_equipo(pagina, "otro", pagina["indice_otro"])

        # Tabla: cada héroe usado contra este jefe, y quién lo usó más rápido
        tabla = pagina["tabla"]
        tabla.heading("otro", text=tr("{0}: mejor · equipos", nombre_otro))
        pagina["lbl_tabla"].configure(text=tr(
            "Héroes usados contra este jefe (verde: tú vas más rápido con él · amarillo: {0} va más rápido · "
            "gris: solo uno lo usó). Clic: cada lado salta a su equipo más rápido con ese héroe.", nombre_otro))
        tabla.delete(*tabla.get_children())

        def orden(k):
            yo, otro = res_yo.get(k), res_otro.get(k)
            return (0 if (yo and otro) else 1), min(x["mejor"].tiempo for x in (yo, otro) if x)

        for k in sorted(set(res_yo) | set(res_otro), key=orden):
            yo, otro = res_yo.get(k), res_otro.get(k)
            if yo and otro:
                d = otro["mejor"].tiempo - yo["mejor"].tiempo
                if abs(d) < 0.0005:
                    texto, tag = tr("igual"), ()
                elif d > 0:
                    texto, tag = tr("Tú, por {0:.3f} s", d), ("gano_yo",)
                else:
                    texto, tag = tr("{0}, por {1:.3f} s", nombre_otro, -d), ("gana_otro",)
            else:
                texto, tag = (tr("solo lo usas tú") if yo else tr("solo lo usa {0}", nombre_otro)), ("solo",)
            tabla.insert("", "end", iid=k, tags=tag, values=(
                (yo or otro)["nombre"],
                f"{formato_tiempo(yo['mejor'].tiempo)} · {yo['equipos']}" if yo else "—",
                f"{formato_tiempo(otro['mejor'].tiempo)} · {otro['equipos']}" if otro else "—",
                texto,
            ))

    @staticmethod
    def _dueno(c):
        """De quién es un equipo cuando se juntan varias fuentes: el amigo, o 'tú' si es tuyo."""
        return getattr(c, "dueno", None) or tr("tú")

    def _texto_equipo(self, i, c, con_dueno=False):
        heroes = ", ".join(h.get("name", "?").split(" - ")[0] for h in c.heroes)
        dueno = f" · {self._dueno(c)}" if con_dueno else ""
        return f"#{i} · {formato_tiempo(c.tiempo)} · {heroes}{dueno} · {fecha_local(c.fecha)[:10]}"

    def _mostrar_equipo(self, pagina, lado, indice, actualizar=True):
        """Muestra el equipo número `indice` de un lado ('yo' / 'otro') y actualiza la comparación."""
        lista = pagina.get("mios" if lado == "yo" else "otros") or []
        tarjeta, combo, boss = pagina[f"tarjeta_{lado}"], pagina[f"combo_{lado}"], pagina.get("boss")
        if not lista:
            combo.set("")
            texto = (tr("Sin equipos tuyos contra este jefe con estos filtros") if lado == "yo" else
                     tr("{0}: sin equipos contra este jefe con estos filtros", pagina.get("nombre_otro", "")))
            tarjeta.mostrar(None, texto, boss_id=boss)
            pagina[f"indice_{lado}"] = -1
        else:
            indice = max(0, min(int(indice), len(lista) - 1))
            pagina[f"indice_{lado}"] = indice
            combo.current(indice)
            c = lista[indice]
            estrella = self._optimo_por_jefe.get(boss) if lado == "yo" else pagina.get("optimo_otro")
            marca = "★ " if estrella is not None and c.firma == estrella.firma else ""
            extra = "" if indice == 0 else f" (+{c.tiempo - lista[0].tiempo:.3f} s)"
            dueno = f" · {self._dueno(c)}" if lado == "otro" and pagina.get("varios") else ""
            tarjeta.mostrar(c, tr("{0}#{1} de {2} · {3}{4}{5}", marca, indice + 1, len(lista),
                                  formato_tiempo(c.tiempo), extra, dueno))
        if actualizar:
            self._actualizar_diferencias(pagina)

    def _actualizar_diferencias(self, pagina):
        """Barra 'tú vs. el otro' y recuadro de diferencias de los dos equipos que se están mostrando."""
        a = pagina["mios"][pagina["indice_yo"]] if pagina.get("indice_yo", -1) >= 0 else None
        b = pagina["otros"][pagina["indice_otro"]] if pagina.get("indice_otro", -1) >= 0 else None
        nombre = pagina.get("nombre_otro") or tr("el otro")
        if b is not None and pagina.get("varios"):
            nombre = getattr(b, "dueno", None) or tr("tu otro equipo")
        versus = pagina["versus"]
        if a and b:
            d = b.tiempo - a.tiempo
            if abs(d) < 0.0005:
                veredicto, color = tr("mismo tiempo"), tema.TEXTO
            elif d > 0:
                veredicto, color = tr("eres {0:.3f} s más rápido", d), tema.OK
            else:
                veredicto, color = tr("{0} es {1:.3f} s más rápido", nombre, -d), tema.WARN
            versus.configure(text=tr("Tú {0}   ⟷   {1} {2}      →  {3}", formato_tiempo(a.tiempo), nombre,
                                     formato_tiempo(b.tiempo), veredicto), fg=color)
        else:
            versus.configure(text=tr("Elige con quién comparar a la derecha.") if a else tr(
                "Sin equipos tuyos contra este jefe con estos filtros."), fg=tema.MUTED)

        t = pagina["dif"]
        t.configure(state="normal")
        t.delete("1.0", "end")
        if not (a and b):
            t.insert("end", tr("Cuando haya un equipo a cada lado, aquí verás qué héroes comparten, cuáles cambian "
                               "y en qué se diferencia la build de los que comparten."), "gris")
            t.configure(state="disabled")
            return
        if id(b) in self._ids_otro:
            nivel, faltas = self.evaluar(b)
            if nivel == rst.PUEDO:
                t.insert("end", tr("✅ Puedes copiar este equipo tal cual con tu roster.") + "\n", "yo")
            elif nivel:
                t.insert("end", f"{rst.ICONO_NIVEL[nivel]} " + tr("Para copiarlo te falta: "), "otro")
                t.insert("end", "; ".join(f["texto"] for f in faltas) + "\n")
        d = diferencias_equipos(a, b)
        nombres = lambda hs: ", ".join(h.get("name", "?").split(" - ")[0] for h in hs)
        if a.firma == b.firma:
            t.insert("end", tr("Es el mismo equipo (mismos héroes y mascota)."), "negrita")
        else:
            t.insert("end", tr("En ambos: "), "negrita")
            t.insert("end", (nombres(x for x, _ in d["ambos"]) or "—") + "\n")
            t.insert("end", tr("Solo en el tuyo: "), "yo")
            t.insert("end", (nombres(d["solo_a"]) or "—") + "     ")
            t.insert("end", tr("Solo en el de {0}: ", nombre), "otro")
            t.insert("end", (nombres(d["solo_b"]) or "—"))
            if d["mascota"]:
                t.insert("end", "\n" + tr("Mascota: "), "negrita")
                t.insert("end", f"{d['mascota'][0]}  ⟷  {d['mascota'][1]}")
        cambios = [(ha, diferencias_build(ha, hb)) for ha, hb in d["ambos"]]
        cambios = [(h, c) for h, c in cambios if c]
        if cambios:
            t.insert("end", "\n" + tr("Misma unidad, distinta build (tú ⟷ {0}):", nombre), "negrita")
            for h, partes in cambios:
                t.insert("end", f"\n  • {h.get('name', '?').split(' - ')[0]}: ", "negrita")
                t.insert("end", "  ·  ".join(partes))
        elif d["ambos"]:
            t.insert("end", "\n" + tr("Los héroes que comparten tienen la misma build."), "gris")
        t.configure(state="disabled")

    def _mover_equipo(self, pagina, lado, paso):
        if "combo_yo" not in pagina:
            return
        self._mostrar_equipo(pagina, lado, pagina.get(f"indice_{lado}", 0) + paso)

    def _al_elegir_heroe_jefe(self, pagina):
        sel = pagina["tabla"].selection()
        if not sel:
            return
        clave = sel[0]
        yo, otro = pagina["res_yo"].get(clave), pagina["res_otro"].get(clave)
        # cada lado salta a su equipo más rápido con ese héroe (si lo usó)
        for lado, dato, lista in (("yo", yo, pagina["mios"]), ("otro", otro, pagina["otros"])):
            if dato:
                indice = next((i for i, c in enumerate(lista) if c is dato["mejor"]), 0)
                self._mostrar_equipo(pagina, lado, indice, actualizar=False)
        self._actualizar_diferencias(pagina)
        if yo:
            self.mostrar_detalle(yo["mejor"], yo["heroe"], "HEROE")
        elif otro:
            self.mostrar_detalle(otro["mejor"], otro["heroe"], "HEROE")

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
                comps = construir_composiciones(datos["runs"], actual.get("heroes_temporales") or (), arrendados_de(actual))
                aplicar_sp_manual(comps, carpeta)
                for c in comps:
                    c.carpeta_origen = carpeta
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
        self._cargar_reglas()
        self.recargar_perfil()
        self._anotar_estrellas(comps)
        self.resultado, self._optimo_por_jefe, self._optimo_otro, self._total_yo = None, {}, None, None
        self._ultimo_optimo = None
        self.lbl_total.configure(text="")
        self.lbl_total_sub.configure(text="")
        self.lbl_resumen.configure(text=tr("Pulsa ▶ Optimizar para elegir el mejor equipo de cada jefe "
                                           "sin repetir héroes."))
        self._actualizar_boton_baneos()

        bosses = sorted({c.boss_id for c in comps}, key=orden_boss)
        self._bosses = bosses
        self.combo_jefe.configure(values=[self._etiqueta_jefe(b) for b in bosses])
        self._preparar_fuentes()
        self.usar_rotacion_reciente()
        self._reconstruir_tabs_jefes()
        if bosses:
            self.combo_jefe.set(self._etiqueta_jefe(bosses[0]))
        completas = sum(1 for r in self.runs
                        if (r.get("result") or {}).get("bossesKilled") == 6)
        self._estado(tr('✓ {0} runs cargadas ({1} completas), {2} composiciones, {3} jefes distintos.', len(self.runs), completas, len(comps), len(bosses)), tema.OK)
        self.actualizar_explorar()
        if self._enfoque_pendiente:
            enfoque, self._enfoque_pendiente = self._enfoque_pendiente, None
            self.enfocar(enfoque.get("texto", ""), enfoque.get("boss"))
        if self._pendiente_opt is not None:
            carpeta, self._pendiente_opt = self._pendiente_opt, None
            self.optimizar_con_carpeta(carpeta)
        else:
            self.nb_jefes.select(self.tab_resumen)

    def enfocar(self, texto, boss=None):
        """Filtra por un héroe/colección y abre la pestaña de ese jefe (o Explorar si no está en la rotación)."""
        self.var_filtro.set(texto)
        if boss and str(boss) in self._paginas_jefe:
            self.nb_jefes.select(self._paginas_jefe[str(boss)]["marco"])
            return
        if boss:
            self.combo_jefe.set(self._etiqueta_jefe(boss))
            self.actualizar_explorar()
        self.var_modo_explorar.set("jefe")
        self._cambiar_modo_explorar()
        self.nb_jefes.select(self.tab_explorar)

    def _al_cambiar_filtros(self):
        guardar_preferencia(self.base_dir, "excluir_temporales", self.var_excluir_temp.get())
        guardar_preferencia(self.base_dir, "excluir_fuera_roster", self.var_excluir_fuera.get())
        self._actualizar_chips()
        self.actualizar_explorar()
        if self.resultado is not None or self._ultimo_optimo is not None:
            self._estado(tr("Opciones cambiadas. Pulsa ▶ Optimizar para recalcular."), tema.WARN)

    def _etiqueta_jefe(self, boss_id):
        return f"{boss_id} · {self.vis.jefe(boss_id)[0]}" if self.vis.disponible else str(boss_id)

    @staticmethod
    def _id_de_etiqueta(etiqueta):
        return str(etiqueta).split(" · ", 1)[0].strip()

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
        """Optimiza con la fuente elegida: tus runs, un amigo / otro servidor, todos los amigos o los elegidos."""
        if self._ocupado or not self.comps:
            return
        etiqueta, clave = self._opciones_fuente[max(0, self.combo_opt_fuente.current())]
        self._clave_opt = clave
        rotacion = self._rotacion_semanal()
        opciones = self._opciones()
        self._ocupado = True
        self.btn_optimizar.configure(state="disabled")

        def lanzar():
            comps, baneos = self._pool(clave)
            baneos = list(baneos)
            self._estado(tr('Optimizando rotación {0} con {1}...', '-'.join(rotacion), etiqueta), tema.INFO)

            def tarea():
                try:
                    res = optimizar(comps, rotacion, opciones, baneos)
                except Exception as error:
                    mensaje = str(error)
                    self._en_ui(lambda: self._fin_optimizacion(None, mensaje, rotacion, clave))
                    return
                self._en_ui(lambda: self._fin_optimizacion(res, None, rotacion, clave))

            threading.Thread(target=tarea, daemon=True).start()

        self._asegurar(clave, lanzar)

    def _fin_optimizacion(self, res, error, rotacion, clave):
        self._ocupado = False
        self.btn_optimizar.configure(state="normal")
        if error:
            self._estado(tr('Error: {0}', error), tema.ERR)
            return
        ok = bool(res.elegidas)
        nombre = self._etiqueta_fuente(clave)
        color = tema.OK if res.estado == "Óptimo global" else (tema.WARN if ok else tema.ERR)
        self._estado(f"{nombre}: {tr(res.estado)} — {res.detalle}", color)
        por_jefe = {boss: comp for boss, comp in zip(rotacion, res.elegidas)} if ok else {}
        if clave == self._clave_propia():
            self.resultado, self._optimo_por_jefe, self._total_yo = res, por_jefe, (res.total if ok else None)
        else:
            self._optimo_otro = {"clave": clave, "nombre": nombre, "por_jefe": por_jefe,
                                 "total": res.total if ok else None} if ok else None
            # el lado derecho de cada jefe pasa a mostrar ese óptimo
            for pagina in self._paginas_jefe.values():
                pagina["fuente_clave"] = clave
        self._rotacion_optimizada = tuple(rotacion)
        self._ultimo_optimo = ({"clave": clave, "nombre": nombre, "por_jefe": por_jefe, "total": res.total}
                               if ok else None)
        if not ok:
            vacios = [self._nombre_jefe(b) for pos, b in enumerate(rotacion, 1)
                      if b and not (res.candidatos or {}).get(pos)]
            if vacios:
                pista = "  " + tr("Sin equipos para: {0}. Revisa los bloqueos de ⚙ Configurar.", ", ".join(vacios))
            else:
                pista = "  " + (tr("Prueba desmarcando 'Solo runs completas' o revisa los bloqueos.")
                                if self.var_completas.get() else tr("Revisa los bloqueos o la rotación."))
            self._estado(pista.strip(), tema.ERR)
            self.lbl_resumen.configure(text=f"{nombre}: {res.detalle}{pista}")
            self.lbl_total.configure(text=tr("Sin solución"))
            self.lbl_total_sub.configure(text=nombre)
        else:
            self._actualizar_resumen_optimo()
        self._invalidar_jefes()
        if ok:
            self.nb_jefes.select(self.tab_resumen)

    def _actualizar_resumen_optimo(self):
        """'Tu óptimo: 2m 19 s · Óptimo de Pedro: 2m 10 s (9 s más rápido)'."""
        partes = []
        if self._total_yo is not None:
            partes.append(tr("★ Tu óptimo: {0}", formato_tiempo(self._total_yo)))
        if self._optimo_otro and self._optimo_otro.get("total") is not None:
            texto = tr("Óptimo de {0}: {1}", self._optimo_otro["nombre"], formato_tiempo(self._optimo_otro["total"]))
            if self._total_yo is not None:
                d = self._optimo_otro["total"] - self._total_yo
                texto += " " + (tr("({0:.3f} s más lento que el tuyo)", d) if d > 0 else
                                tr("({0:.3f} s más rápido que el tuyo)", -d) if d < 0 else tr("(igual)"))
            if self._es_mezcla(self._optimo_otro["clave"]):
                equipos = list(self._optimo_otro["por_jefe"].values())
                tuyos = sum(1 for c in equipos if not getattr(c, "dueno", None))
                de_quien = Counter(c.dueno for c in equipos if getattr(c, "dueno", None))
                texto += " — " + tr("{0} jefes con tus equipos", tuyos)
                if de_quien:
                    texto += ", " + ", ".join(f"{n} {tr('de')} {quien}" for quien, n in de_quien.most_common())
            partes.append(texto)
        partes.append(tr("★ en cada pestaña = equipo elegido · ⟷ = el del otro"))
        self.lbl_resumen.configure(text="   ·   ".join(partes))
        # Total en grande a la derecha: el de la última optimización
        ultimo = self._ultimo_optimo
        if ultimo and ultimo.get("total") is not None:
            self.lbl_total.configure(text=formato_tiempo(ultimo["total"]))
            sub = tr("tiempo total · {0}", ultimo["nombre"])
            if self._total_yo is not None and ultimo["clave"] != self._clave_propia():
                sub += "  ·  " + tr("solo tú: {0}", formato_tiempo(self._total_yo))
            self.lbl_total_sub.configure(text=sub)

    # ---------------- explorar (cualquier jefe) ----------------

    def actualizar_explorar(self, seleccionar=None):
        if hasattr(self, "nb_jefes"):
            self._invalidar_jefes()   # filtros o baneos cambiaron: las pestañas de jefe también
        self.actualizar_runs()
        boss = self._id_de_etiqueta(self.combo_jefe.get())
        self.explorar_lista = []
        if boss and self.comps:
            self.explorar_lista = self._filtrar(self._candidatos(self.comps, boss, self._baneos_yo()))
        texto = tr('{0} equipos distintos', len(self.explorar_lista))
        if boss and self.comps and not self.explorar_lista:
            texto = tr("{0}: sin equipos con estos filtros", self._etiqueta_jefe(boss))
        self.lbl_explorar.configure(text=texto)
        # La lista con íconos se dibuja solo si Explorar está a la vista (es lo más pesado de la ventana)
        self._explorar_pendiente = True
        self._dibujar_explorar_si_visible()

    def _dibujar_explorar_si_visible(self):
        try:
            visible = (self.nb_jefes.select() == str(self.tab_explorar)
                       and self.var_modo_explorar.get() == "jefe")
        except tk.TclError:
            return
        if visible and getattr(self, "_explorar_pendiente", False):
            self._explorar_pendiente = False
            self._llenar_lista_explorar()

    # ---------------- panel de detalle ----------------

    def _nombres_calidad_gear(self):
        go = self.refs.get("gearOptions") or {}
        return {q.get("quality"): q.get("name") for q in go.get("qualities") or []}

    def _nombres_faccion_gear(self):
        go = self.refs.get("gearOptions") or {}
        return {f.get("tag"): f.get("name") for f in go.get("factions") or []}

    def mostrar_detalle(self, comp, obj, tipo):
        self.seleccion = (comp, obj, tipo)
        self._mostrar_panel_detalle()
        if tipo == "HEROE" and self.vis.disponible:
            cabecera = self.imagenes.retrato(obj, self.vis, comp.golden, TAM_RETRATO_DETALLE, con_equipo=True)
        else:
            cabecera = self.imagenes.obtener(obj.get("imageUrl"), TAM_DETALLE)
        self.lbl_img_detalle.configure(image=cabecera)
        self.lbl_nombre_detalle.configure(text=obj.get("name", "?"))
        self.btn_ban_todos.configure(state="normal")
        self.btn_ban_jefe.configure(state="normal")
        self.btn_limitar.configure(state="normal" if tipo == "HEROE" else "disabled")
        self.btn_stats.configure(state="normal")
        no_propio = tipo == "HEROE" and (obj.get("origen") or PROPIO) != PROPIO
        self.btn_ban_copia.configure(state="normal" if no_propio else "disabled")
        de_amigo = id(comp) in self._ids_otro   # equipo de un amigo / otro servidor: va a 'Baneos de amigos'
        self.btn_ban_todos.configure(text=tr("Banear en amigos: todos los jefes") if de_amigo
                                     else tr("Banear en todos los jefes"))
        self.btn_ban_jefe.configure(text=tr("Banear en amigos: solo este jefe") if de_amigo
                                    else tr("Banear solo en este jefe"))

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
        t.insert("end", f"  {tr('Estrellas'):<14}", ("gris", "fila"))
        n = vis.numero_estrellas(h.get("quality"))
        for _ in range(n):
            imagen(vis.estrella(h.get("engraving")), 22)
        t.insert("end", f" {vis.nombre_calidad(h.get('quality'))}\n" if n else
                 f"{vis.nombre_calidad(h.get('quality'))}\n", "fila")
        t.insert("end", f"  {tr('SI (firma)'):<14}", ("gris", "fila"))
        imagen(vis.icono_si(h.get("tid"), h.get("sig")), 40)
        t.insert("end", f" +{h.get('sig', '—')}\n", "fila")

        sp = vis.usa_sp(h, comp.golden)
        if sp == "?" or (h.get("hyper") and comp.sp_manual):
            self._detalle_elegir_sp(t, comp, h, sp)
            sp = None
        if sp is not None:
            t.insert("end", f"  {'Special Power':<14}", ("gris", "fila"))
            if sp:
                t.insert("end", tr("✦ SP usado en este jefe\n"), ("sp_si", "fila"))
            else:
                otro = next((x.get("name") for x in comp.heroes
                             if comp.golden is not None and str(x.get("slot")) == str(comp.golden)), None)
                texto = tr("No usa SP (lo usa {0})", otro) if otro else tr("No usa SP (nadie lo usa en este jefe)")
                t.insert("end", texto + "\n", ("sp_no", "fila"))
        origen = h.get("origen") or PROPIO
        t.insert("end", f"  {tr('Copia'):<14}", ("gris", "fila"))
        if h.get("arrendado"):
            t.insert("end", tr("Propio · arrendado (dimensional)") + "\n", "fila")
        else:
            t.insert("end", tr(NOMBRES_ORIGEN.get(origen, origen)) + "\n",
                     ("fila",) if origen == PROPIO else ("sp_no", "fila"))
        linea(tr("ID"), tr('{0} (instancia {1})', h.get('tid', '—'), h.get('id', '—')))

        titulo(tr("Grabado"))
        t.insert("end", f"  {tr('Total'):<14}", ("gris", "fila"))
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

    # ---------------- Special Power marcado a mano ----------------

    def _detalle_elegir_sp(self, t, comp, h, sp):
        """En el detalle: varios héroes especiales y no se sabe cuál usó el SP -> botones para marcarlo."""
        especiales = [x for x in comp.heroes if x.get("hyper")]
        nombres = " / ".join(x.get("name", "?").split(" - ")[0] for x in especiales)
        t.insert("end", f"  {'Special Power':<14}", ("gris", "fila"))
        if sp == "?":
            t.insert("end", tr("⚠ No se sabe quién lo usó ({0}). Márcalo para guardarlo:\n", nombres),
                     ("sp_no", "fila"))
        else:
            usado = str(comp.golden) == str(h.get("slot"))
            t.insert("end", (tr("✦ SP usado en este jefe (marcado por ti)\n") if usado else
                             tr("No usa SP (marcaste a otro héroe)\n")), ("sp_si" if usado else "gris", "fila"))
        t.insert("end", "  ")
        for x in especiales:
            corto = x.get("name", "?").split(" - ")[0]
            b = ttk.Button(t, text=tr("Lo usó {0}", corto), style="Plano.TButton" if str(comp.golden) != str(
                x.get("slot")) else "TButton", command=lambda s=x.get("slot"), o=h: self.marcar_sp(comp, s, o))
            t.window_create("end", window=b, padx=2)
        if comp.sp_manual:
            b = ttk.Button(t, text=tr("No lo sé"), style="Plano.TButton",
                           command=lambda o=h: self.marcar_sp(comp, None, o))
            t.window_create("end", window=b, padx=2)
        t.insert("end", "\n")

    def marcar_sp(self, comp, slot, heroe):
        """Guarda qué héroe usó el SP en esa ronda (None = no se sabe) y lo vuelve a dibujar todo."""
        carpeta = getattr(comp, "carpeta_origen", None) or self.carpeta
        try:
            guardar_sp_manual(carpeta, comp, slot)
        except OSError as error:
            self._estado(tr("No se pudo guardar: {0}", error), tema.ERR)
            return
        if slot is None:
            comp.golden, comp.sp_manual = deducir_golden(comp.heroes, None), False
        else:
            comp.golden, comp.sp_manual = slot, True
        self._estado(tr("Special Power guardado para esa ronda."), tema.OK)
        self._explorar_pendiente = True
        self._invalidar_jefes()
        self._dibujar_explorar_si_visible()
        self.mostrar_detalle(comp, heroe, "HEROE")

    # ---------------- bloqueos desde el detalle ----------------

    def _carpeta_baneos_amigos(self):
        return self.base_dir / "cuentas" / CARPETA_AMIGOS

    def banear_seleccion(self, todos, solo_copia=False):
        """Bloquea lo elegido en el detalle (si es de un amigo, solo en equipos de amigos)."""
        if not self.seleccion or not self.carpeta:
            return
        comp, obj, tipo = self.seleccion
        de_amigo = id(comp) in self._ids_otro
        nueva = blq.nueva_regla_baneo(tipo, obj.get("name", ""), obj.get("tid") or "",
                                      "TODOS" if todos else comp.boss_id, solo_copia,
                                      blq.APLICA_AMIGOS if de_amigo else blq.APLICA_TODO)
        reglas = blq.sin_duplicados(self.reglas + [nueva])
        if len(reglas) == len(self.reglas):
            self._estado(tr("{0} ya estaba bloqueado.", nueva["nombre"]), tema.WARN)
            return
        self.guardar_reglas(reglas, aviso=False)
        self._estado(tr("Bloqueado: {0}. Pulsa ▶ Optimizar para recalcular.",
                        blq.describir(nueva, etiqueta_jefe=self._nombre_jefe)), tema.WARN)


def _leer_json_simple(ruta):
    try:
        return json.loads(Path(ruta).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
