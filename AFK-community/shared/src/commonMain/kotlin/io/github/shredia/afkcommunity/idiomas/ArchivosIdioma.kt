package io.github.shredia.afkcommunity.idiomas

import io.github.shredia.afkcommunity.recursos.Res
import org.jetbrains.compose.resources.ExperimentalResourceApi

/*
 * Los archivos de idioma van dentro de la app (files/idiomas/, copiados de NC/idiomas/ al compilar).
 * files/idiomas/indice.txt tiene un código por línea: lo genera la compilación, porque los recursos no se
 * pueden listar.
 */

@OptIn(ExperimentalResourceApi::class)
private suspend fun leerRecurso(ruta: String): String? =
    runCatching { Res.readBytes(ruta).decodeToString() }.getOrNull()

/** Contenido de idiomas/<codigo>.json, o null si no existe. */
suspend fun archivoIdioma(codigo: String): String? = leerRecurso("files/idiomas/$codigo.json")

/** [(código, nombre)] de los idiomas incluidos, en el orden de la app Python. */
suspend fun idiomasDisponibles(): List<Pair<String, String>> {
    val codigos = leerRecurso("files/idiomas/indice.txt").orEmpty().lines().map { it.trim() }.filter { it.isNotEmpty() }
    return ordenarIdiomas(codigos.map { codigo ->
        codigo to (archivoIdioma(codigo)?.let { Idiomas.nombre(it) } ?: codigo)
    })
}

/** Carga el idioma [codigo] (si no existe, queda el español). Devuelve el idioma que quedó. */
suspend fun cambiarIdioma(codigo: String?): String =
    Idiomas.usar(codigo, codigo?.let { archivoIdioma(it) })
