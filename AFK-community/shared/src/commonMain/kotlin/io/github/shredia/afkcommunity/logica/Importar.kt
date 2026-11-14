package io.github.shredia.afkcommunity.logica

import io.github.shredia.afkcommunity.datos.ARCHIVO_PREFERENCIAS
import io.github.shredia.afkcommunity.datos.CARPETAS_ESPECIALES
import io.github.shredia.afkcommunity.datos.CARPETA_AMIGOS
import io.github.shredia.afkcommunity.datos.CARPETA_CUENTAS
import io.github.shredia.afkcommunity.datos.CARPETA_LOCAL
import io.github.shredia.afkcommunity.datos.CARPETA_SIN_ASIGNAR
import io.github.shredia.afkcommunity.datos.Datos
import io.github.shredia.afkcommunity.datos.EscritorZip
import io.github.shredia.afkcommunity.datos.LectorZip
import io.github.shredia.afkcommunity.datos.TrozoJson
import io.github.shredia.afkcommunity.datos.a
import io.github.shredia.afkcommunity.datos.aTexto
import io.github.shredia.afkcommunity.datos.con
import io.github.shredia.afkcommunity.datos.entero
import io.github.shredia.afkcommunity.datos.esNulo
import io.github.shredia.afkcommunity.datos.int
import io.github.shredia.afkcommunity.datos.leerJsonTexto
import io.github.shredia.afkcommunity.datos.mutable
import io.github.shredia.afkcommunity.datos.nombre
import io.github.shredia.afkcommunity.datos.o
import io.github.shredia.afkcommunity.datos.obj
import io.github.shredia.afkcommunity.datos.objetos
import io.github.shredia.afkcommunity.datos.padre
import io.github.shredia.afkcommunity.datos.py
import io.github.shredia.afkcommunity.datos.s
import io.github.shredia.afkcommunity.datos.sin
import io.github.shredia.afkcommunity.datos.textoO
import io.github.shredia.afkcommunity.datos.unir
import io.github.shredia.afkcommunity.datos.verdad
import io.github.shredia.afkcommunity.idiomas.tr
import kotlinx.coroutines.yield
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlin.time.Clock
import kotlin.time.ExperimentalTime

/*
 * Importar y exportar datos sin conectarse al sitio (port de navegador/importar.py).
 *
 * Archivos que descarga el sitio a mano:
 *   - afk-runs.json       lista de runs (NC y CR) con cada ronda y la ficha CRUDA del juego de cada héroe.
 *   - afk-inventory.json  captura de la cuenta ("format": "afk-classic-local-inventory").
 *   - afk-NC-<battleId>.json  una sola run, exportada desde su página.
 * Copias de la app: un .zip con la carpeta cuentas/<cuenta>/<servidor>/.
 */

const val FORMATO_INVENTARIO = "afk-classic-local-inventory"
const val FORMATO_RUNS_APP = "afk-community-runs"
const val PREFIJO_ID = "imp-"
private val PARTES_EQUIPO = mapOf(1 to "Weapon", 2 to "Head", 3 to "Body", 4 to "Feet")
private const val TID_MIN_NO_MUEBLE = 30000L
private const val CASILLAS_MUEBLES = 9
const val ARCHIVO_LISTA_GLOBAL = "sources_guardados.json"
private const val DOS_32 = 4294967296L

private fun entero(v: JsonElement?, defecto: Long? = 0) = v.entero(defecto)

// ============================================================
// Reconocer el archivo
// ============================================================

enum class TipoArchivo { RUNS, RUNS_APP, INVENTARIO, COPIA }

/**
 * Las runs de un archivo, leídas de a una (afk-runs.json pesa ~75 MB: no se arma el árbol completo).
 * Se puede recorrer varias veces (analizar y luego importar).
 */
class FuenteRuns private constructor(private val trozos: List<TrozoJson>?, private val sueltas: List<JsonObject>?) {
    val total: Int get() = trozos?.size ?: sueltas!!.size

    fun runs(): Sequence<JsonObject> =
        trozos?.asSequence()?.mapNotNull { it.parsear() as? JsonObject } ?: sueltas!!.asSequence()

    companion object {
        fun deTrozos(trozos: List<TrozoJson>) = FuenteRuns(trozos, null)
        fun deRuns(runs: List<JsonObject>) = FuenteRuns(null, runs)
    }
}

class ArchivoDetectado(val tipo: TipoArchivo?, val datos: JsonObject? = null, val runs: FuenteRuns? = null)

/** Qué es el archivo: runs, inventario, runs de la app, copia (.zip de la app) o nada reconocible. */
fun detectar(nombreArchivo: String, bytes: ByteArray?, esZip: Boolean): ArchivoDetectado {
    if (nombreArchivo.lowercase().endsWith(".zip")) return ArchivoDetectado(if (esZip) TipoArchivo.COPIA else null)
    if (bytes == null || bytes.isEmpty()) return ArchivoDetectado(null)
    val raiz = TrozoJson(bytes)
    return runCatching {
        when (raiz.primero) {
            '[' -> {
                val elementos = raiz.elementos().toList()
                val primera = elementos.firstOrNull()?.parsear() as? JsonObject
                if (primera != null && "battleId" in primera && "rounds" in primera)
                    ArchivoDetectado(TipoArchivo.RUNS, runs = FuenteRuns.deTrozos(elementos))
                else ArchivoDetectado(null)
            }
            '{' -> {
                // el inventario trae un bloque "source" enorme del que solo se usa el servidor: se poda
                val datos = raiz.podado() as JsonObject
                when {
                    datos["format"].s() == FORMATO_INVENTARIO -> ArchivoDetectado(TipoArchivo.INVENTARIO, datos)
                    datos["format"].s() == FORMATO_RUNS_APP -> ArchivoDetectado(TipoArchivo.RUNS_APP, raiz.parsear() as JsonObject)
                    // afk-NC-<battleId>.json: una sola run, exportada desde su página
                    "battleId" in datos && "rounds" in datos -> ArchivoDetectado(TipoArchivo.RUNS, runs = FuenteRuns.deRuns(listOf(raiz.parsear() as JsonObject)))
                    else -> ArchivoDetectado(null, datos)
                }
            }
            else -> ArchivoDetectado(null)
        }
    }.getOrElse { ArchivoDetectado(null) }
}

// ============================================================
// Plantillas: lo que el archivo no trae, sacado de tus datos ya descargados
// ============================================================

class Plantillas private constructor() {
    val heroeTid = HashMap<String, JsonObject>()
    val heroeId = HashMap<String, JsonObject>()
    val mascota = HashMap<String, JsonObject>()      // "tid|jobs" y "tid"
    val tagsColeccion = HashMap<String, JsonElement>()
    var refs: JsonObject = obj()

