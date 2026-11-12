# aplicacion/seccion_amigos.py
"""Amigos: las runs importadas de otros jugadores (ver, renombrar, borrar, optimizar con ellas)."""
import json
from pathlib import Path
from tkinter import ttk, messagebox, simpledialog

from aplicacion import tema
from idiomas import tr, N_


def a_la_papelera(ruta):
    """Envía una carpeta a la Papelera de reciclaje de Windows (se puede recuperar). True si lo logró."""
    import ctypes
    from ctypes import wintypes

    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [("hwnd", wintypes.HWND), ("wFunc", wintypes.UINT), ("pFrom", wintypes.LPCWSTR),
                    ("pTo", wintypes.LPCWSTR), ("fFlags", ctypes.c_uint16), ("fAnyOperationsAborted", wintypes.BOOL),
                    ("hNameMappings", ctypes.c_void_p), ("lpszProgressTitle", wintypes.LPCWSTR)]
    FO_DELETE, FOF_ALLOWUNDO, FOF_NOCONFIRMATION, FOF_SILENT, FOF_NOERRORUI = 3, 0x40, 0x10, 0x4, 0x400
    op = SHFILEOPSTRUCTW(None, FO_DELETE, str(Path(ruta).resolve()) + "\0", None,
                         FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI, False, None, None)
    try:
        return ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op)) == 0 and not Path(ruta).exists()
    except (AttributeError, OSError):
        return False


def _ultima_run(carpeta):
    try:
        runs = json.loads((Path(carpeta) / "runs.json").read_text(encoding="utf-8"))
        fechas = [str(r.get("playedAt") or "") for r in runs if isinstance(r, dict)]
        return max(fechas)[:10] if fechas else "—"
    except (OSError, json.JSONDecodeError, ValueError):
        return "—"


