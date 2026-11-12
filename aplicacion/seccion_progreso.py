# aplicacion/seccion_progreso.py
"""Progreso semanal: tu mejor tiempo total de Nightmare Corridor semana a semana (gráfico + tabla)."""
import queue
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import ttk

from aplicacion import tema
from idiomas import tr, N_


def _fecha(iso):
    try:
        return datetime.fromisoformat(str(iso).replace("Z", "+00:00")).astimezone()
    except ValueError:
        return None


def _formato(segundos):
    if segundos is None:
        return "—"
    minutos, resto = divmod(round(float(segundos), 3), 60)
    return f"{resto:.3f} s" if minutos < 1 else f"{int(minutos)}m {resto:06.3f} s"


def semanas_de(runs):
    """
    Agrupa las runs por semana de NC: misma rotación (los 6 jefes) y dentro de 7 días.
    [{"inicio": datetime, "jefes": [ids], "runs": n, "mejor": s | None, "teorico": s | None, "completas": n}]
    """
    lista = []
    for r in runs:
        f = _fecha(r.get("playedAt"))
        jefes = [str(x.get("bossId")) for x in r.get("rounds") or []]
        if f is None or not jefes:
            continue
        lista.append((f, r, frozenset(jefes), jefes))
    lista.sort(key=lambda x: x[0])
    semanas = []
    for f, r, conjunto, jefes in lista:
        actual = semanas[-1] if semanas else None
        if actual is None or actual["_conjunto"] != conjunto or (f - actual["inicio"]).days >= 7:
            actual = {"inicio": f, "_conjunto": conjunto, "jefes": sorted(conjunto, key=lambda b: (len(b), b)),
                      "runs": 0, "completas": 0, "mejor": None, "_por_jefe": {}}
            semanas.append(actual)
        actual["runs"] += 1
        res = r.get("result") or {}
        if res.get("bossesKilled") == 6 and res.get("timeMs"):
            actual["completas"] += 1
            total = res["timeMs"] / 1000
            actual["mejor"] = total if actual["mejor"] is None else min(actual["mejor"], total)
        for ronda in r.get("rounds") or []:
            rec = ronda.get("recorded") or {}
            if rec.get("bossesKilled") == 1 and rec.get("timeMs"):
                b = str(ronda.get("bossId"))
                t = rec["timeMs"] / 1000
                actual["_por_jefe"][b] = min(actual["_por_jefe"].get(b, t), t)
    for s in semanas:
        pj = s.pop("_por_jefe")
        s["teorico"] = sum(pj.values()) if len(pj) == len(s["_conjunto"]) == 6 else None
        s.pop("_conjunto")
    return semanas


