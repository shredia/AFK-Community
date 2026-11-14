package io.github.shredia.afkcommunity.logica

import io.github.shredia.afkcommunity.datos.entero
import io.github.shredia.afkcommunity.datos.o
import io.github.shredia.afkcommunity.datos.objetos
import io.github.shredia.afkcommunity.datos.py
import io.github.shredia.afkcommunity.datos.real
import io.github.shredia.afkcommunity.datos.s
import io.github.shredia.afkcommunity.datos.verdad
import kotlinx.datetime.TimeZone
import kotlinx.datetime.toLocalDateTime
import kotlinx.serialization.json.JsonObject
import kotlin.time.ExperimentalTime
import kotlin.time.Instant

/*
 * Progreso semanal (port de semanas_de en aplicacion/seccion_progreso.py): tu mejor run completa de cada semana y
 * la suma de tus mejores tiempos por jefe esa semana.
 */

@OptIn(ExperimentalTime::class)
class Semana(
    val inicio: Instant,
    val jefes: List<String>,
    val runs: Int,
    val completas: Int,
    /** Mejor run completa (segundos), o null. */
    val mejor: Double?,
    /** Suma de tus mejores tiempos por jefe esa semana (si los 6 tienen tiempo), o null. */
    val teorico: Double?,
) {
    /** "14/11/2026" en la hora local. */
    val fecha: String get() {
        val d = inicio.toLocalDateTime(TimeZone.currentSystemDefault()).date
        return "${d.day.toString().padStart(2, '0')}/${d.month.ordinal.plus(1).toString().padStart(2, '0')}/${d.year}"
    }
    val fechaCorta: String get() = fecha.take(5)
}

/** Agrupa las runs por semana de NC: misma rotación (los 6 jefes) y dentro de 7 días. */
@OptIn(ExperimentalTime::class)
fun semanasDe(runs: List<JsonObject>): List<Semana> {
    class Actual(val inicio: Instant, val conjunto: Set<String>) {
        var runs = 0; var completas = 0; var mejor: Double? = null
        val porJefe = LinkedHashMap<String, Double>()
    }
    val lista = runs.mapNotNull { r ->
        val f = leerFecha(r["playedAt"].s()) ?: return@mapNotNull null
        val jefes = r["rounds"].objetos().map { it["bossId"].py() }
        if (jefes.isEmpty()) null else Triple(f, r, jefes.toSet())
    }.sortedBy { it.first }
    val semanas = mutableListOf<Actual>()
    for ((f, r, conjunto) in lista) {
        var actual = semanas.lastOrNull()
        if (actual == null || actual.conjunto != conjunto || (f - actual.inicio).inWholeDays >= 7) {
            actual = Actual(f, conjunto)
            semanas += actual
        }
        actual.runs++
        val res = r["result"].o()
        if (res["bossesKilled"].entero(null) == 6L && res["timeMs"].verdad()) {
            actual.completas++
            val total = res["timeMs"].real()!! / 1000
            actual.mejor = actual.mejor?.let { minOf(it, total) } ?: total
        }
        for (ronda in r["rounds"].objetos()) {
            val rec = ronda["recorded"].o()
            if (rec["bossesKilled"].entero(null) == 1L && rec["timeMs"].verdad()) {
                val b = ronda["bossId"].py()
                val t = rec["timeMs"].real()!! / 1000
                actual.porJefe[b] = minOf(actual.porJefe[b] ?: t, t)
            }
        }
    }
    return semanas.map { s ->
        Semana(s.inicio, s.conjunto.sortedWith(compareBy({ it.length }, { it })), s.runs, s.completas, s.mejor,
            if (s.porJefe.size == s.conjunto.size && s.conjunto.size == 6) sumaPy(s.porJefe.values) else null)
    }
}

/**
 * sum() de Python (3.12+) para decimales: suma compensada de Neumaier, como builtin_sum_impl de CPython.
 * Con una suma normal, 117.847 sale 117.84700000000001.
 */
fun sumaPy(valores: Iterable<Double>): Double {
    var resultado = 0.0
    var c = 0.0
    for (x in valores) {
        val t = resultado + x
        c += if (kotlin.math.abs(resultado) >= kotlin.math.abs(x)) (resultado - t) + x else (x - t) + resultado
        resultado = t
    }
    if (c != 0.0 && c.isFinite()) resultado += c
    return resultado
}