class SeccionAmigos:
    def __init__(self, padre, base_dir, al_cambiar=None, importar=None, comparar=None):
        self.base_dir = Path(base_dir)
        self.al_cambiar, self.importar, self.comparar = al_cambiar, importar, comparar
        self.top = tema.ventana(padre)
        self.lista = []

        marco = ttk.Frame(self.top, padding=(24, 18, 24, 12))
        marco.pack(fill="both", expand=True)
        ttk.Label(marco, text=tr("Amigos"), style="Titulo.TLabel").pack(anchor="w")
        ttk.Label(marco, style="Muted.TLabel", wraplength=1000, justify="left", text=tr(
            "Runs de NC de otros jugadores, importadas desde su afk-runs.json. El optimizador puede mezclarlas con "
            "las tuyas y te dice qué equipos más rápidos podrías copiar y qué te falta.")).pack(anchor="w", pady=(2, 12))

        botones = ttk.Frame(marco)
        botones.pack(fill="x", pady=(0, 10))
        ttk.Button(botones, text=tr("+ Importar runs de un amigo…"), style="Acento.TButton",
                   command=lambda: self.importar and self.importar()).pack(side="left")
        self.btn_optimizar = ttk.Button(botones, text=tr("▶ Optimizar con sus runs"), command=self._optimizar)
        self.btn_optimizar.pack(side="left", padx=(8, 0))
        self.btn_renombrar = ttk.Button(botones, text=tr("Renombrar…"), command=self._renombrar)
        self.btn_renombrar.pack(side="left", padx=(8, 0))
        self.btn_borrar = ttk.Button(botones, text=tr("Enviar a la papelera"), command=self._borrar)
        self.btn_borrar.pack(side="left", padx=(8, 0))
        self.lbl_estado = ttk.Label(botones, text="", style="Muted.TLabel")
        self.lbl_estado.pack(side="left", padx=12)

        cols = (("nombre", N_("Nombre"), 220, "w"), ("servidor", N_("Servidor"), 100, "center"),
                ("runs", N_("Runs"), 80, "center"), ("detalles", N_("Con detalle"), 100, "center"),
                ("ultima", N_("Última run"), 120, "center"), ("carpeta", N_("Carpeta"), 260, "w"))
        marco_tabla = ttk.Frame(marco)
        marco_tabla.pack(fill="both", expand=True)
        self.tabla = ttk.Treeview(marco_tabla, columns=[c for c, *_ in cols], show="headings")
        for col, titulo, ancho, anchor in cols:
            self.tabla.heading(col, text=tr(titulo))
            self.tabla.column(col, width=ancho, anchor=anchor, stretch=col in ("nombre", "carpeta"))
        barra = ttk.Scrollbar(marco_tabla, orient="vertical", command=self.tabla.yview)
        self.tabla.configure(yscrollcommand=barra.set)
        self.tabla.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")
        self.tabla.bind("<<TreeviewSelect>>", lambda e: self._botones())
        self.tabla.bind("<Double-1>", lambda e: self._optimizar())
        self.recargar()

    def recargar(self):
        from navegador.importar import amigos
        try:
            self.lista = amigos(self.base_dir)
        except Exception:   # noqa: BLE001
            self.lista = []
        self.tabla.delete(*self.tabla.get_children())
        for i, a in enumerate(self.lista):
            detalles = sum(1 for _ in (a["carpeta"] / "detalles").glob("*.json"))
            self.tabla.insert("", "end", iid=str(i), values=(
                a["nombre"], a["servidor"] or "—", a["runs"], detalles, _ultima_run(a["carpeta"]),
                f"_amigos/{a['carpeta'].name}"))
        self.lbl_estado.configure(text=tr("{0} amigos", len(self.lista)) if self.lista else
                                  tr("Todavía no has importado runs de amigos."))
        self._botones()

    def _elegido(self):
        sel = self.tabla.selection()
        return self.lista[int(sel[0])] if sel and int(sel[0]) < len(self.lista) else None

    def _botones(self):
        estado = "normal" if self._elegido() else "disabled"
        for b in (self.btn_optimizar, self.btn_renombrar, self.btn_borrar):
            b.configure(state=estado)

    def _optimizar(self):
        a = self._elegido()
        if a and self.comparar:
            self.comparar(a["carpeta"])

    def _renombrar(self):
        a = self._elegido()
        if not a:
            return
        nombre = simpledialog.askstring(tr("Renombrar"), tr("Nombre de tu amigo:"), initialvalue=a["nombre"],
                                        parent=self.top)
        if not nombre or not nombre.strip():
            return
        servidor = simpledialog.askstring(tr("Renombrar"), tr("Servidor (opcional):"),
                                          initialvalue=str(a["servidor"] or ""), parent=self.top)
        ficha_ruta = a["carpeta"] / f"{a['carpeta'].name}.json"
        try:
            ficha = json.loads(ficha_ruta.read_text(encoding="utf-8"))
            ficha["name"] = nombre.strip()
            if servidor is not None:
                ficha["svr_id"] = servidor.strip()
            ficha_ruta.write_text(json.dumps(ficha, ensure_ascii=False, indent=2), encoding="utf-8")
        except (OSError, json.JSONDecodeError) as error:
            messagebox.showerror(tr("Renombrar"), tr("No se pudo guardar: {0}", error), parent=self.top)
            return
        self.recargar()
        if self.al_cambiar:
            self.al_cambiar()

    def _borrar(self):
        a = self._elegido()
        if not a:
            return
        if not messagebox.askyesno(tr("Enviar a la papelera"), tr(
                "¿Enviar a la papelera las {0} runs de {1}?\nPuedes recuperarlas desde la Papelera de reciclaje.",
                a["runs"], a["nombre"]), parent=self.top):
            return
        if not a_la_papelera(a["carpeta"]):
            messagebox.showerror(tr("Enviar a la papelera"), tr("No se pudo enviar a la papelera: {0}", a["carpeta"]),
                                 parent=self.top)
            return
        self.recargar()
        if self.al_cambiar:
            self.al_cambiar()
