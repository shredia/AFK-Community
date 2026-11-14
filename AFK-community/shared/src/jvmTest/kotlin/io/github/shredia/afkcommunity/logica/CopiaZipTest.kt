package io.github.shredia.afkcommunity.logica

import io.github.shredia.afkcommunity.datos.AlmacenArchivos
import io.github.shredia.afkcommunity.datos.Datos
import io.github.shredia.afkcommunity.datos.EscritorZip
import io.github.shredia.afkcommunity.datos.LectorZip
import kotlinx.coroutines.test.runTest
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.File
import java.nio.file.Files
import java.util.zip.ZipEntry
import java.util.zip.ZipInputStream
import java.util.zip.ZipOutputStream
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue
import kotlin.time.Duration.Companion.minutes

/** Copias .zip: exportar, restaurar, importar como amigo y rechazar rutas peligrosas. */
class CopiaZipTest {

    private class ZipMemoria(entradas: Map<String, ByteArray>) : LectorZip {
        private val mapa = LinkedHashMap(entradas)
        override val nombres = mapa.keys.toList()
        override fun leer(nombre: String) = mapa[nombre]
        override fun close() {}
    }

    private fun leerZip(bytes: ByteArray): ZipMemoria {
        val m = LinkedHashMap<String, ByteArray>()
        ZipInputStream(ByteArrayInputStream(bytes)).use { z ->
            while (true) {
                val e = z.nextEntry ?: break
                m[e.name] = if (e.isDirectory) ByteArray(0) else z.readBytes()
            }
        }
        return ZipMemoria(m)
    }

    private fun nuevo() = Datos(AlmacenArchivos(Files.createTempDirectory("zip").toFile().apply { deleteOnExit() }))

    private suspend fun personajeConRuns(datos: Datos): String {
        val c = "cuentas/local/146"
        datos.escribirJson("cuentas/local/account.json", io.github.shredia.afkcommunity.datos.obj("id" to "local", "local" to true, "fetchedAt" to ""))
        datos.escribirJson("$c/146.json", io.github.shredia.afkcommunity.datos.obj("uid" to "999", "name" to "Yo", "svr_id" to 146))
        datos.escribirJson("$c/runs.json", io.github.shredia.afkcommunity.datos.aJson(listOf(mapOf("id" to "r1", "playedAt" to "2026-11-01T00:00:00Z", "mine" to true))))
        datos.escribirJson("$c/detalles/r1.json", io.github.shredia.afkcommunity.datos.obj("id" to "r1", "rounds" to emptyList<Any>()))
        datos.escribirJson("$c/$ARCHIVO_INDICE", io.github.shredia.afkcommunity.datos.obj("version" to 5))
        return c
    }

    @Test fun exportarYRestaurar() = runTest {
        val origen = nuevo()
        val c = personajeConRuns(origen)
        val salida = ByteArrayOutputStream()
        val n = ZipOutputStream(salida).use { z ->
            exportarCopia(origen, c, object : EscritorZip {
                override fun agregar(nombre: String, bytes: ByteArray) { z.putNextEntry(ZipEntry(nombre)); z.write(bytes); z.closeEntry() }
            })
        }
        val zip = leerZip(salida.toByteArray())
        assertEquals(4, n)   // ficha, runs, detalle y account.json; el índice no se exporta
        assertTrue("local/146/runs.json" in zip.nombres && "local/account.json" in zip.nombres)
        assertTrue(zip.nombres.none { it.endsWith(ARCHIVO_INDICE) })

        val destino = nuevo()
        assertEquals(listOf("local" to "146"), contenidoCopia(zip))
        importarCopia(destino, zip)
        assertEquals(origen.leerJson("$c/runs.json"), destino.leerJson("$c/runs.json"))
        assertEquals(mapOf("999" to c), destino.mapaPersonajes())

        // como amigo: solo las runs, en cuentas/_amigos/
        val r = importarCopiaDeAmigo(destino, zip, "Pedro", "146")
        assertEquals(1, r.nuevas)
        assertEquals(listOf("Pedro"), amigos(destino).map { it.nombre })
        assertEquals(0, importarCopiaDeAmigo(destino, zip, "Pedro", "146").nuevas)   // la segunda vez no duplica
    }

    @Test fun rechazaRutasPeligrosas() {
        for (malo in listOf("../fuera.json", "/abs/x/y.json", "a/../../b/c.json", "C:/x/y/z.json", "solo.json")) {
            assertFailsWith<IllegalArgumentException>(malo) { contenidoCopia(ZipMemoria(mapOf(malo to ByteArray(0)))) }
        }
    }

    /** El .zip real que exportó la app Python (si está): se importa como amigo. */
    @Test fun zipDeLaAppPython() = runTest(timeout = 5.minutes) {
        val archivo = File(System.getenv("AFK_IMPORTAR_ORIGEN") ?: return@runTest, "shrediaEX.zip")
        if (!archivo.exists()) return@runTest
        val zip = leerZip(archivo.readBytes())
        val datos = nuevo()
        val info = infoCopia(datos, zip)
        println("zip python: ${info.carpetas} nombre=${info.nombre} servidor=${info.servidor} runs=${info.runs} amigo=${info.amigo}")
        val r = importarCopiaDeAmigo(datos, zip, info.nombre.ifEmpty { "Amigo" }, info.servidor)
        println("importadas como amigo: ${r.nuevas}")
        assertEquals(info.runs, r.nuevas)
        val comps = construirComposiciones(cargarIndice(datos, r.carpeta).runs)
        println("composiciones del amigo: ${comps.size}")
        assertTrue(comps.isNotEmpty())
    }
}
