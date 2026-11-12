"""
Estado actual de la cuenta (lo que el sitio obtuvo en el último fetch) guardado localmente.

Fuentes:
- /api/inventory: captura del último fetch del servidor seleccionado (recursos, monedas,
  equipo de reserva, artefactos, mascotas, árbol, héroes temporales). Pesa ~20 MB: se guarda
  solo lo necesario.
- /api/nc-sim/source de tu run más reciente: trae tu roster y colecciones ya procesados
  (SI, grabado, muebles, equipo, colección) en el mismo formato que las rondas de NC.

Se guarda en cuentas/<cuenta>/<servidor>/cuenta_actual.json
"""
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from .rutas import cargar_mapa_personajes, carpeta_personaje
from .scraper import REQUEST_TIMEOUT, _abrir, _sin_progreso, actualizar_tablas_sitio
from .visuales import Visuales
from idiomas import tr

ARCHIVO_CUENTA_ACTUAL = "cuenta_actual.json"


def ruta_cuenta_actual(carpeta_servidor):
    return Path(carpeta_servidor) / ARCHIVO_CUENTA_ACTUAL


def cargar_cuenta_actual(carpeta_servidor):
    archivo = ruta_cuenta_actual(carpeta_servidor)
    if not archivo.exists():
        return None
    try:
        return json.loads(archivo.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def hace_cuanto(iso):
    """'hace 3 h', 'hace 2 días'..."""
    if not iso:
        return tr("nunca")
    try:
        momento = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except ValueError:
        return str(iso)
    segundos = int((datetime.now(timezone.utc) - momento).total_seconds())
    if segundos < 90:
        return tr("hace un momento")
    if segundos < 3600:
        return tr("hace {0} min", segundos // 60)
    if segundos < 86400:
        return tr("hace {0} h", segundos // 3600)
    dias = segundos // 86400
    return tr("hace {0} días", dias) if dias != 1 else tr("hace 1 día")


# ============================================================
# Compactar /api/inventory
# ============================================================

def _etiqueta(labels, tabla, ident):
    return (labels.get(tabla) or {}).get(str(ident)) or {}


def compactar_inventario(inv):
    """De la respuesta de /api/inventory deja solo lo que la app muestra."""
    datos = inv.get("data") or {}
    labels = datos.get("labels") or {}

    def objeto(ident, cantidad, tabla="Item"):
        e = _etiqueta(labels, tabla, ident)
        return {
            "id": ident,
            "cantidad": cantidad,
            "nombre": e.get("name") or f"{tabla} {ident}",
            "categoria": e.get("category") or "",
            "calidad": e.get("quality"),
            "descripcion": e.get("description") or "",
            "imageUrl": e.get("imageUrl"),
        }

    monedas = datos.get("currencies") or {}
    lista_monedas = []
    if monedas.get("gold") is not None:
        lista_monedas.append({"id": "gold", "nombre": "Oro", "cantidad": monedas.get("gold"), "imageUrl": None})
    if monedas.get("diamonds") is not None:
        lista_monedas.append({"id": "diamonds", "nombre": "Diamantes", "cantidad": monedas.get("diamonds"),
                              "imageUrl": None})
    for m in monedas.get("other") or []:
        lista_monedas.append(objeto(m.get("type"), m.get("cnt")))

    equipo = []
    for g in datos.get("equipmentInventory") or []:
        e = _etiqueta(labels, "Equip", g.get("tid"))
        equipo.append({
            "id": g.get("id"), "tid": g.get("tid"), "cantidad": g.get("amount"),
            "estrellas": g.get("enhance_lv"), "faccion": (g.get("attrs") or {}).get("hero_tag"),
            "nombre": e.get("name") or f"Equipo {g.get('tid')}", "categoria": e.get("category") or "",
            "calidad": e.get("quality"), "imageUrl": e.get("imageUrl"),
        })

    mascotas = []
    for p in datos.get("pets") or []:
        e = _etiqueta(labels, "Pet", p.get("tid"))
        mascotas.append({
            "id": p.get("id"), "tid": p.get("tid"), "nombre": e.get("name") or f"Mascota {p.get('tid')}",
            "nivel": p.get("pg_lv"), "trabajos": [j.get("lv") for j in p.get("job_lv") or []],
            "imageUrl": e.get("imageUrl"),
        })

    artefactos = []
    for a in datos.get("artifacts") or []:
        e = _etiqueta(labels, "Artifact", a.get("tid"))
        artefactos.append({"id": a.get("id"), "tid": a.get("tid"), "despertar": a.get("awaken_lv"),
                           "nombre": e.get("name") or f"Artefacto {a.get('tid')}", "imageUrl": e.get("imageUrl"),
                           "descripcion": e.get("description") or ""})

    return {
        "capturedAt": inv.get("capturedAt") or datos.get("capturedAt"),
        "cuenta": datos.get("account") or {},
        "arbol": datos.get("elderTree") or {},
        "monedas": lista_monedas,
        "objetos": [objeto(i.get("id"), i.get("amount")) for i in datos.get("items") or []],
        "equipo_reserva": equipo,
        "mascotas": mascotas,
        "artefactos": artefactos,
        "heroes_temporales": [str(h.get("id")) for h in datos.get("temporaryHeroes") or []],
        # dimensionales arrendados (source_type 4): son tuyos, los subes tú
        "heroes_arrendados": [str(h.get("id")) for h in datos.get("temporaryHeroes") or []
                              if str(h.get("source_type")) in ("4", "None")],
        "heroes_basicos": [
            {"id": str(h.get("id")), "tid": h.get("tid"), "nivel": h.get("level"), "calidad": h.get("quality"),
             "source_type": h.get("source_type"), "nombre": h.get("name")}
            for h in datos.get("heroes") or []
        ],
        "copias_base": [
            {"id": str(h.get("id")), "tid": h.get("tid"), "calidad": h.get("quality"), "nombre": h.get("name"),
             "imageUrl": h.get("imageUrl"), "faccion": h.get("faction"), "clase": h.get("class")}
            for h in datos.get("baseHeroCopies") or []
        ],
        "cobertura": datos.get("coverage") or {},
        # TODAS las colecciones de la cuenta (equipadas o no), tal como vienen del fetch
        "colecciones_fetch": [_coleccion_de_fetch(c) for c in datos.get("collections") or []],
        # héroe -> {colección equipada ahora, calidad ahora}
        "heroes_fetch": {
            str(h.get("id")): {"coleccion": str((h.get("mitama_unit") or {}).get("id") or "") or None,
                               "calidad": h.get("quality"), "nombre": h.get("name"), "tid": h.get("tid")}
            for h in (datos.get("heroes") or []) + (datos.get("temporaryHeroes") or [])
        },
    }


def _entero(v, defecto=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return defecto


def _coleccion_de_fetch(c):
    """Colección de /api/inventory en el mismo formato que las de NC (id, tid, level, mythic, affixes)."""
    afijos = []
    for ranura in sorted(c.get("slot_affixs") or [], key=lambda x: _entero(x.get("slot"))):
        a = ranura.get("affix") or {}
        if a.get("nature") is not None:
            afijos.append({"nature": _entero(a.get("nature")), "quality": _entero(a.get("quality"))})
    return {"id": str(c.get("id")), "tid": _entero(c.get("tid")), "level": _entero(c.get("level")),
            "mythic": sum(1 for a in afijos if a["quality"] >= 5), "affixes": afijos,
            "locked": bool(c.get("locked"))}


def completar_imagenes(estado, vis):
    """Mascotas sin imagen en el inventario: usar la de las tablas del sitio."""
    mascotas_sitio = (vis.t.get("mascotas") or {}) if vis is not None else {}
    for p in estado.get("mascotas") or []:
        if not p.get("imageUrl"):
            info = mascotas_sitio.get(str(p.get("tid"))) or {}
            p["imageUrl"] = info.get("high") or info.get("low")


def urls_visuales_cuenta(estado, vis):
    """Todas las piezas que dibujan las vistas de la cuenta (retratos, SI, equipo, colecciones, afijos)."""
    urls = set(vis.urls_fijas())
    for h in estado.get("roster") or []:
        urls.update(vis.urls_de_ronda({"bossId": None, "heroes": [h]}))
    for c in estado.get("colecciones") or []:
        urls.add(vis.imagen_coleccion(c.get("tid")))
        for a in c.get("affixes") or []:
            urls.add(vis.afijo(a.get("nature"), a.get("quality"))[1])
    for p in estado.get("mascotas") or []:
        urls.add(p.get("imageUrl"))
    return {u for u in urls if u}


def _run_mas_reciente(carpeta_servidor):
    archivo = Path(carpeta_servidor) / "runs.json"
    try:
        runs = json.loads(archivo.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    runs = [r for r in runs if r.get("mine") is True and r.get("id")]
    return max(runs, key=lambda r: str(r.get("playedAt") or ""), default=None)


# ============================================================
# Sincronizar
# ============================================================

async def sincronizar_cuenta(perfil_path, base_dir, progreso=_sin_progreso):
    """
    Guarda el estado actual de la cuenta del último fetch en cuentas/<cuenta>/<servidor>/cuenta_actual.json.
    Retorna (carpeta_servidor, resumen).
    """
    base_dir = Path(base_dir)
    s = _abrir(perfil_path, progreso)

    # Tablas del sitio al día: nombres e imágenes de equipo, SI, afijos, colecciones, mascotas...
    try:
        actualizar_tablas_sitio(s, base_dir, progreso)
    except Exception as error:
        progreso(tr('   ⚠ No se pudieron actualizar las tablas del sitio: {0}', (str(error).splitlines() or [''])[0]))

    progreso(tr("Descargando captura de la cuenta (/api/inventory, ~20 MB)..."))
    r = s.json("/api/inventory", x_page="/inventory", timeout=REQUEST_TIMEOUT * 2)
    if r["status"] != 200 or not isinstance(r["body"], dict) or "inventory" not in r["body"]:
        raise RuntimeError(tr('No se pudo leer el inventario (HTTP {0}).', r['status']))
    compacto = compactar_inventario(r["body"]["inventory"])
    uid = str((compacto.get("cuenta") or {}).get("id") or "")
    progreso(tr('Captura del {0} · personaje {1} · nivel {2}', compacto['capturedAt'], uid, (compacto.get('cuenta') or {}).get('level')))

    mapa = cargar_mapa_personajes(base_dir)
    carpeta = carpeta_personaje(base_dir, mapa, uid)
    carpeta.mkdir(parents=True, exist_ok=True)
    progreso(tr('Servidor de la captura: {0}', carpeta.name))

    # Roster y colecciones procesados (mismo formato que las rondas de NC)
    roster, colecciones, mascotas_roster = [], [], []
    run = _run_mas_reciente(carpeta)
    if run:
        progreso(tr("Leyendo tu roster y colecciones actuales..."))
        rd = s.json(f"/api/nc-sim/source?kind=own&id={run['id']}", x_page="/nc-simulator", timeout=REQUEST_TIMEOUT)
        if rd["status"] == 200 and isinstance(rd["body"], dict):
            roster = rd["body"].get("roster") or []
            colecciones = rd["body"].get("collections") or []
            mascotas_roster = (rd["body"].get("pets") or {}).get("roster") or []
    else:
        progreso(tr("   ⚠ Sin runs de NC en este servidor: no se puede leer el roster procesado."))

    vis = Visuales(base_dir)
    fecha_run = (run or {}).get("playedAt")
    # Colecciones: todas las de la cuenta (fetch). Si el sitio no las trae, las de la run.
    tags = {str(c.get("tid")): c.get("tag") for c in colecciones if c.get("tag") is not None}
    anteriores = cargar_cuenta_actual(carpeta) or {}
    tags.update({str(c.get("tid")): c.get("tag") for c in anteriores.get("colecciones") or []
                 if c.get("tag") is not None and str(c.get("tid")) not in tags})
    if compacto.get("colecciones_fetch"):
        colecciones = []
        for c in compacto["colecciones_fetch"]:
            colecciones.append({**c, "name": vis.nombre_coleccion(c["tid"]), "tag": tags.get(str(c["tid"]))})
        fuente_colecciones = "fetch"
    else:
        fuente_colecciones = "run"
    por_id = {str(c.get("id")): c for c in colecciones}

    # Héroes: colección equipada y calidad ACTUALES (fetch); SI, grabado, muebles y equipo de la última run
    heroes_fetch = compacto.get("heroes_fetch") or {}
    for h in roster:
        actual = heroes_fetch.get(str(h.get("id")))
        if actual:
            if actual.get("calidad") is not None:
                h["quality"] = actual["calidad"]
            h["collection"] = dict(por_id[actual["coleccion"]]) if actual.get("coleccion") in por_id else None
        h["datos_run"] = fecha_run   # SI, grabado, muebles y equipo vienen de esta run

    # Colección -> héroe que la lleva (según el fetch, o según la run si no hay fetch)
    equipada_en = {}
    for hid, actual in heroes_fetch.items():
        if actual.get("coleccion"):
            equipada_en[actual["coleccion"]] = actual.get("nombre")
    if not heroes_fetch:
        for h in roster:
            col = h.get("collection") or {}
            if col.get("id") is not None:
                equipada_en[str(col["id"])] = h.get("name")
    for c in colecciones:
        c["equipada_en"] = equipada_en.get(str(c.get("id")))

    temporales = set(compacto["heroes_temporales"])
    arrendados = set(compacto.get("heroes_arrendados", compacto["heroes_temporales"]))
    for h in roster:
        h["temporal"] = str(h.get("id")) in temporales
        h["arrendado"] = str(h.get("id")) in arrendados

    estado = {
        **compacto,
        "sincronizado": datetime.now(timezone.utc).isoformat(),
        "servidor": carpeta.name,
        "roster": roster,
        "colecciones": colecciones,
        "mascotas_roster": mascotas_roster,
        "fuente_colecciones": fuente_colecciones,
        "fecha_run_roster": fecha_run,
    }
    estado.pop("colecciones_fetch", None)   # ya están en "colecciones"
    completar_imagenes(estado, vis)
    ruta_cuenta_actual(carpeta).write_text(json.dumps(estado, ensure_ascii=False), encoding="utf-8")
    progreso(tr('Guardado: {0} objetos, {1} monedas, {2} héroes, {3} colecciones, {4} piezas de equipo de reserva.', len(estado['objetos']), len(estado['monedas']), len(roster), len(colecciones), len(estado['equipo_reserva'])))
    libres = sum(1 for c in colecciones if not c.get("equipada_en"))
    progreso(tr('Colecciones de la cuenta: {0} ({1} libres, {2} equipadas).', len(colecciones), libres, len(colecciones) - libres))

    # Íconos del inventario (requieren sesión)
    await _descargar_iconos(s, base_dir, estado, progreso, Visuales(base_dir))
    return carpeta, estado


async def _descargar_iconos(s, base_dir, estado, progreso, vis=None):
    urls = set()
    for lista in ("monedas", "objetos", "equipo_reserva", "mascotas", "artefactos"):
        urls.update(o.get("imageUrl") for o in estado.get(lista) or [])
    for h in estado.get("roster") or []:
        urls.add(h.get("imageUrl"))
    if vis is not None and vis.disponible:
        urls.update(urls_visuales_cuenta(estado, vis))
    urls = {u for u in urls if u and u.startswith("/")}
    carpeta = Path(base_dir) / "assets"
    pendientes = [u for u in sorted(urls) if not carpeta.joinpath(*u.lstrip("/").split("/")).exists()]
    if not pendientes:
        return
    progreso(tr('Descargando {0} íconos nuevos...', len(pendientes)))
    for i, url in enumerate(pendientes, 1):
        destino = carpeta.joinpath(*url.lstrip("/").split("/"))
        error = s.descargar(url, destino)
        if error:
            progreso(f"   ⚠ {url}: {error}")
        if i % 25 == 0:
            progreso(tr('   {0}/{1} íconos', i, len(pendientes)))
        await asyncio.sleep(0.03)


# ============================================================
# Héroes que tienes (desarrollados + copias base)
# ============================================================

def _norm(texto):
    import unicodedata
    texto = unicodedata.normalize("NFD", str(texto or "").lower())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn").strip()


def es_arrendado_cuenta(h, estado):
    """Héroe del roster que es un dimensional arrendado (tuyo)."""
    if h.get("arrendado"):
        return True
    return bool(h.get("temporal")) and "heroes_arrendados" not in (estado or {})


def indice_heroes(estado):
    """
    Todos tus héroes por nombre (y por nombre corto antes de " - "):
      - los desarrollados (roster con build completa) y
      - los que solo tienes como copia base (élite, legendaria... sin desarrollar).
    Cada entrada es un dict de héroe con, además:
      calidad_max: tu mejor copia · copias: calidades de las copias base · solo_copias: True si no está desarrollado.
    """
    estado = estado or {}
    copias_por_tid = {}
    for c in estado.get("copias_base") or []:
        copias_por_tid.setdefault(str(c.get("tid")), []).append(c)
    indice = {}

    def registrar(heroe):
        for nombre in (heroe.get("name"), str(heroe.get("name") or "").split(" - ")[0]):
            if nombre:
                indice.setdefault(_norm(nombre), heroe)

    vistos = set()
    for h in estado.get("roster") or []:
        if h.get("temporal") and not es_arrendado_cuenta(h, estado):
            continue
        copias = copias_por_tid.get(str(h.get("tid")), [])
        q = max([int(h.get("quality") or 0)] + [int(c.get("calidad") or 0) for c in copias])
        registrar({**h, "calidad_max": q, "copias": sorted((int(c.get("calidad") or 0) for c in copias), reverse=True),
                   "solo_copias": False})
        vistos.add(str(h.get("tid")))
    for tid, copias in copias_por_tid.items():
        if tid in vistos or not copias[0].get("nombre"):
            continue
        calidades = sorted((int(c.get("calidad") or 0) for c in copias), reverse=True)
        registrar({"name": copias[0]["nombre"], "tid": tid, "quality": calidades[0], "calidad_max": calidades[0],
                   "imageUrl": copias[0].get("imageUrl"), "faction": copias[0].get("faccion"),
                   "copias": calidades, "solo_copias": True})
    return indice


def buscar_heroe(indice, *nombres):
    for n in nombres:
        if n:
            for clave in (_norm(n), _norm(str(n).split(" - ")[0])):
                if clave in indice:
                    return indice[clave]
    return None


# ============================================================
# Cruce con NC
# ============================================================

def uso_en_nc(comps, tid=None, coleccion_id=None, solo_propios=True):
    """
    Cómo se usó un héroe (por tid) o una colección (por id) en tus runs de NC.
    Retorna {"equipos": n, "por_jefe": {boss: (mejor_tiempo, usos)}}.
    """
    por_jefe = {}
    total = 0
    for c in comps:
        if not c.derrotado or c.tiempo <= 0:
            continue
        for h, origen in zip(c.heroes, c.hero_origenes or ("propio",) * len(c.heroes)):
            if solo_propios and origen != "propio":
                continue
            if tid is not None and str(h.get("tid")) != str(tid):
                continue
            if coleccion_id is not None and str((h.get("collection") or {}).get("id")) != str(coleccion_id):
                continue
            total += 1
            mejor, usos = por_jefe.get(c.boss_id, (float("inf"), 0))
            por_jefe[c.boss_id] = (min(mejor, c.tiempo), usos + 1)
            break
    return {"equipos": total, "por_jefe": por_jefe}
