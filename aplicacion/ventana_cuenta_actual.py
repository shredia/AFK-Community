# aplicacion/ventana_cuenta_actual.py
"""
Cuenta actual: fetch en el sitio, sincronización y vista de recursos, héroes, colecciones,
equipo y mascotas, con el cruce hacia Nightmare Corridor.
"""
import asyncio
import json
import queue
import threading
import tkinter as tk
import unicodedata
from datetime import datetime
from pathlib import Path
from tkinter import ttk, messagebox, simpledialog

from navegador.cuenta import (cargar_cuenta_actual, sincronizar_cuenta, hace_cuanto, uso_en_nc,
                              indice_heroes)
from navegador.optimizador import cargar_indice, construir_composiciones
from navegador.rutas import cargar_mapa_personajes
from navegador.scraper import hacer_fetch_servidor, ARCHIVO_ULTIMO_FETCH
from navegador.visuales import Visuales
from aplicacion.imagenes import CacheImagenes
from aplicacion.ventana_progreso import VentanaProgreso
from aplicacion import tema
from idiomas import tr, N_

ICONO = 30
ARCHIVO_NOMBRES_RECURSOS = "nombres_recursos.json"


def _normalizar(texto):
    texto = unicodedata.normalize("NFD", str(texto or "").lower())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def _numero(valor):
    try:
        n = int(float(valor))
    except (TypeError, ValueError):
        return str(valor)
    return f"{n:,}".replace(",", ".")


def _fecha(iso):
    if not iso:
        return "—"
    try:
        return datetime.fromisoformat(str(iso).replace("Z", "+00:00")).astimezone().strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return str(iso)


def listar_personajes(base_dir):
    """[(etiqueta, carpeta_servidor, account_id, server_id)] de tus personajes conocidos."""
    salida = []
    mapa = cargar_mapa_personajes(base_dir)
    for uid, carpeta in mapa.items():
        nombre = carpeta.name
        try:
            nombre = json.loads((carpeta / f"{carpeta.name}.json").read_text(encoding="utf-8")).get("name") or nombre
        except (OSError, json.JSONDecodeError):
            pass
        salida.append((f"{nombre} · Servidor {carpeta.name}", carpeta, carpeta.parent.name, carpeta.name))
    return sorted(salida, key=lambda x: (not (x[1] / "detalles").exists(), x[0].lower()))


