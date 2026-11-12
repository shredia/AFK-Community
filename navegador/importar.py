"""
Importar y exportar datos sin conectarse al sitio.

Archivos que descarga el sitio a mano:
  - afk-runs.json       lista de runs (NC y CR) con cada ronda y la ficha CRUDA del juego de cada héroe
                        (sin el id de run del sitio: se identifican por battleId y fecha).
  - afk-inventory.json  captura de la cuenta ("format": "afk-classic-local-inventory"): es lo mismo que
                        trae /api/inventory en "data", así que se compacta igual que en el fetch.

El sitio guardaba las runs ya procesadas por su simulador (grabado por nodo, muebles por casilla, nombre del
equipo...). Aquí se traduce la ficha cruda a ese formato. Lo que no viene en el archivo (rol del héroe,
casillas de muebles, nivel de mascota, plantilla de nodos de grabado) se toma de los datos que ya tienes
descargados del mismo héroe o mascota; si nunca se descargó, queda vacío.

El héroe que usó su Special Power (golden) no viene en el archivo: con un solo héroe especial en el equipo se
deduce (se activa solo); con dos o más no se puede saber cuál eligió.

Copias de la app: un .zip con la carpeta cuentas/<cuenta>/<servidor>/ para pasarla a otro PC.
"""
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from .cuenta import (ARCHIVO_CUENTA_ACTUAL, _coleccion_de_fetch, cargar_cuenta_actual, compactar_inventario,
                     completar_imagenes)
from .rutas import cargar_mapa_personajes, carpeta_personaje
from .visuales import Visuales
from idiomas import tr

FORMATO_INVENTARIO = "afk-classic-local-inventory"
PREFIJO_ID = "imp-"
PARTES_EQUIPO = {1: "Weapon", 2: "Head", 3: "Body", 4: "Feet"}
TID_MIN_NO_MUEBLE = 30000      # p. ej. 30011: viene junto a los muebles pero no ocupa casilla
CASILLAS_MUEBLES = 9
ARCHIVO_LISTA_GLOBAL = "sources_guardados.json"


def _sin_progreso(_mensaje):
    pass


