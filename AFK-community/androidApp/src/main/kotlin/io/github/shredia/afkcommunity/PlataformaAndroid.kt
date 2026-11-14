package io.github.shredia.afkcommunity

import android.content.Context
import android.net.Uri
import android.provider.OpenableColumns
import io.github.shredia.afkcommunity.datos.Almacen
import io.github.shredia.afkcommunity.datos.ArchivoElegido
import io.github.shredia.afkcommunity.datos.EscritorZip
import io.github.shredia.afkcommunity.datos.LectorZip
import io.github.shredia.afkcommunity.datos.Plataforma
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File
import java.util.zip.ZipEntry
import java.util.zip.ZipFile
import java.util.zip.ZipOutputStream

/**
 * Android: los datos van en la carpeta privada de la app (filesDir/datos, la misma estructura que datos_usuario/
 * de la app Python); los archivos se eligen y se guardan con el selector del sistema.
 */
class PlataformaAndroid(private val actividad: MainActivity) : Plataforma {
    override val almacen: Almacen = AlmacenAndroid(File(actividad.filesDir, "datos"))

    override suspend fun elegirArchivo(): ArchivoElegido? {
        val uri = actividad.pedirArchivo() ?: return null
        return ArchivoAndroid(actividad, uri)
    }

    override suspend fun guardarZip(nombreSugerido: String, escribir: suspend (EscritorZip) -> Unit): String? {
        val uri = actividad.pedirDestino(nombreSugerido) ?: return null
        withContext(Dispatchers.IO) {
            val salida = actividad.contentResolver.openOutputStream(uri) ?: error("No se pudo escribir el archivo")
            ZipOutputStream(salida.buffered()).use { z ->
                escribir(object : EscritorZip {
                    override fun agregar(nombre: String, bytes: ByteArray) {
                        z.putNextEntry(ZipEntry(nombre))
                        z.write(bytes)
                        z.closeEntry()
                    }
                })
            }
        }
        return nombreDe(actividad, uri) ?: nombreSugerido
    }
}

private fun nombreDe(contexto: Context, uri: Uri): String? =
    contexto.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { c ->
        if (c.moveToFirst()) c.getString(0) else null
    }

private class ArchivoAndroid(private val contexto: Context, private val uri: Uri) : ArchivoElegido {
    override val nombre: String = nombreDe(contexto, uri) ?: uri.lastPathSegment ?: "archivo"

    override suspend fun leerBytes(): ByteArray = withContext(Dispatchers.IO) {
        contexto.contentResolver.openInputStream(uri)?.use { it.readBytes() } ?: error("No se pudo leer $nombre")
    }

    /** ZipFile necesita un archivo con acceso directo: se copia primero a la caché de la app. */
    override suspend fun abrirZip(): LectorZip? = withContext(Dispatchers.IO) {
        val copia = File(contexto.cacheDir, "importar.zip")
        contexto.contentResolver.openInputStream(uri)?.use { entrada -> copia.outputStream().use { entrada.copyTo(it) } }
            ?: return@withContext null
        runCatching { ZipFile(copia) }.getOrNull()?.let { LectorZipAndroid(it, copia) }
    }
}

private class LectorZipAndroid(private val zip: ZipFile, private val copia: File) : LectorZip {
    override val nombres: List<String> = zip.entries().toList().map { it.name }
    override fun leer(nombre: String): ByteArray? = zip.getEntry(nombre)?.let { e -> zip.getInputStream(e).use { it.readBytes() } }
    override fun close() {
        zip.close()
        copia.delete()
    }
}

/** El almacén en la carpeta privada de la app (sin java.nio.file, que Android solo trae desde la API 26). */
class AlmacenAndroid(private val raiz: File) : Almacen {
    private fun archivo(ruta: String): File {
        val f = File(raiz, ruta).canonicalFile
        require(f.path.startsWith(raiz.canonicalFile.path)) { "Ruta fuera de la carpeta de datos: $ruta" }
        return f
    }

    override suspend fun leerTexto(ruta: String): String? = leerBytes(ruta)?.decodeToString()

    override suspend fun escribirTexto(ruta: String, texto: String) = escribirBytes(ruta, texto.encodeToByteArray())

    override suspend fun leerBytes(ruta: String): ByteArray? = withContext(Dispatchers.IO) {
        archivo(ruta).takeIf { it.isFile }?.readBytes()
    }

    override suspend fun escribirBytes(ruta: String, bytes: ByteArray) = withContext(Dispatchers.IO) {
        val destino = archivo(ruta)
        destino.parentFile?.mkdirs()
        // Igual que _escribir_json de Python: <nombre>.tmp y luego reemplazar (rename es atómico en el mismo disco)
        val temporal = File(destino.parentFile, destino.name + ".tmp")
        temporal.writeBytes(bytes)
        if (!temporal.renameTo(destino)) {
            destino.delete()
            check(temporal.renameTo(destino)) { "No se pudo guardar $ruta" }
        }
    }

    override suspend fun listar(carpeta: String): List<String> = withContext(Dispatchers.IO) {
        archivo(carpeta).list()?.filter { !it.endsWith(".tmp") }?.sorted().orEmpty()
    }

    override suspend fun existe(ruta: String): Boolean = withContext(Dispatchers.IO) { archivo(ruta).exists() }

    override suspend fun esCarpeta(ruta: String): Boolean = withContext(Dispatchers.IO) { archivo(ruta).isDirectory }

    override suspend fun modificado(ruta: String): Double? = withContext(Dispatchers.IO) {
        archivo(ruta).takeIf { it.exists() }?.lastModified()?.let { it / 1000.0 }
    }

    override suspend fun borrar(ruta: String) = withContext(Dispatchers.IO) {
        val f = archivo(ruta)
        require(f != raiz.canonicalFile) { "No se borra la carpeta de datos completa" }
        f.deleteRecursively()
        Unit
    }
}
