# navegador/roster.py
"""
Tu perfil de roster: qué héroes, colecciones y mascotas tienes (y hasta dónde los tienes).

Sale de la captura de 'Mi cuenta' / afk-inventory.json (cuenta_actual.json) y se puede corregir a mano
(perfil_roster.json en la carpeta del servidor). Sirve para saber si puedes copiar el equipo de otro jugador
y qué te falta para hacerlo.
"""
import json
from pathlib import Path

from idiomas import tr, N_
from .cuenta import cargar_cuenta_actual, es_arrendado_cuenta

ARCHIVO_PERFIL = "perfil_roster.json"
TEMPORALES = ("prestado", "prueba", "temporal")

# Lo que se compara de cada cosa (clave -> nombre visible)
CAMPOS_PERFIL = {
    "HEROE": {"quality": N_("Ascensión"), "sig": N_("SI"), "engraving": N_("Grabado"), "muebles": N_("Muebles")},
    "COLECCION": {"estrellas": N_("★ de habilidad"), "mythic": N_("Míticos"), "level": N_("Nivel")},
    "MASCOTA": {},
}

# Niveles de "¿puedo armar este equipo?"
PUEDO = "ok"       # lo tienes todo, igual o mejor
CASI = "casi"      # tienes los héroes, pero alguna build / colección / mascota es peor
NO_PUEDO = "no"    # te falta algún héroe
ICONO_NIVEL = {PUEDO: "✅", CASI: "🟡", NO_PUEDO: "❌"}
TEXTO_NIVEL = {PUEDO: N_("Puedes armarlo"), CASI: N_("Te falta mejorar algo"), NO_PUEDO: N_("Te falta algún héroe")}


