package io.github.shredia.afkcommunity.logica

import io.github.shredia.afkcommunity.datos.AlmacenArchivos
import io.github.shredia.afkcommunity.datos.Datos
import io.github.shredia.afkcommunity.datos.a
import io.github.shredia.afkcommunity.datos.esNulo
import io.github.shredia.afkcommunity.datos.int
import io.github.shredia.afkcommunity.datos.leerJsonTexto
import io.github.shredia.afkcommunity.datos.o
import io.github.shredia.afkcommunity.datos.objetos
import io.github.shredia.afkcommunity.datos.py
import io.github.shredia.afkcommunity.datos.real
import io.github.shredia.afkcommunity.datos.verdad
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.JsonObject
import java.io.File
import java.nio.file.Files
import java.nio.file.StandardCopyOption
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import kotlin.time.Duration.Companion.minutes

/**
 * Equivalencia con la app Python: casos_prueba/<cuenta>_<servidor>/ (los genera
 * herramientas_migracion/generar_casos.py). Si no hay casos (no se suben a git), la prueba no hace nada.
 */
class EquivalenciaOptimizadorTest {

    private val casos: List<File> = listOf(File("../casos_prueba"), File("casos_prueba"))
        .firstOrNull { it.isDirectory }?.listFiles()?.filter { File(it, "esperado").isDirectory }?.sortedBy { it.name }
        .orEmpty()

    /** Copia entrada/ a una carpeta temporal conservando las fechas (como shutil.copytree). */
    private fun copiaDeTrabajo(caso: File): Pair<Datos, String> {
        val raiz = Files.createTempDirectory("caso").toFile().apply { deleteOnExit() }
        val destino = File(raiz, "servidor")
        val origen = File(caso, "entrada")
        origen.walkTopDown().forEach { f ->
            val d = File(destino, f.relativeTo(origen).path)
            if (f.isDirectory) d.mkdirs()
            else Files.copy(f.toPath(), d.toPath(), StandardCopyOption.COPY_ATTRIBUTES, StandardCopyOption.REPLACE_EXISTING)
        }
        return Datos(AlmacenArchivos(raiz)) to "servidor"
    }

    private fun leer(f: File) = leerJsonTexto(f.readText())!!

    private suspend fun composiciones(datos: Datos, carpeta: String, runs: List<JsonObject>): List<Composicion> {
        val actual = datos.leerObjeto("$carpeta/cuenta_actual.json") ?: JsonObject(emptyMap())
        val comps = construirComposiciones(runs, actual["heroes_temporales"].a().map { it.py() }, arrendadosDe(actual))
        aplicarSpManual(comps, datos, carpeta)
        return comps
    }

    @Test fun indiceYComposiciones() = runTest(timeout = 10.minutes) {
        for (caso in casos) {
            val (datos, carpeta) = copiaDeTrabajo(caso)
            val indice = cargarIndice(datos, carpeta)
            val esperadoRuns = leer(File(caso, "esperado/indice.json")).o()["runs"].objetos()
            assertEquals(esperadoRuns.map { it["id"].py() }, indice.runs.map { it["id"].py() }, "${caso.name}: orden de runs")

            val comps = composiciones(datos, carpeta, indice.runs)
            val esperadas = leer(File(caso, "esperado/composiciones.json")).objetos()
            assertEquals(esperadas.size, comps.size, "${caso.name}: número de composiciones")
            for ((e, c) in esperadas.zip(comps)) {
                val donde = "${caso.name} ${c.runId}#${c.posicion}"
                assertEquals(e["run_id"].py(), c.runId, donde)
                assertEquals(e["posicion"].int(), c.posicion, donde)
                assertEquals(e["boss_id"].py(), c.bossId, donde)
                assertEquals(e["tiempo"].real(), c.tiempo, donde)
                assertEquals(e["derrotado"].verdad(), c.derrotado, donde)
                assertEquals(e["run_completa"].verdad(), c.runCompleta, donde)
                assertEquals(if (e["golden"].esNulo()) null else e["golden"].py(), c.golden?.takeUnless { it.esNulo() }?.py(), donde)
                assertEquals(e["hero_ids"].a().map { it.py() }, c.heroIds, donde)
                assertEquals(e["hero_origenes"].a().map { it.py() }, c.heroOrigenes, donde)
                assertEquals(e["mascota_id"].py(), c.mascotaId, donde)
                assertEquals(e["sp_manual"].verdad(), c.spManual, donde)
                assertEquals(e["firma"].py(), c.firma, donde)
            }
        }
    }

