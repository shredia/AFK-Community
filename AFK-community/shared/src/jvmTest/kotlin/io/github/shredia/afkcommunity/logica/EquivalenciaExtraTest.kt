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
import io.github.shredia.afkcommunity.datos.s
import io.github.shredia.afkcommunity.datos.verdad
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.JsonObject
import java.io.File
import java.nio.file.Files
import java.nio.file.StandardCopyOption
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.time.Duration.Companion.minutes
import kotlin.time.ExperimentalTime

/**
 * Progreso semanal, Fractura temporal y perfil de roster contra la app Python
 * (casos de herramientas_migracion/generar_casos_extra.py). Sin casos, no hace nada.
 */
@OptIn(ExperimentalTime::class)
class EquivalenciaExtraTest {
    private val casos: List<File> = listOf(File("../casos_prueba"), File("casos_prueba"))
        .firstOrNull { it.isDirectory }?.listFiles()?.filter { File(it, "esperado/progreso.json").isFile }?.sortedBy { it.name }
        .orEmpty()
    private val raizNc = listOf(File("../.."), File("..")).first { File(it, "recursos/fractura_temporal_base.json").isFile }
    private val vis = Visuales(leerJsonTexto(File(raizNc, "recursos/assets/tablas_sitio.json").readText()).o())
    private val base = leerJsonTexto(File(raizNc, "recursos/fractura_temporal_base.json").readText()).o()

    private fun leer(f: File) = leerJsonTexto(f.readText())!!

    private fun copia(caso: File): Pair<Datos, String> {
        val raiz = Files.createTempDirectory("caso").toFile().apply { deleteOnExit() }
        val origen = File(caso, "entrada")
        origen.walkTopDown().forEach { f ->
            val d = File(raiz, "servidor/" + f.relativeTo(origen).path)
            if (f.isDirectory) d.mkdirs() else Files.copy(f.toPath(), d.toPath(), StandardCopyOption.COPY_ATTRIBUTES)
        }
        return Datos(AlmacenArchivos(raiz)) to "servidor"
    }

    private suspend fun comps(datos: Datos, carpeta: String): Pair<List<JsonObject>, List<Composicion>> {
        val runs = cargarIndice(datos, carpeta).runs
        val actual = cargarCuentaActual(datos, carpeta) ?: JsonObject(emptyMap())
        val lista = construirComposiciones(runs, actual["heroes_temporales"].a().map { it.py() }, arrendadosDe(actual))
        aplicarSpManual(lista, datos, carpeta)
        anotarEstrellas(lista, vis)
        return runs to lista
    }

    @Test fun progresoSemanal() = runTest(timeout = 5.minutes) {
        for (caso in casos) {
            val (datos, c) = copia(caso)
            val semanas = semanasDe(comps(datos, c).first)
            val esperadas = leer(File(caso, "esperado/progreso.json")).objetos()
            assertEquals(esperadas.size, semanas.size, caso.name)
            for ((e, s) in esperadas.zip(semanas)) {
                assertEquals(leerFecha(e["inicio"].s()), s.inicio, caso.name)
                assertEquals(e["jefes"].a().map { it.py() }, s.jefes, caso.name)
                assertEquals(e["runs"].int(), s.runs)
                assertEquals(e["completas"].int(), s.completas)
                assertEquals(e["mejor"].real(), s.mejor)
                assertEquals(e["teorico"].real(), s.teorico)
            }
        }
    }