    private fun heroe(h: JsonElement?, propia: Boolean = false) {
        val o = h as? JsonObject ?: return
        if (o["tid"].esNulo()) return
        if (o["engravingNodes"].verdad() || o["tid"].py() !in heroeTid) heroeTid[o["tid"].py()] = o
        if (propia) heroeId.getOrPut(o["id"].py()) { o }
        tag(o["collection"])
    }

    private fun mascotaDe(p: JsonElement?) {
        val o = p as? JsonObject ?: return
        if (o["tid"].esNulo()) return
        val jobs = o["jobs"].a().joinToString(",") { it.py() }
        mascota.getOrPut("${o["tid"].py()}|$jobs") { o }
        mascota.getOrPut(o["tid"].py()) { o }
    }

    private fun tag(col: JsonElement?) {
        val o = col as? JsonObject ?: return
        if (!o["tid"].esNulo() && !o["tag"].esNulo()) tagsColeccion.getOrPut(o["tid"].py()) { o["tag"]!! }
    }

    companion object {
        suspend fun crear(datos: Datos, carpeta: String?): Plantillas {
            val p = Plantillas()
            val carpetas = mutableListOf<String>()
            for (cuenta in datos.almacen.listar(CARPETA_CUENTAS)) {
                val c = unir(CARPETA_CUENTAS, cuenta)
                if (!datos.almacen.esCarpeta(c)) continue
                for (s in datos.subcarpetas(c)) carpetas += unir(c, s)
            }
            for (c in carpetas.sortedBy { it != carpeta }) {
                // los id de héroe son de cada personaje: las copias solo de la carpeta destino
                val propia = carpeta != null && c == carpeta
                val indice = datos.leerObjeto(unir(c, ARCHIVO_INDICE)) ?: obj()
                if (p.refs.isEmpty() && indice["refs"].o()["gearOptions"].verdad()) p.refs = indice["refs"].o()
                for ((_, run) in indice["runs"].o()) for (r in run.o()["rounds"].objetos()) {
                    p.mascotaDe(r["pet"])
                    for (h in r["heroes"].objetos()) p.heroe(h, propia)
                }
                val estado = cargarCuentaActual(datos, c) ?: obj()
                for (h in estado["roster"].a()) p.heroe(h, propia)
                for (m in estado["mascotas_roster"].a()) p.mascotaDe(m)
                for (col in estado["colecciones"].a()) p.tag(col)
                yield()
            }
            if (carpeta != null && p.refs.isEmpty()) p.refsDeDetalle(datos, carpeta)
            return p
        }
    }

    private suspend fun refsDeDetalle(datos: Datos, carpeta: String) {
        val dir = unir(carpeta, "detalles")
        val archivos = datos.almacen.listar(dir).filter { it.endsWith(".json") }
            .map { it to (datos.almacen.modificado(unir(dir, it)) ?: 0.0) }.sortedByDescending { it.second }
        for ((n, _) in archivos.take(5)) {
            val d = datos.leerObjeto(unir(dir, n)) ?: continue
            if (d["kind"].s() == "import") continue
            for (t in d["collectionTypes"].a()) tag(t)
            if (d["gearOptions"].verdad()) {
                refs = obj("collectionTags" to d["collectionTags"].o(), "gearOptions" to d["gearOptions"])
                return
            }
        }
    }
}

// ============================================================
// Ficha cruda del juego -> formato de la app
// ============================================================

private fun coleccion(mitama: JsonElement?, vis: Visuales?, plantillas: Plantillas): JsonObject? {
    val m = mitama as? JsonObject ?: return null
    if (m["tid"].esNulo()) return null
    val col = coleccionDeFetch(m)
    val nombre = vis?.nombreColeccion(col["tid"].py())
    return obj("id" to col["id"], "tid" to col["tid"], "name" to (nombre ?: "Colección ${col["tid"].py()}"),
        "tag" to plantillas.tagsColeccion[col["tid"].py()], "level" to col["level"],
        "mythic" to col["mythic"], "affixes" to col["affixes"])
}

private fun equipo(equips: JsonElement?, job: JsonElement?, etiquetas: JsonObject, vis: Visuales?): List<JsonObject> {
    val tabla = vis?.t?.get("equipo").o()
    return equips.o().entries.sortedBy { entero(JsonPrimitive(it.key)) }.map { (claveSlot, e0) ->
        val slot = entero(JsonPrimitive(claveSlot))!!
        val e = e0.o()
        val attrs = e["attrs"].o()
        val nombre: JsonElement?
        val calidad: JsonElement?
        val estrellas: Long
        if (e["resonate_tid"].verdad()) {
            // Pieza resonada: el sitio muestra la pieza con la que resuena (sin estrellas)
            val info = tabla[e["resonate_tid"].py()].o().ifEmpty { etiquetas["Equip"].o()[e["resonate_tid"].py()].o() }
            nombre = info["name"]; calidad = info["quality"]; estrellas = 0
        } else {
            val info = etiquetas["Equip"].o()[e["tid"].py()].o().ifEmpty { tabla[e["tid"].py()].o() }
            nombre = if (e["name"].verdad()) e["name"] else info["name"]
            calidad = if (!e["quality"].esNulo()) e["quality"] else info["quality"]
            estrellas = entero(e["enhance_lv"])!!
        }
        obj("slot" to slot, "part" to (PARTES_EQUIPO[slot.toInt()] ?: slot.toString()),
            "name" to (if (nombre.verdad()) nombre else JsonPrimitive("Equip ${e["tid"].py()}")), "job" to job,
            "quality" to calidad, "stars" to estrellas, "faction" to attrs["hero_tag"], "attuned" to ("hero_tid" in attrs))
    }
}

private fun muebles(lista: JsonElement?, heroTid: Long, plantilla: JsonObject?): Pair<JsonObject, List<Long>> {
    // Cuentan las piezas de ESTE héroe (hero_tag); las demás vienen en la lista pero no ocupan casilla
    val piezas = lista.objetos().filter { (entero(it["tid"]) ?: 0) < TID_MIN_NO_MUEBLE && entero(it["hero_tag"], null) == heroTid }
    val niveles = piezas.map { entero(it["lv"])!! }
    val previo = plantilla ?: obj()
    val previasCasillas = previo["furnitureSlots"].a().map { it.entero(0)!! }
    if (previo["furniture"].o()["pieces"].entero(null) == piezas.size.toLong() &&
        previasCasillas.filter { it >= 0 }.sorted() == niveles.sorted()) {
        return previo["furniture"].o() to previasCasillas
    }
    // Sin datos previos de esta copia: se conoce cuántas piezas y su nivel, no en qué casilla está cada una
    val casillas = (niveles.sortedDescending() + List(CASILLAS_MUEBLES) { -1L }).take(CASILLAS_MUEBLES)
    return obj("pieces" to piezas.size, "level" to 0) to casillas
}

