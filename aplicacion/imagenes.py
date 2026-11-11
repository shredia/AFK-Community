# aplicacion/imagenes.py
"""Carga de imágenes descargadas (NC/assets) para Tkinter, con caché y marcador si falta."""
from pathlib import Path
import tkinter as tk

try:
    from PIL import Image, ImageDraw, ImageTk
except ImportError:  # sin Pillow no se pueden mostrar .webp
    Image = None

BASE_ASSETS = Path(__file__).resolve().parent.parent / "assets"
_FUENTES = {}
# Copias que no son tuyas: (texto de la franja, color RGBA)
ETIQUETAS_ORIGEN = {
    "prestado": ("PRESTADO", (30, 90, 200, 225)),
    "prueba": ("PRUEBA", (150, 60, 190, 225)),
    "temporal": ("PRESTADO/PRUEBA", (30, 90, 200, 225)),
    "fuera_roster": ("YA NO LO TIENES", (120, 120, 120, 225)),
}


def _fuente(tam):
    if tam not in _FUENTES:
        try:
            from PIL import ImageFont
            for nombre in ("arialbd.ttf", "seguisb.ttf", "DejaVuSans-Bold.ttf"):
                try:
                    _FUENTES[tam] = ImageFont.truetype(nombre, tam)
                    break
                except OSError:
                    continue
            else:
                _FUENTES[tam] = ImageFont.load_default()
        except Exception:
            _FUENTES[tam] = None
    return _FUENTES[tam]


