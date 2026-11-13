# aplicacion/ventana_importar.py
"""Importar los archivos que descarga el sitio (afk-runs.json, afk-inventory.json) y copias .zip de la app."""
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from aplicacion import tema
from aplicacion.ventana_progreso import VentanaProgreso
from idiomas import tr, N_
from navegador import importar as imp


def abrir_enlace(url):
    import webbrowser
    webbrowser.open(url, new=2)


def describir_runs(a):
    """Qué trae el archivo de runs, en una frase (ver importar.analizar_runs)."""
    if a["una"]:
        run, res = a["una"], a["una"].get("result") or {}
        ms = res.get("timeMs")
        texto = tr("Una run de NC del {0}: {1} jefes en {2} s (batalla {3}).", a["desde"] or "?",
                   res.get("bossesKilled") or "?", f"{ms / 1000:.1f}" if ms else "?",
                   run.get("battleId") or run.get("id") or "?")
    else:
        texto = tr("{0} runs de NC, del {1} al {2}.", a["nc"], a["desde"] or "?", a["hasta"] or "?")
    if a["otros"]:
        texto += " " + tr("{0} de otros modos se omiten.", a["otros"])
    if a["ya_estan"]:
        texto += " " + (tr("Ya la tienes: se completa, no se duplica.") if a["nc"] == 1 else
                        tr("Ya tienes {0}: se completan, no se duplican.", a["ya_estan"]))
    return texto


def ajustable(etiqueta, margen=4):
    """El texto se reparte en líneas según el ancho disponible (en vez de un wraplength fijo)."""
    etiqueta.bind("<Configure>", lambda e: etiqueta.configure(wraplength=max(e.width - margen, 80)))
    return etiqueta


def mostrar_en_carpeta(ruta):
    """Abre la carpeta del archivo (en Windows, con el archivo seleccionado)."""
    import subprocess
    import sys
    try:
        if sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", str(Path(ruta))])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(Path(ruta))])
        else:
            subprocess.Popen(["xdg-open", str(Path(ruta).parent)])
    except OSError:
        pass


