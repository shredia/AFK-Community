# aplicacion/ventana_principal.py
"""Ventana única: menú lateral a la izquierda y la sección elegida a la derecha."""
import json
import tkinter as tk
from pathlib import Path
from tkinter import ttk, messagebox

import aplicacion.ventana_cuenta
import aplicacion.ventana_NC
import aplicacion.ventana_optimizador
import aplicacion.ventana_cuenta_actual
import aplicacion.ventana_fractura
from aplicacion import tema
from idiomas import tr, N_, idiomas_disponibles, idioma_actual, cambiar_idioma

# (grupo, [(clave, texto del menú)]) — el orden es el del menú lateral
MENU = [
    (None, [("inicio", N_("Inicio"))]),
    (N_("NIGHTMARE CORRIDOR"), [("optimizador", N_("Optimizador")),
                                ("explorar", N_("Explorar equipos")),
                                ("progreso", N_("Progreso semanal")),
                                ("runs", N_("Descargar runs  ·  en desarrollo"))]),
    (N_("CUENTA"), [("cuenta", N_("Mi cuenta")),
                    ("amigos", N_("Amigos"))]),
    (N_("OTROS"), [("fractura", N_("Fractura temporal")),
                   ("guias", N_("Guías  ·  pronto"))]),
]
ICONOS = {"inicio": "⌂", "optimizador": "★", "explorar": "⌕", "progreso": "↗", "runs": "⇩", "cuenta": "◉",
          "amigos": "☺", "fractura": "◈", "guias": "✎", "ajustes": "⚙"}


def sitio_en_desarrollo():
    from navegador.sitio import SITIO_EN_DESARROLLO
    return SITIO_EN_DESARROLLO


def en_desarrollo(host, titulo):
    """Pantalla 'En desarrollo' para lo que necesita conectarse a esperianarchive.com."""
    from navegador.sitio import MENSAJE_DESARROLLO
    marco = ttk.Frame(host, padding=40)
    marco.pack(fill="both", expand=True)
    ttk.Label(marco, text=tr(titulo), style="Titulo.TLabel").pack(anchor="w")
    ttk.Label(marco, text=tr("🚧 En desarrollo"), style="Seccion.TLabel", foreground=tema.WARN).pack(
        anchor="w", pady=(10, 6))
    ttk.Label(marco, text=tr(MENSAJE_DESARROLLO), style="Muted.TLabel", wraplength=700, justify="left").pack(anchor="w")
    return marco


