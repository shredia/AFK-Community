# aplicacion/ventana_importar.py
"""Importar los archivos que descarga el sitio (afk-runs.json, afk-inventory.json) y copias .zip de la app."""
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from aplicacion import tema
from aplicacion.ventana_progreso import VentanaProgreso
from idiomas import tr
from navegador import importar as imp


def abrir_enlace(url):
    import webbrowser
    webbrowser.open(url, new=2)


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
        marco = ttk.Frame(self.top, padding=18)
        marco.pack(fill="both", expand=True)
        ttk.Label(marco, text=tr("Importar / exportar datos"), style="Titulo.TLabel").pack(anchor="w")
        ttk.Label(marco, style="Muted.TLabel", wraplength=700, justify="left",
                  text=tr("Usa los archivos que el sitio te deja descargar a mano. No hace falta iniciar sesión.")).pack(
            anchor="w", pady=(2, 12))

        # ---- importar
        caja = ttk.LabelFrame(marco, text=tr("Importar"), padding=12)
        caja.pack(fill="x")
        ttk.Label(caja, justify="left", wraplength=680, text=tr(
            "1. afk-inventory.json (primero): la captura de un personaje (recursos, héroes, colecciones, equipo, "
            "mascotas). Trae su UID y su servidor: si es nuevo, la app lo registra y te pide su nombre. "
            "Reemplaza su 'Mi cuenta' (la anterior queda como cuenta_actual.anterior.json).\n"
            "2. afk-runs.json: runs de NC. No dice de qué personaje son: eliges uno de los tuyos o un amigo. "
            "Se agregan las que faltan; a las que ya tenías se les suman las estadísticas (daño, curación, "
            "energía…). Las runs de otros modos (CR) se omiten.\n"
            "• Runs compartidas (.json de esta app): runs con el héroe del SP de cada ronda y sus estadísticas.\n"
            "• .zip: una copia exportada desde esta app.\n"
            "¿Varios personajes? Importa el afk-inventory.json de cada uno (en el sitio, haz Fetch de ese "
            "personaje y vuelve a descargarlo).")).pack(anchor="w")
        from navegador.sitio import URL_CUENTAS, URL_RUNS, URL_INVENTARIO, PASOS_DESCARGA
        donde = ttk.Frame(caja)
        donde.pack(fill="x", pady=(10, 0))
        ttk.Label(donde, text=tr(PASOS_DESCARGA), justify="left", style="Muted.TLabel").pack(side="left", anchor="w")
        botones = ttk.Frame(caja)
        botones.pack(anchor="w", pady=(10, 0))
        ttk.Button(botones, text=tr("Elegir archivo e importar..."), style="Acento.TButton",
                   command=self._elegir_e_importar).pack(side="left")
        ttk.Button(botones, text=tr("🌐 Game accounts (Fetch)"),
                   command=lambda: abrir_enlace(URL_CUENTAS)).pack(side="left", padx=(8, 4))
        ttk.Button(botones, text=tr("🌐 My runs (afk-runs.json)"),
                   command=lambda: abrir_enlace(URL_RUNS)).pack(side="left", padx=(0, 4))
        ttk.Button(botones, text=tr("🌐 Inventory (afk-inventory.json)"),
                   command=lambda: abrir_enlace(URL_INVENTARIO)).pack(side="left")

        # ---- exportar
        caja2 = ttk.LabelFrame(marco, text=tr("Exportar"), padding=12)
        caja2.pack(fill="x", pady=(14, 0))
        ttk.Label(caja2, justify="left", wraplength=680, text=tr(
            "• Copia .zip: todo lo de un servidor o de un amigo (runs, detalles, Mi cuenta, Fractura, bloqueos) "
            "para pasarlo a otro PC o tener un respaldo.\n"
            "• Runs para compartir (.json): solo las runs de NC, con el héroe que usó el SP en cada ronda y las "
            "estadísticas. Es lo que conviene mandarle a un amigo: afk-runs.json no guarda el SP.")).pack(anchor="w")
        fila2 = ttk.Frame(caja2)
        fila2.pack(fill="x", pady=(10, 0))
        self.exportables = imp.carpetas_servidor(self.base_dir) + [
            (a["carpeta"], tr("Amigo: {0} · {1} runs", a["nombre"], a["runs"])) for a in imp.amigos(self.base_dir)]
        self.combo_exportar = ttk.Combobox(fila2, state="readonly", width=48,
                                           values=[texto for _, texto in self.exportables])
        if self.exportables:
            self.combo_exportar.current(0)
        self.combo_exportar.pack(side="left")
        ttk.Button(fila2, text=tr("Exportar .zip..."), command=self._exportar,
                   state="normal" if self.exportables else "disabled").pack(side="left", padx=8)
        ttk.Button(fila2, text=tr("Exportar runs para compartir (.json)..."), command=self._exportar_runs,
                   state="normal" if self.exportables else "disabled").pack(side="left")

        # ---- qué trae cada archivo
        caja3 = ttk.LabelFrame(marco, text=tr("Qué se puede y qué no"), padding=12)
        caja3.pack(fill="both", expand=True, pady=(14, 0))
        ttk.Label(caja3, justify="left", wraplength=680, foreground=tema.MUTED, text=tr(
            "Los dos archivos comparten la ficha de cada héroe (calidad, SI, grabado, muebles, equipo y colección) "
            "y el árbol. afk-runs.json no dice qué personaje jugó las runs: por eso se pregunta al importar.\n\n"
            "No viene en los archivos y se completa con lo que ya tienes descargado del mismo héroe o mascota: "
            "rol (tanque/arquero/mago), nodos de grabado, nivel de mascota y en qué casilla va cada mueble.\n\n"
            "Special Power: si el equipo tiene un solo héroe especial (Fawkes, Thoran, Eluard…) se deduce, porque "
            "se activa solo. Si tiene dos o más, el archivo no dice cuál se eligió.")).pack(anchor="w")

        if not getattr(self.top, "incrustada", False):
            ttk.Button(marco, text=tr("Cerrar"), command=self.top.destroy).pack(anchor="e", pady=(12, 0))

    # ------------------------------------------------------------
    def _elegir_e_importar(self):
        ruta = filedialog.askopenfilename(
            parent=self.top, title=tr("Elegir archivo para importar"),
            filetypes=[(tr("Datos del sitio, runs compartidas o copia"), "*.json *.zip"), (tr("Todos"), "*.*")])
        if not ruta:
            return
        if ruta.lower().endswith(".zip") and not messagebox.askyesno(
                tr("Importar copia"), tr("Los archivos de la copia reemplazan a los que tengas con el mismo nombre "
                                         "en esas carpetas. ¿Continuar?"), parent=self.top):
            return
        prog = VentanaProgreso(self.top, "Importando", cancelable=False)

        def leer():
            try:
                prog.log(tr("Leyendo {0}...", Path(ruta).name))
                tipo, datos = imp.detectar(ruta)
                if tipo in ("runs", "runs_app"):
                    if tipo == "runs":
                        resumen = imp.resumen_runs(datos)
                        sugerida = imp.sugerir_destino_runs(self.base_dir, datos)
                    else:
                        resumen = imp.resumen_runs_app(datos)
                        sugerida = imp.sugerir_destino_runs(self.base_dir, datos.get("runs") or [])
                        prog.log(tr("Runs compartidas de {0} (con SP y estadísticas).", resumen.get("nombre") or "?"))
                    prog.log(tr("{0} runs de NC ({1} a {2}). Elige de quién son...",
                                resumen["nc"], resumen["desde"], resumen["hasta"]))
                    self.top.after(0, lambda: self._preguntar_dueno(prog, datos, resumen, sugerida, tipo))
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
                elif tipo == "copia":
                    carpetas = imp.contenido_copia(ruta)
                    prog.log(tr("La copia trae: {0}", ", ".join("/".join(c) for c in carpetas)))
                    n = imp.importar_copia(self.base_dir, ruta, prog.log)
                    prog.log(tr("{0} archivos restaurados.", n))
                else:
                    raise RuntimeError(tr("El archivo no es afk-runs.json, afk-inventory.json, runs compartidas "
                                          "ni una copia de la app."))
                self._terminar(prog)
            except Exception as error:  # noqa: BLE001
                prog.terminar(tr("Error: {0}", error), ok=False)

        threading.Thread(target=leer, daemon=True).start()

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

    def _preguntar_dueno(self, prog, runs, resumen, sugerida, tipo="runs"):
        dialogo = DialogoDuenoRuns(prog.top, self.base_dir, resumen, sugerida)
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
        self.top.after(0, self.al_terminar)

    def _exportar(self):
        i = self.combo_exportar.current()
        if i < 0:
            return
        carpeta = self.exportables[i][0]
        sugerido = f"afk-community-{carpeta.name}-{datetime.now():%Y%m%d}.zip"
        destino = filedialog.asksaveasfilename(parent=self.top, title=tr("Guardar copia"), initialfile=sugerido,
                                               defaultextension=".zip", filetypes=[("Zip", "*.zip")])
        if not destino:
            return
        prog = VentanaProgreso(self.top, "Exportando", cancelable=False)

        def trabajo():
            try:
                prog.log(tr("Comprimiendo {0}...", carpeta))
                n = imp.exportar_copia(carpeta, destino, prog.log)
                prog.terminar(tr("Copia guardada: {0} archivos en {1}", n, destino), ok=True)
            except Exception as error:  # noqa: BLE001
                prog.terminar(tr("Error: {0}", error), ok=False)

        threading.Thread(target=trabajo, daemon=True).start()

    def _exportar_runs(self):
        i = self.combo_exportar.current()
        if i < 0:
            return
        carpeta = self.exportables[i][0]
        sugerido = f"afk-community-runs-{carpeta.name}-{datetime.now():%Y%m%d}.json"
        destino = filedialog.asksaveasfilename(parent=self.top, title=tr("Guardar runs para compartir"),
                                               initialfile=sugerido, defaultextension=".json",
                                               filetypes=[("JSON", "*.json")])
        if not destino:
            return
        prog = VentanaProgreso(self.top, "Exportando", cancelable=False)

        def trabajo():
            try:
                prog.log(tr("Preparando runs de {0}...", carpeta))
                n = imp.exportar_runs(carpeta, destino, prog.log)
                prog.terminar(tr("{0} runs guardadas en {1}", n, destino), ok=True)
            except Exception as error:  # noqa: BLE001
                prog.terminar(tr("Error: {0}", error), ok=False)

        threading.Thread(target=trabajo, daemon=True).start()


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

    def __init__(self, parent, base_dir, resumen, sugerida):
        self.base_dir = base_dir
        self.resultado = None
        self.cuentas = imp.cuentas_personales(base_dir)
        self.lista_amigos = imp.amigos(base_dir)
        carpeta_sugerida, coincidencias = sugerida

        self.top = tk.Toplevel(parent)
        self.top.title(tr("¿De quién son estas runs?"))
        self.top.geometry("620x470")
        self.top.minsize(560, 440)
        self.top.transient(parent)
        self.top.protocol("WM_DELETE_WINDOW", self._cancelar)

        m = ttk.Frame(self.top, padding=16)
        m.pack(fill="both", expand=True)
        ttk.Label(m, text=tr("¿De quién son estas runs?"), style="Titulo.TLabel").pack(anchor="w")
        ttk.Label(m, style="Muted.TLabel", wraplength=580, justify="left", text=tr(
            "El archivo trae {0} runs de NC, del {1} al {2}. No dice qué personaje las jugó.",
            resumen["nc"], resumen["desde"], resumen["hasta"])).pack(anchor="w", pady=(2, 10))

        self.tipo = tk.StringVar(value="propia" if self.cuentas else "amigo")

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
        elif carpeta_sugerida is not None:
            texto = tr("Sugerido: servidor {0} ({1} de estas runs ya están ahí).", carpeta_sugerida.name, coincidencias)
        else:
            texto = tr("Ninguno de tus servidores tiene runs con estas fechas: elige uno, o márcalas como de un amigo.")
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

        botones = ttk.Frame(m)
        botones.pack(fill="x", side="bottom")
        ttk.Button(botones, text=tr("Cancelar"), command=self._cancelar).pack(side="right")
        ttk.Button(botones, text=tr("Importar"), style="Acento.TButton", command=self._aceptar).pack(
            side="right", padx=8)

        self._seleccionar_sugerida(carpeta_sugerida)
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
        propia = self.tipo.get() == "propia"
        for w in (self.combo_cuenta, self.combo_servidor):
            w.configure(state="readonly" if propia else "disabled")
        self.combo_amigo.configure(state="disabled" if propia else "normal")
        self.entrada_srv_amigo.configure(state="disabled" if propia else "normal")
        (self.combo_amigo if not propia else self.combo_servidor).focus_set()

    def _aceptar(self):
        try:
            if self.tipo.get() == "propia":
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