/** Ficha cruda de héroe (afk-runs / afk-inventory) -> héroe como lo guarda la app. */
fun convertirHeroe(snap: JsonObject, plantillas: Plantillas, vis: Visuales?, etiquetas: JsonObject = obj(),
                   slot: JsonElement? = null): JsonObject {
    val tid = entero(snap["tid"])!!
    val fijo = plantillas.heroeTid[tid.toString()] ?: obj()
    val tieneId = !(snap["id"].esNulo() || snap["id"].s() == "")
    val copia = if (tieneId) plantillas.heroeId[snap["id"].py()] else null
    val nodosLv = snap["totem_node_lvs"].o().entries.associate { (k, v) -> k to entero(v)!! }
    val baseNodos = fijo["engravingNodes"].objetos().associateBy { it["key"].py() }
    val nodos = (baseNodos.keys + nodosLv.keys).sortedBy { entero(JsonPrimitive(it)) }.map { k ->
        (baseNodos[k] ?: obj("key" to k, "max" to null, "stats" to emptyList<Any>())).con("level" to (nodosLv[k] ?: 0L))
    }
    val sig = snap["sig"]
    val (mueble, casillas) = muebles(snap["furnitures"], tid, copia)
    val pares = mutableListOf<Pair<String, Any?>>()
    if (slot != null) pares += "slot" to slot
    pares += listOf(
        "id" to (if (tieneId) snap["id"].py() else ""), "tid" to tid,
        "name" to (if (snap["name"].verdad()) snap["name"] else fijo["name"]),
        "imageUrl" to (if (snap["imageUrl"].verdad()) snap["imageUrl"] else fijo["imageUrl"]),
        "faction" to (if (snap["faction"].verdad()) snap["faction"] else fijo["faction"]),
        "quality" to entero(snap["quality"]),
        "sig" to (if (sig.esNulo()) null else if (sig is JsonObject) entero(sig["lv"]) else entero(sig)),
        "engraving" to nodosLv.values.sum(),
        "engravingEditable" to (fijo["engravingEditable"] ?: JsonPrimitive(nodos.isNotEmpty())),
        "engravingNodes" to nodos, "engravingMod" to fijo["engravingMod"],
        "furniture" to mueble, "furnitureSlots" to casillas,
        "job" to fijo["job"], "factionTag" to fijo["factionTag"], "hyper" to (fijo["hyper"] ?: JsonPrimitive(false)),
        "tag" to fijo["tag"],
        "collection" to coleccion(snap["mitama_unit"], vis, plantillas),
        "gear" to equipo(snap["equips"], fijo["job"], etiquetas, vis),
    )
    return obj(*pares.toTypedArray())
}

fun convertirMascota(p: JsonElement?, plantillas: Plantillas, etiquetas: JsonObject = obj(), origen: String = "run"): JsonObject {
    val m = p as? JsonObject ?: return obj()
    val tid = m["tid"].py()
    val jobs = m["job_lv"].objetos().sortedBy { entero(it["job_id"]) }.map { entero(it["lv"])!! }
    val previa = plantillas.mascota["$tid|${jobs.joinToString(",")}"] ?: obj()
    val mismaTid = plantillas.mascota[tid] ?: obj()
    val info = etiquetas["Pet"].o()[tid].o()
    return obj("from" to origen, "id" to m["id"].py(), "tid" to entero(JsonPrimitive(tid)),
        "name" to (info["name"].s()?.takeIf { it.isNotEmpty() } ?: mismaTid["name"].s()?.takeIf { it.isNotEmpty() } ?: "Pet $tid"),
        "imageUrl" to (mismaTid["imageUrl"].s()?.takeIf { it.isNotEmpty() } ?: "/game-ui/run-screen/pets/pet_$tid.webp"),
        "jobs" to jobs, "level" to previa["level"], "maxJob" to mismaTid["maxJob"])
}

// ============================================================
// Personajes y amigos
// ============================================================

/** [(carpeta, texto)] de las carpetas cuentas/<cuenta>/<servidor>/ que tienen personaje. */
suspend fun carpetasServidor(datos: Datos): List<Pair<String, String>> =
    datos.mapaPersonajes().values.toSet().sortedWith(compareBy({ nombre(it).length }, { nombre(it) })).map { c ->
        val ficha = datos.ficha(c) ?: obj()
        val n = if (ficha["name"].verdad()) ficha["name"].py() else ficha["uid"].textoO()
        c to tr("Servidor {0} · {1} · {2} runs", nombre(c), n, datos.numeroRuns(c))
    }

class Amigo(val carpeta: String, val nombre: String, val servidor: String, val runs: Int, val simulada: Boolean)

/** Los amigos de cuentas/_amigos/. */
suspend fun amigos(datos: Datos): List<Amigo> {
    val raiz = unir(CARPETA_CUENTAS, CARPETA_AMIGOS)
    return datos.almacen.listar(raiz).sorted().mapNotNull { n ->
        val c = unir(raiz, n)
        if (!datos.almacen.esCarpeta(c)) return@mapNotNull null
        val ficha = datos.ficha(c) ?: return@mapNotNull null
        Amigo(c, ficha["name"].textoO(n), ficha["svr_id"].textoO(), datos.numeroRuns(c), ficha["simulada"].verdad())
    }
}

const val SUFIJO_SIMULADA = " (simulación)"

/** Nombre de carpeta seguro: sin tildes, solo letras, números, _ y - (máximo 40). */
private fun nombreCarpeta(texto: String): String =
    texto.map { quitarTilde(it) }.joinToString("")
        .replace(Regex("[^A-Za-z0-9_-]+"), "_").trim('_').take(40).ifEmpty { "amigo" }

/** cuentas/_amigos/<nombre>[_<servidor>]/ (la crea con su ficha si no existe). */
suspend fun carpetaAmigo(datos: Datos, nombre: String, servidor: String = "", simulada: Boolean = false): String {
    var n = nombre.trim()
    val srv = servidor.trim()
    require(n.isNotEmpty()) { if (simulada) tr("Escribe un nombre para la simulación.") else tr("Escribe el nombre de tu amigo.") }
    if (simulada && !n.endsWith(SUFIJO_SIMULADA)) n += SUFIJO_SIMULADA
    for (a in amigos(datos)) if (a.nombre.lowercase() == n.lowercase() && a.servidor == srv) return a.carpeta
    val base = nombreCarpeta(n) + (if (srv.isNotEmpty()) "_${nombreCarpeta(srv)}" else "")
    val raiz = unir(CARPETA_CUENTAS, CARPETA_AMIGOS)
    var carpeta = unir(raiz, base)
    var i = 2
    while (datos.almacen.existe(carpeta)) carpeta = unir(raiz, "${base}_${i++}")
    val ficha = obj("uid" to "amigo:${nombre(carpeta)}", "name" to n, "svr_id" to srv, "amigo" to true)
    datos.escribirJson(unir(carpeta, "${nombre(carpeta)}.json"), if (simulada) ficha.con("simulada" to true) else ficha, indentado = true)
    return carpeta
}