class SeccionProgreso:
    def __init__(self, padre, base_dir):
        from aplicacion.ventana_optimizador import listar_servidores
        from navegador.visuales import Visuales
        self.base_dir = Path(base_dir)
        self.vis = Visuales(self.base_dir)
        self._listar = listar_servidores
        self.top = tema.ventana(padre)
        self.semanas = []
        self._cola = queue.Queue()
        self._revisar_cola()

        marco = ttk.Frame(self.top, padding=(24, 18, 24, 12))
        marco.pack(fill="both", expand=True)
        ttk.Label(marco, text=tr("Progreso semanal"), style="Titulo.TLabel").pack(anchor="w")
        ttk.Label(marco, style="Muted.TLabel", text=tr(
            "Tu mejor run completa de cada semana (línea dorada) y la suma de tus mejores tiempos por jefe esa "
            "semana (línea gris: lo que harías juntando tus mejores equipos). Cada semana tiene jefes distintos.")).pack(
            anchor="w", pady=(2, 12))
        fila = ttk.Frame(marco)
        fila.pack(fill="x", pady=(0, 10))
        ttk.Label(fila, text=tr("Runs de:")).pack(side="left")
        self.combo = ttk.Combobox(fila, state="readonly", width=50)
        self.combo.pack(side="left", padx=8)
        self.combo.bind("<<ComboboxSelected>>", lambda e: self.cargar())
        self.lbl_estado = ttk.Label(fila, text="", style="Muted.TLabel")
        self.lbl_estado.pack(side="left", padx=10)

        self.lienzo = tk.Canvas(marco, height=300, background=tema.PANEL, highlightthickness=1,
                                highlightbackground=tema.BORDE)
        self.lienzo.pack(fill="x")
        self.lienzo.bind("<Configure>", lambda e: self._dibujar())

        cols = (("semana", N_("Semana"), 110, "w"), ("jefes", N_("Jefes"), 420, "w"), ("runs", N_("Runs"), 70, "center"),
                ("mejor", N_("Mejor run completa"), 150, "center"), ("teorico", N_("Suma de tus mejores"), 150, "center"),
                ("antes", N_("Última vez con estos jefes"), 200, "center"))
        marco_tabla = ttk.Frame(marco)
        marco_tabla.pack(fill="both", expand=True, pady=(12, 0))
        self.tabla = ttk.Treeview(marco_tabla, columns=[c for c, *_ in cols], show="headings")
        for col, titulo, ancho, anchor in cols:
            self.tabla.heading(col, text=tr(titulo))
            self.tabla.column(col, width=ancho, anchor=anchor, stretch=col == "jefes")
        self.tabla.tag_configure("mejora", foreground=tema.OK)
        self.tabla.tag_configure("empeora", foreground=tema.WARN)
        barra = ttk.Scrollbar(marco_tabla, orient="vertical", command=self.tabla.yview)
        self.tabla.configure(yscrollcommand=barra.set)
        self.tabla.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")
        self.recargar()

    def recargar(self):
        anterior = self.combo.get()
        self.fuentes = self._listar(self.base_dir)
        self.combo.configure(values=[e for e, _ in self.fuentes])
        if not self.fuentes:
            self.lbl_estado.configure(text=tr("No hay runs descargadas ni importadas."))
            return
        nombres = [e for e, _ in self.fuentes]
        self.combo.current(nombres.index(anterior) if anterior in nombres else 0)
        self.cargar()

    def cargar(self):
        i = self.combo.current()
        if i < 0:
            return
        carpeta = self.fuentes[i][1]
        self.lbl_estado.configure(text=tr("Cargando..."), foreground=tema.INFO)

        def tarea():
            from navegador.optimizador import cargar_indice
            try:
                semanas = semanas_de(cargar_indice(carpeta)["runs"])
                error = None
            except Exception as e:   # noqa: BLE001
                semanas, error = [], str(e)
            self._cola.put(lambda: self._listo(semanas, error))
        threading.Thread(target=tarea, daemon=True).start()

    def _revisar_cola(self):
        try:
            while True:
                self._cola.get_nowait()()
        except queue.Empty:
            pass
        try:
            self.top.after(100, self._revisar_cola)
        except tk.TclError:
            pass

    def _listo(self, semanas, error):
        if error:
            self.lbl_estado.configure(text=tr("Error al cargar: {0}", error), foreground=tema.ERR)
            return
        self.semanas = semanas
        completas = [s for s in semanas if s["mejor"] is not None]
        self.lbl_estado.configure(foreground=tema.MUTED, text=tr("{0} semanas · {1} con run completa",
                                                                 len(semanas), len(completas)))
        self._llenar_tabla()
        self._dibujar()

    def _nombre_jefe(self, boss):
        return tr(self.vis.jefe(boss)[0]) if self.vis.disponible else str(boss)

    def _llenar_tabla(self):
        self.tabla.delete(*self.tabla.get_children())
        ultima = {}
        filas = []
        for s in self.semanas:
            clave = tuple(s["jefes"])
            previa = ultima.get(clave)
            antes, tag = "—", ()
            if previa is not None and previa["mejor"] is not None and s["mejor"] is not None:
                d = s["mejor"] - previa["mejor"]
                antes = tr("{0} ({1:+.3f} s)", previa["inicio"].strftime("%d/%m/%Y"), d)
                tag = ("mejora",) if d < 0 else (("empeora",) if d > 0 else ())
            if s["mejor"] is not None:
                ultima[clave] = s
            filas.append((s, antes, tag))
        for s, antes, tag in reversed(filas):   # lo más reciente arriba
            self.tabla.insert("", "end", tags=tag, values=(
                s["inicio"].strftime("%d/%m/%Y"), ", ".join(self._nombre_jefe(b) for b in s["jefes"]),
                f"{s['completas']}/{s['runs']}", _formato(s["mejor"]), _formato(s["teorico"]), antes))

    def _dibujar(self):
        c = self.lienzo
        c.delete("all")
        ancho, alto = max(c.winfo_width(), 200), max(c.winfo_height(), 200)
        datos = [s for s in self.semanas if s["mejor"] is not None or s["teorico"] is not None]
        if not datos:
            c.create_text(ancho / 2, alto / 2, text=tr("Sin runs completas todavía."), fill=tema.MUTED,
                          font=tema.FUENTE)
            return
        izq, der, arr, aba = 80, 24, 20, 40
        valores = [v for s in datos for v in (s["mejor"], s["teorico"]) if v is not None]
        vmin, vmax = min(valores), max(valores)
        margen = max(1.0, (vmax - vmin) * 0.1)
        vmin, vmax = vmin - margen, vmax + margen
        n = len(datos)
        x = lambda i: izq + (ancho - izq - der) * (i / max(1, n - 1) if n > 1 else 0.5)
        y = lambda v: arr + (alto - arr - aba) * (v - vmin) / (vmax - vmin)   # arriba = más rápido
        for k in range(5):
            v = vmin + (vmax - vmin) * k / 4
            yy = y(v)
            c.create_line(izq, yy, ancho - der, yy, fill=tema.BORDE)
            c.create_text(izq - 8, yy, text=_formato(v), anchor="e", fill=tema.MUTED, font=tema.FUENTE_PEQUENA)
        paso = max(1, n // 10)
        for i, s in enumerate(datos):
            if i % paso == 0 or i == n - 1:
                c.create_text(x(i), alto - aba + 14, text=s["inicio"].strftime("%d/%m"), fill=tema.MUTED,
                              font=tema.FUENTE_PEQUENA)
        for campo, color, grosor in (("teorico", tema.TENUE, 2), ("mejor", tema.DORADO, 3)):
            puntos = [(x(i), y(s[campo])) for i, s in enumerate(datos) if s[campo] is not None]
            if len(puntos) > 1:
                c.create_line(*[v for p in puntos for v in p], fill=color, width=grosor, smooth=False)
            for (px, py), s in zip(puntos, [s for s in datos if s[campo] is not None]):
                r = 4 if campo == "mejor" else 3
                punto = c.create_oval(px - r, py - r, px + r, py + r, fill=color, outline=tema.PANEL)
                texto = tr("{0} · {1}: {2}", s["inicio"].strftime("%d/%m/%Y"),
                           tr("mejor run") if campo == "mejor" else tr("suma de mejores"), _formato(s[campo]))
                c.tag_bind(punto, "<Enter>", lambda e, t=texto, px=px, py=py: self._globo(t, px, py))
                c.tag_bind(punto, "<Leave>", lambda e: c.delete("globo"))
        c.create_text(izq, 10, anchor="w", fill=tema.MUTED, font=tema.FUENTE_PEQUENA,
                      text=tr("↑ más rápido"))

    def _globo(self, texto, x, y):
        c = self.lienzo
        c.delete("globo")
        t = c.create_text(x + 10, y - 14, text=texto, anchor="w", fill=tema.TEXTO, font=tema.FUENTE_PEQUENA,
                          tags="globo")
        x1, y1, x2, y2 = c.bbox(t)
        if x2 > c.winfo_width() - 4:
            c.move(t, -(x2 - x1) - 20, 0)
            x1, y1, x2, y2 = c.bbox(t)
        fondo = c.create_rectangle(x1 - 6, y1 - 3, x2 + 6, y2 + 3, fill=tema.PANEL2, outline=tema.BORDE, tags="globo")
        c.tag_raise(t, fondo)
