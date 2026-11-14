package io.github.shredia.afkcommunity.logica

import io.github.shredia.afkcommunity.datos.Datos
import io.github.shredia.afkcommunity.datos.a
import io.github.shredia.afkcommunity.datos.con
import io.github.shredia.afkcommunity.datos.entero
import io.github.shredia.afkcommunity.datos.esNulo
import io.github.shredia.afkcommunity.datos.int
import io.github.shredia.afkcommunity.datos.o
import io.github.shredia.afkcommunity.datos.obj
import io.github.shredia.afkcommunity.datos.objetos
import io.github.shredia.afkcommunity.datos.py
import io.github.shredia.afkcommunity.datos.textoO
import io.github.shredia.afkcommunity.datos.unir
import io.github.shredia.afkcommunity.datos.verdad
import io.github.shredia.afkcommunity.idiomas.tr
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlin.time.Clock
import kotlin.time.ExperimentalTime
import kotlin.time.Instant

/*
 * Estado actual de la cuenta (port de navegador/cuenta.py, sin la parte que se conecta al sitio).
 * Se guarda en cuentas/<cuenta>/<servidor>/cuenta_actual.json
 */

const val ARCHIVO_CUENTA_ACTUAL = "cuenta_actual.json"

suspend fun cargarCuentaActual(datos: Datos, carpeta: String): JsonObject? =
    datos.leerObjeto(unir(carpeta, ARCHIVO_CUENTA_ACTUAL))

/** Momento de un texto ISO ("2026-10-06T23:28:38.000Z" o con "+00:00"), o null. */
@OptIn(ExperimentalTime::class)
fun leerFecha(iso: String?): Instant? {
    if (iso.isNullOrBlank()) return null
    val t = iso.trim().replace(" ", "T")
    return runCatching { Instant.parse(t) }.getOrNull()
        ?: runCatching { Instant.parse(t + "Z") }.getOrNull()
}

/** 'hace 3 h', 'hace 2 días'... */
@OptIn(ExperimentalTime::class)
fun haceCuanto(iso: String?): String {
    if (iso.isNullOrEmpty()) return tr("nunca")
    val momento = leerFecha(iso) ?: return iso
    val segundos = (Clock.System.now() - momento).inWholeSeconds
    if (segundos < 90) return tr("hace un momento")
    if (segundos < 3600) return tr("hace {0} min", segundos / 60)
    if (segundos < 86400) return tr("hace {0} h", segundos / 3600)
    val dias = segundos / 86400
    return if (dias != 1L) tr("hace {0} días", dias) else tr("hace 1 día")
}

// ============================================================
// Compactar /api/inventory (afk-inventory.json trae lo mismo)
// ============================================================

private fun etiqueta(labels: JsonObject, tabla: String, ident: JsonElement?): JsonObject = labels[tabla].o()[ident.py()].o()

