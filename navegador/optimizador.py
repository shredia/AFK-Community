"""
Optimizador Nightmare Corridor (port del módulo VBA NC_Optimizador.bas).

- La rotación son 6 Boss_ID. Los candidatos de cada posición se buscan por Boss_ID,
  así una rotación nueva aprovecha los equipos usados contra ese jefe en cualquier rotación.
- No se puede repetir un héroe entre jefes; las mascotas opcionalmente tampoco.
- Equipos idénticos (mismos 5 héroes + mascota) solo aportan su mejor tiempo.
- Búsqueda por ramificación y poda con límite de tiempo.
"""
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from idiomas import tr, N_

VERSION_INDICE = 5          # 2: cada héroe trae "origen" (propio / prestado / prueba / ...)
ARCHIVO_INDICE = "optimizador_indice.json"
ARCHIVO_BANEOS = "baneos.json"

# Origen de cada héroe usado en una ronda
PROPIO = "propio"                  # está en tu roster
PRESTADO = "prestado"              # copia temporal = plantilla de mercenario (borrow)
PRUEBA = "prueba"                  # copia temporal = plantilla de prueba (test)
TEMPORAL = "temporal"              # copia temporal que no calza con ninguna plantilla
FUERA_ROSTER = "fuera_roster"      # id normal, pero ya no está en tu roster
TEMPORALES = (PRESTADO, PRUEBA, TEMPORAL)
NOMBRES_ORIGEN = {
    PROPIO: N_("Propio"),
    PRESTADO: N_("Prestado (mercenario)"),
    PRUEBA: N_("De prueba"),
    TEMPORAL: N_("Prestado / de prueba"),
    FUERA_ROSTER: N_("Ya no está en tu roster"),
}
ID_TEMPORAL_MIN = 2 ** 32          # el juego da ids ≥ 2^32 a las copias temporales


# ============================================================
# ÍNDICE COMPACTO (evita leer ~0,1 s por cada detalle en cada apertura)
# ============================================================

def _compactar_heroe(h):
    h = dict(h)
    # engravingNodes es enorme; se guarda solo lo necesario para mostrarlo
    h["engravingNodes"] = [
        {"key": n.get("key"), "level": n.get("level"), "max": n.get("max"), "stats": n.get("stats")}
        for n in h.get("engravingNodes") or []
    ]
    return h


def _firma_stats(h):
    return (h.get("quality"), h.get("sig"), h.get("engraving"))


def es_id_temporal(hid):
    try:
        return int(str(hid)) >= ID_TEMPORAL_MIN
    except ValueError:
        return False


def es_arrendado(h):
    """
    Héroe dimensional arrendado: es TUYO (lo asciendes, le cambias colección, SI...), aunque el juego lo
    marque 'borrowed'. Los prestados de verdad (mercenarios) tienen ids temporales (≥ 2^32).
    """
    return bool(h.get("arrendado")) or (bool(h.get("prestado")) and not es_id_temporal(h.get("id")))


def origen_heroe(h, ids_roster, plantillas_borrow, plantillas_test):
    """Clasifica la copia del héroe usada en una ronda."""
    hid = str(h.get("id") or "")
    if es_arrendado(h):            # dimensional arrendado: cuenta como tuyo
        return PROPIO
    if h.get("prestado"):          # runs importadas (afk-runs.json): el archivo dice si era prestado
        return PRESTADO
    temporal = es_id_temporal(hid)
    if hid in ids_roster and not temporal:   # un id temporal nunca es tuyo (mercenario / prueba)
        return PROPIO
    if temporal:
        tid = str(h.get("tid"))
        if plantillas_test.get(tid) == _firma_stats(h):
            return PRUEBA
        if plantillas_borrow.get(tid) == _firma_stats(h):
            return PRESTADO
        return TEMPORAL
    return FUERA_ROSTER if ids_roster else PROPIO