suspend fun renombrarAmigo(datos: Datos, carpeta: String, nuevo: String) {
    val ficha = datos.ficha(carpeta) ?: return
    datos.escribirJson(unir(carpeta, "${nombre(carpeta)}.json"), ficha.con("name" to nuevo.trim()), indentado = true)
}

class PersonajeInventario(val uid: String, val servidor: String, val nivel: JsonElement?, val carpeta: String?, val nombre: String)

/** El personaje del afk-inventory.json; carpeta null si la app aún no lo conoce. */
suspend fun personajeDeInventario(datos: Datos, inv: JsonObject): PersonajeInventario {
    val cuenta = inv["account"].o()
    val uid = cuenta["id"].textoO()
    val fuente = inv["source"].o()
    val servidor = if (fuente["serverId"].verdad()) fuente["serverId"] else fuente["accountCheck"].o()["serverId"]
    require(uid.isNotEmpty() && servidor.verdad()) { tr("El archivo no dice qué personaje es (falta la UID o el servidor).") }
    val carpeta = datos.mapaPersonajes()[uid]
    val ficha = carpeta?.let { datos.ficha(it) } ?: obj()
    return PersonajeInventario(uid, servidor.py(), cuenta["level"], carpeta, ficha["name"].textoO())
}

/** Crea cuentas/local/<servidor>/ con la ficha del personaje y la devuelve (o la que ya existía). */
suspend fun registrarPersonaje(datos: Datos, uid: String, servidor: String, nombre: String?, nivel: JsonElement? = null): String {
    val srv = servidor.trim()
    val n = nombre?.trim()?.takeIf { it.isNotEmpty() } ?: "UID $uid"
    datos.mapaPersonajes()[uid]?.let { return it }
    val raiz = unir(CARPETA_CUENTAS, CARPETA_LOCAL)
    if (!datos.almacen.existe(unir(raiz, "account.json"))) {
        // fetchedAt vacío: si un día el sitio trae este mismo personaje, gana la cuenta del sitio
        datos.escribirJson(unir(raiz, "account.json"), obj("id" to CARPETA_LOCAL, "email" to null, "local" to true, "fetchedAt" to ""), indentado = true)
    }
    var carpeta = unir(raiz, srv)
    if (datos.almacen.existe(unir(carpeta, "$srv.json"))) carpeta = unir(raiz, "${srv}_$uid")
    val servidorNum: Any = srv.toLongOrNull() ?: srv
    datos.escribirJson(unir(carpeta, "${nombre(carpeta)}.json"),
        obj("uid" to uid, "name" to n, "level" to nivel, "svr_id" to servidorNum), indentado = true)
    val sinDueno = unir(CARPETA_CUENTAS, CARPETA_SIN_ASIGNAR, uid)
    if (datos.almacen.esCarpeta(sinDueno)) {
        for (hijo in datos.almacen.listar(sinDueno)) datos.mover(unir(sinDueno, hijo), unir(carpeta, hijo))
        if (datos.almacen.listar(sinDueno).isEmpty()) datos.almacen.borrar(sinDueno)
    }
    return carpeta
}

class CuentaPersonal(val carpeta: String, val texto: String, val servidores: List<Pair<String, String>>, val fecha: String, val local: Boolean)

/** Tus cuentas y sus servidores (los personajes importados primero, luego lo más reciente). */
suspend fun cuentasPersonales(datos: Datos): List<CuentaPersonal> {
    val salida = mutableListOf<CuentaPersonal>()
    for (cuenta in datos.almacen.listar(CARPETA_CUENTAS)) {
        val c = unir(CARPETA_CUENTAS, cuenta)
        val ficha = datos.leerObjeto(unir(c, "account.json"))
        if (cuenta in CARPETAS_ESPECIALES || ficha == null) continue
        val servidores = datos.subcarpetas(c).sortedWith(compareBy({ it.length }, { it })).mapNotNull { s ->
            val cs = unir(c, s)
            val pj = datos.ficha(cs) ?: return@mapNotNull null
            cs to tr("Servidor {0} · {1} · {2} runs", s, if (pj["name"].verdad()) pj["name"].py() else pj["uid"].py(), datos.numeroRuns(cs))
        }
        val fecha = ficha["fetchedAt"].textoO()
        val local = ficha["local"].verdad()
        if (local && servidores.isEmpty()) continue
        val texto = if (local) tr("Personajes importados (afk-inventory.json)")
        else tr("{0} · actualizada {1}", ficha["email"].textoO(cuenta), fecha.take(10).ifEmpty { "?" })
        salida += CuentaPersonal(c, texto, servidores, fecha, local)
    }
    return salida.sortedWith(compareBy<CuentaPersonal>({ it.local }, { it.fecha })).reversed()
}

// ============================================================
// Analizar runs antes de importarlas
// ============================================================

private class HeroeRun(val id: String, val tid: String, val prestado: Boolean)

private fun heroesDeRun(run: JsonObject): List<HeroeRun> = run["rounds"].objetos().flatMap { r ->
    r["heroes"].objetos().map { h ->
        val snap = h["snapshot"].o().ifEmpty { h }
        val hid = snap["id"]
        val prestado = (snap["borrowed"].verdad() || snap["prestado"].verdad()) && snap["source_type"].py() != "4"
        HeroeRun(if (hid.esNulo() || hid.s() == "") "" else hid.py(), snap["tid"].py(), prestado)
    }
}

const val MIN_HEROES_COINCIDEN = 5

class InfoRuns(
    val nc: Int, val otros: Int, val desde: String, val hasta: String, val una: JsonObject?,
    val conIds: Boolean, val sugerida: String? = null, val amigo: Boolean = false, val motivo: String? = null,
    val yaEstan: Int = 0, val nombre: String = "",
)