class VentanaImportar:
    def __init__(self, parent, perfil_path, al_terminar=None):
        self.parent = parent
        self.base_dir = Path(perfil_path).parent
        self.al_terminar = al_terminar or (lambda: None)

        self.top = tema.ventana(parent)
        self.top.title(tr("Importar / exportar datos"))
        self.top.geometry("760x600")
        self.top.minsize(620, 500)
        self.top.transient(parent)
        self._crear_interfaz()

    # ------------------------------------------------------------
    def _crear_interfaz(self):
        from navegador.sitio import URL_CUENTAS, URL_RUNS, URL_INVENTARIO
        marco = ttk.Frame(self.top, padding=18)
        marco.pack(fill="both", expand=True)
        ttk.Label(marco, text=tr("Importar / exportar datos"), style="Titulo.TLabel").pack(anchor="w")
        ttk.Label(marco, style="Muted.TLabel", wraplength=900, justify="left", text=tr(
            "Trae tus datos del sitio o las runs de un amigo, y comparte las tuyas. No hace falta iniciar sesión.")).pack(
            anchor="w", pady=(2, 10))

        # ---- siguiente paso sugerido (según lo que ya tienes)
        self.lbl_siguiente = ttk.Label(marco, text="", foreground=tema.DORADO, wraplength=900, justify="left")
        self.lbl_siguiente.pack(anchor="w", pady=(0, 10))

        columnas = ttk.Frame(marco)
        columnas.pack(fill="x")
        columnas.columnconfigure(0, weight=1, uniform="col")
        columnas.columnconfigure(1, weight=1, uniform="col")

        # ---- importar
        caja = ttk.Frame(columnas, style="Tarjeta.TFrame", padding=16)
        caja.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        ttk.Label(caja, text=tr("📥 Importar"), style="TarjetaTitulo.TLabel").pack(anchor="w")
        ajustable(ttk.Label(caja, style="TarjetaTexto.TLabel", justify="left", text=tr(
            "Elige el archivo: la app reconoce cuál es y te pregunta lo que necesite."))).pack(
            anchor="w", fill="x", pady=(2, 10))
        ttk.Button(caja, text=tr("Elegir archivo…"), style="Acento.TButton",
                   command=self._elegir_e_importar).pack(anchor="w", pady=(0, 12))
        for archivo, texto in (
                ("afk-inventory.json", N_("Tus héroes, colecciones y recursos. Impórtalo primero.")),
                ("afk-runs.json", N_("Tus runs de NC (o las de un amigo).")),
                ("afk-NC-….json", N_("Una sola run, descargada desde su página.")),
                (".zip", N_("El que te manda un amigo, o tu propia copia."))):
            fila = ttk.Frame(caja, style="Panel.TFrame")
            fila.pack(fill="x", pady=2)
            tk.Label(fila, text=archivo, bg=tema.PANEL, fg=tema.DORADO, font=tema.FUENTE_MONO, width=19,
                     anchor="w").pack(side="left")
            ajustable(ttk.Label(fila, text=tr(texto), style="TarjetaTexto.TLabel", justify="left")).pack(
                side="left", fill="x", expand=True)

        # ---- exportar
        caja = ttk.Frame(columnas, style="Tarjeta.TFrame", padding=16)
        caja.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        ttk.Label(caja, text=tr("📤 Compartir o respaldar"), style="TarjetaTitulo.TLabel").pack(anchor="w")
        ajustable(ttk.Label(caja, style="TarjetaTexto.TLabel", justify="left", text=tr(
            "Guarda un .zip y mándaselo a un amigo: su app guarda solo tus runs (con el SP de cada ronda), "
            "sin mezclarlas con sus datos. También sirve para pasar tus datos a otro PC."))).pack(
            anchor="w", fill="x", pady=(2, 10))
        ttk.Label(caja, text=tr("¿Qué quieres guardar?"), style="Tarjeta.TLabel").pack(anchor="w")
        fila = ttk.Frame(caja, style="Panel.TFrame")
        fila.pack(fill="x", pady=(4, 0))
        self.combo_exportar = ttk.Combobox(fila, state="readonly", width=40)
        self.combo_exportar.pack(side="left")
        self.btn_exportar = ttk.Button(fila, text=tr("Guardar .zip…"), style="Acento.TButton", command=self._exportar)
        self.btn_exportar.pack(side="left", padx=8)
        self.fila_guardado = ttk.Frame(caja, style="Panel.TFrame")
        self.fila_guardado.pack(fill="x", pady=(10, 0))

        # ---- dónde se consiguen los archivos
        ttk.Label(marco, text=tr("¿Dónde consigo los archivos del sitio?"), style="Seccion.TLabel").pack(
            anchor="w", pady=(18, 6))
        pasos = ttk.Frame(marco, style="Tarjeta.TFrame", padding=(14, 10))
        pasos.pack(fill="x")
        for i, (texto, boton, url) in enumerate((
                (N_("Inicia sesión en esperianarchive.com. En «Game accounts» elige tu personaje y pulsa "
                    "«Fetch … inventory and runs»."), N_("🌐 Game accounts"), URL_CUENTAS),
                (N_("En «Inventory» descarga afk-inventory.json."), N_("🌐 Inventory"), URL_INVENTARIO),
                (N_("En «My runs» descarga afk-runs.json."), N_("🌐 My runs"), URL_RUNS),
                (N_("Vuelve aquí e impórtalos con «Elegir archivo…»: primero el inventario. ¿Varios personajes? "
                    "Repite con cada uno."), None, None)), 1):
            fila = ttk.Frame(pasos, style="Panel.TFrame")
            fila.pack(fill="x", pady=3)
            ttk.Label(fila, text=f" {i} ", style="TarjetaPaso.TLabel", background=tema.DORADO).pack(side="left")
            ttk.Label(fila, text=tr(texto), style="Tarjeta.TLabel", wraplength=700, justify="left").pack(
                side="left", padx=10)
            if url:
                ttk.Button(fila, text=tr(boton), command=lambda u=url: abrir_enlace(u)).pack(side="right")

        # ---- detalles (plegados)
        self.var_detalles = tk.BooleanVar(value=False)
        self.btn_detalles = ttk.Button(marco, style="Plano.TButton", command=self._alternar_detalles)
        self.btn_detalles.pack(anchor="w", pady=(12, 0))
        self.lbl_detalles = ttk.Label(marco, style="Muted.TLabel", wraplength=900, justify="left", text=tr(
            "• afk-inventory.json reemplaza la 'Mi cuenta' de ese personaje (la anterior queda como "
            "cuenta_actual.anterior.json). Si el personaje es nuevo, la app te pide su nombre.\n"
            "• afk-runs.json no dice qué personaje jugó las runs: por eso se pregunta al importar. Se agregan las "
            "que faltan y a las que ya tenías se les suman las estadísticas. Las runs de otros modos (CR) se omiten.\n"
            "• El .zip trae todo lo de un servidor o de un amigo: runs, Mi cuenta, Fractura y bloqueos. Si es de un "
            "amigo, solo se guardan sus runs. Si es tuyo, sus archivos reemplazan a los que tengas.\n"
            "• También se pueden importar las runs compartidas (.json) de versiones anteriores.\n"
            "• Los archivos del sitio no traen el rol del héroe, los nodos de grabado, el nivel de la mascota ni en "
            "qué casilla va cada mueble: se completan con lo que ya tienes del mismo héroe o mascota.\n"
            "• Special Power: si el equipo tiene un solo héroe especial (Fawkes, Thoran, Eluard…) se deduce, porque "
            "se activa solo. Si tiene dos o más, el archivo no dice cuál se eligió."))
        self._alternar_detalles(inicial=True)

        if not getattr(self.top, "incrustada", False):
            ttk.Button(marco, text=tr("Cerrar"), command=self.top.destroy).pack(side="bottom", anchor="e", pady=(12, 0))
        self.recargar()

    def _alternar_detalles(self, inicial=False):
        if not inicial:
            self.var_detalles.set(not self.var_detalles.get())
        if self.var_detalles.get():
            self.btn_detalles.configure(text=tr("▾ Qué trae cada archivo"))
            self.lbl_detalles.pack(anchor="w", pady=(4, 0), after=self.btn_detalles)
        else:
            self.btn_detalles.configure(text=tr("▸ Qué trae cada archivo"))
            self.lbl_detalles.pack_forget()

    def recargar(self):
        """Lo que se puede exportar y el siguiente paso sugerido (cambian después de importar)."""
        try:
            personajes = [c for c, _ in imp.carpetas_servidor(self.base_dir)]
            amigos = imp.amigos(self.base_dir)
        except Exception:   # noqa: BLE001
            personajes, amigos = [], []
        propios = []
        for carpeta in personajes:
            ficha = imp._leer_json(carpeta / f"{carpeta.name}.json") or {}
            nombre = ficha.get("name") or ficha.get("uid") or carpeta.name
            propios.append((len(imp._leer_json(carpeta / "runs.json") or []), carpeta, nombre))
        propios.sort(key=lambda x: -x[0])   # primero el personaje con más runs (el que más se comparte)
        self.exportables = [(carpeta, f"{nombre}-S{carpeta.name}",
                             tr("👤 {0} · servidor {1} · {2} runs", nombre, carpeta.name, runs))
                            for runs, carpeta, nombre in propios]
        for a in amigos:
            self.exportables.append((a["carpeta"], a["nombre"],
                                     tr("👥 Amigo: {0} · {1} runs", a["nombre"], a["runs"])))
        self.combo_exportar.configure(values=[texto for *_, texto in self.exportables])
        if self.exportables:
            self.combo_exportar.current(0)
        else:
            self.combo_exportar.set(tr("(todavía no hay nada que guardar)"))
        self.btn_exportar.configure(state="normal" if self.exportables else "disabled")

        if not personajes:
            texto, color = tr("👉 Para empezar, importa el afk-inventory.json de tu personaje (abajo se explica "
                              "dónde descargarlo)."), tema.DORADO
        elif not any(runs for runs, *_ in propios):
            texto, color = tr("👉 Siguiente paso: importa tu afk-runs.json y elige «Son mías»."), tema.DORADO
        else:
            texto, color = tr("✔ Tienes {0} personajes y {1} amigos. Vuelve a importar cuando juegues runs nuevas o "
                              "mejores héroes: solo se agrega lo nuevo.", len(personajes), len(amigos)), tema.OK
        self.lbl_siguiente.configure(text=texto, foreground=color)

    def _mostrar_guardado(self, destino):
        for w in self.fila_guardado.winfo_children():
            w.destroy()
        ttk.Label(self.fila_guardado, text=tr("✔ Guardado: {0}", Path(destino).name), style="Tarjeta.TLabel",
                  foreground=tema.OK, wraplength=280).pack(side="left")
        ttk.Button(self.fila_guardado, text=tr("📂 Mostrar en la carpeta"),
                   command=lambda: mostrar_en_carpeta(destino)).pack(side="left", padx=8)

    # ------------------------------------------------------------
    def _elegir_e_importar(self):
        ruta = filedialog.askopenfilename(
            parent=self.top, title=tr("Elegir archivo para importar"),
            filetypes=[(tr("afk-inventory.json, afk-runs.json o .zip"), "*.json *.zip"), (tr("Todos"), "*.*")])
        if not ruta:
            return
        if ruta.lower().endswith(".zip"):
            self._importar_zip(ruta)
            return
        prog = VentanaProgreso(self.top, "Importando", cancelable=False)

        def leer():
            try:
                prog.log(tr("Leyendo {0}...", Path(ruta).name))
                tipo, datos = imp.detectar(ruta)
                if tipo in ("runs", "runs_app"):
                    runs = datos if tipo == "runs" else (datos.get("runs") or [])
                    if tipo == "runs_app":
                        prog.log(tr("Runs compartidas de {0} (con SP y estadísticas).", datos.get("nombre") or "?"))
                    analisis = imp.analizar_runs(self.base_dir, runs, solo_nc=(tipo == "runs"))
                    if not analisis["nc"]:
                        prog.terminar(tr("El archivo no trae runs de NC (solo de otros modos)."), ok=False)
                        return
                    prog.log(describir_runs(analisis))
                    prog.log(tr("Elige de quién son..."))
                    self.top.after(0, lambda: self._preguntar_dueno(prog, datos, analisis, tipo))
                    return
                if tipo == "inventario":
                    info = imp.personaje_de_inventario(self.base_dir, datos)
                    if info["carpeta"] is None:   # personaje nuevo: el archivo no trae su nombre, se pregunta
                        prog.log(tr("Personaje nuevo: UID {0} · servidor {1}.", info["uid"], info["servidor"]))
                        self.top.after(0, lambda: self._preguntar_nombre(prog, datos, info))
                        return
                    prog.log(tr("Personaje: {0} · servidor {1} · UID {2}",
                                info["nombre"] or "?", info["servidor"], info["uid"]))
                    self._importar_inventario(prog, datos)
                    return
                else:
                    raise RuntimeError(tr("El archivo no es afk-runs.json, afk-inventory.json, runs compartidas "
                                          "ni una copia de la app."))
            except Exception as error:  # noqa: BLE001
                prog.terminar(tr("Error: {0}", error), ok=False)

        threading.Thread(target=leer, daemon=True).start()

    def _importar_zip(self, ruta):
        """El .zip de un amigo (se guardan solo sus runs, aparte) o tu propia copia (se restaura)."""
        try:
            info = imp.info_copia(self.base_dir, ruta)
        except (ValueError, OSError, imp.zipfile.BadZipFile) as error:
            messagebox.showerror(tr("Importar .zip"), str(error), parent=self.top)
            return
        if info["mio"]:   # es uno de tus personajes: se restaura sin preguntar de quién es
            if not messagebox.askyesno(tr("Importar copia"), tr(
                    "Es una copia de tu personaje {0}. Sus archivos reemplazan a los que tengas con el mismo nombre. "
                    "¿Continuar?", info["nombre"] or info["uid"]), parent=self.top):
                return
            eleccion = ("mia",)
        else:
            eleccion = DialogoCopia(self.top, info).resultado
            if eleccion is None:
                return
        prog = VentanaProgreso(self.top, "Importando", cancelable=False)

        def trabajo():
            try:
                if eleccion[0] == "amigo":
                    prog.log(tr("Runs de {0} ({1} en la copia)...", eleccion[1], info["runs"]))
                    r = imp.importar_copia_de_amigo(self.base_dir, ruta, eleccion[1], eleccion[2], prog.log)
                    prog.log(tr("Runs nuevas: {0} · ya las tenías: {1}", r["nuevas"], r["ya_estaban"]))
                    prog.log(tr("Ábrelas en el Optimizador NC eligiendo «{0}».", tr("Amigo: {0}", eleccion[1])))
                else:
                    prog.log(tr("La copia trae: {0}", ", ".join("/".join(c) for c in info["carpetas"])))
                    n = imp.importar_copia(self.base_dir, ruta, prog.log)
                    prog.log(tr("{0} archivos restaurados.", n))
                self._terminar(prog)
            except Exception as error:  # noqa: BLE001
                prog.terminar(tr("Error: {0}", error), ok=False)

        threading.Thread(target=trabajo, daemon=True).start()

    def _importar_inventario(self, prog, datos, nombre=None):
        r = imp.importar_inventario(self.base_dir, datos, prog.log, nombre=nombre)
        prog.log(tr("Mi cuenta actualizada: {0} héroes, {1} colecciones, {2} objetos.",
                    r["heroes"], r["colecciones"], r["objetos"]))
        prog.log(tr("Ahora puedes importar las runs de este personaje (afk-runs.json) y elegirlo en «Son mías»."))
        self._terminar(prog)

    def _preguntar_nombre(self, prog, datos, info):
        nombre = DialogoNombrePersonaje(prog.top, info).resultado
        if nombre is None:
            prog.terminar(tr("Importación cancelada."), ok=False)
            return

        def importar():
            try:
                self._importar_inventario(prog, datos, nombre)
            except Exception as error:  # noqa: BLE001
                prog.terminar(tr("Error: {0}", error), ok=False)

        threading.Thread(target=importar, daemon=True).start()

    def _preguntar_dueno(self, prog, runs, analisis, tipo="runs"):
        dialogo = DialogoDuenoRuns(prog.top, self.base_dir, analisis)
        destino = dialogo.resultado   # carpeta, o None si canceló
        if destino is None:
            prog.terminar(tr("Importación cancelada."), ok=False)
            return

        def importar():
            try:
                prog.log(tr("Destino: {0}", destino))
                if tipo == "runs_app":
                    r = imp.importar_runs_app(self.base_dir, runs, destino, prog.log)
                    prog.log(tr("Runs nuevas: {0} · ya las tenías: {1} · completadas con SP / estadísticas: {2}",
                                r["nuevas"], r["ya_estaban"], r["completadas"]))
                else:
                    r = imp.importar_runs(self.base_dir, runs, destino, prog.log)
                    prog.log(tr("Runs nuevas: {0} · ya las tenías: {1} · reimportadas: {2} · otros modos omitidos: {3}",
                                r["nuevas"], r["ya_estaban"], r["actualizadas"], r["otros_modos"]))
                    if r.get("con_estadisticas"):
                        prog.log(tr("Estadísticas agregadas a {0} runs que ya tenías del sitio.", r["con_estadisticas"]))
                if r["nuevas"]:
                    prog.log(tr("Ábrelas en el Optimizador NC eligiendo «{0}».",
                                tr("Amigo: {0}", destino.name) if r["amigo"] else tr("Servidor {0}", destino.name)))
                self._terminar(prog)
            except Exception as error:  # noqa: BLE001
                prog.terminar(tr("Error: {0}", error), ok=False)

        threading.Thread(target=importar, daemon=True).start()

    def _terminar(self, prog):
        prog.terminar(tr("Importación terminada."), ok=True)
        self.top.after(0, self.recargar)
        self.top.after(0, self.al_terminar)

    def _exportar(self):
        i = self.combo_exportar.current()
        if i < 0:
            return
        carpeta, nombre, _ = self.exportables[i]
        sugerido = f"afk-community-{imp._nombre_carpeta(nombre)}-{datetime.now():%Y%m%d}.zip"
        destino = filedialog.asksaveasfilename(parent=self.top, title=tr("Guardar .zip"), initialfile=sugerido,
                                               defaultextension=".zip", filetypes=[("Zip", "*.zip")])
        if not destino:
            return
        prog = VentanaProgreso(self.top, "Exportando", cancelable=False)

        def trabajo():
            try:
                prog.log(tr("Comprimiendo {0}...", nombre))
                n = imp.exportar_copia(carpeta, destino, prog.log)
                prog.terminar(tr("Listo: {0} archivos en {1}", n, Path(destino).name), ok=True)
                self.top.after(0, lambda: self._mostrar_guardado(destino))
            except Exception as error:  # noqa: BLE001
                prog.terminar(tr("Error: {0}", error), ok=False)

        threading.Thread(target=trabajo, daemon=True).start()

