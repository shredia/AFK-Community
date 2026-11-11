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

VERSION_INDICE = 2          # 2: cada héroe trae "origen" (propio / prestado / prueba / ...)
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


def origen_heroe(h, ids_roster, plantillas_borrow, plantillas_test):
    """Clasifica la copia del héroe usada en una ronda."""
    hid = str(h.get("id") or "")
    if hid in ids_roster:
        return PROPIO
    try:
        temporal = int(hid) >= ID_TEMPORAL_MIN
    except ValueError:
        temporal = False
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
            heroes.append(compacto)
        rondas.append({
            "index": r.get("index", 0),
            "bossId": str(r.get("bossId")),
            "recorded": r.get("recorded") or {},
            "golden": r.get("golden"),
            "pet": r.get("pet") or {},
            "heroes": heroes,
        })
    return {
        "id": str(detalle.get("id") or resumen.get("id")),
        "playedAt": resumen.get("playedAt", ""),
        "result": resumen.get("result") or {},
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
        indice["refs"] = _extraer_referencias(detalle) or indice["refs"]

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

    @property
    def firma(self):
        # Una copia prestada/de prueba se considera distinta de la propia (otra build)
        partes = [i if o == PROPIO else f"{i}*{o}" for i, o in zip(self.hero_ids, self.hero_origenes)]
        return "|".join(sorted(partes)) + "|P:" + self.mascota_id

    @property
    def no_propios(self):
        return [(h, o) for h, o in zip(self.heroes, self.hero_origenes) if o != PROPIO]


def construir_composiciones(runs, heroes_temporales=()):
    """
    Una composición por (run, jefe).
    heroes_temporales: ids que el inventario marca como temporales (colaboraciones de prueba);
    si aparecen como "ya no está en tu roster" se reclasifican como "de prueba".
    """
    temporales = {str(i) for i in heroes_temporales}
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
                if origen == FUERA_ROSTER and str(h.get("id")) in temporales:
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
                golden=r.get("golden"),
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
        if not b.get("activo", True):
            continue
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


def candidatos_por_jefe(comps, rotacion, opciones, baneos):
    """posicion (1..6) -> lista de composiciones únicas, ordenadas por tiempo."""
    activos = _conjunto_baneos(baneos)
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
        return Resultado("Sin solución", "La rotación debe tener 6 jefes.")
    if len(set(rotacion)) != 6:
        return Resultado("Sin solución", "Hay jefes repetidos en la rotación.")

    candidatos, consideradas = candidatos_por_jefe(comps, rotacion, opciones, baneos)
    for pos in range(1, 7):
        if not candidatos[pos]:
            return Resultado(
                "Sin solución",
                f"No hay composiciones elegibles para el jefe {pos} (Boss {rotacion[pos - 1]}).",
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
        detalle = ("Límite de tiempo agotado" if estado["agotado"]
                   else "Baneos o conflictos impiden formar seis equipos")
        return Resultado("Sin solución", detalle, candidatos=candidatos,
                         consideradas=consideradas, duracion=duracion)

    return Resultado(
        "Mejor encontrada (no certificada)" if estado["agotado"] else "Óptimo global",
        "Tiempo agotado: resultado factible" if estado["agotado"] else "Búsqueda completa",
        total=estado["mejor"],
        elegidas=estado["elegidas"],
        candidatos=candidatos,
        consideradas=consideradas,
        duracion=duracion,
    )