def _entero(v, defecto=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return defecto


def _leer(ruta):
    try:
        return json.loads(Path(ruta).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def cargar_correcciones(carpeta):
    datos = _leer(Path(carpeta) / ARCHIVO_PERFIL)
    return datos if isinstance(datos, dict) else {}


def guardar_correcciones(carpeta, correcciones):
    (Path(carpeta) / ARCHIVO_PERFIL).write_text(json.dumps(correcciones, ensure_ascii=False, indent=2),
                                                encoding="utf-8")


def valor_heroe(h, campo):
    if campo == "muebles":
        return _entero((h.get("furniture") or {}).get("pieces"))
    return _entero(h.get(campo))


def cargar_perfil(carpeta, vis=None, correcciones=None):
    """
    correcciones: las de perfil_roster.json si es None (o las que estás editando).

    {"HEROE": {tid: {...}}, "COLECCION": {tid: {...}}, "MASCOTA": {tid: {...}},
     "con_inventario": bool, "captura": iso, "manuales": n}
    Cada entrada: {"nombre", "tengo", campos..., "manual": bool}.
    """
    carpeta = Path(carpeta)
    estado = cargar_cuenta_actual(carpeta) or {}
    heroes, colecciones, mascotas = {}, {}, {}

    for h in estado.get("roster") or []:
        if h.get("temporal") and not es_arrendado_cuenta(h, estado):
            continue   # de prueba: no es tuyo (los dimensionales arrendados sí cuentan)
        tid = str(h.get("tid"))
        nuevo = {"nombre": h.get("name") or tid, "tengo": True,
                 **{c: valor_heroe(h, c) for c in CAMPOS_PERFIL["HEROE"]}}
        previo = heroes.get(tid)
        if previo is None or nuevo["quality"] > previo["quality"]:
            heroes[tid] = nuevo
    # héroes que solo tienes como copia base (sin desarrollar)
    for c in estado.get("copias_base") or []:
        tid = str(c.get("tid"))
        if tid not in heroes and c.get("nombre"):
            heroes[tid] = {"nombre": c["nombre"], "tengo": True, "quality": _entero(c.get("calidad")),
                           "sig": 0, "engraving": 0, "muebles": 0}

    for col in estado.get("colecciones") or []:
        tid = str(col.get("tid"))
        estrellas = vis.estrellas_coleccion(col) if vis is not None and getattr(vis, "disponible", False) else None
        nuevo = {"nombre": col.get("name") or tid, "tengo": True, "estrellas": estrellas,
                 "mythic": _entero(col.get("mythic")), "level": _entero(col.get("level"))}
        previo = colecciones.get(tid)
        clave = lambda d: (d.get("estrellas") or 0, d.get("mythic") or 0, d.get("level") or 0)
        if previo is None or clave(nuevo) > clave(previo):
            colecciones[tid] = nuevo

    for p in estado.get("mascotas_roster") or []:
        mascotas[str(p.get("tid"))] = {"nombre": p.get("name") or str(p.get("tid")), "tengo": True}

    perfil = {"HEROE": heroes, "COLECCION": colecciones, "MASCOTA": mascotas,
              "con_inventario": bool(estado.get("roster")), "captura": estado.get("capturedAt"), "manuales": 0}
    aplicar_correcciones(perfil, cargar_correcciones(carpeta) if correcciones is None else correcciones)
    return perfil


def aplicar_correcciones(perfil, correcciones):
    n = 0
    for tipo in ("HEROE", "COLECCION", "MASCOTA"):
        for clave, datos in (correcciones.get(tipo) or {}).items():
            if not isinstance(datos, dict):
                continue
            entrada = perfil[tipo].setdefault(str(clave), {"nombre": datos.get("nombre") or str(clave)})
            entrada.update(datos)
            entrada["manual"] = True
            n += 1
    perfil["manuales"] = n
    return perfil


def hay_datos(perfil):
    return bool(perfil) and (perfil.get("con_inventario") or perfil.get("manuales"))


def _corto(nombre):
    return str(nombre or "?").split(" - ")[0]


def evaluar_equipo(comp, perfil, nombre_calidad=None):
    """
    ¿Puedes armar este equipo con tu roster?
    Devuelve (nivel, faltas) con nivel PUEDO / CASI / NO_PUEDO (o None si no hay perfil) y
    faltas = [{"clave", "texto", "grave"}] (grave = te falta el héroe).
    Sin inventario solo cuentan las correcciones manuales (lo no marcado se supone que lo tienes).
    """
    if not hay_datos(perfil):
        return None, []
    completo = perfil.get("con_inventario")
    faltas = []
    origenes = getattr(comp, "hero_origenes", None) or ("propio",) * len(comp.heroes)
    for h, origen in zip(comp.heroes, origenes):
        if origen in TEMPORALES:
            continue   # lo usó prestado / de prueba: tú también puedes pedirlo
        tid, nombre = str(h.get("tid")), _corto(h.get("name"))
        mio = perfil["HEROE"].get(tid)
        if (mio is None and completo) or (mio is not None and not mio.get("tengo", True)):
            faltas.append({"clave": f"HEROE|{tid}", "texto": tr("{0}: no lo tienes", nombre), "grave": True})
            continue
        if mio is not None:
            for campo, etiqueta in CAMPOS_PERFIL["HEROE"].items():
                necesita, tengo = valor_heroe(h, campo), mio.get(campo)
                if tengo is not None and necesita > _entero(tengo):
                    if campo == "quality" and nombre_calidad:
                        texto = tr("{0}: {1} (tienes {2})", nombre, nombre_calidad(necesita), nombre_calidad(tengo))
                    else:
                        texto = tr("{0}: {1} {2} (tienes {3})", nombre, tr(etiqueta), necesita, tengo)
                    faltas.append({"clave": f"HEROE|{tid}|{campo}|{necesita}", "texto": texto, "grave": False})
        col = h.get("collection") or {}
        if col:
            ctid, cnombre = str(col.get("tid")), col.get("name") or "?"
            mia = perfil["COLECCION"].get(ctid)
            if (mia is None and completo) or (mia is not None and not mia.get("tengo", True)):
                faltas.append({"clave": f"COLECCION|{ctid}", "texto": tr("Colección {0}: no la tienes", cnombre),
                               "grave": False})
            elif mia is not None:
                for campo, etiqueta in CAMPOS_PERFIL["COLECCION"].items():
                    necesita, tengo = col.get(campo), mia.get(campo)
                    if necesita is None or tengo is None:
                        continue
                    if _entero(necesita) > _entero(tengo):
                        faltas.append({"clave": f"COLECCION|{ctid}|{campo}|{necesita}", "grave": False,
                                       "texto": tr("Colección {0}: {1} {2} (tienes {3})", cnombre, tr(etiqueta),
                                                   necesita, tengo)})
    mascota = getattr(comp, "mascota", None) or {}
    if mascota.get("tid") is not None:
        mtid = str(mascota.get("tid"))
        mia = perfil["MASCOTA"].get(mtid)
        if (mia is None and completo and perfil["MASCOTA"]) or (mia is not None and not mia.get("tengo", True)):
            faltas.append({"clave": f"MASCOTA|{mtid}", "grave": False,
                           "texto": tr("Mascota {0}: no la tienes", mascota.get("name", "?"))})
    faltas = _sin_repetir(faltas)
    if any(f["grave"] for f in faltas):
        return NO_PUEDO, faltas
    return (CASI if faltas else PUEDO), faltas


def _sin_repetir(faltas):
    """Si dos héroes llevan la misma colección, se queda la exigencia mayor (y sin duplicar 'no la tienes')."""
    salida, indice = [], {}
    for f in faltas:
        partes = f["clave"].split("|")
        grupo = "|".join(partes[:3]) if len(partes) >= 4 else f["clave"]
        if grupo in indice:
            previa = salida[indice[grupo]]
            if len(partes) >= 4 and int(partes[3]) > int(previa["clave"].split("|")[3]):
                salida[indice[grupo]] = f
            continue
        indice[grupo] = len(salida)
        salida.append(f)
    return salida


def filtrar_por_roster(comps, perfil, modo):
    """modo: 'todos' | 'casi' (puedes o casi) | 'ok' (solo lo que puedes armar tal cual)."""
    if modo not in ("casi", "ok") or not hay_datos(perfil):
        return list(comps)
    permitidos = {PUEDO} if modo == "ok" else {PUEDO, CASI}
    return [c for c in comps if evaluar_equipo(c, perfil)[0] in permitidos]