class VentanaCuentaActual:
    def __init__(self, parent, perfil_path, abrir_optimizador=None):
        self.parent = parent
        self.perfil_path = Path(perfil_path)
        self.base_dir = self.perfil_path.parent
        self.abrir_optimizador = abrir_optimizador
        self.imagenes = CacheImagenes()
        self.vis = Visuales(self.base_dir)
        self.personajes = listar_personajes(self.base_dir)
        self.estado = None
        self.comps = []
        self.carpeta = None
        self._cola = queue.Queue()
        self._items = {}
        self.nombres_recursos = self._cargar_nombres()

        self.top = tk.Toplevel(parent)
        self.top.title(tr("Mi cuenta"))
        self.top.geometry("1450x900")
        self.top.minsize(1100, 700)
        estilo = ttk.Style(self.top)
        estilo.configure("Cuenta.Treeview", rowheight=ICONO + 6)

        self._crear_interfaz()
        self.top.after(100, self._procesar_cola)
        if self.personajes:
            self.combo.current(0)
            self.cambiar_personaje()

    # ---------------- infraestructura ----------------

    def _en_ui(self, f):
        self._cola.put(f)

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

    def _cargar_nombres(self):
        try:
            return json.loads((self.base_dir / ARCHIVO_NOMBRES_RECURSOS).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _guardar_nombres(self):
        (self.base_dir / ARCHIVO_NOMBRES_RECURSOS).write_text(
            json.dumps(self.nombres_recursos, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---------------- interfaz ----------------

    def _crear_interfaz(self):
        arriba = ttk.LabelFrame(self.top, text=tr(" Personaje y sincronización "))
        arriba.pack(fill="x", padx=10, pady=(10, 4))
        f1 = ttk.Frame(arriba)
        f1.pack(fill="x", padx=8, pady=4)
        ttk.Label(f1, text=tr("Personaje:")).pack(side="left")
        self.combo = ttk.Combobox(f1, state="readonly", width=36, values=[p[0] for p in self.personajes])
        self.combo.pack(side="left", padx=(4, 14))
        self.combo.bind("<<ComboboxSelected>>", lambda e: self.cambiar_personaje())
        self.btn_fetch = ttk.Button(f1, text=tr("⟳ Hacer fetch en el sitio y sincronizar"), command=self.hacer_fetch)
        self.btn_fetch.pack(side="left", padx=4)
        self.btn_sync = ttk.Button(f1, text=tr("Solo sincronizar (sin fetch)"), command=self.sincronizar)
        self.btn_sync.pack(side="left", padx=4)

        self.lbl_fetch = ttk.Label(arriba, text="", font=("Arial", 10, "bold"))
        self.lbl_fetch.pack(anchor="w", padx=8)
        self.lbl_captura = ttk.Label(arriba, text="", foreground=tema.MUTED)
        self.lbl_captura.pack(anchor="w", padx=8, pady=(0, 6))

        cuerpo = ttk.PanedWindow(self.top, orient="horizontal")
        cuerpo.pack(fill="both", expand=True, padx=10, pady=(4, 10))
        self.notebook = ttk.Notebook(cuerpo)
        cuerpo.add(self.notebook, weight=3)

        self.tablas = {}
        self._crear_tab("recursos", N_("  Recursos  "), (("cantidad", N_("Cantidad"), 160, "e"), ("categoria", N_("Categoría"), 160, "w")),
                        texto_ayuda=N_("Doble clic en un recurso sin nombre para ponerle uno."))
        self._crear_tab("heroes", N_("  Héroes  "), (
            ("calidad", N_("Calidad"), 110, "center"), ("si", N_("SI"), 45, "center"), ("grabado", N_("Grabado"), 72, "center"),
            ("muebles", N_("Muebles"), 72, "center"), ("coleccion", N_("Colección"), 170, "w"),
            ("equipo", N_("Equipo"), 190, "w"), ("guia", N_("Guía"), 50, "center"), ("nc", N_("Usos en NC"), 80, "center")),
                        texto_ayuda=N_("Guía: ✓ lleva una colección que cumple la recomendación · ◐ tienes una copia que "
                                       "cumple, pero sin poner (libre o en otro héroe) · ✗ no tienes ninguna que cumpla"))
        self._crear_tab("colecciones", N_("  Colecciones  "), (
            ("nivel", N_("Nivel"), 50, "center"), ("estrellas", N_("★"), 50, "center"), ("miticos", N_("Míticos"), 60, "center"),
            ("equipada", N_("Equipada en"), 170, "w"), ("ideal", N_("Ideal para (guía)"), 230, "w"),
            ("nc", N_("Usos en NC"), 80, "center")),
                        texto_ayuda=N_("Todas las colecciones de tu cuenta (del último fetch), puestas o libres. "
                                       "«Ideal para»: tus héroes a los que la guía del sitio les recomienda esta "
                                       "colección y esta copia la cumple."))
        self._crear_tab("equipo", N_("  Equipo de reserva  "), (
            ("categoria", N_("Tipo"), 150, "w"), ("tier", N_("Tier"), 50, "center"), ("estrellas", N_("★"), 50, "center"),
            ("faccion", N_("Facción"), 120, "w"), ("cantidad", N_("Cantidad"), 70, "center")))
        self._crear_tab("mascotas", N_("  Mascotas y artefactos  "), (
            ("nivel", N_("Nivel / despertar"), 120, "center"), ("extra", N_("Trabajos"), 160, "w")))

        # Panel de detalle con el cruce hacia NC
        panel = ttk.LabelFrame(cuerpo, text=tr(" Detalle y uso en Nightmare Corridor "))
        cuerpo.add(panel, weight=2)
        cab = ttk.Frame(panel)
        cab.pack(fill="x", padx=8, pady=8)
        self.lbl_img = ttk.Label(cab)
        self.lbl_img.pack(side="left")
        self.lbl_nombre = ttk.Label(cab, text=tr("Elige un elemento"), font=("Arial", 13, "bold"), wraplength=330)
        self.lbl_nombre.pack(side="left", padx=10)
        self.btn_nc = ttk.Button(panel, text=tr("Ver en el optimizador de NC"), state="disabled", command=self._ver_en_nc)
        self.btn_nc.pack(anchor="w", padx=8)
        marco = ttk.Frame(panel)
        marco.pack(fill="both", expand=True, padx=8, pady=8)
        self.txt = tk.Text(marco, wrap="word", font=("Consolas", 10), state="disabled", width=50)
        barra = ttk.Scrollbar(marco, command=self.txt.yview)
        self.txt.configure(yscrollcommand=barra.set)
        self.txt.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")
        self.txt.tag_configure("titulo", font=("Arial", 10, "bold"), spacing1=8)
        self.txt.tag_configure("gris", foreground=tema.MUTED)
        self.txt.tag_configure("negrita", font=("Arial", 9, "bold"))
        self.txt.tag_configure("ok", foreground=tema.OK, lmargin2=50)
        self.txt.tag_configure("medio", foreground=tema.DORADO, lmargin2=50)
        self.txt.tag_configure("mal", foreground=tema.ERR, lmargin2=50)
        self.txt.tag_configure("sangria", lmargin2=50)
        self.txt.tag_configure("nota", foreground=tema.MUTED, font=("Arial", 8, "italic"), lmargin1=40, lmargin2=40)
        self._enfoque_nc = None

    def _crear_tab(self, clave, titulo, columnas, texto_ayuda=None):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=tr(titulo))
        barra = ttk.Frame(tab)
        barra.pack(fill="x", padx=8, pady=6)
        ttk.Label(barra, text=tr("Buscar:")).pack(side="left")
        var = tk.StringVar()
        ttk.Entry(barra, textvariable=var, width=30).pack(side="left", padx=4)
        var.trace_add("write", lambda *a, c=clave: self._llenar(c))
        contador = ttk.Label(barra, text="", foreground=tema.MUTED)
        contador.pack(side="left", padx=8)
        if texto_ayuda:
            ttk.Label(barra, text=tr(texto_ayuda), foreground=tema.MUTED).pack(side="right")

        marco = ttk.Frame(tab)
        marco.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        tabla = ttk.Treeview(marco, columns=[c[0] for c in columnas], style="Cuenta.Treeview")
        tabla.heading("#0", text=tr("Nombre"))
        tabla.column("#0", width=290, anchor="w")
        for col, texto, ancho, ancla in columnas:
            tabla.heading(col, text=tr(texto), command=lambda c=col, k=clave: self._ordenar(k, c))
            tabla.column(col, width=ancho, anchor=ancla)
        sb = ttk.Scrollbar(marco, orient="vertical", command=tabla.yview)
        tabla.configure(yscrollcommand=sb.set)
        tabla.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        tabla.bind("<<TreeviewSelect>>", lambda e, k=clave: self._al_elegir(k))
        if clave == "recursos":
            tabla.bind("<Double-1>", lambda e: self._renombrar_recurso())
        self.tablas[clave] = {"tabla": tabla, "buscar": var, "contador": contador, "filas": [], "orden": None}

    # ---------------- datos ----------------

    def cambiar_personaje(self):
        i = self.combo.current()
        if i < 0:
            return
        _, self.carpeta, self.account_id, self.server_id = self.personajes[i]
        self.estado = cargar_cuenta_actual(self.carpeta)
        self._mostrar_info_fetch()
        self._preparar_filas()
        for clave in self.tablas:
            self._llenar(clave)
        self.comps = []
        if (self.carpeta / "detalles").exists():
            carpeta = self.carpeta

            def tarea():
                try:
                    datos = cargar_indice(carpeta)
                    comps = construir_composiciones(datos["runs"], (self.estado or {}).get("heroes_temporales") or ())
                except Exception:
                    comps = []
                self._en_ui(lambda: self._fin_comps(carpeta, comps))

            threading.Thread(target=tarea, daemon=True).start()

    def _fin_comps(self, carpeta, comps):
        if carpeta != self.carpeta:
            return
        self.comps = comps
        self._preparar_filas()
        for clave in ("heroes", "colecciones"):
            self._llenar(clave)

    def _mostrar_info_fetch(self):
        cuenta = {}
        try:
            cuenta = json.loads((self.carpeta.parent / "account.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
        ultimo = None
        try:
            ultimo = json.loads((self.carpeta / ARCHIVO_ULTIMO_FETCH).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
        if ultimo:
            fecha = ultimo.get("fetchedAt")
            extra = ""
            if ultimo.get("nc_disponibles") is not None:
                extra = f" · NC: el juego devolvió {ultimo.get('nc_traidas')} de {ultimo.get('nc_disponibles')} runs"
        elif str(cuenta.get("selectedServer")) == str(self.server_id):
            fecha, extra = cuenta.get("fetchedAt"), ""
        else:
            fecha, extra = None, " (este servidor no es el último que se actualizó en el sitio)"
        color = tema.ERR if not fecha else (tema.WARN if "día" in hace_cuanto(fecha) else tema.OK)
        self.lbl_fetch.configure(text=tr('Último fetch en el sitio: {0} ({1}){2}', _fecha(fecha), hace_cuanto(fecha), extra),
                                 foreground=color)
        if self.estado:
            self.lbl_captura.configure(
                text=tr('Datos en la app: captura del {0} ({1}) · sincronizado {2} · nivel {3} · árbol {4}', _fecha(self.estado.get('capturedAt')), hace_cuanto(self.estado.get('capturedAt')), hace_cuanto(self.estado.get('sincronizado')), self.estado.get('cuenta', {}).get('level'), self.estado.get('arbol', {}).get('lv', '—')))
        else:
            self.lbl_captura.configure(text=tr("Aún no hay datos de este personaje en la app: pulsa "
                                            "'Hacer fetch en el sitio y sincronizar'."))

    def _preparar_filas(self):
        """Arma las filas de cada tabla: (texto_busqueda, icono_url, nombre, valores, objeto)."""
        e = self.estado or {}
        filas = {k: [] for k in self.tablas}

        for m in e.get("monedas") or []:
            nombre = self.nombres_recursos.get(str(m["id"])) or (
                m["nombre"] if not str(m["nombre"]).startswith("Item ") else f"Recurso #{m['id']}")
            filas["recursos"].append((nombre, m.get("imageUrl"), nombre,
                                      (_numero(m.get("cantidad")), "Recurso / moneda"), ("moneda", m)))
        for o in sorted(e.get("objetos") or [], key=lambda o: str(o.get("nombre"))):
            filas["recursos"].append((o["nombre"], o.get("imageUrl"), o["nombre"],
                                      (_numero(o.get("cantidad")), o.get("categoria") or ""), ("objeto", o)))

        indice = indice_heroes(e)
        unicos = {id(h): h for h in indice.values()}.values()
        temporales = [h for h in e.get("roster") or [] if h.get("temporal")]
        for h in sorted(list(unicos) + temporales, key=lambda h: str(h.get("name") or "").lower()):
            col = h.get("collection") or {}
            uso = uso_en_nc(self.comps, tid=h.get("tid")) if self.comps else {"equipos": 0}
            mueble = h.get("furniture") or {}
            equipo = " ".join(f"{(g.get('part') or '?')[:1]}:{self.vis.tier_equipo(g) or '—'}★{g.get('stars', 0)}"
                              for g in sorted(h.get("gear") or [], key=lambda g: g.get("slot", 0))) or "—"
            nombre = h.get("name", "?") + ("  " + tr("(temporal)") if h.get("temporal") else "")
            if h.get("solo_copias"):
                nombre += "  " + tr("(solo copia)")
            recs = self.vis.recomendaciones_heroe(h.get("tid"))
            guia = ""
            if recs:
                if col and any(self.vis.evaluar_recomendacion(col, f)[0] for f in recs):
                    guia = "✓"
                elif any((self.vis.mejor_copia(e.get("colecciones"), f) or (None, False))[1] for f in recs):
                    guia = "◐"
                else:
                    guia = "✗"
            filas["heroes"].append((f"{h.get('name')} {col.get('name', '')}", h.get("imageUrl"), nombre, (
                self.vis.nombre_calidad(h.get("calidad_max") or h.get("quality"))
                + (f" (+{len(h['copias']) - (1 if h.get('solo_copias') else 0)})"
                   if len(h.get("copias") or []) - (1 if h.get("solo_copias") else 0) > 0 else ""),
                "—" if h.get("sig") is None else h.get("sig"),
                h.get("engraving", 0), f"{mueble.get('pieces', 0)}/9", col.get("name", "—"), equipo, guia,
                uso["equipos"] or ""), ("heroe", h)))

        # héroes desarrollados con recomendaciones de la guía (para "Ideal para")
        recs_heroes = []
        for h in e.get("roster") or []:
            recs = self.vis.recomendaciones_heroe(h.get("tid"))
            if recs:
                recs_heroes.append((h.get("name"), recs))
        for c in e.get("colecciones") or []:
            uso = uso_en_nc(self.comps, coleccion_id=c.get("id")) if self.comps else {"equipos": 0}
            ideal = [nombre for nombre, recs in recs_heroes
                     if any(str(f.get("collectionTid")) == str(c.get("tid")) and self.vis.evaluar_recomendacion(c, f)[0]
                            for f in recs)]
            texto_ideal = ", ".join(ideal[:3]) + (f" +{len(ideal) - 3}" if len(ideal) > 3 else "")
            afijos = c.get("affixes") or []
            filas["colecciones"].append((f"{c.get('name')} {c.get('equipada_en') or ''}",
                                         self.vis.imagen_coleccion(c.get("tid")), c.get("name", "?"), (
                c.get("level", "—"), "★" * (self.vis.estrellas_coleccion(c) or 0) or "—",
                sum(1 for a in afijos if int(a.get("quality") or 0) >= 5), c.get("equipada_en") or tr("— libre —"),
                texto_ideal, uso["equipos"] or ""), ("coleccion", c)))

        facciones = {str(k): v.get("name") for k, v in (self.vis.t.get("facciones_equipo") or {}).items()}
        for g in e.get("equipo_reserva") or []:
            tier = ((self.vis.t.get("equipo") or {}).get(str(g.get("tid"))) or {}).get("tier")
            filas["equipo"].append((g["nombre"], g.get("imageUrl"), g["nombre"], (
                g.get("categoria"), "—" if tier is None else ("M" if tier == 0 else f"T{tier}"),
                g.get("estrellas") or 0, facciones.get(str(g.get("faccion")), "—"), _numero(g.get("cantidad"))),
                ("equipo", g)))

        for p in e.get("mascotas") or []:
            filas["mascotas"].append((p["nombre"], p.get("imageUrl"), p["nombre"],
                                      (p.get("nivel"), " / ".join(str(x) for x in p.get("trabajos") or [])),
                                      ("mascota", p)))
        for a in e.get("artefactos") or []:
            filas["mascotas"].append((a["nombre"], a.get("imageUrl"), f"{a['nombre']} (artefacto)",
                                      (a.get("despertar"), ""), ("artefacto", a)))

        for k in self.tablas:
            self.tablas[k]["filas"] = filas[k]

    def _llenar(self, clave):
        info = self.tablas[clave]
        tabla = info["tabla"]
        tabla.delete(*tabla.get_children())
        consulta = _normalizar(info["buscar"].get().strip())
        filas = [f for f in info["filas"] if not consulta or consulta in _normalizar(f[0])]
        if info["orden"]:
            col, inverso = info["orden"]
            indice = [c for c in tabla["columns"]].index(col)

            def clave_orden(f):
                v = f[3][indice]
                try:
                    return (0, float(str(v).replace(".", "").replace("★", "1")))
                except ValueError:
                    return (1, str(v))
            filas = sorted(filas, key=clave_orden, reverse=inverso)
        for i, (_, url, nombre, valores, obj) in enumerate(filas):
            iid = f"{clave}{i}"
            tabla.insert("", "end", iid=iid, text=" " + str(nombre), image=self.imagenes.obtener(url, ICONO),
                         values=valores)
            self._items[iid] = obj
        info["contador"].configure(text=tr('{0} de {1}', len(filas), len(info['filas'])))

    def _ordenar(self, clave, col):
        info = self.tablas[clave]
        anterior = info["orden"]
        info["orden"] = (col, not anterior[1] if anterior and anterior[0] == col else True)
        self._llenar(clave)

    # ---------------- detalle + NC ----------------

    def _al_elegir(self, clave):
        sel = self.tablas[clave]["tabla"].selection()
        if not sel or sel[0] not in self._items:
            return
        tipo, obj = self._items[sel[0]]
        t = self.txt
        t.configure(state="normal")
        t.delete("1.0", "end")
        self._enfoque_nc = None
        self._jefe_mas_usado = None

        def linea(etq, val):
            t.insert("end", f"  {etq:<14}", "gris")
            t.insert("end", f"{val}\n")

        if tipo == "heroe":
            self.lbl_img.configure(image=self.imagenes.retrato(obj, self.vis, None, 120, con_equipo=True))
            self.lbl_nombre.configure(text=obj.get("name", "?"))
            col = obj.get("collection") or {}
            t.insert("end", tr("Build actual\n"), "titulo")
            linea(tr("Facción"), f"{obj.get('faction')} · {obj.get('job')}")
            linea(tr("Calidad"), self.vis.nombre_calidad(obj.get("quality")))
            linea(tr("SI"), "—" if obj.get("sig") is None else f"+{obj.get('sig')}")
            linea(tr("Grabado"), obj.get("engraving"))
            linea(tr("Muebles"), f"{(obj.get('furniture') or {}).get('pieces', 0)}/9")
            linea(tr("Colección"), tr('{0} (nv {1})', col.get('name', '—'), col.get('level', '—')))
            for g in sorted(obj.get("gear") or [], key=lambda g: g.get("slot", 0)):
                linea(g.get("part", "?"), f"{g.get('name')} {self.vis.tier_equipo(g) or ''} ★{g.get('stars', 0)}")
            if obj.get("copias"):
                nombres = ", ".join(self.vis.nombre_calidad(q) for q in obj["copias"])
                linea(tr("Copias base"), nombres + ("  " + tr("(no está desarrollado)") if obj.get("solo_copias") else ""))
            if obj.get("temporal"):
                linea(tr("Copia"), tr("Temporal (de prueba)"))
            self._escribir_guia_heroe(obj)
            self._escribir_uso_nc(uso_en_nc(self.comps, tid=obj.get("tid")), obj.get("name", ""))
            self._enfoque_nc = {"texto": obj.get("name", "").split(" - ")[0]}
        elif tipo == "coleccion":
            self.lbl_img.configure(image=self.imagenes.obtener(self.vis.imagen_coleccion(obj.get("tid")), 96))
            self.lbl_nombre.configure(text=obj.get("name", "?"))
            t.insert("end", tr("Colección\n"), "titulo")
            linea(tr("Nivel"), obj.get("level"))
            linea(tr("Estrellas"), "★" * (self.vis.estrellas_coleccion(obj) or 0) or "—")
            linea(tr("Equipada en"), obj.get("equipada_en") or "— (libre)")
            for a in sorted(obj.get("affixes") or [], key=lambda a: -int(a.get("quality") or 0)):
                nombre, icono = self.vis.afijo(a.get("nature"), a.get("quality"))
                valor = self.vis.valor_afijo(obj.get("tid"), a.get("nature"), a.get("quality")) or ""
                t.insert("end", "    ")
                if icono:
                    t.image_create("end", image=self.imagenes.obtener(icono, 24))
                t.insert("end", tr(' {0} {1}  (calidad {2})\n', nombre, valor, a.get('quality')))
            self._escribir_guia_coleccion(obj)
            self._escribir_uso_nc(uso_en_nc(self.comps, coleccion_id=obj.get("id")), obj.get("name", ""))
            self._enfoque_nc = {"texto": obj.get("name", "")}
        else:
            self.lbl_img.configure(image=self.imagenes.obtener(obj.get("imageUrl"), 96))
            nombre = obj.get("nombre", "?")
            if tipo == "moneda":
                nombre = self.nombres_recursos.get(str(obj["id"])) or nombre
            self.lbl_nombre.configure(text=tr(nombre))
            t.insert("end", tr("Detalle\n"), "titulo")
            for etq, clave in (("Cantidad", "cantidad"), ("Categoría", "categoria"), ("Nivel", "nivel"),
                               ("Estrellas", "estrellas"), ("Despertar", "despertar"), ("ID", "id"), ("TID", "tid")):
                if obj.get(clave) not in (None, ""):
                    linea(etq, _numero(obj[clave]) if clave == "cantidad" else obj[clave])
            if obj.get("descripcion"):
                t.insert("end", "\n" + obj["descripcion"] + "\n")
        t.configure(state="disabled")
        self.btn_nc.configure(state="normal" if self._enfoque_nc and self.abrir_optimizador else "disabled")

    def _nombre_heroe(self, tid):
        for h in (self.estado or {}).get("roster") or []:
            if str(h.get("tid")) == str(tid):
                return h.get("name", "?").split(" - ")[0]
        return f"Héroe {tid}"

    def _texto_fila_guia(self, f):
        partes = [f"{self.vis.nombre_coleccion(f['collectionTid'])} +{f.get('skillBonus', 0)}"]
        if f.get("primary"):
            partes.append(f.get("primary"))
        if f.get("secondary"):
            partes.append(f"(2ª: {f['secondary']})")
        return " · ".join(partes)

    def _escribir_guia_heroe(self, h):
        t = self.txt
        recs = self.vis.recomendaciones_heroe(h.get("tid"))
        t.insert("end", tr("Colecciones recomendadas (guía)\n"), "titulo")
        if not self.vis.recomendaciones:
            t.insert("end", tr("  Sin datos de la guía: sincroniza para descargarla.\n"), "gris")
            return
        if not recs:
            t.insert("end", tr("  La guía no tiene recomendación para este héroe.\n"), "gris")
            return
        equipada = h.get("collection") or {}
        colecciones = (self.estado or {}).get("colecciones") or []
        for f in sorted(recs, key=lambda f: (f.get("group") != "Basic", "NC" not in f.get("modos_heroe", []))):
            t.insert("end", "  ")
            icono = self.vis.imagen_coleccion(f["collectionTid"])
            if icono:
                t.image_create("end", image=self.imagenes.obtener(icono, 26))
            t.insert("end", f" {self._texto_fila_guia(f)}\n", "negrita")
            t.insert("end", tr('      {0} · modos: {1}\n', f.get('group'), '/'.join(f.get('modos_heroe') or [])), ("gris", "sangria"))
            if equipada and self.vis.evaluar_recomendacion(equipada, f)[0]:
                t.insert("end", tr("      ✓ La colección que lleva ahora cumple\n"), "ok")
            else:
                mejor = self.vis.mejor_copia(colecciones, f)
                if mejor is None:
                    t.insert("end", tr("      ✗ No tienes esta colección\n"), "mal")
                elif mejor[1]:
                    donde = mejor[0].get("equipada_en") or "libre"
                    t.insert("end", tr('      ✓ Tienes una copia que cumple (#{0}, {1})\n', mejor[0].get('id'), donde), "ok")
                else:
                    donde = mejor[0].get("equipada_en") or "libre"
                    t.insert("end", tr('      ~ Más cercana #{0} ({1}): {2}\n', mejor[0].get('id'), donde, mejor[3]), "medio")
            if f.get("notes"):
                t.insert("end", f"      {f['notes']}\n", "nota")

    def _escribir_guia_coleccion(self, col):
        t = self.txt
        filas = self.vis.recomendaciones_coleccion(col.get("tid"))
        t.insert("end", tr("En la guía de colecciones\n"), "titulo")
        if not filas:
            t.insert("end", tr("  La guía no recomienda este tipo de colección.\n"), "gris")
            return
        for f in filas:
            cumple, _, detalle = self.vis.evaluar_recomendacion(col, f)
            heroes = ", ".join(self._nombre_heroe(tid) for tid in f.get("heroTids") or []) or f.get("audience") or "—"
            t.insert("end", f"  {'✓' if cumple else '✗'} +{f.get('skillBonus', 0)} · {f.get('primary') or '—'}"
                            f" · {'/'.join(f.get('modes') or [])}\n", "ok" if cumple else "medio")
            t.insert("end", tr('      Para: {0}\n', heroes), "sangria")
            if not cumple:
                t.insert("end", tr('      Esta copia: {0}\n', detalle), ("gris", "sangria"))

    def _escribir_uso_nc(self, uso, nombre):
        t = self.txt
        t.insert("end", tr("Uso en Nightmare Corridor (tus copias)\n"), "titulo")
        if not self.comps:
            t.insert("end", tr("  Este personaje no tiene runs de NC descargadas.\n"), "gris")
            return
        if not uso["equipos"]:
            t.insert("end", tr('  No usaste {0} en ningún equipo de NC.\n', nombre), "gris")
            return
        t.insert("end", tr('  En {0} equipos. Mejor tiempo por jefe:\n', uso['equipos']))
        mejor_boss = None
        for boss, (mejor, usos) in sorted(uso["por_jefe"].items(), key=lambda x: x[1][0]):
            nombre_jefe, url = self.vis.jefe(boss)
            t.insert("end", "    ")
            if url:
                t.image_create("end", image=self.imagenes.obtener(url, 28))
            t.insert("end", tr(' {0:<20} {1:7.3f} s  ({2} usos)\n', nombre_jefe, mejor, usos), "sangria")
            mejor_boss = mejor_boss or boss
        if self._enfoque_nc is None:
            self._enfoque_nc = {}
        self._jefe_mas_usado = max(uso["por_jefe"], key=lambda b: uso["por_jefe"][b][1])

    def _ver_en_nc(self):
        if not self._enfoque_nc or not self.abrir_optimizador:
            return
        enfoque = dict(self._enfoque_nc)
        if getattr(self, "_jefe_mas_usado", None):
            enfoque["boss"] = self._jefe_mas_usado
        self.abrir_optimizador(self.carpeta, enfoque)

    def _renombrar_recurso(self):
        sel = self.tablas["recursos"]["tabla"].selection()
        if not sel or sel[0] not in self._items:
            return
        tipo, obj = self._items[sel[0]]
        if tipo != "moneda":
            return
        actual = self.nombres_recursos.get(str(obj["id"]), "")
        nuevo = simpledialog.askstring(tr("Nombre del recurso"), tr('Nombre para el recurso #{0}:', obj['id']),
                                       initialvalue=actual, parent=self.top)
        if nuevo is None:
            return
        if nuevo.strip():
            self.nombres_recursos[str(obj["id"])] = nuevo.strip()
        else:
            self.nombres_recursos.pop(str(obj["id"]), None)
        self._guardar_nombres()
        self._preparar_filas()
        self._llenar("recursos")

    # ---------------- fetch y sincronización ----------------

    def _bloquear(self, si):
        estado = "disabled" if si else "normal"
        self.btn_fetch.configure(state=estado)
        self.btn_sync.configure(state=estado)

    def hacer_fetch(self):
        if not self.carpeta:
            return
        if not messagebox.askyesno(
                tr("Fetch"), tr('El sitio va a leer de nuevo los datos del juego para el servidor {0} (héroes, recursos, runs recientes de NC...). Suele tardar menos de un minuto.\n\n¿Continuar?', self.server_id),
                parent=self.top):
            return
        self._ejecutar(con_fetch=True)

    def sincronizar(self):
        self._ejecutar(con_fetch=False)

    def _ejecutar(self, con_fetch):
        self._bloquear(True)
        prog = VentanaProgreso(self.top, "Fetch y sincronización" if con_fetch else "Sincronizando",
                               cancelable=con_fetch)
        account_id, server_id = self.account_id, self.server_id

        def tarea():
            try:
                if con_fetch:
                    r = asyncio.run(hacer_fetch_servidor(self.perfil_path, self.base_dir, account_id, server_id,
                                                         progreso=prog.log, cancelar=prog.cancelar))
                    if r.get("error"):
                        raise RuntimeError(tr('El sitio informó un error: {0}', r['error']))
                    if r.get("nc_disponibles") is not None:
                        prog.log(tr('NC: el juego devolvió {0} de {1} runs (temporada {2}). Importadas: {3}.', r.get('nc_traidas'), r.get('nc_disponibles'), r.get('nc_temporada'), r.get('runs_importadas')))
                    if prog.cancelar.is_set():
                        prog.terminar(tr("Dejé de esperar. Sincroniza cuando el fetch termine en el sitio."), ok=False)
                        self._en_ui(self._fin)
                        return
                carpeta, estado = asyncio.run(sincronizar_cuenta(self.perfil_path, self.base_dir, progreso=prog.log))
            except Exception as error:
                prog.terminar(f"✗ {error}", ok=False)
                self._en_ui(self._fin)
                return
            prog.terminar(tr("✓ Cuenta sincronizada (servidor {0}). Para traer runs nuevas de NC usa 'Runs de NC' → Actualizar lista y Descargar detalles.", carpeta.name), ok=True)
            self._en_ui(lambda: self._fin(carpeta))

        threading.Thread(target=tarea, daemon=True).start()

    def _fin(self, carpeta=None):
        self._bloquear(False)
        self.personajes = listar_personajes(self.base_dir)
        self.combo.configure(values=[p[0] for p in self.personajes])
        objetivo = carpeta or self.carpeta
        for i, p in enumerate(self.personajes):
            if objetivo and Path(p[1]) == Path(objetivo):
                self.combo.current(i)
        self.vis = Visuales(self.base_dir)
        self.cambiar_personaje()
