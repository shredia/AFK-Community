package io.github.shredia.afkcommunity.logica

import io.github.shredia.afkcommunity.datos.Datos
import io.github.shredia.afkcommunity.datos.con
import io.github.shredia.afkcommunity.datos.objetos
import io.github.shredia.afkcommunity.datos.obj
import io.github.shredia.afkcommunity.datos.py
import io.github.shredia.afkcommunity.datos.textoO
import io.github.shredia.afkcommunity.datos.unir
import io.github.shredia.afkcommunity.datos.verdad
import io.github.shredia.afkcommunity.idiomas.N_
import io.github.shredia.afkcommunity.idiomas.tr
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject

/*
 * Bloqueos unificados del optimizador (port de navegador/bloqueos.py): baneos de héroes / mascotas y límites de
 * build en una sola lista. Cada regla lleva "aplica": "todo", "yo" (solo tus equipos) o "amigos".
 * Se guardan en bloqueos.json de la carpeta del servidor.
 */

const val ARCHIVO_BLOQUEOS = "bloqueos.json"
const val APLICA_TODO = "todo"
const val APLICA_YO = "yo"
const val APLICA_AMIGOS = "amigos"
val NOMBRES_APLICA = linkedMapOf(APLICA_TODO to N_("Todos los equipos"), APLICA_YO to N_("Solo tus equipos"),
    APLICA_AMIGOS to N_("Solo equipos de amigos"))

private fun aplica(b: JsonObject) = b["aplica"]?.py() ?: APLICA_TODO

private fun claveRegla(b: JsonObject): List<String> =
    if (b["limite"].verdad()) listOf("L", b["objeto"].py(), b["nombre"].py(), b["campo"].py(), b["jefe"].py(), aplica(b))
    else listOf("B", b["tipo"].py(), b["nombre"].py(), b["jefe"].py(), b["copia"].textoO(COPIA_TODAS), aplica(b))

fun sinDuplicados(reglas: List<JsonObject>): List<JsonObject> {
    val vistas = HashSet<List<String>>()
    return reglas.filter { vistas.add(claveRegla(it)) }
}

/** Lista de reglas del servidor (migra los archivos viejos la primera vez). */
suspend fun cargarBloqueos(datos: Datos, carpetaServidor: String, carpetaAmigos: String): List<JsonObject> {
    val archivo = datos.leerJson(unir(carpetaServidor, ARCHIVO_BLOQUEOS))
    if (archivo is JsonArray) return archivo.objetos()
    val reglas = mutableListOf<JsonObject>()
    for (b in cargarBaneos(datos, carpetaServidor)) reglas += b.con("aplica" to APLICA_TODO)
    for (b in cargarBaneos(datos, carpetaAmigos)) reglas += b.con("aplica" to APLICA_AMIGOS)
    for (b in datos.leerJson(unir(carpetaServidor, "limites.json")).objetos()) {
        if (b["limite"].verdad()) reglas += b.con("aplica" to b["aplica"].textoO(APLICA_TODO))
    }
    val unicas = sinDuplicados(reglas)
    if (unicas.isNotEmpty()) runCatching { guardarBloqueos(datos, carpetaServidor, unicas) }
    return unicas
}

suspend fun guardarBloqueos(datos: Datos, carpetaServidor: String, reglas: List<JsonObject>) =
    datos.escribirJson(unir(carpetaServidor, ARCHIVO_BLOQUEOS), JsonArray(sinDuplicados(reglas)), indentado = true)

/** Reglas que valen para 'yo' (tus equipos) o 'amigos' (los de otros). */
fun para(reglas: List<JsonObject>, lado: String): List<JsonObject> =
    reglas.filter { aplica(it) == APLICA_TODO || aplica(it) == lado }

/** Texto corto de una regla: 'Saitama: no usar' · 'Dracula: SI máximo 20' · 'Colección X: no la tengo'. */
fun describir(b: JsonObject, conJefe: Boolean = true, etiquetaJefe: ((String) -> String)? = null): String {
    val nombre = b["nombre"].textoO("?").split(" - ")[0]
    var texto = when {
        b["limite"].verdad() -> describirLimite(b)
        b["tipo"].py().uppercase() == "MASCOTA" -> tr("Mascota {0}: no usar", nombre)
        b["copia"].textoO(COPIA_TODAS) == COPIA_NO_PROPIA -> tr("{0}: no usar la copia prestada/prueba", nombre)
        else -> tr("{0}: no usar", nombre)
    }
    val jefe = b["jefe"].textoO("TODOS")
    if (conJefe && jefe != "TODOS") texto += " · " + (etiquetaJefe?.invoke(jefe) ?: tr("jefe {0}", jefe))
    return texto
}

fun nuevaReglaBaneo(tipo: String, nombre: String, ident: String = "", jefe: String = "TODOS",
                    soloCopia: Boolean = false, aplica: String = APLICA_TODO): JsonObject =
    obj("tipo" to tipo, "nombre" to nombre, "id" to ident, "jefe" to jefe.ifEmpty { "TODOS" },
        "copia" to (if (soloCopia) COPIA_NO_PROPIA else COPIA_TODAS), "activo" to true, "aplica" to aplica)

fun nuevaReglaLimite(objeto: String, nombre: String, campo: String, maximo: Int, jefe: String = "TODOS",
                     aplica: String = APLICA_TODO): JsonObject =
    obj("limite" to true, "objeto" to objeto, "nombre" to nombre.ifEmpty { "*" }, "campo" to campo, "max" to maximo,
        "jefe" to jefe.ifEmpty { "TODOS" }, "activo" to true, "aplica" to aplica)
