"""
Traduce los datos de una run a las imágenes del sitio (jefes, equipo, afijos, estrellas, SI, etc.).

Usa NC/assets/tablas_sitio.json, que se descarga desde el módulo GameVisuals del sitio
(las mismas tablas que usa la página para dibujar el diálogo de héroe).
"""
import json
import re
from collections import Counter
from pathlib import Path
from idiomas import tr, N_

ARCHIVO_TABLAS = "tablas_sitio.json"
NOMBRES_CALIDAD = [N_("Desconocida"), N_("Común"), N_("Raro"), N_("Raro+"), N_("Élite"), N_("Élite+"),
                   N_("Legendario"), N_("Legendario+"), N_("Mítico"), N_("Mítico+")]
ICONO_MUEBLE = "/game-ui/icon_furniture_quality_{q}.png"
CALIDADES_MUEBLE = (3, 5, 7, 9)

# Abreviaturas de la guía de colecciones -> naturaleza del afijo (igual que el sitio)
STAT_A_NATURALEZA = {"Atk%": 1, "Def%": 2, "HP%": 3, "F.Atk%": 4, "F.Def%": 5, "F.Ero%": 9, "Erosion": 7,
                     "PP": 11, "MP": 12, "TY": 13, "IS": 14, "PRF": 15, "Heal": 17, "CDA": 21, "Crit": 23, "ERR": 25}
NOMBRES_MODO = {"NC": N_("Nightmare Corridor"), "CR": N_("Cursed Realm"), "TS": N_("Treasure Scramble")}


def ruta_tablas(base_dir):
    return Path(base_dir) / "assets" / ARCHIVO_TABLAS


def extraer_tablas(modulo):
    """Del volcado completo del módulo GameVisuals, conserva solo lo necesario."""
    def buscar(clave):
        for valor in modulo.values():
            if isinstance(valor, dict) and clave in valor:
                return valor
        return {}

    c, d, r, s = buscar("affixes"), buscar("equipment"), buscar("equips"), buscar("backgrounds")
    jefes = next((v for v in modulo.values()
                  if isinstance(v, dict) and v and all(isinstance(x, dict) and "imageUrl" in x and "id" in x
                                                       for x in list(v.values())[:5])), {})
    return {
        "jefes": jefes,
        "jefes_nc": r.get("nc", {}),
        "afijos": c.get("affixes", {}),
        "colecciones": c.get("collections", {}),
        "colecciones_img": s.get("collections", {}),
        "equipo": d.get("equipment", {}),
        "equipo_img": r.get("equips", {}),
        "marcos": d.get("frames", {}),
        "estrellas": d.get("stars", {}),
        "facciones": d.get("factions", {}),
        "facciones_equipo": r.get("factionTags", {}),
        "iconos_calidad": d.get("qualityIcons", {}),
        "si_iconos": r.get("signatureIcons", {}),
        "mascotas": r.get("pets", {}),
        # Retrato: marco de SI (esquina superior izquierda) y muebles
        "marcos_si_retrato": d.get("signatureFrames", {}),
        "mueble_max_nivel": d.get("furnitureMaxLevel", 3),
        # Colección: estrellas de habilidad y valores de afijos
        "coleccion_niveles": d.get("collectionLevels", {}),
        "coleccion_skill_nature": d.get("collectionSkillNature", []),
        "coleccion_skill_valores": d.get("collectionSkillValues", {}),
        "coleccion_max_skill": d.get("collectionMaxSkill", 3),
        "afijo_valores": c.get("values", {}),
        "afijo_calidades": c.get("qualities", {}),
    }


