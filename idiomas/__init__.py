"""
Idiomas de la app.

- El texto en español es la clave: en el código se escribe  tr("Acceso al sitio")  o, con datos,
  tr("Descargados: {0} de {1}", ya, total).
- Cada idioma es un archivo  idiomas/<código>.json :
      {"_meta": {"codigo": "en", "nombre": "English"},
       "traducciones": {"Acceso al sitio": "Site access", "Descargados: {0} de {1}": "Downloaded: {0} of {1}"}}
- Si una frase no está traducida (o está vacía) se muestra en español.
- Para agregar a todos los archivos las frases nuevas del código:
      .venv/Scripts/python -m idiomas actualizar
- Para crear un idioma nuevo:
      .venv/Scripts/python -m idiomas nuevo fr "Français"
"""
import json
from pathlib import Path

CARPETA = Path(__file__).resolve().parent
IDIOMA_BASE = "es"
from navegador.rutas import DATOS   # noqa: E402  (además mueve los datos de la ubicación antigua)

_ARCHIVO_PREFERENCIAS = DATOS / "preferencias.json"

_actual = IDIOMA_BASE
_traducciones = {}


def idiomas_disponibles():
    """[(código, nombre)] de los archivos idiomas/*.json."""
    salida = []
    for archivo in sorted(CARPETA.glob("*.json")):
        try:
            meta = json.loads(archivo.read_text(encoding="utf-8")).get("_meta") or {}
        except (OSError, json.JSONDecodeError):
            meta = {}
        salida.append((archivo.stem, meta.get("nombre") or archivo.stem))
    salida.sort(key=lambda x: (x[0] != IDIOMA_BASE, x[1].lower()))
    return salida


def idioma_actual():
    return _actual


def cambiar_idioma(codigo, guardar=True):
    """Carga el idioma indicado (si no existe, queda el español)."""
    global _actual, _traducciones
    _traducciones = {}
    _actual = IDIOMA_BASE
    if codigo and codigo != IDIOMA_BASE:
        try:
            datos = json.loads((CARPETA / f"{codigo}.json").read_text(encoding="utf-8"))
            _traducciones = {k: v for k, v in (datos.get("traducciones") or {}).items() if v}
            _actual = codigo
        except (OSError, json.JSONDecodeError):
            pass
    if guardar:
        _guardar_preferencia(_actual)
    return _actual


def tr(texto, *args, **kwargs):
    """Traduce `texto` al idioma actual (o lo deja en español) y le inserta los datos."""
    if not isinstance(texto, str):
        return texto
    plantilla = _traducciones.get(texto, texto)
    if args or kwargs:
        try:
            return plantilla.format(*args, **kwargs)
        except (IndexError, KeyError, ValueError):
            # Traducción mal escrita: usar el texto original
            return texto.format(*args, **kwargs)
    return plantilla


def N_(texto):
    """
    Marca un texto para traducirlo más tarde (no lo traduce ahora). Se usa en listas y constantes
    que se muestran después con tr(variable), p. ej. títulos de columnas o nombres de tarjetas.
    """
    return texto


def _guardar_preferencia(codigo):
    try:
        datos = json.loads(_ARCHIVO_PREFERENCIAS.read_text(encoding="utf-8")) if _ARCHIVO_PREFERENCIAS.exists() else {}
    except (OSError, json.JSONDecodeError):
        datos = {}
    datos["idioma"] = codigo
    try:
        _ARCHIVO_PREFERENCIAS.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def _cargar_preferencia():
    try:
        return json.loads(_ARCHIVO_PREFERENCIAS.read_text(encoding="utf-8")).get("idioma") or IDIOMA_BASE
    except (OSError, json.JSONDecodeError, AttributeError):
        return IDIOMA_BASE


# Al importar, usar el idioma guardado en preferencias.json
cambiar_idioma(_cargar_preferencia(), guardar=False)
