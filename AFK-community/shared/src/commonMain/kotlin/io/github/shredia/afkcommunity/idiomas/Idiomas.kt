package io.github.shredia.afkcommunity.idiomas

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive

/*
 * Idiomas de la app (port de idiomas/__init__.py). Los archivos son los mismos de la app Python:
 * NC/idiomas/<código>.json  →  {"_meta": {"codigo", "nombre"}, "traducciones": {"texto en español": "traducción"}}
 *
 * - El texto en español es la clave:  tr("Acceso al sitio"),  tr("Descargados: {0} de {1}", ya, total)
 * - Si una frase no está traducida (o está vacía) se muestra en español.
 * - N_("texto") marca un texto para traducirlo después con tr(variable).
 */
object Idiomas {
    const val BASE = "es"

    var actual: String = BASE
        private set

    private var traducciones: Map<String, String> = emptyMap()

    /**
     * Usa el idioma [codigo] con el contenido de su archivo (o el español si no hay archivo o no se entiende).
     * Devuelve el idioma que quedó.
     */
    fun usar(codigo: String?, contenido: String?): String {
        traducciones = emptyMap()
        actual = BASE
        if (codigo != null && codigo != BASE && contenido != null) {
            val datos = leer(contenido)
            if (datos != null) {
                traducciones = (datos["traducciones"] as? JsonObject).orEmpty()
                    .mapNotNull { (k, v) -> (v as? kotlinx.serialization.json.JsonPrimitive)?.contentOrNull
                        ?.takeIf { it.isNotEmpty() }?.let { k to it } }
                    .toMap()
                actual = codigo
            }
        }
        return actual
    }

    /** Nombre del idioma ("English") según el _meta de su archivo, o null. */
    fun nombre(contenido: String): String? =
        runCatching { leer(contenido)?.get("_meta")?.jsonObject?.get("nombre")?.jsonPrimitive?.contentOrNull }
            .getOrNull()

    internal fun plantilla(texto: String): String = traducciones[texto] ?: texto

    private fun leer(contenido: String): JsonObject? =
        runCatching { Json.parseToJsonElement(contenido) as? JsonObject }.getOrNull()
}

/** Traduce [texto] al idioma actual (o lo deja en español) y le inserta los datos, como str.format de Python. */
fun tr(texto: String, vararg args: Any?): String {
    val plantilla = Idiomas.plantilla(texto)
    if (args.isEmpty()) return plantilla
    val lista = args.toList()
    return try {
        formatear(plantilla, lista)
    } catch (_: IllegalArgumentException) {
        formatear(texto, lista)   // traducción mal escrita: el texto original
    }
}

/** Marca un texto para traducirlo más tarde (no lo traduce ahora). */
@Suppress("FunctionName")
fun N_(texto: String): String = texto

/**
 * Orden de la lista de idiomas, como idiomas_disponibles() de Python: primero el español, luego por nombre.
 * [idiomas]: (código, nombre).
 */
fun ordenarIdiomas(idiomas: List<Pair<String, String>>): List<Pair<String, String>> =
    idiomas.sortedWith(compareBy({ it.first != Idiomas.BASE }, { it.second.lowercase() }))
