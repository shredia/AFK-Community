package io.github.shredia.afkcommunity.logica

import io.github.shredia.afkcommunity.datos.Datos
import io.github.shredia.afkcommunity.datos.esNulo
import io.github.shredia.afkcommunity.datos.int
import io.github.shredia.afkcommunity.datos.o
import io.github.shredia.afkcommunity.datos.objetos
import io.github.shredia.afkcommunity.datos.py
import io.github.shredia.afkcommunity.datos.textoO
import io.github.shredia.afkcommunity.datos.unir
import io.github.shredia.afkcommunity.datos.verdad
import io.github.shredia.afkcommunity.idiomas.N_
import io.github.shredia.afkcommunity.idiomas.tr
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive

/*
 * Tu perfil de roster (port de navegador/roster.py): qué héroes, colecciones y mascotas tienes y hasta dónde.
 * Sale de cuenta_actual.json y se puede corregir a mano (perfil_roster.json en la carpeta del servidor).
 * Sirve para saber si puedes copiar el equipo de otro jugador y qué te falta.
 */

const val ARCHIVO_PERFIL = "perfil_roster.json"

val CAMPOS_PERFIL: Map<String, Map<String, String>> = mapOf(
    "HEROE" to linkedMapOf("quality" to N_("Ascensión"), "sig" to N_("SI"), "engraving" to N_("Grabado"), "muebles" to N_("Muebles")),
    "COLECCION" to linkedMapOf("estrellas" to N_("★ de habilidad"), "mythic" to N_("Míticos"), "level" to N_("Nivel")),
    "MASCOTA" to linkedMapOf(),
)

enum class Nivel(val icono: String, val texto: String) {
    PUEDO("✅", N_("Puedes armarlo")),
    CASI("🟡", N_("Te falta mejorar algo")),
    NO_PUEDO("❌", N_("Te falta algún héroe")),
}

/** Una entrada del perfil: nombre, si lo tienes y sus valores (los campos de CAMPOS_PERFIL). */
class EntradaPerfil(var nombre: String, var tengo: Boolean = true, val valores: MutableMap<String, Int?> = linkedMapOf(),
                    var manual: Boolean = false)

class Perfil(
    val heroes: LinkedHashMap<String, EntradaPerfil>,
    val colecciones: LinkedHashMap<String, EntradaPerfil>,
    val mascotas: LinkedHashMap<String, EntradaPerfil>,
    val conInventario: Boolean,
    val captura: String?,
    var manuales: Int = 0,
) {
    fun de(tipo: String) = when (tipo) { "HEROE" -> heroes; "COLECCION" -> colecciones; else -> mascotas }
    val hayDatos get() = conInventario || manuales > 0
}

class Falta(val clave: String, val texto: String, val grave: Boolean)

suspend fun cargarCorrecciones(datos: Datos, carpeta: String): JsonObject =
    datos.leerObjeto(unir(carpeta, ARCHIVO_PERFIL)) ?: JsonObject(emptyMap())

suspend fun guardarCorrecciones(datos: Datos, carpeta: String, correcciones: JsonObject) =
    datos.escribirJson(unir(carpeta, ARCHIVO_PERFIL), correcciones, indentado = true)

fun valorHeroe(h: JsonObject, campo: String): Int =
    if (campo == "muebles") h["furniture"].o()["pieces"].int(0) else h[campo].int(0)

