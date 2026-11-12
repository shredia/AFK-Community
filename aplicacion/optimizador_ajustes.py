# aplicacion/optimizador_ajustes.py
"""
Ventana '⚙ Configurar' del optimizador, en una sola ventana con pestañas:
  Fuentes · Bloqueos · Mi roster · Búsqueda · Vista
y la ventanita para cambiar la rotación de la semana.
"""
import json
import tkinter as tk
import unicodedata
from pathlib import Path
from tkinter import ttk, messagebox

from navegador import bloqueos as blq
from navegador import roster as rst
from navegador.optimizador import CAMPOS_HEROE, CAMPOS_COLECCION, catalogo
from aplicacion import tema
from idiomas import tr, N_

CARPETA_AMIGOS = "_amigos"


def _norm(texto):
    texto = unicodedata.normalize("NFD", str(texto or "").lower())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def _leer_json(ruta):
    try:
        return json.loads(Path(ruta).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


class ComboBuscable(ttk.Combobox):
    """Combobox editable que filtra su lista mientras escribes (sin tildes ni mayúsculas)."""

    def __init__(self, padre, valores=(), **kw):
        super().__init__(padre, **kw)
        self.todos = list(valores)
        self.configure(values=self.todos)
        self.bind("<KeyRelease>", self._filtrar, add="+")

    def poner_valores(self, valores):
        self.todos = list(valores)
        self.configure(values=self.todos)

    def _filtrar(self, evento):
        if evento.keysym in ("Down", "Up", "Return", "Escape", "Tab"):
            return
        q = _norm(self.get().strip())
        if not q:
            self.configure(values=self.todos)
            return
        empiezan = [v for v in self.todos if _norm(v).startswith(q)]
        contienen = [v for v in self.todos if q in _norm(v) and v not in empiezan]
        self.configure(values=empiezan + contienen)


# ============================================================
# BLOQUEOS (baneos + límites de build, una sola lista)
# ============================================================

class EditorBloqueos(ttk.Frame):
    TIPOS = (("HEROE", N_("Héroe")), ("COLECCION", N_("Colección")), ("MASCOTA", N_("Mascota")))

    def __init__(self, padre, reglas, comps, bosses, etiqueta_jefe, vis, objeto=None, nombre=None):
        super().__init__(padre)
        self.reglas = [dict(b) for b in reglas]
        self.vis = vis
        self.etiqueta_jefe = etiqueta_jefe
        cat = catalogo(comps)
        self.ids = {"HEROE": cat["HEROE"], "MASCOTA": cat["MASCOTA"]}
        self.nombres = {
            "HEROE": sorted(cat["HEROE"], key=_norm),
            "MASCOTA": sorted(cat["MASCOTA"], key=_norm),
            "COLECCION": sorted({(h.get("collection") or {}).get("name") for c in comps for h in c.heroes
                                 if (h.get("collection") or {}).get("name")}, key=_norm),
        }
        self.jefes = ["TODOS"] + list(bosses)

        ttk.Label(self, wraplength=860, justify="left", style="Muted.TLabel", text=tr(
            "Todo lo que el optimizador no debe usar: héroes o mascotas que no quieres, colecciones que no tienes "
            "y builds hasta las que llegas (SI, grabado, muebles, ascensión). Cada regla puede valer para todos los "
            "equipos, solo los tuyos o solo los de amigos. Doble clic: activar / desactivar.")).pack(
            anchor="w", pady=(0, 8))

        marco_tabla = ttk.Frame(self)
        marco_tabla.pack(fill="both", expand=True)
        self.tabla = ttk.Treeview(marco_tabla, columns=("regla", "jefe", "aplica", "activa"), show="headings", height=9)
        for col, titulo, ancho in (("regla", N_("Regla"), 420), ("jefe", N_("Jefe"), 170),
                                   ("aplica", N_("Aplica a"), 170), ("activa", N_("Activa"), 70)):
            self.tabla.heading(col, text=tr(titulo))
            self.tabla.column(col, width=ancho, anchor="w" if col != "activa" else "center", stretch=col == "regla")
        self.tabla.tag_configure("inactiva", foreground=tema.TENUE)
        barra = ttk.Scrollbar(marco_tabla, orient="vertical", command=self.tabla.yview)
        self.tabla.configure(yscrollcommand=barra.set)
        self.tabla.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")
        self.tabla.bind("<Double-1>", lambda e: self._alternar())
        self.tabla.bind("<Delete>", lambda e: self._quitar())

        botones = ttk.Frame(self)
        botones.pack(fill="x", pady=(6, 10))
        ttk.Button(botones, text=tr("Activar / desactivar"), command=self._alternar).pack(side="left")
        ttk.Button(botones, text=tr("Quitar"), command=self._quitar).pack(side="left", padx=6)
        ttk.Button(botones, text=tr("Quitar todas"), style="Plano.TButton", command=self._quitar_todas).pack(side="right")

        form = ttk.Frame(self, style="Tarjeta.TFrame", padding=12)
        form.pack(fill="x")
        ttk.Label(form, text=tr("NUEVA REGLA"), style="PanelMuted.TLabel").grid(row=0, column=0, columnspan=6, sticky="w")
        self.var_objeto = tk.StringVar(value=objeto or "HEROE")
        tipos = ttk.Frame(form, style="Panel.TFrame")
        tipos.grid(row=1, column=0, columnspan=6, sticky="w", pady=(6, 8))
        for valor, texto in self.TIPOS:
            ttk.Radiobutton(tipos, text=tr(texto), value=valor, variable=self.var_objeto, style="Toolbutton",
                            command=self._al_cambiar_objeto).pack(side="left", padx=(0, 4))

        ttk.Label(form, text=tr("Nombre"), style="Panel.TLabel").grid(row=2, column=0, sticky="w")
        self.combo_nombre = ComboBuscable(form, width=30)
        self.combo_nombre.grid(row=3, column=0, sticky="w", padx=(0, 10))
        ttk.Label(form, text=tr("Condición"), style="Panel.TLabel").grid(row=2, column=1, sticky="w")
        self.combo_campo = ttk.Combobox(form, state="readonly", width=30)
        self.combo_campo.grid(row=3, column=1, sticky="w", padx=(0, 10))
        self.combo_campo.bind("<<ComboboxSelected>>", lambda e: self._al_cambiar_campo())
        ttk.Label(form, text=tr("Máximo"), style="Panel.TLabel").grid(row=2, column=2, sticky="w")
        self.var_max = tk.IntVar(value=2)
        self.spin_max = ttk.Spinbox(form, from_=0, to=200, width=6, textvariable=self.var_max,
                                    command=self._al_cambiar_campo)
        self.spin_max.grid(row=3, column=2, sticky="w", padx=(0, 10))
        self.spin_max.bind("<KeyRelease>", lambda e: self._al_cambiar_campo())
        ttk.Label(form, text=tr("Jefe"), style="Panel.TLabel").grid(row=2, column=3, sticky="w")
        self.combo_jefe = ttk.Combobox(form, state="readonly", width=22,
                                       values=[tr("Todos los jefes")] + [etiqueta_jefe(b) for b in bosses])
        self.combo_jefe.current(0)
        self.combo_jefe.grid(row=3, column=3, sticky="w", padx=(0, 10))
        ttk.Label(form, text=tr("Aplica a"), style="Panel.TLabel").grid(row=2, column=4, sticky="w")
        self.combo_aplica = ttk.Combobox(form, state="readonly", width=20,
                                         values=[tr(v) for v in blq.NOMBRES_APLICA.values()])
        self.combo_aplica.current(0)
        self.combo_aplica.grid(row=3, column=4, sticky="w", padx=(0, 10))
        ttk.Button(form, text=tr("+ Agregar"), style="Acento.TButton", command=self._agregar).grid(
            row=3, column=5, sticky="e")
        form.columnconfigure(5, weight=1)
        self.lbl_ayuda = ttk.Label(form, text="", style="PanelMuted.TLabel")
        self.lbl_ayuda.grid(row=4, column=0, columnspan=6, sticky="w", pady=(6, 0))

        self._al_cambiar_objeto()
        if nombre:
            self.combo_nombre.set(nombre)
        self._refrescar()

    # ---- formulario
    def _campos(self):
        """[(clave, texto)] de condiciones para el tipo elegido."""
        objeto = self.var_objeto.get()
        if objeto == "MASCOTA":
            return [("banear", tr("No usar"))]
        if objeto == "COLECCION":
            return [("no_tengo", tr("No la tengo"))] + [(k, tr("{0} máximo", tr(v))) for k, v in CAMPOS_COLECCION.items()]
        return ([("banear", tr("No usar (o no lo tengo)")), ("copia", tr("No usar la copia prestada/prueba"))]
                + [(k, tr("{0} máximo", tr(v))) for k, v in CAMPOS_HEROE.items()])

    def _al_cambiar_objeto(self):
        objeto = self.var_objeto.get()
        self.combo_nombre.poner_valores(([tr("(cualquiera)")] if objeto != "MASCOTA" else []) + self.nombres[objeto])
        self.combo_nombre.set("")
        self.combo_campo.configure(values=[t for _, t in self._campos()])
        self.combo_campo.current(0)
        self._al_cambiar_campo()

    def _campo(self):
        i, campos = self.combo_campo.current(), self._campos()
        return campos[i][0] if 0 <= i < len(campos) else campos[0][0]

    def _al_cambiar_campo(self):
        campo = self._campo()
        con_max = campo not in ("banear", "copia", "no_tengo")
        self.spin_max.configure(state="normal" if con_max else "disabled")
        try:
            valor = int(self.var_max.get())
        except (tk.TclError, ValueError):
            valor = 0
        ayudas = {"quality": tr("Ascensión máxima: {0}", self.vis.nombre_calidad(valor)) if self.vis.disponible else "",
                  "estrellas": tr("★ de habilidad de la colección (0 a 3)"),
                  "muebles": tr("Piezas de mueble (0 a 9)"),
                  "sig": tr("Nivel del artículo exclusivo (SI): 0, 10, 20, 30…"),
                  "engraving": tr("Grabado: 30, 60, 80…"),
                  "mythic": tr("Cantidad de afijos míticos"),
                  "level": tr("Nivel de la colección"),
                  "banear": tr("Descarta cualquier equipo que lo use."),
                  "copia": tr("Solo descarta los equipos donde se usó prestado o de prueba."),
                  "no_tengo": tr("Descarta los equipos que usan esa colección.")}
        self.lbl_ayuda.configure(text=ayudas.get(campo, ""))

    def _agregar(self):
        objeto, campo = self.var_objeto.get(), self._campo()
        nombre = self.combo_nombre.get().strip()
        if not nombre or nombre == tr("(cualquiera)"):
            if campo in ("banear", "copia") or objeto == "MASCOTA":
                self.lbl_ayuda.configure(text=tr("Elige un nombre de la lista."), foreground=tema.WARN)
                return
            nombre = "*"
        i = self.combo_jefe.current()
        jefe = self.jefes[i] if 0 <= i < len(self.jefes) else "TODOS"
        aplica = list(blq.NOMBRES_APLICA)[max(0, self.combo_aplica.current())]
        if campo in ("banear", "copia"):
            nueva = blq.nueva_regla_baneo(objeto, nombre, self.ids.get(objeto, {}).get(nombre, ""), jefe,
                                          solo_copia=campo == "copia", aplica=aplica)
        else:
            try:
                maximo = -1 if campo == "no_tengo" else int(self.var_max.get())
            except (tk.TclError, ValueError):
                return
            nueva = blq.nueva_regla_limite(objeto, nombre, "estrellas" if campo == "no_tengo" else campo, maximo,
                                           jefe, aplica)
        self.reglas = blq.sin_duplicados(self.reglas + [nueva])
        self._refrescar()
        self.lbl_ayuda.configure(text=tr("✓ Agregada: {0}", blq.describir(nueva, con_jefe=False)),
                                 foreground=tema.OK)
        self.combo_nombre.set("")

    # ---- lista
    def _refrescar(self):
        self.tabla.delete(*self.tabla.get_children())
        for i, b in enumerate(self.reglas):
            jefe = str(b.get("jefe") or "TODOS")
            self.tabla.insert("", "end", iid=str(i), tags=() if b.get("activo", True) else ("inactiva",), values=(
                blq.describir(b, con_jefe=False),
                tr("Todos") if jefe == "TODOS" else self.etiqueta_jefe(jefe),
                tr(blq.NOMBRES_APLICA.get(b.get("aplica", blq.APLICA_TODO), "")),
                tr("Sí") if b.get("activo", True) else tr("No")))

    def _quitar(self):
        for iid in sorted(self.tabla.selection(), key=int, reverse=True):
            del self.reglas[int(iid)]
        self._refrescar()

    def _quitar_todas(self):
        if self.reglas and messagebox.askyesno(tr("Bloqueos"), tr("¿Quitar las {0} reglas?", len(self.reglas)),
                                               parent=self):
            self.reglas = []
            self._refrescar()

    def _alternar(self):
        for iid in self.tabla.selection():
            b = self.reglas[int(iid)]
            b["activo"] = not b.get("activo", True)
        sel = self.tabla.selection()
        self._refrescar()
        for iid in sel:
            if self.tabla.exists(iid):
                self.tabla.selection_add(iid)


# ============================================================
# MI ROSTER (lo que tienes; corrige lo que el inventario no sabe)
# ============================================================

class EditorRoster(ttk.Frame):
    """Tabla con tus héroes, colecciones y mascotas; puedes marcar 'lo tengo' y hasta dónde, a mano."""

    COLUMNAS = {"HEROE": ("quality", "sig", "engraving", "muebles"),
                "COLECCION": ("estrellas", "mythic", "level"), "MASCOTA": ()}

    def __init__(self, padre, carpeta, comps, vis):
        super().__init__(padre)
        self.carpeta, self.vis = Path(carpeta), vis
        self.correcciones = rst.cargar_correcciones(carpeta)
        self.perfil = rst.cargar_perfil(carpeta, vis)
        # lo que aparece en cualquier equipo cargado (también de amigos), aunque no esté en tu inventario
        self.vistos = {"HEROE": {}, "COLECCION": {}, "MASCOTA": {}}
        for c in comps:
            for h in c.heroes:
                self.vistos["HEROE"].setdefault(str(h.get("tid")), h.get("name") or "?")
                col = h.get("collection") or {}
                if col.get("tid") is not None:
                    self.vistos["COLECCION"].setdefault(str(col.get("tid")), col.get("name") or "?")
            if (c.mascota or {}).get("tid") is not None:
                self.vistos["MASCOTA"].setdefault(str(c.mascota.get("tid")), c.mascota.get("name") or "?")

        captura = self.perfil.get("captura")
        if self.perfil.get("con_inventario"):
            from navegador.cuenta import hace_cuanto
            texto = tr("Tomado de tu inventario (captura {0}). Lo que no aparece ahí cuenta como que no lo tienes. "
                       "Corrige a mano lo que haya cambiado desde entonces.", hace_cuanto(captura))
            color = "Muted.TLabel"
        else:
            texto = tr("No hay inventario de este servidor: sincroniza 'Mi cuenta' o importa afk-inventory.json. "
                       "Mientras tanto, solo cuenta lo que marques aquí (lo demás se supone que lo tienes).")
            color = "Muted.TLabel"
        ttk.Label(self, text=texto, wraplength=860, justify="left", style=color).pack(anchor="w", pady=(0, 8))

        arriba = ttk.Frame(self)
        arriba.pack(fill="x", pady=(0, 6))
        self.var_tipo = tk.StringVar(value="HEROE")
        for valor, texto in EditorBloqueos.TIPOS:
            ttk.Radiobutton(arriba, text=tr(texto), value=valor, variable=self.var_tipo, style="Toolbutton",
                            command=self._refrescar).pack(side="left", padx=(0, 4))
        ttk.Label(arriba, text="⌕", style="Muted.TLabel").pack(side="left", padx=(16, 4))
        self.var_buscar = tk.StringVar()
        ttk.Entry(arriba, textvariable=self.var_buscar, width=26).pack(side="left")
        self.var_buscar.trace_add("write", lambda *a: self._refrescar())
        self.var_solo_no = tk.BooleanVar(value=False)
        ttk.Checkbutton(arriba, text=tr("Solo lo que no tengo / corregido"), variable=self.var_solo_no,
                        command=self._refrescar).pack(side="left", padx=12)

        marco = ttk.Frame(self)
        marco.pack(fill="both", expand=True)
        self.tabla = ttk.Treeview(marco, columns=("nombre", "tengo", "a", "b", "c", "d", "origen"), show="headings",
                                  height=10)
        for col, ancho in (("nombre", 240), ("tengo", 80), ("a", 120), ("b", 90), ("c", 90), ("d", 90),
                           ("origen", 130)):
            self.tabla.column(col, width=ancho, anchor="w" if col == "nombre" else "center", stretch=col == "nombre")
        self.tabla.tag_configure("no", foreground=tema.ERR)
        self.tabla.tag_configure("manual", foreground=tema.DORADO)
        barra = ttk.Scrollbar(marco, orient="vertical", command=self.tabla.yview)
        self.tabla.configure(yscrollcommand=barra.set)
        self.tabla.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")
        self.tabla.bind("<<TreeviewSelect>>", lambda e: self._al_elegir())

        form = ttk.Frame(self, style="Tarjeta.TFrame", padding=12)
        form.pack(fill="x", pady=(8, 0))
        self.lbl_sel = ttk.Label(form, text=tr("Elige una fila para corregirla"), style="Tarjeta.TLabel",
                                 font=tema.FUENTE_NEGRITA)
        self.lbl_sel.grid(row=0, column=0, columnspan=8, sticky="w", pady=(0, 6))
        self.var_tengo = tk.BooleanVar(value=True)
        ttk.Checkbutton(form, text=tr("Lo tengo"), variable=self.var_tengo, style="Panel.TCheckbutton",
                        command=self._al_marcar_tengo).grid(row=1, column=0, sticky="w", padx=(0, 14))
        self.campos_form = {}
        self.spins = []
        for i in range(4):
            lbl = ttk.Label(form, text="", style="Panel.TLabel")
            lbl.grid(row=1, column=1 + i * 2, sticky="e", padx=(6, 2))
            var = tk.IntVar(value=0)
            sp = ttk.Spinbox(form, from_=0, to=200, width=6, textvariable=var)
            sp.grid(row=1, column=2 + i * 2, sticky="w")
            self.spins.append((lbl, sp, var))
        botones = ttk.Frame(form, style="Panel.TFrame")
        botones.grid(row=2, column=0, columnspan=9, sticky="w", pady=(10, 0))
        ttk.Button(botones, text=tr("Aplicar corrección"), style="Acento.TButton", command=self._aplicar).pack(side="left")
        ttk.Button(botones, text=tr("Volver a lo del inventario"), command=self._deshacer).pack(side="left", padx=8)
        self.lbl_info = ttk.Label(botones, text="", style="PanelMuted.TLabel")
        self.lbl_info.pack(side="left", padx=8)
        self._clave_sel = None
        self._refrescar()

    def _etiquetas(self, tipo):
        return [tr(v) for v in rst.CAMPOS_PERFIL[tipo].values()]

    def _entradas(self, tipo):
        """{clave: datos} = lo del perfil + lo visto en equipos (sin datos = no lo tienes / desconocido)."""
        salida = {k: dict(v) for k, v in self.perfil[tipo].items()}
        for k, nombre in self.vistos[tipo].items():
            if k not in salida:
                salida[k] = {"nombre": nombre, "tengo": not self.perfil.get("con_inventario"), "_visto": True}
        return salida

    def _texto_valor(self, tipo, campo, valor):
        if valor is None:
            return "—"
        if tipo == "HEROE" and campo == "quality" and self.vis.disponible:
            return self.vis.nombre_calidad(valor)
        return str(valor)

    def _refrescar(self):
        tipo = self.var_tipo.get()
        columnas = self.COLUMNAS[tipo]
        titulos = [tr("Nombre"), tr("Lo tengo")] + self._etiquetas(tipo) + [""] * (4 - len(columnas)) + [tr("Origen")]
        for col, titulo in zip(("nombre", "tengo", "a", "b", "c", "d", "origen"), titulos):
            self.tabla.heading(col, text=titulo)
        q = _norm(self.var_buscar.get().strip())
        self.tabla.delete(*self.tabla.get_children())
        entradas = self._entradas(tipo)
        for clave, d in sorted(entradas.items(), key=lambda kv: _norm(kv[1].get("nombre"))):
            if q and q not in _norm(d.get("nombre")):
                continue
            manual = clave in (self.correcciones.get(tipo) or {})
            tengo = d.get("tengo", True)
            if self.var_solo_no.get() and tengo and not manual:
                continue
            valores = [self._texto_valor(tipo, c, d.get(c)) if tengo else "" for c in columnas]
            valores += [""] * (4 - len(valores))
            origen = tr("corregido a mano") if manual else (tr("inventario") if not d.get("_visto") else tr("visto en equipos"))
            self.tabla.insert("", "end", iid=f"{tipo}|{clave}",
                              tags=("manual",) if manual else (() if tengo else ("no",)),
                              values=(d.get("nombre"), tr("Sí") if tengo else tr("No"), *valores, origen))

    def _al_elegir(self):
        sel = self.tabla.selection()
        if not sel:
            return
        tipo, clave = sel[0].split("|", 1)
        d = self._entradas(tipo).get(clave, {})
        self._clave_sel = (tipo, clave)
        self.lbl_sel.configure(text=d.get("nombre", clave))
        self.var_tengo.set(bool(d.get("tengo", True)))
        columnas = self.COLUMNAS[tipo]
        etiquetas = self._etiquetas(tipo)
        for i, (lbl, sp, var) in enumerate(self.spins):
            if i < len(columnas):
                lbl.configure(text=etiquetas[i])
                sp.grid()
                lbl.grid()
                var.set(int(d.get(columnas[i]) or 0))
            else:
                lbl.grid_remove()
                sp.grid_remove()
        self._al_marcar_tengo()
        self.lbl_info.configure(text="")

    def _al_marcar_tengo(self):
        estado = "normal" if self.var_tengo.get() else "disabled"
        for _, sp, _ in self.spins:
            sp.configure(state=estado)

    def _aplicar(self):
        if not self._clave_sel:
            return
        tipo, clave = self._clave_sel
        d = self._entradas(tipo).get(clave, {})
        nuevo = {"nombre": d.get("nombre", clave), "tengo": bool(self.var_tengo.get())}
        if nuevo["tengo"]:
            for (lbl, sp, var), campo in zip(self.spins, self.COLUMNAS[tipo]):
                try:
                    nuevo[campo] = int(var.get())
                except (tk.TclError, ValueError):
                    pass
        self.correcciones.setdefault(tipo, {})[clave] = nuevo
        self._recalcular()
        self.lbl_info.configure(text=tr("✓ Corregido (se guarda al pulsar Guardar)"))

    def _deshacer(self):
        if not self._clave_sel:
            return
        tipo, clave = self._clave_sel
        (self.correcciones.get(tipo) or {}).pop(clave, None)
        self._recalcular()
        self.lbl_info.configure(text=tr("Vuelve a lo del inventario"))

    def _recalcular(self):
        self.perfil = rst.cargar_perfil(self.carpeta, self.vis, correcciones=self.correcciones)
        sel = self.tabla.selection()
        self._refrescar()
        for iid in sel:
            if self.tabla.exists(iid):
                self.tabla.selection_set(iid)
                self.tabla.see(iid)

    def guardar(self):
        rst.guardar_correcciones(self.carpeta, self.correcciones)


# ============================================================
# VENTANA ⚙ CONFIGURAR
# ============================================================

class VentanaConfigurar:
    PESTANAS = (("fuentes", N_("Fuentes")), ("bloqueos", N_("Bloqueos")), ("roster", N_("Mi roster")),
                ("busqueda", N_("Búsqueda")), ("vista", N_("Vista")))

    def __init__(self, opt, pestana="fuentes", objeto=None, nombre=None):
        self.opt = opt
        self.top = tk.Toplevel(opt.top)
        self.top.title(tr("Configurar optimización"))
        self.top.geometry("1000x760")
        self.top.minsize(860, 600)
        self.top.transient(opt.top.winfo_toplevel())
        self.top.configure(background=tema.FONDO)

        ttk.Label(self.top, text=tr("Configurar optimización"), style="Seccion.TLabel").pack(
            anchor="w", padx=18, pady=(14, 6))
        self.nb = ttk.Notebook(self.top)
        self.nb.pack(fill="both", expand=True, padx=14)
        self.tabs = {}
        for clave, titulo in self.PESTANAS:
            tab = ttk.Frame(self.nb, padding=14)
            self.nb.add(tab, text=tr(titulo))
            self.tabs[clave] = tab

        comps = list(opt.comps)
        for cargados in opt._fuentes.values():
            comps.extend(cargados)
        self._crear_fuentes(self.tabs["fuentes"])
        bosses = sorted({c.boss_id for c in opt.comps}, key=lambda b: (0, int(b)) if str(b).isdigit() else (1, str(b)))
        self.editor = EditorBloqueos(self.tabs["bloqueos"], opt.reglas, comps, bosses, opt._etiqueta_jefe, opt.vis,
                                     objeto=objeto, nombre=nombre)
        self.editor.pack(fill="both", expand=True)
        self.roster = EditorRoster(self.tabs["roster"], opt.carpeta, comps, opt.vis)
        self.roster.pack(fill="both", expand=True)
        self._crear_busqueda(self.tabs["busqueda"])
        self._crear_vista(self.tabs["vista"])
        self.nb.select(self.tabs.get(pestana, self.tabs["fuentes"]))

        pie = ttk.Frame(self.top, padding=(14, 10))
        pie.pack(fill="x")
        ttk.Button(pie, text=tr("Cancelar"), command=self.top.destroy).pack(side="right")
        ttk.Button(pie, text=tr("Guardar"), command=lambda: self._guardar(False)).pack(side="right", padx=8)
        ttk.Button(pie, text=tr("Guardar y ▶ Optimizar"), style="Acento.TButton",
                   command=lambda: self._guardar(True)).pack(side="right")
        self.top.grab_set()

    # ---- Fuentes
    def _crear_fuentes(self, tab):
        opt = self.opt
        fila = ttk.Frame(tab)
        fila.pack(fill="x", pady=(0, 10))
        ttk.Label(fila, text=tr("Optimizar con:")).pack(side="left")
        self.combo_fuente = ttk.Combobox(fila, state="readonly", width=46,
                                         values=[e for e, _ in opt._opciones_fuente])
        self.combo_fuente.current(max(0, opt.combo_opt_fuente.current()))
        self.combo_fuente.pack(side="left", padx=8)
        ttk.Label(tab, wraplength=900, justify="left", style="Muted.TLabel", text=tr(
            "Tu selección personalizada: marca de qué carpetas puede sacar equipos (servidores de cualquiera de tus "
            "cuentas y amigos). Cada jefe se toma de cualquiera de ellas, sin repetir héroes. Al marcar algo aquí, "
            "'Optimizar con' pasa a 'Tu selección'.")).pack(anchor="w", pady=(0, 6))
        botones = ttk.Frame(tab)
        botones.pack(fill="x", pady=(0, 8))
        for texto, cual in ((N_("Todo"), "todo"), (N_("Nada"), "nada"), (N_("Solo este servidor"), "actual"),
                            (N_("Este servidor + amigos"), "actual+amigos"), (N_("Solo amigos"), "amigos")):
            ttk.Button(botones, text=tr(texto), command=lambda c=cual: self._marcar(c)).pack(side="left", padx=(0, 4))

        from aplicacion.ventana_optimizador import MarcoDesplazable, listar_servidores
        marco = MarcoDesplazable(tab)
        marco.pack(fill="both", expand=True)
        interior = marco.interior
        etiquetas = {str(c): e for e, c in listar_servidores(opt.base_dir)}
        elegidas = {str(c) for c in opt._seleccion()}
        actual = str(Path(opt.carpeta))
        self.variables = []
        grupos = {}
        for carpeta in opt._todas_las_carpetas():
            grupos.setdefault(carpeta.parent, []).append(carpeta)
        cuentas = sorted((g for g in grupos if g.name != CARPETA_AMIGOS),
                         key=lambda g: str((_leer_json(g / "account.json") or {}).get("fetchedAt") or ""), reverse=True)
        orden = cuentas + [g for g in grupos if g.name == CARPETA_AMIGOS]
        if not orden:
            ttk.Label(interior, text=tr("No hay carpetas con runs."), style="Muted.TLabel").pack(anchor="w")
        for grupo in orden:
            if grupo.name == CARPETA_AMIGOS:
                titulo = tr("AMIGOS")
            else:
                ficha = _leer_json(grupo / "account.json") or {}
                titulo = tr("CUENTA DEL SITIO · actualizada {0}", str(ficha.get("fetchedAt") or "?")[:10])
            caja = ttk.Frame(interior, style="Tarjeta.TFrame", padding=(12, 8))
            caja.pack(fill="x", pady=4)
            ttk.Label(caja, text=titulo, style="PanelMuted.TLabel").pack(anchor="w", pady=(0, 4))
            for carpeta in sorted(grupos[grupo], key=lambda c: (len(c.name), c.name)):
                var = tk.BooleanVar(value=str(carpeta) in elegidas)
                texto = etiquetas.get(str(carpeta), carpeta.name)
                if str(carpeta) == actual:
                    texto += "   " + tr("← abierto ahora")
                ttk.Checkbutton(caja, text=texto, variable=var, style="Tarjeta.TCheckbutton",
                                command=self._seleccion_cambiada).pack(anchor="w", pady=1)
                self.variables.append((carpeta, var))
        self._seleccion_tocada = False

    def _seleccion_cambiada(self):
        self._seleccion_tocada = True
        n = len(self.opt._opciones_fuente) - 1   # 'Tu selección' es la última opción
        self.combo_fuente.current(n)

    def _marcar(self, cual):
        actual = Path(self.opt.carpeta)
        for carpeta, var in self.variables:
            amigo = carpeta.parent.name == CARPETA_AMIGOS
            var.set({"todo": True, "nada": False, "actual": carpeta == actual,
                     "actual+amigos": carpeta == actual or amigo, "amigos": amigo}[cual])
        self._seleccion_cambiada()

    # ---- Búsqueda
    def _crear_busqueda(self, tab):
        opt = self.opt
        self.vars = {}

        def casilla(padre, clave, var, texto, ayuda=None):
            v = tk.BooleanVar(value=var.get())
            self.vars[clave] = (var, v)
            ttk.Checkbutton(padre, text=tr(texto), variable=v, style="Tarjeta.TCheckbutton").pack(anchor="w", pady=(4, 0))
            if ayuda:
                ttk.Label(padre, text=tr(ayuda), style="PanelMuted.TLabel", wraplength=820, justify="left").pack(
                    anchor="w", padx=(26, 0))

        caja = ttk.Frame(tab, style="Tarjeta.TFrame", padding=14)
        caja.pack(fill="x")
        ttk.Label(caja, text=tr("QUÉ RUNS Y EQUIPOS SE USAN"), style="PanelMuted.TLabel").pack(anchor="w")
        casilla(caja, "completas", opt.var_completas, N_("Solo runs completas (6/6)"),
                N_("Desmárcalo si quieres contar equipos de runs donde no llegaste al final."))
        casilla(caja, "mascota", opt.var_mascota, N_("No repetir mascotas entre jefes"))
        casilla(caja, "temp", opt.var_excluir_temp, N_("Excluir equipos con héroes prestados / de prueba"))
        casilla(caja, "fuera", opt.var_excluir_fuera, N_("Excluir equipos con héroes que ya no están en tu roster"))

        caja = ttk.Frame(tab, style="Tarjeta.TFrame", padding=14)
        caja.pack(fill="x", pady=(10, 0))
        ttk.Label(caja, text=tr("EQUIPOS DE AMIGOS Y DE TUS OTROS SERVIDORES"), style="PanelMuted.TLabel").pack(anchor="w")
        ttk.Label(caja, text=tr("Se comparan con 'Mi roster' para saber si puedes copiarlos."),
                  style="PanelMuted.TLabel").pack(anchor="w", pady=(2, 4))
        self.var_roster = tk.StringVar(value=opt.var_modo_roster.get())
        for valor, texto in (("todos", N_("Usar todos")),
                             ("casi", N_("Solo los que puedes armar o casi (✅ 🟡): tienes los héroes")),
                             ("ok", N_("Solo los que puedes armar tal cual (✅)"))):
            ttk.Radiobutton(caja, text=tr(texto), value=valor, variable=self.var_roster,
                            style="Panel.TRadiobutton").pack(anchor="w", pady=1)

        avanzado = ttk.Frame(tab, style="Tarjeta.TFrame", padding=14)
        avanzado.pack(fill="x", pady=(10, 0))
        ttk.Label(avanzado, text=tr("AVANZADO"), style="PanelMuted.TLabel").grid(row=0, column=0, columnspan=4, sticky="w")
        self.var_limite = tk.IntVar(value=opt.var_limite.get())
        self.var_tiempo = tk.IntVar(value=opt.var_tiempo.get())
        ttk.Label(avanzado, text=tr("Equipos por jefe a considerar (0 = todos):"), style="Panel.TLabel").grid(
            row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Spinbox(avanzado, from_=0, to=9999, width=7, textvariable=self.var_limite).grid(
            row=1, column=1, sticky="w", padx=8, pady=(6, 0))
        ttk.Label(avanzado, text=tr("Tiempo máximo de búsqueda (s):"), style="Panel.TLabel").grid(
            row=2, column=0, sticky="w", pady=(6, 0))
        ttk.Spinbox(avanzado, from_=1, to=3600, width=7, textvariable=self.var_tiempo).grid(
            row=2, column=1, sticky="w", padx=8, pady=(6, 0))

    # ---- Vista
    def _crear_vista(self, tab):
        from aplicacion.ventana_optimizador import TAMANOS
        caja = ttk.Frame(tab, style="Tarjeta.TFrame", padding=14)
        caja.pack(fill="x")
        ttk.Label(caja, text=tr("TAMAÑO DE LOS RETRATOS"), style="PanelMuted.TLabel").pack(anchor="w", pady=(0, 6))
        self.var_tamano = tk.StringVar(value=self.opt._tamano)
        for nombre in TAMANOS:
            ttk.Radiobutton(caja, text=tr(nombre), value=nombre, variable=self.var_tamano,
                            style="Panel.TRadiobutton").pack(anchor="w", pady=1)

    # ---- guardar
    def _guardar(self, optimizar):
        opt = self.opt
        from aplicacion.ventana_optimizador import guardar_preferencia
        if self._seleccion_tocada:
            elegidas = [opt._relativa(c) for c, v in self.variables if v.get()]
            guardar_preferencia(opt.base_dir, "seleccion_fuentes", elegidas)
            opt._preparar_fuentes()
        for clave, (destino, v) in self.vars.items():
            destino.set(v.get())
        for destino, origen in ((opt.var_limite, self.var_limite), (opt.var_tiempo, self.var_tiempo)):
            try:
                destino.set(int(origen.get()))
            except (tk.TclError, ValueError):
                pass
        opt.var_modo_roster.set(self.var_roster.get())
        opt.guardar_opciones_busqueda()
        self.roster.guardar()
        opt.recargar_perfil()
        opt.guardar_reglas(self.editor.reglas, aviso=not optimizar)
        i = self.combo_fuente.current()
        if 0 <= i < len(opt._opciones_fuente):
            opt._clave_opt = opt._opciones_fuente[i][1]
            opt.combo_opt_fuente.current(i)
        if self.var_tamano.get() != opt._tamano:
            opt.cambiar_tamano(self.var_tamano.get())
        self.top.grab_release()
        self.top.destroy()
        if optimizar:
            opt.ejecutar_optimizacion()


# ============================================================
# ROTACIÓN DE LA SEMANA
# ============================================================

class VentanaRotacion:
    """Los 6 jefes de la semana (por ID), con imagen; 'Más reciente' toma la de tu última run."""

    def __init__(self, opt):
        self.opt = opt
        self.top = tk.Toplevel(opt.top)
        self.top.title(tr("Rotación de la semana"))
        self.top.transient(opt.top.winfo_toplevel())
        self.top.configure(background=tema.FONDO)
        self.top.resizable(False, False)
        marco = ttk.Frame(self.top, padding=18)
        marco.pack(fill="both", expand=True)
        ttk.Label(marco, text=tr("Rotación de la semana"), style="Seccion.TLabel").grid(row=0, column=0, columnspan=6, sticky="w")
        ttk.Label(marco, style="Muted.TLabel", text=tr(
            "Elige el jefe de cada posición. 'Más reciente' la toma de tu última run, ordenada por ID.")).grid(
            row=1, column=0, columnspan=6, sticky="w", pady=(2, 12))
        self.combos, self.imgs = [], []
        valores = [opt._etiqueta_jefe(b) for b in opt._bosses]
        for i, boss in enumerate(opt._rotacion_semanal()):
            casilla = ttk.Frame(marco)
            casilla.grid(row=2, column=i, padx=6)
            img = ttk.Label(casilla, image=opt.imagenes.obtener(None, 72))
            img.pack()
            ttk.Label(casilla, text=f"{i + 1}", style="Pequeno.TLabel").pack()
            c = ttk.Combobox(casilla, width=18, values=valores)
            c.set(opt._etiqueta_jefe(boss) if boss else "")
            c.pack(pady=(2, 0))
            c.bind("<<ComboboxSelected>>", lambda e: self._pintar())
            c.bind("<KeyRelease>", lambda e: self._pintar())
            self.combos.append(c)
            self.imgs.append(img)
        pie = ttk.Frame(marco)
        pie.grid(row=3, column=0, columnspan=6, sticky="ew", pady=(16, 0))
        ttk.Button(pie, text=tr("Más reciente"), command=self._reciente).pack(side="left")
        ttk.Button(pie, text=tr("Cancelar"), command=self.top.destroy).pack(side="right")
        ttk.Button(pie, text=tr("Aceptar"), style="Acento.TButton", command=self._aceptar).pack(side="right", padx=8)
        self._pintar()
        self.top.grab_set()

    def _ids(self):
        return [self.opt._id_de_etiqueta(c.get()) if c.get().strip() else "" for c in self.combos]

    def _pintar(self):
        for boss, img in zip(self._ids(), self.imgs):
            url = self.opt.vis.jefe(boss)[1] if boss and self.opt.vis.disponible else None
            img.configure(image=self.opt.imagenes.obtener(url, 72))

    def _reciente(self):
        for c, boss in zip(self.combos, self.opt.rotacion_reciente() + [""] * 6):
            c.set(self.opt._etiqueta_jefe(boss) if boss else "")
        self._pintar()

    def _aceptar(self):
        self.opt.poner_rotacion(self._ids())
        self.top.grab_release()
        self.top.destroy()
