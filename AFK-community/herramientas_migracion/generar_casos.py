"""
Casos de prueba de equivalencia: lo que calcula la app Python, para comparar con la versión Kotlin.

Usa los módulos de la app Python (NC/navegador, NC/idiomas) SIN modificarlos, sobre una COPIA de los datos:
la carpeta original no se toca (cargar_indice reescribe optimizador_indice.json, por eso se trabaja en una copia).

    ..\\.venv\\Scripts\\python herramientas_migracion\\generar_casos.py <carpeta> [--salida casos_prueba]

<carpeta> puede ser una carpeta de servidor (cuentas/<cuenta>/<servidor>/) o cualquier carpeta que las contenga
(p. ej. NC_pruebas/datos_usuario/cuentas): se genera un caso por cada servidor con detalles.

Por cada caso, en <salida>/<cuenta>_<servidor>/:
    manifiesto.json     de dónde salió, cuándo y con qué versión de la app Python
    entrada/            la carpeta del servidor tal como estaba (las pruebas Kotlin trabajan sobre una copia)
    esperado/
      indice.json           cargar_indice: runs (en el mismo orden) y referencias
      composiciones.json    construir_composiciones + aplicar_sp_manual (lo que usa la lógica, sin las fichas)
      optimizacion.json     optimizar con varias opciones: estado, total, equipos elegidos y candidatos

Los casos tienen datos de cuentas reales: <salida> está en .gitignore y no se sube.
Al migrar cada etapa se agregan aquí sus casos (importar, roster, progreso, fractura...).
"""
import argparse
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

NC = Path(__file__).resolve().parents[2]          # la app Python
sys.path.insert(0, str(NC))

import idiomas                                     # noqa: E402  (al importarse, igual que al abrir la app)
from navegador import optimizador as opt           # noqa: E402
from navegador import bloqueos                     # noqa: E402
from navegador.cuenta import cargar_cuenta_actual  # noqa: E402

VERSION_CASOS = 1
TIEMPO_MAXIMO = 600.0   # amplio: se busca "Óptimo global", que no depende de la velocidad de la máquina


def _escribir(ruta, datos):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")


def composicion(c):
    """Lo que usa la lógica de una Composicion (las fichas de héroes ya están en indice.json)."""
    return {
        "run_id": c.run_id, "fecha": c.fecha, "rotacion": c.rotacion, "posicion": c.posicion,
        "boss_id": c.boss_id, "tiempo": c.tiempo, "derrotado": c.derrotado, "run_completa": c.run_completa,
        "golden": c.golden, "hero_ids": list(c.hero_ids), "hero_nombres": list(c.hero_nombres),
        "mascota_id": c.mascota_id, "mascota_nombre": c.mascota_nombre, "hero_origenes": list(c.hero_origenes),
        "veces": c.veces, "sp_manual": c.sp_manual, "firma": c.firma,
    }


def _ref(c):
    return {"run_id": c.run_id, "posicion": c.posicion, "tiempo": c.tiempo, "firma": c.firma, "veces": c.veces}


def resultado(res):
    return {
        "estado": res.estado, "detalle": res.detalle, "total": res.total,
        "elegidas": [_ref(c) for c in res.elegidas or []],
        "candidatos": {str(p): [_ref(c) for c in lista] for p, lista in sorted((res.candidatos or {}).items())},
        "consideradas": res.consideradas,
    }


# Variantes de opciones: las de la ventana por defecto y las que cambian el recorrido de la búsqueda
VARIANTES = {
    "por_defecto": {},
    "con_incompletas": {"solo_completas": False},
    "mascotas_repetidas": {"prohibir_repetir_mascota": False},
    "limite_5_por_jefe": {"limite_por_jefe": 5},
    "sin_temporales_ni_fuera_roster": {"excluir_temporales": True, "excluir_fuera_roster": True},
}


def generar(carpeta, salida):
    carpeta = Path(carpeta)
    nombre = f"{carpeta.parent.name}_{carpeta.name}"
    destino = salida / nombre
    if destino.exists():
        shutil.rmtree(destino)
    print(f"· {nombre}")

    # entrada: la carpeta tal como está ahora
    shutil.copytree(carpeta, destino / "entrada")

    with tempfile.TemporaryDirectory() as tmp:
        trabajo = Path(tmp) / carpeta.name
        shutil.copytree(destino / "entrada", trabajo)

        inicio = time.monotonic()
        datos = opt.cargar_indice(trabajo)
        _escribir(destino / "esperado" / "indice.json", datos)

        # igual que VentanaOptimizador al cargar un servidor
        actual = cargar_cuenta_actual(trabajo) or {}
        comps = opt.construir_composiciones(datos["runs"], actual.get("heroes_temporales") or (),
                                            opt.arrendados_de(actual))
        opt.aplicar_sp_manual(comps, trabajo)
        _escribir(destino / "esperado" / "composiciones.json", [composicion(c) for c in comps])

        rotacion = opt.rotacion_mas_reciente(datos["runs"])
        # (la carpeta de baneos de amigos solo se usa para migrar archivos de versiones viejas)
        reglas = bloqueos.para(bloqueos.cargar_bloqueos(trabajo, Path(tmp) / "_sin_amigos"), "yo")
        casos = {}
        for nombre_variante, cambios in VARIANTES.items():
            for con_bloqueos in (False, True):
                if con_bloqueos and not reglas:
                    continue
                opciones = opt.Opciones(tiempo_maximo=TIEMPO_MAXIMO, **cambios)
                # optimizar marca 'veces' en las composiciones: cada variante parte de las mismas
                res = opt.optimizar(comps, rotacion, opciones, reglas if con_bloqueos else [])
                clave = nombre_variante + ("+bloqueos" if con_bloqueos else "")
                casos[clave] = {"opciones": vars(opciones), "con_bloqueos": con_bloqueos, "resultado": resultado(res)}
                print(f"    {clave}: {res.estado} · {res.total:.3f} s · {res.consideradas} consideradas")
        _escribir(destino / "esperado" / "optimizacion.json",
                  {"rotacion": rotacion, "bloqueos": reglas, "casos": casos})

    _escribir(destino / "manifiesto.json", {
        "version_casos": VERSION_CASOS,
        "origen": str(carpeta),
        "generado": time.strftime("%Y-%m-%d %H:%M:%S"),
        "version_app_python": (NC / "version.py").read_text(encoding="utf-8").split('"')[1],
        "runs": len(datos["runs"]),
        "composiciones": len(comps),
        "segundos": round(time.monotonic() - inicio, 1),
    })


def carpetas_servidor(raiz):
    raiz = Path(raiz)
    if (raiz / "detalles").is_dir():
        return [raiz]
    return sorted(p.parent for p in raiz.rglob("detalles") if p.is_dir() and any(p.glob("*.json")))


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[1])
    parser.add_argument("carpeta", help="carpeta de servidor, o una que las contenga")
    parser.add_argument("--salida", default=str(Path(__file__).resolve().parents[1] / "casos_prueba"))
    args = parser.parse_args()

    idiomas.cambiar_idioma(idiomas.IDIOMA_BASE, guardar=False)   # los textos esperados, en español
    salida = Path(args.salida)
    servidores = carpetas_servidor(args.carpeta)
    if not servidores:
        sys.exit(f"No hay carpetas de servidor con detalles en {args.carpeta}")
    for carpeta in servidores:
        generar(carpeta, salida)
    print(f"✓ {len(servidores)} casos en {salida}")


if __name__ == "__main__":
    main()
