# navegador/bloqueos.py
"""
Bloqueos unificados del optimizador: baneos de héroes / mascotas y límites de build en una sola lista.

Cada regla lleva "aplica": "todo" (cualquier equipo), "yo" (solo tus equipos) o "amigos" (solo equipos de
amigos y de tus otros servidores). Se guardan en bloqueos.json de la carpeta del servidor.
La primera vez se migran baneos.json, cuentas/_amigos/baneos.json y limites.json (no se borran).
"""
import json
from pathlib import Path

from idiomas import tr, N_
from .optimizador import cargar_baneos, describir_limite, NOMBRES_COPIA, COPIA_TODAS, COPIA_NO_PROPIA

ARCHIVO_BLOQUEOS = "bloqueos.json"
APLICA_TODO, APLICA_YO, APLICA_AMIGOS = "todo", "yo", "amigos"
NOMBRES_APLICA = {APLICA_TODO: N_("Todos los equipos"), APLICA_YO: N_("Solo tus equipos"),
                  APLICA_AMIGOS: N_("Solo equipos de amigos")}


def _leer(ruta):
    try:
        return json.loads(Path(ruta).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _clave(b):
    if b.get("limite"):
        return ("L", str(b.get("objeto")), str(b.get("nombre")), str(b.get("campo")), str(b.get("jefe")),
                b.get("aplica", APLICA_TODO))
    return ("B", str(b.get("tipo")), str(b.get("nombre")), str(b.get("jefe")), str(b.get("copia") or COPIA_TODAS),
            b.get("aplica", APLICA_TODO))


def sin_duplicados(reglas):
    vistas, salida = set(), []
    for b in reglas:
        k = _clave(b)
        if k not in vistas:
            vistas.add(k)
            salida.append(b)
    return salida


def cargar_bloqueos(carpeta_servidor, carpeta_amigos):
    """Lista de reglas del servidor (migra los archivos viejos la primera vez)."""
    archivo = Path(carpeta_servidor) / ARCHIVO_BLOQUEOS
    datos = _leer(archivo)
    if isinstance(datos, list):
        return [b for b in datos if isinstance(b, dict)]
    reglas = []
    for b in cargar_baneos(carpeta_servidor):
        # antes tus baneos valían también para los equipos de amigos al mezclar: 'todos los equipos'
        reglas.append({**b, "aplica": APLICA_TODO})
    for b in cargar_baneos(carpeta_amigos):
        reglas.append({**b, "aplica": APLICA_AMIGOS})
    limites = _leer(Path(carpeta_servidor) / "limites.json")
    for b in limites if isinstance(limites, list) else []:
        if isinstance(b, dict) and b.get("limite"):
            reglas.append({**b, "aplica": b.get("aplica") or APLICA_TODO})
    reglas = sin_duplicados(reglas)
    if reglas:
        try:
            guardar_bloqueos(carpeta_servidor, reglas)
        except OSError:
            pass
    return reglas


def guardar_bloqueos(carpeta_servidor, reglas):
    (Path(carpeta_servidor) / ARCHIVO_BLOQUEOS).write_text(
        json.dumps(sin_duplicados(reglas), ensure_ascii=False, indent=2), encoding="utf-8")


def para(reglas, lado):
    """Reglas que valen para 'yo' (tus equipos) o 'amigos' (los de otros)."""
    return [b for b in reglas if b.get("aplica", APLICA_TODO) in (APLICA_TODO, lado)]


def describir(b, con_jefe=True, etiqueta_jefe=None):
    """Texto corto de una regla: 'Saitama: no usar' · 'Dracula: SI máximo 20' · 'Colección X: no la tengo'."""
    nombre = str(b.get("nombre") or "?").split(" - ")[0]
    if b.get("limite"):
        texto = describir_limite(b)
    elif str(b.get("tipo")).upper() == "MASCOTA":
        texto = tr("Mascota {0}: no usar", nombre)
    elif (b.get("copia") or COPIA_TODAS) == COPIA_NO_PROPIA:
        texto = tr("{0}: no usar la copia prestada/prueba", nombre)
    else:
        texto = tr("{0}: no usar", nombre)
    jefe = str(b.get("jefe") or "TODOS")
    if con_jefe and jefe != "TODOS":
        texto += " · " + (etiqueta_jefe(jefe) if etiqueta_jefe else tr("jefe {0}", jefe))
    return texto


def nueva_regla_baneo(tipo, nombre, ident="", jefe="TODOS", solo_copia=False, aplica=APLICA_TODO):
    return {"tipo": tipo, "nombre": nombre, "id": str(ident or ""), "jefe": jefe or "TODOS",
            "copia": COPIA_NO_PROPIA if solo_copia else COPIA_TODAS, "activo": True, "aplica": aplica}


def nueva_regla_limite(objeto, nombre, campo, maximo, jefe="TODOS", aplica=APLICA_TODO):
    return {"limite": True, "objeto": objeto, "nombre": nombre or "*", "campo": campo, "max": int(maximo),
            "jefe": jefe or "TODOS", "activo": True, "aplica": aplica}


__all__ = ["cargar_bloqueos", "guardar_bloqueos", "para", "describir", "nueva_regla_baneo", "nueva_regla_limite",
           "NOMBRES_APLICA", "NOMBRES_COPIA", "APLICA_TODO", "APLICA_YO", "APLICA_AMIGOS", "sin_duplicados"]
