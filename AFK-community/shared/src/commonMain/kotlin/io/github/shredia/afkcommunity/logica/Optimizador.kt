package io.github.shredia.afkcommunity.logica

import io.github.shredia.afkcommunity.datos.Datos
import io.github.shredia.afkcommunity.datos.a
import io.github.shredia.afkcommunity.datos.aJson
import io.github.shredia.afkcommunity.datos.clave
import io.github.shredia.afkcommunity.datos.con
import io.github.shredia.afkcommunity.datos.entero
import io.github.shredia.afkcommunity.datos.esNulo
import io.github.shredia.afkcommunity.datos.int
import io.github.shredia.afkcommunity.datos.mutable
import io.github.shredia.afkcommunity.datos.numeroPy
import io.github.shredia.afkcommunity.datos.o
import io.github.shredia.afkcommunity.datos.obj
import io.github.shredia.afkcommunity.datos.objetos
import io.github.shredia.afkcommunity.datos.py
import io.github.shredia.afkcommunity.datos.real
import io.github.shredia.afkcommunity.datos.sin
import io.github.shredia.afkcommunity.datos.textoO
import io.github.shredia.afkcommunity.datos.unir
import io.github.shredia.afkcommunity.datos.verdad
import io.github.shredia.afkcommunity.idiomas.N_
import io.github.shredia.afkcommunity.idiomas.formatear
import io.github.shredia.afkcommunity.idiomas.tr
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.isActive
import kotlinx.coroutines.yield
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlin.time.TimeSource

/*
 * Optimizador Nightmare Corridor (port de navegador/optimizador.py).
 *
 * - La rotación son 6 Boss_ID. Los candidatos de cada posición se buscan por Boss_ID,
 *   así una rotación nueva aprovecha los equipos usados contra ese jefe en cualquier rotación.
 * - No se puede repetir un héroe entre jefes; las mascotas opcionalmente tampoco.
 * - Equipos idénticos (mismos 5 héroes + mascota) solo aportan su mejor tiempo.
 * - Búsqueda por ramificación y poda con límite de tiempo.
 */

const val VERSION_INDICE = 5
const val ARCHIVO_INDICE = "optimizador_indice.json"
const val ARCHIVO_BANEOS = "baneos.json"

// Origen de cada héroe usado en una ronda
const val PROPIO = "propio"
const val PRESTADO = "prestado"
const val PRUEBA = "prueba"
const val TEMPORAL = "temporal"
const val FUERA_ROSTER = "fuera_roster"
val TEMPORALES = setOf(PRESTADO, PRUEBA, TEMPORAL)
val NOMBRES_ORIGEN = mapOf(
    PROPIO to N_("Propio"),
    PRESTADO to N_("Prestado (mercenario)"),
    PRUEBA to N_("De prueba"),
    TEMPORAL to N_("Prestado / de prueba"),
    FUERA_ROSTER to N_("Ya no está en tu roster"),
)
const val ID_TEMPORAL_MIN = 4294967296L   // el juego da ids ≥ 2^32 a las copias temporales

// ============================================================
// ÍNDICE COMPACTO
// ============================================================

private fun compactarHeroe(h: JsonObject): LinkedHashMap<String, JsonElement> {
    val m = h.mutable()
    // engravingNodes es enorme; se guarda solo lo necesario para mostrarlo
    m["engravingNodes"] = JsonArray(h["engravingNodes"].objetos().map { n ->
        obj("key" to n["key"], "level" to n["level"], "max" to n["max"], "stats" to n["stats"])
    })
    return m
}

private fun firmaStats(h: JsonObject): List<String> = listOf(h["quality"].py(), h["sig"].py(), h["engraving"].py())

fun esIdTemporal(hid: JsonElement?): Boolean = esIdTemporal(hid.py())

fun esIdTemporal(hid: String): Boolean = hid.trim().toLongOrNull()?.let { it >= ID_TEMPORAL_MIN } ?: false

/**
 * Héroe dimensional arrendado: es TUYO aunque el juego lo marque 'borrowed'.
 * Los prestados de verdad (mercenarios) tienen ids temporales (≥ 2^32).
 */
fun esArrendado(h: JsonObject): Boolean =
    h["arrendado"].verdad() || (h["prestado"].verdad() && !esIdTemporal(h["id"]))