class VentanaPrincipal:
    def __init__(self, root):
        self.root = root
        tema.aplicar(root)
        self.root.title(tr("Esperian NC"))
        ancho, alto = root.winfo_screenwidth(), root.winfo_screenheight()
        w, h = min(1600, ancho - 60), min(960, alto - 90)
        self.root.geometry(f"{w}x{h}+{max(0, (ancho - w) // 2)}+{max(0, (alto - h) // 3)}")
        self.root.minsize(1100, 680)
        if ancho <= 1600:
            try:
                self.root.state("zoomed")
            except tk.TclError:
                pass
        # Ruta absoluta: funciona aunque se ejecute desde otra carpeta
        self.perfil_path = Path(__file__).resolve().parent.parent / "perfil_esperian"
        self.base_dir = self.perfil_path.parent
        from aplicacion.imagenes import CacheImagenes
        self.imagenes = CacheImagenes()

        self._info_actualizacion = None
        self.secciones = {}        # clave -> {"host", "objeto"}
        self.actual = None
        self.var_menu = tk.StringVar(value="inicio")
        self.root.protocol("WM_DELETE_WINDOW", self.salir)
        self.crear_interfaz()
        self.mostrar("inicio")
        self.root.after(2000, self._revisar_actualizaciones)

    # ============================================
    # ESTRUCTURA
    # ============================================

    def crear_interfaz(self):
        lateral = ttk.Frame(self.root, style="Lateral.TFrame", width=228)
        lateral.pack(side="left", fill="y")
        lateral.pack_propagate(False)
        self.lateral = lateral
        cab = ttk.Frame(lateral, style="Lateral.TFrame")
        cab.pack(fill="x", padx=18, pady=(20, 4))
        ttk.Label(cab, text=tr("Esperian NC"), style="LateralTitulo.TLabel").pack(anchor="w")
        self.lbl_cuenta_lateral = ttk.Label(cab, text="", style="LateralMuted.TLabel", wraplength=190, justify="left")
        self.lbl_cuenta_lateral.pack(anchor="w", pady=(2, 0))

        self.botones_menu = {}
        for grupo, entradas in MENU:
            if grupo:
                ttk.Label(lateral, text=tr(grupo), style="LateralGrupo.TLabel").pack(anchor="w", padx=18, pady=(16, 4))
            else:
                ttk.Frame(lateral, style="Lateral.TFrame", height=10).pack()
            for clave, texto in entradas:
                self.botones_menu[clave] = self._boton_menu(lateral, clave, texto)

        abajo = ttk.Frame(lateral, style="Lateral.TFrame")
        abajo.pack(side="bottom", fill="x", pady=(0, 12))
        from navegador.actualizador import version_local
        ttk.Label(abajo, text=tr("versión {0}", version_local()), style="LateralMuted.TLabel").pack(
            side="bottom", anchor="w", padx=18, pady=(6, 0))
        self.botones_menu["ajustes"] = self._boton_menu(abajo, "ajustes", N_("Ajustes"))

        derecha = ttk.Frame(self.root)
        derecha.pack(side="left", fill="both", expand=True)
        # aviso de versión nueva (se muestra solo si hay una)
        self.banner_act = ttk.Frame(derecha, style="Panel.TFrame", padding=(16, 8))
        self.lbl_banner_act = ttk.Label(self.banner_act, text="", style="Panel.TLabel", foreground=tema.DORADO)
        self.lbl_banner_act.pack(side="left")
        ttk.Button(self.banner_act, text=tr("Actualizar ahora"), style="Acento.TButton",
                   command=self._instalar_actualizacion).pack(side="right")
        self.contenido = ttk.Frame(derecha)
        self.contenido.pack(fill="both", expand=True)
        if self._info_actualizacion:
            self._mostrar_banner(self._info_actualizacion)
        self.actualizar_lateral()

    def _boton_menu(self, padre, clave, texto):
        b = ttk.Radiobutton(padre, text=f"{ICONOS.get(clave, '·')}   {tr(texto)}", value=clave,
                            variable=self.var_menu, style="Nav.Toolbutton", command=lambda: self.mostrar(clave))
        b.pack(fill="x", padx=8, pady=1)
        if clave == "guias" or (clave == "runs" and sitio_en_desarrollo()):
            b.configure(state="disabled")
        return b

    def mostrar(self, clave, **opciones):
        """Muestra una sección (la crea la primera vez; después conserva su estado)."""
        if clave == "explorar":
            opt = self._seccion("optimizador")
            self.var_menu.set("optimizador")
            if opt and hasattr(opt, "ir_a_explorar"):
                opt.ir_a_explorar()
            return
        self.var_menu.set(clave)
        if self.actual and self.actual in self.secciones:
            self.secciones[self.actual]["host"].pack_forget()
        self.actual = clave
        if clave not in self.secciones:
            host = tema.AnfitrionSeccion(self.contenido, al_cerrar=lambda c=clave: self._seccion_cerrada(c))
            self.secciones[clave] = {"host": host, "objeto": None}
            host.pack(fill="both", expand=True)
            try:
                self.secciones[clave]["objeto"] = getattr(self, f"_crear_{clave}")(host, **opciones)
            except Exception as error:   # una sección rota no tumba la app
                for w in host.winfo_children():
                    w.destroy()
                ttk.Label(host, text=tr("No se pudo abrir esta sección:\n{0}", error), foreground=tema.ERR,
                          justify="left").pack(anchor="w", padx=30, pady=30)
        else:
            self.secciones[clave]["host"].pack(fill="both", expand=True)
            if clave == "inicio":
                self.actualizar_inicio()
            elif clave in ("progreso", "amigos"):
                objeto = self.secciones[clave]["objeto"]
                if objeto and hasattr(objeto, "recargar"):
                    objeto.recargar()

    def _seccion(self, clave, **opciones):
        """El objeto de una sección (creándola y mostrándola si hace falta)."""
        self.mostrar(clave, **opciones)
        return (self.secciones.get(clave) or {}).get("objeto")

    def _seccion_cerrada(self, clave):
        """La ventana incrustada se cerró sola (p. ej. tras iniciar sesión): se vuelve a crear al entrar."""
        datos = self.secciones.pop(clave, None)
        if datos:
            datos["host"].destroy()
        if self.actual == clave:
            self.actual = None
            self.mostrar("inicio")

    def recrear(self, clave, **opciones):
        datos = self.secciones.pop(clave, None)
        if datos:
            datos["host"].destroy()
            if self.actual == clave:
                self.actual = None
        self.mostrar(clave, **opciones)

    def datos_cambiaron(self):
        """Se importaron / borraron runs o amigos: lo que depende de ellos se refresca."""
        self.actualizar_lateral()
        opt = (self.secciones.get("optimizador") or {}).get("objeto")
        if opt and hasattr(opt, "recargar_fuentes"):
            opt.recargar_fuentes()
        for clave in ("progreso", "amigos"):
            objeto = (self.secciones.get(clave) or {}).get("objeto")
            if objeto and hasattr(objeto, "recargar"):
                objeto.recargar()

    def salir(self):
        self.salir_sin_cerrar()
        self.root.quit()

    # ============================================
    # SECCIONES
    # ============================================

    def _crear_inicio(self, host):
        marco = ttk.Frame(host)
        marco.pack(fill="both", expand=True, padx=36, pady=28)
        ttk.Label(marco, text=tr("Esperian NC"), style="Titulo.TLabel").pack(anchor="w")
        ttk.Label(marco, text=tr("Arma tu mejor rotación de Nightmare Corridor con los héroes que de verdad tienes."),
                  style="Muted.TLabel", font=tema.FUENTE_SUBTITULO).pack(anchor="w", pady=(2, 18))
        self.fila_estado = ttk.Frame(marco)
        self.fila_estado.pack(fill="x")

        ttk.Label(marco, text=tr("Cómo empezar"), style="Seccion.TLabel").pack(anchor="w", pady=(26, 8))
        pasos = [
            ("importar", N_("Importar tus datos"), N_("Descarga afk-runs.json y afk-inventory.json del sitio e "
                                                      "impórtalos en Ajustes → Importar / exportar.")),
            ("cuenta", N_("Mi cuenta"), N_("Tus héroes, colecciones y mascotas: el optimizador sabe qué tienes.")),
            ("amigos", N_("Amigos"), N_("Importa las runs de tus amigos para copiar sus mejores equipos.")),
            ("optimizador", N_("Optimizador"), N_("El mejor equipo por jefe sin repetir héroes, y qué te falta para mejorar.")),
        ]
        for i, (clave, titulo, texto) in enumerate(pasos, 1):
            fila = ttk.Frame(marco, style="Tarjeta.TFrame", padding=(14, 10))
            fila.pack(fill="x", pady=3)
            ttk.Label(fila, text=f" {i} ", style="TarjetaPaso.TLabel", background=tema.DORADO).pack(side="left")
            textos = ttk.Frame(fila, style="Panel.TFrame")
            textos.pack(side="left", padx=14, fill="x", expand=True)
            ttk.Label(textos, text=tr(titulo), style="Tarjeta.TLabel", font=tema.FUENTE_NEGRITA).pack(anchor="w")
            ttk.Label(textos, text=tr(texto), style="TarjetaTexto.TLabel").pack(anchor="w")
            ttk.Button(fila, text=tr("Abrir  →"), command=lambda c=clave: self._ir_a_ajustes("importar") if c == "importar"
                       else self.mostrar(c)).pack(side="right")
            if clave == "importar":
                from navegador.sitio import URL_RUNS, URL_INVENTARIO
                from aplicacion.ventana_importar import abrir_enlace
                ttk.Button(fila, text=tr("🌐 Inventory"), command=lambda: abrir_enlace(URL_INVENTARIO)).pack(
                    side="right", padx=(6, 0))
                ttk.Button(fila, text=tr("🌐 My runs"), command=lambda: abrir_enlace(URL_RUNS)).pack(
                    side="right", padx=6)
        if sitio_en_desarrollo():
            aviso = ttk.Frame(marco, style="Tarjeta.TFrame", padding=(14, 10))
            aviso.pack(fill="x", pady=(14, 0))
            ttk.Label(aviso, text=tr("🚧 Conexión con el sitio: en desarrollo"), style="Tarjeta.TLabel",
                      foreground=tema.WARN, font=tema.FUENTE_NEGRITA).pack(anchor="w")
            ttk.Label(aviso, text=tr("Iniciar sesión, hacer fetch y descargar runs desde esperianarchive.com está "
                                     "desactivado mientras se adapta al nuevo acceso del sitio. Todo lo demás funciona "
                                     "con los archivos importados."), style="TarjetaTexto.TLabel", wraplength=900,
                      justify="left").pack(anchor="w")
        self.actualizar_inicio()
        return marco

    def actualizar_inicio(self):
        if not getattr(self, "fila_estado", None) or not self.fila_estado.winfo_exists():
            return
        for w in self.fila_estado.winfo_children():
            w.destroy()
        e = self._estado_datos()
        tarjetas = [
            (N_("Cuenta"), e["cuenta"], e["cuenta_detalle"]),
            (N_("Runs con detalle"), str(e["detalles"]), tr("en {0} servidores", e["servidores"])),
            (N_("Amigos"), str(e["amigos"]), tr("con {0} runs importadas", e["runs_amigos"])),
        ]
        for i, (titulo, valor, sub) in enumerate(tarjetas):
            t = ttk.Frame(self.fila_estado, style="Tarjeta.TFrame", padding=(16, 12))
            t.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 10, 0))
            self.fila_estado.columnconfigure(i, weight=1, uniform="estado")
            ttk.Label(t, text=tr(titulo).upper(), style="PanelMuted.TLabel").pack(anchor="w")
            ttk.Label(t, text=valor, style="TarjetaTiempo.TLabel").pack(anchor="w", pady=(4, 0))
            ttk.Label(t, text=sub, style="TarjetaTexto.TLabel").pack(anchor="w")
        self.actualizar_lateral(e)

    def _estado_datos(self):
        from navegador.cuenta import hace_cuanto
        cuentas = self.base_dir / "cuentas"
        capturas = sorted(cuentas.glob("*/*/cuenta_actual.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        capturas = [c for c in capturas if c.parent.parent.name != "_amigos"]
        cuenta, detalle_cuenta, nombre = tr("Sin sincronizar"), tr("Ve a 'Mi cuenta'"), ""
        if capturas:
            try:
                datos = json.loads(capturas[0].read_text(encoding="utf-8"))
                cuenta = tr("Sincronizada")
                detalle_cuenta = tr("captura {0}", hace_cuanto(datos.get("capturedAt")))
                ficha = capturas[0].parent / f"{capturas[0].parent.name}.json"
                if ficha.exists():
                    nombre = (json.loads(ficha.read_text(encoding="utf-8")) or {}).get("name") or ""
                nombre = f"{nombre} · S{capturas[0].parent.name}" if nombre else f"S{capturas[0].parent.name}"
            except (OSError, json.JSONDecodeError, AttributeError):
                pass
        propias = [d for d in cuentas.glob("*/*/detalles") if d.parent.parent.name != "_amigos"]
        detalles = sum(sum(1 for _ in d.glob("*.json")) for d in propias)
        servidores = sum(1 for d in propias if any(d.glob("*.json")))
        try:
            from navegador.importar import amigos
            lista = amigos(self.base_dir)
        except Exception:
            lista = []
        return {"cuenta": cuenta, "cuenta_detalle": detalle_cuenta, "nombre": nombre, "detalles": detalles,
                "servidores": servidores, "amigos": len(lista), "runs_amigos": sum(a["runs"] for a in lista)}

    def actualizar_lateral(self, estado=None):
        e = estado or self._estado_datos()
        try:
            self.lbl_cuenta_lateral.configure(text=e["nombre"] or tr("sin cuenta sincronizada"))
        except tk.TclError:
            pass

    def _crear_optimizador(self, host, carpeta=None, enfoque=None):
        return aplicacion.ventana_optimizador.VentanaOptimizador(host, self.perfil_path, carpeta_inicial=carpeta,
                                                                 enfoque=enfoque)

    def _crear_progreso(self, host):
        from aplicacion.seccion_progreso import SeccionProgreso
        return SeccionProgreso(host, self.base_dir)

    def _crear_runs(self, host):
        if sitio_en_desarrollo():
            return en_desarrollo(host, N_("Descargar runs"))
        return aplicacion.ventana_NC.Ventana_NC(host, self.perfil_path)

    def _crear_cuenta(self, host):
        return aplicacion.ventana_cuenta_actual.VentanaCuentaActual(host, self.perfil_path,
                                                                    abrir_optimizador=self.abrir_optimizador)

    def _crear_amigos(self, host):
        from aplicacion.seccion_amigos import SeccionAmigos
        return SeccionAmigos(host, self.base_dir, al_cambiar=self.datos_cambiaron,
                             importar=lambda: self._ir_a_ajustes("importar"),
                             comparar=self.comparar_con_amigo)

    def _crear_fractura(self, host):
        return aplicacion.ventana_fractura.VentanaFractura(host, self.perfil_path)

    def _crear_ajustes(self, host):
        marco = ttk.Frame(host)
        marco.pack(fill="both", expand=True, padx=24, pady=(20, 12))
        ttk.Label(marco, text=tr("Ajustes"), style="Titulo.TLabel").pack(anchor="w", pady=(0, 10))
        nb = ttk.Notebook(marco)
        nb.pack(fill="both", expand=True)
        self.nb_ajustes = nb

        general = ttk.Frame(nb, padding=20)
        nb.add(general, text=tr("General"))
        fila = ttk.Frame(general)
        fila.pack(anchor="w", pady=(0, 14))
        ttk.Label(fila, text=tr("Idioma:")).pack(side="left")
        self._idiomas = idiomas_disponibles()
        self.combo_idioma = ttk.Combobox(fila, state="readonly", width=16,
                                         values=[nombre for _, nombre in self._idiomas])
        actual = next((i for i, (c, _) in enumerate(self._idiomas) if c == idioma_actual()), 0)
        if self._idiomas:
            self.combo_idioma.current(actual)
        self.combo_idioma.pack(side="left", padx=8)
        self.combo_idioma.bind("<<ComboboxSelected>>", lambda e: self._cambiar_idioma())
        fila = ttk.Frame(general)
        fila.pack(anchor="w", pady=(0, 14))
        from navegador.actualizador import version_local
        ttk.Label(fila, text=tr("Versión instalada: {0}", version_local())).pack(side="left")
        ttk.Button(fila, text=tr("Buscar actualizaciones…"), command=self.abrir_actualizaciones).pack(side="left", padx=10)

        self.tabs_ajustes = {}
        for clave, titulo, crear in (
                ("acceso", N_("Acceso al sitio · en desarrollo"),
                 lambda h: en_desarrollo(h, N_("Acceso al sitio")) if sitio_en_desarrollo()
                 else aplicacion.ventana_cuenta.VentanaCuenta(h, self.perfil_path)),
                ("importar", N_("Importar / exportar"), self._crear_importar)):
            tab = ttk.Frame(nb)
            nb.add(tab, text=tr(titulo))
            host_tab = tema.AnfitrionSeccion(tab)
            host_tab.pack(fill="both", expand=True)
            self.tabs_ajustes[clave] = tab
            crear(host_tab)
        return marco

    def _crear_importar(self, host):
        from aplicacion.ventana_importar import VentanaImportar
        return VentanaImportar(host, self.perfil_path, al_terminar=self.datos_cambiaron)

    def _ir_a_ajustes(self, pestana):
        self.mostrar("ajustes")
        tab = getattr(self, "tabs_ajustes", {}).get(pestana)
        if tab is not None:
            self.nb_ajustes.select(tab)

    # ============================================
    # ACCIONES ENTRE SECCIONES
    # ============================================

    def abrir_optimizador(self, carpeta=None, enfoque=None):
        """Desde 'Mi cuenta': abre el optimizador en ese servidor, enfocado en un héroe / jefe."""
        opt = (self.secciones.get("optimizador") or {}).get("objeto")
        if opt is None:
            self.mostrar("optimizador", carpeta=carpeta, enfoque=enfoque)
            return
        self.mostrar("optimizador")
        if hasattr(opt, "abrir_en"):
            opt.abrir_en(carpeta, enfoque)

    def comparar_con_amigo(self, carpeta):
        opt = self._seccion("optimizador")
        if opt and hasattr(opt, "optimizar_con_carpeta"):
            opt.optimizar_con_carpeta(carpeta)

    # ============================================
    # ACTUALIZACIONES (GitHub)
    # ============================================

    def _revisar_actualizaciones(self):
        """Al abrir: revisa en segundo plano (como mucho cada 12 h) si hay versión nueva publicada."""
        import threading
        from navegador import actualizador as act
        if act.es_copia_desarrollo():
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
            self.banner_act.pack(fill="x", side="top", before=self.contenido)
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
        if self.secciones.keys() - {"inicio", "ajustes"} and not messagebox.askokcancel(
                tr("Idioma"), tr("Para cambiar el idioma se cierran las secciones abiertas. ¿Continuar?"),
                parent=self.root):
            return
        cambiar_idioma(self._idiomas[i][0])
        self.salir_sin_cerrar()
        for hijo in self.root.winfo_children():
            if not isinstance(hijo, tk.Toplevel):
                hijo.destroy()
        self.secciones, self.actual = {}, None
        self.crear_interfaz()
        self.mostrar("ajustes")

    def salir_sin_cerrar(self):
        for datos in self.secciones.values():
            objeto = datos.get("objeto")
            if objeto is not None and hasattr(objeto, "_guardar_ya"):
                try:
                    objeto._guardar_ya()
                except Exception:
                    pass

    # Compatibilidad con código que llama a estos nombres
    def abrir_configuracion(self):
        self._ir_a_ajustes("acceso")

    def accion_cargar_pagina(self):
        self.mostrar("runs")

    def abrir_importar(self):
        self._ir_a_ajustes("importar")

    def abrir_fractura(self):
        self.mostrar("fractura")

    def abrir_cuenta_actual(self):
        self.mostrar("cuenta")

    def actualizar_resumen(self):
        self.actualizar_inicio()


def iniciar_aplicacion():
    root = tk.Tk()
    VentanaPrincipal(root)
    root.mainloop()
