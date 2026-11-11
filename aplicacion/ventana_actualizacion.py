# aplicacion/ventana_actualizacion.py
"""Actualizaciones desde GitHub: token (llavero de Windows), buscar versión nueva e instalarla."""
import threading
import tkinter as tk
import webbrowser
from tkinter import ttk, messagebox

from navegador import actualizador as act
from aplicacion.ventana_progreso import VentanaProgreso
from aplicacion import tema
from idiomas import tr

URL_TOKEN = "https://github.com/settings/personal-access-tokens/new"


def instalar(parent, info, al_terminar=None):
    """Descarga e instala la versión `info` mostrando el progreso; ofrece reiniciar al terminar."""
    if act.es_copia_desarrollo():
        messagebox.showinfo(tr("Actualizar"), tr(
            "Esta carpeta es tu copia de desarrollo (tiene .git), así que no se sobrescribe.\n"
            "Aquí se actualiza con «git pull». Las demás instalaciones sí se actualizan solas."), parent=parent)
        return
    if not messagebox.askyesno(tr("Actualizar"), tr(
            "¿Instalar la versión {0}?\n\nSe guarda una copia del código actual en respaldos/. "
            "Tus datos (cuentas, sesión, guías, Fractura) no se tocan.", info["version"]), parent=parent):
        return
    prog = VentanaProgreso(parent, tr("Actualizando"), cancelable=False)

    def trabajo():
        try:
            act.aplicar(info, progreso=prog.log)
            parent.after(0, lambda: listo(True, ""))
        except Exception as error:   # noqa: BLE001  (se muestra el mensaje y se sigue)
            mensaje = str(error).splitlines()[0] if str(error) else error.__class__.__name__
            parent.after(0, lambda: listo(False, mensaje))

    def listo(ok, mensaje):
        prog.terminar(tr("✓ Versión {0} instalada.", info["version"]) if ok else tr("✗ {0}", mensaje), ok=ok)
        if ok:
            if al_terminar:
                al_terminar()
            if messagebox.askyesno(tr("Actualizar"), tr("Listo. ¿Reiniciar la aplicación ahora?"), parent=parent):
                act.reiniciar()
                parent.winfo_toplevel().destroy()
    threading.Thread(target=trabajo, daemon=True).start()


class VentanaActualizacion:
    def __init__(self, parent, base_dir, al_cambiar=None):
        self.parent = parent
        self.base_dir = base_dir
        self.al_cambiar = al_cambiar
        self.info = None
        self.top = tk.Toplevel(parent)
        self.top.title(tr("Actualizaciones"))
        self.top.geometry("640x470")
        self.top.transient(parent)
        self._crear()
        self._refrescar()

    def _crear(self):
        t = self.top
        ttk.Label(t, text=tr("Actualizaciones"), style="Titulo.TLabel").pack(anchor="w", padx=16, pady=(14, 2))
        self.lbl_version = ttk.Label(t, text="")
        self.lbl_version.pack(anchor="w", padx=16)
        self.lbl_estado = ttk.Label(t, text="", wraplength=600, justify="left")
        self.lbl_estado.pack(anchor="w", padx=16, pady=(8, 4))
        botones = ttk.Frame(t)
        botones.pack(fill="x", padx=16, pady=4)
        self.btn_buscar = ttk.Button(botones, text=tr("Buscar ahora"), command=self._buscar)
        self.btn_buscar.pack(side="left")
        self.btn_instalar = ttk.Button(botones, text=tr("Instalar"), style="Acento.TButton", state="disabled",
                                       command=lambda: instalar(self.top, self.info, self.al_cambiar))
        self.btn_instalar.pack(side="left", padx=8)

        marco = ttk.LabelFrame(t, text=tr(" Token de GitHub (opcional) "), padding=10)
        marco.pack(fill="x", padx=16, pady=12)
        ttk.Label(marco, style="Muted.TLabel", wraplength=580, justify="left", text=tr(
            "Solo hace falta si el repositorio es privado (si es público, déjalo vacío). Para crearlo:\n"
            "1. Abre la página de tokens (botón de abajo) → «Fine-grained token».\n"
            "2. Repository access: «Only select repositories» → shredia/NC.\n"
            "3. Permissions → Repository → Contents: «Read-only». Nada más.\n"
            "4. Genera el token, cópialo y pégalo aquí. Se guarda en el llavero de Windows, no en un archivo.")
        ).pack(anchor="w")
        fila = ttk.Frame(marco)
        fila.pack(fill="x", pady=(8, 0))
        self.var_token = tk.StringVar()
        ttk.Entry(fila, textvariable=self.var_token, show="•", width=48).pack(side="left")
        ttk.Button(fila, text=tr("Guardar"), command=self._guardar_token).pack(side="left", padx=6)
        ttk.Button(fila, text=tr("Quitar"), command=self._quitar_token).pack(side="left")
        ttk.Button(marco, text=tr("Abrir la página de tokens de GitHub"),
                   command=lambda: webbrowser.open(URL_TOKEN)).pack(anchor="w", pady=(8, 0))
        self.lbl_token = ttk.Label(marco, text="", style="Muted.TLabel")
        self.lbl_token.pack(anchor="w", pady=(6, 0))
        ttk.Button(t, text=tr("Cerrar"), command=self.top.destroy).pack(side="right", padx=16, pady=(0, 12))

    def _refrescar(self):
        desarrollo = act.es_copia_desarrollo()
        self.lbl_version.configure(text=tr("Versión instalada: {0}", act.version_local())
                                   + (tr("  ·  copia de desarrollo (git)") if desarrollo else ""))
        tiene = bool(act.leer_token())
        self.lbl_token.configure(text=tr("✓ Token guardado en el llavero de Windows.") if tiene
                                 else tr("Sin token (no hace falta si el repositorio es público)."),
                                 foreground=tema.OK if tiene else tema.MUTED)

    def _guardar_token(self):
        token = self.var_token.get().strip()
        if not token:
            return
        act.guardar_token(token)
        self.var_token.set("")
        self._refrescar()
        self._buscar()

    def _quitar_token(self):
        act.guardar_token(None)
        self._refrescar()

    def _buscar(self):
        self.lbl_estado.configure(text=tr("Buscando en GitHub…"), foreground=tema.TEXTO)
        self.btn_instalar.configure(state="disabled")

        def trabajo():
            try:
                ultima = act.ultima_version()
                self.top.after(0, lambda: self._mostrar(ultima, None))
            except Exception as error:   # noqa: BLE001
                self.top.after(0, lambda: self._mostrar(None, str(error).splitlines()[0]))
        threading.Thread(target=trabajo, daemon=True).start()

    def _mostrar(self, ultima, error):
        if error:
            self.lbl_estado.configure(text=tr("✗ {0}", error), foreground=tema.ERR)
            return
        if not ultima:
            self.lbl_estado.configure(text=tr("Aún no hay versiones publicadas en GitHub."), foreground=tema.MUTED)
            return
        if act.es_mas_nueva(ultima["version"], act.version_local()):
            self.info = ultima
            texto = tr("⬆ Hay una versión nueva: {0}", ultima["version"])
            if ultima.get("notas"):
                texto += "\n\n" + ultima["notas"][:600]
            self.lbl_estado.configure(text=texto, foreground=tema.DORADO)
            self.btn_instalar.configure(state="normal")
        else:
            self.lbl_estado.configure(text=tr("✓ Tienes la última versión ({0}).", ultima["version"]),
                                      foreground=tema.OK)