    /** Sin optimizador_indice.json: el índice se arma desde los detalles y debe dar las mismas runs. */
    @Test fun indiceDesdeCero() = runTest(timeout = 10.minutes) {
        for (caso in casos) {
            val (datos, carpeta) = copiaDeTrabajo(caso)
            datos.almacen.borrar("$carpeta/$ARCHIVO_INDICE")
            val indice = cargarIndice(datos, carpeta)
            val esperado = leer(File(caso, "esperado/indice.json")).o()["runs"].objetos().associateBy { it["id"].py() }
            assertEquals(esperado.keys, indice.runs.map { it["id"].py() }.toSet(), caso.name)
            for (run in indice.runs) assertEquals(esperado[run["id"].py()], run, "${caso.name}: run ${run["id"].py()}")
            assertTrue(datos.almacen.existe("$carpeta/$ARCHIVO_INDICE"))
            // la segunda vez se usa el índice guardado: las mismas runs
            assertEquals(indice.runs, cargarIndice(datos, carpeta).runs)
        }
    }

    @Test fun optimizacion() = runTest(timeout = 10.minutes) {
        for (caso in casos) {
            val (datos, carpeta) = copiaDeTrabajo(caso)
            val indice = cargarIndice(datos, carpeta)
            val comps = composiciones(datos, carpeta, indice.runs)
            val esperado = leer(File(caso, "esperado/optimizacion.json")).o()
            val rotacion = esperado["rotacion"].a().map { it.py() }
            assertEquals(rotacion, rotacionMasReciente(indice.runs), "${caso.name}: rotación")
            val reglas = esperado["bloqueos"].objetos()
            for ((nombre, variante) in esperado["casos"].o()) {
                val v = variante.o()
                val o = v["opciones"].o()
                val opciones = Opciones(
                    soloCompletas = o["solo_completas"].verdad(),
                    prohibirRepetirMascota = o["prohibir_repetir_mascota"].verdad(),
                    limitePorJefe = o["limite_por_jefe"].int(),
                    tiempoMaximo = o["tiempo_maximo"].real()!!,
                    excluirTemporales = o["excluir_temporales"].verdad(),
                    excluirFueraRoster = o["excluir_fuera_roster"].verdad(),
                )
                val res = optimizar(comps, rotacion, opciones, if (v["con_bloqueos"].verdad()) reglas else emptyList())
                val e = v["resultado"].o()
                val donde = "${caso.name} · $nombre"
                assertEquals(e["estado"].py(), res.estado, donde)
                assertEquals(e["detalle"].py(), res.detalle, donde)
                assertEquals(e["total"].real()!!, res.total, 1e-9, donde)
                assertEquals(e["consideradas"].int(), res.consideradas, donde)
                fun ref(c: Composicion) = listOf(c.runId, c.posicion.toString(), c.tiempo.toString(), c.firma, c.veces.toString())
                fun refE(x: JsonObject) = listOf(x["run_id"].py(), x["posicion"].py(), x["tiempo"].real().toString(),
                    x["firma"].py(), x["veces"].py())
                assertEquals(e["elegidas"].objetos().map(::refE), res.elegidas.map(::ref), "$donde: equipos elegidos")
                for ((pos, lista) in e["candidatos"].o()) {
                    assertEquals(lista.objetos().map(::refE), res.candidatos[pos.toInt()].orEmpty().map(::ref),
                        "$donde: candidatos del jefe $pos")
                }
            }
        }
    }
}