    @Test fun fractura() = runTest {
        for (caso in casos) {
            val (datos, c) = copia(caso)
            val e = leer(File(caso, "esperado/fractura.json")).o()
            val bolsa = inventarioFractura(cargarCuentaActual(datos, c), base)
            assertEquals(e["bolsa"].o().mapValues { it.value.real() }, bolsa, "${caso.name}: bolsa")
            val calc = calcularFractura(base, cargarEstadoFractura(datos, c), bolsa)
            val ec = e["calculo"].o()
            val recursos = ec["recursos"].o()
            assertEquals(recursos.keys.toList(), calc.recursos.keys.toList(), "${caso.name}: recursos")
            for ((nombre, x) in calc.recursos) {
                val r = recursos[nombre].o()
                val campos = mapOf("pisos_obtenido" to x.pisosObtenido, "pisos_faltante" to x.pisosFaltante,
                    "tienda_comprado" to x.tiendaComprado, "tienda_planeado" to x.tiendaPlaneado,
                    "tienda_pendiente" to x.tiendaPendiente, "cofres_ahora" to x.cofresAhora,
                    "cofres_planeado" to x.cofresPlaneado, "hasta_meta" to x.hastaMeta, "conseguido" to x.conseguido,
                    "aun_obtenible" to x.aunObtenible, "plan_meta" to x.planMeta, "bolsa" to x.bolsa,
                    "tendras" to x.tendras, "tendras_final" to x.tendrasFinal)
                for ((k, v) in campos) assertEquals(r[k].real(), v, "${caso.name}: $nombre.$k")
            }
            for ((nombre, cofre) in calc.cofres) {
                val ce = ec["cofres"].o()[nombre].o()
                assertEquals(listOf("disponibles", "restantes", "usados_ahora", "gastados", "libres", "usados_planeados", "hasta_meta")
                    .map { ce[it].int() }, listOf(cofre.disponibles, cofre.restantes, cofre.usadosAhora, cofre.gastados,
                    cofre.libres, cofre.usadosPlaneados, cofre.hastaMeta), "${caso.name}: $nombre")
            }
            val m = ec["medallas"].o()
            assertEquals(listOf("ganadas", "por_ganar", "gastadas", "planeadas", "saldo", "saldo_final", "hasta_meta", "saldo_meta")
                .map { m[it].int().toLong() }, listOf(calc.medallas.ganadas, calc.medallas.porGanar, calc.medallas.gastadas,
                calc.medallas.planeadas, calc.medallas.saldo, calc.medallas.saldoFinal, calc.medallas.hastaMeta, calc.medallas.saldoMeta))
            assertEquals(ec["avisos"].a().map { it.py() }, calc.avisos, "${caso.name}: avisos")
            assertEquals(ec["siguiente"].o()["piso"].int(-1), calc.siguiente?.get("piso").int(-1))
        }
    }

    @Test fun roster() = runTest(timeout = 5.minutes) {
        val todos = casos.associate { caso -> caso.name to copia(caso).let { (d, c) -> Triple(d, c, comps(d, c).second) } }
        for (caso in casos) {
            val (datos, c, _) = todos.getValue(caso.name)
            val perfil = armarPerfil(cargarCuentaActual(datos, c), vis, cargarCorrecciones(datos, c))
            val e = leer(File(caso, "esperado/roster.json")).o()
            val ep = e["perfil"].o()
            assertEquals(ep["con_inventario"].verdad(), perfil.conInventario)
            assertEquals(ep["manuales"].int(), perfil.manuales)
            for (tipo in listOf("HEROE", "COLECCION", "MASCOTA")) {
                val esperado = ep[tipo].o()
                assertEquals(esperado.keys, perfil.de(tipo).keys, "${caso.name}: $tipo")
                for ((k, d) in perfil.de(tipo)) {
                    val x = esperado[k].o()
                    assertEquals(x["tengo"]?.verdad() ?: true, d.tengo, "$tipo $k")
                    for ((campo, v) in d.valores) assertEquals(if (x[campo].esNulo()) null else x[campo].int(), v, "$tipo $k $campo")
                }
            }
            val porClave = todos.filterKeys { it != caso.name }.flatMap { (nombre, t) -> t.third.map { (nombre to "${it.runId}|${it.posicion}") to it } }.toMap()
            val niveles = mapOf("ok" to Nivel.PUEDO, "casi" to Nivel.CASI, "no" to Nivel.NO_PUEDO)
            for (ev in e["evaluaciones"].objetos()) {
                val comp = porClave.getValue(ev["caso"].py() to "${ev["run_id"].py()}|${ev["posicion"].py()}")
                val (nivel, faltas) = evaluarEquipo(comp, perfil)
                val donde = "${caso.name} evalúa ${ev["run_id"].py()}#${ev["posicion"].py()}"
                assertEquals(niveles[ev["nivel"].s()], nivel, donde)
                assertEquals(ev["faltas"].a().map { it.py() }, faltas.map { it.texto }, donde)
            }
        }
    }
}
