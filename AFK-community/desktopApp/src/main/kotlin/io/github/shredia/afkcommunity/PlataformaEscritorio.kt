package io.github.shredia.afkcommunity

import io.github.shredia.afkcommunity.datos.AlmacenArchivos
import io.github.shredia.afkcommunity.datos.ArchivoElegido
import io.github.shredia.afkcommunity.datos.EscritorZip
import io.github.shredia.afkcommunity.datos.LectorZip
import io.github.shredia.afkcommunity.datos.Plataforma
import io.github.shredia.afkcommunity.datos.carpetaDeDatos
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.awt.FileDialog
import java.awt.Frame
import java.io.File
import java.util.zip.ZipEntry
import java.util.zip.ZipFile
import java.util.zip.ZipOutputStream

/** Desktop: carpeta de datos propia (o AFK_DATOS), diálogos nativos de archivo y java.util.zip. */
class PlataformaEscritorio : Plataforma {
    override val almacen = AlmacenArchivos(carpetaDeDatos())

    override suspend fun elegirArchivo(): ArchivoElegido? = withContext(Dispatchers.Main) {
        val dialogo = FileDialog(null as Frame?, "Elegir archivo para importar", FileDialog.LOAD)
        dialogo.setFilenameFilter { _, n -> n.lowercase().endsWith(".json") || n.lowercase().endsWith(".zip") }
        dialogo.isVisible = true
        val nombre = dialogo.file ?: return@withContext null
        ArchivoLocal(File(dialogo.directory, nombre))
    }

    override suspend fun guardarZip(nombreSugerido: String, escribir: suspend (EscritorZip) -> Unit): String? {
        val destino = withContext(Dispatchers.Main) {
            val dialogo = FileDialog(null as Frame?, "Guardar .zip", FileDialog.SAVE)
            dialogo.file = nombreSugerido
            dialogo.isVisible = true
            dialogo.file?.let { File(dialogo.directory, if (it.lowercase().endsWith(".zip")) it else "$it.zip") }
        } ?: return null
        withContext(Dispatchers.IO) {
            ZipOutputStream(destino.outputStream().buffered()).use { z ->
                escribir(object : EscritorZip {
                    override fun agregar(nombre: String, bytes: ByteArray) {
                        z.putNextEntry(ZipEntry(nombre))
                        z.write(bytes)
                        z.closeEntry()
                    }
                })
            }
        }
        return destino.absolutePath
    }
}

private class ArchivoLocal(val archivo: File) : ArchivoElegido {
    override val nombre: String = archivo.name
    override suspend fun leerBytes(): ByteArray = withContext(Dispatchers.IO) { archivo.readBytes() }
    override suspend fun abrirZip(): LectorZip? = withContext(Dispatchers.IO) {
        runCatching { ZipFile(archivo) }.getOrNull()?.let { LectorZipArchivo(it) }
    }
}

class LectorZipArchivo(private val zip: ZipFile) : LectorZip {
    override val nombres: List<String> = zip.entries().toList().map { it.name }
    override fun leer(nombre: String): ByteArray? = zip.getEntry(nombre)?.let { e -> zip.getInputStream(e).use { it.readBytes() } }
    override fun close() = zip.close()
}