def _entero(v, defecto=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return defecto


def _leer_json(ruta, defecto=None):
    try:
        return json.loads(Path(ruta).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return defecto


def _escribir_json(ruta, datos, **opciones):
    """Escritura atómica (un corte a la mitad no deja el archivo roto)."""
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_name(ruta.name + ".tmp")
    temporal.write_text(json.dumps(datos, ensure_ascii=False, **opciones), encoding="utf-8")
    temporal.replace(ruta)


# ============================================================
# Reconocer el archivo
# ============================================================

def detectar(ruta):
    """'runs', 'inventario', 'copia' (zip de la app) o None. Devuelve (tipo, datos_cargados)."""
    ruta = Path(ruta)
    if ruta.suffix.lower() == ".zip":
        return ("copia", None) if zipfile.is_zipfile(ruta) else (None, None)
    datos = _leer_json(ruta)
    if isinstance(datos, dict) and datos.get("format") == FORMATO_INVENTARIO:
        return "inventario", datos
    if isinstance(datos, dict) and datos.get("format") == "afk-community-runs":
        return "runs_app", datos
    if isinstance(datos, list) and datos and isinstance(datos[0], dict) and "battleId" in datos[0] \
            and "rounds" in datos[0]:
        return "runs", datos
    return None, datos


# ============================================================
# Plantillas: lo que el archivo no trae, sacado de tus datos ya descargados
# ============================================================

class Plantillas:
    """Datos fijos por héroe (rol, nodos de grabado...), por mascota y referencias de una carpeta."""

    def __init__(self, base_dir, carpeta=None):
        self.heroe_tid = {}       # tid -> héroe procesado (rol, hyper, tag, nodos...)
        self.heroe_id = {}        # id  -> héroe procesado (casillas de muebles de esa copia)
        self.mascota = {}         # (tid, jobs) -> mascota procesada · tid -> idem
        self.tags_coleccion = {}  # tid colección -> tag
        self.refs = {}            # collectionTags, gearOptions (para el optimizador)
        cuentas = Path(base_dir) / "cuentas"
        carpetas = sorted(cuentas.glob("*/*"), key=lambda c: c != carpeta) if cuentas.exists() else []
        for c in carpetas:
            if not c.is_dir():
                continue
            # los id de héroe son de cada personaje: las copias (muebles por casilla) solo de la carpeta destino
            propia = carpeta is not None and Path(c) == Path(carpeta)
            self._de_indice(c, propia)
            estado = cargar_cuenta_actual(c) or {}
            for h in estado.get("roster") or []:
                self._heroe(h, propia)
            for p in estado.get("mascotas_roster") or []:
                self._mascota(p)
            for col in estado.get("colecciones") or []:
                self._tag(col)
        if carpeta is not None and not self.refs:
            self._refs_de_detalle(Path(carpeta))

    def _heroe(self, h, propia=False):
        if not isinstance(h, dict) or h.get("tid") is None:
            return
        if h.get("engravingNodes") or str(h.get("tid")) not in self.heroe_tid:
            self.heroe_tid[str(h.get("tid"))] = h
        if propia:
            self.heroe_id.setdefault(str(h.get("id")), h)
        self._tag(h.get("collection"))

    def _mascota(self, p):
        if not isinstance(p, dict) or p.get("tid") is None:
            return
        self.mascota.setdefault((str(p.get("tid")), tuple(p.get("jobs") or [])), p)
        self.mascota.setdefault(str(p.get("tid")), p)

    def _tag(self, col):
        if isinstance(col, dict) and col.get("tid") is not None and col.get("tag") is not None:
            self.tags_coleccion.setdefault(str(col["tid"]), col["tag"])

    def _de_indice(self, carpeta, propia=False):
        indice = _leer_json(carpeta / "optimizador_indice.json") or {}
        if not self.refs and (indice.get("refs") or {}).get("gearOptions"):
            self.refs = indice["refs"]
        for run in (indice.get("runs") or {}).values():
            for r in run.get("rounds") or []:
                self._mascota(r.get("pet"))
                for h in r.get("heroes") or []:
                    self._heroe(h, propia)

    def _refs_de_detalle(self, carpeta):
        detalles = sorted((carpeta / "detalles").glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
        for archivo in detalles[:5]:
            d = _leer_json(archivo) or {}
            if d.get("kind") == "import":
                continue
            for t in d.get("collectionTypes") or []:
                self._tag(t)
            if d.get("gearOptions"):
                self.refs = {"collectionTags": d.get("collectionTags") or {}, "gearOptions": d["gearOptions"]}
                return


# ============================================================
# Ficha cruda del juego -> formato de la app
# ============================================================

def _coleccion(mitama, vis, plantillas):
    if not isinstance(mitama, dict) or mitama.get("tid") is None:
        return None
    col = _coleccion_de_fetch(mitama)
    col.pop("locked", None)
    nombre = vis.nombre_coleccion(col["tid"]) if vis is not None else None
    return {"id": col["id"], "tid": col["tid"], "name": nombre or f"Colección {col['tid']}",
            "tag": plantillas.tags_coleccion.get(str(col["tid"])), "level": col["level"],
            "mythic": col["mythic"], "affixes": col["affixes"]}


def _equipo(equips, job, etiquetas, vis):
    tabla = (vis.t.get("equipo") or {}) if vis is not None else {}
    salida = []
    for clave, e in sorted((equips or {}).items(), key=lambda x: _entero(x[0])):
        slot = _entero(clave)
        e = e or {}
        attrs = e.get("attrs") or {}
        if e.get("resonate_tid"):
            # Pieza resonada: el sitio muestra la pieza con la que resuena (sin estrellas)
            info = tabla.get(str(e["resonate_tid"])) or (etiquetas.get("Equip") or {}).get(str(e["resonate_tid"])) or {}
            nombre, calidad, estrellas = info.get("name"), info.get("quality"), 0
        else:
            info = (etiquetas.get("Equip") or {}).get(str(e.get("tid"))) or tabla.get(str(e.get("tid"))) or {}
            nombre = e.get("name") or info.get("name")
            calidad = e.get("quality") if e.get("quality") is not None else info.get("quality")
            estrellas = _entero(e.get("enhance_lv"))
        salida.append({
            "slot": slot, "part": PARTES_EQUIPO.get(slot, str(slot)),
            "name": nombre or f"Equip {e.get('tid')}", "job": job, "quality": calidad, "stars": estrellas,
            "faction": attrs.get("hero_tag"), "attuned": "hero_tid" in attrs,
        })
    return salida


def _muebles(lista, hero_tid, plantilla):
    # Cuentan las piezas de ESTE héroe (hero_tag); las demás vienen en la lista pero no ocupan casilla
    piezas = [m for m in lista or [] if _entero(m.get("tid")) < TID_MIN_NO_MUEBLE
              and _entero(m.get("hero_tag"), None) == hero_tid]
    niveles = [_entero(m.get("lv")) for m in piezas]
    previo = plantilla or {}
    if (previo.get("furniture") or {}).get("pieces") == len(piezas) and \
            sorted(x for x in previo.get("furnitureSlots") or [] if x >= 0) == sorted(niveles):
        return dict(previo["furniture"]), list(previo["furnitureSlots"])
    # Sin datos previos de esta copia: se conoce cuántas piezas y su nivel, no en qué casilla está cada una
    casillas = (sorted(niveles, reverse=True) + [-1] * CASILLAS_MUEBLES)[:CASILLAS_MUEBLES]
    return {"pieces": len(piezas), "level": 0}, casillas


def convertir_heroe(snap, plantillas, vis, etiquetas=None, slot=None):
    """Ficha cruda de héroe (afk-runs / afk-inventory) -> héroe como lo guarda la app."""
    etiquetas = etiquetas or {}
    tid = _entero(snap.get("tid"))
    fijo = plantillas.heroe_tid.get(str(tid)) or {}
    copia = plantillas.heroe_id.get(str(snap.get("id")))
    nodos_lv = {str(k): _entero(v) for k, v in (snap.get("totem_node_lvs") or {}).items()}
    base_nodos = {str(n.get("key")): n for n in fijo.get("engravingNodes") or []}
    nodos = []
    for clave in sorted(set(base_nodos) | set(nodos_lv), key=_entero):
        n = dict(base_nodos.get(clave) or {"key": clave, "max": None, "stats": []})
        n["level"] = nodos_lv.get(clave, 0)
        nodos.append(n)
    sig = snap.get("sig")
    mueble, casillas = _muebles(snap.get("furnitures"), tid, copia)
    h = {
        "id": str(snap.get("id")), "tid": tid, "name": snap.get("name") or fijo.get("name"),
        "imageUrl": snap.get("imageUrl") or fijo.get("imageUrl"), "faction": snap.get("faction") or fijo.get("faction"),
        "quality": _entero(snap.get("quality")),
        "sig": None if sig is None else (_entero(sig.get("lv")) if isinstance(sig, dict) else _entero(sig)),
        "engraving": sum(nodos_lv.values()),
        "engravingEditable": fijo.get("engravingEditable", bool(nodos)),
        "engravingNodes": nodos, "engravingMod": fijo.get("engravingMod"),
        "furniture": mueble, "furnitureSlots": casillas,
        "job": fijo.get("job"), "factionTag": fijo.get("factionTag"), "hyper": fijo.get("hyper", False),
        "tag": fijo.get("tag"),
        "collection": _coleccion(snap.get("mitama_unit"), vis, plantillas),
        "gear": _equipo(snap.get("equips"), fijo.get("job"), etiquetas, vis),
    }
    if slot is not None:
        h = {"slot": slot, **h}
    return h


def convertir_mascota(p, plantillas, etiquetas=None, origen="run"):
    if not isinstance(p, dict):
        return {}
    tid = str(p.get("tid"))
    jobs = [_entero(j.get("lv")) for j in sorted(p.get("job_lv") or [], key=lambda j: _entero(j.get("job_id")))]
    previa = plantillas.mascota.get((tid, tuple(jobs))) or {}
    misma_tid = plantillas.mascota.get(tid) or {}
    info = ((etiquetas or {}).get("Pet") or {}).get(tid) or {}
    return {"from": origen, "id": str(p.get("id")), "tid": _entero(tid),
            "name": info.get("name") or misma_tid.get("name") or f"Pet {tid}",
            "imageUrl": misma_tid.get("imageUrl") or f"/game-ui/run-screen/pets/pet_{tid}.webp",
            "jobs": jobs, "level": previa.get("level"), "maxJob": misma_tid.get("maxJob")}


# ============================================================
# afk-runs.json
# ============================================================

def carpetas_servidor(base_dir):
    """[(carpeta, texto)] de las carpetas cuentas/<cuenta>/<servidor>/ que tienen personaje."""
    # Un personaje puede aparecer en varias cuentas: vale la carpeta que usa el resto de la app
    salida = []
    for c in sorted(set(cargar_mapa_personajes(base_dir).values()), key=lambda x: (len(x.name), x.name)):
        ficha = _leer_json(c / f"{c.name}.json") or {}
        nombre = ficha.get("name") or ficha.get("uid") or ""
        runs = len(_leer_json(c / "runs.json") or [])
        salida.append((c, tr("Servidor {0} · {1} · {2} runs", c.name, nombre, runs)))
    return salida


CARPETA_AMIGOS = "_amigos"
CARPETAS_ESPECIALES = {CARPETA_AMIGOS, "_sin_asignar"}


def resumen_runs(runs):
    """{'nc': n, 'otros': n, 'desde': fecha, 'hasta': fecha} del archivo."""
    nc = [r for r in runs if r.get("mode") == "NC"]
    fechas = sorted(str(r.get("playedAt") or "")[:10] for r in nc if r.get("playedAt"))
    return {"nc": len(nc), "otros": len(runs) - len(nc),
            "desde": fechas[0] if fechas else "", "hasta": fechas[-1] if fechas else ""}


def cuentas_personales(base_dir):
    """
    Tus cuentas del sitio y sus servidores:
    [{"carpeta", "texto", "servidores": [(carpeta_servidor, texto)]}], la más reciente primero.
    """
    salida = []
    for cuenta in (Path(base_dir) / "cuentas").glob("*"):
        ficha = _leer_json(cuenta / "account.json")
        if cuenta.name in CARPETAS_ESPECIALES or not isinstance(ficha, dict):
            continue
        servidores = []
        for c in sorted((x for x in cuenta.iterdir() if x.is_dir()), key=lambda x: (len(x.name), x.name)):
            pj = _leer_json(c / f"{c.name}.json")
            if isinstance(pj, dict):
                runs = len(_leer_json(c / "runs.json") or [])
                servidores.append((c, tr("Servidor {0} · {1} · {2} runs", c.name, pj.get("name") or pj.get("uid"), runs)))
        fecha = str(ficha.get("fetchedAt") or "")
        texto = tr("{0} · actualizada {1}", ficha.get("email") or cuenta.name, fecha[:10] or "?")
        salida.append({"carpeta": cuenta, "texto": texto, "servidores": servidores, "fecha": fecha})
    salida.sort(key=lambda x: x["fecha"], reverse=True)
    return salida


def carpeta_activa(base_dir, carpeta):
    """
    Si ese personaje está en varias cuentas, la app usa la carpeta de la cuenta más reciente
    (ver rutas.cargar_mapa_personajes). Devuelve esa carpeta para no partir sus runs en dos.
    """
    ficha = _leer_json(Path(carpeta) / f"{Path(carpeta).name}.json") or {}
    return cargar_mapa_personajes(base_dir).get(str(ficha.get("uid") or ""), Path(carpeta))


def sugerir_destino_runs(base_dir, runs):
    """(carpeta, coincidencias) del servidor que ya tiene runs con las mismas fechas, o (None, 0)."""
    fechas = {r.get("playedAt") for r in runs}
    mejor, coincidencias = None, 0
    for c, _ in carpetas_servidor(base_dir):
        propias = _leer_json(c / "runs.json") or []
        n = sum(1 for r in propias if r.get("playedAt") in fechas)
        if n > coincidencias:
            mejor, coincidencias = c, n
    return mejor, coincidencias


def _nombre_carpeta(texto):
    import re
    import unicodedata
    texto = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^A-Za-z0-9_-]+", "_", texto).strip("_")[:40] or "amigo"


def amigos(base_dir):
    """[{"carpeta", "nombre", "servidor", "runs"}] de cuentas/_amigos/."""
    salida = []
    for c in sorted((Path(base_dir) / "cuentas" / CARPETA_AMIGOS).glob("*")):
        ficha = _leer_json(c / f"{c.name}.json")
        if c.is_dir() and isinstance(ficha, dict):
            salida.append({"carpeta": c, "nombre": ficha.get("name") or c.name, "servidor": ficha.get("svr_id") or "",
                           "runs": len(_leer_json(c / "runs.json") or [])})
    return salida


def carpeta_amigo(base_dir, nombre, servidor=""):
    """cuentas/_amigos/<nombre>[_<servidor>]/ (la crea con su ficha si no existe)."""
    nombre, servidor = str(nombre).strip(), str(servidor or "").strip()
    if not nombre:
        raise ValueError(tr("Escribe el nombre de tu amigo."))
    for a in amigos(base_dir):
        if a["nombre"].lower() == nombre.lower() and str(a["servidor"]) == servidor:
            return a["carpeta"]
    carpeta_base = _nombre_carpeta(nombre) + (f"_{_nombre_carpeta(servidor)}" if servidor else "")
    raiz = Path(base_dir) / "cuentas" / CARPETA_AMIGOS
    carpeta, n = raiz / carpeta_base, 2
    while carpeta.exists():
        carpeta, n = raiz / f"{carpeta_base}_{n}", n + 1
    carpeta.mkdir(parents=True)
    _escribir_json(carpeta / f"{carpeta.name}.json",
                   {"uid": f"amigo:{carpeta.name}", "name": nombre, "svr_id": servidor, "amigo": True}, indent=2)
    return carpeta


def _golden_deducido(heroes, golden=None):
    from .optimizador import deducir_golden, SP_DESCONOCIDO
    g = deducir_golden(heroes, golden)
    return None if g == SP_DESCONOCIDO else g


CAMPOS_STATS = ("damage", "heal", "defend", "kill", "hp_pct", "mp_pct")


def _stats(crudo):
    """{'damage': '123', ...} -> enteros (daño, curación, defensa, kills, vida y energía en 1/100 de %)."""
    if not isinstance(crudo, dict):
        return None
    return {k: _entero(crudo.get(k)) for k in CAMPOS_STATS if crudo.get(k) is not None}


def _stats_ronda(r):
    """Daño de la mascota y del jefe en una ronda del archivo."""
    mascota = next(iter((r.get("petStats") or {}).values()), None)
    jefes = [_stats(v) for v in (r.get("enemyStats") or {}).values()]
    salida = {}
    if mascota:
        salida["mascota"] = _stats(mascota)
    if jefes:
        salida["jefe"] = jefes[0] if len(jefes) == 1 else {
            k: sum(j.get(k, 0) for j in jefes) for k in ("damage", "heal", "defend", "kill")} | {
            "hp_pct": max(j.get("hp_pct", 0) for j in jefes)}
    if r.get("outcome"):
        salida["resultado"] = r.get("outcome")
    return salida


def _fusionar_stats(detalle, run):
    """Agrega a un detalle ya descargado del sitio las estadísticas del archivo. True si cambió algo."""
    cambio = False
    rondas_archivo = sorted(run.get("rounds") or [], key=lambda x: _entero(x.get("round")))
    for rs, ra in zip(sorted(detalle.get("rounds") or [], key=lambda x: x.get("index", 0)), rondas_archivo):
        if str(rs.get("bossId")) != str(ra.get("bossId")):
            continue
        por_slot = {_entero(h.get("slot")): h for h in ra.get("heroes") or []}
        for h in rs.get("heroes") or []:
            crudo = por_slot.get(_entero(h.get("slot")))
            if crudo and crudo.get("stats") and h.get("stats") != _stats(crudo["stats"]):
                h["stats"] = _stats(crudo["stats"])
                cambio = True
        extra = _stats_ronda(ra)
        if extra and rs.get("estadisticas") != extra:
            rs["estadisticas"] = extra
            cambio = True
    return cambio


def importar_runs(base_dir, runs, carpeta, progreso=_sin_progreso):
    """
    Agrega a la carpeta las runs de NC del archivo que aún no tiene. Las que ya se descargaron del
    sitio (misma fecha) no se tocan: esas tienen más datos.
      - Tuyas:  cuentas/<cuenta>/<servidor>/  (también aparecen en 'Runs de NC').
      - Amigo:  cuentas/_amigos/<nombre>/     (solo en el Optimizador; no se mezclan con las tuyas).
    """
    base_dir, carpeta = Path(base_dir), Path(carpeta)
    ficha = _leer_json(carpeta / f"{carpeta.name}.json") or {}
    es_amigo = bool(ficha.get("amigo"))
    personaje = str(ficha.get("uid") or carpeta.name)
    lista = _leer_json(carpeta / "runs.json") or []
    propias = [r for r in lista if r.get("mine")]
    dueno = ficha.get("name") if es_amigo else next((r.get("owner") for r in propias if r.get("owner")), None)
    fechas = {r.get("playedAt") for r in lista if not str(r.get("id", "")).startswith(PREFIJO_ID)}
    id_por_fecha = {r.get("playedAt"): r.get("id") for r in lista if not str(r.get("id", "")).startswith(PREFIJO_ID)}
    ya_importadas = {r.get("id") for r in lista if str(r.get("id", "")).startswith(PREFIJO_ID)}

    progreso(tr("Preparando datos de referencia (héroes, mascotas, colecciones)..."))
    plantillas = Plantillas(base_dir, carpeta)
    vis = Visuales(base_dir)
    vis = vis if vis.disponible else None

    nuevas, repetidas, otros_modos, actualizadas, con_stats = [], 0, 0, 0, 0
    for i, run in enumerate(runs, 1):
        if run.get("mode") != "NC":
            otros_modos += 1
            continue
        if run.get("playedAt") in fechas:
            repetidas += 1
            # ya la tienes del sitio (con el SP de cada ronda): solo se le agregan las estadísticas
            ruta = carpeta / "detalles" / f"{id_por_fecha.get(run.get('playedAt'))}.json"
            detalle = _leer_json(ruta)
            if isinstance(detalle, dict) and _fusionar_stats(detalle, run):
                _escribir_json(ruta, detalle)
                con_stats += 1
            continue
        rid = f"{PREFIJO_ID}{run.get('battleId')}"
        arbol = run.get("elderTree") or {}
        rondas = []
        ids_propios = set()
        for k, r in enumerate(run.get("rounds") or []):
            heroes = []
            for h in sorted(r.get("heroes") or [], key=lambda x: _entero(x.get("slot"))):
                snap = h.get("snapshot") or {}
                heroe = convertir_heroe(snap, plantillas, vis, slot=h.get("slot"))
                if _stats(h.get("stats")):
                    heroe["stats"] = _stats(h.get("stats"))
                if str(snap.get("source_type")) == "4":
                    heroe["arrendado"] = True  # dimensional arrendado: es tuyo aunque venga 'borrowed'
                    ids_propios.add(str(snap.get("id")))
                elif snap.get("borrowed") or _entero(snap.get("id")) >= 2 ** 32:
                    heroe["prestado"] = True   # mercenario: el optimizador lo marca como prestado
                else:
                    ids_propios.add(str(snap.get("id")))
                heroes.append(heroe)
            mascotas = r.get("pets") or []
            rondas.append({
                "index": k, "bossId": str(r.get("bossId")), "recorded": r.get("result") or {},
                "pet": convertir_mascota(mascotas[0], plantillas) if mascotas else {},
                # afk-runs.json no lo trae: con un solo héroe especial se activa solo; con varios no se sabe
                "golden": _golden_deducido(heroes, r.get("golden")),
                "estadisticas": _stats_ronda(r),
                "outcome": r.get("outcome"), "heroes": heroes,
            })
        detalle = {
            "kind": "import", "id": rid, "owner": dueno if es_amigo else None, "importado": True,
            "battleId": run.get("battleId"), "playedAt": run.get("playedAt"), "result": run.get("result") or {},
            "rounds": rondas, "roster": [{"id": i_} for i_ in sorted(ids_propios)], "borrow": [], "test": [],
            "collectionTags": plantillas.refs.get("collectionTags") or {},
            "gearOptions": plantillas.refs.get("gearOptions") or {},
            "tree": {"lv": arbol.get("lv"), "tags": [_entero(v) for _, v in sorted((arbol.get("tag_lvs") or {}).items(),
                                                                                   key=lambda x: _entero(x[0]))]},
        }
        _escribir_json(carpeta / "detalles" / f"{rid}.json", detalle)
        if rid in ya_importadas:
            actualizadas += 1
        else:
            nuevas.append({"id": rid, "character": personaje, "playedAt": run.get("playedAt"),
                           "result": run.get("result") or {}, "owner": dueno, "mine": not es_amigo,
                           "amigo": es_amigo, "importado": True})
        if i % 25 == 0:
            progreso(tr("   {0}/{1} runs revisadas", i, len(runs)))

    if nuevas:
        lista = sorted(lista + nuevas, key=lambda r: str(r.get("playedAt") or ""), reverse=True)
        _escribir_json(carpeta / "runs.json", lista, indent=4)
        if not es_amigo:   # 'Runs de NC' muestra solo las tuyas
            _agregar_a_lista_global(base_dir, nuevas)
    return {"nuevas": len(nuevas), "actualizadas": actualizadas, "ya_estaban": repetidas,
            "otros_modos": otros_modos, "carpeta": carpeta, "amigo": es_amigo, "con_estadisticas": con_stats}


def _agregar_a_lista_global(base_dir, nuevas):
    """La ventana de Runs lee sources_guardados.json: ahí también van las importadas."""
    archivo = Path(base_dir) / ARCHIVO_LISTA_GLOBAL
    actuales = _leer_json(archivo, []) or []
    ids = {r.get("id") for r in actuales}
    actuales.extend(r for r in nuevas if r["id"] not in ids)
    actuales.sort(key=lambda r: str(r.get("playedAt") or ""), reverse=True)
    _escribir_json(archivo, actuales, indent=4)


def conservar_importadas(nuevas_del_sitio, anteriores):
    """
    Al bajar otra vez la lista del sitio, mantener las runs importadas que el sitio no trae
    (las que sí trae, con la misma fecha y personaje, se reemplazan por la versión del sitio).
    """
    del_sitio = {(str(r.get("character")), r.get("playedAt")) for r in nuevas_del_sitio}
    extra = [r for r in anteriores or [] if str(r.get("id", "")).startswith(PREFIJO_ID)
             and (str(r.get("character")), r.get("playedAt")) not in del_sitio]
    return list(nuevas_del_sitio) + extra


# ============================================================
# afk-inventory.json
# ============================================================

def importar_inventario(base_dir, inv, progreso=_sin_progreso):
    """Guarda la captura como cuenta_actual.json (lo mismo que 'Mi cuenta → Fetch', sin conexión)."""
    base_dir = Path(base_dir)
    compacto = compactar_inventario({"data": inv, "capturedAt": inv.get("capturedAt")})
    uid = str((compacto.get("cuenta") or {}).get("id") or "")
    carpeta = carpeta_personaje(base_dir, cargar_mapa_personajes(base_dir), uid)
    carpeta.mkdir(parents=True, exist_ok=True)
    progreso(tr("Captura del {0} · personaje {1} · servidor {2}", compacto.get("capturedAt"), uid, carpeta.name))

    progreso(tr("Preparando datos de referencia (héroes, mascotas, colecciones)..."))
    plantillas = Plantillas(base_dir, carpeta)
    vis = Visuales(base_dir)
    vis_ok = vis if vis.disponible else None
    etiquetas = inv.get("labels") or {}

    colecciones = []
    for c in compacto.get("colecciones_fetch") or []:
        nombre = vis_ok.nombre_coleccion(c["tid"]) if vis_ok else None
        colecciones.append({**c, "name": nombre or f"Colección {c['tid']}",
                            "tag": plantillas.tags_coleccion.get(str(c["tid"]))})
    por_id = {str(c["id"]): c for c in colecciones}

    roster = []
    temporales = {str(h.get("id")) for h in inv.get("temporaryHeroes") or []}
    for snap in (inv.get("heroes") or []) + (inv.get("temporaryHeroes") or []):
        h = convertir_heroe(snap, plantillas, vis_ok, etiquetas)
        col = h.get("collection")
        if col and str(col.get("id")) in por_id:
            h["collection"] = dict(por_id[str(col["id"])])
        h["temporal"] = h["id"] in temporales
        h["arrendado"] = str(snap.get("source_type")) == "4"
        h["datos_run"] = compacto.get("capturedAt")
        roster.append(h)

    equipada_en = {str(h["collection"]["id"]): h.get("name") for h in roster if h.get("collection")}
    for c in colecciones:
        c["equipada_en"] = equipada_en.get(str(c["id"]))

    estado = {
        **compacto,
        "sincronizado": datetime.now(timezone.utc).isoformat(),
        "servidor": carpeta.name,
        "roster": roster,
        "colecciones": colecciones,
        "mascotas_roster": [convertir_mascota(p, plantillas, etiquetas, "roster") for p in inv.get("pets") or []],
        "fuente_colecciones": "fetch",
        "fecha_run_roster": compacto.get("capturedAt"),
        "importado": True,
    }
    estado.pop("colecciones_fetch", None)
    if vis_ok:
        completar_imagenes(estado, vis_ok)

    anterior = carpeta / ARCHIVO_CUENTA_ACTUAL
    if anterior.exists():
        anterior.replace(carpeta / "cuenta_actual.anterior.json")
    _escribir_json(anterior, estado)
    return {"carpeta": carpeta, "heroes": len(roster), "colecciones": len(colecciones),
            "objetos": len(estado["objetos"]), "capturedAt": compacto.get("capturedAt")}


# ============================================================
# Copia de la app (.zip)
# ============================================================

NO_EXPORTAR = {"optimizador_indice.json"}   # se regenera solo


def exportar_copia(carpeta, destino, progreso=_sin_progreso):
    """Guarda cuentas/<cuenta>/<servidor>/ en un .zip (rutas '<cuenta>/<servidor>/...')."""
    carpeta = Path(carpeta)
    raiz = carpeta.parent.parent
    archivos = [f for f in carpeta.rglob("*") if f.is_file() and f.name not in NO_EXPORTAR
                and not f.name.endswith(".tmp")]
    # account.json de la cuenta: la app lo usa para saber a qué carpeta va cada personaje
    if (carpeta.parent / "account.json").is_file():
        archivos.append(carpeta.parent / "account.json")
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        for i, f in enumerate(archivos, 1):
            z.write(f, f.relative_to(raiz).as_posix())
            if i % 100 == 0:
                progreso(tr("   {0}/{1} archivos", i, len(archivos)))
    return len(archivos)


def contenido_copia(ruta_zip):
    """[(cuenta, servidor)] que trae el .zip. Lanza ValueError si tiene rutas no válidas."""
    carpetas = set()
    with zipfile.ZipFile(ruta_zip) as z:
        for nombre in z.namelist():
            partes = PurePosixPath(nombre).parts
            es_cuenta = len(partes) == 2 and partes[1] == "account.json"
            if nombre.startswith(("/", "\\")) or ".." in partes or ":" in nombre or "\\" in nombre \
                    or (len(partes) < 3 and not es_cuenta):
                raise ValueError(tr("El .zip no es una copia de la app ({0}).", nombre))
            if not es_cuenta:
                carpetas.add(partes[:2])
    if not carpetas:
        raise ValueError(tr("El .zip no es una copia de la app."))
    return sorted(carpetas)


def importar_copia(base_dir, ruta_zip, progreso=_sin_progreso):
    """Extrae la copia en cuentas/ (reemplaza los archivos con el mismo nombre)."""
    contenido_copia(ruta_zip)   # valida las rutas antes de escribir nada
    destino = Path(base_dir) / "cuentas"
    with zipfile.ZipFile(ruta_zip) as z:
        nombres = [n for n in z.namelist() if not n.endswith("/")]
        for i, nombre in enumerate(nombres, 1):
            salida = destino.joinpath(*PurePosixPath(nombre).parts)
            if salida.name == "account.json" and salida.exists():
                continue   # la ficha de cuenta que ya tienes es igual o más nueva
            salida.parent.mkdir(parents=True, exist_ok=True)
            salida.write_bytes(z.read(nombre))
            if i % 100 == 0:
                progreso(tr("   {0}/{1} archivos", i, len(nombres)))
    return len(nombres)


# ============================================================
# Runs para compartir (.json con el SP de cada ronda y las estadísticas)
# ============================================================
# afk-runs.json no guarda qué héroe usó su Special Power; las runs bajadas del sitio sí. Este formato
# lleva las runs ya convertidas (con "golden" y "stats") para pasárselas a un amigo sin perder ese dato.
FORMATO_RUNS_APP = "afk-community-runs"


def _compactar_para_compartir(detalle):
    from .optimizador import _compactar_heroe
    rondas = []
    for r in detalle.get("rounds") or []:
        r2 = {k: r.get(k) for k in ("index", "bossId", "recorded", "pet", "golden", "estadisticas", "outcome")
              if r.get(k) is not None}
        r2["heroes"] = [_compactar_heroe(h) for h in r.get("heroes") or []]
        rondas.append(r2)
    plantilla = lambda h: {"tid": h.get("tid"), "quality": h.get("quality"), "sig": h.get("sig"),
                           "engraving": h.get("engraving")}
    return {
        "id": detalle.get("id"), "playedAt": detalle.get("playedAt"), "result": detalle.get("result"),
        "rounds": rondas,
        "roster": [{"id": h.get("id")} for h in detalle.get("roster") or []],
        "borrow": [plantilla(h) for h in detalle.get("borrow") or []],
        "test": [plantilla(h) for h in detalle.get("test") or []],
        "collectionTags": detalle.get("collectionTags") or {}, "gearOptions": detalle.get("gearOptions") or {},
        "tree": detalle.get("tree") or {},
    }


def exportar_runs(carpeta, destino, progreso=_sin_progreso):
    """Guarda las runs de NC de una carpeta en un .json para compartir (con SP y estadísticas). Devuelve n."""
    carpeta = Path(carpeta)
    ficha = _leer_json(carpeta / f"{carpeta.name}.json") or {}
    lista = {str(r.get("id")): r for r in _leer_json(carpeta / "runs.json") or []}
    runs = []
    archivos = sorted((carpeta / "detalles").glob("*.json"))
    for i, archivo in enumerate(archivos, 1):
        detalle = _leer_json(archivo)
        if not isinstance(detalle, dict) or not detalle.get("rounds"):
            continue
        resumen = lista.get(archivo.stem) or {}
        detalle.setdefault("playedAt", resumen.get("playedAt"))
        if not detalle.get("result"):
            detalle["result"] = resumen.get("result") or {}
        runs.append(_compactar_para_compartir(detalle))
        if i % 50 == 0:
            progreso(tr("   {0}/{1} runs", i, len(archivos)))
    datos = {"format": FORMATO_RUNS_APP, "version": 1, "nombre": ficha.get("name") or carpeta.name,
             "servidor": ficha.get("svr_id") or (carpeta.name if carpeta.name.isdigit() else ""), "runs": runs}
    _escribir_json(Path(destino), datos)
    return len(runs)


def resumen_runs_app(datos):
    runs = datos.get("runs") or []
    fechas = sorted(str(r.get("playedAt") or "")[:10] for r in runs if r.get("playedAt"))
    return {"nc": len(runs), "otros": 0, "desde": fechas[0] if fechas else "", "hasta": fechas[-1] if fechas else "",
            "nombre": datos.get("nombre"), "servidor": datos.get("servidor")}


def importar_runs_app(base_dir, datos, carpeta, progreso=_sin_progreso):
    """
    Importa un .json de runs compartido. Las runs que ya tienes (misma fecha) solo reciben lo que les falte:
    el héroe del SP y las estadísticas. Las nuevas se agregan completas.
    """
    from .optimizador import SP_DESCONOCIDO
    base_dir, carpeta = Path(base_dir), Path(carpeta)
    ficha = _leer_json(carpeta / f"{carpeta.name}.json") or {}
    es_amigo = bool(ficha.get("amigo"))
    personaje = str(ficha.get("uid") or carpeta.name)
    lista = _leer_json(carpeta / "runs.json") or []
    por_fecha = {r.get("playedAt"): r.get("id") for r in lista}
    dueno = ficha.get("name") if es_amigo else None
    nuevas, completadas = [], 0
    runs = datos.get("runs") or []
    for i, run in enumerate(runs, 1):
        existente = por_fecha.get(run.get("playedAt"))
        if existente:
            ruta = carpeta / "detalles" / f"{existente}.json"
            detalle = _leer_json(ruta)
            if isinstance(detalle, dict) and _completar_desde(detalle, run, SP_DESCONOCIDO):
                _escribir_json(ruta, detalle)
                completadas += 1
            continue
        rid = str(run.get("id"))
        rid = rid if rid.startswith(PREFIJO_ID) else f"{PREFIJO_ID}{rid}"
        detalle = dict(run, id=rid, kind="import", importado=True, owner=dueno)
        detalle.pop("_firmas", None)
        _escribir_json(carpeta / "detalles" / f"{rid}.json", detalle)
        nuevas.append({"id": rid, "character": personaje, "playedAt": run.get("playedAt"),
                       "result": run.get("result") or {}, "owner": dueno, "mine": not es_amigo,
                       "amigo": es_amigo, "importado": True})
        if i % 50 == 0:
            progreso(tr("   {0}/{1} runs revisadas", i, len(runs)))
    if nuevas:
        lista = sorted(lista + nuevas, key=lambda r: str(r.get("playedAt") or ""), reverse=True)
        _escribir_json(carpeta / "runs.json", lista, indent=4)
        if not es_amigo:
            _agregar_a_lista_global(base_dir, nuevas)
    return {"nuevas": len(nuevas), "ya_estaban": len(runs) - len(nuevas), "completadas": completadas,
            "carpeta": carpeta, "amigo": es_amigo}


def _completar_desde(detalle, run, desconocido):
    """Copia a un detalle que ya tienes el SP (si no lo sabías) y las estadísticas de la misma run."""
    cambio = False
    for rs, ro in zip(sorted(detalle.get("rounds") or [], key=lambda x: x.get("index", 0)),
                      sorted(run.get("rounds") or [], key=lambda x: x.get("index", 0))):
        if str(rs.get("bossId")) != str(ro.get("bossId")):
            continue
        if rs.get("golden") in (None, desconocido) and ro.get("golden") not in (None, desconocido):
            rs["golden"] = ro["golden"]
            cambio = True
        if ro.get("estadisticas") and not rs.get("estadisticas"):
            rs["estadisticas"] = ro["estadisticas"]
            cambio = True
        por_slot = {h.get("slot"): h for h in ro.get("heroes") or []}
        for h in rs.get("heroes") or []:
            otro = por_slot.get(h.get("slot"))
            if otro and otro.get("stats") and not h.get("stats"):
                h["stats"] = otro["stats"]
                cambio = True
    return cambio
