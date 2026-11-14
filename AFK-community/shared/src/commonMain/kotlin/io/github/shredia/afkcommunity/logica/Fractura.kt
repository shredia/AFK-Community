package io.github.shredia.afkcommunity.logica

import io.github.shredia.afkcommunity.datos.Datos
import io.github.shredia.afkcommunity.datos.entero
import io.github.shredia.afkcommunity.datos.esNulo
import io.github.shredia.afkcommunity.datos.int
import io.github.shredia.afkcommunity.datos.o
import io.github.shredia.afkcommunity.datos.objetos
import io.github.shredia.afkcommunity.datos.obj
import io.github.shredia.afkcommunity.datos.py
import io.github.shredia.afkcommunity.datos.real
import io.github.shredia.afkcommunity.datos.s
import io.github.shredia.afkcommunity.datos.textoO
import io.github.shredia.afkcommunity.datos.unir
import kotlinx.datetime.DatePeriod
import kotlinx.datetime.DayOfWeek
import kotlinx.datetime.LocalDate
import kotlinx.datetime.TimeZone
import kotlinx.datetime.plus
import kotlinx.datetime.todayIn
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlin.time.Clock
import kotlin.time.ExperimentalTime

/*
 * Fractura temporal: planificador de recursos (port de navegador/fractura.py, sin la importación de Excel: D5).
 *
 * Datos base (iguales para todos):  datos/fractura_temporal.json (o recursos/fractura_temporal_base.json)
 *   pisos:   [{"piso": 5, "recompensas": {"Oro (M)": 10, ...}}]   (incluye Medallas y Cofre 1/2/3)
 *   cofres:  {"Cofre 1": {"Grabados verdes": 150, ...}}             (cada cofre = elegir UNA opción)
 *   tiendas: [{"nombre": "Tienda 100", "piso": 100, "objetos": [{"objeto", "maximo", "precio", "unidades"}]}]
 *   bolsa:   {recurso: id del objeto en tu bolsa}   (vínculos que se pueden cambiar)
 * Tu avance (por personaje): cuentas/<acc>/<srv>/fractura_temporal.json
 *   piso, meta, cofres (ahora / planeado), cofres_gastados, compras (hechas / planeadas), medallas_juego
 */

const val ARCHIVO_BASE_FRACTURA = "datos/fractura_temporal.json"
const val ARCHIVO_ESTADO_FRACTURA = "fractura_temporal.json"
val COLUMNAS_ESPECIALES = listOf("Medallas", "Cofre 1", "Cofre 2", "Cofre 3")
val EN_INVENTARIO = linkedMapOf("Emblema primordial" to 82, "Emblema amplificador" to 83, "Esencia retorcida" to 122,
    "Medallas" to 10000028)

// ---------------- guardar / cargar ----------------

/** La base guardada en la carpeta de datos, o null (entonces se usa la que viene con la app). */
suspend fun cargarBaseFractura(datos: Datos): JsonObject? = datos.leerObjeto(ARCHIVO_BASE_FRACTURA)

suspend fun guardarBaseFractura(datos: Datos, base: JsonObject) = datos.escribirJson(ARCHIVO_BASE_FRACTURA, base, indentado = true)

suspend fun cargarEstadoFractura(datos: Datos, carpeta: String): JsonObject =
    datos.leerObjeto(unir(carpeta, ARCHIVO_ESTADO_FRACTURA)) ?: obj("piso" to 0, "cofres" to obj(), "compras" to obj())

suspend fun guardarEstadoFractura(datos: Datos, carpeta: String, estado: JsonObject) =
    datos.escribirJson(unir(carpeta, ARCHIVO_ESTADO_FRACTURA), estado, indentado = true)

fun pisosValidos(base: JsonObject): List<Int> = base["pisos"].objetos().map { it["piso"].int() }