class DialogoCopia:
    """Un .zip que no es de tus personajes: ¿de un amigo (solo sus runs, aparte) o tu copia? Modal; deja .resultado:
    ("amigo", nombre, servidor), ("mia",) o None si canceló."""

    def __init__(self, parent, info):
        self.resultado = None
        self.top = tk.Toplevel(parent)
        self.top.title(tr("¿De quién es esta copia?"))
        self.top.resizable(False, False)
        self.top.transient(parent)
        self.top.protocol("WM_DELETE_WINDOW", self._cancelar)
        un_personaje = len(info["carpetas"]) == 1

        m = ttk.Frame(self.top, padding=16)
        m.pack(fill="both", expand=True)
        ttk.Label(m, text=tr("¿De quién es esta copia?"), style="Titulo.TLabel").pack(anchor="w")
        if un_personaje:
            texto = tr("Personaje: {0} · servidor {1} · {2} runs.", info["nombre"] or "?", info["servidor"] or "?",
                       info["runs"])
        else:
            texto = tr("La copia trae varios personajes: {0}.", ", ".join("/".join(c) for c in info["carpetas"]))
        ttk.Label(m, style="Muted.TLabel", wraplength=480, justify="left", text=texto).pack(anchor="w", pady=(2, 10))

        self.tipo = tk.StringVar(value="amigo" if un_personaje else "mia")
        ttk.Radiobutton(m, text=tr("De un amigo"), value="amigo", variable=self.tipo, command=self._estado,
                        state="normal" if un_personaje else "disabled").pack(anchor="w")
        self.marco_amigo = ttk.Frame(m, padding=(24, 4, 0, 8))
        self.marco_amigo.pack(fill="x")
        ttk.Label(self.marco_amigo, text=tr("Nombre:")).grid(row=0, column=0, sticky="w", pady=2)
        self.entrada_nombre = ttk.Entry(self.marco_amigo, width=30)
        self.entrada_nombre.insert(0, info["nombre"] or "")
        self.entrada_nombre.grid(row=0, column=1, sticky="w", padx=8, pady=2)
        ttk.Label(self.marco_amigo, text=tr("Servidor (opcional):")).grid(row=1, column=0, sticky="w", pady=2)
        self.entrada_srv = ttk.Entry(self.marco_amigo, width=12)
        self.entrada_srv.insert(0, info["servidor"] or "")
        self.entrada_srv.grid(row=1, column=1, sticky="w", padx=8, pady=2)
        ttk.Label(self.marco_amigo, style="Muted.TLabel", wraplength=440, justify="left", text=tr(
            "Se guardan solo sus runs, aparte de las tuyas. Su 'Mi cuenta', Fractura y bloqueos no se copian.")).grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(4, 0))

        ttk.Radiobutton(m, text=tr("Es mía: restaurar la copia (otro PC o respaldo)"), value="mia",
                        variable=self.tipo, command=self._estado).pack(anchor="w", pady=(6, 0))
        ttk.Label(m, style="Muted.TLabel", wraplength=460, justify="left", text=tr(
            "Sus archivos reemplazan a los que tengas con el mismo nombre.")).pack(anchor="w", padx=(24, 0))

        botones = ttk.Frame(m)
        botones.pack(fill="x", pady=(14, 0))
        ttk.Button(botones, text=tr("Cancelar"), command=self._cancelar).pack(side="right")
        ttk.Button(botones, text=tr("Importar"), style="Acento.TButton", command=self._aceptar).pack(
            side="right", padx=8)

        self._estado()
        self.top.grab_set()
        self.top.wait_window()

    def _estado(self):
        estado = "normal" if self.tipo.get() == "amigo" else "disabled"
        for w in (self.entrada_nombre, self.entrada_srv):
            w.configure(state=estado)

    def _aceptar(self):
        if self.tipo.get() == "amigo":
            nombre = self.entrada_nombre.get().strip()
            if not nombre:
                messagebox.showwarning(tr("Falta un dato"), tr("Escribe el nombre de tu amigo."), parent=self.top)
                return
            self.resultado = ("amigo", nombre, self.entrada_srv.get().strip())
        else:
            self.resultado = ("mia",)
        self._cancelar(guardar=True)

    def _cancelar(self, guardar=False):
        if not guardar:
            self.resultado = None
        self.top.grab_release()
        self.top.destroy()


