"""
Casos de equivalencia de progreso semanal, Fractura temporal y perfil de roster (lo que calcula la app Python).

Trabaja sobre los casos que ya generó generar_casos.py (casos_prueba/<caso>/entrada/), sin modificarlos:

    ..\\.venv\\Scripts\\python herramientas_migracion\\generar_casos_extra.py [--casos casos_prueba]

Agrega a cada caso, en esperado/:
    progreso.json   semanas_de(runs del índice)
    fractura.json   calcular(base incluida, fractura_temporal.json del caso, bolsa de su cuenta_actual.json)
    roster.json     perfil del caso y evaluar_equipo de los equipos de los OTROS casos (como si fueran de amigos)

Las tablas del sitio son las de recursos/assets (las mismas que trae la app Kotlin).
"""
import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

NC = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(NC))

import idiomas                                       # noqa: E402
from navegador import optimizador as opt             # noqa: E402
from navegador import fractura, roster               # noqa: E402
from navegador.cuenta import cargar_cuenta_actual    # noqa: E402
from navegador.visuales import Visuales              # noqa: E402
from aplicacion.seccion_progreso import semanas_de   # noqa: E402


def _escribir(ruta, datos):
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")


def comps_de(carpeta, vis):
    datos = opt.cargar_indice(carpeta)
    actual = cargar_cuenta_actual(carpeta) or {}
    comps = opt.construir_composiciones(datos["runs"], actual.get("heroes_temporales") or (), opt.arrendados_de(actual))
    opt.aplicar_sp_manual(comps, carpeta)
    for c in comps:   # como VentanaOptimizador._anotar_estrellas
        for h in c.heroes:
            col = h.get("collection")
            if col and "estrellas" not in col:
                col["estrellas"] = vis.estrellas_coleccion(col) or 0
    return datos["runs"], comps


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--casos", default=str(Path(__file__).resolve().parents[1] / "casos_prueba"))
    args = parser.parse_args()
    idiomas.cambiar_idioma(idiomas.IDIOMA_BASE, guardar=False)
    vis = Visuales(NC / "recursos")
    base = json.loads((NC / "recursos" / "fractura_temporal_base.json").read_text(encoding="utf-8"))
    casos = sorted(p for p in Path(args.casos).iterdir() if (p / "entrada").is_dir())

    with tempfile.TemporaryDirectory() as tmp:
        trabajo = {}
        for caso in casos:
            t = Path(tmp) / caso.name
            shutil.copytree(caso / "entrada", t)
            trabajo[caso.name] = (t, *comps_de(t, vis))

        for caso in casos:
            t, runs, comps = trabajo[caso.name]
            semanas = [{"inicio": s["inicio"].isoformat(), "jefes": s["jefes"], "runs": s["runs"],
                        "completas": s["completas"], "mejor": s["mejor"], "teorico": s["teorico"]}
                       for s in semanas_de(runs)]
            _escribir(caso / "esperado" / "progreso.json", semanas)

            cuenta = cargar_cuenta_actual(t)
            estado = fractura.cargar_estado(t)
            bolsa = fractura.inventario(cuenta, base)
            calc = fractura.calcular(base, estado, bolsa)
            _escribir(caso / "esperado" / "fractura.json", {"estado": estado, "bolsa": bolsa, "calculo": calc})

            perfil = roster.cargar_perfil(t, vis)
            evaluaciones = []
            for otro, (_, _, comps_otro) in trabajo.items():
                if otro == caso.name:
                    continue
                for c in comps_otro:
                    nivel, faltas = roster.evaluar_equipo(c, perfil, vis.nombre_calidad)
                    evaluaciones.append({"caso": otro, "run_id": c.run_id, "posicion": c.posicion, "nivel": nivel,
                                         "faltas": [f["texto"] for f in faltas]})
            _escribir(caso / "esperado" / "roster.json", {
                "perfil": {k: perfil[k] for k in ("HEROE", "COLECCION", "MASCOTA", "con_inventario", "manuales")},
                "evaluaciones": evaluaciones})
            print(f"· {caso.name}: {len(semanas)} semanas, {len(calc['recursos'])} recursos de la Fractura, "
                  f"{len(evaluaciones)} equipos evaluados")


if __name__ == "__main__":
    main()