/** Fecha del próximo viernes (hoy si hoy es viernes). */
@OptIn(ExperimentalTime::class)
fun proximoViernes(hoy: LocalDate = Clock.System.todayIn(TimeZone.currentSystemDefault())): LocalDate {
    val dias = (DayOfWeek.FRIDAY.ordinal - hoy.dayOfWeek.ordinal + 7) % 7
    return hoy.plus(DatePeriod(days = dias))
}

// ---------------- cálculo ----------------

/** Las cuentas de un recurso. Los números pueden tener decimales ("Oro (M)"). */
class Recurso {
    var pisosObtenido = 0.0; var pisosFaltante = 0.0
    var tiendaComprado = 0.0; var tiendaPlaneado = 0.0; var tiendaPendiente = 0.0
    var cofresAhora = 0.0; var cofresPlaneado = 0.0; var hastaMeta = 0.0
    var conseguido = 0.0; var aunObtenible = 0.0; var planMeta = 0.0
    var bolsa: Double? = null; var tendras: Double? = null; var tendrasFinal: Double? = null
}

class EstadoCofre(val disponibles: Int, val restantes: Int, val usadosAhora: Int, val gastados: Int,
                  val usadosPlaneados: Int, val hastaMeta: Int) {
    val total get() = disponibles + restantes
    val libres get() = disponibles - usadosAhora - gastados
}

class Medallas(val ganadas: Long, val porGanar: Long, val gastadas: Long, val planeadas: Long, val hastaMeta: Long) {
    val saldo get() = ganadas - gastadas
    val saldoFinal get() = ganadas + porGanar - gastadas - planeadas
    /** El plan se calcula hasta la meta (los pisos que vas a subir), no hasta el final de la Fractura. */
    val saldoMeta get() = saldo + hastaMeta - planeadas
}

class Meta(val piso: Int, val desde: Int, val recompensas: Map<String, Double>)

class CalculoFractura(val recursos: Map<String, Recurso>, val cofres: Map<String, EstadoCofre>, val medallas: Medallas,
                      val avisos: List<String>, val siguiente: JsonObject?, val piso: Int, val meta: Meta?)

private fun num(e: kotlinx.serialization.json.JsonElement?): Double = e.real() ?: 0.0

