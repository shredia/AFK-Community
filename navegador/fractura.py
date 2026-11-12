"""
Fractura temporal: planificador de recursos.

Datos base (iguales para todos):  datos/fractura_temporal.json
  - pisos:   [{"piso": 5, "recompensas": {"Oro (M)": 10, ...}}]   (incluye Medallas y Cofre 1/2/3)
  - cofres:  {"Cofre 1": {"Grabados verdes": 150, ...}}             (cada cofre = elegir UNA opción)
  - tiendas: [{"nombre": "Tienda 100", "piso": 100, "objetos": [{"objeto", "maximo", "precio", "unidades"}]}]
Tu avance (por cuenta/servidor):  cuentas/<acc>/<srv>/fractura_temporal.json
  - piso, elecciones de cofres (ahora / planeadas) y compras (hechas / planeadas)

Ambos se pueden importar desde la planilla fractura_temporal_*.xlsx.
"""
import json
import re
import unicodedata
from pathlib import Path

from navegador.rutas import RAIZ

ARCHIVO_BASE = Path("datos") / "fractura_temporal.json"
ARCHIVO_ESTADO = "fractura_temporal.json"
COLUMNAS_ESPECIALES = ("Medallas", "Cofre 1", "Cofre 2", "Cofre 3")

# Nombres que la planilla escribe de varias formas -> un solo nombre
ALIAS = {
    "esencia retorcida": "Esencia retorcida",
    "cofres rojos": "Cofres rojos",
    "grabajos rojos": "Grabados rojos",
    "grabados rojos": "Grabados rojos",
    "grabados verdes": "Grabados verdes",
    "grabadsos verdes": "Grabados verdes",
    "celepogeos": "Tiradas celepogeas",
    "tiradas celepogeos": "Tiradas celepogeas",
    "tiradas celepogeas": "Tiradas celepogeas",
    "sp": "Tiradas SP",
    "tiradas sp": "Tiradas SP",
    "emblema primordial": "Emblema primordial",
    "emblema amplificador": "Emblema amplificador",
    "emblema amarillo": "Emblema amplificador",
    "emblemas morados": "Emblema primordial",
    "emblema morado": "Emblema primordial",
    "monedas poe": "Monedas Poe",
    "cebos": "Cebos",
    "ezish": "Ezizh",
    "oro(m)": "Oro (M)",
    "polvo azul(m)": "Polvo azul (M)",
}
# Recursos que también aparecen en el inventario sincronizado (id de objeto del sitio)
EN_INVENTARIO = {"Emblema primordial": 82, "Emblema amplificador": 83, "Esencia retorcida": 122,
                 "Medallas": 10000028}


def _sin_tildes(t):
    return "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")


def canonico(nombre):
    t = re.sub(r"\s+", " ", str(nombre or "")).strip()
    clave = _sin_tildes(t.lower())
    if clave in ALIAS:
        return ALIAS[clave]
    return t[:1].upper() + t[1:]


def _num(v):
    if isinstance(v, (int, float)):
        return int(v) if float(v).is_integer() else v
    return 0


# ============================================================
# Importar desde la planilla
# ============================================================

