package io.github.shredia.afkcommunity.ui.pantallas

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.github.shredia.afkcommunity.datos.Servidor
import io.github.shredia.afkcommunity.datos.listarServidores
import io.github.shredia.afkcommunity.idiomas.tr
import io.github.shredia.afkcommunity.logica.Semana
import io.github.shredia.afkcommunity.logica.cargarIndice
import io.github.shredia.afkcommunity.logica.formatoTiempo
import io.github.shredia.afkcommunity.logica.semanasDe
import io.github.shredia.afkcommunity.ui.Colores
import io.github.shredia.afkcommunity.ui.Desplegable
import io.github.shredia.afkcommunity.ui.EstadoApp
import io.github.shredia.afkcommunity.ui.Tarjeta
import io.github.shredia.afkcommunity.ui.Tenue
import io.github.shredia.afkcommunity.ui.Titulo
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

@Composable
fun PantallaProgreso(estado: EstadoApp) {
    var fuentes by remember { mutableStateOf<List<Servidor>>(emptyList()) }
    var carpeta by rememberSaveable { mutableStateOf<String?>(null) }
    var semanas by remember { mutableStateOf<List<Semana>?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    LaunchedEffect(estado.versionDatos) {
        fuentes = estado.datos.listarServidores()
        if (fuentes.none { it.carpeta == carpeta }) carpeta = estado.optimizador.carpeta?.takeIf { c -> fuentes.any { it.carpeta == c } }
            ?: fuentes.firstOrNull()?.carpeta
    }
    LaunchedEffect(carpeta, estado.versionDatos) {
        semanas = null
        error = null
        val c = carpeta ?: return@LaunchedEffect
        runCatching { withContext(Dispatchers.Default) { semanasDe(cargarIndice(estado.datos, c).runs) } }
            .onSuccess { semanas = it }.onFailure { error = it.message }
    }

    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        item {
            Titulo(tr("Progreso semanal"))
            Tenue(tr("Tu mejor run completa de cada semana (línea dorada) y la suma de tus mejores tiempos por jefe esa semana (línea gris: lo que harías juntando tus mejores equipos). Cada semana tiene jefes distintos."))
        }
        if (fuentes.isEmpty()) {
            item { Tenue(tr("No hay runs descargadas ni importadas.")) }
            return@LazyColumn
        }
        item { Desplegable(tr("Runs de:"), fuentes, fuentes.firstOrNull { it.carpeta == carpeta }, { it.etiqueta }, { carpeta = it.carpeta }) }
        error?.let { item { Text(tr("Error al cargar: {0}", it), color = Colores.ERR) } }
        val lista = semanas
        if (lista == null) {
            item { Tenue(tr("Cargando...")) }
            return@LazyColumn
        }
        item {
            Tenue(tr("{0} semanas · {1} con run completa", lista.size, lista.count { it.mejor != null }))
            Tarjeta { Grafico(lista) }
        }
        // «Última vez con estos jefes»: la semana anterior con la misma rotación
        val ultima = HashMap<List<String>, Semana>()
        val filas = lista.map { s ->
            val previa = ultima[s.jefes]
            if (s.mejor != null) ultima[s.jefes] = s
            s to previa?.takeIf { it.mejor != null && s.mejor != null }
        }
        items(filas.reversed()) { (s, previa) -> FilaSemana(estado, s, previa) }
    }
}

@Composable
private fun FilaSemana(estado: EstadoApp, s: Semana, previa: Semana?) {
    Tarjeta {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(s.fecha, fontWeight = FontWeight.SemiBold)
                Tenue(tr("{0}/{1} runs completas", s.completas, s.runs))
            }
            Column(horizontalAlignment = Alignment.End) {
                Text(formatoTiempo(s.mejor), color = Colores.DORADO, fontWeight = FontWeight.Bold)
                Tenue(tr("suma de mejores: {0}", formatoTiempo(s.teorico)))
            }
        }
        Tenue(s.jefes.joinToString(", ") { estado.nombreJefe(it) }, Modifier.padding(top = 4.dp))
        if (previa != null) {
            val d = s.mejor!! - previa.mejor!!
            Text(tr("Última vez con estos jefes: {0} ({1:+.3f} s)", previa.fecha, d), fontSize = 13.sp,
                color = if (d < 0) Colores.OK else if (d > 0) Colores.WARN else Colores.MUTED)
        }
    }
}

/** Mejor run (dorada) y suma de mejores (gris), semana a semana. Arriba = más rápido. */
@Composable
private fun Grafico(semanas: List<Semana>) {
    val datos = semanas.filter { it.mejor != null || it.teorico != null }
    if (datos.isEmpty()) {
        Tenue(tr("Sin runs completas todavía."))
        return
    }
    val medidor = rememberTextMeasurer()
    val estilo = TextStyle(color = Colores.MUTED, fontSize = 10.sp)
    Canvas(Modifier.fillMaxWidth().height(220.dp)) {
        val izq = 70.dp.toPx(); val der = 12.dp.toPx(); val arr = 18.dp.toPx(); val aba = 22.dp.toPx()
        val valores = datos.flatMap { listOfNotNull(it.mejor, it.teorico) }
        var vmin = valores.min(); var vmax = valores.max()
        val margen = maxOf(1.0, (vmax - vmin) * 0.1)
        vmin -= margen; vmax += margen
        val n = datos.size
        fun x(i: Int) = izq + (size.width - izq - der) * (if (n > 1) i.toFloat() / (n - 1) else 0.5f)
        fun y(v: Double) = arr + (size.height - arr - aba) * ((v - vmin) / (vmax - vmin)).toFloat()
        for (k in 0..4) {
            val v = vmin + (vmax - vmin) * k / 4
            val yy = y(v)
            drawLine(Colores.BORDE, Offset(izq, yy), Offset(size.width - der, yy))
            val t = medidor.measure(formatoTiempo(v), estilo)
            drawText(t, topLeft = Offset(izq - t.size.width - 6, yy - t.size.height / 2))
        }
        val paso = maxOf(1, n / 6)
        for ((i, s) in datos.withIndex()) {
            if (i % paso == 0 || i == n - 1) {
                val t = medidor.measure(s.fechaCorta, estilo)
                drawText(t, topLeft = Offset(x(i) - t.size.width / 2, size.height - aba + 4))
            }
        }
        for ((valor, color, grosor) in listOf(Triple({ s: Semana -> s.teorico }, Colores.TENUE, 2f), Triple({ s: Semana -> s.mejor }, Colores.DORADO, 3f))) {
            val puntos = datos.withIndex().mapNotNull { (i, s) -> valor(s)?.let { Offset(x(i), y(it)) } }
            if (puntos.size > 1) {
                val camino = Path().apply { moveTo(puntos[0].x, puntos[0].y); puntos.drop(1).forEach { lineTo(it.x, it.y) } }
                drawPath(camino, color, style = Stroke(width = grosor.dp.toPx()))
            }
            for (p in puntos) drawCircle(color, radius = (if (color == Colores.DORADO) 4 else 3).dp.toPx(), center = p)
        }
        drawText(medidor.measure(tr("↑ más rápido"), estilo), topLeft = Offset(izq, 0f))
    }
}