/** Lo que muestra la pantalla (calcular de Python). bolsa: {recurso: cantidad} de tu inventario. */
fun calcularFractura(base: JsonObject, estado: JsonObject, bolsa: Map<String, Double?> = emptyMap()): CalculoFractura {
    val piso = estado["piso"].int(0)
    val meta = estado["meta"].int(0)
    val recursos = LinkedHashMap<String, Recurso>()
    fun r(nombre: String) = recursos.getOrPut(nombre) { Recurso() }

    val especiales = COLUMNAS_ESPECIALES.associateWith { doubleArrayOf(0.0, 0.0) }
    val enMeta = LinkedHashMap<String, Double>()
    for (p in base["pisos"].objetos()) {
        val n = p["piso"].int()
        val logrado = n <= piso
        val haciaMeta = n in (piso + 1)..meta
        for ((nombre, v) in p["recompensas"].o()) {
            val cant = num(v)
            if (haciaMeta) enMeta[nombre] = (enMeta[nombre] ?: 0.0) + cant
            val esp = especiales[nombre]
            if (esp != null) { esp[if (logrado) 0 else 1] += cant; continue }
            if (logrado) r(nombre).pisosObtenido += cant else r(nombre).pisosFaltante += cant
            if (haciaMeta) r(nombre).hastaMeta += cant
        }
    }

    val avisos = mutableListOf<String>()
    val cofres = LinkedHashMap<String, EstadoCofre>()
    for ((nombre, opcionesE) in base["cofres"].o()) {
        val opciones = opcionesE.o()
        val esp = especiales[nombre] ?: doubleArrayOf(0.0, 0.0)
        val disp = esp[0].toInt(); val rest = esp[1].toInt()
        val elegidos = estado["cofres"].o()[nombre].o()
        val gastados = estado["cofres_gastados"].o()[nombre].int(0)
        val usadosA = elegidos.values.sumOf { it.o()["ahora"].int(0) }
        val usadosP = elegidos.values.sumOf { it.o()["planeado"].int(0) }
        for ((op, e) in elegidos) {
            val porCofre = num(opciones[op])
            r(op).cofresAhora += porCofre * e.o()["ahora"].int(0)
            r(op).cofresPlaneado += porCofre * e.o()["planeado"].int(0)
        }
        cofres[nombre] = EstadoCofre(disp, rest, usadosA, gastados, usadosP, (enMeta[nombre] ?: 0.0).toInt())
        if (usadosA + gastados > disp) avisos += "$nombre: elegiste $usadosA y marcaste $gastados como gastados, pero solo tienes $disp."
        if (usadosP > rest) avisos += "$nombre: planeaste $usadosP pero solo quedan $rest por conseguir."
    }

    var gastadas = 0L
    var planeadas = 0L
    for (t in base["tiendas"].objetos()) {
        for ((i, o) in t["objetos"].objetos().withIndex()) {
            val c = estado["compras"].o()["${t["nombre"].py()}|$i"].o()
            val hechas = c["hechas"].int(0); val plan = c["planeadas"].int(0)
            val precio = o["precio"].entero(0)!!; val unidades = num(o["unidades"]); val maximo = o["maximo"].int(0)
            gastadas += hechas * precio
            planeadas += plan * precio
            val x = r(o["objeto"].py())
            x.tiendaComprado += hechas * unidades
            x.tiendaPlaneado += plan * unidades
            x.tiendaPendiente += maxOf(0, maximo - hechas - plan) * unidades
            if (hechas + plan > maximo) avisos += "${t["nombre"].py()} · ${o["objeto"].py()}: ${hechas + plan} compras, el máximo es $maximo."
        }
    }

    val m = especiales.getValue("Medallas")
    val medallas = Medallas(m[0].toLong(), m[1].toLong(), gastadas, planeadas, (enMeta["Medallas"] ?: 0.0).toLong())
    val juego = estado["medallas_juego"]
    if (!juego.esNulo() && juego is JsonPrimitive && !juego.isString && juego.entero(null) != null && juego.entero(null) != medallas.saldo) {
        val j = juego.entero(null)!!
        val d = medallas.saldo - j
        avisos += "El juego muestra $j medallas y el cálculo da ${medallas.saldo} (diferencia ${if (d >= 0) "+" else ""}$d): revisa el piso o las compras marcadas."
    }
    if (medallas.saldo < 0) avisos += "Gastaste $gastadas medallas pero solo has ganado ${medallas.ganadas}."
    if (medallas.saldoFinal < 0) avisos += "Lo planeado cuesta ${-medallas.saldoFinal} medallas más de las que darán los pisos."

    for (nombre in bolsa.keys) if (nombre !in COLUMNAS_ESPECIALES) r(nombre)
    for ((nombre, x) in recursos) {
        x.conseguido = x.pisosObtenido + x.tiendaComprado + x.cofresAhora
        x.aunObtenible = x.pisosFaltante + x.tiendaPlaneado + x.cofresPlaneado
        x.bolsa = bolsa[nombre]
        x.planMeta = x.hastaMeta + x.tiendaPlaneado + x.cofresPlaneado
        x.tendras = x.bolsa?.let { it + x.planMeta }
        x.tendrasFinal = x.bolsa?.let { it + x.aunObtenible }
    }
    val siguiente = base["pisos"].objetos().firstOrNull { it["piso"].int() > piso }
    return CalculoFractura(recursos, cofres, medallas, avisos, siguiente, piso,
        if (meta > piso) Meta(meta, piso, enMeta) else null)
}

// ---------------- tu bolsa (inventario de la cuenta) ----------------

/** {recurso: id de objeto/moneda en la bolsa}. "-" = sin vínculo. */
fun vinculos(base: JsonObject?): Map<String, String> {
    val salida = LinkedHashMap<String, String>()
    for ((k, v) in EN_INVENTARIO) salida[k] = v.toString()
    for ((k, v) in base?.get("bolsa").o()) if (!v.esNulo() && v.py() != "") salida[k] = v.py()
    return salida.filterValues { it != "-" }
}