def importar_excel(ruta):
    """(datos_base, estado) leídos de la planilla del usuario (hojas 'pisos', 'Total' y 'Tienda')."""
    from openpyxl import load_workbook
    wb = load_workbook(ruta)

    # --- pisos: la tabla con encabezado "Piso" en la columna A
    ws = wb["pisos"]
    fila_enc = next(r for r in range(1, 30) if str(ws.cell(r, 1).value or "").strip().lower() == "piso")
    encabezados = {}
    for c in range(2, ws.max_column + 1):
        v = ws.cell(fila_enc, c).value
        if v:
            encabezados[c] = canonico(v)
    pisos = []
    for r in range(fila_enc + 1, ws.max_row + 1):
        piso = ws.cell(r, 1).value
        if not isinstance(piso, (int, float)):
            continue
        rec = {}
        for c, nombre in encabezados.items():
            v = _num(ws.cell(r, c).value)
            if v:
                rec[nombre] = v
        pisos.append({"piso": int(piso), "recompensas": rec})

    # --- cofres: en 'Total', filas "Cofre... disponibles" (opciones 2 filas arriba, cantidades 1 arriba)
    ws = wb["Total"]
    cofres, estado_cofres = {}, {}
    n = 0
    for r in range(1, ws.max_row + 1):
        if re.match(r"cofre\s*\d*\s*disponibles", str(ws.cell(r, 2).value or ""), re.I):
            n += 1
            nombre = f"Cofre {n}"
            opciones, elegidos = {}, {}
            for c in range(4, ws.max_column + 1):
                op = ws.cell(r - 2, c).value
                if not op:
                    if opciones:
                        break
                    continue
                op = canonico(op)
                opciones[op] = _num(ws.cell(r - 1, c).value)
                ahora, despues = _num(ws.cell(r, c).value), _num(ws.cell(r + 1, c).value)
                if ahora or despues:
                    elegidos[op] = {"ahora": ahora, "planeado": despues}
            cofres[nombre] = opciones
            estado_cofres[nombre] = elegidos
    piso_alcanzado = _num(ws["B4"].value) or 0

    # --- tiendas: en 'Tienda', columna I: "Tienda N" y debajo Objeto / Máximo / Precio / Compras... / Unidades
    ws = wb["Tienda"]
    tiendas, compras = [], {}
    for r in range(1, ws.max_row + 1):
        titulo = str(ws.cell(r, 9).value or "")
        m = re.match(r"tienda\s*(\d+)", titulo, re.I)
        if not m:
            continue
        filas = {}
        for rr in range(r + 1, r + 12):
            etiqueta = _sin_tildes(str(ws.cell(rr, 9).value or "").lower())
            if etiqueta.startswith("tienda"):
                break
            for clave, patron in (("objeto", "objeto"), ("maximo", "maximo"), ("precio", "precio"),
                                  ("hechas", "compras con medallas disponibles"),
                                  ("planeadas", "compras con medallas faltantes"), ("unidades", "unidades")):
                if etiqueta.startswith(patron) and clave not in filas:
                    filas[clave] = rr
        objetos = []
        for c in range(10, ws.max_column + 1):
            obj = ws.cell(filas.get("objeto", 0), c).value if "objeto" in filas else None
            if not obj:
                continue
            def valor(clave):
                return _num(ws.cell(filas[clave], c).value) if clave in filas else 0
            objetos.append({"objeto": canonico(obj), "maximo": valor("maximo"), "precio": valor("precio"),
                            "unidades": valor("unidades") or 1})
            clave = f"{titulo.strip()}|{len(objetos) - 1}"
            if valor("hechas") or valor("planeadas"):
                compras[clave] = {"hechas": valor("hechas"), "planeadas": valor("planeadas")}
        tiendas.append({"nombre": titulo.strip(), "piso": int(m.group(1)), "objetos": objetos})

    base = {"pisos": pisos, "cofres": cofres, "tiendas": tiendas, "origen": Path(ruta).name}
    estado = {"piso": piso_alcanzado, "cofres": estado_cofres, "compras": compras}
    return base, estado


# ============================================================
# Guardar / cargar
# ============================================================

def ruta_base(base_dir):
    return Path(base_dir) / ARCHIVO_BASE