/** Clasifica la copia del héroe usada en una ronda. */
fun origenHeroe(h: JsonObject, idsRoster: Set<String>, plantillasBorrow: Map<String, List<String>>,
                plantillasTest: Map<String, List<String>>): String {
    val hid = h["id"].textoO()
    if (esArrendado(h)) return PROPIO
    if (h["prestado"].verdad()) return PRESTADO
    val temporal = esIdTemporal(hid)
    if (hid in idsRoster && !temporal) return PROPIO
    if (temporal) {
        val tid = h["tid"].py()
        if (plantillasTest[tid] == firmaStats(h)) return PRUEBA
        if (plantillasBorrow[tid] == firmaStats(h)) return PRESTADO
        return TEMPORAL
    }
    return if (idsRoster.isNotEmpty()) FUERA_ROSTER else PROPIO
}

private fun extraerRun(detalle: JsonObject, resumen: JsonObject): JsonObject {
    val idsRoster = detalle["roster"].objetos().map { it["id"].py() }.toSet()
    val borrow = detalle["borrow"].objetos().associate { it["tid"].py() to firmaStats(it) }
    val test = detalle["test"].objetos().associate { it["tid"].py() to firmaStats(it) }
    val rondas = detalle["rounds"].objetos().map { r ->
        val heroes = r["heroes"].objetos().map { h ->
            val compacto = compactarHeroe(h)
            compacto["origen"] = JsonPrimitive(origenHeroe(h, idsRoster, borrow, test))
            if (esArrendado(h)) {
                compacto["arrendado"] = JsonPrimitive(true)
                compacto.remove("prestado")
            }
            JsonObject(compacto)
        }
        obj(
            "index" to (r["index"] ?: JsonPrimitive(0)),
            "bossId" to r["bossId"].py(),
            "recorded" to r["recorded"].o(),
            "golden" to (r["golden"] ?: JsonNull),
            "estadisticas" to r["estadisticas"].o(),
            "pet" to r["pet"].o(),
            "heroes" to heroes,
        )
    }
    return obj(
        "id" to (if (detalle["id"].verdad()) detalle["id"] else resumen["id"]).py(),
        "playedAt" to (if (resumen["playedAt"].verdad()) resumen["playedAt"] else if (detalle["playedAt"].verdad()) detalle["playedAt"] else JsonPrimitive("")),
        "result" to (if (resumen["result"].verdad()) resumen["result"] else detalle["result"].o()),
        "rounds" to rondas,
    )
}

private fun extraerReferencias(detalle: JsonObject): JsonObject = obj(
    "collectionTags" to detalle["collectionTags"].o(),
    "gearOptions" to detalle["gearOptions"].o(),
    "tree" to detalle["tree"].o(),
)

class DatosIndice(val runs: List<JsonObject>, val refs: JsonObject)

/**
 * Las runs de un servidor, usando un índice en disco que solo se actualiza con los detalles nuevos o
 * modificados (el mismo optimizador_indice.json de la app Python).
 */