/** Tu perfil: inventario (cuenta_actual) + correcciones a mano. */
fun armarPerfil(estado: JsonObject?, vis: Visuales?, correcciones: JsonObject): Perfil {
    val e = estado ?: JsonObject(emptyMap())
    val heroes = LinkedHashMap<String, EntradaPerfil>()
    val colecciones = LinkedHashMap<String, EntradaPerfil>()
    val mascotas = LinkedHashMap<String, EntradaPerfil>()

    for (h in e["roster"].objetos()) {
        if (h["temporal"].verdad() && !esArrendadoCuenta(h, e)) continue   // de prueba: no es tuyo
        val tid = h["tid"].py()
        val nuevo = EntradaPerfil(h["name"].textoO(tid), true,
            CAMPOS_PERFIL.getValue("HEROE").keys.associateWithTo(linkedMapOf()) { valorHeroe(h, it) })
        val previo = heroes[tid]
        if (previo == null || (nuevo.valores["quality"] ?: 0) > (previo.valores["quality"] ?: 0)) heroes[tid] = nuevo
    }
    // héroes que solo tienes como copia base (sin desarrollar)
    for (c in e["copias_base"].objetos()) {
        val tid = c["tid"].py()
        if (tid !in heroes && c["nombre"].verdad()) heroes[tid] = EntradaPerfil(c["nombre"].py(), true,
            linkedMapOf("quality" to c["calidad"].int(0), "sig" to 0, "engraving" to 0, "muebles" to 0))
    }
    for (col in e["colecciones"].objetos()) {
        val tid = col["tid"].py()
        val estrellas = if (vis?.disponible == true) vis.estrellasColeccion(col) else null
        val nuevo = EntradaPerfil(col["name"].textoO(tid), true,
            linkedMapOf("estrellas" to estrellas, "mythic" to col["mythic"].int(0), "level" to col["level"].int(0)))
        val previo = colecciones[tid]
        fun clave(d: EntradaPerfil) = Triple(d.valores["estrellas"] ?: 0, d.valores["mythic"] ?: 0, d.valores["level"] ?: 0)
        if (previo == null || compareValuesBy(clave(nuevo), clave(previo), { it.first }, { it.second }, { it.third }) > 0) colecciones[tid] = nuevo
    }
    for (p in e["mascotas_roster"].objetos()) mascotas[p["tid"].py()] = EntradaPerfil(p["name"].textoO(p["tid"].py()))

    val perfil = Perfil(heroes, colecciones, mascotas, e["roster"].objetos().isNotEmpty(), e["capturedAt"]?.textoO())
    aplicarCorrecciones(perfil, correcciones)
    return perfil
}

fun aplicarCorrecciones(perfil: Perfil, correcciones: JsonObject) {
    var n = 0
    for (tipo in listOf("HEROE", "COLECCION", "MASCOTA")) {
        for ((clave, datosE) in correcciones[tipo].o()) {
            val d = datosE as? JsonObject ?: continue
            val entrada = perfil.de(tipo).getOrPut(clave) { EntradaPerfil(d["nombre"].textoO(clave)) }
            for ((k, v) in d) when (k) {
                "nombre" -> entrada.nombre = v.textoO(entrada.nombre)
                "tengo" -> entrada.tengo = v.verdad()
                "manual" -> {}
                else -> entrada.valores[k] = if (v.esNulo()) null else v.int(0)
            }
            entrada.manual = true
            n++
        }
    }
    perfil.manuales = n
}

/** La corrección de una entrada, como la guarda Python: {"nombre", "tengo", campos...}. */
fun correccionDe(entrada: EntradaPerfil): JsonObject = JsonObject(linkedMapOf<String, JsonElement>(
    "nombre" to JsonPrimitive(entrada.nombre), "tengo" to JsonPrimitive(entrada.tengo),
).apply { if (entrada.tengo) for ((k, v) in entrada.valores) if (v != null) put(k, JsonPrimitive(v)) })

private fun corto(nombre: String) = nombre.split(" - ")[0]

/**
 * ¿Puedes armar este equipo con tu roster? (nivel, faltas); nivel null si no hay perfil.
 * Sin inventario solo cuentan las correcciones manuales (lo no marcado se supone que lo tienes).
 */
