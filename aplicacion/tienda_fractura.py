# aplicacion/tienda_fractura.py
"""
Tienda de la Fractura temporal dibujada como en el juego: estantes con las casillas, el stock que queda
("9/9"), el precio en medallas (rojo si no te alcanza), "Vendido" y las secciones "Completa N pisos".

  Clic izquierdo   -> comprar 1
  Clic derecho     -> menú: comprar todos, deshacer, planear...
Los íconos salen de assets/capturas/<objeto>.png (recortados de capturas del juego); si falta uno,
se dibuja una casilla con el nombre.
"""
import tkinter as tk
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps, ImageTk

from idiomas import tr
from navegador.rutas import carpeta_capturas

LADO = 100           # tamaño de la casilla
PASO_X = 165         # distancia entre columnas
ALTO_FILA = 186
POR_FILA = 4
FONDO = "#3a1712"
ESTANTE = "#5b3220"
ESTANTE_LUZ = "#7a4a30"
BANDA = "#22100c"
# facción del catálogo -> ícono guardado en assets/game-ui/icon_hero_<x>.png
FACCIONES = {"Lightbearer": "human", "Mauler": "orc", "Wilder": "elf", "Graveborn": "undead", "Celestial": "god",
             "Hypogean": "devil", "Dimensional": "cross", "Draconis": "dragon"}


def _fuente(tam, negrita=True):
    for nombre in (("segoeuib.ttf", "arialbd.ttf") if negrita else ("segoeui.ttf", "arial.ttf")):
        try:
            return ImageFont.truetype(nombre, tam)
        except OSError:
            continue
    return ImageFont.load_default()