/** De la captura del inventario deja solo lo que la app muestra. inv = {"data": ..., "capturedAt": ...} */
fun compactarInventario(inv: JsonObject): JsonObject {
    val datos = inv["data"].o()
    val labels = datos["labels"].o()

    fun objeto(ident: JsonElement?, cantidad: JsonElement?, tabla: String = "Item"): JsonObject {
        val e = etiqueta(labels, tabla, ident)
        return obj(
            "id" to ident, "cantidad" to cantidad,
            "nombre" to e["name"].textoO("$tabla ${ident.py()}"),
            "categoria" to e["category"].textoO(), "calidad" to e["quality"],
            "descripcion" to e["description"].textoO(), "imageUrl" to e["imageUrl"],
        )
    }

    val monedas = datos["currencies"].o()
    val listaMonedas = mutableListOf<JsonObject>()
    if (!monedas["gold"].esNulo()) listaMonedas += obj("id" to "gold", "nombre" to "Oro", "cantidad" to monedas["gold"], "imageUrl" to null)
    if (!monedas["diamonds"].esNulo()) listaMonedas += obj("id" to "diamonds", "nombre" to "Diamantes", "cantidad" to monedas["diamonds"], "imageUrl" to null)
    for (m in monedas["other"].objetos()) listaMonedas += objeto(m["type"], m["cnt"])

    val equipo = datos["equipmentInventory"].objetos().map { g ->
        val e = etiqueta(labels, "Equip", g["tid"])
        obj("id" to g["id"], "tid" to g["tid"], "cantidad" to g["amount"], "estrellas" to g["enhance_lv"],
            "faccion" to g["attrs"].o()["hero_tag"], "nombre" to e["name"].textoO("Equipo ${g["tid"].py()}"),
            "categoria" to e["category"].textoO(), "calidad" to e["quality"], "imageUrl" to e["imageUrl"])
    }
    val mascotas = datos["pets"].objetos().map { p ->
        val e = etiqueta(labels, "Pet", p["tid"])
        obj("id" to p["id"], "tid" to p["tid"], "nombre" to e["name"].textoO("Mascota ${p["tid"].py()}"),
            "nivel" to p["pg_lv"], "trabajos" to p["job_lv"].objetos().map { it["lv"] }, "imageUrl" to e["imageUrl"])
    }
    val artefactos = datos["artifacts"].objetos().map { a ->
        val e = etiqueta(labels, "Artifact", a["tid"])
        obj("id" to a["id"], "tid" to a["tid"], "despertar" to a["awaken_lv"],
            "nombre" to e["name"].textoO("Artefacto ${a["tid"].py()}"), "imageUrl" to e["imageUrl"],
            "descripcion" to e["description"].textoO())
    }
    val temporales = datos["temporaryHeroes"].objetos()
    val heroes = datos["heroes"].objetos()
    return obj(
        "capturedAt" to (if (inv["capturedAt"].verdad()) inv["capturedAt"] else datos["capturedAt"]),
        "cuenta" to datos["account"].o(),
        "arbol" to datos["elderTree"].o(),
        "monedas" to listaMonedas,
        "objetos" to datos["items"].objetos().map { objeto(it["id"], it["amount"]) },
        "equipo_reserva" to equipo,
        "mascotas" to mascotas,
        "artefactos" to artefactos,
        "heroes_temporales" to temporales.map { it["id"].py() },
        // dimensionales arrendados (source_type 4): son tuyos, los subes tú
        "heroes_arrendados" to temporales.filter { it["source_type"].py() in setOf("4", "None") }.map { it["id"].py() },
        "heroes_basicos" to heroes.map {
            obj("id" to it["id"].py(), "tid" to it["tid"], "nivel" to it["level"], "calidad" to it["quality"],
                "source_type" to it["source_type"], "nombre" to it["name"])
        },
        "copias_base" to datos["baseHeroCopies"].objetos().map {
            obj("id" to it["id"].py(), "tid" to it["tid"], "calidad" to it["quality"], "nombre" to it["name"],
                "imageUrl" to it["imageUrl"], "faccion" to it["faction"], "clase" to it["class"])
        },
        "cobertura" to datos["coverage"].o(),
        "colecciones_fetch" to datos["collections"].objetos().map { coleccionDeFetch(it) },
        "heroes_fetch" to JsonObject((heroes + temporales).associate {
            it["id"].py() to obj(
                "coleccion" to it["mitama_unit"].o()["id"].textoO().ifEmpty { null },
                "calidad" to it["quality"], "nombre" to it["name"], "tid" to it["tid"])
        }),
    )
}

/** Colección del inventario en el mismo formato que las de NC (id, tid, level, mythic, affixes). */
fun coleccionDeFetch(c: JsonObject): JsonObject {
    val afijos = c["slot_affixs"].objetos().sortedBy { it["slot"].int(0) }.mapNotNull { ranura ->
        val a = ranura["affix"].o()
        if (a["nature"].esNulo()) null else obj("nature" to a["nature"].int(0), "quality" to a["quality"].int(0))
    }
    return obj("id" to c["id"].py(), "tid" to c["tid"].int(0), "level" to c["level"].int(0),
        "mythic" to afijos.count { it["quality"].int(0) >= 5 }, "affixes" to afijos, "locked" to c["locked"].verdad())
}

/** Mascotas sin imagen en el inventario: usar la de las tablas del sitio. */
fun completarImagenes(estado: JsonObject, vis: Visuales?): JsonObject {
    val mascotasSitio = vis?.t?.get("mascotas").o()
    return estado.con("mascotas" to estado["mascotas"].objetos().map { p ->
        if (p["imageUrl"].verdad()) p
        else {
            val info = mascotasSitio[p["tid"].py()].o()
            p.con("imageUrl" to (if (info["high"].verdad()) info["high"] else info["low"] ?: JsonNull))
        }
    })
}

// ============================================================
// Héroes que tienes (desarrollados + copias base)
// ============================================================

/** Minúsculas y sin tildes (para buscar por nombre). */
fun normalizar(texto: String?): String {
    val t = (texto ?: "").lowercase()
    val sb = StringBuilder()
    for (ch in t) sb.append(SIN_TILDE[ch] ?: ch)
    return sb.toString().trim()
}

