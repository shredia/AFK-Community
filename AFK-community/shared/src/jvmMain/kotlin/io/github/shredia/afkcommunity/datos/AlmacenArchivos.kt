package io.github.shredia.afkcommunity.datos

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File
import java.nio.file.AtomicMoveNotSupportedException
import java.nio.file.Files
import java.nio.file.StandardCopyOption
import java.util.concurrent.TimeUnit

/** El almacén en una carpeta del disco (Desktop). */
class AlmacenArchivos(val raiz: File) : Almacen {

    private fun archivo(ruta: String): File {
        val f = File(raiz, ruta).canonicalFile
        require(f.toPath().startsWith(raiz.canonicalFile.toPath())) { "Ruta fuera de la carpeta de datos: $ruta" }
        return f
    }

    override suspend fun leerTexto(ruta: String): String? = leerBytes(ruta)?.decodeToString()

    override suspend fun escribirTexto(ruta: String, texto: String) = escribirBytes(ruta, texto.encodeToByteArray())

    override suspend fun leerBytes(ruta: String): ByteArray? = withContext(Dispatchers.IO) {
        archivo(ruta).takeIf { it.isFile }?.readBytes()
    }

    override suspend fun escribirBytes(ruta: String, bytes: ByteArray) = withContext(Dispatchers.IO) {
        val destino = archivo(ruta)
        destino.parentFile.mkdirs()
        // Igual que _escribir_json de Python: <nombre>.tmp y luego reemplazar
        val temporal = File(destino.parentFile, destino.name + ".tmp")
        temporal.writeBytes(bytes)
        try {
            Files.move(temporal.toPath(), destino.toPath(), StandardCopyOption.REPLACE_EXISTING,
                StandardCopyOption.ATOMIC_MOVE)
        } catch (_: AtomicMoveNotSupportedException) {
            Files.move(temporal.toPath(), destino.toPath(), StandardCopyOption.REPLACE_EXISTING)
        }
        Unit
    }

    override suspend fun listar(carpeta: String): List<String> = withContext(Dispatchers.IO) {
        archivo(carpeta).list()?.sorted().orEmpty()
    }

    override suspend fun existe(ruta: String): Boolean = withContext(Dispatchers.IO) { archivo(ruta).exists() }

    override suspend fun esCarpeta(ruta: String): Boolean = withContext(Dispatchers.IO) { archivo(ruta).isDirectory }

    override suspend fun modificado(ruta: String): Double? = withContext(Dispatchers.IO) {
        val f = archivo(ruta)
        if (!f.exists()) null
        else {
            // Como st_mtime de Python (fill_time en posixmodule.c): segundos + nanosegundos · 1e-9.
            // Así el valor coincide con el que guardó la app Python en optimizador_indice.json.
            val ns = Files.getLastModifiedTime(f.toPath()).to(TimeUnit.NANOSECONDS)
            Math.floorDiv(ns, 1_000_000_000L).toDouble() + Math.floorMod(ns, 1_000_000_000L) * 1e-9
        }
    }

    override suspend fun borrar(ruta: String) = withContext(Dispatchers.IO) {
        val f = archivo(ruta)
        require(f != raiz.canonicalFile) { "No se borra la carpeta de datos completa" }
        f.deleteRecursively()
        Unit
    }
}

/**
 * Carpeta de datos de Desktop:
 *  - la variable de entorno AFK_DATOS, si existe (p. ej. una copia de prueba: NC_pruebas/datos_usuario);
 *  - Windows: %APPDATA%/AFK-Community · macOS: ~/Library/Application Support/AFK-Community ·
 *    Linux: $XDG_DATA_HOME/AFK-Community o ~/.local/share/AFK-Community.
 */
fun carpetaDeDatos(): File {
    System.getenv("AFK_DATOS")?.takeIf { it.isNotBlank() }?.let { return File(it) }
    val so = System.getProperty("os.name").lowercase()
    val casa = File(System.getProperty("user.home"))
    val base = when {
        so.startsWith("windows") -> System.getenv("APPDATA")?.let(::File) ?: File(casa, "AppData/Roaming")
        so.startsWith("mac") -> File(casa, "Library/Application Support")
        else -> System.getenv("XDG_DATA_HOME")?.takeIf { it.isNotBlank() }?.let(::File) ?: File(casa, ".local/share")
    }
    return File(base, "AFK-Community")
}