class DialogoNombrePersonaje:
    """Personaje nuevo en afk-inventory.json: pide su nombre (el archivo trae UID y servidor, no el nombre)."""

    def __init__(self, parent, info):
        self.resultado = None
        self.top = tk.Toplevel(parent)
        self.top.title(tr("Personaje nuevo"))
        self.top.resizable(False, False)
        self.top.transient(parent)
        self.top.protocol("WM_DELETE_WINDOW", self._cancelar)

        m = ttk.Frame(self.top, padding=16)
        m.pack(fill="both", expand=True)
        ttk.Label(m, text=tr("Personaje nuevo"), style="Titulo.TLabel").pack(anchor="w")
        ttk.Label(m, wraplength=440, justify="left", text=tr(
            "Este inventario es de un personaje que la app aún no conoce:\n"
            "servidor {0} · UID {1} · nivel {2}.", info["servidor"], info["uid"], info["nivel"] or "?")).pack(
            anchor="w", pady=(4, 8))
        ttk.Label(m, style="Muted.TLabel", wraplength=440, justify="left", text=tr(
            "El archivo no trae el nombre del personaje. Escríbelo para reconocerlo en la app "
            "(si lo dejas vacío se usa la UID).")).pack(anchor="w")
        fila = ttk.Frame(m)
        fila.pack(fill="x", pady=(10, 0))
        ttk.Label(fila, text=tr("Nombre:")).pack(side="left")
        self.entrada = ttk.Entry(fila, width=32)
        self.entrada.pack(side="left", padx=8)
        self.entrada.bind("<Return>", lambda e: self._aceptar())

        botones = ttk.Frame(m)
        botones.pack(fill="x", pady=(14, 0))
        ttk.Button(botones, text=tr("Cancelar"), command=self._cancelar).pack(side="right")
        ttk.Button(botones, text=tr("Importar"), style="Acento.TButton", command=self._aceptar).pack(
            side="right", padx=8)

        self.entrada.focus_set()
        self.top.grab_set()
        self.top.wait_window()
        try:
            parent.grab_set()   # devolver el foco modal a la ventana de progreso
        except tk.TclError:
            pass

    def _aceptar(self):
        self.resultado = self.entrada.get().strip()
        self.top.grab_release()
        self.top.destroy()

    def _cancelar(self):
        self.resultado = None
        self.top.grab_release()
        self.top.destroy()


