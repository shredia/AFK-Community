package io.github.shredia.afkcommunity.datos

/*
 * Lo único que cambia entre plataformas: dónde se guardan los datos, cómo se elige un archivo para importar,
 * dónde se guarda un .zip exportado y cómo se leen y escriben los .zip.
 * Android lo implementa en androidApp (filesDir, selector del sistema); Desktop en desktopApp.
 */

/** Un archivo que eligió el usuario para importar. */
interface ArchivoElegido {
    val nombre: String
    suspend fun leerBytes(): ByteArray
    /** El archivo como .zip, o null si no es un .zip válido. Hay que cerrarlo. */
    suspend fun abrirZip(): LectorZip?
}

interface LectorZip : AutoCloseable {
    /** Nombres de las entradas, como namelist() de Python (las carpetas terminan en "/"). */
    val nombres: List<String>
    fun leer(nombre: String): ByteArray?
}

interface EscritorZip {
    fun agregar(nombre: String, bytes: ByteArray)
}

interface Plataforma {
    val almacen: Almacen

    /** Abre el selector de archivos. null si el usuario cancela. */
    suspend fun elegirArchivo(): ArchivoElegido?

    /**
     * Pide dónde guardar un .zip y lo escribe con [escribir]. Devuelve dónde quedó (para mostrarlo) o null si
     * el usuario cancela.
     */
    suspend fun guardarZip(nombreSugerido: String, escribir: suspend (EscritorZip) -> Unit): String?
}
