"""Ubicación de los archivos descargados dentro de cuentas/<cuenta>/<servidor>/."""
import json
from pathlib import Path

CARPETA_SIN_ASIGNAR = "_sin_asignar"

# Assets comunes a todas las cuentas y servidores
CARPETA_ASSETS = "assets"
CARPETA_CAPTURAS = "capturas"   # íconos recortados de capturas del juego (lo que no se puede descargar)


def carpeta_assets(base_dir):
    return Path(base_dir) / CARPETA_ASSETS


_CAPTURAS_LISTAS = set()


def carpeta_capturas(base_dir):
    """assets/capturas/ (mueve la carpeta antigua datos/fractura_iconos la primera vez)."""
    nueva = carpeta_assets(base_dir) / CARPETA_CAPTURAS
    vieja = Path(base_dir) / "datos" / "fractura_iconos"
    if vieja.is_dir() and not nueva.exists():
        nueva.parent.mkdir(parents=True, exist_ok=True)
        vieja.rename(nueva)
    # los recortes vienen con la aplicación en recursos/capturas: se copian los que falten
    incluidos = Path(base_dir) / "recursos" / "capturas"
    if str(nueva) not in _CAPTURAS_LISTAS and incluidos.is_dir():
        _CAPTURAS_LISTAS.add(str(nueva))
        nueva.mkdir(parents=True, exist_ok=True)
        for archivo in incluidos.iterdir():
            if archivo.is_file() and not (nueva / archivo.name).exists():
                (nueva / archivo.name).write_bytes(archivo.read_bytes())
    return nueva


def cargar_mapa_personajes(base_dir):
    """
    Devuelve {uid_personaje: carpeta_del_servidor} leyendo cuentas/<cuenta>/<servidor>/<servidor>.json.

    Si el mismo personaje aparece en varias cuentas, gana la cuenta con 'fetchedAt' más reciente.
    """
    directorio_cuentas = Path(base_dir) / "cuentas"
    mapa = {}  # uid -> (fetchedAt, carpeta)

    if not directorio_cuentas.exists():
        return {}

    for carpeta_cuenta in directorio_cuentas.iterdir():
        archivo_cuenta = carpeta_cuenta / "account.json"
        if not archivo_cuenta.is_file():
            continue
        try:
            cuenta = json.loads(archivo_cuenta.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        fetched = str(cuenta.get("fetchedAt") or "")

        for carpeta_servidor in carpeta_cuenta.iterdir():
            archivo_personaje = carpeta_servidor / f"{carpeta_servidor.name}.json"
            if not archivo_personaje.is_file():
                continue
            try:
                personaje = json.loads(archivo_personaje.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            uid = str(personaje.get("uid") or "")
            if uid and (uid not in mapa or fetched > mapa[uid][0]):
                mapa[uid] = (fetched, carpeta_servidor)

    return {uid: carpeta for uid, (_, carpeta) in mapa.items()}


def carpeta_personaje(base_dir, mapa, character):
    """Carpeta del servidor del personaje; si no se conoce, cuentas/_sin_asignar/<character>."""
    character = str(character or "desconocido")
    if character in mapa:
        return mapa[character]
    return Path(base_dir) / "cuentas" / CARPETA_SIN_ASIGNAR / character


def ruta_detalle(base_dir, mapa, run):
    """cuentas/<cuenta>/<servidor>/detalles/<id>.json"""
    return carpeta_personaje(base_dir, mapa, run.get("character")) / "detalles" / f"{run['id']}.json"


def todos_los_detalles(base_dir):
    """Todos los archivos de detalle descargados, de todas las cuentas/servidores."""
    directorio_cuentas = Path(base_dir) / "cuentas"
    if not directorio_cuentas.exists():
        return []
    return sorted(directorio_cuentas.glob("*/*/detalles/*.json"))