/** La letra sin tilde, conservando mayúsculas: 'Á' -> 'A', 'ñ' -> 'n'. */
fun quitarTilde(ch: Char): Char {
    val base = SIN_TILDE[ch.lowercaseChar()] ?: return ch
    return if (ch.isUpperCase()) base.uppercaseChar() else base
}

private val SIN_TILDE: Map<Char, Char> = buildMap {
    val con = "áàäâãåéèëêíìïîóòöôõúùüûñçýÿ"
    val sin = "aaaaaaeeeeiiiiooooouuuuncyy"
    for (i in con.indices) put(con[i], sin[i])
}

fun esArrendadoCuenta(h: JsonObject, estado: JsonObject?): Boolean {
    if (h["arrendado"].verdad()) return true
    return h["temporal"].verdad() && "heroes_arrendados" !in (estado ?: obj())
}

/**
 * Todos tus héroes por nombre (y por nombre corto antes de " - "): los desarrollados y los que solo tienes como
 * copia base. Cada entrada trae además calidad_max, copias (calidades) y solo_copias.
 */
fun indiceHeroes(estado: JsonObject?): Map<String, JsonObject> {
    val e = estado ?: obj()
    val copiasPorTid = LinkedHashMap<String, MutableList<JsonObject>>()
    for (c in e["copias_base"].objetos()) copiasPorTid.getOrPut(c["tid"].py()) { mutableListOf() }.add(c)
    val indice = LinkedHashMap<String, JsonObject>()
    fun registrar(heroe: JsonObject) {
        val nombre = heroe["name"].textoO()
        for (n in listOf(nombre, nombre.split(" - ")[0])) if (n.isNotEmpty()) indice.getOrPut(normalizar(n)) { heroe }
    }
    val vistos = HashSet<String>()
    for (h in e["roster"].objetos()) {
        if (h["temporal"].verdad() && !esArrendadoCuenta(h, e)) continue
        val copias = copiasPorTid[h["tid"].py()].orEmpty()
        val q = (listOf(h["quality"].int(0)) + copias.map { it["calidad"].int(0) }).max()
        registrar(h.con("calidad_max" to q, "copias" to copias.map { it["calidad"].int(0) }.sortedDescending(),
            "solo_copias" to false))
        vistos += h["tid"].py()
    }
    for ((tid, copias) in copiasPorTid) {
        if (tid in vistos || !copias[0]["nombre"].verdad()) continue
        val calidades = copias.map { it["calidad"].int(0) }.sortedDescending()
        registrar(obj("name" to copias[0]["nombre"], "tid" to tid, "quality" to calidades[0], "calidad_max" to calidades[0],
            "imageUrl" to copias[0]["imageUrl"], "faction" to copias[0]["faccion"], "copias" to calidades,
            "solo_copias" to true))
    }
    return indice
}

fun buscarHeroe(indice: Map<String, JsonObject>, vararg nombres: String?): JsonObject? {
    for (n in nombres) {
        if (n.isNullOrEmpty()) continue
        for (clave in listOf(normalizar(n), normalizar(n.split(" - ")[0]))) indice[clave]?.let { return it }
    }
    return null
}

// ============================================================
// Cruce con NC
// ============================================================

class UsoNc(val equipos: Int, val porJefe: Map<String, Pair<Double, Int>>)

/** Cómo se usó un héroe (por tid) o una colección (por id) en tus runs de NC. */
fun usoEnNc(comps: List<Composicion>, tid: String? = null, coleccionId: String? = null, soloPropios: Boolean = true): UsoNc {
    val porJefe = LinkedHashMap<String, Pair<Double, Int>>()
    var total = 0
    for (c in comps) {
        if (!c.derrotado || c.tiempo <= 0) continue
        val origenes = c.heroOrigenes.ifEmpty { List(c.heroes.size) { PROPIO } }
        for ((h, origen) in c.heroes.zip(origenes)) {
            if (soloPropios && origen != PROPIO) continue
            if (tid != null && h["tid"].py() != tid) continue
            if (coleccionId != null && h["collection"].o()["id"].py() != coleccionId) continue
            total++
            val (mejor, usos) = porJefe[c.bossId] ?: (Double.POSITIVE_INFINITY to 0)
            porJefe[c.bossId] = minOf(mejor, c.tiempo) to usos + 1
            break
        }
    }
    return UsoNc(total, porJefe)
}