suspend fun cargarIndice(datos: Datos, carpeta: String, progreso: (String) -> Unit = {}): DatosIndice {
    val almacen = datos.almacen
    val archivoIndice = unir(carpeta, ARCHIVO_INDICE)
    val carpetaDetalles = unir(carpeta, "detalles")
    val detalles = almacen.listar(carpetaDetalles).filter { it.endsWith(".json") }.sorted()

    val resumenes = datos.leerLista(unir(carpeta, "runs.json")).objetos().associateBy { it["id"].py() }

    var archivos = LinkedHashMap<String, JsonElement>()
    var runs = LinkedHashMap<String, JsonElement>()
    var refs: JsonObject = obj()
    val previo = datos.leerObjeto(archivoIndice)
    if (previo != null && previo["version"].entero(null) == VERSION_INDICE.toLong()) {
        archivos = previo["archivos"].o().mutable()
        runs = previo["runs"].o().mutable()
        refs = previo["refs"].o()
    }

    val actuales = LinkedHashMap<String, Double>()
    for (n in detalles) actuales[n] = almacen.modificado(unir(carpetaDetalles, n)) ?: 0.0
    val nuevos = detalles.filter { archivos[it].real() != actuales[it] }
    val borrados = archivos.keys - actuales.keys

    for (n in borrados) {
        archivos.remove(n)
        runs.remove(n.removeSuffix(".json"))
    }

    for ((i, archivo) in nuevos.withIndex()) {
        progreso(tr("Indexando detalle {0}/{1}...", i + 1, nuevos.size))
        val detalle = datos.leerObjeto(unir(carpetaDetalles, archivo)) ?: continue
        val rid = archivo.removeSuffix(".json")
        runs[rid] = extraerRun(detalle, resumenes[rid] ?: obj())
        archivos[archivo] = numeroPy(actuales[archivo]!!)
        if (detalle["gearOptions"].verdad() || refs.isEmpty()) refs = extraerReferencias(detalle)
        if (i % 16 == 15) yield()
    }

    // Los resúmenes (fecha, resultado) pueden llegar después que el detalle
    for ((rid, valor) in runs.entries.toList()) {
        val r = resumenes[rid] ?: continue
        val run = valor.o()
        runs[rid] = run.con(
            "playedAt" to (r["playedAt"] ?: run["playedAt"] ?: JsonPrimitive("")),
            "result" to (if (r["result"].verdad()) r["result"] else run["result"].o()),
        )
    }

    if (nuevos.isNotEmpty() || borrados.isNotEmpty()) {
        progreso(tr("Guardando índice..."))
        val indice = obj("version" to VERSION_INDICE, "archivos" to JsonObject(archivos),
            "runs" to JsonObject(runs), "refs" to refs)
        datos.escribirJson(archivoIndice, indice)
    }
    return DatosIndice(runs.values.map { it.o() }, refs)
}

// ============================================================
// COMPOSICIONES
// ============================================================

class Composicion(
    val runId: String,
    val fecha: String,
    val rotacion: String,
    val posicion: Int,            // 1..6 dentro de su run
    val bossId: String,
    val tiempo: Double,           // segundos (0 si no lo derrotó)
    val derrotado: Boolean,
    val runCompleta: Boolean,
    var heroes: List<JsonObject>, // dicts completos, ordenados por slot
    val mascota: JsonObject,
    var golden: JsonElement? = null,
    val heroIds: List<String> = emptyList(),     // tid (o nombre) en mayúsculas
    val heroNombres: List<String> = emptyList(),
    val mascotaId: String = "",
    val mascotaNombre: String = "",
    val heroOrigenes: List<String> = emptyList(),
    var veces: Int = 1,
    val estadisticas: JsonObject = obj(),
    var spManual: Boolean = false,
) {
    /** De quién es el equipo (amigo u otro servidor); null = tuyo. */
    var dueno: String? = null
    var carpetaOrigen: String? = null

    /** Una copia prestada/de prueba se considera distinta de la propia (otra build). */
    val firma: String by lazy {
        val partes = heroIds.zip(heroOrigenes).map { (i, o) -> if (o == PROPIO) i else "$i*$o" }
        partes.sorted().joinToString("|") + "|P:" + mascotaId
    }

    val noPropios: List<Pair<JsonObject, String>> get() = heroes.zip(heroOrigenes).filter { it.second != PROPIO }
}

const val SP_DESCONOCIDO = "?"

/**
 * Slot del héroe que usó su Special Power. Solo los héroes especiales (hyper) lo tienen:
 * con uno solo en el equipo se activa automáticamente; con dos o más se elige uno.
 */
fun deducirGolden(heroes: List<JsonObject>, golden: JsonElement?): JsonElement? {
    if (!golden.esNulo() && !(golden is JsonPrimitive && golden.isString && golden.content == "")) return golden
    val especiales = heroes.filter { it["hyper"].verdad() }.map { it["slot"] ?: JsonNull }
    if (especiales.size == 1) return especiales[0]
    return if (especiales.isNotEmpty()) JsonPrimitive(SP_DESCONOCIDO) else null
}

const val ARCHIVO_SP = "sp_manual.json"

private fun claveSp(c: Composicion) = "${c.runId}|${c.posicion}"

suspend fun cargarSpManual(datos: Datos, carpeta: String): JsonObject =
    datos.leerObjeto(unir(carpeta, ARCHIVO_SP)) ?: obj()