fun evaluarEquipo(comp: Composicion, perfil: Perfil?): Pair<Nivel?, List<Falta>> {
    if (perfil == null || !perfil.hayDatos) return null to emptyList()
    val completo = perfil.conInventario
    val faltas = mutableListOf<Falta>()
    val origenes = comp.heroOrigenes.ifEmpty { List(comp.heroes.size) { PROPIO } }
    for ((h, origen) in comp.heroes.zip(origenes)) {
        if (origen in TEMPORALES) continue   // lo usó prestado / de prueba: tú también puedes pedirlo
        val tid = h["tid"].py()
        val nombre = corto(h["name"].textoO("?"))
        val mio = perfil.heroes[tid]
        if ((mio == null && completo) || (mio != null && !mio.tengo)) {
            faltas += Falta("HEROE|$tid", tr("{0}: no lo tienes", nombre), true)
            continue
        }
        if (mio != null) {
            for ((campo, etiqueta) in CAMPOS_PERFIL.getValue("HEROE")) {
                val necesita = valorHeroe(h, campo)
                val tengo = mio.valores[campo] ?: continue
                if (necesita > tengo) {
                    val texto = if (campo == "quality") tr("{0}: {1} (tienes {2})", nombre,
                        Visuales.nombreCalidad(JsonPrimitive(necesita)), Visuales.nombreCalidad(JsonPrimitive(tengo)))
                    else tr("{0}: {1} {2} (tienes {3})", nombre, tr(etiqueta), necesita, tengo)
                    faltas += Falta("HEROE|$tid|$campo|$necesita", texto, false)
                }
            }
        }
        val col = h["collection"].o()
        if (col.isNotEmpty()) {
            val ctid = col["tid"].py()
            val cnombre = col["name"].textoO("?")
            val mia = perfil.colecciones[ctid]
            if ((mia == null && completo) || (mia != null && !mia.tengo)) {
                faltas += Falta("COLECCION|$ctid", tr("Colección {0}: no la tienes", cnombre), false)
            } else if (mia != null) {
                for ((campo, etiqueta) in CAMPOS_PERFIL.getValue("COLECCION")) {
                    if (col[campo].esNulo()) continue
                    val necesita = col[campo].int(0)
                    val tengo = mia.valores[campo] ?: continue
                    if (necesita > tengo) faltas += Falta("COLECCION|$ctid|$campo|$necesita",
                        tr("Colección {0}: {1} {2} (tienes {3})", cnombre, tr(etiqueta), necesita, tengo), false)
                }
            }
        }
    }
    val mascota = comp.mascota
    if (!mascota["tid"].esNulo()) {
        val mtid = mascota["tid"].py()
        val mia = perfil.mascotas[mtid]
        if ((mia == null && completo && perfil.mascotas.isNotEmpty()) || (mia != null && !mia.tengo)) {
            faltas += Falta("MASCOTA|$mtid", tr("Mascota {0}: no la tienes", mascota["name"].textoO("?")), false)
        }
    }
    val unicas = sinRepetir(faltas)
    if (unicas.any { it.grave }) return Nivel.NO_PUEDO to unicas
    return (if (unicas.isNotEmpty()) Nivel.CASI else Nivel.PUEDO) to unicas
}

/** Si dos héroes llevan la misma colección, se queda la exigencia mayor (y sin duplicar 'no la tienes'). */
private fun sinRepetir(faltas: List<Falta>): List<Falta> {
    val salida = mutableListOf<Falta>()
    val indice = HashMap<String, Int>()
    for (f in faltas) {
        val partes = f.clave.split("|")
        val grupo = if (partes.size >= 4) partes.take(3).joinToString("|") else f.clave
        val i = indice[grupo]
        if (i != null) {
            if (partes.size >= 4 && partes[3].toInt() > salida[i].clave.split("|")[3].toInt()) salida[i] = f
            continue
        }
        indice[grupo] = salida.size
        salida += f
    }
    return salida
}

const val MODO_ROSTER_TODOS = "todos"
const val MODO_ROSTER_CASI = "casi"
const val MODO_ROSTER_OK = "ok"

/** modo: 'todos' | 'casi' (puedes o casi) | 'ok' (solo lo que puedes armar tal cual). */
fun filtrarPorRoster(comps: List<Composicion>, perfil: Perfil?, modo: String): List<Composicion> {
    if (modo !in setOf(MODO_ROSTER_CASI, MODO_ROSTER_OK) || perfil == null || !perfil.hayDatos) return comps
    val permitidos = if (modo == MODO_ROSTER_OK) setOf(Nivel.PUEDO) else setOf(Nivel.PUEDO, Nivel.CASI)
    return comps.filter { evaluarEquipo(it, perfil).first in permitidos }
}
