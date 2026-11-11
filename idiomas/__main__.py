"""
Herramientas de idiomas.

  python -m idiomas actualizar          agrega a cada idiomas/*.json las frases nuevas del código
  python -m idiomas nuevo fr Français   crea un idioma nuevo con todas las frases vacías
  python -m idiomas estado              muestra cuánto falta traducir en cada idioma
"""
import ast
import json
import sys
from pathlib import Path

from . import CARPETA, IDIOMA_BASE

RAIZ = CARPETA.parent
CARPETAS_CODIGO = ("aplicacion", "navegador")


def frases_del_codigo():
    """Todas las frases literales usadas en tr("...") dentro del código, con su ubicación."""
    frases = {}
    for carpeta in CARPETAS_CODIGO:
        for archivo in sorted((RAIZ / carpeta).glob("*.py")):
            arbol = ast.parse(archivo.read_text(encoding="utf-8"))
            for nodo in ast.walk(arbol):
                if (isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Name) and nodo.func.id in ("tr", "N_")
                        and nodo.args and isinstance(nodo.args[0], ast.Constant)
                        and isinstance(nodo.args[0].value, str)):
                    frases.setdefault(nodo.args[0].value, f"{carpeta}/{archivo.name}:{nodo.lineno}")
    return frases


def _leer(archivo):
    try:
        return json.loads(archivo.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"_meta": {"codigo": archivo.stem, "nombre": archivo.stem}, "traducciones": {}}


def _escribir(archivo, datos):
    archivo.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def actualizar():
    frases = frases_del_codigo()
    print(f"Frases en el código: {len(frases)}")
    for archivo in sorted(CARPETA.glob("*.json")):
        datos = _leer(archivo)
        trad = datos.setdefault("traducciones", {})
        if archivo.stem == IDIOMA_BASE:
            # El español es la base: las claves ya son el texto; se guarda la lista como referencia
            datos["traducciones"] = {f: "" for f in sorted(frases)}
            _escribir(archivo, datos)
            print(f"  {archivo.name}: base con {len(frases)} frases")
            continue
        nuevas = [f for f in frases if f not in trad]
        for f in nuevas:
            trad[f] = ""
        sin_uso = [f for f in trad if f not in frases]
        datos["traducciones"] = dict(sorted(trad.items()))
        _escribir(archivo, datos)
        hechas = sum(1 for f in frases if trad.get(f))
        print(f"  {archivo.name}: +{len(nuevas)} nuevas · {hechas}/{len(frases)} traducidas"
              + (f" · {len(sin_uso)} ya no se usan (se conservan)" if sin_uso else ""))


def nuevo(codigo, nombre):
    archivo = CARPETA / f"{codigo}.json"
    if archivo.exists():
        print(f"{archivo.name} ya existe.")
        return
    _escribir(archivo, {"_meta": {"codigo": codigo, "nombre": nombre}, "traducciones": {}})
    actualizar()


def estado():
    frases = frases_del_codigo()
    for archivo in sorted(CARPETA.glob("*.json")):
        if archivo.stem == IDIOMA_BASE:
            continue
        trad = _leer(archivo).get("traducciones") or {}
        hechas = sum(1 for f in frases if trad.get(f))
        print(f"{archivo.stem}: {hechas}/{len(frases)} ({hechas * 100 // max(1, len(frases))}%)")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    orden = sys.argv[1] if len(sys.argv) > 1 else "estado"
    if orden == "actualizar":
        actualizar()
    elif orden == "nuevo" and len(sys.argv) >= 4:
        nuevo(sys.argv[2], " ".join(sys.argv[3:]))
    else:
        estado()