private fun esDesconocido(g: JsonElement?) = g.esNulo() || (g is JsonPrimitive && g.isString && g.content == SP_DESCONOCIDO)

/** Pone en cada ronda dudosa el héroe del SP que marcaste a mano. */
suspend fun aplicarSpManual(comps: List<Composicion>, datos: Datos, carpeta: String): List<Composicion> {
    val manual = cargarSpManual(datos, carpeta)
    if (manual.isEmpty()) return comps
    for (c in comps) {
        val slot = manual[claveSp(c)]
        if (!slot.esNulo() && (esDesconocido(c.golden) || c.spManual)) {
            c.golden = slot
            c.spManual = true
        }
    }
    return comps
}

/** Guarda (o borra, con slot null) el héroe del SP de una ronda. */
suspend fun guardarSpManual(datos: Datos, carpeta: String, comp: Composicion, slot: Int?) {
    val manual = cargarSpManual(datos, carpeta).mutable()
    if (slot == null) manual.remove(claveSp(comp)) else manual[claveSp(comp)] = JsonPrimitive(slot)
    datos.escribirJson(unir(carpeta, ARCHIVO_SP), JsonObject(manual), indentado = true)
}

/** Ids de héroes dimensionales arrendados según la captura de la cuenta. */
fun arrendadosDe(estado: JsonObject?): List<String> {
    val e = estado ?: obj()
    if ("heroes_arrendados" in e) return e["heroes_arrendados"].a().map { it.py() }
    return e["heroes_temporales"].a().map { it.py() }
}

private fun derrotadoRonda(r: JsonObject): Boolean {
    val rec = r["recorded"].o()
    return rec["timeMs"].verdad() && (rec["bossesKilled"].entero(0) ?: 0) >= 1
}

/**
 * Una composición por (run, jefe).
 * heroesTemporales: ids que el inventario marca como temporales; si aparecen como "ya no está en tu roster"
 * se reclasifican como "de prueba".
 */
fun construirComposiciones(runs: List<JsonObject>, heroesTemporales: Collection<String> = emptyList(),
                           heroesArrendados: Collection<String>? = null): List<Composicion> {
    val temporales = heroesTemporales.toSet()
    val arrendados = heroesArrendados?.toSet() ?: temporales
    val comps = mutableListOf<Composicion>()
    for (run in runs) {
        val rondas = run["rounds"].objetos().sortedBy { it["index"].int(0) }
        if (rondas.isEmpty()) continue
        val rotacion = rondas.joinToString("-") { it["bossId"].py() }
        val resultado = run["result"].o()
        val completa = if (!resultado["bossesKilled"].esNulo()) resultado["bossesKilled"].entero(null) == 6L
        else rondas.size == 6 && rondas.all { derrotadoRonda(it) }

        for (r in rondas) {
            val mascota = r["pet"].o()
            val ids = mutableListOf<String>()
            val nombres = mutableListOf<String>()
            val origenes = mutableListOf<String>()
            val heroes = r["heroes"].objetos().sortedBy { it["slot"].int(0) }.map { h0 ->
                var h = h0
                val nombre = clave(h["name"])
                val ident = clave(h["tid"]).ifEmpty { nombre }
                ids += ident
                nombres += nombre
                var origen = h["origen"].textoO(PROPIO)
                val hid = h["id"].py()
                if (hid in arrendados && !esIdTemporal(hid)) {
                    origen = PROPIO
                    h = h.con("origen" to PROPIO, "arrendado" to true)
                } else if (origen == FUERA_ROSTER && hid in temporales) {
                    origen = PRUEBA
                    h = h.con("origen" to PRUEBA)
                }
                origenes += origen
                h
            }
            val rec = r["recorded"].o()
            comps += Composicion(
                runId = run["id"].py(),
                fecha = run["playedAt"].textoO(),
                rotacion = rotacion,
                posicion = r["index"].int(0) + 1,
                bossId = r["bossId"].py(),
                tiempo = (rec["timeMs"].real() ?: 0.0) / 1000,
                derrotado = derrotadoRonda(r),
                runCompleta = completa,
                heroes = heroes,
                mascota = mascota,
                golden = deducirGolden(heroes, r["golden"]),
                estadisticas = r["estadisticas"].o(),
                heroIds = ids,
                heroNombres = nombres,
                mascotaId = clave(mascota["tid"]).ifEmpty { clave(mascota["name"]) },
                mascotaNombre = clave(mascota["name"]),
                heroOrigenes = origenes,
            )
        }
    }
    return comps
}