def _extraer_run(detalle, resumen):
    ids_roster = {str(h.get("id")) for h in detalle.get("roster") or []}
    borrow = {str(h.get("tid")): _firma_stats(h) for h in detalle.get("borrow") or []}
    test = {str(h.get("tid")): _firma_stats(h) for h in detalle.get("test") or []}
    rondas = []
    for r in detalle.get("rounds") or []:
        heroes = []
        for h in r.get("heroes") or []:
            compacto = _compactar_heroe(h)
            compacto["origen"] = origen_heroe(h, ids_roster, borrow, test)
            if es_arrendado(h):
                compacto["arrendado"] = True
                compacto.pop("prestado", None)
            heroes.append(compacto)
        rondas.append({
            "index": r.get("index", 0),
            "bossId": str(r.get("bossId")),
            "recorded": r.get("recorded") or {},
            "golden": r.get("golden"),
            "estadisticas": r.get("estadisticas") or {},   # daño de mascota / jefe (runs importadas)
            "pet": r.get("pet") or {},
            "heroes": heroes,
        })
    return {
        "id": str(detalle.get("id") or resumen.get("id")),
        # las runs importadas (afk-runs.json) traen fecha y resultado en el propio detalle
        "playedAt": resumen.get("playedAt") or detalle.get("playedAt") or "",
        "result": resumen.get("result") or detalle.get("result") or {},
        "rounds": rondas,
    }


def _extraer_referencias(detalle):
    return {
        "collectionTags": detalle.get("collectionTags") or {},
        "gearOptions": detalle.get("gearOptions") or {},
        "tree": detalle.get("tree") or {},
    }


