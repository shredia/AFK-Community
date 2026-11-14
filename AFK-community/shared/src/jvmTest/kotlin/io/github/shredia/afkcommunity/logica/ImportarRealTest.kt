package io.github.shredia.afkcommunity.logica

import io.github.shredia.afkcommunity.datos.AlmacenArchivos
import io.github.shredia.afkcommunity.datos.Datos
import kotlinx.coroutines.test.runTest
import java.io.File
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.time.Duration.Companion.minutes

/**
 * Importa archivos reales del sitio en una carpeta vacía, para compararla con lo que hace la app Python.
 * Solo corre si existen las variables AFK_IMPORTAR_ORIGEN (carpeta con afk-inventory.json y afk-runs.json) y
 * AFK_IMPORTAR_DESTINO (carpeta de datos nueva). Corre con la memoria por defecto de la JVM de pruebas (512 MB),
 * menos de la que tiene un teléfono.
 */
class ImportarRealTest {
    @Test fun importaInventarioYRuns() = runTest(timeout = 10.minutes) {
        val origen = System.getenv("AFK_IMPORTAR_ORIGEN")?.let(::File) ?: return@runTest
        val destino = File(System.getenv("AFK_IMPORTAR_DESTINO") ?: return@runTest)
        destino.deleteRecursively()
        destino.mkdirs()
        val datos = Datos(AlmacenArchivos(destino))

        val inv = detectar("afk-inventory.json", File(origen, "afk-inventory.json").readBytes(), false)
        assertEquals(TipoArchivo.INVENTARIO, inv.tipo)
        val r1 = importarInventario(datos, inv.datos!!, null, "Prueba")
        println("inventario: ${r1.carpeta} ${r1.heroes} heroes, ${r1.colecciones} colecciones, ${r1.objetos} objetos")

        val runs = detectar("afk-runs.json", File(origen, "afk-runs.json").readBytes(), false)
        assertEquals(TipoArchivo.RUNS, runs.tipo)
        val info = analizarRuns(datos, runs.runs!!)
        println("analisis: nc=${info.nc} otros=${info.otros} ${info.desde}..${info.hasta} conIds=${info.conIds} sugerida=${info.sugerida} motivo=${info.motivo}")
        val r2 = importarRuns(datos, runs.runs, r1.carpeta, null)
        println("runs: nuevas=${r2.nuevas} ya=${r2.yaEstaban} otros=${r2.otrosModos}")
        val mb = (Runtime.getRuntime().maxMemory() / 1_000_000)
        println("memoria maxima de la JVM: $mb MB")
    }
}