class ObjetoBolsa(val id: String, val nombre: String, val cantidad: Long, val imagen: String?)

/** Todo lo que hay en la bolsa (monedas y objetos). */
fun objetosBolsa(cuenta: JsonObject?): List<ObjetoBolsa> =
    (cuenta?.get("monedas").objetos() + cuenta?.get("objetos").objetos()).mapNotNull { o ->
        val cant = o["cantidad"].entero(null) ?: return@mapNotNull null
        ObjetoBolsa(o["id"].py(), o["nombre"].textoO(o["id"].py()), cant, o["imageUrl"].s())
    }

/** Objeto de la bolsa por id ("310"), por nombre ("n:Time Emblem") o por expresión ("re:Rift.*R1"). */
private fun buscarEnBolsa(cuenta: JsonObject?, ident: String): JsonObject? {
    for (o in cuenta?.get("monedas").objetos() + cuenta?.get("objetos").objetos()) {
        val nombre = o["nombre"].textoO()
        when {
            ident.startsWith("re:") -> if (runCatching { Regex(ident.drop(3), RegexOption.IGNORE_CASE).containsMatchIn(nombre) }.getOrDefault(false)) return o
            ident.startsWith("n:") -> if (nombre.trim().lowercase() == ident.drop(2).trim().lowercase()) return o
            else -> if (o["id"].py() == ident) return o
        }
    }
    return null
}

/**
 * {recurso: cantidad} de los recursos vinculados a algo de tu bolsa. Los "(M)" se dividen por 1.000.000.
 * Un vínculo por nombre que no está en la bolsa queda en null (puede ser 0 o que el nombre sea distinto).
 */
fun inventarioFractura(cuenta: JsonObject?, base: JsonObject?): Map<String, Double?> {
    if (cuenta == null) return emptyMap()
    val salida = LinkedHashMap<String, Double?>()
    for ((nombre, ident) in vinculos(base)) {
        val o = buscarEnBolsa(cuenta, ident)
        if (o == null) {
            if (ident.startsWith("n:") || ident.startsWith("re:")) salida[nombre] = null
            continue
        }
        val cant = o["cantidad"].entero(null) ?: continue
        salida[nombre] = if (nombre.endsWith("(M)")) kotlin.math.round(cant / 100_000.0) / 10 else cant.toDouble()
    }
    return salida
}

/** Imagen de un recurso: la del objeto vinculado de tu bolsa (o de otra cuenta tuya), o el recorte incluido. */
fun imagenRecurso(cuentas: List<JsonObject>, base: JsonObject?, recurso: String): String {
    val ident = vinculos(base)[recurso]
    if (ident != null) {
        for (c in cuentas) buscarEnBolsa(c, ident)?.get("imageUrl")?.s()?.takeIf { it.isNotEmpty() }?.let { return it }
    }
    return "/capturas/$recurso.png"
}

/** Ícono de un objeto de tienda: héroes con cdn_id usan el ícono del CDN incluido. */
fun imagenObjetoTienda(cuentas: List<JsonObject>, base: JsonObject?, objeto: JsonObject): String =
    objeto["cdn_id"].entero(null)?.let { "/cdn/unit_icon_by_id/$it.webp" } ?: imagenRecurso(cuentas, base, objeto["objeto"].py())

/** 1234567 -> "1.234.567"; 0 -> "—" (_fmt de Python). */
fun fmtFractura(n: Double?): String {
    if (n == null || n == 0.0) return "—"
    val entero = n == kotlin.math.floor(n)
    val parteEntera = kotlin.math.abs(n.toLong()).toString().reversed().chunked(3).joinToString(".").reversed()
    val signo = if (n < 0) "-" else ""
    if (entero) return signo + parteEntera
    // f"{n:,}".replace(",", "."): los miles y los decimales quedan los dos con punto
    val dec = io.github.shredia.afkcommunity.idiomas.pyStr(n).substringAfter('.', "")
    return "$signo$parteEntera.$dec"
}
