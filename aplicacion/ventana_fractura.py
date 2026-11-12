# aplicacion/ventana_fractura.py
"""
Fractura temporal: planificador de recursos por piso, cofres de elección y tiendas de medallas.
Todo se guarda solo (por cuenta/servidor) en fractura_temporal.json.
"""
import tkinter as tk
from pathlib import Path
from tkinter import ttk, filedialog, messagebox

from navegador.cuenta import cargar_cuenta_actual, hace_cuanto
from navegador.fractura import (cargar_base, guardar_base, cargar_estado, guardar_estado, importar_excel, calcular,
                                inventario, pisos_validos, vinculos, objetos_bolsa, proximo_viernes)
from aplicacion.ventana_cuenta_actual import listar_personajes
from aplicacion.vistas_fractura import Fichas, VistaPisos, VistaCofres, VistaResumen
from aplicacion import tema
from idiomas import tr, N_
from navegador.rutas import carpeta_capturas

EXCEL_POR_DEFECTO = Path(__file__).resolve().parent.parent.parent / "Fractura temporal"


def _fmt(n):
    if not n:
        return "—"
    return f"{n:,}".replace(",", ".")


def _desplazable(padre):
    """Frame con barra de desplazamiento vertical; devuelve el frame interior."""
    lienzo = tk.Canvas(padre, highlightthickness=0, background=tema.FONDO)
    sb = ttk.Scrollbar(padre, orient="vertical", command=lienzo.yview)
    lienzo.configure(yscrollcommand=sb.set)
    lienzo.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")
    interior = ttk.Frame(lienzo)
    ventana = lienzo.create_window((0, 0), window=interior, anchor="nw")
    interior.bind("<Configure>", lambda e: lienzo.configure(scrollregion=lienzo.bbox("all")))
    lienzo.bind("<Configure>", lambda e: lienzo.itemconfigure(ventana, width=e.width))

    def rueda(e):
        lienzo.yview_scroll(int(-e.delta / 120) * 3, "units")
    lienzo.bind("<Enter>", lambda e: lienzo.bind_all("<MouseWheel>", rueda))
    lienzo.bind("<Leave>", lambda e: lienzo.unbind_all("<MouseWheel>"))
    return interior


