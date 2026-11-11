# aplicacion/vistas_fractura.py
"""
Vistas con íconos de la Fractura temporal (como en el juego):
  - VistaPisos:   "Recompensas de Fuerza defensiva": cada piso con sus fichas, ✓ en lo obtenido,
                  velo en lo bloqueado y la meta del viernes resaltada.
  - VistaCofres:  cada cofre (R1, R2, R3) con sus opciones; clic = elegir 1, clic derecho = más opciones.
  - VistaResumen: una tarjeta por recurso con lo que tienes en la bolsa, lo conseguido y lo que tendrás.

Los íconos salen, en orden, de: CDN (héroes de la tienda), tu bolsa (imágenes ya descargadas al sincronizar),
assets/capturas/ (recortes de capturas del juego) o el catálogo de héroes.
"""
import json
import tkinter as tk
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageTk

from idiomas import tr
from navegador.rutas import carpeta_capturas

# Colores tipo pergamino, como las pantallas del juego
PAPEL = "#f0e1c2"
FILA = "#dcc59a"
FILA_LOGRADA = "#d6c08f"
FILA_META = "#f5df9c"
FILA_BLOQ = "#e3d3b4"
TINTA = "#4a2f17"
TINTA_SUAVE = "#7a5a3a"
VERDE = "#4f8a2a"

# Marco de cada recurso según su "calidad" en el juego: (fondo, borde)
MARCOS = {"azul": ("#24477d", "#7fb4ff"), "morado": ("#3e2466", "#b77cff"), "dorado": ("#5e4012", "#f0c25a"),
          "rojo": ("#6b1c1c", "#ff7a62"), "marron": ("#3a2a1a", "#b08a55")}
MARCO_RECURSO = {
    "Tiradas normales": "azul", "Piedra de alma poco común": "azul", "Polvo azul (M)": "morado",
    "Polvo morado": "morado", "Emblema primordial": "morado", "Esencia retorcida": "morado",
    "Piedra de héroe de élite": "morado", "Cofre plateado": "morado", "Martillos": "morado",
    "Grabados rojos": "rojo", "Cofres rojos": "rojo", "Medallas": "marron", "Monedas Poe": "marron",
    "Cebos": "marron", "Oro (M)": "marron",
}


def _fuente(tam, negrita=True):
    for nombre in (("segoeuib.ttf", "arialbd.ttf") if negrita else ("segoeui.ttf", "arial.ttf")):
        try:
            return ImageFont.truetype(nombre, tam)
        except OSError:
            continue
    return ImageFont.load_default()


def texto_cantidad(nombre, n):
    if n is None:
        return ""
    if isinstance(n, float) and n.is_integer():
        n = int(n)
    if str(nombre).endswith("(M)"):
        return f"{n}M"
    if isinstance(n, (int, float)) and n >= 100000:
        return f"{n / 1000:.0f}K"
    return str(n)


def _fmt(n):
    if n is None:
        return "—"
    if isinstance(n, float):
        return f"{n:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{n:,}".replace(",", ".")