/** Guarda en cada colección su nivel de habilidad (★), para poder limitar y comparar por él (_anotar_estrellas). */
fun anotarEstrellas(comps: List<Composicion>, vis: Visuales?) {
    if (vis == null || !vis.disponible) return
    for (c in comps) {
        c.heroes = c.heroes.map { h ->
            val col = h["collection"] as? JsonObject
            if (col != null && col.isNotEmpty() && "estrellas" !in col) h.con("collection" to col.con("estrellas" to (vis.estrellasColeccion(col) ?: 0)))
            else h
        }
    }
}

fun rotacionMasReciente(runs: List<JsonObject>): List<String> {
    val ultima = runs.maxByOrNull { it["playedAt"].textoO() } ?: return emptyList()
    return ultima["rounds"].objetos().sortedBy { it["index"].int(0) }.map { it["bossId"].py() }
}

/** {"HEROE": {nombre: id}, "MASCOTA": {nombre: id}} con nombres originales. */
fun catalogo(comps: List<Composicion>): Map<String, Map<String, String>> {
    val heroes = LinkedHashMap<String, String>()
    val mascotas = LinkedHashMap<String, String>()
    for (c in comps) {
        for (h in c.heroes) if (h["name"].verdad()) heroes[h["name"].py()] = h["tid"].textoO()
        if (c.mascota["name"].verdad()) mascotas[c.mascota["name"].py()] = c.mascota["tid"].textoO()
    }
    return mapOf("HEROE" to heroes, "MASCOTA" to mascotas)
}

// ============================================================
// BANEOS
// ============================================================

suspend fun cargarBaneos(datos: Datos, carpeta: String): List<JsonObject> =
    datos.leerJson(unir(carpeta, ARCHIVO_BANEOS)).objetos()

const val COPIA_TODAS = "TODAS"
const val COPIA_NO_PROPIA = "NO_PROPIA"
val NOMBRES_COPIA = mapOf(COPIA_TODAS to N_("Cualquier copia"), COPIA_NO_PROPIA to N_("Solo prestada/prueba"))

private fun activo(b: JsonObject) = b["activo"]?.verdad() ?: true

/** Claves 'TIPO|NOMBRE_O_ID|ALCANCE|COPIA' de los baneos activos. */
fun conjuntoBaneos(baneos: List<JsonObject>): Set<String> {
    val activos = HashSet<String>()
    for (b in baneos) {
        if (!activo(b) || b["limite"].verdad()) continue
        val tipo = clave(b["tipo"])
        val alcance = clave(b["jefe"]).ifEmpty { "TODOS" }
        var copia = clave(b["copia"]).ifEmpty { COPIA_TODAS }
        if (tipo != "HEROE") copia = COPIA_TODAS
        for (valor in listOf(clave(b["nombre"]), clave(b["id"]))) {
            if (valor.isNotEmpty()) activos += "$tipo|$valor|$alcance|$copia"
        }
    }
    return activos
}

fun baneada(comp: Composicion, posicion: Int, activos: Set<String>): Boolean {
    if (activos.isEmpty()) return false
    val alcances = listOf("TODOS", posicion.toString(), comp.bossId)
    val origenes = comp.heroOrigenes.ifEmpty { List(comp.heroIds.size) { PROPIO } }
    for (alcance in alcances) {
        for (i in comp.heroNombres.indices) {
            if (i >= comp.heroIds.size || i >= origenes.size) break
            val nombre = comp.heroNombres[i]
            val ident = comp.heroIds[i]
            val copias = if (origenes[i] == PROPIO) listOf(COPIA_TODAS) else listOf(COPIA_TODAS, COPIA_NO_PROPIA)
            for (copia in copias) {
                if ("HEROE|$nombre|$alcance|$copia" in activos || "HEROE|$ident|$alcance|$copia" in activos) return true
            }
        }
        if ("MASCOTA|${comp.mascotaNombre}|$alcance|$COPIA_TODAS" in activos ||
            "MASCOTA|${comp.mascotaId}|$alcance|$COPIA_TODAS" in activos) return true
    }
    return false
}

