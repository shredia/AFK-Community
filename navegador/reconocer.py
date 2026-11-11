"""
Reconocimiento de héroes en imágenes (por ejemplo, las de una planilla de guías).

Compara cada imagen con los retratos del catálogo del sitio usando un hash perceptual
(dHash de 16x16 sobre el centro de la imagen) y devuelve el héroe más parecido.
"""
from pathlib import Path

from PIL import Image

LADO_HASH = 16


def _preparar(img):
    img = img.convert("RGBA")
    fondo = Image.new("RGBA", img.size, (0, 0, 0, 255))
    fondo.alpha_composite(img)
    img = fondo.convert("L")
    w, h = img.size
    # recorte central (los íconos suelen tener marco/borde distinto según la fuente)
    m = int(min(w, h) * 0.12)
    return img.crop((m, m, w - m, h - m))


def dhash(img, lado=LADO_HASH):
    """Hash de diferencias: compara cada píxel con su vecino de la derecha."""
    peq = _preparar(img).resize((lado + 1, lado), Image.LANCZOS)
    px = list(peq.getdata())
    bits = 0
    for fila in range(lado):
        for col in range(lado):
            izq = px[fila * (lado + 1) + col]
            der = px[fila * (lado + 1) + col + 1]
            bits = (bits << 1) | (1 if izq > der else 0)
    return bits


def distancia(a, b):
    return bin(a ^ b).count("1")


class Reconocedor:
    """referencias: [(clave, nombre, ruta_imagen)]"""

    def __init__(self, referencias):
        self.refs = []
        for clave, nombre, ruta in referencias:
            try:
                with Image.open(ruta) as im:
                    self.refs.append((clave, nombre, dhash(im)))
            except Exception:
                continue

    def reconocer_con_margen(self, img, umbral=80, margen=8, agrupar=lambda clave: clave):
        """
        Como reconocer(), pero acepta distancias mayores solo si el mejor candidato supera por `margen`
        al mejor candidato de OTRO grupo (p. ej. otro afijo, ignorando la calidad).
        """
        if not self.refs:
            return None, None, 999
        h = dhash(img)
        mejores = {}
        for clave, nombre, ref in self.refs:
            d = distancia(h, ref)
            g = agrupar(clave)
            if g not in mejores or d < mejores[g][0]:
                mejores[g] = (d, clave, nombre)
        orden = sorted(mejores.values())
        d, clave, nombre = orden[0]
        segundo = orden[1][0] if len(orden) > 1 else 999
        if d > umbral or segundo - d < margen:
            return None, None, d
        return clave, nombre, d

    def reconocer(self, img, umbral=70):
        """(clave, nombre, distancia) del héroe más parecido, o (None, None, d) si nada se parece."""
        if not self.refs:
            return None, None, 999
        h = dhash(img)
        mejor = min(self.refs, key=lambda r: distancia(h, r[2]))
        d = distancia(h, mejor[2])
        if d > umbral:
            return None, None, d
        return mejor[0], mejor[1], d


def referencias_catalogo(base_dir, heroes_api):
    """[(id, nombre, ruta)] de los retratos del catálogo ya descargados en NC/assets."""
    carpeta = Path(base_dir) / "assets"
    salida = []
    for h in heroes_api:
        url = h.get("imageUrl")
        if not url:
            continue
        ruta = carpeta.joinpath(*url.lstrip("/").split("/"))
        if ruta.exists():
            salida.append((str(h.get("id")), h.get("name"), ruta))
    return salida