/** Lo que se puede saber del archivo antes de importarlo (cuántas runs, de qué fechas, de quién parecen). */
suspend fun analizarRuns(datos: Datos, fuente: FuenteRuns, soloNc: Boolean = true): InfoRuns {
    var nc = 0
    var una: JsonObject? = null
    val fechas = mutableListOf<String>()
    var conIds = false
    val pares = HashSet<Pair<String, String>>()
    for (r in fuente.runs()) {
        if (soloNc && !(r["mode"].esNulo() || r["mode"].s() == "NC")) continue
        nc++
        una = if (nc == 1) r else null
        if (r["playedAt"].verdad()) fechas += r["playedAt"].py()
        for (h in heroesDeRun(r)) {
            if (h.id.isNotEmpty()) {
                conIds = true
                if (!h.prestado && (h.id.toLongOrNull() ?: 0) < DOS_32) pares += h.id to h.tid
            }
        }
        yield()
    }
    fechas.sort()
    val base = InfoRuns(nc, fuente.total - nc, fechas.firstOrNull()?.take(10).orEmpty(),
        fechas.lastOrNull()?.take(10).orEmpty(), una, conIds)
    if (!conIds) return base

    val candidatas = carpetasServidor(datos).map { it.first to false } + amigos(datos).map { it.carpeta to true }
    val setFechas = fechas.toSet()
    var mejor = Triple(0, 0, null as String?)
    var mejorAmigo = false
    for ((carpeta, esAmigo) in candidatas) {
        val propias = datos.leerLista(unir(carpeta, "runs.json")).objetos()
        val enComun = propias.count { it["playedAt"].textoO() in setFechas }
        var mismoId = 0
        if (!esAmigo) {
            val roster = cargarCuentaActual(datos, carpeta)?.get("roster").objetos()
            mismoId = (pares intersect roster.map { it["id"].py() to it["tid"].py() }.toSet()).size
        }
        if (enComun > mejor.first || (enComun == mejor.first && mismoId > mejor.second)) {
            mejor = Triple(enComun, mismoId, carpeta)
            mejorAmigo = esAmigo
        }
    }
    val (enComun, mismoId, carpeta) = mejor
    if (carpeta != null && (enComun > 0 || mismoId >= MIN_HEROES_COINCIDEN)) {
        val ficha = datos.ficha(carpeta) ?: obj()
        return InfoRuns(base.nc, base.otros, base.desde, base.hasta, base.una, true, carpeta, mejorAmigo,
            if (enComun > 0) "fechas" else "heroes", enComun, ficha["name"].textoO(nombre(carpeta)))
    }
    return base
}

// ============================================================
// Importar afk-runs.json
// ============================================================

private val CAMPOS_STATS = listOf("damage", "heal", "defend", "kill", "hp_pct", "mp_pct")

private fun stats(crudo: JsonElement?): JsonObject? {
    val c = crudo as? JsonObject ?: return null
    return JsonObject(CAMPOS_STATS.filter { !c[it].esNulo() }.associateWith { JsonPrimitive(entero(c[it])) })
}

private fun statsRonda(r: JsonObject): JsonObject {
    val mascota = r["petStats"].o().values.firstOrNull()
    val jefes = r["enemyStats"].o().values.mapNotNull { stats(it) }
    val salida = LinkedHashMap<String, JsonElement>()
    if (mascota.verdad()) stats(mascota)?.let { salida["mascota"] = it }
    if (jefes.isNotEmpty()) {
        salida["jefe"] = if (jefes.size == 1) jefes[0] else obj(
            *listOf("damage", "heal", "defend", "kill").map { k -> k to jefes.sumOf { entero(it[k]) ?: 0 } }.toTypedArray(),
            "hp_pct" to jefes.maxOf { entero(it["hp_pct"]) ?: 0 })
    }
    if (r["outcome"].verdad()) salida["resultado"] = r["outcome"]!!
    return JsonObject(salida)
}

/** Agrega a un detalle ya descargado del sitio las estadísticas del archivo. Devuelve el detalle si cambió algo. */
private fun fusionarStats(detalle: JsonObject, run: JsonObject): JsonObject? {
    var cambio = false
    val rondasArchivo = run["rounds"].objetos().sortedBy { entero(it["round"]) }
    val rondas = detalle["rounds"].objetos().sortedBy { it["index"].int(0) }
    val nuevas = rondas.mapIndexed { i, rs ->
        val ra = rondasArchivo.getOrNull(i) ?: return@mapIndexed rs
        if (rs["bossId"].py() != ra["bossId"].py()) return@mapIndexed rs
        val porSlot = ra["heroes"].objetos().associateBy { entero(it["slot"]) }
        val heroes = rs["heroes"].objetos().map { h ->
            val crudo = porSlot[entero(h["slot"])]
            val st = crudo?.get("stats")?.let { stats(it) }
            if (crudo != null && crudo["stats"].verdad() && h["stats"] != st) { cambio = true; h.con("stats" to st) } else h
        }
        var ronda = rs.con("heroes" to heroes)
        val extra = statsRonda(ra)
        if (extra.isNotEmpty() && rs["estadisticas"] != extra) { ronda = ronda.con("estadisticas" to extra); cambio = true }
        ronda
    }
    return if (cambio) detalle.con("rounds" to nuevas) else null
}

class ResultadoImportar(val nuevas: Int, val actualizadas: Int = 0, val yaEstaban: Int = 0, val otrosModos: Int = 0,
                        val carpeta: String, val amigo: Boolean = false, val conEstadisticas: Int = 0, val completadas: Int = 0)

/**
 * Agrega a la carpeta las runs de NC del archivo que aún no tiene. Las que ya se descargaron del sitio (misma
 * fecha) no se tocan: solo reciben las estadísticas.
 */