def cargar_base(base_dir):
    """datos/fractura_temporal.json; en una instalación nueva se parte de recursos/fractura_temporal_base.json."""
    for ruta in (ruta_base(base_dir), RAIZ / "recursos" / "fractura_temporal_base.json"):
        try:
            return json.loads(ruta.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
    return None


def guardar_base(base_dir, datos):
    ruta = ruta_base(base_dir)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")


def cargar_estado(carpeta):
    try:
        return json.loads((Path(carpeta) / ARCHIVO_ESTADO).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"piso": 0, "cofres": {}, "compras": {}}


def guardar_estado(carpeta, estado):
    Path(carpeta).mkdir(parents=True, exist_ok=True)
    (Path(carpeta) / ARCHIVO_ESTADO).write_text(json.dumps(estado, ensure_ascii=False, indent=1), encoding="utf-8")


# ============================================================
# Cálculos
# ============================================================

def pisos_validos(base):
    return [p["piso"] for p in base["pisos"]]


def proximo_viernes(hoy=None):
    """Fecha del próximo viernes (hoy si hoy es viernes)."""
    from datetime import date, timedelta
    hoy = hoy or date.today()
    return hoy + timedelta(days=(4 - hoy.weekday()) % 7)


def calcular(base, estado, bolsa=None):
    """
    Todo lo que muestra la ventana:
      recursos: {nombre: {pisos_obtenido, pisos_faltante, tienda_comprado, tienda_planeado, tienda_pendiente,
                          cofres_ahora, cofres_planeado, conseguido, aun_obtenible, hasta_meta, bolsa, tendras}}
      cofres:   {nombre: {disponibles, restantes, total, usados_ahora, gastados, libres, usados_planeados, hasta_meta}}
      medallas: {ganadas, por_ganar, gastadas, planeadas, saldo, saldo_final, hasta_meta}
      meta:     {piso, desde, recompensas: {recurso: n}} (recompensas de los pisos entre el actual y la meta)
      avisos:   [texto]
    bolsa: {recurso: cantidad} de tu inventario (último fetch); "tendras" = bolsa + aún obtenible.
    """
    piso = int(estado.get("piso") or 0)
    meta = int(estado.get("meta") or 0)
    recursos = {}

    def r(nombre):
        return recursos.setdefault(nombre, {k: 0 for k in (
            "pisos_obtenido", "pisos_faltante", "tienda_comprado", "tienda_planeado", "tienda_pendiente",
            "cofres_ahora", "cofres_planeado", "hasta_meta")})

    especiales = {k: [0, 0] for k in COLUMNAS_ESPECIALES}
    en_meta = {}
    for p in base["pisos"]:
        logrado = p["piso"] <= piso
        hacia_meta = piso < p["piso"] <= meta
        for nombre, cant in p["recompensas"].items():
            if hacia_meta:
                en_meta[nombre] = en_meta.get(nombre, 0) + cant
            if nombre in especiales:
                especiales[nombre][0 if logrado else 1] += cant
                continue
            r(nombre)["pisos_obtenido" if logrado else "pisos_faltante"] += cant
            if hacia_meta:
                r(nombre)["hasta_meta"] += cant

    avisos = []
    cofres = {}
    for nombre, opciones in base["cofres"].items():
        disp, rest = especiales.get(nombre, [0, 0])
        elegidos = (estado.get("cofres") or {}).get(nombre) or {}
        gastados = int((estado.get("cofres_gastados") or {}).get(nombre) or 0)
        usados_a = sum(int(e.get("ahora") or 0) for e in elegidos.values())
        usados_p = sum(int(e.get("planeado") or 0) for e in elegidos.values())
        for op, e in elegidos.items():
            por_cofre = opciones.get(op, 0)
            r(op)["cofres_ahora"] += por_cofre * int(e.get("ahora") or 0)
            r(op)["cofres_planeado"] += por_cofre * int(e.get("planeado") or 0)
        cofres[nombre] = {"disponibles": disp, "restantes": rest, "total": disp + rest,
                          "usados_ahora": usados_a, "gastados": gastados, "libres": disp - usados_a - gastados,
                          "usados_planeados": usados_p, "hasta_meta": en_meta.get(nombre, 0)}
        if usados_a + gastados > disp:
            avisos.append(f"{nombre}: elegiste {usados_a} y marcaste {gastados} como gastados, "
                          f"pero solo tienes {disp}.")
        if usados_p > rest:
            avisos.append(f"{nombre}: planeaste {usados_p} pero solo quedan {rest} por conseguir.")

    gastadas = planeadas = 0
    for t in base["tiendas"]:
        for i, o in enumerate(t["objetos"]):
            c = (estado.get("compras") or {}).get(f"{t['nombre']}|{i}") or {}
            hechas, plan = int(c.get("hechas") or 0), int(c.get("planeadas") or 0)
            gastadas += hechas * o["precio"]
            planeadas += plan * o["precio"]
            x = r(o["objeto"])
            x["tienda_comprado"] += hechas * o["unidades"]
            x["tienda_planeado"] += plan * o["unidades"]
            x["tienda_pendiente"] += max(0, o["maximo"] - hechas - plan) * o["unidades"]
            if hechas + plan > o["maximo"]:
                avisos.append(f"{t['nombre']} · {o['objeto']}: {hechas + plan} compras, el máximo es {o['maximo']}.")

    ganadas, por_ganar = especiales["Medallas"]
    medallas = {"ganadas": ganadas, "por_ganar": por_ganar, "gastadas": gastadas, "planeadas": planeadas,
                "saldo": ganadas - gastadas, "saldo_final": ganadas + por_ganar - gastadas - planeadas,
                "hasta_meta": en_meta.get("Medallas", 0)}
    # el plan se calcula hasta la meta (los pisos que vas a subir), no hasta el final de la Fractura
    medallas["saldo_meta"] = medallas["saldo"] + medallas["hasta_meta"] - planeadas
    juego = estado.get("medallas_juego")
    if isinstance(juego, int) and juego != medallas["saldo"]:
        avisos.append(f"El juego muestra {juego} medallas y el cálculo da {medallas['saldo']} "
                      f"(diferencia {medallas['saldo'] - juego:+}): revisa el piso o las compras marcadas.")
    if medallas["saldo"] < 0:
        avisos.append(f"Gastaste {gastadas} medallas pero solo has ganado {ganadas}.")
    if medallas["saldo_final"] < 0:
        avisos.append(f"Lo planeado cuesta {-medallas['saldo_final']} medallas más de las que darán los pisos.")

    bolsa = bolsa or {}
    for nombre in bolsa:
        if nombre not in COLUMNAS_ESPECIALES:
            r(nombre)
    for nombre, x in recursos.items():
        x["conseguido"] = x["pisos_obtenido"] + x["tienda_comprado"] + x["cofres_ahora"]
        x["aun_obtenible"] = x["pisos_faltante"] + x["tienda_planeado"] + x["cofres_planeado"]
        x["bolsa"] = bolsa.get(nombre)
        # plan hasta la meta: bolsa + pisos hasta la meta + cofres y compras planeados
        x["plan_meta"] = x["hasta_meta"] + x["tienda_planeado"] + x["cofres_planeado"]
        x["tendras"] = (x["bolsa"] + x["plan_meta"]) if x["bolsa"] is not None else None
        x["tendras_final"] = (x["bolsa"] + x["aun_obtenible"]) if x["bolsa"] is not None else None
    siguiente = next((p for p in base["pisos"] if p["piso"] > piso), None)
    return {"recursos": recursos, "cofres": cofres, "medallas": medallas, "avisos": avisos,
            "siguiente": siguiente, "piso": piso,
            "meta": {"piso": meta, "desde": piso, "recompensas": en_meta} if meta > piso else None}


# ============================================================
# Tu bolsa (inventario del último fetch)
# ============================================================

def vinculos(base):
    """{recurso: id de objeto/moneda en la bolsa}. Se pueden cambiar desde la app (se guardan en la base)."""
    salida = {k: str(v) for k, v in EN_INVENTARIO.items()}
    salida.update({k: str(v) for k, v in (base.get("bolsa") or {}).items() if v not in (None, "")})
    return {k: v for k, v in salida.items() if v != "-"}


def objetos_bolsa(estado_cuenta):
    """[(id, nombre, cantidad)] de todo lo que hay en la bolsa (objetos y monedas)."""
    if not estado_cuenta:
        return []
    salida = []
    for o in (estado_cuenta.get("monedas") or []) + (estado_cuenta.get("objetos") or []):
        try:
            cant = int(o.get("cantidad"))
        except (TypeError, ValueError):
            continue
        salida.append((str(o.get("id")), o.get("nombre") or str(o.get("id")), cant))
    return salida


def _buscar_en_bolsa(estado_cuenta, ident):
    """Objeto de la bolsa por id ("310"), por nombre ("n:Time Emblem") o por expresión ("re:Rift.*R1")."""
    for o in (estado_cuenta.get("monedas") or []) + (estado_cuenta.get("objetos") or []):
        if ident.startswith("re:"):
            if re.search(ident[3:], o.get("nombre") or "", re.I):
                return o
        elif ident.startswith("n:"):
            if (o.get("nombre") or "").strip().lower() == ident[2:].strip().lower():
                return o
        elif str(o.get("id")) == ident:
            return o
    return None


def inventario(estado_cuenta, base=None):
    """{recurso: cantidad} de los recursos de la fractura vinculados a algo de tu bolsa.
    Los recursos en millones ("Oro (M)") se dividen por 1.000.000. Un vínculo por nombre que no está en tu bolsa
    queda en None (puede ser 0 o que el nombre sea distinto)."""
    if not estado_cuenta:
        return {}
    salida = {}
    for nombre, ident in vinculos(base or {}).items():
        o = _buscar_en_bolsa(estado_cuenta, ident)
        if o is None:
            if ident.startswith(("n:", "re:")):
                salida[nombre] = None   # vinculado pero no está en la bolsa: 0 o nombre distinto
            continue
        try:
            cant = int(o.get("cantidad"))
        except (TypeError, ValueError):
            continue
        salida[nombre] = round(cant / 1_000_000, 1) if nombre.endswith("(M)") else cant
    return salida


_BOLSAS = {}


def _otras_bolsas(base_dir):
    """Bolsas de todas las cuentas/servidores sincronizados (para encontrar íconos que tu cuenta no tiene)."""
    import glob
    salida = []
    for f in glob.glob(str(Path(base_dir) / "cuentas" / "*" / "*" / "cuenta_actual.json")):
        try:
            mtime = Path(f).stat().st_mtime
            if _BOLSAS.get(f, (None,))[0] != mtime:
                d = json.loads(Path(f).read_text(encoding="utf-8"))
                _BOLSAS[f] = (mtime, {"objetos": d.get("objetos") or [], "monedas": d.get("monedas") or []})
            salida.append(_BOLSAS[f][1])
        except (OSError, json.JSONDecodeError):
            continue
    return salida


def imagen_bolsa(estado_cuenta, base, recurso, base_dir=None):
    """imageUrl del objeto de la bolsa vinculado a un recurso (o None). Con base_dir, si tu cuenta no lo tiene,
    se busca en las bolsas de tus otras cuentas sincronizadas (p. ej. el Time Emblem del servidor 1192)."""
    ident = vinculos(base or {}).get(recurso)
    if not ident:
        return None
    o = _buscar_en_bolsa(estado_cuenta or {}, ident)
    if (o is None or not o.get("imageUrl")) and base_dir:
        for bolsa in _otras_bolsas(base_dir):
            o = _buscar_en_bolsa(bolsa, ident)
            if o and o.get("imageUrl"):
                break
    return (o or {}).get("imageUrl")