// ============================================================
// OPTIMIZACIÓN
// ============================================================

data class Opciones(
    val soloCompletas: Boolean = true,
    val prohibirRepetirMascota: Boolean = true,
    val limitePorJefe: Int = 0,        // 0 = todas
    val tiempoMaximo: Double = 60.0,   // segundos
    val excluirTemporales: Boolean = false,
    val excluirFueraRoster: Boolean = false,
)

const val OPTIMO_GLOBAL = "Óptimo global"
const val MEJOR_ENCONTRADA = "Mejor encontrada (no certificada)"
const val SIN_SOLUCION = "Sin solución"

class Resultado(
    val estado: String,
    val detalle: String,
    val total: Double = 0.0,
    val elegidas: List<Composicion> = emptyList(),
    val candidatos: Map<Int, List<Composicion>> = emptyMap(),
    val consideradas: Int = 0,
    val duracion: Double = 0.0,
)

// ============================================================
// LÍMITES DE BUILD
// ============================================================
// Un límite es un baneo con "limite": True:
//   {"limite": True, "objeto": "HEROE" | "COLECCION", "nombre": "Dracula" | "*", "campo": ..., "max": n,
//    "jefe": "TODOS" | posición | Boss ID, "activo": True}
val CAMPOS_HEROE = linkedMapOf("quality" to N_("Ascensión"), "sig" to N_("SI"), "engraving" to N_("Grabado"),
    "muebles" to N_("Muebles"))
val CAMPOS_COLECCION = linkedMapOf("estrellas" to N_("Nivel de habilidad (★)"), "mythic" to N_("Afijos míticos"),
    "level" to N_("Nivel de colección"))

private fun valorHeroe(h: JsonObject, campo: String?): Long {
    if (campo == "muebles") return h["furniture"].o()["pieces"].entero(0) ?: 0
    return h[campo ?: ""].entero(0) ?: 0
}

data class Limite(val objeto: String, val nombre: String, val campo: String?, val maximo: Long, val alcance: String)

fun limites(baneos: List<JsonObject>): List<Limite> = baneos.mapNotNull { b ->
    if (!b["limite"].verdad() || !activo(b)) return@mapNotNull null
    val maximo = b["max"].entero(null) ?: return@mapNotNull null
    Limite(clave(b["objeto"]), clave(b["nombre"]).ifEmpty { "*" }, b["campo"].takeUnless { it.esNulo() }?.py(),
        maximo, clave(b["jefe"]).ifEmpty { "TODOS" })
}

fun excedeLimite(comp: Composicion, posicion: Int, limites: List<Limite>): Boolean {
    val alcances = setOf("TODOS", posicion.toString(), comp.bossId)
    for ((objeto, nombre, campo, maximo, alcance) in limites) {
        if (alcance !in alcances) continue
        for (h in comp.heroes) {
            if (objeto == "HEROE") {
                if (nombre != "*" && nombre != clave(h["name"]) && nombre != clave(h["tid"])) continue
                if (valorHeroe(h, campo) > maximo) return true
            } else {   // COLECCION
                val col = h["collection"].o()
                if (col.isEmpty() || (nombre != "*" && nombre != clave(col["name"])) && nombre != clave(col["tid"])) continue
                val valor = col[campo ?: ""].entero(0) ?: 0
                if (valor > maximo) return true
            }
        }
    }
    return false
}

/** 'Colección Timeline Watch: máximo ★2' · 'Colección X: no la tengo' · 'Dracula: SI máximo 20'. */
fun describirLimite(b: JsonObject): String {
    val objeto = clave(b["objeto"])
    val nombre = b["nombre"].textoO("*")
    var quien = if (nombre == "*" && objeto == "HEROE") tr("Cualquier héroe")
    else if (nombre == "*") tr("Cualquier colección") else nombre.split(" - ")[0]
    if (objeto == "COLECCION" && nombre != "*") quien = tr("Colección {0}", quien)
    val maximo = b["max"].entero(0) ?: 0
    val campo = b["campo"].textoO()
    if (maximo < 0) return if (objeto == "COLECCION") tr("{0}: no la tengo", quien) else tr("{0}: no lo tengo", quien)
    if (objeto == "COLECCION") return tr("{0}: {1} máximo {2}", quien, tr(CAMPOS_COLECCION[campo] ?: campo), maximo)
    return tr("{0}: {1} máximo {2}", quien, tr(CAMPOS_HEROE[campo] ?: campo), maximo)
}