suspend fun importarRuns(datos: Datos, fuente: FuenteRuns, carpeta: String, vis: Visuales?,
                         progreso: (String) -> Unit = {}): ResultadoImportar {
    val total = fuente.total
    val ficha = datos.ficha(carpeta) ?: obj()
    val esAmigo = ficha["amigo"].verdad()
    val personaje = ficha["uid"].textoO(nombre(carpeta))
    var lista = datos.leerLista(unir(carpeta, "runs.json")).objetos()
    val propias = lista.filter { it["mine"].verdad() }
    val dueno: String? = if (esAmigo) ficha["name"].s() else propias.firstOrNull { it["owner"].verdad() }?.get("owner")?.py()
    val delSitio = lista.filter { !it["id"].textoO().startsWith(PREFIJO_ID) }
    val fechas = delSitio.map { it["playedAt"]?.py() }.toSet()
    val idPorFecha = delSitio.associate { it["playedAt"]?.py() to it["id"].py() }
    val yaImportadas = lista.filter { it["id"].textoO().startsWith(PREFIJO_ID) }.map { it["id"].py() }.toSet()

    progreso(tr("Preparando datos de referencia (héroes, mascotas, colecciones)..."))
    val plantillas = Plantillas.crear(datos, carpeta)

    val nuevas = mutableListOf<JsonObject>()
    var repetidas = 0; var otrosModos = 0; var actualizadas = 0; var conStats = 0
    for ((i, run) in fuente.runs().withIndex()) {
        if (run["mode"].s() != "NC") { otrosModos++; continue }
        if (run["playedAt"]?.py() in fechas) {
            repetidas++
            // ya la tienes del sitio (con el SP de cada ronda): solo se le agregan las estadísticas
            val ruta = unir(carpeta, "detalles", "${idPorFecha[run["playedAt"]?.py()]}.json")
            val detalle = datos.leerObjeto(ruta)
            val fusionado = detalle?.let { fusionarStats(it, run) }
            if (fusionado != null) { datos.escribirJson(ruta, fusionado); conStats++ }
            continue
        }
        val rid = "$PREFIJO_ID${run["battleId"].py()}"
        val arbol = run["elderTree"].o()
        val idsPropios = sortedSetOf<String>()
        val rondas = run["rounds"].objetos().mapIndexed { k, r ->
            val heroes = r["heroes"].objetos().sortedBy { entero(it["slot"]) }.map { h ->
                var snap = h["snapshot"].o()
                if ((snap["id"].esNulo() || snap["id"].s() == "") && snap["borrowed"].verdad() && snap["source_type"].py() != "4") {
                    // la run descargada desde su página no trae el id de la copia: un mercenario recibe un id
                    // temporal (≥ 2^32) para que no se confunda con un dimensional arrendado (que es tuyo)
                    snap = snap.con("id" to DOS_32 + (entero(snap["tid"]) ?: 0))
                }
                var heroe = convertirHeroe(snap, plantillas, vis, slot = h["slot"] ?: JsonNull)
                stats(h["stats"])?.takeIf { it.isNotEmpty() }?.let { heroe = heroe.con("stats" to it) }
                val conId = !(snap["id"].esNulo() || snap["id"].s() == "")
                if (snap["source_type"].py() == "4") {
                    heroe = heroe.con("arrendado" to true)   // dimensional arrendado: es tuyo aunque venga 'borrowed'
                    if (conId) idsPropios += snap["id"].py()
                } else if (snap["borrowed"].verdad() || (entero(snap["id"]) ?: 0) >= DOS_32) {
                    heroe = heroe.con("prestado" to true)   // mercenario
                } else if (conId) {
                    idsPropios += snap["id"].py()
                }
                heroe
            }
            val mascotas = r["pets"].a()
            obj("index" to k, "bossId" to r["bossId"].py(), "recorded" to r["result"].o(),
                "pet" to (if (mascotas.isNotEmpty()) convertirMascota(mascotas[0], plantillas) else obj()),
                // afk-runs.json no lo trae: con un solo héroe especial se activa solo; con varios no se sabe
                "golden" to deducirGolden(heroes, r["golden"]).takeUnless { it.py() == SP_DESCONOCIDO },
                "estadisticas" to statsRonda(r), "outcome" to r["outcome"], "heroes" to heroes)
        }
        val detalle = obj(
            "kind" to "import", "id" to rid, "owner" to (if (esAmigo) dueno else null), "importado" to true,
            "battleId" to run["battleId"], "playedAt" to run["playedAt"], "result" to run["result"].o(),
            "rounds" to rondas, "roster" to idsPropios.map { obj("id" to it) }, "borrow" to emptyList<Any>(), "test" to emptyList<Any>(),
            "collectionTags" to plantillas.refs["collectionTags"].o(), "gearOptions" to plantillas.refs["gearOptions"].o(),
            "tree" to obj("lv" to arbol["lv"], "tags" to arbol["tag_lvs"].o().entries
                .sortedBy { entero(JsonPrimitive(it.key)) }.map { entero(it.value) }),
        )
        datos.escribirJson(unir(carpeta, "detalles", "$rid.json"), detalle)
        if (rid in yaImportadas) actualizadas++
        else nuevas += obj("id" to rid, "character" to personaje, "playedAt" to run["playedAt"], "result" to run["result"].o(),
            "owner" to dueno, "mine" to !esAmigo, "amigo" to esAmigo, "importado" to true)
        if ((i + 1) % 25 == 0) progreso(tr("   {0}/{1} runs revisadas", i + 1, total))
        yield()
    }
    if (nuevas.isNotEmpty()) {
        lista = (lista + nuevas).sortedByDescending { it["playedAt"].textoO() }
        datos.escribirJson(unir(carpeta, "runs.json"), JsonArray(lista), indentado = true)
        if (!esAmigo) agregarAListaGlobal(datos, nuevas)
    }
    return ResultadoImportar(nuevas.size, actualizadas, repetidas, otrosModos, carpeta, esAmigo, conStats)
}

private suspend fun agregarAListaGlobal(datos: Datos, nuevas: List<JsonObject>) {
    val actuales = datos.leerLista(ARCHIVO_LISTA_GLOBAL).objetos().toMutableList()
    val ids = actuales.map { it["id"].py() }.toSet()
    actuales += nuevas.filter { it["id"].py() !in ids }
    datos.escribirJson(ARCHIVO_LISTA_GLOBAL, JsonArray(actuales.sortedByDescending { it["playedAt"].textoO() }), indentado = true)
}

// ============================================================
// afk-inventory.json
// ============================================================

class ResultadoInventario(val carpeta: String, val heroes: Int, val colecciones: Int, val objetos: Int, val capturedAt: String)