class Visuales:
    def __init__(self, base_dir):
        self.t = {}
        archivo = ruta_tablas(base_dir)
        if archivo.exists():
            try:
                self.t = json.loads(archivo.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                self.t = {}
        # nombre de equipo -> [(id, calidad)]
        self._equipo_por_nombre = {}
        for ident, e in (self.t.get("equipo") or {}).items():
            self._equipo_por_nombre.setdefault(str(e.get("name", "")).strip().lower(), []).append(
                (ident, e.get("quality")))

    @property
    def disponible(self):
        return bool(self.t)

    # ---------------- jefes ----------------

    def jefe(self, boss_id):
        """(nombre, imageUrl o None)."""
        info = (self.t.get("jefes") or {}).get(str(boss_id)) or {}
        nombre = info.get("name") or f"Boss {boss_id}"
        url = info.get("imageUrl")
        if not url:
            # Variantes ("X (Monstrous)") sin imagen: usar la de la versión base
            base = re.sub(r"\s*\(.*?\)\s*$", "", nombre).strip().lower()
            for otro in (self.t.get("jefes") or {}).values():
                if otro.get("imageUrl") and str(otro.get("name", "")).strip().lower() == base:
                    url = otro["imageUrl"]
            if not url:
                for nc in (self.t.get("jefes_nc") or {}).values():
                    if nc.get("headUrl") and str(nc.get("name", "")).strip().lower() in (base, nombre.lower()):
                        url = nc["headUrl"]
                        break
        return nombre, url

    # ---------------- héroe ----------------

    @staticmethod
    def nombre_calidad(calidad):
        try:
            q = int(calidad)
        except (TypeError, ValueError):
            return str(calidad)
        if q >= 10:
            return tr("Ascendido") if q == 10 else tr("Ascendido {0}★", q - 10)
        return tr(NOMBRES_CALIDAD[q]) if 0 <= q < len(NOMBRES_CALIDAD) else str(q)

    @staticmethod
    def numero_estrellas(calidad):
        try:
            return max(0, min(5, int(calidad) - 10))
        except (TypeError, ValueError):
            return 0

    def estrella(self, grabado):
        """Imagen de estrella según el grabado (blanca / naranja ≥30 / roja ≥60 / diamante ≥80)."""
        umbrales = sorted(((int(k), v) for k, v in (self.t.get("estrellas") or {}).items()), key=lambda x: x[0])
        url = None
        for minimo, imagen in umbrales:
            if (grabado or 0) >= minimo:
                url = imagen
        return url

    def marco(self, calidad):
        return (self.t.get("marcos") or {}).get(str(calidad))

    def faccion(self, faccion):
        return (self.t.get("facciones") or {}).get(str(faccion))

    def icono_si(self, hero_tid, sig):
        niveles = (self.t.get("si_iconos") or {}).get(str(hero_tid)) or []
        url = None
        for minimo, imagen in niveles:
            if (sig or 0) >= minimo:
                url = imagen
        return url

    @staticmethod
    def icono_mueble(calidad=9):
        return ICONO_MUEBLE.format(q=calidad)

    def marco_si_retrato(self, sig):
        """Marco de SI de la esquina superior izquierda del retrato (SI+10 ... +40)."""
        marcos = self.t.get("marcos_si_retrato") or {}
        if sig is None or not marcos:
            return None
        claves = sorted(int(k) for k in marcos)
        nivel = min(int(sig or 0), claves[-1])
        return marcos.get(str(nivel))

    def insignia_muebles(self, h):
        """
        (insignia, corona) de muebles como en el sitio:
        3+ piezas -> skill_lv1, 9 -> skill_lv2, 9 al nivel máximo -> skill_lv3_1 + corona.
        """
        mueble = h.get("furniture") or {}
        piezas = int(mueble.get("pieces") or 0)
        slots = h.get("furnitureSlots") or []
        maximo = int(self.t.get("mueble_max_nivel") or 3)
        completo = piezas >= 9 and len(slots) >= 9 and all(int(s or 0) >= maximo for s in slots[:9])
        if completo:
            return "/game-ui/skill_lv3_1.png", "/game-ui/skill_lv3_2.png"
        if piezas >= 9:
            return "/game-ui/skill_lv2.png", None
        if piezas >= 3:
            return "/game-ui/skill_lv1.png", None
        return None, None

    @staticmethod
    def usa_sp(h, golden):
        """Héroes especiales (hyper): True si usan su Special Power (golden slot) en esta ronda."""
        if not h.get("hyper"):
            return None
        if golden == "?":   # varios especiales y no se sabe cuál lo usó
            return "?"
        return golden is not None and str(golden) == str(h.get("slot"))

    # ---------------- colección: estrellas y valores ----------------

    def estrellas_coleccion(self, col):
        """Nivel de habilidad (estrellas) de una colección, igual que el sitio."""
        nivel_base = (self.t.get("coleccion_niveles") or {}).get(str(col.get("level")))
        if nivel_base is None:
            return None
        naturalezas = {int(n) for n in self.t.get("coleccion_skill_nature") or []}
        valores = (self.t.get("coleccion_skill_valores") or {}).get(str(col.get("tid"))) or {}
        extra = sum(valores.get(str(a.get("quality")), 0) or 0
                    for a in col.get("affixes") or [] if int(a.get("nature") or 0) in naturalezas)
        return min(int(self.t.get("coleccion_max_skill") or 3), int(nivel_base) + int(extra))

    def valor_afijo(self, col_tid, nature, calidad):
        """Texto '+1.83%' del afijo, o None."""
        info = (self.t.get("afijos") or {}).get(str(nature)) or {}
        atributo = info.get("attribute")
        if not atributo:
            return None
        valor = (((self.t.get("afijo_valores") or {}).get(str(col_tid)) or {}).get(str(calidad)) or {}).get(atributo)
        if valor is None:
            return None
        sufijo = "%" if ".PR" in atributo else ""
        return f"+{round(float(valor), 2):g}{sufijo}"

    def color_calidad_afijo(self, calidad):
        return ((self.t.get("afijo_calidades") or {}).get(str(calidad)) or {}).get("TextColor") or None

    def tier_equipo(self, gear):
        """'M' (tier 0), 'T1'..'T5' o None, según la tabla de equipo del sitio."""
        candidatos = self._equipo_por_nombre.get(str(gear.get("name", "")).strip().lower(), [])
        if not candidatos:
            return None
        ident = next((i for i, q in candidatos if q == gear.get("quality")), candidatos[0][0])
        tier = ((self.t.get("equipo") or {}).get(str(ident)) or {}).get("tier")
        if tier is None:
            return None
        return "M" if int(tier) == 0 else f"T{tier}"

    # ---------------- equipo ----------------

    def imagen_equipo(self, gear):
        candidatos = self._equipo_por_nombre.get(str(gear.get("name", "")).strip().lower(), [])
        if not candidatos:
            return None
        ident = next((i for i, q in candidatos if q == gear.get("quality")), candidatos[0][0])
        return (self.t.get("equipo_img") or {}).get(str(ident))

    def faccion_equipo(self, tag):
        """(nombre, icono) de la facción de una pieza de equipo."""
        info = (self.t.get("facciones_equipo") or {}).get(str(tag)) or {}
        return info.get("name"), info.get("icon")

    # ---------------- colección ----------------

    def imagen_coleccion(self, tid):
        return ((self.t.get("colecciones_img") or {}).get(str(tid)) or {}).get("imageUrl")

    def habilidades_coleccion(self, tid):
        return ((self.t.get("colecciones") or {}).get(str(tid)) or {}).get("skills") or []

    def afijo(self, nature, calidad):
        """(nombre, icono) de un afijo de colección."""
        info = (self.t.get("afijos") or {}).get(str(nature)) or {}
        nombre = info.get("name") or f"Naturaleza {nature}"
        iconos = info.get("icons") or {}
        return nombre, iconos.get(str(calidad)) or (iconos.get(max(iconos, key=int)) if iconos else None)

    # ---------------- guía de colecciones (Collections Checklist) ----------------

    @property
    def recomendaciones(self):
        return self.t.get("recomendaciones_colecciones") or []

    def recomendaciones_heroe(self, hero_tid, modo=None):
        """Filas de la guía que mencionan a este héroe (opcionalmente solo para un modo: NC, CR, TS)."""
        filas = []
        for f in self.recomendaciones:
            tids = [int(t) for t in f.get("heroTids") or []]
            try:
                tid = int(hero_tid)
            except (TypeError, ValueError):
                continue
            if tid not in tids:
                continue
            modos = (f.get("heroModes") or {}).get(str(tid)) or f.get("modes") or []
            if modo and modo not in modos:
                continue
            filas.append(dict(f, modos_heroe=modos))
        return filas

    def recomendaciones_coleccion(self, coleccion_tid):
        return [f for f in self.recomendaciones if str(f.get("collectionTid")) == str(coleccion_tid)]

    def evaluar_recomendacion(self, col, fila):
        """
        Regla del sitio: mismo tipo de colección, exactamente +N de habilidad y, por cada estadística
        pedida, al menos `min` afijos míticos (calidad ≥5) de esa estadística.
        Retorna (cumple, faltan, detalle) — faltan = míticos que faltan + diferencia de habilidad.
        """
        if str(col.get("tid")) != str(fila.get("collectionTid")):
            return False, 99, "otro tipo de colección"
        estrellas = self.estrellas_coleccion(col)
        bonus = None if estrellas is None else estrellas - 1
        objetivo = int(fila.get("skillBonus") or 0)
        faltan, partes = 0, []
        if bonus != objetivo:
            faltan += abs((bonus or 0) - objetivo)
            partes.append(f"tiene +{bonus if bonus is not None else '?'} de habilidad (pide +{objetivo})")
        miticos = Counter(int(a.get("nature") or 0) for a in col.get("affixes") or []
                          if int(a.get("quality") or 0) >= 5)
        for req in fila.get("requirements") or []:
            nature = STAT_A_NATURALEZA.get(req.get("stat"))
            if nature is None:
                continue
            tiene = miticos.get(nature, 0)
            minimo = int(req.get("min") or 0)
            if tiene < minimo:
                faltan += minimo - tiene
                partes.append(f"{req.get('stat')}: {tiene}/{minimo} míticos")
        return faltan == 0, faltan, "; ".join(partes) or "cumple"

    def mejor_copia(self, colecciones, fila):
        """(colección, cumple, faltan, detalle) de tu copia que mejor se ajusta a la fila, o None."""
        mejor = None
        for col in colecciones or []:
            if str(col.get("tid")) != str(fila.get("collectionTid")):
                continue
            cumple, faltan, detalle = self.evaluar_recomendacion(col, fila)
            if mejor is None or faltan < mejor[2]:
                mejor = (col, cumple, faltan, detalle)
        return mejor

    def nombre_coleccion(self, tid):
        return (((self.t.get("colecciones") or {}).get(str(tid)) or {}).get("name")
                or ((self.t.get("colecciones_img") or {}).get(str(tid)) or {}).get("name") or f"Colección {tid}")

    # ---------------- todas las imágenes de una run ----------------

    def urls_de_ronda(self, ronda):
        """Todas las imágenes que se usan para dibujar una ronda (para descargarlas)."""
        urls = set()
        urls.add(self.jefe(ronda.get("bossId"))[1])
        for h in ronda.get("heroes") or []:
            urls.update({
                self.marco(h.get("quality")),
                self.faccion(h.get("faction")),
                self.estrella(h.get("engraving")),
                self.icono_si(h.get("tid"), h.get("sig")),
                self.marco_si_retrato(h.get("sig")),
                *self.insignia_muebles(h),
            })
            for g in h.get("gear") or []:
                urls.add(self.imagen_equipo(g))
                urls.add(self.faccion_equipo(g.get("faction"))[1])
            col = h.get("collection") or {}
            if col:
                urls.add(self.imagen_coleccion(col.get("tid")))
                for a in col.get("affixes") or []:
                    urls.add(self.afijo(a.get("nature"), a.get("quality"))[1])
        return {u for u in urls if u}

    def urls_fijas(self):
        urls = {self.icono_mueble(q) for q in CALIDADES_MUEBLE}
        urls.update({"/game-ui/skill_lv1.png", "/game-ui/skill_lv2.png", "/game-ui/skill_lv3_1.png",
                     "/game-ui/skill_lv3_2.png", "/game-ui/mitama_icon_frame.png", "/game-ui/img_star_light.png",
                     "/game-ui/n_evolve_star_small.png"})
        urls.update(v for v in (self.t.get("marcos_si_retrato") or {}).values() if v)
        urls.update(v for v in (self.t.get("estrellas") or {}).values() if v)
        urls.update(v for v in (self.t.get("facciones") or {}).values() if v)
        return urls