class TiendaVisual:
    def __init__(self, padre, ventana):
        """ventana: la VentanaFractura (base, estado, calc y los métodos para cambiar compras)."""
        self.v = ventana
        self.dir_iconos = carpeta_capturas(ventana.base_dir)
        self._iconos = {}
        self._fotos = []
        self.canvas = tk.Canvas(padre, background=FONDO, highlightthickness=0)
        sb = tk.Scrollbar(padre, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=sb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.canvas.bind("<Configure>", lambda e: self.dibujar())
        self.canvas.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", self._rueda))
        self.canvas.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))
        self._urls_juego = self._iconos_del_juego()

    def _iconos_del_juego(self):
        """{objeto: ruta local} de imágenes del juego ya descargadas (retratos del catálogo, inventario)."""
        import json
        from navegador.fractura import EN_INVENTARIO
        assets = self.v.base_dir / "assets"
        salida = {}

        def local(url):
            return assets.joinpath(*url.lstrip("/").split("/")) if url else None
        try:
            for h in json.loads((assets / "heroes_catalogo.json").read_text(encoding="utf-8")):
                ruta = local(h.get("imageUrl"))
                if ruta and ruta.is_file():
                    salida[h["name"]] = ("heroe", ruta, (h.get("classifications") or {}).get("faction"))
        except (OSError, json.JSONDecodeError):
            pass
        # objetos vinculados con la bolsa: su ícono del inventario (ya descargado al sincronizar)
        from navegador.fractura import imagen_bolsa
        cuenta = getattr(self.v, "cuenta", None) or {}
        from navegador import cdn
        self._unidades = {}
        for t in self.v.base.get("tiendas", []):
            for o in t["objetos"]:
                self._unidades.setdefault(o["objeto"], o.get("unidades") or 1)
                if o.get("cdn_id"):
                    # ícono del juego desde el CDN comunitario (se descarga una vez y queda en assets/cdn)
                    ruta = cdn.icono_unidad(self.v.base_dir, o["cdn_id"])
                    if ruta:
                        info = cdn.unidades(self.v.base_dir).get(str(o["cdn_id"])) or {}
                        salida[o["objeto"]] = ("heroe", ruta, info.get("faction"))
                        continue
                if o["objeto"] in salida:
                    continue
                ruta = local(imagen_bolsa(cuenta, self.v.base, o["objeto"], self.v.base_dir))
                if ruta and ruta.is_file():
                    salida[o["objeto"]] = ("objeto", ruta, None)
        return salida

    def _rueda(self, e):
        self.canvas.yview_scroll(int(-e.delta / 120) * 3, "units")

    # ---------------- imágenes ----------------

    def _icono(self, nombre):
        if nombre not in self._iconos:
            ruta = self.dir_iconos / f"{nombre}.png"
            del_juego = self._urls_juego.get(nombre)
            if del_juego:
                # 1) imagen del juego ya descargada (retrato + marco dorado, u objeto del inventario)
                tipo, archivo, faccion = del_juego
                im = Image.new("RGBA", (LADO, LADO), "#2a1a10")
                foto = Image.open(archivo).convert("RGBA")
                borde = 7 if tipo == "heroe" else 14
                foto.thumbnail((LADO - 2 * borde, LADO - 2 * borde), Image.LANCZOS)
                if tipo == "objeto":
                    # casilla de objeto: fondo violeta, borde dorado y la cantidad por compra abajo a la derecha
                    im = Image.new("RGBA", (LADO, LADO), (0, 0, 0, 0))
                    d = ImageDraw.Draw(im)
                    d.rounded_rectangle((2, 2, LADO - 3, LADO - 3), radius=10, fill="#3b2a5c", outline="#d9a640", width=4)
                    d.rounded_rectangle((7, 7, LADO - 8, LADO - 8), radius=7, outline="#f3d27a", width=1)
                    im.alpha_composite(foto, ((LADO - foto.width) // 2, (LADO - foto.height) // 2 + 4))
                    unidades = self._unidades.get(nombre, 1)
                    if unidades > 1:
                        d = ImageDraw.Draw(im)
                        d.text((LADO - 10, LADO - 10), str(unidades), font=_fuente(18), fill="white", anchor="rs",
                               stroke_width=3, stroke_fill="#1a0c08")
                else:
                    im.paste(foto, ((LADO - foto.width) // 2, (LADO - foto.height) // 2), foto)
                marco = self.v.base_dir / "assets" / "game-ui" / "n_heroframe_yellow.png"
                if tipo == "heroe" and marco.exists():
                    m = Image.open(marco).convert("RGBA").resize((LADO, LADO), Image.LANCZOS)
                    im.alpha_composite(m)
                    icono = FACCIONES.get(faccion)
                    ruta_f = self.v.base_dir / "assets" / "game-ui" / f"icon_hero_{icono}.png" if icono else None
                    if ruta_f and ruta_f.exists():
                        f = Image.open(ruta_f).convert("RGBA").resize((int(LADO * 0.3), int(LADO * 0.3)), Image.LANCZOS)
                        im.alpha_composite(f, (int(LADO * 0.015), int(LADO * 0.005)))
                unidades = self._unidades.get(nombre, 1)
                if tipo == "heroe" and unidades > 1:   # piedras de alma por compra ("60")
                    ImageDraw.Draw(im).text((LADO - 10, LADO - 9), str(unidades), font=_fuente(18), fill="white",
                                            anchor="rs", stroke_width=3, stroke_fill="#1a0c08")
            elif ruta.exists():
                # 2) recorte de la captura del juego
                im = Image.open(ruta).convert("RGBA").resize((LADO, LADO), Image.LANCZOS)
            else:
                im = Image.new("RGBA", (LADO, LADO), "#2b2440")
                d = ImageDraw.Draw(im)
                d.rounded_rectangle((1, 1, LADO - 2, LADO - 2), radius=8, outline="#b08a3e", width=3)
                f = _fuente(14)
                palabras, lineas, linea = nombre.split(), [], ""
                for p in palabras:
                    if len(linea + " " + p) > 11 and linea:
                        lineas.append(linea)
                        linea = p
                    else:
                        linea = (linea + " " + p).strip()
                lineas.append(linea)
                for i, l in enumerate(lineas):
                    d.text((LADO / 2, LADO / 2 + (i - (len(lineas) - 1) / 2) * 17), l, font=f, fill="white",
                           anchor="mm")
            self._iconos[nombre] = im
        return self._iconos[nombre]

    def _medalla(self, tam=22):
        clave = f"_medalla{tam}"
        if clave not in self._iconos:
            ruta = self.dir_iconos / "_medalla.png"
            if ruta.exists():
                im = Image.open(ruta).convert("RGBA").resize((tam, tam), Image.LANCZOS)
            else:
                im = Image.new("RGBA", (tam, tam))
                ImageDraw.Draw(im).ellipse((0, 0, tam - 1, tam - 1), fill="#3d7fd6", outline="white")
            self._iconos[clave] = ImageTk.PhotoImage(im)
        return self._iconos[clave]

    def _casilla(self, objeto, quedan, maximo, plan, bloqueada):
        vendido = quedan <= 0
        agotado = self.dir_iconos / "_agotado.png"
        if vendido and agotado.exists():
            # como en el juego: al agotarse se ve la casilla gris de "Vendido", no el ícono del objeto
            im = Image.open(agotado).convert("RGBA").resize((LADO, LADO), Image.LANCZOS)
        else:
            im = self._icono(objeto).copy()
            if vendido or bloqueada:
                gris = ImageOps.grayscale(im.convert("RGB")).convert("RGBA")
                im = ImageEnhance.Brightness(gris).enhance(0.45 if vendido else 0.6)
        d = ImageDraw.Draw(im, "RGBA")
        # contador de stock (tapa el que venía en la captura)
        d.rounded_rectangle((LADO * 0.36, 3, LADO - 6, LADO * 0.21), radius=5, fill=(25, 14, 12, 235))
        d.text((LADO * 0.68, LADO * 0.12), f"{max(0, quedan)}/{maximo}", font=_fuente(15),
               fill="#ff4d4d" if vendido else "white", anchor="mm")
        if vendido and not agotado.exists():
            d.text((LADO / 2, LADO / 2 + 6), tr("Vendido"), font=_fuente(19), fill="#ff3d7a", anchor="mm",
                   stroke_width=2, stroke_fill="#2a0b10")
        elif bloqueada:
            d.text((LADO / 2, LADO / 2 + 6), tr("Bloqueada"), font=_fuente(15), fill="#e8dcc6", anchor="mm",
                   stroke_width=2, stroke_fill="#1a0c08")
        if plan:
            d.ellipse((4, LADO - 34, 34, LADO - 4), fill="#e3b45a", outline="#3a2406", width=2)
            d.text((19, LADO - 19), f"P{plan}" if plan < 10 else str(plan), font=_fuente(13 if plan < 10 else 14),
                   fill="#1a1206", anchor="mm")
        return ImageTk.PhotoImage(im)

    # ---------------- dibujo ----------------

    def dibujar(self):
        c = self.canvas
        c.delete("all")
        self._fotos = []
        calc = getattr(self.v, "calc", None)
        if not calc:
            return
        ancho = max(c.winfo_width(), POR_FILA * PASO_X + 40)
        saldo = calc["medallas"]["saldo"]
        piso = calc["piso"]

        # barra superior: medallas
        c.create_rectangle(0, 0, ancho, 54, fill=BANDA, outline="")
        c.create_image(24, 27, image=self._medalla(30))
        c.create_text(48, 27, text=f"{saldo:,}".replace(",", "."), anchor="w", fill="white",
                      font=("Segoe UI Semibold", 17))
        plan = calc["medallas"]["planeadas"]
        c.create_text(170, 27, anchor="w", fill="#c9b79c", font=("Segoe UI", 10),
                      text=tr("medallas disponibles · {0} planeadas · {1} por ganar en pisos", f"{plan:,}".replace(",", "."),
                              f"{calc['medallas']['por_ganar']:,}".replace(",", ".")))
        c.create_text(ancho - 16, 27, anchor="e", fill="#c9b79c", font=("Segoe UI", 9),
                      text=tr("Modo comprar") if self._modo() == "comprar"
                      else tr("Modo planear (medallas futuras)"))
        y = 70
        for t in self.v.base.get("tiendas", []):
            bloqueada = piso < t.get("piso", 0)
            if t.get("piso", 0) > 1:
                c.create_rectangle(ancho * 0.12, y, ancho * 0.88, y + 30, fill=BANDA, outline="#5a2a1c")
                texto = tr("Completa {0} pisos para desbloquear", t["piso"])
                if not bloqueada:
                    texto += "  ✓"
                c.create_text(ancho / 2, y + 15, text=texto, fill="#f1e6cf" if not bloqueada else "#a08f78",
                              font=("Segoe UI Semibold", 11))
                y += 44
            objetos = t["objetos"]
            for inicio in range(0, len(objetos), POR_FILA):
                fila = list(enumerate(objetos))[inicio:inicio + POR_FILA]
                x0 = ancho / 2 - (len(fila) - 1) * PASO_X / 2
                # estante
                c.create_rectangle(10, y + LADO - 6, ancho - 10, y + LADO + 34, fill=ESTANTE, outline="")
                c.create_line(10, y + LADO - 6, ancho - 10, y + LADO - 6, fill=ESTANTE_LUZ, width=3)
                for j, (i, o) in enumerate(fila):
                    x = x0 + j * PASO_X
                    clave = f"{t['nombre']}|{i}"
                    comp = (self.v.estado.get("compras") or {}).get(clave) or {}
                    hechas, plan_o = int(comp.get("hechas") or 0), int(comp.get("planeadas") or 0)
                    quedan = o["maximo"] - hechas
                    foto = self._casilla(o.get("icono") or o["objeto"], quedan, o["maximo"], plan_o, bloqueada)
                    self._fotos.append(foto)
                    etiqueta = f"casilla:{clave}"
                    c.create_image(x, y + LADO / 2 - 10, image=foto, tags=(etiqueta, "casilla"))
                    if quedan > 0:
                        # barra de precio
                        c.create_rectangle(x - 52, y + LADO + 2, x + 52, y + LADO + 28, fill="#1d0d0a",
                                           outline="#4a2a1e")
                        c.create_image(x - 38, y + LADO + 15, image=self._medalla(22))
                        c.create_text(x + 8, y + LADO + 15, text=f"{o['precio']}",
                                      fill="#ff4040" if o["precio"] > saldo else "white",
                                      font=("Segoe UI Semibold", 12))
                    self._botones_rapidos(x, y + LADO + 36, clave, o, hechas, plan_o, bloqueada)
                    c.tag_bind(etiqueta, "<Button-1>", lambda e, k=clave, ob=o, bl=bloqueada: self._comprar(k, ob, bl))
                    c.tag_bind(etiqueta, "<Button-3>", lambda e, k=clave, ob=o, bl=bloqueada: self._menu(e, k, ob, bl))
                    c.tag_bind(etiqueta, "<Enter>", lambda e, ob=o, h=hechas, p=plan_o, t_=t:
                               self._info(ob, h, p, t_))
                    c.tag_bind(etiqueta, "<Leave>", lambda e: self.v.lbl_info_tienda.configure(text=""))
                y += ALTO_FILA
            y += 6
        c.configure(scrollregion=(0, 0, ancho, y + 10))
        c.tag_bind("casilla", "<Enter>", lambda e: c.configure(cursor="hand2"), add="+")
        c.tag_bind("casilla", "<Leave>", lambda e: c.configure(cursor=""), add="+")

    def _info(self, o, hechas, plan, t):
        texto = tr("{0} ×{1} · {2} medallas · compradas {3}/{4} · planeadas {5} · {6}",
                   o["objeto"], o["unidades"], o["precio"], hechas, o["maximo"], plan, t["nombre"])
        x = (getattr(self.v, "calc", None) or {}).get("recursos", {}).get(o["objeto"]) or {}
        if x.get("bolsa") is not None:
            texto += tr("  ·  en tu bolsa {0} → en tu meta tendrás {1}", x["bolsa"], x["tendras"])
        elif x:
            texto += tr("  ·  conseguirás {0} más", x.get("aun_obtenible", 0))
        self.v.lbl_info_tienda.configure(text=texto)

    # ---------------- acciones ----------------

    def _modo(self):
        var = getattr(self.v, "modo_tienda", None)
        return var.get() if var is not None else "comprar"

    def _boton(self, x, y, ancho, texto, color, activo, accion):
        """Botón dibujado en el lienzo (rectángulo + texto); gris y sin acción si no aplica."""
        c = self.canvas
        tag = f"btn{len(self._fotos)}_{x:.0f}_{y:.0f}_{texto}"
        relleno = color if activo else "#4a3a34"
        c.create_rectangle(x - ancho / 2, y, x + ancho / 2, y + 22, fill=relleno,
                           outline="#e8c27a" if activo else "#5a4a44", width=1, tags=(tag,))
        c.create_text(x, y + 11, text=texto, fill="white" if activo else "#9a8a80",
                      font=("Segoe UI Semibold", 10), tags=(tag,))
        if activo:
            c.tag_bind(tag, "<Button-1>", lambda e: accion())
            c.tag_bind(tag, "<Enter>", lambda e: c.configure(cursor="hand2"))
            c.tag_bind(tag, "<Leave>", lambda e: c.configure(cursor=""))

    def _botones_rapidos(self, x, y, clave, o, hechas, plan, bloqueada):
        """− / + / Todo bajo cada casilla. En modo 'comprar' cambian lo comprado; en 'planear', lo planeado."""
        if self._modo() == "comprar":
            libres = o["maximo"] - hechas
            puede_mas = libres > 0 and not bloqueada
            self._boton(x - 44, y, 30, "−", "#7a2a20", hechas > 0, lambda: self.v.cambiar_compra(clave, o, dh=-1))
            self._boton(x - 8, y, 30, "+", "#2f6a2a", puede_mas, lambda: self.v.cambiar_compra(clave, o, dh=1))
            if hechas >= o["maximo"]:
                self._boton(x + 38, y, 50, tr("0"), "#7a2a20", True,
                            lambda: self.v.cambiar_compra(clave, o, dh=-hechas))
            else:
                self._boton(x + 38, y, 50, tr("Todo"), "#8a6418", puede_mas,
                            lambda: self.v.cambiar_compra(clave, o, dh=libres))
        else:
            libres = o["maximo"] - hechas - plan
            self._boton(x - 44, y, 30, "−", "#7a2a20", plan > 0, lambda: self.v.cambiar_compra(clave, o, dp=-1))
            self._boton(x - 8, y, 30, "+", "#2a4f7a", libres > 0, lambda: self.v.cambiar_compra(clave, o, dp=1))
            if libres <= 0 and plan:
                self._boton(x + 38, y, 50, tr("0"), "#7a2a20", True,
                            lambda: self.v.cambiar_compra(clave, o, dp=-plan))
            else:
                self._boton(x + 38, y, 50, tr("Todo"), "#2a4f7a", libres > 0,
                            lambda: self.v.cambiar_compra(clave, o, dp=libres))

    def _comprar(self, clave, o, bloqueada):
        if self._modo() == "planear":
            self.v.cambiar_compra(clave, o, dp=1)
            return
        if bloqueada:
            self.v.lbl_info_tienda.configure(text=tr("Esta tienda aún está bloqueada: cambia a «Planear» arriba."))
            return
        self.v.cambiar_compra(clave, o, dh=1)

    def _menu(self, e, clave, o, bloqueada):
        m = tk.Menu(self.canvas, tearoff=0)
        comp = (self.v.estado.get("compras") or {}).get(clave) or {}
        hechas, plan = int(comp.get("hechas") or 0), int(comp.get("planeadas") or 0)
        quedan = o["maximo"] - hechas
        estado_compra = "disabled" if bloqueada or quedan <= 0 else "normal"
        m.add_command(label=tr("Comprar 1"), state=estado_compra, command=lambda: self.v.cambiar_compra(clave, o, dh=1))
        m.add_command(label=tr("Comprar todos los que quedan ({0})", quedan), state=estado_compra,
                      command=lambda: self.v.cambiar_compra(clave, o, dh=quedan))
        m.add_command(label=tr("Deshacer 1 compra"), state="normal" if hechas else "disabled",
                      command=lambda: self.v.cambiar_compra(clave, o, dh=-1))
        m.add_separator()
        libre = o["maximo"] - hechas - plan
        m.add_command(label=tr("Planear +1"), state="normal" if libre > 0 else "disabled",
                      command=lambda: self.v.cambiar_compra(clave, o, dp=1))
        m.add_command(label=tr("Planear todos ({0})", libre), state="normal" if libre > 0 else "disabled",
                      command=lambda: self.v.cambiar_compra(clave, o, dp=libre))
        m.add_command(label=tr("Quitar plan"), state="normal" if plan else "disabled",
                      command=lambda: self.v.cambiar_compra(clave, o, dp=-plan))
        m.tk_popup(e.x_root, e.y_root)
