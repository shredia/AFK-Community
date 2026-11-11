"""
Íconos del CDN comunitario de AFK Arena (github.com/floofpire/cdn).

Solo se descarga lo que falta, una vez, y queda guardado en assets/cdn/ (el repositorio pesa ~13 GB:
nunca se clona). Las peticiones solo llevan el nombre del archivo (id del héroe), ningún dato tuyo.

  unidades(base_dir)              -> {id: info} de unit.min.json (se refresca cada 7 días)
  buscar(base_dir, nombre, despertado=None) -> info del héroe por su nombre en inglés
  icono_unidad(base_dir, uid)     -> Path local del ícono del juego (unit_icon_by_id/<id>.webp)
  icono_enmarcado(base_dir, nombre_archivo) -> Path de framed_unit_icon/<...>.webp (retrato con marco del juego)
"""
import json
import time
import unicodedata
import urllib.request
from pathlib import Path

URL_BASE = "https://raw.githubusercontent.com/floofpire/cdn/main"
CARPETA = Path("assets") / "cdn"
AGENTE = "afk-tools/1.0"
DIAS_INDICE = 7


def _carpeta(base_dir):
    return Path(base_dir) / CARPETA


def _descargar(url, destino, timeout=10):
    destino.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": AGENTE})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        datos = r.read()
    tmp = destino.with_suffix(destino.suffix + ".tmp")
    tmp.write_bytes(datos)
    tmp.replace(destino)
    return destino


def _normalizar(t):
    return "".join(c for c in unicodedata.normalize("NFD", str(t or "").lower()) if unicodedata.category(c) != "Mn").strip()


_CACHE_UNIDADES = {}


def unidades(base_dir):
    """{id: info} de todos los personajes del juego (unit.min.json del CDN)."""
    archivo = _carpeta(base_dir) / "unit.min.json"
    viejo = not archivo.exists() or (time.time() - archivo.stat().st_mtime) > DIAS_INDICE * 86400
    if viejo:
        try:
            _descargar(f"{URL_BASE}/unit.min.json", archivo)
        except OSError:
            pass  # sin conexión: se usa la copia que haya
    clave = (str(archivo), archivo.stat().st_mtime if archivo.exists() else 0)
    if clave not in _CACHE_UNIDADES:
        try:
            _CACHE_UNIDADES[clave] = json.loads(archivo.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            _CACHE_UNIDADES[clave] = {}
    return _CACHE_UNIDADES[clave]


def buscar(base_dir, nombre, despertado=None):
    """Héroe por nombre en inglés ("Ezizh", "Brutus - Lion's Pride"). despertado=True prefiere la forma despertada."""
    base = _normalizar(str(nombre).split(" - ")[0])
    if " - " in str(nombre) and despertado is None:
        despertado = True
    candidatos = [u for u in unidades(base_dir).values()
                  if _normalizar((u.get("names") or {}).get("en")) == base and u.get("rarity")]
    if not candidatos:
        return None
    if despertado is not None:
        preferidos = [u for u in candidatos if bool(u.get("isAwakened")) == despertado]
        candidatos = preferidos or candidatos
    return candidatos[0]


def icono_unidad(base_dir, uid, sufijo=""):
    """Ícono del juego de un personaje (sufijo "" | "_2x" | "_4x"). None si no se pudo obtener."""
    destino = _carpeta(base_dir) / "unit_icon_by_id" / f"{uid}{sufijo}.webp"
    if destino.exists():
        return destino
    try:
        return _descargar(f"{URL_BASE}/unit_icon_by_id/{uid}{sufijo}.webp", destino)
    except OSError:
        return None


def icono_enmarcado(base_dir, nombre_archivo):
    """Retrato con marco del juego, p. ej. "178_a5_si30_f9_e80.webp" (ver README del CDN)."""
    destino = _carpeta(base_dir) / "framed_unit_icon" / nombre_archivo
    if destino.exists():
        return destino
    try:
        return _descargar(f"{URL_BASE}/framed_unit_icon/{nombre_archivo}", destino)
    except OSError:
        return None