class CacheImagenes:
    def __init__(self):
        self._cache = {}

    def obtener(self, url, tam=56):
        """PhotoImage cuadrada de `tam` px para una imageUrl (/api/... o /game-ui/...)."""
        clave = (url or "", tam)
        if clave in self._cache:
            return self._cache[clave]

        foto = None
        if Image is not None:
            ruta = BASE_ASSETS.joinpath(*(url or "").lstrip("/").split("/")) if url else None
            try:
                if ruta and ruta.is_file():
                    img = Image.open(ruta).convert("RGBA")
                    img.thumbnail((tam, tam), Image.LANCZOS)
                    lienzo = Image.new("RGBA", (tam, tam), (0, 0, 0, 0))
                    lienzo.paste(img, ((tam - img.width) // 2, (tam - img.height) // 2), img)
                    foto = ImageTk.PhotoImage(lienzo)
            except Exception:
                foto = None
            if foto is None:
                foto = self._marcador(tam)
        else:
            foto = tk.PhotoImage(width=tam, height=tam)

        self._cache[clave] = foto
        return foto

    # ------------------------------------------------------------
    # Composiciones al estilo del juego (se dibujan a escala 100 px y se reducen)
    # ------------------------------------------------------------

    @staticmethod
    def _abrir(url):
        if not url or Image is None:
            return None
        ruta = BASE_ASSETS.joinpath(*url.lstrip("/").split("/"))
        try:
            return Image.open(ruta).convert("RGBA") if ruta.is_file() else None
        except Exception:
            return None

    @staticmethod
    def _pegar(lienzo, img, x, y, ancho=None, alto=None):
        if img is None:
            return
        if ancho or alto:
            if ancho and not alto:
                alto = round(img.height * ancho / img.width)
            if alto and not ancho:
                ancho = round(img.width * alto / img.height)
            img = img.resize((ancho, alto), Image.LANCZOS)
        lienzo.alpha_composite(img, (int(x), int(y)))

    @staticmethod
    def _texto(dibujo, xy, texto, tam, relleno=(255, 255, 255, 255), ancla="la"):
        dibujo.text(xy, texto, font=_fuente(tam), fill=relleno, anchor=ancla,
                    stroke_width=max(1, tam // 7), stroke_fill=(0, 0, 0, 255))

    def retrato(self, h, vis, golden=None, tam=64, con_coleccion=True, con_equipo=False):
        """
        Retrato del héroe como en el juego:
        facción + marco de SI y muebles arriba a la izquierda, estrellas (color del grabado) delante,
        SP arriba a la derecha y, debajo, la colección con sus estrellas y míticos
        (y opcionalmente una fila con las 4 piezas de equipo).
        """
        col = h.get("collection") or {}
        mueble = h.get("furniture") or {}
        sp = vis.usa_sp(h, golden)
        gear = sorted(h.get("gear") or [], key=lambda g: g.get("slot", 0))
        clave = ("retrato", h.get("tid"), h.get("imageUrl"), h.get("quality"), h.get("engraving"), h.get("sig"),
                 h.get("faction"), mueble.get("pieces"), tuple(h.get("furnitureSlots") or ()), sp,
                 col.get("tid"), col.get("level"), col.get("mythic"),
                 tuple((a.get("nature"), a.get("quality")) for a in col.get("affixes") or ()), con_coleccion,
                 con_equipo, tuple((g.get("name"), g.get("quality"), g.get("stars")) for g in gear) if con_equipo else (),
                 h.get("origen"), tam)
        if clave in self._cache:
            return self._cache[clave]
        if Image is None:
            return self.obtener(h.get("imageUrl"), tam)

        M = 10                       # margen para que el aro del SI sobresalga
        franja = 40 if con_coleccion else 0
        franja_equipo = 31 if con_equipo else 0
        lienzo = Image.new("RGBA", (100 + 2 * M, 100 + 2 * M + franja + franja_equipo), (0, 0, 0, 0))
        dib = ImageDraw.Draw(lienzo)

        # Retrato + marco de calidad
        base = self._abrir(h.get("imageUrl"))
        if base is not None:
            self._pegar(lienzo, base, M + 4, M + 4, 92, 92)
        else:
            dib.rectangle([M, M, M + 99, M + 99], fill=(120, 120, 120, 255))
        self._pegar(lienzo, self._abrir(vis.marco(h.get("quality"))), M, M, 100, 100)

        # Arriba a la izquierda: facción dentro del círculo del marco, rodeada por el aro del SI
        self._pegar(lienzo, self._abrir(vis.faccion(h.get("faction"))), M + 2, M + 2, 27, 27)
        anillo = self._abrir(vis.marco_si_retrato(h.get("sig")))
        if anillo is not None and (h.get("sig") or 0) >= 10:
            self._pegar(lienzo, anillo, M + 15.5 - 22, M + 15.5 - 29, 44)
        if h.get("sig") is not None:
            self._texto(dib, (M + 15, M + 33), f"+{h.get('sig')}", 13, ancla="mt")

        # Insignia de muebles (3 / 9 / 9 al máximo con corona) bajo el SI
        insignia, corona = vis.insignia_muebles(h)
        if insignia:
            self._pegar(lienzo, self._abrir(insignia), M + 1, M + 46, None, 26)
            if corona:
                self._pegar(lienzo, self._abrir(corona), M + 3, M + 40, None, 12)

        # SP (héroes especiales) arriba a la derecha
        if sp is not None:
            color = (255, 205, 60, 255) if sp else (170, 170, 170, 255)
            dib.ellipse([M + 74, M + 3, M + 97, M + 22], fill=(40, 20, 0, 230) if sp else (40, 40, 40, 200),
                        outline=color, width=2)
            self._texto(dib, (M + 85.5, M + 12.5), "SP", 11, relleno=color, ancla="mm")
            if not sp:
                dib.line([M + 76, M + 20, M + 95, M + 5], fill=(220, 60, 60, 255), width=2)

        # Copia no propia: franja bien visible sobre el retrato
        etiqueta = ETIQUETAS_ORIGEN.get(h.get("origen"))
        if etiqueta:
            texto, color = etiqueta
            dib.rectangle([M + 3, M + 60, M + 97, M + 78], fill=color)
            self._texto(dib, (M + 50, M + 69), texto, 14, ancla="mm")

        # Estrellas delante (color según el grabado)
        n = vis.numero_estrellas(h.get("quality"))
        estrella = self._abrir(vis.estrella(h.get("engraving")))
        if n and estrella is not None:
            ancho = 19
            x0 = M + 50 - (n * ancho) / 2
            for i in range(n):
                self._pegar(lienzo, estrella, x0 + i * ancho, M + 80, ancho + 2)

        # Franja inferior: colección
        if con_coleccion:
            y = 100 + 2 * M
            if col:
                icono = self._abrir(vis.imagen_coleccion(col.get("tid")))
                self._pegar(lienzo, icono, M + 2, y + 2, 34, 34)
                self._pegar(lienzo, self._abrir("/game-ui/mitama_icon_frame.png"), M, y, 38, 38)
                estrellas_col = vis.estrellas_coleccion(col) or 0
                luz = self._abrir("/game-ui/img_star_light.png")
                for i in range(estrellas_col):
                    self._pegar(lienzo, luz, M + 40 + i * 21, y + 8, 22, 22)
                # Número de afijos míticos sobre el icono (como en el sitio)
                afijos = col.get("affixes") or []
                miticos = sum(1 for a in afijos if int(a.get("quality") or 0) >= 5) if afijos else col.get("mythic", 0)
                self._texto(dib, (M + 37, y + 37), str(miticos), 19, relleno=(255, 215, 120, 255), ancla="rd")
            else:
                self._texto(dib, (M + 2, y + 12), "Sin colección", 12, relleno=(200, 200, 200, 255))

        # Fila de equipo: arma, casco, cuerpo, botas
        if con_equipo:
            y = 100 + 2 * M + franja
            lado = 29
            x0 = (lienzo.width - 4 * lado - 3) / 2
            for i, g in enumerate(gear[:4]):
                self._pegar(lienzo, self._equipo_pil(g, vis, texto_grande=True), x0 + i * (lado + 1), y + 1, lado, lado)

        alto_final = round(lienzo.height * tam / lienzo.width)
        foto = ImageTk.PhotoImage(lienzo.resize((tam, alto_final), Image.LANCZOS))
        self._cache[clave] = foto
        return foto

    def _equipo_pil(self, gear, vis, texto_grande=False):
        """Icono de equipo 100×100 (PIL) con su tier y estrellas."""
        lienzo = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
        dib = ImageDraw.Draw(lienzo)
        img = self._abrir(vis.imagen_equipo(gear))
        if img is not None:
            self._pegar(lienzo, img, 0, 0, 100, 100)
        else:
            dib.rectangle([0, 0, 99, 99], fill=(120, 120, 120, 255))
        tier = vis.tier_equipo(gear)
        if tier:
            self._texto(dib, (97, 2), tier, 40 if texto_grande else 26, relleno=(255, 230, 120, 255), ancla="ra")
        estrellas = int(gear.get("stars") or 0)
        if estrellas:
            luz = self._abrir("/game-ui/n_evolve_star_small.png")
            paso = 19
            x0 = 50 - estrellas * paso / 2
            for i in range(estrellas):
                self._pegar(lienzo, luz, x0 + i * paso, 76, 22)
        return lienzo

    def equipo(self, gear, vis, tam=40):
        """Icono de equipo con su tier (M, T1..T5) y estrellas, como en el sitio."""
        clave = ("equipo", gear.get("name"), gear.get("quality"), gear.get("stars"), tam)
        if clave in self._cache:
            return self._cache[clave]
        if Image is None:
            return self.obtener(vis.imagen_equipo(gear), tam)
        foto = ImageTk.PhotoImage(self._equipo_pil(gear, vis).resize((tam, tam), Image.LANCZOS))
        self._cache[clave] = foto
        return foto

    @staticmethod
    def _marcador(tam):
        img = Image.new("RGBA", (tam, tam), (200, 200, 200, 255))
        dibujo = ImageDraw.Draw(img)
        dibujo.rectangle([0, 0, tam - 1, tam - 1], outline=(150, 150, 150, 255))
        dibujo.text((tam // 2 - 3, tam // 2 - 6), "?", fill=(90, 90, 90, 255))
        return ImageTk.PhotoImage(img)