/** Las composiciones que no tocan ningún baneo ni límite (según su jefe y su posición en la rotación). */
fun quitarBaneadas(comps: List<Composicion>, rotacion: List<String>, baneos: List<JsonObject>): List<Composicion> {
    val activos = conjuntoBaneos(baneos)
    val lims = limites(baneos)
    if (activos.isEmpty() && lims.isEmpty()) return comps.toList()
    val posicionDe = HashMap<String, Int>()
    rotacion.forEachIndexed { i, boss -> if (boss.isNotEmpty()) posicionDe[boss] = i + 1 }
    return comps.filter { c ->
        val pos = posicionDe[c.bossId] ?: 0
        !baneada(c, pos, activos) && !(lims.isNotEmpty() && excedeLimite(c, pos, lims))
    }
}

/** posicion (1..6) -> lista de composiciones únicas, ordenadas por tiempo. */
fun candidatosPorJefe(comps: List<Composicion>, rotacion: List<String>, opciones: Opciones,
                      baneos: List<JsonObject>): Pair<Map<Int, List<Composicion>>, Int> {
    val activos = conjuntoBaneos(baneos)
    val lims = limites(baneos)
    val posicionDe = HashMap<String, Int>()
    rotacion.forEachIndexed { i, boss -> posicionDe[boss] = i + 1 }   // como el dict de Python: el último gana
    val mejores = (1..6).associateWith { LinkedHashMap<String, Composicion>() }
    val usos = (1..6).associateWith { HashMap<String, Int>() }
    var consideradas = 0

    for (c in comps) {
        val pos = posicionDe[c.bossId] ?: continue
        if (pos == 0 || !c.derrotado || c.tiempo <= 0) continue
        if (opciones.soloCompletas && !c.runCompleta) continue
        if (opciones.excluirTemporales && c.heroOrigenes.any { it in TEMPORALES }) continue
        if (opciones.excluirFueraRoster && FUERA_ROSTER in c.heroOrigenes) continue
        if (baneada(c, pos, activos)) continue
        if (lims.isNotEmpty() && excedeLimite(c, pos, lims)) continue
        consideradas++
        val firma = c.firma
        usos.getValue(pos)[firma] = (usos.getValue(pos)[firma] ?: 0) + 1
        val previo = mejores.getValue(pos)[firma]
        if (previo == null || c.tiempo < previo.tiempo) mejores.getValue(pos)[firma] = c
    }

    val candidatos = LinkedHashMap<Int, List<Composicion>>()
    for (pos in 1..6) {
        var lista = mejores.getValue(pos).values.sortedBy { it.tiempo }   // estable, como sorted de Python
        for (c in lista) c.veces = usos.getValue(pos)[c.firma] ?: 1
        if (opciones.limitePorJefe > 0) lista = lista.take(opciones.limitePorJefe)
        candidatos[pos] = lista
    }
    return candidatos to consideradas
}

/**
 * Busca la combinación más rápida de 6 equipos sin repetir héroes.
 * Cede el control cada 2048 nodos (donde Python revisa el reloj): así no congela la interfaz y se puede
 * cancelar; el recorrido y el resultado son los mismos.
 */
