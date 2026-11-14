package io.github.shredia.afkcommunity.datos

/**
 * Almacén en memoria: para pruebas y, por ahora, para la web (que todavía no guarda en OPFS: Etapa 5).
 * Nada sobrevive al cerrar la app.
 */
class AlmacenMemoria : Almacen {
    private val archivos = LinkedHashMap<String, ByteArray>()
    private val fechas = HashMap<String, Double>()
    private var reloj = 1_700_000_000.0

    private fun limpia(ruta: String) = ruta.trim('/')

    override suspend fun leerTexto(ruta: String): String? = leerBytes(ruta)?.decodeToString()
    override suspend fun escribirTexto(ruta: String, texto: String) = escribirBytes(ruta, texto.encodeToByteArray())
    override suspend fun leerBytes(ruta: String): ByteArray? = archivos[limpia(ruta)]
    override suspend fun escribirBytes(ruta: String, bytes: ByteArray) {
        archivos[limpia(ruta)] = bytes
        reloj += 1
        fechas[limpia(ruta)] = reloj
    }

    override suspend fun listar(carpeta: String): List<String> {
        val prefijo = limpia(carpeta).let { if (it.isEmpty()) "" else "$it/" }
        return archivos.keys.filter { it.startsWith(prefijo) }.map { it.removePrefix(prefijo).substringBefore('/') }
            .toSet().sorted()
    }

    override suspend fun existe(ruta: String): Boolean = limpia(ruta) in archivos || esCarpeta(ruta)
    override suspend fun esCarpeta(ruta: String): Boolean {
        val prefijo = limpia(ruta) + "/"
        return archivos.keys.any { it.startsWith(prefijo) }
    }

    override suspend fun modificado(ruta: String): Double? = fechas[limpia(ruta)]

    override suspend fun borrar(ruta: String) {
        val r = limpia(ruta)
        archivos.keys.filter { it == r || it.startsWith("$r/") }.forEach { archivos.remove(it); fechas.remove(it) }
    }
}

/** Plataforma mínima sin archivos (web, por ahora): se puede navegar, pero no importar. */
class PlataformaMemoria : Plataforma {
    override val almacen: Almacen = AlmacenMemoria()
    override suspend fun elegirArchivo(): ArchivoElegido? = null
    override suspend fun guardarZip(nombreSugerido: String, escribir: suspend (EscritorZip) -> Unit): String? = null
}
