"""
Copia tus imágenes y tablas del juego (datos_usuario/assets/) a recursos/assets/, para que vayan con la app.

    .venv\\Scripts\\python herramientas\\empaquetar_assets.py

Así una instalación nueva ve héroes, jefes, equipo y objetos sin tener que descargarlos del sitio.
Al abrirse, la app copia a su datos_usuario/assets/ lo que le falte (navegador/rutas.py: sembrar_assets).

Se omite lo que tiene datos tuyos o no hace falta:
  urls_por_detalle.json   caché con las rutas de tus runs (ids de tus cuentas); la app la regenera sola
  capturas/               ya va en recursos/capturas/
"""
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ORIGEN = RAIZ / "datos_usuario" / "assets"
DESTINO = RAIZ / "recursos" / "assets"
OMITIR_ARCHIVOS = {"urls_por_detalle.json"}
OMITIR_CARPETAS = {"capturas"}


def archivos():
    for ruta in sorted(ORIGEN.rglob("*")):
        rel = ruta.relative_to(ORIGEN)
        if ruta.is_file() and rel.parts[0] not in OMITIR_CARPETAS and ruta.name not in OMITIR_ARCHIVOS:
            yield ruta, rel


if __name__ == "__main__":
    if not ORIGEN.is_dir():
        sys.exit(f"No hay imágenes en {ORIGEN}.")
    nuevos = actualizados = 0
    for ruta, rel in archivos():
        destino = DESTINO / rel
        if destino.exists() and destino.read_bytes() == ruta.read_bytes():
            continue
        nuevos += not destino.exists()
        actualizados += destino.exists()
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ruta, destino)
    total = sum(1 for p in DESTINO.rglob("*") if p.is_file())
    peso = sum(p.stat().st_size for p in DESTINO.rglob("*") if p.is_file()) / 1e6
    print(f"✓ recursos/assets: {total} archivos ({peso:.1f} MB) · {nuevos} nuevos · {actualizados} actualizados")