/** Guarda la captura como cuenta_actual.json. Si el personaje es nuevo, lo registra en cuentas/local/<servidor>/. */
@OptIn(ExperimentalTime::class)
suspend fun importarInventario(datos: Datos, inv: JsonObject, vis: Visuales?, nombrePersonaje: String? = null,
                               progreso: (String) -> Unit = {}): ResultadoInventario {
    val info = personajeDeInventario(datos, inv)
    if (info.carpeta == null) {
        registrarPersonaje(datos, info.uid, info.servidor, nombrePersonaje, info.nivel)
        progreso(tr("Personaje nuevo registrado: {0} · servidor {1} · UID {2}",
            nombrePersonaje?.takeIf { it.isNotBlank() } ?: "UID ${info.uid}", info.servidor, info.uid))
    } else {
        val f = datos.ficha(info.carpeta) ?: obj()
        if (info.nivel.verdad() && f["level"] != info.nivel) {
            datos.escribirJson(unir(info.carpeta, "${nombre(info.carpeta)}.json"), f.con("level" to info.nivel), indentado = true)
        }
    }
    val compacto = compactarInventario(obj("data" to inv, "capturedAt" to inv["capturedAt"]))
    val uid = compacto["cuenta"].o()["id"].textoO()
    val carpeta = datos.carpetaPersonaje(datos.mapaPersonajes(), uid)
    progreso(tr("Captura del {0} · personaje {1} · servidor {2}", compacto["capturedAt"].py(), uid, nombre(carpeta)))

    progreso(tr("Preparando datos de referencia (héroes, mascotas, colecciones)..."))
    val plantillas = Plantillas.crear(datos, carpeta)
    val etiquetas = inv["labels"].o()

    val colecciones = compacto["colecciones_fetch"].objetos().map { c ->
        c.con("name" to (vis?.nombreColeccion(c["tid"].py()) ?: "Colección ${c["tid"].py()}"),
            "tag" to plantillas.tagsColeccion[c["tid"].py()])
    }
    val porId = colecciones.associateBy { it["id"].py() }
    val temporales = inv["temporaryHeroes"].objetos().map { it["id"].py() }.toSet()
    val roster = (inv["heroes"].objetos() + inv["temporaryHeroes"].objetos()).map { snap ->
        var h = convertirHeroe(snap, plantillas, vis, etiquetas)
        val col = h["collection"] as? JsonObject
        if (col != null && col["id"].py() in porId) h = h.con("collection" to porId[col["id"].py()])
        h.con("temporal" to (h["id"].py() in temporales), "arrendado" to (snap["source_type"].py() == "4"),
            "datos_run" to compacto["capturedAt"])
    }
    val equipadaEn = roster.filter { it["collection"] is JsonObject }.associate { it["collection"].o()["id"].py() to it["name"] }
    val coleccionesFinal = colecciones.map { it.con("equipada_en" to equipadaEn[it["id"].py()]) }

    var estado = compacto.sin("colecciones_fetch").con(
        "sincronizado" to Clock.System.now().toString(),
        "servidor" to nombre(carpeta),
        "roster" to roster,
        "colecciones" to coleccionesFinal,
        "mascotas_roster" to inv["pets"].objetos().map { convertirMascota(it, plantillas, etiquetas, "roster") },
        "fuente_colecciones" to "fetch",
        "fecha_run_roster" to compacto["capturedAt"],
        "importado" to true,
    )
    if (vis != null) estado = completarImagenes(estado, vis)

    val anterior = unir(carpeta, ARCHIVO_CUENTA_ACTUAL)
    datos.almacen.leerBytes(anterior)?.let { datos.almacen.escribirBytes(unir(carpeta, "cuenta_actual.anterior.json"), it) }
    datos.escribirJson(anterior, estado)
    return ResultadoInventario(carpeta, roster.size, coleccionesFinal.size, estado["objetos"].a().size, compacto["capturedAt"].textoO())
}

// ============================================================
// Copia de la app (.zip)
// ============================================================

private val NO_EXPORTAR = setOf(ARCHIVO_INDICE)   // se regenera solo

/** Guarda cuentas/<cuenta>/<servidor>/ en un .zip (rutas '<cuenta>/<servidor>/...'). */
suspend fun exportarCopia(datos: Datos, carpeta: String, zip: EscritorZip, progreso: (String) -> Unit = {}): Int {
    val raiz = padre(padre(carpeta))
    val archivos = datos.archivosDe(carpeta).filter { nombre(it) !in NO_EXPORTAR && !it.endsWith(".tmp") }.toMutableList()
    val cuentaJson = unir(padre(carpeta), "account.json")
    if (datos.almacen.existe(cuentaJson)) archivos += cuentaJson
    for ((i, f) in archivos.withIndex()) {
        val bytes = datos.almacen.leerBytes(f) ?: continue
        zip.agregar(f.removePrefix("$raiz/"), bytes)
        if ((i + 1) % 100 == 0) { progreso(tr("   {0}/{1} archivos", i + 1, archivos.size)); yield() }
    }
    return archivos.size
}

/** [(cuenta, servidor)] que trae el .zip. Lanza IllegalArgumentException si tiene rutas no válidas. */
fun contenidoCopia(zip: LectorZip): List<Pair<String, String>> {
    val carpetas = sortedSetOf<String>()
    for (n in zip.nombres) {
        val partes = n.split("/").filter { it.isNotEmpty() }
        val esCuenta = partes.size == 2 && partes[1] == "account.json"
        require(!(n.startsWith("/") || n.startsWith("\\") || ".." in partes || ":" in n || "\\" in n ||
            (partes.size < 3 && !esCuenta && !n.endsWith("/")))) { tr("El .zip no es una copia de la app ({0}).", n) }
        if (!esCuenta && partes.size >= 2) carpetas += "${partes[0]}/${partes[1]}"
    }
    require(carpetas.isNotEmpty()) { tr("El .zip no es una copia de la app.") }
    return carpetas.map { it.substringBefore('/') to it.substringAfter('/') }
}

private fun jsonZip(zip: LectorZip, n: String): JsonElement? = leerJsonTexto(zip.leer(n)?.decodeToString())

class InfoCopia(val carpetas: List<Pair<String, String>>, val nombre: String, val servidor: String, val uid: String,
                val runs: Int, val amigo: Boolean, val mio: Boolean)

/** Qué trae el .zip, para decidir cómo importarlo. */
suspend fun infoCopia(datos: Datos, zip: LectorZip): InfoCopia {
    val carpetas = contenidoCopia(zip)
    if (carpetas.size != 1) return InfoCopia(carpetas, "", "", "", 0, false, false)
    val (cuenta, servidor) = carpetas[0]
    val ficha = jsonZip(zip, "$cuenta/$servidor/$servidor.json").o()
    val runs = jsonZip(zip, "$cuenta/$servidor/runs.json")
    val uid = ficha["uid"].textoO()
    val amigo = ficha["amigo"].verdad() || cuenta == CARPETA_AMIGOS
    return InfoCopia(carpetas, ficha["name"].textoO(), ficha["svr_id"].textoO().ifEmpty { if (servidor.all { it.isDigit() }) servidor else "" },
        uid, (runs as? JsonArray)?.size ?: 0, amigo, uid.isNotEmpty() && !amigo && uid in datos.mapaPersonajes())
}

/**
 * Importa el .zip de otro jugador como amigo. Solo se copian sus runs (runs.json y detalles/); si ya tenías ese
 * amigo, se agregan las runs nuevas.
 */