suspend fun optimizar(comps: List<Composicion>, rotacionEntrada: List<String>, opciones: Opciones,
                      baneos: List<JsonObject> = emptyList(), cancelar: () -> Boolean = { false }): Resultado {
    val rotacion = rotacionEntrada.map { it.trim() }
    if (rotacion.size != 6 || rotacion.any { it.isEmpty() }) return Resultado(SIN_SOLUCION, tr("La rotación debe tener 6 jefes."))
    if (rotacion.toSet().size != 6) return Resultado(SIN_SOLUCION, tr("Hay jefes repetidos en la rotación."))

    val (candidatos, consideradas) = candidatosPorJefe(comps, rotacion, opciones, baneos)
    for (pos in 1..6) {
        if (candidatos.getValue(pos).isEmpty()) {
            return Resultado(SIN_SOLUCION,
                tr("No hay composiciones elegibles para el jefe {0} (Boss {1}).", pos, rotacion[pos - 1]),
                candidatos = candidatos, consideradas = consideradas)
        }
    }

    // Datos planos para que la búsqueda sea rápida
    class Cand(val t: Double, val hs: Set<String>, val pet: String, val comp: Composicion)
    val cand = (1..6).map { p -> candidatos.getValue(p).map { Cand(it.tiempo, it.heroIds.toSet(), it.mascotaId, it) } }
    val minResto = DoubleArray(7)
    for (nivel in 5 downTo 0) minResto[nivel] = minResto[nivel + 1] + cand[nivel][0].t

    var mejor = Double.POSITIVE_INFINITY
    var elegidas: List<Composicion>? = null
    var agotado = false
    var nodos = 0L
    val inicio = TimeSource.Monotonic.markNow()
    val usadosH = HashSet<String>()
    val usadosP = HashSet<String>()
    val picks = arrayOfNulls<Composicion>(6)
    val unicaMascota = opciones.prohibirRepetirMascota
    val contexto = currentCoroutineContext()

    suspend fun buscar(nivel: Int, total: Double) {
        nodos++
        if (nodos % 2048 == 0L) {
            if (inicio.elapsedNow().inWholeMilliseconds / 1000.0 > opciones.tiempoMaximo || cancelar() || !contexto.isActive) {
                agotado = true
            } else {
                yield()
            }
        }
        if (agotado) return
        if (nivel == 6) {
            if (total < mejor) {
                mejor = total
                elegidas = picks.map { it!! }
            }
            return
        }
        if (total + minResto[nivel] >= mejor) return
        for (c in cand[nivel]) {
            if (total + c.t + minResto[nivel + 1] >= mejor) break   // ordenados por tiempo: los siguientes son peores
            if (c.hs.any { it in usadosH }) continue
            if (unicaMascota && c.pet.isNotEmpty() && c.pet in usadosP) continue
            picks[nivel] = c.comp
            usadosH.addAll(c.hs)
            if (unicaMascota && c.pet.isNotEmpty()) usadosP.add(c.pet)
            buscar(nivel + 1, total + c.t)
            usadosH.removeAll(c.hs)
            if (unicaMascota && c.pet.isNotEmpty()) usadosP.remove(c.pet)
            if (agotado) return
        }
    }

    buscar(0, 0.0)
    val duracion = inicio.elapsedNow().inWholeMilliseconds / 1000.0

    val elegidasFinal = elegidas
    if (elegidasFinal == null) {
        val detalle = if (agotado) tr("Límite de tiempo agotado") else tr("Baneos o conflictos impiden formar seis equipos")
        return Resultado(SIN_SOLUCION, detalle, candidatos = candidatos, consideradas = consideradas, duracion = duracion)
    }
    return Resultado(
        if (agotado) MEJOR_ENCONTRADA else OPTIMO_GLOBAL,
        if (agotado) tr("Tiempo agotado: resultado factible") else tr("Búsqueda completa"),
        total = mejor,
        elegidas = elegidasFinal,
        candidatos = candidatos,
        consideradas = consideradas,
        duracion = duracion,
    )
}

/** Tiempo para mostrar: 23.391 -> '23.391 s' · 132.393 -> '2m 12.393 s'. */
fun formatoTiempo(segundos: Double?): String {
    if (segundos == null) return "—"
    // divmod(round(segundos, 3), 60) de Python
    val redondeado = formatear("{0:.3f}", listOf(segundos)).toDouble()
    val minutos = kotlin.math.floor(redondeado / 60)
    val resto = redondeado - minutos * 60
    if (minutos < 1) return formatear("{0:.3f} s", listOf(resto))
    return formatear("{0}m {1:06.3f} s", listOf(minutos.toInt(), resto))
}

/** Orden de jefes: numéricos primero, por número. */
val ordenBoss: Comparator<String> = compareBy<String>({ it.toIntOrNull() == null }, { it.toIntOrNull() ?: 0 }, { it })