class Fichas:
    """Dibuja las fichas (ícono + marco + cantidad) y las guarda en caché."""

    def __init__(self, ventana):
        self.v = ventana
        self._cache = {}
        self._bases = {}
        self._catalogo = None

    def limpiar(self):
        # las imágenes que están en pantalla se conservan hasta el próximo dibujo
        self._viejas = list(self._cache.values())
        self._cache = {}
        self._bases = {}

    # ---- de dónde sale cada ícono
    def _ruta_asset(self, url):
        return self.v.base_dir / "assets" / Path(*url.lstrip("/").split("/")) if url else None

    def _imagen_base(self, nombre):
        if nombre in self._bases:
            return self._bases[nombre]
        from navegador import cdn
        from navegador.fractura import imagen_bolsa
        base, cuenta = self.v.base, getattr(self.v, "cuenta", None) or {}
        resultado = (None, None)
        # 1) héroes de la tienda: ícono del juego desde el CDN
        for t in base.get("tiendas", []):
            for o in t["objetos"]:
                if o["objeto"] == nombre and o.get("cdn_id"):
                    ruta = cdn.icono_unidad(self.v.base_dir, o["cdn_id"])
                    if ruta:
                        resultado = (Image.open(ruta).convert("RGBA"), "heroe")
        # 2) objeto de la bolsa elegido solo para el ícono (T2/T3/T4) o 3) el objeto vinculado
        if resultado[0] is None:
            url = None
            ident = (base.get("iconos") or {}).get(nombre)
            if ident:
                url = next((o.get("imageUrl") for o in (cuenta.get("objetos") or []) if str(o.get("id")) == str(ident)),
                           None)
            url = url or imagen_bolsa(cuenta, base, nombre, self.v.base_dir)
            ruta = self._ruta_asset(url)
            if ruta and ruta.is_file():
                resultado = (Image.open(ruta).convert("RGBA"), "icono")
        # 4) recortes de capturas del juego
        if resultado[0] is None:
            carpeta = carpeta_capturas(self.v.base_dir)
            if nombre == "Medallas" and (carpeta / "_medalla.png").exists():
                resultado = (Image.open(carpeta / "_medalla.png").convert("RGBA"), "icono")
            elif (carpeta / f"{nombre}__ficha.png").exists():   # versión sin el contador de la tienda
                resultado = (Image.open(carpeta / f"{nombre}__ficha.png").convert("RGBA"), "ficha")
            elif (carpeta / f"{nombre}.png").exists():
                resultado = (Image.open(carpeta / f"{nombre}.png").convert("RGBA"), "ficha")
        # 5) catálogo de héroes
        if resultado[0] is None:
            if self._catalogo is None:
                try:
                    self._catalogo = {h["name"]: h.get("imageUrl") for h in json.loads(
                        (self.v.base_dir / "assets" / "heroes_catalogo.json").read_text(encoding="utf-8"))}
                except (OSError, json.JSONDecodeError):
                    self._catalogo = {}
            ruta = self._ruta_asset(self._catalogo.get(nombre))
            if ruta and ruta.is_file():
                resultado = (Image.open(ruta).convert("RGBA"), "heroe")
        self._bases[nombre] = resultado
        return resultado

    # ---- dibujo
    def ficha(self, nombre, cantidad=None, tam=60, estado="", resaltar=False):
        clave = (nombre, cantidad, tam, estado, resaltar)
        if clave in self._cache:
            return self._cache[clave]
        img, tipo = self._imagen_base(nombre)
        im = Image.new("RGBA", (tam, tam), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        r = max(4, int(tam * 0.12))
        if img is not None and tipo == "ficha":
            im.alpha_composite(img.resize((tam, tam), Image.LANCZOS))
        else:
            fondo, borde = MARCOS.get(MARCO_RECURSO.get(nombre, "dorado"))
            if tipo == "heroe":
                fondo, borde = "#3a2410", "#f0c25a"
            d.rounded_rectangle((1, 1, tam - 2, tam - 2), radius=r, fill=fondo, outline=borde, width=max(2, tam // 22))
            d.rounded_rectangle((4, 4, tam - 5, tam - 5), radius=max(2, r - 3), outline=(255, 255, 255, 50), width=1)
            if img is not None:
                lado = int(tam * (0.88 if tipo == "heroe" else 0.78))
                foto = img.copy()
                foto.thumbnail((lado, lado), Image.LANCZOS)
                im.alpha_composite(foto, ((tam - foto.width) // 2, (tam - foto.height) // 2))
                if tipo == "heroe":
                    d.rounded_rectangle((1, 1, tam - 2, tam - 2), radius=r, outline="#f0c25a", width=max(2, tam // 22))
            else:
                f = _fuente(max(8, tam // 7))
                d.multiline_text((tam / 2, tam / 2), "\n".join(nombre.split()[:3]), font=f, fill="white",
                                 anchor="mm", align="center")
        d = ImageDraw.Draw(im)
        if nombre in ("T2", "T3", "T4"):
            d.text((5, tam - 5), nombre, font=_fuente(max(9, tam // 5)), fill="white", anchor="ls",
                   stroke_width=2, stroke_fill="#1a0c08")
        texto = texto_cantidad(nombre, cantidad)
        if texto:
            f = _fuente(max(9, int(tam * 0.24)))
            if tipo == "ficha":   # tapa el número que trae la captura
                d.rectangle((3, int(tam * 0.70), tam - 4, tam - 4), fill=(30, 18, 10, 150))
            d.text((tam - 4, tam - 3), texto, font=f, fill="white", anchor="rs", stroke_width=2, stroke_fill="#1a0c08")
        if estado == "logrado":
            w = max(3, tam // 10)
            pts = [(tam * 0.22, tam * 0.50), (tam * 0.42, tam * 0.70), (tam * 0.80, tam * 0.28)]
            d.line(pts, fill="#1d3a0c", width=w + 4, joint="curve")
            d.line(pts, fill="#b5f27a", width=w, joint="curve")
        elif estado == "bloqueado":
            velo = Image.new("RGBA", (tam, tam), (240, 225, 195, 120))
            im = Image.alpha_composite(im, velo)
        if resaltar:
            d = ImageDraw.Draw(im)
            d.rounded_rectangle((0, 0, tam - 1, tam - 1), radius=r, outline="#ffd447", width=3)
        foto = ImageTk.PhotoImage(im)
        self._cache[clave] = foto
        return foto


class _Lienzo:
    """Canvas con barra vertical y rueda del mouse."""

    def __init__(self, padre, fondo=PAPEL):
        self.marco = tk.Frame(padre, background=fondo)
        self.canvas = tk.Canvas(self.marco, background=fondo, highlightthickness=0)
        sb = tk.Scrollbar(self.marco, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=sb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.canvas.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", self._rueda))
        self.canvas.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))
        self.canvas.bind("<Map>", lambda e: self.canvas.after_idle(self.dibujar))
        self.info = tk.Label(padre, text="", background=fondo, foreground=TINTA, anchor="w",
                             font=("Segoe UI", 9))

    def _rueda(self, e):
        self.canvas.yview_scroll(int(-e.delta / 120) * 3, "units")

    def pack(self, **kw):
        self.info.pack(side="bottom", fill="x")
        self.marco.pack(**kw)

    def pack_forget(self):
        self.marco.pack_forget()
        self.info.pack_forget()

    def tooltip(self, item, texto):
        self.canvas.tag_bind(item, "<Enter>", lambda e: self.info.configure(text=texto))
        self.canvas.tag_bind(item, "<Leave>", lambda e: self.info.configure(text=""))


# ============================================================
# Recompensas por piso
# ============================================================

class VistaPisos(_Lienzo):
    TAM = 58

    def __init__(self, padre, ventana, fichas):
        super().__init__(padre)
        self.v, self.fichas = ventana, fichas
        self._ultimo_piso = None
        self.canvas.bind("<Configure>", lambda e: self.dibujar())

    def dibujar(self):
        c = self.canvas
        calc = getattr(self.v, "calc", None)
        if not calc or c.winfo_width() < 50:
            return
        c.delete("all")
        ancho = max(c.winfo_width(), 700)
        piso, meta = calc["piso"], (calc.get("meta") or {}).get("piso", 0)
        tam, paso, alto = self.TAM, self.TAM + 8, self.TAM + 22
        y, y_actual, banner = 10, 0, False
        for p in self.v.base["pisos"]:
            n = p["piso"]
            logrado, en_meta = n <= piso, piso < n <= meta
            if not logrado and not banner:
                banner = True
                c.create_rectangle(20, y + 4, ancho - 20, y + 30, fill="#efe0bd", outline="#cdb27c")
                c.create_text(ancho / 2, y + 17, text=tr("◆  Desbloquea para obtener recompensas  ◆"), fill=TINTA,
                              font=("Segoe UI Semibold", 11))
                y += 40
            fondo = FILA_LOGRADA if logrado else (FILA_META if en_meta else FILA_BLOQ)
            fila = c.create_rectangle(14, y, ancho - 14, y + alto - 6, fill=fondo,
                                      outline="#c9a86a" if not en_meta else "#e0a92a", width=1 if not en_meta else 2)
            c.create_text(50, y + (alto - 6) / 2, text=tr("Piso\n{0}", n), fill=TINTA, justify="center",
                          font=("Segoe UI Semibold", 12))
            x = 96
            estado = "logrado" if logrado else ("" if en_meta else "bloqueado")
            for nombre, cant in p["recompensas"].items():
                foto = self.fichas.ficha(nombre, cant, tam, estado)
                item = c.create_image(x, y + 8, image=foto, anchor="nw")
                self.tooltip(item, tr("Piso {0}: {1} ×{2}", n, nombre, _fmt(cant)))
                x += paso
            if logrado:
                txt, color = tr("✓ OBTENIDO"), VERDE
            elif en_meta:
                txt, color = tr("🎯 Meta del viernes"), "#a86a00"
            else:
                txt, color = tr("Bloqueado"), TINTA_SUAVE
            c.create_text(ancho - 30, y + (alto - 6) / 2, text=txt, fill=color, anchor="e",
                          font=("Segoe UI Semibold", 10))
            for item in (fila,):
                c.tag_bind(item, "<Button-3>", lambda e, n=n: self._menu(e, n))
            if n == piso or (piso == 0 and n == 5):
                y_actual = y
            y += alto
        c.configure(scrollregion=(0, 0, ancho, y + 10))
        if self._ultimo_piso != piso:
            self._ultimo_piso = piso
            c.yview_moveto(max(0, (y_actual - 120) / max(1, y + 10)))
        self.info.configure(text=tr("Clic derecho en un piso: marcarlo como tu piso actual o como meta del viernes."))

    def _menu(self, e, n):
        m = tk.Menu(self.canvas, tearoff=0)
        m.add_command(label=tr("Estoy en el piso {0}", n), command=lambda: self.v.fijar_piso(n))
        m.add_command(label=tr("Meta del viernes: piso {0}", n), command=lambda: self.v.fijar_meta(n))
        m.tk_popup(e.x_root, e.y_root)


# ============================================================
# Cofres de elección (R1, R2, R3)
# ============================================================

class VistaCofres(_Lienzo):
    TAM = 70

    def __init__(self, padre, ventana, fichas):
        super().__init__(padre)
        self.v, self.fichas = ventana, fichas
        self._botones = []
        self.canvas.bind("<Configure>", lambda e: self.dibujar())

    def dibujar(self):
        c = self.canvas
        calc = getattr(self.v, "calc", None)
        if not calc or c.winfo_width() < 50:
            return
        c.delete("all")
        for b in self._botones:
            b.destroy()
        self._botones = []
        ancho = max(c.winfo_width(), 700)
        y = 12
        for i, (nombre, opciones) in enumerate(self.v.base.get("cofres", {}).items(), start=1):
            info = calc["cofres"].get(nombre, {})
            elegidos = (self.v.estado.get("cofres") or {}).get(nombre) or {}
            alto = 120 + self.TAM + 40
            c.create_rectangle(14, y, ancho - 14, y + alto, fill="#f6ead0", outline="#c9a86a", width=2)
            # cabecera: el cofre y sus cuentas
            c.create_image(30, y + 14, image=self.fichas.ficha(nombre, None, 84), anchor="nw")
            c.create_text(130, y + 22, anchor="w", fill=TINTA, font=("Segoe UI Semibold", 13),
                          text=tr("Cofre de la Fractura Temporal R{0}", i))
            libres = info.get("libres", 0)
            lineas = tr("Conseguidos {0} · por conseguir {1} · elegidos {2} · ya gastados {3} · planeados {4}",
                        info.get("disponibles", 0), info.get("restantes", 0), info.get("usados_ahora", 0),
                        info.get("gastados", 0), info.get("usados_planeados", 0))
            c.create_text(130, y + 48, anchor="w", fill=TINTA_SUAVE, font=("Segoe UI", 10), text=lineas)
            if libres > 0:
                c.create_text(130, y + 70, anchor="w", fill="#b05a00", font=("Segoe UI Semibold", 10),
                              text=tr("¡{0} sin abrir! Clic en una opción para elegirla.", libres))
            elif libres < 0:
                c.create_text(130, y + 70, anchor="w", fill="#b02020", font=("Segoe UI Semibold", 10),
                              text=tr("Marcaste {0} más de los que tienes.", -libres))
            if info.get("hasta_meta"):
                c.create_text(130, y + 90, anchor="w", fill="#a86a00", font=("Segoe UI", 10),
                              text=tr("+{0} hasta la meta del viernes", info["hasta_meta"]))
            for texto, cmd in ((tr("Ya me gasté los que faltan"), lambda n=nombre: self.v._gastar_restantes(n)),
                               (tr("− gastado"), lambda n=nombre: self.v._poner_gastados(
                                   n, self.v.calc["cofres"][n]["gastados"] - 1)),
                               (tr("+ gastado"), lambda n=nombre: self.v._poner_gastados(
                                   n, self.v.calc["cofres"][n]["gastados"] + 1))):
                b = tk.Button(c, text=texto, command=cmd, relief="groove", background="#e8d3a6",
                              activebackground="#f0dcb0", foreground=TINTA, font=("Segoe UI", 9))
                self._botones.append(b)
            x_b = ancho - 30
            for b in reversed(self._botones[-3:]):
                c.create_window(x_b, y + 22, window=b, anchor="e")
                x_b -= b.winfo_reqwidth() + 8
            # opciones
            x, yo = 40, y + 112
            paso = self.TAM + 54
            for op, cant in opciones.items():
                e = elegidos.get(op) or {}
                a, p = int(e.get("ahora") or 0), int(e.get("planeado") or 0)
                foto = self.fichas.ficha(op, cant, self.TAM, resaltar=bool(a or p))
                item = c.create_image(x + 27, yo, image=foto, anchor="nw")
                c.tag_bind(item, "<Button-1>", lambda ev, n=nombre, o=op: self.v.cambiar_cofre(n, o, "ahora", 1))
                c.tag_bind(item, "<Button-3>", lambda ev, n=nombre, o=op: self._menu(ev, n, o))
                self.tooltip(item, tr("{0} ×{1} por cofre · clic: elegir 1 · clic derecho: más opciones", op, _fmt(cant)))
                c.create_text(x + 27 + self.TAM / 2, yo + self.TAM + 10, fill=TINTA, font=("Segoe UI", 9),
                              text=(tr("Ya {0}", a) if a else "") + ("  " if a and p else "") +
                              (tr("Plan {0}", p) if p else ""))
                if a or p:
                    c.create_text(x + 27 + self.TAM / 2, yo + self.TAM + 25, fill=VERDE, font=("Segoe UI Semibold", 9),
                                  text=f"→ {_fmt((a + p) * cant)}")
                x += paso
            y += alto + 14
        c.configure(scrollregion=(0, 0, ancho, y))

    def _menu(self, e, nombre, op):
        info = self.v.calc["cofres"][nombre]
        elegido = ((self.v.estado.get("cofres") or {}).get(nombre) or {}).get(op) or {}
        a, p = int(elegido.get("ahora") or 0), int(elegido.get("planeado") or 0)
        libres = info.get("libres", 0)
        por_planear = info.get("restantes", 0) - info.get("usados_planeados", 0)
        m = tk.Menu(self.canvas, tearoff=0)
        m.add_command(label=tr("Elegir 1 (de los que tengo)"), state="normal" if libres > 0 else "disabled",
                      command=lambda: self.v.cambiar_cofre(nombre, op, "ahora", 1))
        m.add_command(label=tr("Elegir todos los que tengo aquí ({0})", libres), state="normal" if libres > 0 else "disabled",
                      command=lambda: self.v.cambiar_cofre(nombre, op, "ahora", libres))
        m.add_command(label=tr("Quitar 1 elegido"), state="normal" if a else "disabled",
                      command=lambda: self.v.cambiar_cofre(nombre, op, "ahora", -1))
        m.add_separator()
        m.add_command(label=tr("Planear 1 (de los que faltan)"), state="normal" if por_planear > 0 else "disabled",
                      command=lambda: self.v.cambiar_cofre(nombre, op, "planeado", 1))
        m.add_command(label=tr("Planear todos los que faltan aquí ({0})", por_planear),
                      state="normal" if por_planear > 0 else "disabled",
                      command=lambda: self.v.cambiar_cofre(nombre, op, "planeado", por_planear))
        m.add_command(label=tr("Quitar plan"), state="normal" if p else "disabled",
                      command=lambda: self.v.cambiar_cofre(nombre, op, "planeado", -p))
        m.tk_popup(e.x_root, e.y_root)


# ============================================================
# Recursos: lo que tienes y lo que tendrás
# ============================================================

class VistaResumen(_Lienzo):
    """Plan de tu bolsa: lo que tienes + lo que llegará de pisos, cofres planeados y compras planeadas."""
    TAM = 64
    ANCHO_TARJETA = 300
    ALTO_TARJETA = 150
    ALTO_CABECERA = 112

    def __init__(self, padre, ventana, fichas):
        super().__init__(padre)
        self.v, self.fichas = ventana, fichas
        self.canvas.bind("<Configure>", lambda e: self.dibujar())

    def _filas(self):
        calc = self.v.calc
        claves = set()
        for op in self.v.base.get("cofres", {}).values():
            claves |= set(op)
        for t in self.v.base.get("tiendas", []):
            claves |= {o["objeto"] for o in t["objetos"]}

        def con_plan(x):
            return bool(x["cofres_planeado"] or x["tienda_planeado"])
        filas = sorted(calc["recursos"].items(),
                       key=lambda kv: (not con_plan(kv[1]), kv[0] not in claves, kv[0].lower()))
        if getattr(self.v, "var_solo_clave", None) is not None and self.v.var_solo_clave.get():
            filas = [f for f in filas if f[0] in claves]
        return filas

    def _cabecera(self, c, ancho, calc):
        """Resumen del plan: medallas que sobran y cofres sin destino."""
        c.create_rectangle(14, 10, ancho - 14, 10 + self.ALTO_CABECERA - 12, fill="#efdcb2", outline="#c9a86a")
        c.create_text(30, 30, anchor="w", text=tr("📦 Plan de tu bolsa"), fill=TINTA, font=("Segoe UI Semibold", 13))
        m = calc["medallas"]
        c.create_image(30, 46, image=self.fichas.ficha("Medallas", None, 44), anchor="nw")
        meta = (calc.get("meta") or {}).get("piso") or calc["piso"]
        sobran = m["saldo_meta"]
        c.create_text(30 + 200, 30, anchor="w", fill=TINTA_SUAVE, font=("Segoe UI", 10),
                      text=tr("hasta el piso {0} (tu meta)", meta))
        c.create_text(82, 56, anchor="w", fill=TINTA, font=("Segoe UI", 10),
                      text=tr("Ahora {0} · pisos hasta el {1}: +{2} · compras planeadas −{3}",
                              _fmt(m["saldo"]), meta, _fmt(m["hasta_meta"]), _fmt(m["planeadas"])))
        c.create_text(82, 78, anchor="w", fill=VERDE if sobran >= 0 else "#b02020", font=("Segoe UI Semibold", 10),
                      text=(tr("Te sobrarán {0} medallas", _fmt(sobran)) if sobran >= 0
                            else tr("Te faltan {0} medallas en el piso {1}", _fmt(-sobran), meta))
                      + tr("  ·  al final de la Fractura: {0}", _fmt(m["saldo_final"])))
        x = max(470, ancho * 0.48)
        for nombre, info in calc["cofres"].items():
            sin_abrir = max(0, info.get("libres", 0))
            sin_plan = max(0, info.get("restantes", 0) - info.get("usados_planeados", 0))
            c.create_image(x, 44, image=self.fichas.ficha(nombre, None, 48), anchor="nw")
            c.create_text(x + 56, 56, anchor="w", fill="#b05a00" if sin_abrir else TINTA_SUAVE,
                          font=("Segoe UI Semibold" if sin_abrir else "Segoe UI", 9),
                          text=tr("{0} sin elegir", sin_abrir))
            c.create_text(x + 56, 76, anchor="w", fill="#2a4f7a" if sin_plan else TINTA_SUAVE, font=("Segoe UI", 9),
                          text=tr("{0} sin planear", sin_plan))
            x += 150

    def dibujar(self):
        c = self.canvas
        calc = getattr(self.v, "calc", None)
        if not calc or c.winfo_width() < 50:
            return
        c.delete("all")
        ancho = max(c.winfo_width(), 600)
        self._cabecera(c, ancho, calc)
        cols = max(1, int((ancho - 20) // (self.ANCHO_TARJETA + 12)))
        tarjetas = [("Medallas", None)] + self._filas()
        meta_piso = (calc.get("meta") or {}).get("piso") or calc["piso"]
        y0 = self.ALTO_CABECERA + 4
        for k, (nombre, x) in enumerate(tarjetas):
            cx = 14 + (k % cols) * (self.ANCHO_TARJETA + 12)
            cy = y0 + (k // cols) * (self.ALTO_TARJETA + 12)
            lineas = []          # (texto, color, negrita)
            if nombre == "Medallas":
                m = calc["medallas"]
                en_bolsa = self.v.inv.get("Medallas")
                base_n = en_bolsa if en_bolsa is not None else m["saldo"]
                lineas.append((tr("En tu bolsa: {0}", _fmt(en_bolsa)) if en_bolsa is not None
                               else tr("Saldo calculado: {0}", _fmt(m["saldo"])), TINTA, False))
                if m["hasta_meta"]:
                    lineas.append((tr("🏰 + Pisos hasta el {0}: {1}", meta_piso, _fmt(m["hasta_meta"])),
                                   TINTA_SUAVE, False))
                if m["planeadas"]:
                    lineas.append((tr("🛒 − Tienda (plan): {0}", _fmt(m["planeadas"])), "#2a4f7a", False))
                total = base_n + m["hasta_meta"] - m["planeadas"]
                lineas.append((tr("= En el piso {0}: {1}", meta_piso, _fmt(total)), VERDE if total >= 0 else "#b02020",
                               True))
                if m["por_ganar"] > m["hasta_meta"]:
                    lineas.append((tr("   (+{0} más hasta el final)", _fmt(m["por_ganar"] - m["hasta_meta"])),
                                   "#9a8060", False))
                cantidad, con_plan = base_n, bool(m["planeadas"])
            else:
                bolsa = x.get("bolsa")
                if bolsa is not None:
                    lineas.append((tr("En tu bolsa: {0}", _fmt(bolsa)), TINTA, False))
                elif nombre in self.v.inv:
                    lineas.append((tr("En tu bolsa: ? (no aparece)"), TINTA_SUAVE, False))
                else:
                    lineas.append((tr("Conseguido en la Fractura: {0}", _fmt(x["conseguido"])), TINTA, False))
                if x.get("hasta_meta"):
                    lineas.append((tr("🏰 + Pisos hasta el {0}: {1}", meta_piso, _fmt(x["hasta_meta"])),
                                   TINTA_SUAVE, False))
                if x["cofres_planeado"]:
                    lineas.append((tr("🎁 + Cofres (plan): {0}", _fmt(x["cofres_planeado"])), "#2a4f7a", False))
                if x["tienda_planeado"]:
                    lineas.append((tr("🛒 + Tienda (plan): {0}", _fmt(x["tienda_planeado"])), "#2a4f7a", False))
                if x["tienda_pendiente"]:
                    lineas.append((tr("   sin planear en tienda: {0}", _fmt(x["tienda_pendiente"])), "#9a8060", False))
                if x.get("tendras") is not None:
                    lineas.append((tr("= Tendrás en el piso {0}: {1}", meta_piso, _fmt(x["tendras"])), VERDE, True))
                else:
                    lineas.append((tr("= En la Fractura al piso {0}: {1}", meta_piso,
                                      _fmt(x["conseguido"] + x["plan_meta"])), VERDE, True))
                resto = x["pisos_faltante"] - x.get("hasta_meta", 0)
                if resto:
                    lineas.append((tr("   (+{0} más en los pisos hasta el final)", _fmt(resto)), "#9a8060", False))
                cantidad = bolsa
                con_plan = bool(x["cofres_planeado"] or x["tienda_planeado"])
            rect = c.create_rectangle(cx, cy, cx + self.ANCHO_TARJETA, cy + self.ALTO_TARJETA, fill="#f6ead0",
                                      outline="#e0a92a" if con_plan else "#c9a86a", width=2 if con_plan else 1)
            foto = self.fichas.ficha(nombre, cantidad, self.TAM)
            icono = c.create_image(cx + 10, cy + 34, image=foto, anchor="nw")
            c.create_text(cx + self.TAM + 22, cy + 16, anchor="w", text=nombre, fill=TINTA,
                          font=("Segoe UI Semibold", 11))
            if con_plan:
                c.create_text(cx + self.ANCHO_TARJETA - 10, cy + 16, anchor="e", text=tr("📝 con plan"),
                              fill="#a86a00", font=("Segoe UI", 8))
            for i, (t, color, negrita) in enumerate(lineas[:7]):
                c.create_text(cx + self.TAM + 22, cy + 38 + i * 17, anchor="w", text=t, fill=color,
                              font=("Segoe UI Semibold" if negrita else "Segoe UI", 9 if not negrita else 10))
            for item in (rect, icono):
                c.tag_bind(item, "<Button-3>", lambda e, n=nombre: self._menu(e, n))
                c.tag_bind(item, "<Double-1>", lambda e, n=nombre: self.v.vincular(n))
        filas_total = (len(tarjetas) + cols - 1) // cols
        c.configure(scrollregion=(0, 0, ancho, y0 + 10 + filas_total * (self.ALTO_TARJETA + 12)))
        self.info.configure(text=tr("Plan hasta tu meta (cámbiala arriba). Primero los recursos con plan (borde "
                                    "dorado). Planifica en Cofres y Tienda. Doble clic: vincular con tu bolsa."))

    def _menu(self, e, nombre):
        m = tk.Menu(self.canvas, tearoff=0)
        m.add_command(label=tr("🔗 Vincular «{0}» con la bolsa…", nombre), command=lambda: self.v.vincular(nombre))
        m.tk_popup(e.x_root, e.y_root)
