package io.github.shredia.afkcommunity.datos

/**
 * Los archivos de la app, con rutas relativas a la carpeta de datos y separadas por "/":
 * "cuentas/<cuenta>/<servidor>/runs.json". Es la misma estructura que datos_usuario/ de la app Python.
 *
 * Cada plataforma la guarda en su lugar: una carpeta en Desktop, filesDir en Android, OPFS en la web.
 */
interface Almacen {
    /** Texto UTF-8 del archivo, o null si no existe. */
    suspend fun leerTexto(ruta: String): String?

    /** Escritura atómica (un corte a la mitad no deja el archivo roto). Crea las carpetas que falten. */
    suspend fun escribirTexto(ruta: String, texto: String)

    suspend fun leerBytes(ruta: String): ByteArray?

    suspend fun escribirBytes(ruta: String, bytes: ByteArray)

    /** Nombres (no rutas) de lo que hay dentro de [carpeta], ordenados. Vacío si no existe. */
    suspend fun listar(carpeta: String): List<String>

    suspend fun existe(ruta: String): Boolean

    suspend fun esCarpeta(ruta: String): Boolean

    /**
     * Fecha de modificación en segundos (como st_mtime de Python), o null si no existe. El índice del
     * optimizador la usa para saber qué detalles cambiaron.
     */
    suspend fun modificado(ruta: String): Double?

    /** Borra un archivo o una carpeta con todo su contenido. No falla si no existe. */
    suspend fun borrar(ruta: String)
}

/** Une partes de una ruta del almacén: unir("cuentas", "x", "runs.json") = "cuentas/x/runs.json". */
fun unir(vararg partes: String): String =
    partes.filter { it.isNotEmpty() }.joinToString("/") { it.trim('/') }

/** La carpeta que contiene [ruta] ("" si está en la raíz). */
fun padre(ruta: String): String = ruta.trimEnd('/').substringBeforeLast('/', "")

/** El último nombre de [ruta]. */
fun nombre(ruta: String): String = ruta.trimEnd('/').substringAfterLast('/')