class VentanaFractura:
    def __init__(self, parent, perfil_path):
        self.base_dir = Path(perfil_path).parent
        self.personajes = listar_personajes(self.base_dir)
        self.carpeta = None
        self.base = cargar_base(self.base_dir)
        self.estado = {"piso": 0, "cofres": {}, "compras": {}}
        self.inv = {}
        self._guardado_pendiente = None
        self._cargando = False
        self.cuenta = None
        self.fichas = Fichas(self)

        self.top = tema.ventana(parent)
        self.top.title(tr("Fractura temporal"))
        self.top.geometry("1280x860")
        self.top.minsize(1000, 640)
        self.top.protocol("WM_DELETE_WINDOW", self._cerrar)

        if not self.base:
            self._importar_inicial()
        self._crear()
        if self.personajes:
            self.combo_personaje.current(0)
        self._cambiar_personaje()

    # ---------------- datos ----------------

    def _excel_por_defecto(self):
        archivos = sorted(EXCEL_POR_DEFECTO.glob("fractura_temporal*.xlsx"))
        return archivos[-1] if archivos else None

    def _importar_inicial(self):
        excel = self._excel_por_defecto()
        if excel:
            try:
                self.base, self._estado_excel = importar_excel(excel)
                guardar_base(self.base_dir, self.base)
                return
            except Exception as error:
                messagebox.showwarning(tr("Fractura temporal"), tr("No se pudo leer {0}: {1}", excel.name, error),
                                       parent=self.top)
        self.base = {"pisos": [], "cofres": {}, "tiendas": []}

    def _carpeta_estado(self):
        return self.carpeta or (self.base_dir / "cuentas" / "_sin_cuenta")

    def _cambiar_personaje(self):
        self._guardar_ya()
        i = self.combo_personaje.current() if self.personajes else -1
        self.carpeta = self.personajes[i][1] if i >= 0 else None
        carpeta = self._carpeta_estado()
        if (carpeta / "fractura_temporal.json").exists():
            self.estado = cargar_estado(carpeta)
            self.lbl_origen.configure(text="")
        elif getattr(self, "_estado_excel", None):
            # primera vez: tu avance sale de la planilla
            self.estado = self._estado_excel
            self._estado_excel = None
            self.lbl_origen.configure(text=tr("Avance importado de tu planilla de Excel."))
            self._programar_guardado()
        else:
            self.estado = {"piso": 0, "cofres": {}, "compras": {}}
            self.lbl_origen.configure(text="")
        self.cuenta = cargar_cuenta_actual(self.carpeta) if self.carpeta else None
        self._actualizar_bolsa()
        self._construir_pestanas()
        self._recalcular()

    def importar(self):
        excel = filedialog.askopenfilename(
            parent=self.top, title=tr("Planilla de la Fractura temporal"),
            initialdir=str(EXCEL_POR_DEFECTO if EXCEL_POR_DEFECTO.exists() else self.base_dir),
            filetypes=[("Excel", "*.xlsx")])
        if not excel:
            return
        try:
            base, estado = importar_excel(excel)
        except Exception as error:
            messagebox.showerror(tr("Fractura temporal"), tr("No se pudo leer la planilla: {0}", error), parent=self.top)
            return
        self.base = base
        guardar_base(self.base_dir, base)
        if messagebox.askyesno(tr("Fractura temporal"),
                               tr("Recompensas, cofres y tiendas actualizados.\n\n"
                                  "¿Reemplazar también tu avance (piso, cofres elegidos y compras) por el de la planilla?"),
                               parent=self.top):
            self.estado = estado
            self._programar_guardado()
        self._construir_pestanas()
        self._recalcular()

    def _programar_guardado(self):
        if self._guardado_pendiente:
            self.top.after_cancel(self._guardado_pendiente)
        self._guardado_pendiente = self.top.after(600, self._guardar_ya)

    def _guardar_ya(self):
        if self._guardado_pendiente:
            try:
                self.top.after_cancel(self._guardado_pendiente)
            except tk.TclError:
                pass
            self._guardado_pendiente = None
            guardar_estado(self._carpeta_estado(), self.estado)

    def _cerrar(self):
        self._guardar_ya()
        self.top.destroy()

    # ---------------- interfaz ----------------

    def _crear(self):
        arriba = ttk.Frame(self.top)
        arriba.pack(fill="x", padx=12, pady=(12, 4))
        ttk.Label(arriba, text=tr("Fractura temporal"), style="Titulo.TLabel").pack(side="left")
        ttk.Label(arriba, text=tr("   Cuenta:")).pack(side="left")
        self.combo_personaje = ttk.Combobox(arriba, state="readonly", width=30, values=[p[0] for p in self.personajes])
        self.combo_personaje.pack(side="left", padx=4)
        self.combo_personaje.bind("<<ComboboxSelected>>", lambda e: self._cambiar_personaje())
        ttk.Label(arriba, text=tr("   Piso alcanzado:")).pack(side="left")
        self.var_piso = tk.StringVar()
        self.spin_piso = ttk.Spinbox(arriba, textvariable=self.var_piso, width=6, values=[0] + pisos_validos(self.base),
                                     command=self._cambio_piso, font=("Segoe UI Semibold", 12))
        self.spin_piso.pack(side="left", padx=4)
        self.spin_piso.bind("<Return>", lambda e: self._cambio_piso())
        self.spin_piso.bind("<FocusOut>", lambda e: self._cambio_piso())
        ttk.Label(arriba, text=tr("   Medallas en el juego:")).pack(side="left")
        self.var_med_juego = tk.StringVar()
        ent = ttk.Entry(arriba, textvariable=self.var_med_juego, width=7, font=("Segoe UI Semibold", 12),
                        justify="center")
        ent.pack(side="left", padx=4)
        ent.bind("<Return>", lambda e: self._cambio_medallas_juego())
        ent.bind("<FocusOut>", lambda e: self._cambio_medallas_juego())
        ttk.Button(arriba, text=tr("Importar desde Excel…"), command=self.importar).pack(side="right")
        boton_reinicio = ttk.Menubutton(arriba, text=tr("⟲ Reiniciar"))
        menu = tk.Menu(boton_reinicio, tearoff=0)
        menu.add_command(label=tr("Reiniciar compras (hechas y planeadas)…"), command=self.reiniciar_compras)
        menu.add_command(label=tr("Quitar solo las compras planeadas"), command=lambda: self.reiniciar_compras(True))
        menu.add_separator()
        menu.add_command(label=tr("Reiniciar toda la Fractura (nueva temporada)…"), command=self.reiniciar_todo)
        boton_reinicio["menu"] = menu
        boton_reinicio.pack(side="right", padx=6)

        meta = ttk.Frame(self.top)
        meta.pack(fill="x", padx=12, pady=(2, 0))
        self.lbl_meta_titulo = ttk.Label(meta, text="")
        self.lbl_meta_titulo.pack(side="left")
        self.var_meta = tk.StringVar()
        self.spin_meta = ttk.Spinbox(meta, textvariable=self.var_meta, width=6, values=[0] + pisos_validos(self.base),
                                     command=self._cambio_meta, font=("Segoe UI Semibold", 12))
        self.spin_meta.pack(side="left", padx=4)
        self.spin_meta.bind("<Return>", lambda e: self._cambio_meta())
        self.spin_meta.bind("<FocusOut>", lambda e: self._cambio_meta())
        ttk.Button(meta, text=tr("Piso actual + 20"), command=self._meta_mas_20).pack(side="left", padx=4)
        self.lbl_origen = ttk.Label(meta, text="", style="Muted.TLabel")
        self.lbl_origen.pack(side="left", padx=12)

        # Medallas y próximo piso
        franja = ttk.Frame(self.top, style="Panel.TFrame", padding=(12, 8))
        franja.pack(fill="x", padx=12, pady=6)
        self.lbls_medallas = {}
        for clave, titulo in (("ganadas", N_("Medallas ganadas")), ("gastadas", N_("Gastadas")),
                              ("saldo", N_("Saldo actual")), ("por_ganar", N_("Por ganar en pisos")),
                              ("planeadas", N_("Compras planeadas")), ("saldo_final", N_("Saldo al terminar"))):
            caja = ttk.Frame(franja, style="Panel.TFrame")
            caja.pack(side="left", padx=(0, 26))
            ttk.Label(caja, text=tr(titulo), style="Panel.TLabel", foreground=tema.MUTED).pack(anchor="w")
            lbl = ttk.Label(caja, text="—", style="Panel.TLabel", font=("Segoe UI Semibold", 15))
            lbl.pack(anchor="w")
            self.lbls_medallas[clave] = lbl
        self.lbl_meta = ttk.Label(self.top, text="", wraplength=1240, justify="left", foreground=tema.DORADO,
                                  font=("Segoe UI Semibold", 10))
        self.lbl_meta.pack(anchor="w", padx=14)
        self.lbl_siguiente = ttk.Label(self.top, text="", wraplength=1200, justify="left")
        self.lbl_siguiente.pack(anchor="w", padx=14)
        self.lbl_avisos = ttk.Label(self.top, text="", foreground=tema.ERR, wraplength=1200, justify="left")
        self.lbl_avisos.pack(anchor="w", padx=14)

        self.cuaderno = ttk.Notebook(self.top)
        self.cuaderno.pack(fill="both", expand=True, padx=12, pady=(6, 12))
        self.tab_resumen = ttk.Frame(self.cuaderno, padding=6)
        self.tab_cofres = ttk.Frame(self.cuaderno, padding=6)
        self.tab_tienda = ttk.Frame(self.cuaderno, padding=6)
        self.tab_pisos = ttk.Frame(self.cuaderno, padding=6)
        for tab, texto in ((self.tab_resumen, N_("Resumen por recurso")), (self.tab_cofres, N_("Cofres de elección")),
                           (self.tab_tienda, N_("Tiendas de medallas")), (self.tab_pisos, N_("Recompensas por piso"))):
            self.cuaderno.add(tab, text=tr(texto))
        self._crear_resumen()
        self._crear_pisos()
        self.cont_cofres = None
        self.cont_tienda = None

    def _crear_resumen(self):
        barra = ttk.Frame(self.tab_resumen)
        barra.pack(fill="x", pady=(0, 6))
        self.var_solo_clave = tk.BooleanVar(value=False)
        ttk.Checkbutton(barra, text=tr("Solo recursos de tiendas y cofres"), variable=self.var_solo_clave,
                        command=lambda: (self._llenar_resumen(), self.vista_res.dibujar())).pack(side="left")
        ttk.Button(barra, text=tr("🔗 Vincular con la bolsa…"), command=self._vincular_seleccion).pack(side="left", padx=8)
        self.lbl_bolsa = ttk.Label(barra, style="Muted.TLabel", text="")
        self.lbl_bolsa.pack(side="left", padx=8)
        self.vista_resumen = tk.StringVar(value="visual")
        self._selector_vista(barra, self.vista_resumen, self._cambiar_vista_resumen)
        self.marco_res_visual = ttk.Frame(self.tab_resumen)
        self.vista_res = VistaResumen(self.marco_res_visual, self, self.fichas)
        self.vista_res.pack(fill="both", expand=True)
        self.marco_res_tabla = ttk.Frame(self.tab_resumen)
        ttk.Label(self.marco_res_tabla, style="Muted.TLabel", text=tr(
            "Tendrás = lo que hay en tu bolsa + lo que falta (pisos que faltan + compras y cofres planeados). "
            "Hasta la meta = lo que dan los pisos entre el actual y la meta. "
            "Clic derecho en un recurso para vincularlo con un objeto de tu bolsa.")).pack(anchor="w", pady=(0, 4))
        cols = (("bolsa", N_("En tu bolsa"), 95), ("meta", N_("Hasta la meta"), 100),
                ("obtenible", N_("Aún obtenible"), 100), ("tendras", N_("Tendrás"), 95),
                ("conseguido", N_("Conseguido"), 95), ("pisos", N_("Pisos (logrado / falta)"), 150),
                ("tienda", N_("Tienda (comprado / planeado / sin planear)"), 250),
                ("cofres", N_("Cofres (elegido / planeado)"), 160))
        marco = ttk.Frame(self.marco_res_tabla)
        marco.pack(fill="both", expand=True)
        self.tabla_resumen = ttk.Treeview(marco, columns=[c[0] for c in cols])
        self.tabla_resumen.heading("#0", text=tr("Recurso"))
        self.tabla_resumen.column("#0", width=200, stretch=False)
        for c, t, w in cols:
            self.tabla_resumen.heading(c, text=tr(t))
            self.tabla_resumen.column(c, width=w, anchor="center", stretch=(c == "tienda"))
        sb = ttk.Scrollbar(marco, orient="vertical", command=self.tabla_resumen.yview)
        self.tabla_resumen.configure(yscrollcommand=sb.set)
        self.tabla_resumen.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tabla_resumen.tag_configure("clave", foreground=tema.DORADO)
        self.tabla_resumen.bind("<Button-3>", self._menu_resumen)
        self.tabla_resumen.bind("<Double-1>", lambda e: self._vincular_seleccion())
        self._cambiar_vista_resumen()

    def _selector_vista(self, barra, var, comando):
        for valor, texto in (("visual", tr("🎮 Visual")), ("tabla", tr("📋 Tabla"))):
            ttk.Radiobutton(barra, text=texto, value=valor, variable=var, style="Toolbutton",
                            command=comando).pack(side="right", padx=1)

    def _alternar(self, var, visual, tabla, vista):
        if var.get() == "visual":
            tabla.pack_forget()
            visual.pack(fill="both", expand=True)
            self.top.after_idle(vista.dibujar)
        else:
            visual.pack_forget()
            tabla.pack(fill="both", expand=True)

    def _cambiar_vista_resumen(self):
        self._alternar(self.vista_resumen, self.marco_res_visual, self.marco_res_tabla, self.vista_res)

    def _cambiar_vista_pisos(self):
        self._alternar(self.vista_pisos_var, self.marco_pisos_visual, self.marco_pisos_tabla, self.vista_pisos)

    def _cambiar_vista_cofres(self):
        self._alternar(self.vista_cofres_var, self.marco_cof_visual, self.marco_cof_tabla, self.vista_cofres)

    def _crear_pisos(self):
        barra = ttk.Frame(self.tab_pisos)
        barra.pack(fill="x", pady=(0, 6))
        ttk.Label(barra, style="Muted.TLabel", text=tr(
            "✓ = obtenido · resaltado = lo que ganarás hasta la meta del viernes · claro = bloqueado")).pack(side="left")
        self.vista_pisos_var = tk.StringVar(value="visual")
        self._selector_vista(barra, self.vista_pisos_var, self._cambiar_vista_pisos)
        self.marco_pisos_visual = ttk.Frame(self.tab_pisos)
        self.vista_pisos = VistaPisos(self.marco_pisos_visual, self, self.fichas)
        self.vista_pisos.pack(fill="both", expand=True)
        self.marco_pisos_tabla = ttk.Frame(self.tab_pisos)
        cols = (("recompensas", N_("Recompensas"), 640), ("medallas", N_("Medallas"), 90),
                ("cofres", N_("Cofres"), 140), ("estado", N_("Estado"), 110))
        marco = ttk.Frame(self.marco_pisos_tabla)
        marco.pack(fill="both", expand=True)
        self.tabla_pisos = ttk.Treeview(marco, columns=[c[0] for c in cols])
        self.tabla_pisos.heading("#0", text=tr("Piso"))
        self.tabla_pisos.column("#0", width=70, anchor="center", stretch=False)
        for c, t, w in cols:
            self.tabla_pisos.heading(c, text=tr(t))
            self.tabla_pisos.column(c, width=w, anchor="w" if c == "recompensas" else "center",
                                    stretch=(c == "recompensas"))
        sb = ttk.Scrollbar(marco, orient="vertical", command=self.tabla_pisos.yview)
        self.tabla_pisos.configure(yscrollcommand=sb.set)
        self.tabla_pisos.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tabla_pisos.tag_configure("logrado", foreground=tema.OK)
        self.tabla_pisos.tag_configure("siguiente", foreground=tema.DORADO)
        self.tabla_pisos.tag_configure("pendiente", foreground=tema.MUTED)
        self.tabla_pisos.bind("<Double-1>", self._elegir_piso)
        self._cambiar_vista_pisos()

    def _spin(self, padre, valor, maximo, al_cambiar):
        var = tk.StringVar(value=str(valor or 0))
        sp = ttk.Spinbox(padre, from_=0, to=max(0, maximo), textvariable=var, width=6, justify="center")
        var.trace_add("write", lambda *a: None if self._cargando else al_cambiar(var))
        sp.variable = var
        return sp

    @staticmethod
    def _entero(var):
        try:
            return max(0, int(float(var.get() or 0)))
        except (ValueError, tk.TclError):
            return 0

    def _construir_pestanas(self):
        """Cofres y tiendas: una fila con campos editables por opción u objeto."""
        self._cargando = True
        for tab in (self.tab_cofres, self.tab_tienda):
            for hijo in tab.winfo_children():
                hijo.destroy()
        self.spin_piso.configure(values=[0] + pisos_validos(self.base))
        self.var_piso.set(str(self.estado.get("piso") or 0))
        mj = self.estado.get("medallas_juego")
        self.var_med_juego.set("" if mj is None else str(mj))
        self.spin_meta.configure(values=[0] + pisos_validos(self.base))
        if not self.estado.get("meta"):
            self.estado["meta"] = min(max(pisos_validos(self.base) or [0]), int(self.estado.get("piso") or 0) + 20)
        self.var_meta.set(str(self.estado.get("meta") or 0))
        self.lbl_meta_titulo.configure(text=tr("🎯 Meta para el viernes {0}:", proximo_viernes().strftime("%d/%m")))

        # ---- cofres: vista como en el juego (por defecto) o tabla
        barra = ttk.Frame(self.tab_cofres)
        barra.pack(fill="x", pady=(0, 6))
        if not hasattr(self, "vista_cofres_var"):
            self.vista_cofres_var = tk.StringVar(value="visual")
        self._selector_vista(barra, self.vista_cofres_var, self._cambiar_vista_cofres)
        self.marco_cof_visual = ttk.Frame(self.tab_cofres)
        self.vista_cofres = VistaCofres(self.marco_cof_visual, self, self.fichas)
        self.vista_cofres.pack(fill="both", expand=True)
        self.marco_cof_tabla = ttk.Frame(self.tab_cofres)
        self._cambiar_vista_cofres()
        self.vars_cofre = {}
        cont = _desplazable(self.marco_cof_tabla)
        ttk.Label(cont, style="Muted.TLabel", text=tr(
            "Cada cofre se abre eligiendo UNA opción. 'Ahora' = cofres que ya tienes y elegiste; "
            "'Planeado' = cómo piensas usar los que te faltan por conseguir.")).pack(anchor="w", pady=(0, 8))
        self.ui_cofres = {}
        for nombre, opciones in self.base.get("cofres", {}).items():
            titulo = ttk.Label(cont, text=f" {nombre}", image=self._icono(nombre, 40), compound="left",
                               font=("Segoe UI Semibold", 11), foreground=tema.DORADO)
            marco = ttk.LabelFrame(cont, labelwidget=titulo, padding=8)
            marco.pack(fill="x", pady=6, padx=2)
            cab = ttk.Label(marco, text="")
            cab.grid(row=0, column=0, columnspan=6, sticky="w", pady=(0, 6))
            for c, t in enumerate((tr("Opción"), tr("Por cofre"), tr("Ahora"), tr("Planeado"), tr("Recibes"))):
                ttk.Label(marco, text=t, foreground=tema.DORADO).grid(row=1, column=c, sticky="w", padx=8)
            filas = {}
            elegidos = (self.estado.setdefault("cofres", {})).setdefault(nombre, {})
            for i, (op, cant) in enumerate(opciones.items(), start=2):
                e = elegidos.get(op) or {}
                ttk.Label(marco, text="  " + op, image=self._icono(op, 30), compound="left").grid(
                    row=i, column=0, sticky="w", padx=8, pady=2)
                ttk.Label(marco, text=_fmt(cant)).grid(row=i, column=1, padx=8)
                s1 = self._spin(marco, e.get("ahora"), 99, lambda v, n=nombre, o=op: self._cambio_cofre(n, o, "ahora", v))
                s1.grid(row=i, column=2, padx=8)
                s2 = self._spin(marco, e.get("planeado"), 99,
                                lambda v, n=nombre, o=op: self._cambio_cofre(n, o, "planeado", v))
                s2.grid(row=i, column=3, padx=8)
                self.vars_cofre[(nombre, op)] = {"ahora": s1.variable, "planeado": s2.variable}
                lbl = ttk.Label(marco, text="")
                lbl.grid(row=i, column=4, sticky="w", padx=8)
                filas[op] = lbl
            # cofres que ya abriste sin saber en qué los gastaste
            pie = ttk.Frame(marco)
            pie.grid(row=len(opciones) + 2, column=0, columnspan=6, sticky="w", pady=(8, 0))
            ttk.Label(pie, text=tr("Ya gastados (no sé en qué):")).pack(side="left", padx=(8, 4))
            gastados = (self.estado.setdefault("cofres_gastados", {})).get(nombre, 0)
            sp = self._spin(pie, gastados, 99, lambda v, n=nombre: self._cambio_gastados(n, v))
            sp.pack(side="left")
            ttk.Button(pie, text=tr("Ya me gasté los que faltan"),
                       command=lambda n=nombre: self._gastar_restantes(n)).pack(side="left", padx=6)
            lbl_bolsa = ttk.Label(pie, text="", style="Muted.TLabel")
            lbl_bolsa.pack(side="left", padx=8)
            btn_bolsa = ttk.Button(pie, text=tr("Usar lo que hay en la bolsa"),
                                   command=lambda n=nombre: self._gastados_desde_bolsa(n))
            ttk.Button(pie, text=tr("🔗 Vincular con la bolsa…"),
                       command=lambda n=nombre: self.vincular(n)).pack(side="right", padx=6)
            self.ui_cofres[nombre] = {"cab": cab, "filas": filas, "var_gastados": sp.variable, "lbl_bolsa": lbl_bolsa,
                                      "btn_bolsa": btn_bolsa}

        # ---- tiendas: vista como en el juego (por defecto) o tabla
        barra = ttk.Frame(self.tab_tienda)
        barra.pack(fill="x", pady=(0, 6))
        if not hasattr(self, "vista_tienda"):
            self.vista_tienda = tk.StringVar(value="juego")
        for valor, texto in (("juego", tr("🛒 Como en el juego")), ("tabla", tr("📋 Tabla"))):
            ttk.Radiobutton(barra, text=texto, value=valor, variable=self.vista_tienda, style="Toolbutton",
                            command=self._cambiar_vista_tienda).pack(side="left", padx=1)
        # qué hacen los botones − / + / Todo de cada casilla
        if not hasattr(self, "modo_tienda"):
            self.modo_tienda = tk.StringVar(value="comprar")
        ttk.Label(barra, text=tr("   Botones:")).pack(side="left")
        for valor, texto in (("comprar", tr("🛒 Comprar")), ("planear", tr("📝 Planear"))):
            ttk.Radiobutton(barra, text=texto, value=valor, variable=self.modo_tienda, style="Toolbutton",
                            command=lambda: self.tienda_visual.dibujar()).pack(side="left", padx=1)
        self.lbl_info_tienda = ttk.Label(barra, text="", style="Muted.TLabel")
        self.lbl_info_tienda.pack(side="left", padx=12)
        self.marco_tienda_juego = ttk.Frame(self.tab_tienda)
        self.marco_tienda_tabla = ttk.Frame(self.tab_tienda)
        from aplicacion.tienda_fractura import TiendaVisual
        self.tienda_visual = TiendaVisual(self.marco_tienda_juego, self)
        self._cambiar_vista_tienda()
        self.vars_compra = {}
        cont = _desplazable(self.marco_tienda_tabla)
        ttk.Label(cont, style="Muted.TLabel", text=tr(
            "'Compradas' = lo que ya compraste; 'Planeadas' = lo que piensas comprar con las medallas que te faltan. "
            "El costo se descuenta del saldo de medallas de arriba.")).pack(anchor="w", pady=(0, 8))
        self.ui_tiendas = []
        for t in self.base.get("tiendas", []):
            marco = ttk.LabelFrame(cont, text=f" {t['nombre']} ", padding=8)
            marco.pack(fill="x", pady=6, padx=2)
            cab = ttk.Label(marco, text="")
            cab.grid(row=0, column=0, columnspan=8, sticky="w", pady=(0, 6))
            for c, txt in enumerate((tr("Objeto"), tr("Precio"), tr("Máximo"), tr("Por compra"), tr("Compradas"),
                                     tr("Planeadas"), tr("Costo"), tr("Recibes"))):
                ttk.Label(marco, text=txt, foreground=tema.DORADO).grid(row=1, column=c, sticky="w", padx=8)
            filas = []
            for i, o in enumerate(t["objetos"]):
                clave = f"{t['nombre']}|{i}"
                c = (self.estado.setdefault("compras", {})).get(clave) or {}
                r = i + 2
                ttk.Label(marco, text=o["objeto"]).grid(row=r, column=0, sticky="w", padx=8, pady=2)
                ttk.Label(marco, text=_fmt(o["precio"])).grid(row=r, column=1, padx=8)
                ttk.Label(marco, text=str(o["maximo"])).grid(row=r, column=2, padx=8)
                ttk.Label(marco, text=f"×{o['unidades']}").grid(row=r, column=3, padx=8)
                s_h = self._spin(marco, c.get("hechas"), o["maximo"],
                                 lambda v, k=clave: self._cambio_compra(k, "hechas", v))
                s_h.grid(row=r, column=4, padx=8)
                s_p = self._spin(marco, c.get("planeadas"), o["maximo"],
                                 lambda v, k=clave: self._cambio_compra(k, "planeadas", v))
                s_p.grid(row=r, column=5, padx=8)
                self.vars_compra[clave] = {"hechas": s_h.variable, "planeadas": s_p.variable}
                costo = ttk.Label(marco, text="")
                costo.grid(row=r, column=6, padx=8)
                recibe = ttk.Label(marco, text="")
                recibe.grid(row=r, column=7, sticky="w", padx=8)
                filas.append((clave, o, costo, recibe))
            self.ui_tiendas.append({"tienda": t, "cab": cab, "filas": filas})
        self._cargando = False

    # ---------------- cambios ----------------

    def _cambio_piso(self):
        try:
            piso = max(0, int(float(self.var_piso.get() or 0)))
        except ValueError:
            return
        if piso != self.estado.get("piso"):
            self.estado["piso"] = piso
            self._programar_guardado()
            self._recalcular()

    def _cambio_medallas_juego(self):
        texto = self.var_med_juego.get().strip().replace(".", "")
        valor = int(texto) if texto.isdigit() else None
        if valor != self.estado.get("medallas_juego"):
            self.estado["medallas_juego"] = valor
            self._programar_guardado()
            self._recalcular()

    def _elegir_piso(self, _e=None):
        sel = self.tabla_pisos.selection()
        if sel:
            self.var_piso.set(self.tabla_pisos.item(sel[0], "text"))
            self._cambio_piso()

    def cambiar_cofre(self, nombre, opcion, campo, delta):
        """Desde la vista visual: suma/resta cofres elegidos ('ahora') o planeados, sin pasarse de lo disponible."""
        e = self.estado.setdefault("cofres", {}).setdefault(nombre, {}).setdefault(opcion, {})
        actual = int(e.get(campo) or 0)
        info = self.calc["cofres"].get(nombre, {})
        if campo == "ahora":
            tope = actual + max(0, info.get("libres", 0))
        else:
            tope = actual + max(0, info.get("restantes", 0) - info.get("usados_planeados", 0))
        nuevo = max(0, min(tope, actual + delta)) if delta > 0 else max(0, actual + delta)
        if nuevo == actual:
            if delta > 0:
                self.vista_cofres.info.configure(text=tr("No quedan cofres {0} para eso.", nombre))
            return
        e[campo] = nuevo
        variables = getattr(self, "vars_cofre", {}).get((nombre, opcion))
        if variables:
            self._cargando = True
            variables[campo].set(str(nuevo))
            self._cargando = False
        self._programar_guardado()
        self._recalcular()

    def fijar_piso(self, n):
        self.var_piso.set(str(n))
        self._cambio_piso()

    def fijar_meta(self, n):
        self.var_meta.set(str(n))
        self._cambio_meta()

    def _cambio_cofre(self, nombre, opcion, clave, var):
        e = self.estado.setdefault("cofres", {}).setdefault(nombre, {}).setdefault(opcion, {})
        e[clave] = self._entero(var)
        self._programar_guardado()
        self._recalcular()

    def _cambiar_vista_tienda(self):
        if self.vista_tienda.get() == "juego":
            self.marco_tienda_tabla.pack_forget()
            self.marco_tienda_juego.pack(fill="both", expand=True)
        else:
            self.marco_tienda_juego.pack_forget()
            self.marco_tienda_tabla.pack(fill="both", expand=True)

    def cambiar_compra(self, clave, o, dh=0, dp=0):
        """Compras desde la tienda visual: dh = compras hechas, dp = planeadas (se respetan los máximos)."""
        c = self.estado.setdefault("compras", {}).setdefault(clave, {})
        hechas = min(o["maximo"], max(0, int(c.get("hechas") or 0) + dh))
        plan = min(o["maximo"] - hechas, max(0, int(c.get("planeadas") or 0) + dp))
        c["hechas"], c["planeadas"] = hechas, plan
        variables = getattr(self, "vars_compra", {}).get(clave)
        if variables:
            self._cargando = True
            variables["hechas"].set(str(hechas))
            variables["planeadas"].set(str(plan))
            self._cargando = False
        self._programar_guardado()
        self._recalcular()

    def _cambio_compra(self, clave, campo, var):
        self.estado.setdefault("compras", {}).setdefault(clave, {})[campo] = self._entero(var)
        self._programar_guardado()
        self._recalcular()

    # ---------------- meta del viernes ----------------

    def _cambio_meta(self):
        try:
            meta = max(0, int(float(self.var_meta.get() or 0)))
        except ValueError:
            return
        if meta != self.estado.get("meta"):
            self.estado["meta"] = meta
            self._programar_guardado()
            self._recalcular()

    def _meta_mas_20(self):
        tope = max(pisos_validos(self.base) or [0])
        self.var_meta.set(str(min(tope, int(self.estado.get("piso") or 0) + 20)))
        self._cambio_meta()

    def _pintar_meta(self):
        meta = self.calc.get("meta")
        if not meta:
            self.lbl_meta.configure(text=tr("Elige una meta mayor que tu piso actual para ver lo que ganarás."))
            return
        rec = dict(meta["recompensas"])
        partes = []
        if rec.get("Medallas"):
            partes.append(tr("{0} medallas", _fmt(rec.pop("Medallas"))))
        for k in ("Cofre 1", "Cofre 2", "Cofre 3"):
            if rec.get(k):
                partes.append(f"{k} ×{rec.pop(k)}")
        partes += [f"{k} ×{_fmt(v)}" for k, v in rec.items()]
        self.lbl_meta.configure(text=tr("Del piso {0} al {1} ({2} pisos) ganarás: {3}", meta["desde"], meta["piso"],
                                        meta["piso"] - meta["desde"], ", ".join(partes)))

    # ---------------- reinicios ----------------

    def reiniciar_compras(self, solo_planeadas=False):
        if not solo_planeadas and not messagebox.askyesno(
                tr("Fractura temporal"), tr("¿Borrar todas las compras (hechas y planeadas) de esta cuenta?"),
                parent=self.top):
            return
        if solo_planeadas:
            for c in (self.estado.get("compras") or {}).values():
                c["planeadas"] = 0
        else:
            self.estado["compras"] = {}
        self._programar_guardado()
        self._construir_pestanas()
        self._recalcular()

    def reiniciar_todo(self):
        from tkinter import simpledialog
        piso = simpledialog.askinteger(
            tr("Nueva temporada"), tr("Se borran compras, cofres elegidos y gastados.\n\n¿En qué piso estás ahora?"),
            parent=self.top, minvalue=0, maxvalue=max(pisos_validos(self.base) or [0]), initialvalue=0)
        if piso is None:
            return
        tope = max(pisos_validos(self.base) or [0])
        self.estado = {"piso": piso, "meta": min(tope, piso + 20), "cofres": {}, "compras": {},
                       "cofres_gastados": {}, "medallas_juego": None}
        self._programar_guardado()
        self._construir_pestanas()
        self._recalcular()

    # ---------------- bolsa (inventario del último fetch) ----------------

    def _actualizar_bolsa(self):
        self.inv = inventario(self.cuenta, self.base)
        # nueva caché de íconos (los vínculos pueden haber cambiado); las imágenes que ya están en pantalla
        # se conservan para que Tk no las pierda
        self.__dict__.setdefault("_iconos_en_uso", []).extend(getattr(self, "_iconos", {}).values())
        self._iconos = {}
        if getattr(self, "fichas", None):
            self.fichas.limpiar()
        if hasattr(self, "lbl_bolsa"):
            cuando = (self.cuenta or {}).get("capturedAt")
            self.lbl_bolsa.configure(text=tr("Bolsa del último fetch: {0}", hace_cuanto(cuando)) if cuando
                                     else tr("Sin datos de la bolsa: haz fetch y sincroniza en 'Mi cuenta'."))

    def _menu_resumen(self, e):
        fila = self.tabla_resumen.identify_row(e.y)
        if not fila:
            return
        self.tabla_resumen.selection_set(fila)
        m = tk.Menu(self.top, tearoff=0)
        m.add_command(label=tr("🔗 Vincular «{0}» con la bolsa…", fila), command=lambda: self.vincular(fila))
        if fila in vinculos(self.base):
            m.add_command(label=tr("Quitar vínculo"), command=lambda: self._guardar_vinculo(fila, "-"))
        m.tk_popup(e.x_root, e.y_root)

    def _vincular_seleccion(self):
        sel = self.tabla_resumen.selection()
        if sel:
            self.vincular(sel[0])
        else:
            messagebox.showinfo(tr("Fractura temporal"), tr("Elige primero un recurso de la tabla."), parent=self.top)

    def _guardar_vinculo(self, recurso, ident):
        self.base.setdefault("bolsa", {})[recurso] = ident
        guardar_base(self.base_dir, self.base)
        self._actualizar_bolsa()
        self._recalcular()

    def vincular(self, recurso):
        """Elegir qué objeto de la bolsa corresponde a un recurso (o a un cofre) de la Fractura."""
        objetos = objetos_bolsa(self.cuenta)
        if not objetos:
            messagebox.showinfo(tr("Fractura temporal"),
                                tr("No hay datos de tu bolsa: haz fetch y sincroniza en 'Mi cuenta'."), parent=self.top)
            return
        actual = vinculos(self.base).get(recurso)
        d = tk.Toplevel(self.top)
        d.title(tr("Vincular «{0}» con la bolsa", recurso))
        d.geometry("560x560")
        d.transient(self.top)
        ttk.Label(d, wraplength=520, justify="left", text=tr(
            "Busca el objeto de tu bolsa que corresponde a «{0}». Los que salen como 'Item 100000xx' son monedas "
            "sin nombre: guíate por la cantidad que ves en el juego.", recurso)).pack(anchor="w", padx=10, pady=8)
        var = tk.StringVar()
        ttk.Entry(d, textvariable=var).pack(fill="x", padx=10)
        arbol = ttk.Treeview(d, columns=("cant",), height=16)
        arbol.heading("#0", text=tr("Objeto"))
        arbol.heading("cant", text=tr("Cantidad"))
        arbol.column("cant", width=110, anchor="e")
        arbol.pack(fill="both", expand=True, padx=10, pady=8)

        def llenar(*_):
            arbol.delete(*arbol.get_children())
            filtro = var.get().strip().lower()
            for ident, nombre, cant in objetos:
                if filtro and filtro not in nombre.lower() and filtro not in str(cant) and filtro not in ident:
                    continue
                arbol.insert("", "end", iid=ident, text=f"{nombre}  (id {ident})", values=(_fmt(cant) or "0",))
            if actual and arbol.exists(actual):
                arbol.selection_set(actual)
                arbol.see(actual)
        var.trace_add("write", llenar)
        llenar()

        def aceptar():
            sel = arbol.selection()
            if sel:
                self._guardar_vinculo(recurso, sel[0])
                d.destroy()
        arbol.bind("<Double-1>", lambda e: aceptar())
        botones = ttk.Frame(d)
        botones.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Button(botones, text=tr("Vincular"), style="Acento.TButton", command=aceptar).pack(side="right")
        ttk.Button(botones, text=tr("Quitar vínculo"),
                   command=lambda: (self._guardar_vinculo(recurso, "-"), d.destroy())).pack(side="left")

    def _icono(self, nombre, tam):
        """Ícono de un recurso: el del objeto vinculado en la bolsa (ya descargado) o el recorte guardado."""
        cache = self.__dict__.setdefault("_iconos", {})
        if (nombre, tam) in cache:
            return cache[(nombre, tam)]
        from PIL import Image, ImageTk
        from navegador.fractura import imagen_bolsa
        rutas = []
        url = imagen_bolsa(self.cuenta, self.base, nombre, self.base_dir)
        if url:
            rutas.append(self.base_dir / "assets" / Path(*url.lstrip("/").split("/")))
        rutas.append(carpeta_capturas(self.base_dir) / f"{nombre}.png")
        foto = ""
        for ruta in rutas:
            if ruta.is_file():
                try:
                    im = Image.open(ruta).convert("RGBA")
                    im.thumbnail((tam, tam), Image.LANCZOS)
                    foto = ImageTk.PhotoImage(im)
                    break
                except OSError:
                    continue
        cache[(nombre, tam)] = foto
        return foto

    # ---------------- cofres gastados ----------------

    def _cambio_gastados(self, nombre, var):
        self.estado.setdefault("cofres_gastados", {})[nombre] = self._entero(var)
        self._programar_guardado()
        self._recalcular()

    def _poner_gastados(self, nombre, n):
        self.estado.setdefault("cofres_gastados", {})[nombre] = max(0, n)
        ui = self.ui_cofres.get(nombre)
        if ui:
            self._cargando = True
            ui["var_gastados"].set(str(max(0, n)))
            self._cargando = False
        self._programar_guardado()
        self._recalcular()

    def _gastar_restantes(self, nombre):
        """Todos los cofres conseguidos que no elegiste se marcan como ya gastados."""
        c = self.calc["cofres"][nombre]
        self._poner_gastados(nombre, c["disponibles"] - c["usados_ahora"])

    def _gastados_desde_bolsa(self, nombre):
        """Gastados = conseguidos − elegidos − los que siguen sin abrir en tu bolsa."""
        c = self.calc["cofres"][nombre]
        self._poner_gastados(nombre, c["disponibles"] - c["usados_ahora"] - int(self.inv.get(nombre) or 0))

    # ---------------- cálculo y pintado ----------------

    def _recalcular(self):
        if not self.base or not self.base.get("pisos"):
            self.lbl_siguiente.configure(text=tr("No hay datos de la Fractura: usa 'Importar desde Excel…'."))
            return
        self.calc = calcular(self.base, self.estado, self.inv)
        self._pintar_meta()
        m = self.calc["medallas"]
        for clave, lbl in self.lbls_medallas.items():
            v = m[clave]
            color = tema.ERR if clave.startswith("saldo") and v < 0 else (
                tema.OK if clave.startswith("saldo") else tema.TEXTO)
            lbl.configure(text=f"{v:,}".replace(",", "."), foreground=color)
        sig = self.calc["siguiente"]
        if sig:
            texto = ", ".join(f"{k} ×{_fmt(v)}" for k, v in sig["recompensas"].items())
            self.lbl_siguiente.configure(text=tr("Próximo piso {0}: {1}", sig["piso"], texto))
        else:
            self.lbl_siguiente.configure(text=tr("¡Fractura completa! Ya alcanzaste el último piso."))
        self.lbl_avisos.configure(text="\n".join("⚠ " + a for a in self.calc["avisos"]))
        self._llenar_resumen()
        self._llenar_pisos()
        self._pintar_cofres()
        self._pintar_tiendas()
        if getattr(self, "tienda_visual", None):
            self.tienda_visual.dibujar()
        for vista in ("vista_pisos", "vista_cofres", "vista_res"):
            if getattr(self, vista, None):
                getattr(self, vista).dibujar()

    def _llenar_resumen(self):
        if not getattr(self, "calc", None):
            return
        t = self.tabla_resumen
        t.delete(*t.get_children())
        claves = set()
        for op in self.base.get("cofres", {}).values():
            claves |= set(op)
        for tienda in self.base.get("tiendas", []):
            claves |= {o["objeto"] for o in tienda["objetos"]}
        filas = sorted(self.calc["recursos"].items(), key=lambda kv: (kv[0] not in claves, kv[0].lower()))
        for nombre, x in filas:
            if self.var_solo_clave.get() and nombre not in claves:
                continue
            t.insert("", "end", iid=nombre, text="  " + nombre, tags=("clave",) if nombre in claves else (), values=(
                ("🔗 " + (_fmt(x["bolsa"]) if x["bolsa"] else "0")) if x["bolsa"] is not None
                else ("🔗 ?" if nombre in self.inv else ""),
                ("+" + _fmt(x["hasta_meta"])) if x["hasta_meta"] else "",
                _fmt(x["aun_obtenible"]),
                _fmt(x["tendras"]) if x["tendras"] is not None else "",
                _fmt(x["conseguido"]),
                f"{_fmt(x['pisos_obtenido'])} / {_fmt(x['pisos_faltante'])}",
                f"{_fmt(x['tienda_comprado'])} / {_fmt(x['tienda_planeado'])} / {_fmt(x['tienda_pendiente'])}",
                f"{_fmt(x['cofres_ahora'])} / {_fmt(x['cofres_planeado'])}"))

    def _llenar_pisos(self):
        t = self.tabla_pisos
        t.delete(*t.get_children())
        piso = self.calc["piso"]
        sig = (self.calc["siguiente"] or {}).get("piso")
        iid_sig = None
        for p in self.base["pisos"]:
            rec = dict(p["recompensas"])
            medallas = rec.pop("Medallas", 0)
            cofres = ", ".join(f"{k} ×{rec.pop(k)}" for k in ("Cofre 1", "Cofre 2", "Cofre 3") if k in rec)
            texto = ", ".join(f"{k} ×{_fmt(v)}" for k, v in rec.items())
            if p["piso"] <= piso:
                estado, tag = tr("✓ Logrado"), "logrado"
            elif p["piso"] == sig:
                estado, tag = tr("➜ Siguiente"), "siguiente"
            else:
                estado, tag = "", "pendiente"
            iid = t.insert("", "end", text=str(p["piso"]), values=(texto, _fmt(medallas), cofres, estado), tags=(tag,))
            if p["piso"] == sig:
                iid_sig = iid
        if iid_sig:
            t.see(iid_sig)

    def _pintar_cofres(self):
        for nombre, ui in getattr(self, "ui_cofres", {}).items():
            c = self.calc["cofres"].get(nombre, {})
            libres = c.get("libres", 0)
            ok_a = libres >= 0
            ok_p = c.get("usados_planeados", 0) <= c.get("restantes", 0)
            texto = tr("Conseguidos {0} · por conseguir {1} · elegidos {2} · gastados sin registrar {3} · planeados {4}/{1}",
                       c.get("disponibles", 0), c.get("restantes", 0), c.get("usados_ahora", 0), c.get("gastados", 0),
                       c.get("usados_planeados", 0))
            if libres > 0:
                texto += tr("  ·  ¡{0} sin abrir!", libres)
            if c.get("hasta_meta"):
                texto += tr("  ·  +{0} hasta la meta", c["hasta_meta"])
            ui["cab"].configure(text=texto, foreground=tema.ERR if not (ok_a and ok_p) else (
                tema.WARN if libres > 0 else tema.TEXTO))
            en_bolsa = self.inv.get(nombre)
            if en_bolsa is None:
                ui["lbl_bolsa"].configure(
                    text=tr("No aparece en tu bolsa (puede que no tengas o que el nombre sea otro)") if nombre in self.inv
                    else tr("(vincula el cofre con la bolsa para comparar)"), foreground=tema.MUTED)
                ui["btn_bolsa"].pack_forget()
            else:
                ui["lbl_bolsa"].configure(text=tr("En tu bolsa: {0} sin abrir", en_bolsa),
                                          foreground=tema.OK if en_bolsa == max(0, libres) else tema.WARN)
                ui["btn_bolsa"].pack(side="left", padx=4)
            opciones = self.base["cofres"][nombre]
            elegidos = self.estado.get("cofres", {}).get(nombre, {})
            for op, lbl in ui["filas"].items():
                e = elegidos.get(op) or {}
                a, p = int(e.get("ahora") or 0), int(e.get("planeado") or 0)
                partes = []
                if a:
                    partes.append(tr("{0} ya", _fmt(a * opciones[op])))
                if p:
                    partes.append(tr("{0} planeado", _fmt(p * opciones[op])))
                lbl.configure(text=" + ".join(partes))

    def _pintar_tiendas(self):
        piso = self.calc["piso"]
        for ui in getattr(self, "ui_tiendas", []):
            t = ui["tienda"]
            gasto = plan = 0
            for clave, o, costo, recibe in ui["filas"]:
                c = self.estado.get("compras", {}).get(clave) or {}
                h, p = int(c.get("hechas") or 0), int(c.get("planeadas") or 0)
                gasto += h * o["precio"]
                plan += p * o["precio"]
                costo.configure(text=_fmt((h + p) * o["precio"]),
                                foreground=tema.ERR if h + p > o["maximo"] else tema.TEXTO)
                quedan = o["maximo"] - h - p
                recibe.configure(text=(_fmt((h + p) * o["unidades"]) if h + p else "")
                                 + (tr("  (quedan {0})", quedan) if quedan > 0 else ""),
                                 foreground=tema.MUTED if quedan > 0 else tema.OK)
            bloqueada = piso < t.get("piso", 0)
            ui["cab"].configure(
                text=(tr("🔒 Se abre en el piso {0}", t["piso"]) if bloqueada else tr("Abierta desde el piso {0}", t["piso"]))
                + tr("  ·  gastado {0} · planeado {1} medallas", _fmt(gasto), _fmt(plan)),
                foreground=tema.MUTED if bloqueada else tema.TEXTO)