suspend fun importarCopiaDeAmigo(datos: Datos, zip: LectorZip, nombreAmigo: String, servidor: String = "",
                                 progreso: (String) -> Unit = {}): ResultadoImportar {
    val carpetas = contenidoCopia(zip)
    require(carpetas.size == 1) { tr("La copia trae varios personajes: pídele a tu amigo que exporte uno solo.") }
    val (cuenta, srv) = carpetas[0]
    val prefijo = "$cuenta/$srv/"
    val carpeta = carpetaAmigo(datos, nombreAmigo, servidor)
    val ficha = datos.ficha(carpeta) ?: obj()
    val personaje = ficha["uid"].textoO(nombre(carpeta))
    val dueno = ficha["name"].textoO(nombreAmigo)
    val runs = jsonZip(zip, prefijo + "runs.json").objetos()
    val detalles = zip.nombres.filter { it.startsWith(prefijo + "detalles/") && it.endsWith(".json") && it.count { c -> c == '/' } == 3 }
    for ((i, n) in detalles.withIndex()) {
        val detalle = jsonZip(zip, n) as? JsonObject
        if (detalle != null) datos.escribirJson(unir(carpeta, "detalles", nombre(n)), detalle.con("owner" to dueno))
        if ((i + 1) % 100 == 0) { progreso(tr("   {0}/{1} runs", i + 1, detalles.size)); yield() }
    }
    var lista = datos.leerLista(unir(carpeta, "runs.json")).objetos()
    val previas = lista.map { it["id"].py() }.toSet()
    val nuevas = runs.filter { it["id"].py() !in previas }
        .map { it.con("character" to personaje, "owner" to dueno, "mine" to false, "amigo" to true) }
    if (nuevas.isNotEmpty()) {
        lista = (lista + nuevas).sortedByDescending { it["playedAt"].textoO() }
        datos.escribirJson(unir(carpeta, "runs.json"), JsonArray(lista), indentado = true)
    }
    return ResultadoImportar(nuevas.size, yaEstaban = runs.size - nuevas.size, carpeta = carpeta, amigo = true)
}

/** Restaura tu propia copia en cuentas/ (reemplaza los archivos con el mismo nombre). */
suspend fun importarCopia(datos: Datos, zip: LectorZip, progreso: (String) -> Unit = {}): Int {
    val carpetas = contenidoCopia(zip)   // valida las rutas antes de escribir nada
    for ((cuenta, srv) in carpetas) {
        val uidZip = jsonZip(zip, "$cuenta/$srv/$srv.json").o()["uid"].textoO()
        val uidAqui = datos.ficha(unir(CARPETA_CUENTAS, cuenta, srv))?.get("uid").textoO()
        require(uidZip.isEmpty() || uidAqui.isEmpty() || uidZip == uidAqui) {
            tr("La copia es de otro personaje y reemplazaría al que tienes en {0}/{1}. Si es de un amigo, impórtala como «De un amigo».", cuenta, srv)
        }
    }
    val nombres = zip.nombres.filter { !it.endsWith("/") }
    for ((i, n) in nombres.withIndex()) {
        val salida = unir(CARPETA_CUENTAS, n)
        if (nombre(salida) == "account.json" && datos.almacen.existe(salida)) continue
        zip.leer(n)?.let { datos.almacen.escribirBytes(salida, it) }
        if ((i + 1) % 100 == 0) { progreso(tr("   {0}/{1} archivos", i + 1, nombres.size)); yield() }
    }
    return nombres.size
}

// ============================================================
// Runs compartidas (.json de versiones anteriores, con el SP de cada ronda y las estadísticas)
// ============================================================

suspend fun importarRunsApp(datos: Datos, contenido: JsonObject, carpeta: String, progreso: (String) -> Unit = {}): ResultadoImportar {
    val ficha = datos.ficha(carpeta) ?: obj()
    val esAmigo = ficha["amigo"].verdad()
    val personaje = ficha["uid"].textoO(nombre(carpeta))
    var lista = datos.leerLista(unir(carpeta, "runs.json")).objetos()
    val porFecha = lista.associate { it["playedAt"]?.py() to it["id"].py() }
    val dueno = if (esAmigo) ficha["name"].s() else null
    val nuevas = mutableListOf<JsonObject>()
    var completadas = 0
    val runs = contenido["runs"].objetos()
    for ((i, run) in runs.withIndex()) {
        val existente = porFecha[run["playedAt"]?.py()]
        if (existente != null) {
            val ruta = unir(carpeta, "detalles", "$existente.json")
            val completo = datos.leerObjeto(ruta)?.let { completarDesde(it, run) }
            if (completo != null) { datos.escribirJson(ruta, completo); completadas++ }
            continue
        }
        val id0 = run["id"].py()
        val rid = if (id0.startsWith(PREFIJO_ID)) id0 else "$PREFIJO_ID$id0"
        val detalle = run.con("id" to rid, "kind" to "import", "importado" to true, "owner" to dueno).sin("_firmas")
        datos.escribirJson(unir(carpeta, "detalles", "$rid.json"), detalle)
        nuevas += obj("id" to rid, "character" to personaje, "playedAt" to run["playedAt"], "result" to run["result"].o(),
            "owner" to dueno, "mine" to !esAmigo, "amigo" to esAmigo, "importado" to true)
        if ((i + 1) % 50 == 0) { progreso(tr("   {0}/{1} runs revisadas", i + 1, runs.size)); yield() }
    }
    if (nuevas.isNotEmpty()) {
        lista = (lista + nuevas).sortedByDescending { it["playedAt"].textoO() }
        datos.escribirJson(unir(carpeta, "runs.json"), JsonArray(lista), indentado = true)
        if (!esAmigo) agregarAListaGlobal(datos, nuevas)
    }
    return ResultadoImportar(nuevas.size, yaEstaban = runs.size - nuevas.size, carpeta = carpeta, amigo = esAmigo, completadas = completadas)
}

/** Copia a un detalle que ya tienes el SP (si no lo sabías) y las estadísticas de la misma run. null si nada cambió. */
private fun completarDesde(detalle: JsonObject, run: JsonObject): JsonObject? {
    var cambio = false
    val otras = run["rounds"].objetos().sortedBy { it["index"].int(0) }
    val rondas = detalle["rounds"].objetos().sortedBy { it["index"].int(0) }.mapIndexed { i, rs0 ->
        val ro = otras.getOrNull(i) ?: return@mapIndexed rs0
        var rs = rs0
        if (rs["bossId"].py() != ro["bossId"].py()) return@mapIndexed rs
        val desconocido = { g: JsonElement? -> g.esNulo() || g.s() == SP_DESCONOCIDO }
        if (desconocido(rs["golden"]) && !desconocido(ro["golden"])) { rs = rs.con("golden" to ro["golden"]); cambio = true }
        if (ro["estadisticas"].verdad() && !rs["estadisticas"].verdad()) { rs = rs.con("estadisticas" to ro["estadisticas"]); cambio = true }
        val porSlot = ro["heroes"].objetos().associateBy { it["slot"].py() }
        rs.con("heroes" to rs["heroes"].objetos().map { h ->
            val otro = porSlot[h["slot"].py()]
            if (otro != null && otro["stats"].verdad() && !h["stats"].verdad()) { cambio = true; h.con("stats" to otro["stats"]) } else h
        })
    }
    return if (cambio) detalle.con("rounds" to rondas) else null
}

/** Borra un amigo (su carpeta completa). */
suspend fun borrarAmigo(datos: Datos, carpeta: String) {
    require(padre(carpeta).endsWith(CARPETA_AMIGOS)) { "No es una carpeta de amigo" }
    datos.almacen.borrar(carpeta)
}