def cargar_indice(carpeta_servidor, progreso=lambda m: None):
    """
    Devuelve {"runs": [...], "refs": {...}} para un servidor, usando un índice en disco
    que solo se actualiza con los detalles nuevos o modificados.
    """
    carpeta = Path(carpeta_servidor)
    archivo_indice = carpeta / ARCHIVO_INDICE
    detalles = sorted((carpeta / "detalles").glob("*.json"))

    resumenes = {}
    archivo_runs = carpeta / "runs.json"
    if archivo_runs.exists():
        try:
            resumenes = {str(r.get("id")): r for r in json.loads(archivo_runs.read_text(encoding="utf-8"))}
        except (OSError, json.JSONDecodeError):
            pass

    indice = {"version": VERSION_INDICE, "archivos": {}, "runs": {}, "refs": {}}
    if archivo_indice.exists():
        try:
            previo = json.loads(archivo_indice.read_text(encoding="utf-8"))
            if previo.get("version") == VERSION_INDICE:
                indice = previo
        except (OSError, json.JSONDecodeError):
            pass

    actuales = {f.name: f.stat().st_mtime for f in detalles}
    nuevos = [f for f in detalles if indice["archivos"].get(f.name) != actuales[f.name]]
    borrados = set(indice["archivos"]) - set(actuales)

    for nombre in borrados:
        indice["archivos"].pop(nombre, None)
        indice["runs"].pop(Path(nombre).stem, None)

    for i, archivo in enumerate(nuevos, 1):
        progreso(tr('Indexando detalle {0}/{1}...', i, len(nuevos)))
        try:
            detalle = json.loads(archivo.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        rid = archivo.stem
        indice["runs"][rid] = _extraer_run(detalle, resumenes.get(rid, {}))
        indice["archivos"][archivo.name] = actuales[archivo.name]
        if detalle.get("gearOptions") or not indice["refs"]:
            indice["refs"] = _extraer_referencias(detalle)

    # Los resúmenes (fecha, resultado) pueden llegar después que el detalle
    for rid, run in indice["runs"].items():
        if rid in resumenes:
            run["playedAt"] = resumenes[rid].get("playedAt", run.get("playedAt", ""))
            run["result"] = resumenes[rid].get("result") or run.get("result") or {}

    if nuevos or borrados:
        progreso(tr("Guardando índice..."))
        archivo_indice.write_text(json.dumps(indice, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    return {"runs": list(indice["runs"].values()), "refs": indice["refs"]}


# ============================================================
# COMPOSICIONES
# ============================================================

def _clave(valor):
    return str(valor if valor is not None else "").strip().upper()


@dataclass
class Composicion:
    run_id: str
    fecha: str
    rotacion: str
    posicion: int            # 1..6 dentro de su run
    boss_id: str
    tiempo: float            # segundos (0 si no lo derrotó)
    derrotado: bool
    run_completa: bool
    heroes: list             # dicts completos, ordenados por slot
    mascota: dict
    golden: object = None
    hero_ids: tuple = ()     # tid (o nombre) en mayúsculas
    hero_nombres: tuple = ()
    mascota_id: str = ""
    mascota_nombre: str = ""
    hero_origenes: tuple = ()  # PROPIO / PRESTADO / PRUEBA / TEMPORAL / FUERA_ROSTER
    veces: int = 1           # cuántas veces se usó este mismo equipo contra el jefe
    estadisticas: dict = field(default_factory=dict)   # {"mascota": {...}, "jefe": {...}} si las hay
    sp_manual: bool = False  # el héroe del SP lo marcaste tú (había varios especiales)

    @property
    def firma(self):
        # Una copia prestada/de prueba se considera distinta de la propia (otra build)
        partes = [i if o == PROPIO else f"{i}*{o}" for i, o in zip(self.hero_ids, self.hero_origenes)]
        return "|".join(sorted(partes)) + "|P:" + self.mascota_id

    @property
    def no_propios(self):
        return [(h, o) for h, o in zip(self.heroes, self.hero_origenes) if o != PROPIO]


SP_DESCONOCIDO = "?"   # varios héroes especiales y el dato no dice cuál usó su Special Power


def deducir_golden(heroes, golden):
    """
    Slot del héroe que usó su Special Power. Solo los héroes especiales (hyper) lo tienen:
    con uno solo en el equipo se activa automáticamente; con dos o más se elige uno.
    Si el dato no viene (runs importadas de afk-runs.json): uno -> ese; varios -> SP_DESCONOCIDO.
    """
    if golden not in (None, ""):
        return golden
    especiales = [h.get("slot") for h in heroes if h.get("hyper")]
    if len(especiales) == 1:
        return especiales[0]
    return SP_DESCONOCIDO if especiales else None


ARCHIVO_SP = "sp_manual.json"   # {"<run_id>|<posición>": slot} cuando hay varios especiales


def _clave_sp(comp):
    return f"{comp.run_id}|{comp.posicion}"


def cargar_sp_manual(carpeta):
    try:
        datos = json.loads((Path(carpeta) / ARCHIVO_SP).read_text(encoding="utf-8"))
        return datos if isinstance(datos, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def aplicar_sp_manual(comps, carpeta):
    """Pone en cada ronda dudosa el héroe del SP que marcaste a mano."""
    manual = cargar_sp_manual(carpeta)
    if not manual:
        return comps
    for c in comps:
        slot = manual.get(_clave_sp(c))
        if slot is not None and (c.golden in (None, SP_DESCONOCIDO) or c.sp_manual):
            c.golden, c.sp_manual = slot, True
    return comps


def guardar_sp_manual(carpeta, comp, slot):
    """Guarda (o borra, con slot None) el héroe del SP de una ronda."""
    manual = cargar_sp_manual(carpeta)
    if slot is None:
        manual.pop(_clave_sp(comp), None)
    else:
        manual[_clave_sp(comp)] = slot
    (Path(carpeta) / ARCHIVO_SP).write_text(json.dumps(manual, ensure_ascii=False, indent=1), encoding="utf-8")


def arrendados_de(estado):
    """Ids de héroes dimensionales arrendados según la captura de la cuenta."""
    estado = estado or {}
    if "heroes_arrendados" in estado:
        return estado.get("heroes_arrendados") or ()
    return estado.get("heroes_temporales") or ()   # capturas viejas: los temporales eran los arrendados


def construir_composiciones(runs, heroes_temporales=(), heroes_arrendados=None):
    """
    Una composición por (run, jefe).
    heroes_temporales: ids que el inventario marca como temporales (colaboraciones de prueba);
    si aparecen como "ya no está en tu roster" se reclasifican como "de prueba".
    """
    temporales = {str(i) for i in heroes_temporales}
    arrendados = temporales if heroes_arrendados is None else {str(i) for i in heroes_arrendados}
    comps = []
    for run in runs:
        rondas = sorted(run.get("rounds") or [], key=lambda r: r.get("index", 0))
        if not rondas:
            continue
        rotacion = "-".join(str(r.get("bossId")) for r in rondas)
        resultado = run.get("result") or {}

        def derrotado(r):
            rec = r.get("recorded") or {}
            return bool(rec.get("timeMs")) and (rec.get("bossesKilled") or 0) >= 1

        if resultado.get("bossesKilled") is not None:
            completa = resultado.get("bossesKilled") == 6
        else:
            completa = len(rondas) == 6 and all(derrotado(r) for r in rondas)

        for r in rondas:
            heroes = sorted(r.get("heroes") or [], key=lambda h: h.get("slot", 0))
            mascota = r.get("pet") or {}
            ids, nombres, origenes = [], [], []
            for h in heroes:
                nombre = _clave(h.get("name"))
                ident = _clave(h.get("tid")) or nombre
                ids.append(ident)
                nombres.append(nombre)
                origen = h.get("origen") or PROPIO
                if str(h.get("id")) in arrendados and not es_id_temporal(h.get("id")):
                    origen = PROPIO          # dimensional arrendado (ya vencido o no): era tuyo
                    h["origen"], h["arrendado"] = PROPIO, True
                elif origen == FUERA_ROSTER and str(h.get("id")) in temporales:
                    origen = PRUEBA
                    h["origen"] = PRUEBA  # para que el retrato y el detalle lo muestren igual
                origenes.append(origen)
            rec = r.get("recorded") or {}
            comps.append(Composicion(
                run_id=str(run.get("id")),
                fecha=str(run.get("playedAt") or ""),
                rotacion=rotacion,
                posicion=int(r.get("index", 0)) + 1,
                boss_id=str(r.get("bossId")),
                tiempo=(rec.get("timeMs") or 0) / 1000,
                derrotado=derrotado(r),
                run_completa=completa,
                heroes=heroes,
                mascota=mascota,
                golden=deducir_golden(heroes, r.get("golden")),
                estadisticas=r.get("estadisticas") or {},
                hero_ids=tuple(ids),
                hero_nombres=tuple(nombres),
                mascota_id=_clave(mascota.get("tid")) or _clave(mascota.get("name")),
                mascota_nombre=_clave(mascota.get("name")),
                hero_origenes=tuple(origenes),
            ))
    return comps


def rotacion_mas_reciente(runs):
    if not runs:
        return []
    ultima = max(runs, key=lambda r: str(r.get("playedAt") or ""))
    rondas = sorted(ultima.get("rounds") or [], key=lambda r: r.get("index", 0))
    return [str(r.get("bossId")) for r in rondas]


def catalogo(comps):
    """{"HEROE": {nombre: id}, "MASCOTA": {nombre: id}} con nombres originales."""
    cat = {"HEROE": {}, "MASCOTA": {}}
    for c in comps:
        for h in c.heroes:
            if h.get("name"):
                cat["HEROE"][h["name"]] = str(h.get("tid") or "")
        if c.mascota.get("name"):
            cat["MASCOTA"][c.mascota["name"]] = str(c.mascota.get("tid") or "")
    return cat


# ============================================================
# BANEOS
# ============================================================

def cargar_baneos(carpeta_servidor):
    archivo = Path(carpeta_servidor) / ARCHIVO_BANEOS
    if not archivo.exists():
        return []
    try:
        datos = json.loads(archivo.read_text(encoding="utf-8"))
        return [b for b in datos if isinstance(b, dict)]
    except (OSError, json.JSONDecodeError):
        return []


def guardar_baneos(carpeta_servidor, baneos):
    archivo = Path(carpeta_servidor) / ARCHIVO_BANEOS
    archivo.write_text(json.dumps(baneos, ensure_ascii=False, indent=2), encoding="utf-8")


# Alcance de un baneo de héroe según la copia usada
COPIA_TODAS = "TODAS"            # cualquier copia (propia o no)
COPIA_NO_PROPIA = "NO_PROPIA"    # solo copias prestadas / de prueba / fuera de tu roster
NOMBRES_COPIA = {COPIA_TODAS: N_("Cualquier copia"), COPIA_NO_PROPIA: N_("Solo prestada/prueba")}


def _conjunto_baneos(baneos):
    """Claves 'TIPO|NOMBRE_O_ID|ALCANCE|COPIA' de los baneos activos."""
    activos = set()
    for b in baneos:
        if not b.get("activo", True) or b.get("limite"):
            continue   # los límites de build se revisan aparte (_limites / _excede_limite)
        tipo = _clave(b.get("tipo"))
        alcance = _clave(b.get("jefe")) or "TODOS"
        copia = _clave(b.get("copia")) or COPIA_TODAS
        if tipo != "HEROE":
            copia = COPIA_TODAS
        for valor in (_clave(b.get("nombre")), _clave(b.get("id"))):
            if valor:
                activos.add(f"{tipo}|{valor}|{alcance}|{copia}")
    return activos


def _baneada(comp, posicion, activos):
    if not activos:
        return False
    alcances = ("TODOS", str(posicion), comp.boss_id)
    origenes = comp.hero_origenes or (PROPIO,) * len(comp.hero_ids)
    for alcance in alcances:
        for nombre, ident, origen in zip(comp.hero_nombres, comp.hero_ids, origenes):
            copias = (COPIA_TODAS,) if origen == PROPIO else (COPIA_TODAS, COPIA_NO_PROPIA)
            for copia in copias:
                if (f"HEROE|{nombre}|{alcance}|{copia}" in activos
                        or f"HEROE|{ident}|{alcance}|{copia}" in activos):
                    return True
        if (f"MASCOTA|{comp.mascota_nombre}|{alcance}|{COPIA_TODAS}" in activos
                or f"MASCOTA|{comp.mascota_id}|{alcance}|{COPIA_TODAS}" in activos):
            return True
    return False


# ============================================================
# OPTIMIZACIÓN
# ============================================================

@dataclass
class Opciones:
    solo_completas: bool = True
    prohibir_repetir_mascota: bool = True
    limite_por_jefe: int = 0        # 0 = todas
    tiempo_maximo: float = 60.0     # segundos
    excluir_temporales: bool = False    # equipos con héroes prestados / de prueba
    excluir_fuera_roster: bool = False  # equipos con héroes que ya no están en tu roster


@dataclass
class Resultado:
    estado: str                     # "Óptimo global", "Mejor encontrada (no certificada)", "Sin solución"
    detalle: str
    total: float = 0.0
    elegidas: list = field(default_factory=list)      # 6 Composicion o []
    candidatos: dict = field(default_factory=dict)    # posicion -> [Composicion] ordenadas
    consideradas: int = 0
    duracion: float = 0.0


# ============================================================
# LÍMITES DE BUILD ("no tengo esa colección a ★3", "mi Dracula tiene SI 20"...)
# ============================================================
# Un límite es un baneo con "limite": True:
#   {"limite": True, "objeto": "HEROE" | "COLECCION", "nombre": "Dracula" | "*", "campo": ..., "max": n,
#    "jefe": "TODOS" | posición | Boss ID, "activo": True}
# Se descarta el equipo si algún héroe supera el máximo. max = -1 en una colección = "no la tengo".
CAMPOS_HEROE = {"quality": N_("Ascensión"), "sig": N_("SI"), "engraving": N_("Grabado"), "muebles": N_("Muebles")}
CAMPOS_COLECCION = {"estrellas": N_("Nivel de habilidad (★)"), "mythic": N_("Afijos míticos"),
                    "level": N_("Nivel de colección")}


def _valor_heroe(h, campo):
    if campo == "muebles":
        return int((h.get("furniture") or {}).get("pieces") or 0)
    try:
        return int(h.get(campo) or 0)
    except (TypeError, ValueError):
        return 0


def _limites(baneos):
    salida = []
    for b in baneos:
        if b.get("limite") and b.get("activo", True):
            try:
                maximo = int(b.get("max"))
            except (TypeError, ValueError):
                continue
            salida.append((_clave(b.get("objeto")), _clave(b.get("nombre")) or "*", b.get("campo"), maximo,
                           _clave(b.get("jefe")) or "TODOS"))
    return salida


def _excede_limite(comp, posicion, limites):
    alcances = {"TODOS", str(posicion), str(comp.boss_id)}
    for objeto, nombre, campo, maximo, alcance in limites:
        if alcance not in alcances:
            continue
        for h in comp.heroes:
            if objeto == "HEROE":
                if nombre not in ("*", _clave(h.get("name"))) and nombre != _clave(h.get("tid")):
                    continue
                if _valor_heroe(h, campo) > maximo:
                    return True
            else:   # COLECCION
                col = h.get("collection") or {}
                if not col or nombre not in ("*", _clave(col.get("name"))) and nombre != _clave(col.get("tid")):
                    continue
                try:
                    valor = int(col.get(campo) or 0)
                except (TypeError, ValueError):
                    valor = 0
                if valor > maximo:
                    return True
    return False


def describir_limite(b):
    """'Colección Timeline Watch: máximo ★2' · 'Colección X: no la tengo' · 'Dracula: SI máximo 20'."""
    objeto = _clave(b.get("objeto"))
    nombre = b.get("nombre") or "*"
    quien = tr("Cualquier héroe") if nombre == "*" and objeto == "HEROE" else (
        tr("Cualquier colección") if nombre == "*" else str(nombre).split(" - ")[0])
    if objeto == "COLECCION" and nombre != "*":
        quien = tr("Colección {0}", quien)
    if int(b.get("max", 0)) < 0:
        return tr("{0}: no la tengo", quien) if objeto == "COLECCION" else tr("{0}: no lo tengo", quien)
    if objeto == "COLECCION":
        return tr("{0}: {1} máximo {2}", quien, tr(CAMPOS_COLECCION.get(b.get("campo"), b.get("campo"))),
                  b.get("max"))
    return tr("{0}: {1} máximo {2}", quien, tr(CAMPOS_HEROE.get(b.get("campo"), b.get("campo"))), b.get("max"))


def quitar_baneadas(comps, rotacion, baneos):
    """
    Las composiciones que no tocan ningún baneo ni límite (según su jefe y su posición en la rotación).
    Sirve para mezclar fuentes con baneos distintos: p. ej. tus equipos + los de amigos con 'Baneos de amigos'.
    """
    activos, limites = _conjunto_baneos(baneos), _limites(baneos)
    if not activos and not limites:
        return list(comps)
    posicion_de = {boss: i for i, boss in enumerate(rotacion, 1) if boss}
    return [c for c in comps
            if not _baneada(c, posicion_de.get(c.boss_id, 0), activos)
            and not (limites and _excede_limite(c, posicion_de.get(c.boss_id, 0), limites))]


def candidatos_por_jefe(comps, rotacion, opciones, baneos):
    """posicion (1..6) -> lista de composiciones únicas, ordenadas por tiempo."""
    activos = _conjunto_baneos(baneos)
    limites = _limites(baneos)
    posicion_de = {boss: i for i, boss in enumerate(rotacion, 1)}
    mejores = {i: {} for i in range(1, 7)}
    usos = {i: {} for i in range(1, 7)}
    consideradas = 0

    for c in comps:
        pos = posicion_de.get(c.boss_id)
        if not pos or not c.derrotado or c.tiempo <= 0:
            continue
        if opciones.solo_completas and not c.run_completa:
            continue
        if opciones.excluir_temporales and any(o in TEMPORALES for o in c.hero_origenes):
            continue
        if opciones.excluir_fuera_roster and FUERA_ROSTER in c.hero_origenes:
            continue
        if _baneada(c, pos, activos):
            continue
        if limites and _excede_limite(c, pos, limites):
            continue
        consideradas += 1
        firma = c.firma
        usos[pos][firma] = usos[pos].get(firma, 0) + 1
        if firma not in mejores[pos] or c.tiempo < mejores[pos][firma].tiempo:
            mejores[pos][firma] = c

    candidatos = {}
    for pos in range(1, 7):
        lista = sorted(mejores[pos].values(), key=lambda c: c.tiempo)
        for c in lista:
            c.veces = usos[pos][c.firma]
        if opciones.limite_por_jefe > 0:
            lista = lista[:opciones.limite_por_jefe]
        candidatos[pos] = lista
    return candidatos, consideradas


def optimizar(comps, rotacion, opciones, baneos=(), cancelar=None):
    rotacion = [str(b).strip() for b in rotacion]
    if len(rotacion) != 6 or any(not b for b in rotacion):
        return Resultado("Sin solución", tr("La rotación debe tener 6 jefes."))
    if len(set(rotacion)) != 6:
        return Resultado("Sin solución", tr("Hay jefes repetidos en la rotación."))

    candidatos, consideradas = candidatos_por_jefe(comps, rotacion, opciones, baneos)
    for pos in range(1, 7):
        if not candidatos[pos]:
            return Resultado(
                "Sin solución",
                tr("No hay composiciones elegibles para el jefe {0} (Boss {1}).", pos, rotacion[pos - 1]),
                candidatos=candidatos, consideradas=consideradas,
            )

    # Datos planos para que la búsqueda sea rápida
    cand = [[(c.tiempo, frozenset(c.hero_ids), c.mascota_id, c) for c in candidatos[p]] for p in range(1, 7)]
    min_resto = [0.0] * 7
    for nivel in range(5, -1, -1):
        min_resto[nivel] = min_resto[nivel + 1] + cand[nivel][0][0]

    estado = {"mejor": float("inf"), "elegidas": None, "agotado": False, "nodos": 0}
    inicio = time.monotonic()
    usados_h, usados_p = set(), set()
    picks = [None] * 6
    unica_mascota = opciones.prohibir_repetir_mascota

    def buscar(nivel, total):
        estado["nodos"] += 1
        if estado["nodos"] % 2048 == 0:
            if time.monotonic() - inicio > opciones.tiempo_maximo or (cancelar is not None and cancelar.is_set()):
                estado["agotado"] = True
        if estado["agotado"]:
            return
        if nivel == 6:
            if total < estado["mejor"]:
                estado["mejor"] = total
                estado["elegidas"] = list(picks)
            return
        if total + min_resto[nivel] >= estado["mejor"]:
            return
        for t, hs, pet, comp in cand[nivel]:
            if total + t + min_resto[nivel + 1] >= estado["mejor"]:
                break  # ordenados por tiempo: los siguientes son peores
            if not usados_h.isdisjoint(hs):
                continue
            if unica_mascota and pet and pet in usados_p:
                continue
            picks[nivel] = comp
            usados_h.update(hs)
            if unica_mascota and pet:
                usados_p.add(pet)
            buscar(nivel + 1, total + t)
            usados_h.difference_update(hs)
            if unica_mascota and pet:
                usados_p.discard(pet)
            if estado["agotado"]:
                return

    buscar(0, 0.0)
    duracion = time.monotonic() - inicio

    if estado["elegidas"] is None:
        detalle = (tr("Límite de tiempo agotado") if estado["agotado"]
                   else tr("Baneos o conflictos impiden formar seis equipos"))
        return Resultado("Sin solución", detalle, candidatos=candidatos,
                         consideradas=consideradas, duracion=duracion)

    return Resultado(
        N_("Mejor encontrada (no certificada)") if estado["agotado"] else N_("Óptimo global"),
        tr("Tiempo agotado: resultado factible") if estado["agotado"] else tr("Búsqueda completa"),
        total=estado["mejor"],
        elegidas=estado["elegidas"],
        candidatos=candidatos,
        consideradas=consideradas,
        duracion=duracion,
    )