class DialogoDuenoRuns:
    """Pregunta de quién son las runs: tuyas (cuenta + servidor) o de un amigo. Modal; deja .resultado."""

    def __init__(self, parent, base_dir, analisis):
        self.base_dir = base_dir
        self.resultado = None
        self.cuentas = imp.cuentas_personales(base_dir)
        self.lista_amigos = imp.amigos(base_dir)
        a = analisis
        carpeta_sugerida = a["sugerida"] if a["sugerida"] is not None and not a["amigo"] else None
        amigo_sugerido = a["sugerida"] if a["amigo"] else None

        self.top = tk.Toplevel(parent)
        self.top.title(tr("¿De quién son estas runs?"))
        self.top.geometry("640x600")
        self.top.minsize(580, 560)
        self.top.transient(parent)
        self.top.protocol("WM_DELETE_WINDOW", self._cancelar)

        m = ttk.Frame(self.top, padding=16)
        m.pack(fill="both", expand=True)
        ttk.Label(m, text=tr("¿De quién son estas runs?"), style="Titulo.TLabel").pack(anchor="w")
        ttk.Label(m, style="Muted.TLabel", wraplength=580, justify="left", text=describir_runs(a)).pack(
            anchor="w", pady=(2, 6))
        if not a["con_ids"]:
            # una run descargada desde su página no dice de quién es: decide quien importa
            ttk.Label(m, foreground=tema.WARN, wraplength=580, justify="left", text=tr(
                "Este archivo no trae los ids de los héroes, así que la app no puede saber de quién es. "
                "Elige una opción.")).pack(anchor="w", pady=(0, 6))
            inicial = ""
        else:
            inicial = "amigo" if amigo_sugerido or not self.cuentas else "propia"
        self.tipo = tk.StringVar(value=inicial)

        # ---- tuyas
        ttk.Radiobutton(m, text=tr("Son mías"), value="propia", variable=self.tipo,
                        command=self._actualizar_estado,
                        state="normal" if self.cuentas else "disabled").pack(anchor="w")
        self.marco_propia = ttk.Frame(m, padding=(24, 4, 0, 8))
        self.marco_propia.pack(fill="x")
        ttk.Label(self.marco_propia, text=tr("Cuenta:")).grid(row=0, column=0, sticky="w", pady=2)
        self.combo_cuenta = ttk.Combobox(self.marco_propia, state="readonly", width=50,
                                         values=[c["texto"] for c in self.cuentas])
        self.combo_cuenta.grid(row=0, column=1, sticky="w", padx=8, pady=2)
        self.combo_cuenta.bind("<<ComboboxSelected>>", lambda e: self._llenar_servidores())
        ttk.Label(self.marco_propia, text=tr("Servidor:")).grid(row=1, column=0, sticky="w", pady=2)
        self.combo_servidor = ttk.Combobox(self.marco_propia, state="readonly", width=50)
        self.combo_servidor.grid(row=1, column=1, sticky="w", padx=8, pady=2)
        if not self.cuentas:
            texto = tr("Aún no tienes personajes. Importa primero el afk-inventory.json de ese personaje: "
                       "la app reconoce su UID y servidor, y después podrás elegirlo aquí.")
        elif carpeta_sugerida is not None and a["motivo"] == "fechas":
            texto = tr("✔ Sugerido: {0} · servidor {1} ({2} de estas runs ya están ahí).", a["nombre"],
                       carpeta_sugerida.name, a["ya_estan"])
        elif carpeta_sugerida is not None:
            texto = tr("✔ Sugerido: {0} · servidor {1} (los héroes de estas runs son de ese personaje).", a["nombre"],
                       carpeta_sugerida.name)
        elif amigo_sugerido is not None:
            texto = tr("Parecen de {0}: ya tienes {1} de estas runs en sus datos.", a["nombre"], a["ya_estan"])
        elif not a["con_ids"]:
            texto = tr("Elige el personaje que la jugó.")
        else:
            texto = tr("No coincide con ninguno de tus personajes: elige uno, o márcalas como de un amigo.")
        ttk.Label(self.marco_propia, text=texto, style="Muted.TLabel", wraplength=520).grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(4, 0))

        # ---- amigo
        ttk.Radiobutton(m, text=tr("Son de un amigo"), value="amigo", variable=self.tipo,
                        command=self._actualizar_estado).pack(anchor="w", pady=(6, 0))
        self.marco_amigo = ttk.Frame(m, padding=(24, 4, 0, 8))
        self.marco_amigo.pack(fill="x")
        ttk.Label(self.marco_amigo, text=tr("Nombre:")).grid(row=0, column=0, sticky="w", pady=2)
        self.combo_amigo = ttk.Combobox(self.marco_amigo, width=30, values=[a["nombre"] for a in self.lista_amigos])
        self.combo_amigo.grid(row=0, column=1, sticky="w", padx=8, pady=2)
        self.combo_amigo.bind("<<ComboboxSelected>>", lambda e: self._amigo_elegido())
        ttk.Label(self.marco_amigo, text=tr("Servidor (opcional):")).grid(row=1, column=0, sticky="w", pady=2)
        self.entrada_srv_amigo = ttk.Entry(self.marco_amigo, width=12)
        self.entrada_srv_amigo.grid(row=1, column=1, sticky="w", padx=8, pady=2)
        ttk.Label(self.marco_amigo, style="Muted.TLabel", wraplength=520, text=tr(
            "Se guardan aparte: no se mezclan con tus runs ni con 'Mi cuenta'. "
            "Las verás en el Optimizador como «Amigo: nombre».")).grid(row=2, column=0, columnspan=2, sticky="w",
                                                                       pady=(4, 0))

        # ---- simulada en la página
        ttk.Radiobutton(m, text=tr("Es una simulación de la página"), value="simulada", variable=self.tipo,
                        command=self._actualizar_estado).pack(anchor="w", pady=(6, 0))
        self.marco_simulada = ttk.Frame(m, padding=(24, 4, 0, 8))
        self.marco_simulada.pack(fill="x")
        ttk.Label(self.marco_simulada, text=tr("Nombre:")).grid(row=0, column=0, sticky="w", pady=2)
        self.entrada_simulada = ttk.Entry(self.marco_simulada, width=32)
        self.entrada_simulada.grid(row=0, column=1, sticky="w", padx=8, pady=2)
        ttk.Label(self.marco_simulada, style="Muted.TLabel", wraplength=520, text=tr(
            "Runs del simulador, no jugadas. Se guardan aparte, como «nombre (simulación)»: no se mezclan con "
            "tus runs ni con las de tus amigos.")).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))

        botones = ttk.Frame(m)
        botones.pack(fill="x", side="bottom")
        ttk.Button(botones, text=tr("Cancelar"), command=self._cancelar).pack(side="right")
        ttk.Button(botones, text=tr("Importar"), style="Acento.TButton", command=self._aceptar).pack(
            side="right", padx=8)

        self._seleccionar_sugerida(carpeta_sugerida)
        if amigo_sugerido is not None:
            i = next((i for i, x in enumerate(self.lista_amigos) if Path(x["carpeta"]) == Path(amigo_sugerido)), None)
            if i is not None:
                self.combo_amigo.current(i)
                self._amigo_elegido()
        self._actualizar_estado()

        self._parent = parent
        self.top.grab_set()
        self.top.wait_window()
        try:
            parent.grab_set()   # devolver el foco modal a la ventana de progreso
        except tk.TclError:
            pass

    # ------------------------------------------------------------
    def _seleccionar_sugerida(self, carpeta):
        i_cuenta, i_srv = 0, None
        if carpeta is not None:
            for i, c in enumerate(self.cuentas):
                for j, (srv, _) in enumerate(c["servidores"]):
                    if Path(srv) == Path(carpeta):
                        i_cuenta, i_srv = i, j
        if self.cuentas:
            self.combo_cuenta.current(i_cuenta)
            self._llenar_servidores(i_srv)

    def _llenar_servidores(self, seleccion=None):
        i = self.combo_cuenta.current()
        servidores = self.cuentas[i]["servidores"] if 0 <= i < len(self.cuentas) else []
        self.combo_servidor.configure(values=[t for _, t in servidores])
        self.combo_servidor.set("")
        if servidores:
            self.combo_servidor.current(seleccion if seleccion is not None else 0)

    def _amigo_elegido(self):
        i = self.combo_amigo.current()
        if 0 <= i < len(self.lista_amigos):
            self.entrada_srv_amigo.delete(0, "end")
            self.entrada_srv_amigo.insert(0, str(self.lista_amigos[i]["servidor"] or ""))

    def _actualizar_estado(self):
        tipo = self.tipo.get()   # "propia", "amigo", "simulada" o "" (aún no elige)
        for w in (self.combo_cuenta, self.combo_servidor):
            w.configure(state="readonly" if tipo == "propia" else "disabled")
        for w in (self.combo_amigo, self.entrada_srv_amigo):
            w.configure(state="normal" if tipo == "amigo" else "disabled")
        self.entrada_simulada.configure(state="normal" if tipo == "simulada" else "disabled")
        foco = {"propia": self.combo_servidor, "amigo": self.combo_amigo, "simulada": self.entrada_simulada}.get(tipo)
        if foco is not None:
            foco.focus_set()

    def _aceptar(self):
        try:
            if not self.tipo.get():
                raise ValueError(tr("Elige de quién es: tuya, de un amigo o una simulación de la página."))
            if self.tipo.get() == "simulada":
                self.resultado = imp.carpeta_amigo(self.base_dir, self.entrada_simulada.get(), simulada=True)
            elif self.tipo.get() == "propia":
                i, j = self.combo_cuenta.current(), self.combo_servidor.current()
                if i < 0 or j < 0:
                    raise ValueError(tr("Elige la cuenta y el servidor."))
                elegida = self.cuentas[i]["servidores"][j][0]
                activa = imp.carpeta_activa(self.base_dir, elegida)
                if Path(activa) != Path(elegida) and not messagebox.askokcancel(
                        tr("Servidor en otra cuenta"),
                        tr("Este personaje también está en una cuenta del sitio más reciente. Para no partir sus runs "
                           "en dos, se guardarán en esa:\n{0}", activa), parent=self.top):
                    return
                self.resultado = Path(activa)
            else:
                self.resultado = imp.carpeta_amigo(self.base_dir, self.combo_amigo.get(), self.entrada_srv_amigo.get())
        except ValueError as error:
            messagebox.showwarning(tr("Falta un dato"), str(error), parent=self.top)
            return
        self._cerrar()

    def _cancelar(self):
        self.resultado = None
        self._cerrar()

    def _cerrar(self):
        self.top.grab_release()
        self.top.destroy()
